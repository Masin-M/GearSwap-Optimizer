"""
Item Database Loader

Parses Windower's items.lua resource file and loads it into Python data structures.
"""

import re
import os
from pathlib import Path
from typing import Dict, Optional, List, Tuple, Any
from dataclasses import dataclass, field
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
WSDIST_DIR = SCRIPT_DIR / 'wsdist_beta-main'

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(WSDIST_DIR))
from models import ItemBase, Stats, Slot, SLOT_BITMASK


class LuaTableParser:
    """
    Parser for Lua table syntax used in Windower resource files.
    
    Handles the format:
    return {
        [id] = {key=value, key=value, ...},
        ...
    }
    """
    
    def __init__(self, content: str):
        self.content = content
        self.pos = 0
    
    def parse(self) -> Dict[int, Dict[str, Any]]:
        """Parse the Lua file and return a dict of id -> item data."""
        # Skip to the opening brace
        self._skip_to_table_start()
        return self._parse_table()
    
    def _skip_to_table_start(self):
        """Skip past 'return {' to the table contents."""
        # Find 'return' followed by '{'
        match = re.search(r'return\s*\{', self.content)
        if match:
            self.pos = match.end()
        else:
            raise ValueError("Could not find 'return {' in Lua file")
    
    def _skip_whitespace(self):
        """Skip whitespace and comments."""
        while self.pos < len(self.content):
            c = self.content[self.pos]
            if c in ' \t\n\r':
                self.pos += 1
            elif c == '-' and self.pos + 1 < len(self.content) and self.content[self.pos + 1] == '-':
                # Skip line comment
                while self.pos < len(self.content) and self.content[self.pos] != '\n':
                    self.pos += 1
            else:
                break
    
    def _parse_table(self) -> Dict[int, Dict[str, Any]]:
        """Parse a Lua table with numeric keys."""
        result = {}
        self._skip_whitespace()
        
        while self.pos < len(self.content):
            self._skip_whitespace()
            
            if self.content[self.pos] == '}':
                self.pos += 1
                break
            
            if self.content[self.pos] == ',':
                self.pos += 1
                continue
            
            # Parse [key] = value or key = value
            if self.content[self.pos] == '[':
                self.pos += 1
                key = self._parse_number()
                self._skip_whitespace()
                if self.content[self.pos] == ']':
                    self.pos += 1
                self._skip_whitespace()
                if self.content[self.pos] == '=':
                    self.pos += 1
                self._skip_whitespace()
                
                value = self._parse_value()
                if isinstance(key, int) and isinstance(value, dict):
                    result[key] = value
            else:
                # Skip malformed entries
                self._skip_to_next_entry()
        
        return result
    
    def _parse_value(self) -> Any:
        """Parse a Lua value (string, number, table, etc.)."""
        self._skip_whitespace()
        
        if self.pos >= len(self.content):
            return None
        
        c = self.content[self.pos]
        
        if c == '{':
            return self._parse_inner_table()
        elif c == '"' or c == "'":
            return self._parse_string()
        elif c == '-' or c.isdigit():
            return self._parse_number()
        elif self.content[self.pos:self.pos+4] == 'true':
            self.pos += 4
            return True
        elif self.content[self.pos:self.pos+5] == 'false':
            self.pos += 5
            return False
        elif self.content[self.pos:self.pos+3] == 'nil':
            self.pos += 3
            return None
        else:
            # Identifier or other
            return self._parse_identifier()
    
    def _parse_inner_table(self) -> Dict[str, Any]:
        """Parse a Lua table with string keys (item data)."""
        result = {}
        self.pos += 1  # Skip '{'
        
        while self.pos < len(self.content):
            self._skip_whitespace()
            
            if self.content[self.pos] == '}':
                self.pos += 1
                break
            
            if self.content[self.pos] == ',':
                self.pos += 1
                continue
            
            # Parse key
            if self.content[self.pos] == '[':
                self.pos += 1
                if self.content[self.pos] == '"' or self.content[self.pos] == "'":
                    key = self._parse_string()
                else:
                    key = self._parse_number()
                self._skip_whitespace()
                if self.content[self.pos] == ']':
                    self.pos += 1
            else:
                key = self._parse_identifier()
            
            self._skip_whitespace()
            
            if self.pos < len(self.content) and self.content[self.pos] == '=':
                self.pos += 1
                self._skip_whitespace()
                value = self._parse_value()
                result[key] = value
        
        return result
    
    def _parse_string(self) -> str:
        """Parse a quoted string."""
        quote = self.content[self.pos]
        self.pos += 1
        result = []
        
        while self.pos < len(self.content):
            c = self.content[self.pos]
            
            if c == quote:
                self.pos += 1
                break
            elif c == '\\':
                self.pos += 1
                if self.pos < len(self.content):
                    escaped = self.content[self.pos]
                    if escaped == 'n':
                        result.append('\n')
                    elif escaped == 't':
                        result.append('\t')
                    elif escaped == 'r':
                        result.append('\r')
                    else:
                        result.append(escaped)
                    self.pos += 1
            else:
                result.append(c)
                self.pos += 1
        
        return ''.join(result)
    
    def _parse_number(self) -> int:
        """Parse a number."""
        start = self.pos
        
        if self.content[self.pos] == '-':
            self.pos += 1
        
        while self.pos < len(self.content) and (self.content[self.pos].isdigit() or self.content[self.pos] == '.'):
            self.pos += 1
        
        num_str = self.content[start:self.pos]
        try:
            if '.' in num_str:
                return float(num_str)
            return int(num_str)
        except ValueError:
            return 0
    
    def _parse_identifier(self) -> str:
        """Parse an identifier."""
        start = self.pos
        
        while self.pos < len(self.content) and (self.content[self.pos].isalnum() or self.content[self.pos] == '_'):
            self.pos += 1
        
        return self.content[start:self.pos]
    
    def _skip_to_next_entry(self):
        """Skip to the next table entry."""
        depth = 0
        while self.pos < len(self.content):
            c = self.content[self.pos]
            if c == '{':
                depth += 1
            elif c == '}':
                if depth == 0:
                    break
                depth -= 1
            elif c == ',' and depth == 0:
                self.pos += 1
                break
            self.pos += 1


