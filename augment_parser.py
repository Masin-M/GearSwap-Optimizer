"""
Augment Parser

Handles decoding and parsing of item augments from various sources:
1. Plain-text augments (e.g., "STR+10", "Accuracy+15")
2. Encoded augment IDs (numeric augment system)
3. Fixed-path upgrades (AF/Relic/Empy +2/+3)

Parsing Strategy:
- Phase 1: Extract all numeric patterns [STAT_NAME][+/-][DIGITS][optional %]
- Phase 2: Normalize stat names via lookup table
- Phase 3: Handle descriptive augments separately (Enhances, Path, etc.)
"""

import re
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
WSDIST_DIR = SCRIPT_DIR / 'wsdist_beta-main'

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(WSDIST_DIR))
from models import Stats


@dataclass
class AugmentDefinition:
    """Definition of an augment type."""
    id: int
    name: str
    stat: str  # Which stat this affects
    base_value: int = 0
    per_tier: int = 0  # Value increase per tier
    max_tier: int = 0
    is_percentage: bool = False


# =============================================================================
# NUMERIC AUGMENT PATTERN
# =============================================================================
# Matches: [STAT_NAME][+/-][DIGITS][optional %]
# Stat name can include: letters, spaces, dots, quotes (escaped as \")
# Examples:
#   STR+10
#   Mag. Acc.+25
#   \"Mag.Atk.Bns.\"+25
#   "Fast Cast"+10
#   Accuracy+20 Attack+20  (multiple in one string)
#
# Pattern breakdown:
#   (                           # Start capture group for stat name
#     (?:\\"|")?                # Optional leading quote (escaped or regular)
#     [A-Za-z]                  # Must have at least one letter
#     [A-Za-z\s\.\'\-]*         # Letters, spaces, dots, apostrophes, hyphens
#     (?:\\"|")?                # Optional trailing quote
#   )
#   ([+-])                      # Sign
#   (\d+)                       # Digits
#   (%?)                        # Optional percent
#
NUMERIC_AUGMENT_PATTERN = re.compile(r'((?:\\"|")[A-Za-z][A-Za-z\s\.\'\-]*(?:\\"|")|[A-Za-z][A-Za-z\s\.]*?)([+-])(\d+)(%?)')


