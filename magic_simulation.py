"""
Magic Damage Simulation for FFXI

Simulates magic damage output for gear validation, similar to physical DPS simulation.
Supports both free nuking and magic burst scenarios.

Usage:
    from optimizer.magic_simulation import MagicSimulator, CasterStats
    
    sim = MagicSimulator()
    result = sim.simulate_spell(
        spell_name='Thunder VI',
        caster=CasterStats(int_stat=400, mab=300, magic_accuracy=600),
        target=TargetStats(int_stat=150, magic_evasion=500),
        magic_burst=True,
    )
"""

import random
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from enum import Enum

try:
    from .magic_formulas import (
        Element, MagicType, ResistState,
        calculate_dstat_bonus, calculate_magic_accuracy, calculate_magic_hit_rate,
        roll_resist_state, get_resist_state_average, calculate_base_damage,
        calculate_mb_multiplier, calculate_mbb_multiplier,
        calculate_mab_mdb_ratio, calculate_mtdr,
    )
    from .spell_database import (
        SpellData, get_spell, can_magic_burst, ALL_SPELLS,
    )
except ImportError:
    from magic_formulas import (
        Element, MagicType, ResistState,
        calculate_dstat_bonus, calculate_magic_accuracy, calculate_magic_hit_rate,
        roll_resist_state, get_resist_state_average, calculate_base_damage,
        calculate_mb_multiplier, calculate_mbb_multiplier,
        calculate_mab_mdb_ratio, calculate_mtdr,
    )
    from spell_database import (
        SpellData, get_spell, can_magic_burst, ALL_SPELLS,
    )


# =============================================================================
# Caster and Target Stats
# =============================================================================

@dataclass
class CasterStats:
    """Stats for the spell caster derived from gear/buffs."""
    
    # Primary stats
    int_stat: int = 300
    mnd_stat: int = 250
    
    # Magic offense
    mab: int = 200                    # Magic Attack Bonus
    magic_damage: int = 0             # Magic Damage + from gear
    magic_accuracy: int = 0           # Magic Accuracy from gear
    
    # Skills (1:1 with magic accuracy)
    elemental_magic_skill: int = 500
    dark_magic_skill: int = 400
    enfeebling_magic_skill: int = 400
    healing_magic_skill: int = 400
    enhancing_magic_skill: int = 400
    divine_magic_skill: int = 400
    
    # Magic Burst Bonus
    mbb_gear: int = 0                 # Caps at 4000 (40%)
    mbb_ii_gear: int = 0              # No cap (MBB II)
    mbb_trait: int = 0                # Job trait (uncapped)
    mbb_jp: int = 0                   # Job Points (uncapped)
    mbb_gifts: int = 0                # Gifts (uncapped)
    
    # Elemental affinity
    affinity: Dict[Element, int] = field(default_factory=dict)
    
    # Other modifiers
    fast_cast: int = 0                # Fast Cast %
    
    # For specific spell types
    drain_aspir_potency: int = 0      # Drain/Aspir potency bonus (basis points)
    cure_potency: int = 0             # Cure potency bonus (caps at 5000)
    enfeebling_effect: int = 0        # Enfeebling effect bonus
    enhancing_duration: int = 0       # Enhancing duration bonus
    
    def get_skill_for_type(self, magic_type: MagicType) -> int:
        """Get the appropriate magic skill for spell type."""
        skill_map = {
            MagicType.ELEMENTAL: self.elemental_magic_skill,
            MagicType.DARK: self.dark_magic_skill,
            MagicType.ENFEEBLING_INT: self.enfeebling_magic_skill,
            MagicType.ENFEEBLING_MND: self.enfeebling_magic_skill,
            MagicType.HEALING: self.healing_magic_skill,
            MagicType.ENHANCING: self.enhancing_magic_skill,
            MagicType.DIVINE: self.divine_magic_skill,
        }
        return skill_map.get(magic_type, 400)
    
    def get_stat_for_type(self, magic_type: MagicType) -> int:
        """Get the relevant stat (INT or MND) for spell type."""
        if magic_type in [MagicType.ELEMENTAL, MagicType.DARK, 
                          MagicType.ENFEEBLING_INT, MagicType.NINJUTSU]:
            return self.int_stat
        else:
            return self.mnd_stat


