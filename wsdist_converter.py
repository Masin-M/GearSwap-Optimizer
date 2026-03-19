"""
wsdist Converter

Converts parsed item data from the internal Stats/ItemInstance format
to wsdist-compatible gear dictionaries.

wsdist uses a different representation for percentage stats:
- Internal: basis points (800 = 8%)
- wsdist: integer percent (8)

This module handles the conversion and format differences.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import re


# Weapon skill type ID to name mapping (from FFXI)
SKILL_TYPE_NAMES = {
    0: "None",
    1: "Hand-to-Hand",
    2: "Dagger",
    3: "Sword",
    4: "Great Sword",
    5: "Axe",
    6: "Great Axe",
    7: "Scythe",
    8: "Polearm",
    9: "Katana",
    10: "Great Katana",
    11: "Club",
    12: "Staff",
    25: "Archery",
    26: "Marksmanship",
    27: "Throwing",
}


# wsdist skill name mapping (some differ from FFXI internal names)
WSDIST_SKILL_NAMES = {
    "Hand-to-Hand": "Hand-to-Hand",
    "Dagger": "Dagger",
    "Sword": "Sword",
    "Great Sword": "Great Sword",
    "Axe": "Axe",
    "Great Axe": "Great Axe",
    "Scythe": "Scythe",
    "Polearm": "Polearm",
    "Katana": "Katana",
    "Great Katana": "Great Katana",
    "Club": "Club",
    "Staff": "Staff",
    "Archery": "Archery",
    "Marksmanship": "Marksmanship",
    "Throwing": "Throwing",
}


def get_skill_type_name(skill_id: int) -> str:
    """Get the skill type name from skill ID."""
    return SKILL_TYPE_NAMES.get(skill_id, "None")


def _extract_path_letter_from_item(item) -> Optional[str]:
    """
    Extract the path letter (A/B/C/D) from an item's augments_raw list.

    Returns the uppercase path letter, or None if no path augment is found.
    """
    augments_raw = getattr(item, 'augments_raw', None)
    if not augments_raw:
        return None
    for aug in augments_raw:
        if not isinstance(aug, str):
            continue
        # Matches "Path: B", "Path:A", "Path A", etc.
        match = re.search(r'Path[:\s]+([A-Da-d])', aug)
        if match:
            return match.group(1).upper()
    return None


def _merge_stats(base_stats, extra_stats) -> Any:
    """
    Return a new Stats object that is the element-wise sum of base_stats and
    extra_stats.

    Both arguments must be Stats dataclass instances.  Scalar int/float fields
    are summed directly; the ``special_effects`` list is concatenated.
    ``skill_bonuses`` (if present) is taken from base_stats unchanged because
    path augments do not affect weapon-skill bonus entries.
    """
    # Lazy import to avoid circular dependencies at module load time.
    from models import Stats

    merged = Stats()
    for field_name in Stats.__dataclass_fields__:
        if field_name in ('skill_bonuses', 'special_effects'):
            continue
        base_val = getattr(base_stats, field_name, 0) or 0
        extra_val = getattr(extra_stats, field_name, 0) or 0
        setattr(merged, field_name, base_val + extra_val)

    # Preserve skill_bonuses from base (path augments never change these)
    if hasattr(base_stats, 'skill_bonuses'):
        merged.skill_bonuses = base_stats.skill_bonuses

    # Concatenate special-effect strings from both sides
    base_fx = list(getattr(base_stats, 'special_effects', None) or [])
    extra_fx = list(getattr(extra_stats, 'special_effects', None) or [])
    merged.special_effects = base_fx + extra_fx

    return merged


def to_wsdist_gear(item, augment_string: str = "") -> Dict[str, Any]:
    """
    Convert a parsed item (ItemInstance or ItemBase) to wsdist-compatible gear dict.
    
    This handles the unit conversion from internal basis points to wsdist's
    integer percentage format.
    
    Args:
        item: ItemInstance or ItemBase object with parsed stats
        augment_string: Optional augment path/rank string for Name2
        
    Returns:
        Dictionary in wsdist gear format
    """
    # Handle both ItemInstance and ItemBase
    augments_raw = None
    if hasattr(item, 'total_stats'):
        # ItemInstance
        stats = item.total_stats
        base = item.base
        name = item.name
        # Get raw augments for Lua output
        augments_raw = getattr(item, 'augments_raw', None)

        # ------------------------------------------------------------------
        # Path augment stat injection
        # ------------------------------------------------------------------
        # Path-augmented items (e.g. Nyame Helm Path B) carry extra stats
        # that are NOT parsed from the item's text description — they live
        # in the path augment database (augment_tables.json).
        # If the item is a path item with a non-zero rank, look up the bonus
        # Stats from the database and merge them into our working stats object
        # so that every downstream consumer (wsdist dict, beam-search scorer)
        # sees the full stat picture.
        if getattr(item, 'has_path_augment', False) and getattr(item, 'rank', 0) > 0:
            path_letter = _extract_path_letter_from_item(item)
            item_base_id = getattr(base, 'id', None)
            if path_letter and item_base_id is not None:
                try:
                    # Lazy import keeps the module loadable even when the DB
                    # file is absent (non-fatal warning already handled inside
                    # PathAugmentDatabase.load()).
                    from path_augment_db import get_path_augment_db
                    db = get_path_augment_db()
                    if db.is_loaded:
                        path_stats = db.get_path_stats(
                            item_base_id, path_letter, item.rank
                        )
                        if path_stats is not None:
                            stats = _merge_stats(stats, path_stats)
                except Exception:
                    # Never let a DB miss crash the conversion pipeline.
                    pass
    elif hasattr(item, 'base_stats'):
        # ItemBase
        stats = item.base_stats
        base = item
        name = item.name
    else:
        raise ValueError(f"Unknown item type: {type(item)}")
    
    # Build the Name2 field (unique identifier with augments)
    # If we have raw augments, include them in Name2 for uniqueness
    if augment_string:
        name2 = f"{name} {augment_string}"
    elif augments_raw:
        # Build a condensed augment string for Name2
        aug_parts = []
        for aug in augments_raw:
            if aug and aug != 'none' and aug != '':
                if isinstance(aug, str):
                    aug_parts.append(aug)
        if aug_parts:
            # Use semicolon-joined augments for Name2 uniqueness
            name2 = f"{name} ({'; '.join(aug_parts)})"
        else:
            name2 = name
    else:
        name2 = name
    
    # Get job list from bitmask
    jobs = _extract_jobs(base.jobs if hasattr(base, 'jobs') else 0)
    
    # Build augments list for Lua output (filter out empty/none values)
    augments_list = None
    if augments_raw:
        augments_list = [
            aug for aug in augments_raw 
            if aug and aug != 'none' and aug != '' and isinstance(aug, str)
        ]
        if not augments_list:
            augments_list = None
    
    gear = {
        "Name": name,
        "Name2": name2,
        "Jobs": jobs,
        
        # =====================================================================
        # PRIMARY STATS (no conversion needed)
        # =====================================================================
        "STR": stats.STR,
        "DEX": stats.DEX,
        "VIT": stats.VIT,
        "AGI": stats.AGI,
        "INT": stats.INT,
        "MND": stats.MND,
        "CHR": stats.CHR,
        
        # =====================================================================
        # HP/MP (no conversion)
        # =====================================================================
        "HP": stats.HP,
        "MP": stats.MP,
        
        # =====================================================================
        # DIRECT STATS (no conversion needed)
        # =====================================================================
        "Accuracy": stats.accuracy,
        "Attack": stats.attack,
        "Ranged Accuracy": stats.ranged_accuracy,
        "Ranged Attack": stats.ranged_attack,
        "Magic Accuracy": stats.magic_accuracy,
        "Magic Attack": stats.magic_attack,
        "Magic Damage": stats.magic_damage,
        "Evasion": stats.evasion,
        "Magic Evasion": stats.magic_evasion,
        "Magic Defense": stats.magic_defense,
        "Defense": stats.defense,
        
        # =====================================================================
        # CONVERT: basis points (×100) to integer %
        # =====================================================================
        "Gear Haste": stats.gear_haste // 100,
        "DA": stats.double_attack // 100,
        "TA": stats.triple_attack // 100,
        "QA": stats.quad_attack // 100,
        "Dual Wield": stats.dual_wield // 100,
        "Crit Rate": stats.crit_rate // 100,
        "Crit Damage": stats.crit_damage // 100,
        "Weapon Skill Damage": stats.ws_damage // 100,
        "DT": stats.damage_taken // 100,
        "PDT": stats.physical_dt // 100,
        "MDT": stats.magical_dt // 100,
        "Magic Burst Damage": stats.magic_burst_bonus // 100,
        "Magic Burst Damage II": stats.magic_burst_damage_ii // 100,
        "PDL": stats.pdl // 100,
        "Skillchain Bonus": stats.skillchain_bonus // 100,
        "Fast Cast": stats.fast_cast // 100,
        "Cure Potency": stats.cure_potency // 100,
        
        # =====================================================================
        # STORE TP (NOT basis points - just integer)
        # =====================================================================
        "Store TP": stats.store_tp,
        
        # =====================================================================
        # TP-SPECIFIC STATS (integer values)
        # =====================================================================
        "TP Bonus": stats.tp_bonus,
        "Daken": stats.daken,
        "Martial Arts": stats.martial_arts,
        "Zanshin": stats.zanshin,
        "Kick Attacks": stats.kick_attacks,
        "Subtle Blow": stats.subtle_blow,
        "Subtle Blow II": stats.subtle_blow_ii,
        "Fencer": stats.fencer,
        "Conserve TP": stats.conserve_tp,
        "Regain": stats.regain,
        
        # =====================================================================
        # OCCASIONAL ATTACKS (integer %)
        # =====================================================================
        "OA2": stats.oa2,
        "OA3": stats.oa3,
        "OA4": stats.oa4,
        "OA5": stats.oa5,
        "OA6": stats.oa6,
        "OA7": stats.oa7,
        "OA8": stats.oa8,
        "FUA": stats.fua,
        
        # =====================================================================
        # RANGED-SPECIFIC (integer values)
        # =====================================================================
        "Double Shot": stats.double_shot,
        "Triple Shot": stats.triple_shot,
        "True Shot": stats.true_shot,
        "Recycle": stats.recycle,
        "Barrage": stats.barrage,
        
        # =====================================================================
        # MAGIC SKILL (integer values)
        # =====================================================================
        "Magic Accuracy Skill": stats.magic_accuracy_skill,
        
        # =====================================================================
        # WEAPON SKILLS (gear bonuses)
        # =====================================================================
        "Hand-to-Hand Skill": stats.hand_to_hand_skill,
        "Dagger Skill": stats.dagger_skill,
        "Sword Skill": stats.sword_skill,
        "Great Sword Skill": stats.great_sword_skill,
        "Axe Skill": stats.axe_skill,
        "Great Axe Skill": stats.great_axe_skill,
        "Scythe Skill": stats.scythe_skill,
        "Polearm Skill": stats.polearm_skill,
        "Katana Skill": stats.katana_skill,
        "Great Katana Skill": stats.great_katana_skill,
        "Club Skill": stats.club_skill,
        "Staff Skill": stats.staff_skill,
        "Archery Skill": stats.archery_skill,
        "Marksmanship Skill": stats.marksmanship_skill,
        "Throwing Skill": stats.throwing_skill,
        
        # =====================================================================
        # MAGIC SKILLS (gear bonuses)
        # =====================================================================
        "Healing Magic Skill": stats.healing_magic_skill,
        "Enfeebling Magic Skill": stats.enfeebling_magic_skill,
        "Enhancing Magic Skill": stats.enhancing_magic_skill,
        "Elemental Magic Skill": stats.elemental_magic_skill,
        "Divine Magic Skill": stats.divine_magic_skill,
        "Dark Magic Skill": stats.dark_magic_skill,
        "Singing Skill": stats.singing_skill,
        "Ninjutsu Skill": stats.ninjutsu_skill,
        "Blue Magic Skill": stats.blue_magic_skill,
        "Summoning Skill": stats.summoning_magic_skill,
        
        # =====================================================================
        # JOB-SPECIFIC (convert basis points where applicable)
        # =====================================================================
        "EnSpell Damage": stats.enspell_damage,
        "EnSpell Damage%": stats.enspell_damage_pct // 100,
        "Ninjutsu Magic Attack": stats.ninjutsu_magic_attack,
        "Ninjutsu Damage%": stats.ninjutsu_damage_pct // 100,
        "Blood Pact Damage": stats.blood_pact_damage // 100,
        "Occult Acumen": stats.occult_acumen,
        
        # =====================================================================
        # ELEMENTAL BONUSES
        # =====================================================================
        "Fire Elemental Bonus": stats.fire_elemental_bonus,
        "Ice Elemental Bonus": stats.ice_elemental_bonus,
        "Wind Elemental Bonus": stats.wind_elemental_bonus,
        "Earth Elemental Bonus": stats.earth_elemental_bonus,
        "Lightning Elemental Bonus": stats.lightning_elemental_bonus,
        "Water Elemental Bonus": stats.water_elemental_bonus,
        "Light Elemental Bonus": stats.light_elemental_bonus,
        "Dark Elemental Bonus": stats.dark_elemental_bonus,
    }
    
    # =========================================================================
    # WEAPON-SPECIFIC FIELDS
    # =========================================================================
    if stats.damage > 0 or stats.delay > 0:
        gear["DMG"] = stats.damage
        gear["Delay"] = stats.delay

        # Determine the correct Type string using slot bitmask.
        # create_player checks:
        #   gearset["ranged"].get("Type") in ["Gun","Bow","Crossbow"]
        #   gearset["ammo"].get("Type")   in ["Bullet","Arrow","Bolt","Shuriken"]
        # Getting this wrong zeroes out Ranged Attack and Ranged Accuracy.
        #
        # FFXI slot bitmasks: MAIN=1, SUB=2, RANGE=4, AMMO=8
        slots = base.slots if hasattr(base, 'slots') else 0
        skill_id = base.skill if hasattr(base, 'skill') else 0
        is_range_slot = bool(slots & 4)   # equips in RANGE slot → bow/gun
        is_ammo_slot  = bool(slots & 8)   # equips in AMMO slot  → arrow/bolt/shuriken

        if is_ammo_slot:
            if skill_id == 27:   # Throwing
                gear["Type"] = "Shuriken"
            elif skill_id == 26: # Marksmanship
                gear["Type"] = "Bolt"
            else:                # Archery (25) or fallback
                gear["Type"] = "Arrow"
        elif is_range_slot:
            if skill_id == 26:   # Marksmanship → Gun (covers Crossbow)
                gear["Type"] = "Gun"
            else:                # Archery (25) or fallback
                gear["Type"] = "Bow"
        else:
            gear["Type"] = "Weapon"  # Melee weapon in MAIN or SUB slot

        # Skill Type string used by create_player for Attack/Accuracy
        if skill_id > 0:
            gear["Skill Type"] = get_skill_type_name(skill_id)
    else:
        # Determine Type for non-weapons based on slot and item_type
        slots = base.slots if hasattr(base, 'slots') else 0
        item_type = base.item_type if hasattr(base, 'item_type') else 0
        
        # SUB slot only (not MAIN) = Shield or Grip
        # SLOT_BITMASK: MAIN=1, SUB=2
        is_sub_only = (slots & 2) and not (slots & 1)
        
        if is_sub_only:
            if item_type == 5:  # Armor category (includes shields)
                gear["Type"] = "Shield"
            elif item_type == 4:  # Ranged/Throwing category (grips when no damage)
                gear["Type"] = "Grip"
        elif slots > 0:
            # Other equipment (armor)
            gear["Type"] = "Armor"
    
    # =========================================================================
    # Remove zero values to keep dict clean (except essential fields)
    # =========================================================================
    essential_fields = {"Name", "Name2", "Jobs", "Type", "Skill Type", "DMG", "Delay"}
    gear = {k: v for k, v in gear.items() 
            if (v != 0 and v is not None) or k in essential_fields}
    
    # Add augments as metadata field (underscore prefix so wsdist ignores it)
    # wsdist sums all numeric values, so we can't use "augments" directly
    if augments_list:
        gear["_augments"] = augments_list
    
    return gear


def _extract_jobs(job_bitmask: int) -> List[str]:
    """
    Extract job abbreviations from a job bitmask.
    
    Args:
        job_bitmask: Bitmask where bit N = job ID N can equip
        
    Returns:
        List of lowercase job abbreviations (e.g., ["war", "nin", "sam"])
    """
    if job_bitmask == 0:
        # All jobs
        return ["war", "mnk", "whm", "blm", "rdm", "thf", "pld", "drk", 
                "bst", "brd", "rng", "smn", "sam", "nin", "drg", "blu", 
                "cor", "pup", "dnc", "sch", "geo", "run"]
    
    job_names = [
        None,   # 0 - None
        "war",  # 1
        "mnk",  # 2
        "whm",  # 3
        "blm",  # 4
        "rdm",  # 5
        "thf",  # 6
        "pld",  # 7
        "drk",  # 8
        "bst",  # 9
        "brd",  # 10
        "rng",  # 11
        "sam",  # 12
        "nin",  # 13
        "drg",  # 14
        "smn",  # 15
        "blu",  # 16
        "cor",  # 17
        "pup",  # 18
        "dnc",  # 19
        "sch",  # 20
        "geo",  # 21
        "run",  # 22
    ]
    
    jobs = []
    for i in range(1, len(job_names)):
        if job_bitmask & (1 << i):
            jobs.append(job_names[i])
    
    return jobs if jobs else ["all"]


def batch_convert_to_wsdist(items: List[Any]) -> List[Dict[str, Any]]:
    """
    Convert a list of items to wsdist format.
    
    Args:
        items: List of ItemInstance or ItemBase objects
        
    Returns:
        List of wsdist-compatible gear dictionaries
    """
    return [to_wsdist_gear(item) for item in items]


def format_wsdist_output(gear_list: List[Dict[str, Any]], 
                         variable_name: str = "gear") -> str:
    """
    Format a list of wsdist gear dicts as Python code.
    
    Args:
        gear_list: List of gear dictionaries
        variable_name: Variable name for the output
        
    Returns:
        Python code string defining the gear list
    """
    lines = [f"{variable_name} = ["]
    
    for gear in gear_list:
        # Format each gear dict as a Python dict literal
        items = []
        for key, value in gear.items():
            if isinstance(value, str):
                items.append(f'"{key}": "{value}"')
            elif isinstance(value, list):
                items.append(f'"{key}": {value}')
            else:
                items.append(f'"{key}": {value}')
        
        lines.append("    {" + ", ".join(items) + "},")
    
    lines.append("]")
    
    return "\n".join(lines)
