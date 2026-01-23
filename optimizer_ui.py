#!/usr/bin/env python3
"""
Gear Set Optimizer UI

A terminal-based interface for optimizing gear sets.

Usage:
    python optimizer_ui.py [inventory_csv_path]

OPTIMIZED VERSION:
- Pre-stripped gear cache (avoids repeated dict comprehensions)
- Parallel simulation with ProcessPoolExecutor
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

# =============================================================================
# FROZEN EXECUTABLE DETECTION
# =============================================================================
# PyInstaller + Windows + ProcessPoolExecutor is problematic.
# Child processes fail to spawn properly in frozen executables.
# We detect this and fall back to sequential processing.

def _is_frozen_windows():
    """Check if running as a frozen PyInstaller exe on Windows."""
    return getattr(sys, 'frozen', False) and sys.platform == 'win32'

# Disable parallel by default when frozen on Windows
PARALLEL_AVAILABLE = not _is_frozen_windows()

# =============================================================================
# PATH SETUP
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
WSDIST_DIR = SCRIPT_DIR / 'wsdist_beta-main'

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(WSDIST_DIR))

# =============================================================================
# IMPORTS
# =============================================================================

from models import Job, Slot, OptimizationProfile, Stats
from inventory_loader import Inventory, load_inventory
from wsdist_converter import to_wsdist_gear
from beam_search_optimizer import (
    BeamSearchOptimizer,
    WSDIST_SLOTS,
    ARMOR_SLOTS,
    SLOT_TO_WSDIST,
)

# from fast_beam_search_optimizer import FastBeamSearchOptimizer

from numba_beam_search_optimizer import NumbaBeamSearchOptimizer

from ws_database import (
    WEAPONSKILLS,
    WeaponType,
    WSType,
    WeaponskillData,
    get_weaponskills_by_type,
    get_weaponskill,
)
from job_gifts_loader import (
    load_job_gifts,
    apply_job_gifts_to_player,
    JobGifts,
    JobGiftsCollection,
    get_job_gifts_summary,
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


# =============================================================================
# WSDIST GEAR HELPERS
# =============================================================================

def strip_gear_metadata(gear_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strip metadata fields from a gear dict before passing to wsdist.
    
    wsdist iterates through all keys and tries to sum numeric values.
    Metadata fields like '_augments' (a list) would cause type errors.
    
    Args:
        gear_dict: A wsdist gear dictionary
        
    Returns:
        A copy with underscore-prefixed keys removed
    """
    return {k: v for k, v in gear_dict.items() if not k.startswith('_')}


def build_stripped_gear_cache(
    item_pool: Dict[str, List[Dict[str, Any]]]
) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """
    Pre-strip metadata from all items in the item pool.
    
    Args:
        item_pool: Dict of slot -> list of gear dicts from extract_item_pool()
    
    Returns:
        Dict mapping (slot, Name2) -> stripped gear dict
    """
    cache = {}
    
    for slot, items in item_pool.items():
        for gear in items:
            name2 = gear.get('Name2', gear.get('Name', 'Unknown'))
            # Strip once, cache forever
            stripped = {k: v for k, v in gear.items() if not k.startswith('_')}
            cache[(slot, name2)] = stripped
    
    return cache


def build_gearset_fast(
    candidate_gear: Dict[str, Dict],
    stripped_cache: Dict[Tuple[str, str], Dict[str, Any]],
    empty_gear: Dict,
    slots: List[str],
) -> Dict[str, Dict]:
    """
    Build a gearset using pre-stripped gear from cache.
    """
    gearset = {}
    
    for slot in slots:
        if slot in candidate_gear:
            gear = candidate_gear[slot]
            name2 = gear.get('Name2', gear.get('Name', 'Unknown'))
            
            cache_key = (slot, name2)
            if cache_key in stripped_cache:
                gearset[slot] = stripped_cache[cache_key]
            else:
                # Fallback for fixed gear not in pool
                gearset[slot] = {k: v for k, v in gear.items() if not k.startswith('_')}
        else:
            gearset[slot] = empty_gear.copy()
    
    return gearset


# =============================================================================
# TP SET PROFILE TYPES
# =============================================================================

from enum import Enum

class TPSetType(Enum):
    """Types of TP sets with different optimization priorities."""
    PURE_TP = "Pure TP (Fastest WS)"
    HYBRID_TP = "Hybrid TP (TP + Damage)"
    ACC_TP = "Accuracy TP (High Acc + TP)"
    DT_TP = "DT TP (Survivability + TP)"
    REFRESH_TP = "Refresh TP (MP Sustain + TP)"


# =============================================================================
# JOB DEFINITIONS
# =============================================================================

JOB_LIST = [
    "WAR", "MNK", "WHM", "BLM", "RDM", "THF",
    "PLD", "DRK", "BST", "BRD", "RNG", "SMN",
    "SAM", "NIN", "DRG", "BLU", "COR", "PUP",
    "DNC", "SCH", "GEO", "RUN"
]

JOB_ENUM_MAP = {
    "WAR": Job.WAR, "MNK": Job.MNK, "WHM": Job.WHM, "BLM": Job.BLM,
    "RDM": Job.RDM, "THF": Job.THF, "PLD": Job.PLD, "DRK": Job.DRK,
    "BST": Job.BST, "BRD": Job.BRD, "RNG": Job.RNG, "SMN": Job.SMN,
    "SAM": Job.SAM, "NIN": Job.NIN, "DRG": Job.DRG, "BLU": Job.BLU,
    "COR": Job.COR, "PUP": Job.PUP, "DNC": Job.DNC, "SCH": Job.SCH,
    "GEO": Job.GEO, "RUN": Job.RUN,
}

# Map wsdist skill types to our WeaponType enum
SKILL_TO_WEAPON_TYPE = {
    "Hand-to-Hand": WeaponType.HAND_TO_HAND,
    "Dagger": WeaponType.DAGGER,
    "Sword": WeaponType.SWORD,
    "Great Sword": WeaponType.GREAT_SWORD,
    "Axe": WeaponType.AXE,
    "Great Axe": WeaponType.GREAT_AXE,
    "Scythe": WeaponType.SCYTHE,
    "Polearm": WeaponType.POLEARM,
    "Katana": WeaponType.KATANA,
    "Great Katana": WeaponType.GREAT_KATANA,
    "Club": WeaponType.CLUB,
    "Staff": WeaponType.STAFF,
    "Archery": WeaponType.ARCHERY,
    "Marksmanship": WeaponType.MARKSMANSHIP,
}


# =============================================================================
# UI HELPERS
# =============================================================================

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_menu(title: str, options: List[str], show_back: bool = True) -> int:
    """
    Display a menu and get user selection.
    
    Returns:
        Selected index (0-based), or -1 for back/quit
    """
    print_header(title)
    print()
    
    for i, option in enumerate(options, 1):
        print(f"  {i:3d}. {option}")
    
    if show_back:
        print(f"\n    0. Back / Cancel")
    
    print()
    
    while True:
        try:
            choice = input("Enter choice: ").strip()
            if choice == "0" or choice.lower() in ("q", "quit", "back", "b"):
                return -1
            
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return idx
            else:
                print(f"Please enter a number between 1 and {len(options)}")
        except ValueError:
            print("Please enter a valid number")


