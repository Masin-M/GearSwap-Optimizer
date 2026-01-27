"""
Data models for GearSwap Optimizer

Defines the core data structures for items, stats, and gear slots.
"""

from dataclasses import dataclass, field
from enum import IntEnum, IntFlag, auto
from typing import Optional, Dict, List, Set, Any


class Slot(IntEnum):
    """Equipment slot IDs matching FFXI/GearSwap conventions."""
    MAIN = 0
    SUB = 1
    RANGE = 2
    AMMO = 3
    HEAD = 4
    NECK = 9
    LEFT_EAR = 11
    RIGHT_EAR = 12
    BODY = 5
    HANDS = 6
    LEFT_RING = 13
    RIGHT_RING = 14
    BACK = 15
    WAIST = 10
    LEGS = 7
    FEET = 8


# Slot bitmask values (for items.lua slots field)
SLOT_BITMASK = {
    Slot.MAIN: 0x0001,
    Slot.SUB: 0x0002,
    Slot.RANGE: 0x0004,
    Slot.AMMO: 0x0008,
    Slot.HEAD: 0x0010,
    Slot.BODY: 0x0020,
    Slot.HANDS: 0x0040,
    Slot.LEGS: 0x0080,
    Slot.FEET: 0x0100,
    Slot.NECK: 0x0200,
    Slot.WAIST: 0x0400,
    Slot.LEFT_EAR: 0x0800,
    Slot.RIGHT_EAR: 0x1000,
    Slot.LEFT_RING: 0x2000,
    Slot.RIGHT_RING: 0x4000,
    Slot.BACK: 0x8000,
}

# GearSwap slot names
SLOT_NAMES = {
    Slot.MAIN: 'main',
    Slot.SUB: 'sub',
    Slot.RANGE: 'range',
    Slot.AMMO: 'ammo',
    Slot.HEAD: 'head',
    Slot.NECK: 'neck',
    Slot.LEFT_EAR: 'left_ear',
    Slot.RIGHT_EAR: 'right_ear',
    Slot.BODY: 'body',
    Slot.HANDS: 'hands',
    Slot.LEFT_RING: 'left_ring',
    Slot.RIGHT_RING: 'right_ring',
    Slot.BACK: 'back',
    Slot.WAIST: 'waist',
    Slot.LEGS: 'legs',
    Slot.FEET: 'feet',
}


class Job(IntEnum):
    """Job IDs matching FFXI conventions."""
    NONE = 0
    WAR = 1
    MNK = 2
    WHM = 3
    BLM = 4
    RDM = 5
    THF = 6
    PLD = 7
    DRK = 8
    BST = 9
    BRD = 10
    RNG = 11
    SAM = 12
    NIN = 13
    DRG = 14
    SMN = 15
    BLU = 16
    COR = 17
    PUP = 18
    DNC = 19
    SCH = 20
    GEO = 21
    RUN = 22


# Job bitmask values (bit position = job_id)
JOB_BITMASK = {job: (1 << job.value) if job.value > 0 else 0 for job in Job}


class Container(IntEnum):
    """Inventory container IDs."""
    INVENTORY = 0
    SAFE = 1
    STORAGE = 2
    TEMPORARY = 3
    LOCKER = 4
    SATCHEL = 5
    SACK = 6
    CASE = 7
    WARDROBE = 8
    SAFE2 = 9
    WARDROBE2 = 10
    WARDROBE3 = 11
    WARDROBE4 = 12
    WARDROBE5 = 13
    WARDROBE6 = 14
    WARDROBE7 = 15
    WARDROBE8 = 16
    RECYCLE = 17


# Containers that can be equipped from
EQUIPPABLE_CONTAINERS = {
    Container.INVENTORY,
    Container.WARDROBE,
    Container.WARDROBE2,
    Container.WARDROBE3,
    Container.WARDROBE4,
    Container.WARDROBE5,
    Container.WARDROBE6,
    Container.WARDROBE7,
    Container.WARDROBE8,
}


