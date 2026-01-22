"""
Numba-Accelerated Beam Search Optimizer for Gear Selection

Highly optimized version using Numba JIT compilation for the hot loops.
All string/dict operations are converted to integer array operations.

Key optimizations over FastBeamSearchOptimizer:
1. JIT-compiled expansion kernel (no Python overhead in inner loop)
2. Separate scoring pass from reconstruction (only reconstruct top-k)
3. Memory-efficient: only store (score, beam_idx, item_idx) during expansion

Same interface as BeamSearchOptimizer - drop-in replacement.
"""

import sys
import numpy as np
import numba
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field

SCRIPT_DIR = Path(__file__).parent
WSDIST_DIR = SCRIPT_DIR / 'wsdist_beta-main'

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(WSDIST_DIR))

from models import Stats, Slot, Job, OptimizationProfile
from inventory_loader import Inventory
from wsdist_converter import to_wsdist_gear

# Import constants from original module
from beam_search_optimizer import (
    is_valid_sub_for_main,
    WSDIST_SLOTS, ARMOR_SLOTS, WEAPON_SLOTS, ALL_SLOTS,
    SLOT_TO_WSDIST, WSDIST_TO_SLOT,
    GearsetCandidate,
)


# =============================================================================
# SLOT INDEXING
# =============================================================================

SLOT_ORDER = ['main', 'sub', 'ranged', 'ammo', 'head', 'neck', 'ear1', 'ear2',
              'body', 'hands', 'ring1', 'ring2', 'back', 'waist', 'legs', 'feet']
SLOT_TO_IDX = {name: i for i, name in enumerate(SLOT_ORDER)}
N_SLOTS = len(SLOT_ORDER)

# Paired slots for canonical ordering
PAIR_SLOT_MAP = {
    SLOT_TO_IDX['ear2']: SLOT_TO_IDX['ear1'],
    SLOT_TO_IDX['ring2']: SLOT_TO_IDX['ring1'],
}


# =============================================================================
# STAT INDEXING (same as fast version)
# =============================================================================

def _get_stat_fields() -> List[str]:
    """Extract numeric stat field names from Stats dataclass."""
    fields = []
    for field_name in Stats.__dataclass_fields__:
        if field_name in ('skill_bonuses', 'special_effects'):
            continue
        fields.append(field_name)
    return fields

STAT_FIELDS = _get_stat_fields()
STAT_TO_INDEX = {name: i for i, name in enumerate(STAT_FIELDS)}
N_STATS = len(STAT_FIELDS)

