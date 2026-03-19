"""
Regen/Refresh Spell Optimizer

Optimizes gear sets for casting Regen and Refresh spells.
Focuses purely on gear contribution - job abilities are the user's concern.

Two optimization modes:
1. Max Tick - Maximize HP/tick or MP/tick (potency focused)
2. Max Magnitude - Maximize total HP/MP = potency × number_of_ticks

Reference: https://www.bg-wiki.com/ffxi/Category:Regen_Spell
           https://www.bg-wiki.com/ffxi/Category:Enhancing_Magic
"""

from dataclasses import dataclass
from typing import Tuple
from enum import Enum, auto
import math


class OptimizationMode(Enum):
    """Optimization strategy for Regen/Refresh sets."""
    MAX_TICK = auto()      # Maximize potency (HP/tick or MP/tick)
    MAX_MAGNITUDE = auto() # Maximize total recovery (potency × ticks)


class SpellType(Enum):
    """Spell type for optimization."""
    REGEN = auto()
    REFRESH = auto()


@dataclass
class GearStats:
    """
    Gear-derived stats relevant to Regen/Refresh optimization.
    """
    # Regen spell potency - flat HP/tick added
    # e.g., Bookworm's Cape '"Regen" potency+8', Telchine augments
    regen_potency: int = 0
    
    # Regen spell duration - flat seconds added
    # e.g., Telchine Chasuble 'Regen effect duration +27'
    regen_effect_duration: int = 0
    
    # Refresh spell potency - flat MP/tick added (rare)
    refresh_potency: int = 0
    
    # Refresh spell duration - flat seconds added
    refresh_effect_duration: int = 0
    
    # Enhancing magic duration - NON-AUGMENTED gear (basis points)
    # e.g., Embla Sash, Ammurapi Shield
    # Applied at a different step than augmented gear!
    enhancing_duration: int = 0
    
    # Enhancing magic duration - AUGMENTED gear (basis points)
    # e.g., Telchine 'Enh. Mag. eff. dur. +10'
    # Applied at a different step than non-augmented gear!
    enhancing_duration_augment: int = 0


# =============================================================================
# BASE SPELL DATA
# =============================================================================

REGEN_BASE_DATA = {
    # tier: (base_hp_per_tick, base_duration_seconds)
    1: (5,  75),   # Regen I:   5 HP/tick,  75 sec
    2: (12, 60),   # Regen II:  12 HP/tick,  60 sec
    3: (20, 60),   # Regen III: 20 HP/tick,  60 sec
    4: (30, 60),   # Regen IV:  30 HP/tick,  60 sec
    5: (40, 60),   # Regen V:   40 HP/tick,  60 sec
}

REFRESH_BASE_DATA = {
    # tier: (base_mp_per_tick, base_duration_seconds)
    1: (3, 150),   # Refresh I: 3 MP/tick, 150 sec
    2: (6, 150),   # Refresh II: 6 MP/tick, 150 sec
    3: (9, 150),   # Refresh III: 9 MP/tick, 150 sec
}


# =============================================================================
# GEAR CONTRIBUTION CALCULATIONS
# =============================================================================

def calculate_regen_gear_potency(gear: GearStats) -> int:
    """
    Calculate gear's contribution to Regen HP per tick.
    
    This is the flat HP/tick added by gear to the base spell.
    
    Args:
        gear: Gear stats
        
    Returns:
        Gear's HP/tick contribution
    """
    return gear.regen_potency