@dataclass
class Stats:
    """
    Normalized stat container.
    
    All stats are stored as integers.
    Percentages are stored as basis points (100 = 1%).
    """
    # Primary stats
    STR: int = 0
    DEX: int = 0
    VIT: int = 0
    AGI: int = 0
    INT: int = 0
    MND: int = 0
    CHR: int = 0
    
    # HP/MP
    HP: int = 0
    MP: int = 0
    
    # Offensive stats
    accuracy: int = 0
    attack: int = 0
    ranged_accuracy: int = 0
    ranged_attack: int = 0
    magic_accuracy: int = 0
    magic_attack: int = 0  # Magic Attack Bonus
    magic_damage: int = 0
    
    # Weapon stats
    damage: int = 0
    delay: int = 0
    
    # Haste (in basis points, 1000 = 10%)
    # gear_haste: from equipment, caps at 25% (2500)
    # magic_haste: from spells/songs, caps at 43.75% (4375) - typically not on gear
    # ja_haste: from job abilities, caps at 25% (2500) - never on gear
    gear_haste: int = 0
    magic_haste: int = 0  # Rarely on gear, but included for completeness
    
    # Store TP
    store_tp: int = 0
    
    # Dual Wield (in basis points)
    dual_wield: int = 0
    
    # Multi-attack (in basis points)
    double_attack: int = 0
    triple_attack: int = 0
    quad_attack: int = 0
    
    # Critical hit (in basis points)
    crit_rate: int = 0
    crit_damage: int = 0
    magic_crit_rate: int = 0    # Magic crit hit rate (e.g., Locus Ring)
    magic_crit_damage: int = 0  # Magic crit hit damage bonus
    
    # Weaponskill
    ws_damage: int = 0  # Weaponskill damage bonus (basis points)
    ws_acc: int = 0     # Weaponskill accuracy bonus
    
    # Defensive stats
    defense: int = 0
    evasion: int = 0
    magic_evasion: int = 0
    magic_defense: int = 0
    
    # Damage taken (in basis points, negative = reduction)
    damage_taken: int = 0       # General DT (applies to all damage types)
    physical_dt: int = 0        # Physical Damage Taken (PDT)
    magical_dt: int = 0         # Magical Damage Taken (MDT)
    breath_dt: int = 0          # Breath Damage Taken (BDT)
    
    # Magic stats (in basis points where applicable)
    magic_burst_bonus: int = 0      # Magic Burst Bonus (capped at 4000 = 40% from gear)
    cure_potency: int = 0           # Cure Potency (capped at 5000 = 50%)
    cure_potency_ii: int = 0        # Cure Potency Received (capped at 3000 = 30%)
    fast_cast: int = 0              # Fast Cast (capped at 8000 = 80%)
    
    # Magic skill bonuses (from gear)
    healing_magic_skill: int = 0
    enfeebling_magic_skill: int = 0
    enhancing_magic_skill: int = 0
    elemental_magic_skill: int = 0
    divine_magic_skill: int = 0
    dark_magic_skill: int = 0
    singing_skill: int = 0
    wind_instrument_skill: int = 0
    string_instrument_skill: int = 0
    ninjutsu_skill: int = 0
    blue_magic_skill: int = 0
    geomancy_skill: int = 0
    handbell_skill: int = 0
    summoning_magic_skill: int = 0
    
    # Combat skill values (character's actual skill cap, not just gear bonuses)
    # These represent the player's skill level for each weapon type
    hand_to_hand_skill: int = 0
    dagger_skill: int = 0
    sword_skill: int = 0
    great_sword_skill: int = 0
    axe_skill: int = 0
    great_axe_skill: int = 0
    scythe_skill: int = 0
    polearm_skill: int = 0
    katana_skill: int = 0
    great_katana_skill: int = 0
    club_skill: int = 0
    staff_skill: int = 0
    archery_skill: int = 0
    marksmanship_skill: int = 0
    throwing_skill: int = 0
    evasion_skill: int = 0
    shield_skill: int = 0
    parrying_skill: int = 0
    guard_skill: int = 0
    
    # Magic skill values (character's actual skill cap)
    healing_magic_skill_cap: int = 0
    enfeebling_magic_skill_cap: int = 0
    enhancing_magic_skill_cap: int = 0
    elemental_magic_skill_cap: int = 0
    divine_magic_skill_cap: int = 0
    dark_magic_skill_cap: int = 0
    singing_skill_cap: int = 0
    string_skill_cap: int = 0
    wind_skill_cap: int = 0
    ninjutsu_skill_cap: int = 0
    summoning_skill_cap: int = 0
    blue_magic_skill_cap: int = 0
    geomancy_skill_cap: int = 0
    
    # Magic effect bonuses
    enfeebling_effect: int = 0      # Enfeebling magic effect +
    enhancing_duration: int = 0     # Enhancing magic duration (basis points)
    enfeebling_duration: int = 0    # Enfeebling magic duration (basis points)
    
    # Dark Magic potency
    drain_aspir_potency: int = 0    # Drain/Aspir potency bonus (basis points)
    
    # Absorb spell bonuses (DRK)
    # Per BG-Wiki: "Dark Magic does nothing for the potency of Absorb spells"
    # Potency comes from equipment bonuses, not skill
    absorb_potency: int = 0         # "Absorb" effect potency +% (basis points)
    absorb_effect_duration: int = 0 # "Absorb" effect duration +% (basis points)
    dark_magic_duration: int = 0    # Dark magic duration +% (basis points)
    
    # Enspell damage bonuses (RDM)
    sword_enhancement_flat: int = 0   # "Sword enhancement spell damage +N" (flat damage)
    sword_enhancement_percent: int = 0 # "Sword enhancement spell dmg. +N%" (basis points)
    
    # Damage limit bonuses (flat values, added to damage cap)
    physical_damage_limit: int = 0  # Physical damage limit+
    magical_damage_limit: int = 0   # Magical damage limit+
    
    # ==========================================================================
    # TP-RELATED STATS (for wsdist compatibility)
    # ==========================================================================
    tp_bonus: int = 0            # TP Bonus (flat, adds to WS TP)
    daken: int = 0               # NIN Daken shuriken throw % (integer %)
    martial_arts: int = 0        # MNK Martial Arts delay reduction
    zanshin: int = 0             # SAM Zanshin retry % (integer %)
    kick_attacks: int = 0        # MNK Kick Attacks % (integer %)
    kick_attacks_dmg: int = 0    # MNK Kick Attacks damage+
    subtle_blow: int = 0         # Subtle Blow (integer)
    subtle_blow_ii: int = 0      # Subtle Blow II (integer)
    fencer: int = 0              # Fencer trait level (1-8)
    conserve_tp: int = 0         # Conserve TP % (integer %)
    regain: int = 0              # Regain (TP/tick)
    
    # ==========================================================================
    # RESOURCE RECOVERY (MP/HP per tick) - PASSIVE GEAR
    # ==========================================================================
    # These are for gear that gives passive regen/refresh (DT/Idle sets)
    # e.g., 'Adds "Refresh" effect' or '"Refresh"+2' augments
    refresh: int = 0             # Refresh (MP/tick) - passive from gear
    regen: int = 0               # Regen (HP/tick) - passive from gear
    convert_mp: int = 0          # Convert MP recovered bonus
    
    # ==========================================================================
    # MIDCAST REGEN/REFRESH SPELL STATS
    # ==========================================================================
    # These affect Regen/Refresh SPELLS you cast (for sets.midcast.Regen/Refresh)
    # NOT passive gear-based recovery
    
    # Regen spell potency (adds flat HP/tick to Regen spells)
    # e.g., Bookworm's Cape '"Regen" potency+8', Telchine augments
    regen_potency: int = 0       # Flat HP/tick added to Regen spell
    
    # Regen spell duration (flat seconds added)
    # e.g., Telchine Chasuble 'Regen effect duration +27'
    # This is DIFFERENT from general enhancing duration %
    regen_effect_duration: int = 0  # Flat seconds added to Regen duration
    
    # Refresh spell potency (adds flat MP/tick to Refresh spells)
    # Rare stat - most Refresh optimization is duration-based
    refresh_potency: int = 0     # Flat MP/tick added to Refresh spell
    
    # Refresh spell duration (flat seconds added)
    refresh_effect_duration: int = 0  # Flat seconds added to Refresh duration
    
    # ==========================================================================
    # ENHANCING MAGIC DURATION (Important: Augmented vs Non-Augmented)
    # ==========================================================================
    # Per BG-Wiki, these apply at DIFFERENT steps of the duration formula!
    # Non-augmented: Embla Sash, Ammurapi Shield, etc. (already have enhancing_duration)
    # Augmented: Telchine 'Enh. Mag. eff. dur. +10' augments (separate multiplier)
    enhancing_duration_augment: int = 0  # Augmented gear % (basis points, e.g., Telchine)
    
    # ==========================================================================
    # OCCASIONAL ATTACKS (OA2-OA8, FUA)
    # ==========================================================================
    # These are rare - mainly on Mythic aftermath and Kraken Club
    oa2: int = 0                 # Occasionally attacks 2x %
    oa3: int = 0                 # Occasionally attacks 3x %
    oa4: int = 0                 # Occasionally attacks 4x %
    oa5: int = 0                 # Occasionally attacks 5x %
    oa6: int = 0                 # Occasionally attacks 6x %
    oa7: int = 0                 # Occasionally attacks 7x %
    oa8: int = 0                 # Occasionally attacks 8x %
    fua: int = 0                 # Follow-up Attack % (Samurai Empyrean)
    
    # ==========================================================================
    # DAMAGE MODIFIERS
    # ==========================================================================
    pdl: int = 0                 # Physical Damage Limit % (basis points)
    skillchain_bonus: int = 0    # Skillchain Bonus % (basis points)
    da_damage_pct: int = 0       # DA damage % bonus
    ta_damage_pct: int = 0       # TA damage % bonus
    
    # ==========================================================================
    # RANGED-SPECIFIC
    # ==========================================================================
    double_shot: int = 0         # Double Shot % (integer %)
    triple_shot: int = 0         # Triple Shot % (integer %)
    true_shot: int = 0           # True Shot % (integer %)
    recycle: int = 0             # Recycle % (integer %)
    barrage: int = 0             # Barrage +N shots
    
    # ==========================================================================
    # MAGIC-SPECIFIC
    # ==========================================================================
    magic_accuracy_skill: int = 0    # Magic Accuracy Skill (different from M.Acc)
    magic_burst_damage_ii: int = 0   # Magic Burst Damage II % (basis points)
    
    # ==========================================================================
    # JOB-SPECIFIC STATS
    # ==========================================================================
    # RDM EnSpell
    enspell_damage: int = 0      # EnSpell Damage flat+
    enspell_damage_pct: int = 0  # EnSpell Damage % (basis points)
    
    # NIN Ninjutsu
    ninjutsu_magic_attack: int = 0   # Ninjutsu Magic Attack+
    ninjutsu_damage_pct: int = 0     # Ninjutsu Damage % (basis points)
    
    # SMN Blood Pact
    blood_pact_damage: int = 0   # Blood Pact Damage % (basis points)
    
    # DRK/BLM Occult Acumen
    occult_acumen: int = 0       # Occult Acumen (TP from magic)
    
    # Elemental bonuses (stored per element)
    fire_elemental_bonus: int = 0
    ice_elemental_bonus: int = 0
    wind_elemental_bonus: int = 0
    earth_elemental_bonus: int = 0
    lightning_elemental_bonus: int = 0
    water_elemental_bonus: int = 0
    light_elemental_bonus: int = 0
    dark_elemental_bonus: int = 0
    
    # Skill bonuses (generic)
    skill_bonuses: Dict[str, int] = field(default_factory=dict)
    
    # Special effects (stored as strings for now)
    special_effects: List[str] = field(default_factory=list)
    
    def __add__(self, other: 'Stats') -> 'Stats':
        """Add two Stats objects together."""
        if not isinstance(other, Stats):
            return NotImplemented
        
        result = Stats()
        for field_name in self.__dataclass_fields__:
            self_val = getattr(self, field_name)
            other_val = getattr(other, field_name)
            
            if isinstance(self_val, int):
                setattr(result, field_name, self_val + other_val)
            elif isinstance(self_val, dict):
                merged = dict(self_val)
                for k, v in other_val.items():
                    merged[k] = merged.get(k, 0) + v
                setattr(result, field_name, merged)
            elif isinstance(self_val, list):
                setattr(result, field_name, self_val + other_val)
        
        return result
    
    def copy(self) -> 'Stats':
        """Create a copy of this Stats object."""
        result = Stats()
        for field_name in self.__dataclass_fields__:
            val = getattr(self, field_name)
            if isinstance(val, dict):
                setattr(result, field_name, dict(val))
            elif isinstance(val, list):
                setattr(result, field_name, list(val))
            else:
                setattr(result, field_name, val)
        return result


@dataclass
class ItemBase:
    """
    Base item data from items.lua resource file.
    
    This represents the static item definition, not an instance.
    """
    id: int
    name: str
    name_log: str = ''
    
    # Category
    category: str = ''  # 'Weapon', 'Armor', etc.
    item_type: int = 0
    
    # Equipment restrictions
    jobs: int = 0       # Job bitmask
    level: int = 0
    item_level: int = 0
    superior_level: int = 0
    races: int = 0      # Race bitmask
    slots: int = 0      # Slot bitmask
    
    # Weapon-specific
    skill: int = 0      # Weapon skill type
    damage: int = 0
    delay: int = 0
    
    # Flags
    flags: int = 0
    stack: int = 1
    targets: int = 0
    
    # Base stats (from item_descriptions or base attributes)
    # These are UNCONDITIONAL stats that always apply
    base_stats: Stats = field(default_factory=Stats)
    
    # Conditional stats - only apply in specific situations
    # Pet stats (BST, SMN, PUP, DRG pets)
    pet_stats: Optional[Stats] = None
    # Automaton-specific stats (PUP)
    automaton_stats: Optional[Stats] = None
    # Dynamis zone stats
    dynamis_stats: Optional[Stats] = None
    # Avatar-specific stats (SMN)
    avatar_stats: Optional[Stats] = None
    # Wyvern-specific stats (DRG)
    wyvern_stats: Optional[Stats] = None
    # Daytime-only stats
    daytime_stats: Optional[Stats] = None
    # Day-specific stats (keyed by day name: 'firesday', 'earthsday', etc.)
    day_stats: Optional[Dict[str, Stats]] = None
    
    # Description text (for parsing additional stats)
    description: str = ''
    
    # Multi-slot flag - True if this item blocks additional slots
    # (e.g., Onca Suit occupies body but blocks legs)
    # These items are excluded from optimization since their stats
    # can't be fairly compared to single-slot items
    is_multi_slot: bool = False
    
    def can_equip(self, job: Job) -> bool:
        """Check if the given job can equip this item."""
        if self.jobs == 0:
            return True  # All jobs
        return bool(self.jobs & JOB_BITMASK.get(job, 0))
    
    def get_slots(self) -> List[Slot]:
        """Get list of slots this item can be equipped in."""
        result = []
        for slot, mask in SLOT_BITMASK.items():
            if self.slots & mask:
                result.append(slot)
        return result


