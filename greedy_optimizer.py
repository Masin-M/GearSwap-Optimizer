"""
Greedy Optimizer for Idle/DT and JA Sets

Fast optimization paths that don't require wsdist simulation.
These sets are purely stat-based and can be solved greedily.

For Idle/DT sets:
  - Uses beam search scoring directly (already weighted for DT, refresh, etc.)
  - No combat simulation needed
  - Just verify caps are respected

For JA sets:
  - Look up items that "Enhance X effect" for the specific JA
  - Fill remaining slots with secondary priority (usually DT)
"""

import re
from typing import Dict, List, Optional, Tuple, Set, Any, Union
from dataclasses import dataclass, field
from enum import Enum

from models import Job, Slot, Stats, OptimizationProfile, ItemInstance
from inventory_loader import Inventory


# =============================================================================
# JA Enhancement Index
# =============================================================================

@dataclass
class JAEnhancement:
    """Represents an item that enhances a Job Ability."""
    item: ItemInstance
    ja_name: str
    slot: Slot
    effect_text: str  # Full text like "Enhances 'Berserk' effect"


class JAEnhancementIndex:
    """
    Index of items that enhance specific Job Abilities.
    
    Scans inventory for "Enhances X effect" patterns and builds
    a lookup table for fast JA set optimization.
    """
    
    # Pattern to match various formats:
    # - Enhances 'X' effect
    # - Enhances "X" effect  
    # - Enhances ""X"" effect (CSV escaped)
    ENHANCE_PATTERNS = [
        # CSV escaped: ""X""
        re.compile(
            r'Enhances\s+""([^"]+)""(?:\s+and\s+""([^"]+)"")?\s+effect',
            re.IGNORECASE
        ),
        # Standard quotes: "X" or 'X'
        re.compile(
            r'Enhances\s+["\']([^"\']+)["\'](?:\s+and\s+["\']([^"\']+)["\'])?\s+effect',
            re.IGNORECASE
        ),
    ]
    
    def __init__(self, inventory: Optional[Inventory] = None):
        # JA name -> list of (slot, item) tuples
        self.by_ja: Dict[str, List[Tuple[Slot, ItemInstance]]] = {}
        # slot -> JA name -> item (for quick slot lookup)
        self.by_slot: Dict[Slot, Dict[str, ItemInstance]] = {}
        # All enhancement items
        self.all_enhancements: List[JAEnhancement] = []
        
        if inventory:
            self.build_index(inventory)
    
    def build_index(self, inventory: Inventory, job: Optional[Job] = None):
        """
        Build the JA enhancement index from inventory.
        
        Args:
            inventory: Player inventory
            job: Optional job filter (only index items the job can equip)
        """
        self.by_ja.clear()
        self.by_slot.clear()
        self.all_enhancements.clear()
        
        for item in inventory.items:
            # Skip if job can't equip
            if job and not item.base.can_equip(job):
                continue
            
            # Skip if not from equippable container
            if not item.can_equip_from():
                continue
            
            # Check augments_raw for enhancement effects
            enhancement_texts = self._find_enhancements(item)
            
            for effect_text, ja_names in enhancement_texts:
                for ja_name in ja_names:
                    # Normalize JA name
                    ja_name_normalized = ja_name.strip()
                    
                    # Get slots this item can go in
                    for slot in item.base.get_slots():
                        enhancement = JAEnhancement(
                            item=item,
                            ja_name=ja_name_normalized,
                            slot=slot,
                            effect_text=effect_text,
                        )
                        self.all_enhancements.append(enhancement)
                        
                        # Index by JA
                        if ja_name_normalized not in self.by_ja:
                            self.by_ja[ja_name_normalized] = []
                        self.by_ja[ja_name_normalized].append((slot, item))
                        
                        # Index by slot
                        if slot not in self.by_slot:
                            self.by_slot[slot] = {}
                        self.by_slot[slot][ja_name_normalized] = item
    
    def _find_enhancements(self, item: ItemInstance) -> List[Tuple[str, List[str]]]:
        """
        Find enhancement effects in item's augments.
        
        Returns:
            List of (full_effect_text, [ja_name1, ja_name2, ...])
        """
        results = []
        
        def try_match(text: str) -> Optional[Tuple[str, List[str]]]:
            """Try all patterns against text."""
            for pattern in self.ENHANCE_PATTERNS:
                match = pattern.search(text)
                if match:
                    ja_names = [match.group(1)]
                    if match.group(2):  # "X and Y" pattern
                        ja_names.append(match.group(2))
                    return (text, ja_names)
            return None
        
        # Check augments_raw (strings from CSV)
        for aug in item.augments_raw:
            if not isinstance(aug, str):
                continue
            
            result = try_match(aug)
            if result:
                results.append(result)
        
        # Also check special_effects if available
        if hasattr(item, 'augment_stats') and item.augment_stats:
            for effect in item.augment_stats.special_effects:
                result = try_match(effect)
                if result:
                    # Avoid duplicates
                    if not any(effect in r[0] for r in results):
                        results.append(result)
        
        return results
    
    def get_items_for_ja(self, ja_name: str) -> List[Tuple[Slot, ItemInstance]]:
        """
        Get all items that enhance a specific JA.
        
        Args:
            ja_name: Name of the Job Ability (e.g., "Berserk", "Aggressor")
            
        Returns:
            List of (slot, item) tuples
        """
        # Try exact match first
        if ja_name in self.by_ja:
            return self.by_ja[ja_name]
        
        # Try case-insensitive match
        ja_lower = ja_name.lower()
        for key, items in self.by_ja.items():
            if key.lower() == ja_lower:
                return items
        
        return []
    
    def get_item_for_slot(self, slot: Slot, ja_name: str) -> Optional[ItemInstance]:
        """Get the enhancement item for a specific slot and JA."""
        if slot not in self.by_slot:
            return None
        
        slot_items = self.by_slot[slot]
        
        if ja_name in slot_items:
            return slot_items[ja_name]
        
        # Case-insensitive fallback
        ja_lower = ja_name.lower()
        for key, item in slot_items.items():
            if key.lower() == ja_lower:
                return item
        
        return None
    
    def list_all_jas(self) -> List[str]:
        """Get list of all JA names that have enhancement gear."""
        return sorted(self.by_ja.keys())
    
    def print_index(self):
        """Print the full index for debugging."""
        print("\n" + "=" * 60)
        print("JA ENHANCEMENT INDEX")
        print("=" * 60)
        
        for ja_name in sorted(self.by_ja.keys()):
            items = self.by_ja[ja_name]
            print(f"\n{ja_name}:")
            for slot, item in items:
                aug_info = ""
                if item.augments_raw:
                    aug_info = f" [{', '.join(str(a) for a in item.augments_raw[:2])}...]"
                print(f"  {slot.name:12s}: {item.name}{aug_info}")