@dataclass
class MagicTargetStats:
    """Stats for the spell target."""
    
    # Stats
    int_stat: int = 150
    mnd_stat: int = 150
    
    # Magic defense
    magic_evasion: int = 500
    magic_defense_bonus: int = 0      # MDB (can be negative with debuffs)
    magic_damage_taken: int = 0       # MDT reduction (basis points, negative = less damage)
    
    # Elemental resistance
    element_resist: Dict[Element, int] = field(default_factory=dict)
    
    def get_stat_for_type(self, magic_type: MagicType) -> int:
        """Get the relevant stat for comparison."""
        if magic_type in [MagicType.ELEMENTAL, MagicType.DARK,
                          MagicType.ENFEEBLING_INT, MagicType.NINJUTSU]:
            return self.int_stat
        else:
            return self.mnd_stat


# =============================================================================
# Predefined Targets (similar to physical simulation)
# =============================================================================

MAGIC_TARGETS = {
    'apex_mob': MagicTargetStats(
        int_stat=200, mnd_stat=200,
        magic_evasion=600, magic_defense_bonus=30,
    ),
    'odyssey_nm': MagicTargetStats(
        int_stat=250, mnd_stat=250,
        magic_evasion=750, magic_defense_bonus=50,
    ),
    'sortie_boss': MagicTargetStats(
        int_stat=280, mnd_stat=280,
        magic_evasion=800, magic_defense_bonus=40,
    ),
    'ambuscade_vd': MagicTargetStats(
        int_stat=220, mnd_stat=220,
        magic_evasion=650, magic_defense_bonus=25,
    ),
    'training_dummy': MagicTargetStats(
        int_stat=100, mnd_stat=100,
        magic_evasion=300, magic_defense_bonus=0,
    ),
    'high_resist': MagicTargetStats(
        int_stat=300, mnd_stat=300,
        magic_evasion=900, magic_defense_bonus=60,
    ),
}


# =============================================================================
# Simulation Results
# =============================================================================

@dataclass
class SpellCastResult:
    """Result of a single spell cast."""
    spell_name: str
    damage: int
    resist_state: ResistState
    hit_rate: float
    magic_burst: bool
    
    # Damage breakdown
    base_d: int
    mab_mdb_ratio: float
    mb_multiplier: float
    mbb_multiplier: float


@dataclass
class MagicSimulationResult:
    """Result of running multiple spell casts."""
    spell_name: str
    num_casts: int
    
    # Damage statistics
    total_damage: int
    average_damage: float
    min_damage: int
    max_damage: int
    
    # Resist statistics
    unresisted_rate: float
    half_resist_rate: float
    quarter_resist_rate: float
    eighth_resist_rate: float
    
    # If time-based (for DPS calculation)
    dps: Optional[float] = None
    cast_time: Optional[float] = None
    
    # Individual casts (optional)
    casts: List[SpellCastResult] = field(default_factory=list)


# =============================================================================
# Magic Damage Simulator
# =============================================================================

