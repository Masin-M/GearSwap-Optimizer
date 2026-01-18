#!/usr/bin/env python3
"""
Full Integration Test: Inventory → Beam Search → wsdist

This script demonstrates the complete pipeline:
1. Load inventory from CSV (automated item reading)
2. Convert items to wsdist format
3. Run beam search to find contender gearsets
4. Extract reduced item pool
5. Pass to wsdist for final simulation-based optimization

Usage:
    python integration_test.py [inventory_csv_path]
"""

import sys
import os
from pathlib import Path

# =============================================================================
# PATH SETUP
# =============================================================================

# Add required paths
SCRIPT_DIR = Path(__file__).parent
WSDIST_DIR = SCRIPT_DIR / 'wsdist_beta-main'

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(WSDIST_DIR))

# =============================================================================
# IMPORTS
# =============================================================================

# Our modules
from models import Job, Slot, OptimizationProfile
from inventory_loader import Inventory, load_inventory
from wsdist_converter import to_wsdist_gear
from beam_search_optimizer import (
    BeamSearchOptimizer, 
    WSDIST_SLOTS, 
    ARMOR_SLOTS,
    prepare_wsdist_check_gear
)

# wsdist imports
try:
    from gear import Empty, all_jobs
    from enemies import preset_enemies
    from create_player import create_player, create_enemy
    from actions import average_ws
    WSDIST_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import wsdist modules: {e}")
    print("Running in test mode without wsdist simulation")
    WSDIST_AVAILABLE = False
    
    # Stub definitions for testing
    all_jobs = ["war", "mnk", "whm", "blm", "rdm", "thf", "pld", "drk", 
                "bst", "brd", "rng", "smn", "sam", "nin", "drg", "blu", 
                "cor", "pup", "dnc", "sch", "geo", "run"]
    Empty = {"Name": "Empty", "Name2": "Empty", "Type": "None", "Jobs": all_jobs}


# =============================================================================
# SAMPLE WEAPONS (for testing when inventory doesn't have weapons)
# =============================================================================

SAMPLE_WEAPONS = {
    "Naegling": {
        "Name": "Naegling", "Name2": "Naegling", "Type": "Weapon",
        "Skill Type": "Sword", "DMG": 166, "Delay": 240,
        "STR": 15, "DEX": 15, "MND": 15, "INT": 15,
        "Accuracy": 40, "Attack": 30, "Magic Accuracy": 40,
        "Sword Skill": 250, "Magic Accuracy Skill": 250,
        "Jobs": ["war", "rdm", "thf", "pld", "drk", "bst", "brd", 
                 "rng", "nin", "drg", "blu", "cor", "run"],
    },
    "Blurred Shield +1": {
        "Name": "Blurred Shield +1", "Name2": "Blurred Shield +1",
        "Type": "Shield", "STR": 8, "DEX": 8, "VIT": 8,
        "Gear Haste": 3,
        "Jobs": ["war", "pld", "drk", "bst", "drg", "run"],
    },
    "Chango": {
        "Name": "Chango", "Name2": "Chango R15", "Type": "Weapon",
        "Skill Type": "Great Axe", "DMG": 352, "Delay": 480,
        "Accuracy": 30, "Magic Accuracy": 30, "Store TP": 10, "TP Bonus": 500,
        "Great Axe Skill": 269, "Magic Accuracy Skill": 228,
        "Jobs": ["war"],
    },
}


# =============================================================================
# OPTIMIZATION PROFILES FOR DIFFERENT TASKS
# =============================================================================

def create_ws_profile(job: Job, ws_type: str = 'physical') -> OptimizationProfile:
    """
    Create an optimization profile for weaponskill optimization.
    
    Args:
        job: Player's job
        ws_type: 'physical', 'magical', or 'hybrid'
    """
    if ws_type == 'physical':
        # Physical WS: STR scaling, Attack, WSD, PDL
        weights = {
            'STR': 1.0,
            'attack': 0.5,
            'accuracy': 0.3,
            'ws_damage': 200.0,  # Very high - basis points so 1% = 100
            'double_attack': 0.8,
            'triple_attack': 1.2,
            'quad_attack': 1.5,
            'crit_rate': 0.6,
            'crit_damage': 0.4,
            'pdl': 150.0,  # Physical Damage Limit
        }
    elif ws_type == 'magical':
        weights = {
            'INT': 1.0,
            'MND': 0.5,
            'magic_attack': 1.5,
            'magic_accuracy': 0.8,
            'ws_damage': 200.0,
            'magic_burst_bonus': 50.0,
        }
    else:  # hybrid
        weights = {
            'STR': 0.8,
            'INT': 0.5,
            'attack': 0.4,
            'magic_attack': 0.6,
            'accuracy': 0.3,
            'magic_accuracy': 0.3,
            'ws_damage': 200.0,
        }
    
    return OptimizationProfile(
        name=f"{ws_type.title()} WS ({job.name})",
        weights=weights,
        hard_caps={
            'gear_haste': 2500,      # 25% cap
            'damage_taken': -5000,   # -50% cap
            'physical_dt': -5000,
            'magical_dt': -5000,
        },
        job=job,
    )


