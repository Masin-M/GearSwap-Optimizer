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
import traceback as _traceback
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

# =============================================================================
# FROZEN EXECUTABLE DETECTION
# =============================================================================
# PyInstaller + Windows + ProcessPoolExecutor requires freeze_support() to be
# called at the very start of the entry point (launcher.py).
# With freeze_support() in place, parallel processing should work.

def _is_frozen():
    """Check if running as a frozen PyInstaller executable."""
    return getattr(sys, 'frozen', False)

def _is_frozen_windows():
    """Check if running as a frozen PyInstaller exe on Windows."""
    return _is_frozen() and sys.platform == 'win32'

def _test_multiprocessing():
    """
    Test if multiprocessing actually works in the current environment.
    Returns True if a simple multiprocessing task succeeds.
    """
    try:
        import multiprocessing
        # Use spawn method explicitly on Windows for frozen executables
        if _is_frozen_windows():
            try:
                multiprocessing.set_start_method('spawn', force=True)
            except RuntimeError:
                pass  # Already set
        
        # Quick test: can we create a pool and run a simple task?
        def _test_worker(x):
            return x * 2
        
        with multiprocessing.Pool(1) as pool:
            result = pool.map(_test_worker, [1])
            return result == [2]
    except Exception as e:
        print(f"Multiprocessing test failed: {e}")
        return False

# Test multiprocessing availability at import time
# With freeze_support() properly configured in launcher.py, this should work
if _is_frozen_windows():
    # For frozen Windows executables, test if multiprocessing actually works
    PARALLEL_AVAILABLE = _test_multiprocessing()
    if not PARALLEL_AVAILABLE:
        print("Warning: Multiprocessing not available in frozen executable. "
              "Falling back to single-threaded mode.")
else:
    # For non-frozen or non-Windows, parallel should always work
    PARALLEL_AVAILABLE = True

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