# =============================================================================
# STAT NAME NORMALIZATION LOOKUP
# =============================================================================
# Maps raw stat names (as extracted) to canonical stat attribute names.
# Quoted stats from Lua use escaped quotes: \"Stat Name\"
#
# Format:
#   'RawName': 'stat_attr'           - simple 1:1 value
#   'RawName': ('stat_attr', 100)    - percentage stat (multiply by 100)
#
STAT_LOOKUP = {
    # -------------------------------------------------------------------------
    # Primary Stats
    # -------------------------------------------------------------------------
    'STR': 'STR',
    'DEX': 'DEX',
    'VIT': 'VIT',
    'AGI': 'AGI',
    'INT': 'INT',
    'MND': 'MND',
    'CHR': 'CHR',
    
    # -------------------------------------------------------------------------
    # HP / MP
    # -------------------------------------------------------------------------
    'HP': 'HP',
    'MP': 'MP',
    
    # -------------------------------------------------------------------------
    # Accuracy / Attack
    # -------------------------------------------------------------------------
    'Accuracy': 'accuracy',
    'Acc.': 'accuracy',
    'Attack': 'attack',
    'Atk.': 'attack',
    
    # Magic accuracy/attack
    'Mag. Acc.': 'magic_accuracy',
    'Mag. Acc': 'magic_accuracy',
    'Mag.Acc.': 'magic_accuracy',
    'Magic Acc.': 'magic_accuracy',
    'Magic Acc': 'magic_accuracy',
    'Magic Accuracy': 'magic_accuracy',
    
    'Mag. Dmg.': 'magic_damage',
    'Mag.Dmg.': 'magic_damage',
    'Magic Dmg.': 'magic_damage',
    
    # Quoted magic attack bonus (various escaped forms)
    '\\"Mag.Atk.Bns.\\"': 'magic_attack',
    '"Mag.Atk.Bns."': 'magic_attack',
    'Mag.Atk.Bns.': 'magic_attack',
    'M.A.B.': 'magic_attack',
    
    # Ranged
    'R.Acc.': 'ranged_accuracy',
    'Ranged Acc.': 'ranged_accuracy',
    'Ranged Accuracy': 'ranged_accuracy',
    'R.Atk.': 'ranged_attack',
    'Ranged Atk.': 'ranged_attack',
    'Ranged Attack': 'ranged_attack',
    
    # -------------------------------------------------------------------------
    # Defense / Evasion
    # -------------------------------------------------------------------------
    'Def.': 'defense',
    'Defense': 'defense',
    'Eva.': 'evasion',
    'Evasion': 'evasion',
    
    'M.Eva.': 'magic_evasion',
    'Magic Eva.': 'magic_evasion',
    'Magic Evasion': 'magic_evasion',
    'M.Def.': 'magic_defense',
    'Magic Def.': 'magic_defense',
    'Magic Defense': 'magic_defense',
    
    # -------------------------------------------------------------------------
    # Multi-attack (percentage stats - multiply by 100 for basis points)
    # -------------------------------------------------------------------------
    '\\"Dbl.Atk.\\"': ('double_attack', 100),
    '"Dbl.Atk."': ('double_attack', 100),
    'Dbl.Atk.': ('double_attack', 100),
    '\\"Double Attack\\"': ('double_attack', 100),
    '"Double Attack"': ('double_attack', 100),
    'DA': ('double_attack', 100),
    
    '\\"Triple Atk.\\"': ('triple_attack', 100),
    '"Triple Atk."': ('triple_attack', 100),
    'Triple Atk.': ('triple_attack', 100),
    '\\"Triple Attack\\"': ('triple_attack', 100),
    '"Triple Attack"': ('triple_attack', 100),
    'TA': ('triple_attack', 100),
    
    '\\"Quad. Atk.\\"': ('quad_attack', 100),
    '"Quad. Atk."': ('quad_attack', 100),
    'QA': ('quad_attack', 100),
    
    # -------------------------------------------------------------------------
    # Store TP
    # -------------------------------------------------------------------------
    '\\"Store TP\\"': 'store_tp',
    '"Store TP"': 'store_tp',
    'Store TP': 'store_tp',
    'STP': 'store_tp',
    
    # -------------------------------------------------------------------------
    # Haste / Dual Wield (percentage stats)
    # -------------------------------------------------------------------------
    'Haste': ('gear_haste', 100),
    'Gear Haste': ('gear_haste', 100),
    'Magic Haste': ('magic_haste', 100),
    
    '\\"Dual Wield\\"': ('dual_wield', 100),
    '"Dual Wield"': ('dual_wield', 100),
    'Dual Wield': ('dual_wield', 100),
    'DW': ('dual_wield', 100),
    
    # -------------------------------------------------------------------------
    # Critical Hit
    # -------------------------------------------------------------------------
    'Crit. hit rate': ('crit_rate', 100),
    '\\"Crit.hit rate\\"': ('crit_rate', 100),
    '"Crit.hit rate"': ('crit_rate', 100),
    'Critical hit rate': ('crit_rate', 100),
    
    'Crit. hit dmg.': ('crit_damage', 100),
    '\\"Crit.hit damage\\"': ('crit_damage', 100),
    '"Crit.hit damage"': ('crit_damage', 100),
    
    # -------------------------------------------------------------------------
    # Damage Taken (percentage stats)
    # -------------------------------------------------------------------------
    'Phys. dmg. taken': ('physical_dt', 100),
    'Physical damage taken': ('physical_dt', 100),
    'PDT': ('physical_dt', 100),
    
    'Mag. dmg. taken': ('magical_dt', 100),
    'Magic damage taken': ('magical_dt', 100),
    'MDT': ('magical_dt', 100),
    
    'Breath dmg. taken': ('breath_dt', 100),
    'BDT': ('breath_dt', 100),
    
    'Dmg. taken': ('damage_taken', 100),
    'Damage taken': ('damage_taken', 100),
    'DT': ('damage_taken', 100),
    
    # -------------------------------------------------------------------------
    # Weapon Skill
    # -------------------------------------------------------------------------
    'WSD': ('ws_damage', 100),
    '\\"Weapon skill damage\\"': ('ws_damage', 100),
    '"Weapon skill damage"': ('ws_damage', 100),
    'Weapon skill damage': ('ws_damage', 100),
    
    'WS Acc.': 'ws_acc',
    'Weaponskill Acc.': 'ws_acc',
    
    # -------------------------------------------------------------------------
    # Magic Stats
    # -------------------------------------------------------------------------
    '\\"Fast Cast\\"': ('fast_cast', 100),
    '"Fast Cast"': ('fast_cast', 100),
    'Fast Cast': ('fast_cast', 100),
    'FC': ('fast_cast', 100),
    
    '\\"Magic Burst Bonus\\"': ('magic_burst_bonus', 100),
    '"Magic Burst Bonus"': ('magic_burst_bonus', 100),
    'Magic burst dmg.': ('magic_burst_bonus', 100),
    'MB': ('magic_burst_bonus', 100),
    
    '\\"Cure potency\\"': ('cure_potency', 100),
    '"Cure potency"': ('cure_potency', 100),
    'Cure potency': ('cure_potency', 100),
    
    '\\"Cure Potency II\\"': ('cure_potency_ii', 100),
    '"Cure Potency II"': ('cure_potency_ii', 100),
    'Cure received': ('cure_potency_ii', 100),
    
    # -------------------------------------------------------------------------
    # Magic Skills
    # -------------------------------------------------------------------------
    'Healing magic skill': 'healing_magic_skill',
    'Enfeebling magic skill': 'enfeebling_magic_skill',
    'Enhancing magic skill': 'enhancing_magic_skill',
    'Elemental magic skill': 'elemental_magic_skill',
    'Divine magic skill': 'divine_magic_skill',
    'Dark magic skill': 'dark_magic_skill',
    
    'Enfeebling magic effect': 'enfeebling_effect',
    'Enhancing magic duration': ('enhancing_duration', 100),
    
    # -------------------------------------------------------------------------
    # Weapon Skills (combat)
    # -------------------------------------------------------------------------
    'Sword skill': 'skill_sword',
    'Great Sword skill': 'skill_great_sword',
    'Dagger skill': 'skill_dagger',
    'Katana skill': 'skill_katana',
    'Great Katana skill': 'skill_great_katana',
    'Axe skill': 'skill_axe',
    'Great Axe skill': 'skill_great_axe',
    'Scythe skill': 'skill_scythe',
    'Polearm skill': 'skill_polearm',
    'Club skill': 'skill_club',
    'Staff skill': 'skill_staff',
    'H2H skill': 'skill_h2h',
    'Hand-to-Hand skill': 'skill_h2h',
    
    # -------------------------------------------------------------------------
    # Weapon Stats
    # -------------------------------------------------------------------------
    'DMG': 'damage',
    'Damage': 'damage',
    'Delay': 'delay',
    
    # =========================================================================
    # TP-RELATED STATS (wsdist compatibility)
    # =========================================================================
    '\\"TP Bonus\\"': 'tp_bonus',
    '"TP Bonus"': 'tp_bonus',
    'TP Bonus': 'tp_bonus',
    
    '\\"Daken\\"': 'daken',
    '"Daken"': 'daken',
    'Daken': 'daken',
    
    '\\"Martial Arts\\"': 'martial_arts',
    '"Martial Arts"': 'martial_arts',
    'Martial Arts': 'martial_arts',
    
    '\\"Zanshin\\"': 'zanshin',
    '"Zanshin"': 'zanshin',
    'Zanshin': 'zanshin',
    
    '\\"Kick Attacks\\"': 'kick_attacks',
    '"Kick Attacks"': 'kick_attacks',
    'Kick Attacks': 'kick_attacks',
    '\\"Kick Attacks Dmg.\\"': 'kick_attacks_dmg',
    '"Kick Attacks Dmg."': 'kick_attacks_dmg',
    
    '\\"Subtle Blow\\"': 'subtle_blow',
    '"Subtle Blow"': 'subtle_blow',
    'Subtle Blow': 'subtle_blow',
    '\\"Subtle Blow II\\"': 'subtle_blow_ii',
    '"Subtle Blow II"': 'subtle_blow_ii',
    'Subtle Blow II': 'subtle_blow_ii',
    'SB': 'subtle_blow',
    'SBII': 'subtle_blow_ii',
    
    '\\"Fencer\\"': 'fencer',
    '"Fencer"': 'fencer',
    'Fencer': 'fencer',
    
    '\\"Conserve TP\\"': 'conserve_tp',
    '"Conserve TP"': 'conserve_tp',
    'Conserve TP': 'conserve_tp',
    
    '\\"Regain\\"': 'regain',
    '"Regain"': 'regain',
    'Regain': 'regain',
    
    # =========================================================================
    # PASSIVE GEAR REGEN/REFRESH (for DT/Idle sets)
    # =========================================================================
    # These give passive MP/HP per tick from wearing the gear
    # e.g., '"Refresh"+2' augments or gear with 'Refresh+3'
    '\\"Refresh\\"': 'refresh',
    '"Refresh"': 'refresh',
    'Refresh': 'refresh',
    
    '\\"Regen\\"': 'regen',
    '"Regen"': 'regen',
    'Regen': 'regen',
    
    # =========================================================================
    # MIDCAST REGEN SPELL STATS (for sets.midcast.Regen)
    # =========================================================================
    # Regen potency - flat HP/tick added to Regen spells you cast
    # e.g., Bookworm's Cape '"Regen" potency+8'
    '\\"Regen\\" potency': 'regen_potency',
    '"Regen" potency': 'regen_potency',
    'Regen potency': 'regen_potency',
    
    # Regen effect duration - flat seconds added to Regen spell duration
    # e.g., Telchine Chasuble, Lugh's Cape
    # Note: This is FLAT seconds, not percentage
    'Regen effect dur.': 'regen_effect_duration',
    '\\"Regen\\" effect dur.': 'regen_effect_duration',
    '"Regen" effect dur.': 'regen_effect_duration',
    'Regen effect duration': 'regen_effect_duration',
    
    # =========================================================================
    # MIDCAST REFRESH SPELL STATS (for sets.midcast.Refresh)
    # =========================================================================
    # Refresh potency - flat MP/tick added (rare stat)
    '\\"Refresh\\" potency': 'refresh_potency',
    '"Refresh" potency': 'refresh_potency',
    'Refresh potency': 'refresh_potency',
    
    # Refresh effect duration - flat seconds added
    'Refresh effect dur.': 'refresh_effect_duration',
    '\\"Refresh\\" effect dur.': 'refresh_effect_duration',
    '"Refresh" effect dur.': 'refresh_effect_duration',
    'Refresh effect duration': 'refresh_effect_duration',
    
    # =========================================================================
    # ENHANCING MAGIC DURATION FROM AUGMENTS (separate from non-augmented)
    # =========================================================================
    # Telchine/Chironic/etc augments use this format
    # Applies at a different step than non-augmented enhancing duration gear
    'Enh. Mag. eff. dur.': ('enhancing_duration_augment', 100),
    'Enh. mag. eff. dur.': ('enhancing_duration_augment', 100),
    '\\"Enh. Mag. eff. dur.\\"': ('enhancing_duration_augment', 100),
    '"Enh. Mag. eff. dur."': ('enhancing_duration_augment', 100),
    
    # =========================================================================
    # OCCASIONAL ATTACKS
    # =========================================================================
    '\\"OA2\\"': 'oa2',
    '"OA2"': 'oa2',
    'OA2': 'oa2',
    '\\"OA3\\"': 'oa3',
    '"OA3"': 'oa3',
    'OA3': 'oa3',
    '\\"OA4\\"': 'oa4',
    '"OA4"': 'oa4',
    'OA4': 'oa4',
    '\\"OA5\\"': 'oa5',
    '"OA5"': 'oa5',
    'OA5': 'oa5',
    '\\"OA6\\"': 'oa6',
    '"OA6"': 'oa6',
    'OA6': 'oa6',
    '\\"OA7\\"': 'oa7',
    '"OA7"': 'oa7',
    'OA7': 'oa7',
    '\\"OA8\\"': 'oa8',
    '"OA8"': 'oa8',
    'OA8': 'oa8',
    '\\"FUA\\"': 'fua',
    '"FUA"': 'fua',
    'FUA': 'fua',
    '\\"Follow-up Attack\\"': 'fua',
    '"Follow-up Attack"': 'fua',
    'Follow-up Attack': 'fua',
    
    # =========================================================================
    # DAMAGE MODIFIERS
    # =========================================================================
    '\\"PDL\\"': ('pdl', 100),
    '"PDL"': ('pdl', 100),
    'PDL': ('pdl', 100),
    'Phys. dmg. limit': ('pdl', 100),
    'Physical damage limit': ('pdl', 100),
    
    '\\"Skillchain Bonus\\"': ('skillchain_bonus', 100),
    '"Skillchain Bonus"': ('skillchain_bonus', 100),
    'Skillchain Bonus': ('skillchain_bonus', 100),
    'SC Bonus': ('skillchain_bonus', 100),
    
    '\\"DA Damage%\\"': 'da_damage_pct',
    '"DA Damage%"': 'da_damage_pct',
    'DA Damage%': 'da_damage_pct',
    '\\"TA Damage%\\"': 'ta_damage_pct',
    '"TA Damage%"': 'ta_damage_pct',
    'TA Damage%': 'ta_damage_pct',
    
    # =========================================================================
    # RANGED-SPECIFIC
    # =========================================================================
    '\\"Double Shot\\"': 'double_shot',
    '"Double Shot"': 'double_shot',
    'Double Shot': 'double_shot',
    '\\"Triple Shot\\"': 'triple_shot',
    '"Triple Shot"': 'triple_shot',
    'Triple Shot': 'triple_shot',
    '\\"True Shot\\"': 'true_shot',
    '"True Shot"': 'true_shot',
    'True Shot': 'true_shot',
    '\\"Recycle\\"': 'recycle',
    '"Recycle"': 'recycle',
    'Recycle': 'recycle',
    '\\"Barrage\\"': 'barrage',
    '"Barrage"': 'barrage',
    'Barrage': 'barrage',
    
    # =========================================================================
    # MAGIC-SPECIFIC
    # =========================================================================
    'Magic Accuracy Skill': 'magic_accuracy_skill',
    'Mag. Acc. Skill': 'magic_accuracy_skill',
    '\\"Mag. Acc. Skill\\"': 'magic_accuracy_skill',
    '"Mag. Acc. Skill"': 'magic_accuracy_skill',
    
    '\\"Magic Burst Damage II\\"': ('magic_burst_damage_ii', 100),
    '"Magic Burst Damage II"': ('magic_burst_damage_ii', 100),
    'Magic Burst Damage II': ('magic_burst_damage_ii', 100),
    'MBII': ('magic_burst_damage_ii', 100),
    
    # -------------------------------------------------------------------------
    # Dark Magic / Absorb Spells (DRK)
    # Per BG-Wiki: Absorb potency is NOT affected by Dark Magic Skill
    # Potency comes from equipment bonuses (Liberator, Pavor Gauntlets, etc.)
    # -------------------------------------------------------------------------
    # Absorb effect potency (equipment-based, not skill-based)
    '\\"Absorb\\"': ('absorb_potency', 100),
    '"Absorb"': ('absorb_potency', 100),
    'Absorb': ('absorb_potency', 100),
    '\\"Absorb\\"+': ('absorb_potency', 100),
    '"Absorb"+': ('absorb_potency', 100),
    'Absorb potency': ('absorb_potency', 100),
    '\\"Absorb\\" effect potency': ('absorb_potency', 100),
    '"Absorb" effect potency': ('absorb_potency', 100),
    
    # Absorb effect duration
    '\\"Absorb\\" effect duration': ('absorb_effect_duration', 100),
    '"Absorb" effect duration': ('absorb_effect_duration', 100),
    'Absorb effect duration': ('absorb_effect_duration', 100),
    'Absorb duration': ('absorb_effect_duration', 100),
    
    # Dark magic duration (affects Absorb duration via skill formula)
    'Dark magic duration': ('dark_magic_duration', 100),
    'Dark magic effect duration': ('dark_magic_duration', 100),
    '\\"Dark magic duration\\"': ('dark_magic_duration', 100),
    '"Dark magic duration"': ('dark_magic_duration', 100),
    
    # Drain/Aspir potency (for completeness - skill-based)
    'Drain and Aspir potency': ('drain_aspir_potency', 100),
    '\\"Drain\\" and \\"Aspir\\" potency': ('drain_aspir_potency', 100),
    '"Drain" and "Aspir" potency': ('drain_aspir_potency', 100),
    'Drain potency': ('drain_aspir_potency', 100),
    'Aspir potency': ('drain_aspir_potency', 100),
    
    # =========================================================================
    # JOB-SPECIFIC STATS
    # =========================================================================
    # EnSpell (RDM)
    '\\"EnSpell Damage\\"': 'enspell_damage',
    '"EnSpell Damage"': 'enspell_damage',
    'EnSpell Damage': 'enspell_damage',
    '\\"EnSpell Damage%\\"': ('enspell_damage_pct', 100),
    '"EnSpell Damage%"': ('enspell_damage_pct', 100),
    
    # Ninjutsu (NIN)
    '\\"Ninjutsu Magic Attack\\"': 'ninjutsu_magic_attack',
    '"Ninjutsu Magic Attack"': 'ninjutsu_magic_attack',
    'Ninjutsu Magic Attack': 'ninjutsu_magic_attack',
    '\\"Ninjutsu Damage%\\"': ('ninjutsu_damage_pct', 100),
    '"Ninjutsu Damage%"': ('ninjutsu_damage_pct', 100),
    'Ninjutsu Damage': ('ninjutsu_damage_pct', 100),
    
    # Blood Pact (SMN)
    '\\"Blood Pact Damage\\"': ('blood_pact_damage', 100),
    '"Blood Pact Damage"': ('blood_pact_damage', 100),
    'Blood Pact Damage': ('blood_pact_damage', 100),
    'BP Damage': ('blood_pact_damage', 100),
    
    # Occult Acumen
    '\\"Occult Acumen\\"': 'occult_acumen',
    '"Occult Acumen"': 'occult_acumen',
    'Occult Acumen': 'occult_acumen',
    
    # =========================================================================
    # ELEMENTAL BONUSES
    # =========================================================================
    'Fire Elemental Bonus': 'fire_elemental_bonus',
    'Ice Elemental Bonus': 'ice_elemental_bonus',
    'Wind Elemental Bonus': 'wind_elemental_bonus',
    'Earth Elemental Bonus': 'earth_elemental_bonus',
    'Lightning Elemental Bonus': 'lightning_elemental_bonus',
    'Thunder Elemental Bonus': 'lightning_elemental_bonus',
    'Water Elemental Bonus': 'water_elemental_bonus',
    'Light Elemental Bonus': 'light_elemental_bonus',
    'Dark Elemental Bonus': 'dark_elemental_bonus',
}


