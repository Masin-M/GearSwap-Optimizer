"""
Magic Damage Formulas for FFXI

Complete magic damage calculation system including:
- Base damage (D) with dINT scaling
- Magic Burst multipliers (MB, MBB, MBB II)
- MAB/MDB ratio
- Magic Accuracy and Hit Rate
- Resist states

Reference: https://www.bg-wiki.com/ffxi/Magic_Damage
All percentages stored as basis points (100 = 1%) for consistency.
"""

import random
from typing import Tuple, Optional, Dict, List
from dataclasses import dataclass
from enum import Enum, auto


class Element(Enum):
    """Magic elements in FFXI."""
    FIRE = auto()
    ICE = auto()
    WIND = auto()
    EARTH = auto()
    THUNDER = auto()
    WATER = auto()
    LIGHT = auto()
    DARK = auto()


class MagicType(Enum):
    """Types of magic for accuracy calculations."""
    ELEMENTAL = auto()      # Uses Elemental Magic skill, dINT
    DARK = auto()           # Uses Dark Magic skill, dINT
    DIVINE = auto()         # Uses Divine Magic skill, dMND
    ENFEEBLING_INT = auto() # Uses Enfeebling skill, dINT (Sleep, Gravity, etc.)
    ENFEEBLING_MND = auto() # Uses Enfeebling skill, dMND (Slow, Paralyze, etc.)
    HEALING = auto()        # Uses Healing Magic skill, dMND
    ENHANCING = auto()      # Uses Enhancing Magic skill
    NINJUTSU = auto()       # Uses Ninjutsu skill, no dSTAT


class ResistState(Enum):
    """Magic resist states and their damage multipliers."""
    UNRESISTED = 1.0
    HALF = 0.5
    QUARTER = 0.25
    EIGHTH = 0.125


# =============================================================================
# Magic Accuracy / Hit Rate
# =============================================================================

def calculate_dstat_bonus(caster_stat: int, target_stat: int) -> float:
    """
    Calculate magic accuracy bonus from stat difference (dINT, dMND, etc.).
    
    Uses the accurate piecewise function from wsdist/nuking.py:
    - Full 1:1 ratio within ±10 dSTAT
    - 0.5:1 ratio from ±10 to ±30 dSTAT  
    - 0.25:1 ratio from ±30 to ±70 dSTAT
    - Caps at ±30 magic accuracy at ±70 stat difference
    
    Reference: https://luteff11.livedoor.blog/archives/49725347.html
    
    Args:
        caster_stat: Caster's relevant stat (INT, MND, etc.)
        target_stat: Target's relevant stat
        
    Returns:
        Magic accuracy bonus from dSTAT (can be negative)
    """
    dstat = caster_stat - target_stat
    
    # Piecewise function matching wsdist's nuking.py
    if dstat <= -70:
        dstat_macc = -30
    elif dstat <= -30:
        dstat_macc = 0.25 * dstat - 12.5
    elif dstat <= -10:
        dstat_macc = 0.5 * dstat - 5.0
    elif dstat <= 10:
        dstat_macc = 1.0 * dstat
    elif dstat <= 30:
        dstat_macc = 0.5 * dstat + 5.0
    elif dstat <= 70:
        dstat_macc = 0.25 * dstat + 12.5
    else:
        dstat_macc = 30
    
    return dstat_macc


def calculate_magic_accuracy(
    skill: int,
    magic_acc_gear: int = 0,
    dstat_bonus: int = 0,
    magic_burst: bool = False,
) -> int:
    """
    Calculate total magic accuracy.
    
    Args:
        skill: Magic skill (1:1 with magic accuracy)
        magic_acc_gear: Magic accuracy from gear
        dstat_bonus: Bonus from dINT/dMND (use calculate_dstat_bonus)
        magic_burst: If True, add +100 magic accuracy
        
    Returns:
        Total magic accuracy
    """
    total = skill + magic_acc_gear + dstat_bonus
    
    if magic_burst:
        total += 100
    
    return total


