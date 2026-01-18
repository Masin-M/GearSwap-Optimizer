"""
Inventory Loader

Loads inventory CSV dumps and joins them with the item database.
"""

import csv
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass
import sys


SCRIPT_DIR = Path(__file__).parent
WSDIST_DIR = SCRIPT_DIR / 'wsdist_beta-main'

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(WSDIST_DIR))

from models import (
    ItemBase, ItemInstance, Stats, Container, Slot, Job,
    SLOT_BITMASK, EQUIPPABLE_CONTAINERS
)
from item_database import ItemDatabase, get_database
from augment_parser import resolve_augments
from path_augment_db import (
    get_path_augment_db, PathAugmentDatabase,
    parse_path_augment, is_path_augment
)

# Import extdata decoder if available
try:
    from .extdata_decoder import ExtdataDecoder, AugmentDatabase
    HAS_EXTDATA_DECODER = True
except ImportError:
    HAS_EXTDATA_DECODER = False


@dataclass
class InventoryStats:
    """Summary statistics for loaded inventory."""
    total_items: int = 0
    equippable_items: int = 0
    items_by_container: Dict[Container, int] = None
    items_by_slot: Dict[Slot, int] = None
    
    def __post_init__(self):
        if self.items_by_container is None:
            self.items_by_container = {}
        if self.items_by_slot is None:
            self.items_by_slot = {}


