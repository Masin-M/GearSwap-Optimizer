"""
Beam Search Optimizer for Gear Selection

This module implements beam search to narrow down gear candidates from a player's
inventory before passing to wsdist for full simulation-based optimization.

The workflow:
1. Load inventory → Filter by job/slot → All candidate items per slot
2. Beam Search (weighted scoring) → N contender gearsets
3. Extract item pool from contenders → Reduced set per slot
4. Pass to wsdist's build_set for final optimization

Author: Integration layer for GSO + wsdist
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from copy import deepcopy

from pathlib import Path
SCRIPT_DIR = Path(__file__).parent
WSDIST_DIR = SCRIPT_DIR / 'wsdist_beta-main'

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(WSDIST_DIR))
# Local imports - adjust paths as needed
from models import (
    Stats, Slot, Job, Container,
    OptimizationProfile, BuffContext,
    create_priority_profile,
    SLOT_BITMASK, EQUIPPABLE_CONTAINERS
)
from inventory_loader import Inventory, load_inventory
from wsdist_converter import to_wsdist_gear


# =============================================================================
# WEAPON TYPE CLASSIFICATION
# =============================================================================

# Two-handed weapon skill types - these can ONLY use grips in the offhand
TWO_HANDED_SKILLS = frozenset({
    "Great Sword",
    "Great Axe",
    "Scythe",
    "Polearm",
    "Staff",
    "Great Katana",
})

# One-handed weapon skill types - these can use weapons (dual wield), shields, or grips
ONE_HANDED_SKILLS = frozenset({
    "Dagger",
    "Sword",
    "Axe",
    "Club",
    "Katana",
})

# Hand-to-Hand - uses both hands, no sub slot allowed
HAND_TO_HAND_SKILL = "Hand-to-Hand"


def is_two_handed_weapon(weapon: Dict[str, Any]) -> bool:
    """Check if a weapon is two-handed based on its skill type."""
    skill_type = weapon.get("Skill Type", "")
    return skill_type in TWO_HANDED_SKILLS


def is_one_handed_weapon(weapon: Dict[str, Any]) -> bool:
    """Check if a weapon is one-handed based on its skill type."""
    skill_type = weapon.get("Skill Type", "")
    return skill_type in ONE_HANDED_SKILLS


def is_hand_to_hand_weapon(weapon: Dict[str, Any]) -> bool:
    """Check if a weapon is Hand-to-Hand."""
    skill_type = weapon.get("Skill Type", "")
    return skill_type == HAND_TO_HAND_SKILL


def get_valid_sub_types(main_weapon: Dict[str, Any]) -> Set[str]:
    """
    Get the valid sub slot item types based on main weapon.
    
    Args:
        main_weapon: The main hand weapon dict
        
    Returns:
        Set of valid Type values for sub slot items
    """
    if is_hand_to_hand_weapon(main_weapon):
        # H2H uses both hands - no sub allowed
        return set()
    elif is_two_handed_weapon(main_weapon):
        # 2H weapons can only use grips
        return {"Grip"}
    else:
        # 1H weapons can use weapons (dual wield), shields, or grips
        return {"Weapon", "Shield", "Grip"}


def is_valid_sub_for_main(sub_item: Dict[str, Any], main_weapon: Dict[str, Any]) -> bool:
    """
    Check if a sub item is valid for the given main weapon.
    
    Rules:
    - 2-handed weapons can NEVER go in the sub slot
    - Hand-to-Hand weapons can NEVER go in the sub slot
    - If main is H2H: no sub allowed
    - If main is 2H: sub can only be Grip
    - If main is 1H: sub can be 1H Weapon (dual wield), Shield, or Grip
    
    Args:
        sub_item: The potential sub slot item
        main_weapon: The main hand weapon
        
    Returns:
        True if the sub item is valid for this main weapon
    """
    # Empty is always valid (except for H2H where sub is disabled)
    if sub_item.get("Name") == "Empty":
        return not is_hand_to_hand_weapon(main_weapon)
    
    # 2-handed weapons can NEVER go in the sub slot
    if is_two_handed_weapon(sub_item):
        return False
    
    # Hand-to-Hand weapons can NEVER go in the sub slot
    if is_hand_to_hand_weapon(sub_item):
        return False
    
    valid_types = get_valid_sub_types(main_weapon)
    item_type = sub_item.get("Type", "")
    
    return item_type in valid_types


# =============================================================================
# SLOT ORDERING
# =============================================================================

# wsdist slot names in a sensible order for beam search
# Weapons are typically fixed, so we start with high-impact armor slots
WSDIST_SLOTS = ['main', 'sub', 'ranged', 'ammo', 'head', 'neck', 'ear1', 'ear2',
                'body', 'hands', 'ring1', 'ring2', 'back', 'waist', 'legs', 'feet']

# Slots to optimize (excluding weapons which are typically fixed)
ARMOR_SLOTS = ['ammo', 'head', 'neck', 'ear1', 'ear2', 'body', 'hands', 
               'ring1', 'ring2', 'back', 'waist', 'legs', 'feet']

# Weapon slots (main, sub, ranged) - only included when explicitly requested
WEAPON_SLOTS = ['main', 'sub', 'ranged']

# All optimizable slots (weapons + armor)
ALL_SLOTS = WEAPON_SLOTS + ARMOR_SLOTS

# Map from Slot enum to wsdist slot names
SLOT_TO_WSDIST = {
    Slot.MAIN: 'main',
    Slot.SUB: 'sub',
    Slot.RANGE: 'ranged',
    Slot.AMMO: 'ammo',
    Slot.HEAD: 'head',
    Slot.NECK: 'neck',
    Slot.LEFT_EAR: 'ear1',
    Slot.RIGHT_EAR: 'ear2',
    Slot.BODY: 'body',
    Slot.HANDS: 'hands',
    Slot.LEFT_RING: 'ring1',
    Slot.RIGHT_RING: 'ring2',
    Slot.BACK: 'back',
    Slot.WAIST: 'waist',
    Slot.LEGS: 'legs',
    Slot.FEET: 'feet',
}

WSDIST_TO_SLOT = {v: k for k, v in SLOT_TO_WSDIST.items()}


# =============================================================================
# BEAM SEARCH STATE
# =============================================================================

@dataclass
class GearsetCandidate:
    """
    Represents a partial or complete gearset during beam search.
    """
    # The gearset as wsdist-compatible dicts
    gear: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Accumulated stats for quick scoring
    stats: Stats = field(default_factory=Stats)
    
    # Score from the optimization profile
    score: float = 0.0
    
    # Track sub slot stats that need special handling for magic calculations
    # Per nuking.py: "Magic Accuracy Skill" from offhand does NOT contribute to spell accuracy
    sub_magic_accuracy_skill: int = 0
    
    # Track how many of each item (by Name2) are used in this candidate
    # This allows proper handling of duplicate items (e.g., two Genmei Earrings)
    used_items: Dict[str, int] = field(default_factory=dict)
    
    def copy(self) -> 'GearsetCandidate':
        """Create a deep copy of this candidate."""
        new_candidate = GearsetCandidate()
        new_candidate.gear = {k: v.copy() for k, v in self.gear.items()}
        new_candidate.stats = self.stats.copy()
        new_candidate.score = self.score
        new_candidate.sub_magic_accuracy_skill = self.sub_magic_accuracy_skill
        new_candidate.used_items = self.used_items.copy()
        return new_candidate


# =============================================================================
# BEAM SEARCH OPTIMIZER
# =============================================================================

class BeamSearchOptimizer:
    """
    Beam search optimizer for gear selection.
    
    Uses weighted scoring from OptimizationProfile to quickly evaluate
    gear combinations without full simulation. Produces a set of contender
    gearsets that can be passed to wsdist for final optimization.
    """
    
    def __init__(
        self,
        inventory: Inventory,
        profile: OptimizationProfile,
        beam_width: int = 25,
        job: Optional[Job] = None,
        include_weapons: bool = False,
    ):
        """
        Initialize the beam search optimizer.
        
        Args:
            inventory: Player's inventory with parsed items
            profile: Optimization profile with weights and caps
            beam_width: Number of candidates to keep at each step
            job: Job to filter items by (uses profile.job if not specified)
            include_weapons: If True, include weapon slots in optimization (default: False)
        """
        self.inventory = inventory
        self.profile = profile
        self.beam_width = beam_width
        self.job = job or profile.job
        self.include_weapons = include_weapons
        
        # Cache of converted items per slot
        self._item_cache: Dict[str, List[Dict[str, Any]]] = {}
        
        # Track how many of each item (by Name2) the player owns
        # This allows equipping duplicate items (e.g., two Genmei Earrings)
        self._item_counts: Dict[str, int] = {}
        
        # Pre-build item pools
        self._build_item_pools()
    
    def _build_item_pools(self):
        """Build wsdist-compatible item pools for each slot."""
        # Determine which slots to build pools for
        slots_to_build = ALL_SLOTS if self.include_weapons else ARMOR_SLOTS
        
        # Track item counts globally by Name2
        # Use a set to track which physical items we've already counted (by id)
        self._item_counts.clear()
        counted_item_ids: Set[int] = set()  # Track by Python object id to avoid double-counting
        
        # Helper to count an item if not already counted
        def count_item(item_instance, wsdist_gear):
            item_id = id(item_instance)  # Use Python object id as unique identifier
            if item_id not in counted_item_ids:
                counted_item_ids.add(item_id)
                name2 = wsdist_gear.get('Name2', wsdist_gear.get('Name', 'Unknown'))
                if name2 not in self._item_counts:
                    self._item_counts[name2] = 0
                self._item_counts[name2] += 1
        
        # Process each slot
        for wsdist_slot in slots_to_build:
            # Skip second slot of pairs - we'll copy the pool later
            if wsdist_slot in ('ear2', 'ring2'):
                continue
                
            slot_enum = WSDIST_TO_SLOT.get(wsdist_slot)
            if slot_enum is None:
                continue
            
            # Handle slots that can use either left or right position
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
            
            # Convert to wsdist format and count unique items
            # Use dict to deduplicate configurations while counting physical items
            item_dict: Dict[str, Dict[str, Any]] = {}  # Name2 -> wsdist gear
            
            for item in items:
                try:
                    # Build augment string for Name2
                    augment_str = ""
                    if item.rank > 0 and item.has_path_augment:
                        # Find path letter from augments
                        for aug in item.augments_raw:
                            if isinstance(aug, str) and aug.startswith("Path:"):
                                path_letter = aug.split(":")[1].strip()
                                augment_str = f"Path: {path_letter} R{item.rank}"
                                break
                    
                    wsdist_gear = to_wsdist_gear(item, augment_str)
                    name2 = wsdist_gear.get('Name2', wsdist_gear.get('Name', 'Unknown'))
                    
                    # Count this physical item (only once across all slots)
                    count_item(item, wsdist_gear)
                    
                    # Store unique configuration (only need one copy in pool)
                    if name2 not in item_dict:
                        item_dict[name2] = wsdist_gear
                        
                except Exception as e:
                    print(f"Warning: Failed to convert {item.name}: {e}")
            
            self._item_cache[wsdist_slot] = list(item_dict.values())
        
        # For paired slots (ear1/ear2, ring1/ring2), ensure they share the same pool
        # so both slots can access all available items
        if 'ear1' in self._item_cache:
            self._item_cache['ear2'] = self._item_cache['ear1']
        if 'ring1' in self._item_cache:
            self._item_cache['ring2'] = self._item_cache['ring1']
        
        # For weapon optimization, we need to handle sub slot items specially
        # We'll keep all potential sub items in the pool, but filter dynamically
        # during search based on what main weapon is selected
        if self.include_weapons and 'main' in self._item_cache:
            # Build a comprehensive sub pool that includes:
            # - All items originally in sub (shields, grips)
            # - All main-hand weapons (for dual-wield with 1H weapons)
            sub_items = self._item_cache.get('sub', [])
            main_items = self._item_cache.get('main', [])
            
            # Add main-hand weapons to sub pool if not already present
            # The actual filtering based on weapon type happens in search()
            sub_names = {item.get('Name2', item.get('Name')) for item in sub_items}
            for item in main_items:
                name2 = item.get('Name2', item.get('Name'))
                if name2 not in sub_names:
                    sub_items.append(item)
            self._item_cache['sub'] = sub_items
            
        print(f"Built item pools: {', '.join(f'{k}:{len(v)}' for k, v in self._item_cache.items())}")
        print(f"Item counts tracked: {len(self._item_counts)} unique items")
    
    def get_items_for_slot(self, slot: str) -> List[Dict[str, Any]]:
        """Get available items for a slot in wsdist format."""
        return self._item_cache.get(slot, [])
    
    def get_valid_sub_items(self, main_weapon: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Get valid sub slot items based on the main weapon.
        
        Args:
            main_weapon: The selected main weapon, or None
            
        Returns:
            List of valid sub slot items
        """
        all_sub_items = self.get_items_for_slot('sub')
        
        if main_weapon is None:
            return all_sub_items
        
        # Filter based on main weapon type
        return [item for item in all_sub_items 
                if is_valid_sub_for_main(item, main_weapon)]
    
    def _score_stats(self, stats: Stats) -> float:
        """
        Score a stats object using the optimization profile weights.
        
        Applies hard caps and soft caps as penalties.
        """
        score = 0.0
        weights = self.profile.weights
        hard_caps = self.profile.hard_caps
        soft_caps = self.profile.soft_caps
        
        for stat_name, weight in weights.items():
            if not hasattr(stats, stat_name):
                continue
            
            value = getattr(stats, stat_name)
            
            # Check hard cap
            if stat_name in hard_caps:
                cap = hard_caps[stat_name]
                if cap < 0:  # Negative cap (e.g., DT -50%)
                    value = max(value, cap)
                else:
                    value = min(value, cap)
            
            # Apply weight
            contribution = value * weight
            
            # Soft cap penalty - reduced value for exceeding soft cap
            if stat_name in soft_caps:
                soft_cap = soft_caps[stat_name]
                if value > soft_cap:
                    excess = value - soft_cap
                    # Reduce contribution from excess by 90%
                    contribution = soft_cap * weight + excess * weight * 0.1
            
            score += contribution
        
        return score
    
    def _score_gear(self, gear_dict: Dict[str, Any]) -> Tuple[float, Stats]:
        """
        Score a single piece of gear and return its contribution.
        
        Returns:
            (score, stats) tuple
        """
        stats = Stats()
        
        # Map wsdist keys to Stats attributes
        # EXPANDED: Now includes many more stats for magic and other builds
        STAT_MAP = {
            # Primary stats
            'STR': 'STR', 'DEX': 'DEX', 'VIT': 'VIT', 'AGI': 'AGI',
            'INT': 'INT', 'MND': 'MND', 'CHR': 'CHR',
            'HP': 'HP', 'MP': 'MP',
            
            # Offensive stats (flat values)
            'Accuracy': 'accuracy', 'Attack': 'attack',
            'Ranged Accuracy': 'ranged_accuracy', 'Ranged Attack': 'ranged_attack',
            'Magic Accuracy': 'magic_accuracy', 'Magic Attack': 'magic_attack',
            'Magic Damage': 'magic_damage',
            'Magic Accuracy Skill': 'magic_accuracy_skill',
            # Quoted variants for augmented gear (capes, etc.)
            '"Mag.Atk.Bns."': 'magic_attack',
            
            # Defensive stats (flat values)
            'Defense': 'defense', 'Evasion': 'evasion',
            'Magic Evasion': 'magic_evasion', 'Magic Defense': 'magic_defense',
            
            # Store TP (flat value)
            'Store TP': 'store_tp',
            '"Store TP"': 'store_tp',  # Quoted variant
            
            # TP Bonus (flat value)
            'TP Bonus': 'tp_bonus',
            
            # Multi-attack (percentages in wsdist)
            'DA': 'double_attack', 'TA': 'triple_attack', 'QA': 'quad_attack',
            # Quoted variants for augmented gear
            '"Dbl.Atk."': 'double_attack',
            '"Triple Atk."': 'triple_attack',
            
            # Haste and speed (percentages)
            'Dual Wield': 'dual_wield',
            '"Dual Wield"': 'dual_wield',  # Quoted variant
            'Gear Haste': 'gear_haste',
            
            # Critical hit (percentages)
            'Crit Rate': 'crit_rate', 'Crit Damage': 'crit_damage',
            # Quoted variants for augmented gear
            '"Crit.hit rate"': 'crit_rate',
            '"Crit.hit damage"': 'crit_damage',
            
            # Weaponskill damage (percentage)
            'Weapon Skill Damage': 'ws_damage',
            '"Weapon skill damage"': 'ws_damage',  # Quoted variant
            
            # Damage taken (percentages, negative = reduction)
            'DT': 'damage_taken', 'PDT': 'physical_dt', 'MDT': 'magical_dt',
            
            # Magic burst (percentages)
            'Magic Burst Damage': 'magic_burst_bonus',
            '"Magic Burst Damage"': 'magic_burst_bonus',  # Quoted variant
            'Magic Burst Damage II': 'magic_burst_damage_ii',
            '"Magic Burst Damage II"': 'magic_burst_damage_ii',  # Quoted variant
            
            # Physical damage limit
            'PDL': 'pdl',
            
            # Skillchain
            'Skillchain Bonus': 'skillchain_bonus',
            
            # Fast Cast (percentage)
            'Fast Cast': 'fast_cast',
            '"Fast Cast"': 'fast_cast',  # Quoted variant used by augmented gear (capes, etc.)
            
            # Cure Potency
            'Cure Potency': 'cure_potency',
            '"Cure potency"': 'cure_potency',  # Quoted variant
            'Cure Potency II': 'cure_potency_ii',
            '"Cure Potency II"': 'cure_potency_ii',  # Quoted variant
            
            # Enhancing Duration (percentage)
            'Enhancing Duration': 'enhancing_duration',
            '"Enhancing Duration"': 'enhancing_duration',  # Quoted variant
            'Enh. Mag. eff. dur.': 'enhancing_duration',  # Alternative form
            '"Enh. Mag. eff. dur."': 'enhancing_duration',  # Quoted alternative
            'Enhancing magic effect duration': 'enhancing_duration',
            
            # =====================================================
            # MAGIC SKILLS (flat values) - ADDED
            # =====================================================
            'Elemental Magic Skill': 'elemental_magic_skill',
            '"Elemental Magic Skill"': 'elemental_magic_skill',  # Quoted variant
            'Dark Magic Skill': 'dark_magic_skill',
            '"Dark Magic Skill"': 'dark_magic_skill',  # Quoted variant
            'Enfeebling Magic Skill': 'enfeebling_magic_skill',
            '"Enfeebling Magic Skill"': 'enfeebling_magic_skill',  # Quoted variant
            'Divine Magic Skill': 'divine_magic_skill',
            '"Divine Magic Skill"': 'divine_magic_skill',  # Quoted variant
            'Healing Magic Skill': 'healing_magic_skill',
            '"Healing Magic Skill"': 'healing_magic_skill',  # Quoted variant
            'Enhancing Magic Skill': 'enhancing_magic_skill',
            '"Enhancing Magic Skill"': 'enhancing_magic_skill',  # Quoted variant
            'Ninjutsu Skill': 'ninjutsu_skill',
            '"Ninjutsu Skill"': 'ninjutsu_skill',  # Quoted variant
            'Blue Magic Skill': 'blue_magic_skill',
            '"Blue Magic Skill"': 'blue_magic_skill',  # Quoted variant
            'Singing Skill': 'singing_skill',
            '"Singing Skill"': 'singing_skill',  # Quoted variant
            'Summoning Skill': 'summoning_magic_skill',
            '"Summoning Skill"': 'summoning_magic_skill',  # Quoted variant
            'Geomancy Skill': 'geomancy_skill',
            '"Geomancy Skill"': 'geomancy_skill',  # Quoted variant
            'Handbell Skill': 'handbell_skill',
            '"Handbell Skill"': 'handbell_skill',  # Quoted variant
            
            # =====================================================
            # WEAPON SKILLS (flat values) - ADDED
            # =====================================================
            'Hand-to-Hand Skill': 'hand_to_hand_skill',
            'Dagger Skill': 'dagger_skill',
            'Sword Skill': 'sword_skill',
            'Great Sword Skill': 'great_sword_skill',
            'Axe Skill': 'axe_skill',
            'Great Axe Skill': 'great_axe_skill',
            'Scythe Skill': 'scythe_skill',
            'Polearm Skill': 'polearm_skill',
            'Katana Skill': 'katana_skill',
            'Great Katana Skill': 'great_katana_skill',
            'Club Skill': 'club_skill',
            'Staff Skill': 'staff_skill',
            'Archery Skill': 'archery_skill',
            'Marksmanship Skill': 'marksmanship_skill',
            'Throwing Skill': 'throwing_skill',
            'Shield Skill': 'shield_skill',
            
            # =====================================================
            # RANGED-SPECIFIC (flat values) - ADDED
            # =====================================================
            'Double Shot': 'double_shot',
            'Triple Shot': 'triple_shot',
            'True Shot': 'true_shot',
            'Barrage': 'barrage',
            'Recycle': 'recycle',
            
            # =====================================================
            # JOB-SPECIFIC STATS - ADDED
            # =====================================================
            'Daken': 'daken',
            'Martial Arts': 'martial_arts',
            'Zanshin': 'zanshin',
            'Kick Attacks': 'kick_attacks',
            'Subtle Blow': 'subtle_blow',
            'Subtle Blow II': 'subtle_blow_ii',
            'Fencer': 'fencer',
            'Conserve TP': 'conserve_tp',
            'Regain': 'regain',
            
            # =====================================================
            # OCCASIONAL ATTACKS - ADDED
            # =====================================================
            'OA2': 'oa2', 'OA3': 'oa3', 'OA4': 'oa4', 'OA5': 'oa5',
            'OA6': 'oa6', 'OA7': 'oa7', 'OA8': 'oa8',
            'FUA': 'fua',
            
            # =====================================================
            # ELEMENTAL BONUSES - ADDED
            # =====================================================
            'Fire Elemental Bonus': 'fire_elemental_bonus',
            'Ice Elemental Bonus': 'ice_elemental_bonus',
            'Wind Elemental Bonus': 'wind_elemental_bonus',
            'Earth Elemental Bonus': 'earth_elemental_bonus',
            'Lightning Elemental Bonus': 'lightning_elemental_bonus',
            'Water Elemental Bonus': 'water_elemental_bonus',
            'Light Elemental Bonus': 'light_elemental_bonus',
            'Dark Elemental Bonus': 'dark_elemental_bonus',
            
            # =====================================================
            # JOB-SPECIFIC MAGIC - ADDED
            # =====================================================
            'EnSpell Damage': 'enspell_damage',
            'Ninjutsu Magic Attack': 'ninjutsu_magic_attack',
            'Blood Pact Damage': 'blood_pact_damage',
            'Occult Acumen': 'occult_acumen',
        }
        
        # Stats that are percentages in wsdist format and need conversion to basis points
        PERCENTAGE_STATS = {
            'double_attack', 'triple_attack', 'quad_attack',
            'dual_wield', 'gear_haste', 'crit_rate', 'crit_damage',
            'ws_damage', 'damage_taken', 'physical_dt', 'magical_dt',
            'magic_burst_bonus', 'magic_burst_damage_ii', 'pdl',
            'skillchain_bonus', 'fast_cast', 'cure_potency', 'cure_potency_ii',
            'blood_pact_damage', 'enhancing_duration',
        }
        
        for wsdist_key, stat_attr in STAT_MAP.items():
            if wsdist_key in gear_dict:
                value = gear_dict[wsdist_key]
                # Convert percentages to basis points for internal stats
                if stat_attr in PERCENTAGE_STATS:
                    value = value * 100  # Convert % to basis points
                setattr(stats, stat_attr, value)
        
        score = self._score_stats(stats)
        return score, stats
    
    def _score_candidate(self, candidate: GearsetCandidate) -> float:
        """Score a complete or partial gearset candidate."""
        return self._score_stats(candidate.stats)
    
    def _add_stats(self, base: Stats, addition: Stats) -> Stats:
        """Add two Stats objects together."""
        # Use the Stats.__add__ method which properly handles
        # dict fields (skill_bonuses) and list fields (special_effects)
        return base + addition
    
    def search(
        self,
        fixed_gear: Optional[Dict[str, Dict[str, Any]]] = None,
        slots_to_optimize: Optional[List[str]] = None,
    ) -> List[GearsetCandidate]:
        """
        Run beam search to find top gearset candidates.
        
        Args:
            fixed_gear: Pre-selected gear (e.g., weapons) as wsdist dicts
            slots_to_optimize: Which slots to search (defaults to ARMOR_SLOTS, 
                              or ALL_SLOTS if include_weapons was set)
        
        Returns:
            List of top candidates sorted by score (best first)
        """
        if slots_to_optimize is None:
            slots_to_optimize = ALL_SLOTS if self.include_weapons else ARMOR_SLOTS
        
        # Initialize beam with a single empty candidate
        initial = GearsetCandidate()
        
        # Add fixed gear to initial candidate
        if fixed_gear:
            for slot, gear in fixed_gear.items():
                initial.gear[slot] = gear.copy()
                _, gear_stats = self._score_gear(gear)
                initial.stats = self._add_stats(initial.stats, gear_stats)
                
                # Track this item as used
                name2 = gear.get('Name2', gear.get('Name', 'Empty'))
                if name2 != 'Empty':
                    initial.used_items[name2] = initial.used_items.get(name2, 0) + 1
                
                # Track sub slot's Magic Accuracy Skill for proper magic calculations
                # Per nuking.py: offhand's "Magic Accuracy Skill" does NOT contribute to spell accuracy
                if slot == 'sub':
                    initial.sub_magic_accuracy_skill = gear_stats.magic_accuracy_skill
        
        beam = [initial]
        
        # Process each slot
        for slot in slots_to_optimize:
            # For sub slot, we need to filter based on main weapon
            if slot == 'sub' and self.include_weapons:
                # Get items dynamically based on each candidate's main weapon
                print(f"  {slot}: Filtering based on main weapon type...")
                new_beam = []
                
                for candidate in beam:
                    main_weapon = candidate.gear.get('main')
                    valid_sub_items = self.get_valid_sub_items(main_weapon)
                    
                    if not valid_sub_items:
                        # H2H or no valid subs - keep candidate as-is with empty sub
                        new_beam.append(candidate)
                        continue
                    
                    for item in valid_sub_items:
                        name2 = item.get('Name2', item.get('Name', 'Empty'))
                        
                        # Skip Empty items for duplicate checking
                        if name2 != 'Empty':
                            owned_count = self._item_counts.get(name2, 0)
                            used_count = candidate.used_items.get(name2, 0)
                            
                            if used_count >= owned_count:
                                continue
                        
                        # Create new candidate with this item
                        new_candidate = candidate.copy()
                        new_candidate.gear[slot] = item.copy()
                        
                        if name2 != 'Empty':
                            new_candidate.used_items[name2] = new_candidate.used_items.get(name2, 0) + 1
                        
                        _, item_stats = self._score_gear(item)
                        new_candidate.stats = self._add_stats(candidate.stats, item_stats)
                        new_candidate.score = self._score_candidate(new_candidate)
                        new_candidate.sub_magic_accuracy_skill = item_stats.magic_accuracy_skill
                        
                        new_beam.append(new_candidate)
                
                # Prune to beam width
                new_beam.sort(key=lambda c: c.score, reverse=True)
                beam = new_beam[:self.beam_width]
                
                if beam:
                    print(f"    Valid subs found. Top score: {beam[0].score:.1f}, "
                          f"Bottom score: {beam[-1].score:.1f}")
                continue
            
            # Normal slot processing
            items = self.get_items_for_slot(slot)
            
            if not items:
                print(f"  {slot}: No items available, skipping")
                continue
            
            print(f"  {slot}: Testing {len(items)} items across {len(beam)} candidates...")
            
            # Expand beam with all items for this slot
            new_beam = []
            
            for candidate in beam:
                for item in items:
                    name2 = item.get('Name2', item.get('Name', 'Empty'))
                    
                    # Skip Empty items for duplicate checking
                    if name2 != 'Empty':
                        # Check if we have this item available
                        # (owned count > currently used count)
                        owned_count = self._item_counts.get(name2, 0)
                        used_count = candidate.used_items.get(name2, 0)
                        
                        if used_count >= owned_count:
                            # Already using all copies of this item
                            continue
                    
                    # Create new candidate with this item
                    new_candidate = candidate.copy()
                    new_candidate.gear[slot] = item.copy()
                    
                    # Track this item as used
                    if name2 != 'Empty':
                        new_candidate.used_items[name2] = new_candidate.used_items.get(name2, 0) + 1
                    
                    # Update stats and score
                    _, item_stats = self._score_gear(item)
                    new_candidate.stats = self._add_stats(candidate.stats, item_stats)
                    new_candidate.score = self._score_candidate(new_candidate)
                    
                    # Track sub slot's Magic Accuracy Skill for proper magic calculations
                    # Per nuking.py: offhand's "Magic Accuracy Skill" does NOT contribute to spell accuracy
                    if slot == 'sub':
                        new_candidate.sub_magic_accuracy_skill = item_stats.magic_accuracy_skill
                    
                    new_beam.append(new_candidate)
            
            # Prune to beam width
            new_beam.sort(key=lambda c: c.score, reverse=True)
            beam = new_beam[:self.beam_width]
            
            if beam:
                print(f"    Top score: {beam[0].score:.1f}, "
                      f"Bottom score: {beam[-1].score:.1f}")
        
        return beam
    
    def extract_item_pool(
        self,
        contenders: List[GearsetCandidate]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract the union of items across all contender gearsets.
        
        This creates the reduced item pool to pass to wsdist.
        
        Args:
            contenders: List of contender gearsets from beam search
        
        Returns:
            Dict mapping slot name to list of unique items (wsdist format)
        """
        pool: Dict[str, Dict[str, Dict[str, Any]]] = {}  # slot -> name2 -> gear
        
        for candidate in contenders:
            for slot, gear in candidate.gear.items():
                if slot not in pool:
                    pool[slot] = {}
                
                name2 = gear.get('Name2', gear.get('Name', 'Unknown'))
                if name2 not in pool[slot]:
                    pool[slot][name2] = gear
        
        # Convert to list format
        result = {slot: list(items.values()) for slot, items in pool.items()}
        
        return result
    
    def print_contenders(self, contenders: List[GearsetCandidate]):
        """Print a summary of the contender gearsets."""
        print("\n" + "=" * 70)
        print("CONTENDER GEARSETS")
        print("=" * 70)
        
        for i, candidate in enumerate(contenders):
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


# =============================================================================
# INTEGRATION HELPERS
# =============================================================================

def create_empty_gearset() -> Dict[str, Dict[str, Any]]:
    """Create an empty gearset with Empty items in all slots."""
    empty = {"Name": "Empty", "Name2": "Empty", "Skill Type": "None", 
             "Type": "None", "Jobs": ["war", "mnk", "whm", "blm", "rdm", "thf", 
                                       "pld", "drk", "bst", "brd", "rng", "smn", 
                                       "sam", "nin", "drg", "blu", "cor", "pup", 
                                       "dnc", "sch", "geo", "run"]}
    return {slot: empty.copy() for slot in WSDIST_SLOTS}


def prepare_wsdist_check_gear(
    item_pool: Dict[str, List[Dict[str, Any]]],
    fixed_gear: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Prepare the check_gear dict for wsdist's build_set function.
    
    Args:
        item_pool: Reduced item pool from beam search
        fixed_gear: Fixed gear (weapons) to include
    
    Returns:
        check_gear dict for wsdist
    """
    check_gear = {}
    
    for slot in WSDIST_SLOTS:
        if fixed_gear and slot in fixed_gear:
            # Fixed slot - only one option
            check_gear[slot] = [fixed_gear[slot]]
        elif slot in item_pool:
            check_gear[slot] = item_pool[slot]
        else:
            # Empty slot
            check_gear[slot] = [create_empty_gearset()[slot]]
    
    return check_gear


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def optimize_for_weaponskill(
    inventory_path: str,
    job: Job,
    main_weapon: Dict[str, Any],
    sub_weapon: Dict[str, Any],
    ws_type: str = 'physical',  # 'physical', 'magical', 'hybrid'
    beam_width: int = 25,
) -> Tuple[List[GearsetCandidate], Dict[str, List[Dict[str, Any]]]]:
    """
    High-level function to optimize gear for a weaponskill.
    
    Args:
        inventory_path: Path to inventory CSV
        job: Player's job
        main_weapon: Main hand weapon in wsdist format
        sub_weapon: Sub weapon in wsdist format
        ws_type: Type of weaponskill for profile selection
        beam_width: Number of contenders to find
    
    Returns:
        (contenders, item_pool) tuple
    """
    # Load inventory
    print(f"Loading inventory from {inventory_path}...")
    inventory = load_inventory(inventory_path)
    print(f"  Loaded {len(inventory.items)} items")
    
    # Create profile based on WS type
    if ws_type == 'physical':
        # Physical WS: prioritize STR, Attack, WSD, multi-attack
        profile = OptimizationProfile(
            name=f"Physical WS ({job.name})",
            weights={
                'STR': 1.0,
                'attack': 0.5,
                'accuracy': 0.3,
                'ws_damage': 2.0,  # High priority
                'double_attack': 0.8,
                'triple_attack': 1.2,
                'quad_attack': 1.5,
                'crit_rate': 0.6,
                'crit_damage': 0.4,
                'pdl': 1.5,
            },
            job=job,
        )
    elif ws_type == 'magical':
        # Magical WS: prioritize INT/MND, MAB, Magic Accuracy
        profile = OptimizationProfile(
            name=f"Magical WS ({job.name})",
            weights={
                'INT': 1.0,
                'MND': 0.5,
                'magic_attack': 1.5,
                'magic_accuracy': 0.8,
                'ws_damage': 2.0,
                'magic_burst_bonus': 0.5,
            },
            job=job,
        )
    else:  # hybrid
        profile = OptimizationProfile(
            name=f"Hybrid WS ({job.name})",
            weights={
                'STR': 0.8,
                'INT': 0.5,
                'attack': 0.4,
                'magic_attack': 0.6,
                'accuracy': 0.3,
                'magic_accuracy': 0.3,
                'ws_damage': 2.0,
                'double_attack': 0.5,
                'triple_attack': 0.8,
            },
            job=job,
        )
    
    # Run beam search
    print(f"\nRunning beam search with profile: {profile.name}")
    optimizer = BeamSearchOptimizer(inventory, profile, beam_width, job)
    
    fixed_gear = {
        'main': main_weapon,
        'sub': sub_weapon,
    }
    
    contenders = optimizer.search(fixed_gear=fixed_gear)
    item_pool = optimizer.extract_item_pool(contenders)
    
    return contenders, item_pool


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Example: Test with a sample inventory
    print("Beam Search Optimizer - Example Usage")
    print("=" * 70)
    
    # This would normally use your actual inventory
    inventory_path = "inventory_full_Masinmanci_20260111_124357.csv"
    
    # Example weapon (would come from user selection)
    naegling = {
        "Name": "Naegling", "Name2": "Naegling", "Type": "Weapon",
        "Skill Type": "Sword", "DMG": 166, "Delay": 240,
        "STR": 15, "DEX": 15, "MND": 15, "INT": 15,
        "Accuracy": 40, "Attack": 30, "Magic Accuracy": 40,
        "Sword Skill": 250, "Magic Accuracy Skill": 250,
        "Jobs": ["war", "rdm", "thf", "pld", "drk", "bst", "brd", 
                 "rng", "nin", "drg", "blu", "cor", "run"],
    }
    
    blurred_shield = {
        "Name": "Blurred Shield +1", "Name2": "Blurred Shield +1",
        "Type": "Shield", "STR": 8, "DEX": 8, "VIT": 8,
        "Gear Haste": 3, "Shield Skill": 119,
        "Jobs": ["war", "pld", "drk", "bst", "drg", "run"],
    }
    
    try:
        contenders, item_pool = optimize_for_weaponskill(
            inventory_path,
            Job.WAR,
            naegling,
            blurred_shield,
            ws_type='physical',
            beam_width=25,
        )
        
        # Print results
        optimizer = BeamSearchOptimizer.__new__(BeamSearchOptimizer)
        optimizer.print_contenders = lambda c: BeamSearchOptimizer.print_contenders(optimizer, c)
        optimizer.print_item_pool = lambda p: BeamSearchOptimizer.print_item_pool(optimizer, p)
        
        BeamSearchOptimizer.print_contenders(None, contenders)
        BeamSearchOptimizer.print_item_pool(None, item_pool)
        
        # Prepare for wsdist
        print("\n" + "=" * 70)
        print("READY FOR WSDIST")
        print("=" * 70)
        print(f"\nItem pool has {sum(len(v) for v in item_pool.values())} total items")
        print("This can now be passed to wsdist's build_set as check_gear")
        
    except FileNotFoundError:
        print(f"Inventory file not found. Please provide a valid path.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()