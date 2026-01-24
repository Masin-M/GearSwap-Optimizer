"""
GearSwap Lua Parser

Parses existing GearSwap Lua files to extract set definitions,
identify placeholder sets, and enable in-place updates.

Phase 3 of the GearSwap Optimizer project.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set, Union

from pathlib import Path

from models import (
    Slot, Job, GearSet, ItemInstance, OptimizationProfile,
    Stats,
)
from ws_database import get_weaponskill, WeaponskillData
from optimizer_ui import TPSetType, create_tp_profile

# Import greedy optimizer for JA and idle/DT sets
try:
    from greedy_optimizer import (
        JAEnhancementIndex,
        run_ja_optimization,
    )
    HAS_GREEDY_OPTIMIZER = True
except ImportError:
    HAS_GREEDY_OPTIMIZER = False
    JAEnhancementIndex = None


# =============================================================================
# Dual Wield Detection
# =============================================================================

# Jobs that natively dual wield
DUAL_WIELD_JOBS = {'NIN', 'DNC', 'BLU'}

# Jobs that can sub for dual wield
DUAL_WIELD_SUBJOBS = {'NIN', 'DNC'}

# 1H weapon types that can be dual wielded
DUAL_WIELD_WEAPON_TYPES = {'Sword', 'Dagger', 'Club', 'Katana', 'Axe'}


def detect_dual_wield(job: Optional[Job], 
                      sub_job: Optional[str] = None,
                      main_weapon: Optional[Dict] = None,
                      sub_weapon: Optional[Dict] = None) -> bool:
    """
    Detect if the current setup uses dual wield.
    
    Args:
        job: Main job
        sub_job: Sub job abbreviation (e.g., 'NIN')
        main_weapon: Main weapon dict with 'Skill Type' key
        sub_weapon: Sub weapon dict with 'Skill Type' or 'Type' key
        
    Returns:
        True if dual wielding, False otherwise
    """
    if job is None:
        return False
    
    job_name = job.name.upper()
    
    # Check if job or subjob can dual wield
    can_dual_wield = (
        job_name in DUAL_WIELD_JOBS or 
        (sub_job and sub_job.upper() in DUAL_WIELD_SUBJOBS)
    )
    
    if not can_dual_wield:
        return False
    
    # If we have weapon info, verify both are 1H weapons
    if main_weapon and sub_weapon:
        main_skill = main_weapon.get('Skill Type', '')
        sub_type = sub_weapon.get('Type', '')
        sub_skill = sub_weapon.get('Skill Type', '')
        
        # Sub must be a weapon (not shield/grip)
        if sub_type != 'Weapon':
            return False
        
        # Both must be dual-wieldable weapon types
        if main_skill not in DUAL_WIELD_WEAPON_TYPES:
            return False
        if sub_skill and sub_skill not in DUAL_WIELD_WEAPON_TYPES:
            return False
        
        return True
    
    # If no weapon info, assume DW based on job capability
    return can_dual_wield


# =============================================================================
# Slot Name Mappings
# =============================================================================

LUA_TO_SLOT = {
    'main': Slot.MAIN,
    'sub': Slot.SUB,
    'range': Slot.RANGE,
    'ammo': Slot.AMMO,
    'head': Slot.HEAD,
    'neck': Slot.NECK,
    'ear1': Slot.LEFT_EAR,
    'ear2': Slot.RIGHT_EAR,
    'left_ear': Slot.LEFT_EAR,
    'right_ear': Slot.RIGHT_EAR,
    'body': Slot.BODY,
    'hands': Slot.HANDS,
    'ring1': Slot.LEFT_RING,
    'ring2': Slot.RIGHT_RING,
    'left_ring': Slot.LEFT_RING,
    'right_ring': Slot.RIGHT_RING,
    'back': Slot.BACK,
    'waist': Slot.WAIST,
    'legs': Slot.LEGS,
    'feet': Slot.FEET,
}

SLOT_TO_LUA = {
    Slot.MAIN: 'main',
    Slot.SUB: 'sub',
    Slot.RANGE: 'range',
    Slot.AMMO: 'ammo',
    Slot.HEAD: 'head',
    Slot.NECK: 'neck',
    Slot.LEFT_EAR: 'ear1',
    Slot.RIGHT_EAR: 'ear2',
    Slot.BODY: 'body',
    Slot.HANDS: 'hands',
    Slot.LEFT_RING: 'ring1',
    Slot.RIGHT_RING: 'ring2',
    Slot.BACK: 'back',
    Slot.WAIST: 'waist',
    Slot.LEGS: 'legs',
    Slot.FEET: 'feet',
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class LuaItem:
    """Represents an item in a Lua gear set."""
    name: str                               # Item name
    augments: Optional[List[str]] = None    # Augment strings if present
    is_augmented: bool = False              # True if uses {name=..., augments=...} syntax
    raw_text: str = ""                      # Original Lua text for preservation


@dataclass
class LuaSetDefinition:
    """Represents a parsed gear set from Lua."""
    name: str                               # Full name: "sets.engaged.DT"
    path: List[str] = field(default_factory=list)  # Path parts: ["sets", "engaged", "DT"]
    items: Dict[str, LuaItem] = field(default_factory=dict)  # slot_name -> LuaItem
    base_set: Optional[str] = None          # Base set if uses set_combine
    is_placeholder: bool = False            # Has PLACEHOLDER comment
    placeholder_context: str = ""           # Text after "PLACEHOLDER:" if any
    line_start: int = 0                     # Starting line in source file
    line_end: int = 0                       # Ending line in source file
    raw_text: str = ""                      # Original Lua text
    indent: str = "    "                    # Detected indentation


@dataclass
class GearSwapFile:
    """Parsed GearSwap Lua file."""
    filepath: str
    sets: Dict[str, LuaSetDefinition] = field(default_factory=dict)
    mode_options: Dict[str, List[str]] = field(default_factory=dict)
    job: Optional[str] = None               # Detected job (from filename/comments)
    raw_content: str = ""                   # Original file content
    lines: List[str] = field(default_factory=list)  # Content split into lines


# =============================================================================
# Parser Class
# =============================================================================

class LuaParser:
    """
    Parser for GearSwap Lua files.
    
    Extracts set definitions, items, and placeholders.
    """
    
    # Regex patterns for set definitions
    # 
    # These patterns need to handle various GearSwap naming conventions:
    # - Pure dot notation: sets.idle.DT
    # - Bracket at end: sets.WS['Savage Blade']
    # - Mixed (bracket in middle): sets.midcast['Elemental Magic'].Resistant
    # - Mixed (bracket in middle): sets.midcast['Elemental Magic'].MB
    #
    # The key insight is that bracket notation can appear ANYWHERE in the path,
    # and can be followed by more dot notation for variants like .Resistant, .MB, etc.
    
    # Path segment patterns (reusable components)
    # A segment is either .identifier or ['string'] or ["string"]
    _DOT_SEGMENT = r'\.[a-zA-Z_][a-zA-Z0-9_]*'
    _BRACKET_SINGLE = r"\['[^']+'\]"
    _BRACKET_DOUBLE = r'\["[^"]+"\]'
    _ANY_SEGMENT = rf'(?:{_DOT_SEGMENT}|{_BRACKET_SINGLE}|{_BRACKET_DOUBLE})'
    
    # Pattern 1: Simple dot notation - sets.idle = { ... }
    # Kept for backwards compatibility, but PATTERN_MIXED handles this too
    PATTERN_DOT = re.compile(
        r'^(\s*)(sets(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+)\s*=\s*\{',
        re.MULTILINE
    )
    
    # Pattern 2: Bracket notation with single quotes - sets.WS['Entropy'] = { ... }
    # Now also matches sets.midcast['Elemental Magic'].Resistant = { ... }
    PATTERN_BRACKET_SINGLE = re.compile(
        rf"^(\s*)(sets(?:{_ANY_SEGMENT})*\['[^']+'\](?:{_DOT_SEGMENT})*)\s*=\s*\{{",
        re.MULTILINE
    )
    
    # Pattern 3: Bracket notation with double quotes - sets.WS["Cross Reaper"] = { ... }
    # Now also matches sets.midcast["Elemental Magic"].MB = { ... }
    PATTERN_BRACKET_DOUBLE = re.compile(
        rf'^(\s*)(sets(?:{_ANY_SEGMENT})*\["[^"]+"\](?:{_DOT_SEGMENT})*)\s*=\s*\{{',
        re.MULTILINE
    )
    
    # Pattern 4: set_combine - sets.idle.DT = set_combine(sets.idle, { ... })
    PATTERN_SET_COMBINE = re.compile(
        r'^(\s*)(sets(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+)\s*=\s*set_combine\s*\(\s*(sets[^,]+)\s*,\s*\{',
        re.MULTILINE
    )
    
    # Pattern 4b: set_combine with bracket notation (bracket anywhere in path)
    # Matches: sets.midcast['Elemental Magic'].MB = set_combine(...)
    PATTERN_SET_COMBINE_BRACKET = re.compile(
        rf"^(\s*)(sets(?:{_ANY_SEGMENT})*(?:\['[^']+'\]|\[\"[^\"]+\"\])(?:{_DOT_SEGMENT})*)\s*=\s*set_combine\s*\(\s*(sets[^,]+)\s*,\s*\{{",
        re.MULTILINE
    )
    
    # Pattern for mode options - state.OffenseMode:options('Normal', 'Acc')
    PATTERN_MODE_OPTIONS = re.compile(
        r"state\.(\w+):options\s*\(([^)]+)\)"
    )
    
    # Pattern for simple item - head="Nyame Helm"
    PATTERN_SIMPLE_ITEM = re.compile(
        r'([a-z_][a-z0-9_]*)\s*=\s*"([^"]+)"'
    )
    
    # Pattern for augmented item - head={ name="Odyssean Helm", augments={'Acc+25','STR+10'}}
    PATTERN_AUGMENTED_ITEM = re.compile(
        r"([a-z_][a-z0-9_]*)\s*=\s*\{\s*name\s*=\s*\"([^\"]+)\"\s*,\s*augments\s*=\s*\{([^}]+)\}\s*\}"
    )
    
    # Pattern for placeholder comment
    PATTERN_PLACEHOLDER = re.compile(
        r'--\s*PLACEHOLDER(?:\s*:\s*(.+))?',
        re.IGNORECASE
    )
    
    def __init__(self):
        self.current_file: Optional[GearSwapFile] = None
    
    def parse_file(self, filepath: str) -> GearSwapFile:
        """
        Parse a GearSwap Lua file.
        
        Args:
            filepath: Path to the .lua file
            
        Returns:
            GearSwapFile with all parsed data
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return self.parse_content(content, filepath)
    
    def parse_content(self, content: str, filepath: str = "<string>") -> GearSwapFile:
        """
        Parse GearSwap Lua content from a string.
        
        Args:
            content: Lua file content
            filepath: Original filepath (for reference)
            
        Returns:
            GearSwapFile with all parsed data
        """
        gsfile = GearSwapFile(
            filepath=filepath,
            raw_content=content,
            lines=content.splitlines(keepends=True),
        )
        self.current_file = gsfile
        
        # Detect job from filename
        gsfile.job = self._detect_job(filepath, content)
        
        # Parse mode options
        gsfile.mode_options = self._parse_mode_options(content)
        
        # Parse all set definitions
        gsfile.sets = self._parse_all_sets(content)
        
        return gsfile
    
    def _detect_job(self, filepath: str, content: str) -> Optional[str]:
        """Detect job from filename or content."""
        # Check filename (e.g., "DRK.lua", "THF_gear.lua")
        filename = Path(filepath).stem.upper()
        job_names = ['WAR', 'MNK', 'WHM', 'BLM', 'RDM', 'THF', 'PLD', 'DRK',
                     'BST', 'BRD', 'RNG', 'SAM', 'NIN', 'DRG', 'SMN', 'BLU',
                     'COR', 'PUP', 'DNC', 'SCH', 'GEO', 'RUN']
        
        for job in job_names:
            if job in filename:
                return job
        
        # Check content for job hints
        job_pattern = re.compile(r'(?:job|player\.main_job)\s*[=:]\s*[\'"]?(\w{3})[\'"]?', re.IGNORECASE)
        match = job_pattern.search(content)
        if match:
            return match.group(1).upper()
        
        return None
    
    def _parse_mode_options(self, content: str) -> Dict[str, List[str]]:
        """Parse state mode options."""
        modes = {}
        
        for match in self.PATTERN_MODE_OPTIONS.finditer(content):
            mode_name = match.group(1)
            options_str = match.group(2)
            
            # Parse options - handle both 'Option' and "Option" formats
            options = re.findall(r"['\"]([^'\"]+)['\"]", options_str)
            modes[mode_name] = options
        
        return modes
    
    def _parse_all_sets(self, content: str) -> Dict[str, LuaSetDefinition]:
        """Parse all set definitions from content."""
        sets = {}
        
        # Find all set definition starting points
        set_starts = []
        
        # Check set_combine patterns first (more specific)
        for match in self.PATTERN_SET_COMBINE.finditer(content):
            indent, set_name, base_set = match.groups()
            set_starts.append((match.start(), match.end(), indent, set_name, base_set.strip()))
        
        for match in self.PATTERN_SET_COMBINE_BRACKET.finditer(content):
            indent, set_name, base_set = match.groups()
            set_starts.append((match.start(), match.end(), indent, set_name, base_set.strip()))
        
        # Then regular patterns
        for match in self.PATTERN_DOT.finditer(content):
            indent, set_name = match.groups()
            # Skip if this position already matched a set_combine
            if not any(s[0] == match.start() for s in set_starts):
                set_starts.append((match.start(), match.end(), indent, set_name, None))
        
        for match in self.PATTERN_BRACKET_SINGLE.finditer(content):
            indent, set_name = match.groups()
            if not any(s[0] == match.start() for s in set_starts):
                set_starts.append((match.start(), match.end(), indent, set_name, None))
        
        for match in self.PATTERN_BRACKET_DOUBLE.finditer(content):
            indent, set_name = match.groups()
            if not any(s[0] == match.start() for s in set_starts):
                set_starts.append((match.start(), match.end(), indent, set_name, None))
        
        # Sort by position
        set_starts.sort(key=lambda x: x[0])
        
        # Parse each set
        for i, (start_pos, header_end, indent, set_name, base_set) in enumerate(set_starts):
            # Find the matching closing brace
            end_pos = self._find_closing_brace(content, header_end - 1)
            
            if end_pos == -1:
                continue  # Malformed set, skip
            
            # Extract raw text
            raw_text = content[start_pos:end_pos + 1]
            
            # Calculate line numbers
            line_start = content[:start_pos].count('\n') + 1
            line_end = content[:end_pos].count('\n') + 1
            
            # Parse items within the set
            items = self._parse_items(raw_text)
            
            # Check for placeholder
            is_placeholder, placeholder_context = self._check_placeholder(raw_text)
            
            # Parse path from set name
            path = self._parse_set_path(set_name)
            
            set_def = LuaSetDefinition(
                name=set_name,
                path=path,
                items=items,
                base_set=base_set,
                is_placeholder=is_placeholder,
                placeholder_context=placeholder_context,
                line_start=line_start,
                line_end=line_end,
                raw_text=raw_text,
                indent=indent,
            )
            
            sets[set_name] = set_def
        
        return sets
    
    def _find_closing_brace(self, content: str, start: int) -> int:
        """Find the matching closing brace for an opening brace."""
        depth = 0
        i = start
        
        while i < len(content):
            char = content[i]
            
            # Skip strings
            if char == '"':
                i += 1
                while i < len(content) and content[i] != '"':
                    if content[i] == '\\':
                        i += 1  # Skip escaped char
                    i += 1
            elif char == "'":
                i += 1
                while i < len(content) and content[i] != "'":
                    if content[i] == '\\':
                        i += 1
                    i += 1
            # Skip comments
            elif char == '-' and i + 1 < len(content) and content[i + 1] == '-':
                # Skip to end of line
                while i < len(content) and content[i] != '\n':
                    i += 1
            elif char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    return i
            
            i += 1
        
        return -1  # Not found
    
    def _parse_items(self, set_text: str) -> Dict[str, LuaItem]:
        """Parse items from a set definition."""
        items = {}
        
        # Find augmented items first (more specific pattern)
        augmented_spans = []  # Track exact spans of augmented item matches
        for match in self.PATTERN_AUGMENTED_ITEM.finditer(set_text):
            slot_name = match.group(1)
            item_name = match.group(2)
            augments_str = match.group(3)
            
            # Parse augments
            augments = re.findall(r"['\"]([^'\"]+)['\"]", augments_str)
            
            items[slot_name] = LuaItem(
                name=item_name,
                augments=augments,
                is_augmented=True,
                raw_text=match.group(0),
            )
            augmented_spans.append((match.start(), match.end()))
        
        # Find simple items (skip positions within augmented item matches)
        for match in self.PATTERN_SIMPLE_ITEM.finditer(set_text):
            slot_name = match.group(1)
            item_name = match.group(2)
            
            # Skip if this match is inside an augmented item span
            match_pos = match.start()
            inside_augmented = any(start <= match_pos < end for start, end in augmented_spans)
            if inside_augmented:
                continue
            
            # Skip if we already have this slot (from augmented item)
            if slot_name in items:
                continue
            
            # Skip the "name" key inside augmented items (extra safety)
            if slot_name == 'name':
                continue
            
            items[slot_name] = LuaItem(
                name=item_name,
                augments=None,
                is_augmented=False,
                raw_text=match.group(0),
            )
        
        return items
    
    def _check_placeholder(self, set_text: str) -> Tuple[bool, str]:
        """Check if set has a PLACEHOLDER comment."""
        match = self.PATTERN_PLACEHOLDER.search(set_text)
        if match:
            context = match.group(1) or ""
            return True, context.strip()
        
        # Also check for empty sets (no items)
        # A set with only comments/whitespace is effectively a placeholder
        items = self._parse_items(set_text)
        if not items:
            return True, ""
        
        return False, ""
    
    def _parse_set_path(self, set_name: str) -> List[str]:
        """Parse set name into path components."""
        # Handle bracket notation
        # sets.WS['Entropy'] -> ['sets', 'WS', 'Entropy']
        
        path = []
        current = ""
        in_bracket = False
        bracket_char = None
        
        i = 0
        while i < len(set_name):
            char = set_name[i]
            
            if char == '.' and not in_bracket:
                if current:
                    path.append(current)
                    current = ""
            elif char == '[':
                if current:
                    path.append(current)
                    current = ""
                in_bracket = True
                # Look for quote type
                if i + 1 < len(set_name) and set_name[i + 1] in '"\'':
                    bracket_char = set_name[i + 1]
                    i += 1  # Skip the quote
            elif char == ']':
                if current:
                    path.append(current)
                    current = ""
                in_bracket = False
                bracket_char = None
            elif in_bracket and bracket_char and char == bracket_char:
                # End quote in bracket
                pass
            else:
                current += char
            
            i += 1
        
        if current:
            path.append(current)
        
        return path


