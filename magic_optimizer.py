#!/usr/bin/env python3
"""
Magic Beam Search Optimizer

Integrates beam search optimization with the magic damage simulation system.
Finds optimal gear sets for magic damage or magic accuracy.

Usage:
    from magic_optimizer import run_magic_optimization, MagicOptimizationType
    
    results = run_magic_optimization(
        inventory=inventory,
        job=Job.BLM,
        spell_name="Thunder VI",
        optimization_type=MagicOptimizationType.DAMAGE,
        magic_burst=True,
    )
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

# Path setup
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# Local imports
from models import (
    Stats, Slot, Job, OptimizationProfile,
    SLOT_BITMASK,
)
from inventory_loader import Inventory
from beam_search_optimizer import (
    BeamSearchOptimizer,
    GearsetCandidate,
    ARMOR_SLOTS,
    WSDIST_SLOTS,
    SLOT_TO_WSDIST,
)



from numba_beam_search_optimizer import NumbaBeamSearchOptimizer


from magic_simulation import (
    MagicSimulator,
    CasterStats,
    MagicTargetStats,
    MagicSimulationResult,
    EnfeeblingSimulationResult,
    HealingSimulationResult,
    EnhancingSimulationResult,
    DarkMagicSimulationResult,
    MAGIC_TARGETS,
)
from spell_database import get_spell, SpellData
from magic_formulas import MagicType, Element
from job_gifts_loader import JobGifts


# =============================================================================
# OPTIMIZATION TYPES
# =============================================================================

class MagicOptimizationType(Enum):
    """Types of magic optimization priorities."""
    DAMAGE = "damage"           # Maximize magic damage output
    ACCURACY = "accuracy"       # Maximize magic accuracy (for landing spells)
    BURST_DAMAGE = "burst"      # Maximize magic burst damage specifically
    POTENCY = "potency"         # Maximize effect potency (skill stacking for enfeebling/dark)


# =============================================================================
# MAGIC OPTIMIZATION PROFILES
# =============================================================================

def create_magic_damage_profile(
    job: Job,
    spell: Optional[SpellData] = None,
    magic_burst: bool = True,
    include_weapons: bool = False,
) -> OptimizationProfile:
    """
    Create an optimization profile for maximum magic damage.
    
    Priorities:
    1. INT (primary stat for most damage spells)
    2. MAB (Magic Attack Bonus)
    3. Magic Damage (flat damage bonus)
    4. MBB (Magic Burst Bonus - capped at 40% from gear)
    5. MBB II (uncapped)
    6. Magic Accuracy (secondary - need to land the spell)
    
    Args:
        job: Player's job
        spell: Optional spell data for element-specific bonuses
        magic_burst: Whether optimizing for magic burst (affects MBB weight)
        include_weapons: Whether to include weapon slots in optimization
    
    Returns:
        OptimizationProfile configured for magic damage
    """
    # Base weights for damage optimization
    weights = {
        # Primary stats - these directly affect damage
        'INT': 8.0,              # Primary stat for elemental/dark magic
        'MND': 2.0,              # Secondary, used for divine/healing
        'magic_attack': 12.0,    # MAB - major damage multiplier
        'magic_damage': 15.0,    # Flat magic damage - very valuable
        
        # Magic Burst Bonus (only valuable if bursting)
        'magic_burst_bonus': 10.0 if magic_burst else 0.0,      # MBB (capped)
        'magic_burst_damage_ii': 12.0 if magic_burst else 0.0,  # MBB II (uncapped)
        
        # Accuracy - need to land the spell
        'magic_accuracy': 4.0,
        
        # Skills - contribute to accuracy
        'elemental_magic_skill': 2.0,
        'dark_magic_skill': 1.5,
        'divine_magic_skill': 1.0,
        
        # NOTE: Fast Cast is NOT included here - it's a separate precast optimization
        # Midcast gear should focus on damage/accuracy, not cast speed
    }
    
    # Adjust weights based on spell type if provided
    if spell:
        if spell.magic_type == MagicType.DIVINE:
            weights['MND'] = 8.0
            weights['INT'] = 2.0
            weights['divine_magic_skill'] = 3.0
        elif spell.magic_type == MagicType.DARK:
            weights['dark_magic_skill'] = 3.0
    
    # Build excluded slots
    exclude_slots = set()
    if not include_weapons:
        exclude_slots = {Slot.MAIN, Slot.SUB}
    
    return OptimizationProfile(
        name=f"Magic Damage ({job.name})",
        weights=weights,
        hard_caps={
            'magic_burst_bonus': 4000,  # 40% MBB cap from gear
        },
        soft_caps={},
        exclude_slots=exclude_slots,
        job=job,
    )


def create_magic_accuracy_profile(
    job: Job,
    spell: Optional[SpellData] = None,
    include_weapons: bool = False,
) -> OptimizationProfile:
    """
    Create an optimization profile for maximum magic accuracy.
    
    Used for enfeebling spells, debuffs, or any spell that must land.
    
    Priorities:
    1. Magic Accuracy AND Magic Skill (both contribute 1:1 to hit rate)
    2. INT/MND (for dSTAT bonus to accuracy)
    3. Some damage stats as tiebreakers
    
    Args:
        job: Player's job
        spell: Optional spell data for skill-specific bonuses
        include_weapons: Whether to include weapon slots
    
    Returns:
        OptimizationProfile configured for magic accuracy
    """
    # Base weights for accuracy optimization
    # NOTE: Magic skill contributes 1:1 to magic accuracy in the formula,
    # so skill should be weighted the same as magic_accuracy
    weights = {
        # Primary - direct magic accuracy AND skill (both 1:1 in formula)
        'magic_accuracy': 15.0,
        
        # Skills - 1:1 with magic accuracy, so weight same as magic_accuracy
        'elemental_magic_skill': 15.0,
        'enfeebling_magic_skill': 15.0,
        'dark_magic_skill': 15.0,
        'divine_magic_skill': 15.0,
        'healing_magic_skill': 15.0,
        'enhancing_magic_skill': 15.0,
        
        # Stats for dSTAT bonus (contributes to accuracy but diminishing returns)
        # At best ~0.5 macc per point of dSTAT, so weight lower
        'INT': 4.0,
        'MND': 4.0,
        
        # Secondary - some damage is nice as tiebreaker
        'magic_attack': 1.0,
        'magic_damage': 1.0,
        
        # NOTE: Fast Cast is NOT included here - it's a separate precast optimization
    }
    
    # Adjust based on spell type - boost the RELEVANT skill even higher
    if spell:
        if spell.magic_type == MagicType.ENFEEBLING_INT:
            weights['INT'] = 6.0  # INT matters more for INT-based enfeebles
            weights['MND'] = 0.0
            weights['enfeebling_magic_skill'] = 18.0  # Prioritize the right skill
            # Zero out irrelevant skills
            weights['elemental_magic_skill'] = 0.0
            weights['dark_magic_skill'] = 0.0
            weights['divine_magic_skill'] = 0.0
            weights['healing_magic_skill'] = 0.0
            weights['enhancing_magic_skill'] = 0.0
        elif spell.magic_type == MagicType.ENFEEBLING_MND:
            weights['MND'] = 6.0
            weights['INT'] = 0.0
            weights['enfeebling_magic_skill'] = 18.0
            weights['elemental_magic_skill'] = 0.0
            weights['dark_magic_skill'] = 0.0
            weights['divine_magic_skill'] = 0.0
            weights['healing_magic_skill'] = 0.0
            weights['enhancing_magic_skill'] = 0.0
        elif spell.magic_type == MagicType.DARK:
            weights['INT'] = 6.0
            weights['MND'] = 0.0
            weights['dark_magic_skill'] = 18.0
            weights['elemental_magic_skill'] = 0.0
            weights['enfeebling_magic_skill'] = 0.0
            weights['divine_magic_skill'] = 0.0
            weights['healing_magic_skill'] = 0.0
            weights['enhancing_magic_skill'] = 0.0
        elif spell.magic_type == MagicType.DIVINE:
            weights['MND'] = 6.0
            weights['INT'] = 0.0
            weights['divine_magic_skill'] = 18.0
            weights['elemental_magic_skill'] = 0.0
            weights['dark_magic_skill'] = 0.0
            weights['enfeebling_magic_skill'] = 0.0
            weights['healing_magic_skill'] = 0.0
            weights['enhancing_magic_skill'] = 0.0
        elif spell.magic_type == MagicType.ELEMENTAL:
            weights['INT'] = 6.0
            weights['MND'] = 0.0
            weights['elemental_magic_skill'] = 18.0
            weights['dark_magic_skill'] = 0.0
            weights['enfeebling_magic_skill'] = 0.0
            weights['divine_magic_skill'] = 0.0
            weights['healing_magic_skill'] = 0.0
            weights['enhancing_magic_skill'] = 0.0
    
    exclude_slots = set()
    if not include_weapons:
        exclude_slots = {Slot.MAIN, Slot.SUB}
    
    return OptimizationProfile(
        name=f"Magic Accuracy ({job.name})",
        weights=weights,
        hard_caps={},
        exclude_slots=exclude_slots,
        job=job,
    )


def create_magic_burst_profile(
    job: Job,
    spell: Optional[SpellData] = None,
    include_weapons: bool = False,
) -> OptimizationProfile:
    """
    Create an optimization profile specifically for magic burst damage.
    
    Similar to damage profile but with higher weight on MBB stats.
    
    Args:
        job: Player's job
        spell: Optional spell data
        include_weapons: Whether to include weapon slots
    
    Returns:
        OptimizationProfile configured for magic burst
    """
    weights = {
        # MBB stats are king for bursting
        'magic_burst_bonus': 15.0,       # MBB (capped at 40%)
        'magic_burst_damage_ii': 18.0,   # MBB II (uncapped) - prioritize this
        
        # Standard damage stats
        'INT': 6.0,
        'MND': 1.5,
        'magic_attack': 10.0,
        'magic_damage': 12.0,
        
        # Accuracy matters for burst - resisted burst is wasted
        'magic_accuracy': 5.0,
        'elemental_magic_skill': 2.5,
        
        # NOTE: Fast Cast is NOT included here - it's a separate precast optimization
    }
    
    if spell and spell.magic_type == MagicType.DIVINE:
        weights['MND'] = 6.0
        weights['INT'] = 1.5
        weights['divine_magic_skill'] = 3.0
    
    exclude_slots = set()
    if not include_weapons:
        exclude_slots = {Slot.MAIN, Slot.SUB}
    
    return OptimizationProfile(
        name=f"Magic Burst ({job.name})",
        weights=weights,
        hard_caps={
            'magic_burst_bonus': 4000,
        },
        exclude_slots=exclude_slots,
        job=job,
    )


def create_magic_potency_profile(
    job: Job,
    spell: Optional[SpellData] = None,
    include_weapons: bool = False,
) -> OptimizationProfile:
    """
    Create an optimization profile for maximum spell potency/effect.
    
    Used for spells where effect strength scales with skill or stats:
    - Enfeebling: Slow %, Paralyze %, Blind accuracy reduction, etc.
    - Dark (Drain/Aspir): Amount drained scales with Dark Magic Skill
    - Dark (Bio): DOT damage scales with skill
    - Dark (Absorb): SPECIAL - Potency NOT affected by Dark Magic Skill!
                     Per BG-Wiki: "Dark Magic does nothing for the potency 
                     of Absorb spells, but does affect accuracy and duration."
                     Potency is based on job level + equipment bonuses
                     (Liberator, Pavor Gauntlets, Erra Pendant, etc.)
    - Divine: Repose duration, etc.
    
    Priorities vary by spell type:
    - Enfeebling (MND-based): Enfeebling Skill > MND > Enfeebling Effect > M.Acc
    - Enfeebling (INT-based): Enfeebling Skill > INT > Enfeebling Effect > M.Acc
    - Dark (Drain/Aspir): Dark Magic Skill > INT > M.Acc
    - Dark (Bio): Dark Magic Skill > MAB > INT > M.Acc  
    - Dark (Absorb): Absorb Potency gear > Duration gear > Dark Skill (duration) > M.Acc
    - Divine: Divine Magic Skill > MND > M.Acc
    
    Args:
        job: Player's job
        spell: Spell data for type-specific optimization
        include_weapons: Whether to include weapon slots
    
    Returns:
        OptimizationProfile configured for potency
    """
    # Default weights - skill is KING for potency
    # Zero out irrelevant skills by default, set the right one based on spell type
    weights = {
        # Skills are PRIMARY for potency - weight very high
        'enfeebling_magic_skill': 0.0,  # Set based on spell type
        'dark_magic_skill': 0.0,
        'divine_magic_skill': 0.0,
        'healing_magic_skill': 0.0,
        'enhancing_magic_skill': 0.0,
        'elemental_magic_skill': 0.0,
        
        # Stats contribute to potency formulas (secondary)
        'INT': 6.0,
        'MND': 6.0,
        
        # Enfeebling-specific bonuses
        'enfeebling_effect': 20.0,       # "Enfeebling magic effect +"
        'enfeebling_duration': 12.0,     # Duration helps maintain debuffs
        
        # Accuracy is SECONDARY for potency - spell must land but skill matters more
        'magic_accuracy': 6.0,
        
        # Some damage for spells like Bio that do both
        'magic_attack': 2.0,
        'magic_damage': 2.0,
        
        # NOTE: Fast Cast is NOT included here - it's a separate precast optimization
        
        # Potency-specific stats
        'cure_potency': 25.0,
        'drain_aspir_potency': 18.0,
    }
    
    # Adjust weights based on spell type - set the RELEVANT skill very high
    if spell:
        if spell.magic_type == MagicType.ENFEEBLING_MND:
            # MND-based enfeebling: Slow, Paralyze, Addle, Distract, Frazzle
            weights['enfeebling_magic_skill'] = 35.0  # Skill is KING for potency
            weights['MND'] = 8.0
            weights['INT'] = 2.0
            weights['magic_accuracy'] = 6.0  # Still need to land, but secondary
            weights['enfeebling_effect'] = 20.0
            # Filler weights to prevent beam collapse (keeps candidates alive)
            weights['fast_cast'] = 0.05
            weights['damage_taken'] = -1.0
            weights['physical_dt'] = -1.0
            weights['magical_dt'] = -1.0
            # Zero out irrelevant weights
            weights['cure_potency'] = 0.0
            weights['drain_aspir_potency'] = 0.0
            weights['magic_attack'] = 0.0
            weights['magic_damage'] = 0.0
            weights['enhancing_duration'] = 0.0
            
        elif spell.magic_type == MagicType.ENFEEBLING_INT:
            # INT-based enfeebling: Blind, Gravity, Sleep, Dispel, Break
            weights['enfeebling_magic_skill'] = 35.0  # Skill is KING for potency
            weights['INT'] = 8.0
            weights['MND'] = 2.0
            weights['magic_accuracy'] = 6.0  # Still need to land, but secondary
            weights['enfeebling_effect'] = 20.0
            # Filler weights to prevent beam collapse (keeps candidates alive)
            weights['fast_cast'] = 0.05
            weights['damage_taken'] = -1.0
            weights['physical_dt'] = -1.0
            weights['magical_dt'] = -1.0
            # Zero out irrelevant weights
            weights['cure_potency'] = 0.0
            weights['drain_aspir_potency'] = 0.0
            weights['magic_attack'] = 0.0
            weights['magic_damage'] = 0.0
            weights['enhancing_duration'] = 0.0
            
        elif spell.magic_type == MagicType.DARK:
            # Dark magic has different subtypes with different mechanics:
            # - Absorb-STAT: Potency NOT affected by Dark Magic Skill (per BG-Wiki)
            #                Potency is based on job level + equipment bonuses
            #                Accuracy and Duration ARE affected by Dark Magic Skill
            # - Drain/Aspir: Potency IS affected by Dark Magic Skill
            # - Bio: Initial damage uses MAB, DOT potency uses skill
            
            if spell.name.startswith('Absorb'):
                # ABSORB SPELLS - Special handling per BG-Wiki:
                # "Dark Magic does nothing for the potency of Absorb spells,
                #  but does affect accuracy and duration."
                # Potency comes from: Job level (fixed) + Equipment bonuses
                # Equipment: Liberator, Pavor Gauntlets, Erra Pendant, etc.
                
                # Absorb-specific potency stats (equipment bonuses)
                weights['absorb_potency'] = 35.0           # "Absorb" effect potency +%
                weights['absorb_effect_duration'] = 18.0   # "Absorb" effect duration +%
                
                # Dark Magic Skill affects DURATION (not potency), so moderate weight
                # Formula: Duration = (180 + floor((Skill - 490.5)/10)*2) * modifiers
                weights['dark_magic_skill'] = 12.0         # For duration scaling
                weights['dark_magic_duration'] = 15.0      # Dark magic duration +%
                
                # Accuracy stats - Dark Magic Skill contributes to landing the spell
                weights['magic_accuracy'] = 8.0
                weights['INT'] = 4.0  # Minor accuracy contribution
                
                weights['MND'] = 0.0
                weights['enfeebling_effect'] = 0.0
                
                # Filler weights to prevent beam collapse
                weights['fast_cast'] = 0.05
                weights['damage_taken'] = -1.0
                weights['physical_dt'] = -1.0
                weights['magical_dt'] = -1.0
                
                # Zero out irrelevant weights
                weights['cure_potency'] = 0.0
                weights['drain_aspir_potency'] = 0.0
                weights['enhancing_duration'] = 0.0
                weights['enfeebling_duration'] = 0.0
                weights['magic_attack'] = 0.0
                weights['magic_damage'] = 0.0
                
            elif spell.name.startswith('Bio'):
                # BIO SPELLS - Initial hit uses MAB, DOT potency uses skill
                weights['dark_magic_skill'] = 25.0
                weights['magic_attack'] = 10.0
                weights['magic_damage'] = 10.0
                weights['INT'] = 8.0
                weights['MND'] = 0.0
                weights['magic_accuracy'] = 6.0
                weights['enfeebling_effect'] = 0.0
                
                # Filler weights
                weights['fast_cast'] = 0.05
                weights['damage_taken'] = -1.0
                weights['physical_dt'] = -1.0
                weights['magical_dt'] = -1.0
                
                # Zero out irrelevant
                weights['cure_potency'] = 0.0
                weights['drain_aspir_potency'] = 0.0
                weights['enhancing_duration'] = 0.0
                weights['enfeebling_duration'] = 0.0
                
            else:
                # DRAIN/ASPIR SPELLS - Potency IS affected by Dark Magic Skill
                weights['dark_magic_skill'] = 35.0
                weights['drain_aspir_potency'] = 18.0      # Drain/Aspir potency +%
                weights['INT'] = 8.0
                weights['MND'] = 0.0
                weights['magic_accuracy'] = 6.0
                weights['enfeebling_effect'] = 0.0
                
                # Filler weights
                weights['fast_cast'] = 0.05
                weights['damage_taken'] = -1.0
                weights['physical_dt'] = -1.0
                weights['magical_dt'] = -1.0
                
                # Zero out irrelevant
                weights['cure_potency'] = 0.0
                weights['enhancing_duration'] = 0.0
                weights['enfeebling_duration'] = 0.0
                weights['magic_attack'] = 0.0
                weights['magic_damage'] = 0.0
                
        elif spell.magic_type == MagicType.DIVINE:
            # Divine magic: skill affects potency
            weights['divine_magic_skill'] = 35.0
            weights['MND'] = 8.0
            weights['INT'] = 0.0
            weights['magic_accuracy'] = 6.0
            weights['enfeebling_effect'] = 0.0
            # Filler weights to prevent beam collapse (keeps candidates alive)
            weights['fast_cast'] = 0.05
            weights['damage_taken'] = -1.0
            weights['physical_dt'] = -1.0
            weights['magical_dt'] = -1.0
            # Zero out irrelevant weights
            weights['cure_potency'] = 0.0
            weights['drain_aspir_potency'] = 0.0
            weights['enhancing_duration'] = 0.0
            weights['enfeebling_duration'] = 0.0
            weights['magic_attack'] = 0.0
            weights['magic_damage'] = 0.0
            
        elif spell.magic_type == MagicType.HEALING:
            # Healing: Cure potency scales with MND and skill
            weights['healing_magic_skill'] = 30.0
            weights['MND'] = 12.0
            weights['cure_potency'] = 25.0
            weights['magic_accuracy'] = 0.0  # Cures don't miss
            weights['INT'] = 0.0
            weights['enfeebling_effect'] = 0.0
            # Filler weights to prevent beam collapse (keeps candidates alive)
            weights['fast_cast'] = 0.05
            weights['damage_taken'] = -1.0
            weights['physical_dt'] = -1.0
            weights['magical_dt'] = -1.0
            # Zero out irrelevant weights
            weights['drain_aspir_potency'] = 0.0
            weights['enhancing_duration'] = 0.0
            weights['enfeebling_duration'] = 0.0
            weights['magic_attack'] = 0.0
            weights['magic_damage'] = 0.0
            
        elif spell.magic_type == MagicType.ENHANCING:
            # Enhancing: duration and potency from skill
            # Primary stats - maximize these
            weights['enhancing_magic_skill'] = 30.0  # 5 skill = 150 points
            weights['enhancing_duration'] = 22.0
            
            # Filler weights to prevent beam collapse (keeps candidates alive)
            weights['fast_cast'] = 0.05
            weights['damage_taken'] = -1.0
            weights['physical_dt'] = -1.0
            weights['magical_dt'] = -1.0
            
            # Zero out irrelevant weights
            weights['MND'] = 0.0
            weights['magic_accuracy'] = 0.0  # Enhancing on self doesn't miss
            weights['INT'] = 0.0
            weights['enfeebling_effect'] = 0.0
            weights['cure_potency'] = 0.0
            weights['drain_aspir_potency'] = 0.0
            weights['enfeebling_duration'] = 0.0
            weights['magic_attack'] = 0.0
            weights['magic_damage'] = 0.0
            
            # Enspell-specific: Check if this is an Enspell and add sword enhancement weights
            if spell.properties.get('enspell', False):
                # Enspells benefit from sword enhancement damage bonuses
                weights['sword_enhancement_flat'] = 25.0    # Flat damage per hit
                weights['sword_enhancement_percent'] = 20.0  # Percentage boost (basis points)
    
    exclude_slots = set()
    if not include_weapons:
        exclude_slots = {Slot.MAIN, Slot.SUB}
    
    return OptimizationProfile(
        name=f"Magic Potency ({job.name})",
        weights=weights,
        hard_caps={
            'cure_potency': 5000,  # 50% cap
            'fast_cast': 5000,     # 80% cap (only relevant for enhancing)
        },
        exclude_slots=exclude_slots,
        job=job,
    )


# =============================================================================
# JOB GIFT MAGIC BONUSES
# =============================================================================

@dataclass
class JobGiftMagicBonuses:
    """
    Additional magic stat bonuses from job gifts.
    
    These stats aren't part of JobMagicPreset but need to be applied
    when creating the base character for simulation.
    """
    magic_accuracy: int = 0
    magic_attack: int = 0
    magic_damage: int = 0
    fast_cast: int = 0  # basis points (100 = 1%)
    mbb_trait_bonus: int = 0  # basis points added to job's innate MBB trait
    
    # Skill bonuses (added to base job skills)
    elemental_skill_bonus: int = 0
    dark_skill_bonus: int = 0
    enfeebling_skill_bonus: int = 0
    divine_skill_bonus: int = 0
    healing_skill_bonus: int = 0
    enhancing_skill_bonus: int = 0


# =============================================================================
# GEAR TO CASTER STATS CONVERSION
# =============================================================================

def gear_to_caster_stats(
    gear_stats: Stats,
    job_preset: 'JobMagicPreset',
    sub_magic_accuracy_skill: int = 0,
    job_gift_bonuses: Optional[JobGiftMagicBonuses] = None,
) -> CasterStats:
    """
    Convert accumulated gear stats to CasterStats for simulation.
    
    Args:
        gear_stats: Summed stats from gear
        job_preset: Job's base magic stats (may already have job gift skills applied)
        sub_magic_accuracy_skill: Magic Accuracy Skill from offhand weapon (will be subtracted)
                                  Per nuking.py: offhand's "Magic Accuracy Skill" does NOT 
                                  contribute to spell accuracy
        job_gift_bonuses: Additional magic stat bonuses from job gifts
    
    Returns:
        CasterStats ready for simulation
    """
    # Get job gift bonuses or use empty defaults
    gifts = job_gift_bonuses or JobGiftMagicBonuses()
    
    # Calculate effective magic accuracy skill by subtracting offhand contribution
    # This matches the approach in nuking.py lines 31-32:
    #   magic_accuracy_skill = gearset.playerstats["Magic Accuracy Skill"]
    #   magic_accuracy_skill -= gearset.gear["sub"].get("Magic Accuracy Skill",0)
    effective_magic_acc_skill = gear_stats.magic_accuracy_skill - sub_magic_accuracy_skill
    
    # Total magic accuracy = job gifts + gear magic accuracy + effective magic accuracy skill
    total_magic_accuracy = gifts.magic_accuracy + gear_stats.magic_accuracy + effective_magic_acc_skill
    
    return CasterStats(
        # Primary stats = base + gear
        int_stat=job_preset.base_int + gear_stats.INT,
        mnd_stat=job_preset.base_mnd + gear_stats.MND,
        
        # Magic offense from job gifts + gear (includes effective magic accuracy skill)
        mab=gifts.magic_attack + gear_stats.magic_attack,
        magic_damage=gifts.magic_damage + gear_stats.magic_damage,
        magic_accuracy=total_magic_accuracy,
        
        # Skills = base (already includes job gift bonuses) + gear bonus
        elemental_magic_skill=job_preset.elemental_skill + gear_stats.elemental_magic_skill,
        dark_magic_skill=job_preset.dark_skill + gear_stats.dark_magic_skill,
        enfeebling_magic_skill=job_preset.enfeebling_skill + gear_stats.enfeebling_magic_skill,
        divine_magic_skill=job_preset.divine_skill + gear_stats.divine_magic_skill,
        healing_magic_skill=job_preset.healing_skill + gear_stats.healing_magic_skill,
        enhancing_magic_skill=job_preset.enhancing_skill + gear_stats.enhancing_magic_skill,
        
        # Magic Burst Bonus from gear (in basis points)
        mbb_gear=gear_stats.magic_burst_bonus,
        mbb_ii_gear=gear_stats.magic_burst_damage_ii,
        # MBB trait from job preset (already includes job gift bonus)
        mbb_trait=job_preset.mbb_trait,
        
        # Fast cast from job gifts + gear
        fast_cast=gifts.fast_cast + gear_stats.fast_cast,
        
        # Potency-specific stats from gear
        drain_aspir_potency=gear_stats.drain_aspir_potency,
        cure_potency=gear_stats.cure_potency,
        enfeebling_effect=gear_stats.enfeebling_effect,
        enhancing_duration=gear_stats.enhancing_duration,
        
        # Enspell damage bonuses
        sword_enhancement_flat=gear_stats.sword_enhancement_flat,
        sword_enhancement_percent=gear_stats.sword_enhancement_percent,
    )


@dataclass
class JobMagicPreset:
    """Preset base stats for a job's magic capabilities."""
    base_int: int
    base_mnd: int
    elemental_skill: int
    dark_skill: int
    enfeebling_skill: int
    divine_skill: int
    healing_skill: int = 0      # Added for Healing magic potency calculations
    enhancing_skill: int = 0    # Added for Enhancing magic potency calculations
    mbb_trait: int = 0          # basis points