def print_table(headers: List[str], rows: List[List[str]], widths: List[int] = None):
    """Print a formatted table."""
    if widths is None:
        widths = [max(len(str(h)), max(len(str(row[i])) for row in rows) if rows else 0) + 2
                  for i, h in enumerate(headers)]
    
    # Header
    header_str = "  ".join(f"{h:<{w}}" for h, w in zip(headers, widths))
    print(f"  {header_str}")
    print("  " + "-" * sum(widths))
    
    # Rows
    for row in rows:
        row_str = "  ".join(f"{str(c):<{w}}" for c, w in zip(row, widths))
        print(f"  {row_str}")


# =============================================================================
# GEAR EXTRACTION
# =============================================================================

def get_weapons_from_inventory(inventory: Inventory, job: Job) -> List[Dict[str, Any]]:
    """Get all weapons from inventory that the job can equip."""
    from models import SLOT_BITMASK
    
    weapons = []
    main_mask = SLOT_BITMASK.get(Slot.MAIN, 0)
    
    # Check main slot items
    for item in inventory.items:
        # Check if it's equippable in main hand
        if not (item.base.slots & main_mask):
            continue
        
        # Check if job can equip
        if not item.base.can_equip(job):
            continue
        
        # Convert to wsdist format
        wsdist_item = to_wsdist_gear(item)
        if wsdist_item and wsdist_item.get("Type") == "Weapon":
            weapons.append(wsdist_item)
    
    return weapons


def get_offhand_from_inventory(inventory: Inventory, job: Job, main_weapon: Dict = None) -> List[Dict[str, Any]]:
    """
    Get all valid off-hand items for the job based on the main weapon.
    
    Rules:
    - 1H weapons: Can use Weapons (dual-wield), Shields, or Grips
    - 2H weapons: Can only use Grips
    - Hand-to-Hand: No sub slot allowed
    """
    from models import SLOT_BITMASK
    
    # Determine what types of off-hand items are valid
    TWO_HANDED_SKILLS = {"Great Sword", "Great Axe", "Scythe", "Polearm", "Staff", "Great Katana"}
    
    main_skill = main_weapon.get("Skill Type", "") if main_weapon else ""
    is_2h = main_skill in TWO_HANDED_SKILLS
    is_h2h = main_skill == "Hand-to-Hand"
    
    # Hand-to-Hand uses both hands, no sub allowed
    if is_h2h:
        return []
    
    offhands = []
    sub_mask = SLOT_BITMASK.get(Slot.SUB, 0)
    
    for item in inventory.items:
        # Check if it's equippable in sub slot
        if not (item.base.slots & sub_mask):
            continue
        
        # Check if job can equip
        if not item.base.can_equip(job):
            continue
        
        # Convert to wsdist format
        wsdist_item = to_wsdist_gear(item)
        if not wsdist_item:
            continue
            
        item_type = wsdist_item.get("Type", "")
        
        # Filter based on main weapon type
        if is_2h:
            # 2H weapons can only use Grips
            if item_type == "Grip":
                offhands.append(wsdist_item)
        else:
            # 1H weapons can use Weapons, Shields, or Grips
            if item_type in ("Weapon", "Shield", "Grip"):
                offhands.append(wsdist_item)
    
    return offhands


def get_weaponskills_for_weapon(weapon: Dict[str, Any]) -> List[WeaponskillData]:
    """Get all weaponskills available for a weapon's skill type."""
    skill_type = weapon.get("Skill Type", "")
    weapon_type = SKILL_TO_WEAPON_TYPE.get(skill_type)
    
    if weapon_type is None:
        return []
    
    return get_weaponskills_by_type(weapon_type)


# =============================================================================
# OPTIMIZATION PROFILES
# =============================================================================

def create_ws_profile_from_data(job: Job, ws_data: WeaponskillData) -> OptimizationProfile:
    """Create an optimization profile from weaponskill data."""
    
    # Get base weights from WS data
    weights = ws_data.get_stat_weights()
    
    # Scale weights for our basis point system
    scaled_weights = {}
    for stat, weight in weights.items():
        # Convert stat names to match our system
        stat_lower = stat.lower()
        if stat_lower in ('str', 'dex', 'vit', 'agi', 'int', 'mnd', 'chr'):
            scaled_weights[stat.upper()] = weight
        elif stat_lower == 'attack':
            scaled_weights['attack'] = weight
        elif stat_lower == 'accuracy':
            scaled_weights['accuracy'] = weight
        elif stat_lower == 'ws_damage':
            scaled_weights['ws_damage'] = weight * 20  # Scale for basis points
        elif stat_lower == 'double_attack':
            scaled_weights['double_attack'] = weight * 25
        elif stat_lower == 'triple_attack':
            scaled_weights['triple_attack'] = weight * 25
        elif stat_lower == 'quad_attack':
            scaled_weights['quad_attack'] = weight * 25
        elif stat_lower == 'crit_rate':
            scaled_weights['crit_rate'] = weight * 20
        elif stat_lower == 'crit_damage':
            scaled_weights['crit_damage'] = weight * 20
        elif stat_lower == 'magic_attack':
            scaled_weights['magic_attack'] = weight * 15
        else:
            scaled_weights[stat] = weight
    
    # Add PDL for physical WS
    if ws_data.ws_type in (WSType.PHYSICAL, WSType.HYBRID):
        scaled_weights['pdl'] = 150.0
    
    return OptimizationProfile(
        name=f"{ws_data.name} ({job.name})",
        weights=scaled_weights,
        hard_caps={
            'gear_haste': 2500,
            'damage_taken': -5000,
        },
        job=job,
    )


