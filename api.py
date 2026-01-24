#!/usr/bin/env python3
"""
FFXI Gear Set Optimizer - FastAPI Backend

Provides REST API endpoints for the web UI to interact with
the gear optimization system.
"""

import sys
import os
import io

# =============================================================================
# WINDOWS ENCODING FIX (must be before any other imports that might print)
# =============================================================================
# When running as a windowed exe (console=False), stdout/stderr may be None
# or use cp1252 encoding which can't handle Unicode characters like ✓ ✗ ⚠
# This fix ensures all output uses UTF-8 with error replacement

def _setup_safe_output():
    """Configure stdout/stderr to handle Unicode safely on Windows."""
    if sys.platform != 'win32':
        return
    
    # Case 1: No console at all (windowed mode) - redirect to devnull
    if sys.stdout is None or sys.stderr is None:
        devnull = open(os.devnull, 'w', encoding='utf-8')
        if sys.stdout is None:
            sys.stdout = devnull
        if sys.stderr is None:
            sys.stderr = devnull
        return
    
    # Case 2: Console exists but may have wrong encoding - wrap with UTF-8
    try:
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True
            )
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True
            )
    except Exception:
        # If wrapping fails, redirect to devnull as fallback
        devnull = open(os.devnull, 'w', encoding='utf-8')
        sys.stdout = devnull
        sys.stderr = devnull

_setup_safe_output()
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import json
import traceback

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# =============================================================================
# PATH SETUP
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
WSDIST_DIR = SCRIPT_DIR / 'wsdist_beta-main'

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(WSDIST_DIR))

# =============================================================================
# IMPORTS FROM OPTIMIZER
# =============================================================================

from models import Job, Slot, OptimizationProfile, Stats, ItemInstance
from inventory_loader import Inventory, load_inventory
from item_database import get_database, ItemDatabase
from wsdist_converter import to_wsdist_gear
from beam_search_optimizer import (
    BeamSearchOptimizer,
    WSDIST_SLOTS,
    ARMOR_SLOTS,
    SLOT_TO_WSDIST,
)

from numba_beam_search_optimizer import NumbaBeamSearchOptimizer
from lua_parser import (
    LuaParser,
    GearSwapFile,
    LuaSetDefinition,
    LuaItem,
    find_placeholder_sets,
    infer_profile_from_set,
    update_set_in_content,
    wsdist_gear_to_lua_items,
    parse_gearswap_content,
)


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

# Import optimizer functions
from optimizer_ui import (
    TPSetType,
    JOB_LIST,
    JOB_ENUM_MAP,
    SKILL_TO_WEAPON_TYPE,
    get_weapons_from_inventory,
    get_offhand_from_inventory,
    get_weaponskills_for_weapon,
    create_ws_profile_from_data,
    create_tp_profile,
    get_tp_profile_description,
    run_ws_optimization,
    run_tp_optimization,
    simulate_tp_set,
)

# wsdist imports
try:
    from gear import Empty, all_jobs
    from enemies import preset_enemies, enemies
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


# Buff imports
try:
    from buffs import brd, geo, whm, cor, geo_debuffs, whm_debuffs, misc_debuffs
except ImportError:
    brd = {}
    geo = {}
    whm = {}
    cor = {}
    geo_debuffs = {}
    whm_debuffs = {}
    misc_debuffs = {}

# Magic optimization imports
try:
    from magic_optimizer import (
        run_magic_optimization,
        MagicOptimizationType,
        get_valid_optimization_types,
        is_burst_relevant,
        get_job_preset,
        JOB_MAGIC_PRESETS,
        get_evaluation_details,
        get_stratification_note,
        get_target_name,
    )
    from magic_simulation import (
        MagicSimulator,
        CasterStats,
        MagicTargetStats,
        MAGIC_TARGETS,
    )
    from spell_database import (
        get_spell,
        ALL_SPELLS,
        SpellData,
    )
    from magic_formulas import MagicType, Element
    MAGIC_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import magic modules: {e}")
    MAGIC_AVAILABLE = False
    ALL_SPELLS = {}
    MAGIC_TARGETS = {}

# =============================================================================
# DT Set Types (Damage Taken / Survivability Sets)
# =============================================================================

from enum import Enum

class DTSetType(Enum):
    """DT/Survivability set optimization types."""
    PURE_DT = "Pure DT (Maximum Survivability)"
    DT_TP = "DT + TP (Cap DT, then TP)"
    DT_REFRESH = "DT + Refresh (Mage Idle)"
    DT_REGEN = "DT + Regen (HP Recovery)"
    PDT_ONLY = "PDT Only (Physical Focus)"
    MDT_ONLY = "MDT Only (Magical Focus)"
    FAST_CAST = "Fast Cast (Precast Set)"
    GENERIC_WS = "Generic WS (WS Damage + PDL)"
    # NOTE: Enhancing Skill, Enhancing Duration, and Cure Potency are now handled
    # through the Magic tab using MagicOptimizationType.POTENCY with spell-specific profiles


def get_dt_profile_description(dt_type: DTSetType) -> str:
    """Get a description for a DT set type."""
    descriptions = {
        DTSetType.PURE_DT: "Maximum damage reduction. Caps DT/PDT/MDT at -50% each. Secondary: HP, Defense, Evasion.",
        DTSetType.DT_TP: "Survivability while building TP. Caps DT first (-50%), then maximizes TP generation stats.",
        DTSetType.DT_REFRESH: "Mage idle set. Caps DT, then prioritizes Refresh and MP for sustain.",
        DTSetType.DT_REGEN: "HP recovery set. Caps DT, then prioritizes Regen and HP for downtime.",
        DTSetType.PDT_ONLY: "Physical damage focus. Maximizes PDT and DT for physical-heavy content.",
        DTSetType.MDT_ONLY: "Magical damage focus. Maximizes MDT and DT for magical-heavy content.",
        DTSetType.FAST_CAST: "Precast set. Maximizes Fast Cast (caps at 80%). Secondary: HP for survivability.",
        DTSetType.GENERIC_WS: "Generic weaponskill set. Maximizes WS Damage % and Physical Damage Limit+. For precast.WS without specific WS.",
    }
    return descriptions.get(dt_type, "DT optimization set")


def create_dt_profile(
    dt_type: DTSetType,
    job: Optional[Job] = None,
    include_weapons: bool = False,
) -> OptimizationProfile:
    """
    Create a DT/survivability optimization profile.
    
    DT CAPS (FFXI mechanics):
    - Damage Taken (DT): -50% cap (affects all damage)
    - Physical Damage Taken (PDT): -50% cap (physical only)
    - Magical Damage Taken (MDT): -50% cap (magical only)
    
    These stack multiplicatively:
    - With -50% DT and -50% PDT, physical damage = 0.5 * 0.5 = 0.25 (75% reduction)
    - With -50% DT and -50% MDT, magical damage = 0.5 * 0.5 = 0.25 (75% reduction)
    
    Args:
        dt_type: Type of DT set to optimize for
        job: Job requirement
        include_weapons: Whether to include main/sub in optimization
        
    Returns:
        OptimizationProfile configured for the specified DT type
    """
    # DT values are stored as negative basis points: -5000 = -50%
    # We use negative weights because more negative DT = better survivability
    # E.g., -5000 DT * -100 weight = +500,000 score (good)
    #       -2500 DT * -100 weight = +250,000 score (less good)
    
    exclude = set() if include_weapons else {Slot.MAIN, Slot.SUB}
    
    if dt_type == DTSetType.PURE_DT:
        # Maximum survivability - pure DT focus
        return OptimizationProfile(
            name="Pure DT",
            weights={
                # Primary DT stats - extremely high weight to ensure capping
                'damage_taken': -100.0,     # General DT (best stat)
                'physical_dt': -100.0,      # PDT
                'magical_dt': -80.0,        # MDT
                # Secondary defensive stats
                'HP': 3.0,
                'defense': 1.0,
                'VIT': 1.0,                 # Reduces enemy fSTR
                'evasion': 0.5,
                'magic_evasion': 0.4,
                'AGI': 0.3,                 # Reduces enemy crit rate
            },
            hard_caps={
                'damage_taken': -5000,      # -50% cap
                'physical_dt': -5000,       # -50% cap
                'magical_dt': -5000,        # -50% cap
            },
            exclude_slots=exclude,
            job=job,
        )
    
    elif dt_type == DTSetType.DT_TP:
        # DT-capped TP set - survivability first, then TP
        # Use tiered weights: DT tier ~100x, TP tier ~10x
        return OptimizationProfile(
            name="DT + TP",
            weights={
                # Tier 1: DT stats (must cap first) - 100x weight tier
                'damage_taken': -100.0,
                'physical_dt': -100.0,
                'magical_dt': -80.0,
                # Tier 2: TP stats - 10x weight tier
                'store_tp': 10.0,
                'double_attack': 8.0,
                'triple_attack': 12.0,
                'quad_attack': 15.0,
                'gear_haste': 7.0,
                'dual_wield': 6.0,
                'accuracy': 5.0,
                # Tier 3: Secondary stats - 1x weight tier
                'HP': 2.0,
                'attack': 1.0,
                'defense': 0.5,
            },
            hard_caps={
                'damage_taken': -5000,
                'physical_dt': -5000,
                'magical_dt': -5000,
                'gear_haste': 2500,         # 25% gear haste cap
            },
            exclude_slots=exclude,
            job=job,
        )
    
    elif dt_type == DTSetType.DT_REFRESH:
        # Mage idle - DT + MP recovery
        return OptimizationProfile(
            name="DT + Refresh",
            weights={
                # Tier 1: DT stats
                'damage_taken': -100.0,
                'physical_dt': -100.0,
                'magical_dt': -80.0,
                # Tier 2: MP sustain
                'refresh': 50.0,            # Very valuable for mages
                'MP': 5.0,
                # Tier 3: Secondary
                'HP': 2.0,
                'defense': 0.5,
                'magic_evasion': 0.4,
            },
            hard_caps={
                'damage_taken': -5000,
                'physical_dt': -5000,
                'magical_dt': -5000,
            },
            exclude_slots=exclude,
            job=job,
        )
    
    elif dt_type == DTSetType.DT_REGEN:
        # Resting set - DT + HP recovery
        return OptimizationProfile(
            name="DT + Regen",
            weights={
                # Tier 1: DT stats
                'damage_taken': -100.0,
                'physical_dt': -100.0,
                'magical_dt': -80.0,
                # Tier 2: HP recovery
                'regen': 50.0,
                'HP': 5.0,
                # Tier 3: Secondary
                'defense': 1.0,
                'VIT': 0.8,
                'evasion': 0.4,
            },
            hard_caps={
                'damage_taken': -5000,
                'physical_dt': -5000,
                'magical_dt': -5000,
            },
            exclude_slots=exclude,
            job=job,
        )
    
    elif dt_type == DTSetType.PDT_ONLY:
        # Physical damage focus
        return OptimizationProfile(
            name="PDT Only",
            weights={
                # Primary: Physical DT
                'physical_dt': -120.0,      # Highest priority
                'damage_taken': -100.0,     # Also helps physical
                'magical_dt': -20.0,        # Lower priority
                # Secondary
                'HP': 3.0,
                'defense': 2.0,             # More important vs physical
                'VIT': 1.5,
                'evasion': 1.0,
                'AGI': 0.5,
            },
            hard_caps={
                'damage_taken': -5000,
                'physical_dt': -5000,
                'magical_dt': -5000,
            },
            exclude_slots=exclude,
            job=job,
        )
    
    elif dt_type == DTSetType.MDT_ONLY:
        # Magical damage focus
        return OptimizationProfile(
            name="MDT Only",
            weights={
                # Primary: Magical DT
                'magical_dt': -120.0,       # Highest priority
                'damage_taken': -100.0,     # Also helps magical
                'physical_dt': -20.0,       # Lower priority
                # Secondary
                'HP': 3.0,
                'magic_evasion': 2.0,       # More important vs magic
                'magic_defense': 1.5,
                'MND': 1.0,                 # Can help vs some magic
                'defense': 0.5,
            },
            hard_caps={
                'damage_taken': -5000,
                'physical_dt': -5000,
                'magical_dt': -5000,
            },
            exclude_slots=exclude,
            job=job,
        )
    
    elif dt_type == DTSetType.FAST_CAST:
        # Fast Cast precast set
        # Fast Cast caps at 80% (8000 basis points)
        # Note: fast_cast is stored in basis points (100 = 1%)
        return OptimizationProfile(
            name="Fast Cast",
            weights={
                # Primary: Fast Cast - extremely high weight
                'fast_cast': 100.0,         # Primary focus
                # Secondary: Survivability while casting
                'HP': 5.0,                  # Important to survive while casting
                'damage_taken': -3.0,       # Some DT is nice
                'physical_dt': -2.0,
                'magical_dt': -2.0,
                'defense': 1.0,
                'magic_evasion': 0.5,
            },
            hard_caps={
                'fast_cast': 8000,          # 80% cap (in basis points)
            },
            exclude_slots=exclude,
            job=job,
        )
    
    elif dt_type == DTSetType.GENERIC_WS:
        # Generic Weaponskill set - for sets.precast.WS without specific WS name
        # Maximize WS damage modifiers and physical damage limit
        # WS Damage is stored as basis points (1000 = 10%)
        # PDL (Physical Damage Limit) is also basis points
        return OptimizationProfile(
            name="Generic WS",
            weights={
                # Primary: WS damage modifiers
                'ws_damage': 50.0,              # WS Damage % - most important
                'pdl': 40.0,                    # Physical Damage Limit+
                # Secondary: Generic damage stats that help most WS
                'STR': 8.0,                     # Common WS modifier
                'attack': 5.0,                  # More attack = more damage
                'DEX': 4.0,                     # Common WS modifier, affects crit
                'accuracy': 3.0,                # Need to hit
                'crit_rate': 3.0,               # Critical hit rate
                'crit_damage': 2.5,             # Critical damage bonus
                'VIT': 2.0,                     # Some WS use VIT
                'MND': 1.0,                     # Some WS use MND
            },
            hard_caps={},  # No caps for WS damage stats
            exclude_slots=exclude,
            job=job,
        )
    
    # Default: Pure DT
    return OptimizationProfile(
        name="DT Set",
        weights={
            'damage_taken': -100.0,
            'physical_dt': -100.0,
            'magical_dt': -80.0,
            'HP': 3.0,
            'defense': 1.0,
        },
        hard_caps={
            'damage_taken': -5000,
            'physical_dt': -5000,
            'magical_dt': -5000,
        },
        exclude_slots=exclude,
        job=job,
    )


def run_dt_optimization(
    inventory: Inventory,
    job: Job,
    dt_type: DTSetType,
    main_weapon: Optional[Dict] = None,
    sub_weapon: Optional[Dict] = None,
    beam_width: int = 100,
    include_weapons: bool = False,
    # TP calculation parameters
    buffs: Optional[Dict] = None,
    abilities: Optional[Dict] = None,
    target_data: Optional[Dict] = None,
    master_level: int = 0,
    sub_job: str = "war",
    job_gifts: Optional[Any] = None,
) -> List[Tuple[Any, Dict]]:
    """
    Run DT set optimization.
    
    Args:
        inventory: Player's gear inventory
        job: Job to optimize for
        dt_type: Type of DT set to build
        main_weapon: Main hand weapon (locked)
        sub_weapon: Sub weapon (locked)
        beam_width: Number of candidates to consider
        include_weapons: Whether to include weapons in optimization
        buffs: wsdist-format buff dict for TP calculation
        abilities: Abilities dict for TP calculation
        target_data: Target/enemy data dict
        master_level: Master level (0-50)
        sub_job: Sub job for TP calculation
        job_gifts: Optional job gifts
        
    Returns:
        List of (candidate, metrics) tuples sorted appropriately
    """
    
    
    # Create profile for this DT type
    profile = create_dt_profile(dt_type, job=job, include_weapons=include_weapons)
    
    # Set up fixed gear (weapons) if provided and not including weapons in optimization
    fixed_gear = {}
    if not include_weapons:
        if main_weapon:
            fixed_gear['main'] = main_weapon
        if sub_weapon:
            fixed_gear['sub'] = sub_weapon
    
    # Run optimization
    optimizer = NumbaBeamSearchOptimizer(inventory, profile, beam_width, job, include_weapons=include_weapons)
    results = optimizer.search(fixed_gear=fixed_gear if fixed_gear else None)
    
    # Set up TP simulation - we can calculate TP if:
    # 1. main_weapon was passed explicitly, OR
    # 2. include_weapons is True (weapons will be in candidate gear)
    print(f"DEBUG: main_weapon={main_weapon is not None}, include_weapons={include_weapons}")
    can_calculate_tp = WSDIST_AVAILABLE and (main_weapon is not None or include_weapons)
    print(f"DEBUG: can_calculate_tp={can_calculate_tp}")
    enemy = None
    
    if can_calculate_tp:
        # Set up enemy from target_data or use default
        if target_data:
            enemy_data = target_data.copy()
            if "Base Defense" not in enemy_data:
                enemy_data["Base Defense"] = enemy_data.get("Defense", 1550)
        else:
            enemy_data = {
                "Name": "Apex Leech", "Level": 129,
                "Defense": 1142, "Evasion": 1043,
                "VIT": 254, "AGI": 298,
                "Base Defense": 1142,
            }
        enemy = create_enemy(enemy_data)
        
        # Default buffs if not provided
        if buffs is None:
            buffs = {}
        if abilities is None:
            abilities = {}
    
    # Calculate metrics for each result
    output = []
    for candidate in results:
        stats = candidate.stats
        
        # Calculate effective DT percentages
        # DT values are in basis points: -5000 = -50%
        # Apply hard caps: DT/PDT/MDT all cap at -50% (-5000 basis points)
        raw_dt = getattr(stats, 'damage_taken', 0)
        raw_pdt = getattr(stats, 'physical_dt', 0)
        raw_mdt = getattr(stats, 'magical_dt', 0)
        
        # Cap at -5000 basis points (-50%)
        capped_dt = max(raw_dt, -5000)
        capped_pdt = max(raw_pdt, -5000)
        capped_mdt = max(raw_mdt, -5000)
        
        # Convert to percentages
        dt_pct = capped_dt / 100
        pdt_pct = capped_pdt / 100
        mdt_pct = capped_mdt / 100
        
        # Check if DT is capped (at or beyond -50%)
        dt_capped = raw_dt <= -5000
        
        # Calculate effective damage reduction
        # Physical: (1 + DT%/100) * (1 + PDT%/100)
        # At -50% DT and -50% PDT: 0.5 * 0.5 = 0.25 = 75% reduction
        phys_multiplier = (1 + dt_pct/100) * (1 + pdt_pct/100)
        magic_multiplier = (1 + dt_pct/100) * (1 + mdt_pct/100)
        
        # Calculate Fast Cast (stored in basis points: 100 = 1%)
        raw_fc = getattr(stats, 'fast_cast', 0)
        fc_pct = raw_fc // 100  # Convert basis points to percentage
        fc_capped = fc_pct >= 80  # 80% cap
        
        metrics = {
            'score': candidate.score,
            'dt_pct': dt_pct,
            'pdt_pct': pdt_pct,
            'mdt_pct': mdt_pct,
            'dt_capped': dt_capped,
            'physical_reduction': (1 - phys_multiplier) * 100,  # % damage reduced
            'magical_reduction': (1 - magic_multiplier) * 100,
            'hp': getattr(stats, 'HP', 0),
            'defense': getattr(stats, 'defense', 0),
            'evasion': getattr(stats, 'evasion', 0),
            'magic_evasion': getattr(stats, 'magic_evasion', 0),
            'refresh': getattr(stats, 'refresh', 0),
            'regen': getattr(stats, 'regen', 0),
            # Fast Cast metrics
            'fast_cast': min(fc_pct, 80),  # Cap at 80%
            'fast_cast_capped': fc_capped,
            # TP metrics (will be populated if possible)
            'time_to_ws': None,
            'tp_per_round': None,
            'dps': None,
        }
        
        # Calculate TP metrics if we can
        if can_calculate_tp and enemy is not None:
            try:
                # Build gearset for simulation (strip metadata like _augments)
                gearset = {}
                for slot in WSDIST_SLOTS:
                    if slot in candidate.gear:
                        gearset[slot] = strip_gear_metadata(candidate.gear[slot])
                    else:
                        gearset[slot] = Empty.copy()
                
                # Use passed weapons if provided, otherwise use candidate's gear weapons
                if main_weapon:
                    gearset['main'] = strip_gear_metadata(main_weapon)
                if sub_weapon:
                    gearset['sub'] = strip_gear_metadata(sub_weapon)
                
                # Check if we have a valid main weapon for TP simulation
                candidate_main = gearset.get('main', {})
                has_valid_main = (
                    candidate_main.get('Name', 'Empty') != 'Empty' and
                    candidate_main.get('Type') == 'Weapon'
                )
                
                # print(f"TP calculation check: has_valid_main={has_valid_main}, main_name={candidate_main.get('Name', 'None')}")
                
                if has_valid_main:
                    #print(f"Running TP simulation for candidate with main={candidate_main.get('Name', 'None')}")
                    
                    # Simulate TP set
                    tp_metrics = simulate_tp_set(
                        gearset=gearset,
                        enemy=enemy,
                        main_job=job.name.lower(),
                        sub_job=sub_job,
                        ws_threshold=1000,
                        buffs=buffs,
                        abilities=abilities,
                        job_gifts=job_gifts,
                        master_level=master_level,
                    )
                    
                    # print(f"TP simulation result: time_to_ws={tp_metrics.get('time_to_ws')}, tp_per_round={tp_metrics.get('tp_per_round')}")
                    
                    metrics['time_to_ws'] = tp_metrics.get('time_to_ws')
                    metrics['tp_per_round'] = tp_metrics.get('tp_per_round')
                    metrics['dps'] = tp_metrics.get('dps')
                else:
                    print(f"Skipping TP simulation - no valid main weapon in candidate gear")
                
            except Exception as e:
                import traceback
                print(f"Warning: Could not calculate TP metrics: {e}")
                print(traceback.format_exc())
        else:
            # print(f"Skipping TP calculation: WSDIST_AVAILABLE={WSDIST_AVAILABLE}, can_calculate_tp={can_calculate_tp}, enemy={enemy is not None}")
            pass

        output.append((candidate, metrics))
    
    # Sort based on DT type
    if dt_type == DTSetType.DT_TP:
        # For DT_TP: Sort by dt_capped (capped first), then by time_to_ws (lower is better)
        def dt_tp_sort_key(item):
            _, metrics = item
            # dt_capped=True should come first (so we use 0 for True, 1 for False)
            capped_priority = 0 if metrics['dt_capped'] else 1
            # time_to_ws: lower is better, use infinity if not calculated
            time_to_ws = metrics.get('time_to_ws') or float('inf')
            return (capped_priority, time_to_ws)
        
        output.sort(key=dt_tp_sort_key)
    # For other DT types, keep the original beam search score order
    
    return output