# =============================================================================
# DESCRIPTIVE AUGMENT PATTERNS
# =============================================================================
# These don't have numeric values - they're flags or special effects
#
DESCRIPTIVE_PATTERNS = [
    # Ability enhancements - handles both \" and " quotes
    (re.compile(r'Enhances\s+(?:\\"|")?([^"\\]+)(?:\\"|")?\s+effect', re.IGNORECASE), 'enhances'),
    (re.compile(r'Augments\s+(?:\\"|")?([^"\\]+)(?:\\"|")?', re.IGNORECASE), 'augments'),
    
    # Path indicators
    (re.compile(r'Path:\s*([A-Z])', re.IGNORECASE), 'path'),
    
    # Special properties without values
    (re.compile(r'Occasionally attacks twice', re.IGNORECASE), 'occasionally_double'),
    (re.compile(r'Occasionally attacks thrice', re.IGNORECASE), 'occasionally_triple'),
    
    # Immunobreak and similar
    (re.compile(r'Immunobreak Chance', re.IGNORECASE), 'immunobreak'),
    
    # Duration/potency without number
    (re.compile(r'Enhancing Magic duration', re.IGNORECASE), 'enhancing_duration_flag'),
    
    # =========================================================================
    # PASSIVE REGEN/REFRESH FROM GEAR
    # =========================================================================
    # "Adds Refresh effect" - gives passive 1 MP/tick
    # "Adds improved Refresh effect" - gives passive 2 MP/tick (set bonus)
    (re.compile(r'Adds\s+improved\s+(?:\\"|")?Refresh(?:\\"|")?\s+effect', re.IGNORECASE), 'adds_improved_refresh'),
    (re.compile(r'Adds\s+(?:\\"|")?Refresh(?:\\"|")?\s+effect', re.IGNORECASE), 'adds_refresh'),
    
    # "Adds Regen effect" - gives passive HP/tick
    (re.compile(r'Adds\s+improved\s+(?:\\"|")?Regen(?:\\"|")?\s+effect', re.IGNORECASE), 'adds_improved_regen'),
    (re.compile(r'Adds\s+(?:\\"|")?Regen(?:\\"|")?\s+effect', re.IGNORECASE), 'adds_regen'),
]