def create_tp_profile(job: Job, tp_type: TPSetType = TPSetType.PURE_TP, 
                      is_dual_wield: bool = False) -> OptimizationProfile:
    """
    Create an optimization profile for TP sets.
    
    Args:
        job: Player's job
        tp_type: Type of TP set to optimize for
        is_dual_wield: Whether using dual wield weapons
    
    Returns:
        OptimizationProfile configured for the TP set type
    """
    
    if tp_type == TPSetType.PURE_TP:
        # Pure TP: Maximum TP gain speed, minimal concern for other stats
        weights = {
            'store_tp': 10.0,
            'double_attack': 80.0,
            'triple_attack': 120.0,
            'quad_attack': 160.0,
            'gear_haste': 70.0,
            'accuracy': 3.0,
            'attack': 1.0,
            'crit_rate': 2.0,
        }
        name = f"Pure TP ({job.name})"
        
    elif tp_type == TPSetType.HYBRID_TP:
        # Hybrid: Balance TP gain with TP phase damage
        weights = {
            'store_tp': 8.0,
            'double_attack': 70.0,
            'triple_attack': 100.0,
            'quad_attack': 140.0,
            'gear_haste': 60.0,
            'accuracy': 5.0,
            'attack': 3.0,
            'crit_rate': 4.0,
            'crit_damage': 3.0,
            'STR': 0.5,
            'DEX': 0.3,
        }
        name = f"Hybrid TP ({job.name})"
        
    elif tp_type == TPSetType.ACC_TP:
        # High Accuracy TP: For tough content where accuracy matters
        weights = {
            'store_tp': 6.0,
            'double_attack': 50.0,
            'triple_attack': 75.0,
            'quad_attack': 100.0,
            'gear_haste': 50.0,
            'accuracy': 15.0,           # Much higher priority on accuracy
            'attack': 2.0,
            'DEX': 1.0,                 # DEX gives accuracy
            'AGI': 0.5,                 # AGI gives ranged acc
            'skill': 3.0,               # Weapon skill helps accuracy
        }
        name = f"Accuracy TP ({job.name})"
        
    elif tp_type == TPSetType.DT_TP:
        # DT TP: Survivability while building TP
        weights = {
            'store_tp': 5.0,
            'double_attack': 40.0,
            'triple_attack': 60.0,
            'quad_attack': 80.0,
            'gear_haste': 40.0,
            'accuracy': 4.0,
            'attack': 1.0,
            # Defensive stats
            'damage_taken': -50.0,      # Negative = reduction is good
            'physical_dt': -40.0,
            'magical_dt': -30.0,
            'defense': 0.5,
            'VIT': 0.3,
            'magic_evasion': 0.3,
        }
        name = f"DT TP ({job.name})"
        
    elif tp_type == TPSetType.REFRESH_TP:
        # Refresh TP: MP sustain for mage jobs or subjob casting
        weights = {
            'store_tp': 5.0,
            'double_attack': 40.0,
            'triple_attack': 60.0,
            'quad_attack': 80.0,
            'gear_haste': 40.0,
            'accuracy': 3.0,
            'attack': 1.0,
            # MP stats
            'refresh': 100.0,           # Refresh is very valuable
            'MP': 0.5,
            'convert_mp': 50.0,         # MP recovered effects
        }
        name = f"Refresh TP ({job.name})"
    
    else:
        # Default to pure TP
        weights = {
            'store_tp': 10.0,
            'double_attack': 80.0,
            'triple_attack': 120.0,
            'quad_attack': 160.0,
            'gear_haste': 70.0,
            'accuracy': 3.0,
            'attack': 1.0,
        }
        name = f"TP Set ({job.name})"
    
    # Add dual wield weight if applicable
    if is_dual_wield:
        weights['dual_wield'] = 60.0 if tp_type in (TPSetType.PURE_TP, TPSetType.HYBRID_TP) else 40.0
    
    # Set caps
    hard_caps = {'gear_haste': 2500}  # 25% gear haste cap
    
    # DT cap for DT set
    if tp_type == TPSetType.DT_TP:
        hard_caps['damage_taken'] = -5000  # -50% DT cap
        hard_caps['physical_dt'] = -5000
        hard_caps['magical_dt'] = -5000
    
    soft_caps = {}
    if is_dual_wield:
        # With Haste II (30%) + March x2 (16%), need ~11% DW to cap delay
        soft_caps['dual_wield'] = 1100
    
    return OptimizationProfile(
        name=name,
        weights=weights,
        hard_caps=hard_caps,
        soft_caps=soft_caps,
        job=job,
    )


def get_tp_profile_description(tp_type: TPSetType) -> str:
    """Get a description of what a TP set type optimizes for."""
    descriptions = {
        TPSetType.PURE_TP: "Maximum TP gain speed. Prioritizes STP, multi-attack, and haste.",
        TPSetType.HYBRID_TP: "Balance TP speed with TP phase damage. Good all-around set.",
        TPSetType.ACC_TP: "High accuracy for tough content. Trades some TP speed for hit rate.",
        TPSetType.DT_TP: "Survivability focus. Damage reduction + reasonable TP gain.",
        TPSetType.REFRESH_TP: "MP sustain for casting jobs. Refresh + TP building.",
    }
    return descriptions.get(tp_type, "Unknown TP set type")


# =============================================================================
# SIMULATION
# =============================================================================

def simulate_ws(
    gearset: Dict[str, Dict],
    enemy: object,
    ws_name: str,
    ws_data: WeaponskillData,
    tp: int = 2000,
    buffs: Dict = None,
    abilities: Dict = None,
    main_job: str = "war",
    sub_job: str = "sam",
    job_gifts: Optional[JobGifts] = None,
    master_level: int = 50,
) -> Tuple[float, Dict]:
    """Simulate a weaponskill and return damage + stats."""
    if buffs is None:
        buffs = {}
    if abilities is None:
        abilities = {}
    
    player = create_player(
        main_job=main_job,
        sub_job=sub_job,
        master_level=master_level,
        gearset=gearset,
        buffs=buffs,
        abilities=abilities,
    )
    
    # Apply job gifts if provided
    if job_gifts:
        apply_job_gifts_to_player(player, job_gifts)
    
    # Determine WS type for wsdist
    if ws_data.ws_type == WSType.MAGICAL:
        ws_type = "magic"
    elif ws_data.ws_type == WSType.HYBRID:
        ws_type = "hybrid"
    else:
        ws_type = "melee"
    
    damage, _ = average_ws(
        player=player,
        enemy=enemy,
        ws_name=ws_name,
        input_tp=tp,
        ws_type=ws_type,
        input_metric="Damage",
        simulation=False,
    )
    
    return damage, player.stats