@dataclass
class ItemInstance:
    """
    An instance of an item in inventory.
    
    This represents a specific item with augments, location, etc.
    """
    base: ItemBase
    
    # Location
    container: Container
    slot: int
    
    # Instance data
    count: int = 1
    status: int = 0
    
    # Augments (raw)
    augments_raw: List[Any] = field(default_factory=list)
    extdata: str = ''
    
    # Path augment rank (1-25, only meaningful for path-augmented items)
    rank: int = 0
    
    # Resolved augment stats
    augment_stats: Stats = field(default_factory=Stats)
    
    # Flag indicating if path stats were successfully resolved from database
    path_stats_resolved: bool = False
    
    # Cached total stats
    _total_stats: Optional[Stats] = field(default=None, repr=False)
    
    @property
    def id(self) -> int:
        return self.base.id
    
    @property
    def name(self) -> str:
        return self.base.name
    
    @property
    def total_stats(self) -> Stats:
        """Get total stats (base + augments)."""
        if self._total_stats is None:
            self._total_stats = self.base.base_stats + self.augment_stats
        return self._total_stats
    
    def invalidate_cache(self):
        """Clear cached calculations."""
        self._total_stats = None
    
    def can_equip_from(self) -> bool:
        """Check if this item can be equipped (is in a wardrobe)."""
        return self.container in EQUIPPABLE_CONTAINERS
    
    @property
    def has_path_augment(self) -> bool:
        """Check if this item has a Path augment (A/B/C/D)."""
        for aug in self.augments_raw:
            if isinstance(aug, str) and 'Path:' in aug:
                return True
        return False
    
    @property
    def path_augment(self) -> Optional[str]:
        """Get the path augment string if present."""
        for aug in self.augments_raw:
            if isinstance(aug, str) and 'Path:' in aug:
                return aug
        return None
    
    @property
    def gearswap_name(self) -> str:
        """
        Get the name to use in GearSwap sets.
        
        For augmented items, this includes augment syntax.
        """
        if not self.augments_raw:
            return self.base.name
        
        # Format augments for GearSwap
        aug_parts = []
        for aug in self.augments_raw:
            if aug and aug != 'none' and aug != '':
                aug_parts.append(str(aug))
        
        if not aug_parts:
            return self.base.name
        
        # Return as table with augments
        # This will be formatted properly by the Lua generator
        return self.base.name


@dataclass
class GearSet:
    """A complete gear set for a specific purpose."""
    name: str
    items: Dict[Slot, Optional[ItemInstance]] = field(default_factory=dict)
    
    # Metadata
    purpose: str = ''  # 'TP', 'WS', 'Idle', etc.
    conditions: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def total_stats(self) -> Stats:
        """Calculate total stats for the set."""
        total = Stats()
        for item in self.items.values():
            if item:
                total = total + item.total_stats
        return total
    
    def get_slots_filled(self) -> Set[Slot]:
        """Get set of slots that have items."""
        return {slot for slot, item in self.items.items() if item is not None}
    
    def get_slots_empty(self) -> Set[Slot]:
        """Get set of slots without items."""
        all_slots = set(Slot)
        return all_slots - self.get_slots_filled()


@dataclass
class BuffContext:
    """
    Represents expected buffs for optimization context.
    
    Used to calculate things like how much gear DW is needed.
    All values in basis points (100 = 1%).
    """
    # Haste buffs
    magic_haste: int = 0      # From spells: Haste (1500), Haste II (3000), capped (4375)
    ja_haste: int = 0         # From job abilities: Haste Samba, etc.
    
    # Job's native Dual Wield trait
    dw_trait: int = 0         # NIN99: 3500, DNC80: 3000, THF83: 1000, etc.
    
    # Common presets
    @classmethod
    def no_buffs(cls) -> 'BuffContext':
        return cls(magic_haste=0, ja_haste=0)
    
    @classmethod
    def haste_1(cls, dw_trait: int = 0) -> 'BuffContext':
        """Haste spell (15%)"""
        return cls(magic_haste=1500, ja_haste=0, dw_trait=dw_trait)
    
    @classmethod
    def haste_2(cls, dw_trait: int = 0) -> 'BuffContext':
        """Haste II / Erratic Flutter (30%)"""
        return cls(magic_haste=3000, ja_haste=0, dw_trait=dw_trait)
    
    @classmethod
    def max_haste(cls, dw_trait: int = 0) -> 'BuffContext':
        """Capped magic haste (43.75%) + some JA haste"""
        return cls(magic_haste=4375, ja_haste=1000, dw_trait=dw_trait)
    
    def get_dw_needed(self, gear_haste: int = 2500) -> int:
        """
        Calculate gear DW needed to cap delay at 80%.
        
        Args:
            gear_haste: Expected gear haste (default: capped at 2500)
        
        Returns:
            Required gear DW in basis points to hit 80% delay cap
        """
        # Apply caps
        gear_h = min(gear_haste, 2500)  # 25% gear haste cap
        magic_h = min(self.magic_haste, 4375)  # 43.75% magic haste cap
        ja_h = min(self.ja_haste, 2500)  # 25% JA haste cap
        
        # Total haste factor (what remains after haste)
        total_haste_pct = (gear_h + magic_h + ja_h) / 10000
        haste_factor = 1.0 - total_haste_pct
        
        # We need: (1 - total_dw) * haste_factor = 0.20 (20% minimum delay)
        # Solving: total_dw = 1 - (0.20 / haste_factor)
        if haste_factor <= 0.20:
            return 0  # Already at cap with haste alone
        
        needed_total_dw = (1.0 - (0.20 / haste_factor)) * 10000
        
        # Subtract job trait to get gear DW needed
        gear_dw_needed = needed_total_dw - self.dw_trait
        
        return max(0, int(gear_dw_needed))


@dataclass
class OptimizationProfile:
    """
    Defines weights and constraints for gear optimization.
    
    Supports two scoring modes:
    1. Weighted scoring (default): Uses stat weights for fast scoring
    2. Simulation scoring: Uses actual combat formulas for accurate scoring
    
    Simulation scoring is recommended for TP sets where stat interactions
    (Store TP + multi-attack + haste) cannot be captured by weighted scoring.
    """
    name: str
    
    # Stat weights (higher = more important)
    # Used for dominance filtering AND scoring (when use_simulation=False)
    weights: Dict[str, float] = field(default_factory=dict)
    
    # Minimum constraints (stat must be >= value)
    minimums: Dict[str, int] = field(default_factory=dict)
    
    # Maximum constraints (stat must be <= value)
    maximums: Dict[str, int] = field(default_factory=dict)
    
    # Soft caps (diminishing returns above cap - value above cap worth 10%)
    soft_caps: Dict[str, int] = field(default_factory=dict)
    
    # Hard caps (stats wasted above this value - no benefit)
    # Examples: DT (-5000), gear_haste (2500), magic_burst_bonus (4000)
    hard_caps: Dict[str, int] = field(default_factory=dict)
    
    # Buff context for DW/haste calculations
    buff_context: Optional[BuffContext] = None
    
    # Required slots to optimize (None = all except excluded)
    slots: Optional[Set[Slot]] = None
    
    # Slots to exclude from optimization (default: main/sub weapons)
    # Weapon swaps cause TP loss, so typically excluded
    exclude_slots: Set[Slot] = field(default_factory=lambda: {Slot.MAIN, Slot.SUB})
    
    # Job requirement
    job: Optional[Job] = None
    
    # Character level (for item level requirements)
    character_level: int = 99
    
    # Item level cap (for iLvl gear)
    item_level_cap: int = 119
    
    # Legacy compatibility: map old 'caps' to 'soft_caps'
    caps: Dict[str, int] = field(default_factory=dict)
    
    # ==========================================================================
    # SIMULATION SCORING SETTINGS
    # ==========================================================================
    # When use_simulation=True, the optimizer uses combat formulas instead of
    # weighted stats for final scoring. This correctly handles stat interactions
    # like the Store TP / multi-attack tradeoff.
    
    # Enable simulation-based scoring (default: False for backwards compatibility)
    use_simulation: bool = False
    
    # Simulation mode: 'tp_rate', 'ws_damage', 'dps', or 'weighted' (fallback)
    # - tp_rate: Score by TP per second (for TP sets)
    # - ws_damage: Score by WS damage (for WS sets) 
    # - dps: Score by full DPS cycle (for hybrid analysis)
    # - weighted: Use traditional weighted scoring
    simulation_mode: str = 'weighted'
    
    # Weapon parameters (required for simulation)
    weapon_delay: int = 0          # Main weapon delay
    weapon_damage: int = 0         # Main weapon damage (for WS/DPS modes)
    weapon_type: Optional[str] = None  # Weapon type string
    
    # Dual wield configuration
    is_dual_wield: bool = False    # Whether dual wielding
    off_hand_delay: int = 0        # Off-hand weapon delay
    off_hand_damage: int = 0       # Off-hand weapon damage
    
    # Target assumptions (for accuracy-dependent scoring)
    assumed_hit_rate: float = 0.95  # Default: 95% hit rate (used if target_evasion not set)
    target_evasion: int = 0         # Target's evasion (if >0, calculates hit rate from accuracy)
    base_accuracy: int = 1100       # Player's base accuracy (skill + DEX + buffs, before gear)
    
    def __post_init__(self):
        # Merge legacy 'caps' into 'soft_caps' for backwards compatibility
        if self.caps and not self.soft_caps:
            self.soft_caps = dict(self.caps)