# =============================================================================
# Helper Functions
# =============================================================================

def find_placeholder_sets(gsfile: GearSwapFile) -> List[LuaSetDefinition]:
    """
    Find all sets marked with PLACEHOLDER comments.
    
    Args:
        gsfile: Parsed GearSwap file
        
    Returns:
        List of set definitions that need optimization
    """
    placeholders = []
    
    for set_def in gsfile.sets.values():
        if set_def.is_placeholder:
            placeholders.append(set_def)
    
    return placeholders


def resolve_set_combine(gsfile: GearSwapFile, 
                        set_def: LuaSetDefinition,
                        max_depth: int = 10) -> Dict[str, LuaItem]:
    """
    Resolve set_combine inheritance to get full item list.
    
    Follows the inheritance chain and merges items.
    Later items override earlier ones.
    
    Args:
        gsfile: The full parsed file (for looking up base sets)
        set_def: The set definition to resolve
        max_depth: Maximum inheritance depth (to prevent infinite loops)
        
    Returns:
        Complete dict of slot_name -> LuaItem
    """
    if max_depth <= 0:
        return dict(set_def.items)
    
    if not set_def.base_set:
        return dict(set_def.items)
    
    # Find the base set
    base_set_def = gsfile.sets.get(set_def.base_set)
    
    if not base_set_def:
        # Base set not found, return just this set's items
        return dict(set_def.items)
    
    # Recursively resolve the base set
    base_items = resolve_set_combine(gsfile, base_set_def, max_depth - 1)
    
    # Merge: this set's items override base
    base_items.update(set_def.items)
    
    return base_items