# =============================================================================
# DT Stats Calculator
# =============================================================================

@dataclass
class DTStats:
    """Calculated DT stats for a gear set."""
    damage_taken: int = 0      # General DT (basis points, -5000 = -50%)
    physical_dt: int = 0       # PDT
    magical_dt: int = 0        # MDT
    breath_dt: int = 0         # BDT (breath damage)
    
    # Effective values (after combining DT + PDT/MDT)
    effective_pdt: int = 0
    effective_mdt: int = 0
    
    # Caps
    DT_CAP = -5000  # -50%
    
    # Other defensive stats
    hp: int = 0
    defense: int = 0
    magic_evasion: int = 0
    
    # Utility stats
    refresh: int = 0
    regen: int = 0
    movement_speed: int = 0
    
    def calculate_effective(self):
        """Calculate effective PDT/MDT (DT stacks with PDT/MDT)."""
        # DT applies to both physical and magical
        raw_pdt = self.damage_taken + self.physical_dt
        raw_mdt = self.damage_taken + self.magical_dt
        
        # Apply cap
        self.effective_pdt = max(raw_pdt, self.DT_CAP)
        self.effective_mdt = max(raw_mdt, self.DT_CAP)
    
    def is_dt_capped(self) -> bool:
        """Check if DT is at cap."""
        return self.effective_pdt <= self.DT_CAP or self.effective_mdt <= self.DT_CAP
    
    def format_summary(self) -> str:
        """Format a summary string."""
        self.calculate_effective()
        
        pdt_pct = self.effective_pdt / 100
        mdt_pct = self.effective_mdt / 100
        
        cap_note = " (CAPPED)" if self.is_dt_capped() else ""
        
        lines = [
            f"PDT: {pdt_pct:.0f}%  |  MDT: {mdt_pct:.0f}%{cap_note}",
            f"  DT: {self.damage_taken/100:.0f}%  PDT: {self.physical_dt/100:.0f}%  MDT: {self.magical_dt/100:.0f}%",
        ]
        
        if self.hp or self.defense:
            lines.append(f"  HP: +{self.hp}  Defense: +{self.defense}")
        
        if self.refresh or self.regen:
            lines.append(f"  Refresh: +{self.refresh}  Regen: +{self.regen}")
        
        return "\n".join(lines)


def calculate_dt_stats_from_gear(gear: Dict[str, Dict]) -> DTStats:
    """
    Calculate DT stats from a wsdist-format gear dict.
    
    Args:
        gear: Dict of slot -> wsdist item dict
        
    Returns:
        DTStats with totals
    """
    stats = DTStats()
    
    # Stat key mappings (wsdist uses various naming conventions)
    DT_KEYS = ['DT', 'Damage Taken', 'damage_taken', 'PDT', 'MDT']
    PDT_KEYS = ['PDT', 'Physical Damage Taken', 'physical_dt']
    MDT_KEYS = ['MDT', 'Magical Damage Taken', 'magical_dt', 'Magic Damage Taken']
    HP_KEYS = ['HP', 'hp']
    DEF_KEYS = ['Defense', 'DEF', 'defense']
    MEVA_KEYS = ['Magic Evasion', 'Magic Eva.', 'magic_evasion']
    REFRESH_KEYS = ['Refresh', 'refresh']
    REGEN_KEYS = ['Regen', 'regen']
    
    def get_stat(item: Dict, keys: List[str]) -> int:
        """Get a stat value from item dict, checking multiple key names."""
        for key in keys:
            if key in item:
                val = item[key]
                if isinstance(val, (int, float)):
                    return int(val)
        return 0
    
    for slot, item in gear.items():
        if item is None or item.get('Name') == 'Empty':
            continue
        
        # DT (general damage taken, applies to both physical and magical)
        # Note: In wsdist, negative values = damage reduction
        dt_val = get_stat(item, ['DT', 'Damage Taken'])
        if dt_val:
            # Convert to basis points if needed (DT is usually -X%)
            if -100 <= dt_val <= 0:
                stats.damage_taken += dt_val * 100
            else:
                stats.damage_taken += dt_val
        
        # PDT
        pdt_val = get_stat(item, PDT_KEYS)
        if pdt_val:
            if -100 <= pdt_val <= 0:
                stats.physical_dt += pdt_val * 100
            else:
                stats.physical_dt += pdt_val
        
        # MDT
        mdt_val = get_stat(item, MDT_KEYS)
        if mdt_val:
            if -100 <= mdt_val <= 0:
                stats.magical_dt += mdt_val * 100
            else:
                stats.magical_dt += mdt_val
        
        # Other stats
        stats.hp += get_stat(item, HP_KEYS)
        stats.defense += get_stat(item, DEF_KEYS)
        stats.magic_evasion += get_stat(item, MEVA_KEYS)
        stats.refresh += get_stat(item, REFRESH_KEYS)
        stats.regen += get_stat(item, REGEN_KEYS)
    
    stats.calculate_effective()
    return stats


def _remaining_dt_caps(
    fixed_gear,
    dt_hard_cap_bp: int = -5000,
):
    """
    Compute the remaining DT budget for each pool after accounting for
    whatever DT/PDT/MDT is already present in ``fixed_gear``.

    FFXI: eff_pdt = DT + PDT (cap -50%), eff_mdt = DT + MDT (cap -50%).
    Returns the gap left in each stat before those pools hit the cap.
    """
    if not fixed_gear:
        return {'damage_taken': dt_hard_cap_bp, 'physical_dt': dt_hard_cap_bp, 'magical_dt': dt_hard_cap_bp}
    locked = calculate_dt_stats_from_gear(fixed_gear)
    eff_pdt_locked = locked.damage_taken + locked.physical_dt
    eff_mdt_locked = locked.damage_taken + locked.magical_dt
    phys_room  = max(dt_hard_cap_bp, dt_hard_cap_bp - eff_pdt_locked)
    magic_room = max(dt_hard_cap_bp, dt_hard_cap_bp - eff_mdt_locked)
    # DT burns both pools simultaneously — cap it at the tighter pool
    dt_room  = max(dt_hard_cap_bp, max(phys_room, magic_room))
    pdt_room = max(dt_hard_cap_bp, phys_room  - dt_room)
    mdt_room = max(dt_hard_cap_bp, magic_room - dt_room)
    return {'damage_taken': dt_room, 'physical_dt': pdt_room, 'magical_dt': mdt_room}


# =============================================================================
# Greedy Idle/DT Optimization (No wsdist)
# =============================================================================

