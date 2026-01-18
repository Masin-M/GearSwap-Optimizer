#!/usr/bin/env python3
"""
Inventory-Based Gear Optimization Test

This script loads your actual inventory from CSV and tests optimization
using the wsdist simulator for damage calculations.
"""

import sys
import os
import csv

# Add paths
sys.path.insert(0, '/home/martin/Projects/GSO_wsdist/wsdist_beta-main')
sys.path.insert(0, '/home/martin/Projects/GSO_wsdist')

# wsdist imports
from gear import Empty, all_jobs
from enemies import preset_enemies
from create_player import create_player, create_enemy
from actions import average_ws

# =============================================================================
# SLOT MAPPING
# =============================================================================
SLOT_MAP = {
    # CSV column -> wsdist slot
    'main': 'main',
    'sub': 'sub',
    'range': 'ranged',
    'ammo': 'ammo',
    'head': 'head',
    'neck': 'neck',
    'left_ear': 'ear1',
    'right_ear': 'ear2',
    'body': 'body',
    'hands': 'hands',
    'left_ring': 'ring1',
    'right_ring': 'ring2',
    'back': 'back',
    'waist': 'waist',
    'legs': 'legs',
    'feet': 'feet',
}

WSDIST_SLOTS = ['main', 'sub', 'ranged', 'ammo', 'head', 'neck', 'ear1', 'ear2',
                'body', 'hands', 'ring1', 'ring2', 'back', 'waist', 'legs', 'feet']

# =============================================================================
# ITEM PARSING
# =============================================================================

def parse_csv_inventory(csv_path):
    """
    Parse the inventory CSV and return a list of items with basic info.
    
    Returns:
        List of dicts with keys: id, name, slot_flags, container_id
    """
    items = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            item = {
                'id': int(row['item_id']),
                'name': row.get('item_name', ''),
                'slot_flags': int(row.get('slot_flags', 0)),
                'container_id': int(row.get('container_id', 0)),
                'augments': row.get('augments', ''),
                'rank': int(row['rank']) if row.get('rank', '').strip() else 0,
            }
            items.append(item)
    return items


def get_slot_from_flags(slot_flags):
    """
    Convert slot_flags bitmask to slot name(s).
    
    From FFXI:
    - main = 0x0001
    - sub = 0x0002
    - range = 0x0004
    - ammo = 0x0008
    - head = 0x0010
    - body = 0x0020
    - hands = 0x0040
    - legs = 0x0080
    - feet = 0x0100
    - neck = 0x0200
    - waist = 0x0400
    - left_ear = 0x0800
    - right_ear = 0x1000
    - left_ring = 0x2000
    - right_ring = 0x4000
    - back = 0x8000
    """
    SLOT_BITS = {
        0x0001: 'main',
        0x0002: 'sub',
        0x0004: 'ranged',
        0x0008: 'ammo',
        0x0010: 'head',
        0x0020: 'body',
        0x0040: 'hands',
        0x0080: 'legs',
        0x0100: 'feet',
        0x0200: 'neck',
        0x0400: 'waist',
        0x0800: 'ear1',
        0x1000: 'ear2',
        0x2000: 'ring1',
        0x4000: 'ring2',
        0x8000: 'back',
    }
    
    slots = []
    for bit, slot in SLOT_BITS.items():
        if slot_flags & bit:
            slots.append(slot)
    return slots


# =============================================================================
# KNOWN GEAR DATABASE (hardcoded for testing)
# =============================================================================
# This maps item names to their stats. In a full implementation, this would
# come from your item_database.py and augment parsing.