class AugmentParser:
    """
    Parser for item augments.
    
    Uses a two-phase approach:
    1. Extract numeric patterns with one regex
    2. Normalize stat names via lookup table
    3. Handle descriptive augments separately
    """
    
    def __init__(self):
        self.augment_table: Dict[int, AugmentDefinition] = {}
        self._load_augment_table()
    
    def _load_augment_table(self):
        """
        Load augment ID definitions.
        
        In a full implementation, this would load from GearSwap's augments.lua.
        For now, we include common augment ID mappings.
        """
        # Placeholder - numeric augment IDs would be loaded here
        pass
    
    def parse_augments(self, augments_raw: List[Any]) -> Stats:
        """
        Parse augments into a Stats object.
        
        Args:
            augments_raw: List of augments (can be strings or numeric IDs)
        
        Returns:
            Stats object with augment bonuses
        """
        stats = Stats()
        
        if not augments_raw:
            return stats
        
        for aug in augments_raw:
            if aug is None or aug == 'none' or aug == '':
                continue
            
            if isinstance(aug, str):
                # Parse text augment
                self._parse_text_augment(aug, stats)
            elif isinstance(aug, int):
                # Decode numeric augment ID
                self._decode_augment_id(aug, stats)
            elif isinstance(aug, (list, tuple)) and len(aug) >= 2:
                # Augment with tier: (id, tier)
                self._decode_augment_id(aug[0], stats, tier=aug[1])
        
        return stats
    
    def _parse_text_augment(self, text: str, stats: Stats):
        """
        Parse a text-based augment string using two-phase approach.
        
        Phase 1: Extract all numeric patterns
        Phase 2: Normalize and apply to stats
        Phase 3: Handle descriptive augments
        """
        text = text.strip()
        processed_text = text  # Track remaining text after special pattern removal
        
        # =================================================================
        # Pre-Phase: Special patterns that the main regex doesn't handle well
        # =================================================================
        # Handle "Regen" potency+X and similar patterns with quoted prefix
        special_patterns = [
            # Regen potency: "Regen" potency+8 or \"Regen\" potency+8
            (re.compile(r'(?:\\"|")?Regen(?:\\"|")?\s+potency\s*[+]?\s*(\d+)', re.IGNORECASE), 'regen_potency'),
            # Refresh potency: "Refresh" potency+X
            (re.compile(r'(?:\\"|")?Refresh(?:\\"|")?\s+potency\s*[+]?\s*(\d+)', re.IGNORECASE), 'refresh_potency'),
            # Pet Regen: Pet: "Regen"+3 (for SMN/BST/PUP)
            (re.compile(r'Pet:\s*(?:\\"|")?Regen(?:\\"|")?\s*[+]\s*(\d+)', re.IGNORECASE), 'pet_regen'),
        ]
        
        for pattern, stat_attr in special_patterns:
            match = pattern.search(text)
            if match:
                try:
                    value = int(match.group(1))
                    if hasattr(stats, stat_attr):
                        current = getattr(stats, stat_attr)
                        setattr(stats, stat_attr, current + value)
                    elif stat_attr == 'pet_regen':
                        # Store pet stats separately for now
                        stats.special_effects.append(f'Pet: Regen+{value}')
                    # Remove matched portion to avoid double-counting in main regex
                    processed_text = pattern.sub('', processed_text)
                except (ValueError, IndexError):
                    pass
        
        # =================================================================
        # Phase 1 & 2: Numeric augments (on processed text)
        # =================================================================
        matches = NUMERIC_AUGMENT_PATTERN.findall(processed_text)
        
        for stat_name, sign, value_str, percent in matches:
            stat_name = stat_name.strip()
            
            try:
                raw_value = int(value_str)
                if sign == '-':
                    raw_value = -raw_value
            except ValueError:
                continue
            
            # Look up the canonical stat name
            normalized = self._normalize_stat_name(stat_name)
            
            if normalized is None:
                # Unknown stat - store as special effect
                stats.special_effects.append(f"{stat_name}{sign}{value_str}{percent}")
                continue
            
            # Handle tuple format: (stat_name, multiplier)
            if isinstance(normalized, tuple):
                stat_attr, multiplier = normalized
                value = raw_value * multiplier
            else:
                stat_attr = normalized
                # If percent sign present and not already a percentage stat, multiply
                if percent == '%':
                    value = raw_value * 100
                else:
                    value = raw_value
            
            # Apply to stats
            self._apply_stat(stats, stat_attr, value)
        
        # =================================================================
        # Phase 3: Descriptive augments
        # =================================================================
        self._parse_descriptive_augment(text, stats)
    
    def _normalize_stat_name(self, raw_name: str) -> Optional[Any]:
        """
        Normalize a raw stat name to canonical form.
        
        Returns:
            - str: The canonical stat attribute name
            - tuple: (stat_name, multiplier) for percentage stats
            - None: Unknown stat
        """
        # Direct lookup first
        if raw_name in STAT_LOOKUP:
            return STAT_LOOKUP[raw_name]
        
        # Try stripping escaped quotes: \"Name\" -> Name
        if raw_name.startswith('\\"') and raw_name.endswith('\\"'):
            inner = raw_name[2:-2]
            if inner in STAT_LOOKUP:
                return STAT_LOOKUP[inner]
            # Try with regular quotes
            quoted = f'"{inner}"'
            if quoted in STAT_LOOKUP:
                return STAT_LOOKUP[quoted]
        
        # Try stripping regular quotes: "Name" -> Name  
        if raw_name.startswith('"') and raw_name.endswith('"'):
            inner = raw_name[1:-1]
            if inner in STAT_LOOKUP:
                return STAT_LOOKUP[inner]
        
        # Case-insensitive lookup as last resort
        raw_lower = raw_name.lower()
        for key, value in STAT_LOOKUP.items():
            if key.lower() == raw_lower:
                return value
        
        return None
    
    def _apply_stat(self, stats: Stats, stat_attr: str, value: int):
        """Apply a value to a stat attribute."""
        # Handle skill bonuses specially
        if stat_attr.startswith('skill_'):
            skill_name = stat_attr[6:]  # Remove 'skill_' prefix
            stats.skill_bonuses[skill_name] = stats.skill_bonuses.get(skill_name, 0) + value
        elif hasattr(stats, stat_attr):
            current = getattr(stats, stat_attr)
            setattr(stats, stat_attr, current + value)
        else:
            # Unknown attribute - store as special effect
            stats.special_effects.append(f"{stat_attr}: {value:+d}")
    
    def _parse_descriptive_augment(self, text: str, stats: Stats):
        """Parse descriptive augments (Enhances, Path, Adds Refresh/Regen, etc.)."""
        
        for pattern, effect_type in DESCRIPTIVE_PATTERNS:
            match = pattern.search(text)
            if match:
                if effect_type == 'enhances':
                    ability = match.group(1).strip()
                    stats.special_effects.append(f'Enhances "{ability}" effect')
                elif effect_type == 'augments':
                    ability = match.group(1).strip()
                    stats.special_effects.append(f'Augments "{ability}"')
                elif effect_type == 'path':
                    path = match.group(1).upper()
                    stats.special_effects.append(f'Path: {path}')
                # =========================================================
                # Passive Refresh from gear
                # =========================================================
                elif effect_type == 'adds_improved_refresh':
                    # "Adds improved Refresh effect" - typically set bonus giving +2 MP/tick
                    stats.refresh += 2
                elif effect_type == 'adds_refresh':
                    # "Adds Refresh effect" - standard 1 MP/tick
                    stats.refresh += 1
                # =========================================================
                # Passive Regen from gear
                # =========================================================
                elif effect_type == 'adds_improved_regen':
                    # "Adds improved Regen effect" - set bonus, higher value
                    stats.regen += 2
                elif effect_type == 'adds_regen':
                    # "Adds Regen effect" - standard value (varies, usually 1-3)
                    stats.regen += 1
                else:
                    # Simple flag-type effects
                    stats.special_effects.append(effect_type)
        
        # Handle "All magic skills +X"
        all_magic_match = re.search(r'All magic skills?\s*[+]?\s*(\d+)', text, re.IGNORECASE)
        if all_magic_match:
            try:
                value = int(all_magic_match.group(1))
                stats.healing_magic_skill += value
                stats.enfeebling_magic_skill += value
                stats.enhancing_magic_skill += value
                stats.elemental_magic_skill += value
                stats.divine_magic_skill += value
                stats.dark_magic_skill += value
            except ValueError:
                pass
    
    def _decode_augment_id(self, aug_id: int, stats: Stats, tier: int = 0):
        """
        Decode a numeric augment ID.
        
        The augment ID system in FFXI encodes the augment type and tier
        in a single number. The exact mapping depends on the content.
        
        Args:
            aug_id: The augment ID
            stats: Stats object to update
            tier: Optional tier override
        """
        # Check if we have this augment defined
        if aug_id in self.augment_table:
            aug_def = self.augment_table[aug_id]
            value = aug_def.base_value + (aug_def.per_tier * tier)
            
            if aug_def.is_percentage:
                value *= 100  # Convert to basis points
            
            if hasattr(stats, aug_def.stat):
                current = getattr(stats, aug_def.stat)
                setattr(stats, aug_def.stat, current + value)
        else:
            # Unknown augment - store as special effect for manual review
            stats.special_effects.append(f'Unknown Augment ID: {aug_id}')
    
    def load_augment_table_from_lua(self, lua_path: str):
        """
        Load augment definitions from GearSwap's augments.lua.
        
        This would parse the actual augment tables used by GearSwap.
        """
        # Implementation would parse the Lua file and populate self.augment_table
        pass