# Pre-defined optimization profiles
PROFILE_MELEE_TP = OptimizationProfile(
    name='Melee TP',
    weights={
        'store_tp': 10.0,
        'accuracy': 5.0,
        'double_attack': 8.0,
        'triple_attack': 12.0,
        'quad_attack': 15.0,
        'gear_haste': 7.0,
        'dual_wield': 6.0,      # Weight DW for delay reduction
        'attack': 1.0,
        'DEX': 0.5,
        'STR': 0.3,
    },
    hard_caps={
        'gear_haste': 2500,     # 25% gear haste cap - no benefit above this
    },
    soft_caps={
        'dual_wield': 8000,     # Varies by context - will be adjusted dynamically
    },
    buff_context=BuffContext.haste_2(),  # Default: assume Haste II
    exclude_slots={Slot.MAIN, Slot.SUB},  # Weapon swaps lose TP
)

PROFILE_MELEE_WS = OptimizationProfile(
    name='Melee WS',
    weights={
        'ws_damage': 15.0,
        'attack': 3.0,
        'STR': 2.0,  # Varies by WS
        'DEX': 1.0,
        'accuracy': 2.0,
        'crit_rate': 4.0,
        'crit_damage': 5.0,
    },
    exclude_slots={Slot.MAIN, Slot.SUB},  # Weapon swaps lose TP
)

PROFILE_MAGIC_NUKE = OptimizationProfile(
    name='Magic Nuke',
    weights={
        'magic_attack': 10.0,
        'INT': 5.0,
        'magic_damage': 8.0,
        'magic_accuracy': 3.0,
        'magic_burst_bonus': 12.0,
    },
    hard_caps={
        'magic_burst_bonus': 4000,  # 40% MBB cap from gear
    },
    exclude_slots={Slot.MAIN, Slot.SUB},  # Usually keep same weapon for casting
)

PROFILE_IDLE_DT = OptimizationProfile(
    name='Idle DT',
    weights={
        # DT values are negative (e.g., -400 = -4%), so we use negative weights
        # to make more negative DT = higher score
        'physical_dt': -10.0,
        'magical_dt': -8.0,
        'damage_taken': -10.0,
        'HP': 2.0,
        'defense': 0.5,
        'evasion': 0.3,
    },
    hard_caps={
        'damage_taken': -5000,   # -50% DT cap
        'physical_dt': -5000,    # -50% PDT cap
        'magical_dt': -5000,     # -50% MDT cap
    },
    exclude_slots=set(),  # Idle sets CAN include weapons
)


# =============================================================================
# Profile Factory Functions
# =============================================================================

def create_tp_profile(name: str = 'TP Set',
                     job: Optional[Job] = None,
                     dw_trait: int = 0,
                     magic_haste: int = 3000,
                     ja_haste: int = 0,
                     prioritize_dw: bool = False,
                     weapon_delay: int = 0,
                     use_simulation: bool = True,
                     is_dual_wield: bool = False,
                     off_hand_delay: int = 0) -> OptimizationProfile:
    """
    Create a TP set optimization profile with specific buff context.
    
    When use_simulation=True (default), scoring uses actual TP/second simulation
    instead of weighted stats. This correctly handles:
    - Store TP / multi-attack interaction (Zoar Subligar bug)
    - Haste / DW breakpoints
    - Actual TP gain rate optimization
    
    Args:
        name: Profile name
        job: Job requirement
        dw_trait: Job's Dual Wield trait in basis points (e.g., NIN99=3500, DNC80=3000)
        magic_haste: Expected magic haste in basis points (Haste II=3000, capped=4375)
        ja_haste: Expected JA haste in basis points
        prioritize_dw: If True, weight DW more heavily (for jobs that need DW to cap)
        weapon_delay: Main hand weapon delay (REQUIRED for simulation scoring)
        use_simulation: If True, use TP/second simulation for scoring (default: True)
        is_dual_wield: Whether the job is dual wielding
        off_hand_delay: Off-hand weapon delay (if dual wielding)
    
    Returns:
        OptimizationProfile configured for TP building
        
    Note:
        If weapon_delay is 0 and use_simulation is True, simulation will fall back
        to weighted scoring. Always provide weapon_delay for accurate TP optimization.
    """
    ctx = BuffContext(magic_haste=magic_haste, ja_haste=ja_haste, dw_trait=dw_trait)
    dw_needed = ctx.get_dw_needed()
    
    # Adjust DW weight based on need
    dw_weight = 8.0 if prioritize_dw and dw_needed > 0 else 6.0
    
    # Determine simulation mode
    # Only use simulation if we have weapon delay (required for TP calculation)
    simulation_mode = 'tp_rate' if use_simulation and weapon_delay > 0 else 'weighted'
    
    return OptimizationProfile(
        name=name,
        weights={
            'store_tp': 10.0,
            'accuracy': 5.0,
            'double_attack': 8.0,
            'triple_attack': 12.0,
            'quad_attack': 15.0,
            'gear_haste': 7.0,
            'dual_wield': dw_weight,
            'attack': 1.0,
            'DEX': 0.5,
            'STR': 0.3,
        },
        hard_caps={
            'gear_haste': 2500,
        },
        soft_caps={
            'dual_wield': max(dw_needed, 1000),  # Dynamic based on context
        },
        buff_context=ctx,
        exclude_slots={Slot.MAIN, Slot.SUB},
        job=job,
        # Simulation settings
        use_simulation=use_simulation and weapon_delay > 0,
        simulation_mode=simulation_mode,
        weapon_delay=weapon_delay,
        is_dual_wield=is_dual_wield,
        off_hand_delay=off_hand_delay,
    )


def create_dt_profile(name: str = 'DT Set',
                     job: Optional[Job] = None,
                     include_weapons: bool = True,
                     prioritize_pdt: bool = False,
                     prioritize_mdt: bool = False) -> OptimizationProfile:
    """
    Create a DT set optimization profile.
    
    Args:
        name: Profile name
        job: Job requirement
        include_weapons: If True, allow weapon selection (for idle sets)
        prioritize_pdt: If True, weight PDT more heavily
        prioritize_mdt: If True, weight MDT more heavily
    
    Returns:
        OptimizationProfile configured for damage reduction
    
    Note on Defensive Stat Weights:
        The current weights for VIT, Defense, and Evasion are approximations.
        Their true value depends on enemy stats. See TODO below for formulas
        to implement target-specific optimization.
    
    TODO: Target-Specific DT Optimization
    =====================================
    To properly weight defensive stats, we need enemy stats. Here are the
    formulas from combat_formulas.py:
    
    EVASION → Hit Rate Reduction:
        hit_rate = 0.75 + ((enemy_acc - player_eva) * 0.005)
        hit_rate = clamp(hit_rate, 0.20, 0.95)
        
        - Each 1 Evasion reduces enemy hit rate by 0.5%
        - At 95% enemy hit rate: +100 eva → 45% hit rate (huge value!)
        - At 20% enemy hit rate (floor): evasion is worthless
        - Effective damage reduction = (old_hit_rate - new_hit_rate) / old_hit_rate
        
        Example (Odyssey boss, ~90% hit rate):
            +50 evasion → 90% - 25% = 65% hit rate
            Damage reduction = (90-65)/90 = 27.8% effective DT
    
    VIT → fSTR Reduction (reduces damage per hit):
        dSTR = enemy_str - player_vit
        
        fSTR calculation (each point reduces enemy damage):
            if dSTR >= 0:
                if dSTR <= 12:   fSTR = dSTR // 2      → 2 VIT = -1 damage/hit
                elif dSTR <= 24: fSTR = 6 + (dSTR-12)//4  → 4 VIT = -1 damage
                else:            fSTR = 9 + (dSTR-24)//8  → 8 VIT = -1 damage
            else:
                fSTR = dSTR // 2  (negative, reduces enemy damage)
        
        fSTR is added directly to base damage, so:
            damage = (weapon_dmg + fSTR + WSC) * pDIF
        
        Example (enemy STR 300, player VIT 200, dSTR=100):
            fSTR = 9 + (100-24)//8 = 9 + 9 = 18 damage added per hit
            +50 VIT → dSTR=50 → fSTR = 9 + (50-24)//8 = 9 + 3 = 12
            Reduction = 6 damage per hit (value depends on total hit damage)
    
    DEFENSE → pDIF Reduction:
        cRatio = enemy_attack / player_defense
        pDIF scales with cRatio (complex piecewise function)
        
        Approximate relationship:
            pDIF ≈ cRatio for cRatio in [0.5, 2.0] range
            +10% defense ≈ -9% pDIF ≈ -9% damage (diminishing returns)
        
        Example (enemy attack 1500, defense 1000):
            cRatio = 1.5 → pDIF ≈ 1.5
            +100 defense → cRatio = 1500/1100 = 1.36 → pDIF ≈ 1.36
            Damage reduction ≈ (1.5-1.36)/1.5 = 9.3%
    
    MAGIC EVASION → Magic Hit Rate:
        Similar to physical evasion but for spells.
        Affects both damage spells landing and enfeebles.
    
    Future Enhancement:
        Create create_dt_profile_for_target(target: TargetStats) that:
        1. Takes enemy stats (STR, ACC, ATK, etc.)
        2. Calculates marginal value of each defensive stat
        3. Returns weights proportional to actual damage reduction
        
        Could also create presets:
        - create_dt_profile_odyssey_boss()
        - create_dt_profile_dynamis_wave3()
        - create_dt_profile_apex_mobs()
        
        Reference target stats in simulation.py TARGETS dict:
        - odyssey_boss: DEF 1600, EVA 1400, VIT 280, AGI 250
        - apex_toad: DEF 1350, EVA 1200, VIT 220, AGI 180
        - etc.
    """
    # Base weights for DT stats (negative because lower is better)
    dt_weight = -10.0
    pdt_weight = -12.0 if prioritize_pdt else -10.0
    mdt_weight = -12.0 if prioritize_mdt else -8.0
    
    # Defensive stat weights (approximations - see TODO above for proper calculation)
    # These assume a "typical" high-end enemy where all stats have some value
    return OptimizationProfile(
        name=name,
        weights={
            # Primary DT stats (most valuable, directly cap at -50%)
            'damage_taken': dt_weight,
            'physical_dt': pdt_weight,
            'magical_dt': mdt_weight,
            
            # HP is always valuable as a buffer
            'HP': 2.0,
            
            # VIT reduces enemy fSTR, lowering damage per hit
            # At high dSTR (enemy STR >> player VIT), 8 VIT = -1 damage/hit
            # More valuable when closer to enemy STR
            'VIT': 0.8,
            
            # Defense reduces pDIF ratio
            # Diminishing returns but always provides some reduction
            'defense': 0.5,
            
            # Evasion reduces hit rate (0.5% per point)
            # Extremely valuable if enemy isn't at 95% cap
            # Worthless if enemy is already at 20% floor
            'evasion': 0.4,
            
            # Magic evasion for spell resistance
            'magic_evasion': 0.3,
            
            # AGI affects enemy crit rate via dDEX formula (enemy DEX vs player AGI)
            # dDEX crit bonus caps around 5-6%, so AGI has limited but real value
            'AGI': 0.3,
        },
        hard_caps={
            'damage_taken': -5000,   # -50% cap
            'physical_dt': -5000,    # -50% cap  
            'magical_dt': -5000,     # -50% cap
        },
        exclude_slots=set() if include_weapons else {Slot.MAIN, Slot.SUB},
        job=job,
    )