def extract_ja_name_from_set(set_def: LuaSetDefinition) -> Optional[str]:
    """
    Extract Job Ability name from a JA set definition.
    
    Handles patterns like:
    - sets.precast.JA['Berserk']
    - sets.precast.JA["Aggressor"]
    - sets.precast.JA.Berserk
    
    Args:
        set_def: The set definition
        
    Returns:
        JA name if found, None otherwise
    """
    set_name = set_def.name
    
    # Pattern 1: Bracket notation with quotes - JA['Name'] or JA["Name"]
    bracket_match = re.search(r"JA\[(['\"])([^'\"]+)\1\]", set_name, re.IGNORECASE)
    if bracket_match:
        return bracket_match.group(2)
    
    # Pattern 2: Dot notation - JA.Name
    dot_match = re.search(r"JA\.(\w+)", set_name, re.IGNORECASE)
    if dot_match:
        return dot_match.group(1)
    
    # Pattern 3: Check placeholder context for JA name hints
    if set_def.placeholder_context:
        # Look for JA names in the context (e.g., "PLACEHOLDER: Berserk")
        context = set_def.placeholder_context.strip()
        if context and not ' ' in context:
            # Single word - likely a JA name
            return context
    
    return None


def is_ja_profile(profile: OptimizationProfile) -> bool:
    """Check if a profile is for a JA set (name starts with 'JA:')."""
    return profile.name.startswith("JA:")


