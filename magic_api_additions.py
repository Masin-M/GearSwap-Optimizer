"""
MAGIC API ADDITIONS FOR api.py
==============================

This file contains all the code that needs to be added to api.py to support
magic optimization. Copy these sections into the appropriate places in api.py.

Organization:
1. New imports
2. Spell category definitions (for UI grouping)
3. Magic target presets
4. Magic buff definitions
5. Pydantic models for requests/responses
6. API endpoint handlers
"""

# =============================================================================
# SECTION 1: NEW IMPORTS (add to existing imports section)
# =============================================================================

# Add these imports near the top of api.py, with the other local imports:

"""
from magic_optimizer import (
    run_magic_optimization,
    MagicOptimizationType,
    get_valid_optimization_types,
    is_burst_relevant,
    get_job_preset,
    JOB_MAGIC_PRESETS,
)
from magic_simulation import (
    MagicSimulator,
    CasterStats,
    MagicTargetStats,
    MAGIC_TARGETS,
)
from spell_database import (
    get_spell,
    ALL_SPELLS,
    SpellData,
)
from magic_formulas import MagicType, Element
"""


# =============================================================================
# SECTION 2: SPELL CATEGORIES (add after TARGET_PRESETS)
# =============================================================================

SPELL_CATEGORIES = {
    "elemental_tier_1": {
        "id": "elemental_tier_1",
        "name": "Elemental Tier I",
        "spells": ["Stone", "Water", "Aero", "Fire", "Blizzard", "Thunder"],
    },
    "elemental_tier_2": {
        "id": "elemental_tier_2",
        "name": "Elemental Tier II",
        "spells": ["Stone II", "Water II", "Aero II", "Fire II", "Blizzard II", "Thunder II"],
    },
    "elemental_tier_3": {
        "id": "elemental_tier_3",
        "name": "Elemental Tier III",
        "spells": ["Stone III", "Water III", "Aero III", "Fire III", "Blizzard III", "Thunder III"],
    },
    "elemental_tier_4": {
        "id": "elemental_tier_4",
        "name": "Elemental Tier IV",
        "spells": ["Stone IV", "Water IV", "Aero IV", "Fire IV", "Blizzard IV", "Thunder IV"],
    },
    "elemental_tier_5": {
        "id": "elemental_tier_5",
        "name": "Elemental Tier V",
        "spells": ["Stone V", "Water V", "Aero V", "Fire V", "Blizzard V", "Thunder V"],
    },
    "elemental_tier_6": {
        "id": "elemental_tier_6",
        "name": "Elemental Tier VI",
        "spells": ["Stone VI", "Water VI", "Aero VI", "Fire VI", "Blizzard VI", "Thunder VI"],
    },
    "elemental_ga": {
        "id": "elemental_ga",
        "name": "-ga Spells (AoE)",
        "spells": ["Stonega", "Waterga", "Aeroga", "Firaga", "Blizzaga", "Thundaga",
                   "Stonega II", "Waterga II", "Aeroga II", "Firaga II", "Blizzaga II", "Thundaga II",
                   "Stonega III", "Waterga III", "Aeroga III", "Firaga III", "Blizzaga III", "Thundaga III"],
    },
    "elemental_ja": {
        "id": "elemental_ja",
        "name": "-ja Spells (AoE)",
        "spells": ["Stoneja", "Waterja", "Aeroja", "Firaja", "Blizzaja", "Thundaja"],
    },
    "ancient_magic": {
        "id": "ancient_magic",
        "name": "Ancient Magic",
        "spells": ["Quake", "Flood", "Tornado", "Flare", "Freeze", "Burst"],
    },
    "ancient_magic_2": {
        "id": "ancient_magic_2",
        "name": "Ancient Magic II",
        "spells": ["Quake II", "Flood II", "Tornado II", "Flare II", "Freeze II", "Burst II"],
    },
    "comet": {
        "id": "comet",
        "name": "Comet",
        "spells": ["Comet"],
    },
    "helix": {
        "id": "helix",
        "name": "Helix Spells",
        "spells": ["Geohelix", "Hydrohelix", "Anemohelix", "Pyrohelix", "Cryohelix", "Ionohelix", 
                   "Luminohelix", "Noctohelix"],
    },
    "helix_2": {
        "id": "helix_2",
        "name": "Helix II Spells",
        "spells": ["Geohelix II", "Hydrohelix II", "Anemohelix II", "Pyrohelix II", "Cryohelix II", 
                   "Ionohelix II", "Luminohelix II", "Noctohelix II"],
    },
    "divine_banish": {
        "id": "divine_banish",
        "name": "Divine (Banish)",
        "spells": ["Banish", "Banish II", "Banish III", "Banishga", "Banishga II"],
    },
    "divine_holy": {
        "id": "divine_holy",
        "name": "Divine (Holy)",
        "spells": ["Holy", "Holy II"],
    },
    "dark_bio": {
        "id": "dark_bio",
        "name": "Dark (Bio)",
        "spells": ["Bio", "Bio II", "Bio III"],
    },
    "dark_drain": {
        "id": "dark_drain",
        "name": "Dark (Drain/Aspir)",
        "spells": ["Drain", "Drain II", "Drain III", "Aspir", "Aspir II", "Aspir III"],
    },
    "dark_utility": {
        "id": "dark_utility",
        "name": "Dark (Utility)",
        "spells": ["Stun", "Absorb-STR", "Absorb-DEX", "Absorb-VIT", "Absorb-AGI", 
                   "Absorb-INT", "Absorb-MND", "Absorb-CHR", "Absorb-ACC", "Absorb-TP", "Absorb-Attri"],
    },
    "enfeebling_mnd": {
        "id": "enfeebling_mnd",
        "name": "Enfeebling (MND)",
        "spells": ["Slow", "Slow II", "Paralyze", "Paralyze II", "Addle", "Addle II", 
                   "Silence", "Distract", "Distract II", "Distract III", 
                   "Frazzle", "Frazzle II", "Frazzle III"],
    },
    "enfeebling_int": {
        "id": "enfeebling_int",
        "name": "Enfeebling (INT)",
        "spells": ["Blind", "Blind II", "Gravity", "Gravity II", "Poison", "Poison II",
                   "Sleep", "Sleep II", "Dispel", "Break", "Breakga"],
    },
    "dia": {
        "id": "dia",
        "name": "Dia",
        "spells": ["Dia", "Dia II", "Dia III", "Diaga"],
    },
    "enspell": {
        "id": "enspell",
        "name": "Enspells",
        "spells": ["Enfire", "Enblizzard", "Enaero", "Enstone", "Enthunder", "Enwater",
                   "Enfire II", "Enblizzard II", "Enaero II", "Enstone II", "Enthunder II", "Enwater II",
                   "Enlight", "Enlight II", "Endark", "Endark II"],
    },
}

