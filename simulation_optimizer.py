"""
Simulation-Based Gear Optimizer

Uses beam search to narrow down the item pool, then runs actual simulations
to find the truly optimal gear set.

Flow:
1. Filter out irrelevant items (fishing gear, etc.)
2. Run beam search to get candidate pool
3. Run simulation on candidates to find optimal set
4. For DT/FC sets, just validate caps without simulation
"""

import sys
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass
from enum import Enum

# Path setup
SCRIPT_DIR = Path(__file__).parent
WSDIST_DIR = SCRIPT_DIR / 'wsdist_beta-main'
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(WSDIST_DIR))

# =============================================================================
# IMPORTS
# =============================================================================

from models import Job, Slot, OptimizationProfile
from inventory_loader import Inventory
from beam_search_optimizer import (
    BeamSearchOptimizer,
    WSDIST_SLOTS,
    ARMOR_SLOTS,
)

# wsdist imports
try:
    from gear import Empty, all_jobs
    from enemies import preset_enemies
    from create_player import create_player, create_enemy
    from actions import average_ws, average_attack_round
    WSDIST_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import wsdist modules: {e}")
    WSDIST_AVAILABLE = False
    all_jobs = ["war", "mnk", "whm", "blm", "rdm", "thf", "pld", "drk",
                "bst", "brd", "rng", "smn", "sam", "nin", "drg", "blu",
                "cor", "pup", "dnc", "sch", "geo", "run"]
    Empty = {"Name": "Empty", "Name2": "Empty", "Type": "None", "Jobs": all_jobs}

# Magic imports
try:
    from magic_simulation import (
        MagicSimulator,
        CasterStats,
        MagicTargetStats,
        MAGIC_TARGETS,
    )
    from magic_formulas import Element
    from spell_database import get_spell, ALL_SPELLS
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    MAGIC_TARGETS = {}
    ALL_SPELLS = {}
    Element = None


# =============================================================================
# GEAR STAT SANITIZATION
# =============================================================================

# Known numeric stat fields that should be integers in wsdist gear dicts
NUMERIC_GEAR_STATS = {
    # Primary stats
    "STR", "DEX", "VIT", "AGI", "INT", "MND", "CHR",
    # HP/MP
    "HP", "MP",
    # Combat stats
    "Accuracy", "Attack", "Ranged Accuracy", "Ranged Attack",
    "Magic Accuracy", "Magic Attack", "Magic Damage",
    "Evasion", "Magic Evasion", "Magic Defense", "Defense",
    # Percentage stats
    "Gear Haste", "DA", "TA", "QA", "Dual Wield",
    "Crit Rate", "Crit Damage", "Weapon Skill Damage",
    "DT", "PDT", "MDT", "PDL",
    "Magic Burst Damage", "Magic Burst Damage II",
    "Skillchain Bonus", "Fast Cast", "Cure Potency",
    # Integer stats
    "Store TP", "TP Bonus", "Daken", "Martial Arts", "Zanshin",
    "Kick Attacks", "Subtle Blow", "Subtle Blow II", "Fencer",
    "Conserve TP", "Regain",
    # Occasional attacks
    "OA2", "OA3", "OA4", "OA5", "OA6", "OA7", "OA8", "FUA",
    # Ranged
    "Double Shot", "Triple Shot", "True Shot", "Recycle", "Barrage",
    # Skills
    "Magic Accuracy Skill",
    "Hand-to-Hand Skill", "Dagger Skill", "Sword Skill", "Great Sword Skill",
    "Axe Skill", "Great Axe Skill", "Scythe Skill", "Polearm Skill",
    "Katana Skill", "Great Katana Skill", "Club Skill", "Staff Skill",
    "Archery Skill", "Marksmanship Skill", "Throwing Skill",
    "Healing Magic Skill", "Enfeebling Magic Skill", "Enhancing Magic Skill",
    "Elemental Magic Skill", "Divine Magic Skill", "Dark Magic Skill",
    "Singing Skill", "Ninjutsu Skill", "Blue Magic Skill", "Summoning Skill",
    # Job-specific
    "EnSpell Damage", "EnSpell Damage%", "Ninjutsu Magic Attack", "Ninjutsu Damage%",
    "Blood Pact Damage", "Occult Acumen",
    # Elemental
    "Fire Elemental Bonus", "Ice Elemental Bonus", "Wind Elemental Bonus",
    "Earth Elemental Bonus", "Lightning Elemental Bonus", "Water Elemental Bonus",
    "Light Elemental Bonus", "Dark Elemental Bonus",
    # Weapon
    "DMG", "Delay",
}