class MagicSimulator:
    """Simulates magic damage for gear optimization."""
    
    def __init__(self, seed: Optional[int] = None):
        """
        Initialize simulator.
        
        Args:
            seed: Random seed for reproducible results
        """
        if seed is not None:
            random.seed(seed)
    
    def calculate_spell_damage(
        self,
        spell: SpellData,
        caster: CasterStats,
        target: MagicTargetStats,
        magic_burst: bool = False,
        skillchain_steps: int = 2,
        num_targets: int = 1,
        force_unresisted: bool = False,
    ) -> SpellCastResult:
        """
        Calculate damage for a single spell cast.
        
        Args:
            spell: SpellData for the spell to cast
            caster: Caster stats
            target: Target stats
            magic_burst: Whether this is a magic burst
            skillchain_steps: Number of WS in skillchain (for MB multiplier)
            num_targets: Number of targets (for AoE reduction)
            force_unresisted: If True, assume unresisted (for average calculations)
            
        Returns:
            SpellCastResult with damage and breakdown
        """
        # Get relevant stats based on spell type
        caster_stat = caster.get_stat_for_type(spell.magic_type)
        target_stat = target.get_stat_for_type(spell.magic_type)
        skill = caster.get_skill_for_type(spell.magic_type)
        
        # Calculate dSTAT bonus for magic accuracy
        dstat_bonus = calculate_dstat_bonus(caster_stat, target_stat)
        
        # Calculate total magic accuracy
        total_macc = calculate_magic_accuracy(
            skill=skill,
            magic_acc_gear=caster.magic_accuracy,
            dstat_bonus=dstat_bonus,
            magic_burst=magic_burst,
        )
        
        # Calculate hit rate
        hit_rate = calculate_magic_hit_rate(total_macc, target.magic_evasion)
        
        # Roll for resist (or force unresisted)
        if force_unresisted:
            resist_state = ResistState.UNRESISTED
        else:
            resist_state = roll_resist_state(hit_rate)
        
        # Calculate base damage D
        dint = caster_stat - target_stat
        base_d = calculate_base_damage(
            spell_v=spell.base_v,
            spell_m_values=spell.m_values,
            caster_int=caster_stat,
            target_int=target_stat,
            magic_damage_gear=caster.magic_damage,
        )
        
        # Apply multipliers in order (with flooring)
        damage = float(base_d)
        
        # MTDR (AoE penalty)
        if spell.is_aoe and num_targets > 1:
            damage = int(damage * calculate_mtdr(num_targets))
        
        # Elemental affinity
        affinity = caster.affinity.get(spell.element, 0)
        if affinity > 0:
            damage = int(damage * (1.0 + affinity / 10000))
        
        # Resist
        damage = int(damage * resist_state.value)
        
        # Magic Burst multipliers
        mb_mult = 1.0
        mbb_mult = 1.0
        if magic_burst and skillchain_steps >= 2:
            mb_mult = calculate_mb_multiplier(skillchain_steps)
            damage = int(damage * mb_mult)
            
            mbb_mult = calculate_mbb_multiplier(
                mbb_gear=caster.mbb_gear,
                mbb_ii_gear=caster.mbb_ii_gear,
                mbb_trait=caster.mbb_trait,
                mbb_jp=caster.mbb_jp,
                mbb_gifts=caster.mbb_gifts,
            )
            damage = int(damage * mbb_mult)
        
        # MAB/MDB ratio
        mab_mdb = calculate_mab_mdb_ratio(caster.mab, target.magic_defense_bonus)
        damage = int(damage * mab_mdb)
        
        # Target MDT
        if target.magic_damage_taken != 0:
            mdt_mult = 1.0 + (target.magic_damage_taken / 10000)
            damage = int(damage * mdt_mult)
        
        return SpellCastResult(
            spell_name=spell.name,
            damage=max(0, damage),
            resist_state=resist_state,
            hit_rate=hit_rate,
            magic_burst=magic_burst,
            base_d=base_d,
            mab_mdb_ratio=mab_mdb,
            mb_multiplier=mb_mult,
            mbb_multiplier=mbb_mult,
        )
    
    def simulate_spell(
        self,
        spell_name: str,
        caster: CasterStats,
        target: MagicTargetStats,
        magic_burst: bool = False,
        skillchain_steps: int = 2,
        num_casts: int = 1000,
        num_targets: int = 1,
    ) -> MagicSimulationResult:
        """
        Run a Monte Carlo simulation of spell casts.
        
        Args:
            spell_name: Name of spell to simulate
            caster: Caster stats
            target: Target stats
            magic_burst: Whether these are magic bursts
            skillchain_steps: Number of WS in skillchain
            num_casts: Number of casts to simulate
            num_targets: Number of targets for AoE
            
        Returns:
            MagicSimulationResult with statistics
        """
        spell = get_spell(spell_name)
        if spell is None:
            raise ValueError(f"Unknown spell: {spell_name}")
        
        casts = []
        resist_counts = {state: 0 for state in ResistState}
        
        for _ in range(num_casts):
            result = self.calculate_spell_damage(
                spell=spell,
                caster=caster,
                target=target,
                magic_burst=magic_burst,
                skillchain_steps=skillchain_steps,
                num_targets=num_targets,
            )
            casts.append(result)
            resist_counts[result.resist_state] += 1
        
        damages = [c.damage for c in casts]
        
        return MagicSimulationResult(
            spell_name=spell_name,
            num_casts=num_casts,
            total_damage=sum(damages),
            average_damage=sum(damages) / num_casts,
            min_damage=min(damages),
            max_damage=max(damages),
            unresisted_rate=resist_counts[ResistState.UNRESISTED] / num_casts,
            half_resist_rate=resist_counts[ResistState.HALF] / num_casts,
            quarter_resist_rate=resist_counts[ResistState.QUARTER] / num_casts,
            eighth_resist_rate=resist_counts[ResistState.EIGHTH] / num_casts,
            casts=casts if num_casts <= 100 else [],  # Only store if small sample
        )
    
    def compare_gear_sets(
        self,
        spell_name: str,
        caster_sets: Dict[str, CasterStats],
        target: MagicTargetStats,
        magic_burst: bool = False,
        num_casts: int = 1000,
    ) -> Dict[str, MagicSimulationResult]:
        """
        Compare multiple gear sets for a spell.
        
        Args:
            spell_name: Spell to test
            caster_sets: Dict of set name -> CasterStats
            target: Target to test against
            magic_burst: Whether to test MB damage
            num_casts: Simulations per set
            
        Returns:
            Dict of set name -> simulation result
        """
        results = {}
        for name, caster in caster_sets.items():
            results[name] = self.simulate_spell(
                spell_name=spell_name,
                caster=caster,
                target=target,
                magic_burst=magic_burst,
                num_casts=num_casts,
            )
        return results