# Quick access list for popular nukes (for UI quick-select)
POPULAR_NUKES = [
    "Thunder VI", "Fire VI", "Blizzard VI", "Aero VI", "Stone VI", "Water VI",
    "Burst II", "Freeze II", "Flare II", "Tornado II", "Quake II", "Flood II",
    "Thundaja", "Firaja", "Blizzaja",
]


# =============================================================================
# SECTION 3: MAGIC TARGET PRESETS (add after SPELL_CATEGORIES)
# =============================================================================

# Note: These supplement the physical TARGET_PRESETS with magic-specific stats
# The MAGIC_TARGETS from magic_simulation.py will be used directly,
# but we define this for API serialization

MAGIC_TARGET_PRESETS = {
    "apex_mob": {
        "id": "apex_mob",
        "name": "Apex Mob",
        "level": 129,
        "int_stat": 200,
        "mnd_stat": 200,
        "magic_evasion": 600,
        "magic_defense_bonus": 30,
    },
    "odyssey_nm": {
        "id": "odyssey_nm",
        "name": "Odyssey NM",
        "level": 140,
        "int_stat": 250,
        "mnd_stat": 250,
        "magic_evasion": 750,
        "magic_defense_bonus": 50,
    },
    "sortie_boss": {
        "id": "sortie_boss",
        "name": "Sortie Boss",
        "level": 145,
        "int_stat": 280,
        "mnd_stat": 280,
        "magic_evasion": 800,
        "magic_defense_bonus": 40,
    },
    "ambuscade_vd": {
        "id": "ambuscade_vd",
        "name": "Ambuscade VD",
        "level": 135,
        "int_stat": 220,
        "mnd_stat": 220,
        "magic_evasion": 650,
        "magic_defense_bonus": 25,
    },
    "training_dummy": {
        "id": "training_dummy",
        "name": "Training Dummy",
        "level": 1,
        "int_stat": 100,
        "mnd_stat": 100,
        "magic_evasion": 300,
        "magic_defense_bonus": 0,
    },
    "high_resist": {
        "id": "high_resist",
        "name": "High Resist Target",
        "level": 150,
        "int_stat": 300,
        "mnd_stat": 300,
        "magic_evasion": 900,
        "magic_defense_bonus": 60,
    },
}


