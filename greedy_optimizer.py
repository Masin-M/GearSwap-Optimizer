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
        secondary_profile = OptimizationProfile(
            name=f"JA:{ja_name} (DT fill)",
            weights={
                'damage_taken': -100.0,
                'physical_dt': -80.0,
                'magical_dt': -60.0,
                'HP': 3.0,
                'defense': 1.0,
            },
            hard_caps={
                'damage_taken': -5000,
                'physical_dt': -5000,
                'magical_dt': -5000,
            },
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
