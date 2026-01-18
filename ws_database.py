"""
Weaponskill Database

Contains weaponskill formulas, stat modifiers, and optimization profiles.
Based on data from bg-wiki and player testing.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


class WeaponType(Enum):
    """Weapon types in FFXI."""
    HAND_TO_HAND = "Hand-to-Hand"
    DAGGER = "Dagger"
    SWORD = "Sword"
    GREAT_SWORD = "Great Sword"
    AXE = "Axe"
    GREAT_AXE = "Great Axe"
    SCYTHE = "Scythe"
    POLEARM = "Polearm"
    KATANA = "Katana"
    GREAT_KATANA = "Great Katana"
    CLUB = "Club"
    STAFF = "Staff"
    ARCHERY = "Archery"
    MARKSMANSHIP = "Marksmanship"


class WSType(Enum):
    """Weaponskill damage type."""
    PHYSICAL = "Physical"
    MAGICAL = "Magical"
    HYBRID = "Hybrid"


@dataclass
class WeaponskillData:
    """Data for a single weaponskill."""
    name: str
    weapon_type: WeaponType
    ws_type: WSType
    
    # Stat modifiers (as percentages, e.g., 50 = 50%)
    stat_modifiers: Dict[str, int]  # e.g., {"STR": 50, "MND": 50}
    
    # fTP values at 1000/2000/3000 TP
    ftp: Tuple[float, float, float]
    
    # Number of hits
    hits: int = 1
    
    # Does fTP replicate to all hits?
    ftp_replicating: bool = False
    
    # Can this WS crit?
    can_crit: bool = False
    
    # Crit rate bonus from TP (basis points at 1000/2000/3000)
    crit_rate_tp: Optional[Tuple[int, int, int]] = None
    
    # Element (for hybrid/magical)
    element: Optional[str] = None
    
    # Skillchain properties
    skillchain: List[str] = field(default_factory=list)
    
    # Special notes
    notes: str = ""
    
    def get_stat_weights(self, include_attack: bool = True) -> Dict[str, float]:
        """
        Calculate recommended stat weights for this WS.
        
        Returns weights suitable for optimization.
        """
        weights = {}
        
        # Base stat modifiers - higher modifier = higher weight
        # The α correction (0.85) is already factored into base damage
        for stat, pct in self.stat_modifiers.items():
            # Weight based on modifier percentage
            # 50% mod = weight of ~2.0, 80% mod = weight of ~3.0
            weights[stat] = pct / 25.0
        
        # Attack is always valuable for physical WS
        if self.ws_type in (WSType.PHYSICAL, WSType.HYBRID) and include_attack:
            weights['attack'] = 1.5
        
        # Accuracy is important
        weights['accuracy'] = 1.0
        
        # WS damage bonus is very powerful
        weights['ws_damage'] = 10.0
        
        # Multi-hit WS benefit more from multi-attack
        if self.hits >= 2 and not self.ftp_replicating:
            weights['double_attack'] = 3.0
            weights['triple_attack'] = 4.5
            weights['quad_attack'] = 6.0
        
        # Crit rate/damage for WS that can crit
        if self.can_crit:
            weights['crit_rate'] = 4.0
            weights['crit_damage'] = 5.0
        
        # Magic stats for magical/hybrid
        if self.ws_type == WSType.MAGICAL:
            weights['magic_attack'] = 5.0
            weights['INT'] = weights.get('INT', 0) + 2.0
        elif self.ws_type == WSType.HYBRID:
            weights['magic_attack'] = 3.0
        
        return weights


# =============================================================================
# WEAPONSKILL DATABASE
# =============================================================================

WEAPONSKILLS: Dict[str, WeaponskillData] = {
    # -------------------------------------------------------------------------
    # SWORD
    # -------------------------------------------------------------------------
    "Savage Blade": WeaponskillData(
        name="Savage Blade",
        weapon_type=WeaponType.SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "MND": 50},
        ftp=(4.0, 10.25, 13.75),
        hits=2,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Fragmentation", "Scission"],
        notes="High fTP scaling with TP. Naegling/Kaja Sword add +15% WS damage."
    ),
    
    "Chant du Cygne": WeaponskillData(
        name="Chant du Cygne",
        weapon_type=WeaponType.SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 80},
        ftp=(2.25, 2.25, 2.25),
        hits=3,
        ftp_replicating=True,
        can_crit=True,
        crit_rate_tp=(1500, 2500, 4000),  # +15/25/40% crit rate
        skillchain=["Light", "Distortion"],
        notes="Empyrean WS. fTP replicates. Stack crit rate/damage and DEX."
    ),
    
    "Requiescat": WeaponskillData(
        name="Requiescat",
        weapon_type=WeaponType.SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"MND": 73},
        ftp=(1.0, 1.0, 1.0),
        hits=5,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Gravitation", "Scission"],
        notes="Ignores defense. Best at low attack vs high def targets."
    ),
    
    "Expiacion": WeaponskillData(
        name="Expiacion",
        weapon_type=WeaponType.SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 30, "INT": 30, "DEX": 20},
        ftp=(3.75, 7.5, 10.0),
        hits=3,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Distortion", "Scission"],
        notes="Tizona mythic WS. High base fTP."
    ),
    
    "Death Blossom": WeaponskillData(
        name="Death Blossom",
        weapon_type=WeaponType.SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"MND": 50, "STR": 30},
        ftp=(2.0, 2.0, 2.0),
        hits=3,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Fragmentation", "Distortion"],
        notes="Cannot critical hit."
    ),
    
    "Fast Blade": WeaponskillData(
        name="Fast Blade",
        weapon_type=WeaponType.SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 20, "DEX": 20},
        ftp=(1.0, 1.0, 1.0),
        hits=2,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Scission"],
        notes="Basic sword WS."
    ),
    
    "Fast Blade II": WeaponskillData(
        name="Fast Blade II",
        weapon_type=WeaponType.SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 30, "DEX": 30},
        ftp=(2.0, 2.0, 2.0),
        hits=2,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Scission"],
        notes="Ambuscade sword WS. fTP replicates."
    ),
    
    "Burning Blade": WeaponskillData(
        name="Burning Blade",
        weapon_type=WeaponType.SWORD,
        ws_type=WSType.HYBRID,
        stat_modifiers={"STR": 40, "INT": 40},
        ftp=(1.0, 1.5, 2.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Fire",
        skillchain=["Liquefaction"],
        notes="Basic hybrid fire sword WS."
    ),
    
    "Swift Blade": WeaponskillData(
        name="Swift Blade",
        weapon_type=WeaponType.SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "MND": 50},
        ftp=(1.5, 1.5, 1.5),
        hits=3,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Gravitation"],
        notes="3-hit fTP replicating."
    ),
    
    "Knights of Round": WeaponskillData(
        name="Knights of Round",
        weapon_type=WeaponType.SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"MND": 40, "STR": 40},
        ftp=(2.75, 2.75, 2.75),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Light", "Fusion"],
        notes="Excalibur relic WS."
    ),
    
    "Imperator": WeaponskillData(
        name="Imperator",
        weapon_type=WeaponType.SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 60, "MND": 40},
        ftp=(4.0, 4.0, 4.0),
        hits=3,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Detonation", "Compression", "Distortion"],
        notes="Prime WS. 3-hit fTP replicating."
    ),

    # -------------------------------------------------------------------------
    # DAGGER
    # -------------------------------------------------------------------------
    "Rudra's Storm": WeaponskillData(
        name="Rudra's Storm",
        weapon_type=WeaponType.DAGGER,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 80},
        ftp=(6.0, 15.0, 19.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,  # Cannot crit unless forced
        skillchain=["Darkness", "Distortion"],
        notes="Empyrean WS. Extremely high fTP scaling. Best with SA/TA or forced crit."
    ),
    
    "Evisceration": WeaponskillData(
        name="Evisceration",
        weapon_type=WeaponType.DAGGER,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 50},
        ftp=(1.25, 1.25, 1.25),
        hits=5,
        ftp_replicating=True,
        can_crit=True,
        crit_rate_tp=(1000, 1500, 2000),  # +10/15/20% crit rate
        skillchain=["Gravitation", "Transfixion"],
        notes="Multi-hit crit WS. Good for TP spam."
    ),
    
    "Aeolian Edge": WeaponskillData(
        name="Aeolian Edge",
        weapon_type=WeaponType.DAGGER,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"DEX": 28, "INT": 28},
        ftp=(2.0, 3.0, 4.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Wind",
        skillchain=["Impaction", "Scission", "Detonation"],
        notes="Magical WS. Affected by MAB/magic damage."
    ),
    
    "Mandalic Stab": WeaponskillData(
        name="Mandalic Stab",
        weapon_type=WeaponType.DAGGER,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 60},
        ftp=(4.0, 6.09, 8.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Fusion", "Compression"],
        notes="Carnwenhan mythic WS."
    ),
    
    "Exenterator": WeaponskillData(
        name="Exenterator",
        weapon_type=WeaponType.DAGGER,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"AGI": 73, "INT": 15},
        ftp=(1.0, 1.0, 1.0),
        hits=4,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Fragmentation", "Scission"],
        notes="First hit has +100% attack bonus."
    ),
    
    "Viper Bite": WeaponskillData(
        name="Viper Bite",
        weapon_type=WeaponType.DAGGER,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 100},
        ftp=(1.0, 1.0, 1.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Scission"],
        notes="Basic dagger WS. Adds Poison effect."
    ),
    
    "Dancing Edge": WeaponskillData(
        name="Dancing Edge",
        weapon_type=WeaponType.DAGGER,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 40, "CHR": 40},
        ftp=(1.1875, 1.1875, 1.1875),
        hits=5,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Scission", "Detonation"],
        notes="Multi-hit WS. Accuracy varies with TP."
    ),
    
    "Shark Bite": WeaponskillData(
        name="Shark Bite",
        weapon_type=WeaponType.DAGGER,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 40, "AGI": 40},
        ftp=(4.5, 6.8, 8.5),
        hits=2,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Fragmentation"],
        notes="High fTP scaling."
    ),
    
    "Mercy Stroke": WeaponskillData(
        name="Mercy Stroke",
        weapon_type=WeaponType.DAGGER,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 80},
        ftp=(5.0, 5.0, 5.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Darkness", "Gravitation"],
        notes="Relic WS. Extra damage on low HP targets."
    ),
    
    "Ruthless Stroke": WeaponskillData(
        name="Ruthless Stroke",
        weapon_type=WeaponType.DAGGER,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 60, "AGI": 40},
        ftp=(4.0, 4.0, 4.0),
        hits=5,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Liquefaction", "Impaction", "Fragmentation"],
        notes="Prime WS. 5-hit fTP replicating."
    ),

    # -------------------------------------------------------------------------
    # GREAT SWORD
    # -------------------------------------------------------------------------
    "Resolution": WeaponskillData(
        name="Resolution",
        weapon_type=WeaponType.GREAT_SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 85},
        ftp=(1.0, 3.0, 5.0),
        hits=5,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Fragmentation", "Scission"],
        notes="Multi-hit with high STR mod. ACC varies with TP."
    ),
    
    "Torcleaver": WeaponskillData(
        name="Torcleaver",
        weapon_type=WeaponType.GREAT_SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"VIT": 80},
        ftp=(4.75, 7.5, 10.0),
        hits=1,
        ftp_replicating=False,
        can_crit=True,
        crit_rate_tp=(2000, 3500, 5000),
        skillchain=["Light", "Distortion", "Scission"],
        notes="Empyrean WS. High fTP, can crit."
    ),
    
    "Scourge": WeaponskillData(
        name="Scourge",
        weapon_type=WeaponType.GREAT_SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 40, "VIT": 40},
        ftp=(3.0, 3.0, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Light", "Fusion"],
        notes="Ragnarok relic WS."
    ),
    
    "Hard Slash": WeaponskillData(
        name="Hard Slash",
        weapon_type=WeaponType.GREAT_SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 100},
        ftp=(1.0, 1.0, 1.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Scission"],
        notes="Basic great sword WS."
    ),
    
    "Freezebite": WeaponskillData(
        name="Freezebite",
        weapon_type=WeaponType.GREAT_SWORD,
        ws_type=WSType.HYBRID,
        stat_modifiers={"STR": 40, "INT": 40},
        ftp=(1.0, 2.0, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Ice",
        skillchain=["Detonation", "Induration"],
        notes="Hybrid ice damage."
    ),
    
    "Shockwave": WeaponskillData(
        name="Shockwave",
        weapon_type=WeaponType.GREAT_SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 100},
        ftp=(1.125, 1.125, 1.125),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Reverberation"],
        notes="AoE WS. Dispels target."
    ),
    
    "Sickle Moon": WeaponskillData(
        name="Sickle Moon",
        weapon_type=WeaponType.GREAT_SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "AGI": 50},
        ftp=(2.5625, 2.5625, 2.5625),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Scission", "Impaction"],
        notes="Accuracy varies with TP."
    ),
    
    "Spinning Slash": WeaponskillData(
        name="Spinning Slash",
        weapon_type=WeaponType.GREAT_SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 100},
        ftp=(1.5, 1.5, 1.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Fragmentation"],
        notes="AoE WS."
    ),
    
    "Ground Strike": WeaponskillData(
        name="Ground Strike",
        weapon_type=WeaponType.GREAT_SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "INT": 50},
        ftp=(3.0, 5.5, 8.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Fragmentation", "Distortion"],
        notes="High fTP scaling."
    ),
    
    "Herculean Slash": WeaponskillData(
        name="Herculean Slash",
        weapon_type=WeaponType.GREAT_SWORD,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"VIT": 80},
        ftp=(2.0, 2.5, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Ice",
        skillchain=["Detonation", "Induration", "Impaction"],
        notes="Magical ice damage. Paralyzes target."
    ),
    
    "Fimbulvetr": WeaponskillData(
        name="Fimbulvetr",
        weapon_type=WeaponType.GREAT_SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 60, "VIT": 40},
        ftp=(4.0, 4.0, 4.0),
        hits=3,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Detonation", "Compression", "Distortion"],
        notes="Prime WS. 3-hit fTP replicating."
    ),

    # -------------------------------------------------------------------------
    # GREAT KATANA
    # -------------------------------------------------------------------------
    "Tachi: Fudo": WeaponskillData(
        name="Tachi: Fudo",
        weapon_type=WeaponType.GREAT_KATANA,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 80},
        ftp=(3.75, 5.75, 8.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Light", "Distortion"],
        notes="Empyrean WS. High damage, creates Light SC."
    ),
    
    "Tachi: Shoha": WeaponskillData(
        name="Tachi: Shoha",
        weapon_type=WeaponType.GREAT_KATANA,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 73, "MND": 15},
        ftp=(1.375, 1.375, 1.375),
        hits=2,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Fragmentation", "Compression"],
        notes="Good for building TP. fTP replicates."
    ),
    
    "Tachi: Kaiten": WeaponskillData(
        name="Tachi: Kaiten",
        weapon_type=WeaponType.GREAT_KATANA,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 80},
        ftp=(3.0, 3.0, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Light", "Fragmentation"],
        notes="Good base damage. Masamune adds WS damage."
    ),
    
    "Tachi: Rana": WeaponskillData(
        name="Tachi: Rana",
        weapon_type=WeaponType.GREAT_KATANA,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50},
        ftp=(1.0, 1.0, 1.0),
        hits=3,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Gravitation", "Distortion"],
        notes="Kogarasumaru mythic WS."
    ),
    
    "Tachi: Enpi": WeaponskillData(
        name="Tachi: Enpi",
        weapon_type=WeaponType.GREAT_KATANA,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 60},
        ftp=(1.0, 1.5, 2.0),
        hits=2,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Transfixion", "Scission"],
        notes="Basic great katana WS."
    ),
    
    "Tachi: Goten": WeaponskillData(
        name="Tachi: Goten",
        weapon_type=WeaponType.GREAT_KATANA,
        ws_type=WSType.HYBRID,
        stat_modifiers={"STR": 60},
        ftp=(0.5, 1.5, 2.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Thunder",
        skillchain=["Transfixion", "Impaction"],
        notes="Hybrid thunder damage."
    ),
    
    "Tachi: Kagero": WeaponskillData(
        name="Tachi: Kagero",
        weapon_type=WeaponType.GREAT_KATANA,
        ws_type=WSType.HYBRID,
        stat_modifiers={"STR": 75},
        ftp=(0.5, 1.5, 2.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Fire",
        skillchain=["Liquefaction"],
        notes="Hybrid fire damage."
    ),
    
    "Tachi: Jinpu": WeaponskillData(
        name="Tachi: Jinpu",
        weapon_type=WeaponType.GREAT_KATANA,
        ws_type=WSType.HYBRID,
        stat_modifiers={"STR": 30, "INT": 30},
        ftp=(0.5, 2.0, 4.0),
        hits=2,
        ftp_replicating=False,
        can_crit=False,
        element="Wind",
        skillchain=["Scission", "Detonation"],
        notes="Hybrid wind damage."
    ),
    
    "Tachi: Koki": WeaponskillData(
        name="Tachi: Koki",
        weapon_type=WeaponType.GREAT_KATANA,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"STR": 30, "MND": 30},
        ftp=(1.0, 2.0, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Light",
        skillchain=["Transfixion", "Compression"],
        notes="Magical light damage."
    ),
    
    "Tachi: Yukikaze": WeaponskillData(
        name="Tachi: Yukikaze",
        weapon_type=WeaponType.GREAT_KATANA,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 75},
        ftp=(1.5625, 2.6875, 4.125),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Detonation", "Induration", "Impaction"],
        notes="Attack varies with TP. Blinds target."
    ),
    
    "Tachi: Gekko": WeaponskillData(
        name="Tachi: Gekko",
        weapon_type=WeaponType.GREAT_KATANA,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 75},
        ftp=(1.5625, 2.6875, 4.125),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Distortion", "Reverberation"],
        notes="Attack varies with TP. Silences target."
    ),
    
    "Tachi: Kasha": WeaponskillData(
        name="Tachi: Kasha",
        weapon_type=WeaponType.GREAT_KATANA,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 75},
        ftp=(1.5625, 2.6875, 4.125),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Fusion", "Compression"],
        notes="Attack varies with TP. Binds target."
    ),
    
    "Tachi: Ageha": WeaponskillData(
        name="Tachi: Ageha",
        weapon_type=WeaponType.GREAT_KATANA,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"CHR": 60, "STR": 40},
        ftp=(2.0, 2.0, 2.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Compression", "Scission"],
        notes="Dispels target. Accuracy varies with TP."
    ),
    
    "Tachi: Mumei": WeaponskillData(
        name="Tachi: Mumei",
        weapon_type=WeaponType.GREAT_KATANA,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 60, "MND": 40},
        ftp=(4.0, 4.0, 4.0),
        hits=3,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Darkness", "Gravitation"],
        notes="Prime WS. 3-hit fTP replicating."
    ),

    # -------------------------------------------------------------------------
    # KATANA
    # -------------------------------------------------------------------------
    "Blade: Shun": WeaponskillData(
        name="Blade: Shun",
        weapon_type=WeaponType.KATANA,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 73, "CHR": 15},
        ftp=(1.0, 1.0, 1.0),
        hits=5,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Fusion", "Impaction"],
        notes="Multi-hit. Good for TP building."
    ),
    
    "Blade: Hi": WeaponskillData(
        name="Blade: Hi",
        weapon_type=WeaponType.KATANA,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"AGI": 80},
        ftp=(5.0, 5.0, 5.0),
        hits=1,
        ftp_replicating=False,
        can_crit=True,
        crit_rate_tp=(1000, 1500, 2000),
        skillchain=["Darkness", "Gravitation"],
        notes="Empyrean WS. High fTP, can crit. Kannagi adds WS damage."
    ),
    
    "Blade: Metsu": WeaponskillData(
        name="Blade: Metsu",
        weapon_type=WeaponType.KATANA,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 80},
        ftp=(5.0, 5.0, 5.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Darkness", "Fragmentation"],
        notes="Nagi mythic WS. Very high single-hit damage."
    ),
    
    "Blade: Retsu": WeaponskillData(
        name="Blade: Retsu",
        weapon_type=WeaponType.KATANA,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 60, "STR": 20},
        ftp=(0.5, 1.5, 2.5),
        hits=2,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Scission"],
        notes="Basic katana WS. Adds Paralysis effect."
    ),
    
    "Blade: Teki": WeaponskillData(
        name="Blade: Teki",
        weapon_type=WeaponType.KATANA,
        ws_type=WSType.HYBRID,
        stat_modifiers={"STR": 30, "INT": 30},
        ftp=(0.5, 1.375, 2.25),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Water",
        skillchain=["Reverberation"],
        notes="Hybrid water damage."
    ),
    
    "Blade: To": WeaponskillData(
        name="Blade: To",
        weapon_type=WeaponType.KATANA,
        ws_type=WSType.HYBRID,
        stat_modifiers={"STR": 40, "INT": 40},
        ftp=(0.5, 1.5, 2.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Ice",
        skillchain=["Induration", "Detonation"],
        notes="Hybrid ice damage."
    ),
    
    "Blade: Chi": WeaponskillData(
        name="Blade: Chi",
        weapon_type=WeaponType.KATANA,
        ws_type=WSType.HYBRID,
        stat_modifiers={"STR": 30, "INT": 30},
        ftp=(0.5, 1.375, 2.25),
        hits=2,
        ftp_replicating=False,
        can_crit=False,
        element="Earth",
        skillchain=["Transfixion", "Impaction"],
        notes="Hybrid earth damage."
    ),
    
    "Blade: Ei": WeaponskillData(
        name="Blade: Ei",
        weapon_type=WeaponType.KATANA,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"STR": 40, "INT": 40},
        ftp=(1.0, 3.0, 5.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Dark",
        skillchain=["Compression"],
        notes="Magical dark damage. Drains HP."
    ),
    
    "Blade: Jin": WeaponskillData(
        name="Blade: Jin",
        weapon_type=WeaponType.KATANA,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 40, "STR": 40},
        ftp=(1.375, 1.375, 1.375),
        hits=3,
        ftp_replicating=True,
        can_crit=True,
        crit_rate_tp=(1000, 1500, 2000),
        skillchain=["Detonation", "Impaction"],
        notes="Multi-hit crit WS."
    ),
    
    "Blade: Ten": WeaponskillData(
        name="Blade: Ten",
        weapon_type=WeaponType.KATANA,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 30, "DEX": 30},
        ftp=(4.5, 7.5, 10.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Gravitation", "Transfixion"],
        notes="High fTP scaling."
    ),
    
    "Blade: Ku": WeaponskillData(
        name="Blade: Ku",
        weapon_type=WeaponType.KATANA,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 30, "INT": 30},
        ftp=(1.25, 1.25, 1.25),
        hits=5,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Gravitation", "Transfixion"],
        notes="Multi-hit WS. Accuracy varies with TP."
    ),
    
    "Blade: Yu": WeaponskillData(
        name="Blade: Yu",
        weapon_type=WeaponType.KATANA,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"DEX": 40, "INT": 40},
        ftp=(2.0, 3.5, 5.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Water",
        skillchain=["Reverberation", "Impaction"],
        notes="Magical water damage."
    ),
    
    "Blade: Kamu": WeaponskillData(
        name="Blade: Kamu",
        weapon_type=WeaponType.KATANA,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 60, "INT": 60},
        ftp=(1.0, 1.0, 1.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Fragmentation", "Compression"],
        notes="Kikoku mythic WS. Reduces enemy defense."
    ),
    
    "Zesho Meppo": WeaponskillData(
        name="Zesho Meppo",
        weapon_type=WeaponType.KATANA,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 50, "CHR": 50},
        ftp=(3.0, 3.0, 3.0),
        hits=8,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Darkness", "Gravitation"],
        notes="Prime WS. 8-hit fTP replicating."
    ),

    # -------------------------------------------------------------------------
    # AXE
    # -------------------------------------------------------------------------
    "Decimation": WeaponskillData(
        name="Decimation",
        weapon_type=WeaponType.AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "VIT": 50},
        ftp=(1.75, 1.75, 1.75),
        hits=3,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Fusion", "Reverberation"],
        notes="Multi-hit. fTP replicates."
    ),
    
    "Ruinator": WeaponskillData(
        name="Ruinator",
        weapon_type=WeaponType.AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 73, "VIT": 15},
        ftp=(1.33, 1.33, 1.33),
        hits=4,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Distortion", "Detonation"],
        notes="Farsha mythic WS."
    ),
    
    "Cloudsplitter": WeaponskillData(
        name="Cloudsplitter",
        weapon_type=WeaponType.AXE,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"STR": 40, "MND": 40},
        ftp=(2.25, 4.5, 7.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Lightning",
        skillchain=["Darkness", "Fragmentation"],
        notes="Empyrean magical WS."
    ),
    
    "Raging Axe": WeaponskillData(
        name="Raging Axe",
        weapon_type=WeaponType.AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 100},
        ftp=(1.0, 1.0, 1.0),
        hits=2,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Detonation", "Impaction"],
        notes="Basic axe WS."
    ),
    
    "Spinning Axe": WeaponskillData(
        name="Spinning Axe",
        weapon_type=WeaponType.AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 100},
        ftp=(1.5, 1.5, 1.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Impaction", "Scission"],
        notes="Basic AoE axe WS."
    ),
    
    "Rampage": WeaponskillData(
        name="Rampage",
        weapon_type=WeaponType.AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50},
        ftp=(1.0, 1.0, 1.0),
        hits=5,
        ftp_replicating=True,
        can_crit=True,
        crit_rate_tp=(1500, 2500, 4000),
        skillchain=["Scission"],
        notes="5-hit WS with crit rate scaling."
    ),
    
    "Calamity": WeaponskillData(
        name="Calamity",
        weapon_type=WeaponType.AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "VIT": 50},
        ftp=(3.0, 4.25, 6.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Scission", "Impaction"],
        notes="High fTP scaling."
    ),
    
    "Mistral Axe": WeaponskillData(
        name="Mistral Axe",
        weapon_type=WeaponType.AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50},
        ftp=(3.5, 5.0, 7.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Fusion", "Scission"],
        notes="High fTP scaling."
    ),
    
    "Bora Axe": WeaponskillData(
        name="Bora Axe",
        weapon_type=WeaponType.AXE,
        ws_type=WSType.HYBRID,
        stat_modifiers={"DEX": 60, "INT": 40},
        ftp=(1.0, 2.0, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Wind",
        skillchain=["Scission", "Detonation"],
        notes="Hybrid wind damage."
    ),
    
    "Onslaught": WeaponskillData(
        name="Onslaught",
        weapon_type=WeaponType.AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 80},
        ftp=(3.0, 3.0, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Darkness", "Gravitation"],
        notes="Guttler relic WS."
    ),
    
    "Primal Rend": WeaponskillData(
        name="Primal Rend",
        weapon_type=WeaponType.AXE,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"CHR": 60, "MND": 40},
        ftp=(2.0, 2.5, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Light",
        skillchain=["Gravitation", "Reverberation"],
        notes="Aymur mythic WS. Magical light damage."
    ),
    
    "Blitz": WeaponskillData(
        name="Blitz",
        weapon_type=WeaponType.AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 60, "VIT": 40},
        ftp=(3.5, 3.5, 3.5),
        hits=4,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Liquefaction", "Impaction", "Fragmentation"],
        notes="Prime WS. 4-hit fTP replicating."
    ),

    # -------------------------------------------------------------------------
    # GREAT AXE
    # -------------------------------------------------------------------------
    "Ukko's Fury": WeaponskillData(
        name="Ukko's Fury",
        weapon_type=WeaponType.GREAT_AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 80},
        ftp=(3.0, 3.0, 3.0),
        hits=2,
        ftp_replicating=True,
        can_crit=True,
        crit_rate_tp=(3500, 5500, 7000),
        skillchain=["Light", "Fragmentation"],
        notes="Empyrean WS. Very high crit rate scaling. Top tier damage."
    ),
    
    "Upheaval": WeaponskillData(
        name="Upheaval",
        weapon_type=WeaponType.GREAT_AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"VIT": 73},
        ftp=(1.0, 3.5, 6.5),
        hits=4,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Fusion", "Compression"],
        notes="Multi-hit with high VIT mod."
    ),
    
    "Raging Rush": WeaponskillData(
        name="Raging Rush",
        weapon_type=WeaponType.GREAT_AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "VIT": 50},
        ftp=(1.0, 1.0, 1.0),
        hits=3,
        ftp_replicating=True,
        can_crit=True,
        crit_rate_tp=(3500, 5000, 6500),
        skillchain=["Induration", "Reverberation"],
        notes="fTP replicates. Crit rate varies with TP."
    ),
    
    "Iron Tempest": WeaponskillData(
        name="Iron Tempest",
        weapon_type=WeaponType.GREAT_AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 100},
        ftp=(1.0, 1.0, 1.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Scission"],
        notes="Basic great axe WS."
    ),
    
    "Shield Break": WeaponskillData(
        name="Shield Break",
        weapon_type=WeaponType.GREAT_AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"VIT": 100},
        ftp=(1.0, 1.0, 1.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Impaction"],
        notes="Reduces target evasion."
    ),
    
    "Armor Break": WeaponskillData(
        name="Armor Break",
        weapon_type=WeaponType.GREAT_AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 60, "VIT": 60},
        ftp=(1.0, 1.0, 1.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Impaction"],
        notes="Reduces target defense."
    ),
    
    "Weapon Break": WeaponskillData(
        name="Weapon Break",
        weapon_type=WeaponType.GREAT_AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"VIT": 100},
        ftp=(1.0, 1.0, 1.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Impaction"],
        notes="Reduces target attack."
    ),
    
    "Full Break": WeaponskillData(
        name="Full Break",
        weapon_type=WeaponType.GREAT_AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"VIT": 100},
        ftp=(1.5, 1.5, 1.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Distortion"],
        notes="Reduces all target stats."
    ),
    
    "Steel Cyclone": WeaponskillData(
        name="Steel Cyclone",
        weapon_type=WeaponType.GREAT_AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "VIT": 50},
        ftp=(2.25, 2.25, 2.25),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Distortion", "Detonation"],
        notes="AoE great axe WS."
    ),
    
    "Metatron Torment": WeaponskillData(
        name="Metatron Torment",
        weapon_type=WeaponType.GREAT_AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 80},
        ftp=(5.0, 5.0, 5.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Light", "Fusion"],
        notes="Bravura relic WS."
    ),
    
    "King's Justice": WeaponskillData(
        name="King's Justice",
        weapon_type=WeaponType.GREAT_AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "VIT": 50},
        ftp=(2.0, 4.125, 6.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Fragmentation", "Scission"],
        notes="High fTP scaling."
    ),
    
    "Disaster": WeaponskillData(
        name="Disaster",
        weapon_type=WeaponType.GREAT_AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 60, "VIT": 40},
        ftp=(4.0, 4.0, 4.0),
        hits=3,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Detonation", "Compression", "Distortion"],
        notes="Prime WS. 3-hit fTP replicating."
    ),

    # -------------------------------------------------------------------------
    # POLEARM
    # -------------------------------------------------------------------------
    "Stardiver": WeaponskillData(
        name="Stardiver",
        weapon_type=WeaponType.POLEARM,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 73, "VIT": 15},
        ftp=(0.75, 0.75, 0.75),
        hits=4,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Gravitation", "Transfixion"],
        notes="Multi-hit with high STR mod."
    ),
    
    "Camlann's Torment": WeaponskillData(
        name="Camlann's Torment",
        weapon_type=WeaponType.POLEARM,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 60, "VIT": 60},
        ftp=(3.0, 3.0, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Light", "Distortion"],
        notes="Empyrean WS. High stat mods."
    ),
    
    "Impulse Drive": WeaponskillData(
        name="Impulse Drive",
        weapon_type=WeaponType.POLEARM,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 100},
        ftp=(1.0, 3.0, 5.5),
        hits=2,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Gravitation", "Induration"],
        notes="Very high STR mod. Damage varies with TP."
    ),
    
    "Double Thrust": WeaponskillData(
        name="Double Thrust",
        weapon_type=WeaponType.POLEARM,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 30, "DEX": 30},
        ftp=(1.0, 1.0, 1.0),
        hits=2,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Transfixion"],
        notes="Basic polearm WS."
    ),
    
    "Thunder Thrust": WeaponskillData(
        name="Thunder Thrust",
        weapon_type=WeaponType.POLEARM,
        ws_type=WSType.HYBRID,
        stat_modifiers={"STR": 40, "INT": 40},
        ftp=(1.0, 2.0, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Thunder",
        skillchain=["Impaction", "Transfixion"],
        notes="Hybrid thunder damage."
    ),
    
    "Raiden Thrust": WeaponskillData(
        name="Raiden Thrust",
        weapon_type=WeaponType.POLEARM,
        ws_type=WSType.HYBRID,
        stat_modifiers={"STR": 40, "INT": 40},
        ftp=(1.0, 2.5, 4.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Thunder",
        skillchain=["Impaction", "Transfixion"],
        notes="Stronger hybrid thunder damage."
    ),
    
    "Penta Thrust": WeaponskillData(
        name="Penta Thrust",
        weapon_type=WeaponType.POLEARM,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 20, "DEX": 20},
        ftp=(1.0, 1.0, 1.0),
        hits=5,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Compression", "Transfixion"],
        notes="5-hit fTP replicating."
    ),
    
    "Wheeling Thrust": WeaponskillData(
        name="Wheeling Thrust",
        weapon_type=WeaponType.POLEARM,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 80},
        ftp=(1.75, 1.75, 1.75),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Fusion"],
        notes="Ignores defense. Defense varies with TP."
    ),
    
    "Sonic Thrust": WeaponskillData(
        name="Sonic Thrust",
        weapon_type=WeaponType.POLEARM,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 100},
        ftp=(2.0, 2.0, 2.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Scission", "Transfixion"],
        notes="AoE polearm WS."
    ),
    
    "Geirskogul": WeaponskillData(
        name="Geirskogul",
        weapon_type=WeaponType.POLEARM,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 80},
        ftp=(3.5, 3.5, 3.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Light", "Distortion"],
        notes="Gungnir relic WS."
    ),
    
    "Drakesbane": WeaponskillData(
        name="Drakesbane",
        weapon_type=WeaponType.POLEARM,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50},
        ftp=(1.0, 1.0, 1.0),
        hits=4,
        ftp_replicating=True,
        can_crit=True,
        crit_rate_tp=(1000, 2000, 3500),
        skillchain=["Fusion", "Transfixion"],
        notes="Ryunohige mythic WS. 4-hit crit WS."
    ),
    
    "Diarmuid": WeaponskillData(
        name="Diarmuid",
        weapon_type=WeaponType.POLEARM,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 60, "DEX": 40},
        ftp=(3.5, 3.5, 3.5),
        hits=4,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Detonation", "Compression", "Distortion"],
        notes="Prime WS. 4-hit fTP replicating."
    ),

    # -------------------------------------------------------------------------
    # SCYTHE
    # -------------------------------------------------------------------------
    "Entropy": WeaponskillData(
        name="Entropy",
        weapon_type=WeaponType.SCYTHE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"INT": 73, "MND": 15},
        ftp=(1.0, 1.0, 1.0),
        hits=4,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Gravitation", "Reverberation"],
        notes="Unique INT/MND mods for scythe."
    ),
    
    "Quietus": WeaponskillData(
        name="Quietus",
        weapon_type=WeaponType.SCYTHE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 60, "MND": 60},
        ftp=(3.0, 3.0, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Darkness", "Distortion"],
        notes="Empyrean WS. High stat mods."
    ),
    
    "Insurgency": WeaponskillData(
        name="Insurgency",
        weapon_type=WeaponType.SCYTHE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 20, "INT": 20},
        ftp=(0.5, 0.5, 0.5),
        hits=4,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Compression", "Reverberation"],
        notes="Liberator mythic WS."
    ),
    
    "Cross Reaper": WeaponskillData(
        name="Cross Reaper",
        weapon_type=WeaponType.SCYTHE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 60, "MND": 60},
        ftp=(2.0, 2.0, 2.0),
        hits=2,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Distortion", "Detonation"],
        notes="Multi-hit with fTP replicating."
    ),
    
    "Spiral Hell": WeaponskillData(
        name="Spiral Hell",
        weapon_type=WeaponType.SCYTHE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "INT": 50},
        ftp=(1.375, 1.375, 1.375),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Distortion", "Scission"],
        notes="Standard scythe WS."
    ),
    
    "Infernal Scythe": WeaponskillData(
        name="Infernal Scythe",
        weapon_type=WeaponType.SCYTHE,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"INT": 70, "MND": 30},
        ftp=(2.0, 2.5, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Dark",
        skillchain=["Shadow", "Reverberation"],
        notes="Magical dark damage scythe WS."
    ),
    
    "Slice": WeaponskillData(
        name="Slice",
        weapon_type=WeaponType.SCYTHE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 100},
        ftp=(1.0, 1.0, 1.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Scission"],
        notes="Basic scythe WS."
    ),
    
    "Dark Harvest": WeaponskillData(
        name="Dark Harvest",
        weapon_type=WeaponType.SCYTHE,
        ws_type=WSType.HYBRID,
        stat_modifiers={"STR": 40, "INT": 40},
        ftp=(1.0, 1.5, 2.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Dark",
        skillchain=["Reverberation"],
        notes="Hybrid dark damage."
    ),
    
    "Shadow of Death": WeaponskillData(
        name="Shadow of Death",
        weapon_type=WeaponType.SCYTHE,
        ws_type=WSType.HYBRID,
        stat_modifiers={"STR": 40, "INT": 40},
        ftp=(1.0, 2.0, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Dark",
        skillchain=["Induration", "Reverberation"],
        notes="Stronger hybrid dark damage."
    ),
    
    "Nightmare Scythe": WeaponskillData(
        name="Nightmare Scythe",
        weapon_type=WeaponType.SCYTHE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 60, "MND": 60},
        ftp=(1.25, 1.25, 1.25),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Compression", "Scission"],
        notes="Sleep effect."
    ),
    
    "Spinning Scythe": WeaponskillData(
        name="Spinning Scythe",
        weapon_type=WeaponType.SCYTHE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 100},
        ftp=(1.5, 1.5, 1.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Reverberation"],
        notes="AoE scythe WS."
    ),
    
    "Guillotine": WeaponskillData(
        name="Guillotine",
        weapon_type=WeaponType.SCYTHE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 25, "MND": 25},
        ftp=(1.0, 1.0, 1.0),
        hits=4,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Induration"],
        notes="4-hit fTP replicating. Silence effect."
    ),
    
    "Catastrophe": WeaponskillData(
        name="Catastrophe",
        weapon_type=WeaponType.SCYTHE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 40, "INT": 40},
        ftp=(2.75, 2.75, 2.75),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Gravitation", "Reverberation"],
        notes="Apocalypse relic WS. Drains HP."
    ),
    
    "Origin": WeaponskillData(
        name="Origin",
        weapon_type=WeaponType.SCYTHE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 60, "INT": 40},
        ftp=(3.5, 3.5, 3.5),
        hits=4,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Detonation", "Compression", "Distortion"],
        notes="Prime WS. 4-hit fTP replicating."
    ),

    # -------------------------------------------------------------------------
    # CLUB
    # -------------------------------------------------------------------------
    "Black Halo": WeaponskillData(
        name="Black Halo",
        weapon_type=WeaponType.CLUB,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 70, "MND": 30},
        ftp=(5.5, 10.0, 13.5),
        hits=2,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Fragmentation", "Compression"],
        notes="Very high fTP scaling. Maxentius adds WS damage."
    ),
    
    "Realmrazer": WeaponskillData(
        name="Realmrazer",
        weapon_type=WeaponType.CLUB,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"MND": 73, "VIT": 15},
        ftp=(1.0, 1.0, 1.0),
        hits=5,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Fusion", "Impaction"],
        notes="Multi-hit MND WS."
    ),
    
    "Judgement": WeaponskillData(
        name="Judgement",
        weapon_type=WeaponType.CLUB,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"MND": 50, "STR": 30},
        ftp=(3.0, 4.25, 7.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Light", "Impaction"],
        notes="Light skillchain."
    ),
    
    "Hexa Strike": WeaponskillData(
        name="Hexa Strike",
        weapon_type=WeaponType.CLUB,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "MND": 50},
        ftp=(1.0, 1.0, 1.0),
        hits=6,
        ftp_replicating=True,
        can_crit=True,
        crit_rate_tp=(1500, 2500, 3500),
        skillchain=["Fusion", "Impaction"],
        notes="6-hit WS with crit chance."
    ),
    
    "Mystic Boon": WeaponskillData(
        name="Mystic Boon",
        weapon_type=WeaponType.CLUB,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"MND": 100},
        ftp=(1.0, 2.0, 3.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Fusion", "Compression"],
        notes="Converts damage to MP. Yagrush mythic WS."
    ),
    
    "Dagan": WeaponskillData(
        name="Dagan",
        weapon_type=WeaponType.CLUB,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"CHR": 80},
        ftp=(1.0, 1.0, 1.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Light"],
        notes="Empyrean WS. Restores HP/MP to party."
    ),
    
    "Randgrith": WeaponskillData(
        name="Randgrith",
        weapon_type=WeaponType.CLUB,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 40, "MND": 40},
        ftp=(3.0, 3.0, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Light", "Fragmentation"],
        notes="Mjollnir relic WS."
    ),
    
    "Flash Nova": WeaponskillData(
        name="Flash Nova",
        weapon_type=WeaponType.CLUB,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"MND": 50, "STR": 30},
        ftp=(2.0, 2.5, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Light",
        skillchain=["Compression", "Reverberation"],
        notes="Magical light damage."
    ),
    
    "Seraph Strike": WeaponskillData(
        name="Seraph Strike",
        weapon_type=WeaponType.CLUB,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"STR": 40, "MND": 40},
        ftp=(1.0, 2.0, 2.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Light",
        skillchain=["Impaction", "Scission"],
        notes="Basic magical light club WS."
    ),
    
    "Shining Strike": WeaponskillData(
        name="Shining Strike",
        weapon_type=WeaponType.CLUB,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"STR": 40, "MND": 40},
        ftp=(1.0, 1.5, 2.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Light",
        skillchain=["Impaction"],
        notes="Basic magical light club WS."
    ),
    
    "Skullbreaker": WeaponskillData(
        name="Skullbreaker",
        weapon_type=WeaponType.CLUB,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 100},
        ftp=(1.0, 1.0, 1.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Induration", "Reverberation"],
        notes="Stuns target."
    ),
    
    "True Strike": WeaponskillData(
        name="True Strike",
        weapon_type=WeaponType.CLUB,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 100},
        ftp=(1.5, 1.5, 1.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Detonation", "Impaction"],
        notes="Ignores defense. Defense varies with TP."
    ),
    
    "Exudation": WeaponskillData(
        name="Exudation",
        weapon_type=WeaponType.CLUB,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"MND": 60, "INT": 40},
        ftp=(2.0, 2.0, 2.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Induration", "Reverberation"],
        notes="Chatoyant staff mythic WS. Drains HP/MP."
    ),
    
    "Dagda": WeaponskillData(
        name="Dagda",
        weapon_type=WeaponType.CLUB,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"MND": 60, "CHR": 40},
        ftp=(4.0, 4.0, 4.0),
        hits=3,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Liquefaction", "Impaction", "Fragmentation"],
        notes="Prime WS. 3-hit fTP replicating."
    ),

    # -------------------------------------------------------------------------
    # HAND-TO-HAND
    # -------------------------------------------------------------------------
    "Victory Smite": WeaponskillData(
        name="Victory Smite",
        weapon_type=WeaponType.HAND_TO_HAND,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 80},
        ftp=(3.0, 3.0, 3.0),
        hits=4,
        ftp_replicating=True,
        can_crit=True,
        crit_rate_tp=(4000, 6000, 8000),
        skillchain=["Light", "Fragmentation"],
        notes="Empyrean WS. Very high crit rate. Top tier damage."
    ),
    
    "Shijin Spiral": WeaponskillData(
        name="Shijin Spiral",
        weapon_type=WeaponType.HAND_TO_HAND,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 73, "CHR": 15},
        ftp=(1.5, 1.5, 1.5),
        hits=5,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Fusion", "Reverberation"],
        notes="Multi-hit DEX WS."
    ),
    
    "Howling Fist": WeaponskillData(
        name="Howling Fist",
        weapon_type=WeaponType.HAND_TO_HAND,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"VIT": 50, "STR": 20},
        ftp=(2.05, 2.05, 2.05),
        hits=2,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Impaction", "Transfixion"],
        notes="fTP replicates."
    ),
    
    "Combo": WeaponskillData(
        name="Combo",
        weapon_type=WeaponType.HAND_TO_HAND,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 100},
        ftp=(1.0, 1.0, 1.0),
        hits=3,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Impaction"],
        notes="Basic H2H WS."
    ),
    
    "One Inch Punch": WeaponskillData(
        name="One Inch Punch",
        weapon_type=WeaponType.HAND_TO_HAND,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"VIT": 100},
        ftp=(1.0, 1.0, 1.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Compression"],
        notes="Ignores defense based on TP."
    ),
    
    "Raging Fists": WeaponskillData(
        name="Raging Fists",
        weapon_type=WeaponType.HAND_TO_HAND,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 30, "DEX": 30},
        ftp=(1.0, 1.0, 1.0),
        hits=5,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Impaction"],
        notes="5-hit fTP replicating."
    ),
    
    "Backhand Blow": WeaponskillData(
        name="Backhand Blow",
        weapon_type=WeaponType.HAND_TO_HAND,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "DEX": 50},
        ftp=(1.75, 1.75, 1.75),
        hits=1,
        ftp_replicating=False,
        can_crit=True,
        crit_rate_tp=(1000, 2000, 3500),
        skillchain=["Detonation"],
        notes="Crit rate varies with TP."
    ),
    
    "Spinning Attack": WeaponskillData(
        name="Spinning Attack",
        weapon_type=WeaponType.HAND_TO_HAND,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 100},
        ftp=(1.0, 1.0, 1.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Liquefaction", "Impaction"],
        notes="AoE H2H WS."
    ),
    
    "Dragon Kick": WeaponskillData(
        name="Dragon Kick",
        weapon_type=WeaponType.HAND_TO_HAND,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "DEX": 50},
        ftp=(2.0, 2.0, 2.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Fragmentation"],
        notes="Kick attack WS."
    ),
    
    "Asuran Fists": WeaponskillData(
        name="Asuran Fists",
        weapon_type=WeaponType.HAND_TO_HAND,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 15, "VIT": 15},
        ftp=(1.25, 1.25, 1.25),
        hits=8,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Gravitation", "Liquefaction"],
        notes="8-hit fTP replicating. Accuracy varies with TP."
    ),
    
    "Tornado Kick": WeaponskillData(
        name="Tornado Kick",
        weapon_type=WeaponType.HAND_TO_HAND,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 40, "VIT": 40},
        ftp=(1.69, 1.69, 1.69),
        hits=3,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Detonation", "Induration", "Impaction"],
        notes="Kick attack WS. 3-hit fTP replicating."
    ),
    
    "Ascetic's Fury": WeaponskillData(
        name="Ascetic's Fury",
        weapon_type=WeaponType.HAND_TO_HAND,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "VIT": 50},
        ftp=(1.5, 1.5, 1.5),
        hits=2,
        ftp_replicating=True,
        can_crit=True,
        crit_rate_tp=(3000, 4500, 6000),
        skillchain=["Fusion", "Transfixion"],
        notes="Glanzfaust mythic WS. Crit WS."
    ),
    
    "Stringing Pummel": WeaponskillData(
        name="Stringing Pummel",
        weapon_type=WeaponType.HAND_TO_HAND,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 32, "VIT": 32},
        ftp=(1.0, 1.0, 1.0),
        hits=6,
        ftp_replicating=True,
        can_crit=True,
        crit_rate_tp=(2500, 3500, 5000),
        skillchain=["Gravitation", "Liquefaction"],
        notes="Kenkonken mythic WS. 6-hit crit WS."
    ),
    
    "Final Heaven": WeaponskillData(
        name="Final Heaven",
        weapon_type=WeaponType.HAND_TO_HAND,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"VIT": 60},
        ftp=(3.0, 3.0, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Light", "Fusion"],
        notes="Spharai relic WS."
    ),
    
    "Maru Kala": WeaponskillData(
        name="Maru Kala",
        weapon_type=WeaponType.HAND_TO_HAND,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "VIT": 50},
        ftp=(3.5, 3.5, 3.5),
        hits=4,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Detonation", "Compression", "Distortion"],
        notes="Prime WS. 4-hit fTP replicating."
    ),

    # -------------------------------------------------------------------------
    # STAFF
    # -------------------------------------------------------------------------
    "Shattersoul": WeaponskillData(
        name="Shattersoul",
        weapon_type=WeaponType.STAFF,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"INT": 73, "MND": 15},
        ftp=(1.375, 1.375, 1.375),
        hits=3,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Gravitation", "Reverberation"],
        notes="Multi-hit INT WS. Also lowers target MDB."
    ),
    
    "Cataclysm": WeaponskillData(
        name="Cataclysm",
        weapon_type=WeaponType.STAFF,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"STR": 30, "INT": 30},
        ftp=(2.75, 2.75, 2.75),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Dark",
        skillchain=["Compression", "Reverberation"],
        notes="Magical dark damage."
    ),
    
    "Heavy Swing": WeaponskillData(
        name="Heavy Swing",
        weapon_type=WeaponType.STAFF,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 100},
        ftp=(1.0, 1.0, 1.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Impaction"],
        notes="Basic staff WS."
    ),
    
    "Rock Crusher": WeaponskillData(
        name="Rock Crusher",
        weapon_type=WeaponType.STAFF,
        ws_type=WSType.HYBRID,
        stat_modifiers={"STR": 40, "INT": 40},
        ftp=(1.0, 1.5, 2.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Earth",
        skillchain=["Impaction"],
        notes="Hybrid earth damage."
    ),
    
    "Earth Crusher": WeaponskillData(
        name="Earth Crusher",
        weapon_type=WeaponType.STAFF,
        ws_type=WSType.HYBRID,
        stat_modifiers={"STR": 40, "INT": 40},
        ftp=(1.0, 2.0, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Earth",
        skillchain=["Detonation", "Impaction"],
        notes="AoE hybrid earth damage."
    ),
    
    "Starburst": WeaponskillData(
        name="Starburst",
        weapon_type=WeaponType.STAFF,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"STR": 40, "MND": 40},
        ftp=(1.0, 2.0, 2.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Light",
        skillchain=["Compression", "Reverberation"],
        notes="Magical light damage."
    ),
    
    "Sunburst": WeaponskillData(
        name="Sunburst",
        weapon_type=WeaponType.STAFF,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"STR": 40, "MND": 40},
        ftp=(1.0, 2.5, 4.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Light",
        skillchain=["Transfixion", "Reverberation"],
        notes="Stronger magical light damage."
    ),
    
    "Shell Crusher": WeaponskillData(
        name="Shell Crusher",
        weapon_type=WeaponType.STAFF,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 100},
        ftp=(1.0, 1.0, 1.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Detonation"],
        notes="Lowers target magic defense."
    ),
    
    "Full Swing": WeaponskillData(
        name="Full Swing",
        weapon_type=WeaponType.STAFF,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "MND": 50},
        ftp=(2.0, 2.0, 2.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Liquefaction", "Impaction"],
        notes="AoE staff WS."
    ),
    
    "Retribution": WeaponskillData(
        name="Retribution",
        weapon_type=WeaponType.STAFF,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "MND": 50},
        ftp=(2.0, 4.0, 7.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Gravitation", "Reverberation"],
        notes="High fTP scaling."
    ),
    
    "Gate of Tartarus": WeaponskillData(
        name="Gate of Tartarus",
        weapon_type=WeaponType.STAFF,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"CHR": 80},
        ftp=(2.0, 2.0, 2.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Darkness", "Distortion"],
        notes="Claustrum relic WS."
    ),
    
    "Omniscience": WeaponskillData(
        name="Omniscience",
        weapon_type=WeaponType.STAFF,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"MND": 80},
        ftp=(2.0, 2.5, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Dark",
        skillchain=["Gravitation", "Transfixion"],
        notes="Tupsimati mythic WS. Lowers target magic defense."
    ),
    
    "Vidohunir": WeaponskillData(
        name="Vidohunir",
        weapon_type=WeaponType.STAFF,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"INT": 80},
        ftp=(3.0, 3.0, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Dark",
        skillchain=["Darkness", "Gravitation"],
        notes="Laevateinn mythic WS."
    ),
    
    "Myrkr": WeaponskillData(
        name="Myrkr",
        weapon_type=WeaponType.STAFF,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"MND": 80},
        ftp=(1.0, 1.0, 1.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Fragmentation", "Compression"],
        notes="Empyrean WS. Converts HP to MP."
    ),
    
    "Oshala": WeaponskillData(
        name="Oshala",
        weapon_type=WeaponType.STAFF,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"INT": 60, "MND": 40},
        ftp=(3.5, 3.5, 3.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Light",
        skillchain=["Liquefaction", "Impaction", "Fragmentation"],
        notes="Prime WS. Magical light damage."
    ),

    # -------------------------------------------------------------------------
    # MARKSMANSHIP / ARCHERY
    # -------------------------------------------------------------------------
    "Wildfire": WeaponskillData(
        name="Wildfire",
        weapon_type=WeaponType.MARKSMANSHIP,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"AGI": 60},
        ftp=(6.0, 6.85, 7.75),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Fire",
        skillchain=["Darkness", "Gravitation"],
        notes="Empyrean magical WS. Armageddon adds WS damage."
    ),
    
    "Last Stand": WeaponskillData(
        name="Last Stand",
        weapon_type=WeaponType.MARKSMANSHIP,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"AGI": 73},
        ftp=(2.0, 2.0, 2.0),
        hits=2,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Fusion", "Reverberation"],
        notes="Multi-hit ranged WS."
    ),
    
    "Trueflight": WeaponskillData(
        name="Trueflight",
        weapon_type=WeaponType.MARKSMANSHIP,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"AGI": 50, "MND": 50},
        ftp=(4.0, 4.5, 5.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Light",
        skillchain=["Fragmentation", "Scission"],
        notes="Magical light damage."
    ),
    
    "Hot Shot": WeaponskillData(
        name="Hot Shot",
        weapon_type=WeaponType.MARKSMANSHIP,
        ws_type=WSType.HYBRID,
        stat_modifiers={"AGI": 70, "INT": 30},
        ftp=(1.0, 2.0, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Fire",
        skillchain=["Liquefaction"],
        notes="Hybrid fire damage."
    ),
    
    "Split Shot": WeaponskillData(
        name="Split Shot",
        weapon_type=WeaponType.MARKSMANSHIP,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"AGI": 100},
        ftp=(1.0, 1.0, 1.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Transfixion"],
        notes="Basic marksmanship WS."
    ),
    
    "Sniper Shot": WeaponskillData(
        name="Sniper Shot",
        weapon_type=WeaponType.MARKSMANSHIP,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"AGI": 100},
        ftp=(1.5, 1.5, 1.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Transfixion", "Detonation"],
        notes="Lowers target defense."
    ),
    
    "Slug Shot": WeaponskillData(
        name="Slug Shot",
        weapon_type=WeaponType.MARKSMANSHIP,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"AGI": 100},
        ftp=(2.5, 3.0, 4.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Liquefaction", "Transfixion"],
        notes="High damage single shot."
    ),
    
    "Blast Shot": WeaponskillData(
        name="Blast Shot",
        weapon_type=WeaponType.MARKSMANSHIP,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"AGI": 100},
        ftp=(1.5, 1.5, 1.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Induration", "Transfixion"],
        notes="Stuns target."
    ),
    
    "Detonator": WeaponskillData(
        name="Detonator",
        weapon_type=WeaponType.MARKSMANSHIP,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"AGI": 73},
        ftp=(2.0, 2.0, 2.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Fusion", "Transfixion"],
        notes="Fomalhaut mythic WS."
    ),
    
    "Coronach": WeaponskillData(
        name="Coronach",
        weapon_type=WeaponType.MARKSMANSHIP,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 40, "AGI": 40},
        ftp=(4.0, 4.0, 4.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Darkness", "Fragmentation"],
        notes="Annihilator relic WS."
    ),
    
    "Terminus": WeaponskillData(
        name="Terminus",
        weapon_type=WeaponType.MARKSMANSHIP,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"AGI": 60, "DEX": 40},
        ftp=(4.0, 4.0, 4.0),
        hits=3,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Liquefaction", "Impaction", "Fragmentation"],
        notes="Prime WS. 3-hit fTP replicating."
    ),
    
    "Apex Arrow": WeaponskillData(
        name="Apex Arrow",
        weapon_type=WeaponType.ARCHERY,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"AGI": 73},
        ftp=(3.0, 3.0, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Fragmentation", "Transfixion"],
        notes="High damage ranged WS."
    ),
    
    "Jishnu's Radiance": WeaponskillData(
        name="Jishnu's Radiance",
        weapon_type=WeaponType.ARCHERY,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 80},
        ftp=(1.75, 1.75, 1.75),
        hits=3,
        ftp_replicating=True,
        can_crit=True,
        crit_rate_tp=(3000, 4500, 6000),
        skillchain=["Light", "Fusion"],
        notes="Empyrean WS. Multi-hit crit WS."
    ),
    
    "Flaming Arrow": WeaponskillData(
        name="Flaming Arrow",
        weapon_type=WeaponType.ARCHERY,
        ws_type=WSType.HYBRID,
        stat_modifiers={"STR": 40, "AGI": 40},
        ftp=(1.0, 1.5, 2.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Fire",
        skillchain=["Liquefaction", "Transfixion"],
        notes="Hybrid fire damage."
    ),
    
    "Piercing Arrow": WeaponskillData(
        name="Piercing Arrow",
        weapon_type=WeaponType.ARCHERY,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "AGI": 50},
        ftp=(1.5, 1.5, 1.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Reverberation", "Transfixion"],
        notes="Basic archery WS."
    ),
    
    "Dulling Arrow": WeaponskillData(
        name="Dulling Arrow",
        weapon_type=WeaponType.ARCHERY,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "AGI": 50},
        ftp=(1.5, 1.5, 1.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Liquefaction", "Transfixion"],
        notes="Lowers target defense."
    ),
    
    "Sidewinder": WeaponskillData(
        name="Sidewinder",
        weapon_type=WeaponType.ARCHERY,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "AGI": 50},
        ftp=(4.0, 5.0, 6.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Reverberation", "Transfixion", "Detonation"],
        notes="High fTP scaling."
    ),
    
    "Blast Arrow": WeaponskillData(
        name="Blast Arrow",
        weapon_type=WeaponType.ARCHERY,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 50, "AGI": 50},
        ftp=(1.5, 1.5, 1.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Induration", "Transfixion"],
        notes="Stuns target."
    ),
    
    "Empyreal Arrow": WeaponskillData(
        name="Empyreal Arrow",
        weapon_type=WeaponType.ARCHERY,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 16, "AGI": 25},
        ftp=(2.0, 2.5, 3.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Fusion", "Transfixion"],
        notes="Attack varies with TP."
    ),
    
    "Refulgent Arrow": WeaponskillData(
        name="Refulgent Arrow",
        weapon_type=WeaponType.ARCHERY,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 60, "AGI": 60},
        ftp=(5.0, 5.0, 5.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Reverberation", "Transfixion"],
        notes="High stat mods."
    ),
    
    "Namas Arrow": WeaponskillData(
        name="Namas Arrow",
        weapon_type=WeaponType.ARCHERY,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 40, "AGI": 40},
        ftp=(2.75, 2.75, 2.75),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Light", "Distortion"],
        notes="Yoichinoyumi relic WS."
    ),
    
    "Sarv": WeaponskillData(
        name="Sarv",
        weapon_type=WeaponType.ARCHERY,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"AGI": 60, "DEX": 40},
        ftp=(4.0, 4.0, 4.0),
        hits=3,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Liquefaction", "Impaction", "Fragmentation"],
        notes="Prime WS. 3-hit fTP replicating."
    ),
    
    # -------------------------------------------------------------------------
    # JOB-SPECIFIC / ADDITIONAL WEAPON SKILLS
    # -------------------------------------------------------------------------
    "Leaden Salute": WeaponskillData(
        name="Leaden Salute",
        weapon_type=WeaponType.MARKSMANSHIP,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"AGI": 73, "MND": 15},
        ftp=(4.0, 6.7, 10.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Dark",
        skillchain=["Gravitation", "Transfixion"],
        notes="COR Empyrean WS. Exceptional with Death Penalty. Affected by MAB and day/weather."
    ),
    
    "Mordant Rime": WeaponskillData(
        name="Mordant Rime",
        weapon_type=WeaponType.DAGGER,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"CHR": 85},
        ftp=(5.0, 5.0, 5.0),
        hits=2,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Fragmentation", "Distortion"],
        notes="BRD Empyrean WS. Unique CHR mod."
    ),
    
    "Dimidiation": WeaponskillData(
        name="Dimidiation",
        weapon_type=WeaponType.GREAT_SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"DEX": 80},
        ftp=(8.5, 8.5, 8.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Light", "Distortion"],
        notes="RUN Empyrean WS. Very high fTP, DEX based."
    ),
    
    "Pyrrhic Kleos": WeaponskillData(
        name="Pyrrhic Kleos",
        weapon_type=WeaponType.DAGGER,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 40, "DEX": 40},
        ftp=(2.5, 2.5, 2.5),
        hits=4,
        ftp_replicating=True,
        can_crit=False,
        skillchain=["Distortion", "Scission"],
        notes="DNC Empyrean WS. Multi-hit fTP replicating."
    ),
    
    "Spinning Attack": WeaponskillData(
        name="Spinning Attack",
        weapon_type=WeaponType.GREAT_AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 100},
        ftp=(1.5, 1.5, 1.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Liquefaction", "Scission", "Impaction"],
        notes="AoE WS. High STR mod."
    ),
    
    "Fell Cleave": WeaponskillData(
        name="Fell Cleave",
        weapon_type=WeaponType.GREAT_AXE,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 60, "VIT": 60},
        ftp=(2.75, 2.75, 2.75),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Scission", "Detonation"],
        notes="Standard great axe WS."
    ),
    
    "Sanguine Blade": WeaponskillData(
        name="Sanguine Blade",
        weapon_type=WeaponType.SWORD,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"MND": 50, "STR": 50},
        ftp=(2.75, 2.75, 2.75),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Dark",
        skillchain=["Compression", "Reverberation"],
        notes="Magical sword WS. Drains HP."
    ),
    
    "Red Lotus Blade": WeaponskillData(
        name="Red Lotus Blade",
        weapon_type=WeaponType.SWORD,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"STR": 40, "INT": 40},
        ftp=(1.5, 1.5, 1.5),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Fire",
        skillchain=["Liquefaction", "Detonation"],
        notes="Basic magical fire sword WS."
    ),
    
    "Seraph Blade": WeaponskillData(
        name="Seraph Blade",
        weapon_type=WeaponType.SWORD,
        ws_type=WSType.MAGICAL,
        stat_modifiers={"STR": 40, "MND": 40},
        ftp=(2.0, 2.5, 3.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        element="Light",
        skillchain=["Scission"],
        notes="Magical light sword WS."
    ),
    
    "Circle Blade": WeaponskillData(
        name="Circle Blade",
        weapon_type=WeaponType.SWORD,
        ws_type=WSType.PHYSICAL,
        stat_modifiers={"STR": 100},
        ftp=(1.0, 1.0, 1.0),
        hits=1,
        ftp_replicating=False,
        can_crit=False,
        skillchain=["Reverberation", "Impaction"],
        notes="AoE sword WS."
    ),
}


def get_weaponskill(name: str) -> Optional[WeaponskillData]:
    """Get weaponskill data by name (case-insensitive)."""
    name_lower = name.lower()
    for ws_name, ws_data in WEAPONSKILLS.items():
        if ws_name.lower() == name_lower:
            return ws_data
    return None


def get_weaponskills_by_type(weapon_type: WeaponType) -> List[WeaponskillData]:
    """Get all weaponskills for a weapon type."""
    return [ws for ws in WEAPONSKILLS.values() if ws.weapon_type == weapon_type]


def get_all_weaponskill_names() -> List[str]:
    """Get list of all weaponskill names."""
    return list(WEAPONSKILLS.keys())


def get_weaponskills_for_job(job_name: str) -> List[str]:
    """
    Get weaponskills commonly used by a job.
    This is a simplified mapping - actual availability depends on weapons owned.
    """
    job_ws_map = {
        "WAR": ["Resolution", "Ukko's Fury", "Upheaval", "Decimation"],
        "MNK": ["Victory Smite", "Shijin Spiral", "Howling Fist"],
        "WHM": ["Black Halo", "Realmrazer", "Judgement"],
        "BLM": ["Cataclysm", "Shattersoul"],
        "RDM": ["Savage Blade", "Chant du Cygne", "Requiescat"],
        "THF": ["Rudra's Storm", "Evisceration", "Aeolian Edge", "Exenterator"],
        "PLD": ["Savage Blade", "Chant du Cygne", "Requiescat", "Torcleaver"],
        "DRK": ["Torcleaver", "Resolution", "Entropy", "Quietus"],
        "BST": ["Decimation", "Ruinator", "Cloudsplitter"],
        "BRD": ["Savage Blade", "Mordant Rime", "Evisceration"],
        "RNG": ["Last Stand", "Wildfire", "Trueflight", "Apex Arrow", "Jishnu's Radiance"],
        "SAM": ["Tachi: Fudo", "Tachi: Shoha", "Tachi: Kaiten", "Tachi: Rana"],
        "NIN": ["Blade: Shun", "Blade: Hi", "Blade: Metsu"],
        "DRG": ["Stardiver", "Camlann's Torment", "Impulse Drive"],
        "SMN": ["Garuda's Favor"],  # SMN doesn't really WS
        "BLU": ["Savage Blade", "Chant du Cygne", "Requiescat", "Expiacion"],
        "COR": ["Savage Blade", "Last Stand", "Wildfire", "Leaden Salute"],
        "PUP": ["Victory Smite", "Shijin Spiral"],
        "DNC": ["Rudra's Storm", "Evisceration", "Exenterator", "Pyrrhic Kleos"],
        "SCH": ["Cataclysm", "Shattersoul"],
        "GEO": ["Black Halo", "Realmrazer"],
        "RUN": ["Resolution", "Savage Blade", "Dimidiation"],
    }
    return job_ws_map.get(job_name.upper(), [])