def get_ja_name_from_profile(profile: OptimizationProfile) -> Optional[str]:
    """Extract JA name from a JA profile."""
    if is_ja_profile(profile):
        return profile.name[3:]  # Remove "JA:" prefix
    return None


def infer_profile_from_set(set_def: LuaSetDefinition, 
                           job: Optional[Job] = None,
                           sub_job: Optional[str] = None,
                           main_weapon: Optional[Dict] = None,
                           sub_weapon: Optional[Dict] = None) -> OptimizationProfile:
    """
    Infer optimization profile from set name/path.
    
    Uses set naming conventions to determine the appropriate
    optimization profile. For TP/engaged sets, delegates to the
    standardized create_tp_profile from optimizer_ui.
    
    Args:
        set_def: The set definition
        job: Optional job for job-specific profiles
        sub_job: Optional sub job for dual wield detection
        main_weapon: Optional main weapon dict for dual wield detection
        sub_weapon: Optional sub weapon dict for dual wield detection
        
    Returns:
        An appropriate OptimizationProfile
    """
    name_lower = set_def.name.lower()
    path_lower = [p.lower() for p in set_def.path]
    context_lower = set_def.placeholder_context.lower()
    
    # Detect dual wield for TP profiles
    is_dual_wield = detect_dual_wield(job, sub_job, main_weapon, sub_weapon)
    
    # =========================================================================
    # Helper profile creators (for non-TP sets)
    # =========================================================================
    
    def make_dt_profile(name: str, pdt_focus: bool = False, mdt_focus: bool = False) -> OptimizationProfile:
        """Create a DT/idle profile."""
        weights = {
            'damage_taken': -100.0,
            'physical_dt': -100.0 if pdt_focus else -80.0,
            'magical_dt': -100.0 if mdt_focus else -60.0,
            'HP': 3.0,
            'defense': 1.0,
            'refresh': 5.0,
        }
        return OptimizationProfile(
            name=name,
            weights=weights,
            hard_caps={
                'damage_taken': -5000,
                'physical_dt': -5000,
                'magical_dt': -5000,
            },
            exclude_slots={Slot.MAIN, Slot.SUB},
            job=job,
        )
    
    # =========================================================================
    # Profile inference logic
    # =========================================================================
    
    # Check placeholder context for hints
    if 'haste' in context_lower and 'max' in context_lower:
        return create_tp_profile(job, TPSetType.PURE_TP, is_dual_wield)
    if 'haste ii' in context_lower or 'haste 2' in context_lower:
        return create_tp_profile(job, TPSetType.PURE_TP, is_dual_wield)
    if 'acc' in context_lower:
        return create_tp_profile(job, TPSetType.ACC_TP, is_dual_wield)
    
    # Check for WS names using the database
    # Extract potential WS name from set path (e.g., "sets.precast.WS['Savage Blade']" -> "Savage Blade")
    def extract_ws_name(set_name: str) -> Optional[str]:
        """Extract weaponskill name from set path."""
        # Match bracket notation: WS['Name'] or WS["Name"]
        bracket_match = re.search(r"WS\[(['\"])([^'\"]+)\1\]", set_name, re.IGNORECASE)
        if bracket_match:
            return bracket_match.group(2)
        # Match dot notation after WS: WS.Name
        dot_match = re.search(r"WS\.(\w+)", set_name, re.IGNORECASE)
        if dot_match:
            return dot_match.group(1)
        return None
    
    # Check path patterns - IDLE sets
    if 'idle' in path_lower:
        # Pet idle sets - not implemented yet
        # TODO: Implement pet-specific optimization (e.g., dragoon wyvern casting)
        # if 'pet' in path_lower:
        #     return None
        if 'dt' in path_lower:
            return make_dt_profile(name=set_def.name, pdt_focus=True)
        if 'regen' in path_lower:
            # Regen idle - prioritize HP recovery
            return OptimizationProfile(
                name=set_def.name,
                weights={
                    'regen': 15.0,
                    'HP': 5.0,
                    'damage_taken': -50.0,
                    'physical_dt': -40.0,
                    'magical_dt': -30.0,
                },
                hard_caps={
                    'damage_taken': -5000,
                    'physical_dt': -5000,
                    'magical_dt': -5000,
                },
                exclude_slots={Slot.MAIN, Slot.SUB},
                job=job,
            )
        if 'refresh' in path_lower:
            return make_dt_profile(name=set_def.name)
        if 'mdt' in path_lower:
            return make_dt_profile(name=set_def.name, mdt_focus=True)
        return make_dt_profile(name=set_def.name)
    
    # ENGAGED sets - use standardized TP profiles from optimizer_ui
    if 'engaged' in path_lower:
        # Check for STP.DT pattern (e.g., engaged.STP.DT)
        has_stp = 'stp' in path_lower or 'stp' in name_lower
        has_dt = 'dt' in path_lower or 'hybrid' in path_lower
        has_acc = 'acc' in path_lower or 'fullacc' in path_lower
        
        if has_stp and has_dt:
            # engaged.STP.DT -> DT_TP (survivability + TP focus)
            return create_tp_profile(job, TPSetType.DT_TP, is_dual_wield)
        elif has_dt:
            # engaged.DT -> BALANCED_DT (equal offense + defense)
            return create_tp_profile(job, TPSetType.BALANCED_DT, is_dual_wield)
        elif has_acc:
            # engaged.Acc -> ACC_TP (high accuracy + TP)
            return create_tp_profile(job, TPSetType.ACC_TP, is_dual_wield)
        elif has_stp:
            # engaged.STP -> PURE_TP (fastest TP gain)
            return create_tp_profile(job, TPSetType.PURE_TP, is_dual_wield)
        elif 'maxhaste' in name_lower or 'max' in path_lower:
            # explicit max haste -> PURE_TP
            return create_tp_profile(job, TPSetType.PURE_TP, is_dual_wield)
        else:
            # Base engaged -> HYBRID_TP (balanced damage + TP)
            return create_tp_profile(job, TPSetType.HYBRID_TP, is_dual_wield)
    
    # WEAPONSKILL sets - use database
    if 'ws' in path_lower or 'weaponskill' in path_lower or 'precast.ws' in name_lower:
        ws_name_extracted = extract_ws_name(set_def.name)
        if ws_name_extracted:
            ws_data = get_weaponskill(ws_name_extracted)
            if ws_data:
                # Use the database's stat weights directly
                weights = ws_data.get_stat_weights(include_attack=True)
                return OptimizationProfile(
                    name=set_def.name,
                    weights=weights,
                    exclude_slots={Slot.MAIN, Slot.SUB},
                    job=job,
                )
    
    # PRECAST sets
    if 'precast' in path_lower:
        # JA (Job Ability) sets - check for JA name in path
        if 'ja' in path_lower:
            ja_name = extract_ja_name_from_set(set_def)
            if ja_name:
                # Return a special "JA profile" that signals we need JA optimization
                # The actual optimization is handled in optimize_placeholder_set()
                return OptimizationProfile(
                    name=f"JA:{ja_name}",
                    weights={
                        # Secondary priority: DT while using JA
                        'damage_taken': -100.0,
                        'physical_dt': -80.0,
                        'magical_dt': -60.0,
                        'HP': 3.0,
                    },
                    hard_caps={
                        'damage_taken': -5000,
                        'physical_dt': -5000,
                        'magical_dt': -5000,
                    },
                    exclude_slots={Slot.MAIN, Slot.SUB},
                    job=job,
                )
        
        if 'fc' in path_lower or 'fast' in name_lower or 'fc' in name_lower:
            return OptimizationProfile(
                name=set_def.name,
                weights={'fast_cast': 10.0, 'HP': 1.0},
                hard_caps={'fast_cast': 8000},
                exclude_slots={Slot.MAIN, Slot.SUB},
                job=job,
            )
        # Generic precast
        return OptimizationProfile(
            name=set_def.name,
            weights={'fast_cast': 10.0},
            hard_caps={'fast_cast': 8000},
            exclude_slots={Slot.MAIN, Slot.SUB},
            job=job,
        )
    
    # MIDCAST sets (magic - kept as-is since user said they're reasonable)
    if 'midcast' in path_lower:
        # Elemental Magic / Nuking
        if 'elemental' in name_lower or 'nuke' in name_lower or 'mb' in name_lower:
            # Check for accuracy/resistant variant FIRST
            # These prioritize landing the spell over raw damage
            if 'resistant' in name_lower or 'acc' in name_lower:
                weights = {
                    'magic_accuracy': 15.0,       # Primary focus
                    'elemental_magic_skill': 10.0, # Contributes to accuracy
                    'INT': 8.0,                   # Also contributes to accuracy
                    'magic_attack': 5.0,          # Secondary damage
                    'magic_damage': 3.0,          # Tertiary damage
                }
                return OptimizationProfile(
                    name=set_def.name,
                    weights=weights,
                    exclude_slots={Slot.MAIN, Slot.SUB},
                    job=job,
                )
            # Magic Burst variant - prioritize MB stats
            if 'mb' in name_lower:
                weights = {
                    'magic_attack': 10.0,
                    'magic_damage': 8.0,
                    'INT': 5.0,
                    'magic_accuracy': 3.0,
                    'magic_burst_damage_ii': 5,
                    'magic_burst_bonus': 5,
                }
                return OptimizationProfile(
                    name=set_def.name,
                    weights=weights,
                    hard_caps={'magic_burst_bonus': 4000},
                    exclude_slots={Slot.MAIN, Slot.SUB},
                    job=job,
                )
            else:
                weights = {
                    'magic_attack': 10.0,
                    'magic_damage': 8.0,
                    'magic_accuracy': 5.0,
                    'elemental_magic_skill': 3.0,
                    'INT': 5.0,
                }
                return OptimizationProfile(
                    name=set_def.name,
                    weights=weights,
                    exclude_slots={Slot.MAIN, Slot.SUB},
                    job=job,
                )
        if 'dark' in name_lower:
            return OptimizationProfile(
                name=set_def.name,
                weights={
                    'dark_magic_skill': 10.0,
                    'magic_accuracy': 5.0,
                    'INT': 2.0,
                },
                exclude_slots={Slot.MAIN, Slot.SUB},
                job=job,
            )
        if 'drain' in name_lower or 'aspir' in name_lower:
            return OptimizationProfile(
                name=set_def.name,
                weights={
                    'drain_aspir_potency': 20.0,
                    'dark_magic_skill': 10.0,
                    'magic_accuracy': 5.0,
                    'INT': 2.0,
                },
                exclude_slots={Slot.MAIN, Slot.SUB},
                job=job,
            )
        if 'cure' in name_lower or 'heal' in name_lower:
            return OptimizationProfile(
                name=set_def.name,
                weights={
                    'cure_potency': 10.0,
                    'MND': 5.0,
                    'healing_magic_skill': 5.0,
                },
                hard_caps={'cure_potency': 5000},
                exclude_slots={Slot.MAIN, Slot.SUB},
                job=job,
            )
        if 'enhanc' in name_lower or 'buff' in name_lower:
            return OptimizationProfile(
                name=set_def.name,
                weights={
                    'enhancing_magic_skill': 10.0,
                    'enhancing_duration': 8.0,
                },
                exclude_slots={Slot.MAIN, Slot.SUB},
                job=job,
            )
        if 'enfeebl' in name_lower or 'mndenfeeble' in name_lower:
            return OptimizationProfile(
                name=set_def.name,
                weights={
                    'enfeebling_magic_skill': 10.0,
                    'magic_accuracy': 8.0,
                    'MND': 5.0,
                },
                exclude_slots={Slot.MAIN, Slot.SUB},
                job=job,
            )
        if 'intenfeeble' in name_lower:
            return OptimizationProfile(
                name=set_def.name,
                weights={
                    'enfeebling_magic_skill': 10.0,
                    'magic_accuracy': 8.0,
                    'INT': 5.0,
                },
                exclude_slots={Slot.MAIN, Slot.SUB},
                job=job,
            )
        # Generic midcast
        return OptimizationProfile(
            name=set_def.name,
            weights={'magic_accuracy': 5.0, 'INT': 2.0, 'MND': 2.0},
            exclude_slots={Slot.MAIN, Slot.SUB},
            job=job,
        )
    
    # Buff sets
    if 'buff' in path_lower:
        return OptimizationProfile(
            name=set_def.name,
            weights={'HP': 1.0},
            exclude_slots={Slot.MAIN, Slot.SUB},
            job=job,
        )
    
    # Defense sets
    if 'defense' in path_lower or 'pdt' in path_lower or 'mdt' in path_lower:
        return make_dt_profile(name=set_def.name)
    
    # Kiting set
    if 'kiting' in name_lower or 'movement' in name_lower:
        return OptimizationProfile(
            name=set_def.name,
            weights={'movement_speed': 10.0, 'HP': 1.0},
            exclude_slots={Slot.MAIN, Slot.SUB},
            job=job,
        )
    
    # Default to HYBRID_TP profile (balanced TP + damage)
    return create_tp_profile(job, TPSetType.HYBRID_TP, is_dual_wield)