# Job presets (same as magic_ui.py)
JOB_MAGIC_PRESETS = {
    Job.BLM: JobMagicPreset(
        base_int=165, base_mnd=120,
        elemental_skill=500, dark_skill=424, enfeebling_skill=424, divine_skill=0,
        healing_skill=0, enhancing_skill=305,
        mbb_trait=1600,
    ),
    Job.RDM: JobMagicPreset(
        base_int=145, base_mnd=145,
        elemental_skill=424, dark_skill=373, enfeebling_skill=500, divine_skill=0,
        healing_skill=404, enhancing_skill=500,
        mbb_trait=0,
    ),
    Job.WHM: JobMagicPreset(
        base_int=125, base_mnd=165,
        elemental_skill=0, dark_skill=0, enfeebling_skill=404, divine_skill=500,
        healing_skill=500, enhancing_skill=500,
        mbb_trait=0,
    ),
    Job.SCH: JobMagicPreset(
        base_int=155, base_mnd=145,
        elemental_skill=449, dark_skill=404, enfeebling_skill=449, divine_skill=0,
        healing_skill=449, enhancing_skill=449,
        mbb_trait=800,
    ),
    Job.GEO: JobMagicPreset(
        base_int=150, base_mnd=140,
        elemental_skill=424, dark_skill=354, enfeebling_skill=424, divine_skill=0,
        mbb_trait=0,
    ),
    Job.DRK: JobMagicPreset(
        base_int=135, base_mnd=120,
        elemental_skill=354, dark_skill=424, enfeebling_skill=354, divine_skill=0,
        mbb_trait=0,
    ),
    Job.NIN: JobMagicPreset(
        base_int=130, base_mnd=115,
        elemental_skill=354, dark_skill=0, enfeebling_skill=354, divine_skill=0,
        mbb_trait=0,
    ),
    Job.BLU: JobMagicPreset(
        base_int=140, base_mnd=130,
        elemental_skill=386, dark_skill=386, enfeebling_skill=386, divine_skill=0,
        mbb_trait=0,
    ),
    Job.SMN: JobMagicPreset(
        base_int=140, base_mnd=150,
        elemental_skill=0, dark_skill=0, enfeebling_skill=0, divine_skill=0,
        mbb_trait=0,
    ),
    Job.PLD: JobMagicPreset(
        base_int=115, base_mnd=145,
        elemental_skill=0, dark_skill=0, enfeebling_skill=0, divine_skill=424,
        mbb_trait=0,
    ),
    Job.RUN: JobMagicPreset(
        base_int=130, base_mnd=125,
        elemental_skill=373, dark_skill=0, enfeebling_skill=373, divine_skill=373,
        mbb_trait=0,
    ),
}