def run_idle_optimization_fast(
    inventory: 'Inventory',
    job: Job,
    main_weapon: Dict[str, Any],
    sub_weapon: Dict[str, Any],
    profile: OptimizationProfile,
    beam_width: int = 25,
    job_gifts: Optional[Any] = None,
) -> List[Tuple[Any, DTStats]]:
    """
    Run fast idle/DT optimization without wsdist simulation.
    
    For idle sets, we only care about stats - no combat simulation needed.
    This uses the beam search to find candidates, then just calculates
    the actual DT values for display.
    
    Args:
        inventory: Player inventory
        job: Main job
        main_weapon: Main weapon (fixed)
        sub_weapon: Sub weapon (fixed)
        profile: Optimization profile with stat weights
        beam_width: Beam search width
        job_gifts: Optional job gifts (unused for idle, but kept for API compat)
        
    Returns:
        List of (candidate, DTStats) tuples sorted by beam score
    """
    from numba_beam_search_optimizer import NumbaBeamSearchOptimizer
    from beam_search_optimizer import WSDIST_SLOTS
    
    print("\n" + "-" * 70)
    print("Running Fast Idle/DT Optimization (no wsdist)")
    print("-" * 70)
    print(f"  Profile: {profile.name}")
    
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
    print(f"\n✓ Found {len(contenders)} contender sets")
    
    # Calculate DT stats for each candidate (no simulation!)
    results = []
    for candidate in contenders:
        # Build gearset for stat calculation
        gearset = {}
        for slot in WSDIST_SLOTS:
            if slot in candidate.gear:
                gearset[slot] = candidate.gear[slot]
            elif slot == 'main':
                gearset[slot] = main_weapon
            elif slot == 'sub':
                gearset[slot] = sub_weapon
        
        # Calculate DT stats
        dt_stats = calculate_dt_stats_from_gear(gearset)
        
        results.append((candidate, dt_stats))
    
    # Already sorted by beam score (higher is better)
    return results


def display_idle_results(results: List[Tuple[Any, DTStats]], profile_name: str = "Idle"):
    """Display idle/DT optimization results."""
    print("\n" + "=" * 70)
    print(f"IDLE/DT OPTIMIZATION RESULTS - {profile_name}")
    print("=" * 70)
    
    for rank, (candidate, dt_stats) in enumerate(results[:5], 1):
        print(f"\n#{rank} - Score: {candidate.score:.1f}")
        print(f"    {dt_stats.format_summary()}")
        print("    Gear:")
        for slot in ['head', 'body', 'hands', 'legs', 'feet', 'ear1', 'ear2',
                     'ring1', 'ring2', 'waist', 'neck', 'back', 'ammo']:
            if slot in candidate.gear:
                name = candidate.gear[slot].get('Name2',
                       candidate.gear[slot].get('Name', 'Empty'))
                if name != 'Empty':
                    print(f"      {slot:8s}: {name}")


# =============================================================================
# JA Set Optimization
# =============================================================================