def generate_set_lua(items: Dict[str, LuaItem],
                     indent: str = "    ",
                     base_indent: str = "") -> str:
    """
    Generate Lua table syntax for items.
    
    Args:
        items: Dict of slot_name -> LuaItem
        indent: Indentation for each line
        base_indent: Base indentation for the whole block
        
    Returns:
        Lua table string like:
        {
            head="Nyame Helm",
            body="Sakpata's Plate",
            ...
        }
    """
    lines = ["{"]
    
    # Standard slot order
    slot_order = [
        'main', 'sub', 'range', 'ammo',
        'head', 'neck', 'ear1', 'ear2',
        'body', 'hands', 'ring1', 'ring2',
        'back', 'waist', 'legs', 'feet',
    ]
    
    # Also handle left_ear/right_ear variants
    slot_aliases = {
        'left_ear': 'ear1',
        'right_ear': 'ear2',
        'left_ring': 'ring1',
        'right_ring': 'ring2',
    }
    
    # Normalize item keys
    normalized_items = {}
    for slot_name, item in items.items():
        normalized = slot_aliases.get(slot_name, slot_name)
        normalized_items[normalized] = item
    
    for slot_name in slot_order:
        if slot_name in normalized_items:
            item = normalized_items[slot_name]
            item_str = _format_lua_item(item)
            lines.append(f"{base_indent}{indent}{slot_name}={item_str},")
    
    lines.append(f"{base_indent}}}")
    
    return "\n".join(lines)


