"""
Extdata Decoder for FFXI Equipment Augments

Decodes the binary extdata from inventory items to extract augment information.

Supports:
- Type 0x01/0x02: Standard augmented equipment (11-bit ID + 5-bit value format)
- Type 0x03: Path/Rank augmentable gear (Odyssey, RMEA, JSE Necks, Ambuscade, etc.)
"""

import re
import json
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from pathlib import Path


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class PathRankInfo:
    """Information extracted from Path/Rank gear extdata."""
    path: str  # A, B, C, D, or empty if not applicable
    rank: int  # 0-30 depending on item type
    max_rank: int  # Maximum rank for this item type (15, 25, or 30)
    item_type: str  # 'odyssey', 'rmea', 'jse_neck', 'ambuscade', etc.


@dataclass
class AugmentTier:
    """Augment values at a specific rank for a path."""
    rank: int
    stats: Dict[str, Union[int, float]]  # stat_name -> value
    description: str = ""  # Human-readable description


@dataclass 
class PathAugmentTable:
    """Complete augment progression for a single path of an item."""
    item_id: int
    item_name: str
    path: str  # A, B, C, D
    max_rank: int
    tiers: Dict[int, AugmentTier]  # rank -> AugmentTier


class AugmentDatabase:
    """Database of augment ID -> text mappings from augments.lua"""
    
    def __init__(self):
        self.augments: Dict[int, str] = {}
    
    def load_from_lua(self, lua_path: str):
        """Load augments from Windower's augments.lua file."""
        with open(lua_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse entries like: [123] = {id=123,en="STR%+d ",ja="..."},
        pattern = r'\[(\d+)\]\s*=\s*\{[^}]*en="([^"]*)"'
        
        for match in re.finditer(pattern, content):
            aug_id = int(match.group(1))
            aug_text = match.group(2)
            self.augments[aug_id] = aug_text
    
    def get_augment_text(self, aug_id: int, value: int) -> str:
        """Get augment text with value substituted."""
        template = self.augments.get(aug_id)
        
        if not template:
            return f"Aug#{aug_id}: {value}"
        
        # Skip placeholder entries that just show the next number
        if template.isdigit():
            return f"Aug#{aug_id}: {value}"
        
        try:
            result = template
            while '%+d' in result:
                result = result.replace('%+d', f'{value:+d}', 1)
            while '%d' in result:
                result = result.replace('%d', str(value), 1)
            result = result.replace('%%', '%')
            result = result.replace('\\\"', '"')
            return result.strip()
        except:
            return f"{template}: {value}"


# =============================================================================
# PATH/RANK AUGMENT TABLES
# =============================================================================

class PathRankAugmentDatabase:
    """
    Database of Path/Rank augment progressions.
    
    Structure:
        tables[item_id][path] = PathAugmentTable
    
    Tables are loaded from JSON files or populated by the trawler.
    """
    
    def __init__(self):
        self.tables: Dict[int, Dict[str, PathAugmentTable]] = {}
        self._item_metadata: Dict[int, Dict[str, Any]] = {}
    
    def load_from_json(self, json_path: str):
        """Load augment tables from a JSON file."""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for item_id_str, item_data in data.get('items', {}).items():
            item_id = int(item_id_str)
            self._item_metadata[item_id] = {
                'name': item_data.get('name', ''),
                'max_rank': item_data.get('max_rank', 15),
                'item_type': item_data.get('item_type', 'unknown'),
            }
            
            self.tables[item_id] = {}
            for path, path_data in item_data.get('paths', {}).items():
                tiers = {}
                for rank_str, tier_data in path_data.get('tiers', {}).items():
                    rank = int(rank_str)
                    tiers[rank] = AugmentTier(
                        rank=rank,
                        stats=tier_data.get('stats', {}),
                        description=tier_data.get('description', ''),
                    )
                
                self.tables[item_id][path] = PathAugmentTable(
                    item_id=item_id,
                    item_name=item_data.get('name', ''),
                    path=path,
                    max_rank=item_data.get('max_rank', 15),
                    tiers=tiers,
                )
    
    def save_to_json(self, json_path: str):
        """Save augment tables to a JSON file."""
        data = {'items': {}}
        
        for item_id, paths in self.tables.items():
            meta = self._item_metadata.get(item_id, {})
            item_data = {
                'name': meta.get('name', ''),
                'max_rank': meta.get('max_rank', 15),
                'item_type': meta.get('item_type', 'unknown'),
                'paths': {},
            }
            
            for path, table in paths.items():
                path_data = {'tiers': {}}
                for rank, tier in table.tiers.items():
                    path_data['tiers'][str(rank)] = {
                        'stats': tier.stats,
                        'description': tier.description,
                    }
                item_data['paths'][path] = path_data
            
            data['items'][str(item_id)] = item_data
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def get_augments(self, item_id: int, path: str, rank: int) -> Optional[Dict[str, Union[int, float]]]:
        """Get augment stats for an item at a specific path and rank."""
        if item_id not in self.tables:
            return None
        if path not in self.tables[item_id]:
            return None
        
        table = self.tables[item_id][path]
        
        # Exact rank match
        if rank in table.tiers:
            return table.tiers[rank].stats.copy()
        
        # Find the highest rank <= requested rank (augments carry forward)
        applicable_rank = 0
        for r in table.tiers:
            if r <= rank and r > applicable_rank:
                applicable_rank = r
        
        if applicable_rank > 0:
            return table.tiers[applicable_rank].stats.copy()
        
        return None
    
    def get_item_metadata(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get metadata for an item (name, max_rank, type)."""
        return self._item_metadata.get(item_id)
    
    def add_item(self, item_id: int, name: str, max_rank: int, item_type: str):
        """Add or update item metadata."""
        self._item_metadata[item_id] = {
            'name': name,
            'max_rank': max_rank,
            'item_type': item_type,
        }
        if item_id not in self.tables:
            self.tables[item_id] = {}
    
    def add_tier(self, item_id: int, path: str, rank: int, stats: Dict[str, Union[int, float]], description: str = ""):
        """Add an augment tier for an item path."""
        if item_id not in self.tables:
            self.tables[item_id] = {}
        
        if path not in self.tables[item_id]:
            meta = self._item_metadata.get(item_id, {})
            self.tables[item_id][path] = PathAugmentTable(
                item_id=item_id,
                item_name=meta.get('name', ''),
                path=path,
                max_rank=meta.get('max_rank', 15),
                tiers={},
            )
        
        self.tables[item_id][path].tiers[rank] = AugmentTier(
            rank=rank,
            stats=stats,
            description=description,
        )


# =============================================================================
# EXTDATA DECODER
# =============================================================================

class ExtdataDecoder:
    """
    Decodes FFXI equipment extdata to extract augments.
    
    Extdata types:
        0x01, 0x02: Standard augmented equipment (11+5 bit format)
        0x03: Path/Rank augmentable gear (Odyssey, RMEA, JSE, Ambuscade)
    """
    
    # Item type detection based on item ID ranges and known items
    # This is a simplified heuristic - can be expanded
    ODYSSEY_ARMOR_IDS = set(range(23761, 23790))  # Nyame set and similar
    RMEA_WEAPON_IDS = {20890}  # Anguta, etc. - needs expansion
    
    def __init__(self, augment_db: Optional[AugmentDatabase] = None,
                 path_rank_db: Optional[PathRankAugmentDatabase] = None):
        self.augment_db = augment_db
        self.path_rank_db = path_rank_db or PathRankAugmentDatabase()
    
    def decode_hex(self, hex_str: str, item_id: int = 0, augments_text: str = "") -> Dict[str, Any]:
        """
        Decode a hex string extdata.
        
        Args:
            hex_str: The hex-encoded extdata string
            item_id: The item ID (used for context)
            augments_text: The augments field text (e.g., "Path: B")
        
        Returns:
            Dictionary with decoded information
        """
        if not hex_str or hex_str == '0' * len(hex_str):
            return {'type': 0, 'augments': [], 'path_rank': None}
        
        try:
            data = bytes.fromhex(hex_str)
        except ValueError:
            return {'type': 0, 'augments': [], 'error': 'Invalid hex string', 'path_rank': None}
        
        return self.decode_bytes(data, item_id, augments_text)
    
    def decode_bytes(self, data: bytes, item_id: int = 0, augments_text: str = "") -> Dict[str, Any]:
        """Decode extdata bytes."""
        if len(data) < 4:
            return {'type': 0, 'augments': [], 'path_rank': None}
        
        result = {
            'type': data[0],
            'subtype': data[1],
            'augments': [],
            'path_rank': None,
            'raw_bytes': {
                'byte_0': data[0],
                'byte_1': data[1],
                'bytes_4_5': (data[4] | (data[5] << 8)) if len(data) > 5 else 0,
                'byte_6': data[6] if len(data) > 6 else 0,
                'byte_7': data[7] if len(data) > 7 else 0,
                'bytes_8_9': (data[8] | (data[9] << 8)) if len(data) > 9 else 0,
            },
        }
        
        # Type 0x03: Path/Rank gear (Odyssey, RMEA, JSE, Ambuscade)
        if data[0] == 0x03:
            path_rank_info = self._decode_path_rank(data, item_id, augments_text)
            result['path_rank'] = path_rank_info
            
            # Look up augments from database if available
            if path_rank_info and self.path_rank_db:
                augments = self.path_rank_db.get_augments(
                    item_id, 
                    path_rank_info.path, 
                    path_rank_info.rank
                )
                if augments:
                    result['path_rank_augments'] = augments
        
        # Type 0x01 or 0x02: Standard augmented equipment
        elif data[0] in (0x01, 0x02):
            augments = self._decode_standard_augments(data)
            result['augments'] = augments
        
        return result
    
    def _decode_path_rank(self, data: bytes, item_id: int, augments_text: str) -> PathRankInfo:
        """
        Decode Path/Rank information from type 0x03 extdata.
        
        Format:
            Byte 0: 0x03 (type marker)
            Byte 1: 0x83 (common subtype)
            Bytes 2-3: Usually 0x0000
            Bytes 4-5: Item-specific identifier
            Byte 6: Rank × 4
            Byte 7: Usually 0x00-0x02
            Bytes 8-9: Additional item-specific data
        """
        # Extract rank from byte 6
        rank = data[6] // 4 if len(data) > 6 else 0
        
        # Extract path from augments text field
        path = self._extract_path_from_text(augments_text)
        
        # Determine item type and max rank
        item_type, max_rank = self._determine_item_type(item_id)
        
        return PathRankInfo(
            path=path,
            rank=rank,
            max_rank=max_rank,
            item_type=item_type,
        )
    
    def _extract_path_from_text(self, augments_text: str) -> str:
        """Extract path letter from augments text like 'Path: B'."""
        if not augments_text:
            return ""
        
        match = re.search(r'Path:\s*([A-Da-d])', augments_text)
        if match:
            return match.group(1).upper()
        
        return ""
    
    def _determine_item_type(self, item_id: int) -> Tuple[str, int]:
        """
        Determine the item type and max rank based on item ID.
        
        Returns:
            (item_type, max_rank)
        """
        # Check metadata from database first
        if self.path_rank_db:
            meta = self.path_rank_db.get_item_metadata(item_id)
            if meta:
                return meta.get('item_type', 'unknown'), meta.get('max_rank', 15)
        
        # Fallback heuristics based on known ID ranges
        # Odyssey armor (Nyame, Sakpata, Gleti, Mpaca, Agwu, etc.)
        if item_id in self.ODYSSEY_ARMOR_IDS or 23700 <= item_id <= 23900:
            return 'odyssey', 30
        
        # Odyssey accessories (ammo, etc.)
        if 21400 <= item_id <= 21500:
            return 'odyssey', 30
        
        # RMEA weapons (Aeonic, Mythic, Relic, Empyrean)
        if item_id in self.RMEA_WEAPON_IDS or 20800 <= item_id <= 21100:
            return 'rmea', 15
        
        # JSE Necks
        if 25400 <= item_id <= 25500:
            return 'jse_neck', 25
        
        # Ambuscade gear (belts, capes, etc.)
        if 28400 <= item_id <= 28500:
            return 'ambuscade', 25
        
        # Default
        return 'unknown', 15
    
    def _decode_standard_augments(self, data: bytes) -> List[Tuple[int, int, str]]:
        """
        Decode augments from standard equipment extdata (type 0x01/0x02).
        
        Format: 11-bit ID + 5-bit value = 16 bits per augment
        """
        augments = []
        pos = 2  # Skip type bytes
        
        while pos + 1 < len(data):
            word = data[pos] | (data[pos + 1] << 8)
            
            if word == 0:
                pos += 2
                continue
            
            aug_id = word & 0x7FF  # Lower 11 bits
            value = (word >> 11) & 0x1F  # Upper 5 bits
            
            if 0 < aug_id < 2048:
                text = ""
                if self.augment_db:
                    text = self.augment_db.get_augment_text(aug_id, value)
                augments.append((aug_id, value, text))
            
            pos += 2
        
        # Filter out invalid augments
        return [(a, v, t) for a, v, t in augments if 0 < a < 2000]


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def decode_inventory_extdata(csv_path: str, augments_lua_path: str = None) -> List[Dict[str, Any]]:
    """
    Decode all extdata from an inventory CSV.
    
    Returns list of items with non-empty decoded extdata.
    """
    import csv
    
    # Load augment database if path provided
    aug_db = None
    if augments_lua_path:
        aug_db = AugmentDatabase()
        aug_db.load_from_lua(augments_lua_path)
    
    decoder = ExtdataDecoder(aug_db)
    results = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            extdata = row.get('extdata', '')
            
            # Skip empty or all-zeros extdata
            if not extdata or extdata == '0' * len(extdata):
                continue
            
            item_id = int(row.get('item_id', 0))
            augments_text = row.get('augments', '')
            
            result = decoder.decode_hex(extdata, item_id, augments_text)
            
            # Only include items with meaningful data
            if result.get('augments') or result.get('path_rank'):
                result['item_id'] = item_id
                result['container'] = row.get('container_name', row.get('container_id', ''))
                result['slot'] = row.get('slot', '')
                result['extdata'] = extdata
                result['augments_text'] = augments_text
                results.append(result)
    
    return results


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python extdata_decoder.py <inventory.csv> [augments.lua]")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    lua_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    items = decode_inventory_extdata(csv_path, lua_path)
    
    print(f"\nFound {len(items)} items with extdata:\n")
    
    for item in items:
        print(f"Item {item['item_id']} ({item['container']}):")
        print(f"  Extdata: {item['extdata'][:32]}...")
        
        if item.get('path_rank'):
            pr = item['path_rank']
            print(f"  Type: {pr.item_type}")
            print(f"  Path: {pr.path or 'N/A'}")
            print(f"  Rank: {pr.rank}/{pr.max_rank}")
        
        if item.get('augments'):
            for aug_id, value, text in item['augments']:
                print(f"  - [{aug_id}] {text}")
        
        if item.get('path_rank_augments'):
            print(f"  Augments: {item['path_rank_augments']}")
        
        print()