def _apply_tp_bonus_slot_rules(
    main_weapon:   Optional[Dict[str, Any]],
    sub_weapon:    Optional[Dict[str, Any]],
    ranged_weapon: Optional[Dict[str, Any]],
    ammo:          Optional[Dict[str, Any]],
    is_ranged_ws:  bool,
) -> Tuple[
    Optional[Dict[str, Any]],
    Optional[Dict[str, Any]],
    Optional[Dict[str, Any]],
    Optional[Dict[str, Any]],
]:
    """
    Enforce FFXI's TP Bonus slot rules for weapons and ammo before optimization.

    TP Bonus on a weapon has two distinct sources with different applicability:

    - Base / innate (white text, e.g. Heishi Shorinken, Aeonic weapons):
        Only applies when that specific weapon is the one executing the WS.
        Melee WS  -> only the MAIN-hand weapon's base TP Bonus counts.
        Ranged WS -> only the RANGED-slot weapon's base TP Bonus counts.
        SUB and AMMO slots never contribute base TP Bonus.

    - Augmented (yellow text, e.g. Magian TP Bonus weapon):
        Acts as a global buff — applies to ALL weaponskills regardless of slot.
        Detected by the presence of a string containing "TP Bonus" in the
        item's _augments list.

    Path augments ("Path: A" in _augments) merge their stats globally via
    to_wsdist_gear(), so path-granted TP Bonus is treated as base here
    (no "TP Bonus" string appears in _augments for path items). This is the
    correct conservative default — no currently-known path augment grants
    TP Bonus.

    Args:
        main_weapon:   Main-hand weapon dict (may contain _augments).
        sub_weapon:    Sub / off-hand weapon dict.
        ranged_weapon: Ranged-slot weapon dict (bow / gun).
        ammo:          Ammo-slot dict (arrow / bolt / bullet).
        is_ranged_ws:  True for Archery / Marksmanship weaponskills.

    Returns:
        (main_weapon, sub_weapon, ranged_weapon, ammo) — originals returned
        unchanged when no correction is needed; a shallow copy with
        "TP Bonus" set to 0 is returned for any slot that would incorrectly
        contribute base TP Bonus.
    """

    def _has_augmented_tp_bonus(item: Dict[str, Any]) -> bool:
        """Return True if any augment string on this item grants TP Bonus."""
        for aug in item.get('_augments') or []:
            if isinstance(aug, str) and 'TP Bonus' in aug:
                return True
        return False

    def _zero_base_tp_bonus(item: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        If the item has a non-zero base TP Bonus (not from an augment),
        return a shallow copy with TP Bonus zeroed out. Otherwise return
        the original unchanged.
        """
        if item is None:
            return None
        if not item.get('TP Bonus'):
            return item
        if _has_augmented_tp_bonus(item):
            # Augmented TP Bonus is global — leave it alone.
            return item
        # Base TP Bonus in an invalid slot — zero it on a copy.
        corrected = dict(item)
        corrected['TP Bonus'] = 0
        name = item.get('Name2', item.get('Name', '?'))
        print(f"  [TP Bonus] Zeroing base TP Bonus on '{name}' (invalid slot for this WS type)")
        return corrected

    if is_ranged_ws:
        # Ranged WS: only the ranged slot carries base TP Bonus.
        return (
            _zero_base_tp_bonus(main_weapon),
            _zero_base_tp_bonus(sub_weapon),
            ranged_weapon,                     # valid slot — untouched
            _zero_base_tp_bonus(ammo),
        )
    else:
        # Melee / hybrid / magical WS: only the main slot carries base TP Bonus.
        return (
            main_weapon,                       # valid slot — untouched
            _zero_base_tp_bonus(sub_weapon),
            _zero_base_tp_bonus(ranged_weapon),
            _zero_base_tp_bonus(ammo),
        )


def apply_custom_buffs_to_player(player: Any, custom_buffs: Optional[Dict[str, Any]]) -> None:
    """
    Apply custom buff stats directly to a player object.
    
    This is similar to apply_job_gifts_to_player but for user-entered custom buffs.
    Since wsdist's create_player doesn't understand a "Custom" buff source,
    we apply these stats after player creation.
    
    Args:
        player: Player object from create_player()
        custom_buffs: Dict with stats like:
            - STR, DEX, VIT, AGI (primary stats)
            - attack, ranged_attack (flat attack bonuses)
            - attack_pct (attack multiplier, e.g., 31.25 for 31.25%)
            - accuracy, ranged_accuracy
            - magic_haste (percentage, e.g., 30 for 30%)
            - store_tp
            - double_attack, triple_attack
            - crit_rate
            - pdl (physical damage limit)
    """
    if not custom_buffs:
        return
    
    # Primary stats
    if custom_buffs.get("STR", 0):
        player.stats["STR"] = player.stats.get("STR", 0) + custom_buffs["STR"]
    if custom_buffs.get("DEX", 0):
        player.stats["DEX"] = player.stats.get("DEX", 0) + custom_buffs["DEX"]
    if custom_buffs.get("VIT", 0):
        player.stats["VIT"] = player.stats.get("VIT", 0) + custom_buffs["VIT"]
    if custom_buffs.get("AGI", 0):
        player.stats["AGI"] = player.stats.get("AGI", 0) + custom_buffs["AGI"]
    
    # Attack stats
    if custom_buffs.get("attack", 0):
        player.stats["Attack"] = player.stats.get("Attack", 0) + custom_buffs["attack"]
        # Also add to base attack for proper calculation
        player.stats["Attack1"] = player.stats.get("Attack1", 0) + custom_buffs["attack"]
    if custom_buffs.get("ranged_attack", 0):
        player.stats["Ranged Attack"] = player.stats.get("Ranged Attack", 0) + custom_buffs["ranged_attack"]
    
    # Attack% multiplier - must apply directly to Attack1/Attack2 since 
    # create_player.finalize_stats() has already run and applied any existing Attack%
    # Setting Attack% after player creation has no effect on damage calculations.
    if custom_buffs.get("attack_pct", 0):
        raw_value = custom_buffs["attack_pct"]
        # Convert from percentage (23) to decimal (0.23)
        attack_pct_decimal = raw_value / 100.0
        
        # Apply attack% bonus to Attack1 (main hand)
        base_attack1 = player.stats.get("Attack1", 0)
        if base_attack1:
            attack_bonus1 = int(base_attack1 * attack_pct_decimal)
            player.stats["Attack1"] = base_attack1 + attack_bonus1
            print(f"[DEBUG] attack_pct: raw={raw_value}%, Attack1: {base_attack1} + {attack_bonus1} = {player.stats['Attack1']}")
        
        # Apply attack% bonus to Attack2 (off-hand) if dual wielding
        base_attack2 = player.stats.get("Attack2", 0)
        if base_attack2:
            attack_bonus2 = int(base_attack2 * attack_pct_decimal)
            player.stats["Attack2"] = base_attack2 + attack_bonus2
            print(f"[DEBUG] attack_pct: Attack2: {base_attack2} + {attack_bonus2} = {player.stats['Attack2']}")
        
        # Also update Attack% for display/reference purposes
        current_attack_pct = player.stats.get("Attack%", 0) or 0
        player.stats["Attack%"] = current_attack_pct + attack_pct_decimal 
    
    # Accuracy stats
    if custom_buffs.get("accuracy", 0):
        player.stats["Accuracy"] = player.stats.get("Accuracy", 0) + custom_buffs["accuracy"]
        player.stats["Accuracy1"] = player.stats.get("Accuracy1", 0) + custom_buffs["accuracy"]
    if custom_buffs.get("ranged_accuracy", 0):
        player.stats["Ranged Accuracy"] = player.stats.get("Ranged Accuracy", 0) + custom_buffs["ranged_accuracy"]
    
    # Magic Haste - wsdist uses fractional representation
    if custom_buffs.get("magic_haste", 0):
        # Convert from percentage (30) to fraction (0.30)
        haste_fraction = custom_buffs["magic_haste"] / 100.0
        player.stats["Magic Haste"] = player.stats.get("Magic Haste", 0) + haste_fraction
    
    # TP stats
    if custom_buffs.get("store_tp", 0):
        player.stats["Store TP"] = player.stats.get("Store TP", 0) + custom_buffs["store_tp"]
    
    # Multi-attack
    if custom_buffs.get("double_attack", 0):
        player.stats["DA"] = player.stats.get("DA", 0) + custom_buffs["double_attack"]
    if custom_buffs.get("triple_attack", 0):
        player.stats["TA"] = player.stats.get("TA", 0) + custom_buffs["triple_attack"]
    
    # Critical stats
    if custom_buffs.get("crit_rate", 0):
        player.stats["Crit Rate"] = player.stats.get("Crit Rate", 0) + custom_buffs["crit_rate"]
    
    # Physical Damage Limit
    if custom_buffs.get("pdl", 0):
        player.stats["PDL"] = player.stats.get("PDL", 0) + custom_buffs["pdl"]


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
    BALANCED_DT = "Balanced DT (Equal Offense + Defense)"
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


def get_ranged_weapons_from_inventory(inventory: Inventory, job: Job) -> List[Dict[str, Any]]:
    """Get all ranged weapons (bows, guns, crossbows) from inventory that the job can equip."""
    from models import SLOT_BITMASK
    
    weapons = []
    range_mask = SLOT_BITMASK.get(Slot.RANGE, 0)
    
    for item in inventory.items:
        # Check if it's equippable in range slot
        if not (item.base.slots & range_mask):
            continue
        
        # Check if job can equip
        if not item.base.can_equip(job):
            continue
        
        # Convert to wsdist format
        wsdist_item = to_wsdist_gear(item)
        if wsdist_item and wsdist_item.get("Type") in ("Bow", "Gun", "Crossbow"):
            weapons.append(wsdist_item)
    
    return weapons


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

RANGED_SKILL_TYPES = frozenset({"Archery", "Marksmanship"})


def is_ranged_weaponskill(ws_data: WeaponskillData) -> bool:
    """Return True if this WS fires from the ranged slot (Archery / Marksmanship)."""
    return getattr(ws_data, 'skill_type', None) in RANGED_SKILL_TYPES or \
           getattr(ws_data, 'weapon_type', None) in (WeaponType.ARCHERY, WeaponType.MARKSMANSHIP)


def create_ws_profile_from_data(job: Job, ws_data: WeaponskillData) -> OptimizationProfile:
    """Create an optimization profile from weaponskill data."""
    
    # Get base weights from WS data
    weights = ws_data.get_stat_weights()
    print(weights)

    is_ranged = is_ranged_weaponskill(ws_data)

    # Scale weights for our basis point system
    scaled_weights = {}
    for stat, weight in weights.items():
        # Convert stat names to match our system
        stat_lower = stat.lower()
        if stat_lower in ('str', 'dex', 'vit', 'agi', 'int', 'mnd', 'chr'):
            scaled_weights[stat.upper()] = weight
        elif stat_lower == 'attack':
            # Ranged WS uses Ranged Attack, not melee Attack
            scaled_weights['ranged_attack' if is_ranged else 'attack'] = weight
        elif stat_lower == 'accuracy':
            # Ranged WS accuracy comes from Ranged Accuracy, not melee Accuracy
            scaled_weights['ranged_accuracy' if is_ranged else 'accuracy'] = weight
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
        elif stat_lower == 'tp_bonus':
            # TP Bonus is valued by how much it moves fTP at the 1000 TP tier.
            # +N TP Bonus at 1000 TP → fires as (1000+N) TP, gaining
            #   (ftp[1]-ftp[0]) * N/1000  extra fTP above base ftp[0].
            # That gain as a % of base fTP = gain/ftp[0]*100, directly comparable
            # to WSD%.  We calibrate the weight so that scoring 1 raw unit of
            # tp_bonus equals the same score as an equivalent WSD% improvement,
            # using the already-scaled ws_damage weight (raw_ws_damage_wt * 20).
            #
            # Formula: tp_bonus_weight = (ftp[1]-ftp[0]) * ws_damage_scaled / (10 * ftp[0])
            #
            # Example — Savage Blade (ftp 4.0→10.25→13.75), ws_damage_wt=10 (scaled 200):
            #   (10.25-4.0) * 200 / (10 * 4.0) = 6.25*200/40 = 31.25
            #   → Moonshade +250 scores 250*31.25 = 7812, matching ~39% WSD gain.
            #
            # For flat-fTP WS (ftp[1]==ftp[0]) the weight is 0: TP Bonus genuinely
            # has no WS damage value when fTP doesn't scale with TP.
            ws_damage_raw_wt = weights.get('ws_damage', 0.0)
            ws_damage_scaled = ws_damage_raw_wt * 20.0
            ftp_1k_slope = ws_data.ftp[1] - ws_data.ftp[0]
            base_ftp = max(ws_data.ftp[0], 0.5)  # guard against zero-base WS
            tp_bonus_weight = ftp_1k_slope * ws_damage_scaled / (10.0 * base_ftp)
            scaled_weights['tp_bonus'] = max(tp_bonus_weight, 0.1)
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
        # Pure TP: Maximum TP gain speed.
        # DT weights are intentionally included even here: Malignance-family gear
        # carries DT alongside strong physical stats and should win over items that
        # only have equivalent accuracy/attack but no survivability benefit.
        # Negative weights on magic-only stats (fast_cast, cure_potency, enhancing_duration)
        # ensure items like Viti. Gloves or augmented-magic Amalric pieces score
        # negative and get removed from the pool by the score > 0 filter.
        #
        # NOTE on store_tp scaling: store_tp is a raw integer (+1 STP = value 1),
        # while multi-attack stats (double_attack etc.) are stored in basis points
        # (+1% DA = value 100). Game mechanics show STP+1 ≈ DA+1% in TP/second
        # for a dual-wield job, so store_tp weight must be ~100x the per-bp DA weight
        # to be on the same scale. At double_attack=80.0/bp: store_tp = 80*100 = 8000.
        weights = {
            'store_tp': 8000.0,
            'double_attack': 80.0,
            'triple_attack': 120.0,
            'quad_attack': 160.0,
            'gear_haste': 70.0,
            'accuracy': 30.0,
            'attack': 1.0,
            'crit_rate': 2.0,
            # DT: rewards survivability-focused gear (Malignance set, Nyame, etc.)
            'damage_taken': -15.0,
            'physical_dt': -12.0,
            'magical_dt': -8.0,
            # Magic-only stats: penalise items with no TP-relevant contribution.
            # A piece with fast_cast+5% (500bp) gets -5*500 = -2500, which swamps
            # any incidental physical-accuracy base stats it might have.
            'fast_cast': -5.0,
            'cure_potency': -5.0,
            'enhancing_duration': -.30,
            'magic_accuracy_skill': -2.0,
        }
        name = f"Pure TP ({job.name})"
        
    elif tp_type == TPSetType.HYBRID_TP:
        # Hybrid: Balance TP gain with TP phase damage
        # store_tp scaled to match basis-point DA weight (see PURE_TP note above)
        weights = {
            'store_tp': 7000.0,
            'double_attack': 70.0,
            'triple_attack': 100.0,
            'quad_attack': 140.0,
            'gear_haste': 60.0,
            'accuracy': 35.0,
            'attack': 3.0,
            'crit_rate': 4.0,
            'crit_damage': 3.0,
            'STR': 0.5,
            'DEX': 0.3,
            # DT: same rationale as PURE_TP
            'damage_taken': -18.0,
            'physical_dt': -14.0,
            'magical_dt': -10.0,
            # Magic-only penalties
            'fast_cast': -5.0,
            'cure_potency': -5.0,
            'enhancing_duration': -.30,
            'magic_accuracy_skill': -2.0,
        }
        name = f"Hybrid TP ({job.name})"
        
    elif tp_type == TPSetType.ACC_TP:
        # High Accuracy TP: For tough content where accuracy matters
        # store_tp scaled to match basis-point DA weight (see PURE_TP note above)
        weights = {
            'store_tp': 5000.0,
            'double_attack': 50.0,
            'triple_attack': 75.0,
            'quad_attack': 100.0,
            'gear_haste': 50.0,
            'accuracy': 75.0,           # Much higher priority on accuracy
            'attack': 2.0,
            'DEX': 1.0,                 # DEX gives accuracy
            'AGI': 0.5,                 # AGI gives ranged acc
            'skill': 3.0,               # Weapon skill helps accuracy
        }
        name = f"Accuracy TP ({job.name})"
        
    elif tp_type == TPSetType.DT_TP:
        # DT TP: Survivability while building TP
        # store_tp scaled to match basis-point DA weight (see PURE_TP note above)
        weights = {
            'store_tp': 4000.0,
            'double_attack': 40.0,
            'triple_attack': 60.0,
            'quad_attack': 80.0,
            'gear_haste': 40.0,
            'accuracy': 45.0,
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
    
    elif tp_type == TPSetType.BALANCED_DT:
        # Balanced DT: Equal priority on offense and defense while engaged
        # For engaged.DT - not focused on STP, just balanced survivability + offense
        # store_tp scaled to match basis-point DA weight (see PURE_TP note above)
        weights = {
            # Offensive stats - equal-ish weighting
            'store_tp': 5000.0,
            'double_attack': 50.0,
            'triple_attack': 75.0,
            'quad_attack': 100.0,
            'gear_haste': 50.0,
            'accuracy': 50.0,
            'attack': 2.0,
            'crit_rate': 3.0,
            # Defensive stats - equal priority with offense
            'damage_taken': -50.0,
            'physical_dt': -40.0,
            'magical_dt': -30.0,
            'defense': 1.0,
            'VIT': 0.5,
            'magic_evasion': 0.5,
        }
        name = f"Balanced DT ({job.name})"
        
    elif tp_type == TPSetType.REFRESH_TP:
        # Refresh TP: MP sustain for mage jobs or subjob casting
        # store_tp scaled to match basis-point DA weight (see PURE_TP note above)
        weights = {
            'store_tp': 4000.0,
            'double_attack': 40.0,
            'triple_attack': 60.0,
            'quad_attack': 80.0,
            'gear_haste': 40.0,
            'accuracy': 30.0,
            'attack': 1.0,
            # MP stats
            'refresh': 100.0,           # Refresh is very valuable
            'MP': 0.5,
            'convert_mp': 50.0,         # MP recovered effects
        }
        name = f"Refresh TP ({job.name})"
    
    else:
        # Default to pure TP
        # store_tp scaled to match basis-point DA weight (see PURE_TP note above)
        weights = {
            'store_tp': 8000.0,
            'double_attack': 80.0,
            'triple_attack': 120.0,
            'quad_attack': 160.0,
            'gear_haste': 70.0,
            'accuracy': 40.0,
            'attack': 1.0,
        }
        name = f"TP Set ({job.name})"
    
    # Add dual wield weight if applicable
    if is_dual_wield:
        weights['dual_wield'] = 60.0 if tp_type in (TPSetType.PURE_TP, TPSetType.HYBRID_TP) else 40.0
    
    # Set caps
    hard_caps = {'gear_haste': 2500}  # 25% gear haste cap
    
    # DT cap for any profile that has DT weights (prevents over-stacking)
    if tp_type in (TPSetType.PURE_TP, TPSetType.HYBRID_TP,
                   TPSetType.DT_TP, TPSetType.BALANCED_DT):
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
        TPSetType.BALANCED_DT: "Equal offense and defense. For engaged.DT style hybrid sets.",
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
    custom_buffs: Optional[Dict[str, Any]] = None,
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
    
    # Apply custom buffs after job gifts
    if custom_buffs:
        apply_custom_buffs_to_player(player, custom_buffs)
    
    # Determine WS type for wsdist
    if ws_data.ws_type == WSType.MAGICAL:
        ws_type = "magic"
    elif ws_data.ws_type == WSType.HYBRID:
        ws_type = "hybrid"
    elif is_ranged_weaponskill(ws_data):
        ws_type = "ranged"
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
    custom_buffs: Optional[Dict[str, Any]] = None,
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
        custom_buffs: Optional custom buff stats to apply
    
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
    
    # Apply custom buffs after job gifts
    if custom_buffs:
        apply_custom_buffs_to_player(player, custom_buffs)
    
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
     tp, buffs, abilities, main_job, sub_job, job_gifts_dict, master_level, custom_buffs) = args
    
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
        
        # Apply custom buffs after job gifts
        if custom_buffs:
            apply_custom_buffs_to_player(player, custom_buffs)
        
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
        tb = _traceback.format_exc()
        return (idx, 0.0, f"{e}\n{tb}")


def _tp_simulation_worker(args: Tuple) -> Tuple[int, Dict[str, float], Any]:
    """Worker function for parallel TP simulation."""
    (idx, gearset, enemy_data, main_job, sub_job, 
     ws_threshold, buffs, abilities, job_gifts_dict, master_level, custom_buffs) = args
    
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
        
        # Apply custom buffs after job gifts
        if custom_buffs:
            apply_custom_buffs_to_player(player, custom_buffs)
        
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
    custom_buffs: Optional[Dict[str, Any]] = None,
    ammo: Optional[Dict[str, Any]] = None,  # Locked ammo for ranged WSes; None = free slot (melee)
    ranged_weapon: Optional[Dict[str, Any]] = None,  # Ranged weapon (bow/gun) for ranged WSes
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
        custom_buffs: Optional custom buff stats to apply to player
    
    Returns:
        List of (candidate, damage) tuples sorted by damage.
    """
    print("\n" + "-" * 70)
    print("Running Beam Search...")
    print("-" * 70)

    # -------------------------------------------------------------------------
    # TP BONUS SLOT RULES
    # Apply before beam search so both scoring and simulation see correct values.
    # Base TP Bonus (innate on the weapon) is only valid in the slot that
    # executes the WS: main for melee, ranged for ranged WS.
    # Augmented TP Bonus (string "TP Bonus" found in _augments) is global and
    # is left untouched regardless of slot.
    # -------------------------------------------------------------------------
    main_weapon, sub_weapon, ranged_weapon, ammo = _apply_tp_bonus_slot_rules(
        main_weapon=main_weapon,
        sub_weapon=sub_weapon,
        ranged_weapon=ranged_weapon,
        ammo=ammo,
        is_ranged_ws=is_ranged_weaponskill(ws_data),
    )

    # Create optimization profile
    profile = create_ws_profile_from_data(job, ws_data)
    print(f"  Profile: {profile.name}")
    print(f"  Weights: {dict(list(profile.weights.items())[:5])}...")
    
    if job_gifts:
        print(f"  Job Gifts: {job_gifts.job} (JP: {job_gifts.jp_spent})")
    
    if buffs:
        print(f"  Buffs: {list(buffs.keys())}")
    if custom_buffs:
        non_zero = {k: v for k, v in custom_buffs.items() if v}
        if non_zero:
            print(f"  Custom Buffs: {non_zero}")
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
    
    # Lock the ranged slot whenever a ranged weapon is provided — it contributes
    # stats even during a melee WS (e.g. COR with a gun equipped).
    # When a ranged weapon is hard-set the ammo slot is also always locked:
    #   - Ranged WS: lock to the specified ammo piece (arrows/bolts/bullets).
    #   - Melee WS:  lock to the specified ammo piece, or None (= empty slot)
    #     so the beam search cannot freely fill the slot with a stat piece.
    fixed_gear = {
        'main': main_weapon,
        'sub':  sub_weapon,
    }
    if ranged_weapon:
        fixed_gear['ranged'] = ranged_weapon
        fixed_gear['ammo'] = ammo  # None locks the slot to empty for melee WS
    
    # Run two-phase beam search
    contenders = optimizer.two_phase_search(fixed_gear=fixed_gear)
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
    
    # Use provided buffs or empty dict (no default buffs to get accurate baseline)
    if buffs is None:
        buffs = {}
    
    if abilities is None:
        abilities = {}
    
    # Convert job_gifts to dict for pickling (needed by helper)
    job_gifts_dict = None
    if job_gifts:
        job_gifts_dict = {
            'job':      job_gifts.job,
            'jp_spent': job_gifts.jp_spent,
            'stats':    job_gifts.stats,
        }

    # =========================================================================
    # SIMULATION — delegated to shared helper
    # =========================================================================
    print("\n" + "-" * 70)
    print("Simulating with wsdist...")
    print("-" * 70)

    return _simulate_ws_candidates(
        contenders=contenders,
        item_pool=item_pool,
        main_weapon=main_weapon,
        ranged_weapon=ranged_weapon,
        sub_weapon=sub_weapon,
        enemy_data=enemy_data,
        ws_data=ws_data,
        job=job,
        sub_job=sub_job,
        job_gifts=job_gifts,
        job_gifts_dict=job_gifts_dict,
        buffs=buffs,
        abilities=abilities,
        tp=tp,
        master_level=master_level,
        custom_buffs=custom_buffs,
        parallel=parallel,
        max_workers=max_workers,
        ammo=ammo,
    )
# GAR (GEAR ABOVE REPLACEMENT) ANALYSIS
# =============================================================================

def compute_item_gar(
    simulated_results: List[Tuple[Any, float]],
    slot: str,
    min_appearances: int = 2,
) -> Dict[str, float]:
    """
    Compute the average score delta for every item seen in a given slot.

    For each item I in ``slot``:

        GAR(I) = mean(score | item I in slot) - mean(score | item I NOT in slot)

    This is the mean marginal contribution of the item averaged across the
    contexts in which other items were chosen by the beam search — directly
    analogous to WAR in baseball.  Items that consistently appear in
    high-scoring sets receive a high positive delta; items that are only
    present in mediocre sets receive a low or negative delta.

    Parameters
    ----------
    simulated_results : list of (GearsetCandidate, float)
        Output of a run_*_optimization call, already sorted by score.
    slot : str
        wsdist slot name, e.g. 'head', 'ring1'.
    min_appearances : int
        Minimum number of sets the item must appear in to be ranked.
        Items below this threshold are excluded (unreliable estimate).

    Returns
    -------
    dict : name2 → gar_delta (float).  Higher is better.
    """
    # Collect scores split by item presence
    with_scores:    Dict[str, List[float]] = {}   # name2 → scores when present
    without_scores: Dict[str, List[float]] = {}   # name2 → scores when absent

    # First pass: record which item each set uses
    set_items: List[str] = []
    for candidate, score in simulated_results:
        if score <= 0:
            set_items.append('Empty')
            continue
        gear = candidate.gear.get(slot)
        if gear:
            name2 = gear.get('Name2', gear.get('Name', 'Empty'))
        else:
            name2 = 'Empty'
        set_items.append(name2)

    # Second pass: build with/without buckets for every item we've seen
    all_item_names = {n for n in set_items if n != 'Empty'}

    for item_name in all_item_names:
        with_scores[item_name]    = []
        without_scores[item_name] = []

    for (candidate, score), item_in_slot in zip(simulated_results, set_items):
        if score <= 0:
            continue
        for item_name in all_item_names:
            if item_in_slot == item_name:
                with_scores[item_name].append(score)
            else:
                without_scores[item_name].append(score)

    # Compute delta for each item that clears the appearance threshold
    gar: Dict[str, float] = {}
    for item_name in all_item_names:
        w = with_scores[item_name]
        wo = without_scores[item_name]
        if len(w) < min_appearances:
            continue
        mean_with    = sum(w)  / len(w)
        mean_without = sum(wo) / len(wo) if wo else 0.0
        gar[item_name] = mean_with - mean_without

    return gar


def print_gar_rankings(
    gar_by_slot: Dict[str, Dict[str, float]],
    top_n: int = 5,
):
    """Pretty-print GAR rankings for every slot."""
    print("\n" + "=" * 70)
    print("GAR RANKINGS (Gear Above Replacement — score delta)")
    print("=" * 70)

    for slot in WSDIST_SLOTS:
        gar = gar_by_slot.get(slot)
        if not gar:
            continue
        ranked = sorted(gar.items(), key=lambda x: x[1], reverse=True)
        print(f"\n  {slot}:")
        max_abs = max((abs(d) for _, d in ranked), default=0.0)
        for rank, (name, delta) in enumerate(ranked[:top_n], 1):
            bar = "█" * max(0, int(delta / max_abs * 20)) if max_abs > 0 else ""
            sign = "+" if delta >= 0 else ""
            print(f"    {rank}. {name:<35s}  {sign}{delta:,.0f}  {bar}")


def _simulate_ws_candidates(
    contenders: List[Any],
    item_pool: Dict[str, List[Dict]],
    main_weapon: Dict[str, Any],
    sub_weapon: Dict[str, Any],
    enemy_data: Dict,
    ws_data: Any,
    job: Any,
    sub_job: str,
    job_gifts: Optional[Any],
    job_gifts_dict: Optional[Dict],
    buffs: Dict,
    abilities: Dict,
    tp: int,
    master_level: int,
    custom_buffs: Optional[Dict],
    parallel: bool,
    max_workers: Optional[int],
    ammo: Optional[Dict[str, Any]] = None,  # Locked ammo for ranged WSes; None = free slot (melee)
    ranged_weapon: Optional[Dict[str, Any]] = None,  # Ranged weapon (bow/gun) for ranged WSes
) -> List[Tuple[Any, float]]:
    """
    Shared helper: simulate a list of WS candidates and return scored pairs.

    Extracted so both ``run_ws_optimization`` and ``run_ws_optimization_slow``
    can call it without duplicating the parallel-dispatch boilerplate.
    """
    stripped_cache = build_stripped_gear_cache(item_pool)

    # Seed the strip-cache for all fixed weapon slots.
    if main_weapon:
        name2    = main_weapon.get('Name2', main_weapon.get('Name', 'Unknown'))
        stripped = {k: v for k, v in main_weapon.items() if not k.startswith('_')}
        stripped_cache[('main', name2)] = stripped
    if ranged_weapon:
        name2    = ranged_weapon.get('Name2', ranged_weapon.get('Name', 'Unknown'))
        stripped = {k: v for k, v in ranged_weapon.items() if not k.startswith('_')}
        stripped_cache[('ranged', name2)] = stripped
    if sub_weapon:
        name2    = sub_weapon.get('Name2', sub_weapon.get('Name', 'Unknown'))
        stripped = {k: v for k, v in sub_weapon.items() if not k.startswith('_')}
        stripped_cache[('sub', name2)] = stripped

    # For ranged WSes, seed the stripped cache with the locked ammo so that
    # build_gearset_fast resolves it correctly. Melee WSes leave ammo free.
    if ammo and is_ranged_weaponskill(ws_data):
        name2    = ammo.get('Name2', ammo.get('Name', 'Unknown'))
        stripped = {k: v for k, v in ammo.items() if not k.startswith('_')}
        stripped_cache[('ammo', name2)] = stripped

    if ws_data.ws_type == WSType.MAGICAL:
        ws_type_str = "magic"
    elif ws_data.ws_type == WSType.HYBRID:
        ws_type_str = "hybrid"
    elif is_ranged_weaponskill(ws_data):
        ws_type_str = "ranged"
    else:
        ws_type_str = "melee"

    # ── Diagnostic: log what we're about to simulate ─────────────────────────
    print(f"\n[DEBUG] _simulate_ws_candidates diagnostics:")
    print(f"  ws_name     = {ws_data.name}")
    print(f"  ws_type_str = {ws_type_str}")
    print(f"  candidates  = {len(contenders)}")
    print(f"  main_weapon = {main_weapon.get('Name2', main_weapon.get('Name', 'None')) if main_weapon else 'None'}")
    print(f"  sub_weapon  = {sub_weapon.get('Name2', sub_weapon.get('Name', 'None')) if sub_weapon else 'None'}")
    print(f"  ammo        = {ammo.get('Name2', ammo.get('Name', 'None')) if ammo else 'None'}")
    print(f"  tp          = {tp}")
    print(f"  job         = {job.name.lower()}, sub_job = {sub_job}")
    print(f"  master_lvl  = {master_level}")
    # Log first candidate's gear slot keys and weapon/ammo presence
    if contenders:
        first_gear = contenders[0].gear
        print(f"  [first candidate gear slots]: {sorted(first_gear.keys())}")
        for chk in ('main', 'ranged', 'sub', 'ammo'):
            item = first_gear.get(chk)
            name = item.get('Name2', item.get('Name', 'Empty')) if item else 'MISSING'
            print(f"    [{chk}] = {name}")

    print(f"  Building {len(contenders)} gearsets...")
    gearsets = [
        build_gearset_fast(c.gear, stripped_cache, Empty.copy(), WSDIST_SLOTS)
        for c in contenders
    ]

    # Defensive: ensure the ranged weapon is present in every gearset.
    # For melee WSes the beam search locks the ranged slot, but if it was
    # missing from a candidate (e.g. slow-mode didn't lock the slot) then
    # build_gearset_fast would silently insert an empty dict.
    # wsdist needs the actual ranged weapon to account for its stat contributions.
    if ranged_weapon:
        rw_name2    = ranged_weapon.get('Name2', ranged_weapon.get('Name', 'Unknown'))
        rw_stripped = stripped_cache.get(('ranged', rw_name2)) or {
            k: v for k, v in ranged_weapon.items() if not k.startswith('_')
        }
        _injected = 0
        for gs in gearsets:
            existing = gs.get('ranged', {})
            if not existing or not existing.get('Name2') or existing.get('Name2') == 'Empty':
                gs['ranged'] = rw_stripped
                _injected += 1
        if _injected:
            print(f"  [ranged] Injected locked ranged weapon into {_injected} gearsets (was missing/empty)")

    # Log first gearset's weapon/ammo slots after build to confirm resolution
    if gearsets:
        for chk in ('main', 'ranged', 'sub', 'ammo'):
            slot_data = gearsets[0].get(chk, {})
            name = slot_data.get('Name2', slot_data.get('Name', 'Empty'))
            print(f"  [gearset[0] {chk}] = {name}")

    if parallel and PARALLEL_AVAILABLE and len(contenders) > 1:
        if max_workers is None:
            max_workers = max(1, multiprocessing.cpu_count() - 4)
        print(f"  Simulating {len(contenders)} sets with {max_workers} workers...")

        work_items = [
            (idx, gearsets[idx], enemy_data, ws_data.name, ws_type_str,
             tp, buffs, abilities, job.name.lower(), sub_job.lower(),
             job_gifts_dict, master_level, custom_buffs)
            for idx in range(len(contenders))
        ]
        raw = [None] * len(contenders)
        errors: List[str] = []

        # Use 'spawn' context to avoid fork-safety crashes with Numba/LLVM.
        # Forking a process that has Numba's JIT compiler or LLVM thread pools
        # already initialised causes memory corruption (free(): invalid pointer)
        # in child processes, especially on the first run of a new code path
        # (e.g. ranged WS) that hasn't been JIT-compiled in the parent yet.
        # 'spawn' starts a fresh interpreter per worker, sidestepping this entirely.
        _spawn_ctx = multiprocessing.get_context('spawn')
        with ProcessPoolExecutor(max_workers=max_workers, mp_context=_spawn_ctx) as executor:
            futures = {executor.submit(_ws_simulation_worker, a): a[0] for a in work_items}
            for future in as_completed(futures):
                idx, damage, err = future.result()
                if err:
                    errors.append(f"#{idx+1}: {err}")
                    raw[idx] = (contenders[idx], 0.0)
                else:
                    raw[idx] = (contenders[idx], damage)

        for e in errors:
            print(f"  [WORKER ERROR] {e}")
        results = raw

    else:
        print(f"  Simulating {len(contenders)} sets sequentially...")
        results = []
        enemy = create_enemy(enemy_data)
        for i, candidate in enumerate(contenders):
            try:
                damage, _ = simulate_ws(
                    gearset=gearsets[i], enemy=enemy,
                    ws_name=ws_data.name, ws_data=ws_data,
                    tp=tp, buffs=buffs, abilities=abilities,
                    main_job=job.name.lower(), sub_job=sub_job.lower(),
                    job_gifts=job_gifts, master_level=master_level,
                    custom_buffs=custom_buffs,
                )
                results.append((candidate, damage))
            except Exception as e:
                tb = _traceback.format_exc()
                print(f"  [SIM ERROR #{i+1}] {e}\n{tb}")
                results.append((candidate, 0.0))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def _simulate_tp_candidates(
    contenders: List[Any],
    item_pool: Dict[str, List[Dict]],
    main_weapon: Dict[str, Any],
    sub_weapon: Dict[str, Any],
    enemy_data: Dict,
    job: Any,
    sub_job: str,
    job_gifts: Optional[Any],
    job_gifts_dict: Optional[Dict],
    buffs: Dict,
    abilities: Dict,
    master_level: int,
    custom_buffs: Optional[Dict],
    parallel: bool,
    max_workers: Optional[int],
    ranged_weapon: Optional[Dict[str, Any]] = None,
) -> List[Tuple[Any, Dict]]:
    """Shared helper: simulate a list of TP candidates and return scored pairs."""
    stripped_cache = build_stripped_gear_cache(item_pool)
    for slot_name, gear in (('main', main_weapon), ('sub', sub_weapon), ('ranged', ranged_weapon)):
        if gear:
            name2    = gear.get('Name2', gear.get('Name', 'Unknown'))
            stripped = {k: v for k, v in gear.items() if not k.startswith('_')}
            stripped_cache[(slot_name, name2)] = stripped

    print(f"  Building {len(contenders)} gearsets...")
    gearsets = [
        build_gearset_fast(c.gear, stripped_cache, Empty.copy(), WSDIST_SLOTS)
        for c in contenders
    ]

    if parallel and PARALLEL_AVAILABLE and len(contenders) > 1:
        if max_workers is None:
            max_workers = max(1, multiprocessing.cpu_count() - 4)
        print(f"  Simulating {len(contenders)} sets with {max_workers} workers...")

        work_items = [
            (idx, gearsets[idx], enemy_data, job.name.lower(), sub_job.lower(),
             1000, buffs, abilities, job_gifts_dict, master_level, custom_buffs)
            for idx in range(len(contenders))
        ]
        raw = [None] * len(contenders)
        errors: List[str] = []

        # Use 'spawn' context — same fork-safety rationale as _simulate_ws_candidates.
        _spawn_ctx = multiprocessing.get_context('spawn')
        with ProcessPoolExecutor(max_workers=max_workers, mp_context=_spawn_ctx) as executor:
            futures = {executor.submit(_tp_simulation_worker, a): a[0] for a in work_items}
            for future in as_completed(futures):
                idx, metrics, err = future.result()
                if err:
                    errors.append(f"#{idx+1}: {err}")
                    raw[idx] = (contenders[idx], {})
                else:
                    raw[idx] = (contenders[idx], metrics)

        for e in errors:
            print(f"  Error: {e}")
        results = raw

    else:
        print(f"  Simulating {len(contenders)} sets sequentially...")
        results = []
        enemy = create_enemy(enemy_data)
        for i, candidate in enumerate(contenders):
            try:
                metrics = simulate_tp_set(
                    gearset=gearsets[i], enemy=enemy,
                    main_job=job.name.lower(), sub_job=sub_job.lower(),
                    buffs=buffs, abilities=abilities,
                    job_gifts=job_gifts, master_level=master_level,
                    custom_buffs=custom_buffs,
                )
                results.append((candidate, metrics))
            except Exception as e:
                print(f"  Error #{i+1}: {e}")
                results.append((candidate, {}))

    # Sort by time_to_ws ascending (lower is better)
    results.sort(key=lambda x: x[1].get('time_to_ws', float('inf')))
    return results


# =============================================================================
# SLOW MODE — ITERATIVE GAR REFINEMENT
# =============================================================================

def run_ws_optimization_slow(
    inventory,
    job: Job,
    main_weapon: Dict[str, Any],
    sub_weapon: Dict[str, Any],
    ws_data: Any,
    beam_width: int = 25,
    job_gifts=None,
    buffs: Optional[Dict] = None,
    abilities: Optional[Dict] = None,
    target_data: Optional[Dict] = None,
    tp: int = 2000,
    master_level: int = 50,
    sub_job: str = "war",
    parallel: bool = True,
    max_workers: Optional[int] = None,
    custom_buffs: Optional[Dict[str, Any]] = None,
    max_iterations: int = 3,
    top_n_per_slot: int = 3,
    ammo: Optional[Dict[str, Any]] = None,  # Locked ammo for ranged WSes; None = free slot (melee)
    ranged_weapon: Optional[Dict[str, Any]] = None,  # Ranged weapon (bow/gun) for ranged WSes
) -> List[Tuple[Any, float]]:
    """
    Iterative slow-mode WS optimizer using GAR-based pool refinement.

    Each iteration:
      1. Run two-phase beam search on the current item pools.
      2. Simulate all candidate sets with wsdist → true scores.
      3. For every slot, compute each item's average score delta
         (GAR = mean score when present − mean score when absent).
      4. Prune each slot's pool to the top ``top_n_per_slot`` items by GAR.
      5. Repeat until the pool is stable or ``max_iterations`` is reached.

    The first iteration is identical to the normal optimizer.  Subsequent
    iterations work on a dramatically smaller search space, so the beam
    search is much more likely to explore the globally optimal combinations
    rather than being forced to guess across a large accessory space.

    Parameters
    ----------
    max_iterations : int
        Maximum number of beam-search/simulate/prune cycles.
    top_n_per_slot : int
        How many items to keep per slot after each GAR pass.
        2-3 is usually sufficient; raise it if you suspect the right item
        is being pruned (check the printed GAR rankings to verify).
    """
    if buffs     is None: buffs     = {}
    if abilities is None: abilities = {}

    # -------------------------------------------------------------------------
    # TP BONUS SLOT RULES
    # Apply before beam search so both scoring and simulation see correct values.
    # Base TP Bonus (innate on the weapon) is only valid in the slot that
    # executes the WS: main for melee, ranged for ranged WS.
    # Augmented TP Bonus (string "TP Bonus" found in _augments) is global and
    # is left untouched regardless of slot.
    # -------------------------------------------------------------------------
    main_weapon, sub_weapon, ranged_weapon, ammo = _apply_tp_bonus_slot_rules(
        main_weapon=main_weapon,
        sub_weapon=sub_weapon,
        ranged_weapon=ranged_weapon,
        ammo=ammo,
        is_ranged_ws=is_ranged_weaponskill(ws_data),
    )

    profile = create_ws_profile_from_data(job, ws_data)

    # Enemy setup (shared across all iterations)
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

    job_gifts_dict = None
    if job_gifts:
        job_gifts_dict = {
            'job':      job_gifts.job,
            'jp_spent': job_gifts.jp_spent,
            'stats':    job_gifts.stats,
        }

    fixed_gear = {'main': main_weapon, 'sub': sub_weapon}

    # For ranged WSes the weapon fires from the 'ranged' slot, not 'main'.
    # For melee WSes, a ranged weapon (e.g. COR's gun) is still locked because
    # it contributes stats; ammo is left free so the beam search can pick the
    # best piece.
    if is_ranged_weaponskill(ws_data):
        fixed_gear = {
            'main':   main_weapon,    # melee weapon (e.g. Naegling) — stat contributor
            'ranged': ranged_weapon,  # bow/gun — provides Ranged DMG/Delay/SkillType
            'sub':    sub_weapon,
        }
        if ammo:
            fixed_gear['ammo'] = ammo
    elif ranged_weapon:
        # Melee WS with a ranged weapon equipped (e.g. COR) — lock the slot so
        # the beam search preserves its stats and candidates carry it through to
        # wsdist simulation. Also lock ammo so the optimizer cannot freely fill
        # the slot with a stat piece.
        fixed_gear['ranged'] = ranged_weapon
        fixed_gear['ammo'] = ammo  # None locks the slot to empty

    # Build the optimizer once — we'll prune its internal pools each iteration
    optimizer = NumbaBeamSearchOptimizer(
        inventory=inventory,
        profile=profile,
        beam_width=beam_width,
        job=job,
    )

    prev_pool_signature = None
    final_results: List[Tuple[Any, float]] = []

    for iteration in range(max_iterations):
        print(f"\n{'='*70}")
        print(f"SLOW MODE — ITERATION {iteration + 1}/{max_iterations}")
        print('='*70)

        # ── Beam search ──────────────────────────────────────────────────────
        contenders   = optimizer.two_phase_search(fixed_gear=fixed_gear)
        item_pool    = optimizer.extract_item_pool(contenders=contenders)
        print(f"\n✓ {len(contenders)} contenders from beam search")

        if not WSDIST_AVAILABLE:
            print("⚠ wsdist not available — returning beam search results")
            return [(c, c.score) for c in contenders]

        # ── Simulate ─────────────────────────────────────────────────────────
        print("\n" + "-" * 70)
        print(f"Simulating iteration {iteration + 1}...")
        print("-" * 70)
        results = _simulate_ws_candidates(
            contenders=contenders,
            item_pool=item_pool,
            main_weapon=main_weapon,
            sub_weapon=sub_weapon,
            enemy_data=enemy_data,
            ws_data=ws_data,
            job=job,
            sub_job=sub_job,
            job_gifts=job_gifts,
            job_gifts_dict=job_gifts_dict,
            buffs=buffs,
            abilities=abilities,
            tp=tp,
            master_level=master_level,
            custom_buffs=custom_buffs,
            parallel=parallel,
            max_workers=max_workers,
            ammo=ammo,
            ranged_weapon=ranged_weapon,
        )
        final_results = results

        best_score = results[0][1] if results else 0
        print(f"\n  Best this iteration: {best_score:,.0f}")

        # ── GAR analysis ─────────────────────────────────────────────────────
        # Use only the top half of results to anchor GAR on competitive sets,
        # not the long tail of weak candidates.
        top_half = results[: max(1, len(results) // 2)]

        gar_by_slot: Dict[str, Dict[str, float]] = {}
        keep_items:  Dict[str, set] = {}

        # Slots that are fixed (weapons) should never be pruned
        fixed_slots = set(fixed_gear.keys())

        from numba_beam_search_optimizer import PHASE1_SLOTS, PHASE2_SLOTS
        optimized_slots = [
            s for s in (PHASE1_SLOTS + PHASE2_SLOTS)
            if s not in fixed_slots
        ]

        for slot in optimized_slots:
            gar = compute_item_gar(top_half, slot)
            if not gar:
                continue
            gar_by_slot[slot] = gar
            top_items = sorted(gar.items(), key=lambda x: x[1], reverse=True)
            keep_items[slot] = {name for name, _ in top_items[:top_n_per_slot]}

        print_gar_rankings(gar_by_slot, top_n=top_n_per_slot + 2)

        # ── Stability check ───────────────────────────────────────────────────
        pool_signature = frozenset(
            (slot, frozenset(names))
            for slot, names in keep_items.items()
        )
        if pool_signature == prev_pool_signature:
            print(f"\n✓ Item pools stable after iteration {iteration + 1} — stopping early")
            break
        prev_pool_signature = pool_signature

        # ── Prune for next iteration ──────────────────────────────────────────
        if iteration < max_iterations - 1:
            # Paired slots (ear1/ear2, ring1/ring2) share a single item pool in
            # the optimizer. prune_item_pools skips ear2/ring2 and mirrors ear1/
            # ring1's pool onto the partner. If we naively pass each slot's
            # individual GAR top-N, the second slot's best items get silently
            # dropped. Fix: merge both slots' keep sets into the *first* slot key
            # so the shared pool retains items that matter for either position.
            for slot1, slot2 in [('ear1', 'ear2'), ('ring1', 'ring2')]:
                s1_items = keep_items.get(slot1, set())
                s2_items = keep_items.get(slot2, set())
                if s1_items or s2_items:
                    keep_items[slot1] = s1_items | s2_items
                # slot2 entry is ignored by prune_item_pools; leave it for
                # pool_signature stability tracking only.

            optimizer.prune_item_pools(keep_items)

    return final_results


def run_tp_optimization_slow(
    inventory,
    job: Job,
    main_weapon: Dict[str, Any],
    sub_weapon: Dict[str, Any],
    tp_type: 'TPSetType' = None,
    beam_width: int = 25,
    job_gifts=None,
    buffs: Optional[Dict] = None,
    abilities: Optional[Dict] = None,
    target_data: Optional[Dict] = None,
    master_level: int = 50,
    sub_job: str = "war",
    parallel: bool = True,
    max_workers: Optional[int] = None,
    custom_buffs: Optional[Dict[str, Any]] = None,
    max_iterations: int = 3,
    top_n_per_slot: int = 3,
    ranged_weapon: Optional[Dict[str, Any]] = None,
    ammo: Optional[Dict[str, Any]] = None,
) -> List[Tuple[Any, Dict]]:
    """
    Iterative slow-mode TP optimizer using GAR-based pool refinement.

    Mirrors ``run_ws_optimization_slow`` but scores sets by ``time_to_ws``
    (lower is better).  GAR for TP is computed as:

        GAR(I) = mean(time_to_ws | I absent) − mean(time_to_ws | I present)

    So a positive delta still means "this item is good" — it reduces time.

    Parameters
    ----------
    max_iterations : int
        Maximum beam-search/simulate/prune cycles.
    top_n_per_slot : int
        Items to keep per slot after each GAR pass.
    """
    if tp_type is None:
        tp_type = TPSetType.PURE_TP
    if buffs     is None: buffs     = {}
    if abilities is None: abilities = {}

    is_dual_wield = (sub_weapon.get("Type") == "Weapon" and
                     sub_weapon.get("Name") != "Empty")
    profile = create_tp_profile(job, tp_type, is_dual_wield)

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

    job_gifts_dict = None
    if job_gifts:
        job_gifts_dict = {
            'job':      job_gifts.job,
            'jp_spent': job_gifts.jp_spent,
            'stats':    job_gifts.stats,
        }

    fixed_gear = {'main': main_weapon, 'sub': sub_weapon}

    # Lock ranged/ammo slots when a ranged weapon is provided so the beam search
    # cannot overwrite them. Delay is always sourced from melee weapon(s) only.
    if ranged_weapon:
        fixed_gear['ranged'] = ranged_weapon
        fixed_gear['ammo'] = ammo  # None locks the slot to empty

    optimizer = NumbaBeamSearchOptimizer(
        inventory=inventory,
        profile=profile,
        beam_width=beam_width,
        job=job,
    )

    prev_pool_signature = None
    final_results: List[Tuple[Any, Dict]] = []

    for iteration in range(max_iterations):
        print(f"\n{'='*70}")
        print(f"SLOW MODE (TP) — ITERATION {iteration + 1}/{max_iterations}")
        print('='*70)

        contenders = optimizer.two_phase_search(fixed_gear=fixed_gear)
        item_pool  = optimizer.extract_item_pool(contenders=contenders)
        print(f"\n✓ {len(contenders)} contenders from beam search")

        if not WSDIST_AVAILABLE:
            return [(c, {'time_to_ws': 0, 'tp_per_round': 0, 'dps': 0, 'score': c.score})
                    for c in contenders]

        print("\n" + "-" * 70)
        print(f"Simulating iteration {iteration + 1}...")
        print("-" * 70)
        results = _simulate_tp_candidates(
            contenders=contenders,
            item_pool=item_pool,
            main_weapon=main_weapon,
            sub_weapon=sub_weapon,
            ranged_weapon=ranged_weapon,
            enemy_data=enemy_data,
            job=job,
            sub_job=sub_job,
            job_gifts=job_gifts,
            job_gifts_dict=job_gifts_dict,
            buffs=buffs,
            abilities=abilities,
            master_level=master_level,
            custom_buffs=custom_buffs,
            parallel=parallel,
            max_workers=max_workers,
        )
        final_results = results

        best_time = results[0][1].get('time_to_ws', 0) if results else 0
        print(f"\n  Best time_to_ws this iteration: {best_time:.2f}s")

        # For TP, GAR = reduction in time_to_ws when item is present.
        # Convert to pseudo-scores so compute_item_gar works unchanged:
        # score = -time_to_ws  (lower time → higher pseudo-score = better GAR).
        tp_pseudo = [
            (candidate, -metrics.get('time_to_ws', 0))
            for candidate, metrics in results
            if metrics
        ]
        top_half = tp_pseudo[: max(1, len(tp_pseudo) // 2)]

        gar_by_slot: Dict[str, Dict[str, float]] = {}
        keep_items:  Dict[str, set] = {}
        fixed_slots = set(fixed_gear.keys())

        from numba_beam_search_optimizer import PHASE1_SLOTS, PHASE2_SLOTS
        optimized_slots = [
            s for s in (PHASE1_SLOTS + PHASE2_SLOTS)
            if s not in fixed_slots
        ]

        for slot in optimized_slots:
            gar = compute_item_gar(top_half, slot)
            if not gar:
                continue
            gar_by_slot[slot] = gar
            top_items = sorted(gar.items(), key=lambda x: x[1], reverse=True)
            keep_items[slot] = {name for name, _ in top_items[:top_n_per_slot]}

        print_gar_rankings(gar_by_slot, top_n=top_n_per_slot + 2)

        pool_signature = frozenset(
            (slot, frozenset(names))
            for slot, names in keep_items.items()
        )
        if pool_signature == prev_pool_signature:
            print(f"\n✓ Item pools stable after iteration {iteration + 1} — stopping early")
            break
        prev_pool_signature = pool_signature

        if iteration < max_iterations - 1:
            # Same paired-slot union fix as run_ws_optimization_slow — see
            # comment there for full explanation.
            for slot1, slot2 in [('ear1', 'ear2'), ('ring1', 'ring2')]:
                s1_items = keep_items.get(slot1, set())
                s2_items = keep_items.get(slot2, set())
                if s1_items or s2_items:
                    keep_items[slot1] = s1_items | s2_items

            optimizer.prune_item_pools(keep_items)

    return final_results


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
    custom_buffs: Optional[Dict[str, Any]] = None,
    ranged_weapon: Optional[Dict[str, Any]] = None,
    ammo: Optional[Dict[str, Any]] = None,
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
        custom_buffs: Optional custom buff stats to apply to player
        ranged_weapon: Ranged weapon to lock (stats only; delay never used for TP)
        ammo: Ammo piece to lock alongside ranged weapon (None = empty slot)
    
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
    if custom_buffs:
        non_zero = {k: v for k, v in custom_buffs.items() if v}
        if non_zero:
            print(f"  Custom Buffs: {non_zero}")
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
    
    # Lock main and sub for melee TP calculations.
    # If a ranged weapon is provided, lock that slot too so the beam search
    # cannot overwrite it with a stat piece — the ranged weapon contributes
    # its stats to every set (e.g. COR with a gun). Its delay is NEVER used
    # here; TP gain is always calculated from the melee weapon(s) only.
    # Locking ammo alongside the ranged weapon follows the same rule as WS.
    fixed_gear = {
        'main': main_weapon,
        'sub':  sub_weapon,
    }
    if ranged_weapon:
        fixed_gear['ranged'] = ranged_weapon
        fixed_gear['ammo'] = ammo  # None locks the slot to empty

    # Run two-phase beam search
    contenders = optimizer.two_phase_search(fixed_gear=fixed_gear)
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

    # Set up enemy
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

    if buffs     is None: buffs     = {}
    if abilities is None: abilities = {}

    job_gifts_dict = None
    if job_gifts:
        job_gifts_dict = {
            'job':      job_gifts.job,
            'jp_spent': job_gifts.jp_spent,
            'stats':    job_gifts.stats,
        }

    results = _simulate_tp_candidates(
        contenders=contenders,
        item_pool=item_pool,
        main_weapon=main_weapon,
        sub_weapon=sub_weapon,
        ranged_weapon=ranged_weapon,
        enemy_data=enemy_data,
        job=job,
        sub_job=sub_job,
        job_gifts=job_gifts,
        job_gifts_dict=job_gifts_dict,
        buffs=buffs,
        abilities=abilities,
        master_level=master_level,
        custom_buffs=custom_buffs,
        parallel=parallel,
        max_workers=max_workers,
    )

    # Attach beam score for display
    for candidate, metrics in results:
        if isinstance(metrics, dict):
            metrics.setdefault('score', candidate.score)

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
    default_path = ""
    
    if len(sys.argv) > 1:
        inventory_path = sys.argv[1]
    else:
        inventory_path = default_path
    
    ui = OptimizerUI(inventory_path)
    ui.run()


if __name__ == "__main__":
    main()