# =============================================================================
# SECTION 4: MAGIC BUFF DEFINITIONS (add to BUFF_DEFINITIONS)
# =============================================================================

# Add these entries to the existing BUFF_DEFINITIONS dict:

MAGIC_BUFF_ADDITIONS = {
    # Add to existing "cor" section:
    "cor_magic": {
        "Wizard's Roll XI": {"magic_attack": 50},
        "Wizard's Roll X": {"magic_attack": 30},
        "Warlock's Roll XI": {"magic_accuracy": 52},
        "Warlock's Roll X": {"magic_accuracy": 32},
    },
    # Add to existing "geo" section:
    "geo_magic": {
        "Geo-Acumen": {"magic_attack_pct": 35},  # 35% MAB
        "Indi-Acumen": {"magic_attack_pct": 20},
        "Geo-Focus": {"magic_accuracy": 75},
        "Indi-Focus": {"magic_accuracy": 45},
        "Geo-Languor": {"magic_evasion_down": 75},  # Target debuff
        "Indi-Languor": {"magic_evasion_down": 45},
        "Geo-Malaise": {"magic_defense_down": 35},  # Target debuff
        "Indi-Malaise": {"magic_defense_down": 20},
    },
    # SCH-specific abilities
    "sch": {
        "Ebullience": {"magic_damage_mult": 40},  # +40% magic damage on next spell
        "Immanence": {"skillchain_enabled": True},
        "Dark Arts": {"dark_magic_cast_time": -10, "dark_magic_recast": -10},
        "Light Arts": {"enhancing_cast_time": -10, "healing_cast_time": -10},
    },
    # Magic-specific food
    "food_magic": {
        "Tropical Crepe": {"INT": 8, "magic_attack": 60, "magic_accuracy": 60},
        "Pear Crepe": {"INT": 6, "magic_attack": 50, "magic_accuracy": 50},
        "Miso Ramen +1": {"DEX": 8, "accuracy": 90, "ranged_accuracy": 90, "magic_accuracy": 90},
        "Seafood Stew": {"INT": 6, "MND": 6, "magic_attack": 40},
        "Rolanberry Pie +1": {"INT": 7, "MP": 70},
    },
}

# Magic-specific debuffs on target
MAGIC_DEBUFF_DEFINITIONS = {
    "geo_magic_debuff": {
        "Geo-Languor": {"magic_evasion_down": 75},
        "Indi-Languor": {"magic_evasion_down": 45},
        "Geo-Malaise": {"magic_defense_down": 35},
        "Indi-Malaise": {"magic_defense_down": 20},
    },
    "rdm": {
        "Frazzle III": {"magic_evasion_down": 45},
        "Frazzle II": {"magic_evasion_down": 30},
        "Frazzle": {"magic_evasion_down": 15},
    },
}