KNOWN_GEAR = {
    # Weapons
    "Naegling": {
        "Name": "Naegling", "Name2": "Naegling", "Type": "Weapon",
        "Skill Type": "Sword", "DMG": 166, "Delay": 240,
        "STR": 15, "DEX": 15, "MND": 15, "INT": 15,
        "Accuracy": 40, "Attack": 30, "Magic Accuracy": 40,
        "Sword Skill": 250, "Magic Accuracy Skill": 250,
        "Jobs": ["war", "rdm", "thf", "pld", "drk", "bst", "brd", "rng", "nin", "drg", "blu", "cor", "run"],
    },
    "Blurred Shield +1": {
        "Name": "Blurred Shield +1", "Name2": "Blurred Shield +1",
        "Type": "Shield", "STR": 8, "DEX": 8, "VIT": 8,
        "Gear Haste": 3, "Shield Skill": 119,
        "Jobs": ["war", "pld", "drk", "bst", "drg", "run"],
    },
    
    # Head
    "Flam. Zucchetto +2": {
        "Name": "Flam. Zucchetto +2", "Name2": "Flam. Zucchetto +2",
        "STR": 25, "DEX": 9, "VIT": 32, "Accuracy": 24, "Attack": 24,
        "TA": 5, "Store TP": 6,
        "Jobs": ["war", "pld", "drk", "drg", "sam"],
    },
    "Sakpata's Helm": {
        "Name": "Sakpata's Helm", "Name2": "Sakpata's Helm",
        "STR": 26, "VIT": 33, "Accuracy": 40, "Attack": 40,
        "DA": 7, "DT": -7,
        "Jobs": ["war", "pld", "drk", "drg", "sam"],
    },
    "Nyame Helm": {
        "Name": "Nyame Helm", "Name2": "Nyame Helm",
        "STR": 26, "DEX": 26, "VIT": 26, "Accuracy": 40, "Attack": 40,
        "DT": -7, "Weapon Skill Damage": 10,
        "Jobs": all_jobs,
    },
    "Hjarrandi Helm": {
        "Name": "Hjarrandi Helm", "Name2": "Hjarrandi Helm",
        "STR": 27, "DEX": 23, "VIT": 28, "Accuracy": 35, "Attack": 35,
        "DA": 6, "Crit Rate": 5,
        "Jobs": ["war", "pld", "drk", "drg", "sam", "nin"],
    },
    
    # Body
    "Sakpata's Plate": {
        "Name": "Sakpata's Plate", "Name2": "Sakpata's Plate",
        "STR": 33, "VIT": 33, "Accuracy": 40, "Attack": 40,
        "DT": -10, "PDL": 5, "Store TP": 10,
        "Jobs": ["war", "pld", "drk", "drg", "sam"],
    },
    "Nyame Mail": {
        "Name": "Nyame Mail", "Name2": "Nyame Mail",
        "STR": 30, "DEX": 30, "VIT": 30, "Accuracy": 40, "Attack": 40,
        "DT": -9, "Weapon Skill Damage": 13,
        "Jobs": all_jobs,
    },
    
    # Hands
    "Sakpata's Gauntlets": {
        "Name": "Sakpata's Gauntlets", "Name2": "Sakpata's Gauntlets",
        "STR": 24, "DEX": 32, "VIT": 38, "Accuracy": 35, "Attack": 35,
        "DA": 6, "DT": -8, "Store TP": 8,
        "Jobs": ["war", "pld", "drk", "drg", "sam"],
    },
    "Nyame Gauntlets": {
        "Name": "Nyame Gauntlets", "Name2": "Nyame Gauntlets",
        "STR": 28, "DEX": 28, "VIT": 28, "Accuracy": 40, "Attack": 40,
        "DT": -7, "Weapon Skill Damage": 11,
        "Jobs": all_jobs,
    },
    
    # Legs
    "Sakpata's Cuisses": {
        "Name": "Sakpata's Cuisses", "Name2": "Sakpata's Cuisses",
        "STR": 42, "VIT": 32, "Accuracy": 40, "Attack": 40,
        "DT": -9, "Store TP": 9,
        "Jobs": ["war", "pld", "drk", "drg", "sam"],
    },
    "Nyame Flanchard": {
        "Name": "Nyame Flanchard", "Name2": "Nyame Flanchard",
        "STR": 32, "DEX": 32, "VIT": 32, "Accuracy": 40, "Attack": 40,
        "DT": -8, "Weapon Skill Damage": 12,
        "Jobs": all_jobs,
    },
    
    # Feet
    "Nyame Sollerets": {
        "Name": "Nyame Sollerets", "Name2": "Nyame Sollerets",
        "STR": 26, "DEX": 26, "VIT": 26, "Accuracy": 40, "Attack": 40,
        "DT": -7, "Weapon Skill Damage": 10,
        "Jobs": all_jobs,
    },
    "Flam. Gambieras +2": {
        "Name": "Flam. Gambieras +2", "Name2": "Flam. Gambieras +2",
        "STR": 16, "DEX": 17, "VIT": 24, "Accuracy": 24, "Attack": 24,
        "Crit Rate": 5, "Store TP": 5,
        "Jobs": ["war", "pld", "drk", "drg", "sam"],
    },
    "Sakpata's Leggings": {
        "Name": "Sakpata's Leggings", "Name2": "Sakpata's Leggings",
        "STR": 18, "VIT": 25, "Accuracy": 35, "Attack": 35,
        "TA": 4, "DT": -6,
        "Jobs": ["war", "pld", "drk", "drg", "sam"],
    },
    
    # Neck
    "Rep. Plat. Medal": {
        "Name": "Rep. Plat. Medal", "Name2": "Rep. Plat. Medal",
        "STR": 18, "DEX": 18, "VIT": 18, "Accuracy": 30, "Dual Wield": 3,
        "Jobs": all_jobs,
    },
    "Fotia Gorget": {
        "Name": "Fotia Gorget", "Name2": "Fotia Gorget",
        "ftp": 0.1,  # Special: FTP bonus
        "Jobs": all_jobs,
    },
    
    # Waist
    "Sailfi Belt +1": {
        "Name": "Sailfi Belt +1", "Name2": "Sailfi Belt +1",
        "STR": 15, "DEX": 15, "Weapon Skill Damage": 5, "DA": 2, "TA": 2,
        "Jobs": all_jobs,
    },
    "Fotia Belt": {
        "Name": "Fotia Belt", "Name2": "Fotia Belt",
        "ftp": 0.1,  # Special: FTP bonus
        "Jobs": all_jobs,
    },
    "Kentarch Belt +1": {
        "Name": "Kentarch Belt +1", "Name2": "Kentarch Belt +1",
        "STR": 10, "DEX": 10, "Accuracy": 14, "Attack": 14, "DA": 3,
        "Jobs": all_jobs,
    },
    
    # Earrings
    "Cessance Earring": {
        "Name": "Cessance Earring", "Name2": "Cessance Earring",
        "DEX": 4, "Accuracy": 6, "Attack": 6, "DA": 3, "Store TP": 5,
        "Jobs": all_jobs,
    },
    "Telos Earring": {
        "Name": "Telos Earring", "Name2": "Telos Earring",
        "STR": 5, "DEX": 5, "Accuracy": 10, "Attack": 10, "DA": 1, "Store TP": 5,
        "Jobs": all_jobs,
    },
    "Moonshade Earring": {
        "Name": "Moonshade Earring", "Name2": "Moonshade Earring",
        "TP Bonus": 250, "Accuracy": 4, "Magic Accuracy": 4,
        "Jobs": all_jobs,
    },
    "Thrud Earring": {
        "Name": "Thrud Earring", "Name2": "Thrud Earring",
        "STR": 10, "VIT": 10, "Weapon Skill Damage": 3,
        "Jobs": all_jobs,
    },
    
    # Rings
    "Niqmaddu Ring": {
        "Name": "Niqmaddu Ring", "Name2": "Niqmaddu Ring",
        "STR": 10, "DEX": 10, "VIT": 10, "QA": 3,
        "Jobs": all_jobs,
    },
    "Epaminondas's Ring": {
        "Name": "Epaminondas's Ring", "Name2": "Epaminondas's Ring",
        "STR": 5, "DEX": 5, "VIT": 5, "Weapon Skill Damage": 5,
        "Jobs": all_jobs,
    },
    "Sroda Ring": {
        "Name": "Sroda Ring", "Name2": "Sroda Ring",
        "STR": 15, "Weapon Skill Damage": 3,
        "Jobs": all_jobs,
    },
    "Cornelia's Ring": {
        "Name": "Cornelia's Ring", "Name2": "Cornelia's Ring",
        "STR": 15, "VIT": 15, "Accuracy": 15, "Attack": 15,
        "Jobs": all_jobs,
    },
    "Flamma Ring": {
        "Name": "Flamma Ring", "Name2": "Flamma Ring",
        "STR": 5, "DEX": 5, "VIT": 10, "Accuracy": 5, "Attack": 5, "Store TP": 3,
        "Jobs": ["war", "pld", "drk", "drg", "sam"],
    },
    
    # Back (capes)
    "Cichol's Mantle": {
        "Name": "Cichol's Mantle", "Name2": "Cichol's Mantle STR DA",
        "STR": 30, "Accuracy": 20, "Attack": 20, "DA": 10, "Weapon Skill Damage": 10,
        "Jobs": ["war"],
    },
    
    # Ammo
    "Coiste Bodhar": {
        "Name": "Coiste Bodhar", "Name2": "Coiste Bodhar Path: A R15",
        "STR": 15, "VIT": 10, "Accuracy": 15, "Attack": 15, "DA": 3, "Store TP": 5,
        "Jobs": ["war", "pld", "drk", "drg", "run"],
    },
}