# Stat mapping from wsdist keys to our stat field names
WSDIST_TO_STAT = {
    'STR': 'STR', 'DEX': 'DEX', 'VIT': 'VIT', 'AGI': 'AGI',
    'INT': 'INT', 'MND': 'MND', 'CHR': 'CHR', 'HP': 'HP', 'MP': 'MP',
    'Accuracy': 'accuracy', 'Attack': 'attack',
    'Ranged Accuracy': 'ranged_accuracy', 'Ranged Attack': 'ranged_attack',
    'Magic Accuracy': 'magic_accuracy', 'Magic Attack': 'magic_attack',
    'Magic Damage': 'magic_damage', 'Magic Accuracy Skill': 'magic_accuracy_skill',
    '"Mag.Atk.Bns."': 'magic_attack',
    'Defense': 'defense', 'Evasion': 'evasion',
    'Magic Evasion': 'magic_evasion', 'Magic Defense': 'magic_defense',
    'Store TP': 'store_tp', '"Store TP"': 'store_tp', 'TP Bonus': 'tp_bonus',
    'DA': 'double_attack', 'TA': 'triple_attack', 'QA': 'quad_attack',
    '"Dbl.Atk."': 'double_attack', '"Triple Atk."': 'triple_attack',
    'Dual Wield': 'dual_wield', '"Dual Wield"': 'dual_wield', 'Gear Haste': 'gear_haste',
    'Crit Rate': 'crit_rate', 'Crit Damage': 'crit_damage',
    '"Crit.hit rate"': 'crit_rate', '"Crit.hit damage"': 'crit_damage',
    'Weapon Skill Damage': 'ws_damage', '"Weapon skill damage"': 'ws_damage',
    'DT': 'damage_taken', 'PDT': 'physical_dt', 'MDT': 'magical_dt',
    'Magic Burst Damage': 'magic_burst_bonus', '"Magic Burst Damage"': 'magic_burst_bonus',
    'Magic Burst Damage II': 'magic_burst_damage_ii', '"Magic Burst Damage II"': 'magic_burst_damage_ii',
    'PDL': 'pdl', 'Skillchain Bonus': 'skillchain_bonus',
    'Fast Cast': 'fast_cast', '"Fast Cast"': 'fast_cast',
    'Cure Potency': 'cure_potency', '"Cure potency"': 'cure_potency',
    'Cure Potency II': 'cure_potency_ii', '"Cure Potency II"': 'cure_potency_ii',
    'Enhancing Duration': 'enhancing_duration', '"Enhancing Duration"': 'enhancing_duration',
    'Enh. Mag. eff. dur.': 'enhancing_duration', '"Enh. Mag. eff. dur."': 'enhancing_duration',
    'Enhancing magic effect duration': 'enhancing_duration',
    'Elemental Magic Skill': 'elemental_magic_skill', '"Elemental Magic Skill"': 'elemental_magic_skill',
    'Dark Magic Skill': 'dark_magic_skill', '"Dark Magic Skill"': 'dark_magic_skill',
    'Enfeebling Magic Skill': 'enfeebling_magic_skill', '"Enfeebling Magic Skill"': 'enfeebling_magic_skill',
    'Divine Magic Skill': 'divine_magic_skill', '"Divine Magic Skill"': 'divine_magic_skill',
    'Healing Magic Skill': 'healing_magic_skill', '"Healing Magic Skill"': 'healing_magic_skill',
    'Enhancing Magic Skill': 'enhancing_magic_skill', '"Enhancing Magic Skill"': 'enhancing_magic_skill',
    'Ninjutsu Skill': 'ninjutsu_skill', '"Ninjutsu Skill"': 'ninjutsu_skill',
    'Blue Magic Skill': 'blue_magic_skill', '"Blue Magic Skill"': 'blue_magic_skill',
    'Singing Skill': 'singing_skill', '"Singing Skill"': 'singing_skill',
    'Summoning Skill': 'summoning_magic_skill', '"Summoning Skill"': 'summoning_magic_skill',
    'Geomancy Skill': 'geomancy_skill', '"Geomancy Skill"': 'geomancy_skill',
    'Handbell Skill': 'handbell_skill', '"Handbell Skill"': 'handbell_skill',
    'Hand-to-Hand Skill': 'hand_to_hand_skill', 'Dagger Skill': 'dagger_skill',
    'Sword Skill': 'sword_skill', 'Great Sword Skill': 'great_sword_skill',
    'Axe Skill': 'axe_skill', 'Great Axe Skill': 'great_axe_skill',
    'Scythe Skill': 'scythe_skill', 'Polearm Skill': 'polearm_skill',
    'Katana Skill': 'katana_skill', 'Great Katana Skill': 'great_katana_skill',
    'Club Skill': 'club_skill', 'Staff Skill': 'staff_skill',
    'Archery Skill': 'archery_skill', 'Marksmanship Skill': 'marksmanship_skill',
    'Throwing Skill': 'throwing_skill', 'Shield Skill': 'shield_skill',
    'Double Shot': 'double_shot', 'Triple Shot': 'triple_shot',
    'True Shot': 'true_shot', 'Barrage': 'barrage', 'Recycle': 'recycle',
    'Daken': 'daken', 'Martial Arts': 'martial_arts', 'Zanshin': 'zanshin',
    'Kick Attacks': 'kick_attacks', 'Subtle Blow': 'subtle_blow',
    'Subtle Blow II': 'subtle_blow_ii', 'Fencer': 'fencer',
    'Conserve TP': 'conserve_tp', 'Regain': 'regain',
    'OA2': 'oa2', 'OA3': 'oa3', 'OA4': 'oa4', 'OA5': 'oa5',
    'OA6': 'oa6', 'OA7': 'oa7', 'OA8': 'oa8', 'FUA': 'fua',
    'Fire Elemental Bonus': 'fire_elemental_bonus',
    'Ice Elemental Bonus': 'ice_elemental_bonus',
    'Wind Elemental Bonus': 'wind_elemental_bonus',
    'Earth Elemental Bonus': 'earth_elemental_bonus',
    'Lightning Elemental Bonus': 'lightning_elemental_bonus',
    'Water Elemental Bonus': 'water_elemental_bonus',
    'Light Elemental Bonus': 'light_elemental_bonus',
    'Dark Elemental Bonus': 'dark_elemental_bonus',
    'EnSpell Damage': 'enspell_damage', 'Ninjutsu Magic Attack': 'ninjutsu_magic_attack',
    'Blood Pact Damage': 'blood_pact_damage', 'Occult Acumen': 'occult_acumen',
    'Enfeebling magic effect': 'enfeebling_effect', '"Enfeebling magic effect"': 'enfeebling_effect',
    'Enfeebling Magic Effect': 'enfeebling_effect',
    'Drain and Aspir potency': 'drain_aspir_potency', '"Drain and Aspir potency"': 'drain_aspir_potency',
    'Drain/Aspir potency': 'drain_aspir_potency',
    'Sword enhancement spell damage': 'sword_enhancement_flat',
    '"Sword enhancement spell damage"': 'sword_enhancement_flat',
    'Sword enhancement spell dmg.': 'sword_enhancement_percent',
    '"Sword enhancement spell dmg."': 'sword_enhancement_percent',
}