DEFAULT_MAGIC_PRESET = JobMagicPreset(
    base_int=130, base_mnd=130,
    elemental_skill=354, dark_skill=354, enfeebling_skill=354, divine_skill=354,
    mbb_trait=0,
)


def get_job_preset(job: Job) -> JobMagicPreset:
    """Get the magic preset for a job."""
    return JOB_MAGIC_PRESETS.get(job, DEFAULT_MAGIC_PRESET)


def apply_job_gifts_to_magic(
    job_preset: JobMagicPreset,
    job_gifts: Optional[JobGifts],
) -> Tuple[JobMagicPreset, JobGiftMagicBonuses]:
    """
    Apply job gifts to create a modified magic preset and additional bonuses.
    
    This creates a base "character" with job gifts applied, similar to how
    WS/TP optimization handles job gifts.
    
    Args:
        job_preset: Base job magic preset
        job_gifts: Job gifts data (or None if not loaded)
    
    Returns:
        Tuple of (modified_preset, additional_bonuses)
    """
    if job_gifts is None:
        return job_preset, JobGiftMagicBonuses()
    
    stats = job_gifts.get_wsdist_stats()
    
    # Create modified preset with skill bonuses applied
    modified_preset = JobMagicPreset(
        base_int=job_preset.base_int,
        base_mnd=job_preset.base_mnd,
        elemental_skill=job_preset.elemental_skill + int(stats.get('Elemental Magic Skill', 0)),
        dark_skill=job_preset.dark_skill + int(stats.get('Dark Magic Skill', 0)),
        enfeebling_skill=job_preset.enfeebling_skill + int(stats.get('Enfeebling Magic Skill', 0)),
        divine_skill=job_preset.divine_skill + int(stats.get('Divine Magic Skill', 0)),
        healing_skill=job_preset.healing_skill + int(stats.get('Healing Magic Skill', 0)),
        enhancing_skill=job_preset.enhancing_skill + int(stats.get('Enhancing Magic Skill', 0)),
        # MBB trait from job gifts is added to the job's innate MBB trait
        # Note: job_gifts stores this in basis points (e.g., 1600 = 16%)
        mbb_trait=job_preset.mbb_trait + int(stats.get('Magic Burst Damage Trait', 0)),
    )
    
    # Create additional bonuses for stats not in JobMagicPreset
    bonuses = JobGiftMagicBonuses(
        magic_accuracy=int(stats.get('Magic Accuracy', 0)),
        magic_attack=int(stats.get('Magic Attack', 0)),
        magic_damage=int(stats.get('Magic Damage', 0)),
        # Fast Cast from job gifts is already in basis points
        fast_cast=int(stats.get('Fast Cast', 0)),
    )
    
    return modified_preset, bonuses