# =============================================================================
# SECTION 5: PYDANTIC MODELS (add after existing models)
# =============================================================================

from pydantic import BaseModel
from typing import Dict, List, Optional, Any


class SpellInfo(BaseModel):
    """Information about a single spell."""
    name: str
    element: str
    magic_type: str
    skill_type: str
    tier: int
    mp_cost: int
    cast_time: float
    is_aoe: bool
    base_v: int
    dint_cap: int


class SpellCategoryInfo(BaseModel):
    """Spell category with list of spells."""
    id: str
    name: str
    spells: List[str]


class MagicOptimizationTypeInfo(BaseModel):
    """Information about a magic optimization type."""
    id: str
    name: str
    description: str


class MagicTargetInfo(BaseModel):
    """Magic target preset information."""
    id: str
    name: str
    level: int
    int_stat: int
    mnd_stat: int
    magic_evasion: int
    magic_defense_bonus: int


class MagicOptimizeRequest(BaseModel):
    """Request body for magic optimization."""
    job: str
    sub_job: str = "rdm"
    spell_name: str
    optimization_type: str  # "damage", "accuracy", "burst", "potency"
    magic_burst: bool = True
    skillchain_steps: int = 2
    target: str = "apex_mob"
    include_weapons: bool = False
    beam_width: int = 25
    buffs: Dict[str, Any] = {}
    debuffs: List[str] = []
    master_level: int = 0


class MagicGearsetResult(BaseModel):
    """A single gear set result from magic optimization."""
    rank: int
    score: float
    damage: Optional[float] = None
    hit_rate: Optional[float] = None
    potency_score: Optional[float] = None
    gear: Dict[str, Dict[str, Any]]
    stats: Dict[str, Any] = {}


class MagicOptimizeResponse(BaseModel):
    """Response from magic optimization endpoint."""
    success: bool
    spell_name: str
    optimization_type: str
    magic_burst: bool
    target: str
    results: List[MagicGearsetResult]
    error: Optional[str] = None


class MagicStatsRequest(BaseModel):
    """Request for magic stats calculation."""
    job: str
    sub_job: str = "rdm"
    master_level: int = 0
    gearset: Dict[str, Dict[str, Any]]
    spell_name: Optional[str] = None
    buffs: Dict[str, Any] = {}
    target: str = "apex_mob"


class MagicStatsResponse(BaseModel):
    """Response with calculated magic stats."""
    success: bool
    stats: Dict[str, Any] = {}
    error: Optional[str] = None


# =============================================================================
# SECTION 6: API ENDPOINTS (add after existing endpoints)
# =============================================================================

# NOTE: These are the endpoint handler functions. Add them to api.py.
# The actual FastAPI decorators (@app.get, @app.post) are included.


# -----------------------------------------------------------------------------
# GET /api/spells - Get all spells grouped by category
# -----------------------------------------------------------------------------
"""
@app.get("/api/spells")
async def get_spells():
    '''
    Get all available spells grouped by category.
    
    Returns a dict with:
    - categories: List of category info with spell names
    - popular: List of popular nuke spell names for quick-select
    - all_spells: Dict of spell_name -> basic spell info
    '''
    from spell_database import ALL_SPELLS, get_spell
    from magic_formulas import MagicType, Element
    
    # Build category list
    categories = []
    for cat_id, cat_data in SPELL_CATEGORIES.items():
        # Filter to only spells that exist in database
        valid_spells = [s for s in cat_data["spells"] if s in ALL_SPELLS]
        if valid_spells:
            categories.append({
                "id": cat_data["id"],
                "name": cat_data["name"],
                "spells": valid_spells,
            })
    
    # Build simplified spell info dict
    all_spells_info = {}
    for name, spell in ALL_SPELLS.items():
        all_spells_info[name] = {
            "name": spell.name,
            "element": spell.element.name if hasattr(spell.element, 'name') else str(spell.element),
            "magic_type": spell.magic_type.name if hasattr(spell.magic_type, 'name') else str(spell.magic_type),
            "tier": spell.tier,
            "mp_cost": spell.mp_cost,
            "is_aoe": spell.is_aoe,
        }
    
    # Filter popular nukes to only those in database
    popular = [s for s in POPULAR_NUKES if s in ALL_SPELLS]
    
    return {
        "categories": categories,
        "popular": popular,
        "all_spells": all_spells_info,
        "count": len(ALL_SPELLS),
    }
"""