def create_ws_profile(name: str = 'WS Set',
                     job: Optional[Job] = None,
                     primary_stat: str = 'STR',
                     secondary_stat: Optional[str] = None,
                     ftp_replicating: bool = False) -> OptimizationProfile:
    """
    Create a WS set optimization profile.
    
    Args:
        name: Profile name
        job: Job requirement
        primary_stat: Primary stat for WS (STR, DEX, VIT, etc.)
        secondary_stat: Secondary stat if WS has dual scaling
        ftp_replicating: If True, also weight multi-attack (for fTP replicating WSes)
    
    Returns:
        OptimizationProfile configured for weaponskill damage
    """
    weights = {
        'ws_damage': 15.0,
        'attack': 3.0,
        'accuracy': 2.0,
        'crit_rate': 4.0,
        'crit_damage': 5.0,
    }
    
    # Set primary stat weight
    weights[primary_stat] = 2.5
    
    # Set secondary stat weight if provided
    if secondary_stat:
        weights[secondary_stat] = 1.5
    
    # Add multi-attack for fTP replicating WSes
    if ftp_replicating:
        weights['double_attack'] = 3.0
        weights['triple_attack'] = 5.0
        weights['quad_attack'] = 6.0
    
    return OptimizationProfile(
        name=name,
        weights=weights,
        exclude_slots={Slot.MAIN, Slot.SUB},
        job=job,
    )


def create_acc_tp_profile(name: str = 'Acc/TP Set',
                          job: Optional[Job] = None,
                          dw_trait: int = 0,
                          magic_haste: int = 3000,
                          ja_haste: int = 0) -> OptimizationProfile:
    """
    Create an Accuracy-focused TP set with tiered priorities.
    
    Priority order (strict):
        1. Accuracy - maximized first
        2. TP stats - Store TP, multi-attack, haste, DW
        3. DT - damage reduction as tiebreaker
    
    Uses tiered weights (100:10:1 ratio) to enforce priority ordering.
    
    Args:
        name: Profile name
        job: Job requirement
        dw_trait: Job's Dual Wield trait in basis points
        magic_haste: Expected magic haste in basis points (Haste II=3000)
        ja_haste: Expected JA haste in basis points
    
    Returns:
        OptimizationProfile configured for accuracy-first TP building
    """
    ctx = BuffContext(magic_haste=magic_haste, ja_haste=ja_haste, dw_trait=dw_trait)
    dw_needed = ctx.get_dw_needed()
    
    # Tiered weights enforce priority: Accuracy >> TP >> DT
    # Tier 1: Accuracy (weight ~100)
    # Tier 2: TP stats (weights ~10)  
    # Tier 3: DT (weights ~1)
    
    return OptimizationProfile(
        name=name,
        weights={
            # Tier 1: Accuracy (highest priority)
            'accuracy': 100.0,
            
            # Tier 2: TP stats (secondary priority)
            'store_tp': 10.0,
            'double_attack': 8.0,
            'triple_attack': 12.0,
            'quad_attack': 15.0,
            'gear_haste': 7.0,
            'dual_wield': 6.0,
            'attack': 1.0,
            'DEX': 0.5,
            'STR': 0.3,
            
            # Tier 3: DT (tertiary/tiebreaker)
            'damage_taken': -0.1,
            'physical_dt': -0.1,
            'magical_dt': -0.08,
        },
        hard_caps={
            'gear_haste': 2500,      # 25% gear haste cap
            'damage_taken': -5000,   # -50% DT cap
            'physical_dt': -5000,
            'magical_dt': -5000,
        },
        soft_caps={
            'dual_wield': max(dw_needed, 1000),
        },
        buff_context=ctx,
        exclude_slots={Slot.MAIN, Slot.SUB},
        job=job,
    )


def create_hybrid_tp_dt_profile(name: str = 'Hybrid TP/DT Set',
                                job: Optional[Job] = None,
                                dw_trait: int = 0,
                                magic_haste: int = 3000,
                                ja_haste: int = 0,
                                dt_priority: float = 0.5) -> OptimizationProfile:
    """
    Create a hybrid TP/DT set (engaged.DT style).
    
    Balances TP generation with survivability. Use dt_priority to adjust
    the balance between offense and defense.
    
    Args:
        name: Profile name
        job: Job requirement
        dw_trait: Job's Dual Wield trait in basis points
        magic_haste: Expected magic haste in basis points
        ja_haste: Expected JA haste in basis points
        dt_priority: 0.0 = full TP focus, 1.0 = full DT focus, 0.5 = balanced
    
    Returns:
        OptimizationProfile configured for hybrid TP/DT
    """
    ctx = BuffContext(magic_haste=magic_haste, ja_haste=ja_haste, dw_trait=dw_trait)
    dw_needed = ctx.get_dw_needed()
    
    # Scale weights based on dt_priority
    # At 0.0: full TP weights, minimal DT
    # At 0.5: balanced
    # At 1.0: full DT weights, minimal TP
    tp_scale = 1.0 - (dt_priority * 0.7)  # TP scales from 1.0 to 0.3
    dt_scale = 0.3 + (dt_priority * 0.7)  # DT scales from 0.3 to 1.0
    
    return OptimizationProfile(
        name=name,
        weights={
            # TP stats (scaled by tp_scale)
            'store_tp': 10.0 * tp_scale,
            'accuracy': 5.0 * tp_scale,
            'double_attack': 8.0 * tp_scale,
            'triple_attack': 12.0 * tp_scale,
            'quad_attack': 15.0 * tp_scale,
            'gear_haste': 7.0 * tp_scale,
            'dual_wield': 6.0 * tp_scale,
            'attack': 1.0 * tp_scale,
            
            # DT stats (scaled by dt_scale, negative weights)
            'damage_taken': -10.0 * dt_scale,
            'physical_dt': -10.0 * dt_scale,
            'magical_dt': -8.0 * dt_scale,
            'HP': 2.0 * dt_scale,
            'defense': 0.5 * dt_scale,
        },
        hard_caps={
            'gear_haste': 2500,
            'damage_taken': -5000,
            'physical_dt': -5000,
            'magical_dt': -5000,
        },
        soft_caps={
            'dual_wield': max(dw_needed, 1000),
        },
        buff_context=ctx,
        exclude_slots={Slot.MAIN, Slot.SUB},
        job=job,
    )


# =============================================================================
# Magic Profile Factory Functions
# =============================================================================