# =============================================================================
# SIMULATION-BASED EVALUATION
# =============================================================================

def evaluate_magic_damage(
    candidate: GearsetCandidate,
    spell: SpellData,
    job_preset: JobMagicPreset,
    target: MagicTargetStats,
    magic_burst: bool = True,
    skillchain_steps: int = 2,
    num_casts: int = 100,
    job_gift_bonuses: Optional[JobGiftMagicBonuses] = None,
    buff_bonuses: Optional[Dict[str, int]] = None,
) -> float:
    """
    Evaluate a gear set candidate using actual magic simulation.
    
    Args:
        candidate: Gear set candidate from beam search
        spell: Spell to simulate
        job_preset: Job's base magic stats (with job gift skills applied)
        target: Target stats
        magic_burst: Whether to simulate magic burst
        skillchain_steps: Number of skillchain steps (for MB)
        num_casts: Number of simulation iterations
        job_gift_bonuses: Additional magic stat bonuses from job gifts
        buff_bonuses: Additional stat bonuses from buffs (GEO, COR, food, etc.)
    
    Returns:
        Average damage from simulation
    """
    # Convert candidate stats to CasterStats, subtracting offhand magic accuracy skill
    caster = gear_to_caster_stats(
        candidate.stats, 
        job_preset,
        sub_magic_accuracy_skill=candidate.sub_magic_accuracy_skill,
        job_gift_bonuses=job_gift_bonuses,
    )
    
    # Apply buff bonuses if provided
    if buff_bonuses:
        caster.int_stat += buff_bonuses.get("INT", 0)
        caster.mnd_stat += buff_bonuses.get("MND", 0)
        caster.mab += buff_bonuses.get("magic_attack", 0)
        caster.magic_accuracy += buff_bonuses.get("magic_accuracy", 0)
    
    # Run simulation
    sim = MagicSimulator(seed=42)
    result = sim.simulate_spell(
        spell_name=spell.name,
        caster=caster,
        target=target,
        magic_burst=magic_burst,
        skillchain_steps=skillchain_steps,
        num_casts=num_casts,
    )
    
    return result.average_damage