PERCENTAGE_STATS = frozenset({
    'double_attack', 'triple_attack', 'quad_attack', 'dual_wield', 'gear_haste',
    'crit_rate', 'crit_damage', 'ws_damage', 'damage_taken', 'physical_dt', 'magical_dt',
    'magic_burst_bonus', 'magic_burst_damage_ii', 'pdl', 'skillchain_bonus',
    'fast_cast', 'cure_potency', 'cure_potency_ii', 'blood_pact_damage',
    'enhancing_duration', 'drain_aspir_potency', 'sword_enhancement_percent',
})


# =============================================================================
# NUMBA KERNELS
# =============================================================================

@numba.jit(nopython=True, cache=True, fastmath=True)
def _expand_and_score_kernel(
    # Beam state
    beam_stats,         # (beam_size, n_stats) float64
    beam_gear,          # (beam_size, n_slots) int32 - item index per slot
    beam_used,          # (beam_size, n_unique_items) int16 - usage counts
    
    # Items for this slot
    item_stats,         # (n_items, n_stats) float64
    item_ids,           # (n_items,) int32 - global item ID, -1 for Empty
    
    # Ownership
    owned_counts,       # (n_unique_items,) int16
    
    # Scoring
    weight_vector,      # (n_stats,) float64
    hard_cap_indices,   # (n_hard_caps,) int32
    hard_cap_values,    # (n_hard_caps,) float64
    hard_cap_is_neg,    # (n_hard_caps,) bool
    soft_cap_indices,   # (n_soft_caps,) int32
    soft_cap_values,    # (n_soft_caps,) float64
    
    # Slot info
    slot_idx,           # int32 - which slot we're filling
    pair_slot_idx,      # int32 - paired slot for canonical ordering, -1 if N/A
    
    # Output arrays (pre-allocated for max_expansions)
    out_scores,         # (max_expansions,) float64
    out_beam_idx,       # (max_expansions,) int32
    out_item_idx,       # (max_expansions,) int32
) -> int:
    """
    Expand beam by trying all items for a slot.
    
    Only outputs (score, beam_idx, item_idx) tuples - reconstruction happens later.
    Returns count of valid expansions.
    """
    beam_size = beam_stats.shape[0]
    n_items = item_stats.shape[0]
    n_stats = beam_stats.shape[1]
    n_hard_caps = len(hard_cap_indices)
    n_soft_caps = len(soft_cap_indices)
    
    n_valid = 0
    
    for b in range(beam_size):
        # Get pair item ID for canonical ordering
        pair_item_id = -1
        if pair_slot_idx >= 0:
            pair_item_idx = beam_gear[b, pair_slot_idx]
            if pair_item_idx >= 0:
                pair_item_id = item_ids[pair_item_idx]
        
        for i in range(n_items):
            item_id = item_ids[i]
            
            # Skip if we don't own enough copies (-1 means Empty, always valid)
            if item_id >= 0:
                if beam_used[b, item_id] >= owned_counts[item_id]:
                    continue
            
            # Canonical ordering: skip if item_id < pair_item_id
            if pair_item_id >= 0 and item_id >= 0 and item_id < pair_item_id:
                continue
            
            # Compute score directly without storing full stats
            score = 0.0
            for s in range(n_stats):
                val = beam_stats[b, s] + item_stats[i, s]
                score += val * weight_vector[s]
            
            # Apply hard cap adjustments
            for c in range(n_hard_caps):
                s = hard_cap_indices[c]
                cap = hard_cap_values[c]
                val = beam_stats[b, s] + item_stats[i, s]
                if hard_cap_is_neg[c]:
                    # Negative cap (e.g., DT -50%): value should not go below cap
                    if val < cap:
                        # We over-counted, remove the excess contribution
                        score -= (val - cap) * weight_vector[s]
                else:
                    # Positive cap: value should not exceed cap
                    if val > cap:
                        score -= (val - cap) * weight_vector[s]
            
            # Apply soft cap penalties
            for c in range(n_soft_caps):
                s = soft_cap_indices[c]
                cap = soft_cap_values[c]
                val = beam_stats[b, s] + item_stats[i, s]
                if val > cap:
                    excess = val - cap
                    score -= excess * weight_vector[s] * 0.9
            
            # Store result
            out_scores[n_valid] = score
            out_beam_idx[n_valid] = b
            out_item_idx[n_valid] = i
            n_valid += 1
    
    return n_valid