# -----------------------------------------------------------------------------
# GET /api/spells/categories - Get spell category list
# -----------------------------------------------------------------------------
"""
@app.get("/api/spells/categories")
async def get_spell_categories():
    '''Get list of spell categories.'''
    categories = []
    for cat_id, cat_data in SPELL_CATEGORIES.items():
        categories.append({
            "id": cat_data["id"],
            "name": cat_data["name"],
            "spell_count": len(cat_data["spells"]),
        })
    return {"categories": categories}
"""


# -----------------------------------------------------------------------------
# GET /api/spells/{category} - Get spells in a category
# -----------------------------------------------------------------------------
"""
@app.get("/api/spells/category/{category_id}")
async def get_spells_by_category(category_id: str):
    '''Get all spells in a specific category.'''
    from spell_database import ALL_SPELLS
    
    if category_id not in SPELL_CATEGORIES:
        raise HTTPException(status_code=404, detail=f"Category not found: {category_id}")
    
    cat_data = SPELL_CATEGORIES[category_id]
    spells = []
    
    for spell_name in cat_data["spells"]:
        if spell_name in ALL_SPELLS:
            spell = ALL_SPELLS[spell_name]
            spells.append({
                "name": spell.name,
                "element": spell.element.name,
                "magic_type": spell.magic_type.name,
                "tier": spell.tier,
                "mp_cost": spell.mp_cost,
                "cast_time": spell.cast_time,
                "is_aoe": spell.is_aoe,
            })
    
    return {
        "category": {
            "id": cat_data["id"],
            "name": cat_data["name"],
        },
        "spells": spells,
    }
"""


# -----------------------------------------------------------------------------
# GET /api/spell/{spell_name} - Get detailed spell info
# -----------------------------------------------------------------------------
"""
@app.get("/api/spell/{spell_name}")
async def get_spell_details(spell_name: str):
    '''Get detailed information for a specific spell.'''
    from spell_database import get_spell
    from magic_optimizer import get_valid_optimization_types, is_burst_relevant
    
    spell = get_spell(spell_name)
    if spell is None:
        raise HTTPException(status_code=404, detail=f"Spell not found: {spell_name}")
    
    # Get valid optimization types for this spell
    valid_types = get_valid_optimization_types(spell_name)
    valid_type_names = [t.value for t in valid_types]
    
    # Check if MB is relevant
    mb_relevant = is_burst_relevant(spell_name)
    
    return {
        "name": spell.name,
        "element": spell.element.name,
        "magic_type": spell.magic_type.name,
        "skill_type": spell.skill_type,
        "tier": spell.tier,
        "mp_cost": spell.mp_cost,
        "cast_time": spell.cast_time,
        "recast_time": spell.recast_time,
        "is_aoe": spell.is_aoe,
        "base_v": spell.base_v,
        "dint_cap": spell.dint_cap,
        "m_values": {str(k): v for k, v in spell.m_values.items()},
        "properties": spell.properties,
        "valid_optimization_types": valid_type_names,
        "magic_burst_relevant": mb_relevant,
    }
"""