def create_tp_profile(job: Job, is_dual_wield: bool = False) -> OptimizationProfile:
    """Create an optimization profile for TP set optimization."""
    weights = {
        'store_tp': 10.0,
        'double_attack': 80.0,
        'triple_attack': 120.0,
        'quad_attack': 160.0,
        'gear_haste': 70.0,
        'accuracy': 3.0,
        'attack': 1.0,
    }
    
    if is_dual_wield:
        weights['dual_wield'] = 60.0
    
    return OptimizationProfile(
        name=f"TP Set ({job.name})",
        weights=weights,
        hard_caps={
            'gear_haste': 2500,
        },
        soft_caps={
            'dual_wield': 1100 if is_dual_wield else 0,  # ~11% needed with haste
        },
        job=job,
    )


# =============================================================================
# MAIN INTEGRATION TEST
# =============================================================================

def run_integration_test(inventory_path: str):
    """
    Run the full integration test.
    
    Args:
        inventory_path: Path to the inventory CSV file
    """
    print()
    print("=" * 70)
    print("INVENTORY → BEAM SEARCH → WSDIST INTEGRATION TEST")
    print("=" * 70)
    
    # =========================================================================
    # STEP 1: Load Inventory
    # =========================================================================
    print("\n" + "-" * 70)
    print("STEP 1: Loading Inventory")
    print("-" * 70)
    
    try:
        inventory = load_inventory(inventory_path)
        print(f"✓ Loaded {len(inventory.items)} items from {inventory_path}")
        print(f"  Equippable items: {inventory.stats.equippable_items}")
        
        # Show items by slot
        print("\n  Items by slot:")
        for slot, count in sorted(inventory.stats.items_by_slot.items(), 
                                   key=lambda x: x[0].value):
            print(f"    {slot.name:15s}: {count:3d} items")
            
    except FileNotFoundError:
        print(f"✗ Inventory file not found: {inventory_path}")
        return
    except Exception as e:
        print(f"✗ Error loading inventory: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # =========================================================================
    # STEP 2: Set up optimization parameters
    # =========================================================================
    print("\n" + "-" * 70)
    print("STEP 2: Setting Up Optimization")
    print("-" * 70)
    
    # Configuration
    job = Job.WAR
    ws_name = "Savage Blade"
    ws_type = "physical"
    beam_width = 10
    
    print(f"  Job: {job.name}")
    print(f"  Weaponskill: {ws_name}")
    print(f"  WS Type: {ws_type}")
    print(f"  Beam Width: {beam_width}")
    
    # Create profile
    profile = create_ws_profile(job, ws_type)
    print(f"  Profile: {profile.name}")
    
    # Fixed weapons
    main_weapon = SAMPLE_WEAPONS["Naegling"]
    sub_weapon = SAMPLE_WEAPONS["Blurred Shield +1"]
    
    print(f"  Main: {main_weapon['Name2']}")
    print(f"  Sub: {sub_weapon['Name2']}")
    
    # =========================================================================
    # STEP 3: Run Beam Search
    # =========================================================================
    print("\n" + "-" * 70)
    print("STEP 3: Running Beam Search")
    print("-" * 70)
    
    optimizer = BeamSearchOptimizer(
        inventory=inventory,
        profile=profile,
        beam_width=beam_width,
        job=job,
    )
    
    fixed_gear = {
        'main': main_weapon,
        'sub': sub_weapon,
    }
    
    print("\nSearching for contenders...")
    contenders = optimizer.search(fixed_gear=fixed_gear)
    
    print(f"\n✓ Found {len(contenders)} contender gearsets")
    
    # =========================================================================
    # STEP 4: Extract Item Pool
    # =========================================================================
    print("\n" + "-" * 70)
    print("STEP 4: Extracting Item Pool")
    print("-" * 70)
    
    item_pool = optimizer.extract_item_pool(contenders)
    
    total_items = sum(len(items) for items in item_pool.values())
    print(f"✓ Extracted {total_items} unique items across {len(item_pool)} slots")
    
    print("\nReduced pool per slot:")
    for slot in WSDIST_SLOTS:
        if slot in item_pool:
            items = item_pool[slot]
            print(f"  {slot:12s}: {len(items):2d} items")
            for item in items[:3]:  # Show first 3
                print(f"    - {item.get('Name2', item.get('Name', '?'))}")
            if len(items) > 3:
                print(f"    ... and {len(items) - 3} more")
    
    # =========================================================================
    # STEP 5: Show Contender Sets
    # =========================================================================
    print("\n" + "-" * 70)
    print("STEP 5: Top Contender Gearsets")
    print("-" * 70)
    
    for i, candidate in enumerate(contenders[:3]):  # Show top 3
        print(f"\n--- Contender #{i+1} (Score: {candidate.score:.1f}) ---")
        for slot in WSDIST_SLOTS:
            if slot in candidate.gear:
                name = candidate.gear[slot].get('Name2', 
                       candidate.gear[slot].get('Name', 'Empty'))
                print(f"  {slot:12s}: {name}")
    
    # =========================================================================
    # STEP 6: Run wsdist Simulation (if available)
    # =========================================================================
    if not WSDIST_AVAILABLE:
        print("\n" + "-" * 70)
        print("STEP 6: wsdist Simulation (SKIPPED - wsdist not available)")
        print("-" * 70)
        print("To complete the pipeline, ensure wsdist modules are importable.")
        return
    
    print("\n" + "-" * 70)
    print("STEP 6: wsdist Simulation")
    print("-" * 70)
    
    # Set up enemy
    enemy_data = preset_enemies.get("Apex Toad", {
        "Name": "Apex Toad",
        "Level": 135,
        "Defense": 1550,
        "Evasion": 1350,
        "VIT": 350,
        "AGI": 300,
    }).copy()
    enemy_data["Base Defense"] = enemy_data.get("Defense", 1550)
    enemy = create_enemy(enemy_data)
    
    # Buffs
    buffs = {
        "Food": {"STR": 7, "Attack": 150, "Ranged Attack": 150},
        "BRD": {"Attack": 280, "Ranged Attack": 280, "Magic Haste": 0.25,
                "Accuracy": 50, "Ranged Accuracy": 50},
    }
    abilities = {"Berserk": True, "Warcry": True}
    
    print(f"  Enemy: {enemy_data.get('Name', 'Unknown')}")
    print(f"  TP: 2000")
    print(f"  Buffs: {list(buffs.keys())}")
    
    # Test top contenders with wsdist
    print("\nSimulating contender sets...")
    
    results = []
    for i, candidate in enumerate(contenders):
        try:
            # Build gearset for wsdist
            gearset = {}
            for slot in WSDIST_SLOTS:
                if slot in candidate.gear:
                    gearset[slot] = candidate.gear[slot].copy()
                else:
                    gearset[slot] = Empty.copy()
            
            # Create player and calculate damage
            player = create_player(
                main_job="war",
                sub_job="sam",
                master_level=50,
                gearset=gearset,
                buffs=buffs,
                abilities=abilities,
            )
            
            damage, _ = average_ws(
                player=player,
                enemy=enemy,
                ws_name=ws_name,
                input_tp=2000,
                ws_type="melee",
                input_metric="Damage",
                simulation=False,
            )
            
            results.append((i, candidate, damage))
            
        except Exception as e:
            print(f"  Contender #{i+1}: Error - {e}")
    
    # Sort by damage and show results
    results.sort(key=lambda x: x[2], reverse=True)
    
    print("\n" + "=" * 70)
    print("FINAL RESULTS - Ranked by Simulated Damage")
    print("=" * 70)
    
    for rank, (orig_idx, candidate, damage) in enumerate(results[:5]):
        print(f"\n#{rank+1} - {damage:,.0f} damage (was contender #{orig_idx+1})")
        print(f"    Beam score: {candidate.score:.1f}")
        for slot in ['head', 'body', 'hands', 'legs', 'feet', 'ear1', 'ear2', 
                     'ring1', 'ring2', 'waist', 'neck', 'back', 'ammo']:
            if slot in candidate.gear:
                name = candidate.gear[slot].get('Name2', 
                       candidate.gear[slot].get('Name', 'Empty'))
                if name != 'Empty':
                    print(f"      {slot:8s}: {name}")
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("INTEGRATION TEST COMPLETE")
    print("=" * 70)
    
    if results:
        best_idx, best_candidate, best_damage = results[0]
        print(f"\n✓ Best set found: {best_damage:,.0f} damage")
        print(f"  (Contender #{best_idx+1} with beam score {best_candidate.score:.1f})")
    
    print(f"\nPipeline summary:")
    print(f"  1. Loaded {len(inventory.items)} items from inventory")
    print(f"  2. Beam search produced {len(contenders)} contenders")
    print(f"  3. Extracted pool of {total_items} unique items")
    print(f"  4. wsdist simulated {len(results)} gearsets")
    
    # Show the reduced search space
    full_combinations = 1
    reduced_combinations = 1
    for slot in ARMOR_SLOTS:
        full_count = len(optimizer.get_items_for_slot(slot))
        reduced_count = len(item_pool.get(slot, []))
        if full_count > 0:
            full_combinations *= full_count
        if reduced_count > 0:
            reduced_combinations *= reduced_count
    
    print(f"\n  Search space reduction:")
    print(f"    Full: {full_combinations:,} combinations")
    print(f"    Reduced: {reduced_combinations:,} combinations")
    if full_combinations > 0:
        reduction = (1 - reduced_combinations / full_combinations) * 100
        print(f"    Reduction: {reduction:.2f}%")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Default inventory path
    default_path = "inventory_full_Masinmanci_20260111_124357.csv"
    
    if len(sys.argv) > 1:
        inventory_path = sys.argv[1]
    else:
        inventory_path = default_path
    
    run_integration_test(inventory_path)