def get_gear_by_name(name):
    """Look up gear stats by name."""
    # Handle known variations
    name_clean = name.strip()
    
    # Direct lookup
    if name_clean in KNOWN_GEAR:
        return KNOWN_GEAR[name_clean].copy()
    
    # Try partial match for augmented items
    for known_name, gear in KNOWN_GEAR.items():
        if known_name.lower() in name_clean.lower():
            return gear.copy()
    
    return None


# =============================================================================
# OPTIMIZATION
# =============================================================================

def optimize_slot(base_gearset, slot, options, job, buffs, abilities, enemy, ws_name, tp):
    """
    Find the best gear for a single slot by testing all options.
    
    Args:
        base_gearset: Starting gearset dict
        slot: Slot to optimize ('head', 'body', etc.)
        options: List of gear dicts to test
        job: Main job string
        buffs: Buffs dict for create_player
        abilities: Abilities dict for create_player
        enemy: Enemy object
        ws_name: Weaponskill name
        tp: TP value to test at
    
    Returns:
        (best_gear, best_damage, results_list)
    """
    if not options:
        return None, 0, []
    
    results = []
    best_damage = 0
    best_gear = None
    
    for gear in options:
        # Create test gearset
        test_gearset = base_gearset.copy()
        test_gearset[slot] = gear
        
        try:
            player = create_player(
                main_job=job,
                sub_job="sam",
                master_level=50,
                gearset=test_gearset,
                buffs=buffs,
                abilities=abilities,
            )
            
            damage, _ = average_ws(
                player=player,
                enemy=enemy,
                ws_name=ws_name,
                input_tp=tp,
                ws_type="melee",
                input_metric="Damage",
                simulation=False,
            )
            
            results.append((gear["Name2"], damage))
            
            if damage > best_damage:
                best_damage = damage
                best_gear = gear
                
        except Exception as e:
            results.append((gear.get("Name2", "Unknown"), f"Error: {e}"))
    
    return best_gear, best_damage, results