def calculate_regen_gear_duration(gear: GearStats, base_duration: float) -> Tuple[float, int]:
    """
    Calculate gear's effect on Regen duration.
    
    Duration Formula (from BG-Wiki):
        (Base_Duration + Flat_Bonuses) 
        × (1 + Non_Augmented_Gear%)
        × (1 + Augmented_Gear%)
    
    Note: Non-augmented and augmented duration are SEPARATE multipliers!
    
    Args:
        gear: Gear stats
        base_duration: Base spell duration in seconds
        
    Returns:
        Tuple of (final_duration_seconds, number_of_ticks)
    """
    # Step 1: Add flat duration bonuses from gear
    duration = base_duration + gear.regen_effect_duration
    
    # Step 2: Apply non-augmented gear % bonus (Embla Sash, Ammurapi, etc.)
    if gear.enhancing_duration > 0:
        duration = duration * (1.0 + gear.enhancing_duration / 10000)
    
    # Step 3: Apply augmented gear % bonus (Telchine augments - separate multiplier!)
    if gear.enhancing_duration_augment > 0:
        duration = duration * (1.0 + gear.enhancing_duration_augment / 10000)
    
    # Calculate ticks (1 tick = 3 seconds)
    ticks = int(duration // 3)
    
    return duration, ticks


def calculate_regen_total(
    tier: int,
    gear: GearStats,
) -> Tuple[int, float, int, int]:
    """
    Calculate total Regen output with gear.
    
    Args:
        tier: Regen tier (1-5)
        gear: Gear stats
        
    Returns:
        Tuple of (total_hp, duration_seconds, num_ticks, hp_per_tick)
    """
    base_hp, base_duration = REGEN_BASE_DATA.get(tier, (40, 60))
    
    # Gear potency adds flat HP/tick
    hp_per_tick = base_hp + calculate_regen_gear_potency(gear)
    
    # Gear duration extends the spell
    duration, ticks = calculate_regen_gear_duration(gear, base_duration)
    
    total_hp = hp_per_tick * ticks
    
    return total_hp, duration, ticks, hp_per_tick


def calculate_refresh_gear_potency(gear: GearStats) -> int:
    """
    Calculate gear's contribution to Refresh MP per tick.
    
    Args:
        gear: Gear stats
        
    Returns:
        Gear's MP/tick contribution
    """
    return gear.refresh_potency


def calculate_refresh_gear_duration(gear: GearStats, base_duration: float) -> Tuple[float, int]:
    """
    Calculate gear's effect on Refresh duration.
    
    Args:
        gear: Gear stats
        base_duration: Base spell duration in seconds
        
    Returns:
        Tuple of (final_duration_seconds, number_of_ticks)
    """
    # Step 1: Add flat duration bonuses
    duration = base_duration + gear.refresh_effect_duration
    
    # Step 2: Apply non-augmented gear % bonus
    if gear.enhancing_duration > 0:
        duration = duration * (1.0 + gear.enhancing_duration / 10000)
    
    # Step 3: Apply augmented gear % bonus
    if gear.enhancing_duration_augment > 0:
        duration = duration * (1.0 + gear.enhancing_duration_augment / 10000)
    
    # Calculate ticks (1 tick = 3 seconds)
    ticks = int(duration // 3)
    
    return duration, ticks


def calculate_refresh_total(
    tier: int,
    gear: GearStats,
) -> Tuple[int, float, int, int]:
    """
    Calculate total Refresh output with gear.
    
    Args:
        tier: Refresh tier (1-3)
        gear: Gear stats
        
    Returns:
        Tuple of (total_mp, duration_seconds, num_ticks, mp_per_tick)
    """
    base_mp, base_duration = REFRESH_BASE_DATA.get(tier, (9, 150))
    
    # Gear potency adds flat MP/tick
    mp_per_tick = base_mp + calculate_refresh_gear_potency(gear)
    
    # Gear duration extends the spell
    duration, ticks = calculate_refresh_gear_duration(gear, base_duration)
    
    total_mp = mp_per_tick * ticks
    
    return total_mp, duration, ticks, mp_per_tick


# =============================================================================
# OPTIMIZATION SCORING
# =============================================================================

def score_regen_set(
    gear: GearStats,
    tier: int = 5,
    mode: OptimizationMode = OptimizationMode.MAX_MAGNITUDE,
) -> float:
    """
    Score a gear set for Regen optimization.
    
    Args:
        gear: Gear stats from the set
        tier: Regen tier (1-5), default Regen V
        mode: MAX_TICK or MAX_MAGNITUDE
        
    Returns:
        Score value (higher is better)
    """
    total_hp, duration, ticks, hp_per_tick = calculate_regen_total(tier, gear)
    
    if mode == OptimizationMode.MAX_TICK:
        return float(hp_per_tick)
    else:  # MAX_MAGNITUDE
        return float(total_hp)


def score_refresh_set(
    gear: GearStats,
    tier: int = 3,
    mode: OptimizationMode = OptimizationMode.MAX_MAGNITUDE,
) -> float:
    """
    Score a gear set for Refresh optimization.
    
    Args:
        gear: Gear stats from the set
        tier: Refresh tier (1-3), default Refresh III
        mode: MAX_TICK or MAX_MAGNITUDE
        
    Returns:
        Score value (higher is better)
    """
    total_mp, duration, ticks, mp_per_tick = calculate_refresh_total(tier, gear)
    
    if mode == OptimizationMode.MAX_TICK:
        return float(mp_per_tick)
    else:  # MAX_MAGNITUDE
        return float(total_mp)


def extract_gear_stats(stats) -> GearStats:
    """
    Extract relevant gear stats from a full Stats object.
    
    Args:
        stats: Full Stats object (from models.py)
        
    Returns:
        GearStats with relevant fields extracted
    """
    return GearStats(
        regen_potency=getattr(stats, 'regen_potency', 0),
        regen_effect_duration=getattr(stats, 'regen_effect_duration', 0),
        refresh_potency=getattr(stats, 'refresh_potency', 0),
        refresh_effect_duration=getattr(stats, 'refresh_effect_duration', 0),
        enhancing_duration=getattr(stats, 'enhancing_duration', 0),
        enhancing_duration_augment=getattr(stats, 'enhancing_duration_augment', 0),
    )


# =============================================================================
# OPTIMIZATION PROFILE
# =============================================================================

@dataclass
class RegenRefreshProfile:
    """
    Optimization profile for Regen/Refresh midcast sets.
    """
    name: str
    spell_type: SpellType
    spell_tier: int
    mode: OptimizationMode
    
    def score(self, gear: GearStats) -> float:
        """Score a gear set for this profile."""
        if self.spell_type == SpellType.REGEN:
            return score_regen_set(gear, self.spell_tier, self.mode)
        else:
            return score_refresh_set(gear, self.spell_tier, self.mode)
    
    def calculate(self, gear: GearStats) -> Tuple[int, float, int, int]:
        """Get full calculation results."""
        if self.spell_type == SpellType.REGEN:
            return calculate_regen_total(self.spell_tier, gear)
        else:
            return calculate_refresh_total(self.spell_tier, gear)


def create_regen_profile(
    name: str = "Regen V Midcast",
    tier: int = 5,
    mode: OptimizationMode = OptimizationMode.MAX_MAGNITUDE,
) -> RegenRefreshProfile:
    """Create a Regen optimization profile."""
    return RegenRefreshProfile(
        name=name,
        spell_type=SpellType.REGEN,
        spell_tier=tier,
        mode=mode,
    )


def create_refresh_profile(
    name: str = "Refresh III Midcast",
    tier: int = 3,
    mode: OptimizationMode = OptimizationMode.MAX_MAGNITUDE,
) -> RegenRefreshProfile:
    """Create a Refresh optimization profile."""
    return RegenRefreshProfile(
        name=name,
        spell_type=SpellType.REFRESH,
        spell_tier=tier,
        mode=mode,
    )


# =============================================================================
# DISPLAY / COMPARISON
# =============================================================================

def format_regen_summary(gear: GearStats, tier: int = 5) -> str:
    """Format a summary of Regen spell output with gear."""
    total_hp, duration, ticks, hp_per_tick = calculate_regen_total(tier, gear)
    base_hp, base_dur = REGEN_BASE_DATA[tier]
    
    lines = [
        f"=== Regen {['I','II','III','IV','V'][tier-1]} with Gear ===",
        f"",
        f"Base:     {base_hp} HP/tick, {base_dur} sec ({base_dur//3} ticks), {base_hp * (base_dur//3)} HP total",
        f"With Gear: {hp_per_tick} HP/tick, {duration:.1f} sec ({ticks} ticks), {total_hp} HP total",
        f"",
        f"Gear Contribution:",
        f"  Potency:     +{gear.regen_potency} HP/tick",
        f"  Flat Dur:    +{gear.regen_effect_duration} sec",
        f"  Dur % (gear): +{gear.enhancing_duration/100:.1f}%",
        f"  Dur % (aug):  +{gear.enhancing_duration_augment/100:.1f}%",
    ]
    return "\n".join(lines)


def format_refresh_summary(gear: GearStats, tier: int = 3) -> str:
    """Format a summary of Refresh spell output with gear."""
    total_mp, duration, ticks, mp_per_tick = calculate_refresh_total(tier, gear)
    base_mp, base_dur = REFRESH_BASE_DATA[tier]
    
    lines = [
        f"=== Refresh {['I','II','III'][tier-1]} with Gear ===",
        f"",
        f"Base:     {base_mp} MP/tick, {base_dur} sec ({base_dur//3} ticks), {base_mp * (base_dur//3)} MP total",
        f"With Gear: {mp_per_tick} MP/tick, {duration:.1f} sec ({ticks} ticks), {total_mp} MP total",
        f"",
        f"Gear Contribution:",
        f"  Potency:     +{gear.refresh_potency} MP/tick",
        f"  Flat Dur:    +{gear.refresh_effect_duration} sec",
        f"  Dur % (gear): +{gear.enhancing_duration/100:.1f}%",
        f"  Dur % (aug):  +{gear.enhancing_duration_augment/100:.1f}%",
    ]
    return "\n".join(lines)


def compare_sets(
    sets: dict,  # name -> GearStats
    spell_type: SpellType = SpellType.REGEN,
    tier: int = 5,
) -> str:
    """
    Compare multiple gear sets for Regen or Refresh.
    
    Args:
        sets: Dict mapping set name to GearStats
        spell_type: REGEN or REFRESH
        tier: Spell tier
        
    Returns:
        Formatted comparison string
    """
    lines = []
    
    if spell_type == SpellType.REGEN:
        base_val, base_dur = REGEN_BASE_DATA[tier]
        spell_name = f"Regen {['I','II','III','IV','V'][tier-1]}"
        unit = "HP"
    else:
        base_val, base_dur = REFRESH_BASE_DATA[tier]
        spell_name = f"Refresh {['I','II','III'][tier-1]}"
        unit = "MP"
    
    lines.append(f"=== {spell_name} Gear Comparison ===")
    lines.append(f"Base: {base_val} {unit}/tick, {base_dur} sec")
    lines.append("")
    lines.append(f"{'Set Name':<20} {unit+'/Tick':>10} {'Ticks':>8} {'Total '+unit:>12} {'Score':>10}")
    lines.append("-" * 64)
    
    results = []
    for name, gear in sets.items():
        if spell_type == SpellType.REGEN:
            total, dur, ticks, per_tick = calculate_regen_total(tier, gear)
        else:
            total, dur, ticks, per_tick = calculate_refresh_total(tier, gear)
        results.append((name, per_tick, ticks, total))
    
    # Sort by total (MAX_MAGNITUDE)
    results.sort(key=lambda x: x[3], reverse=True)
    
    for name, per_tick, ticks, total in results:
        lines.append(f"{name:<20} {per_tick:>10} {ticks:>8} {total:>12} {total:>10}")
    
    return "\n".join(lines)


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Example: Compare potency-focused vs duration-focused Regen sets
    
    potency_set = GearStats(
        regen_potency=22,              # Bookworm's Cape + Telchine body
        regen_effect_duration=27,      # Telchine Chasuble
        enhancing_duration=2000,       # 20% from Embla Sash + Ammurapi
        enhancing_duration_augment=1000,  # 10% from some Telchine pieces
    )
    
    duration_set = GearStats(
        regen_potency=8,               # Just Bookworm's Cape
        regen_effect_duration=27,      # Telchine Chasuble
        enhancing_duration=2000,       # 20%
        enhancing_duration_augment=4000,  # 40% from full Telchine augment set
    )
    
    balanced_set = GearStats(
        regen_potency=15,
        regen_effect_duration=27,
        enhancing_duration=2000,
        enhancing_duration_augment=2500,
    )
    
    print(compare_sets({
        "Potency Focus": potency_set,
        "Duration Focus": duration_set,
        "Balanced": balanced_set,
    }, SpellType.REGEN, tier=5))
    
    print("\n")
    print(format_regen_summary(potency_set, tier=5))


# =============================================================================
# INVENTORY OPTIMIZER
# =============================================================================

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from models import Slot, Job
    from inventory_loader import Inventory


# Slots relevant to an enhancing midcast set.
# Imported lazily to avoid circular dependencies when this module is used standalone.
_MIDCAST_SLOT_NAMES = [
    'head', 'neck', 'left_ear', 'right_ear',
    'body', 'hands', 'left_ring', 'right_ring',
    'back', 'waist', 'legs', 'feet',
]
_WEAPON_SLOT_NAMES = ['main', 'sub']


@dataclass
class SlotCandidate:
    """A single item candidate for a slot."""
    slot_name: str
    item: Any                  # ItemInstance
    gear_stats: GearStats
    potency: int               # Spell-specific potency (regen_potency or refresh_potency)
    duration_contribution: float  # Flat seconds + % contribution (computed per-slot preview)


@dataclass
class RegenRefreshResult:
    """Result of a Regen/Refresh gear optimization."""
    spell_type: SpellType
    spell_tier: int
    mode: OptimizationMode

    # Best item per slot (slot_name -> ItemInstance, or None if empty)
    gear_set: Dict[str, Any] = field(default_factory=dict)

    # Which slots were filled by the potency pass (phase 1)
    potency_slots: List[str] = field(default_factory=list)

    # Which slots were filled by the duration pass (phase 2)
    duration_slots: List[str] = field(default_factory=list)

    # Accumulated gear stats across the full set
    gear_stats: GearStats = field(default_factory=GearStats)

    # Final spell output
    total_resource: int = 0    # Total HP (Regen) or MP (Refresh) returned
    duration_seconds: float = 0.0
    num_ticks: int = 0
    per_tick: int = 0

    # Raw score (same as total_resource for MAX_MAGNITUDE, per_tick for MAX_TICK)
    score: float = 0.0


def _extract_gear_stats_from_item(item, spell_type: SpellType) -> GearStats:
    """Pull the six relevant stats from an ItemInstance's total_stats."""
    s = item.total_stats
    return GearStats(
        regen_potency=getattr(s, 'regen_potency', 0),
        regen_effect_duration=getattr(s, 'regen_effect_duration', 0),
        refresh_potency=getattr(s, 'refresh_potency', 0),
        refresh_effect_duration=getattr(s, 'refresh_effect_duration', 0),
        enhancing_duration=getattr(s, 'enhancing_duration', 0),
        enhancing_duration_augment=getattr(s, 'enhancing_duration_augment', 0),
    )


def _has_any_relevant_stat(gs: GearStats, spell_type: SpellType) -> bool:
    """Return True if this GearStats contributes anything for the given spell type."""
    if spell_type == SpellType.REGEN:
        return (gs.regen_potency > 0 or gs.regen_effect_duration > 0
                or gs.enhancing_duration > 0 or gs.enhancing_duration_augment > 0)
    else:
        return (gs.refresh_potency > 0 or gs.refresh_effect_duration > 0
                or gs.enhancing_duration > 0 or gs.enhancing_duration_augment > 0)


def _get_potency(gs: GearStats, spell_type: SpellType) -> int:
    return gs.regen_potency if spell_type == SpellType.REGEN else gs.refresh_potency


def _add_gear_stats(a: GearStats, b: GearStats) -> GearStats:
    """Return a new GearStats that is the sum of a and b."""
    return GearStats(
        regen_potency=a.regen_potency + b.regen_potency,
        regen_effect_duration=a.regen_effect_duration + b.regen_effect_duration,
        refresh_potency=a.refresh_potency + b.refresh_potency,
        refresh_effect_duration=a.refresh_effect_duration + b.refresh_effect_duration,
        enhancing_duration=a.enhancing_duration + b.enhancing_duration,
        enhancing_duration_augment=a.enhancing_duration_augment + b.enhancing_duration_augment,
    )


def _score(gear: GearStats, spell_type: SpellType, spell_tier: int,
           mode: OptimizationMode) -> float:
    if spell_type == SpellType.REGEN:
        return score_regen_set(gear, spell_tier, mode)
    else:
        return score_refresh_set(gear, spell_tier, mode)


def optimize_regen_refresh(
    inventory: 'Inventory',
    spell_type: SpellType,
    spell_tier: int,
    job: 'Job',
    mode: OptimizationMode = OptimizationMode.MAX_MAGNITUDE,
    include_weapons: bool = False,
) -> RegenRefreshResult:
    """
    Two-phase greedy optimization for Regen/Refresh midcast sets.

    Phase 1 - Potency lock:
        Find every item in the inventory that carries regen_potency (for Regen)
        or refresh_potency (for Refresh).  For each slot that has such an item,
        choose the one with the highest potency and lock the slot.  If two items
        in the same slot have equal potency, the one with more total duration
        contribution wins; item level breaks any remaining tie.

    Phase 2 - Duration fill:
        With potency-locked slots fixed, iterate over the remaining slots and
        pick the item that maximises the spell score given the gear accumulated
        so far.  Because enhancing_duration and enhancing_duration_augment are
        separate multiplicative steps, the marginal value of a percentage-duration
        item depends on the current accumulated state - so each slot is evaluated
        against the running total rather than in isolation.

    Args:
        inventory:       Loaded player inventory.
        spell_type:      SpellType.REGEN or SpellType.REFRESH.
        spell_tier:      Spell tier (Regen 1-5, Refresh 1-3).
        job:             Player's job (used to filter equippable items).
        mode:            MAX_TICK or MAX_MAGNITUDE.
        include_weapons: Whether to consider main/sub slots.

    Returns:
        RegenRefreshResult with the best item per slot and full spell output.
    """
    from models import Slot, SLOT_NAMES

    # Build the set of slot names we care about
    slot_names = list(_MIDCAST_SLOT_NAMES)
    if include_weapons:
        slot_names = _WEAPON_SLOT_NAMES + slot_names

    # Reverse-map slot_name -> Slot enum for inventory lookup
    name_to_slot = {v: k for k, v in SLOT_NAMES.items()}

    # -------------------------------------------------------------------------
    # Collect candidates: items per slot that have at least one relevant stat
    # -------------------------------------------------------------------------
    candidates: Dict[str, List[Any]] = {s: [] for s in slot_names}

    for item in inventory.items:
        if not item.can_equip_from():
            continue
        if job and not item.base.can_equip(job):
            continue

        gs = _extract_gear_stats_from_item(item, spell_type)
        if not _has_any_relevant_stat(gs, spell_type):
            continue

        # An item may fit multiple slots - add to each applicable one
        for slot_name in slot_names:
            slot_enum = name_to_slot.get(slot_name)
            if slot_enum is None:
                continue
            item_slots = item.base.get_slots()
            if slot_enum in item_slots:
                candidates[slot_name].append(item)

    # -------------------------------------------------------------------------
    # Phase 1: Lock slots that have potency items
    # -------------------------------------------------------------------------
    locked: Dict[str, Any] = {}           # slot_name -> ItemInstance
    locked_stats: Dict[str, GearStats] = {}

    for slot_name in slot_names:
        potency_items = [
            item for item in candidates[slot_name]
            if _get_potency(_extract_gear_stats_from_item(item, spell_type), spell_type) > 0
        ]
        if not potency_items:
            continue

        def _phase1_key(item):
            gs = _extract_gear_stats_from_item(item, spell_type)
            potency = _get_potency(gs, spell_type)
            # Tiebreak 1: total duration contribution at a notional base
            # (flat seconds + combined % applied to base duration to get a scalar)
            base_dur = REGEN_BASE_DATA[spell_tier][1] if spell_type == SpellType.REGEN \
                       else REFRESH_BASE_DATA[spell_tier][1]
            preview_dur = (base_dur + gs.regen_effect_duration + gs.refresh_effect_duration) \
                          * (1 + gs.enhancing_duration / 10000) \
                          * (1 + gs.enhancing_duration_augment / 10000)
            # Tiebreak 2: item level
            return (potency, preview_dur, item.base.item_level)

        best = max(potency_items, key=_phase1_key)
        locked[slot_name] = best
        locked_stats[slot_name] = _extract_gear_stats_from_item(best, spell_type)

    # Accumulated gear from phase 1
    current_gear = GearStats()
    for gs in locked_stats.values():
        current_gear = _add_gear_stats(current_gear, gs)

    # -------------------------------------------------------------------------
    # Phase 2: Fill remaining slots by maximising score delta
    # -------------------------------------------------------------------------
    duration_filled: Dict[str, Any] = {}

    remaining_slots = [s for s in slot_names if s not in locked]

    for slot_name in remaining_slots:
        slot_candidates = candidates[slot_name]
        if not slot_candidates:
            continue

        best_item = None
        best_score = _score(current_gear, spell_type, spell_tier, mode)

        for item in slot_candidates:
            gs = _extract_gear_stats_from_item(item, spell_type)
            trial_gear = _add_gear_stats(current_gear, gs)
            trial_score = _score(trial_gear, spell_type, spell_tier, mode)
            if trial_score > best_score:
                best_score = trial_score
                best_item = item
            elif trial_score == best_score and best_item is not None:
                # Tiebreak: prefer item with more potency, then higher item level
                challenger_potency = _get_potency(gs, spell_type)
                current_best_potency = _get_potency(
                    _extract_gear_stats_from_item(best_item, spell_type), spell_type)
                if challenger_potency > current_best_potency:
                    best_item = item
                elif challenger_potency == current_best_potency:
                    if item.base.item_level > best_item.base.item_level:
                        best_item = item

        if best_item is not None:
            duration_filled[slot_name] = best_item
            gs = _extract_gear_stats_from_item(best_item, spell_type)
            current_gear = _add_gear_stats(current_gear, gs)

    # -------------------------------------------------------------------------
    # Build result
    # -------------------------------------------------------------------------
    gear_set = {**locked, **duration_filled}

    if spell_type == SpellType.REGEN:
        total, duration, ticks, per_tick = calculate_regen_total(spell_tier, current_gear)
    else:
        total, duration, ticks, per_tick = calculate_refresh_total(spell_tier, current_gear)

    final_score = _score(current_gear, spell_type, spell_tier, mode)

    return RegenRefreshResult(
        spell_type=spell_type,
        spell_tier=spell_tier,
        mode=mode,
        gear_set=gear_set,
        potency_slots=list(locked.keys()),
        duration_slots=list(duration_filled.keys()),
        gear_stats=current_gear,
        total_resource=total,
        duration_seconds=duration,
        num_ticks=ticks,
        per_tick=per_tick,
        score=final_score,
    )


def format_optimization_result(result: RegenRefreshResult) -> str:
    """Format an optimization result for display."""
    spell_name = (
        f"Regen {['I','II','III','IV','V'][result.spell_tier - 1]}"
        if result.spell_type == SpellType.REGEN
        else f"Refresh {['I','II','III'][result.spell_tier - 1]}"
    )
    unit = "HP" if result.spell_type == SpellType.REGEN else "MP"
    mode_str = "Max Tick" if result.mode == OptimizationMode.MAX_TICK else "Max Magnitude"

    lines = [
        f"=== {spell_name} Midcast Optimization ({mode_str}) ===",
        f"",
        f"Result:  {result.per_tick} {unit}/tick  x  {result.num_ticks} ticks"
        f"  ({result.duration_seconds:.1f}s)  =  {result.total_resource} {unit} total",
        f"",
        f"Gear Contribution:",
        f"  {'Regen potency' if result.spell_type == SpellType.REGEN else 'Refresh potency'}:"
        f"  +{result.gear_stats.regen_potency if result.spell_type == SpellType.REGEN else result.gear_stats.refresh_potency}"
        f" {unit}/tick",
        f"  Flat duration:   +{result.gear_stats.regen_effect_duration if result.spell_type == SpellType.REGEN else result.gear_stats.refresh_effect_duration}s",
        f"  Enh. dur (gear): +{result.gear_stats.enhancing_duration / 100:.1f}%",
        f"  Enh. dur (aug):  +{result.gear_stats.enhancing_duration_augment / 100:.1f}%",
        f"",
    ]

    if result.potency_slots:
        lines.append(f"Phase 1 - Potency locked slots: {', '.join(result.potency_slots)}")
        for slot_name in result.potency_slots:
            item = result.gear_set.get(slot_name)
            if item:
                lines.append(f"  {slot_name:<12} {item.name}")
    else:
        lines.append("Phase 1 - No potency items found in inventory")

    lines.append("")

    if result.duration_slots:
        lines.append(f"Phase 2 - Duration filled slots: {', '.join(result.duration_slots)}")
        for slot_name in result.duration_slots:
            item = result.gear_set.get(slot_name)
            if item:
                lines.append(f"  {slot_name:<12} {item.name}")
    else:
        lines.append("Phase 2 - No additional duration items found")

    return "\n".join(lines)