@numba.jit(nopython=True, cache=True, parallel=True)
def _reconstruct_topk_kernel(
    # Selection indices
    topk_indices,       # (k,) int32 - indices into out_* arrays
    out_beam_idx,       # (n_valid,) int32
    out_item_idx,       # (n_valid,) int32
    out_scores,         # (n_valid,) float64
    
    # Source beam
    beam_stats,         # (beam_size, n_stats) float64
    beam_gear,          # (beam_size, n_slots) int32
    beam_used,          # (beam_size, n_unique_items) int16
    
    # Item data
    item_stats,         # (n_items, n_stats) float64
    item_ids,           # (n_items,) int32
    
    # Slot info
    slot_idx,           # int32
    
    # Output arrays (pre-allocated for k)
    new_stats,          # (k, n_stats) float64
    new_gear,           # (k, n_slots) int32
    new_used,           # (k, n_unique_items) int16
    new_scores,         # (k,) float64
):
    """Reconstruct full candidate data for top-k selections."""
    k = len(topk_indices)
    n_stats = beam_stats.shape[1]
    n_slots = beam_gear.shape[1]
    n_unique = beam_used.shape[1]
    
    for i in numba.prange(k):
        idx = topk_indices[i]
        b = out_beam_idx[idx]
        item = out_item_idx[idx]
        item_id = item_ids[item]
        
        # Copy and add stats
        for s in range(n_stats):
            new_stats[i, s] = beam_stats[b, s] + item_stats[item, s]
        
        # Copy gear and update slot
        for sl in range(n_slots):
            new_gear[i, sl] = beam_gear[b, sl]
        new_gear[i, slot_idx] = item
        
        # Copy used counts and increment
        for u in range(n_unique):
            new_used[i, u] = beam_used[b, u]
        if item_id >= 0:
            new_used[i, item_id] += 1
        
        new_scores[i] = out_scores[idx]


# =============================================================================
# NUMBA BEAM SEARCH OPTIMIZER
# =============================================================================