class AugmentResolver:
    """
    High-level augment resolution that handles all augment types.
    """
    
    def __init__(self):
        self.parser = AugmentParser()
    
    def resolve(self, item_id: int, augments_raw: List[Any], extdata: str = '') -> Stats:
        """
        Resolve all augments for an item into final stats.
        
        Args:
            item_id: The base item ID
            augments_raw: Raw augment data from inventory
            extdata: Extended data hex string (for encoded augments)
        
        Returns:
            Stats object with all augment bonuses
        """
        stats = Stats()
        
        # Parse standard augments
        if augments_raw:
            stats = stats + self.parser.parse_augments(augments_raw)
        
        # Handle extdata-encoded augments (e.g., Ambuscade gear paths)
        if extdata:
            extdata_stats = self._decode_extdata(item_id, extdata)
            stats = stats + extdata_stats
        
        return stats
    
    def _decode_extdata(self, item_id: int, extdata: str) -> Stats:
        """
        Decode augments from extdata hex string.
        
        This handles special augment encoding used by certain content types.
        """
        stats = Stats()
        
        if not extdata or len(extdata) < 4:
            return stats
        
        try:
            # Convert hex string to bytes
            data = bytes.fromhex(extdata)
            
            # The exact structure depends on the item type
            # This is a placeholder for the actual decoding logic
            # which would need to match GearSwap's extdata handling
            
        except (ValueError, IndexError):
            pass
        
        return stats


# =============================================================================
# Singleton instances
# =============================================================================
_parser: Optional[AugmentParser] = None
_resolver: Optional[AugmentResolver] = None


def get_parser() -> AugmentParser:
    """Get the global augment parser instance."""
    global _parser
    if _parser is None:
        _parser = AugmentParser()
    return _parser


def get_resolver() -> AugmentResolver:
    """Get the global augment resolver instance."""
    global _resolver
    if _resolver is None:
        _resolver = AugmentResolver()
    return _resolver


def parse_augments(augments_raw: List[Any]) -> Stats:
    """Convenience function to parse augments."""
    return get_parser().parse_augments(augments_raw)


def resolve_augments(item_id: int, augments_raw: List[Any], extdata: str = '') -> Stats:
    """Convenience function to resolve all augments for an item."""
    return get_resolver().resolve(item_id, augments_raw, extdata)