class Inventory:
    """
    Represents a player's inventory state.
    
    Contains all items loaded from CSV, joined with item database.
    """
    
    def __init__(self, item_db: Optional[ItemDatabase] = None,
                 path_augment_db: Optional[PathAugmentDatabase] = None):
        self.item_db = item_db or get_database()
        self.path_augment_db = path_augment_db or get_path_augment_db()
        self.items: List[ItemInstance] = []
        self.items_by_id: Dict[int, List[ItemInstance]] = {}
        self.items_by_slot: Dict[Slot, List[ItemInstance]] = {}
        self.stats: InventoryStats = InventoryStats()
    
    def load_from_csv(self, csv_path: str, equip_only: bool = False):
        """
        Load inventory from CSV file.
        
        Args:
            csv_path: Path to inventory CSV file
            equip_only: If True, only load items from equippable containers
        """
        self.items.clear()
        self.items_by_id.clear()
        self.items_by_slot.clear()
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                item = self._parse_row(row)
                if item is None:
                    continue
                
                # Filter for equippable containers if requested
                if equip_only and item.container not in EQUIPPABLE_CONTAINERS:
                    continue
                
                self._add_item(item)
        
        self._calculate_stats()
    
    def _parse_row(self, row: Dict[str, str]) -> Optional[ItemInstance]:
        """Parse a CSV row into an ItemInstance."""
        try:
            item_id = int(row['item_id'])
            container_id = int(row['container_id'])
            slot = int(row['slot'])
            count = int(row.get('count', 1))
            status = int(row.get('status', 0))
            
            # Parse rank (new column for path augments)
            rank_str = row.get('rank', '')
            rank = int(rank_str) if rank_str else 0
            
            # Get base item from database
            base_item = self.item_db.get_item(item_id)
            if base_item is None:
                # Create a minimal base item if not in database
                base_item = ItemBase(
                    id=item_id,
                    name=row.get('item_name', f'Unknown_{item_id}'),
                    name_log=row.get('item_name_log', ''),
                )
            
            # Parse augments
            augments_raw = self._parse_augments(row.get('augments', ''))
            extdata = row.get('extdata', '')
            
            # Check if this is a path-augmented item
            path_letter = None
            path_stats_resolved = False
            augment_stats = Stats()
            
            for aug in augments_raw:
                if isinstance(aug, str) and is_path_augment(aug):
                    path_letter = parse_path_augment(aug)
                    break
            
            if path_letter and rank > 0:
                # Try to resolve stats from path augment database
                path_stats = self.path_augment_db.get_path_stats(item_id, path_letter, rank)
                if path_stats:
                    augment_stats = path_stats
                    path_stats_resolved = True
                else:
                    # Item not in database yet - flag it but continue
                    # The item will still be usable, just without path stats
                    augment_stats.special_effects.append(
                        f"Path {path_letter} R{rank} (stats not in database)"
                    )
            else:
                # Non-path augments - use standard resolution
                augment_stats = resolve_augments(item_id, augments_raw, extdata)
            
            # Create item instance
            item = ItemInstance(
                base=base_item,
                container=Container(container_id),
                slot=slot,
                count=count,
                status=status,
                augments_raw=augments_raw,
                extdata=extdata,
                rank=rank,
                augment_stats=augment_stats,
                path_stats_resolved=path_stats_resolved,
            )
            
            return item
            
        except (KeyError, ValueError) as e:
            print(f"Warning: Failed to parse row: {e}")
            return None
    
    def _parse_augments(self, augments_str: str) -> List[Any]:
        """Parse augments string from CSV."""
        if not augments_str:
            return []
        
        # Handle escaped semicolons
        augments_str = augments_str.replace('\\;', '\x00')
        parts = augments_str.split(';')
        
        result = []
        for part in parts:
            part = part.replace('\x00', ';').strip()
            if not part or part == 'none':
                continue
            
            # Try to parse as integer (numeric augment ID)
            try:
                result.append(int(part))
            except ValueError:
                # Keep as string (text augment)
                result.append(part)
        
        return result
    
    def _add_item(self, item: ItemInstance):
        """Add an item to the inventory indexes."""
        self.items.append(item)
        
        # Index by ID
        if item.id not in self.items_by_id:
            self.items_by_id[item.id] = []
        self.items_by_id[item.id].append(item)
        
        # Index by slot
        for slot in item.base.get_slots():
            if slot not in self.items_by_slot:
                self.items_by_slot[slot] = []
            self.items_by_slot[slot].append(item)
    
    def _calculate_stats(self):
        """Calculate inventory statistics."""
        self.stats = InventoryStats()
        self.stats.total_items = len(self.items)
        
        for item in self.items:
            # Count by container
            container = item.container
            self.stats.items_by_container[container] = \
                self.stats.items_by_container.get(container, 0) + 1
            
            # Count equippable items
            if item.can_equip_from():
                self.stats.equippable_items += 1
            
            # Count by slot
            for slot in item.base.get_slots():
                self.stats.items_by_slot[slot] = \
                    self.stats.items_by_slot.get(slot, 0) + 1
    
    def get_items_for_slot(self, slot: Slot, job: Optional[Job] = None,
                          equippable_only: bool = True,
                          exclude_path_items: bool = False) -> List[ItemInstance]:
        """
        Get all items that can be equipped in a given slot.
        
        Args:
            slot: The equipment slot
            job: Optional job to filter by
            equippable_only: If True, only return items in equippable containers
            exclude_path_items: If True, exclude items with Path augments
        
        Returns:
            List of ItemInstance objects
        """
        items = self.items_by_slot.get(slot, [])
        
        result = []
        for item in items:
            # Filter by equippable container
            if equippable_only and not item.can_equip_from():
                continue
            
            # Filter by job
            if job and not item.base.can_equip(job):
                continue
            
            # Filter out path items if requested
            if exclude_path_items and item.has_path_augment:
                continue
            
            result.append(item)
        
        return result
    
    def get_path_items_for_slot(self, slot: Slot, job: Optional[Job] = None,
                                equippable_only: bool = True) -> List[ItemInstance]:
        """
        Get items with Path augments for a given slot.
        
        These items have stats that vary by path and need manual review
        if not in the path augment database.
        """
        items = self.items_by_slot.get(slot, [])
        
        result = []
        for item in items:
            if equippable_only and not item.can_equip_from():
                continue
            if job and not item.base.can_equip(job):
                continue
            if item.has_path_augment:
                result.append(item)
        
        return result
    
    def get_unresolved_path_items(self) -> List[ItemInstance]:
        """
        Get all path-augmented items whose stats couldn't be resolved.
        
        These items are in the inventory with Path augments but are not
        in the path augment database, so their stats are unknown.
        """
        return [
            item for item in self.items
            if item.has_path_augment and not item.path_stats_resolved
        ]
    
    def get_resolved_path_items(self) -> List[ItemInstance]:
        """
        Get all path-augmented items whose stats were successfully resolved.
        """
        return [
            item for item in self.items
            if item.has_path_augment and item.path_stats_resolved
        ]
    
    def get_item_by_name(self, name: str) -> Optional[ItemInstance]:
        """Get an item by name (first match)."""
        name_lower = name.lower()
        for item in self.items:
            if item.name.lower() == name_lower:
                return item
        return None
    
    def search_items(self, query: str) -> List[ItemInstance]:
        """Search items by name substring."""
        query_lower = query.lower()
        return [item for item in self.items 
                if query_lower in item.name.lower()]
    
    def get_unique_items_for_slot(self, slot: Slot, job: Optional[Job] = None) -> List[ItemInstance]:
        """
        Get unique items for a slot (deduplicated by name + augments).
        
        For optimization, we only need unique item configurations.
        """
        items = self.get_items_for_slot(slot, job)
        
        # Deduplicate by (name, augments)
        seen = set()
        unique = []
        
        for item in items:
            key = (item.name, tuple(sorted(str(a) for a in item.augments_raw)))
            if key not in seen:
                seen.add(key)
                unique.append(item)
        
        return unique