def _format_lua_item(item: LuaItem) -> str:
    """
    Format a LuaItem as Lua code.
    
    Uses single quotes for augment strings (Lua convention).
    """
    if not item.augments:
        return f'"{item.name}"'
    
    # Augmented item - use single quotes for augments
    # Internal double quotes like "Fast Cast" are preserved inside single quotes
    aug_parts = []
    for aug in item.augments:
        if aug and aug != 'none':
            # Use single quotes - internal double quotes are preserved
            aug_parts.append(f"'{aug}'")
    
    if not aug_parts:
        return f'"{item.name}"'
    
    aug_str = ', '.join(aug_parts)
    return f'{{ name="{item.name}", augments={{{aug_str}}} }}'


# Weapon slots that are typically excluded from optimized sets
# (changing main/sub/range loses TP, so most sets should only contain armor + ammo)
# NOTE: Ammo does NOT cause TP loss and is important for optimization
WEAPON_SLOTS_LUA = {'main', 'sub', 'range'}
WEAPON_SLOTS_ENUM = {Slot.MAIN, Slot.SUB, Slot.RANGE}


def gear_set_to_lua_items(gear_set: GearSet, exclude_weapons: bool = True) -> Dict[str, LuaItem]:
    """
    Convert a GearSet to a dict of LuaItems.
    
    Args:
        gear_set: The optimized GearSet
        exclude_weapons: If True (default), exclude main/sub/range slots.
                        Weapons are excluded because swapping them causes TP loss.
                        Ammo is NOT excluded as it doesn't cause TP loss.
                        Set to False for refresh/regain idle sets or other cases 
                        where weapon-specific stats matter.
        
    Returns:
        Dict of slot_name -> LuaItem
    """
    items = {}
    
    for slot, item in gear_set.items.items():
        if item is None:
            continue
        
        # Skip weapon slots if requested
        if exclude_weapons and slot in WEAPON_SLOTS_ENUM:
            continue
        
        slot_name = SLOT_TO_LUA.get(slot, slot.name.lower())
        
        # Convert augments
        augments = None
        if item.augments_raw:
            augments = [a for a in item.augments_raw if a and a != 'none']
            if not augments:
                augments = None
        
        items[slot_name] = LuaItem(
            name=item.name,
            augments=augments,
            is_augmented=bool(augments),
        )
    
    return items