# -----------------------------------------------------------------------------
# GET /api/magic/optimization-types - Get valid optimization types for a spell
# -----------------------------------------------------------------------------
"""
@app.get("/api/magic/optimization-types")
async def get_magic_optimization_types(spell_name: str = None):
    '''
    Get valid optimization types, optionally filtered by spell.
    
    Query params:
        spell_name: If provided, returns only valid types for that spell
    '''
    from magic_optimizer import get_valid_optimization_types, MagicOptimizationType
    
    # Define all types with descriptions
    all_types = {
        "damage": {
            "id": "damage",
            "name": "Damage",
            "description": "Maximize magic damage output (INT, MAB, Magic Damage)"
        },
        "accuracy": {
            "id": "accuracy",
            "name": "Accuracy",
            "description": "Maximize magic accuracy for landing spells (M.Acc, Skill, INT/MND)"
        },
        "burst": {
            "id": "burst",
            "name": "Magic Burst",
            "description": "Maximize magic burst damage (MBB, MBB II, MAB)"
        },
        "potency": {
            "id": "potency",
            "name": "Potency",
            "description": "Maximize spell effect potency (Skill, Effect+, Duration)"
        },
    }
    
    if spell_name:
        valid_types = get_valid_optimization_types(spell_name)
        valid_type_ids = [t.value for t in valid_types]
        return {
            "spell_name": spell_name,
            "types": [all_types[t] for t in valid_type_ids if t in all_types]
        }
    
    return {"types": list(all_types.values())}
"""


# -----------------------------------------------------------------------------
# GET /api/magic/targets - Get magic target presets
# -----------------------------------------------------------------------------
"""
@app.get("/api/magic/targets")
async def get_magic_targets():
    '''Get available magic target presets.'''
    targets = []
    for target_id, data in MAGIC_TARGET_PRESETS.items():
        targets.append(data)
    return {"targets": targets}
"""


# -----------------------------------------------------------------------------
# POST /api/optimize/magic - Run magic gear optimization
# -----------------------------------------------------------------------------
"""
@app.post("/api/optimize/magic", response_model=MagicOptimizeResponse)
async def optimize_magic(request: MagicOptimizeRequest):
    '''
    Run magic gear optimization.
    
    This endpoint:
    1. Validates the spell and job
    2. Creates an optimization profile based on the optimization_type
    3. Runs beam search to find candidate gear sets
    4. Evaluates candidates with magic simulation
    5. Returns ranked results with gear and stats
    '''
    from magic_optimizer import (
        run_magic_optimization, MagicOptimizationType, get_job_preset
    )
    from magic_simulation import MAGIC_TARGETS, MagicTargetStats
    
    if not state.inventory:
        return MagicOptimizeResponse(
            success=False,
            spell_name=request.spell_name,
            optimization_type=request.optimization_type,
            magic_burst=request.magic_burst,
            target=request.target,
            results=[],
            error="No inventory loaded"
        )
    
    try:
        # Map job string to enum
        job_enum = JOB_ENUM_MAP.get(request.job.upper())
        if not job_enum:
            return MagicOptimizeResponse(
                success=False,
                spell_name=request.spell_name,
                optimization_type=request.optimization_type,
                magic_burst=request.magic_burst,
                target=request.target,
                results=[],
                error=f"Invalid job: {request.job}"
            )
        
        # Map optimization type string to enum
        opt_type_map = {
            "damage": MagicOptimizationType.DAMAGE,
            "accuracy": MagicOptimizationType.ACCURACY,
            "burst": MagicOptimizationType.BURST_DAMAGE,
            "potency": MagicOptimizationType.POTENCY,
        }
        opt_type = opt_type_map.get(request.optimization_type.lower(), MagicOptimizationType.DAMAGE)
        
        # Get target stats
        target = MAGIC_TARGETS.get(request.target, MAGIC_TARGETS['apex_mob'])
        
        # Apply magic debuffs to target if any
        # (Future: process request.debuffs to modify target.magic_evasion, etc.)
        
        # Run optimization
        results = run_magic_optimization(
            inventory=state.inventory,
            job=job_enum,
            spell_name=request.spell_name,
            optimization_type=opt_type,
            target=target,
            magic_burst=request.magic_burst,
            skillchain_steps=request.skillchain_steps,
            include_weapons=request.include_weapons,
            beam_width=request.beam_width,
        )
        
        # Format results
        formatted_results = []
        for rank, (candidate, score) in enumerate(results[:10], 1):
            # Build gear dict
            gear_dict = {}
            for slot, item in candidate.gear.items():
                gear_dict[slot] = {
                    "name": item.get("Name", "Empty"),
                    "name2": item.get("Name2", item.get("Name", "Empty")),
                }
            
            # Build stats summary
            stats_summary = {
                "INT": candidate.stats.INT,
                "MND": candidate.stats.MND,
                "magic_attack": candidate.stats.magic_attack,
                "magic_damage": candidate.stats.magic_damage,
                "magic_accuracy": candidate.stats.magic_accuracy,
                "magic_burst_bonus": candidate.stats.magic_burst_bonus,
                "magic_burst_damage_ii": candidate.stats.magic_burst_damage_ii,
                "elemental_magic_skill": candidate.stats.elemental_magic_skill,
                "dark_magic_skill": candidate.stats.dark_magic_skill,
                "enfeebling_magic_skill": candidate.stats.enfeebling_magic_skill,
                "fast_cast": candidate.stats.fast_cast,
            }
            
            # Determine what score represents based on optimization type
            result_entry = MagicGearsetResult(
                rank=rank,
                score=candidate.score,
                gear=gear_dict,
                stats=stats_summary,
            )
            
            # Add type-specific score interpretation
            if opt_type == MagicOptimizationType.ACCURACY:
                result_entry.hit_rate = score  # Score is hit rate (0-1)
            elif opt_type == MagicOptimizationType.POTENCY:
                result_entry.potency_score = score
            else:
                result_entry.damage = score  # Score is average damage
            
            formatted_results.append(result_entry)
        
        return MagicOptimizeResponse(
            success=True,
            spell_name=request.spell_name,
            optimization_type=request.optimization_type,
            magic_burst=request.magic_burst,
            target=request.target,
            results=formatted_results,
        )
    
    except Exception as e:
        import traceback
        return MagicOptimizeResponse(
            success=False,
            spell_name=request.spell_name,
            optimization_type=request.optimization_type,
            magic_burst=request.magic_burst,
            target=request.target,
            results=[],
            error=f"{str(e)}\n{traceback.format_exc()}"
        )
"""