def calculate_magic_hit_rate(
    magic_accuracy: int,
    magic_evasion: int,
    cap: float = 0.95,
    floor: float = 0.05,
) -> float:
    """
    Calculate magic hit rate (probability of landing unresisted).
    
    Formula:
        If dMAcc < 0: Hit Rate = 50% + floor(dMAcc/2)%
        If dMAcc >= 0: Hit Rate = 50% + dMAcc%
        
    Args:
        magic_accuracy: Caster's total magic accuracy
        magic_evasion: Target's magic evasion
        cap: Maximum hit rate (default 95%)
        floor: Minimum hit rate (default 5%)
        
    Returns:
        Hit rate as decimal (0.05 to 0.95)
    """
    dmacc = magic_accuracy - magic_evasion
    
    if dmacc < 0:
        # Below 50%, each point of MA = 0.5% hit rate
        hit_rate = 0.50 + (dmacc // 2) / 100
    else:
        # Above 50%, each point of MA = 1% hit rate
        hit_rate = 0.50 + dmacc / 100
    
    return max(floor, min(cap, hit_rate))


def roll_resist_state(magic_hit_rate: float) -> ResistState:
    """
    Roll for resist state based on magic hit rate.
    
    Uses the correct 3-roll sequential method from wsdist/nuking.py:
    - Roll up to 3 times, stopping on first success
    - Each failed roll halves damage
    - This produces correct probability distribution
    
    At 95% hit rate:
    - Unresisted: 95%
    - Half: 4.75% (fail once, then succeed)
    - Quarter: 0.2375% (fail twice, then succeed)
    - Eighth: 0.0125% (fail all three)
    
    Args:
        magic_hit_rate: Hit rate as decimal (0.05 to 0.95)
        
    Returns:
        ResistState enum value
    """
    resist_multiplier = 1.0
    
    for _ in range(3):
        if random.random() < magic_hit_rate:
            # Success - stop rolling
            break
        else:
            # Failed roll - halve damage and continue
            resist_multiplier *= 0.5
    
    # Convert multiplier to ResistState enum
    if resist_multiplier == 1.0:
        return ResistState.UNRESISTED
    elif resist_multiplier == 0.5:
        return ResistState.HALF
    elif resist_multiplier == 0.25:
        return ResistState.QUARTER
    else:
        return ResistState.EIGHTH


def get_resist_state_average(magic_hit_rate: float) -> float:
    """
    Calculate the average resist coefficient analytically (no RNG).
    
    This is useful for calculating expected/average damage without
    running Monte Carlo simulations. Uses the exact formula from
    wsdist/nuking.py.
    
    The formula accounts for the 3-roll sequential resist system:
    - P(unresisted) = hit_rate
    - P(half) = hit_rate * (1 - hit_rate)  [fail once, then succeed]
    - P(quarter) = hit_rate * (1 - hit_rate)^2  [fail twice, then succeed]
    - P(eighth) = (1 - hit_rate)^3  [fail all three]
    
    Average = 1.0*P(unresisted) + 0.5*P(half) + 0.25*P(quarter) + 0.125*P(eighth)
    
    Simplified: hit_rate + 0.5*hit_rate*(1-hit_rate) + 0.25*hit_rate*(1-hit_rate)^2 + 0.125*(1-hit_rate)^3
    
    Args:
        magic_hit_rate: Hit rate as decimal (0.0 to 1.0)
        
    Returns:
        Average resist multiplier (0.125 to 1.0)
    """
    h = magic_hit_rate
    miss = 1.0 - h
    
    resist_avg = (
        h +                           # Unresisted: hit_rate * 1.0
        0.500 * h * miss +            # Half: hit_rate * miss * 0.5
        0.250 * h * (miss ** 2) +     # Quarter: hit_rate * miss^2 * 0.25
        0.125 * (miss ** 3)           # Eighth: miss^3 * 0.125
    )
    
    return resist_avg


# =============================================================================
# Base Damage (D) Calculation
# =============================================================================

def calculate_base_damage(
    spell_v: int,
    spell_m_values: Dict[int, Tuple[int, float]],
    caster_int: int,
    target_int: int,
    magic_damage_gear: int = 0,
) -> int:
    """
    Calculate base spell damage (D) with dINT scaling.
    
    D = mDMG + V + (dINT × M)
    
    The M value changes at different dINT thresholds.
    
    Args:
        spell_v: Base V value of the spell (at dINT 0)
        spell_m_values: Dict mapping dINT threshold to (V_at_threshold, M_multiplier)
                        e.g., {0: (100, 3.0), 50: (250, 2.0), 100: (350, 1.0)}
        caster_int: Caster's INT stat
        target_int: Target's INT stat
        magic_damage_gear: "Magic Damage +" from gear
        
    Returns:
        Base damage D value
    """
    dint = caster_int - target_int
    
    if dint < 0:
        # Negative dINT: D = mDMG + V + dINT (M is always 1 for penalties)
        return max(1, magic_damage_gear + spell_v + dint)
    
    # Find the appropriate V and M for this dINT
    # Sort thresholds in descending order to find the highest applicable one
    thresholds = sorted(spell_m_values.keys(), reverse=True)
    
    for threshold in thresholds:
        if dint >= threshold:
            v_at_threshold, m = spell_m_values[threshold]
            # Calculate: D = mDMG + V_threshold + (dINT - threshold) × M
            d = magic_damage_gear + v_at_threshold + int((dint - threshold) * m)
            return d
    
    # Fallback to base V if no threshold matched (shouldn't happen)
    return magic_damage_gear + spell_v + dint


# =============================================================================
# Magic Burst Multipliers
# =============================================================================

def calculate_mb_multiplier(skillchain_steps: int) -> float:
    """
    Calculate base Magic Burst multiplier from skillchain.
    
    Formula from wsdist: MB = 1.35 + (0.10 × (steps - 2))
    
    - 2-step skillchain: 1.35 (base +35%)
    - 3-step skillchain: 1.45 (+10% per additional step)
    - 4-step skillchain: 1.55
    - etc.
    
    Args:
        skillchain_steps: Number of weapon skills in the skillchain (2+)
        
    Returns:
        Magic Burst multiplier (1.0 if no MB, 1.35+ for MB)
    """
    if skillchain_steps < 2:
        return 1.0
    
    # Base 1.35 for 2-step, +0.10 for each additional step
    return 1.35 + (0.10 * (skillchain_steps - 2))


def calculate_mbb_multiplier(
    mbb_gear: int,
    mbb_ii_gear: int = 0,
    mbb_trait: int = 0,
    mbb_jp: int = 0,
    mbb_gifts: int = 0,
    am_ii_merits: int = 0,
) -> float:
    """
    Calculate Magic Burst Bonus multiplier.
    
    MBB = 1.0 + Gear + Trait + JP + Gifts + AM_II_Merits
    
    Gear category caps at 40%, traits/JP/gifts/MBB II gear do not.
    
    Args:
        mbb_gear: Magic Burst Bonus from gear (basis points, caps at 4000)
        mbb_ii_gear: Magic Burst Bonus II from gear (basis points, no cap)
        mbb_trait: MBB from job trait (basis points, e.g., BLM 1300 = 13%)
        mbb_jp: MBB from Job Points (basis points)
        mbb_gifts: MBB from Gifts (basis points)
        am_ii_merits: Ancient Magic II merit level (0-5, gives 0-12%)
        
    Returns:
        Magic Burst Bonus multiplier
    """
    # Gear category caps at 40%
    gear_capped = min(mbb_gear, 4000)
    
    # AM II merits: 3% per merit after the first (0, 3, 6, 9, 12%)
    am_ii_bonus = max(0, (am_ii_merits - 1) * 300) if am_ii_merits > 0 else 0
    
    # Uncapped sources (MBB II gear, trait, JP, gifts)
    uncapped = mbb_ii_gear + mbb_trait + mbb_jp + mbb_gifts
    
    # Total MBB
    total = gear_capped + am_ii_bonus + uncapped
    
    return 1.0 + (total / 10000)


# =============================================================================
# MAB/MDB Ratio
# =============================================================================

def calculate_mab_mdb_ratio(mab: int, mdb: int) -> float:
    """
    Calculate the MAB/MDB damage multiplier.
    
    Formula: (1 + MAB/100) / (1 + max(-0.5, MDB/100))
    
    MDB is floored at -50% (divisor minimum 0.5).
    
    Args:
        mab: Total Magic Attack Bonus
        mdb: Target's Magic Defense Bonus (can be negative with debuffs)
        
    Returns:
        MAB/MDB multiplier
    """
    mab_mult = 1.0 + (mab / 100)
    mdb_mult = 1.0 + max(-0.5, mdb / 100)
    
    return mab_mult / mdb_mult


# =============================================================================
# Other Multipliers
# =============================================================================

def calculate_mtdr(num_targets: int) -> float:
    """
    Calculate Multiple-Target Damage Reduction.
    
    Args:
        num_targets: Number of targets hit
        
    Returns:
        MTDR multiplier
    """
    if num_targets <= 1:
        return 1.0
    elif num_targets >= 10:
        return 0.4
    else:
        return 0.9 - (0.05 * num_targets)


def calculate_staff_bonus(
    staff_element: Optional[Element],
    spell_element: Element,
    is_hq: bool = False,
) -> float:
    """
    Calculate elemental staff damage bonus.
    
    Args:
        staff_element: Element of equipped staff (None if not elemental)
        spell_element: Element of the spell
        is_hq: Whether the staff is HQ
        
    Returns:
        Staff multiplier (0.85 to 1.15)
    """
    if staff_element is None:
        return 1.0
    
    if staff_element == spell_element:
        return 1.15 if is_hq else 1.1
    
    # Check for opposed element (simplified - would need full wheel)
    # For now, return 1.0 for non-matching
    return 1.0


def calculate_day_weather_bonus(
    spell_element: Element,
    current_day: Optional[Element] = None,
    current_weather: Optional[Element] = None,
    double_weather: bool = False,
    has_obi: bool = False,
) -> float:
    """
    Calculate day and weather bonus.
    
    Max bonus is 1.4.
    
    Args:
        spell_element: Element of the spell
        current_day: Element of the current day (None = no day bonus)
        current_weather: Element of current weather (None = no weather)
        double_weather: Whether weather is double
        has_obi: Whether wearing matching elemental obi (guarantees proc)
        
    Returns:
        Day/Weather multiplier (capped at 1.4)
    """
    bonus = 1.0
    
    # Day bonus (procs randomly unless obi)
    if current_day == spell_element:
        if has_obi or random.random() < 0.33:  # ~33% proc rate
            bonus += 0.1
    
    # Weather bonus
    if current_weather == spell_element:
        if has_obi or random.random() < 0.33:
            if double_weather:
                bonus += 0.25
            else:
                bonus += 0.1
    
    return min(bonus, 1.4)


# =============================================================================
# Complete Magic Damage Calculation
# =============================================================================

@dataclass
class MagicDamageResult:
    """Result of magic damage calculation."""
    base_damage: int
    resist_state: ResistState
    final_damage: int
    hit_rate: float
    
    # Breakdown
    d_value: int
    mab_mdb_ratio: float
    mb_multiplier: float
    mbb_multiplier: float


def calculate_magic_damage(
    # Spell stats
    spell_v: int,
    spell_m_values: Dict[int, Tuple[int, float]],
    spell_element: Element,
    
    # Caster stats
    caster_int: int,
    magic_damage_gear: int,
    mab: int,
    magic_accuracy: int,
    
    # Target stats
    target_int: int,
    target_meva: int,
    
    # Optional caster stats
    mbb_gear: int = 0,
    mbb_ii_gear: int = 0,
    mbb_trait: int = 0,
    
    # Optional target stats
    target_mdb: int = 0,
    target_mdt: int = 0,
    
    # Combat context
    magic_burst: bool = False,
    skillchain_steps: int = 0,
    num_targets: int = 1,
    
    # Optional bonuses
    affinity_bonus: int = 0,
    potency_multiplier: float = 1.0,
) -> MagicDamageResult:
    """
    Calculate complete magic damage.
    
    Returns MagicDamageResult with damage and all factors.
    """
    # Calculate base damage D
    d_value = calculate_base_damage(
        spell_v, spell_m_values, caster_int, target_int, magic_damage_gear
    )
    
    # Calculate hit rate
    dstat = calculate_dstat_bonus(caster_int, target_int)
    total_macc = calculate_magic_accuracy(magic_accuracy, 0, dstat, magic_burst)
    hit_rate = calculate_magic_hit_rate(total_macc, target_meva)
    
    # Roll for resist
    resist_state = roll_resist_state(hit_rate)
    
    # Apply multipliers in order (with flooring after each)
    damage = float(d_value)
    
    # MTDR
    damage = int(damage * calculate_mtdr(num_targets))
    
    # Affinity
    if affinity_bonus > 0:
        affinity_mult = 1.0 + (affinity_bonus / 10000)
        damage = int(damage * affinity_mult)
    
    # Resist
    damage = int(damage * resist_state.value)
    
    # Magic Burst
    mb_multiplier = 1.0
    mbb_multiplier = 1.0
    if magic_burst and skillchain_steps >= 2:
        mb_multiplier = calculate_mb_multiplier(skillchain_steps)
        damage = int(damage * mb_multiplier)
        
        mbb_multiplier = calculate_mbb_multiplier(mbb_gear, mbb_ii_gear, mbb_trait)
        damage = int(damage * mbb_multiplier)
    
    # MAB/MDB
    mab_mdb = calculate_mab_mdb_ratio(mab, target_mdb)
    damage = int(damage * mab_mdb)
    
    # Target MDT (damage taken reduction)
    if target_mdt != 0:
        mdt_mult = 1.0 + (target_mdt / 10000)  # Negative = reduction
        damage = int(damage * mdt_mult)
    
    # Potency multipliers (Ebullience, etc.)
    if potency_multiplier != 1.0:
        damage = int(damage * potency_multiplier)
    
    return MagicDamageResult(
        base_damage=d_value,
        resist_state=resist_state,
        final_damage=max(0, damage),
        hit_rate=hit_rate,
        d_value=d_value,
        mab_mdb_ratio=mab_mdb,
        mb_multiplier=mb_multiplier,
        mbb_multiplier=mbb_multiplier,
    )


# =============================================================================
# Dark Magic (Drain/Aspir) Formulas
# =============================================================================

def calculate_drain_potency(
    dark_skill: int,
    drain_potency_gear: int = 0,
    affinity_bonus: int = 0,
) -> Tuple[int, int]:
    """
    Calculate Drain spell potency range.
    
    Formula:
        At ≤300 skill: max = Dark Magic Skill + 20
        At >300 skill: max = Skill × 5/8 + 132.5
        
    Min is 75% of max. Actual randomly falls between min and max.
    
    Args:
        dark_skill: Dark Magic skill
        drain_potency_gear: Drain/Aspir potency from gear (basis points)
        affinity_bonus: Dark affinity bonus (basis points)
        
    Returns:
        Tuple of (min_potency, max_potency)
    """
    if dark_skill <= 300:
        base_max = dark_skill + 20
    else:
        base_max = int(dark_skill * 5 / 8 + 132.5)
    
    # Apply potency gear
    potency_mult = 1.0 + (drain_potency_gear / 10000)
    max_potency = int(base_max * potency_mult)
    
    # Apply affinity
    if affinity_bonus > 0:
        affinity_mult = 1.0 + (affinity_bonus / 10000)
        max_potency = int(max_potency * affinity_mult)
    
    # Min is 75% of max
    min_potency = int(max_potency * 0.75)
    
    return (min_potency, max_potency)


def calculate_aspir_potency(
    dark_skill: int,
    aspir_tier: int = 1,
    drain_potency_gear: int = 0,
    affinity_bonus: int = 0,
) -> Tuple[int, int]:
    """
    Calculate Aspir spell potency range.
    
    Formulas vary by tier:
        Aspir I: At ≤300: Skill/3 + 20; At >300: Skill × 0.4
        Aspir II: Skill × 0.6
        Aspir III: Skill × 0.8
        
    Min is 50% of max.
    
    Args:
        dark_skill: Dark Magic skill
        aspir_tier: 1, 2, or 3
        drain_potency_gear: Drain/Aspir potency from gear (basis points)
        affinity_bonus: Dark affinity bonus (basis points)
        
    Returns:
        Tuple of (min_potency, max_potency)
    """
    if aspir_tier == 1:
        if dark_skill <= 300:
            base_max = dark_skill // 3 + 20
        else:
            base_max = int(dark_skill * 0.4)
    elif aspir_tier == 2:
        base_max = int(dark_skill * 0.6)
    else:  # Aspir III
        base_max = int(dark_skill * 0.8)
    
    # Apply potency gear
    potency_mult = 1.0 + (drain_potency_gear / 10000)
    max_potency = int(base_max * potency_mult)
    
    # Apply affinity
    if affinity_bonus > 0:
        affinity_mult = 1.0 + (affinity_bonus / 10000)
        max_potency = int(max_potency * affinity_mult)
    
    # Min is 50% of max
    min_potency = int(max_potency * 0.5)
    
    return (min_potency, max_potency)


# =============================================================================
# Enfeebling Magic Potency
# =============================================================================

def calculate_slow_potency(caster_mnd: int, target_mnd: int, is_slow_ii: bool = False) -> int:
    """
    Calculate Slow spell potency in basis points.
    
    Slow I: 7.3% to 29.2% based on dMND (caps at ±75)
    Slow II: 12.5% to 35.56% based on dMND
    
    Returns:
        Slow effect in basis points
    """
    dmnd = min(75, max(-75, caster_mnd - target_mnd))
    
    if is_slow_ii:
        # Slow II: 12.5% to 35.56%
        # Range is 2306 basis points over 150 dMND range
        base = 1250 + int((dmnd + 75) * 2306 / 150)
        return min(3556, max(1250, base))
    else:
        # Slow I: 7.3% to 29.2%
        # Range is 2190 basis points over 150 dMND range
        base = 730 + int((dmnd + 75) * 2190 / 150)
        return min(2920, max(730, base))


def calculate_paralyze_potency(caster_mnd: int, target_mnd: int, is_para_ii: bool = False) -> int:
    """
    Calculate Paralyze proc rate in basis points.
    
    Paralyze I: 5% to 25% based on dMND (caps at ±40)
    Paralyze II: 10% to 30% based on dMND
    
    Returns:
        Paralyze proc rate in basis points
    """
    dmnd = min(40, max(-40, caster_mnd - target_mnd))
    
    if is_para_ii:
        # Para II: 10% to 30%
        base = 1000 + int((dmnd + 40) * 2000 / 80)
        return min(3000, max(1000, base))
    else:
        # Para I: 5% to 25%
        base = 500 + int((dmnd + 40) * 2000 / 80)
        return min(2500, max(500, base))


def calculate_blind_potency(caster_int: int, target_int: int, is_blind_ii: bool = False) -> int:
    """
    Calculate Blind accuracy reduction.
    
    Blind I: 5 to 50 based on dINT (-73 to +120)
    Blind II: 15 to 90 based on dINT
    
    Returns:
        Accuracy reduction value
    """
    dint = min(120, max(-73, caster_int - target_int))
    
    if is_blind_ii:
        # Blind II: 15 to 90
        base = 15 + int((dint + 73) * 75 / 193)
        return min(90, max(15, base))
    else:
        # Blind I: 5 to 50
        base = 5 + int((dint + 73) * 45 / 193)
        return min(50, max(5, base))


# =============================================================================
# Enspell Damage Calculations
# =============================================================================

def calculate_enspell_damage(
    enhancing_skill: int,
    tier: int = 1,
    attack_rounds: int = 0,
    sword_enhancement_flat: int = 0,
    sword_enhancement_percent: int = 0,
    composure_active: bool = False,
    merit_bonus: int = 0,
    jp_gift_bonus: int = 0,
) -> int:
    """
    Calculate Enspell damage per hit.
    
    Tier I formula:
        If skill <= 200: floor(6*skill/100) + 3
        If skill > 200: floor(5*skill/100) + 5
        Cap: 21
        
    Tier II formula:
        Same base, but builds +1 per attack round up to 2x base
        Cap: 42
        Only first hit of each round gets full damage
        
    Full formula:
        (((Base + Merits + JP Gifts + Sword Enhancement +n) 
          × (Composure + Sword Enhancement +n%)) 
          × Staff × Affinity × Resist × Day/Weather × TMDA) × Potency
    
    Args:
        enhancing_skill: Caster's Enhancing Magic skill
        tier: Enspell tier (1 or 2)
        attack_rounds: Number of attack rounds since cast (for Tier II buildup)
        sword_enhancement_flat: Flat "Sword enhancement spell damage +n" from gear
        sword_enhancement_percent: Percent "Sword enhancement spell damage +n%" from weapons
        composure_active: Whether Composure is active (+25%)
        merit_bonus: RDM Group 2 merit bonus
        jp_gift_bonus: RDM Job Point gift bonus
        
    Returns:
        Base enspell damage before resist/affinity modifiers
    """
    # Calculate base damage from skill
    if enhancing_skill <= 200:
        base = (6 * enhancing_skill // 100) + 3
    else:
        base = (5 * enhancing_skill // 100) + 5
    
    # Cap at tier-appropriate value
    tier_1_cap = 21
    tier_2_cap = 42
    
    base = min(base, tier_1_cap)
    
    # For Tier II, add buildup from attack rounds
    if tier == 2:
        buildup = min(attack_rounds, tier_1_cap)  # Can't exceed base cap
        base = min(base + buildup, tier_2_cap)
    
    # Add flat bonuses
    damage = base + merit_bonus + jp_gift_bonus + sword_enhancement_flat
    
    # Apply percent multipliers
    multiplier = 1.0
    if composure_active:
        multiplier += 0.25
    if sword_enhancement_percent > 0:
        multiplier += sword_enhancement_percent / 100
    
    return int(damage * multiplier)


def calculate_enlight_endark_damage(
    magic_skill: int,
    tier: int = 1,
    ticks_elapsed: int = 0,
    potency_gear: int = 0,
) -> Tuple[int, int]:
    """
    Calculate Enlight/Endark damage and stat bonus.
    
    Unlike RDM Enspells, Enlight/Endark:
    - Use Divine/Dark Magic skill respectively
    - Start at high potency and decay over time
    - Grant Accuracy (Enlight) or Attack (Endark) equal to current damage
    
    Args:
        magic_skill: Divine Magic skill (Enlight) or Dark Magic skill (Endark)
        tier: Spell tier (1 or 2, with II being a Job Gift)
        ticks_elapsed: Number of decay ticks elapsed
        potency_gear: Enlight/Endark potency bonus gear
        
    Returns:
        Tuple of (damage_per_hit, stat_bonus)
    """
    # Base potency scales with skill
    # Approximate formula: skill / 10 for starting damage
    if tier == 2:
        base = int(magic_skill * 0.12)  # Tier II is ~20% higher
    else:
        base = int(magic_skill * 0.1)
    
    # Apply potency gear
    if potency_gear > 0:
        base = int(base * (1.0 + potency_gear / 100))
    
    # Apply decay (loses potency over time)
    # Approximate decay: -1 per tick
    current = max(1, base - ticks_elapsed)
    
    # Stat bonus equals current damage
    stat_bonus = current
    
    return (current, stat_bonus)


# =============================================================================
# Bio DOT Damage
# =============================================================================

def calculate_bio_dot(dark_skill: int, bio_tier: int = 3) -> int:
    """
    Calculate Bio spell DOT damage per tick.
    
    Bio III formula: floor((Dark Magic Skill + 59) / 27)
    Bio II/I use different divisors.
    
    Args:
        dark_skill: Caster's Dark Magic skill
        bio_tier: Bio spell tier (1, 2, or 3)
        
    Returns:
        DOT damage per tick (3-second ticks)
    """
    if bio_tier == 3:
        # Bio III: floor((skill + 59) / 27), caps at 17
        dot = (dark_skill + 59) // 27
        return min(17, dot)
    elif bio_tier == 2:
        # Bio II: floor((skill + 59) / 36)
        dot = (dark_skill + 59) // 36
        return min(12, dot)
    else:
        # Bio I: floor((skill + 59) / 54)
        dot = (dark_skill + 59) // 54
        return min(8, dot)


def calculate_dia_dot(tier: int = 1) -> int:
    """
    Calculate Dia DOT damage per tick.
    
    Dia is a fixed DOT based on tier, not skill.
    
    Args:
        tier: Dia spell tier (1, 2, or 3)
        
    Returns:
        DOT damage per tick
    """
    # Dia DOT is fixed by tier
    return {1: 1, 2: 2, 3: 3}.get(tier, 1)


# =============================================================================
# Divine Magic (Banish/Holy) - Uses dMND instead of dINT
# =============================================================================

def calculate_divine_damage(
    spell_v: int,
    spell_m: float,
    caster_mnd: int,
    target_mnd: int,
    magic_damage_gear: int = 0,
    mab: int = 0,
    target_mdb: int = 0,
    divine_skill: int = 0,
    divine_emblem_active: bool = False,
    is_undead: bool = False,
) -> int:
    """
    Calculate Divine magic damage (Banish, Holy).
    
    Divine magic uses dMND instead of dINT but otherwise follows
    the same damage formula as elemental magic.
    
    Divine Emblem gives a massive multiplier based on Divine skill:
        Damage = floor(Normal Damage × (1 + Divine Magic Skill / 100))
    
    Args:
        spell_v: Base V value of spell
        spell_m: M multiplier at current dMND threshold
        caster_mnd: Caster's MND
        target_mnd: Target's MND
        magic_damage_gear: Magic Damage+ from gear
        mab: Magic Attack Bonus
        target_mdb: Target's Magic Defense Bonus
        divine_skill: Divine Magic skill (for Divine Emblem)
        divine_emblem_active: Whether Divine Emblem JA is active
        is_undead: Whether target is undead (bonus damage)
        
    Returns:
        Calculated damage before resist
    """
    # Calculate dMND (works like dINT for divine)
    dmnd = caster_mnd - target_mnd
    
    # Base damage: mDMG + V + (dMND × M)
    d = magic_damage_gear + spell_v + int(max(0, dmnd) * spell_m)
    
    # MAB/MDB ratio
    mab_mult = (1 + mab / 100) / (1 + max(-0.5, target_mdb / 100))
    damage = int(d * mab_mult)
    
    # Divine Emblem multiplier
    if divine_emblem_active and divine_skill > 0:
        emblem_mult = 1 + (divine_skill / 100)
        damage = int(damage * emblem_mult)
    
    # Bonus damage vs undead (Banish effect)
    if is_undead:
        damage = int(damage * 1.5)  # Approximate undead weakness
    
    return damage