def run_ja_optimization(
    inventory: 'Inventory',
    job: Job,
    ja_name: str,
    main_weapon: Optional[Dict[str, Any]] = None,
    sub_weapon: Optional[Dict[str, Any]] = None,
    secondary_profile: Optional[OptimizationProfile] = None,
    beam_width: int = 25,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Optimize a JA (Job Ability) set.
    
    Strategy:
    1. Find all items that "Enhance X effect" for this JA
    2. Lock those items into the corresponding slots
    3. Fill remaining slots with secondary priority (default: DT)
    
    Args:
        inventory: Player inventory
        job: Main job
        ja_name: Name of the Job Ability (e.g., "Berserk")
        main_weapon: Optional main weapon (usually not needed for JA sets)
        sub_weapon: Optional sub weapon
        secondary_profile: Profile for filling non-JA slots (default: DT)
        beam_width: Beam width for secondary optimization
        
    Returns:
        Tuple of (gear_dict, list_of_enhancement_slots)
    """
    from numba_beam_search_optimizer import NumbaBeamSearchOptimizer
    from optimizer_ui import create_tp_profile, TPSetType
    
    print("\n" + "-" * 70)
    print(f"Optimizing JA Set: {ja_name}")
    print("-" * 70)
    
    # Build JA enhancement index
    ja_index = JAEnhancementIndex(inventory)
    
    # Find enhancement items for this JA
    ja_items = ja_index.get_items_for_ja(ja_name)
    
    if not ja_items:
        print(f"  ⚠ No enhancement gear found for '{ja_name}'")
        print(f"  Available JAs with gear: {', '.join(ja_index.list_all_jas()[:10])}...")
    else:
        print(f"  Found {len(ja_items)} enhancement item(s):")
        for slot, item in ja_items:
            print(f"    {slot.name}: {item.name}")
    
    # Build fixed gear dict with JA enhancement items
    fixed_gear = {}
    enhancement_slots = []
    
    # Convert JA items to wsdist format and lock them
    from wsdist_converter import to_wsdist_gear
    
    for slot, item in ja_items:
        # Convert slot enum to wsdist slot name
        slot_name = slot.name.lower()
        if slot_name == 'left_ear':
            slot_name = 'ear1'
        elif slot_name == 'right_ear':
            slot_name = 'ear2'
        elif slot_name == 'left_ring':
            slot_name = 'ring1'
        elif slot_name == 'right_ring':
            slot_name = 'ring2'
        
        # Skip if we already have an item in this slot
        # (first item wins - could improve with stat comparison)
        if slot_name in fixed_gear:
            continue
        
        wsdist_item = to_wsdist_gear(item)
        if wsdist_item:
            fixed_gear[slot_name] = wsdist_item
            enhancement_slots.append(slot_name)
    
    # Add weapons if provided
    if main_weapon:
        fixed_gear['main'] = main_weapon
    if sub_weapon:
        fixed_gear['sub'] = sub_weapon
    
    # Use DT profile for remaining slots if not specified
    if secondary_profile is None:
        remaining_caps = _remaining_dt_caps(fixed_gear)
        secondary_profile = OptimizationProfile(
            name=f"JA:{ja_name} (DT fill)",
            weights={
                'damage_taken': -100.0,
                'physical_dt': -80.0,
                'magical_dt': -60.0,
                'HP': 3.0,
                'defense': 1.0,
            },
            hard_caps=remaining_caps,
            job=job,
        )
    
    print(f"\n  Running beam search for remaining slots...")
    print(f"  Fixed slots: {list(fixed_gear.keys())}")
    
    # Run beam search for remaining slots
    optimizer = NumbaBeamSearchOptimizer(
        inventory=inventory,
        profile=secondary_profile,
        beam_width=beam_width,
        job=job,
    )
    
    contenders = optimizer.search(fixed_gear=fixed_gear)
    
    if contenders:
        best = contenders[0]
        # Merge fixed gear with optimized gear
        final_gear = dict(best.gear)
        for slot, item in fixed_gear.items():
            final_gear[slot] = item
        
        return final_gear, enhancement_slots
    else:
        return fixed_gear, enhancement_slots


def display_ja_results(gear: Dict[str, Any], ja_name: str, enhancement_slots: List[str]):
    """Display JA optimization results."""
    print("\n" + "=" * 70)
    print(f"JA SET: {ja_name}")
    print("=" * 70)
    
    dt_stats = calculate_dt_stats_from_gear(gear)
    print(f"\n{dt_stats.format_summary()}")
    
    print("\nGear:")
    slot_order = ['main', 'sub', 'range', 'ammo', 'head', 'neck', 'ear1', 'ear2',
                  'body', 'hands', 'ring1', 'ring2', 'back', 'waist', 'legs', 'feet']
    
    for slot in slot_order:
        if slot in gear and gear[slot].get('Name') != 'Empty':
            name = gear[slot].get('Name2', gear[slot].get('Name', 'Empty'))
            marker = " ★" if slot in enhancement_slots else ""
            print(f"  {slot:8s}: {name}{marker}")
    
    if enhancement_slots:
        print(f"\n★ = JA Enhancement slot")


# =============================================================================
# Convenience Functions
# =============================================================================

def is_idle_or_dt_profile(profile: OptimizationProfile) -> bool:
    """
    Check if a profile is for idle/DT (doesn't need combat sim).
    
    These profiles prioritize defensive stats and don't need
    attack round simulation.
    """
    weights = profile.weights
    
    # Check if it's primarily defensive
    defensive_weight = (
        abs(weights.get('damage_taken', 0)) +
        abs(weights.get('physical_dt', 0)) +
        abs(weights.get('magical_dt', 0)) +
        weights.get('HP', 0) * 10 +
        weights.get('defense', 0) * 5 +
        weights.get('refresh', 0) * 20 +
        weights.get('regen', 0) * 20
    )
    
    offensive_weight = (
        weights.get('store_tp', 0) +
        weights.get('double_attack', 0) +
        weights.get('triple_attack', 0) +
        weights.get('attack', 0) +
        weights.get('accuracy', 0)
    )
    
    # If defensive weight is dominant, it's an idle set
    return defensive_weight > offensive_weight * 2


def optimize_set_smart(
    inventory: 'Inventory',
    job: Job,
    main_weapon: Dict[str, Any],
    sub_weapon: Dict[str, Any],
    profile: OptimizationProfile,
    **kwargs
) -> List[Tuple[Any, Any]]:
    """
    Smart optimization that chooses fast path when possible.
    
    - Idle/DT sets: Uses fast path (no wsdist)
    - TP sets: Uses full simulation
    """
    if is_idle_or_dt_profile(profile):
        print("  → Using fast idle/DT optimization (no combat sim)")
        return run_idle_optimization_fast(
            inventory=inventory,
            job=job,
            main_weapon=main_weapon,
            sub_weapon=sub_weapon,
            profile=profile,
            **kwargs
        )
    else:
        # Fall back to full simulation
        from optimizer_ui import run_tp_optimization
        print("  → Using full TP simulation")
        return run_tp_optimization(
            inventory=inventory,
            job=job,
            main_weapon=main_weapon,
            sub_weapon=sub_weapon,
            **kwargs
        )


# =============================================================================
# Greedy Stat + DT Optimization (Enmity / Passive Refresh / Passive Regen)
# =============================================================================

# Slot enum name -> wsdist gear dict key
_SLOT_ENUM_TO_WSDIST: Dict[str, str] = {
    'LEFT_EAR':  'ear1',
    'RIGHT_EAR': 'ear2',
    'LEFT_RING':  'ring1',
    'RIGHT_RING': 'ring2',
    'HEAD':  'head',
    'BODY':  'body',
    'HANDS': 'hands',
    'LEGS':  'legs',
    'FEET':  'feet',
    'NECK':  'neck',
    'WAIST': 'waist',
    'BACK':  'back',
    'AMMO':  'ammo',
    # Weapon slots intentionally omitted — these sets lock weapons externally
}


def _slot_to_wsdist(slot: 'Slot') -> Optional[str]:
    """Convert a Slot enum value to its wsdist gear dict key."""
    return _SLOT_ENUM_TO_WSDIST.get(slot.name.upper())


def _find_best_items_by_stat(
    inventory: 'Inventory',
    job: 'Job',
    stat_keys: List[str],
) -> Dict[str, Tuple[Dict[str, Any], int]]:
    """
    Scan inventory and return the best item per gear slot for a given stat.

    Weapon slots (main/sub/range) are skipped — the caller locks weapons.

    Returns:
        {wsdist_slot_name: (wsdist_item_dict, stat_value)}
        Only slots where at least one item has stat_value > 0 are included.
    """
    from wsdist_converter import to_wsdist_gear

    best: Dict[str, Tuple[Dict[str, Any], int]] = {}

    for item in inventory.items:
        if not item.can_equip_from():
            continue
        if not item.base.can_equip(job):
            continue

        wsdist_item = to_wsdist_gear(item)
        if not wsdist_item:
            continue

        # Sum the target stat across all matching keys
        stat_val = 0
        for key in stat_keys:
            v = wsdist_item.get(key, 0)
            if isinstance(v, (int, float)):
                stat_val += int(v)

        if stat_val <= 0:
            continue

        for slot in item.base.get_slots():
            slot_name = _slot_to_wsdist(slot)
            if not slot_name:
                continue  # weapon slot — skip

            if slot_name not in best or stat_val > best[slot_name][1]:
                best[slot_name] = (wsdist_item, stat_val)

    return best


def _calc_stat_from_gear(
    gear: Dict[str, Any],
    stat_keys: List[str],
) -> int:
    """Sum a stat across all filled slots in a wsdist gear dict."""
    total = 0
    for item in gear.values():
        if item is None or item.get('Name', 'Empty') == 'Empty':
            continue
        for key in stat_keys:
            v = item.get(key, 0)
            if isinstance(v, (int, float)):
                total += int(v)
    return total


def _build_greedy_metrics(
    full_gear: Dict[str, Any],
    candidate_score: float,
    primary_stat_keys: List[str],
) -> Dict[str, Any]:
    """
    Build a metrics dict compatible with the api.py DTGearsetResult format
    from a completed wsdist gear dict.
    """
    dt_stats = calculate_dt_stats_from_gear(full_gear)

    # Raw DT components in basis points (e.g., -3000 = -30%)
    raw_dt  = dt_stats.damage_taken
    raw_pdt = dt_stats.physical_dt
    raw_mdt = dt_stats.magical_dt

    # Apply cap
    capped_dt  = max(raw_dt,  -5000)
    capped_pdt = max(raw_pdt, -5000)
    capped_mdt = max(raw_mdt, -5000)

    # Convert to percentages (e.g., -30.0)
    dt_pct  = capped_dt  / 100
    pdt_pct = capped_pdt / 100
    mdt_pct = capped_mdt / 100

    # Combined damage multipliers
    phys_mult  = (1 + dt_pct  / 100) * (1 + pdt_pct / 100)
    magic_mult = (1 + dt_pct  / 100) * (1 + mdt_pct / 100)

    # Primary stat total across the full set
    primary_total = _calc_stat_from_gear(full_gear, primary_stat_keys)

    return {
        'score':              candidate_score,
        'dt_pct':             dt_pct,
        'pdt_pct':            pdt_pct,
        'mdt_pct':            mdt_pct,
        'dt_capped':          dt_stats.is_dt_capped(),
        'physical_reduction': (1 - phys_mult)  * 100,
        'magical_reduction':  (1 - magic_mult) * 100,
        'hp':                 dt_stats.hp,
        'defense':            dt_stats.defense,
        'evasion':            0,
        'magic_evasion':      dt_stats.magic_evasion,
        'refresh':            dt_stats.refresh,
        'regen':              dt_stats.regen,
        'enmity':             _calc_stat_from_gear(full_gear, ['Enmity', 'enmity']),
        'fast_cast':          0,
        'fast_cast_capped':   False,
        'time_to_ws':         None,
        'tp_per_round':       None,
        'dps':                None,
        # Convenience: the primary stat total under its natural key
        '_primary_total':     primary_total,
    }


def _run_stat_plus_dt_optimization(
    inventory: 'Inventory',
    job: 'Job',
    stat_keys: List[str],
    stat_label: str,
    main_weapon: Optional[Dict[str, Any]] = None,
    sub_weapon: Optional[Dict[str, Any]] = None,
    beam_width: int = 25,
    job_gifts: Optional[Any] = None,
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    Generic greedy stat + DT fill optimization.

    Strategy
    --------
    1. For each gear slot, find the item that contributes the most of
       ``stat_keys`` (e.g., Enmity, Refresh, Regen).
    2. Lock those items as fixed gear so the beam search can't replace them.
    3. Run beam search on the remaining slots using a pure-DT profile so
       the rest of the set maintains survivability.
    4. Merge the two halves and compute summary metrics.

    Returns
    -------
    List[Tuple[full_gear_dict, metrics_dict]]
        ``full_gear_dict`` is in wsdist format (slot -> item dict).
        ``metrics_dict`` matches the shape expected by api.DTGearsetResult.
    """
    from numba_beam_search_optimizer import NumbaBeamSearchOptimizer
    from beam_search_optimizer import WSDIST_SLOTS

    print(f"\n{'─' * 70}")
    print(f"Greedy {stat_label.upper()} + DT Optimization")
    print(f"{'─' * 70}")

    # --- Step 1: Find the best item per slot for the target stat ---
    best_stat_items = _find_best_items_by_stat(inventory, job, stat_keys)

    if best_stat_items:
        print(f"  Found {stat_label} items in {len(best_stat_items)} slot(s):")
        for slot, (item, val) in sorted(best_stat_items.items()):
            name = item.get('Name2', item.get('Name', '?'))
            print(f"    {slot:8s}: {name}  (+{val})")
    else:
        print(f"  ⚠ No {stat_label} items found in inventory — falling back to pure DT.")

    # --- Step 2: Build fixed gear (stat items + weapons) ---
    fixed_gear: Dict[str, Any] = {}
    if main_weapon:
        fixed_gear['main'] = main_weapon
    if sub_weapon:
        fixed_gear['sub'] = sub_weapon
    for slot_name, (wsdist_item, _) in best_stat_items.items():
        fixed_gear[slot_name] = wsdist_item

    # --- Step 3: Fill remaining slots with DT using beam search ---
    remaining_caps = _remaining_dt_caps(fixed_gear)
    dt_profile = OptimizationProfile(
        name=f"{stat_label} DT-fill",
        weights={
            'damage_taken': -100.0,
            'physical_dt':  -80.0,
            'magical_dt':   -60.0,
            'HP':            3.0,
            'defense':       1.0,
        },
        hard_caps=remaining_caps,
        job=job,
    )

    optimizer = NumbaBeamSearchOptimizer(
        inventory=inventory,
        profile=dt_profile,
        beam_width=beam_width,
        job=job,
    )
    contenders = optimizer.search(fixed_gear=fixed_gear)
    print(f"  ✓ Beam search returned {len(contenders)} contender(s)")

    # --- Step 4: Assemble full gear sets and compute metrics ---
    results: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for candidate in contenders:
        # Merge: fixed_gear wins over candidate.gear (beam search
        # may not have included fixed slots in candidate.gear)
        full_gear: Dict[str, Any] = {}
        for slot in WSDIST_SLOTS:
            if slot in fixed_gear:
                full_gear[slot] = fixed_gear[slot]
            elif slot in candidate.gear:
                full_gear[slot] = candidate.gear[slot]

        metrics = _build_greedy_metrics(full_gear, candidate.score, stat_keys)
        results.append((full_gear, metrics))

    return results


# ---------------------------------------------------------------------------
# Public helpers — called by api.py
# ---------------------------------------------------------------------------

def _run_greedy_stat_optimization(
    inventory,
    job,
    stat_attr: str,
    stat_label: str,
    metric_key: str,
    main_weapon=None,
    sub_weapon=None,
    top_n: int = 10,
):
    """
    Generic greedy stat optimizer that reads directly from item.total_stats.

    Reads ``stat_attr`` from each ItemInstance's total_stats so the value is
    always found regardless of wsdist export key names.  Paired slots
    (ear1/ear2, ring1/ring2) share a candidate pool and a count check prevents
    the same unique item from filling both slots.  Only slots that actually
    carry the stat are included in the returned gear dict.

    Used by run_enmity_optimization, run_passive_refresh_optimization, and
    run_passive_regen_optimization.
    """
    from wsdist_converter import to_wsdist_gear

    print(f"\n{chr(9472) * 70}")
    print(f"Greedy {stat_label.upper()} Optimization")
    print(f"{chr(9472) * 70}")

    _SINGLE_SLOTS = ['head', 'neck', 'body', 'hands', 'back', 'waist', 'legs', 'feet', 'ammo']
    _PAIRED_SLOTS = [('ear1', 'ear2'), ('ring1', 'ring2')]

    gear = {}
    total_stat = 0

    # ── Single slots ──────────────────────────────────────────────────────────
    for slot_name in _SINGLE_SLOTS:
        best_item = None
        best_val = 0
        for inv_item in inventory.items:
            if not inv_item.can_equip_from():
                continue
            if not inv_item.base.can_equip(job):
                continue
            if not any(_slot_to_wsdist(s) == slot_name for s in inv_item.base.get_slots()):
                continue
            val = getattr(inv_item.total_stats, stat_attr, 0) or 0
            if val > best_val:
                best_val = val
                best_item = inv_item
        if best_item is not None:
            wsdist_item = to_wsdist_gear(best_item)
            if wsdist_item:
                gear[slot_name] = wsdist_item
                total_stat += best_val
                name = wsdist_item.get('Name2', wsdist_item.get('Name', '?'))
                print(f"  {slot_name:8s}: {name}  (+{best_val})")

    # ── Paired slots ──────────────────────────────────────────────────────────
    for slot_a, slot_b in _PAIRED_SLOTS:
        pool = []
        seen = {}
        for inv_item in inventory.items:
            if not inv_item.can_equip_from():
                continue
            if not inv_item.base.can_equip(job):
                continue
            item_wsdist_slots = {_slot_to_wsdist(s) for s in inv_item.base.get_slots()}
            if slot_a not in item_wsdist_slots and slot_b not in item_wsdist_slots:
                continue
            val = getattr(inv_item.total_stats, stat_attr, 0) or 0
            if val <= 0:
                continue
            wsdist_item = to_wsdist_gear(inv_item)
            if not wsdist_item:
                continue
            name = wsdist_item.get('Name', 'Unknown')
            if name in seen:
                pool[seen[name]]['count'] = min(2, pool[seen[name]]['count'] + 1)
            else:
                seen[name] = len(pool)
                pool.append({'name': name, 'val': val, 'count': 1, 'wsdist': wsdist_item})

        if not pool:
            continue

        best_pair = None
        best_pair_total = 0
        for i in range(len(pool)):
            for j in range(i, len(pool)):
                if i == j and pool[i]['count'] < 2:
                    continue
                pair_total = pool[i]['val'] + pool[j]['val']
                if pair_total > best_pair_total:
                    best_pair_total = pair_total
                    best_pair = (i, j)

        if best_pair is not None:
            i, j = best_pair
            gear[slot_a] = pool[i]['wsdist']
            gear[slot_b] = pool[j]['wsdist']
            total_stat += best_pair_total
            print(f"  {slot_a:8s}: {pool[i]['name']}  (+{pool[i]['val']})")
            print(f"  {slot_b:8s}: {pool[j]['name']}  (+{pool[j]['val']})")

    if main_weapon:
        gear['main'] = main_weapon
    if sub_weapon:
        gear['sub'] = sub_weapon

    if not gear:
        print(f"  ⚠ No {stat_label} items found in inventory.")
        return []

    print(f"\n  Total {stat_label} from gear: +{total_stat}")

    metrics = _build_greedy_metrics(gear, float(total_stat), [stat_attr])
    metrics[metric_key] = total_stat
    metrics['score']    = float(total_stat)

    return [(gear, metrics)]


def run_enmity_optimization(
    inventory: 'Inventory',
    job: 'Job',
    main_weapon: Optional[Dict[str, Any]] = None,
    sub_weapon: Optional[Dict[str, Any]] = None,
    beam_width: int = 25,
    job_gifts: Optional[Any] = None,
    top_n: int = 10,
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    Greedy enmity optimization.
    Reads enmity from item.total_stats; handles paired slots; returns only
    slots that carry enmity.
    """
    return _run_greedy_stat_optimization(
        inventory=inventory, job=job,
        stat_attr='enmity', stat_label='enmity', metric_key='enmity',
        main_weapon=main_weapon, sub_weapon=sub_weapon,
    )


def run_passive_refresh_optimization(
    inventory: 'Inventory',
    job: 'Job',
    main_weapon: Optional[Dict[str, Any]] = None,
    sub_weapon: Optional[Dict[str, Any]] = None,
    beam_width: int = 25,
    job_gifts: Optional[Any] = None,
    top_n: int = 10,
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    Greedy passive Refresh optimization.
    Reads refresh from item.total_stats; handles paired slots; returns only
    slots that carry passive refresh.
    """
    return _run_greedy_stat_optimization(
        inventory=inventory, job=job,
        stat_attr='refresh', stat_label='refresh', metric_key='refresh',
        main_weapon=main_weapon, sub_weapon=sub_weapon,
    )


def run_passive_regen_optimization(
    inventory: 'Inventory',
    job: 'Job',
    main_weapon: Optional[Dict[str, Any]] = None,
    sub_weapon: Optional[Dict[str, Any]] = None,
    beam_width: int = 25,
    job_gifts: Optional[Any] = None,
    top_n: int = 10,
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    Greedy passive Regen optimization.
    Reads regen from item.total_stats; handles paired slots; returns only
    slots that carry passive regen.
    """
    return _run_greedy_stat_optimization(
        inventory=inventory, job=job,
        stat_attr='regen', stat_label='regen', metric_key='regen',
        main_weapon=main_weapon, sub_weapon=sub_weapon,
    )


def run_sird_optimization(
    inventory: 'Inventory',
    job: 'Job',
    main_weapon: Optional[Dict[str, Any]] = None,
    sub_weapon: Optional[Dict[str, Any]] = None,
    beam_width: int = 25,
    job_gifts: Optional[Any] = None,
    top_n: int = 10,
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    Greedy Spell Interruption Rate Down (SIRD) optimization.

    Reads spell_interruption_rate_down from item.total_stats; handles paired
    slots (ears, rings); returns only slots that carry SIRD.

    The in-game cap is 102%. Once gear totals reach or exceed that value,
    additional SIRD from more slots provides no further benefit.
    """
    SIRD_CAP = 102

    results = _run_greedy_stat_optimization(
        inventory=inventory, job=job,
        stat_attr='spell_interruption_rate_down',
        stat_label='Spell Interruption Rate Down',
        metric_key='spell_interruption_rate_down',
        main_weapon=main_weapon, sub_weapon=sub_weapon,
    )

    if results:
        _, metrics = results[0]
        total = metrics.get('spell_interruption_rate_down', 0)
        if total >= SIRD_CAP:
            print(f"  ✓ SIRD cap reached: {total}% >= {SIRD_CAP}%")
        else:
            print(f"  ⚠ SIRD total: {total}%  (cap is {SIRD_CAP}% — {SIRD_CAP - total}% short)")

    return results


# =============================================================================
# EHP (Effective HP) DP Optimization
# =============================================================================

def _get_dt_pct_from_wsdist(item: Dict[str, Any], *keys: str) -> int:
    """
    Read a DT stat from a wsdist item dict and return it as a positive
    integer percentage point value (0-50).

    FFXI stores DT values in two formats depending on the source:
      - Small negative percentage  : -5   → 5%
      - Negative basis points      : -500 → 5%

    We return a positive integer so the DP can do simple integer arithmetic.
    """
    for k in keys:
        val = item.get(k, 0)
        if not val:
            continue
        val = float(val)
        if -100.0 <= val <= 0.0:
            return int(round(abs(val)))           # already a percentage
        elif val < -100.0:
            return int(round(abs(val) / 100.0))  # basis-points → percentage
    return 0


def _extract_ehp_items_for_slot(
    inventory: 'Inventory',
    job: 'Job',
    slot_name: str,
) -> List[Dict[str, Any]]:
    """
    Build the candidate item list for one gear slot.

    Returns a list of dicts:
        { name, wsdist, hp, dt, pdt, mdt }
    where dt/pdt/mdt are positive integer percentage points (0-50).

    An 'Empty' sentinel is always appended so slots can legitimately be
    left unfilled during the DP.
    """
    from wsdist_converter import to_wsdist_gear

    items: List[Dict[str, Any]] = []
    seen_names: Set[str] = set()

    for inv_item in inventory.items:
        if not inv_item.can_equip_from():
            continue
        if not inv_item.base.can_equip(job):
            continue

        # Quickly skip items that don't fit this slot at all
        if not any(_slot_to_wsdist(s) == slot_name for s in inv_item.base.get_slots()):
            continue

        wsdist_item = to_wsdist_gear(inv_item)
        if not wsdist_item:
            continue

        name = wsdist_item.get('Name', 'Unknown')
        if name in seen_names:
            continue
        seen_names.add(name)

        hp  = int(float(wsdist_item.get('HP', 0) or 0))
        dt  = _get_dt_pct_from_wsdist(wsdist_item, 'DT', 'Damage Taken',          'damage_taken')
        pdt = _get_dt_pct_from_wsdist(wsdist_item, 'PDT', 'Physical Damage Taken', 'physical_dt')
        mdt = _get_dt_pct_from_wsdist(wsdist_item, 'MDT', 'Magical Damage Taken',  'magical_dt',
                                                            'Magic Damage Taken')

        items.append({
            'name':   name,
            'wsdist': wsdist_item,
            'hp':     hp,
            'dt':     dt,
            'pdt':    pdt,
            'mdt':    mdt,
        })

    # Sentinel: always allow leaving a slot empty
    items.append({'name': 'Empty', 'wsdist': None, 'hp': 0, 'dt': 0, 'pdt': 0, 'mdt': 0})
    return items



def _extract_ehp_items_for_slot_pair(
    inventory,
    job,
    slot_a: str,
    slot_b: str,
):
    """
    Shared candidate pool for a paired slot (ear1/ear2 or ring1/ring2).
    Counts owned copies so the DP can block same-item duplicates.
    Returns dicts: { name, wsdist, hp, dt, pdt, mdt, count }
    """
    from wsdist_converter import to_wsdist_gear
    name_to_count = {}
    name_to_wsdist = {}
    for inv_item in inventory.items:
        if not inv_item.can_equip_from():
            continue
        if not inv_item.base.can_equip(job):
            continue
        item_slots = {_slot_to_wsdist(s) for s in inv_item.base.get_slots()}
        if slot_a not in item_slots and slot_b not in item_slots:
            continue
        wsdist_item = to_wsdist_gear(inv_item)
        if not wsdist_item:
            continue
        name = wsdist_item.get('Name', 'Unknown')
        name_to_count[name] = min(2, name_to_count.get(name, 0) + 1)
        if name not in name_to_wsdist:
            name_to_wsdist[name] = wsdist_item
    items = []
    for name, wsdist_item in name_to_wsdist.items():
        hp  = int(float(wsdist_item.get('HP', 0) or 0))
        dt  = _get_dt_pct_from_wsdist(wsdist_item, 'DT', 'Damage Taken', 'damage_taken')
        pdt = _get_dt_pct_from_wsdist(wsdist_item, 'PDT', 'Physical Damage Taken', 'physical_dt')
        mdt = _get_dt_pct_from_wsdist(wsdist_item, 'MDT', 'Magical Damage Taken', 'magical_dt', 'Magic Damage Taken')
        items.append({'name': name, 'wsdist': wsdist_item, 'hp': hp, 'dt': dt, 'pdt': pdt, 'mdt': mdt, 'count': name_to_count[name]})
    items.append({'name': 'Empty', 'wsdist': None, 'hp': 0, 'dt': 0, 'pdt': 0, 'mdt': 0, 'count': 2})
    return items


def _build_ehp_metrics(
    gear: Dict[str, Any],
    ehp: float,
    eff_pdt: int,
    eff_mdt: int,
    hp: int,
) -> Dict[str, Any]:
    """
    Build a metrics dict for an EHP-optimised set, matching DTGearsetResult shape.

    FFXI DT mechanics (corrected):
        DT on an item contributes equally to both PDT and MDT pools.
        PDT and MDT each cap independently at 50%.

    The DP tracks (eff_pdt, eff_mdt) directly — already the combined totals
    including any DT contribution — so no separate dt value is needed here.

    For display we report:
        dt_pct  = 0       (DT is not a separate game stat; it feeds pdt/mdt)
        pdt_pct = -eff_pdt
        mdt_pct = -eff_mdt
    """
    phys_mult  = 1.0 - eff_pdt / 100.0   # already the full physical reduction
    magic_mult = 1.0 - eff_mdt / 100.0   # already the full magical reduction

    phys_reduction  = eff_pdt  # = (1 - phys_mult) * 100
    magic_reduction = eff_mdt

    # Pull any other stats (defense, regen, refresh, …) from the gear dict
    dt_stats = calculate_dt_stats_from_gear(gear)

    return {
        'score':              ehp,
        'ehp':                round(ehp, 1),
        # No separate DT column — fold it all into pdt/mdt for the UI
        'dt_pct':             0.0,
        'pdt_pct':            float(-eff_pdt),
        'mdt_pct':            float(-eff_mdt),
        'dt_capped':          eff_pdt >= 50 or eff_mdt >= 50,
        'physical_reduction': float(phys_reduction),
        'magical_reduction':  float(magic_reduction),
        'hp':                 hp,
        'defense':            dt_stats.defense,
        'evasion':            0,
        'magic_evasion':      dt_stats.magic_evasion,
        'refresh':            dt_stats.refresh,
        'regen':              dt_stats.regen,
        'enmity':             0,
        'fast_cast':          0,
        'fast_cast_capped':   False,
        'time_to_ws':         None,
        'tp_per_round':       None,
        'dps':                None,
    }


def run_ehp_optimization(
    inventory: 'Inventory',
    job: 'Job',
    main_weapon: Optional[Dict[str, Any]] = None,
    sub_weapon: Optional[Dict[str, Any]] = None,
    # Accepted for API compatibility with the other greedy optimizers.
    beam_width: int = 25,
    job_gifts: Optional[Any] = None,
    top_n: int = 10,
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    EHP-maximising integer DP optimizer.

    FFXI DT mechanics (corrected)
    ==============================
    An item's DT stat contributes to *both* PDT and MDT simultaneously —
    it is a shorthand, not a third separate pool.  PDT and MDT each cap
    independently at 50%.

    So for any item:
        effective PDT contribution = item.dt + item.pdt
        effective MDT contribution = item.dt + item.mdt

    State space
    -----------
    state = (eff_pdt, eff_mdt)
        Each is the running cumulative PDT or MDT (0–50), already accounting
        for DT contributions.
        Theoretical maximum: 51 × 51 = 2,601 states — very manageable.

    DP transition
    -------------
        new_eff_pdt = min(50, cur_eff_pdt + item.dt + item.pdt)
        new_eff_mdt = min(50, cur_eff_mdt + item.dt + item.mdt)
        new_hp      = cur_hp + item.hp
        Keep if new_hp > best previously seen for (new_eff_pdt, new_eff_mdt).

    Memory efficiency
    -----------------
    Each DP entry stores a backtracking pointer (item_idx, prev_state) instead
    of a full gear snapshot.  Gear is reconstructed by replaying dp_history
    after the DP completes — O(slots) per top-N result.

    EHP scoring
    -----------
    Physical EHP = HP / (1 − eff_pdt/100)
    Magical  EHP = HP / (1 − eff_mdt/100)
    Final    EHP = min(physical EHP, magical EHP)   ← conservative worst-case

    Returns
    -------
    List of (gear_dict, metrics_dict) sorted by descending EHP.
    """
    SLOT_GROUPS = [
        'head', 'neck', ('ear1', 'ear2'),
        'body', 'hands', ('ring1', 'ring2'),
        'back', 'waist', 'legs', 'feet', 'ammo',
    ]

    print(f"\n{'─' * 70}")
    print("EHP Integer DP Optimization")
    print(f"{'─' * 70}")

    groups_data = []
    for group in SLOT_GROUPS:
        if isinstance(group, str):
            candidates = _extract_ehp_items_for_slot(inventory, job, group)
            non_empty = [c for c in candidates if c['name'] != 'Empty']
            print(f"  {group:14s}: {len(non_empty):3d} item(s)")
            groups_data.append((group, candidates))
        else:
            slot_a, slot_b = group
            pair_pool = _extract_ehp_items_for_slot_pair(inventory, job, slot_a, slot_b)
            non_empty = [c for c in pair_pool if c['name'] != 'Empty']
            print(f"  {slot_a}/{slot_b:10s}: {len(non_empty):3d} item(s) in shared pool")
            groups_data.append((group, pair_pool))

    State = Tuple[int, int]
    dp = {(0, 0): (0, -1, None)}
    dp_history = []

    for group_key, pool in groups_data:
        next_dp = {}
        if isinstance(group_key, str):
            for cur_state, (cur_hp, _, _) in dp.items():
                cur_pdt, cur_mdt = cur_state
                for item_idx, item in enumerate(pool):
                    new_pdt   = min(50, cur_pdt + item['dt'] + item['pdt'])
                    new_mdt   = min(50, cur_mdt + item['dt'] + item['mdt'])
                    new_state = (new_pdt, new_mdt)
                    new_hp    = cur_hp + item['hp']
                    if new_state not in next_dp or new_hp > next_dp[new_state][0]:
                        next_dp[new_state] = (new_hp, item_idx, cur_state)
            label = group_key
        else:
            slot_a, slot_b = group_key
            n = len(pool)
            for cur_state, (cur_hp, _, _) in dp.items():
                cur_pdt, cur_mdt = cur_state
                for i in range(n):
                    for j in range(i, n):
                        if i == j and pool[i].get('count', 1) < 2:
                            continue
                        a, b = pool[i], pool[j]
                        new_pdt   = min(50, cur_pdt + a['dt'] + a['pdt'] + b['dt'] + b['pdt'])
                        new_mdt   = min(50, cur_mdt + a['dt'] + a['mdt'] + b['dt'] + b['mdt'])
                        new_hp    = cur_hp + a['hp'] + b['hp']
                        new_state = (new_pdt, new_mdt)
                        if new_state not in next_dp or new_hp > next_dp[new_state][0]:
                            next_dp[new_state] = (new_hp, (i, j), cur_state)
            label = f"{slot_a}/{slot_b}"
        dp = next_dp
        dp_history.append(dp)
        print(f"  After {label:14s}: {len(dp):5d} reachable states")

    print(f"\n  Total final states : {len(dp)}")

    scored = []
    for (eff_pdt, eff_mdt), (hp, _, _) in dp.items():
        if hp == 0 and eff_pdt == 0 and eff_mdt == 0:
            continue
        phys_mult  = 1.0 - eff_pdt / 100.0
        magic_mult = 1.0 - eff_mdt / 100.0
        phys_ehp  = hp / phys_mult  if phys_mult  > 0.0 else float('inf')
        magic_ehp = hp / magic_mult if magic_mult > 0.0 else float('inf')
        scored.append((min(phys_ehp, magic_ehp), (eff_pdt, eff_mdt)))
    scored.sort(key=lambda x: x[0], reverse=True)

    def _reconstruct_gear(final_state):
        gear = {}
        state = final_state
        for group_idx in reversed(range(len(groups_data))):
            group_key, pool = groups_data[group_idx]
            _, item_ref, prev_state = dp_history[group_idx][state]
            if isinstance(group_key, str):
                item = pool[item_ref]
                if item['wsdist'] is not None:
                    gear[group_key] = item['wsdist']
            else:
                s_a, s_b = group_key
                i, j = item_ref
                if pool[i]['wsdist'] is not None:
                    gear[s_a] = pool[i]['wsdist']
                if pool[j]['wsdist'] is not None:
                    gear[s_b] = pool[j]['wsdist']
            state = prev_state
        return gear

    # ── Assemble results ─────────────────────────────────────────────────────
    results: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []

    for ehp, (eff_pdt, eff_mdt) in scored[:top_n]:
        gear = _reconstruct_gear((eff_pdt, eff_mdt))

        # Weapons are not part of the DP — attach the player's chosen weapons
        if main_weapon:
            gear['main'] = main_weapon
        if sub_weapon:
            gear['sub'] = sub_weapon

        hp = dp[(eff_pdt, eff_mdt)][0]
        metrics = _build_ehp_metrics(gear, ehp, eff_pdt, eff_mdt, hp)
        results.append((gear, metrics))

    if results:
        best_m = results[0][1]
        print(f"  ✓ Best EHP : {best_m['ehp']:,.0f}  "
              f"(HP={best_m['hp']}, "
              f"eff_PDT={-best_m['pdt_pct']:.0f}%, "
              f"eff_MDT={-best_m['mdt_pct']:.0f}%)")

    return results
