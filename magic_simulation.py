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
        # Enfeebling formulas
        calculate_slow_potency, calculate_paralyze_potency, calculate_blind_potency,
        # Dark magic formulas
        calculate_drain_potency, calculate_aspir_potency, calculate_bio_dot,
        # Enspell formulas
        calculate_enspell_damage, calculate_enlight_endark_damage,
        # Healing formulas
        calculate_cure_amount, calculate_curaga_amount,
        # Enhancing formulas
        calculate_phalanx_potency, calculate_regen_potency, calculate_refresh_potency,
        calculate_haste_potency, calculate_enhancing_duration, calculate_temper_potency,
        calculate_gain_potency,
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
        # Enfeebling formulas
        calculate_slow_potency, calculate_paralyze_potency, calculate_blind_potency,
        # Dark magic formulas
        calculate_drain_potency, calculate_aspir_potency, calculate_bio_dot,
        # Enspell formulas
        calculate_enspell_damage, calculate_enlight_endark_damage,
        # Healing formulas
        calculate_cure_amount, calculate_curaga_amount,
        # Enhancing formulas
        calculate_phalanx_potency, calculate_regen_potency, calculate_refresh_potency,
        calculate_haste_potency, calculate_enhancing_duration, calculate_temper_potency,
        calculate_gain_potency,
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
    
    # Enspell damage bonuses (RDM)
    sword_enhancement_flat: int = 0   # "Sword enhancement spell damage +N"
    sword_enhancement_percent: int = 0 # "Sword enhancement spell dmg. +N%"
    
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
    # New high-difficulty targets for realistic endgame testing
    'odyssey_v25': MagicTargetStats(
        int_stat=350, mnd_stat=350,
        magic_evasion=1200, magic_defense_bonus=80,
    ),
    'odyssey_v20': MagicTargetStats(
        int_stat=320, mnd_stat=320,
        magic_evasion=1100, magic_defense_bonus=70,
    ),
    'odyssey_v15': MagicTargetStats(
        int_stat=290, mnd_stat=290,
        magic_evasion=1000, magic_defense_bonus=60,
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


@dataclass
class EnfeeblingSimulationResult:
    """Result of enfeebling spell simulation."""
    spell_name: str
    landed: bool
    hit_rate: float
    
    # Potency results (spell-dependent)
    potency_value: float          # The actual effect value
    potency_unit: str             # '%', 'acc reduction', 'eva reduction', etc.
    potency_description: str      # Human readable: "29.7% Slow"
    
    # Duration
    base_duration: float          # Seconds
    enhanced_duration: float      # After duration gear
    
    # Stat breakdown
    skill_contribution: int
    stat_contribution: int        # dINT or dMND contribution
    gear_bonus: int               # Enfeebling effect+ gear


@dataclass
class HealingSimulationResult:
    """Result of healing spell simulation."""
    spell_name: str
    
    # Healing output
    hp_healed: int
    hp_healed_with_received: int  # If target has Cure Potency II
    
    # Efficiency
    mp_cost: int
    hp_per_mp: float
    
    # Breakdown
    base_hp: int
    cure_potency_mult: float
    skill_contribution: int
    mnd_contribution: int


@dataclass  
class EnhancingSimulationResult:
    """Result of enhancing spell simulation."""
    spell_name: str
    
    # Potency (varies by spell type)
    potency_value: float          # The effect value
    potency_unit: str             # 'damage', 'reduction', '%', etc.
    potency_description: str      # Human readable
    
    # Duration
    base_duration: float
    final_duration: float
    
    # For enspells specifically
    damage_per_hit: int = 0
    damage_at_cap: int = 0        # After buildup for Tier II
    
    # Breakdown
    skill_contribution: int = 0
    gear_contribution: int = 0


@dataclass
class DarkMagicSimulationResult:
    """Result of dark magic (Drain/Aspir/Bio) simulation."""
    spell_name: str
    hit_rate: float
    
    # For Drain/Aspir
    amount_drained: int = 0
    resource_type: str = ""       # 'HP' or 'MP'
    
    # For Bio
    initial_damage: int = 0
    dot_damage_per_tick: int = 0
    dot_duration: float = 0       # Seconds
    total_dot_damage: int = 0
    
    # Combined
    total_damage: int = 0         # Initial + total DOT
    
    # Breakdown
    skill_contribution: int = 0
    stat_contribution: int = 0
    potency_gear_bonus: int = 0


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
            caster_int=caster.int_stat,
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
    
    # =========================================================================
    # ENFEEBLING MAGIC SIMULATION
    # =========================================================================
    
    def simulate_enfeebling(
        self,
        spell_name: str,
        caster: CasterStats,
        target: MagicTargetStats,
    ) -> EnfeeblingSimulationResult:
        """
        Simulate an enfeebling spell and return potency.
        
        Handles: Slow, Paralyze, Blind, Gravity, Addle, Distract, Frazzle, etc.
        
        Args:
            spell_name: Name of the enfeebling spell
            caster: Caster stats
            target: Target stats
            
        Returns:
            EnfeeblingSimulationResult with potency and duration info
        """
        spell = get_spell(spell_name)
        if spell is None:
            raise ValueError(f"Unknown spell: {spell_name}")
        
        # Get relevant stat based on spell type
        if spell.magic_type == MagicType.ENFEEBLING_MND:
            caster_stat = caster.mnd_stat
            target_stat = target.mnd_stat
        else:  # ENFEEBLING_INT
            caster_stat = caster.int_stat
            target_stat = target.int_stat
        
        skill = caster.enfeebling_magic_skill
        
        # Calculate hit rate
        dstat_bonus = calculate_dstat_bonus(caster_stat, target_stat)
        total_macc = calculate_magic_accuracy(
            skill=skill,
            magic_acc_gear=caster.magic_accuracy,
            dstat_bonus=int(dstat_bonus),
        )
        hit_rate = calculate_magic_hit_rate(total_macc, target.magic_evasion)
        
        # Calculate potency based on spell
        potency_value = 0.0
        potency_unit = ''
        potency_description = ''
        
        spell_lower = spell_name.lower()
        
        if 'slow' in spell_lower:
            is_slow_ii = 'ii' in spell_lower
            potency_value = calculate_slow_potency(
                caster.mnd_stat, target.mnd_stat, is_slow_ii
            )
            # Add enfeebling effect bonus (approximate: each point = +0.1% potency)
            potency_value = potency_value + caster.enfeebling_effect * 10
            potency_unit = 'basis points'
            potency_description = f"{potency_value/100:.1f}% Slow"
            
        elif 'paralyze' in spell_lower or 'para' in spell_lower:
            is_para_ii = 'ii' in spell_lower
            potency_value = calculate_paralyze_potency(
                caster.mnd_stat, target.mnd_stat, is_para_ii
            )
            potency_value = potency_value + caster.enfeebling_effect * 10
            potency_unit = 'basis points'
            potency_description = f"{potency_value/100:.1f}% Paralyze"
            
        elif 'blind' in spell_lower:
            is_blind_ii = 'ii' in spell_lower
            potency_value = calculate_blind_potency(
                caster.int_stat, target.int_stat, is_blind_ii
            )
            potency_value = potency_value + caster.enfeebling_effect
            potency_unit = 'accuracy reduction'
            potency_description = f"-{int(potency_value)} Accuracy"
            
        elif 'gravity' in spell_lower:
            # Gravity is fixed 50% reduction, skill affects duration/landing
            potency_value = 5000
            potency_unit = 'basis points'
            potency_description = "50% Movement Speed"
            
        elif 'addle' in spell_lower:
            # Addle reduces magic attack and accuracy
            is_addle_ii = 'ii' in spell_lower
            base = 20 if is_addle_ii else 10
            skill_bonus = max(0, (skill - 300) // 20)
            potency_value = base + skill_bonus + caster.enfeebling_effect
            potency_unit = 'magic attack/acc down'
            potency_description = f"-{int(potency_value)} M.Atk/M.Acc"
            
        elif 'distract' in spell_lower:
            # Distract reduces evasion
            tier = 3 if 'iii' in spell_lower else (2 if 'ii' in spell_lower else 1)
            base = {1: 25, 2: 45, 3: 65}.get(tier, 25)
            skill_bonus = max(0, (skill - 300) // 15)
            potency_value = base + skill_bonus + caster.enfeebling_effect
            potency_unit = 'evasion down'
            potency_description = f"-{int(potency_value)} Evasion"
            
        elif 'frazzle' in spell_lower:
            # Frazzle reduces magic evasion
            tier = 3 if 'iii' in spell_lower else (2 if 'ii' in spell_lower else 1)
            base = {1: 25, 2: 45, 3: 65}.get(tier, 25)
            skill_bonus = max(0, (skill - 300) // 15)
            potency_value = base + skill_bonus + caster.enfeebling_effect
            potency_unit = 'magic evasion down'
            potency_description = f"-{int(potency_value)} M.Eva"
            
        else:
            # Default for other enfeebles (Sleep, Silence, etc.)
            # These are typically binary (either lands or doesn't)
            potency_value = skill + caster.enfeebling_effect
            potency_unit = 'skill'
            potency_description = f"Skill {int(potency_value)}"
        
        # Calculate duration
        base_duration = spell.properties.get('base_duration', 120.0)
        duration_bonus = caster.enhancing_duration / 10000  # Convert basis points
        # Note: Enfeebling duration is separate stat, but uses same logic
        enhanced_duration = base_duration * (1 + duration_bonus)
        
        return EnfeeblingSimulationResult(
            spell_name=spell.name,
            landed=True,  # Assuming landed for potency calc
            hit_rate=hit_rate,
            potency_value=potency_value,
            potency_unit=potency_unit,
            potency_description=potency_description,
            base_duration=base_duration,
            enhanced_duration=enhanced_duration,
            skill_contribution=skill,
            stat_contribution=int(dstat_bonus),
            gear_bonus=caster.enfeebling_effect,
        )
    
    # =========================================================================
    # HEALING MAGIC SIMULATION
    # =========================================================================
    
    def simulate_healing(
        self,
        spell_name: str,
        caster: CasterStats,
        target_cure_potency_ii: int = 0,
    ) -> HealingSimulationResult:
        """
        Simulate a healing spell and return HP healed.
        
        Args:
            spell_name: Name of the healing spell (Cure, Curaga, etc.)
            caster: Caster stats
            target_cure_potency_ii: Target's Cure Potency II (received bonus)
            
        Returns:
            HealingSimulationResult with healing output
        """
        spell = get_spell(spell_name)
        if spell is None:
            raise ValueError(f"Unknown spell: {spell_name}")
        
        # Determine spell tier from name
        tier = spell.tier
        
        # Check if it's Curaga (AoE)
        is_curaga = 'curaga' in spell_name.lower()
        
        if is_curaga:
            hp_healed = calculate_curaga_amount(
                spell_tier=tier,
                caster_mnd=caster.mnd_stat,
                healing_skill=caster.healing_magic_skill,
                cure_potency=caster.cure_potency,
            )
        else:
            hp_healed = calculate_cure_amount(
                spell_tier=tier,
                caster_mnd=caster.mnd_stat,
                caster_vit=0,  # VIT contribution is minimal
                healing_skill=caster.healing_magic_skill,
                cure_potency=caster.cure_potency,
            )
        
        # Calculate with target's received bonus
        cure_pot_ii_mult = 1.0 + min(target_cure_potency_ii, 3000) / 10000
        hp_with_received = int(hp_healed * cure_pot_ii_mult)
        
        # MP cost and efficiency
        mp_cost = spell.mp_cost
        hp_per_mp = hp_healed / mp_cost if mp_cost > 0 else 0
        
        # Breakdown
        cure_pot_mult = 1.0 + min(caster.cure_potency, 5000) / 10000
        
        return HealingSimulationResult(
            spell_name=spell.name,
            hp_healed=hp_healed,
            hp_healed_with_received=hp_with_received,
            mp_cost=mp_cost,
            hp_per_mp=hp_per_mp,
            base_hp=int(hp_healed / cure_pot_mult),
            cure_potency_mult=cure_pot_mult,
            skill_contribution=caster.healing_magic_skill,
            mnd_contribution=caster.mnd_stat,
        )
    
    # =========================================================================
    # ENHANCING MAGIC SIMULATION
    # =========================================================================
    
    def simulate_enhancing(
        self,
        spell_name: str,
        caster: CasterStats,
        composure_active: bool = False,
        perpetuance_active: bool = False,
        attack_rounds: int = 0,  # For Tier II enspell buildup
    ) -> EnhancingSimulationResult:
        """
        Simulate an enhancing spell and return potency/duration.
        
        Handles: Enspells, Phalanx, Haste, Refresh, Regen, Temper, Gain-stats, etc.
        
        Args:
            spell_name: Name of the enhancing spell
            caster: Caster stats
            composure_active: RDM Composure (+duration, +enspell potency)
            perpetuance_active: SCH Perpetuance (+100% duration)
            attack_rounds: Attack rounds for Tier II enspell buildup
            
        Returns:
            EnhancingSimulationResult with potency and duration info
        """
        spell = get_spell(spell_name)
        if spell is None:
            raise ValueError(f"Unknown spell: {spell_name}")
        
        skill = caster.enhancing_magic_skill
        
        potency_value = 0.0
        potency_unit = ''
        potency_description = ''
        damage_per_hit = 0
        damage_at_cap = 0
        gear_contribution = 0
        
        spell_lower = spell_name.lower()
        
        # Get base duration from spell properties or default
        base_duration = spell.properties.get('base_duration', 180.0)
        
        # Check for enspells
        if spell.properties.get('enspell', False):
            tier = spell.properties.get('enspell_tier', 1)
            
            # Get sword enhancement bonuses from caster
            # Note: These would be stored in CasterStats - need to add
            sword_flat = getattr(caster, 'sword_enhancement_flat', 0)
            sword_pct = getattr(caster, 'sword_enhancement_percent', 0)
            
            damage_per_hit = calculate_enspell_damage(
                enhancing_skill=skill,
                tier=tier,
                attack_rounds=0,  # Initial damage
                sword_enhancement_flat=sword_flat,
                sword_enhancement_percent=sword_pct,
                composure_active=composure_active,
            )
            
            if tier == 2:
                # Calculate damage at cap (after buildup)
                damage_at_cap = calculate_enspell_damage(
                    enhancing_skill=skill,
                    tier=tier,
                    attack_rounds=attack_rounds if attack_rounds > 0 else 21,  # Default to cap
                    sword_enhancement_flat=sword_flat,
                    sword_enhancement_percent=sword_pct,
                    composure_active=composure_active,
                )
            else:
                damage_at_cap = damage_per_hit
            
            potency_value = damage_at_cap
            potency_unit = 'damage'
            potency_description = f"{damage_at_cap} dmg/hit"
            gear_contribution = sword_flat + sword_pct
            base_duration = 180.0  # Enspells typically 3 min base
            
        elif 'phalanx' in spell_lower:
            potency_value = calculate_phalanx_potency(skill)
            potency_unit = 'damage reduction'
            potency_description = f"-{int(potency_value)} dmg/hit"
            base_duration = 180.0
            
        elif 'haste' in spell_lower:
            is_haste_ii = 'ii' in spell_lower
            potency_value = calculate_haste_potency(skill, is_haste_ii)
            potency_unit = 'basis points'
            potency_description = f"{potency_value/100:.1f}% Haste"
            base_duration = 180.0
            
        elif 'refresh' in spell_lower:
            tier = 3 if 'iii' in spell_lower else (2 if 'ii' in spell_lower else 1)
            potency_value = calculate_refresh_potency(skill, tier, composure_active=composure_active)
            potency_unit = 'MP/tick'
            potency_description = f"{int(potency_value)} MP/tick"
            base_duration = 150.0  # 2.5 minutes
            
        elif 'regen' in spell_lower:
            tier = min(5, max(1, spell.tier))
            potency_value = calculate_regen_potency(skill, tier)
            potency_unit = 'HP/tick'
            potency_description = f"{int(potency_value)} HP/tick"
            base_duration = 60.0 + tier * 15  # Scales with tier
            
        elif 'temper' in spell_lower:
            is_temper_ii = 'ii' in spell_lower
            potency_value = calculate_temper_potency(skill, is_temper_ii)
            potency_unit = 'basis points'
            potency_description = f"+{potency_value/100:.1f}% TA"
            base_duration = 180.0
            
        elif 'gain-' in spell_lower:
            potency_value = calculate_gain_potency(skill)
            potency_unit = 'stat bonus'
            stat_name = spell_lower.replace('gain-', '').upper()
            potency_description = f"+{int(potency_value)} {stat_name}"
            base_duration = 300.0  # 5 minutes
            
        else:
            # Default: skill-based potency
            potency_value = skill
            potency_unit = 'skill'
            potency_description = f"Skill {skill}"
        
        # Calculate final duration
        final_duration = calculate_enhancing_duration(
            base_duration=base_duration,
            enhancing_skill=skill,
            duration_gear=caster.enhancing_duration,
            composure_active=composure_active,
            perpetuance_active=perpetuance_active,
        )
        
        return EnhancingSimulationResult(
            spell_name=spell.name,
            potency_value=potency_value,
            potency_unit=potency_unit,
            potency_description=potency_description,
            base_duration=base_duration,
            final_duration=final_duration,
            damage_per_hit=damage_per_hit,
            damage_at_cap=damage_at_cap,
            skill_contribution=skill,
            gear_contribution=gear_contribution,
        )
    
    # =========================================================================
    # DARK MAGIC SIMULATION
    # =========================================================================
    
    def simulate_dark_magic(
        self,
        spell_name: str,
        caster: CasterStats,
        target: MagicTargetStats,
    ) -> DarkMagicSimulationResult:
        """
        Simulate a dark magic spell (Drain, Aspir, Bio).
        
        Args:
            spell_name: Name of the dark spell
            caster: Caster stats
            target: Target stats
            
        Returns:
            DarkMagicSimulationResult with drain amount or DOT info
        """
        spell = get_spell(spell_name)
        if spell is None:
            raise ValueError(f"Unknown spell: {spell_name}")
        
        skill = caster.dark_magic_skill
        
        # Calculate hit rate
        dstat_bonus = calculate_dstat_bonus(caster.int_stat, target.int_stat)
        total_macc = calculate_magic_accuracy(
            skill=skill,
            magic_acc_gear=caster.magic_accuracy,
            dstat_bonus=int(dstat_bonus),
        )
        hit_rate = calculate_magic_hit_rate(total_macc, target.magic_evasion)
        
        spell_lower = spell_name.lower()
        
        amount_drained = 0
        resource_type = ""
        initial_damage = 0
        dot_per_tick = 0
        dot_duration = 0.0
        total_dot = 0
        potency_gear = caster.drain_aspir_potency
        
        if 'drain' in spell_lower:
            # Drain HP
            tier = 3 if 'iii' in spell_lower else (2 if 'ii' in spell_lower else 1)
            min_drain, max_drain = calculate_drain_potency(
                dark_skill=skill,
                drain_tier=tier,
                drain_potency_gear=potency_gear,
            )
            amount_drained = random.randint(min_drain, max_drain)
            resource_type = 'HP'
            
        elif 'aspir' in spell_lower:
            # Aspir MP
            tier = 3 if 'iii' in spell_lower else (2 if 'ii' in spell_lower else 1)
            min_aspir, max_aspir = calculate_aspir_potency(
                dark_skill=skill,  # Approximate
                aspir_tier=tier,
                drain_potency_gear=potency_gear,
            )
            amount_drained = random.randint(min_aspir, max_aspir)
            resource_type = 'MP'
            
        elif 'bio' in spell_lower:
            # Bio: initial damage + DOT
            tier = 3 if 'iii' in spell_lower else (2 if 'ii' in spell_lower else 1)
            
            # Initial damage uses standard nuke formula
            # For simplicity, use base damage calculation
            initial_damage = int(spell.base_v * (1.0 + caster.mab / 100))
            
            # DOT damage
            dot_per_tick = calculate_bio_dot(skill, tier)
            dot_duration = {1: 60, 2: 90, 3: 120}.get(tier, 60)
            num_ticks = int(dot_duration / 3)  # 3-second ticks
            total_dot = dot_per_tick * num_ticks
        
        total_damage = amount_drained + initial_damage + total_dot
        
        return DarkMagicSimulationResult(
            spell_name=spell.name,
            hit_rate=hit_rate,
            amount_drained=amount_drained,
            resource_type=resource_type,
            initial_damage=initial_damage,
            dot_damage_per_tick=dot_per_tick,
            dot_duration=dot_duration,
            total_dot_damage=total_dot,
            total_damage=total_damage,
            skill_contribution=skill,
            stat_contribution=int(dstat_bonus),
            potency_gear_bonus=potency_gear,
        )


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