# =============================================================================
# FastAPI App Setup
# =============================================================================

app = FastAPI(
    title="FFXI Gear Set Optimizer",
    description="Optimize gear sets for FFXI using beam search and wsdist simulation",
    version="1.0.0"
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Global State
# =============================================================================

class AppState:
    """Global application state."""
    def __init__(self):
        self.inventory: Optional[Inventory] = None
        self.job_gifts: Optional[JobGiftsCollection] = None
        self.inventory_filename: str = ""
        self.job_gifts_filename: str = ""
        self.inventory_csv_content: str = ""  # Raw CSV for caching

state = AppState()

# =============================================================================
# Pydantic Models for API
# =============================================================================

class StatusResponse(BaseModel):
    status: str
    inventory_loaded: bool
    inventory_filename: str
    item_count: int
    job_gifts_loaded: bool
    job_gifts_filename: str
    wsdist_available: bool

class JobInfo(BaseModel):
    code: str
    name: str
    jp_spent: int = 0
    has_master: bool = False

class WeaponInfo(BaseModel):
    name: str
    name2: str
    skill_type: str
    damage: int
    delay: int
    item_level: int
    jobs: List[str]
    stats: Dict[str, Any]

class WeaponskillInfo(BaseModel):
    name: str
    weapon_type: str
    ws_type: str
    hits: int
    ftp_replicating: bool
    can_crit: bool
    stat_modifiers: Dict[str, int]
    skillchain: List[str]

class OptimizeRequest(BaseModel):
    job: str
    sub_job: str = "war"
    main_weapon: Dict[str, Any]
    sub_weapon: Dict[str, Any]
    weaponskill: Optional[str] = None
    tp_type: Optional[str] = None
    target: str = "apex_toad"
    buffs: Dict[str, Any] = {}
    abilities: List[str] = []
    food: str = ""
    debuffs: List[str] = []
    use_simulation: bool = True
    beam_width: int = 100  # Default to 100 for better coverage
    master_level: int = 0
    min_tp: int = 1000

class GearsetResult(BaseModel):
    rank: int
    score: float
    damage: Optional[float] = None
    time_to_ws: Optional[float] = None
    tp_per_round: Optional[float] = None
    dps: Optional[float] = None
    gear: Dict[str, Dict[str, Any]]

class OptimizeResponse(BaseModel):
    success: bool
    optimization_type: str
    results: List[GearsetResult]
    error: Optional[str] = None


# =============================================================================
# Magic Pydantic Models
# =============================================================================

class SpellInfo(BaseModel):
    """Information about a single spell."""
    name: str
    element: str
    magic_type: str
    skill_type: str
    tier: int
    mp_cost: int
    cast_time: float
    is_aoe: bool
    base_v: int
    dint_cap: int


class SpellCategoryInfo(BaseModel):
    """Spell category with list of spells."""
    id: str
    name: str
    spells: List[str]


class MagicOptimizationTypeInfo(BaseModel):
    """Information about a magic optimization type."""
    id: str
    name: str
    description: str


class MagicTargetInfo(BaseModel):
    """Magic target preset information."""
    id: str
    name: str
    level: int
    int_stat: int
    mnd_stat: int
    magic_evasion: int
    magic_defense_bonus: int


class MagicOptimizeRequest(BaseModel):
    """Request body for magic optimization."""
    job: str
    sub_job: str = "rdm"
    spell_name: str
    optimization_type: str  # "damage", "accuracy", "burst", "potency"
    magic_burst: bool = True
    skillchain_steps: int = 2
    target: str = "apex_mob"
    include_weapons: bool = False
    main_weapon: Optional[Dict[str, Any]] = None  # Fixed main weapon when not optimizing weapons
    sub_weapon: Optional[Dict[str, Any]] = None   # Fixed sub weapon when not optimizing weapons
    beam_width: int = 100  # Default to 100 for better results
    buffs: Dict[str, Any] = {}
    debuffs: List[str] = []
    master_level: int = 0


class MagicGearsetResult(BaseModel):
    """A single gear set result from magic optimization."""
    rank: int
    score: float
    damage: Optional[float] = None
    hit_rate: Optional[float] = None
    potency_score: Optional[float] = None
    raw_potency: Optional[float] = None  # For POTENCY: the potency before hit_rate multiplication
    gear: Dict[str, Dict[str, Any]]
    stats: Dict[str, Any] = {}


class MagicOptimizeResponse(BaseModel):
    """Response from magic optimization endpoint."""
    success: bool
    spell_name: str
    optimization_type: str
    magic_burst: bool
    target: str
    evaluated_target: Optional[str] = None  # The target actually used (may differ if stratification stepped up)
    stratification_note: Optional[str] = None  # Message if target was adjusted for discrimination
    results: List[MagicGearsetResult]
    error: Optional[str] = None


class MagicSimulateRequest(BaseModel):
    """Request body for direct magic simulation."""
    job: str
    sub_job: str = "rdm"
    spell_name: str
    gearset: Dict[str, Dict[str, Any]]
    magic_burst: bool = True
    skillchain_steps: int = 2
    target: str = "apex_mob"
    buffs: Dict[str, Any] = {}
    debuffs: List[str] = []
    master_level: int = 0
    num_casts: int = 100  # Number of simulation casts


class MagicSimulateResponse(BaseModel):
    """Response from magic simulation endpoint."""
    success: bool
    spell_name: str
    magic_burst: bool
    target: str
    num_casts: int
    
    # Damage statistics
    average_damage: Optional[float] = None
    min_damage: Optional[int] = None
    max_damage: Optional[int] = None
    
    # Hit/Resist statistics
    hit_rate: Optional[float] = None
    unresisted_rate: Optional[float] = None
    half_resist_rate: Optional[float] = None
    quarter_resist_rate: Optional[float] = None
    eighth_resist_rate: Optional[float] = None
    
    # Breakdown info
    base_damage: Optional[int] = None
    mab_mdb_ratio: Optional[float] = None
    mb_multiplier: Optional[float] = None
    mbb_multiplier: Optional[float] = None
    
    # Stats used
    stats: Dict[str, Any] = {}
    
    error: Optional[str] = None


class MagicStatsRequest(BaseModel):
    """Request for magic stats calculation."""
    job: str
    sub_job: str = "rdm"
    master_level: int = 0
    gearset: Dict[str, Dict[str, Any]]
    spell_name: Optional[str] = None
    buffs: Dict[str, Any] = {}
    target: str = "apex_mob"


class MagicStatsResponse(BaseModel):
    """Response with calculated magic stats."""
    success: bool
    stats: Dict[str, Any] = {}
    error: Optional[str] = None


# =============================================================================
# Buff Conversion Helper
# =============================================================================

def convert_ui_buffs_to_wsdist(
    ui_buffs: Dict[str, List[str]],
    abilities: List[str],
    food: str,
    debuffs: List[str],
) -> Tuple[Dict[str, Dict], Dict[str, bool], Dict]:
    """
    Convert UI-format buffs to wsdist format.
    
    Args:
        ui_buffs: {"brd": ["Minuet V", "Honor March"], "cor": [...], ...}
        abilities: ["Berserk", "Hasso", ...]
        food: "Grape Daifuku"
        debuffs: ["Dia III", "Geo-Frailty", ...]
    
    Returns:
        (buffs_dict, abilities_dict, debuffs_info) where:
        - buffs_dict: wsdist format {"BRD": {"Attack": 280, ...}, ...}
        - abilities_dict: {"Berserk": True, ...}
        - debuffs_info: {"defense_down_pct": 0.35, "evasion_down": 50, ...}
    """
    buffs_dict = {}
    
    # Process food
    if food and food in BUFF_DEFINITIONS.get("food", {}):
        food_stats = BUFF_DEFINITIONS["food"][food]
        buffs_dict["Food"] = {
            "STR": food_stats.get("STR", 0),
            "DEX": food_stats.get("DEX", 0),
            "VIT": food_stats.get("VIT", 0),
            "AGI": food_stats.get("AGI", 0),
            "INT": food_stats.get("INT", 0),
            "MND": food_stats.get("MND", 0),
            "CHR": food_stats.get("CHR", 0),
            "Attack": food_stats.get("attack", 0),
            "Ranged Attack": food_stats.get("attack", 0),
            "Accuracy": food_stats.get("accuracy", 0),
            "Ranged Accuracy": food_stats.get("ranged_accuracy", food_stats.get("accuracy", 0)),
        }
    
    # Process BRD songs
    if "brd" in ui_buffs and ui_buffs["brd"]:
        brd_stats = {
            "Attack": 0, "Ranged Attack": 0, "Accuracy": 0, "Ranged Accuracy": 0,
            "Magic Haste": 0, "STR": 0, "DEX": 0, "VIT": 0, "AGI": 0,
            "INT": 0, "MND": 0, "CHR": 0, "PDL": 0,
        }
        for song in ui_buffs["brd"]:
            if song in BUFF_DEFINITIONS.get("brd", {}):
                s = BUFF_DEFINITIONS["brd"][song]
                brd_stats["Attack"] += s.get("attack", 0)
                brd_stats["Ranged Attack"] += s.get("attack", 0)
                brd_stats["Accuracy"] += s.get("accuracy", 0)
                brd_stats["Ranged Accuracy"] += s.get("accuracy", 0)
                brd_stats["Magic Haste"] += s.get("magic_haste", 0)
                brd_stats["PDL"] += s.get("pdl", 0)
                for stat in ["STR", "DEX", "VIT", "AGI", "INT", "MND", "CHR"]:
                    brd_stats[stat] += s.get(stat, 0)
        buffs_dict["BRD"] = brd_stats
    
    # Process COR rolls
    if "cor" in ui_buffs and ui_buffs["cor"]:
        cor_stats = {
            "Attack%": 0, "Accuracy": 0, "Ranged Accuracy": 0,
            "Store TP": 0, "DA": 0, "Crit Rate": 0, "Regain": 0,
            "Magic Attack": 0,
        }
        for roll in ui_buffs["cor"]:
            if roll in BUFF_DEFINITIONS.get("cor", {}):
                r = BUFF_DEFINITIONS["cor"][roll]
                cor_stats["Attack%"] += r.get("attack_pct", 0)
                cor_stats["Accuracy"] += r.get("accuracy", 0)
                cor_stats["Ranged Accuracy"] += r.get("ranged_accuracy", 0)
                cor_stats["Store TP"] += r.get("store_tp", 0)
                cor_stats["DA"] += r.get("double_attack", 0)
                cor_stats["Crit Rate"] += r.get("crit_rate", 0)
                cor_stats["Regain"] += r.get("regain", 0)
                cor_stats["Magic Attack"] += r.get("magic_attack", 0)
        buffs_dict["COR"] = cor_stats
    
    # Process GEO bubbles
    if "geo" in ui_buffs and ui_buffs["geo"]:
        geo_stats = {
            "Attack%": 0, "Accuracy": 0, "Magic Haste": 0,
            "STR": 0, "DEX": 0, "VIT": 0, "AGI": 0, "INT": 0, "MND": 0, "CHR": 0,
            "Magic Attack": 0, "Magic Accuracy": 0,
        }
        for bubble in ui_buffs["geo"]:
            if bubble in BUFF_DEFINITIONS.get("geo", {}):
                g = BUFF_DEFINITIONS["geo"][bubble]
                geo_stats["Attack%"] += g.get("attack_pct", 0)
                geo_stats["Accuracy"] += g.get("accuracy", 0)
                geo_stats["Magic Haste"] += g.get("magic_haste", 0)
                geo_stats["Magic Attack"] += g.get("magic_attack", 0)
                geo_stats["Magic Accuracy"] += g.get("magic_accuracy", 0)
                for stat in ["STR", "DEX", "VIT", "AGI", "INT", "MND", "CHR"]:
                    geo_stats[stat] += g.get(stat, 0)
        buffs_dict["GEO"] = geo_stats
    
    # Process WHM spells
    if "whm" in ui_buffs and ui_buffs["whm"]:
        whm_stats = {
            "Magic Haste": 0,
            "STR": 0, "DEX": 0, "VIT": 0, "AGI": 0, "INT": 0, "MND": 0, "CHR": 0,
            "MDT": 0,
        }
        for spell in ui_buffs["whm"]:
            if spell in BUFF_DEFINITIONS.get("whm", {}):
                w = BUFF_DEFINITIONS["whm"][spell]
                whm_stats["Magic Haste"] += w.get("magic_haste", 0)
                whm_stats["MDT"] += w.get("mdt", 0)
                for stat in ["STR", "DEX", "VIT", "AGI", "INT", "MND", "CHR"]:
                    whm_stats[stat] += w.get(stat, 0)
        buffs_dict["WHM"] = whm_stats
    
    # Build abilities dict
    abilities_dict = {}
    for ability in abilities:
        abilities_dict[ability] = True
    
    # Process debuffs
    debuffs_info = {
        "defense_down_pct": 0,
        "evasion_down": 0,
        "magic_defense_down": 0,
        "magic_evasion_down": 0,
    }
    for debuff in debuffs:
        for category in DEBUFF_DEFINITIONS.values():
            if debuff in category:
                d = category[debuff]
                debuffs_info["defense_down_pct"] += d.get("defense_down_pct", 0)
                debuffs_info["evasion_down"] += d.get("evasion_down", 0)
                debuffs_info["magic_defense_down"] += d.get("magic_defense_down", 0)
                debuffs_info["magic_evasion_down"] += d.get("magic_evasion_down", 0)
    
    # Cap defense down at 50%
    debuffs_info["defense_down_pct"] = min(debuffs_info["defense_down_pct"], 0.5)
    
    return buffs_dict, abilities_dict, debuffs_info


# =============================================================================
# Optimization Helper Functions
# =============================================================================

def get_job_enum_or_error(job: str, opt_type: str):
    """
    Validate job and return job enum, or return an error response.
    
    Returns:
        Tuple of (job_enum, None) on success, or (None, error_response) on failure
    """
    job_enum = JOB_ENUM_MAP.get(job) or JOB_ENUM_MAP.get(job.upper())
    if not job_enum:
        return None, f"Invalid job: {job}"
    return job_enum, None


def get_job_gifts_for_job(job: str):
    """Get job gifts for a job if available."""
    if state.job_gifts and job.upper() in state.job_gifts.gifts:
        return state.job_gifts.gifts[job.upper()]
    return None


def prepare_target_with_debuffs(target_key: str, debuffs_info: dict, default_target: str = "apex_toad"):
    """
    Get target data and apply debuffs.
    
    Args:
        target_key: Target preset key
        debuffs_info: Dict with defense_down_pct and evasion_down values
        default_target: Fallback target if key not found
    
    Returns:
        Modified target data dict
    """
    key = target_key if target_key in TARGET_PRESETS else default_target
    target_data = TARGET_PRESETS[key].copy()
    target_data["Base Defense"] = target_data.get("Defense", 1500)
    # Apply defense down debuff
    target_data["Defense"] = int(target_data["Defense"] * (1 - debuffs_info.get("defense_down_pct", 0)))
    target_data["Evasion"] = target_data["Evasion"] - debuffs_info.get("evasion_down", 0)
    return target_data


def format_gear_dict(candidate, include_full_stats: bool = True) -> Dict[str, Dict]:
    """
    Format a candidate's gear into API response format.
    
    Args:
        candidate: Optimization candidate with gear attribute
        include_full_stats: If True, include all item stats (for melee).
                          If False, only include name/name2 (for magic).
    
    Returns:
        Dict mapping slot names to item dicts
    """
    gear_dict = {}
    for slot in WSDIST_SLOTS:
        if slot in candidate.gear:
            item = candidate.gear[slot]
            if include_full_stats:
                gear_dict[slot] = {
                    "name": item.get("Name", "Empty"),
                    "name2": item.get("Name2", item.get("Name", "Empty")),
                    "_augments": item.get("_augments"),  # For Lua output
                    **{k: v for k, v in item.items() if k not in ("Name", "Name2", "_augments")}
                }
            else:
                gear_dict[slot] = {
                    "name": item.get("Name", "Empty"),
                    "name2": item.get("Name2", item.get("Name", "Empty")),
                    "_augments": item.get("_augments"),  # For Lua output
                }
    return gear_dict


# =============================================================================
# Target/Enemy Presets
# =============================================================================

TARGET_PRESETS = {
    "training_dummy": {
        "Name": "Training Dummy", "Level": 1,
        "Defense": 100, "Evasion": 100,
        "VIT": 50, "AGI": 50, "MND": 50, "INT": 50, "CHR": 50,
        "Magic Evasion": 0, "Magic Defense": 0, "Magic DT%": 0,
    },
    "apex_leech": {
        "Name": "Apex Leech", "Level": 129,
        "Defense": 1142, "Evasion": 1043,
        "VIT": 254, "AGI": 298, "MND": 233, "INT": 233, "CHR": 247,
        "Magic Evasion": 0, "Magic Defense": 0, "Magic DT%": 0,
    },
    "apex_crawler": {
        "Name": "Apex Crawler", "Level": 129,
        "Defense": 1142, "Evasion": 1043,
        "VIT": 254, "AGI": 298, "MND": 233, "INT": 233, "CHR": 247,
        "Magic Evasion": 0, "Magic Defense": 0, "Magic DT%": 0,
    },
    "apex_lizard": {
        "Name": "Apex Lizard", "Level": 129,
        "Defense": 1142, "Evasion": 1043,
        "VIT": 254, "AGI": 298, "MND": 233, "INT": 233, "CHR": 247,
        "Magic Evasion": 0, "Magic Defense": 0, "Magic DT%": 0,
    },
    "apex_toad": {
        "Name": "Apex Toad", "Level": 132,
        "Defense": 1239, "Evasion": 1133,
        "VIT": 270, "AGI": 348, "MND": 224, "INT": 293, "CHR": 277,
        "Magic Evasion": 0, "Magic Defense": 0, "Magic DT%": -25,
    },
    "apex_crab": {
        "Name": "Apex Crab", "Level": 135,
        "Defense": 1338, "Evasion": 1224,
        "VIT": 289, "AGI": 340, "MND": 267, "INT": 267, "CHR": 282,
        "Magic Evasion": 0, "Magic Defense": 0, "Magic DT%": 0,
    },
    "apex_bat": {
        "Name": "Apex Bat", "Level": 135,
        "Defense": 1338, "Evasion": 1224,
        "VIT": 289, "AGI": 340, "MND": 267, "INT": 267, "CHR": 282,
        "Magic Evasion": 0, "Magic Defense": 0, "Magic DT%": 0,
    },
    "odyssey_normal": {
        "Name": "Odyssey (Normal)", "Level": 140,
        "Defense": 1530, "Evasion": 1383,
        "VIT": 356, "AGI": 343, "MND": 297, "INT": 297, "CHR": 297,
        "Magic Evasion": 0, "Magic Defense": 0, "Magic DT%": 0,
    },
    "odyssey_boss": {
        "Name": "Odyssey (Boss)", "Level": 145,
        "Defense": 1704, "Evasion": 1551,
        "VIT": 381, "AGI": 440, "MND": 353, "INT": 365, "CHR": 353,
        "Magic Evasion": 0, "Magic Defense": 0, "Magic DT%": 0,
    },
    "dynamis_wave3": {
        "Name": "Dynamis Wave 3", "Level": 147,
        "Defense": 1791, "Evasion": 1628,
        "VIT": 399, "AGI": 443, "MND": 377, "INT": 390, "CHR": 377,
        "Magic Evasion": 0, "Magic Defense": 0, "Magic DT%": 0,
    },
}

# =============================================================================
# Spell Categories (for Magic UI grouping)
# =============================================================================

SPELL_CATEGORIES = {
    "elemental_tier_1": {
        "id": "elemental_tier_1",
        "name": "Elemental Tier I",
        "spells": ["Stone", "Water", "Aero", "Fire", "Blizzard", "Thunder"],
    },
    "elemental_tier_2": {
        "id": "elemental_tier_2",
        "name": "Elemental Tier II",
        "spells": ["Stone II", "Water II", "Aero II", "Fire II", "Blizzard II", "Thunder II"],
    },
    "elemental_tier_3": {
        "id": "elemental_tier_3",
        "name": "Elemental Tier III",
        "spells": ["Stone III", "Water III", "Aero III", "Fire III", "Blizzard III", "Thunder III"],
    },
    "elemental_tier_4": {
        "id": "elemental_tier_4",
        "name": "Elemental Tier IV",
        "spells": ["Stone IV", "Water IV", "Aero IV", "Fire IV", "Blizzard IV", "Thunder IV"],
    },
    "elemental_tier_5": {
        "id": "elemental_tier_5",
        "name": "Elemental Tier V",
        "spells": ["Stone V", "Water V", "Aero V", "Fire V", "Blizzard V", "Thunder V"],
    },
    "elemental_tier_6": {
        "id": "elemental_tier_6",
        "name": "Elemental Tier VI",
        "spells": ["Stone VI", "Water VI", "Aero VI", "Fire VI", "Blizzard VI", "Thunder VI"],
    },
    "elemental_ga": {
        "id": "elemental_ga",
        "name": "-ga Spells (AoE)",
        "spells": ["Stonega", "Waterga", "Aeroga", "Firaga", "Blizzaga", "Thundaga",
                   "Stonega II", "Waterga II", "Aeroga II", "Firaga II", "Blizzaga II", "Thundaga II",
                   "Stonega III", "Waterga III", "Aeroga III", "Firaga III", "Blizzaga III", "Thundaga III"],
    },
    "elemental_ja": {
        "id": "elemental_ja",
        "name": "-ja Spells (AoE)",
        "spells": ["Stoneja", "Waterja", "Aeroja", "Firaja", "Blizzaja", "Thundaja"],
    },
    "ancient_magic": {
        "id": "ancient_magic",
        "name": "Ancient Magic",
        "spells": ["Quake", "Flood", "Tornado", "Flare", "Freeze", "Burst"],
    },
    "ancient_magic_2": {
        "id": "ancient_magic_2",
        "name": "Ancient Magic II",
        "spells": ["Quake II", "Flood II", "Tornado II", "Flare II", "Freeze II", "Burst II"],
    },
    "comet": {
        "id": "comet",
        "name": "Comet",
        "spells": ["Comet"],
    },
    "helix": {
        "id": "helix",
        "name": "Helix Spells",
        "spells": ["Geohelix", "Hydrohelix", "Anemohelix", "Pyrohelix", "Cryohelix", "Ionohelix", 
                   "Luminohelix", "Noctohelix"],
    },
    "helix_2": {
        "id": "helix_2",
        "name": "Helix II Spells",
        "spells": ["Geohelix II", "Hydrohelix II", "Anemohelix II", "Pyrohelix II", "Cryohelix II", 
                   "Ionohelix II", "Luminohelix II", "Noctohelix II"],
    },
    "divine_banish": {
        "id": "divine_banish",
        "name": "Divine (Banish)",
        "spells": ["Banish", "Banish II", "Banish III", "Banishga", "Banishga II"],
    },
    "divine_holy": {
        "id": "divine_holy",
        "name": "Divine (Holy)",
        "spells": ["Holy", "Holy II"],
    },
    "dark_bio": {
        "id": "dark_bio",
        "name": "Dark (Bio)",
        "spells": ["Bio", "Bio II", "Bio III"],
    },
    "dark_drain": {
        "id": "dark_drain",
        "name": "Dark (Drain/Aspir)",
        "spells": ["Drain", "Drain II", "Drain III", "Aspir", "Aspir II", "Aspir III"],
    },
    "dark_stun": {
        "id": "dark_stun",
        "name": "Dark (Stun)",
        "spells": ["Stun"],
    },
    "absorb_spells": {
        "id": "absorb_spells",
        "name": "Absorb Spells",
        "spells": ["Absorb-STR", "Absorb-DEX", "Absorb-VIT", "Absorb-AGI", 
                   "Absorb-INT", "Absorb-MND", "Absorb-CHR", "Absorb-ACC", "Absorb-TP", "Absorb-Attri"],
    },
    "enfeebling_mnd": {
        "id": "enfeebling_mnd",
        "name": "Enfeebling (MND)",
        "spells": ["Slow", "Slow II", "Paralyze", "Paralyze II", "Addle", "Addle II", 
                   "Silence", "Distract", "Distract II", "Distract III", 
                   "Frazzle", "Frazzle II", "Frazzle III"],
    },
    "enfeebling_int": {
        "id": "enfeebling_int",
        "name": "Enfeebling (INT)",
        "spells": ["Blind", "Blind II", "Gravity", "Gravity II", "Poison", "Poison II",
                   "Sleep", "Sleep II", "Dispel", "Break", "Breakga"],
    },
    "dia": {
        "id": "dia",
        "name": "Dia",
        "spells": ["Dia", "Dia II", "Dia III", "Diaga"],
    },
    "enspell": {
        "id": "enspell",
        "name": "Enspells",
        "spells": ["Enfire", "Enblizzard", "Enaero", "Enstone", "Enthunder", "Enwater",
                   "Enfire II", "Enblizzard II", "Enaero II", "Enstone II", "Enthunder II", "Enwater II",
                   "Enlight", "Enlight II", "Endark", "Endark II"],
    },
}

# Quick access list for popular nukes (for UI quick-select)
POPULAR_NUKES = [
    "Thunder VI", "Fire VI", "Blizzard VI", "Aero VI", "Stone VI", "Water VI",
    "Burst II", "Freeze II", "Flare II", "Tornado II", "Quake II", "Flood II",
    "Thundaja", "Firaja", "Blizzaja",
]

# =============================================================================
# Magic Target Presets
# =============================================================================

MAGIC_TARGET_PRESETS = {
    "apex_mob": {
        "id": "apex_mob",
        "name": "Apex Mob",
        "level": 129,
        "int_stat": 200,
        "mnd_stat": 200,
        "magic_evasion": 600,
        "magic_defense_bonus": 30,
    },
    "odyssey_nm": {
        "id": "odyssey_nm",
        "name": "Odyssey NM (Low)",
        "level": 140,
        "int_stat": 250,
        "mnd_stat": 250,
        "magic_evasion": 750,
        "magic_defense_bonus": 50,
    },
    "odyssey_v15": {
        "id": "odyssey_v15",
        "name": "Odyssey V15",
        "level": 145,
        "int_stat": 290,
        "mnd_stat": 290,
        "magic_evasion": 1000,
        "magic_defense_bonus": 60,
    },
    "odyssey_v20": {
        "id": "odyssey_v20",
        "name": "Odyssey V20",
        "level": 148,
        "int_stat": 320,
        "mnd_stat": 320,
        "magic_evasion": 1100,
        "magic_defense_bonus": 70,
    },
    "odyssey_v25": {
        "id": "odyssey_v25",
        "name": "Odyssey V25",
        "level": 150,
        "int_stat": 350,
        "mnd_stat": 350,
        "magic_evasion": 1200,
        "magic_defense_bonus": 80,
    },
    "sortie_boss": {
        "id": "sortie_boss",
        "name": "Sortie Boss",
        "level": 145,
        "int_stat": 280,
        "mnd_stat": 280,
        "magic_evasion": 800,
        "magic_defense_bonus": 40,
    },
    "ambuscade_vd": {
        "id": "ambuscade_vd",
        "name": "Ambuscade VD",
        "level": 135,
        "int_stat": 220,
        "mnd_stat": 220,
        "magic_evasion": 650,
        "magic_defense_bonus": 25,
    },
    "training_dummy": {
        "id": "training_dummy",
        "name": "Training Dummy",
        "level": 1,
        "int_stat": 100,
        "mnd_stat": 100,
        "magic_evasion": 300,
        "magic_defense_bonus": 0,
    },
    "high_resist": {
        "id": "high_resist",
        "name": "High Resist Target",
        "level": 150,
        "int_stat": 300,
        "mnd_stat": 300,
        "magic_evasion": 900,
        "magic_defense_bonus": 60,
    },
}

# =============================================================================
# Buff Definitions for UI
# =============================================================================

HASTE_BUFFS = {
    "haste": {"name": "Haste", "source": "WHM", "magic_haste": 150/1024},
    "haste2": {"name": "Haste II", "source": "WHM", "magic_haste": 307/1024},
    "march_honor": {"name": "Honor March", "source": "BRD", "magic_haste": 126/1024},
    "march_victory": {"name": "Victory March", "source": "BRD", "magic_haste": 163/1024},
    "march_advancing": {"name": "Advancing March", "source": "BRD", "magic_haste": 108/1024},
    "geo_haste": {"name": "Indi/Geo-Haste", "source": "GEO", "magic_haste": 299/1024},
}

DAMAGE_BUFFS = {
    "minuet5": {"name": "Minuet V", "source": "BRD", "attack": 149},
    "minuet4": {"name": "Minuet IV", "source": "BRD", "attack": 137},
    "geo_fury": {"name": "Geo-Fury", "source": "GEO", "attack_pct": 0.347},
    "chaos_roll": {"name": "Chaos Roll (XI)", "source": "COR", "attack_pct": 0.3125},
    "berserk": {"name": "Berserk", "source": "WAR", "attack_pct": 0.25},
    "warcry": {"name": "Warcry", "source": "WAR", "attack": 0},  # Placeholder
}

ACCURACY_BUFFS = {
    "madrigal_blade": {"name": "Blade Madrigal", "source": "BRD", "accuracy": 60},
    "madrigal_sword": {"name": "Sword Madrigal", "source": "BRD", "accuracy": 45},
    "geo_precision": {"name": "Geo-Precision", "source": "GEO", "accuracy": 50},
    "hunter_roll": {"name": "Hunter's Roll (XI)", "source": "COR", "accuracy": 50},
    "aggressor": {"name": "Aggressor", "source": "WAR", "accuracy": 25},
}

DEBUFF_OPTIONS = {
    "dia3": {"name": "Dia III", "source": "WHM", "defense_down": 208/1024},
    "geo_frailty": {"name": "Geo-Frailty", "source": "GEO", "defense_down": 0.148},
    "angon": {"name": "Angon", "source": "DRG", "defense_down": 0.20},
    "armor_break": {"name": "Armor Break", "source": "WAR", "defense_down": 0.25},
    "box_step": {"name": "Box Step", "source": "DNC", "defense_down": 0.23},
}

# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    html_path = SCRIPT_DIR / "static" / "index.html"
    if html_path.exists():
        return FileResponse(html_path)
    return HTMLResponse("<h1>FFXI Gear Optimizer API</h1><p>Static files not found</p>")


@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """Get the current application status."""
    return StatusResponse(
        status="ready" if state.inventory else "no_inventory",
        inventory_loaded=state.inventory is not None,
        inventory_filename=state.inventory_filename,
        item_count=len(state.inventory.items) if state.inventory else 0,
        job_gifts_loaded=state.job_gifts is not None,
        job_gifts_filename=state.job_gifts_filename,
        wsdist_available=WSDIST_AVAILABLE,
    )


@app.post("/api/upload/inventory")
async def upload_inventory(file: UploadFile = File(...)):
    """Upload an inventory CSV file."""
    try:
        # Save to temp file
        temp_path = SCRIPT_DIR / f"temp_{file.filename}"
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)
        
        # Load inventory
        state.inventory = load_inventory(str(temp_path))
        state.inventory_filename = file.filename
        
        # Store raw CSV content for caching
        state.inventory_csv_content = content.decode('utf-8')
        
        # Clean up temp file
        temp_path.unlink()
        
        return {
            "success": True,
            "filename": file.filename,
            "item_count": len(state.inventory.items),
            "message": f"Loaded {len(state.inventory.items)} items"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


class CachedInventoryRequest(BaseModel):
    """Request model for reloading cached inventory."""
    csv_content: str  # Raw CSV content
    character_name: Optional[str] = None


@app.get("/api/inventory/raw")
async def get_inventory_raw():
    """
    Get the raw CSV content of the currently loaded inventory.
    
    This is used for caching - the frontend stores the CSV and can
    reload it later without re-uploading the file.
    """
    if not hasattr(state, 'inventory_csv_content') or not state.inventory_csv_content:
        return {
            "success": False,
            "error": "No inventory CSV content available"
        }
    
    return {
        "success": True,
        "csv_content": state.inventory_csv_content
    }


@app.post("/api/upload/inventory/reload")
async def reload_cached_inventory(request: CachedInventoryRequest):
    """
    Reload inventory from cached CSV data stored in browser localStorage.
    
    This endpoint allows the frontend to restore inventory data that was
    previously cached, enabling persistence across browser sessions without
    requiring re-upload of the inventory CSV file.
    """
    try:
        if not request.csv_content:
            return {
                "success": False,
                "error": "No CSV content provided"
            }
        
        # Write CSV content to temp file and parse it
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(request.csv_content)
            temp_path = f.name
        
        try:
            # Load inventory using the standard loader
            state.inventory = load_inventory(temp_path)
            state.inventory_filename = request.character_name or "Cached"
            state.inventory_csv_content = request.csv_content  # Keep for future caching
            
            return {
                "success": True,
                "item_count": len(state.inventory.items),
                "message": f"Restored {len(state.inventory.items)} items from cache"
            }
        finally:
            # Clean up temp file
            import os
            os.unlink(temp_path)
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.post("/api/upload/jobgifts")
async def upload_job_gifts(file: UploadFile = File(...)):
    """Upload a job gifts CSV file."""
    try:
        # Save to temp file
        temp_path = SCRIPT_DIR / f"temp_{file.filename}"
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)
        
        # Load job gifts
        state.job_gifts = load_job_gifts(str(temp_path))
        state.job_gifts_filename = file.filename
        
        # Clean up temp file
        temp_path.unlink()
        
        # Count jobs with JP
        jobs_with_jp = sum(1 for jg in state.job_gifts.gifts.values() if jg.jp_spent > 0)
        
        return {
            "success": True,
            "filename": file.filename,
            "jobs_with_jp": jobs_with_jp,
            "message": f"Loaded job gifts for {jobs_with_jp} jobs"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


class CachedJobGiftsRequest(BaseModel):
    """Request model for reloading cached job gifts."""
    gifts: Dict[str, Dict[str, Any]]


@app.post("/api/upload/jobgifts/reload")
async def reload_cached_job_gifts(request: CachedJobGiftsRequest):
    """
    Reload job gifts from cached data stored in browser localStorage.
    """
    try:
        if not request.gifts:
            return {
                "success": False,
                "error": "No job gifts provided in cache"
            }
        
        # Convert cached data back to JobGifts objects
        from job_gifts_loader import JobGifts
        
        gifts_dict = {}
        for job_code, gift_data in request.gifts.items():
            gifts_dict[job_code.upper()] = JobGifts(
                job=job_code.upper(),
                jp_spent=gift_data.get('jp_spent', 0),
                stats=gift_data.get('stats', {}),
            )
        
        state.job_gifts = JobGiftsCollection(gifts=gifts_dict)
        state.job_gifts_filename = "Cached"
        
        jobs_with_jp = sum(1 for jg in state.job_gifts.gifts.values() if jg.jp_spent > 0)
        
        return {
            "success": True,
            "jobs_with_jp": jobs_with_jp,
            "message": f"Restored job gifts for {jobs_with_jp} jobs from cache"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.get("/api/jobgifts")
async def get_job_gifts():
    """Get all job gifts data for caching."""
    if not state.job_gifts:
        return {"gifts": {}}
    
    # Serialize job gifts for caching
    gifts_data = {}
    for job_code, jg in state.job_gifts.gifts.items():
        gifts_data[job_code] = {
            "job": jg.job,
            "jp_spent": jg.jp_spent,
            "stats": jg.stats,
        }
    
    return {"gifts": gifts_data}


@app.get("/api/jobs")
async def get_jobs():
    """Get list of available jobs with JP info."""
    jobs = []
    for code in JOB_LIST:
        jp_spent = 0
        has_master = False
        
        if state.job_gifts and code.upper() in state.job_gifts.gifts:
            jg = state.job_gifts.gifts[code.upper()]
            jp_spent = jg.jp_spent
            has_master = jp_spent >= 2100
        
        jobs.append({
            "code": code,
            "name": f"{code}",
            "jp_spent": jp_spent,
            "has_master": has_master,
        })
    
    return {"jobs": jobs}


@app.get("/api/weapons/{job}")
async def get_weapons(job: str):
    """Get weapons available for a job."""
    if not state.inventory:
        raise HTTPException(status_code=400, detail="No inventory loaded")
    
    if job not in JOB_ENUM_MAP:
        raise HTTPException(status_code=400, detail=f"Invalid job: {job}")
    
    job_enum = JOB_ENUM_MAP[job]
    weapons = get_weapons_from_inventory(state.inventory, job_enum)
    
    # Format weapon data for frontend
    result = []
    for w in weapons:
        result.append({
            "name": w.get("Name", "Unknown"),
            "name2": w.get("Name2", w.get("Name", "Unknown")),
            "skill_type": w.get("Skill Type", "Unknown"),
            "damage": w.get("DMG", 0),
            "delay": w.get("Delay", 0),
            "item_level": w.get("Item Level", 0),
            "jobs": w.get("Jobs", []),
            "stats": {k: v for k, v in w.items() if k not in ["Name", "Name2", "Jobs", "Type", "Skill Type"]},
            "_raw": w,  # Include raw data for optimization
        })
    
    # Sort by item level descending, then by name
    result.sort(key=lambda x: (-x["item_level"], x["name"]))
    
    return {"weapons": result}


@app.get("/api/offhand/{job}")
async def get_offhand(job: str, main_weapon: str = None, main_skill: str = None):
    """Get off-hand items available for a job based on main weapon."""
    if not state.inventory:
        raise HTTPException(status_code=400, detail="No inventory loaded")
    
    if job not in JOB_ENUM_MAP:
        raise HTTPException(status_code=400, detail=f"Invalid job: {job}")
    
    job_enum = JOB_ENUM_MAP[job]
    
    # Build a mock main weapon dict for the function
    main_weapon_dict = None
    if main_skill:
        main_weapon_dict = {"Skill Type": main_skill}
    
    offhands = get_offhand_from_inventory(state.inventory, job_enum, main_weapon_dict)
    
    # Add Empty option
    empty = {"Name": "Empty", "Name2": "Empty", "Type": "None", "Jobs": all_jobs}
    
    result = [{"name": "Empty", "name2": "Empty", "type": "None", "_raw": empty}]
    
    for item in offhands:
        result.append({
            "name": item.get("Name", "Unknown"),
            "name2": item.get("Name2", item.get("Name", "Unknown")),
            "type": item.get("Type", "Unknown"),
            "skill_type": item.get("Skill Type", ""),
            "damage": item.get("DMG", 0),
            "delay": item.get("Delay", 0),
            "item_level": item.get("Item Level", 0),
            "stats": {k: v for k, v in item.items() if k not in ["Name", "Name2", "Jobs", "Type"]},
            "_raw": item,
        })
    
    return {"offhand": result}


@app.get("/api/weaponskills")
async def get_weaponskills(skill_type: str):
    """Get weaponskills for a weapon skill type."""
    weapon_type = SKILL_TO_WEAPON_TYPE.get(skill_type)
    
    if weapon_type is None:
        return {"weaponskills": []}
    
    ws_list = get_weaponskills_by_type(weapon_type)
    
    result = []
    for ws in ws_list:
        ws_type_str = "Physical"
        if ws.ws_type == WSType.MAGICAL:
            ws_type_str = "Magical"
        elif ws.ws_type == WSType.HYBRID:
            ws_type_str = "Hybrid"
        
        mod_str = "/".join(f"{k}:{v}%" for k, v in ws.stat_modifiers.items())
        
        result.append({
            "name": ws.name,
            "weapon_type": ws.weapon_type.value,
            "ws_type": ws_type_str,
            "hits": ws.hits,
            "ftp_replicating": ws.ftp_replicating,
            "can_crit": ws.can_crit,
            "stat_modifiers": ws.stat_modifiers,
            "skillchain": ws.skillchain,
            "mod_string": mod_str,
        })
    
    return {"weaponskills": result}


@app.get("/api/buffs")
async def get_buffs():
    """Get available buffs."""
    return {
        "haste": HASTE_BUFFS,
        "damage": DAMAGE_BUFFS,
        "accuracy": ACCURACY_BUFFS,
        "debuffs": DEBUFF_OPTIONS,
    }


@app.get("/api/targets")
async def get_targets():
    """Get available target presets."""
    result = []
    for key, data in TARGET_PRESETS.items():
        result.append({
            "id": key,
            "name": data["Name"],
            "level": data["Level"],
            "defense": data["Defense"],
            "evasion": data["Evasion"],
        })
    return {"targets": result}


@app.get("/api/tp-types")
async def get_tp_types():
    """Get available TP set types."""
    result = []
    for tp_type in TPSetType:
        result.append({
            "id": tp_type.name.lower(),
            "name": tp_type.value,
            "description": get_tp_profile_description(tp_type),
        })
    return {"tp_types": result}


@app.post("/api/optimize/ws", response_model=OptimizeResponse)
async def optimize_ws(request: OptimizeRequest):
    """Run weaponskill optimization."""
    if not state.inventory:
        return OptimizeResponse(
            success=False,
            optimization_type="ws",
            results=[],
            error="No inventory loaded"
        )
    
    try:
        # Validate job
        job_enum, error = get_job_enum_or_error(request.job, "ws")
        if error:
            return OptimizeResponse(success=False, optimization_type="ws", results=[], error=error)
        
        # Get weaponskill data
        ws_data = get_weaponskill(request.weaponskill)
        if not ws_data:
            return OptimizeResponse(
                success=False,
                optimization_type="ws",
                results=[],
                error=f"Weaponskill not found: {request.weaponskill}"
            )
        
        # Get job gifts and prepare buffs/target
        job_gifts = get_job_gifts_for_job(request.job)
        buffs_dict, abilities_dict, debuffs_info = convert_ui_buffs_to_wsdist(
            ui_buffs=request.buffs,
            abilities=request.abilities,
            food=request.food,
            debuffs=request.debuffs,
        )
        target_data = prepare_target_with_debuffs(request.target, debuffs_info)
        
        # Run optimization
        results = run_ws_optimization(
            inventory=state.inventory,
            job=job_enum,
            main_weapon=request.main_weapon,
            sub_weapon=request.sub_weapon,
            ws_data=ws_data,
            beam_width=10000,
            job_gifts=job_gifts,
            buffs=buffs_dict,
            abilities=abilities_dict,
            target_data=target_data,
            tp=request.min_tp,
            master_level=request.master_level,
            sub_job=request.sub_job,
        )
        
        # Format results
        formatted_results = []
        for rank, (candidate, damage) in enumerate(results[:10], 1):
            formatted_results.append(GearsetResult(
                rank=rank,
                score=candidate.score,
                damage=damage,
                gear=format_gear_dict(candidate),
            ))
        
        return OptimizeResponse(
            success=True,
            optimization_type="ws",
            results=formatted_results,
        )
    
    except Exception as e:
        return OptimizeResponse(
            success=False,
            optimization_type="ws",
            results=[],
            error=f"{str(e)}\n{traceback.format_exc()}"
        )


@app.post("/api/optimize/tp", response_model=OptimizeResponse)
async def optimize_tp(request: OptimizeRequest):
    """Run TP set optimization."""
    if not state.inventory:
        return OptimizeResponse(
            success=False,
            optimization_type="tp",
            results=[],
            error="No inventory loaded"
        )
    
    try:
        # Validate job
        job_enum, error = get_job_enum_or_error(request.job, "tp")
        if error:
            return OptimizeResponse(success=False, optimization_type="tp", results=[], error=error)
        
        # Map TP type
        tp_type_map = {
            "pure_tp": TPSetType.PURE_TP,
            "hybrid_tp": TPSetType.HYBRID_TP,
            "acc_tp": TPSetType.ACC_TP,
            "dt_tp": TPSetType.DT_TP,
            "refresh_tp": TPSetType.REFRESH_TP,
        }
        tp_type = tp_type_map.get(request.tp_type, TPSetType.PURE_TP)
        
        # Get job gifts and prepare buffs/target
        job_gifts = get_job_gifts_for_job(request.job)
        buffs_dict, abilities_dict, debuffs_info = convert_ui_buffs_to_wsdist(
            ui_buffs=request.buffs,
            abilities=request.abilities,
            food=request.food,
            debuffs=request.debuffs,
        )
        target_data = prepare_target_with_debuffs(request.target, debuffs_info)
        
        # Run optimization
        results = run_tp_optimization(
            inventory=state.inventory,
            job=job_enum,
            main_weapon=request.main_weapon,
            sub_weapon=request.sub_weapon,
            tp_type=tp_type,
            beam_width=10000,
            job_gifts=job_gifts,
            buffs=buffs_dict,
            abilities=abilities_dict,
            target_data=target_data,
            master_level=request.master_level,
            sub_job=request.sub_job,
        )
        
        # Format results
        formatted_results = []
        for rank, (candidate, metrics) in enumerate(results[:10], 1):
            formatted_results.append(GearsetResult(
                rank=rank,
                score=metrics.get("score", 0),
                time_to_ws=metrics.get("time_to_ws"),
                tp_per_round=metrics.get("tp_per_round"),
                dps=metrics.get("dps"),
                gear=format_gear_dict(candidate),
            ))
        
        return OptimizeResponse(
            success=True,
            optimization_type="tp",
            results=formatted_results,
        )
    
    except Exception as e:
        return OptimizeResponse(
            success=False,
            optimization_type="tp",
            results=[],
            error=f"{str(e)}\n{traceback.format_exc()}"
        )


# =============================================================================
# DT (Damage Taken / Survivability) Set Optimization
# =============================================================================

@app.get("/api/dt-types")
async def get_dt_types():
    """Get available DT set types."""
    result = []
    for dt_type in DTSetType:
        result.append({
            "id": dt_type.name.lower(),
            "name": dt_type.value,
            "description": get_dt_profile_description(dt_type),
        })
    return {"dt_types": result}


class DTOptimizeRequest(BaseModel):
    """Request model for DT optimization."""
    job: str
    dt_type: str = "pure_dt"
    main_weapon: Optional[Dict] = None
    sub_weapon: Optional[Dict] = None
    include_weapons: bool = False
    beam_width: int = 100
    # TP calculation parameters (optional - needed for TP metrics)
    sub_job: str = "war"
    master_level: int = 0
    target: str = "apex_leech"  # Default to leech for DT sets (lower evasion, common DT target)
    buffs: Dict[str, Any] = {}
    abilities: List[str] = []
    food: str = ""
    debuffs: List[str] = []


class DTGearsetResult(BaseModel):
    """Result model for a single DT gearset."""
    rank: int
    score: float
    dt_pct: float           # General DT %
    pdt_pct: float          # Physical DT %
    mdt_pct: float          # Magical DT %
    physical_reduction: float   # Total physical damage reduction %
    magical_reduction: float    # Total magical damage reduction %
    hp: int
    defense: int
    evasion: int
    magic_evasion: int
    refresh: int
    regen: int
    gear: Dict[str, Any]
    # TP metrics (calculated for all DT sets)
    time_to_ws: Optional[float] = None
    tp_per_round: Optional[float] = None
    dps: Optional[float] = None
    dt_capped: bool = False  # True if DT is at -50% cap
    # Fast Cast metrics
    fast_cast: Optional[int] = None  # Fast Cast % (0-80)
    fast_cast_capped: bool = False   # True if FC is at 80% cap


class DTOptimizeResponse(BaseModel):
    """Response model for DT optimization."""
    success: bool
    optimization_type: str = "dt"
    results: List[DTGearsetResult]
    error: Optional[str] = None


@app.post("/api/optimize/dt", response_model=DTOptimizeResponse)
async def optimize_dt(request: DTOptimizeRequest):
    """Run DT/survivability set optimization."""
    print(f"\n=== DT OPTIMIZATION REQUEST ===")
    print(f"Job: {request.job}")
    print(f"DT Type: {request.dt_type}")
    print(f"Main Weapon: {request.main_weapon}")
    print(f"Sub Weapon: {request.sub_weapon}")
    print(f"Include Weapons: {request.include_weapons}")
    print(f"Target: {request.target}")
    print(f"================================\n")
    
    if not state.inventory:
        return DTOptimizeResponse(
            success=False,
            results=[],
            error="No inventory loaded"
        )
    
    try:
        # Validate job
        job_enum, error = get_job_enum_or_error(request.job, "dt")
        if error:
            return DTOptimizeResponse(success=False, results=[], error=error)
        
        # Map DT type
        dt_type_map = {
            "pure_dt": DTSetType.PURE_DT,
            "dt_tp": DTSetType.DT_TP,
            "dt_refresh": DTSetType.DT_REFRESH,
            "dt_regen": DTSetType.DT_REGEN,
            "pdt_only": DTSetType.PDT_ONLY,
            "mdt_only": DTSetType.MDT_ONLY,
            "fast_cast": DTSetType.FAST_CAST,
            "generic_ws": DTSetType.GENERIC_WS,
        }
        dt_type = dt_type_map.get(request.dt_type.lower(), DTSetType.PURE_DT)
        
        # Get job gifts
        job_gifts = get_job_gifts_for_job(request.job)
        
        # Convert UI buffs to wsdist format for TP calculation
        buffs_dict = {}
        abilities_dict = {}
        debuffs_info = {"defense_down_pct": 0, "evasion_down": 0}
        
        if request.buffs or request.abilities or request.food or request.debuffs:
            buffs_dict, abilities_dict, debuffs_info = convert_ui_buffs_to_wsdist(
                ui_buffs=request.buffs,
                abilities=request.abilities,
                food=request.food,
                debuffs=request.debuffs,
            )
        
        # Get target data (can be None for DT)
        target_data = None
        if request.target and request.target in TARGET_PRESETS:
            target_data = prepare_target_with_debuffs(request.target, debuffs_info)
        
        # Run optimization
        results = run_dt_optimization(
            inventory=state.inventory,
            job=job_enum,
            dt_type=dt_type,
            main_weapon=request.main_weapon,
            sub_weapon=request.sub_weapon,
            beam_width=request.beam_width,
            include_weapons=request.include_weapons,
            # TP calculation parameters
            buffs=buffs_dict,
            abilities=abilities_dict,
            target_data=target_data,
            master_level=request.master_level,
            sub_job=request.sub_job,
            job_gifts=job_gifts,
        )
        
        # Format results
        formatted_results = []
        for rank, (candidate, metrics) in enumerate(results[:10], 1):
            formatted_results.append(DTGearsetResult(
                rank=rank,
                score=metrics.get("score", 0),
                dt_pct=metrics.get("dt_pct", 0),
                pdt_pct=metrics.get("pdt_pct", 0),
                mdt_pct=metrics.get("mdt_pct", 0),
                physical_reduction=metrics.get("physical_reduction", 0),
                magical_reduction=metrics.get("magical_reduction", 0),
                hp=int(metrics.get("hp", 0)),
                defense=int(metrics.get("defense", 0)),
                evasion=int(metrics.get("evasion", 0)),
                magic_evasion=int(metrics.get("magic_evasion", 0)),
                refresh=int(metrics.get("refresh", 0)),
                regen=int(metrics.get("regen", 0)),
                gear=format_gear_dict(candidate),
                # TP metrics
                time_to_ws=metrics.get("time_to_ws"),
                tp_per_round=metrics.get("tp_per_round"),
                dps=metrics.get("dps"),
                dt_capped=metrics.get("dt_capped", False),
                # Fast Cast metrics
                fast_cast=metrics.get("fast_cast"),
                fast_cast_capped=metrics.get("fast_cast_capped", False),
            ))
        
        return DTOptimizeResponse(
            success=True,
            results=formatted_results,
        )
    
    except Exception as e:
        return DTOptimizeResponse(
            success=False,
            results=[],
            error=f"{str(e)}\n{traceback.format_exc()}"
        )


# =============================================================================
# Full Buff/Debuff Definitions (matching wsdist)
# =============================================================================

BUFF_DEFINITIONS = {
    "brd": {
        "Honor March": {"magic_haste": 126/1024, "attack": 168, "accuracy": 42, "songs": 1},
        "Victory March": {"magic_haste": 163/1024, "songs": 1},
        "Advancing March": {"magic_haste": 108/1024, "songs": 1},
        "Minuet V": {"attack": 149, "songs": 1},
        "Minuet IV": {"attack": 137, "songs": 1},
        "Minuet III": {"attack": 121, "songs": 1},
        "Blade Madrigal": {"accuracy": 60, "songs": 1},
        "Sword Madrigal": {"accuracy": 45, "songs": 1},
        "Herculean Etude": {"STR": 15, "songs": 1},
        "Uncanny Etude": {"DEX": 15, "songs": 1},
        "Vital Etude": {"VIT": 15, "songs": 1},
        "Swift Etude": {"AGI": 15, "songs": 1},
        "Sage Etude": {"INT": 15, "songs": 1},
        "Logical Etude": {"MND": 15, "songs": 1},
        "Aria of Passion": {"pdl": 12, "songs": 1},
    },
    "cor": {
        "Chaos Roll XI": {"attack_pct": 0.3125},
        "Chaos Roll X": {"attack_pct": 0.1875},
        "Samurai Roll XI": {"store_tp": 40},
        "Samurai Roll X": {"store_tp": 24},
        "Fighter's Roll XI": {"double_attack": 15},
        "Fighter's Roll X": {"double_attack": 7},
        "Rogue's Roll XI": {"crit_rate": 14},
        "Rogue's Roll X": {"crit_rate": 8},
        "Hunter's Roll XI": {"accuracy": 50, "ranged_accuracy": 50},
        "Hunter's Roll X": {"accuracy": 30, "ranged_accuracy": 30},
        "Wizard's Roll XI": {"magic_attack": 30},
        "Tactician's Roll XI": {"regain": 40},
    },
    "geo": {
        "Geo-Fury": {"attack_pct": 0.347},
        "Indi-Fury": {"attack_pct": 0.20},
        "Geo-Precision": {"accuracy": 50},
        "Indi-Precision": {"accuracy": 30},
        "Geo-Haste": {"magic_haste": 299/1024},
        "Indi-Haste": {"magic_haste": 200/1024},
        "Geo-STR": {"STR": 25},
        "Geo-DEX": {"DEX": 25},
        "Geo-VIT": {"VIT": 25},
        "Geo-Acumen": {"magic_attack": 15},
        "Geo-Focus": {"magic_accuracy": 50},
        "Entrust Indi-Fury": {"attack_pct": 0.20},
        "Entrust Indi-Haste": {"magic_haste": 200/1024},
    },
    "whm": {
        "Haste": {"magic_haste": 150/1024},
        "Haste II": {"magic_haste": 307/1024},
        "Boost-STR": {"STR": 25},
        "Boost-DEX": {"DEX": 25},
        "Boost-VIT": {"VIT": 25},
        "Boost-AGI": {"AGI": 25},
        "Gain-STR": {"STR": 55},
        "Gain-DEX": {"DEX": 55},
        "Firestorm II": {"STR": 7},
        "Thunderstorm II": {"DEX": 7},
        "Sandstorm II": {"VIT": 7},
        "Shell V": {"mdt": -29},
    },
    "abilities": {
        "Berserk": {"attack_pct": 0.25, "job": "war"},
        "Warcry": {"attack": 0, "job": "war"},
        "Aggressor": {"accuracy": 25, "job": "war"},
        "Mighty Strikes": {"crit_rate": 100, "job": "war"},
        "Last Resort": {"attack_pct": 0.25, "job": "drk"},
        "Hasso": {"STR": 14, "ja_haste": 10, "accuracy": 10, "job": "sam"},
        "Meditate": {"tp": 0, "job": "sam"},
        "Sekkanoki": {"tp": 0, "job": "sam"},
        "Sange": {"daken": 100, "job": "nin"},
        "Innin": {"crit_rate": 20, "accuracy": 20, "job": "nin"},
        "Focus": {"crit_rate": 20, "accuracy": 100, "job": "mnk"},
        "Impetus": {"crit_rate": 50, "attack": 140, "job": "mnk"},
        "Footwork": {"kick_attacks": 20, "job": "mnk"},
        "Sharpshot": {"ranged_accuracy": 40, "job": "rng"},
        "Velocity Shot": {"ranged_attack_pct": 0.15, "job": "rng"},
        "Double Shot": {"double_shot": 40, "job": "rng"},
        "Triple Shot": {"triple_shot": 40, "job": "cor"},
        "Sneak Attack": {"job": "thf"},
        "Trick Attack": {"job": "thf"},
        "Conspirator": {"accuracy": 45, "job": "thf"},
    },
    "food": {
        "Grape Daifuku": {"STR": 7, "attack": 150, "accuracy": 60},
        "Sublime Sushi +1": {"STR": 8, "accuracy": 90, "attack": 0},
        "Red Curry Bun +1": {"STR": 9, "attack": 180, "accuracy": 0},
        "Miso Ramen +1": {"DEX": 8, "accuracy": 90, "ranged_accuracy": 90},
        "Custom Food": {"STR": 0, "DEX": 0, "attack": 0, "accuracy": 0},
    },
}

DEBUFF_DEFINITIONS = {
    "whm": {
        "Dia": {"defense_down_pct": 0.101},
        "Dia II": {"defense_down_pct": 0.152},
        "Dia III": {"defense_down_pct": 0.203},
    },
    "geo": {
        "Geo-Frailty": {"defense_down_pct": 0.148},
        "Indi-Frailty": {"defense_down_pct": 0.10},
        "Geo-Torpor": {"evasion_down": 50},
        "Geo-Malaise": {"magic_defense_down": 15},
        "Geo-Languor": {"magic_evasion_down": 50},
    },
    "cor": {
        "Light Shot": {"defense_down_pct": 0.027},
    },
    "misc": {
        "Angon": {"defense_down_pct": 0.20},
        "Armor Break": {"defense_down_pct": 0.25},
        "Box Step": {"defense_down_pct": 0.23},
        "Box Step (sub)": {"defense_down_pct": 0.13},
        "Corrosive Ooze": {"defense_down_pct": 0.33},
        "Distract III": {"evasion_down": 280},
        "Swooping Frenzy": {"defense_down_pct": 0.25, "magic_defense_down": 25},
    },
}

# =============================================================================
# Magic-Specific Buff Definitions
# =============================================================================

MAGIC_BUFF_ADDITIONS = {
    # COR magic rolls
    "cor_magic": {
        "Wizard's Roll XI": {"magic_attack": 50},
        "Wizard's Roll X": {"magic_attack": 30},
        "Warlock's Roll XI": {"magic_accuracy": 52},
        "Warlock's Roll X": {"magic_accuracy": 32},
    },
    # GEO magic bubbles
    "geo_magic": {
        "Geo-Acumen": {"magic_attack_pct": 35},  # 35% MAB
        "Indi-Acumen": {"magic_attack_pct": 20},
        "Geo-Focus": {"magic_accuracy": 75},
        "Indi-Focus": {"magic_accuracy": 45},
        "Geo-Languor": {"magic_evasion_down": 75},  # Target debuff
        "Indi-Languor": {"magic_evasion_down": 45},
        "Geo-Malaise": {"magic_defense_down": 35},  # Target debuff
        "Indi-Malaise": {"magic_defense_down": 20},
    },
    # SCH-specific abilities
    "sch": {
        "Ebullience": {"magic_damage_mult": 40},  # +40% magic damage on next spell
        "Immanence": {"skillchain_enabled": True},
        "Dark Arts": {"dark_magic_cast_time": -10, "dark_magic_recast": -10},
        "Light Arts": {"enhancing_cast_time": -10, "healing_cast_time": -10},
    },
    # Magic-specific food
    "food_magic": {
        "Tropical Crepe": {"INT": 8, "magic_attack": 60, "magic_accuracy": 60},
        "Pear Crepe": {"INT": 6, "magic_attack": 50, "magic_accuracy": 50},
        "Miso Ramen +1": {"DEX": 8, "accuracy": 90, "ranged_accuracy": 90, "magic_accuracy": 90},
        "Seafood Stew": {"INT": 6, "MND": 6, "magic_attack": 40},
        "Rolanberry Pie +1": {"INT": 7, "MP": 70},
    },
}

# Magic-specific debuffs on target
MAGIC_DEBUFF_DEFINITIONS = {
    "geo_magic_debuff": {
        "Geo-Languor": {"magic_evasion_down": 75},
        "Indi-Languor": {"magic_evasion_down": 45},
        "Geo-Malaise": {"magic_defense_down": 35},
        "Indi-Malaise": {"magic_defense_down": 20},
    },
    "rdm": {
        "Frazzle III": {"magic_evasion_down": 45},
        "Frazzle II": {"magic_evasion_down": 30},
        "Frazzle": {"magic_evasion_down": 15},
    },
}


@app.get("/api/buffs/full")
async def get_full_buffs():
    """Get complete buff/debuff definitions matching wsdist."""
    return {
        "buffs": BUFF_DEFINITIONS,
        "debuffs": DEBUFF_DEFINITIONS,
    }


class StatsRequest(BaseModel):
    job: str
    sub_job: str = "war"
    master_level: int = 0
    gearset: Dict[str, Dict[str, Any]]
    buffs: Dict[str, List[str]] = {}  # {"brd": ["Minuet V", "Honor March"], ...}
    abilities: List[str] = []
    food: str = ""
    target: str = "apex_toad"
    debuffs: List[str] = []


@app.post("/api/stats/calculate")
async def calculate_stats(request: StatsRequest):
    """Calculate full player stats for a gearset with buffs."""
    if not WSDIST_AVAILABLE:
        return {"error": "wsdist not available for stats calculation"}
    
    try:
        # Debug: Log what we received
        print("\n" + "="*60)
        print("STATS CALCULATION REQUEST")
        print("="*60)
        print(f"Job: {request.job}/{request.sub_job} ML{request.master_level}")
        print(f"Gearset slots received: {list(request.gearset.keys())}")
        for slot, item in request.gearset.items():
            if item:
                name = item.get("Name", item.get("name", "?"))
                has_stats = any(k in item for k in ["STR", "DEX", "Attack", "Accuracy"])
                print(f"  {slot}: {name} (has stats: {has_stats})")
        
        # Build a proper wsdist-format gearset with all required slots
        wsdist_gearset = {}
        required_slots = ["main", "sub", "ranged", "ammo", "head", "neck", "ear1", "ear2",
                         "body", "hands", "ring1", "ring2", "back", "waist", "legs", "feet"]
        
        # Default empty item
        empty_item = {"Name": "Empty", "Name2": "Empty", "Type": "None", "Jobs": all_jobs}
        
        # Build inventory lookup cache (Name2 -> wsdist_item)
        # This is built once and used for all slot lookups
        inventory_cache: Dict[str, Dict[str, Any]] = {}
        if state.inventory:
            for inv_item in state.inventory.items:
                # Build augment string for matching
                augment_str = ""
                if inv_item.rank > 0 and inv_item.has_path_augment:
                    for aug in inv_item.augments_raw:
                        if isinstance(aug, str) and aug.startswith("Path:"):
                            path_letter = aug.split(":")[1].strip()
                            augment_str = f"Path: {path_letter} R{inv_item.rank}"
                            break
                
                wsdist_item = to_wsdist_gear(inv_item, augment_str)
                if wsdist_item:
                    name = wsdist_item.get("Name", "")
                    name2 = wsdist_item.get("Name2", "")
                    # Store by both Name and Name2 for flexible lookup
                    if name2 and name2 not in inventory_cache:
                        inventory_cache[name2] = wsdist_item
                    if name and name not in inventory_cache:
                        inventory_cache[name] = wsdist_item
        
        def lookup_gear_from_inventory(item_name: str, item_name2: str = None) -> Optional[Dict[str, Any]]:
            """Look up full gear stats from inventory cache by name."""
            if item_name == "Empty":
                return None
            
            # Try Name2 first (more specific, includes augments)
            if item_name2 and item_name2 in inventory_cache:
                return inventory_cache[item_name2]
            
            # Fallback to Name
            if item_name in inventory_cache:
                return inventory_cache[item_name]
            
            return None
        
        for slot in required_slots:
            if slot in request.gearset and request.gearset[slot]:
                item = request.gearset[slot]
                # Normalize field names to what wsdist expects (capital letters)
                normalized = {}
                for key, value in item.items():
                    # Convert common lowercase keys to wsdist format
                    if key == "name":
                        normalized["Name"] = value
                    elif key == "name2":
                        normalized["Name2"] = value
                    elif key == "Type" or key == "type":
                        normalized["Type"] = value
                    elif key == "Skill Type" or key == "skill_type":
                        normalized["Skill Type"] = value
                    elif key == "DMG" or key == "dmg":
                        normalized["DMG"] = value
                    elif key == "Delay" or key == "delay":
                        normalized["Delay"] = value
                    else:
                        # Keep other keys as-is (they're likely already correct)
                        normalized[key] = value
                
                # Ensure required fields exist
                if "Name" not in normalized:
                    normalized["Name"] = item.get("name", "Empty")
                if "Name2" not in normalized:
                    normalized["Name2"] = item.get("name2", normalized.get("Name", "Empty"))
                if "Type" not in normalized:
                    normalized["Type"] = item.get("type", "None")
                if "Jobs" not in normalized:
                    normalized["Jobs"] = all_jobs
                
                # Skip empty items
                if normalized.get("Name") == "Empty" or normalized.get("name") == "Empty":
                    wsdist_gearset[slot] = empty_item.copy()
                else:
                    # Check if we have stats - if not, look up from inventory
                    has_stats = any(k in normalized for k in ["STR", "DEX", "VIT", "AGI", "INT", "MND", 
                                                               "Attack", "Accuracy", "DA", "TA",
                                                               "Magic Attack", "Magic Accuracy"])
                    if not has_stats:
                        # Try to look up full gear from inventory
                        inv_gear = lookup_gear_from_inventory(
                            normalized.get("Name", ""), 
                            normalized.get("Name2", "")
                        )
                        if inv_gear:
                            print(f"  Looked up {slot} from inventory: {inv_gear.get('Name2', inv_gear.get('Name'))}")
                            wsdist_gearset[slot] = inv_gear
                        else:
                            print(f"  Warning: Could not find {normalized.get('Name2', normalized.get('Name'))} in inventory")
                            wsdist_gearset[slot] = normalized
                    else:
                        wsdist_gearset[slot] = normalized
            else:
                wsdist_gearset[slot] = empty_item.copy()
        
        # Strip metadata from all gear items before passing to wsdist
        # wsdist iterates through all keys and tries to sum numeric values,
        # so we need to remove any non-numeric fields like _augments (a list)
        for slot in wsdist_gearset:
            wsdist_gearset[slot] = strip_gear_metadata(wsdist_gearset[slot])
        
        # Build buffs dict for wsdist using the convert function
        buffs_dict, abilities_dict, _ = convert_ui_buffs_to_wsdist(
            ui_buffs=request.buffs,
            abilities=request.abilities,
            food=request.food,
            debuffs=request.debuffs,
        )
        
        # Create player
        player = create_player(
            main_job=request.job.lower(),
            sub_job=request.sub_job.lower(),
            master_level=request.master_level,
            gearset=wsdist_gearset,
            buffs=buffs_dict,
            abilities=abilities_dict,
        )
        
        # Debug: Show key player stats
        print(f"\nPlayer stats created:")
        print(f"  STR: {player.stats.get('STR', 'N/A')}")
        print(f"  Attack1: {player.stats.get('Attack1', 'N/A')}")
        print(f"  Accuracy1: {player.stats.get('Accuracy1', 'N/A')}")
        print(f"  DA: {player.stats.get('DA', 'N/A')}")
        print(f"  Store TP: {player.stats.get('Store TP', 'N/A')}")
        
        # Get job gifts if available
        jp_spent = 0
        if state.job_gifts and request.job.upper() in state.job_gifts.gifts:
            jg = state.job_gifts.gifts[request.job.upper()]
            jp_spent = jg.jp_spent
            apply_job_gifts_to_player(player, jg)
        
        # Get target for accuracy calculation
        target_data = TARGET_PRESETS.get(request.target, TARGET_PRESETS["apex_toad"]).copy()
        target_data["Base Defense"] = target_data.get("Defense", 1500)
        
        # Apply debuffs to target
        total_def_down = 0
        total_eva_down = 0
        for debuff in request.debuffs:
            for category in DEBUFF_DEFINITIONS.values():
                if debuff in category:
                    d = category[debuff]
                    total_def_down += d.get("defense_down_pct", 0)
                    total_eva_down += d.get("evasion_down", 0)
        
        target_defense = target_data["Defense"] * (1 - min(total_def_down, 0.5))
        target_evasion = target_data["Evasion"] - total_eva_down
        
        # Calculate accuracy components
        main_skill = wsdist_gearset.get("main", {}).get("Skill Type", "Sword")
        skill_name = f"{main_skill} Skill"
        skill_level = player.stats.get(skill_name, 0)
        
        # DEX contribution (0.75 per DEX)
        dex = player.stats.get("DEX", 0)
        acc_from_dex = int(0.75 * dex)
        
        # Skill contribution
        def get_skill_accuracy(skill):
            acc = 0
            if skill > 200:
                acc += int((min(skill, 400) - 200) * 0.9) + 200
            else:
                acc += skill
            if skill > 400:
                acc += int((min(skill, 600) - 400) * 0.8)
            if skill > 600:
                acc += int((skill - 600) * 0.9)
            return acc
        
        acc_from_skill = get_skill_accuracy(skill_level)
        
        # Gear accuracy (from player stats, already includes gear)
        acc_from_gear = player.stats.get("Accuracy", 0)
        
        # Buff accuracy
        acc_from_buffs = 0
        for source in buffs_dict.values():
            acc_from_buffs += source.get("Accuracy", 0)
        
        # JP accuracy (simplified)
        acc_from_jp = min(jp_spent // 100, 36) if jp_spent > 0 else 0
        
        total_accuracy = player.stats.get("Accuracy1", 0)
        
        # Hit rate calculation
        acc_diff = total_accuracy - target_evasion
        if acc_diff >= 200:
            hit_rate = 0.95
        elif acc_diff <= -200:
            hit_rate = 0.20
        else:
            hit_rate = 0.75 + (acc_diff * 0.001)
            hit_rate = max(0.20, min(0.95, hit_rate))
        
        # Format stats for response
        # Note: Frontend expects percentage stats in basis points (1200 = 12%)
        # wsdist stores DA/TA/Crit as integers (12 = 12%), so multiply by 100
        # Haste stats are decimals (0.25 = 25%), multiply by 1024 for /1024 format
        stats_response = {
            "job": request.job.upper(),
            "sub_job": request.sub_job.upper(),
            "master_level": request.master_level,
            "jp_spent": jp_spent,
            
            "primary_stats": {
                "STR": int(player.stats.get("STR", 0)),
                "DEX": int(player.stats.get("DEX", 0)),
                "VIT": int(player.stats.get("VIT", 0)),
                "AGI": int(player.stats.get("AGI", 0)),
                "INT": int(player.stats.get("INT", 0)),
                "MND": int(player.stats.get("MND", 0)),
                "CHR": int(player.stats.get("CHR", 0)),
            },
            
            "tp_stats": {
                # Store TP is an integer
                "store_tp": int(player.stats.get("Store TP", 0)),
                # Gear Haste is a decimal (0.25 = 25%), frontend does /100 so send 2500 for 25%
                "gear_haste": int(player.stats.get("Gear Haste", 0) * 10000),
                # Magic Haste is a decimal
                "magic_haste": int(player.stats.get("Magic Haste", 0) * 10000),
                # JA Haste is a decimal
                "ja_haste": int(player.stats.get("JA Haste", 0) * 10000),
                # Dual Wield is an integer percent in wsdist, multiply by 100 for basis points
                "dual_wield": int(player.stats.get("Dual Wield", 0) * 100),
                # DA/TA/QA are integer percents in wsdist, multiply by 100 for basis points
                "double_attack": int(player.stats.get("DA", 0) * 100),
                "triple_attack": int(player.stats.get("TA", 0) * 100),
                "quad_attack": int(player.stats.get("QA", 0) * 100),
                "martial_arts": int(player.stats.get("Martial Arts", 0)),
            },
            
            "offensive_stats": {
                "accuracy": int(player.stats.get("Accuracy1", 0)),
                "accuracy2": int(player.stats.get("Accuracy2", 0)),
                "attack": int(player.stats.get("Attack1", 0)),
                "attack2": int(player.stats.get("Attack2", 0)),
                # Crit Rate is an integer percent, multiply by 100 for basis points
                "crit_rate": int(player.stats.get("Crit Rate", 0) * 100),
                # Crit Damage is an integer percent
                "crit_damage": int(player.stats.get("Crit Damage", 0) * 100),
                # WS Damage is an integer percent
                "ws_damage": int(player.stats.get("Weapon Skill Damage", 0) * 100),
                # PDL is an integer percent (PDL Trait + PDL gear)
                "pdl": int((player.stats.get("PDL Trait", 0) + player.stats.get("PDL", 0)) * 100),
                "dmg1": int(player.stats.get("DMG1", 0)),
                "dmg2": int(player.stats.get("DMG2", 0)),
                "delay1": int(player.stats.get("Delay1", 0)),
                "delay2": int(player.stats.get("Delay2", 0)),
            },
            
            "defensive_stats": {
                "hp": int(player.stats.get("HP", 0)),
                "mp": int(player.stats.get("MP", 0)),
                "defense": int(player.stats.get("Defense", 0)),
                "evasion": int(player.stats.get("Evasion", 0)),
                # DT stats are integer percents (negative values), multiply by 100
                "pdt": int(player.stats.get("PDT", 0) * 100),
                "mdt": int(player.stats.get("MDT", 0) * 100),
                "dt": int(player.stats.get("DT", 0) * 100),
                "magic_evasion": int(player.stats.get("Magic Evasion", 0)),
            },
            
            "accuracy_breakdown": {
                "from_dex": acc_from_dex,
                "from_skill": acc_from_skill,
                "skill_level": skill_level,
                "skill_type": main_skill,
                "from_gear": acc_from_gear - acc_from_buffs,
                "from_jp": acc_from_jp,
                "from_buffs": acc_from_buffs,
                "total": total_accuracy,
            },
            
            "vs_target": {
                "target_name": target_data.get("Name", "Unknown"),
                "target_level": target_data.get("Level", 0),
                "target_defense": int(target_defense),
                "target_evasion": int(target_evasion),
                "acc_differential": int(total_accuracy - target_evasion),
                "hit_rate": round(hit_rate * 100, 1),
                "ws_hit_rate": round(min(hit_rate + 0.50, 0.99 if hit_rate < 0.95 else 0.95) * 100, 1),
                "acc_capped": hit_rate >= 0.95,
            },
        }
        
        return {"success": True, "stats": stats_response}
        
    except Exception as e:
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


@app.get("/api/inventory")
async def get_inventory(slot: str = None, job: str = None, show_all: bool = False, search: str = None):
    """Get inventory items, optionally filtered by slot and job.
    
    Args:
        slot: Filter by equipment slot
        job: Filter by job that can equip
        show_all: If true, show all items from database (not just inventory)
        search: Search string to filter items by name
    """
    items = []
    
    if show_all:
        # Get all items from the database
        try:
            db = get_database()
            if not db.items:
                return {"items": [], "error": "Item database not loaded"}
            
            from models import Container
            
            for item_id, item_base in db.items.items():
                try:
                    # Convert to wsdist format - create minimal ItemInstance
                    # Use Container.INVENTORY (0) as default container
                    inv_item = ItemInstance(
                        base=item_base,
                        container=Container(0),  # Inventory container
                        slot=0,
                        count=1,
                    )
                    wsdist_item = to_wsdist_gear(inv_item)
                    if not wsdist_item:
                        continue
                    
                    # Filter by job if specified
                    if job and job.upper() in JOB_ENUM_MAP:
                        job_enum = JOB_ENUM_MAP[job.upper()]
                        if not item_base.can_equip(job_enum):
                            continue
                    
                    # Filter by search string
                    if search:
                        search_lower = search.lower()
                        name_match = search_lower in item_base.name.lower()
                        name2_match = search_lower in wsdist_item.get("Name2", "").lower()
                        if not name_match and not name2_match:
                            continue
                    
                    items.append({
                        "id": item_base.id,
                        "name": item_base.name,
                        "name2": wsdist_item.get("Name2", item_base.name),
                        "type": wsdist_item.get("Type", "Unknown"),
                        "slot": wsdist_item.get("Slot", "Unknown"),
                        "item_level": wsdist_item.get("Item Level", 0),
                        "jobs": wsdist_item.get("Jobs", []),
                        "stats": {k: v for k, v in wsdist_item.items() 
                                 if k not in ["Name", "Name2", "Jobs", "Type", "Slot"]},
                    })
                except Exception:
                    # Skip items that fail to convert
                    continue
        except Exception as e:
            import traceback
            return {"items": [], "error": f"Failed to load item database: {str(e)}", "trace": traceback.format_exc()}
    else:
        # Return items from loaded inventory
        if not state.inventory:
            return {"items": [], "error": "No inventory loaded"}
        
        for item in state.inventory.items:
            # Convert to wsdist format to get stats
            wsdist_item = to_wsdist_gear(item)
            if not wsdist_item:
                continue
            
            # Filter by job if specified
            if job and job.upper() in JOB_ENUM_MAP:
                job_enum = JOB_ENUM_MAP[job.upper()]
                if not item.base.can_equip(job_enum):
                    continue
            
            # Filter by search string
            if search:
                search_lower = search.lower()
                name_match = search_lower in item.base.name.lower()
                name2_match = search_lower in wsdist_item.get("Name2", "").lower()
                if not name_match and not name2_match:
                    continue
            
            items.append({
                "id": item.base.id,
                "name": item.base.name,
                "name2": wsdist_item.get("Name2", item.base.name),
                "type": wsdist_item.get("Type", "Unknown"),
                "slot": wsdist_item.get("Slot", "Unknown"),
                "item_level": wsdist_item.get("Item Level", 0),
                "jobs": wsdist_item.get("Jobs", []),
                "stats": {k: v for k, v in wsdist_item.items() 
                         if k not in ["Name", "Name2", "Jobs", "Type", "Slot"]},
            })
    
    # Sort by item level descending
    items.sort(key=lambda x: (-x["item_level"], x["name"]))
    
    return {"items": items, "count": len(items)}


@app.get("/api/item/{item_id}")
async def get_item(item_id: int):
    """Get a single item by ID from the database."""
    try:
        from models import Container
        
        db = get_database()
        item_base = db.get_item(item_id)
        if not item_base:
            return {"error": f"Item {item_id} not found"}
        
        inv_item = ItemInstance(
            base=item_base,
            container=Container(0),
            slot=0,
            count=1,
        )
        wsdist_item = to_wsdist_gear(inv_item)
        if not wsdist_item:
            return {"error": f"Could not convert item {item_id}"}
        
        return {
            "id": item_base.id,
            "name": item_base.name,
            "name2": wsdist_item.get("Name2", item_base.name),
            "type": wsdist_item.get("Type", "Unknown"),
            "slot": wsdist_item.get("Slot", "Unknown"),
            "item_level": wsdist_item.get("Item Level", 0),
            "jobs": wsdist_item.get("Jobs", []),
            "stats": {k: v for k, v in wsdist_item.items() 
                     if k not in ["Name", "Name2", "Jobs", "Type", "Slot"]},
        }
    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()}


@app.get("/api/inventory/search")
async def search_inventory(q: str, slot: str = None, limit: int = 15):
    """
    Search inventory items by name with optional slot filtering.
    Returns full wsdist item data suitable for simulation.
    
    Args:
        q: Search query string (minimum 2 characters)
        slot: Filter by slot type: main, sub, range, ammo (optional)
        limit: Maximum number of results to return (default 15)
    """
    from models import Slot, SLOT_BITMASK
    
    if not state.inventory:
        return {"items": [], "error": "No inventory loaded"}
    
    if len(q) < 2:
        return {"items": [], "error": "Search query must be at least 2 characters"}
    
    # Map slot names to slot masks for filtering
    slot_masks = {
        'main': SLOT_BITMASK.get(Slot.MAIN, 0),
        'sub': SLOT_BITMASK.get(Slot.SUB, 0),
        'range': SLOT_BITMASK.get(Slot.RANGE, 0),
        'ranged': SLOT_BITMASK.get(Slot.RANGE, 0),
        'ammo': SLOT_BITMASK.get(Slot.AMMO, 0),
    }
    
    target_mask = slot_masks.get(slot.lower()) if slot else None
    
    items = []
    search_lower = q.lower()
    
    for item in state.inventory.items:
        # Convert to wsdist format
        wsdist_item = to_wsdist_gear(item)
        if not wsdist_item:
            continue
        
        # Filter by slot if specified
        if target_mask and not (item.base.slots & target_mask):
            continue
        
        # Filter by search string
        name_match = search_lower in item.base.name.lower()
        name2_match = search_lower in wsdist_item.get("Name2", "").lower()
        if not name_match and not name2_match:
            continue
        
        # Build item data - include full wsdist data for simulation
        item_data = {
            "id": item.base.id,
            "name": item.base.name,
            "Name": item.base.name,  # Include wsdist format
            "Name2": wsdist_item.get("Name2", item.base.name),
            "type": wsdist_item.get("Type", "Unknown"),
            "Type": wsdist_item.get("Type", "Unknown"),
            "slot": wsdist_item.get("Slot", "Unknown"),
            "item_level": wsdist_item.get("Item Level", 0),
            "jobs": wsdist_item.get("Jobs", []),
            "Jobs": wsdist_item.get("Jobs", []),
            # Include key weapon stats
            "damage": wsdist_item.get("Damage", wsdist_item.get("DMG", 0)),
            "Damage": wsdist_item.get("Damage", wsdist_item.get("DMG", 0)),
            "delay": wsdist_item.get("Delay", 0),
            "Delay": wsdist_item.get("Delay", 0),
            "skill": wsdist_item.get("Skill Type", ""),
            "Skill Type": wsdist_item.get("Skill Type", ""),
            # Include raw wsdist dict for simulation (same as weapons endpoint)
            "_raw": wsdist_item,
        }
        
        # Add all other stats from wsdist for simulation use
        for k, v in wsdist_item.items():
            if k not in item_data:
                item_data[k] = v
        
        items.append(item_data)
        
        if len(items) >= limit:
            break
    
    # Sort by item level descending, then by name
    items.sort(key=lambda x: (-x.get("item_level", 0), x.get("name", "")))
    
    return {"items": items, "count": len(items)}


# =============================================================================
# Magic API Endpoints
# =============================================================================

@app.get("/api/spells")
async def get_spells():
    """
    Get all available spells grouped by category.
    
    Returns a dict with:
    - categories: List of category info with spell names
    - popular: List of popular nuke spell names for quick-select
    - all_spells: Dict of spell_name -> basic spell info
    """
    if not MAGIC_AVAILABLE:
        return {"error": "Magic modules not available", "categories": [], "popular": [], "all_spells": {}, "count": 0}
    
    # Build category list
    categories = []
    for cat_id, cat_data in SPELL_CATEGORIES.items():
        # Filter to only spells that exist in database
        valid_spells = [s for s in cat_data["spells"] if s in ALL_SPELLS]
        if valid_spells:
            categories.append({
                "id": cat_data["id"],
                "name": cat_data["name"],
                "spells": valid_spells,
            })
    
    # Build simplified spell info dict
    all_spells_info = {}
    for name, spell in ALL_SPELLS.items():
        all_spells_info[name] = {
            "name": spell.name,
            "element": spell.element.name if hasattr(spell.element, 'name') else str(spell.element),
            "magic_type": spell.magic_type.name if hasattr(spell.magic_type, 'name') else str(spell.magic_type),
            "tier": spell.tier,
            "mp_cost": spell.mp_cost,
            "is_aoe": spell.is_aoe,
        }
    
    # Filter popular nukes to only those in database
    popular = [s for s in POPULAR_NUKES if s in ALL_SPELLS]
    
    return {
        "categories": categories,
        "popular": popular,
        "all_spells": all_spells_info,
        "count": len(ALL_SPELLS),
    }


@app.get("/api/spells/categories")
async def get_spell_categories():
    """Get list of spell categories."""
    categories = []
    for cat_id, cat_data in SPELL_CATEGORIES.items():
        categories.append({
            "id": cat_data["id"],
            "name": cat_data["name"],
            "spell_count": len(cat_data["spells"]),
        })
    return {"categories": categories}


@app.get("/api/spells/category/{category_id}")
async def get_spells_by_category(category_id: str):
    """Get all spells in a specific category."""
    if not MAGIC_AVAILABLE:
        raise HTTPException(status_code=503, detail="Magic modules not available")
    
    if category_id not in SPELL_CATEGORIES:
        raise HTTPException(status_code=404, detail=f"Category not found: {category_id}")
    
    cat_data = SPELL_CATEGORIES[category_id]
    spells = []
    
    for spell_name in cat_data["spells"]:
        if spell_name in ALL_SPELLS:
            spell = ALL_SPELLS[spell_name]
            spells.append({
                "name": spell.name,
                "element": spell.element.name,
                "magic_type": spell.magic_type.name,
                "tier": spell.tier,
                "mp_cost": spell.mp_cost,
                "cast_time": spell.cast_time,
                "is_aoe": spell.is_aoe,
            })
    
    return {
        "category": {
            "id": cat_data["id"],
            "name": cat_data["name"],
        },
        "spells": spells,
    }


@app.get("/api/spell/{spell_name}")
async def get_spell_details(spell_name: str):
    """Get detailed information for a specific spell."""
    if not MAGIC_AVAILABLE:
        raise HTTPException(status_code=503, detail="Magic modules not available")
    
    spell = get_spell(spell_name)
    if spell is None:
        raise HTTPException(status_code=404, detail=f"Spell not found: {spell_name}")
    
    # Get valid optimization types for this spell
    valid_types = get_valid_optimization_types(spell_name)
    valid_type_names = [t.value for t in valid_types]
    
    # Check if MB is relevant
    mb_relevant = is_burst_relevant(spell_name)
    
    return {
        "name": spell.name,
        "element": spell.element.name,
        "magic_type": spell.magic_type.name,
        "skill_type": spell.skill_type,
        "tier": spell.tier,
        "mp_cost": spell.mp_cost,
        "cast_time": spell.cast_time,
        "recast_time": spell.recast_time,
        "is_aoe": spell.is_aoe,
        "base_v": spell.base_v,
        "dint_cap": spell.dint_cap,
        "m_values": {str(k): v for k, v in spell.m_values.items()},
        "properties": spell.properties,
        "valid_optimization_types": valid_type_names,
        "magic_burst_relevant": mb_relevant,
    }


@app.get("/api/magic/optimization-types")
async def get_magic_optimization_types(spell_name: str = None):
    """
    Get valid optimization types, optionally filtered by spell.
    
    Query params:
        spell_name: If provided, returns only valid types for that spell
    """
    # Define all types with descriptions
    all_types = {
        "damage": {
            "id": "damage",
            "name": "Damage",
            "description": "Maximize magic damage output (INT, MAB, Magic Damage)"
        },
        "accuracy": {
            "id": "accuracy",
            "name": "Accuracy",
            "description": "Maximize magic accuracy for landing spells (M.Acc, Skill, INT/MND)"
        },
        "burst": {
            "id": "burst",
            "name": "Magic Burst",
            "description": "Maximize magic burst damage (MBB, MBB II, MAB)"
        },
        "potency": {
            "id": "potency",
            "name": "Potency",
            "description": "Maximize spell effect potency (Skill, Effect+, Duration)"
        },
    }
    
    if spell_name and MAGIC_AVAILABLE:
        valid_types = get_valid_optimization_types(spell_name)
        valid_type_ids = [t.value for t in valid_types]
        return {
            "spell_name": spell_name,
            "types": [all_types[t] for t in valid_type_ids if t in all_types]
        }
    
    return {"types": list(all_types.values())}


@app.get("/api/magic/targets")
async def get_magic_targets():
    """Get available magic target presets."""
    targets = []
    for target_id, data in MAGIC_TARGET_PRESETS.items():
        targets.append(data)
    return {"targets": targets}


@app.get("/api/magic/buffs")
async def get_magic_buffs():
    """Get magic-specific buff and debuff definitions."""
    return {
        "buffs": MAGIC_BUFF_ADDITIONS,
        "debuffs": MAGIC_DEBUFF_DEFINITIONS,
    }


@app.post("/api/optimize/magic", response_model=MagicOptimizeResponse)
async def optimize_magic(request: MagicOptimizeRequest):
    """
    Run magic gear optimization.
    
    This endpoint:
    1. Validates the spell and job
    2. Creates an optimization profile based on the optimization_type
    3. Runs beam search to find candidate gear sets
    4. Evaluates candidates with magic simulation
    5. Returns ranked results with gear and stats
    """
    if not MAGIC_AVAILABLE:
        return MagicOptimizeResponse(
            success=False,
            spell_name=request.spell_name,
            optimization_type=request.optimization_type,
            magic_burst=request.magic_burst,
            target=request.target,
            results=[],
            error="Magic modules not available"
        )
    
    if not state.inventory:
        return MagicOptimizeResponse(
            success=False,
            spell_name=request.spell_name,
            optimization_type=request.optimization_type,
            magic_burst=request.magic_burst,
            target=request.target,
            results=[],
            error="No inventory loaded"
        )
    
    try:
        # Map job string to enum
        job_enum = JOB_ENUM_MAP.get(request.job.upper())
        if not job_enum:
            return MagicOptimizeResponse(
                success=False,
                spell_name=request.spell_name,
                optimization_type=request.optimization_type,
                magic_burst=request.magic_burst,
                target=request.target,
                results=[],
                error=f"Invalid job: {request.job}"
            )
        
        # Map optimization type string to enum
        opt_type_map = {
            "damage": MagicOptimizationType.DAMAGE,
            "accuracy": MagicOptimizationType.ACCURACY,
            "burst": MagicOptimizationType.BURST_DAMAGE,
            "potency": MagicOptimizationType.POTENCY,
        }
        opt_type = opt_type_map.get(request.optimization_type.lower(), MagicOptimizationType.DAMAGE)
        
        # Get target stats
        target = MAGIC_TARGETS.get(request.target, MAGIC_TARGETS.get('apex_mob'))
        if target is None:
            # Fallback to creating a basic target from presets
            target_preset = MAGIC_TARGET_PRESETS.get(request.target, MAGIC_TARGET_PRESETS['apex_mob'])
            target = MagicTargetStats(
                int_stat=target_preset['int_stat'],
                mnd_stat=target_preset['mnd_stat'],
                magic_evasion=target_preset['magic_evasion'],
                magic_defense_bonus=target_preset['magic_defense_bonus'],
            )
        
        # Apply magic debuffs to target if any
        total_meva_down = 0
        total_mdef_down = 0
        for debuff in request.debuffs:
            for category in MAGIC_DEBUFF_DEFINITIONS.values():
                if debuff in category:
                    d = category[debuff]
                    total_meva_down += d.get("magic_evasion_down", 0)
                    total_mdef_down += d.get("magic_defense_down", 0)
        
        # Create modified target with debuffs applied
        if total_meva_down > 0 or total_mdef_down > 0:
            target = MagicTargetStats(
                int_stat=target.int_stat,
                mnd_stat=target.mnd_stat,
                magic_evasion=max(0, target.magic_evasion - total_meva_down),
                magic_defense_bonus=max(0, target.magic_defense_bonus - total_mdef_down),
            )
        
        # Get job gifts if available
        job_gifts = None
        if state.job_gifts and request.job.upper() in state.job_gifts.gifts:
            job_gifts = state.job_gifts.gifts[request.job.upper()]
        
        # Build fixed_gear from weapons when not optimizing weapons
        fixed_gear = None
        if not request.include_weapons and (request.main_weapon or request.sub_weapon):
            fixed_gear = {}
            if request.main_weapon and request.main_weapon.get("Name", "Empty") != "Empty":
                fixed_gear["main"] = request.main_weapon
            if request.sub_weapon and request.sub_weapon.get("Name", "Empty") != "Empty":
                fixed_gear["sub"] = request.sub_weapon
        
        # Convert UI buffs to stat bonuses
        # Food may be in buffs.food as a string
        food = request.buffs.get("food", "") if isinstance(request.buffs.get("food"), str) else ""
        buff_bonuses = convert_magic_buffs_to_caster_stats(request.buffs, food=food)
        
        # Debug: Print target info
        print(f"\n[DEBUG API] Magic Optimization Request:")
        print(f"  request.target = '{request.target}'")
        print(f"  Target resolved to: magic_evasion={target.magic_evasion}, int={target.int_stat}, mnd={target.mnd_stat}")
        print(f"  Optimization type: {opt_type}")
        print(f"  Available MAGIC_TARGETS keys: {list(MAGIC_TARGETS.keys())}")
        
        # Run optimization
        results = run_magic_optimization(
            inventory=state.inventory,
            job=job_enum,
            spell_name=request.spell_name,
            optimization_type=opt_type,
            target=target,
            magic_burst=request.magic_burst,
            skillchain_steps=request.skillchain_steps,
            include_weapons=request.include_weapons,
            fixed_gear=fixed_gear,
            beam_width=request.beam_width,
            job_gifts=job_gifts,
            buff_bonuses=buff_bonuses,
        )
        
        # Extract stratification info from results
        stratification_note = get_stratification_note(results)
        evaluated_target_name = None
        if results and hasattr(results[0][0], '_eval_target'):
            evaluated_target_name = get_target_name(results[0][0]._eval_target)
        
        # Helper function to create a unique key for a gear set
        def gear_set_key(candidate):
            """Create a unique string key for a gear set based on actual gear names."""
            slots = ['main', 'sub', 'ranged', 'ammo', 'head', 'neck', 'ear1', 'ear2',
                     'body', 'hands', 'ring1', 'ring2', 'back', 'waist', 'legs', 'feet']
            items = []
            for slot in slots:
                if slot in candidate.gear:
                    item = candidate.gear[slot]
                    name = item.get("Name2", item.get("Name", "Empty"))
                    items.append(f"{slot}:{name}")
                else:
                    items.append(f"{slot}:Empty")
            return "|".join(items)
        
        # Deduplicate results - keep only unique gear sets
        seen_sets = set()
        unique_results = []
        for candidate, score in results:
            key = gear_set_key(candidate)
            if key not in seen_sets:
                seen_sets.add(key)
                unique_results.append((candidate, score))
        
        # Format results (up to 10 unique sets)
        formatted_results = []
        
        # Get job preset for calculating total values
        from magic_optimizer import get_job_preset, apply_job_gifts_to_magic, gear_to_caster_stats
        base_preset = get_job_preset(job_enum)
        job_preset, job_gift_bonuses_calc = apply_job_gifts_to_magic(base_preset, job_gifts)
        
        for rank, (candidate, score) in enumerate(unique_results[:10], 1):
            # Build gear dict (include _augments for Lua output)
            gear_dict = {}
            for slot, item in candidate.gear.items():
                gear_dict[slot] = {
                    "name": item.get("Name", "Empty"),
                    "name2": item.get("Name2", item.get("Name", "Empty")),
                    "_augments": item.get("_augments"),  # For Lua output
                }
            
            # Create CasterStats to get TOTAL values (job preset + gear + gifts)
            caster = gear_to_caster_stats(
                candidate.stats,
                job_preset,
                sub_magic_accuracy_skill=candidate.sub_magic_accuracy_skill,
                job_gift_bonuses=job_gift_bonuses_calc,
            )
            
            # Apply buff bonuses if provided
            if buff_bonuses:
                caster.int_stat += buff_bonuses.get("INT", 0)
                caster.mnd_stat += buff_bonuses.get("MND", 0)
                caster.mab += buff_bonuses.get("magic_attack", 0)
                caster.magic_accuracy += buff_bonuses.get("magic_accuracy", 0)
            
            # Build stats summary with TOTAL values (job preset + gear + gifts)
            stats_summary = {
                "INT": caster.int_stat,  # Total INT
                "MND": caster.mnd_stat,  # Total MND
                "magic_attack": caster.mab,  # Total MAB
                "magic_damage": caster.magic_damage,  # Total magic damage
                "magic_accuracy": caster.magic_accuracy,  # Total magic accuracy
                "magic_burst_bonus": candidate.stats.magic_burst_bonus,  # Gear only (trait added separately)
                "magic_burst_damage_ii": candidate.stats.magic_burst_damage_ii,
                "elemental_magic_skill": caster.elemental_magic_skill,  # Total skill
                "dark_magic_skill": caster.dark_magic_skill,  # Total skill
                "enfeebling_magic_skill": caster.enfeebling_magic_skill,  # Total skill
                "enhancing_magic_skill": caster.enhancing_magic_skill,  # Total skill
                "fast_cast": candidate.stats.fast_cast,  # Keep as gear value (basis points)
                # Also include gear-only values for reference
                "gear_INT": candidate.stats.INT,
                "gear_MND": candidate.stats.MND,
                "gear_magic_attack": candidate.stats.magic_attack,
                "gear_enfeebling_skill": candidate.stats.enfeebling_magic_skill,
            }
            
            # Get evaluation details from the candidate (stored during optimization)
            eval_details = get_evaluation_details(candidate)
            
            # Use stored hit_rate if available, otherwise calculate it
            if 'hit_rate' in eval_details:
                calculated_hit_rate = eval_details['hit_rate']
            else:
                # Fallback: Calculate hit_rate against the original requested target
                from magic_formulas import calculate_dstat_bonus, calculate_magic_accuracy, calculate_magic_hit_rate
                
                spell = get_spell(request.spell_name)
                if spell:
                    # Get relevant stat based on spell type
                    if spell.magic_type in [MagicType.DIVINE, MagicType.ENFEEBLING_MND, MagicType.HEALING]:
                        caster_stat = caster.mnd_stat
                        target_stat = target.mnd_stat
                    else:
                        caster_stat = caster.int_stat
                        target_stat = target.int_stat
                    
                    # Get skill for spell type
                    skill = caster.get_skill_for_type(spell.magic_type)
                    
                    # Calculate accuracy
                    dstat_bonus = calculate_dstat_bonus(caster_stat, target_stat)
                    total_macc = calculate_magic_accuracy(
                        skill=skill,
                        magic_acc_gear=caster.magic_accuracy,
                        dstat_bonus=int(dstat_bonus),
                        magic_burst=False,
                    )
                    calculated_hit_rate = calculate_magic_hit_rate(total_macc, target.magic_evasion)
                else:
                    calculated_hit_rate = 0.0
            
            # Determine what score represents based on optimization type
            result_entry = MagicGearsetResult(
                rank=rank,
                score=score,
                gear=gear_dict,
                stats=stats_summary,
            )
            
            # Add type-specific score interpretation AND always include hit_rate
            result_entry.hit_rate = calculated_hit_rate
            
            if opt_type == MagicOptimizationType.ACCURACY:
                pass  # hit_rate already set, score is also hit_rate
            elif opt_type == MagicOptimizationType.POTENCY:
                result_entry.potency_score = score  # This is now effective_score = potency × hit_rate
                # Also provide the raw potency for display
                if 'potency' in eval_details:
                    result_entry.raw_potency = eval_details['potency']
            else:
                result_entry.damage = score  # Score is average damage
            
            formatted_results.append(result_entry)
        
        return MagicOptimizeResponse(
            success=True,
            spell_name=request.spell_name,
            optimization_type=request.optimization_type,
            magic_burst=request.magic_burst,
            target=request.target,
            evaluated_target=evaluated_target_name,
            stratification_note=stratification_note,
            results=formatted_results,
        )
    
    except Exception as e:
        import traceback as tb
        return MagicOptimizeResponse(
            success=False,
            spell_name=request.spell_name,
            optimization_type=request.optimization_type,
            magic_burst=request.magic_burst,
            target=request.target,
            results=[],
            error=f"{str(e)}\n{tb.format_exc()}"
        )


@app.post("/api/magic/simulate", response_model=MagicSimulateResponse)
async def simulate_magic(request: MagicSimulateRequest):
    """
    Simulate a spell with a specific gear set.
    
    For direct simulation without optimization. Returns damage statistics
    and breakdown for a given gear set against a target.
    
    This is useful for:
    - Testing a manually-selected gear set
    - Comparing specific sets side-by-side
    - Understanding damage breakdown components
    """
    if not MAGIC_AVAILABLE:
        return MagicSimulateResponse(
            success=False,
            spell_name=request.spell_name,
            magic_burst=request.magic_burst,
            target=request.target,
            num_casts=request.num_casts,
            error="Magic modules not available"
        )
    
    try:
        # Validate spell
        spell = get_spell(request.spell_name)
        if spell is None:
            return MagicSimulateResponse(
                success=False,
                spell_name=request.spell_name,
                magic_burst=request.magic_burst,
                target=request.target,
                num_casts=request.num_casts,
                error=f"Unknown spell: {request.spell_name}"
            )
        
        # Map job string to enum
        job_enum = JOB_ENUM_MAP.get(request.job.upper())
        if not job_enum:
            return MagicSimulateResponse(
                success=False,
                spell_name=request.spell_name,
                magic_burst=request.magic_burst,
                target=request.target,
                num_casts=request.num_casts,
                error=f"Invalid job: {request.job}"
            )
        
        # Get job preset for base stats
        job_preset = get_job_preset(job_enum)
        
        # Get job gifts and apply to base character
        job_gifts = None
        if state.job_gifts and request.job.upper() in state.job_gifts.gifts:
            job_gifts = state.job_gifts.gifts[request.job.upper()]
        
        # Build base character stats from job preset
        # Skills start from job preset (which we'll modify with job gifts)
        total_ele_skill = job_preset.elemental_skill
        total_dark_skill = job_preset.dark_skill
        total_enf_skill = job_preset.enfeebling_skill
        mbb_trait = job_preset.mbb_trait
        
        # Apply job gifts to base character stats
        job_gift_macc = 0
        job_gift_mab = 0
        job_gift_mdmg = 0
        job_gift_fc = 0
        
        if job_gifts:
            gift_stats = job_gifts.get_wsdist_stats()
            # Skills from job gifts
            total_ele_skill += int(gift_stats.get('Elemental Magic Skill', 0))
            total_dark_skill += int(gift_stats.get('Dark Magic Skill', 0))
            total_enf_skill += int(gift_stats.get('Enfeebling Magic Skill', 0))
            # MBB trait from job gifts (already in basis points)
            mbb_trait += int(gift_stats.get('Magic Burst Damage Trait', 0))
            # Additional stats from job gifts
            job_gift_macc = int(gift_stats.get('Magic Accuracy', 0))
            job_gift_mab = int(gift_stats.get('Magic Attack', 0))
            job_gift_mdmg = int(gift_stats.get('Magic Damage', 0))
            job_gift_fc = int(gift_stats.get('Fast Cast', 0))
        
        # Build CasterStats from job gifts + gear + buffs
        total_int = job_preset.base_int
        total_mnd = job_preset.base_mnd
        total_mab = job_gift_mab
        total_mdmg = job_gift_mdmg
        total_macc = job_gift_macc
        total_mbb = 0
        total_mbb_ii = 0
        total_fc = job_gift_fc
        
        # Master level stat bonus
        ml_bonus = request.master_level // 5  # +1 all stats per 5 ML
        total_int += ml_bonus
        total_mnd += ml_bonus
        
        # Parse gear stats from gearset
        for slot, item in request.gearset.items():
            if item and item.get("name", item.get("Name", "Empty")) != "Empty":
                total_int += item.get("INT", 0)
                total_mnd += item.get("MND", 0)
                total_mab += item.get("Magic Attack", item.get("Magic Atk. Bonus", 0))
                total_mdmg += item.get("Magic Damage", 0)
                total_macc += item.get("Magic Accuracy", item.get("Magic Acc.", 0))
                total_mbb += item.get("Magic Burst Bonus", item.get("Magic burst dmg.", 0))
                total_mbb_ii += item.get("Magic Burst Bonus II", item.get("Magic burst dmg. II", 0))
                total_ele_skill += item.get("Elemental Magic Skill", item.get("Elem. magic skill", 0))
                total_dark_skill += item.get("Dark Magic Skill", 0)
                total_enf_skill += item.get("Enfeebling Magic Skill", item.get("Enfb.mag. skill", 0))
                total_fc += item.get("Fast Cast", item.get('"Fast Cast"', 0))
        
        # Apply buffs
        buff_bonuses = convert_magic_buffs_to_caster_stats(request.buffs)
        total_int += buff_bonuses.get("INT", 0)
        total_mnd += buff_bonuses.get("MND", 0)
        total_mab += buff_bonuses.get("magic_attack", 0)
        total_macc += buff_bonuses.get("magic_accuracy", 0)
        
        # Apply percentage MAB if any (like Geo-Acumen)
        if buff_bonuses.get("magic_attack_pct", 0) > 0:
            total_mab = int(total_mab * (1.0 + buff_bonuses["magic_attack_pct"] / 100))
        
        # Create CasterStats object
        caster = CasterStats(
            int_stat=total_int,
            mnd_stat=total_mnd,
            mab=total_mab,
            magic_damage=total_mdmg,
            magic_accuracy=total_macc,
            elemental_magic_skill=total_ele_skill,
            dark_magic_skill=total_dark_skill,
            enfeebling_magic_skill=total_enf_skill,
            mbb_gear=total_mbb,
            mbb_ii_gear=total_mbb_ii,
            mbb_trait=mbb_trait,
            fast_cast=total_fc,
        )
        
        # Get target stats
        target_data = MAGIC_TARGET_PRESETS.get(request.target)
        if target_data:
            target = MagicTargetStats(
                int_stat=target_data.get("int_stat", 200),
                mnd_stat=target_data.get("mnd_stat", 200),
                magic_evasion=target_data.get("magic_evasion", 600),
                magic_defense_bonus=target_data.get("magic_defense_bonus", 30),
            )
        else:
            # Fallback to default apex mob
            target = MAGIC_TARGETS.get('apex_mob', MagicTargetStats())
        
        # Apply debuffs to target
        for debuff in request.debuffs:
            for category in MAGIC_DEBUFF_DEFINITIONS.values():
                if debuff in category:
                    d = category[debuff]
                    target.magic_evasion -= d.get("magic_evasion_down", 0)
                    target.magic_defense_bonus -= d.get("magic_defense_down", 0)
        
        # Run simulation
        sim = MagicSimulator(seed=42)  # Fixed seed for reproducibility
        result = sim.simulate_spell(
            spell_name=request.spell_name,
            caster=caster,
            target=target,
            magic_burst=request.magic_burst,
            skillchain_steps=request.skillchain_steps,
            num_casts=request.num_casts,
        )
        
        # Get a single cast for breakdown info
        single_cast = sim.calculate_spell_damage(
            spell=spell,
            caster=caster,
            target=target,
            magic_burst=request.magic_burst,
            skillchain_steps=request.skillchain_steps,
            force_unresisted=True,  # For consistent breakdown
        )
        
        return MagicSimulateResponse(
            success=True,
            spell_name=request.spell_name,
            magic_burst=request.magic_burst,
            target=request.target,
            num_casts=request.num_casts,
            
            average_damage=result.average_damage,
            min_damage=result.min_damage,
            max_damage=result.max_damage,
            
            hit_rate=single_cast.hit_rate,
            unresisted_rate=result.unresisted_rate,
            half_resist_rate=result.half_resist_rate,
            quarter_resist_rate=result.quarter_resist_rate,
            eighth_resist_rate=result.eighth_resist_rate,
            
            base_damage=single_cast.base_d,
            mab_mdb_ratio=single_cast.mab_mdb_ratio,
            mb_multiplier=single_cast.mb_multiplier,
            mbb_multiplier=single_cast.mbb_multiplier,
            
            stats={
                "INT": total_int,
                "MND": total_mnd,
                "MAB": total_mab,
                "Magic Damage": total_mdmg,
                "Magic Accuracy": total_macc,
                "MBB (Gear)": total_mbb,
                "MBB II": total_mbb_ii,
                "MBB (Trait)": job_preset.mbb_trait,
                "Elemental Skill": total_ele_skill,
                "Dark Skill": total_dark_skill,
                "Enfeebling Skill": total_enf_skill,
                "Fast Cast": total_fc,
                "Target M.Eva": target.magic_evasion,
                "Target MDB": target.magic_defense_bonus,
            },
        )
    
    except Exception as e:
        import traceback as tb
        return MagicSimulateResponse(
            success=False,
            spell_name=request.spell_name,
            magic_burst=request.magic_burst,
            target=request.target,
            num_casts=request.num_casts,
            error=f"{str(e)}\n{tb.format_exc()}"
        )


@app.post("/api/stats/calculate/magic")
async def calculate_magic_stats(request: MagicStatsRequest):
    """
    Calculate effective magic stats for a gear set.
    
    Returns detailed magic stats including:
    - Primary stats (INT, MND)
    - Magic offense (MAB, M.Dmg, M.Acc)
    - Magic skills
    - Magic Burst Bonus (capped and uncapped portions)
    - Fast Cast
    """
    if not MAGIC_AVAILABLE:
        return {"success": False, "error": "Magic modules not available"}
    
    try:
        job_enum = JOB_ENUM_MAP.get(request.job.upper())
        if not job_enum:
            return {"success": False, "error": f"Invalid job: {request.job}"}
        
        # Get job preset for base stats
        job_preset = get_job_preset(job_enum)
        
        # Get job gifts and apply to base character
        job_gifts = None
        if state.job_gifts and request.job.upper() in state.job_gifts.gifts:
            job_gifts = state.job_gifts.gifts[request.job.upper()]
        
        # Build base character stats from job preset
        total_ele_skill = job_preset.elemental_skill
        total_dark_skill = job_preset.dark_skill
        total_enf_skill = job_preset.enfeebling_skill
        mbb_trait = job_preset.mbb_trait
        
        # Apply job gifts to base character stats
        job_gift_macc = 0
        job_gift_mab = 0
        job_gift_mdmg = 0
        job_gift_fc = 0
        
        if job_gifts:
            gift_stats = job_gifts.get_wsdist_stats()
            total_ele_skill += int(gift_stats.get('Elemental Magic Skill', 0))
            total_dark_skill += int(gift_stats.get('Dark Magic Skill', 0))
            total_enf_skill += int(gift_stats.get('Enfeebling Magic Skill', 0))
            mbb_trait += int(gift_stats.get('Magic Burst Damage Trait', 0))
            job_gift_macc = int(gift_stats.get('Magic Accuracy', 0))
            job_gift_mab = int(gift_stats.get('Magic Attack', 0))
            job_gift_mdmg = int(gift_stats.get('Magic Damage', 0))
            job_gift_fc = int(gift_stats.get('Fast Cast', 0))
        
        # Sum stats from job gifts + gear + buffs
        total_int = job_preset.base_int
        total_mnd = job_preset.base_mnd
        total_mab = job_gift_mab
        total_mdmg = job_gift_mdmg
        total_macc = job_gift_macc
        total_mbb = 0
        total_mbb_ii = 0
        total_fc = job_gift_fc
        
        # Parse gear stats from gearset
        for slot, item in request.gearset.items():
            if item and item.get("name", item.get("Name", "Empty")) != "Empty":
                total_int += item.get("INT", 0)
                total_mnd += item.get("MND", 0)
                total_mab += item.get("Magic Attack", item.get("Magic Atk. Bonus", 0))
                total_mdmg += item.get("Magic Damage", 0)
                total_macc += item.get("Magic Accuracy", item.get("Magic Acc.", 0))
                total_mbb += item.get("Magic Burst Bonus", item.get("Magic burst dmg.", 0))
                total_mbb_ii += item.get("Magic Burst Bonus II", item.get("Magic burst dmg. II", 0))
                total_ele_skill += item.get("Elemental Magic Skill", item.get("Elem. magic skill", 0))
                total_dark_skill += item.get("Dark Magic Skill", 0)
                total_enf_skill += item.get("Enfeebling Magic Skill", item.get("Enfb.mag. skill", 0))
                total_fc += item.get("Fast Cast", item.get('"Fast Cast"', 0))
        
        # Apply buffs
        buff_bonuses = convert_magic_buffs_to_caster_stats(request.buffs)
        total_int += buff_bonuses.get("INT", 0)
        total_mnd += buff_bonuses.get("MND", 0)
        total_mab += buff_bonuses.get("magic_attack", 0)
        total_macc += buff_bonuses.get("magic_accuracy", 0)
        
        # Get spell info if provided
        spell_info = None
        if request.spell_name:
            spell = get_spell(request.spell_name)
            if spell:
                spell_info = {
                    "name": spell.name,
                    "element": spell.element.name,
                    "magic_type": spell.magic_type.name,
                }
        
        return {
            "success": True,
            "stats": {
                "job": request.job.upper(),
                "sub_job": request.sub_job.upper(),
                "master_level": request.master_level,
                
                "primary_stats": {
                    "INT": total_int,
                    "MND": total_mnd,
                },
                
                "magic_offense": {
                    "magic_attack_bonus": total_mab,
                    "magic_damage": total_mdmg,
                    "magic_accuracy": total_macc,
                },
                
                "magic_burst": {
                    "mbb_gear": total_mbb,
                    "mbb_gear_capped": min(total_mbb, 4000),
                    "mbb_ii": total_mbb_ii,
                    "mbb_trait": mbb_trait,
                    "mbb_total_effective": min(total_mbb, 4000) + total_mbb_ii + mbb_trait,
                },
                
                "skills": {
                    "elemental": total_ele_skill,
                    "dark": total_dark_skill,
                    "enfeebling": total_enf_skill,
                },
                
                "fast_cast": total_fc,
                "fast_cast_capped": min(total_fc, 8000),
                
                "spell_info": spell_info,
            }
        }
    
    except Exception as e:
        import traceback as tb
        return {"success": False, "error": str(e), "traceback": tb.format_exc()}


def convert_magic_buffs_to_caster_stats(
    ui_buffs: Dict[str, List[str]],
    food: str = "",
) -> Dict[str, int]:
    """
    Convert UI-format magic buffs to stat bonuses.
    
    Args:
        ui_buffs: {"geo": ["Geo-Acumen"], "cor": ["Wizard's Roll XI"], ...}
        food: Food name
    
    Returns:
        Dict of stat bonuses to apply to CasterStats
    """
    bonuses = {
        "INT": 0,
        "MND": 0,
        "magic_attack": 0,
        "magic_accuracy": 0,
    }
    
    # Process GEO magic buffs
    if "geo" in ui_buffs:
        for buff in ui_buffs["geo"]:
            if buff in MAGIC_BUFF_ADDITIONS.get("geo_magic", {}):
                b = MAGIC_BUFF_ADDITIONS["geo_magic"][buff]
                bonuses["magic_attack"] += b.get("magic_attack", 0)
                bonuses["magic_accuracy"] += b.get("magic_accuracy", 0)
                # GEO MAB% is treated as flat MAB bonus (how it works in FFXI)
                bonuses["magic_attack"] += b.get("magic_attack_pct", 0)
    
    # Process COR magic rolls
    if "cor" in ui_buffs:
        for buff in ui_buffs["cor"]:
            if buff in MAGIC_BUFF_ADDITIONS.get("cor_magic", {}):
                b = MAGIC_BUFF_ADDITIONS["cor_magic"][buff]
                bonuses["magic_attack"] += b.get("magic_attack", 0)
                bonuses["magic_accuracy"] += b.get("magic_accuracy", 0)
    
    # Process food
    if food and food in MAGIC_BUFF_ADDITIONS.get("food_magic", {}):
        f = MAGIC_BUFF_ADDITIONS["food_magic"][food]
        bonuses["INT"] += f.get("INT", 0)
        bonuses["MND"] += f.get("MND", 0)
        bonuses["magic_attack"] += f.get("magic_attack", 0)
        bonuses["magic_accuracy"] += f.get("magic_accuracy", 0)
    
    return bonuses


# =============================================================================
# Lua Template Optimization - Pydantic Models
# =============================================================================

class LuaSetInfo(BaseModel):
    """Information about a single set in the Lua file."""
    name: str
    path: List[str]
    is_placeholder: bool
    has_items: bool
    item_count: int
    base_set: Optional[str] = None
    inferred_profile_type: str
    # New fields for smarter optimization
    set_type: str = "unknown"  # ws, tp, magic_damage, magic_burst, magic_accuracy, dt, fc, other
    ws_name: Optional[str] = None  # Extracted WS name if applicable
    weapon_type: Optional[str] = None  # Required weapon type for WS
    representative_spell: Optional[str] = None  # Representative spell for magic sets
    spell_type: Optional[str] = None  # elemental, dark, enfeebling_int, enfeebling_mnd, divine
    tp_set_type: Optional[str] = None  # pure_tp, hybrid_tp, acc_tp, dt_tp, refresh_tp (for engaged sets)


class LuaParseResponse(BaseModel):
    """Response from parsing a Lua file."""
    success: bool
    filename: str
    job: Optional[str] = None
    total_sets: int
    placeholder_sets: int
    sets: List[LuaSetInfo]
    error: Optional[str] = None
    # New fields for weapon requirements
    required_weapons: Dict[str, List[str]] = {}  # weapon_type -> list of WS names
    required_weapon_types: List[str] = []  # Ordered list of weapon types needed


class LuaOptimizedSet(BaseModel):
    """A single optimized set result."""
    name: str
    profile_type: str
    items: Dict[str, str]  # slot -> item name
    score: float
    # Simulation results
    optimization_type: Optional[str] = None  # ws_simulation, tp_simulation, magic_damage, etc.
    simulation_value: Optional[float] = None  # Damage, time_to_ws, etc.
    simulation_details: Optional[Dict[str, Any]] = None  # Additional simulation stats


class LuaOptimizeResponse(BaseModel):
    """Response from Lua optimization endpoint."""
    success: bool
    filename: str
    job: str
    sets_optimized: int
    sets_skipped: int
    optimized_sets: List[LuaOptimizedSet]
    errors: List[str]
    lua_content: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# Lua Template Optimization - Helper Functions
# =============================================================================

def classify_lua_set_type(set_name: str, context: str = "") -> str:
    """
    Classify a set based on its name to determine optimization approach.
    
    Returns one of: ws, tp, magic_damage, magic_burst, magic_accuracy, enhancing, 
                    enhancing_skill, enhancing_duration, healing, dt, fc, ja_composure, 
                    ja_saboteur, ja_generic, other
    """
    name_lower = set_name.lower()
    context_lower = context.lower()
    
    # Weaponskill sets
    if 'precast.ws' in name_lower or "ws[" in name_lower or 'weaponskill' in name_lower:
        return 'ws'
    
    # TP/Engaged sets
    if 'engaged' in name_lower:
        return 'tp'
    
    # Job Ability sets - check BEFORE general precast
    # These are sets.precast.JA['AbilityName'] style
    if 'precast.ja' in name_lower or "ja[" in name_lower:
        # Composure - extends enhancing magic duration on self
        if 'composure' in name_lower:
            return 'ja_composure'
        # Saboteur - enhances next enfeebling spell potency
        if 'saboteur' in name_lower:
            return 'ja_saboteur'
        # Chainspell - just needs to be activated quickly (FC helps)
        if 'chainspell' in name_lower:
            return 'fc'  # FC is still useful for activating quickly
        # Other JAs - generic handling (often just want to maximize the JA effect)
        return 'ja_generic'
    
    # Magic sets (midcast)
    if 'midcast' in name_lower:
        # Cure/Healing magic - check BEFORE elemental to avoid "Curaga" matching something else
        if any(x in name_lower for x in ['cure', 'curaga', 'cura', 'healing']):
            return 'healing'
        
        # Enhancing magic - check BEFORE elemental to avoid conflicts
        # Note: Check for specific enhancing spells and generic enhancing
        if any(x in name_lower for x in ['enhancing', 'haste', 'refresh', 'phalanx', 
                                          'stoneskin', 'aquaveil', 'shell', 'protect',
                                          'regen', 'blink', 'bar', 'gain', 'boost',
                                          'temper', 'enspell', 'spikes', 'invisible',
                                          'sneak', 'deodorize']):
            # But not if it's clearly elemental (e.g., "EnhancedThunder" - unlikely but safe)
            if not any(x in name_lower for x in ['elemental', 'nuke', 'thunder', 'fire', 
                                                   'blizzard', 'aero', 'water']):
                # Check if it's specifically for duration or skill
                if 'duration' in name_lower:
                    return 'enhancing_duration'
                if 'skill' in name_lower:
                    return 'enhancing_skill'
                # Default enhancing midcast = maximize skill
                return 'enhancing_skill'
        
        # Elemental/Nuke damage
        if any(x in name_lower for x in ['elemental', 'nuke', 'thunder', 'fire', 
                                          'blizzard', 'aero', 'water']):
            # Note: removed 'stone' from this list - handled separately below
            # Check for accuracy/resistant variant - prioritize landing spells
            if 'resistant' in name_lower or ('acc' in name_lower and 'magic' not in name_lower):
                return 'magic_accuracy'
            if 'mb' in name_lower or 'burst' in name_lower or 'burst' in context_lower:
                return 'magic_burst'
            return 'magic_damage'
        
        # Stone element (but not Stoneskin which was caught above)
        if 'stone' in name_lower and 'skin' not in name_lower:
            # Check for accuracy/resistant variant
            if 'resistant' in name_lower or ('acc' in name_lower and 'magic' not in name_lower):
                return 'magic_accuracy'
            if 'mb' in name_lower or 'burst' in name_lower or 'burst' in context_lower:
                return 'magic_burst'
            return 'magic_damage'
        
        # Impact - special case, it's enfeebling focused but also does damage
        if 'impact' in name_lower:
            return 'magic_accuracy'  # Impact is primarily for its debuff, optimize for accuracy
        
        # Dark magic damage (but not Drain/Aspir which are separate)
        if any(x in name_lower for x in ['dark', 'bio', 'absorb', 'stun']):
            return 'magic_damage'
        
        # Drain/Aspir specific
        if any(x in name_lower for x in ['drain', 'aspir']):
            return 'magic_damage'
        
        # Enfeebling - accuracy focused
        if any(x in name_lower for x in ['enfeebl', 'enfeeb', 'paralyze', 'slow', 
                                          'silence', 'gravity', 'bind', 'sleep',
                                          'blind', 'dispel', 'frazzle', 'distract',
                                          'poison', 'dia', 'addle', 'break']):
            return 'magic_accuracy'
        
        # Divine magic
        if 'divine' in name_lower or 'banish' in name_lower or 'holy' in name_lower:
            return 'magic_damage'
        
        # Generic magic - check if it looks like a buff/enhancing set
        # If it has "duration" or "potency" in name, it's probably enhancing
        if 'duration' in name_lower:
            return 'enhancing_duration'
        if 'potency' in name_lower or 'skill' in name_lower:
            return 'enhancing_skill'
        
        # Default midcast to magic_damage (will use elemental)
        return 'magic_damage'
    
    # Buff sets (not midcast but buff-related)
    if 'buff' in name_lower:
        # Check for specific buff types
        if 'composure' in name_lower:
            return 'ja_composure'
        return 'other'
    
    # DT/Idle sets
    if 'idle' in name_lower or 'dt' in name_lower or 'defense' in name_lower:
        return 'dt'
    
    # FC/Precast sets (but not WS or JA - JA was caught above)
    if 'precast' in name_lower and 'ws' not in name_lower:
        # Check if it's specifically a FC variant
        if 'fc' in name_lower:
            return 'fc'
        # Impact precast - still FC focused
        if 'impact' in name_lower:
            return 'fc'
        # Dispelga precast - still FC focused  
        if 'dispelga' in name_lower:
            return 'fc'
        # Generic precast = FC
        return 'fc'
    
    return 'other'


def infer_tp_type_from_set_name(set_name: str, context: str = "") -> str:
    """
    Infer the appropriate TPSetType from an engaged set's name.
    
    Analyzes set naming conventions to determine the optimization priority:
    - DT suffix -> dt_tp (survivability + TP)
    - HighAcc/MidAcc suffix -> acc_tp (accuracy focus)
    - LowAcc suffix -> hybrid_tp (some accuracy, balanced)
    - STP suffix -> pure_tp (maximum TP speed)
    - Refresh suffix -> refresh_tp (MP sustain)
    - Base engaged -> pure_tp (default)
    
    Args:
        set_name: The full set name (e.g., "sets.engaged.MidAcc.DT")
        context: Optional placeholder context for additional hints
        
    Returns:
        One of: pure_tp, hybrid_tp, acc_tp, dt_tp, refresh_tp
    """
    name_lower = set_name.lower()
    context_lower = context.lower() if context else ""
    
    # Split path for easier analysis
    # "sets.engaged.MidAcc.DT" -> ["sets", "engaged", "midacc", "dt"]
    path_parts = [p.lower() for p in name_lower.replace('[', '.').replace(']', '').replace("'", "").replace('"', '').split('.')]
    
    # Check for DT - this takes precedence as it's a hybrid survivability set
    # Matches: sets.engaged.DT, sets.engaged.LowAcc.DT, sets.engaged.MidAcc.DT, etc.
    if 'dt' in path_parts or name_lower.endswith('.dt'):
        return 'dt_tp'
    
    # Check context for DT hints
    if 'dt' in context_lower or 'hybrid' in context_lower or 'survivability' in context_lower:
        return 'dt_tp'
    
    # Check for accuracy variants
    # HighAcc and MidAcc -> full accuracy focus
    if 'highacc' in path_parts or 'midacc' in path_parts:
        return 'acc_tp'
    if 'highacc' in name_lower or 'midacc' in name_lower:
        return 'acc_tp'
    if 'fullacc' in name_lower or 'full_acc' in name_lower:
        return 'acc_tp'
    
    # LowAcc -> hybrid (some accuracy but not full focus)
    if 'lowacc' in path_parts or 'lowacc' in name_lower:
        return 'hybrid_tp'
    
    # Check for STP (Store TP) focus -> pure TP
    if 'stp' in path_parts or name_lower.endswith('.stp'):
        return 'pure_tp'
    
    # Check for refresh/MP sustain
    if 'refresh' in path_parts or 'refresh' in name_lower:
        return 'refresh_tp'
    if 'mp' in context_lower or 'refresh' in context_lower:
        return 'refresh_tp'
    
    # Check context for other hints
    if 'acc' in context_lower or 'accuracy' in context_lower:
        return 'acc_tp'
    if 'stp' in context_lower or 'store tp' in context_lower:
        return 'pure_tp'
    if 'hybrid' in context_lower:
        return 'hybrid_tp'
    
    # Default: base engaged set -> pure_tp for maximum TP generation
    return 'pure_tp'


def extract_ws_name_from_set(set_name: str) -> Optional[str]:
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


def get_weapon_type_for_ws(ws_name: str) -> Optional[str]:
    """Get the weapon type required for a weaponskill."""
    ws_data = get_weaponskill(ws_name)
    if ws_data and hasattr(ws_data, 'weapon_type'):
        return ws_data.weapon_type.value
    return None


def get_representative_spell_for_set(set_name: str, context: str = "") -> tuple:
    """
    Determine an appropriate representative spell for magic set optimization.
    
    Returns tuple of (spell_name, spell_type)
    spell_type is one of: elemental, dark, drain, divine, enfeebling_int, enfeebling_mnd, 
                          enhancing, healing, None
    
    Returns (None, 'enhancing') or (None, 'healing') for sets that shouldn't use damage simulation.
    """
    name_lower = set_name.lower()
    context_lower = context.lower()
    
    # =========================================================================
    # HEALING MAGIC - Cure sets
    # =========================================================================
    if any(x in name_lower for x in ['cure', 'curaga', 'cura', 'healing']):
        # Return Cure IV as representative - commonly used, good baseline
        return ('Cure IV', 'healing')
    
    # =========================================================================
    # ENHANCING MAGIC - These don't benefit from damage simulation
    # =========================================================================
    # Specific enhancing spells
    if 'stoneskin' in name_lower:
        return (None, 'enhancing')  # Stoneskin - optimize for enhancing skill/duration
    if 'phalanx' in name_lower:
        return (None, 'enhancing')  # Phalanx - optimize for enhancing skill
    if 'refresh' in name_lower:
        return (None, 'enhancing')  # Refresh - optimize for enhancing duration/potency
    if 'haste' in name_lower:
        return (None, 'enhancing')  # Haste - no gear optimization really needed
    if 'aquaveil' in name_lower:
        return (None, 'enhancing')  # Aquaveil - optimize for enhancing skill
    if 'regen' in name_lower:
        return (None, 'enhancing')  # Regen - optimize for enhancing duration/potency
    
    # Generic enhancing magic sets
    if any(x in name_lower for x in ['enhancing', 'duration', 'enhancingskill', 
                                      'enhancingduration', 'enspell', 'temper',
                                      'gain', 'boost', 'bar', 'protect', 'shell',
                                      'blink', 'invisible', 'sneak', 'deodorize']):
        return (None, 'enhancing')  # Don't use damage simulation
    
    # =========================================================================
    # Check for Magic Burst indicator
    # =========================================================================
    is_burst = 'mb' in name_lower or 'burst' in name_lower or 'burst' in context_lower
    
    # =========================================================================
    # ELEMENTAL DAMAGE - Use high tier spells
    # =========================================================================
    if any(x in name_lower for x in ['elemental', 'nuke']):
        # Check for specific element in name
        if 'thunder' in name_lower:
            return ('Thunder VI', 'elemental')
        elif 'fire' in name_lower:
            return ('Fire VI', 'elemental')
        elif 'blizzard' in name_lower or 'ice' in name_lower:
            return ('Blizzard VI', 'elemental')
        elif 'aero' in name_lower or 'wind' in name_lower:
            return ('Aero VI', 'elemental')
        elif 'stone' in name_lower or 'earth' in name_lower:
            return ('Stone VI', 'elemental')
        elif 'water' in name_lower:
            return ('Water VI', 'elemental')
        else:
            # Default to Thunder VI as it's commonly used
            return ('Thunder VI', 'elemental')
    
    # Specific element names in midcast (but not conflicting with enhancing)
    if 'thunder' in name_lower:
        return ('Thunder VI', 'elemental')
    if 'fire' in name_lower:
        return ('Fire VI', 'elemental')
    if 'blizzard' in name_lower:
        return ('Blizzard VI', 'elemental')
    if 'aero' in name_lower:
        return ('Aero VI', 'elemental')
    # Stone - but not Stoneskin (already handled above)
    if 'stone' in name_lower and 'skin' not in name_lower:
        return ('Stone VI', 'elemental')
    if 'water' in name_lower:
        return ('Water VI', 'elemental')
    
    # =========================================================================
    # DARK MAGIC
    # =========================================================================
    # Drain/Aspir specific sets
    if 'drain' in name_lower or 'aspir' in name_lower:
        return ('Drain III', 'drain')
    
    # Absorb spells - dark magic that drains stats
    if 'absorb' in name_lower:
        return ('Absorb-STR', 'dark')
    
    # Stun
    if 'stun' in name_lower:
        return ('Stun', 'dark')
    
    # General dark magic (use Bio as representative - doesn't have special gear)
    if 'dark' in name_lower:
        return ('Bio III', 'dark')
    
    # =========================================================================
    # DIVINE MAGIC
    # =========================================================================
    if 'divine' in name_lower or 'banish' in name_lower or 'holy' in name_lower:
        return ('Holy II', 'divine')
    
    # =========================================================================
    # ENFEEBLING MAGIC
    # =========================================================================
    # Impact - special dark magic enfeeble (uses INT)
    if 'impact' in name_lower:
        return ('Impact', 'enfeebling_int')
    
    # Dispelga - special enfeeble
    if 'dispelga' in name_lower:
        return ('Dispelga', 'enfeebling_int')
    
    # INT-based enfeebling (potency based on INT)
    if 'intenfeeble' in name_lower or 'int enfeeble' in name_lower:
        return ('Poison II', 'enfeebling_int')
    
    # Check for specific INT-based enfeebles
    if any(x in name_lower for x in ['blind', 'gravity', 'poison', 'dispel', 'sleep', 'break', 'bind']):
        return ('Poison II', 'enfeebling_int')
    
    # MND-based enfeebling (potency based on MND)
    if 'mndenfeeble' in name_lower or 'mnd enfeeble' in name_lower:
        return ('Slow II', 'enfeebling_mnd')
    
    # Check for specific MND-based enfeebles
    if any(x in name_lower for x in ['slow', 'paralyze', 'silence', 'addle']):
        return ('Slow II', 'enfeebling_mnd')
    
    # Generic enfeebling - default to MND-based as more common
    if 'enfeebl' in name_lower or 'enfeeb' in name_lower:
        return ('Slow II', 'enfeebling_mnd')
    
    # Skill-based enfeebles (Distract/Frazzle)
    if 'distract' in name_lower or 'frazzle' in name_lower:
        return ('Distract III', 'enfeebling_mnd')
    
    # Dia - technically enfeebling
    if 'dia' in name_lower:
        return ('Dia III', 'enfeebling_mnd')
    
    # =========================================================================
    # DEFAULT - If nothing matches, return None to skip simulation
    # =========================================================================
    # Don't default to Thunder VI for unknown sets - let the optimizer handle it
    return (None, 'other')


# =============================================================================
# Lua Template Optimization - Endpoints
# =============================================================================

@app.post("/api/lua/parse")
async def parse_lua_file(file: UploadFile = File(...)):
    """
    Parse a GearSwap Lua file and identify placeholder sets.
    
    Returns information about all sets found, which ones need optimization,
    what weapon types are required for WS sets, and representative spells
    for magic sets.
    
    The frontend uses this to:
    1. Display the parsed sets
    2. Show dynamic weapon selection based on WS requirements
    3. Orchestrate optimization by calling appropriate endpoints
    """
    try:
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # Parse the Lua file
        gsfile = parse_gearswap_content(content_str, file.filename)
        
        # Find placeholder sets
        placeholders = find_placeholder_sets(gsfile)
        placeholder_names = {s.name for s in placeholders}
        
        # Track required weapons by type
        required_weapons: Dict[str, List[str]] = {}  # weapon_type -> list of WS names
        
        # Build set info list
        sets_info = []
        for set_name, set_def in gsfile.sets.items():
            # Infer profile type for display
            job = Job[gsfile.job] if gsfile.job and gsfile.job in Job.__members__ else None
            profile = infer_profile_from_set(set_def, job)
            
            # Classify set type
            set_type = classify_lua_set_type(set_def.name, set_def.placeholder_context)
            
            # Initialize optional fields
            ws_name = None
            weapon_type = None
            representative_spell = None
            spell_type = None
            tp_set_type = None
            
            # For WS sets, extract WS name and weapon type
            if set_type == 'ws' and set_def.name in placeholder_names:
                ws_name = extract_ws_name_from_set(set_def.name)
                if ws_name:
                    weapon_type = get_weapon_type_for_ws(ws_name)
                    if weapon_type:
                        # Track for required weapons summary
                        if weapon_type not in required_weapons:
                            required_weapons[weapon_type] = []
                        if ws_name not in required_weapons[weapon_type]:
                            required_weapons[weapon_type].append(ws_name)
            
            # For TP/engaged sets, infer the TP set type
            if set_type == 'tp' and set_def.name in placeholder_names:
                tp_set_type = infer_tp_type_from_set_name(
                    set_def.name,
                    set_def.placeholder_context
                )
            
            # For magic sets, determine representative spell
            if set_type in ('magic_damage', 'magic_burst', 'magic_accuracy') and set_def.name in placeholder_names:
                representative_spell, spell_type = get_representative_spell_for_set(
                    set_def.name, 
                    set_def.placeholder_context
                )
            
            sets_info.append(LuaSetInfo(
                name=set_def.name,
                path=set_def.path,
                is_placeholder=set_def.name in placeholder_names,
                has_items=bool(set_def.items),
                item_count=len(set_def.items),
                base_set=set_def.base_set,
                inferred_profile_type=profile.name,
                set_type=set_type,
                ws_name=ws_name,
                weapon_type=weapon_type,
                representative_spell=representative_spell,
                spell_type=spell_type,
                tp_set_type=tp_set_type,
            ))
        
        # Build ordered list of required weapon types
        required_weapon_types = list(required_weapons.keys())
        
        return LuaParseResponse(
            success=True,
            filename=file.filename,
            job=gsfile.job,
            total_sets=len(gsfile.sets),
            placeholder_sets=len(placeholders),
            sets=sets_info,
            required_weapons=required_weapons,
            required_weapon_types=required_weapon_types,
        )
        
    except Exception as e:
        return LuaParseResponse(
            success=False,
            filename=file.filename,
            job=None,
            total_sets=0,
            placeholder_sets=0,
            sets=[],
            error=f"{str(e)}\n{traceback.format_exc()}"
        )


# =============================================================================
# DEPRECATED: /api/lua/optimize endpoint removed
# Optimization is now orchestrated by the frontend using existing endpoints:
# - /api/optimize/ws for weaponskill sets
# - /api/optimize/tp for TP/engaged sets
# - /api/optimize/magic for magic sets
# - /api/optimize/dt for DT/idle sets
# =============================================================================

# =============================================================================
# Static Files
# =============================================================================

# Create static directory if it doesn't exist
static_dir = SCRIPT_DIR / "static"
static_dir.mkdir(exist_ok=True)
(static_dir / "css").mkdir(exist_ok=True)
(static_dir / "js").mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("FFXI Gear Set Optimizer - Web Server")
    print("=" * 60)
    print(f"wsdist available: {WSDIST_AVAILABLE}")
    print(f"magic available: {MAGIC_AVAILABLE}")
    print(f"Static files: {static_dir}")
    print()
    print("Starting server at http://localhost:8000")
    print("API docs available at http://localhost:8000/docs")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)