# =============================================================================
# MAIN TEST
# =============================================================================

def main():
    print()
    print("=" * 70)
    print("INVENTORY-BASED GEAR OPTIMIZATION TEST")
    print("=" * 70)
    print()
    
    # Load inventory
    csv_path = "/home/martin/Projects/GSO_wsdist/inventory_full_Masinmanci_20260111_124357.csv"
    print(f"Loading inventory from: {csv_path}")
    
    try:
        raw_items = parse_csv_inventory(csv_path)
        print(f"  Loaded {len(raw_items)} items")
    except Exception as e:
        print(f"  ERROR loading inventory: {e}")
        return
    
    # Set up enemy with Base Defense
    enemy_data = preset_enemies["Apex Toad"].copy()
    enemy_data["Base Defense"] = enemy_data["Defense"]
    enemy = create_enemy(enemy_data)
    
    # Standard buffs
    buffs = {
        "Food": {"STR": 7, "Attack": 150, "Ranged Attack": 150},
        "BRD": {"Attack": 280, "Ranged Attack": 280, "Magic Haste": 0.25,
                "Accuracy": 50, "Ranged Accuracy": 50},
    }
    abilities = {"Berserk": True, "Warcry": True}
    
    # Create base gearset
    base_gearset = {
        'main': KNOWN_GEAR["Naegling"].copy(),
        'sub': KNOWN_GEAR["Blurred Shield +1"].copy(),
        'ranged': Empty.copy(),
        'ammo': KNOWN_GEAR["Coiste Bodhar"].copy(),
        'head': KNOWN_GEAR["Nyame Helm"].copy(),
        'neck': KNOWN_GEAR["Rep. Plat. Medal"].copy(),
        'ear1': KNOWN_GEAR["Moonshade Earring"].copy(),
        'ear2': KNOWN_GEAR["Thrud Earring"].copy(),
        'body': KNOWN_GEAR["Nyame Mail"].copy(),
        'hands': KNOWN_GEAR["Nyame Gauntlets"].copy(),
        'ring1': KNOWN_GEAR["Epaminondas's Ring"].copy(),
        'ring2': KNOWN_GEAR["Sroda Ring"].copy(),
        'back': KNOWN_GEAR["Cichol's Mantle"].copy(),
        'waist': KNOWN_GEAR["Sailfi Belt +1"].copy(),
        'legs': KNOWN_GEAR["Nyame Flanchard"].copy(),
        'feet': KNOWN_GEAR["Nyame Sollerets"].copy(),
    }
    
    # Calculate baseline damage
    print()
    print("-" * 70)
    print("BASELINE: Full Nyame WS set")
    print("-" * 70)
    
    player = create_player("war", "sam", 50, base_gearset, buffs, abilities)
    base_damage, _ = average_ws(player, enemy, "Savage Blade", 2000, "melee", "Damage", False)
    print(f"Savage Blade @ 2000 TP: {base_damage:,.0f}")
    
    # Test optimization for specific slots
    print()
    print("-" * 70)
    print("SLOT OPTIMIZATION: Finding best gear per slot")
    print("-" * 70)
    
    # Define options for each slot to test
    slot_options = {
        'head': [
            KNOWN_GEAR["Nyame Helm"],
            KNOWN_GEAR["Sakpata's Helm"],
            KNOWN_GEAR["Hjarrandi Helm"],
            KNOWN_GEAR["Flam. Zucchetto +2"],
        ],
        'body': [
            KNOWN_GEAR["Nyame Mail"],
            KNOWN_GEAR["Sakpata's Plate"],
        ],
        'hands': [
            KNOWN_GEAR["Nyame Gauntlets"],
            KNOWN_GEAR["Sakpata's Gauntlets"],
        ],
        'legs': [
            KNOWN_GEAR["Nyame Flanchard"],
            KNOWN_GEAR["Sakpata's Cuisses"],
        ],
        'feet': [
            KNOWN_GEAR["Nyame Sollerets"],
            KNOWN_GEAR["Sakpata's Leggings"],
            KNOWN_GEAR["Flam. Gambieras +2"],
        ],
        'ring1': [
            KNOWN_GEAR["Epaminondas's Ring"],
            KNOWN_GEAR["Sroda Ring"],
            KNOWN_GEAR["Niqmaddu Ring"],
            KNOWN_GEAR["Cornelia's Ring"],
        ],
        'ear1': [
            KNOWN_GEAR["Moonshade Earring"],
            KNOWN_GEAR["Thrud Earring"],
            KNOWN_GEAR["Cessance Earring"],
            KNOWN_GEAR["Telos Earring"],
        ],
        'waist': [
            KNOWN_GEAR["Sailfi Belt +1"],
            KNOWN_GEAR["Kentarch Belt +1"],
            KNOWN_GEAR["Fotia Belt"],
        ],
    }
    
    optimized_gearset = base_gearset.copy()
    
    for slot, options in slot_options.items():
        print(f"\n{slot.upper()}:")
        best_gear, best_damage, results = optimize_slot(
            optimized_gearset, slot, options,
            "war", buffs, abilities, enemy, "Savage Blade", 2000
        )
        
        # Sort results
        numeric_results = [(n, d) for n, d in results if isinstance(d, (int, float))]
        for name, damage in sorted(numeric_results, key=lambda x: x[1], reverse=True):
            marker = " <-- BEST" if name == best_gear.get("Name2", "") else ""
            print(f"  {name:30} -> {damage:>8,.0f}{marker}")
        
        if best_gear:
            optimized_gearset[slot] = best_gear
    
    # Final comparison
    print()
    print("=" * 70)
    print("FINAL COMPARISON")
    print("=" * 70)
    
    # Calculate optimized damage
    player_opt = create_player("war", "sam", 50, optimized_gearset, buffs, abilities)
    opt_damage, _ = average_ws(player_opt, enemy, "Savage Blade", 2000, "melee", "Damage", False)
    
    improvement = ((opt_damage - base_damage) / base_damage) * 100
    
    print(f"\nBaseline damage:  {base_damage:>10,.0f}")
    print(f"Optimized damage: {opt_damage:>10,.0f}")
    print(f"Improvement:      {improvement:>10.1f}%")
    
    print("\nOptimized gear:")
    for slot in WSDIST_SLOTS:
        gear = optimized_gearset.get(slot, {})
        name = gear.get("Name2", gear.get("Name", "Empty"))
        print(f"  {slot:12} = {name}")
    
    print()
    print("=" * 70)
    print("Test completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