# =============================================================================
# File Update Functions
# =============================================================================

def update_set_in_content(content: str,
                          set_def: LuaSetDefinition,
                          new_items: Dict[str, LuaItem],
                          preserve_base: bool = True) -> str:
    """
    Update a single set in the file content.
    
    Args:
        content: Original file content
        set_def: The set definition to update
        new_items: New items to insert
        preserve_base: If True, preserve set_combine base reference
        
    Returns:
        Updated file content
    """
    # Build the new set text
    if set_def.base_set and preserve_base:
        # set_combine format
        items_lua = generate_set_lua(new_items, indent="    ", base_indent=set_def.indent)
        # Remove the outer braces since set_combine provides them
        items_inner = items_lua[1:-1].strip()
        new_text = f"{set_def.indent}{set_def.name} = set_combine({set_def.base_set}, {{\n{items_inner}\n{set_def.indent}}})"
    else:
        # Regular format
        items_lua = generate_set_lua(new_items, indent="    ", base_indent=set_def.indent)
        new_text = f"{set_def.indent}{set_def.name} = {items_lua}"
    
    # Find and replace the old set text
    # We need to find the exact position in the content
    old_text = set_def.raw_text
    
    # Replace
    updated = content.replace(old_text, new_text, 1)
    
    return updated


def update_gearswap_file(gsfile: GearSwapFile,
                         set_name: str,
                         optimized_gear: GearSet,
                         preserve_locked: bool = True,
                         locked_slots: Optional[Set[str]] = None) -> str:
    """
    Return updated Lua file content with optimized set.
    
    Args:
        gsfile: Original parsed file
        set_name: Name of set to update (e.g., "sets.engaged.DT")
        optimized_gear: The optimized GearSet from optimizer
        preserve_locked: If True, keep main/sub from original
        locked_slots: Additional slots to preserve from original
        
    Returns:
        Updated Lua file content as string
    """
    if set_name not in gsfile.sets:
        raise ValueError(f"Set '{set_name}' not found in file")
    
    set_def = gsfile.sets[set_name]
    
    # Convert optimized gear to LuaItems
    new_items = gear_set_to_lua_items(optimized_gear)
    
    # Determine which slots to preserve
    preserved_slots = set(locked_slots or [])
    if preserve_locked:
        preserved_slots.add('main')
        preserved_slots.add('sub')
    
    # Get original items for preserved slots
    original_items = resolve_set_combine(gsfile, set_def)
    
    for slot_name in preserved_slots:
        if slot_name in original_items:
            new_items[slot_name] = original_items[slot_name]
    
    # Update the content
    return update_set_in_content(gsfile.raw_content, set_def, new_items)


def update_all_placeholders(gsfile: GearSwapFile,
                            optimizer,  # BeamSearchOptimizer instance
                            job: Optional[Job] = None,
                            inventory: Optional['Inventory'] = None) -> Tuple[str, List[str]]:
    """
    Update all placeholder sets in the file.
    
    Args:
        gsfile: Parsed GearSwap file
        optimizer: BeamSearchOptimizer instance with loaded inventory
        job: Job for optimization (uses file's detected job if not provided)
        inventory: Optional inventory for JA optimization (uses optimizer's if not provided)
        
    Returns:
        Tuple of (updated_content, list_of_updated_set_names)
    """
    job = job or (Job[gsfile.job] if gsfile.job else None)
    
    # Get inventory from optimizer if not provided
    if inventory is None and hasattr(optimizer, 'inventory'):
        inventory = optimizer.inventory
    
    # Build JA enhancement index if we have the greedy optimizer
    ja_index = None
    if HAS_GREEDY_OPTIMIZER and inventory:
        ja_index = JAEnhancementIndex(inventory)
        if ja_index.by_ja:
            print(f"  JA Enhancement Index: {len(ja_index.by_ja)} JAs with gear")
    
    placeholders = find_placeholder_sets(gsfile)
    updated_names = []
    content = gsfile.raw_content
    
    for set_def in placeholders:
        # Infer the appropriate profile
        profile = infer_profile_from_set(set_def, job)
        
        # Check if this is a JA set
        if is_ja_profile(profile) and ja_index:
            ja_name = get_ja_name_from_profile(profile)
            ja_items = ja_index.get_items_for_ja(ja_name) if ja_name else []
            
            if ja_items:
                print(f"  → JA Set '{ja_name}': Found {len(ja_items)} enhancement item(s)")
                # Use greedy optimizer for JA set
                new_items = _optimize_ja_set(
                    inventory=inventory,
                    job=job,
                    ja_name=ja_name,
                    profile=profile,
                )
                if new_items:
                    content = update_set_in_content(content, set_def, new_items)
                    updated_names.append(set_def.name)
            else:
                print(f"  → JA Set '{ja_name}': No enhancement gear found, using DT fill")
                # Fall back to just DT optimization
                results = optimizer.search(profile=profile)
                if results:
                    best = results[0]
                    new_items = wsdist_gear_to_lua_items(best.gear)
                    content = update_set_in_content(content, set_def, new_items)
                    updated_names.append(set_def.name)
        else:
            # Standard optimization using beam search
            results = optimizer.search(profile=profile)
            
            if results:
                # Get the best result and convert to LuaItems
                best = results[0]
                new_items = wsdist_gear_to_lua_items(best.gear)
                content = update_set_in_content(content, set_def, new_items)
                updated_names.append(set_def.name)
        
        # Re-parse to get updated positions for next iteration
        parser = LuaParser()
        temp_gsfile = parser.parse_content(content, gsfile.filepath)
    
    return content, updated_names


def _optimize_ja_set(inventory: 'Inventory',
                     job: Job,
                     ja_name: str,
                     profile: OptimizationProfile) -> Optional[Dict[str, LuaItem]]:
    """
    Optimize a JA set using the greedy optimizer.
    
    Args:
        inventory: Player inventory
        job: Job for optimization
        ja_name: Name of the Job Ability
        profile: The JA profile (used for secondary stat priority)
        
    Returns:
        Dict of slot_name -> LuaItem, or None if optimization failed
    """
    if not HAS_GREEDY_OPTIMIZER:
        print("  ⚠ greedy_optimizer not available")
        return None
    
    # Use run_ja_optimization from greedy_optimizer
    gear_dict, enhancement_slots = run_ja_optimization(
        inventory=inventory,
        job=job,
        ja_name=ja_name,
        main_weapon=None,  # JA sets don't need weapons
        sub_weapon=None,
        secondary_profile=profile,
        beam_width=25,
    )
    
    if not gear_dict:
        return None
    
    # Convert to LuaItems
    lua_items = wsdist_gear_to_lua_items(gear_dict)
    
    return lua_items