def create_magic_nuke_profile(name: str = 'Elemental Magic',
                              job: Optional[Job] = None,
                              include_weapons: bool = False) -> OptimizationProfile:
    """
    Create an elemental nuking optimization profile.
    
    Optimizes for raw magic damage without magic burst.
    
    Stat priorities:
        1. Magic Attack Bonus - Primary damage multiplier
        2. INT - Affects dINT scaling and magic accuracy
        3. Magic Damage+ - Flat damage bonus to base D
        4. Elemental Magic Skill - 1:1 with magic accuracy
        5. Magic Accuracy - Landing spells unresisted
    
    Args:
        name: Profile name
        job: Job requirement
        include_weapons: If True, allow weapon selection
    
    Returns:
        OptimizationProfile configured for elemental nuking
    """
    return OptimizationProfile(
        name=name,
        weights={
            'magic_attack': 10.0,
            'INT': 5.0,
            'magic_damage': 8.0,
            'elemental_magic_skill': 4.0,
            'magic_accuracy': 3.0,
        },
        exclude_slots=set() if include_weapons else {Slot.MAIN, Slot.SUB},
        job=job,
    )


def create_magic_burst_profile(name: str = 'Magic Burst',
                               job: Optional[Job] = None,
                               include_weapons: bool = False) -> OptimizationProfile:
    """
    Create a magic burst optimization profile.
    
    Optimizes for magic burst damage. MBB from gear caps at 40% (4000 basis points),
    but trait/JP/gift bonuses are uncapped.
    
    Stat priorities:
        1. Magic Burst Bonus - Multiplier on top of base MB damage (gear cap 40%)
        2. Magic Attack Bonus - Primary damage multiplier
        3. INT - dINT scaling
        4. Magic Damage+ - Flat damage bonus
        5. Magic Accuracy - +100 during MB, but still want to cap
    
    Args:
        name: Profile name
        job: Job requirement
        include_weapons: If True, allow weapon selection
    
    Returns:
        OptimizationProfile configured for magic burst damage
    """
    return OptimizationProfile(
        name=name,
        weights={
            'magic_burst_bonus': 12.0,
            'magic_attack': 10.0,
            'INT': 5.0,
            'magic_damage': 8.0,
            'elemental_magic_skill': 3.0,
            'magic_accuracy': 2.0,
        },
        hard_caps={
            'magic_burst_bonus': 4000,  # 40% MBB cap from gear
        },
        exclude_slots=set() if include_weapons else {Slot.MAIN, Slot.SUB},
        job=job,
    )


def create_enfeebling_profile(name: str = 'Enfeebling Magic',
                              job: Optional[Job] = None,
                              potency_focus: bool = False,
                              include_weapons: bool = False) -> OptimizationProfile:
    """
    Create an enfeebling magic optimization profile.
    
    Enfeebling skill affects BOTH accuracy AND potency for most spells.
    MND affects Slow/Paralyze/Addle potency (dMND).
    INT affects Blind/Gravity potency (dINT).
    
    Stat priorities (accuracy focus):
        1. Enfeebling Magic Skill - Accuracy AND potency
        2. Magic Accuracy - Landing enfeebles
        3. MND - dMND for MND-based enfeebles
        4. INT - dINT for INT-based enfeebles
    
    Stat priorities (potency focus):
        1. Enfeebling Magic Skill - Primary potency stat
        2. MND/INT - Secondary potency from dSTAT
        3. Enfeebling Effect+ - Direct potency bonus
        4. Magic Accuracy - Still need to land
    
    Args:
        name: Profile name
        job: Job requirement
        potency_focus: If True, weight potency over accuracy
        include_weapons: If True, allow weapon selection
    
    Returns:
        OptimizationProfile configured for enfeebling magic
    """
    if potency_focus:
        weights = {
            'enfeebling_magic_skill': 12.0,
            'MND': 8.0,
            'INT': 6.0,
            'enfeebling_effect': 8.0,
            'magic_accuracy': 4.0,
        }
    else:
        weights = {
            'enfeebling_magic_skill': 10.0,
            'magic_accuracy': 10.0,
            'MND': 6.0,
            'INT': 4.0,
            'enfeebling_effect': 3.0,
        }
    
    return OptimizationProfile(
        name=name,
        weights=weights,
        exclude_slots=set() if include_weapons else {Slot.MAIN, Slot.SUB},
        job=job,
    )


def create_enhancing_profile(name: str = 'Enhancing Magic',
                             job: Optional[Job] = None,
                             duration_focus: bool = False,
                             include_weapons: bool = False) -> OptimizationProfile:
    """
    Create an enhancing magic optimization profile.
    
    Enhancing skill is the PRIMARY stat for potency of:
    - Stoneskin (absorb amount)
    - Phalanx (damage reduction)
    - Enspells (damage per hit)
    - Gain/Boost spells (stat bonus)
    
    Stat priorities:
        1. Enhancing Magic Skill - Primary potency stat
        2. MND - Secondary stat for some spells
        3. Enhancing Duration - Longer buffs
    
    Args:
        name: Profile name
        job: Job requirement
        duration_focus: If True, prioritize duration over potency
        include_weapons: If True, allow weapon selection
    
    Returns:
        OptimizationProfile configured for enhancing magic
    """
    if duration_focus:
        weights = {
            'enhancing_duration': 12.0,
            'enhancing_magic_skill': 8.0,
            'MND': 4.0,
        }
    else:
        weights = {
            'enhancing_magic_skill': 12.0,
            'MND': 6.0,
            'enhancing_duration': 4.0,
        }
    
    return OptimizationProfile(
        name=name,
        weights=weights,
        exclude_slots=set() if include_weapons else {Slot.MAIN, Slot.SUB},
        job=job,
    )


def create_healing_profile(name: str = 'Healing Magic',
                           job: Optional[Job] = None,
                           include_weapons: bool = False) -> OptimizationProfile:
    """
    Create a healing magic (Cure) optimization profile.
    
    Cure potency from gear caps at 50% (5000 basis points).
    MND affects base cure amount.
    VIT affects cure amount received (Cure Potency II).
    
    Stat priorities:
        1. Cure Potency - Direct multiplier (caps at 50%)
        2. MND - Base cure scaling
        3. Healing Magic Skill - Affects enmity reduction, minor potency
        4. VIT - Cure Potency II (received)
    
    Args:
        name: Profile name
        job: Job requirement
        include_weapons: If True, allow weapon selection
    
    Returns:
        OptimizationProfile configured for healing magic
    """
    return OptimizationProfile(
        name=name,
        weights={
            'cure_potency': 12.0,
            'MND': 8.0,
            'healing_magic_skill': 4.0,
            'VIT': 3.0,
            'cure_potency_ii': 2.0,
        },
        hard_caps={
            'cure_potency': 5000,  # 50% cap
        },
        exclude_slots=set() if include_weapons else {Slot.MAIN, Slot.SUB},
        job=job,
    )


def create_dark_magic_profile(name: str = 'Dark Magic',
                              job: Optional[Job] = None,
                              include_weapons: bool = False) -> OptimizationProfile:
    """
    Create a dark magic (Drain/Aspir) optimization profile.
    
    IMPORTANT: Drain/Aspir potency scales with Dark Magic SKILL, not MAB!
    MAB is nearly useless for Drain/Aspir. INT affects accuracy, not potency.
    
    Formula: Drain potency = floor((Dark Magic Skill - 300) × M) + base
    
    Stat priorities:
        1. Dark Magic Skill - PRIMARY potency stat
        2. Magic Accuracy - Landing the spell
        3. INT - dINT bonus to magic accuracy
    
    Note: For offensive dark magic like Bio DOT or Absorb spells,
    the priorities may differ slightly.
    
    Args:
        name: Profile name
        job: Job requirement
        include_weapons: If True, allow weapon selection
    
    Returns:
        OptimizationProfile configured for dark magic
    """
    return OptimizationProfile(
        name=name,
        weights={
            'dark_magic_skill': 12.0,
            'magic_accuracy': 8.0,
            'INT': 4.0,
        },
        exclude_slots=set() if include_weapons else {Slot.MAIN, Slot.SUB},
        job=job,
    )


def create_divine_magic_profile(name: str = 'Divine Magic',
                                job: Optional[Job] = None,
                                divine_emblem: bool = False,
                                include_weapons: bool = False) -> OptimizationProfile:
    """
    Create a divine magic (Banish/Holy) optimization profile.
    
    Divine magic uses dMND instead of dINT for damage scaling.
    Divine Emblem JA multiplies damage by (1 + Divine Skill / 100).
    
    Stat priorities (normal):
        1. Magic Attack Bonus - Primary multiplier
        2. MND - dMND damage scaling
        3. Divine Magic Skill - Accuracy
        4. Magic Accuracy - Landing unresisted
    
    Stat priorities (Divine Emblem):
        1. Divine Magic Skill - HUGE multiplier with Divine Emblem
        2. Magic Attack Bonus - Stacks with DE multiplier
        3. MND - dMND scaling
    
    Args:
        name: Profile name
        job: Job requirement
        divine_emblem: If True, optimize for Divine Emblem usage
        include_weapons: If True, allow weapon selection
    
    Returns:
        OptimizationProfile configured for divine magic
    """
    if divine_emblem:
        # Divine Emblem: damage × (1 + Divine Skill / 100)
        # At 500 skill = 6x damage multiplier!
        weights = {
            'divine_magic_skill': 15.0,
            'magic_attack': 10.0,
            'MND': 6.0,
            'magic_damage': 5.0,
            'magic_accuracy': 2.0,
        }
    else:
        weights = {
            'magic_attack': 10.0,
            'MND': 8.0,
            'divine_magic_skill': 5.0,
            'magic_damage': 6.0,
            'magic_accuracy': 4.0,
        }
    
    return OptimizationProfile(
        name=name,
        weights=weights,
        exclude_slots=set() if include_weapons else {Slot.MAIN, Slot.SUB},
        job=job,
    )


