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
    1: (5, 75),    # Regen I: 5 HP/tick, 75 sec
    2: (12, 60),   # Regen II: 12 HP/tick, 60 sec
    3: (20, 60),   # Regen III: 20 HP/tick, 60 sec
    4: (30, 60),   # Regen IV: 30 HP/tick, 60 sec
    5: (40, 60),   # Regen V: 40 HP/tick, 60 sec
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