class ItemDatabase:
    """
    Database of all FFXI items loaded from Windower resources.
    """
    
    def __init__(self):
        self.items: Dict[int, ItemBase] = {}
        self.items_by_name: Dict[str, ItemBase] = {}
        self.descriptions: Dict[int, str] = {}
    
    def load_from_lua(self, items_lua_path: str, descriptions_lua_path: Optional[str] = None):
        """
        Load items from Windower's items.lua file.
        
        Args:
            items_lua_path: Path to items.lua
            descriptions_lua_path: Optional path to item_descriptions.lua
        """
        # Load main items file
        with open(items_lua_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        parser = LuaTableParser(content)
        raw_items = parser.parse()
        
        # Load descriptions if provided
        if descriptions_lua_path and os.path.exists(descriptions_lua_path):
            with open(descriptions_lua_path, 'r', encoding='utf-8') as f:
                desc_content = f.read()
            
            desc_parser = LuaTableParser(desc_content)
            self.descriptions = {}
            raw_descs = desc_parser.parse()
            for item_id, desc_data in raw_descs.items():
                if isinstance(desc_data, dict):
                    self.descriptions[item_id] = desc_data.get('en', '')
                elif isinstance(desc_data, str):
                    self.descriptions[item_id] = desc_data
        
        # Convert raw items to ItemBase objects
        for item_id, data in raw_items.items():
            item = self._create_item(item_id, data)
            if item:
                self.items[item_id] = item
                self.items_by_name[item.name.lower()] = item
                if item.name_log:
                    self.items_by_name[item.name_log.lower()] = item
    
    def _create_item(self, item_id: int, data: Dict[str, Any]) -> Optional[ItemBase]:
        """Create an ItemBase from raw Lua data."""
        try:
            item = ItemBase(
                id=item_id,
                name=data.get('en', data.get('english', f'Item_{item_id}')),
                name_log=data.get('enl', data.get('english_log', '')),
                category=data.get('category', ''),
                item_type=data.get('type', 0),
                jobs=data.get('jobs', 0),
                level=data.get('level', 0),
                item_level=data.get('item_level', data.get('ilevel', 0)),
                superior_level=data.get('superior_level', 0),
                races=data.get('races', 0),
                slots=data.get('slots', 0),
                skill=data.get('skill', 0),
                damage=data.get('damage', 0),
                delay=data.get('delay', 0),
                flags=data.get('flags', 0),
                stack=data.get('stack', 1),
                targets=data.get('targets', 0),
            )
            
            # Set base stats for weapons
            if item.damage > 0:
                item.base_stats.damage = item.damage
            if item.delay > 0:
                item.base_stats.delay = item.delay
            
            # Parse description for stats if available
            if item_id in self.descriptions:
                item.description = self.descriptions[item_id]
                self._parse_description_stats(item)
            
            return item
            
        except Exception as e:
            print(f"Warning: Failed to create item {item_id}: {e}")
            return None
    
    # Conditional prefix patterns - stats after these only apply in specific situations
    # Format: (regex pattern, target field name or None to ignore)
    CONDITIONAL_PREFIXES = [
        # Prefixes to parse into separate stat buckets
        (r'Pet:\s*', 'pet'),
        (r'Automaton:\s*', 'automaton'),
        (r'(?:In\s+)?Dynamis:\s*', 'dynamis'),
        (r'Avatar:\s*', 'avatar'),
        (r'Wyvern:\s*', 'wyvern'),
        (r'Daytime:\s*', 'daytime'),
        # Day-specific prefixes (will be stored in day_stats dict)
        (r'(Firesday)s?:\s*', 'day'),
        (r'(Earthsday)s?:\s*', 'day'),
        (r'(Watersday)s?:\s*', 'day'),
        (r'(Windsday)s?:\s*', 'day'),
        (r'(Iceday)s?:\s*', 'day'),
        (r'(Lightningsday)s?:\s*', 'day'),
        (r'(Lightsday)s?:\s*', 'day'),
        (r'(Darksday)s?:\s*', 'day'),
        # Prefixes to IGNORE (old content, stats don't apply in normal situations)
        (r'Reives?:\s*', None),
        (r'Campaign:\s*', None),
        (r'Assault:\s*', None),
        (r'Salvage:\s*', None),
        (r'Domain Invasion:\s*', None),
    ]
    
    # Common stat patterns in FFXI item descriptions
    # Note: Pattern value format is (regex, stat_name, multiplier)
    # Multiplier of 100 converts percentage to basis points
    STAT_PATTERNS = [
        # Primary stats
        (r'STR\s*[+]?\s*(\d+)', 'STR', 1),
        (r'DEX\s*[+]?\s*(\d+)', 'DEX', 1),
        (r'VIT\s*[+]?\s*(\d+)', 'VIT', 1),
        (r'AGI\s*[+]?\s*(\d+)', 'AGI', 1),
        (r'INT\s*[+]?\s*(\d+)', 'INT', 1),
        (r'MND\s*[+]?\s*(\d+)', 'MND', 1),
        (r'CHR\s*[+]?\s*(\d+)', 'CHR', 1),
        
        # HP/MP
        (r'HP\s*[+]?\s*(\d+)', 'HP', 1),
        (r'MP\s*[+]?\s*(\d+)', 'MP', 1),
        
        # Offensive
        # Note: Negative lookbehinds prevent "Magic Accuracy" or "Ranged Accuracy" 
        # from also matching the plain "Accuracy" pattern
        (r'(?<!Magic\s)(?<!Magic)(?<!Ranged\s)(?<!Ranged)Accuracy\s*[+]?\s*(\d+)', 'accuracy', 1),
        (r'(?<!Ranged\s)(?<!Ranged)Attack\s*[+]?\s*(\d+)', 'attack', 1),
        (r'Ranged Accuracy\s*[+]?\s*(\d+)', 'ranged_accuracy', 1),
        (r'Ranged Attack\s*[+]?\s*(\d+)', 'ranged_attack', 1),
        (r'"Mag(?:ic)?\.?\s*Atk\.?\s*(?:Bonus|Bns)\.?"\s*[+]?\s*(\d+)', 'magic_attack', 1),
        (r'Magic Accuracy\s*[+]?\s*(\d+)', 'magic_accuracy', 1),
        (r'Magic Damage\s*[+]?\s*(\d+)', 'magic_damage', 1),
        
        # Haste (convert to basis points)
        # "Haste" on gear IS gear haste - use negative lookbehind to avoid "Magic Haste" or "Gear Haste" 
        # Note: lookbehind handles both with and without space (Magic Haste vs MagicHaste)
        (r'(?<!Magic)(?<!Magic\s)(?<!Gear)(?<!Gear\s)Haste\s*[+:]?\s*(\d+)%?', 'gear_haste', 100),
        
        # Magic Haste from gear (rare, e.g., Erra Pendant) - this is NOT the same as gear haste!
        # Magic haste from gear doesn't stack with Haste spells, so it's nearly useless with support
        (r'Magic\s*Haste\s*[+:]?\s*(\d+)%?', 'magic_haste', 100),
        
        # Store TP (can be negative, e.g., "Store TP"-4)
        (r'"Store\s*TP"\s*([+-]?\d+)', 'store_tp', 1),
        (r'Store TP\s*([+-]?\d+)', 'store_tp', 1),
        
        # Multi-attack (percentages to basis points)
        (r'"Double Attack"\s*[+]?\s*(\d+)%?', 'double_attack', 100),
        (r'"Triple Attack"\s*[+]?\s*(\d+)%?', 'triple_attack', 100),
        (r'"Quad\.?\s*Attack"\s*[+]?\s*(\d+)%?', 'quad_attack', 100),
        
        # Dual Wield
        (r'"Dual Wield"\s*[+]?\s*(\d+)%?', 'dual_wield', 100),
        
        # Critical - use negative lookbehind to avoid matching "Magic critical hit rate"
        (r'(?<!Magic\s)(?<!Magic)Critical hit rate\s*[+]?\s*(\d+)%?', 'crit_rate', 100),
        (r'"Crit\.?\s*hit"\s*[+]?\s*(\d+)%?', 'crit_rate', 100),
        
        # Magic Critical hit rate (separate stat, e.g., Locus Ring)
        (r'Magic critical hit rate\s*[+]?\s*(\d+)%?', 'magic_crit_rate', 100),
        
        # Defense - matches both "Defense+X" and "DEF:X" formats
        (r'(?:Defense|DEF)\s*[+:]?\s*(\d+)', 'defense', 1),
        # Note: Negative lookbehind prevents "Magic Evasion" from also matching plain "Evasion"
        (r'(?<!Magic\s)(?<!Magic)Evasion\s*[+]?\s*(\d+)', 'evasion', 1),
        (r'Magic Evasion\s*[+]?\s*(\d+)', 'magic_evasion', 1),
        (r'Magic Def\.?\s*Bonus\s*[+]?\s*(\d+)', 'magic_defense', 1),
        
        # Damage Taken - Each type is independent, all can apply
        # Physical damage taken (format: "Physical damage taken -4%")
        (r'Phys(?:ical)?\.?\s*(?:dmg|damage)\.?\s*taken\s*([+-]?\d+)%?', 'physical_dt', 100),
        # Magical damage taken (format: "Magic damage taken -5%")
        (r'Mag(?:ic)?\.?\s*(?:dmg|damage)\.?\s*taken\s*([+-]?\d+)%?', 'magical_dt', 100),
        # Breath damage taken (format: "Breath damage taken -5%")
        (r'Breath\.?\s*(?:dmg|damage)\.?\s*taken\s*([+-]?\d+)%?', 'breath_dt', 100),
        # General damage taken - only match if not preceded by Physical/Magic/Breath
        # Format: "Damage taken -11%" or "Dmg. taken -5%"
        (r'(?<!Physical\s)(?<!Phys\.\s)(?<!Magic\s)(?<!Mag\.\s)(?<!Breath\s)(?:Dmg|Damage)\.?\s*taken\s*([+-]?\d+)%?', 'damage_taken', 100),
        
        # Weaponskill
        (r'Weapon\s*skill\s*damage\s*[+]?\s*(\d+)%?', 'ws_damage', 100),
        (r'"WS(?:D|Dmg)"\s*[+]?\s*(\d+)%?', 'ws_damage', 100),
        
        # Magic stats
        (r'"Magic Burst Bonus"\s*[+]?\s*(\d+)%?', 'magic_burst_bonus', 100),
        (r'Magic burst dmg\.?\s*[+]?\s*(\d+)%?', 'magic_burst_bonus', 100),
        (r'MB\s*[+]?\s*(\d+)%?', 'magic_burst_bonus', 100),
        # "Bonus damage added to magic burst" has no number - capture optional, default handled in parser
        (r'Bonus damage added to magic burst\.?(?:\s*[+]?\s*(\d+)%?)?', 'magic_burst_bonus', 100),
        (r'"Cure potency"\s*[+]?\s*(\d+)%?', 'cure_potency', 100),
        (r'Cure potency\s*[+]?\s*(\d+)%?', 'cure_potency', 100),
        (r'"Cure Potency II"\s*[+]?\s*(\d+)%?', 'cure_potency_ii', 100),
        (r'Healing magic skill\s*[+]?\s*(\d+)', 'healing_magic_skill', 1),
        (r'Enfeebling magic skill\s*[+]?\s*(\d+)', 'enfeebling_magic_skill', 1),
        (r'Enhancing magic skill\s*[+]?\s*(\d+)', 'enhancing_magic_skill', 1),
        (r'Elemental magic skill\s*[+]?\s*(\d+)', 'elemental_magic_skill', 1),
        (r'Divine magic skill\s*[+]?\s*(\d+)', 'divine_magic_skill', 1),
        (r'Dark magic skill\s*[+]?\s*(\d+)', 'dark_magic_skill', 1),
        (r'Enfeebling magic effect\s*[+]?\s*(\d+)', 'enfeebling_effect', 1),
        (r'Enhancing magic duration\s*[+]?\s*(\d+)%?', 'enhancing_duration', 100),
        (r'"Fast Cast"\s*[+]?\s*(\d+)%?', 'fast_cast', 100),
        (r'Fast Cast\s*[+]?\s*(\d+)%?', 'fast_cast', 100),
        
        # Combat skill bonuses (from gear)
        # Note: These are flat skill bonuses that add to character skill cap
        # Order matters - put compound names (Great Sword) before simple names (Sword)
        # to prevent "Great Sword skill" from matching "Sword skill"
        (r'Hand-to-Hand\s+skill\s*[+]?\s*(\d+)', 'hand_to_hand_skill', 1),
        (r'H2H\s+skill\s*[+]?\s*(\d+)', 'hand_to_hand_skill', 1),
        (r'Dagger\s+skill\s*[+]?\s*(\d+)', 'dagger_skill', 1),
        # Great versions first, then simple versions with word boundary
        (r'Great\s+Sword\s+skill\s*[+]?\s*(\d+)', 'great_sword_skill', 1),
        (r'Greatsword\s+skill\s*[+]?\s*(\d+)', 'great_sword_skill', 1),
        (r'\bSword\s+skill\s*[+]?\s*(\d+)', 'sword_skill', 1),
        (r'Great\s+Axe\s+skill\s*[+]?\s*(\d+)', 'great_axe_skill', 1),
        (r'Greataxe\s+skill\s*[+]?\s*(\d+)', 'great_axe_skill', 1),
        (r'\bAxe\s+skill\s*[+]?\s*(\d+)', 'axe_skill', 1),
        (r'Great\s+Katana\s+skill\s*[+]?\s*(\d+)', 'great_katana_skill', 1),
        (r'Greatkatana\s+skill\s*[+]?\s*(\d+)', 'great_katana_skill', 1),
        (r'G\.\s*Katana\s+skill\s*[+]?\s*(\d+)', 'great_katana_skill', 1),
        (r'\bKatana\s+skill\s*[+]?\s*(\d+)', 'katana_skill', 1),
        (r'Scythe\s+skill\s*[+]?\s*(\d+)', 'scythe_skill', 1),
        (r'Polearm\s+skill\s*[+]?\s*(\d+)', 'polearm_skill', 1),
        (r'Club\s+skill\s*[+]?\s*(\d+)', 'club_skill', 1),
        (r'Staff\s+skill\s*[+]?\s*(\d+)', 'staff_skill', 1),
        (r'Archery\s+skill\s*[+]?\s*(\d+)', 'archery_skill', 1),
        (r'Marksmanship\s+skill\s*[+]?\s*(\d+)', 'marksmanship_skill', 1),
        (r'Throwing\s+skill\s*[+]?\s*(\d+)', 'throwing_skill', 1),
        (r'Evasion\s+skill\s*[+]?\s*(\d+)', 'evasion_skill', 1),
        (r'Shield\s+skill\s*[+]?\s*(\d+)', 'shield_skill', 1),
        (r'Parrying\s+skill\s*[+]?\s*(\d+)', 'parrying_skill', 1),
        (r'Guard\s+skill\s*[+]?\s*(\d+)', 'guard_skill', 1),
        
        # Additional magic skills that might appear on gear
        (r'Singing\s+skill\s*[+]?\s*(\d+)', 'singing_skill', 1),
        (r'Wind\s+instrument\s+skill\s*[+]?\s*(\d+)', 'wind_instrument_skill', 1),
        (r'String\s+instrument\s+skill\s*[+]?\s*(\d+)', 'string_instrument_skill', 1),
        (r'Ninjutsu\s+skill\s*[+]?\s*(\d+)', 'ninjutsu_skill', 1),
        (r'Blue\s+magic\s+skill\s*[+]?\s*(\d+)', 'blue_magic_skill', 1),
        (r'Geomancy\s+skill\s*[+]?\s*(\d+)', 'geomancy_skill', 1),
        (r'Handbell\s+skill\s*[+]?\s*(\d+)', 'handbell_skill', 1),
        (r'Summoning\s+(?:magic\s+)?skill\s*[+]?\s*(\d+)', 'summoning_magic_skill', 1),
        
        # =========================================================================
        # TP-RELATED STATS (HIGH PRIORITY for wsdist)
        # =========================================================================
        # TP Bonus (54 items in wsdist)
        (r'"TP Bonus"\s*[+]?\s*(\d+)', 'tp_bonus', 1),
        (r'TP Bonus\s*[+]?\s*(\d+)', 'tp_bonus', 1),
        
        # Daken - NIN shuriken throw (16 items)
        (r'"Daken"\s*[+]?\s*(\d+)%?', 'daken', 1),
        (r'Daken\s*[+]?\s*(\d+)%?', 'daken', 1),
        
        # Martial Arts - MNK delay reduction (8 items)
        (r'"Martial Arts"\s*[+]?\s*(\d+)', 'martial_arts', 1),
        (r'Martial Arts\s*[+]?\s*(\d+)', 'martial_arts', 1),
        
        # Zanshin - SAM/2H retry attacks (11 items)
        (r'"Zanshin"\s*[+]?\s*(\d+)%?', 'zanshin', 1),
        (r'Zanshin\s*[+]?\s*(\d+)%?', 'zanshin', 1),
        
        # Kick Attacks - MNK (9 items)
        (r'"Kick Attacks"\s*[+]?\s*(\d+)%?', 'kick_attacks', 1),
        (r'Kick Attacks\s*[+]?\s*(\d+)%?', 'kick_attacks', 1),
        (r'"Kick Attacks Dmg\.?"\s*[+]?\s*(\d+)', 'kick_attacks_dmg', 1),
        
        # Subtle Blow (91 items)
        (r'"Subtle Blow"\s*[+]?\s*(\d+)', 'subtle_blow', 1),
        (r'(?<![I\s])Subtle Blow\s*[+]?\s*(\d+)', 'subtle_blow', 1),
        (r'"Subtle Blow II"\s*[+]?\s*(\d+)', 'subtle_blow_ii', 1),
        (r'Subtle Blow II\s*[+]?\s*(\d+)', 'subtle_blow_ii', 1),
        
        # Fencer trait (7 items)
        (r'"Fencer"\s*[+]?\s*(\d+)', 'fencer', 1),
        (r'Fencer\s*[+]?\s*(\d+)', 'fencer', 1),
        
        # Crit Damage (31 items) - already have crit_rate, need crit_damage
        (r'"Crit(?:ical)?\.?\s*(?:hit\s*)?damage"\s*[+]?\s*(\d+)%?', 'crit_damage', 100),
        (r'Crit(?:ical)?\.?\s*hit\s*damage\s*[+]?\s*(\d+)%?', 'crit_damage', 100),
        
        # Conserve TP (2 items)
        (r'"Conserve TP"\s*[+]?\s*(\d+)%?', 'conserve_tp', 1),
        (r'Conserve TP\s*[+]?\s*(\d+)%?', 'conserve_tp', 1),
        
        # Regain (34 items)
        (r'"Regain"\s*[+]?\s*(\d+)', 'regain', 1),
        (r'Regain\s*[+]?\s*(\d+)', 'regain', 1),
        
        # =========================================================================
        # OCCASIONAL ATTACKS (OA2-OA8, FUA)
        # =========================================================================
        (r'"OA2"\s*[+]?\s*(\d+)%?', 'oa2', 1),
        (r'"OA3"\s*[+]?\s*(\d+)%?', 'oa3', 1),
        (r'"OA4"\s*[+]?\s*(\d+)%?', 'oa4', 1),
        (r'"OA5"\s*[+]?\s*(\d+)%?', 'oa5', 1),
        (r'"OA6"\s*[+]?\s*(\d+)%?', 'oa6', 1),
        (r'"OA7"\s*[+]?\s*(\d+)%?', 'oa7', 1),
        (r'"OA8"\s*[+]?\s*(\d+)%?', 'oa8', 1),
        (r'"FUA"\s*[+]?\s*(\d+)%?', 'fua', 1),
        (r'"Follow-up Attack"\s*[+]?\s*(\d+)%?', 'fua', 1),
        
        # =========================================================================
        # DAMAGE MODIFIERS
        # =========================================================================
        # PDL - Physical Damage Limit (169 items!)
        (r'"PDL"\s*[+]?\s*(\d+)%?', 'pdl', 100),
        (r'Phys(?:ical)?\.?\s*(?:dmg|damage)\.?\s*limit\s*[+]?\s*(\d+)%?', 'pdl', 100),
        
        # Skillchain Bonus (104 items)
        (r'"Skillchain Bonus"\s*[+]?\s*(\d+)%?', 'skillchain_bonus', 100),
        (r'Skillchain (?:dmg|damage)\s*[+]?\s*(\d+)%?', 'skillchain_bonus', 100),
        
        # DA/TA Damage modifiers
        (r'"DA Damage%?"\s*[+]?\s*(\d+)', 'da_damage_pct', 1),
        (r'"TA Damage%?"\s*[+]?\s*(\d+)', 'ta_damage_pct', 1),
        
        # =========================================================================
        # RANGED-SPECIFIC
        # =========================================================================
        (r'"Double Shot"\s*[+]?\s*(\d+)%?', 'double_shot', 1),
        (r'Double Shot\s*[+]?\s*(\d+)%?', 'double_shot', 1),
        (r'"Triple Shot"\s*[+]?\s*(\d+)%?', 'triple_shot', 1),
        (r'Triple Shot\s*[+]?\s*(\d+)%?', 'triple_shot', 1),
        (r'"True Shot"\s*[+]?\s*(\d+)%?', 'true_shot', 1),
        (r'True Shot\s*[+]?\s*(\d+)%?', 'true_shot', 1),
        (r'"Recycle"\s*[+]?\s*(\d+)%?', 'recycle', 1),
        (r'Recycle\s*[+]?\s*(\d+)%?', 'recycle', 1),
        (r'"Barrage"\s*[+]?\s*(\d+)', 'barrage', 1),
        (r'Barrage\s*[+]?\s*(\d+)', 'barrage', 1),
        
        # =========================================================================
        # MAGIC-SPECIFIC
        # =========================================================================
        # Magic Accuracy Skill (302 items!) - different from Magic Accuracy
        (r'Magic Accuracy Skill\s*[+]?\s*(\d+)', 'magic_accuracy_skill', 1),
        (r'"Mag(?:ic)?\.?\s*Acc\.?\s*Skill"\s*[+]?\s*(\d+)', 'magic_accuracy_skill', 1),
        
        # Magic Burst Damage II (48 items in wsdist)
        (r'"Magic Burst Damage II"\s*[+]?\s*(\d+)%?', 'magic_burst_damage_ii', 100),
        (r'Magic Burst Damage II\s*[+]?\s*(\d+)%?', 'magic_burst_damage_ii', 100),
        
        # =========================================================================
        # JOB-SPECIFIC STATS
        # =========================================================================
        # EnSpell (RDM)
        (r'"EnSpell Damage"\s*[+]?\s*(\d+)', 'enspell_damage', 1),
        (r'EnSpell Damage\s*[+]?\s*(\d+)', 'enspell_damage', 1),
        (r'"EnSpell Damage%"\s*[+]?\s*(\d+)', 'enspell_damage_pct', 100),
        
        # Ninjutsu (NIN)
        (r'"Ninjutsu Magic Attack"\s*[+]?\s*(\d+)', 'ninjutsu_magic_attack', 1),
        (r'Ninjutsu (?:magic\s*)?damage\s*[+]?\s*(\d+)%?', 'ninjutsu_damage_pct', 100),
        (r'"Ninjutsu Damage%?"\s*[+]?\s*(\d+)', 'ninjutsu_damage_pct', 100),
        
        # Blood Pact (SMN)
        (r'"Blood Pact Damage"\s*[+]?\s*(\d+)%?', 'blood_pact_damage', 100),
        (r'Blood Pact (?:dmg|damage)\s*[+]?\s*(\d+)%?', 'blood_pact_damage', 100),
        
        # Occult Acumen (11 items)
        (r'"Occult Acumen"\s*[+]?\s*(\d+)', 'occult_acumen', 1),
        (r'Occult Acumen\s*[+]?\s*(\d+)', 'occult_acumen', 1),
        
        # =========================================================================
        # ELEMENTAL BONUSES
        # =========================================================================
        (r'Fire\s+Elemental\s+Bonus\s*[+]?\s*(\d+)', 'fire_elemental_bonus', 1),
        (r'Ice\s+Elemental\s+Bonus\s*[+]?\s*(\d+)', 'ice_elemental_bonus', 1),
        (r'Wind\s+Elemental\s+Bonus\s*[+]?\s*(\d+)', 'wind_elemental_bonus', 1),
        (r'Earth\s+Elemental\s+Bonus\s*[+]?\s*(\d+)', 'earth_elemental_bonus', 1),
        (r'(?:Lightning|Thunder)\s+Elemental\s+Bonus\s*[+]?\s*(\d+)', 'lightning_elemental_bonus', 1),
        (r'Water\s+Elemental\s+Bonus\s*[+]?\s*(\d+)', 'water_elemental_bonus', 1),
        (r'Light\s+Elemental\s+Bonus\s*[+]?\s*(\d+)', 'light_elemental_bonus', 1),
        (r'Dark\s+Elemental\s+Bonus\s*[+]?\s*(\d+)', 'dark_elemental_bonus', 1),
    ]
    
    def _segment_description(self, desc: str) -> List[Tuple[Optional[str], Optional[str], str]]:
        """
        Segment a description into sections based on conditional prefixes.
        
        Returns a list of tuples: (condition_type, day_name_if_applicable, text_segment)
        - condition_type is None for base stats, 'pet', 'dynamis', etc., or None for ignored sections
        - day_name is set only when condition_type is 'day' (e.g., 'firesday')
        - text_segment is the text belonging to that condition
        
        Ignored prefixes (Reives, Campaign, etc.) return condition_type=None with empty segment.
        """
        segments = []
        
        # Build a combined pattern to find all conditional prefixes
        # We need to track the position and type of each prefix
        prefix_matches = []
        
        for pattern, target in self.CONDITIONAL_PREFIXES:
            for match in re.finditer(pattern, desc, re.IGNORECASE):
                # For day patterns, extract the day name from the capture group
                day_name = None
                if target == 'day' and match.lastindex and match.lastindex >= 1:
                    day_name = match.group(1).lower()
                prefix_matches.append((match.start(), match.end(), target, day_name))
        
        # Sort by position
        prefix_matches.sort(key=lambda x: x[0])
        
        if not prefix_matches:
            # No conditional prefixes - entire description is base stats
            return [('base', None, desc)]
        
        # Extract segments
        current_pos = 0
        
        for start, end, target, day_name in prefix_matches:
            # Text before this prefix belongs to the previous section
            if start > current_pos:
                if not segments:
                    # First segment is base stats
                    segments.append(('base', None, desc[current_pos:start]))
                else:
                    # Append to the previous segment
                    prev_type, prev_day, prev_text = segments[-1]
                    segments[-1] = (prev_type, prev_day, prev_text + desc[current_pos:start])
            
            # Start a new segment for this prefix
            # If target is None, this is an ignored prefix - we'll add it but mark to skip
            segments.append((target, day_name, ''))
            current_pos = end
        
        # Text after the last prefix belongs to the last segment
        if current_pos < len(desc):
            if segments:
                prev_type, prev_day, prev_text = segments[-1]
                segments[-1] = (prev_type, prev_day, prev_text + desc[current_pos:])
        
        return segments
    
    def _parse_stats_from_text(self, text: str, stats: Stats):
        """Parse stats from a text segment into a Stats object."""
        # Skills that have "Great X" variants - need special handling to avoid double-counting
        great_skill_variants = {
            'sword_skill': 'great_sword_skill',
            'axe_skill': 'great_axe_skill', 
            'katana_skill': 'great_katana_skill',
        }
        great_skill_matched = set()  # Track which "Great X" skills were found
        
        for pattern, stat_name, multiplier in self.STAT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Track if this is a "Great X" skill
                if stat_name in great_skill_variants.values():
                    great_skill_matched.add(stat_name)
                
                # Skip simple skill if "Great X" version was already matched
                if stat_name in great_skill_variants:
                    great_version = great_skill_variants[stat_name]
                    if great_version in great_skill_matched:
                        # Double-check: is this match part of a "Great X" match?
                        # Check if "Great " precedes this match
                        start_pos = match.start()
                        prefix_check = text[max(0, start_pos-6):start_pos].lower()
                        if 'great' in prefix_check or 'g.' in prefix_check:
                            continue  # Skip - this is part of "Great X"
                
                captured = match.group(1)
                # Handle patterns with optional/implied values
                if captured is None:
                    # "Bonus damage added to magic burst" has no explicit number - default to 4%
                    if stat_name == 'magic_burst_bonus':
                        value = 4 * multiplier
                    else:
                        continue
                else:
                    try:
                        value = int(captured) * multiplier
                    except ValueError:
                        continue
                
                # Set the stat value
                if hasattr(stats, stat_name):
                    current = getattr(stats, stat_name)
                    setattr(stats, stat_name, current + value)
        
        # Special handling for "All magic skills +X"
        all_magic_match = re.search(r'All magic skills?\s*[+]?\s*(\d+)', text, re.IGNORECASE)
        if all_magic_match:
            try:
                value = int(all_magic_match.group(1))
                stats.healing_magic_skill += value
                stats.enfeebling_magic_skill += value
                stats.enhancing_magic_skill += value
                stats.elemental_magic_skill += value
                stats.divine_magic_skill += value
                stats.dark_magic_skill += value
            except ValueError:
                pass
    
    # Pattern to detect multi-slot items (e.g., "Cannot equip headgear")
    # These items occupy multiple slots and their stats can't be properly compared
    # to single-slot items, so we skip parsing them entirely
    # Note: "leggear" is a typo in game data but we need to match it
    MULTI_SLOT_PATTERN = re.compile(
        r'[Cc]annot\s+(?:be\s+)?equip(?:ped)?\s+(?:with\s+)?'
        r'(headgear|head\s*gear|body\s*armor|handgear|hand\s*gear|'
        r'legwear|leg\s*wear|leggear|footgear|foot\s*gear|'
        r'head|body|hands|legs|feet)',
        re.IGNORECASE
    )
    
    def _parse_description_stats(self, item: ItemBase):
        """
        Parse stats from item description text.
        
        This handles conditional stat prefixes:
        - Base stats (no prefix) go into item.base_stats
        - Pet: stats go into item.pet_stats
        - Dynamis: stats go into item.dynamis_stats
        - Avatar: stats go into item.avatar_stats
        - Wyvern: stats go into item.wyvern_stats
        - Daytime: stats go into item.daytime_stats
        - Day-specific (Firesday:, etc.) go into item.day_stats dict
        - Ignored prefixes (Reives:, Campaign:, etc.) are skipped entirely
        
        Multi-slot items (those with "Cannot equip X" in description) are
        skipped entirely as their stats can't be properly compared to
        single-slot items in the optimizer.
        """
        desc = item.description
        if not desc:
            return
        
        # Check for multi-slot items (e.g., Onca Suit which blocks legs)
        # These items have "Cannot equip X" in their description
        multi_slot_match = self.MULTI_SLOT_PATTERN.search(desc)
        if multi_slot_match:
            blocked_slot = multi_slot_match.group(1)
            item.is_multi_slot = True
            item.base_stats.special_effects.append(
                f"Multi-slot item (blocks {blocked_slot}) - stats not parsed"
            )

            #print(item.name)
            # Don't parse stats - the item will have empty stats and won't
            # be selected by the optimizer
            return
        
        # Segment the description by conditional prefixes
        segments = self._segment_description(desc)
        
        for condition_type, day_name, text in segments:
            if not text.strip():
                continue
                
            if condition_type is None:
                # Ignored prefix (Reives, Campaign, etc.) - skip entirely
                continue
            elif condition_type == 'base':
                # Base stats
                self._parse_stats_from_text(text, item.base_stats)
            elif condition_type == 'pet':
                if item.pet_stats is None:
                    item.pet_stats = Stats()
                self._parse_stats_from_text(text, item.pet_stats)
            elif condition_type == 'automaton':
                if item.automaton_stats is None:
                    item.automaton_stats = Stats()
                self._parse_stats_from_text(text, item.automaton_stats)
            elif condition_type == 'dynamis':
                if item.dynamis_stats is None:
                    item.dynamis_stats = Stats()
                self._parse_stats_from_text(text, item.dynamis_stats)
            elif condition_type == 'avatar':
                if item.avatar_stats is None:
                    item.avatar_stats = Stats()
                self._parse_stats_from_text(text, item.avatar_stats)
            elif condition_type == 'wyvern':
                if item.wyvern_stats is None:
                    item.wyvern_stats = Stats()
                self._parse_stats_from_text(text, item.wyvern_stats)
            elif condition_type == 'daytime':
                if item.daytime_stats is None:
                    item.daytime_stats = Stats()
                self._parse_stats_from_text(text, item.daytime_stats)
            elif condition_type == 'day' and day_name:
                if item.day_stats is None:
                    item.day_stats = {}
                if day_name not in item.day_stats:
                    item.day_stats[day_name] = Stats()
                self._parse_stats_from_text(text, item.day_stats[day_name])
    
    def get_item(self, item_id: int) -> Optional[ItemBase]:
        """Get item by ID."""
        return self.items.get(item_id)
    
    def get_item_by_name(self, name: str) -> Optional[ItemBase]:
        """Get item by name (case-insensitive)."""
        return self.items_by_name.get(name.lower())
    
    def get_items_for_slot(self, slot: Slot) -> List[ItemBase]:
        """Get all items that can be equipped in a given slot."""
        mask = SLOT_BITMASK.get(slot, 0)
        return [item for item in self.items.values() if item.slots & mask]
    
    def search_items(self, query: str) -> List[ItemBase]:
        """Search items by name substring."""
        query_lower = query.lower()
        return [item for item in self.items.values() 
                if query_lower in item.name.lower()]


# Global database instance
_database: Optional[ItemDatabase] = None


def get_database() -> ItemDatabase:
    """
    Get the global item database instance.
    
    Auto-loads from common locations if not already loaded.
    """
    global _database
    if _database is None:
        _database = ItemDatabase()
        
        # Try to auto-load from common locations
        script_dir = Path(__file__).parent
        
        # Check for items.lua in the same directory
        items_path = script_dir / 'items.lua'
        descriptions_path = script_dir / 'item_descriptions.lua'
        
        if items_path.exists():
            desc_path = str(descriptions_path) if descriptions_path.exists() else None
            try:
                _database.load_from_lua(str(items_path), desc_path)
            except Exception as e:
                print(f"Warning: Failed to auto-load item database: {e}")
    
    return _database


def load_database(items_path: str, descriptions_path: Optional[str] = None) -> ItemDatabase:
    """Load the global item database from Lua files."""
    db = get_database()
    db.load_from_lua(items_path, descriptions_path)
    return db