def evaluate_magic_accuracy(
    candidate: GearsetCandidate,
    spell: SpellData,
    job_preset: JobMagicPreset,
    target: MagicTargetStats,
    job_gift_bonuses: Optional[JobGiftMagicBonuses] = None,
    buff_bonuses: Optional[Dict[str, int]] = None,
) -> float:
    """
    Evaluate a gear set candidate for magic accuracy.
    
    Returns the calculated hit rate (0.0 to 1.0).
    
    Args:
        candidate: Gear set candidate
        spell: Spell to evaluate for
        job_preset: Job's base magic stats (with job gift skills applied)
        target: Target stats
        job_gift_bonuses: Additional magic stat bonuses from job gifts
        buff_bonuses: Additional stat bonuses from buffs (GEO, COR, food, etc.)
    
    Returns:
        Hit rate as decimal
    """
    from magic_formulas import (
        calculate_dstat_bonus, calculate_magic_accuracy, calculate_magic_hit_rate
    )
    
    # Convert candidate stats to CasterStats, subtracting offhand magic accuracy skill
    caster = gear_to_caster_stats(
        candidate.stats, 
        job_preset,
        sub_magic_accuracy_skill=candidate.sub_magic_accuracy_skill,
        job_gift_bonuses=job_gift_bonuses,
    )
    
    # Apply buff bonuses if provided
    if buff_bonuses:
        caster.int_stat += buff_bonuses.get("INT", 0)
        caster.mnd_stat += buff_bonuses.get("MND", 0)
        caster.mab += buff_bonuses.get("magic_attack", 0)
        caster.magic_accuracy += buff_bonuses.get("magic_accuracy", 0)
    
    # Get relevant stat and skill based on spell type
    if spell.magic_type in [MagicType.DIVINE, MagicType.ENFEEBLING_MND, MagicType.HEALING]:
        caster_stat = caster.mnd_stat
        target_stat = target.mnd_stat
    else:
        caster_stat = caster.int_stat
        target_stat = target.int_stat
    
    skill = caster.get_skill_for_type(spell.magic_type)
    
    # Calculate dSTAT bonus
    dstat_bonus = calculate_dstat_bonus(caster_stat, target_stat)
    
    # Calculate total magic accuracy
    total_macc = calculate_magic_accuracy(
        skill=skill,
        magic_acc_gear=caster.magic_accuracy,
        dstat_bonus=int(dstat_bonus),
        magic_burst=False,  # Don't assume MB bonus for accuracy evaluation
    )
    
    # Calculate hit rate
    hit_rate = calculate_magic_hit_rate(total_macc, target.magic_evasion)
    
    # Debug output for first few evaluations
    if not hasattr(evaluate_magic_accuracy, '_debug_count'):
        evaluate_magic_accuracy._debug_count = 0
    evaluate_magic_accuracy._debug_count += 1
    
    if evaluate_magic_accuracy._debug_count <= 3:
        print(f"\n  [DEBUG] evaluate_magic_accuracy #{evaluate_magic_accuracy._debug_count}:")
        print(f"    Spell: {spell.name} (type: {spell.magic_type})")
        print(f"    Job preset enfeebling_skill: {job_preset.enfeebling_skill}")
        print(f"    Gear enfeebling_magic_skill: {candidate.stats.enfeebling_magic_skill}")
        print(f"    Caster skill (from get_skill_for_type): {skill}")
        print(f"    Caster magic_accuracy (incl skill+gear+gifts): {caster.magic_accuracy}")
        print(f"    Caster stat (INT/MND): {caster_stat}, Target stat: {target_stat}")
        print(f"    dstat_bonus: {dstat_bonus}")
        print(f"    total_macc = skill({skill}) + magic_acc_gear({caster.magic_accuracy}) + dstat({int(dstat_bonus)}) = {total_macc}")
        print(f"    TARGET magic_evasion: {target.magic_evasion}")
        print(f"    dMAcc = {total_macc} - {target.magic_evasion} = {total_macc - target.magic_evasion}")
        
        # Manual hit rate calculation check
        dmacc = total_macc - target.magic_evasion
        if dmacc < 0:
            manual_hit = 0.50 + (dmacc // 2) / 100
        else:
            manual_hit = 0.50 + dmacc / 100
        manual_hit = max(0.05, min(0.95, manual_hit))
        print(f"    Manual hit rate calc: {manual_hit:.4f} ({manual_hit*100:.1f}%)")
        print(f"    Function hit_rate: {hit_rate:.4f} ({hit_rate*100:.1f}%)")
        
        if abs(hit_rate - manual_hit) > 0.001:
            print(f"    *** MISMATCH DETECTED! ***")
    
    return hit_rate


def evaluate_magic_potency(
    candidate: GearsetCandidate,
    spell: SpellData,
    job_preset: 'JobMagicPreset',
    target: MagicTargetStats,
    job_gift_bonuses: Optional[JobGiftMagicBonuses] = None,
    buff_bonuses: Optional[Dict[str, int]] = None,
) -> float:
    """
    Evaluate a gear set for potency optimization using actual simulation.
    
    This function now calls the actual simulation methods instead of
    weighted scoring, providing accurate potency values.
    
    Args:
        candidate: Gear set candidate
        spell: Spell to evaluate for
        job_preset: Job's base magic stats (with job gift skills applied)
        target: Target stats
        job_gift_bonuses: Additional magic stat bonuses from job gifts
        buff_bonuses: Additional stat bonuses from buffs (GEO, COR, food, etc.)
    
    Returns:
        Potency score (higher is better) - actual potency value from simulation
    """
    from magic_formulas import (
        calculate_dstat_bonus, calculate_magic_accuracy, calculate_magic_hit_rate
    )
    
    # Convert candidate stats to CasterStats, subtracting offhand magic accuracy skill
    caster = gear_to_caster_stats(
        candidate.stats, 
        job_preset,
        sub_magic_accuracy_skill=candidate.sub_magic_accuracy_skill,
        job_gift_bonuses=job_gift_bonuses,
    )
    
    # Apply buff bonuses if provided
    if buff_bonuses:
        caster.int_stat += buff_bonuses.get("INT", 0)
        caster.mnd_stat += buff_bonuses.get("MND", 0)
        caster.mab += buff_bonuses.get("magic_attack", 0)
        caster.magic_accuracy += buff_bonuses.get("magic_accuracy", 0)
    
    # Create simulator
    sim = MagicSimulator(seed=42)
    
    # Calculate base hit rate for accuracy factor
    if spell.magic_type in [MagicType.DIVINE, MagicType.ENFEEBLING_MND, MagicType.HEALING]:
        caster_stat = caster.mnd_stat
        target_stat = target.mnd_stat
    else:
        caster_stat = caster.int_stat
        target_stat = target.int_stat
    
    skill = caster.get_skill_for_type(spell.magic_type)
    dstat_bonus = calculate_dstat_bonus(caster_stat, target_stat)
    total_macc = calculate_magic_accuracy(
        skill=skill,
        magic_acc_gear=caster.magic_accuracy,
        dstat_bonus=int(dstat_bonus),
        magic_burst=False,
    )
    hit_rate = calculate_magic_hit_rate(total_macc, target.magic_evasion)
    
    # Route to appropriate simulation based on spell type
    potency_score = 0.0
    sim_result = None
    
    if spell.magic_type in [MagicType.ENFEEBLING_INT, MagicType.ENFEEBLING_MND]:
        # Enfeebling simulation
        result = sim.simulate_enfeebling(spell.name, caster, target)
        sim_result = result
        # Score is the potency value - higher potency = better
        potency_score = result.potency_value
        # For percentage-based enfeebles (Slow, Para), the value is in basis points
        # For accuracy-based (Blind), value is flat reduction
        # Normalize to make them comparable
        if result.potency_unit == 'basis points':
            potency_score = result.potency_value  # Already good scale
        elif result.potency_unit == 'accuracy reduction':
            potency_score = result.potency_value * 50  # Scale up flat values
        else:
            potency_score = result.potency_value * 10  # Default scaling
            
    elif spell.magic_type == MagicType.HEALING:
        # Healing simulation
        result = sim.simulate_healing(spell.name, caster)
        sim_result = result
        # Score is HP healed
        potency_score = result.hp_healed
        
    elif spell.magic_type == MagicType.ENHANCING:
        # Enhancing simulation
        result = sim.simulate_enhancing(spell.name, caster)
        sim_result = result
        # Score depends on spell type
        if spell.properties.get('enspell', False):
            # Enspells: damage per hit * expected duration contribution
            # Higher damage + longer duration = better
            potency_score = result.damage_at_cap * 100 + result.final_duration
        else:
            # Other enhancing: potency value + duration bonus
            potency_score = result.potency_value + result.final_duration * 0.5
            
    elif spell.magic_type == MagicType.DARK:
        # Dark magic simulation
        result = sim.simulate_dark_magic(spell.name, caster, target)
        sim_result = result
        # Score is total damage/drain amount
        potency_score = result.total_damage
        
    elif spell.magic_type == MagicType.DIVINE:
        # Divine magic - use standard damage simulation for now
        result = sim.simulate_spell(spell.name, caster, target, num_casts=10)
        potency_score = result.average_damage
        
    else:
        # Default: standard damage simulation
        result = sim.simulate_spell(spell.name, caster, target, num_casts=10)
        potency_score = result.average_damage
    
    # Apply hit rate factor for spells that need to land
    # Healing and self-enhancing don't need this
    if spell.magic_type not in [MagicType.HEALING, MagicType.ENHANCING]:
        # Softer penalty to not zero out good potency sets
        acc_factor = 0.5 + (hit_rate * 0.5)  # Range: 0.525 to 0.975
        potency_score = potency_score * acc_factor
    
    # Debug output for first few evaluations
    if hasattr(evaluate_magic_potency, '_debug_count'):
        evaluate_magic_potency._debug_count += 1
    else:
        evaluate_magic_potency._debug_count = 1
    
    if evaluate_magic_potency._debug_count <= 3:
        print(f"\n  [DEBUG] evaluate_magic_potency #{evaluate_magic_potency._debug_count}:")
        print(f"    Spell: {spell.name} (type: {spell.magic_type})")
        
        if sim_result is not None:
            if isinstance(sim_result, EnfeeblingSimulationResult):
                print(f"    Simulation: {sim_result.potency_description}")
                print(f"    Duration: {sim_result.base_duration:.0f}s → {sim_result.enhanced_duration:.0f}s")
                print(f"    Skill: {sim_result.skill_contribution}, Effect bonus: {sim_result.gear_bonus}")
            elif isinstance(sim_result, HealingSimulationResult):
                print(f"    HP Healed: {sim_result.hp_healed}")
                print(f"    HP/MP efficiency: {sim_result.hp_per_mp:.1f}")
                print(f"    Cure Potency mult: {sim_result.cure_potency_mult:.2f}")
            elif isinstance(sim_result, EnhancingSimulationResult):
                print(f"    Potency: {sim_result.potency_description}")
                print(f"    Duration: {sim_result.base_duration:.0f}s → {sim_result.final_duration:.0f}s")
                if sim_result.damage_per_hit > 0:
                    print(f"    Enspell damage: {sim_result.damage_per_hit} → {sim_result.damage_at_cap} (at cap)")
            elif isinstance(sim_result, DarkMagicSimulationResult):
                if sim_result.resource_type:
                    print(f"    Drain amount: {sim_result.amount_drained} {sim_result.resource_type}")
                else:
                    print(f"    Initial: {sim_result.initial_damage}, DOT: {sim_result.dot_damage_per_tick}/tick")
                    print(f"    Total damage: {sim_result.total_damage}")
        
        print(f"    Hit rate: {hit_rate:.3f}")
        print(f"    Final score: {potency_score:.1f}")
    
    return potency_score


# =============================================================================
# MAIN OPTIMIZATION WORKFLOW
# =============================================================================

def run_magic_optimization(
    inventory: Inventory,
    job: Job,
    spell_name: str,
    optimization_type: MagicOptimizationType = MagicOptimizationType.DAMAGE,
    target: Optional[MagicTargetStats] = None,
    magic_burst: bool = True,
    skillchain_steps: int = 2,
    include_weapons: bool = False,
    fixed_gear: Optional[Dict[str, Dict[str, Any]]] = None,
    beam_width: int = 25,
    num_sim_casts: int = 100,
    job_gifts: Optional[JobGifts] = None,
    buff_bonuses: Optional[Dict[str, int]] = None,
) -> List[Tuple[GearsetCandidate, float]]:
    """
    Run magic gear optimization using beam search + simulation.
    
    Args:
        inventory: Player's inventory
        job: Player's job
        spell_name: Name of spell to optimize for
        optimization_type: What to optimize (DAMAGE, ACCURACY, BURST)
        target: Target stats (defaults to apex_mob)
        magic_burst: Whether to optimize for magic burst
        skillchain_steps: Number of skillchain steps for MB
        include_weapons: Whether to include weapon slots in optimization
        fixed_gear: Pre-selected gear (e.g., weapons) as wsdist dicts
        beam_width: Number of candidates in beam search
        num_sim_casts: Number of casts for damage simulation
        job_gifts: Job gifts for the player (for base character stats)
        buff_bonuses: Additional stat bonuses from buffs (GEO, COR, food, etc.)
    
    Returns:
        List of (candidate, score) tuples sorted by score (best first)
    """
    # Reset debug counters for fresh output each run
    if hasattr(evaluate_magic_accuracy, '_debug_count'):
        evaluate_magic_accuracy._debug_count = 0
    if hasattr(evaluate_magic_potency, '_debug_count'):
        evaluate_magic_potency._debug_count = 0
    
    # Get spell data
    spell = get_spell(spell_name)
    if spell is None:
        raise ValueError(f"Unknown spell: {spell_name}")
    
    # Get job preset and apply job gifts to create base character
    base_preset = get_job_preset(job)
    job_preset, job_gift_bonuses = apply_job_gifts_to_magic(base_preset, job_gifts)
    
    # Set default target
    if target is None:
        target = MAGIC_TARGETS['apex_mob']
    
    # DEBUG: Print target info
    print(f"\n[DEBUG] Target passed to run_magic_optimization:")
    print(f"  magic_evasion: {target.magic_evasion}")
    print(f"  int_stat: {target.int_stat}")
    print(f"  mnd_stat: {target.mnd_stat}")
    
    # Create optimization profile based on type
    if optimization_type == MagicOptimizationType.DAMAGE:
        profile = create_magic_damage_profile(job, spell, magic_burst, include_weapons)
    elif optimization_type == MagicOptimizationType.ACCURACY:
        profile = create_magic_accuracy_profile(job, spell, include_weapons)
    elif optimization_type == MagicOptimizationType.BURST_DAMAGE:
        profile = create_magic_burst_profile(job, spell, include_weapons)
    elif optimization_type == MagicOptimizationType.POTENCY:
        profile = create_magic_potency_profile(job, spell, include_weapons)
    else:
        profile = create_magic_damage_profile(job, spell, magic_burst, include_weapons)
    
    print(f"\n{'='*70}")
    print(f"MAGIC OPTIMIZATION - {spell_name}")
    print(f"{'='*70}")
    print(f"  Job: {job.name}")
    print(f"  Type: {optimization_type.value}")
    print(f"  Magic Burst: {'Yes' if magic_burst else 'No'}")
    print(f"  Include Weapons: {'Yes' if include_weapons else 'No'}")
    if job_gifts:
        print(f"  Job Gifts: Loaded (JP: {job_gifts.jp_spent})")
        if job_gift_bonuses.magic_accuracy > 0:
            print(f"    - Magic Accuracy: +{job_gift_bonuses.magic_accuracy}")
        if job_gift_bonuses.magic_attack > 0:
            print(f"    - Magic Attack: +{job_gift_bonuses.magic_attack}")
    
    # Determine which slots to optimize
    slots_to_optimize = list(ARMOR_SLOTS)
    if include_weapons:
        slots_to_optimize = ['main', 'sub', 'ranged'] + slots_to_optimize
    
    # Remove fixed gear slots from optimization
    if fixed_gear:
        slots_to_optimize = [s for s in slots_to_optimize if s not in fixed_gear]
    
    # Create optimizer
    print(f"\n{'-'*70}")
    print("Running Beam Search...")
    print(f"{'-'*70}")


    optimizer = NumbaBeamSearchOptimizer(
        inventory=inventory,
        profile=profile,
        beam_width=beam_width,
        job=job,
        include_weapons=include_weapons,
    )

    
    # optimizer = FastBeamSearchOptimizer(
    #     inventory=inventory,
    #     profile=profile,
    #     beam_width=beam_width,
    #     job=job,
    #     include_weapons=include_weapons,
    # )
    
    # optimizer = BeamSearchOptimizer(
    #     inventory=inventory,
    #     profile=profile,
    #     beam_width=beam_width,
    #     job=job,
    #     include_weapons=include_weapons,
    # )
    
    # Run beam search
    contenders = optimizer.search(
        fixed_gear=fixed_gear,
        slots_to_optimize=slots_to_optimize,
    )

    item_pool = optimizer.extract_item_pool(contenders=contenders)
    optimizer.print_item_pool(item_pool)
    
    print(f"\n✓ Found {len(contenders)} contender sets")
    
    # Evaluate contenders with simulation
    print(f"\n{'-'*70}")
    print("Evaluating with Magic Simulation...")
    if buff_bonuses:
        print(f"  With buffs: +{buff_bonuses.get('magic_attack', 0)} MAB, +{buff_bonuses.get('magic_accuracy', 0)} M.Acc")
    print(f"{'-'*70}")
    
    results = []
    
    for i, candidate in enumerate(contenders):
        try:
            if optimization_type == MagicOptimizationType.ACCURACY:
                # Score by hit rate
                score = evaluate_magic_accuracy(
                    candidate, spell, job_preset, target,
                    job_gift_bonuses=job_gift_bonuses,
                    buff_bonuses=buff_bonuses,
                )
            elif optimization_type == MagicOptimizationType.POTENCY:
                # Score by potency (skill + effect bonuses)
                score = evaluate_magic_potency(
                    candidate, spell, job_preset, target,
                    job_gift_bonuses=job_gift_bonuses,
                    buff_bonuses=buff_bonuses,
                )
            else:
                # Score by damage (DAMAGE and BURST_DAMAGE)
                score = evaluate_magic_damage(
                    candidate, spell, job_preset, target,
                    magic_burst=magic_burst,
                    skillchain_steps=skillchain_steps,
                    num_casts=num_sim_casts,
                    job_gift_bonuses=job_gift_bonuses,
                    buff_bonuses=buff_bonuses,
                )
            
            results.append((candidate, score))
            
        except Exception as e:
            print(f"  Warning: Failed to evaluate contender #{i+1}: {e}")
    
    # Sort by score (higher is better)
    results.sort(key=lambda x: x[1], reverse=True)
    
    return results


def display_magic_results(
    results: List[Tuple[GearsetCandidate, float]],
    spell_name: str,
    optimization_type: MagicOptimizationType,
    top_n: int = 5,
):
    """
    Display magic optimization results.
    
    Args:
        results: List of (candidate, score) tuples
        spell_name: Name of spell optimized for
        optimization_type: Type of optimization performed
        top_n: Number of top results to show
    """
    print(f"\n{'='*70}")
    print(f"OPTIMIZATION RESULTS - {spell_name}")
    print(f"{'='*70}")
    
    # Determine score label and format based on optimization type
    if optimization_type == MagicOptimizationType.ACCURACY:
        score_label = "Hit Rate"
        score_format = "{:.1%}"
    elif optimization_type == MagicOptimizationType.POTENCY:
        score_label = "Potency Score"
        score_format = "{:,.0f}"
    else:
        score_label = "Avg Damage"
        score_format = "{:,.0f}"
    
    for rank, (candidate, score) in enumerate(results[:top_n], 1):
        formatted_score = score_format.format(score)
        print(f"\n#{rank} - {score_label}: {formatted_score}")
        print(f"    Beam Score: {candidate.score:.1f}")
        
        # Show key magic stats
        stats = candidate.stats
        print(f"    INT: +{stats.INT}  MND: +{stats.MND}  MAB: +{stats.magic_attack}")
        print(f"    M.Dmg: +{stats.magic_damage}  M.Acc: +{stats.magic_accuracy}")
        
        # Show relevant stats based on optimization type
        if optimization_type == MagicOptimizationType.POTENCY:
            # Show skill bonuses for potency
            print(f"    Enf.Skill: +{stats.enfeebling_magic_skill}  Dark.Skill: +{stats.dark_magic_skill}  Div.Skill: +{stats.divine_magic_skill}")
            print(f"    Enf.Effect: +{stats.enfeebling_effect}  Enf.Duration: +{stats.enfeebling_duration//100}%")
        else:
            print(f"    MBB: +{stats.magic_burst_bonus//100}%  MBB II: +{stats.magic_burst_damage_ii//100}%")
        
        print("    Gear:")
        for slot in ['head', 'body', 'hands', 'legs', 'feet', 'neck', 'ear1', 'ear2',
                     'ring1', 'ring2', 'waist', 'back', 'main', 'sub', 'ammo']:
            if slot in candidate.gear:
                name = candidate.gear[slot].get('Name2',
                       candidate.gear[slot].get('Name', 'Empty'))
                if name != 'Empty':
                    print(f"      {slot:8s}: {name}")
    
    if len(results) >= 2:
        best = results[0][1]
        worst = results[-1][1]
        if optimization_type == MagicOptimizationType.ACCURACY:
            print(f"\n  Best: {best:.1%}  |  Worst: {worst:.1%}")
        else:
            print(f"\n  Best: {best:,.0f}  |  Worst: {worst:,.0f}  |  Range: {best-worst:,.0f}")


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def quick_magic_optimize(
    inventory_path: str,
    job_name: str,
    spell_name: str,
    optimization_type: str = "damage",
    magic_burst: bool = True,
    include_weapons: bool = False,
    target_name: str = "apex_mob",
) -> List[Tuple[GearsetCandidate, float]]:
    """
    Quick convenience function for magic optimization.
    
    Args:
        inventory_path: Path to inventory CSV
        job_name: Job name string (e.g., "BLM")
        spell_name: Spell name (e.g., "Thunder VI")
        optimization_type: "damage", "accuracy", "burst", or "potency"
        magic_burst: Whether to optimize for magic burst
        include_weapons: Whether to include weapon slots
        target_name: Target preset name
    
    Returns:
        List of (candidate, score) tuples
    """
    from inventory_loader import load_inventory
    
    # Map strings to enums
    job_map = {
        "WAR": Job.WAR, "MNK": Job.MNK, "WHM": Job.WHM, "BLM": Job.BLM,
        "RDM": Job.RDM, "THF": Job.THF, "PLD": Job.PLD, "DRK": Job.DRK,
        "BST": Job.BST, "BRD": Job.BRD, "RNG": Job.RNG, "SMN": Job.SMN,
        "SAM": Job.SAM, "NIN": Job.NIN, "DRG": Job.DRG, "BLU": Job.BLU,
        "COR": Job.COR, "PUP": Job.PUP, "DNC": Job.DNC, "SCH": Job.SCH,
        "GEO": Job.GEO, "RUN": Job.RUN,
    }
    
    type_map = {
        "damage": MagicOptimizationType.DAMAGE,
        "accuracy": MagicOptimizationType.ACCURACY,
        "burst": MagicOptimizationType.BURST_DAMAGE,
        "potency": MagicOptimizationType.POTENCY,
    }
    
    job = job_map.get(job_name.upper())
    if job is None:
        raise ValueError(f"Unknown job: {job_name}")
    
    opt_type = type_map.get(optimization_type.lower(), MagicOptimizationType.DAMAGE)
    target = MAGIC_TARGETS.get(target_name, MAGIC_TARGETS['apex_mob'])
    
    # Load inventory
    print(f"Loading inventory from {inventory_path}...")
    inventory = load_inventory(inventory_path)
    inventory.load_from_csv(inventory_path, equip_only=True)
    print(f"  Loaded {len(inventory.items)} equippable items")
    
    # Run optimization
    results = run_magic_optimization(
        inventory=inventory,
        job=job,
        spell_name=spell_name,
        optimization_type=opt_type,
        target=target,
        magic_burst=magic_burst,
        include_weapons=include_weapons,
    )
    
    # Display results
    display_magic_results(results, spell_name, opt_type)
    
    return results


# =============================================================================
# WEBUI-ORIENTED HELPERS
# =============================================================================

def get_valid_optimization_types(spell_name: str) -> List[MagicOptimizationType]:
    """
    Get the valid optimization types for a given spell.
    
    Different spell types have different valid optimization goals:
    - Elemental damage spells: DAMAGE, BURST_DAMAGE, ACCURACY
    - Enfeebling spells: POTENCY, ACCURACY
    - Dark spells (Drain/Aspir/Bio): POTENCY, DAMAGE, ACCURACY
    - Divine spells: DAMAGE, ACCURACY
    
    Args:
        spell_name: Name of the spell
        
    Returns:
        List of valid MagicOptimizationType values
    """
    spell = get_spell(spell_name)
    if spell is None:
        # Default to all types if spell not found
        return [
            MagicOptimizationType.DAMAGE,
            MagicOptimizationType.ACCURACY,
            MagicOptimizationType.BURST_DAMAGE,
            MagicOptimizationType.POTENCY,
        ]
    
    valid_types = []
    
    if spell.magic_type == MagicType.ELEMENTAL:
        # Elemental nukes - damage focused
        valid_types = [
            MagicOptimizationType.DAMAGE,
            MagicOptimizationType.BURST_DAMAGE,
            MagicOptimizationType.ACCURACY,
        ]
    elif spell.magic_type in [MagicType.ENFEEBLING_INT, MagicType.ENFEEBLING_MND]:
        # Enfeebling - potency and accuracy
        valid_types = [
            MagicOptimizationType.POTENCY,
            MagicOptimizationType.ACCURACY,
        ]
    elif spell.magic_type == MagicType.DARK:
        # Dark magic - depends on spell subtype
        if spell.name.startswith('Absorb'):
            # Absorb spells: Potency from equipment, Accuracy from skill
            # Per BG-Wiki: "Dark Magic does nothing for the potency of Absorb spells"
            valid_types = [
                MagicOptimizationType.POTENCY,   # Equipment-based potency (Liberator, etc.)
                MagicOptimizationType.ACCURACY,  # Dark Magic Skill affects landing
            ]
        elif spell.name.startswith('Bio'):
            # Bio does damage + DOT potency
            valid_types = [
                MagicOptimizationType.POTENCY,
                MagicOptimizationType.DAMAGE,
                MagicOptimizationType.ACCURACY,
            ]
        else:
            # Drain/Aspir - potency from Dark Magic Skill
            valid_types = [
                MagicOptimizationType.POTENCY,
                MagicOptimizationType.ACCURACY,
            ]
    elif spell.magic_type == MagicType.DIVINE:
        # Divine - damage and accuracy
        valid_types = [
            MagicOptimizationType.DAMAGE,
            MagicOptimizationType.BURST_DAMAGE,
            MagicOptimizationType.ACCURACY,
        ]
    elif spell.magic_type == MagicType.HEALING:
        # Healing - potency (cure potency)
        valid_types = [
            MagicOptimizationType.POTENCY,
        ]
    elif spell.magic_type == MagicType.ENHANCING:
        # Enhancing - potency (duration/effect)
        valid_types = [
            MagicOptimizationType.POTENCY,
        ]
    else:
        # Default
        valid_types = [
            MagicOptimizationType.DAMAGE,
            MagicOptimizationType.ACCURACY,
        ]
    
    return valid_types


def is_burst_relevant(spell_name: str) -> bool:
    """
    Check if Magic Burst option is relevant for a spell.
    
    MB is relevant for damage spells, not for enfeebling/utility spells.
    
    Args:
        spell_name: Name of the spell
        
    Returns:
        True if MB option should be shown
    """
    spell = get_spell(spell_name)
    if spell is None:
        return True  # Default to showing MB option
    
    # MB is relevant for damage-dealing spells
    damage_types = [
        MagicType.ELEMENTAL,
        MagicType.DIVINE,
        MagicType.DARK,  # Bio can MB
    ]
    
    # Not relevant for enfeebling, healing, enhancing
    non_mb_types = [
        MagicType.ENFEEBLING_INT,
        MagicType.ENFEEBLING_MND,
        MagicType.HEALING,
        MagicType.ENHANCING,
    ]
    
    if spell.magic_type in non_mb_types:
        return False
    
    # Special case: Drain/Aspir/Absorb don't benefit from MB damage
    if spell.name.startswith('Drain') or spell.name.startswith('Aspir') or spell.name.startswith('Absorb'):
        return False
    
    return spell.magic_type in damage_types


@dataclass
class OptimizationRequest:
    """
    Structured request for magic optimization.
    
    Designed to match the webUI flow:
    1. Select spell → spell_name
    2. Select goal → optimization_type  
    3. Select MB → magic_burst
    4. Run optimization
    """
    spell_name: str
    optimization_type: MagicOptimizationType
    magic_burst: bool = False
    include_weapons: bool = False
    target_name: str = "apex_mob"


def optimize_from_request(
    inventory: Inventory,
    job: Job,
    request: OptimizationRequest,
    beam_width: int = 25,
) -> List[Tuple[GearsetCandidate, float]]:
    """
    Run optimization from a structured request.
    
    This is the primary entry point for webUI integration.
    
    Args:
        inventory: Player's loaded inventory
        job: Player's job
        request: OptimizationRequest with spell, goal, and options
        beam_width: Beam search width
        
    Returns:
        List of (candidate, score) tuples
    """
    target = MAGIC_TARGETS.get(request.target_name, MAGIC_TARGETS['apex_mob'])
    
    return run_magic_optimization(
        inventory=inventory,
        job=job,
        spell_name=request.spell_name,
        optimization_type=request.optimization_type,
        target=target,
        magic_burst=request.magic_burst,
        include_weapons=request.include_weapons,
        beam_width=beam_width,
    )


# =============================================================================
# MAIN (for testing)
# =============================================================================

if __name__ == "__main__":
    print("Magic Beam Search Optimizer")
    print("="*70)
    
    # Example usage
    inventory_path = "inventory_full_Masinmanci_20260111_124357.csv"
    
    try:
        results = quick_magic_optimize(
            inventory_path=inventory_path,
            job_name="BLM",
            spell_name="Thunder VI",
            optimization_type="damage",
            magic_burst=True,
            include_weapons=False,
        )
        
        print(f"\n✓ Optimization complete! Found {len(results)} gear sets.")
        
    except FileNotFoundError:
        print(f"Inventory file not found: {inventory_path}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()