class NumbaBeamSearchOptimizer:
    """
    Numba-accelerated beam search optimizer.
    
    Drop-in replacement for BeamSearchOptimizer with same interface.
    Optimized for beam_width > 1000 using JIT-compiled kernels.
    """
    
    def __init__(
        self,
        inventory: Inventory,
        profile: OptimizationProfile,
        beam_width: int = 25,
        job: Optional[Job] = None,
        include_weapons: bool = False,
    ):
        self.inventory = inventory
        self.profile = profile
        self.beam_width = beam_width
        self.job = job or profile.job
        self.include_weapons = include_weapons
        
        # Item storage (original format for output)
        self._items: Dict[str, List[Dict[str, Any]]] = {}
        
        # Numeric arrays for Numba
        self._item_stats: Dict[str, np.ndarray] = {}   # slot -> (n_items, n_stats)
        self._item_ids: Dict[str, np.ndarray] = {}     # slot -> (n_items,) global item IDs
        
        # Global item ID mapping
        self._name2_to_id: Dict[str, int] = {}  # name2 -> global ID
        self._id_to_name2: List[str] = []       # global ID -> name2
        self._owned_counts: np.ndarray = None   # (n_unique,) owned count per item
        
        # Weight vector and caps for scoring
        self._weight_vector = np.zeros(N_STATS, dtype=np.float64)
        self._hard_cap_indices: np.ndarray = None
        self._hard_cap_values: np.ndarray = None
        self._hard_cap_is_neg: np.ndarray = None
        self._soft_cap_indices: np.ndarray = None
        self._soft_cap_values: np.ndarray = None
        
        # Build everything
        self._setup_scoring()
        self._build_item_pools()
        self._finalize_owned_counts()
    
    def _setup_scoring(self):
        """Set up weight vector and cap arrays for Numba."""
        # Weight vector
        for stat_name, weight in self.profile.weights.items():
            if stat_name in STAT_TO_INDEX:
                self._weight_vector[STAT_TO_INDEX[stat_name]] = weight
        
        # Hard caps
        hard_caps = []
        for stat_name, cap in self.profile.hard_caps.items():
            if stat_name in STAT_TO_INDEX:
                hard_caps.append((STAT_TO_INDEX[stat_name], cap, cap < 0))
        
        if hard_caps:
            self._hard_cap_indices = np.array([h[0] for h in hard_caps], dtype=np.int32)
            self._hard_cap_values = np.array([h[1] for h in hard_caps], dtype=np.float64)
            self._hard_cap_is_neg = np.array([h[2] for h in hard_caps], dtype=np.bool_)
        else:
            self._hard_cap_indices = np.zeros(0, dtype=np.int32)
            self._hard_cap_values = np.zeros(0, dtype=np.float64)
            self._hard_cap_is_neg = np.zeros(0, dtype=np.bool_)
        
        # Soft caps
        soft_caps = []
        for stat_name, cap in self.profile.soft_caps.items():
            if stat_name in STAT_TO_INDEX:
                soft_caps.append((STAT_TO_INDEX[stat_name], cap))
        
        if soft_caps:
            self._soft_cap_indices = np.array([s[0] for s in soft_caps], dtype=np.int32)
            self._soft_cap_values = np.array([s[1] for s in soft_caps], dtype=np.float64)
        else:
            self._soft_cap_indices = np.zeros(0, dtype=np.int32)
            self._soft_cap_values = np.zeros(0, dtype=np.float64)
    
    def _get_or_create_item_id(self, name2: str) -> int:
        """Get or create a global item ID for a name2."""
        if name2 == 'Empty':
            return -1  # Special ID for Empty
        
        if name2 not in self._name2_to_id:
            new_id = len(self._id_to_name2)
            self._name2_to_id[name2] = new_id
            self._id_to_name2.append(name2)
        
        return self._name2_to_id[name2]
    
    def _gear_to_stats_array(self, gear_dict: Dict[str, Any]) -> np.ndarray:
        """Convert wsdist gear dict to numpy stats array."""
        stats = np.zeros(N_STATS, dtype=np.float64)
        
        for wsdist_key, stat_name in WSDIST_TO_STAT.items():
            if wsdist_key in gear_dict:
                value = gear_dict[wsdist_key]
                if stat_name in STAT_TO_INDEX:
                    if stat_name in PERCENTAGE_STATS:
                        value = value * 100
                    stats[STAT_TO_INDEX[stat_name]] = value
        
        return stats
    
    def _score_stats_array(self, stats: np.ndarray) -> float:
        """Score a stats array (for filtering during pool building)."""
        adjusted = stats.copy()
        
        for i, idx in enumerate(self._hard_cap_indices):
            cap = self._hard_cap_values[i]
            if self._hard_cap_is_neg[i]:
                adjusted[idx] = max(adjusted[idx], cap)
            else:
                adjusted[idx] = min(adjusted[idx], cap)
        
        score = np.dot(adjusted, self._weight_vector)
        
        for i, idx in enumerate(self._soft_cap_indices):
            cap = self._soft_cap_values[i]
            if stats[idx] > cap:
                excess = stats[idx] - cap
                score -= excess * self._weight_vector[idx] * 0.9
        
        return score
    
    def _build_item_pools(self):
        """Build item pools with numeric arrays for Numba."""
        slots_to_build = ALL_SLOTS if self.include_weapons else ARMOR_SLOTS
        
        # Temporary storage for owned counts (will finalize after all items processed)
        temp_owned: Dict[str, int] = {}
        counted_item_ids: Set[int] = set()
        
        def count_item(item_instance, name2: str):
            item_id = id(item_instance)
            if item_id not in counted_item_ids:
                counted_item_ids.add(item_id)
                temp_owned[name2] = temp_owned.get(name2, 0) + 1
        
        for wsdist_slot in slots_to_build:
            if wsdist_slot in ('ear2', 'ring2'):
                continue
            
            slot_enum = WSDIST_TO_SLOT.get(wsdist_slot)
            if slot_enum is None:
                continue
            
            # Get items
            if wsdist_slot == 'ear1':
                items = (
                    self.inventory.get_items_for_slot(Slot.LEFT_EAR, self.job) +
                    self.inventory.get_items_for_slot(Slot.RIGHT_EAR, self.job)
                )
            elif wsdist_slot == 'ring1':
                items = (
                    self.inventory.get_items_for_slot(Slot.LEFT_RING, self.job) +
                    self.inventory.get_items_for_slot(Slot.RIGHT_RING, self.job)
                )
            else:
                items = self.inventory.get_items_for_slot(slot_enum, self.job)
            
            # Convert and filter
            item_dict: Dict[str, Tuple[Dict[str, Any], np.ndarray]] = {}
            
            for item in items:
                try:
                    augment_str = ""
                    if item.rank > 0 and item.has_path_augment:
                        for aug in item.augments_raw:
                            if isinstance(aug, str) and aug.startswith("Path:"):
                                path_letter = aug.split(":")[1].strip()
                                augment_str = f"Path: {path_letter} R{item.rank}"
                                break
                    
                    wsdist_gear = to_wsdist_gear(item, augment_str)
                    name2 = wsdist_gear.get('Name2', wsdist_gear.get('Name', 'Unknown'))
                    
                    stats_array = self._gear_to_stats_array(wsdist_gear)
                    item_score = self._score_stats_array(stats_array)
                    
                    if item_score <= 0:
                        continue
                    
                    count_item(item, name2)
                    self._get_or_create_item_id(name2)  # Ensure ID exists
                    
                    if name2 not in item_dict:
                        item_dict[name2] = (wsdist_gear, stats_array)
                    
                except Exception as e:
                    print(f"Warning: Failed to convert {item.name}: {e}")
            
            # Convert to arrays
            if item_dict:
                names = list(item_dict.keys())
                items_list = [item_dict[n][0] for n in names]
                stats_list = [item_dict[n][1] for n in names]
                ids_list = [self._get_or_create_item_id(n) for n in names]
                
                self._items[wsdist_slot] = items_list
                self._item_stats[wsdist_slot] = np.array(stats_list, dtype=np.float64)
                self._item_ids[wsdist_slot] = np.array(ids_list, dtype=np.int32)
            else:
                self._items[wsdist_slot] = []
                self._item_stats[wsdist_slot] = np.zeros((0, N_STATS), dtype=np.float64)
                self._item_ids[wsdist_slot] = np.zeros(0, dtype=np.int32)
        
        # Copy for paired slots
        for slot1, slot2 in [('ear1', 'ear2'), ('ring1', 'ring2')]:
            if slot1 in self._items:
                self._items[slot2] = self._items[slot1]
                self._item_stats[slot2] = self._item_stats[slot1]
                self._item_ids[slot2] = self._item_ids[slot1]
        
        # Handle weapon sub slot
        if self.include_weapons and 'main' in self._items:
            sub_items = list(self._items.get('sub', []))
            sub_stats = list(self._item_stats.get('sub', []))
            sub_ids = list(self._item_ids.get('sub', []))
            
            existing_names = {item.get('Name2', item.get('Name')) for item in sub_items}
            
            for i, item in enumerate(self._items.get('main', [])):
                name2 = item.get('Name2', item.get('Name'))
                if name2 not in existing_names:
                    sub_items.append(item)
                    sub_stats.append(self._item_stats['main'][i])
                    sub_ids.append(self._item_ids['main'][i])
            
            self._items['sub'] = sub_items
            if sub_stats:
                self._item_stats['sub'] = np.array(sub_stats, dtype=np.float64)
                self._item_ids['sub'] = np.array(sub_ids, dtype=np.int32)
        
        # Store temp_owned for finalization
        self._temp_owned = temp_owned
        
        print(f"Built item pools: {', '.join(f'{k}:{len(v)}' for k, v in self._items.items())}")
        print(f"Unique items tracked: {len(self._id_to_name2)}")
    
    def _finalize_owned_counts(self):
        """Convert owned counts to numpy array."""
        n_unique = len(self._id_to_name2)
        self._owned_counts = np.zeros(max(n_unique, 1), dtype=np.int16)
        
        for name2, count in self._temp_owned.items():
            if name2 in self._name2_to_id:
                self._owned_counts[self._name2_to_id[name2]] = count
        
        del self._temp_owned
    
    def get_items_for_slot(self, slot: str) -> List[Dict[str, Any]]:
        """Get available items for a slot in wsdist format."""
        return self._items.get(slot, [])
    
    def search(
        self,
        fixed_gear: Optional[Dict[str, Dict[str, Any]]] = None,
        slots_to_optimize: Optional[List[str]] = None,
    ) -> List[GearsetCandidate]:
        """
        Run beam search to find top gearset candidates.
        
        Same interface as BeamSearchOptimizer.search().
        """
        if slots_to_optimize is None:
            slots_to_optimize = ALL_SLOTS if self.include_weapons else ARMOR_SLOTS
        
        # Initialize beam arrays
        beam_stats = np.zeros((1, N_STATS), dtype=np.float64)
        beam_gear = np.full((1, N_SLOTS), -1, dtype=np.int32)
        beam_used = np.zeros((1, max(len(self._id_to_name2), 1)), dtype=np.int16)
        beam_scores = np.zeros(1, dtype=np.float64)
        
        # Track fixed gear for reconstruction
        self._fixed_gear = fixed_gear or {}
        self._fixed_gear_stats: Dict[str, np.ndarray] = {}
        
        # Add fixed gear
        if fixed_gear:
            for slot, gear in fixed_gear.items():
                slot_idx = SLOT_TO_IDX[slot]
                gear_stats = self._gear_to_stats_array(gear)
                beam_stats[0] += gear_stats
                beam_gear[0, slot_idx] = -2  # -2 means fixed gear
                self._fixed_gear_stats[slot] = gear_stats
                
                name2 = gear.get('Name2', gear.get('Name', 'Empty'))
                if name2 != 'Empty':
                    item_id = self._get_or_create_item_id(name2)
                    if item_id >= 0 and item_id < len(beam_used[0]):
                        beam_used[0, item_id] += 1
            
            beam_scores[0] = self._score_stats_array(beam_stats[0])
        
        # Pre-allocate output arrays for expansion (worst case size)
        max_items_per_slot = max(len(v) for v in self._items.values()) if self._items else 1
        max_expansions = self.beam_width * max_items_per_slot
        
        out_scores = np.zeros(max_expansions, dtype=np.float64)
        out_beam_idx = np.zeros(max_expansions, dtype=np.int32)
        out_item_idx = np.zeros(max_expansions, dtype=np.int32)
        
        # Process each slot
        for slot in slots_to_optimize:
            if slot in self._fixed_gear:
                continue
            
            slot_idx = SLOT_TO_IDX[slot]
            pair_slot_idx = PAIR_SLOT_MAP.get(slot_idx, -1)
            
            item_stats = self._item_stats.get(slot)
            item_ids = self._item_ids.get(slot)
            items = self._items.get(slot, [])
            
            if item_stats is None or len(items) == 0:
                print(f"  {slot}: No items available, skipping")
                continue
            
            n_items = len(items)
            beam_size = len(beam_stats)
            
            # Special handling for sub slot with weapon filtering
            if slot == 'sub' and self.include_weapons:
                beam_stats, beam_gear, beam_used, beam_scores = self._process_sub_slot(
                    beam_stats, beam_gear, beam_used, beam_scores,
                    item_stats, item_ids, items, slot_idx
                )
                continue
            
            print(f"  {slot}: Testing {n_items} items across {beam_size} candidates...")
            
            # Run Numba kernel
            n_valid = _expand_and_score_kernel(
                beam_stats, beam_gear, beam_used,
                item_stats, item_ids,
                self._owned_counts,
                self._weight_vector,
                self._hard_cap_indices, self._hard_cap_values, self._hard_cap_is_neg,
                self._soft_cap_indices, self._soft_cap_values,
                slot_idx, pair_slot_idx,
                out_scores, out_beam_idx, out_item_idx
            )
            
            if n_valid == 0:
                print(f"    No valid expansions!")
                continue
            
            # Select top-k using argpartition (O(n) average)
            k = min(self.beam_width, n_valid)
            if n_valid > k:
                # argpartition gives indices of k largest (unsorted)
                topk_indices = np.argpartition(out_scores[:n_valid], -k)[-k:]
            else:
                topk_indices = np.arange(n_valid, dtype=np.int32)
            
            # Allocate new beam arrays
            new_stats = np.zeros((k, N_STATS), dtype=np.float64)
            new_gear = np.zeros((k, N_SLOTS), dtype=np.int32)
            new_used = np.zeros((k, len(self._owned_counts)), dtype=np.int16)
            new_scores = np.zeros(k, dtype=np.float64)
            
            # Reconstruct top-k candidates
            _reconstruct_topk_kernel(
                topk_indices.astype(np.int32), out_beam_idx, out_item_idx, out_scores,
                beam_stats, beam_gear, beam_used,
                item_stats, item_ids,
                slot_idx,
                new_stats, new_gear, new_used, new_scores
            )
            
            beam_stats = new_stats
            beam_gear = new_gear
            beam_used = new_used
            beam_scores = new_scores
            
            # Print progress
            best_idx = np.argmax(beam_scores)
            worst_idx = np.argmin(beam_scores)
            top_item_idx = beam_gear[best_idx, slot_idx]
            top_item_name = items[top_item_idx].get('Name2', 'Unknown') if top_item_idx >= 0 else 'Unknown'
            
            print(f"    Top score: {beam_scores[best_idx]:.1f}, "
                  f"Bottom score: {beam_scores[worst_idx]:.1f}")
            print(f"    Winner: {top_item_name}")
        
        # Convert to GearsetCandidate objects
        return self._convert_to_gearset_candidates(beam_stats, beam_gear, beam_used, beam_scores)
    
    def _process_sub_slot(
        self,
        beam_stats: np.ndarray,
        beam_gear: np.ndarray,
        beam_used: np.ndarray,
        beam_scores: np.ndarray,
        item_stats: np.ndarray,
        item_ids: np.ndarray,
        items: List[Dict[str, Any]],
        slot_idx: int,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Handle sub slot with weapon-dependent filtering (done in Python)."""
        print(f"  sub: Filtering based on main weapon type...")
        
        beam_size = len(beam_stats)
        main_slot_idx = SLOT_TO_IDX['main']
        
        # Collect all valid expansions
        expansions = []
        
        for b in range(beam_size):
            # Get main weapon
            main_gear_idx = beam_gear[b, main_slot_idx]
            if main_gear_idx == -2:  # Fixed gear
                main_weapon = self._fixed_gear.get('main')
            elif main_gear_idx >= 0:
                main_weapon = self._items['main'][main_gear_idx]
            else:
                main_weapon = None
            
            # Filter valid sub items
            for i, item in enumerate(items):
                if main_weapon and not is_valid_sub_for_main(item, main_weapon):
                    continue
                
                item_id = item_ids[i]
                
                # Check ownership
                if item_id >= 0:
                    if beam_used[b, item_id] >= self._owned_counts[item_id]:
                        continue
                
                # Compute score
                new_stat = beam_stats[b] + item_stats[i]
                score = self._score_stats_array(new_stat)
                
                expansions.append((score, b, i))
        
        if not expansions:
            return beam_stats, beam_gear, beam_used, beam_scores
        
        # Select top-k
        k = min(self.beam_width, len(expansions))
        expansions.sort(key=lambda x: x[0], reverse=True)
        top_expansions = expansions[:k]
        
        # Reconstruct
        new_stats = np.zeros((k, N_STATS), dtype=np.float64)
        new_gear = np.zeros((k, N_SLOTS), dtype=np.int32)
        new_used = np.zeros((k, len(self._owned_counts)), dtype=np.int16)
        new_scores = np.zeros(k, dtype=np.float64)
        
        for idx, (score, b, i) in enumerate(top_expansions):
            new_stats[idx] = beam_stats[b] + item_stats[i]
            new_gear[idx] = beam_gear[b]
            new_gear[idx, slot_idx] = i
            new_used[idx] = beam_used[b]
            item_id = item_ids[i]
            if item_id >= 0:
                new_used[idx, item_id] += 1
            new_scores[idx] = score
        
        print(f"    Valid subs found. Top score: {new_scores[0]:.1f}, "
              f"Bottom score: {new_scores[-1]:.1f}")
        
        return new_stats, new_gear, new_used, new_scores
    
    def _convert_to_gearset_candidates(
        self,
        beam_stats: np.ndarray,
        beam_gear: np.ndarray,
        beam_used: np.ndarray,
        beam_scores: np.ndarray,
    ) -> List[GearsetCandidate]:
        """Convert numpy arrays back to GearsetCandidate objects."""
        # Sort by score descending
        sorted_indices = np.argsort(beam_scores)[::-1]
        
        result = []
        for idx in sorted_indices:
            candidate = GearsetCandidate()
            candidate.score = float(beam_scores[idx])
            
            # Reconstruct gear dict
            for slot_name, slot_idx in SLOT_TO_IDX.items():
                item_idx = beam_gear[idx, slot_idx]
                
                if item_idx == -2:  # Fixed gear
                    if slot_name in self._fixed_gear:
                        candidate.gear[slot_name] = self._fixed_gear[slot_name].copy()
                elif item_idx >= 0:
                    candidate.gear[slot_name] = self._items[slot_name][item_idx].copy()
            
            # Reconstruct used_items dict
            for item_id in range(len(beam_used[idx])):
                count = beam_used[idx, item_id]
                if count > 0:
                    name2 = self._id_to_name2[item_id]
                    candidate.used_items[name2] = int(count)
            
            # Reconstruct Stats object
            candidate.stats = self._array_to_stats(beam_stats[idx])
            
            # Sub magic accuracy skill
            if 'sub' in candidate.gear:
                sub_stats = self._gear_to_stats_array(candidate.gear['sub'])
                magic_acc_idx = STAT_TO_INDEX.get('magic_accuracy_skill', -1)
                if magic_acc_idx >= 0:
                    candidate.sub_magic_accuracy_skill = int(sub_stats[magic_acc_idx])
            
            result.append(candidate)
        
        return result
    
    def _array_to_stats(self, arr: np.ndarray) -> Stats:
        """Convert numpy stats array back to Stats object."""
        stats = Stats()
        for i, field_name in enumerate(STAT_FIELDS):
            setattr(stats, field_name, int(arr[i]))
        return stats
    
    def extract_item_pool(
        self,
        contenders: List[GearsetCandidate]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Extract the union of items across all contender gearsets."""
        pool: Dict[str, Dict[str, Dict[str, Any]]] = {}
        
        for candidate in contenders:
            for slot, gear in candidate.gear.items():
                if slot not in pool:
                    pool[slot] = {}
                
                name2 = gear.get('Name2', gear.get('Name', 'Unknown'))
                if name2 not in pool[slot]:
                    pool[slot][name2] = gear
        
        result = {slot: list(items.values()) for slot, items in pool.items()}
        
        # Print summary
        print("\n" + "=" * 70)
        print("ITEM POOL REDUCTION SUMMARY")
        print("=" * 70)
        print(f"{'Slot':<10} {'Initial':>8} {'Final':>8} {'Reduction':>10}")
        print("-" * 40)
        
        total_initial = 0
        total_final = 0
        
        for slot in WSDIST_SLOTS:
            initial_count = len(self._items.get(slot, []))
            final_count = len(result.get(slot, []))
            total_initial += initial_count
            total_final += final_count
            
            if initial_count > 0:
                reduction_pct = ((initial_count - final_count) / initial_count) * 100
                print(f"{slot:<10} {initial_count:>8} {final_count:>8} {reduction_pct:>9.1f}%")
        
        print("-" * 40)
        if total_initial > 0:
            total_reduction = ((total_initial - total_final) / total_initial) * 100
            print(f"{'TOTAL':<10} {total_initial:>8} {total_final:>8} {total_reduction:>9.1f}%")
        
        return result
    
    def print_contenders(self, contenders: List[GearsetCandidate]):
        """Print a summary of the contender gearsets."""
        print("\n" + "=" * 70)
        print("CONTENDER GEARSETS")
        print("=" * 70)
        
        for i, candidate in enumerate(contenders[:10]):
            print(f"\n--- Contender #{i+1} (Score: {candidate.score:.1f}) ---")
            for slot in WSDIST_SLOTS:
                if slot in candidate.gear:
                    name = candidate.gear[slot].get('Name2',
                           candidate.gear[slot].get('Name', 'Empty'))
                    print(f"  {slot:12s}: {name}")
    
    def print_item_pool(self, pool: Dict[str, List[Dict[str, Any]]]):
        """Print a summary of the reduced item pool."""
        print("\n" + "=" * 70)
        print("REDUCED ITEM POOL FOR WSDIST")
        print("=" * 70)
        
        for slot in WSDIST_SLOTS:
            if slot in pool:
                items = pool[slot]
                names = [g.get('Name2', g.get('Name', '?')) for g in items]
                print(f"\n{slot} ({len(items)} items):")
                for name in names:
                    print(f"  - {name}")