# -----------------------------------------------------------------------------
# GET /api/magic/buffs - Get magic-specific buff definitions
# -----------------------------------------------------------------------------
"""
@app.get("/api/magic/buffs")
async def get_magic_buffs():
    '''Get magic-specific buff and debuff definitions.'''
    return {
        "buffs": MAGIC_BUFF_ADDITIONS,
        "debuffs": MAGIC_DEBUFF_DEFINITIONS,
    }
"""


# -----------------------------------------------------------------------------
# POST /api/stats/calculate/magic - Calculate magic stats for a gearset
# -----------------------------------------------------------------------------
"""
@app.post("/api/stats/calculate/magic")
async def calculate_magic_stats(request: MagicStatsRequest):
    '''
    Calculate effective magic stats for a gear set.
    
    Returns detailed magic stats including:
    - Primary stats (INT, MND)
    - Magic offense (MAB, M.Dmg, M.Acc)
    - Magic skills
    - Magic Burst Bonus (capped and uncapped portions)
    - Fast Cast
    '''
    from magic_optimizer import get_job_preset, JOB_MAGIC_PRESETS
    from spell_database import get_spell
    
    try:
        job_enum = JOB_ENUM_MAP.get(request.job.upper())
        if not job_enum:
            return {"success": False, "error": f"Invalid job: {request.job}"}
        
        # Get job preset for base stats
        job_preset = get_job_preset(job_enum)
        
        # Sum stats from gear (simplified - actual implementation would
        # use the full stat calculation pipeline)
        total_int = job_preset.base_int
        total_mnd = job_preset.base_mnd
        total_mab = 0
        total_mdmg = 0
        total_macc = 0
        total_mbb = 0
        total_mbb_ii = 0
        total_ele_skill = job_preset.elemental_skill
        total_dark_skill = job_preset.dark_skill
        total_enf_skill = job_preset.enfeebling_skill
        total_fc = 0
        
        # This is a placeholder - actual implementation would parse gear stats
        # from request.gearset and sum them properly
        
        # Get spell info if provided
        spell_info = None
        if request.spell_name:
            spell = get_spell(request.spell_name)
            if spell:
                spell_info = {
                    "name": spell.name,
                    "element": spell.element.name,
                    "magic_type": spell.magic_type.name,
                }
        
        return {
            "success": True,
            "stats": {
                "job": request.job.upper(),
                "sub_job": request.sub_job.upper(),
                "master_level": request.master_level,
                
                "primary_stats": {
                    "INT": total_int,
                    "MND": total_mnd,
                },
                
                "magic_offense": {
                    "magic_attack_bonus": total_mab,
                    "magic_damage": total_mdmg,
                    "magic_accuracy": total_macc,
                },
                
                "magic_burst": {
                    "mbb_gear": total_mbb,
                    "mbb_gear_capped": min(total_mbb, 4000),
                    "mbb_ii": total_mbb_ii,
                    "mbb_trait": job_preset.mbb_trait,
                    "mbb_total_effective": min(total_mbb, 4000) + total_mbb_ii + job_preset.mbb_trait,
                },
                
                "skills": {
                    "elemental": total_ele_skill,
                    "dark": total_dark_skill,
                    "enfeebling": total_enf_skill,
                },
                
                "fast_cast": total_fc,
                "fast_cast_capped": min(total_fc, 8000),
                
                "spell_info": spell_info,
            }
        }
    
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}
"""