def simulate_tp_set(
    gearset: Dict[str, Dict],
    enemy: object,
    main_job: str = "war",
    sub_job: str = "sam",
    ws_threshold: int = 1000,
    starting_tp: int = 0,
    buffs: Dict = None,
    abilities: Dict = None,
    job_gifts: Optional[JobGifts] = None,
    master_level: int = 50,
) -> Dict[str, float]:
    """
    Simulate a TP set and return key metrics.
    
    Args:
        gearset: wsdist-format gearset dict
        enemy: Enemy object from create_enemy
        main_job: Main job
        sub_job: Sub job
        ws_threshold: TP threshold for WS (usually 1000)
        starting_tp: Starting TP value
        buffs: Buff dict
        abilities: Abilities dict
        job_gifts: Optional job gifts to apply
        master_level: Master level (0-50)
    
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
        main_job=main_job,
        sub_job=sub_job,
        master_level=master_level,
        gearset=gearset,
        buffs=buffs,
        abilities=abilities,
    )
    
    # Apply job gifts if provided
    if job_gifts:
        apply_job_gifts_to_player(player, job_gifts)
    
    # Get TP set metrics using "Time to WS" metric
    result = average_attack_round(
        player=player,
        enemy=enemy,
        starting_tp=starting_tp,
        ws_threshold=ws_threshold,
        input_metric="Time to WS",
        simulation=True,
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
# PARALLEL SIMULATION WORKERS (must be at module level for pickling)
# =============================================================================

def _ws_simulation_worker(args: Tuple) -> Tuple[int, float, Any]:
    """Worker function for parallel WS simulation."""
    (idx, gearset, enemy_data, ws_name, ws_type_str, 
     tp, buffs, abilities, main_job, sub_job, job_gifts_dict, master_level) = args
    
    try:
        enemy = create_enemy(enemy_data)
        
        player = create_player(
            main_job=main_job,
            sub_job=sub_job,
            master_level=master_level,
            gearset=gearset,
            buffs=buffs,
            abilities=abilities,
        )
        
        if job_gifts_dict:
            job_gifts = JobGifts(**job_gifts_dict)
            apply_job_gifts_to_player(player, job_gifts)
        
        damage, _ = average_ws(
            player=player,
            enemy=enemy,
            ws_name=ws_name,
            input_tp=tp,
            ws_type=ws_type_str,
            input_metric="Damage",
            simulation=False,
        )
        
        return (idx, damage, None)
        
    except Exception as e:
        return (idx, 0.0, str(e))


def _tp_simulation_worker(args: Tuple) -> Tuple[int, Dict[str, float], Any]:
    """Worker function for parallel TP simulation."""
    (idx, gearset, enemy_data, main_job, sub_job, 
     ws_threshold, buffs, abilities, job_gifts_dict, master_level) = args
    
    try:
        enemy = create_enemy(enemy_data)
        
        player = create_player(
            main_job=main_job,
            sub_job=sub_job,
            master_level=master_level,
            gearset=gearset,
            buffs=buffs,
            abilities=abilities,
        )
        
        if job_gifts_dict:
            job_gifts = JobGifts(**job_gifts_dict)
            apply_job_gifts_to_player(player, job_gifts)
        
        result = average_attack_round(
            player=player,
            enemy=enemy,
            starting_tp=0,
            ws_threshold=ws_threshold,
            input_metric="Time to WS",
            simulation=True,
        )
        
        time_to_ws = result[0]
        damage_per_round = result[1][0]
        tp_per_round = result[1][1]
        time_per_round = result[1][2]
        
        dps = damage_per_round / time_per_round if time_per_round > 0 else 0
        
        metrics = {
            'time_to_ws': time_to_ws,
            'tp_per_round': tp_per_round,
            'damage_per_round': damage_per_round,
            'time_per_round': time_per_round,
            'dps': dps,
        }
        
        return (idx, metrics, None)
        
    except Exception as e:
        return (idx, {}, str(e))


# =============================================================================
# MAIN OPTIMIZATION WORKFLOW
# =============================================================================

def run_ws_optimization(
    inventory: Inventory,
    job: Job,
    main_weapon: Dict[str, Any],
    sub_weapon: Dict[str, Any],
    ws_data: WeaponskillData,
    beam_width: int = 25,
    job_gifts: Optional[JobGifts] = None,
    buffs: Optional[Dict] = None,
    abilities: Optional[Dict] = None,
    target_data: Optional[Dict] = None,
    tp: int = 2000,
    master_level: int = 50,
    sub_job: str = "war",
    parallel: bool = True,
    max_workers: int = None,
) -> List[Tuple[Any, float]]:
    """
    Run the full WS optimization workflow.
    
    Args:
        inventory: Player inventory
        job: Main job enum
        main_weapon: Main weapon data
        sub_weapon: Sub weapon data
        ws_data: Weaponskill data
        beam_width: Beam search width
        job_gifts: Optional job gifts
        buffs: wsdist-format buff dict {"BRD": {"Attack": 280, ...}, ...}
        abilities: Abilities dict {"Berserk": True, ...}
        target_data: Target/enemy data dict
        tp: TP level for WS
        master_level: Master level (0-50)
        parallel: Enable parallel simulation (default True)
        max_workers: Max parallel workers (default: CPU count - 1)
    
    Returns:
        List of (candidate, damage) tuples sorted by damage.
    """
    print("\n" + "-" * 70)
    print("Running Beam Search...")
    print("-" * 70)
    
    # Create optimization profile
    profile = create_ws_profile_from_data(job, ws_data)
    print(f"  Profile: {profile.name}")
    print(f"  Weights: {dict(list(profile.weights.items())[:5])}...")
    
    if job_gifts:
        print(f"  Job Gifts: {job_gifts.job} (JP: {job_gifts.jp_spent})")
    
    if buffs:
        print(f"  Buffs: {list(buffs.keys())}")
    if abilities:
        active = [k for k, v in abilities.items() if v]
        if active:
            print(f"  Abilities: {active}")

    optimizer = NumbaBeamSearchOptimizer(
        inventory=inventory,
        profile=profile,
        beam_width=beam_width,
        job=job,
    )
    
    # Set fixed weapons
    fixed_gear = {
        'main': main_weapon,
        'sub': sub_weapon,
    }
    
    # Run beam search
    contenders = optimizer.search(fixed_gear=fixed_gear)
    item_pool = optimizer.extract_item_pool(contenders=contenders)

    optimizer.print_item_pool(item_pool)
    print(f"\n✓ Found {len(contenders)} contender sets")
    
    if not WSDIST_AVAILABLE:
        print("\n⚠ wsdist not available - showing beam search results only")
        return [(c, c.score) for c in contenders]
    
    # Simulate with wsdist
    print("\n" + "-" * 70)
    print("Simulating with wsdist...")
    print("-" * 70)
    
    # Set up enemy from target_data or use default
    if target_data:
        enemy_data = target_data.copy()
        if "Base Defense" not in enemy_data:
            enemy_data["Base Defense"] = enemy_data.get("Defense", 1550)
    else:
        enemy_data = preset_enemies.get("Apex Toad", {
            "Name": "Apex Toad", "Level": 135,
            "Defense": 1550, "Evasion": 1350,
            "VIT": 350, "AGI": 300,
        }).copy()
        enemy_data["Base Defense"] = enemy_data.get("Defense", 1550)
    
    # Use provided buffs or default
    if buffs is None:
        buffs = {
            "Food": {"STR": 7, "Attack": 150, "Ranged Attack": 150},
            "BRD": {"Attack": 280, "Ranged Attack": 280, "Magic Haste": 0.25,
                    "Accuracy": 50, "Ranged Accuracy": 50},
        }
    
    if abilities is None:
        abilities = {"Berserk": True, "Warcry": True}
    
    # =========================================================================
    # OPTIMIZED SIMULATION SECTION
    # =========================================================================
    
    # Build pre-stripped gear cache from item_pool
    print("  Building stripped gear cache...")
    stripped_cache = build_stripped_gear_cache(item_pool)
    
    # Add fixed weapons to cache (they're not in item_pool)
    for slot in ['main', 'sub']:
        gear = main_weapon if slot == 'main' else sub_weapon
        if gear:
            name2 = gear.get('Name2', gear.get('Name', 'Unknown'))
            stripped = {k: v for k, v in gear.items() if not k.startswith('_')}
            stripped_cache[(slot, name2)] = stripped
    
    # Determine WS type string
    if ws_data.ws_type == WSType.MAGICAL:
        ws_type_str = "magic"
    elif ws_data.ws_type == WSType.HYBRID:
        ws_type_str = "hybrid"
    else:
        ws_type_str = "melee"
    
    # Convert job_gifts to dict for pickling
    job_gifts_dict = None
    if job_gifts:
        job_gifts_dict = {
            'job': job_gifts.job,
            'jp_spent': job_gifts.jp_spent,
            'stats': job_gifts.stats,
        }
    
    # Build all gearsets upfront using cache
    print(f"  Building {len(contenders)} gearsets...")
    gearsets = []
    for candidate in contenders:
        gearset = build_gearset_fast(candidate.gear, stripped_cache, Empty.copy(), WSDIST_SLOTS)
        gearsets.append(gearset)
    
    if parallel and PARALLEL_AVAILABLE and len(contenders) > 1:
        # PARALLEL SIMULATION
        if max_workers is None:
            max_workers = max(1, multiprocessing.cpu_count() - 4)
        
        print(f"  Simulating {len(contenders)} sets with {max_workers} workers...")
        
        work_items = [
            (idx, gearsets[idx], enemy_data, ws_data.name, ws_type_str,
             tp, buffs, abilities, job.name.lower(), sub_job.lower(), 
             job_gifts_dict, master_level)
            for idx in range(len(contenders))
        ]
        
        results = [None] * len(contenders)
        errors = []
        
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_ws_simulation_worker, args): args[0] for args in work_items}
            
            completed = 0
            for future in as_completed(futures):
                idx, damage, error = future.result()
                if error:
                    errors.append(f"Contender #{idx+1}: {error}")
                    results[idx] = (contenders[idx], 0.0)
                else:
                    results[idx] = (contenders[idx], damage)
                
                completed += 1
                # if completed % 5 == 0 or completed == len(contenders):
                #     print(f"    Completed {completed}/{len(contenders)}")
        
        for err in errors:
            print(f"  Error: {err}")
    
    else:
        # SEQUENTIAL SIMULATION (fallback)
        print(f"  Simulating {len(contenders)} sets sequentially...")
        results = []
        enemy = create_enemy(enemy_data)
        
        for i, candidate in enumerate(contenders):
            try:
                damage, _ = simulate_ws(
                    gearset=gearsets[i],
                    enemy=enemy,
                    ws_name=ws_data.name,
                    ws_data=ws_data,
                    tp=tp,
                    buffs=buffs,
                    abilities=abilities,
                    main_job=job.name.lower(),
                    sub_job=sub_job.lower(),
                    job_gifts=job_gifts,
                    master_level=master_level,
                )
                results.append((candidate, damage))
            except Exception as e:
                print(f"  Error simulating contender #{i+1}: {e}")
                results.append((candidate, 0.0))
    
    # Sort by damage
    results.sort(key=lambda x: x[1], reverse=True)
    
    return results


def display_results(results: List[Tuple[Any, float]], ws_name: str):
    """Display optimization results."""
    print("\n" + "=" * 70)
    print(f"OPTIMIZATION RESULTS - {ws_name}")
    print("=" * 70)
    
    for rank, (candidate, damage) in enumerate(results[:5], 1):
        print(f"\n#{rank} - {damage:,.0f} damage")
        print(f"    Beam Score: {candidate.score:.1f}")
        print("    Gear:")
        for slot in ['head', 'body', 'hands', 'legs', 'feet', 'ear1', 'ear2',
                     'ring1', 'ring2', 'waist', 'neck', 'back', 'ammo']:
            if slot in candidate.gear:
                name = candidate.gear[slot].get('Name2',
                       candidate.gear[slot].get('Name', 'Empty'))
                if name != 'Empty':
                    print(f"      {slot:8s}: {name}")
    
    if len(results) >= 2:
        best = results[0][1]
        worst = results[-1][1]
        print(f"\n  Best: {best:,.0f}  |  Worst: {worst:,.0f}  |  Range: {best-worst:,.0f} ({(best/worst-1)*100:.1f}%)")


def run_tp_optimization(
    inventory: Inventory,
    job: Job,
    main_weapon: Dict[str, Any],
    sub_weapon: Dict[str, Any],
    tp_type: TPSetType = TPSetType.PURE_TP,
    beam_width: int = 25,
    job_gifts: Optional[JobGifts] = None,
    buffs: Optional[Dict] = None,
    abilities: Optional[Dict] = None,
    target_data: Optional[Dict] = None,
    master_level: int = 50,
    sub_job: str = "war",
    parallel: bool = True,
    max_workers: int = None,
) -> List[Tuple[Any, Dict]]:
    """
    Run the full TP optimization workflow.
    
    Args:
        inventory: Player inventory
        job: Main job enum
        main_weapon: Main weapon data
        sub_weapon: Sub weapon data
        tp_type: TP set type/priority
        beam_width: Beam search width
        job_gifts: Optional job gifts
        buffs: wsdist-format buff dict {"BRD": {"Attack": 280, ...}, ...}
        abilities: Abilities dict {"Berserk": True, ...}
        target_data: Target/enemy data dict
        master_level: Master level (0-50)
        parallel: Enable parallel simulation (default True)
        max_workers: Max parallel workers (default: CPU count - 1)
    
    Returns:
        List of (candidate, metrics_dict) tuples sorted by time_to_ws.
    """
    # Check if dual wielding
    is_dual_wield = (sub_weapon.get("Type") == "Weapon" and 
                     sub_weapon.get("Name") != "Empty")
    
    print("\n" + "-" * 70)
    print("Running Beam Search for TP Set...")
    print("-" * 70)
    
    # Create optimization profile
    profile = create_tp_profile(job, tp_type, is_dual_wield)
    print(f"  Profile: {profile.name}")
    print(f"  Description: {get_tp_profile_description(tp_type)}")
    print(f"  Dual Wield: {'Yes' if is_dual_wield else 'No'}")
    
    if job_gifts:
        print(f"  Job Gifts: {job_gifts.job} (JP: {job_gifts.jp_spent})")
    
    if buffs:
        print(f"  Buffs: {list(buffs.keys())}")
    if abilities:
        active = [k for k, v in abilities.items() if v]
        if active:
            print(f"  Abilities: {active}")
    
    optimizer = NumbaBeamSearchOptimizer(
        inventory=inventory,
        profile=profile,
        beam_width=beam_width,
        job=job,
    )
    
    # Set fixed weapons
    fixed_gear = {
        'main': main_weapon,
        'sub': sub_weapon,
    }
    
    # Run beam search
    contenders = optimizer.search(fixed_gear=fixed_gear)
    item_pool = optimizer.extract_item_pool(contenders=contenders)

    optimizer.print_item_pool(item_pool)
    print(f"\n✓ Found {len(contenders)} contender sets")
    
    if not WSDIST_AVAILABLE:
        print("\n⚠ wsdist not available - showing beam search results only")
        return [(c, {'time_to_ws': 0, 'tp_per_round': 0, 'dps': 0, 'score': c.score}) 
                for c in contenders]
    
    # Simulate with wsdist
    print("\n" + "-" * 70)
    print("Simulating with wsdist...")
    print("-" * 70)
    
    # Set up enemy from target_data or use default
    if target_data:
        enemy_data = target_data.copy()
        if "Base Defense" not in enemy_data:
            enemy_data["Base Defense"] = enemy_data.get("Defense", 1550)
    else:
        enemy_data = preset_enemies.get("Apex Toad", {
            "Name": "Apex Toad", "Level": 135,
            "Defense": 1550, "Evasion": 1350,
            "VIT": 350, "AGI": 300,
        }).copy()
        enemy_data["Base Defense"] = enemy_data.get("Defense", 1550)
    
    # Use provided buffs or default
    if buffs is None:
        buffs = {
            "Food": {"STR": 7, "Attack": 150, "Ranged Attack": 150, "Accuracy": 50},
            "BRD": {"Attack": 280, "Ranged Attack": 280, "Magic Haste": 0.25,
                    "Accuracy": 50, "Ranged Accuracy": 50},
            "GEO": {"Attack": 300, "Accuracy": 40},
        }
    
    if abilities is None:
        abilities = {"Berserk": True, "Aggressor": True}
    
    # =========================================================================
    # OPTIMIZED SIMULATION SECTION
    # =========================================================================
    
    # Build pre-stripped gear cache from item_pool
    print("  Building stripped gear cache...")
    stripped_cache = build_stripped_gear_cache(item_pool)
    
    # Add fixed weapons to cache
    for slot in ['main', 'sub']:
        gear = main_weapon if slot == 'main' else sub_weapon
        if gear:
            name2 = gear.get('Name2', gear.get('Name', 'Unknown'))
            stripped = {k: v for k, v in gear.items() if not k.startswith('_')}
            stripped_cache[(slot, name2)] = stripped
    
    # Convert job_gifts to dict for pickling
    job_gifts_dict = None
    if job_gifts:
        job_gifts_dict = {
            'job': job_gifts.job,
            'jp_spent': job_gifts.jp_spent,
            'stats': job_gifts.stats,
        }
    
    # Build all gearsets upfront using cache
    print(f"  Building {len(contenders)} gearsets...")
    gearsets = []
    for candidate in contenders:
        gearset = build_gearset_fast(candidate.gear, stripped_cache, Empty.copy(), WSDIST_SLOTS)
        gearsets.append(gearset)
    
    if parallel and PARALLEL_AVAILABLE and len(contenders) > 1:
        # PARALLEL SIMULATION
        if max_workers is None:
            max_workers = max(1, multiprocessing.cpu_count() - 4)
        
        print(f"  Simulating {len(contenders)} sets with {max_workers} workers...")
        
        work_items = [
            (idx, gearsets[idx], enemy_data, job.name.lower(), sub_job.lower(),
             1000, buffs, abilities, job_gifts_dict, master_level)
            for idx in range(len(contenders))
        ]
        
        results = [None] * len(contenders)
        errors = []
        
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_tp_simulation_worker, args): args[0] for args in work_items}
            
            completed = 0
            for future in as_completed(futures):
                idx, metrics, error = future.result()
                if error:
                    errors.append(f"Contender #{idx+1}: {error}")
                    metrics = {'time_to_ws': float('inf'), 'tp_per_round': 0, 
                               'dps': 0, 'damage_per_round': 0, 'time_per_round': 0}
                
                metrics['score'] = contenders[idx].score
                results[idx] = (contenders[idx], metrics)
                
                completed += 1
                # if completed % 5 == 0 or completed == len(contenders):
                #     print(f"    Completed {completed}/{len(contenders)}")
        
        for err in errors:
            print(f"  Error: {err}")
    
    else:
        # SEQUENTIAL SIMULATION (fallback)
        print(f"  Simulating {len(contenders)} sets sequentially...")
        results = []
        enemy = create_enemy(enemy_data)
        
        for i, candidate in enumerate(contenders):
            try:
                metrics = simulate_tp_set(
                    gearset=gearsets[i],
                    enemy=enemy,
                    main_job=job.name.lower(),
                    sub_job=sub_job.lower(),
                    ws_threshold=1000,
                    buffs=buffs,
                    abilities=abilities,
                    job_gifts=job_gifts,
                    master_level=master_level,
                )
                metrics['score'] = candidate.score
                results.append((candidate, metrics))
            except Exception as e:
                print(f"  Error simulating contender #{i+1}: {e}")
                results.append((candidate, {'time_to_ws': float('inf'), 'tp_per_round': 0, 
                                            'dps': 0, 'score': candidate.score}))
    
    # Sort by time_to_ws (lower is better)
    results.sort(key=lambda x: x[1]['time_to_ws'])
    
    return results


def display_tp_results(results: List[Tuple[Any, Dict]], tp_type: TPSetType):
    """Display TP optimization results."""
    print("\n" + "=" * 70)
    print(f"TP OPTIMIZATION RESULTS - {tp_type.value}")
    print("=" * 70)
    
    for rank, (candidate, metrics) in enumerate(results[:5], 1):
        time_to_ws = metrics['time_to_ws']
        tp_per_round = metrics['tp_per_round']
        dps = metrics['dps']
        ws_per_min = 60.0 / time_to_ws if time_to_ws > 0 else 0
        
        print(f"\n#{rank} - {time_to_ws:.2f}s to WS ({ws_per_min:.2f} WS/min)")
        print(f"    TP/Round: {tp_per_round:.1f}")
        print(f"    TP Phase DPS: {dps:.0f}")
        print(f"    Beam Score: {metrics.get('score', 0):.1f}")
        print("    Gear:")
        for slot in ['head', 'body', 'hands', 'legs', 'feet', 'ear1', 'ear2',
                     'ring1', 'ring2', 'waist', 'neck', 'back', 'ammo']:
            if slot in candidate.gear:
                name = candidate.gear[slot].get('Name2',
                       candidate.gear[slot].get('Name', 'Empty'))
                if name != 'Empty':
                    print(f"      {slot:8s}: {name}")
    
    if len(results) >= 2:
        fastest = results[0][1]['time_to_ws']
        slowest = results[-1][1]['time_to_ws']
        diff = slowest - fastest
        diff_pct = (slowest / fastest - 1) * 100 if fastest > 0 else 0
        print(f"\n  Fastest: {fastest:.2f}s  |  Slowest: {slowest:.2f}s  |  Diff: {diff:.2f}s ({diff_pct:.1f}%)")


# =============================================================================
# MAIN UI LOOP
# =============================================================================

class OptimizerUI:
    """Main UI class for the gear optimizer."""
    
    def __init__(self, inventory_path: str, job_gifts_path: str = None):
        self.inventory_path = inventory_path
        self.job_gifts_path = job_gifts_path
        self.inventory: Optional[Inventory] = None
        self.job_gifts_collection: Optional[JobGiftsCollection] = None
        self.selected_job: Optional[Job] = None
        self.main_weapon: Optional[Dict] = None
        self.sub_weapon: Optional[Dict] = None
        self.selected_ws: Optional[WeaponskillData] = None
    
    def load_inventory(self) -> bool:
        """Load the inventory file."""
        try:
            print(f"\nLoading inventory from {self.inventory_path}...")
            self.inventory = load_inventory(self.inventory_path)
            print(f"✓ Loaded {len(self.inventory.items)} items")
            
            # Try to load job gifts
            self._load_job_gifts()
            
            return True
        except FileNotFoundError:
            print(f"✗ File not found: {self.inventory_path}")
            return False
        except Exception as e:
            print(f"✗ Error loading inventory: {e}")
            return False
    
    def _load_job_gifts(self):
        """Try to load job gifts from CSV."""
        # Try explicit path first
        if self.job_gifts_path:
            try:
                self.job_gifts_collection = load_job_gifts(self.job_gifts_path)
                jobs_with_jp = sum(1 for jg in self.job_gifts_collection.gifts.values() 
                                   if jg.jp_spent > 0)
                print(f"✓ Loaded job gifts ({jobs_with_jp} jobs with JP)")
                return
            except Exception as e:
                print(f"⚠ Could not load job gifts from {self.job_gifts_path}: {e}")
        
        # Try to find job gifts file based on inventory filename
        inv_path = Path(self.inventory_path)
        possible_names = [
            inv_path.parent / f"jobgifts_{inv_path.stem.replace('inventory_full_', '')}.csv",
            inv_path.parent / inv_path.name.replace("inventory_full_", "jobgifts_"),
            inv_path.parent / "jobgifts.csv",
        ]
        
        for path in possible_names:
            if path.exists():
                try:
                    self.job_gifts_collection = load_job_gifts(str(path))
                    jobs_with_jp = sum(1 for jg in self.job_gifts_collection.gifts.values() 
                                       if jg.jp_spent > 0)
                    print(f"✓ Loaded job gifts from {path.name} ({jobs_with_jp} jobs with JP)")
                    return
                except Exception as e:
                    print(f"⚠ Could not load job gifts from {path}: {e}")
        
        print("ℹ No job gifts file found (using wsdist defaults)")
    
    def get_current_job_gifts(self) -> Optional[JobGifts]:
        """Get job gifts for the currently selected job."""
        if not self.job_gifts_collection or not self.selected_job:
            return None
        return self.job_gifts_collection.get_job(self.selected_job.name)
    
    def select_job(self) -> bool:
        """Job selection menu."""
        # Format jobs in a nice grid
        options = []
        for i, job in enumerate(JOB_LIST):
            options.append(job)
        
        idx = print_menu("SELECT JOB", options)
        if idx < 0:
            return False
        
        job_name = JOB_LIST[idx]
        self.selected_job = JOB_ENUM_MAP[job_name]
        print(f"\n✓ Selected: {job_name}")
        return True
    
    def select_main_weapon(self) -> bool:
        """Main weapon selection menu."""
        if not self.selected_job:
            print("Please select a job first")
            return False
        
        weapons = get_weapons_from_inventory(self.inventory, self.selected_job)
        
        if not weapons:
            print(f"\n✗ No weapons found for {self.selected_job.name}")
            return False
        
        # Sort by name for easier browsing
        weapons.sort(key=lambda w: w.get("Name2", w.get("Name", "")))
        
        # Create options with weapon info
        options = []
        for w in weapons:
            name = w.get("Name2", w.get("Name", "Unknown"))
            skill = w.get("Skill Type", "?")
            dmg = w.get("DMG", 0)
            delay = w.get("Delay", 0)
            options.append(f"{name} ({skill}, D:{dmg} Dly:{delay})")
        
        idx = print_menu(f"SELECT MAIN WEAPON ({self.selected_job.name})", options)
        if idx < 0:
            return False
        
        self.main_weapon = weapons[idx]
        print(f"\n✓ Selected: {self.main_weapon.get('Name2', self.main_weapon.get('Name'))}")
        return True
    
    def select_sub_weapon(self) -> bool:
        """Off-hand selection menu."""
        if not self.selected_job or not self.main_weapon:
            print("Please select job and main weapon first")
            return False
        
        offhands = get_offhand_from_inventory(self.inventory, self.selected_job, self.main_weapon)
        
        # Add "Empty" option
        empty_option = {"Name": "Empty", "Name2": "Empty", "Type": "None", "Jobs": all_jobs}
        offhands.insert(0, empty_option)
        
        # Sort (after empty)
        offhands[1:] = sorted(offhands[1:], key=lambda w: w.get("Name2", w.get("Name", "")))
        
        # Create options
        options = []
        for w in offhands:
            name = w.get("Name2", w.get("Name", "Unknown"))
            item_type = w.get("Type", "?")
            if item_type == "Weapon":
                skill = w.get("Skill Type", "?")
                dmg = w.get("DMG", 0)
                options.append(f"{name} ({skill}, D:{dmg})")
            elif item_type == "Shield":
                options.append(f"{name} (Shield)")
            elif item_type == "Grip":
                options.append(f"{name} (Grip)")
            else:
                options.append(name)
        
        idx = print_menu(f"SELECT OFF-HAND ({self.selected_job.name})", options)
        if idx < 0:
            return False
        
        self.sub_weapon = offhands[idx]
        print(f"\n✓ Selected: {self.sub_weapon.get('Name2', self.sub_weapon.get('Name'))}")
        return True
    
    def select_weaponskill(self) -> bool:
        """Weaponskill selection menu."""
        if not self.main_weapon:
            print("Please select a main weapon first")
            return False
        
        ws_list = get_weaponskills_for_weapon(self.main_weapon)
        
        if not ws_list:
            skill_type = self.main_weapon.get("Skill Type", "Unknown")
            print(f"\n✗ No weaponskills found for {skill_type}")
            return False
        
        # Sort by name
        ws_list.sort(key=lambda ws: ws.name)
        
        # Create options with WS info
        options = []
        for ws in ws_list:
            mod_str = "/".join(f"{s}:{v}" for s, v in ws.stat_modifiers.items())
            ws_type = ws.ws_type.value
            hits = f"{ws.hits}hit" if ws.hits > 1 else "1hit"
            options.append(f"{ws.name} ({ws_type}, {hits}, {mod_str})")
        
        idx = print_menu(f"SELECT WEAPONSKILL ({self.main_weapon.get('Skill Type')})", options)
        if idx < 0:
            return False
        
        self.selected_ws = ws_list[idx]
        print(f"\n✓ Selected: {self.selected_ws.name}")
        return True
    
    def run_optimization(self):
        """Run the optimization with current selections."""
        if not all([self.selected_job, self.main_weapon, self.sub_weapon, self.selected_ws]):
            print("\n✗ Please complete all selections first")
            return
        
        # Get job gifts for current job
        job_gifts = self.get_current_job_gifts()
        
        print("\n" + "=" * 70)
        print("RUNNING OPTIMIZATION")
        print("=" * 70)
        print(f"  Job: {self.selected_job.name}")
        print(f"  Main: {self.main_weapon.get('Name2', self.main_weapon.get('Name'))}")
        print(f"  Sub: {self.sub_weapon.get('Name2', self.sub_weapon.get('Name'))}")
        print(f"  WS: {self.selected_ws.name}")
        if job_gifts:
            print(f"  Job Points: {job_gifts.jp_spent}")
        
        results = run_ws_optimization(
            inventory=self.inventory,
            job=self.selected_job,
            main_weapon=self.main_weapon,
            sub_weapon=self.sub_weapon,
            ws_data=self.selected_ws,
            beam_width=25,
            job_gifts=job_gifts,
        )
        
        display_results(results, self.selected_ws.name)
        
        input("\nPress Enter to continue...")
    
    def show_current_selection(self):
        """Display current selections."""
        print("\n--- Current Selection ---")
        job_str = self.selected_job.name if self.selected_job else '(not selected)'
        if self.selected_job:
            job_gifts = self.get_current_job_gifts()
            if job_gifts and job_gifts.jp_spent > 0:
                job_str += f" (JP: {job_gifts.jp_spent})"
        print(f"  Job:    {job_str}")
        print(f"  Main:   {self.main_weapon.get('Name2', 'not selected') if self.main_weapon else '(not selected)'}")
        print(f"  Sub:    {self.sub_weapon.get('Name2', 'not selected') if self.sub_weapon else '(not selected)'}")
        print(f"  WS:     {self.selected_ws.name if self.selected_ws else '(not selected)'}")
    
    def select_tp_type(self) -> Optional[TPSetType]:
        """TP set type selection menu."""
        options = []
        tp_types = list(TPSetType)
        
        for tp_type in tp_types:
            desc = get_tp_profile_description(tp_type)
            options.append(f"{tp_type.value}\n         {desc}")
        
        print_header("SELECT TP SET TYPE")
        print()
        for i, option in enumerate(options, 1):
            print(f"  {i:3d}. {option}")
        print(f"\n    0. Back / Cancel")
        print()
        
        while True:
            try:
                choice = input("Enter choice: ").strip()
                if choice == "0" or choice.lower() in ("q", "quit", "back", "b"):
                    return None
                
                idx = int(choice) - 1
                if 0 <= idx < len(tp_types):
                    return tp_types[idx]
                else:
                    print(f"Please enter a number between 1 and {len(tp_types)}")
            except ValueError:
                print("Please enter a valid number")
    
    def run_tp_optimization_menu(self):
        """Run TP optimization with type selection."""
        if not all([self.selected_job, self.main_weapon, self.sub_weapon]):
            print("\n✗ Please select Job, Main Weapon, and Off-Hand first")
            input("Press Enter to continue...")
            return
        
        # Select TP set type
        tp_type = self.select_tp_type()
        if tp_type is None:
            return
        
        # Get job gifts for current job
        job_gifts = self.get_current_job_gifts()
        
        # Check if dual wielding
        is_dual_wield = (self.sub_weapon.get("Type") == "Weapon" and 
                         self.sub_weapon.get("Name") != "Empty")
        
        print("\n" + "=" * 70)
        print("RUNNING TP OPTIMIZATION")
        print("=" * 70)
        print(f"  Job: {self.selected_job.name}")
        print(f"  Main: {self.main_weapon.get('Name2', self.main_weapon.get('Name'))}")
        print(f"  Sub: {self.sub_weapon.get('Name2', self.sub_weapon.get('Name'))}")
        print(f"  Set Type: {tp_type.value}")
        print(f"  Dual Wield: {'Yes' if is_dual_wield else 'No'}")
        if job_gifts:
            print(f"  Job Points: {job_gifts.jp_spent}")
        
        results = run_tp_optimization(
            inventory=self.inventory,
            job=self.selected_job,
            main_weapon=self.main_weapon,
            sub_weapon=self.sub_weapon,
            tp_type=tp_type,
            beam_width=25,
            job_gifts=job_gifts,
        )
        
        display_tp_results(results, tp_type)
        
        input("\nPress Enter to continue...")
    
    def main_menu(self):
        """Main menu loop."""
        while True:
            self.show_current_selection()
            
            options = [
                "Select Job",
                "Select Main Weapon",
                "Select Off-Hand",
                "Select Weaponskill",
                "Run WS Optimization",
                "Run TP Optimization",
                "Quit"
            ]
            
            # Check what we can do
            has_weapons = all([self.selected_job, self.main_weapon, self.sub_weapon])
            can_ws_optimize = has_weapons and self.selected_ws is not None
            
            idx = print_menu("GEAR SET OPTIMIZER", options, show_back=False)
            
            if idx == 0:  # Select Job
                if self.select_job():
                    # Reset dependent selections
                    self.main_weapon = None
                    self.sub_weapon = None
                    self.selected_ws = None
            
            elif idx == 1:  # Select Main Weapon
                if not self.selected_job:
                    print("\n⚠ Please select a job first")
                    input("Press Enter to continue...")
                else:
                    if self.select_main_weapon():
                        # Reset dependent selections
                        self.sub_weapon = None
                        self.selected_ws = None
            
            elif idx == 2:  # Select Off-Hand
                if not self.main_weapon:
                    print("\n⚠ Please select a main weapon first")
                    input("Press Enter to continue...")
                else:
                    self.select_sub_weapon()
            
            elif idx == 3:  # Select Weaponskill
                if not self.main_weapon:
                    print("\n⚠ Please select a main weapon first")
                    input("Press Enter to continue...")
                else:
                    self.select_weaponskill()
            
            elif idx == 4:  # Run WS Optimization
                if not can_ws_optimize:
                    print("\n⚠ Please complete all selections (including Weaponskill) first")
                    input("Press Enter to continue...")
                else:
                    self.run_optimization()
            
            elif idx == 5:  # TP Optimization
                if not has_weapons:
                    print("\n⚠ Please select Job, Main Weapon, and Off-Hand first")
                    input("Press Enter to continue...")
                else:
                    self.run_tp_optimization_menu()
            
            elif idx == 6 or idx == -1:  # Quit
                print("\nGoodbye!")
                break
    
    def run(self):
        """Main entry point."""
        print_header("GEAR SET OPTIMIZER")
        print(f"\n  Inventory: {self.inventory_path}")
        print(f"  wsdist: {'Available' if WSDIST_AVAILABLE else 'Not Available'}")
        
        if not self.load_inventory():
            return
        
        self.main_menu()


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    # Default inventory path
    default_path = "inventory_full_Masinmanci_20260111_124357.csv"
    
    if len(sys.argv) > 1:
        inventory_path = sys.argv[1]
    else:
        inventory_path = default_path
    
    ui = OptimizerUI(inventory_path)
    ui.run()


if __name__ == "__main__":
    main()