def sanitize_gear_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize a single gear item dict to ensure all numeric stats are integers.
    
    This handles cases where stat values may be strings (from JSON parsing,
    augment parsing, etc.) which would cause type errors when wsdist tries
    to sum them.
    
    Args:
        item: A gear item dictionary
        
    Returns:
        A new dictionary with numeric stats converted to integers
    """
    if item is None:
        return None
    
    sanitized = {}
    for key, value in item.items():
        if key in NUMERIC_GEAR_STATS:
            # Convert to int, handling strings and floats
            try:
                if isinstance(value, str):
                    value = value.strip()
                    if value:
                        sanitized[key] = int(float(value))
                    else:
                        sanitized[key] = 0
                elif value is not None:
                    sanitized[key] = int(value)
                else:
                    sanitized[key] = 0
            except (ValueError, TypeError):
                sanitized[key] = 0
        else:
            sanitized[key] = value
    
    return sanitized


def sanitize_gearset(gearset: Dict[str, Dict]) -> Dict[str, Dict]:
    """
    Sanitize an entire gearset to ensure all numeric stats are integers.
    
    Args:
        gearset: Dictionary of slot -> gear item dict
        
    Returns:
        New gearset dictionary with all items sanitized
    """
    if gearset is None:
        return None
    
    return {
        slot: sanitize_gear_item(item) if item else item
        for slot, item in gearset.items()
    }


# =============================================================================
# SET TYPE CLASSIFICATION
# =============================================================================

class SetOptimizationType(Enum):
    """How to optimize different set types."""
    WS_SIMULATION = "ws_simulation"           # Weaponskill - simulate damage
    TP_SIMULATION = "tp_simulation"           # TP/Engaged - simulate time to WS
    MAGIC_DAMAGE = "magic_damage"             # Magic damage - simulate spell damage
    MAGIC_ACCURACY = "magic_accuracy"         # Magic acc - beam search with acc weights
    MAGIC_BURST = "magic_burst"               # Magic burst - simulate MB damage
    DT_CAPPED = "dt_capped"                   # DT sets - beam search with cap validation
    FC_CAPPED = "fc_capped"                   # FC sets - beam search with cap validation
    BEAM_ONLY = "beam_only"                   # Generic - beam search only


# =============================================================================
# FISHING GEAR FILTER
# =============================================================================

FISHING_KEYWORDS = {
    'fishing', 'fish', 'angler', 'fisherman', 'halcyon', 'penguin',
    'ebisu', 'lu shang', 'lushang', 'mooching', 'serpent', 'puffin',
}

FISHING_ITEMS = {
    # Known fishing rods and gear
    "Ebisu Fishing Rod",
    "Lu Shang's F. Rod",
    "Halcyon Rod",
    "Mooching Rod",
    "Serpent Rumble",
    "Penguin Ring",
    "Fisherman's Tunica",
    "Fisherman's Hose",
    "Fisherman's Boots",
    "Fisherman's Gloves",
    "Fisherman's Belt",
    "Angler's Tunica",
    "Angler's Hose",
    "Tracer Bullet",
    "Worm Lure",
    "Minnow",
    "Fly Lure",
    "Shrimp Lure",
    "Crayfish Ball",
    "Little Worm",
    "Lugworm",
    "Rogue Rig",
    "Sabiki Rig",
    "Frog Lure",
    "Sinking Minnow",
    "Robber Rig",
}


def is_fishing_gear(item: Dict[str, Any]) -> bool:
    """Check if an item is fishing-related gear."""
    name = item.get('Name', '').lower()
    name2 = item.get('Name2', '').lower()
    
    # Check against known fishing items
    if item.get('Name', '') in FISHING_ITEMS or item.get('Name2', '') in FISHING_ITEMS:
        return True
    
    # Check keywords
    for keyword in FISHING_KEYWORDS:
        if keyword in name or keyword in name2:
            return True
    
    # Check item type if available
    item_type = item.get('Type', '').lower()
    if 'fishing' in item_type:
        return True
    
    # Check skill type
    skill = item.get('Skill Type', '').lower()
    if 'fishing' in skill:
        return True
    
    return False


def filter_fishing_gear(items: List[Dict[str, Any]], slot: str) -> List[Dict[str, Any]]:
    """
    Filter out fishing gear from a list of items.
    Only applies to ranged/ammo slots where fishing gear is common.
    """
    if slot not in ('range', 'ranged', 'ammo'):
        return items
    
    return [item for item in items if not is_fishing_gear(item)]


def filter_inventory_fishing_gear(inventory: Inventory) -> Inventory:
    """
    Create a filtered copy of the inventory without fishing gear.
    
    This removes fishing rods and bait from the ranged/ammo slots
    to reduce combinatorial explosion during optimization.
    
    Args:
        inventory: Original inventory
        
    Returns:
        New Inventory with fishing items removed
    """
    from models import Slot, SLOT_BITMASK
    
    # Get slot masks for range and ammo
    range_mask = SLOT_BITMASK.get(Slot.RANGE, 0)
    ammo_mask = SLOT_BITMASK.get(Slot.AMMO, 0)
    
    # Filter items
    filtered_items = []
    removed_count = 0
    
    for item in inventory.items:
        # Check if this item goes in range or ammo slot
        is_range_or_ammo = bool(item.base.slots & (range_mask | ammo_mask))
        
        if is_range_or_ammo:
            # Check if it's fishing gear by looking at the item data
            item_name = item.name.lower()
            item_name2 = getattr(item, 'name2', item.name).lower() if hasattr(item, 'name2') else item_name
            
            # Check against fishing keywords and known items
            is_fishing = False
            for keyword in FISHING_KEYWORDS:
                if keyword in item_name or keyword in item_name2:
                    is_fishing = True
                    break
            
            if item.name in FISHING_ITEMS:
                is_fishing = True
            
            # Check skill type if available
            if hasattr(item.base, 'skill') and item.base.skill:
                if 'fishing' in str(item.base.skill).lower():
                    is_fishing = True
            
            if is_fishing:
                removed_count += 1
                continue
        
        filtered_items.append(item)
    
    if removed_count > 0:
        print(f"  Filtered out {removed_count} fishing items from inventory")
    
    # Create a new inventory-like object with filtered items
    # We need to be careful here since Inventory is a dataclass
    filtered_inventory = deepcopy(inventory)
    filtered_inventory.items = filtered_items
    
    return filtered_inventory


# =============================================================================
# STANDARD BUFF CONFIGURATIONS
# =============================================================================

# Standard melee buffs (WS and TP)
MELEE_STANDARD_BUFFS = {
    "Food": {
        "STR": 7,
        "Attack": 150,
        "Ranged Attack": 150,
        "Accuracy": 60,
        "Ranged Accuracy": 60,
    },
    "BRD": {
        "Attack": 280,           # Minuet V + IV approximately
        "Ranged Attack": 280,
        "Accuracy": 60,          # Blade Madrigal
        "Ranged Accuracy": 60,
        "Magic Haste": 0.25,     # March
    },
}

MELEE_STANDARD_DEBUFFS = {
    "defense_down_pct": 0.203 + 0.28,  # Dia III (20.3%) + Distract III approx effect
    "evasion_down": 280,               # Distract III
}

# Magic damage/MB buffs
MAGIC_DAMAGE_BUFFS = {
    "Food": {
        "INT": 8,
        "Magic Attack": 60,
        "Magic Accuracy": 60,
    },
    "COR": {
        "Magic Attack": 50,      # Wizard's Roll XI
    },
    "BRD": {
        "Magic Haste": 0.25,
    },
    "GEO": {
        "Magic Attack%": 35,     # Geo-Acumen
    },
}

MAGIC_DAMAGE_DEBUFFS = {
    "magic_evasion_down": 75,    # Geo-Languor
    "magic_defense_down": 35,    # Geo-Malaise
}

# Magic accuracy buffs
MAGIC_ACCURACY_BUFFS = {
    "Food": {
        "INT": 8,
        "Magic Attack": 60,
        "Magic Accuracy": 90,    # Miso Ramen or similar
    },
    "COR": {
        "Magic Accuracy": 52,    # Warlock's Roll XI
        "Magic Attack": 50,      # Wizard's Roll XI
    },
}

MAGIC_ACCURACY_DEBUFFS = {
    "magic_evasion_down": 45,    # Frazzle III
}


# =============================================================================
# TARGET CONFIGURATIONS
# =============================================================================

# Standard targets for different optimization types
TARGETS = {
    "training_dummy": {
        "Name": "Training Dummy",
        "Level": 1,
        "Defense": 100,
        "Base Defense": 100,
        "Evasion": 100,
        "VIT": 50,
        "AGI": 50,
        "MND": 50,
        "INT": 50,
        "CHR": 50,
        "Magic Evasion": 0,
        "Magic Defense": 0,
    },
    "apex_toad": {
        "Name": "Apex Toad",
        "Level": 132,
        "Defense": 1239,
        "Base Defense": 1239,
        "Evasion": 1133,
        "VIT": 270,
        "AGI": 348,
        "MND": 224,
        "INT": 293,
        "CHR": 277,
        "Magic Evasion": 600,
        "Magic Defense": 30,
    },
    "apex_toad_debuffed": {
        "Name": "Apex Toad (Debuffed)",
        "Level": 132,
        # Defense reduced by Dia III + Distract III effect
        "Defense": int(1239 * (1 - 0.203)),  # ~988
        "Base Defense": 1239,
        "Evasion": 1133 - 280,  # Distract III
        "VIT": 270,
        "AGI": 348,
        "MND": 224,
        "INT": 293,
        "CHR": 277,
        "Magic Evasion": 600 - 75,  # Geo-Languor
        "Magic Defense": 30 - 35,    # Geo-Malaise (can go negative)
    },
}


# =============================================================================
# SET TYPE INFERENCE
# =============================================================================

def classify_set_type(set_name: str, context: str = "") -> SetOptimizationType:
    """
    Classify a set based on its name to determine optimization approach.
    
    Args:
        set_name: Full set name (e.g., "sets.precast.WS['Savage Blade']")
        context: Optional placeholder context text
        
    Returns:
        SetOptimizationType indicating how to optimize this set
    """
    name_lower = set_name.lower()
    context_lower = context.lower()
    
    # Weaponskill sets -> simulation
    if 'precast.ws' in name_lower or "ws[" in name_lower or 'weaponskill' in name_lower:
        return SetOptimizationType.WS_SIMULATION
    
    # TP/Engaged sets -> simulation
    if 'engaged' in name_lower:
        if 'acc' in name_lower or 'accuracy' in context_lower:
            # High accuracy engaged - still simulate but note the context
            return SetOptimizationType.TP_SIMULATION
        return SetOptimizationType.TP_SIMULATION
    
    # Magic sets
    if 'midcast' in name_lower:
        # Elemental/Nuke damage
        if any(x in name_lower for x in ['elemental', 'nuke', 'thunder', 'fire', 
                                          'blizzard', 'aero', 'stone', 'water']):
            if 'mb' in name_lower or 'burst' in name_lower or 'burst' in context_lower:
                return SetOptimizationType.MAGIC_BURST
            return SetOptimizationType.MAGIC_DAMAGE
        
        # Dark magic damage (Drain/Aspir)
        if any(x in name_lower for x in ['drain', 'aspir', 'dark']):
            return SetOptimizationType.MAGIC_DAMAGE
        
        # Enfeebling - accuracy focused
        if any(x in name_lower for x in ['enfeebl', 'enfeeb', 'paralyze', 'slow', 
                                          'silence', 'gravity', 'bind', 'sleep',
                                          'blind', 'dispel', 'frazzle', 'distract']):
            return SetOptimizationType.MAGIC_ACCURACY
        
        # Divine magic
        if 'divine' in name_lower or 'banish' in name_lower or 'holy' in name_lower:
            return SetOptimizationType.MAGIC_DAMAGE
    
    # DT/Idle sets -> cap validation
    if 'idle' in name_lower or 'dt' in name_lower or 'defense' in name_lower:
        return SetOptimizationType.DT_CAPPED
    
    # FC/Precast sets -> cap validation
    if 'precast' in name_lower and 'ws' not in name_lower:
        if 'fc' in name_lower or 'fast' in name_lower:
            return SetOptimizationType.FC_CAPPED
        return SetOptimizationType.FC_CAPPED  # Default precast to FC
    
    # Default to beam search only
    return SetOptimizationType.BEAM_ONLY


def extract_ws_name(set_name: str) -> Optional[str]:
    """Extract weaponskill name from a set name like sets.precast.WS['Savage Blade']"""
    import re
    
    # Try bracket notation with quotes
    match = re.search(r"\[(['\"])(.+?)\1\]", set_name)
    if match:
        return match.group(2)
    
    # Try dot notation after WS
    match = re.search(r"\.WS\.(\w+)", set_name, re.IGNORECASE)
    if match:
        return match.group(1).replace('_', ' ')
    
    return None


def extract_spell_name(set_name: str) -> Optional[str]:
    """Extract spell name from a set name if present."""
    import re
    
    # Try bracket notation
    match = re.search(r"\[(['\"])(.+?)\1\]", set_name)
    if match:
        return match.group(2)
    
    return None


# =============================================================================
# CAP VALIDATION
# =============================================================================

@dataclass
class CapValidationResult:
    """Result of validating stat caps."""
    total_value: int
    cap: int
    is_capped: bool
    overcap_amount: int
    efficiency_pct: float  # How much of the cap is used


def validate_stat_caps(
    gear: Dict[str, Dict],
    caps: Dict[str, int],
) -> Dict[str, CapValidationResult]:
    """
    Validate that gear respects stat caps and report efficiency.
    
    Args:
        gear: wsdist-format gearset
        caps: Dict of stat_name -> cap_value (e.g., {'gear_haste': 2500})
        
    Returns:
        Dict of stat_name -> CapValidationResult
    """
    results = {}
    
    # Calculate totals for each capped stat
    stat_totals = {}
    for stat_name in caps:
        stat_totals[stat_name] = 0
    
    # Stat name mappings (gear stat names to profile stat names)
    stat_mappings = {
        'gear_haste': ['Gear Haste', 'Haste', 'gear_haste'],
        'fast_cast': ['Fast Cast', 'fast_cast', '"Fast Cast"'],
        'damage_taken': ['DT', 'Damage Taken', 'damage_taken', 'DT%'],
        'physical_dt': ['PDT', 'Physical Damage Taken', 'physical_dt', 'PDT%'],
        'magical_dt': ['MDT', 'Magical Damage Taken', 'magical_dt', 'MDT%'],
    }
    
    for slot, item in gear.items():
        if item is None or item.get('Name') == 'Empty':
            continue
        
        for cap_stat, cap_value in caps.items():
            # Get possible stat names
            possible_names = stat_mappings.get(cap_stat, [cap_stat])
            
            for stat_name in possible_names:
                if stat_name in item:
                    value = item[stat_name]
                    if isinstance(value, (int, float)):
                        stat_totals[cap_stat] = stat_totals.get(cap_stat, 0) + value
    
    # Build results
    for stat_name, cap_value in caps.items():
        total = stat_totals.get(stat_name, 0)
        is_capped = abs(total) >= abs(cap_value)
        overcap = max(0, abs(total) - abs(cap_value))
        efficiency = min(100.0, (abs(total) / abs(cap_value)) * 100) if cap_value != 0 else 0
        
        results[stat_name] = CapValidationResult(
            total_value=total,
            cap=cap_value,
            is_capped=is_capped,
            overcap_amount=overcap,
            efficiency_pct=efficiency,
        )
    
    return results


# =============================================================================
# SIMULATION FUNCTIONS
# =============================================================================

def simulate_ws_damage(
    gearset: Dict[str, Dict],
    ws_name: str,
    job: str,
    sub_job: str = "war",
    tp: int = 2000,
    buffs: Dict = None,
    target: Dict = None,
    master_level: int = 50,
) -> Tuple[float, Dict]:
    """
    Simulate weaponskill damage.
    
    Returns:
        (damage, player_stats)
    """
    if not WSDIST_AVAILABLE:
        return 0.0, {}
    
    if buffs is None:
        buffs = MELEE_STANDARD_BUFFS
    
    if target is None:
        target = TARGETS["apex_toad_debuffed"]
    
    # Create player
    player = create_player(
        main_job=job.lower(),
        sub_job=sub_job.lower(),
        master_level=master_level,
        gearset=gearset,
        buffs=buffs,
        abilities={},
    )
    
    # Create enemy
    enemy = create_enemy(target)
    
    # Determine WS type
    # This is simplified - ideally we'd look up the WS in ws_database
    ws_type = "melee"  # Default to melee
    
    magical_ws = {'Sanguine Blade', 'Red Lotus Blade', 'Seraph Blade', 'Aeolian Edge',
                  'Leaden Salute', 'Wildfire', 'Hot Shot', 'Trueflight'}
    hybrid_ws = {'Savage Blade', 'Expiacion', 'Requiescat'}
    
    if ws_name in magical_ws:
        ws_type = "magic"
    elif ws_name in hybrid_ws:
        ws_type = "hybrid"
    
    try:
        damage, _ = average_ws(
            player=player,
            enemy=enemy,
            ws_name=ws_name,
            input_tp=tp,
            ws_type=ws_type,
            input_metric="Damage",
            simulation=False,
        )
        return damage, player.stats if hasattr(player, 'stats') else {}
    except Exception as e:
        print(f"WS simulation error: {e}")
        return 0.0, {}


def simulate_tp_metrics(
    gearset: Dict[str, Dict],
    job: str,
    sub_job: str = "war",
    buffs: Dict = None,
    target: Dict = None,
    master_level: int = 50,
) -> Dict[str, float]:
    """
    Simulate TP set metrics (time to WS, TP per round, DPS).
    
    Returns:
        Dict with time_to_ws, tp_per_round, dps, etc.
    """
    if not WSDIST_AVAILABLE:
        return {'time_to_ws': 999, 'tp_per_round': 0, 'dps': 0}
    
    if buffs is None:
        buffs = MELEE_STANDARD_BUFFS
    
    if target is None:
        target = TARGETS["apex_toad_debuffed"]
    
    # Create player
    player = create_player(
        main_job=job.lower(),
        sub_job=sub_job.lower(),
        master_level=master_level,
        gearset=gearset,
        buffs=buffs,
        abilities={},
    )
    
    # Create enemy
    enemy = create_enemy(target)
    
    try:
        result = average_attack_round(
            player=player,
            enemy=enemy,
            starting_tp=0,
            ws_threshold=1000,
            input_metric="Time to WS",
            simulation=False,
        )
        
        time_to_ws = result[0]
        damage_per_round = result[1][0]
        tp_per_round = result[1][1]
        time_per_round = result[1][2]
        
        dps = damage_per_round / time_per_round if time_per_round > 0 else 0
        
        return {
            'time_to_ws': time_to_ws,
            'tp_per_round': tp_per_round,
            'damage_per_round': damage_per_round,
            'time_per_round': time_per_round,
            'dps': dps,
        }
    except Exception as e:
        print(f"TP simulation error: {e}")
        return {'time_to_ws': 999, 'tp_per_round': 0, 'dps': 0}


def simulate_magic_damage(
    gearset: Dict[str, Dict],
    spell_name: str,
    job: str,
    magic_burst: bool = False,
    target: str = "apex_mob",
    buffs: Dict = None,
) -> Tuple[float, float]:
    """
    Simulate magic damage using the MagicSimulator.
    
    Args:
        gearset: wsdist-format gear dictionary
        spell_name: Name of the spell to simulate
        job: Job abbreviation (e.g., 'BLM', 'RDM', 'SCH')
        magic_burst: Whether to simulate magic burst damage
        target: Target preset name
        buffs: Optional buff overrides (uses MAGIC_DAMAGE_BUFFS if None)
        
    Returns:
        (average_damage, unresisted_rate)
    """
    if not MAGIC_AVAILABLE:
        return 0.0, 0.0
    
    if buffs is None:
        buffs = MAGIC_DAMAGE_BUFFS
    
    # Job base stats for magic jobs (at ML50)
    JOB_BASE_STATS = {
        'BLM': {'INT': 115, 'MND': 100, 'elemental_skill': 512, 'dark_skill': 424, 'mbb_trait': 1300, 'mbb_jp': 500, 'mbb_gifts': 500},
        'RDM': {'INT': 110, 'MND': 110, 'elemental_skill': 488, 'dark_skill': 404, 'enfeebling_skill': 505, 'mbb_trait': 500, 'mbb_jp': 0, 'mbb_gifts': 0},
        'SCH': {'INT': 112, 'MND': 108, 'elemental_skill': 494, 'dark_skill': 414, 'mbb_trait': 1300, 'mbb_jp': 500, 'mbb_gifts': 1000},
        'GEO': {'INT': 108, 'MND': 106, 'elemental_skill': 465, 'dark_skill': 386, 'mbb_trait': 0, 'mbb_jp': 0, 'mbb_gifts': 0},
        'WHM': {'INT': 100, 'MND': 115, 'elemental_skill': 386, 'dark_skill': 354, 'divine_skill': 512, 'mbb_trait': 0, 'mbb_jp': 0, 'mbb_gifts': 0},
        'DRK': {'INT': 105, 'MND': 95, 'elemental_skill': 386, 'dark_skill': 465, 'mbb_trait': 0, 'mbb_jp': 0, 'mbb_gifts': 0},
        'NIN': {'INT': 100, 'MND': 95, 'elemental_skill': 386, 'ninjutsu_skill': 465, 'mbb_trait': 0, 'mbb_jp': 0, 'mbb_gifts': 0},
    }
    
    # Default stats for jobs not in list
    job_upper = job.upper() if job else 'BLM'
    job_stats = JOB_BASE_STATS.get(job_upper, {
        'INT': 100, 'MND': 100, 'elemental_skill': 400, 'dark_skill': 354, 
        'mbb_trait': 0, 'mbb_jp': 0, 'mbb_gifts': 0
    })
    
    # Initialize caster stats with job base
    caster = CasterStats(
        int_stat=job_stats['INT'],
        mnd_stat=job_stats['MND'],
        mab=0,
        magic_damage=0,
        magic_accuracy=0,
        elemental_magic_skill=job_stats.get('elemental_skill', 400),
        dark_magic_skill=job_stats.get('dark_skill', 354),
        divine_magic_skill=job_stats.get('divine_skill', 354),
        enfeebling_magic_skill=job_stats.get('enfeebling_skill', 404),
        mbb_trait=job_stats.get('mbb_trait', 0),
        mbb_jp=job_stats.get('mbb_jp', 0),
        mbb_gifts=job_stats.get('mbb_gifts', 0),
        mbb_gear=0,
        mbb_ii_gear=0,
    )
    
    # Apply buffs
    for buff_source, buff_stats in buffs.items():
        if isinstance(buff_stats, dict):
            caster.int_stat += buff_stats.get('INT', 0)
            caster.mnd_stat += buff_stats.get('MND', 0)
            caster.mab += buff_stats.get('Magic Attack', buff_stats.get('Magic Atk. Bonus', 0))
            caster.magic_accuracy += buff_stats.get('Magic Accuracy', 0)
            # MAB% (like Geo-Acumen) - convert to flat MAB approximation
            mab_pct = buff_stats.get('Magic Attack%', 0)
            if mab_pct > 0:
                caster.mab += int(mab_pct * 3)  # Rough approximation: 35% ≈ +105 MAB
    
    # Stat name variants in wsdist gear format
    STAT_NAMES = {
        'INT': ['INT'],
        'MND': ['MND'],
        'MAB': ['Magic Atk. Bonus', 'Magic Attack Bonus', 'Magic Attack', 'MAB'],
        'MAGIC_DAMAGE': ['Magic Damage', '"Mag.Dmg."+', 'Mag. Dmg.'],
        'MAGIC_ACC': ['Magic Accuracy', 'Mag. Acc.', 'Magic Acc.'],
        'MBB': ['Magic Burst Bonus', '"Magic Burst Bonus"+', 'Magic Burst Dmg.'],
        'MBB_II': ['Magic Burst Bonus II', '"Magic Burst Bonus II"+'],
        'ELEM_SKILL': ['Elemental Magic Skill', 'Elemental magic skill'],
        'DARK_SKILL': ['Dark Magic Skill', 'Dark magic skill'],
        'AFFINITY_FIRE': ['Fire Affinity', 'Fire affinity'],
        'AFFINITY_ICE': ['Ice Affinity', 'Ice affinity', 'Blizzard Affinity'],
        'AFFINITY_WIND': ['Wind Affinity', 'Wind affinity'],
        'AFFINITY_EARTH': ['Earth Affinity', 'Earth affinity'],
        'AFFINITY_THUNDER': ['Thunder Affinity', 'Thunder affinity', 'Lightning Affinity'],
        'AFFINITY_WATER': ['Water Affinity', 'Water affinity'],
        'AFFINITY_LIGHT': ['Light Affinity', 'Light affinity'],
        'AFFINITY_DARK': ['Dark Affinity', 'Dark affinity'],
    }
    
    def get_stat(item: Dict, stat_key: str) -> int:
        """Get stat value trying multiple name variants."""
        for name in STAT_NAMES.get(stat_key, [stat_key]):
            if name in item:
                val = item[name]
                if isinstance(val, (int, float)):
                    return int(val)
        return 0
    
    # Aggregate stats from gear
    for slot, item in gearset.items():
        if item is None or item.get('Name') == 'Empty':
            continue
        
        caster.int_stat += get_stat(item, 'INT')
        caster.mnd_stat += get_stat(item, 'MND')
        caster.mab += get_stat(item, 'MAB')
        caster.magic_damage += get_stat(item, 'MAGIC_DAMAGE')
        caster.magic_accuracy += get_stat(item, 'MAGIC_ACC')
        
        # MBB is in percent, CasterStats expects basis points (40% = 4000)
        mbb = get_stat(item, 'MBB')
        if mbb > 0:
            caster.mbb_gear += mbb * 100  # Convert % to basis points
        
        mbb_ii = get_stat(item, 'MBB_II')
        if mbb_ii > 0:
            caster.mbb_ii_gear += mbb_ii * 100
        
        caster.elemental_magic_skill += get_stat(item, 'ELEM_SKILL')
        caster.dark_magic_skill += get_stat(item, 'DARK_SKILL')
        
        # Element affinity
        affinity_map = {
            'AFFINITY_FIRE': Element.FIRE,
            'AFFINITY_ICE': Element.ICE,
            'AFFINITY_WIND': Element.WIND,
            'AFFINITY_EARTH': Element.EARTH,
            'AFFINITY_THUNDER': Element.THUNDER,
            'AFFINITY_WATER': Element.WATER,
            'AFFINITY_LIGHT': Element.LIGHT,
            'AFFINITY_DARK': Element.DARK,
        } if Element else {}
        for aff_key, element in affinity_map.items():
            aff_val = get_stat(item, aff_key)
            if aff_val > 0:
                current = caster.affinity.get(element, 0)
                caster.affinity[element] = current + (aff_val * 100)  # Convert to basis points
    
    # Cap MBB gear at 40% (4000 basis points) per game mechanics
    caster.mbb_gear = min(caster.mbb_gear, 4000)
    
    # Get target and apply debuffs
    magic_target = MAGIC_TARGETS.get(target)
    if magic_target is None:
        magic_target = MagicTargetStats(
            int_stat=200, mnd_stat=200,
            magic_evasion=600, magic_defense_bonus=30,
        )
    else:
        # Create a copy to apply debuffs
        magic_target = MagicTargetStats(
            int_stat=magic_target.int_stat,
            mnd_stat=magic_target.mnd_stat,
            magic_evasion=magic_target.magic_evasion,
            magic_defense_bonus=magic_target.magic_defense_bonus,
            magic_damage_taken=magic_target.magic_damage_taken,
        )
    
    # Apply debuffs from MAGIC_DAMAGE_DEBUFFS
    debuffs = MAGIC_DAMAGE_DEBUFFS
    magic_target.magic_evasion -= debuffs.get('magic_evasion_down', 0)
    magic_target.magic_defense_bonus -= debuffs.get('magic_defense_down', 0)
    
    # Run simulation
    sim = MagicSimulator(seed=42)
    try:
        result = sim.simulate_spell(
            spell_name=spell_name,
            caster=caster,
            target=magic_target,
            magic_burst=magic_burst,
            num_casts=100,
        )
        return result.average_damage, result.unresisted_rate
    except Exception as e:
        print(f"Magic simulation error for {spell_name}: {e}")
        return 0.0, 0.0


# =============================================================================
# MAIN OPTIMIZATION FUNCTION
# =============================================================================

@dataclass
class SimulationOptimizationResult:
    """Result from simulation-based optimization."""
    gear: Dict[str, Dict]
    score: float
    simulation_value: float  # Damage, time_to_ws, etc.
    optimization_type: SetOptimizationType
    cap_validation: Optional[Dict[str, CapValidationResult]] = None
    stats: Dict[str, Any] = None


def optimize_set_with_simulation(
    inventory: Inventory,
    job: Job,
    set_name: str,
    profile: OptimizationProfile,
    beam_width: int = 50,
    fixed_gear: Dict[str, Dict] = None,
    ws_name: Optional[str] = None,
    spell_name: Optional[str] = None,
    context: str = "",
    master_level: int = 50,
    sub_job: str = "war",
) -> List[SimulationOptimizationResult]:
    """
    Optimize a gear set using beam search + simulation.
    
    Args:
        inventory: Player inventory
        job: Job enum
        set_name: Name of the set being optimized
        profile: Optimization profile for beam search
        beam_width: Number of candidates from beam search
        fixed_gear: Fixed gear (weapons, etc.)
        ws_name: Weaponskill name if WS set
        spell_name: Spell name if magic set
        context: Placeholder context for additional hints
        master_level: Master level for simulation
        sub_job: Sub job for simulation
        
    Returns:
        List of SimulationOptimizationResult sorted by best first
    """
    # Classify the set type
    opt_type = classify_set_type(set_name, context)
    
    # Extract WS/spell name from set name if not provided
    if ws_name is None and opt_type == SetOptimizationType.WS_SIMULATION:
        ws_name = extract_ws_name(set_name)
    
    if spell_name is None and opt_type in (SetOptimizationType.MAGIC_DAMAGE, 
                                            SetOptimizationType.MAGIC_BURST,
                                            SetOptimizationType.MAGIC_ACCURACY):
        spell_name = extract_spell_name(set_name)
    
    # Create a filtered inventory that excludes fishing gear
    filtered_inventory = filter_inventory_fishing_gear(inventory)
    
    # Create optimizer with filtered inventory
    optimizer = BeamSearchOptimizer(
        inventory=filtered_inventory,
        profile=profile,
        beam_width=beam_width,
        job=job,
    )
    
    # Run beam search
    candidates = optimizer.search(fixed_gear=fixed_gear)
    
    if not candidates:
        return []
    
    results = []
    
    # Process based on optimization type
    if opt_type == SetOptimizationType.WS_SIMULATION:
        # Simulate WS damage for each candidate
        for candidate in candidates:
            gearset = _build_gearset(candidate.gear)
            
            if ws_name:
                damage, stats = simulate_ws_damage(
                    gearset=gearset,
                    ws_name=ws_name,
                    job=job.name,
                    sub_job=sub_job,
                    master_level=master_level,
                )
            else:
                # No WS name - use beam score
                damage = candidate.score
                stats = {}
            
            results.append(SimulationOptimizationResult(
                gear=candidate.gear,
                score=candidate.score,
                simulation_value=damage,
                optimization_type=opt_type,
                stats=stats,
            ))
        
        # Sort by simulated damage (descending)
        results.sort(key=lambda x: x.simulation_value, reverse=True)
    
    elif opt_type == SetOptimizationType.TP_SIMULATION:
        # Simulate TP metrics for each candidate
        for candidate in candidates:
            gearset = _build_gearset(candidate.gear)
            
            metrics = simulate_tp_metrics(
                gearset=gearset,
                job=job.name,
                sub_job=sub_job,
                master_level=master_level,
            )
            
            results.append(SimulationOptimizationResult(
                gear=candidate.gear,
                score=candidate.score,
                simulation_value=metrics['time_to_ws'],
                optimization_type=opt_type,
                stats=metrics,
            ))
        
        # Sort by time to WS (ascending - lower is better)
        results.sort(key=lambda x: x.simulation_value)
    
    elif opt_type in (SetOptimizationType.MAGIC_DAMAGE, SetOptimizationType.MAGIC_BURST):
        # Simulate magic damage
        magic_burst = (opt_type == SetOptimizationType.MAGIC_BURST)
        
        for candidate in candidates:
            gearset = _build_gearset(candidate.gear)
            
            if spell_name and MAGIC_AVAILABLE:
                damage, unresisted_rate = simulate_magic_damage(
                    gearset=gearset,
                    spell_name=spell_name,
                    job=job.name,
                    magic_burst=magic_burst,
                )
                stats = {
                    'spell_name': spell_name,
                    'magic_burst': magic_burst,
                    'unresisted_rate': unresisted_rate,
                }
            else:
                damage = candidate.score
                stats = {'spell_name': spell_name or 'Unknown'}
            
            results.append(SimulationOptimizationResult(
                gear=candidate.gear,
                score=candidate.score,
                simulation_value=damage,
                optimization_type=opt_type,
                stats=stats,
            ))
        
        # Sort by damage (descending)
        results.sort(key=lambda x: x.simulation_value, reverse=True)
    
    elif opt_type == SetOptimizationType.DT_CAPPED:
        # Validate DT caps
        dt_caps = {
            'damage_taken': -5000,      # -50%
            'physical_dt': -5000,
            'magical_dt': -5000,
        }
        
        for candidate in candidates:
            cap_results = validate_stat_caps(candidate.gear, dt_caps)
            
            # Penalize overcapping
            efficiency_score = sum(r.efficiency_pct for r in cap_results.values()) / len(cap_results)
            overcap_penalty = sum(r.overcap_amount for r in cap_results.values())
            adjusted_score = candidate.score - (overcap_penalty * 0.1)
            
            results.append(SimulationOptimizationResult(
                gear=candidate.gear,
                score=candidate.score,
                simulation_value=efficiency_score,
                optimization_type=opt_type,
                cap_validation=cap_results,
            ))
        
        # Sort by beam score (considering overcap penalty handled in beam search)
        results.sort(key=lambda x: x.score, reverse=True)
    
    elif opt_type == SetOptimizationType.FC_CAPPED:
        # Validate FC cap
        fc_caps = {
            'fast_cast': 8000,  # 80%
        }
        
        for candidate in candidates:
            cap_results = validate_stat_caps(candidate.gear, fc_caps)
            
            results.append(SimulationOptimizationResult(
                gear=candidate.gear,
                score=candidate.score,
                simulation_value=cap_results.get('fast_cast', CapValidationResult(0, 8000, False, 0, 0)).efficiency_pct,
                optimization_type=opt_type,
                cap_validation=cap_results,
            ))
        
        # Sort by beam score
        results.sort(key=lambda x: x.score, reverse=True)
    
    else:
        # Beam search only
        for candidate in candidates:
            results.append(SimulationOptimizationResult(
                gear=candidate.gear,
                score=candidate.score,
                simulation_value=candidate.score,
                optimization_type=opt_type,
            ))
    
    return results


def _build_gearset(gear: Dict[str, Dict]) -> Dict[str, Dict]:
    """Build a complete gearset with Empty items for missing slots.
    
    Also sanitizes all gear items to ensure numeric stats are integers,
    preventing type errors when wsdist sums the stats.
    """
    gearset = {}
    for slot in WSDIST_SLOTS:
        if slot in gear and gear[slot]:
            # Sanitize the gear item to ensure all stats are numeric
            gearset[slot] = sanitize_gear_item(gear[slot].copy())
        else:
            gearset[slot] = Empty.copy()
    return gearset


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_optimization_config(opt_type: SetOptimizationType) -> Dict[str, Any]:
    """Get the buff/debuff configuration for an optimization type."""
    configs = {
        SetOptimizationType.WS_SIMULATION: {
            'buffs': MELEE_STANDARD_BUFFS,
            'debuffs': MELEE_STANDARD_DEBUFFS,
            'target': 'apex_toad_debuffed',
        },
        SetOptimizationType.TP_SIMULATION: {
            'buffs': MELEE_STANDARD_BUFFS,
            'debuffs': MELEE_STANDARD_DEBUFFS,
            'target': 'apex_toad_debuffed',
        },
        SetOptimizationType.MAGIC_DAMAGE: {
            'buffs': MAGIC_DAMAGE_BUFFS,
            'debuffs': MAGIC_DAMAGE_DEBUFFS,
            'target': 'apex_mob',
        },
        SetOptimizationType.MAGIC_BURST: {
            'buffs': MAGIC_DAMAGE_BUFFS,
            'debuffs': MAGIC_DAMAGE_DEBUFFS,
            'target': 'apex_mob',
        },
        SetOptimizationType.MAGIC_ACCURACY: {
            'buffs': MAGIC_ACCURACY_BUFFS,
            'debuffs': MAGIC_ACCURACY_DEBUFFS,
            'target': 'odyssey_nm',  # Higher magic evasion for acc testing
        },
    }
    return configs.get(opt_type, {})
