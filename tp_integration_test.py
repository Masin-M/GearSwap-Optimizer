#!/usr/bin/env python3
"""
TP Set Integration Test: Inventory → Beam Search → wsdist

This script demonstrates the TP optimization pipeline:
1. Load inventory from CSV (automated item reading)
2. Convert items to wsdist format
3. Run beam search to find TP set contenders
4. Extract reduced item pool
5. Pass to wsdist for final simulation-based optimization

The key metric for TP sets is "Time to WS" - how quickly you can
build from 0 TP to your WS threshold (usually 1000 or 1250 TP).

Usage:
    python tp_integration_test.py [inventory_csv_path]
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
    from actions import average_attack_round, get_delay_timing
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
    "Tauret": {
        "Name": "Tauret", "Name2": "Tauret", "Type": "Weapon",
        "Skill Type": "Dagger", "DMG": 120, "Delay": 186,
        "STR": 15, "DEX": 15, "VIT": 15, "AGI": 15,
        "Accuracy": 40, "Attack": 30,
        "Crit Rate": 10,  # Tauret has crit rate bonus at low TP
        "Dagger Skill": 269,
        "Jobs": ["war", "rdm", "thf", "pld", "drk", "bst", "brd", 
                 "rng", "nin", "drg", "blu", "cor", "dnc"],
    },
    "Gleti's Knife": {
        "Name": "Gleti's Knife", "Name2": "Gleti's Knife", "Type": "Weapon",
        "Skill Type": "Dagger", "DMG": 118, "Delay": 186,
        "DEX": 20, "AGI": 20,
        "Accuracy": 35, "Attack": 25,
        "Store TP": 8,
        "Dagger Skill": 250,
        "Jobs": ["war", "rdm", "thf", "pld", "drk", "bst", "brd", 
                 "rng", "nin", "drg", "blu", "cor", "dnc"],
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
# OPTIMIZATION PROFILES FOR TP SETS
# =============================================================================

def create_tp_profile(job: Job, is_dual_wield: bool = False) -> OptimizationProfile:
    """
    Create an optimization profile for TP set optimization.
    
    TP sets prioritize:
    - Store TP (more TP per swing)
    - Multi-attack (DA/TA/QA for more hits = more TP)
    - Haste (faster attack speed)
    - Accuracy (need to hit to get TP)
    
    Args:
        job: Player's job
        is_dual_wield: Whether using dual wield (affects DW weight)
    """
    weights = {
        # TP building stats (highest priority)
        'store_tp': 10.0,          # Each point of Store TP is very valuable
        
        # Multi-attack (each extra hit = more TP)
        'double_attack': 80.0,     # ~1% DA is worth about 8 Store TP
        'triple_attack': 120.0,    # TA is more valuable than DA
        'quad_attack': 160.0,      # QA is even more valuable
        
        # Haste (faster swings = more TP over time)
        'gear_haste': 70.0,        # 1% gear haste is valuable
        
        # Accuracy (need to hit to gain TP)
        'accuracy': 3.0,           # Important but secondary
        
        # Attack (some TP phase damage contribution)
        'attack': 1.0,             # Lower priority for pure TP set
        
        # Crit (some weapons like Tauret benefit)
        'crit_rate': 2.0,
    }
    
    if is_dual_wield:
        # Dual wield gives extra swings (main + off-hand)
        weights['dual_wield'] = 60.0
    
    return OptimizationProfile(
        name=f"TP Set ({job.name})",
        weights=weights,
        hard_caps={
            'gear_haste': 2500,    # 25% gear haste cap
        },
        soft_caps={
            # With Haste II (30%) + March x2 (16%), you need ~11% DW to cap delay
            'dual_wield': 1100 if is_dual_wield else 0,
        },
        job=job,
    )


def create_hybrid_tp_profile(job: Job, is_dual_wield: bool = False) -> OptimizationProfile:
    """
    Create a hybrid TP set profile that also values TP phase damage.
    
    This is useful when TP phase damage contribution matters
    (e.g., on certain jobs or when fighting weaker enemies).
    """
    weights = {
        # TP building stats
        'store_tp': 8.0,
        'double_attack': 70.0,
        'triple_attack': 100.0,
        'quad_attack': 140.0,
        'gear_haste': 60.0,
        
        # More emphasis on damage
        'accuracy': 5.0,
        'attack': 3.0,
        'crit_rate': 4.0,
        'crit_damage': 3.0,
        
        # Base stats for damage
        'STR': 0.5,
        'DEX': 0.3,
    }
    
    if is_dual_wield:
        weights['dual_wield'] = 50.0
    
    return OptimizationProfile(
        name=f"Hybrid TP Set ({job.name})",
        weights=weights,
        hard_caps={
            'gear_haste': 2500,
        },
        soft_caps={
            'dual_wield': 1100 if is_dual_wield else 0,
        },
        job=job,
    )


# =============================================================================
# TP SIMULATION HELPER
# =============================================================================

def simulate_tp_set(
    gearset: dict,
    enemy: object,
    player_job: str = "war",
    sub_job: str = "sam",
    master_level: int = 50,
    ws_threshold: int = 1000,
    starting_tp: int = 0,
    buffs: dict = None,
    abilities: dict = None,
) -> dict:
    """
    Simulate a TP set and return key metrics.
    
    Args:
        gearset: wsdist-format gearset dict
        enemy: Enemy object from create_enemy
        player_job: Main job
        sub_job: Sub job
        master_level: Master level
        ws_threshold: TP threshold for WS (usually 1000)
        starting_tp: Starting TP value
        buffs: Buff dict
        abilities: Abilities dict
    
    Returns:
        dict with:
            - time_to_ws: Seconds to reach WS threshold
            - tp_per_round: TP gained per attack round
            - damage_per_round: Damage per attack round
            - time_per_round: Time per attack round
            - dps: Damage per second (TP phase only)
    """
    if buffs is None:
        buffs = {}
    if abilities is None:
        abilities = {}
    
    # Create player with the gearset
    player = create_player(
        main_job=player_job,
        sub_job=sub_job,
        master_level=master_level,
        gearset=gearset,
        buffs=buffs,
        abilities=abilities,
    )
    
    # Get TP set metrics using "Time to WS" metric
    result = average_attack_round(
        player=player,
        enemy=enemy,
        starting_tp=starting_tp,
        ws_threshold=ws_threshold,
        input_metric="Time to WS",
        simulation=False,
    )
    
    # result format: (metric, [damage, tp_per_round, time_per_round, invert], magic_damage)
    time_to_ws = result[0]
    damage_per_round = result[1][0]
    tp_per_round = result[1][1]
    time_per_round = result[1][2]
    
    # Calculate DPS (TP phase only)
    dps = damage_per_round / time_per_round if time_per_round > 0 else 0
    
    return {
        'time_to_ws': time_to_ws,
        'tp_per_round': tp_per_round,
        'damage_per_round': damage_per_round,
        'time_per_round': time_per_round,
        'dps': dps,
    }


# =============================================================================
# MAIN INTEGRATION TEST
# =============================================================================

def run_tp_integration_test(inventory_path: str):
    """
    Run the full TP integration test.
    
    Args:
        inventory_path: Path to the inventory CSV file
    """
    print()
    print("=" * 70)
    print("TP SET OPTIMIZATION: INVENTORY → BEAM SEARCH → WSDIST")
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
    print("STEP 2: Setting Up TP Optimization")
    print("-" * 70)
    
    # Configuration
    job = Job.WAR
    is_dual_wield = False  # Using sword + shield
    ws_threshold = 1000    # Standard WS threshold
    beam_width = 10
    
    print(f"  Job: {job.name}")
    print(f"  Dual Wield: {is_dual_wield}")
    print(f"  WS Threshold: {ws_threshold} TP")
    print(f"  Beam Width: {beam_width}")
    
    # Create TP profile
    profile = create_tp_profile(job, is_dual_wield)
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
    print("STEP 3: Running Beam Search for TP Set")
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
    
    print("\nSearching for TP set contenders...")
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
                # Show relevant TP stats
                name = item.get('Name2', item.get('Name', '?'))
                stp = item.get('Store TP', 0)
                da = item.get('DA', 0)
                ta = item.get('TA', 0)
                haste = item.get('Gear Haste', 0)
                stats = []
                if stp: stats.append(f"STP+{stp}")
                if da: stats.append(f"DA+{da}")
                if ta: stats.append(f"TA+{ta}")
                if haste: stats.append(f"Haste+{haste}")
                stat_str = f" ({', '.join(stats)})" if stats else ""
                print(f"    - {name}{stat_str}")
            if len(items) > 3:
                print(f"    ... and {len(items) - 3} more")
    
    # =========================================================================
    # STEP 5: Show Contender Sets
    # =========================================================================
    print("\n" + "-" * 70)
    print("STEP 5: Top TP Set Contenders (Beam Search Scoring)")
    print("-" * 70)
    
    for i, candidate in enumerate(contenders[:3]):  # Show top 3
        print(f"\n--- Contender #{i+1} (Beam Score: {candidate.score:.1f}) ---")
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
    print("STEP 6: wsdist TP Simulation")
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
    
    # Standard TP phase buffs
    buffs = {
        "Food": {"STR": 7, "Attack": 150, "Ranged Attack": 150},
        "BRD": {"Attack": 280, "Ranged Attack": 280, "Magic Haste": 0.25,
                "Accuracy": 50, "Ranged Accuracy": 50},
    }
    abilities = {"Berserk": True, "Warcry": True}
    
    print(f"  Enemy: {enemy_data.get('Name', 'Unknown')}")
    print(f"  WS Threshold: {ws_threshold} TP")
    print(f"  Buffs: {list(buffs.keys())}")
    
    # Test top contenders with wsdist
    print("\nSimulating TP sets...")
    
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
            
            # Simulate TP set
            metrics = simulate_tp_set(
                gearset=gearset,
                enemy=enemy,
                player_job="war",
                sub_job="sam",
                master_level=50,
                ws_threshold=ws_threshold,
                starting_tp=0,
                buffs=buffs,
                abilities=abilities,
            )
            
            results.append((i, candidate, metrics))
            
        except Exception as e:
            print(f"  Contender #{i+1}: Error - {e}")
            import traceback
            traceback.print_exc()
    
    # Sort by Time to WS (lower is better)
    results.sort(key=lambda x: x[2]['time_to_ws'])
    
    print("\n" + "=" * 70)
    print("FINAL RESULTS - Ranked by Time to WS (lower is better)")
    print("=" * 70)
    
    for rank, (orig_idx, candidate, metrics) in enumerate(results[:5]):
        print(f"\n#{rank+1} - {metrics['time_to_ws']:.2f}s to WS (was contender #{orig_idx+1})")
        print(f"    Beam score: {candidate.score:.1f}")
        print(f"    TP/Round: {metrics['tp_per_round']:.1f}")
        print(f"    Time/Round: {metrics['time_per_round']:.3f}s")
        print(f"    Dmg/Round: {metrics['damage_per_round']:.0f}")
        print(f"    TP Phase DPS: {metrics['dps']:.0f}")
        print("    Gear:")
        for slot in ['head', 'body', 'hands', 'legs', 'feet', 'ear1', 'ear2', 
                     'ring1', 'ring2', 'waist', 'neck', 'back', 'ammo']:
            if slot in candidate.gear:
                name = candidate.gear[slot].get('Name2', 
                       candidate.gear[slot].get('Name', 'Empty'))
                if name != 'Empty':
                    print(f"      {slot:8s}: {name}")
    
    # =========================================================================
    # COMPARISON: Time to WS details
    # =========================================================================
    if len(results) >= 2:
        print("\n" + "=" * 70)
        print("TIME TO WS COMPARISON")
        print("=" * 70)
        
        best = results[0]
        worst = results[-1]
        
        best_time = best[2]['time_to_ws']
        worst_time = worst[2]['time_to_ws']
        
        print(f"\n  Fastest: {best_time:.2f}s (Contender #{best[0]+1})")
        print(f"  Slowest: {worst_time:.2f}s (Contender #{worst[0]+1})")
        print(f"  Difference: {worst_time - best_time:.2f}s ({(worst_time/best_time - 1)*100:.1f}% slower)")
        
        # Calculate WSs per minute
        best_ws_per_min = 60 / (best_time + 2.0)  # +2s for WS animation
        worst_ws_per_min = 60 / (worst_time + 2.0)
        
        print(f"\n  WS/minute (best): {best_ws_per_min:.2f}")
        print(f"  WS/minute (worst): {worst_ws_per_min:.2f}")
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("TP OPTIMIZATION TEST COMPLETE")
    print("=" * 70)
    
    if results:
        best_idx, best_candidate, best_metrics = results[0]
        print(f"\n✓ Best TP set found: {best_metrics['time_to_ws']:.2f}s to {ws_threshold} TP")
        print(f"  (Contender #{best_idx+1} with beam score {best_candidate.score:.1f})")
    
    print(f"\nPipeline summary:")
    print(f"  1. Loaded {len(inventory.items)} items from inventory")
    print(f"  2. Beam search produced {len(contenders)} contenders")
    print(f"  3. Extracted pool of {total_items} unique items")
    print(f"  4. wsdist simulated {len(results)} TP sets")
    
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
    
    run_tp_integration_test(inventory_path)