def create_enspell_profile(name: str = 'Enspell Melee',
                           job: Optional[Job] = None,
                           include_weapons: bool = False) -> OptimizationProfile:
    """
    Create an enspell (RDM) melee optimization profile.
    
    Enspell damage scales with Enhancing Magic Skill.
    "Sword enhancement spell damage +n" from gear adds flat damage.
    Multi-attack increases enspell procs (each hit can proc enspell).
    
    Formula:
        If skill <= 200: floor(6×skill/100) + 3
        If skill > 200: floor(5×skill/100) + 5
        Cap: 21 (Tier I) or 42 (Tier II with buildup)
    
    Stat priorities:
        1. Enhancing Magic Skill - Base enspell damage
        2. Sword Enhancement Damage+ - Flat bonus to enspell
        3. Double/Triple Attack - More procs per round
        4. Accuracy - Need to hit to proc
        5. Store TP - Build TP from enspell hits
    
    Args:
        name: Profile name
        job: Job requirement
        include_weapons: If True, allow weapon selection
    
    Returns:
        OptimizationProfile configured for enspell melee
    """
    return OptimizationProfile(
        name=name,
        weights={
            'enhancing_magic_skill': 10.0,
            'sword_enhancement_flat': 8.0,    # "Sword enhancement spell damage +N"
            'sword_enhancement_percent': 6.0,  # "Sword enhancement spell dmg. +N%"
            'double_attack': 8.0,
            'triple_attack': 12.0,
            'accuracy': 6.0,
            'store_tp': 5.0,
            'INT': 3.0,  # Affects enspell magic accuracy
        },
        exclude_slots=set() if include_weapons else {Slot.MAIN, Slot.SUB},
        job=job,
    )


def create_fast_cast_profile(name: str = 'Fast Cast',
                             job: Optional[Job] = None,
                             include_weapons: bool = False) -> OptimizationProfile:
    """
    Create a fast cast (precast) optimization profile.
    
    Fast Cast reduces cast time. Gear cap is 80% (8000 basis points).
    Job traits provide additional FC that is NOT subject to gear cap.
    
    For precast sets, the ONLY goal is maximizing fast cast.
    Other stats are irrelevant since you swap to midcast gear.
    
    Stat priorities:
        1. Fast Cast - Only stat that matters
    
    Args:
        name: Profile name
        job: Job requirement
        include_weapons: If True, allow weapon selection
    
    Returns:
        OptimizationProfile configured for fast cast
    """
    return OptimizationProfile(
        name=name,
        weights={
            'fast_cast': 15.0,
        },
        hard_caps={
            'fast_cast': 8000,  # 80% gear cap
        },
        exclude_slots=set() if include_weapons else {Slot.MAIN, Slot.SUB},
        job=job,
    )


# =============================================================================
# PLAYER BASE STATS
# =============================================================================

# Base stats for a Level 99 character with NO master levels or job point bonuses
# These represent the absolute minimum for a freshly-leveled character
# Reference: https://www.bg-wiki.com/ffxi/Category:Jobs (job-specific stat pages)
FRESH_99_BASE_STATS = {
    # Melee jobs (higher STR/DEX)
    'WAR': Stats(STR=75, DEX=73, VIT=73, AGI=68, INT=65, MND=60, CHR=60, HP=1800, MP=0, accuracy=0, attack=0),
    'MNK': Stats(STR=70, DEX=73, VIT=75, AGI=70, INT=60, MND=65, CHR=63, HP=1850, MP=0, accuracy=0, attack=0),
    'THF': Stats(STR=68, DEX=78, VIT=65, AGI=78, INT=63, MND=60, CHR=65, HP=1600, MP=0, accuracy=0, attack=0),
    'PLD': Stats(STR=73, DEX=70, VIT=78, AGI=63, INT=63, MND=73, CHR=70, HP=1900, MP=200, accuracy=0, attack=0),
    'DRK': Stats(STR=78, DEX=70, VIT=70, AGI=65, INT=70, MND=60, CHR=58, HP=1750, MP=180, accuracy=0, attack=0),
    'SAM': Stats(STR=75, DEX=73, VIT=68, AGI=68, INT=60, MND=60, CHR=65, HP=1750, MP=0, accuracy=0, attack=0),
    'NIN': Stats(STR=68, DEX=75, VIT=63, AGI=75, INT=68, MND=60, CHR=63, HP=1600, MP=0, accuracy=0, attack=0),
    'DRG': Stats(STR=75, DEX=68, VIT=70, AGI=65, INT=60, MND=63, CHR=60, HP=1800, MP=0, accuracy=0, attack=0),
    'DNC': Stats(STR=65, DEX=75, VIT=63, AGI=75, INT=63, MND=63, CHR=73, HP=1550, MP=0, accuracy=0, attack=0),
    'RUN': Stats(STR=70, DEX=68, VIT=73, AGI=65, INT=68, MND=70, CHR=65, HP=1800, MP=150, accuracy=0, attack=0),
    
    # Hybrid jobs
    'RDM': Stats(STR=63, DEX=68, VIT=63, AGI=65, INT=73, MND=73, CHR=68, HP=1400, MP=300, accuracy=0, attack=0),
    'BLU': Stats(STR=68, DEX=68, VIT=68, AGI=65, INT=68, MND=65, CHR=65, HP=1600, MP=250, accuracy=0, attack=0),
    'BST': Stats(STR=70, DEX=70, VIT=70, AGI=68, INT=60, MND=65, CHR=68, HP=1700, MP=0, accuracy=0, attack=0),
    'BRD': Stats(STR=60, DEX=68, VIT=60, AGI=68, INT=65, MND=65, CHR=78, HP=1350, MP=180, accuracy=0, attack=0),
    'COR': Stats(STR=63, DEX=73, VIT=63, AGI=73, INT=63, MND=63, CHR=68, HP=1450, MP=0, accuracy=0, attack=0),
    'RNG': Stats(STR=68, DEX=75, VIT=63, AGI=78, INT=60, MND=60, CHR=63, HP=1500, MP=0, accuracy=0, attack=0),
    'PUP': Stats(STR=68, DEX=73, VIT=70, AGI=70, INT=65, MND=63, CHR=68, HP=1650, MP=100, accuracy=0, attack=0),
    
    # Mage jobs (higher INT/MND)
    'WHM': Stats(STR=58, DEX=60, VIT=68, AGI=58, INT=68, MND=78, CHR=70, HP=1350, MP=400, accuracy=0, attack=0),
    'BLM': Stats(STR=55, DEX=63, VIT=60, AGI=63, INT=78, MND=68, CHR=65, HP=1200, MP=450, accuracy=0, attack=0),
    'SMN': Stats(STR=55, DEX=60, VIT=60, AGI=60, INT=70, MND=78, CHR=73, HP=1250, MP=420, accuracy=0, attack=0),
    'SCH': Stats(STR=58, DEX=63, VIT=63, AGI=63, INT=73, MND=73, CHR=65, HP=1300, MP=380, accuracy=0, attack=0),
    'GEO': Stats(STR=58, DEX=63, VIT=63, AGI=63, INT=73, MND=73, CHR=70, HP=1300, MP=380, accuracy=0, attack=0),
}


# Master Level 25 bonus stats (adds to base stats)
# Master Levels provide:
# - +15 to all primary stats at ML25
# - +250 HP
# - +50 MP (for jobs with MP)
# - Job Point bonuses (assumed capped):
#   - +20 accuracy, +20 attack, +20 ranged accuracy, +20 ranged attack
#   - +10 to primary stats from job gifts
# Reference: https://www.bg-wiki.com/ffxi/Master_Level
MASTER_LEVEL_25_BONUS = Stats(
    STR=25,    # 15 from ML + ~10 from job gifts
    DEX=25,
    VIT=25,
    AGI=25,
    INT=25,
    MND=25,
    CHR=25,
    HP=250,
    MP=50,
    accuracy=20,   # Job point bonus
    attack=20,     # Job point bonus
)


def get_player_base_stats(job: Job, preset: str = 'master_25') -> Stats:
    """
    Get base player stats for a job.
    
    Args:
        job: The job to get stats for
        preset: Either 'fresh_99' or 'master_25'
        
    Returns:
        Stats object with base player stats
    """
    job_name = job.name if isinstance(job, Job) else str(job)
    
    base = FRESH_99_BASE_STATS.get(job_name, Stats())
    
    if preset == 'master_25':
        return base + MASTER_LEVEL_25_BONUS
    else:
        return base.copy()


# =============================================================================
# PRIORITY-BASED PROFILE FACTORIES
# =============================================================================
# These create profiles with tiered weights based on optimization priority.
# The primary stat group gets ~100x weight, secondary gets ~10x, tertiary gets ~1x.
# This ensures  search maximizes primary before considering secondary.


####This is old and left over from the original implementation. It might be worthwhile to come back later and check out
####we could use these in the future.