# =============================================================================
# Convenience Functions
# =============================================================================

def quick_magic_test(
    spell_name: str,
    int_stat: int = 400,
    mab: int = 300,
    mbb_gear: int = 4000,
    mbb_trait: int = 1300,
    magic_accuracy: int = 600,
    elemental_skill: int = 500,
    target_name: str = 'apex_mob',
    magic_burst: bool = True,
    num_casts: int = 100,
) -> MagicSimulationResult:
    """
    Quick spell damage test with sensible defaults.
    
    Returns simulation result for the specified configuration.
    """
    caster = CasterStats(
        int_stat=int_stat,
        mab=mab,
        magic_accuracy=magic_accuracy,
        elemental_magic_skill=elemental_skill,
        mbb_gear=mbb_gear,
        mbb_trait=mbb_trait,
    )
    
    target = MAGIC_TARGETS.get(target_name, MAGIC_TARGETS['apex_mob'])
    
    sim = MagicSimulator(seed=42)
    return sim.simulate_spell(
        spell_name=spell_name,
        caster=caster,
        target=target,
        magic_burst=magic_burst,
        num_casts=num_casts,
    )


def estimate_magic_dps(
    spell_name: str,
    caster: CasterStats,
    target: MagicTargetStats,
    cast_time: float = 5.0,
    recast_time: float = 0.0,
    magic_burst: bool = False,
) -> float:
    """
    Estimate magic DPS (damage per second).
    
    Note: This is simplified - doesn't account for MB timing windows,
    skillchain setup time, etc.
    
    Args:
        spell_name: Spell to calculate for
        caster: Caster stats
        target: Target stats
        cast_time: Cast time in seconds (after fast cast)
        recast_time: Recast delay in seconds
        magic_burst: Whether magic bursting
        
    Returns:
        Estimated DPS
    """
    sim = MagicSimulator(seed=42)
    result = sim.simulate_spell(
        spell_name=spell_name,
        caster=caster,
        target=target,
        magic_burst=magic_burst,
        num_casts=100,
    )
    
    cycle_time = cast_time + recast_time
    return result.average_damage / cycle_time