class InventoryManager:
    """
    Manages multiple inventory snapshots and provides unified access.
    """
    
    def __init__(self, item_db: Optional[ItemDatabase] = None,
                 path_augment_db: Optional[PathAugmentDatabase] = None):
        self.item_db = item_db or get_database()
        self.path_augment_db = path_augment_db or get_path_augment_db()
        self.inventories: Dict[str, Inventory] = {}
        self.current: Optional[Inventory] = None
    
    def load_inventory(self, csv_path: str, name: Optional[str] = None,
                      set_current: bool = True) -> Inventory:
        """
        Load an inventory from CSV.
        
        Args:
            csv_path: Path to inventory CSV
            name: Optional name for this inventory (defaults to filename)
            set_current: Whether to set this as the current inventory
        
        Returns:
            Loaded Inventory object
        """
        if name is None:
            name = Path(csv_path).stem
        
        inventory = Inventory(self.item_db, self.path_augment_db)
        inventory.load_from_csv(csv_path)
        
        self.inventories[name] = inventory
        
        if set_current:
            self.current = inventory
        
        return inventory
    
    def get_inventory(self, name: str) -> Optional[Inventory]:
        """Get a named inventory."""
        return self.inventories.get(name)
    
    def list_inventories(self) -> List[str]:
        """List all loaded inventory names."""
        return list(self.inventories.keys())


# Global manager instance
_manager: Optional[InventoryManager] = None


def get_manager() -> InventoryManager:
    """Get the global inventory manager."""
    global _manager
    if _manager is None:
        _manager = InventoryManager()
    return _manager


def load_inventory(csv_path: str, item_db: Optional[ItemDatabase] = None,
                   path_augment_db: Optional[PathAugmentDatabase] = None) -> Inventory:
    """
    Convenience function to load an inventory.
    
    Args:
        csv_path: Path to inventory CSV file
        item_db: Optional item database (uses global if not provided)
        path_augment_db: Optional path augment database (uses global if not provided)
    
    Returns:
        Loaded Inventory object
    """
    inv = Inventory(item_db, path_augment_db)
    inv.load_from_csv(csv_path)
    return inv