# =============================================================================
# SECTION 7: HELPER FUNCTION FOR MAGIC BUFF CONVERSION
# =============================================================================

def convert_magic_buffs_to_caster_stats(
    ui_buffs: Dict[str, List[str]],
    food: str = "",
) -> Dict[str, int]:
    """
    Convert UI-format magic buffs to stat bonuses.
    
    Args:
        ui_buffs: {"geo": ["Geo-Acumen"], "cor": ["Wizard's Roll XI"], ...}
        food: Food name
    
    Returns:
        Dict of stat bonuses to apply to CasterStats
    """
    bonuses = {
        "INT": 0,
        "MND": 0,
        "magic_attack": 0,
        "magic_accuracy": 0,
        "magic_attack_pct": 0,  # Percentage MAB (like Geo-Acumen)
    }
    
    # Process GEO magic buffs
    if "geo" in ui_buffs:
        for buff in ui_buffs["geo"]:
            if buff in MAGIC_BUFF_ADDITIONS.get("geo_magic", {}):
                b = MAGIC_BUFF_ADDITIONS["geo_magic"][buff]
                bonuses["magic_attack"] += b.get("magic_attack", 0)
                bonuses["magic_accuracy"] += b.get("magic_accuracy", 0)
                bonuses["magic_attack_pct"] += b.get("magic_attack_pct", 0)
    
    # Process COR magic rolls
    if "cor" in ui_buffs:
        for buff in ui_buffs["cor"]:
            if buff in MAGIC_BUFF_ADDITIONS.get("cor_magic", {}):
                b = MAGIC_BUFF_ADDITIONS["cor_magic"][buff]
                bonuses["magic_attack"] += b.get("magic_attack", 0)
                bonuses["magic_accuracy"] += b.get("magic_accuracy", 0)
    
    # Process food
    if food and food in MAGIC_BUFF_ADDITIONS.get("food_magic", {}):
        f = MAGIC_BUFF_ADDITIONS["food_magic"][food]
        bonuses["INT"] += f.get("INT", 0)
        bonuses["MND"] += f.get("MND", 0)
        bonuses["magic_attack"] += f.get("magic_attack", 0)
        bonuses["magic_accuracy"] += f.get("magic_accuracy", 0)
    
    return bonuses
