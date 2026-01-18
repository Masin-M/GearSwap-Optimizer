"""
Path Augment Database

Loads and queries the augment_tables.json file to resolve stats for items
with Path augments (A/B/C/D). These items have variable stats based on
the chosen path and rank tier.

Path items cannot have their stats parsed from text descriptions, so this
database provides the actual stat values.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import sys


SCRIPT_DIR = Path(__file__).parent
WSDIST_DIR = SCRIPT_DIR / 'wsdist_beta-main'

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(WSDIST_DIR))
from models import Stats


@dataclass
class PathTierData:
    """Data for a single tier of a path augment."""
    rank: int
    stats: Dict[str, Any]
    description: str = ''
    interpolated: bool = False


@dataclass
class PathData:
    """Data for a single path (A, B, C, or D) of an item."""
    path: str
    tiers: Dict[int, PathTierData] = field(default_factory=dict)
    is_complete: bool = False
    
    def get_tier(self, rank: int) -> Optional[PathTierData]:
        """Get tier data for a specific rank."""
        return self.tiers.get(rank)
    
    def get_max_rank(self) -> int:
        """Get the maximum rank available for this path."""
        if not self.tiers:
            return 0
        return max(self.tiers.keys())


@dataclass
class PathItemData:
    """Full augment data for a path-augmented item."""
    item_id: int
    name: str
    item_type: str = ''
    category: str = ''
    max_rank: int = 15
    source_url: str = ''
    has_full_wiki_table: bool = False
    interpolation_applied: bool = False
    paths: Dict[str, PathData] = field(default_factory=dict)
    
    def get_path(self, path: str) -> Optional[PathData]:
        """Get data for a specific path."""
        return self.paths.get(path.upper())
    
    def get_stats(self, path: str, rank: int) -> Optional[Dict[str, Any]]:
        """Get stats for a specific path and rank."""
        path_data = self.get_path(path)
        if not path_data:
            return None
        tier_data = path_data.get_tier(rank)
        if not tier_data:
            return None
        return tier_data.stats
    
    def get_available_paths(self) -> List[str]:
        """Get list of available paths for this item."""
        return list(self.paths.keys())


# =============================================================================
# STAT NAME MAPPING
# =============================================================================
# Maps JSON stat names to canonical Stats class attribute names.
# Stats not in this map are assumed to match the Stats class directly.
#
# Some stats in the JSON may not have a direct Stats class attribute;
# these will be stored in special_effects.

STAT_NAME_MAP = {
    # Duration stats (basis points in Stats class)
    'enhancing_duration': 'enhancing_duration',
    'enfeebling_duration': 'enfeebling_duration',  # May need to add to Stats
    
    # Damage limit stats (special - may not be in Stats)
    'physical_damage_limit': 'physical_damage_limit',
    'magical_damage_limit': 'magical_damage_limit',
    
    # Common abbreviations that might appear
    'MAB': 'magic_attack',
    'MDB': 'magic_defense',
    'DA': 'double_attack',
    'TA': 'triple_attack',
    'QA': 'quad_attack',
    'STP': 'store_tp',
    'DW': 'dual_wield',
    'FC': 'fast_cast',
    'DT': 'damage_taken',
    'PDT': 'physical_dt',
    'MDT': 'magical_dt',
    'WSD': 'ws_damage',
    
    # Primary stats (already uppercase, but include for completeness)
    'STR': 'STR',
    'DEX': 'DEX',
    'VIT': 'VIT',
    'AGI': 'AGI',
    'INT': 'INT',
    'MND': 'MND',
    'CHR': 'CHR',
    'HP': 'HP',
    'MP': 'MP',
}

# Stats that should be stored as basis points (multiply by 100)
# Note: Damage limit stats are FLAT values, not percentages
BASIS_POINT_STATS = {
    'double_attack', 'triple_attack', 'quad_attack',
    'dual_wield', 'gear_haste', 'magic_haste',
    'crit_rate', 'crit_damage', 'magic_crit_damage',
    'ws_damage', 'damage_taken', 'physical_dt', 'magical_dt', 'breath_dt',
    'magic_burst_bonus', 'cure_potency', 'cure_potency_ii', 'fast_cast',
    'enhancing_duration', 'enfeebling_duration',
}


def normalize_stat_name(name: str) -> str:
    """Convert a stat name to canonical form."""
    # Check direct mapping first
    if name in STAT_NAME_MAP:
        return STAT_NAME_MAP[name]
    
    # Already lowercase_snake_case or uppercase primary stat
    return name


class PathAugmentDatabase:
    """
    Database for path-augmented item stats.
    
    Loads data from augment_tables.json and provides lookup by item_id,
    path, and rank.
    """
    
    def __init__(self):
        self.items: Dict[int, PathItemData] = {}
        self.items_by_name: Dict[str, PathItemData] = {}
        self.metadata: Dict[str, Any] = {}
        self._loaded = False
    
    def load(self, json_path: Optional[str] = None) -> bool:
        """
        Load the augment tables from JSON.
        
        Args:
            json_path: Path to augment_tables.json. If None, uses default location.
            
        Returns:
            True if loaded successfully, False otherwise.
        """
        if json_path is None:
            # Default location: optimizer/augment_data/augment_tables.json
            module_dir = Path(__file__).parent
            json_path = module_dir / 'augment_data' / 'augment_tables.json'
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"Warning: Augment tables not found at {json_path}")
            return False
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse augment tables: {e}")
            return False
        
        self._parse_data(data)
        self._loaded = True
        return True
    
    def _parse_data(self, data: Dict[str, Any]):
        """Parse the loaded JSON data into structured objects."""
        self.metadata = data.get('metadata', {})
        
        items_data = data.get('items', {})
        for item_id_str, item_data in items_data.items():
            try:
                item_id = int(item_id_str)
            except ValueError:
                continue
            
            # Parse paths
            paths = {}
            for path_letter, path_data in item_data.get('paths', {}).items():
                tiers = {}
                for rank_str, tier_data in path_data.get('tiers', {}).items():
                    try:
                        rank = int(rank_str)
                    except ValueError:
                        continue
                    
                    tiers[rank] = PathTierData(
                        rank=rank,
                        stats=tier_data.get('stats', {}),
                        description=tier_data.get('description', ''),
                        interpolated=tier_data.get('interpolated', False),
                    )
                
                paths[path_letter.upper()] = PathData(
                    path=path_letter.upper(),
                    tiers=tiers,
                    is_complete=path_data.get('is_complete', False),
                )
            
            # Create item data
            path_item = PathItemData(
                item_id=item_id,
                name=item_data.get('name', f'Unknown_{item_id}'),
                item_type=item_data.get('item_type', ''),
                category=item_data.get('category', ''),
                max_rank=item_data.get('max_rank', 15),
                source_url=item_data.get('source_url', ''),
                has_full_wiki_table=item_data.get('has_full_wiki_table', False),
                interpolation_applied=item_data.get('interpolation_applied', False),
                paths=paths,
            )
            
            self.items[item_id] = path_item
            self.items_by_name[path_item.name.lower()] = path_item
    
    def get_item(self, item_id: int) -> Optional[PathItemData]:
        """Get path item data by ID."""
        return self.items.get(item_id)
    
    def get_item_by_name(self, name: str) -> Optional[PathItemData]:
        """Get path item data by name (case-insensitive)."""
        return self.items_by_name.get(name.lower())
    
    def has_item(self, item_id: int) -> bool:
        """Check if an item is in the database."""
        return item_id in self.items
    
    def get_path_stats(self, item_id: int, path: str, rank: int) -> Optional[Stats]:
        """
        Get resolved Stats object for an item's path and rank.
        
        Args:
            item_id: The item ID
            path: The path letter (A, B, C, or D)
            rank: The rank tier (1-25 depending on item)
            
        Returns:
            Stats object with the path augment bonuses, or None if not found.
        """
        item_data = self.get_item(item_id)
        if not item_data:
            return None
        
        raw_stats = item_data.get_stats(path, rank)
        if not raw_stats:
            return None
        
        return self._convert_to_stats(raw_stats)
    
    def _convert_to_stats(self, raw_stats: Dict[str, Any]) -> Stats:
        """
        Convert raw stat dictionary to Stats object.
        
        Handles stat name normalization and basis point conversion.
        """
        stats = Stats()
        
        for stat_name, value in raw_stats.items():
            # Normalize the stat name
            canonical_name = normalize_stat_name(stat_name)
            
            # Convert to int if needed
            try:
                int_value = int(value)
            except (ValueError, TypeError):
                # Non-numeric value - store as special effect
                stats.special_effects.append(f"{stat_name}: {value}")
                continue
            
            # Check if this is a basis point stat that needs conversion
            # NOTE: The JSON stores values as displayed in-game (e.g., 15 for 15%)
            # Our Stats class stores basis points (e.g., 1500 for 15%)
            if canonical_name in BASIS_POINT_STATS:
                int_value *= 100
            
            # Apply to Stats object
            if hasattr(stats, canonical_name):
                current = getattr(stats, canonical_name)
                setattr(stats, canonical_name, current + int_value)
            else:
                # Unknown stat - store as special effect
                stats.special_effects.append(f"{stat_name}: {value}")
        
        return stats
    
    def list_items(self) -> List[Tuple[int, str]]:
        """List all items in the database as (id, name) tuples."""
        return [(item.item_id, item.name) for item in self.items.values()]
    
    @property
    def is_loaded(self) -> bool:
        """Check if the database has been loaded."""
        return self._loaded
    
    @property
    def item_count(self) -> int:
        """Get the number of items in the database."""
        return len(self.items)


# =============================================================================
# PATH AUGMENT PARSING UTILITIES
# =============================================================================

# Pattern to extract path letter from augment string
# Matches: "Path: A", "Path: B", "Path A", etc.
PATH_PATTERN = re.compile(r'Path[:\s]*([A-Da-d])', re.IGNORECASE)


def parse_path_augment(augment_str: str) -> Optional[str]:
    """
    Extract the path letter from an augment string.
    
    Args:
        augment_str: The augment string (e.g., "Path: A")
        
    Returns:
        The path letter (uppercase) or None if not found.
    """
    match = PATH_PATTERN.search(augment_str)
    if match:
        return match.group(1).upper()
    return None


def is_path_augment(augment_str: str) -> bool:
    """Check if an augment string represents a path augment."""
    return PATH_PATTERN.search(augment_str) is not None


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_database: Optional[PathAugmentDatabase] = None


def get_path_augment_db() -> PathAugmentDatabase:
    """
    Get the global path augment database instance.
    
    Automatically loads the database on first access.
    """
    global _database
    if _database is None:
        _database = PathAugmentDatabase()
        _database.load()
    return _database


def reload_path_augment_db(json_path: Optional[str] = None) -> PathAugmentDatabase:
    """
    Reload the path augment database from disk.
    
    Args:
        json_path: Optional path to JSON file. Uses default if None.
        
    Returns:
        The reloaded database instance.
    """
    global _database
    _database = PathAugmentDatabase()
    _database.load(json_path)
    return _database