# def create_priority_profile(
#     name: str,
#     priority: str,
#     job: Optional[Job] = None,
#     dw_trait: int = 0,
#     magic_haste: int = 3000,
#     ja_haste: int = 0,
#     weapon_delay: int = 0,
#     is_dual_wield: bool = False,
#     off_hand_delay: int = 0,
#     target_evasion: int = 0,
#     base_accuracy: int = 1100,
# ) -> OptimizationProfile:
#     """
#     Create an optimization profile based on priority preset.
    
#     Priority presets and their weight distributions:
    
#     PURE_TP: Maximum TP rate, ignore other stats
#         - TP stats: 100x weight
        
#     PURE_ACC: Maximum accuracy
#         - Accuracy stats: 100x weight
        
#     PURE_DT: Maximum damage reduction
#         - DT stats: 100x weight
        
#     ACC_TP: Accuracy first, then TP
#         - Accuracy: 100x weight (maximize first)
#         - TP stats: 10x weight (secondary)
        
#     TP_ACC: TP first, then Accuracy (default)
#         - TP stats: 100x weight
#         - Accuracy: 10x weight
        
#     ACC_DT: Accuracy first, then DT
#         - Accuracy: 100x weight
#         - DT stats: 10x weight
        
#     DT_TP: DT first, then TP (engaged.DT style)
#         - DT stats: 100x weight
#         - TP stats: 10x weight
        
#     TP_DT: TP first, then DT
#         - TP stats: 100x weight
#         - DT stats: 10x weight
    
#     Args:
#         name: Profile name
#         priority: Priority preset string (e.g., 'acc_tp', 'pure_tp')
#         job: Job requirement
#         dw_trait: Job's DW trait in basis points
#         magic_haste: Magic haste in basis points
#         ja_haste: JA haste in basis points
#         weapon_delay: Weapon delay for simulation
#         is_dual_wield: Whether dual wielding
#         off_hand_delay: Off-hand delay
#         target_evasion: Target's evasion stat (if >0, calculates hit rate from accuracy)
#         base_accuracy: Player's base accuracy from skills/DEX/buffs (before gear)
        
#     Returns:
#         OptimizationProfile configured for the specified priority
#     """
#     ctx = BuffContext(magic_haste=magic_haste, ja_haste=ja_haste, dw_trait=dw_trait)
#     dw_needed = ctx.get_dw_needed()
    
#     # Define stat group weights
#     # Tier 1 (primary): 100x - will be maximized first
#     # Tier 2 (secondary): 10x - considered after primary is good
#     # Tier 3 (tertiary): 1x - nice to have / tiebreaker
    
#     # TP stat weights (for Tier 1, scale down for lower tiers)
#     TP_WEIGHTS_T1 = {
#         'store_tp': 100.0,
#         'double_attack': 80.0,
#         'triple_attack': 120.0,
#         'quad_attack': 150.0,
#         'gear_haste': 70.0,
#         'dual_wield': 60.0 if is_dual_wield else 0.0,
#         'attack': 10.0,
#     }
    
#     # Accuracy stat weights
#     ACC_WEIGHTS_T1 = {
#         'accuracy': 100.0,
#         'DEX': 5.0,  # Minor accuracy contribution
#     }
    
#     # DT stat weights (negative because lower DT = better)
#     DT_WEIGHTS_T1 = {
#         'damage_taken': -100.0,
#         'physical_dt': -100.0,
#         'magical_dt': -80.0,
#         'HP': 20.0,
#         'VIT': 8.0,
#         'defense': 5.0,
#     }
    
#     # Scale weights by tier
#     def scale_weights(weights: dict, tier: int) -> dict:
#         """Scale weights by tier (1=100%, 2=10%, 3=1%)"""
#         scale = {1: 1.0, 2: 0.1, 3: 0.01}[tier]
#         return {k: v * scale for k, v in weights.items()}
    
#     # Build weights based on priority
#     weights = {}
    
#     priority_lower = priority.lower()
    
#     if priority_lower == 'pure_tp':
#         weights = TP_WEIGHTS_T1.copy()
        
#     elif priority_lower == 'pure_acc':
#         weights = ACC_WEIGHTS_T1.copy()
        
#     elif priority_lower == 'pure_dt':
#         weights = DT_WEIGHTS_T1.copy()
        
#     elif priority_lower == 'acc_tp':
#         # Accuracy first, then TP
#         weights.update(scale_weights(ACC_WEIGHTS_T1, 1))  # Primary
#         weights.update(scale_weights(TP_WEIGHTS_T1, 2))   # Secondary
        
#     elif priority_lower == 'tp_acc':
#         # TP first, then Accuracy (default)
#         weights.update(scale_weights(TP_WEIGHTS_T1, 1))   # Primary
#         weights.update(scale_weights(ACC_WEIGHTS_T1, 2))  # Secondary
        
#     elif priority_lower == 'acc_dt':
#         # Accuracy first, then DT
#         weights.update(scale_weights(ACC_WEIGHTS_T1, 1))  # Primary
#         weights.update(scale_weights(DT_WEIGHTS_T1, 2))   # Secondary
        
#     elif priority_lower == 'dt_tp':
#         # DT first, then TP (engaged.DT style)
#         weights.update(scale_weights(DT_WEIGHTS_T1, 1))   # Primary
#         weights.update(scale_weights(TP_WEIGHTS_T1, 2))   # Secondary
        
#     elif priority_lower == 'tp_dt':
#         # TP first, then DT
#         weights.update(scale_weights(TP_WEIGHTS_T1, 1))   # Primary
#         weights.update(scale_weights(DT_WEIGHTS_T1, 2))   # Secondary
        
#     else:
#         # Default to TP_ACC if unknown priority
#         weights.update(scale_weights(TP_WEIGHTS_T1, 1))
#         weights.update(scale_weights(ACC_WEIGHTS_T1, 2))
    
#     return OptimizationProfile(
#         name=name,
#         weights=weights,
#         hard_caps={
#             'gear_haste': 2500,      # 25% gear haste cap
#             'double_attack': 10000,
#             'damage_taken': -5000,   # -50% DT cap
#             'physical_dt': -5000,
#             'magical_dt': -5000,
#         },
#         soft_caps={
#             'dual_wield': max(dw_needed, 1000) if is_dual_wield else 0,
#         },
#         buff_context=ctx,
#         exclude_slots={Slot.MAIN, Slot.SUB},
#         job=job,
#         use_simulation=weapon_delay > 0,
#         simulation_mode='tp_rate' if weapon_delay > 0 else 'weighted',
#         weapon_delay=weapon_delay,
#         is_dual_wield=is_dual_wield,
#         off_hand_delay=off_hand_delay,
#         target_evasion=target_evasion,
#         base_accuracy=base_accuracy,
#     )


# def create_dt_priority_profile(
        
#     name: str,
#     dt_type: str,
#     job: Optional[Job] = None,
#     include_weapons: bool = False,
#     include_hp: bool = True,
#     include_defense: bool = True,
# ) -> OptimizationProfile:
#     """
#     Create a DT set optimization profile based on DT type priority.
    
#     DT Types:
#     - 'dt': General Damage Taken - reduces ALL damage
#     - 'pdt': Physical Damage Taken - only physical damage
#     - 'mdt': Magical Damage Taken - only magical damage
    
#     Each type caps at -50% separately. They stack multiplicatively.
    
#     Args:
#         name: Profile name
#         dt_type: DT type to prioritize ('dt', 'pdt', 'mdt')
#         job: Job requirement
#         include_weapons: Include weapon slots in optimization
#         include_hp: Include HP in optimization
#         include_defense: Include Defense in optimization
        
#     Returns:
#         OptimizationProfile configured for the specified DT type
#     """
#     dt_type_lower = dt_type.lower()
    
#     # Base weights for DT stats
#     # Negative weights because lower (more negative) = better
#     weights = {}
    
#     if dt_type_lower == 'dt':
#         # General DT - affects both physical and magical
#         weights = {
#             'damage_taken': -12.0,    # Primary - most versatile
#             'physical_dt': -8.0,      # Secondary
#             'magical_dt': -8.0,       # Secondary
#         }
#     elif dt_type_lower == 'pdt':
#         # Physical DT priority
#         weights = {
#             'physical_dt': -12.0,     # Primary
#             'damage_taken': -10.0,    # Also reduces physical
#             'magical_dt': -4.0,       # Low priority
#         }
#     elif dt_type_lower == 'mdt':
#         # Magical DT priority
#         weights = {
#             'magical_dt': -12.0,      # Primary
#             'damage_taken': -10.0,    # Also reduces magical
#             'physical_dt': -4.0,      # Low priority
#         }
#     else:
#         # Default to general DT
#         weights = {
#             'damage_taken': -12.0,
#             'physical_dt': -8.0,
#             'magical_dt': -8.0,
#         }
    
#     # Add secondary stats
#     if include_hp:
#         weights['HP'] = 2.0
#         weights['VIT'] = 0.8  # Reduces enemy fSTR
    
#     if include_defense:
#         weights['defense'] = 0.5
#         weights['evasion'] = 0.4
#         weights['magic_evasion'] = 0.3
#         weights['AGI'] = 0.3  # Reduces enemy crit rate
    
#     return OptimizationProfile(
#         name=name,
#         weights=weights,
#         hard_caps={
#             'damage_taken': -5000,   # -50% cap
#             'physical_dt': -5000,
#             'magical_dt': -5000,
#         },
#         exclude_slots=set() if include_weapons else {Slot.MAIN, Slot.SUB},
#         job=job,
#     )