def wsdist_gear_to_lua_items(gear: Dict[str, Dict], exclude_weapons: bool = True) -> Dict[str, LuaItem]:
    """
    Convert wsdist gear dict to LuaItems.
    
    Args:
        gear: Dict of slot_name -> wsdist item dict
        exclude_weapons: If True (default), exclude main/sub/range slots.
                        Weapons are excluded because swapping them causes TP loss.
                        Ammo is NOT excluded as it doesn't cause TP loss.
                        Set to False for refresh/regain idle sets or other cases 
                        where weapon-specific stats matter.
        
    Returns:
        Dict of slot_name -> LuaItem
    """
    items = {}
    
    for slot_name, item in gear.items():
        if item is None:
            continue
        
        # Skip weapon slots if requested
        if exclude_weapons and slot_name.lower() in WEAPON_SLOTS_LUA:
            continue
        
        # Use 'Name' for Lua output (base item name without augment suffix)
        # Name2 is used internally for uniqueness but includes augment strings
        name = item.get('Name', 'Empty')
        if name == 'Empty':
            continue
        
        # Get augments if present
        # Check _augments first (our convention to avoid wsdist summing it)
        # Then fall back to augments/Augments for compatibility
        augments = None
        if '_augments' in item:
            augments = item['_augments']
        elif 'augments' in item:
            augments = item['augments']
        elif 'Augments' in item:
            augments = item['Augments']
        
        items[slot_name] = LuaItem(
            name=name,
            augments=augments,
            is_augmented=bool(augments),
        )
    
    return items


# =============================================================================
# Convenience Functions
# =============================================================================

def parse_gearswap_file(filepath: str) -> GearSwapFile:
    """
    Parse a GearSwap Lua file.
    
    Args:
        filepath: Path to the .lua file
        
    Returns:
        GearSwapFile with all parsed data
    """
    parser = LuaParser()
    return parser.parse_file(filepath)


def parse_gearswap_content(content: str, filepath: str = "<string>") -> GearSwapFile:
    """
    Parse GearSwap Lua content from a string.
    
    Args:
        content: Lua file content
        filepath: Original filepath (for reference)
        
    Returns:
        GearSwapFile with all parsed data
    """
    parser = LuaParser()
    return parser.parse_content(content, filepath)


def list_ja_enhancements(inventory: 'Inventory', job: Optional[Job] = None) -> Dict[str, List[Tuple[str, str]]]:
    """
    List all JAs that have enhancement gear in inventory.
    
    Args:
        inventory: Player inventory
        job: Optional job filter
        
    Returns:
        Dict of JA name -> list of (slot_name, item_name) tuples
    """
    if not HAS_GREEDY_OPTIMIZER:
        print("Warning: greedy_optimizer not available")
        return {}
    
    ja_index = JAEnhancementIndex(inventory)
    
    result = {}
    for ja_name, items in ja_index.by_ja.items():
        result[ja_name] = []
        for slot, item in items:
            slot_name = slot.name.lower()
            if slot_name == 'left_ear':
                slot_name = 'ear1'
            elif slot_name == 'right_ear':
                slot_name = 'ear2'
            elif slot_name == 'left_ring':
                slot_name = 'ring1'
            elif slot_name == 'right_ring':
                slot_name = 'ring2'
            result[ja_name].append((slot_name, item.name))
    
    return result


def print_ja_enhancement_summary(inventory: 'Inventory', job: Optional[Job] = None):
    """
    Print a summary of JA enhancement gear in inventory.
    
    Args:
        inventory: Player inventory
        job: Optional job filter
    """
    ja_enhancements = list_ja_enhancements(inventory, job)
    
    if not ja_enhancements:
        print("No JA enhancement gear found in inventory.")
        return
    
    print("\n" + "=" * 60)
    print("JA ENHANCEMENT GEAR AVAILABLE")
    print("=" * 60)
    
    for ja_name in sorted(ja_enhancements.keys()):
        items = ja_enhancements[ja_name]
        print(f"\n{ja_name}:")
        for slot_name, item_name in items:
            print(f"  {slot_name:8s}: {item_name}")
    
    print(f"\nTotal: {len(ja_enhancements)} JAs with enhancement gear")


def optimize_single_set(gsfile: GearSwapFile,
                        set_name: str,
                        optimizer,
                        job: Optional[Job] = None,
                        inventory: Optional['Inventory'] = None) -> Tuple[str, bool]:
    """
    Optimize a single set in the GearSwap file.
    
    This is useful for optimizing specific sets without updating all placeholders.
    
    Args:
        gsfile: Parsed GearSwap file
        set_name: Name of set to optimize (e.g., "sets.precast.JA['Berserk']")
        optimizer: BeamSearchOptimizer instance
        job: Job for optimization
        inventory: Optional inventory for JA optimization
        
    Returns:
        Tuple of (updated_content, success_bool)
    """
    job = job or (Job[gsfile.job] if gsfile.job else None)
    
    if set_name not in gsfile.sets:
        print(f"Error: Set '{set_name}' not found in file")
        return gsfile.raw_content, False
    
    set_def = gsfile.sets[set_name]
    
    # Get inventory from optimizer if not provided
    if inventory is None and hasattr(optimizer, 'inventory'):
        inventory = optimizer.inventory
    
    # Infer profile
    profile = infer_profile_from_set(set_def, job)
    
    # Check if JA set
    if is_ja_profile(profile) and HAS_GREEDY_OPTIMIZER and inventory:
        ja_index = JAEnhancementIndex(inventory)
        ja_name = get_ja_name_from_profile(profile)
        
        if ja_name and ja_index.get_items_for_ja(ja_name):
            print(f"Optimizing JA set: {ja_name}")
            new_items = _optimize_ja_set(
                inventory=inventory,
                job=job,
                ja_name=ja_name,
                profile=profile,
            )
            if new_items:
                content = update_set_in_content(gsfile.raw_content, set_def, new_items)
                return content, True
    
    # Standard optimization
    results = optimizer.search(profile=profile)
    
    if results:
        best = results[0]
        new_items = wsdist_gear_to_lua_items(best.gear)
        content = update_set_in_content(gsfile.raw_content, set_def, new_items)
        return content, True
    
    return gsfile.raw_content, False
