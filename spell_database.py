"""
Spell Database for FFXI Magic Simulation

Contains spell data for all common offensive magic including:
- Base damage values (V)
- INT multipliers (M) at each dINT threshold
- Element, skill type, and other properties

Reference: https://www.bg-wiki.com/ffxi/Magic_Damage
"""

from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional, List
from enum import Enum, auto

try:
    from .magic_formulas import Element, MagicType
except ImportError:
    from magic_formulas import Element, MagicType


@dataclass
class SpellData:
    """
    Complete spell data for damage calculation.
    
    m_values is a dict mapping dINT threshold to (V_at_threshold, M_multiplier).
    For example, Stone II has:
        {0: (100, 3.0), 50: (250, 2.0), 100: (350, 1.0), 200: (450, 0.0)}
    """
    name: str
    element: Element
    magic_type: MagicType
    skill_type: str  # 'elemental', 'dark', 'divine', 'enfeebling', etc.
    
    # Base damage at dINT = 0
    base_v: int
    
    # Dict of dINT threshold -> (V at that threshold, M multiplier)
    m_values: Dict[int, Tuple[int, float]]
    
    # Tier for categorization
    tier: int = 1
    
    # MP cost
    mp_cost: int = 0
    
    # Cast time in seconds
    cast_time: float = 0.0
    
    # Recast time in seconds
    recast_time: float = 0.0
    
    # Is AoE spell
    is_aoe: bool = False
    
    # Maximum dINT cap (beyond which INT gives no benefit)
    dint_cap: int = 100
    
    # Special properties
    properties: Dict[str, any] = field(default_factory=dict)


# =============================================================================
# Elemental Magic - Single Target Nukes
# =============================================================================

ELEMENTAL_TIER_I = {
    'Stone': SpellData(
        name='Stone', element=Element.EARTH, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=10, tier=1, mp_cost=4,
        m_values={0: (10, 2.0), 50: (110, 1.0), 100: (160, 0.0)},
        dint_cap=100,
    ),
    'Water': SpellData(
        name='Water', element=Element.WATER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=25, tier=1, mp_cost=5,
        m_values={0: (25, 1.8), 50: (115, 1.0), 100: (165, 0.0)},
        dint_cap=100,
    ),
    'Aero': SpellData(
        name='Aero', element=Element.WIND, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=40, tier=1, mp_cost=6,
        m_values={0: (40, 1.6), 50: (120, 1.0), 100: (170, 0.0)},
        dint_cap=100,
    ),
    'Fire': SpellData(
        name='Fire', element=Element.FIRE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=55, tier=1, mp_cost=7,
        m_values={0: (55, 1.4), 50: (125, 1.0), 100: (175, 0.0)},
        dint_cap=100,
    ),
    'Blizzard': SpellData(
        name='Blizzard', element=Element.ICE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=70, tier=1, mp_cost=8,
        m_values={0: (70, 1.2), 50: (130, 1.0), 100: (180, 0.0)},
        dint_cap=100,
    ),
    'Thunder': SpellData(
        name='Thunder', element=Element.THUNDER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=85, tier=1, mp_cost=9,
        m_values={0: (85, 1.0), 50: (135, 1.0), 100: (185, 0.0)},
        dint_cap=100,
    ),
}

ELEMENTAL_TIER_II = {
    'Stone II': SpellData(
        name='Stone II', element=Element.EARTH, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=100, tier=2, mp_cost=16,
        m_values={0: (100, 3.0), 50: (250, 2.0), 100: (350, 1.0), 200: (450, 0.0)},
        dint_cap=200,
    ),
    'Water II': SpellData(
        name='Water II', element=Element.WATER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=120, tier=2, mp_cost=19,
        m_values={0: (120, 2.8), 50: (260, 1.9), 100: (355, 1.0), 200: (455, 0.0)},
        dint_cap=200,
    ),
    'Aero II': SpellData(
        name='Aero II', element=Element.WIND, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=140, tier=2, mp_cost=22,
        m_values={0: (140, 2.6), 50: (270, 1.8), 100: (360, 1.0), 200: (460, 0.0)},
        dint_cap=200,
    ),
    'Fire II': SpellData(
        name='Fire II', element=Element.FIRE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=160, tier=2, mp_cost=26,
        m_values={0: (160, 2.4), 50: (280, 1.7), 100: (365, 1.0), 200: (465, 0.0)},
        dint_cap=200,
    ),
    'Blizzard II': SpellData(
        name='Blizzard II', element=Element.ICE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=180, tier=2, mp_cost=31,
        m_values={0: (180, 2.2), 50: (290, 1.6), 100: (370, 1.0), 200: (470, 0.0)},
        dint_cap=200,
    ),
    'Thunder II': SpellData(
        name='Thunder II', element=Element.THUNDER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=200, tier=2, mp_cost=37,
        m_values={0: (200, 2.0), 50: (300, 1.5), 100: (375, 1.0), 200: (475, 0.0)},
        dint_cap=200,
    ),
}

ELEMENTAL_TIER_III = {
    'Stone III': SpellData(
        name='Stone III', element=Element.EARTH, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=200, tier=3, mp_cost=40,
        m_values={0: (200, 4.0), 50: (400, 3.0), 100: (550, 2.0), 200: (750, 1.0), 300: (850, 0.0)},
        dint_cap=300,
    ),
    'Water III': SpellData(
        name='Water III', element=Element.WATER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=230, tier=3, mp_cost=46,
        m_values={0: (230, 3.7), 50: (415, 2.9), 100: (560, 1.95), 200: (755, 1.0), 300: (855, 0.0)},
        dint_cap=300,
    ),
    'Aero III': SpellData(
        name='Aero III', element=Element.WIND, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=260, tier=3, mp_cost=52,
        m_values={0: (260, 3.4), 50: (430, 2.8), 100: (570, 1.9), 200: (760, 1.0), 300: (860, 0.0)},
        dint_cap=300,
    ),
    'Fire III': SpellData(
        name='Fire III', element=Element.FIRE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=290, tier=3, mp_cost=63,
        m_values={0: (290, 3.1), 50: (445, 2.7), 100: (580, 1.85), 200: (765, 1.0), 300: (865, 0.0)},
        dint_cap=300,
    ),
    'Blizzard III': SpellData(
        name='Blizzard III', element=Element.ICE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=320, tier=3, mp_cost=75,
        m_values={0: (320, 2.8), 50: (460, 2.6), 100: (590, 1.8), 200: (770, 1.0), 300: (870, 0.0)},
        dint_cap=300,
    ),
    'Thunder III': SpellData(
        name='Thunder III', element=Element.THUNDER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=350, tier=3, mp_cost=91,
        m_values={0: (350, 2.5), 50: (475, 2.5), 100: (600, 1.75), 200: (775, 1.0), 300: (875, 0.0)},
        dint_cap=300,
    ),
}

ELEMENTAL_TIER_IV = {
    'Stone IV': SpellData(
        name='Stone IV', element=Element.EARTH, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=400, tier=4, mp_cost=88,
        m_values={0: (400, 5.0), 50: (650, 4.0), 100: (850, 3.0), 200: (1150, 2.0), 300: (1350, 1.0), 400: (1450, 0.0)},
        dint_cap=400,
    ),
    'Water IV': SpellData(
        name='Water IV', element=Element.WATER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=440, tier=4, mp_cost=99,
        m_values={0: (440, 4.7), 50: (675, 3.9), 100: (870, 2.95), 200: (1165, 1.99), 300: (1364, 1.0), 400: (1464, 0.0)},
        dint_cap=400,
    ),
    'Aero IV': SpellData(
        name='Aero IV', element=Element.WIND, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=480, tier=4, mp_cost=113,
        m_values={0: (480, 4.4), 50: (700, 3.8), 100: (890, 2.9), 200: (1180, 1.98), 300: (1378, 1.0), 400: (1478, 0.0)},
        dint_cap=400,
    ),
    'Fire IV': SpellData(
        name='Fire IV', element=Element.FIRE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=520, tier=4, mp_cost=135,
        m_values={0: (520, 4.2), 50: (730, 3.7), 100: (915, 2.85), 200: (1195, 1.97), 300: (1397, 1.0), 400: (1497, 0.0)},
        dint_cap=400,
    ),
    'Blizzard IV': SpellData(
        name='Blizzard IV', element=Element.ICE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=560, tier=4, mp_cost=162,
        m_values={0: (560, 3.9), 50: (755, 3.6), 100: (935, 2.8), 200: (1210, 1.96), 300: (1411, 1.0), 400: (1511, 0.0)},
        dint_cap=400,
    ),
    'Thunder IV': SpellData(
        name='Thunder IV', element=Element.THUNDER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=600, tier=4, mp_cost=194,
        m_values={0: (600, 3.6), 50: (780, 3.5), 100: (955, 2.75), 200: (1225, 1.95), 300: (1425, 1.0), 400: (1525, 0.0)},
        dint_cap=400,
    ),
}

ELEMENTAL_TIER_V = {
    'Stone V': SpellData(
        name='Stone V', element=Element.EARTH, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=650, tier=5, mp_cost=135,
        m_values={0: (650, 6.0), 50: (950, 5.0), 100: (1200, 4.0), 200: (1600, 3.0), 300: (1900, 2.0), 400: (2100, 1.0), 500: (2200, 0.0)},
        dint_cap=500,
    ),
    'Water V': SpellData(
        name='Water V', element=Element.WATER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=700, tier=5, mp_cost=153,
        m_values={0: (700, 5.6), 50: (980, 4.74), 100: (1217, 3.95), 200: (1612, 2.99), 300: (1911, 1.99), 400: (2110, 1.0), 500: (2210, 0.0)},
        dint_cap=500,
    ),
    'Aero V': SpellData(
        name='Aero V', element=Element.WIND, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=750, tier=5, mp_cost=173,
        m_values={0: (750, 5.2), 50: (1010, 4.5), 100: (1235, 3.9), 200: (1625, 2.98), 300: (1923, 1.98), 400: (2121, 1.0), 500: (2221, 0.0)},
        dint_cap=500,
    ),
    'Fire V': SpellData(
        name='Fire V', element=Element.FIRE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=800, tier=5, mp_cost=198,
        m_values={0: (800, 4.8), 50: (1040, 4.24), 100: (1252, 3.85), 200: (1637, 2.97), 300: (1934, 1.97), 400: (2131, 1.0), 500: (2231, 0.0)},
        dint_cap=500,
    ),
    'Blizzard V': SpellData(
        name='Blizzard V', element=Element.ICE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=850, tier=5, mp_cost=228,
        m_values={0: (850, 4.4), 50: (1070, 4.0), 100: (1270, 3.8), 200: (1650, 2.96), 300: (1946, 1.96), 400: (2142, 1.0), 500: (2242, 0.0)},
        dint_cap=500,
    ),
    'Thunder V': SpellData(
        name='Thunder V', element=Element.THUNDER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=900, tier=5, mp_cost=263,
        m_values={0: (900, 4.0), 50: (1100, 3.74), 100: (1287, 3.75), 200: (1662, 2.95), 300: (1957, 1.95), 400: (2152, 1.0), 500: (2252, 0.0)},
        dint_cap=500,
    ),
}

ELEMENTAL_TIER_VI = {
    'Stone VI': SpellData(
        name='Stone VI', element=Element.EARTH, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=950, tier=6, mp_cost=228,
        m_values={0: (950, 7.0), 50: (1300, 6.0), 100: (1600, 5.0), 200: (2100, 4.0), 300: (2500, 3.0), 400: (2800, 2.0), 500: (3000, 1.0), 600: (3100, 0.0)},
        dint_cap=600,
    ),
    'Water VI': SpellData(
        name='Water VI', element=Element.WATER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=1010, tier=6, mp_cost=256,
        m_values={0: (1010, 6.5), 50: (1335, 5.9), 100: (1630, 4.9), 200: (2120, 3.9), 300: (2510, 2.95), 400: (2805, 1.99), 500: (3004, 1.0), 600: (3104, 0.0)},
        dint_cap=600,
    ),
    'Aero VI': SpellData(
        name='Aero VI', element=Element.WIND, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=1070, tier=6, mp_cost=289,
        m_values={0: (1070, 6.0), 50: (1370, 5.8), 100: (1660, 4.8), 200: (2140, 3.8), 300: (2520, 2.9), 400: (2810, 1.98), 500: (3008, 1.0), 600: (3108, 0.0)},
        dint_cap=600,
    ),
    'Fire VI': SpellData(
        name='Fire VI', element=Element.FIRE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=1130, tier=6, mp_cost=329,
        m_values={0: (1130, 5.5), 50: (1405, 5.7), 100: (1690, 4.7), 200: (2160, 3.7), 300: (2530, 2.85), 400: (2815, 1.97), 500: (3012, 1.0), 600: (3112, 0.0)},
        dint_cap=600,
    ),
    'Blizzard VI': SpellData(
        name='Blizzard VI', element=Element.ICE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=1190, tier=6, mp_cost=377,
        m_values={0: (1190, 5.0), 50: (1440, 5.6), 100: (1720, 4.6), 200: (2180, 3.6), 300: (2540, 2.8), 400: (2820, 1.96), 500: (3016, 1.0), 600: (3116, 0.0)},
        dint_cap=600,
    ),
    'Thunder VI': SpellData(
        name='Thunder VI', element=Element.THUNDER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=1250, tier=6, mp_cost=437,
        m_values={0: (1250, 4.5), 50: (1475, 5.5), 100: (1750, 4.5), 200: (2200, 3.5), 300: (2550, 2.75), 400: (2825, 1.95), 500: (3020, 1.0), 600: (3120, 0.0)},
        dint_cap=600,
    ),
}

# =============================================================================
# Elemental Magic - AoE (-ga spells)
# =============================================================================

ELEMENTAL_GA_TIER_I = {
    'Stonega': SpellData(
        name='Stonega', element=Element.EARTH, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=60, tier=1, mp_cost=12, is_aoe=True,
        m_values={0: (60, 3.0), 50: (210, 2.0), 100: (310, 1.0), 200: (410, 0.0)},
        dint_cap=200,
    ),
    'Waterga': SpellData(
        name='Waterga', element=Element.WATER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=80, tier=1, mp_cost=15, is_aoe=True,
        m_values={0: (80, 2.8), 50: (220, 1.9), 100: (315, 1.0), 200: (415, 0.0)},
        dint_cap=200,
    ),
    'Aeroga': SpellData(
        name='Aeroga', element=Element.WIND, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=100, tier=1, mp_cost=18, is_aoe=True,
        m_values={0: (100, 2.6), 50: (230, 1.8), 100: (320, 1.0), 200: (420, 0.0)},
        dint_cap=200,
    ),
    'Firaga': SpellData(
        name='Firaga', element=Element.FIRE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=120, tier=1, mp_cost=21, is_aoe=True,
        m_values={0: (120, 2.4), 50: (240, 1.7), 100: (325, 1.0), 200: (425, 0.0)},
        dint_cap=200,
    ),
    'Blizzaga': SpellData(
        name='Blizzaga', element=Element.ICE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=160, tier=1, mp_cost=28, is_aoe=True,
        m_values={0: (160, 2.2), 50: (270, 1.6), 100: (350, 1.0), 200: (450, 0.0)},
        dint_cap=200,
    ),
    'Thundaga': SpellData(
        name='Thundaga', element=Element.THUNDER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=200, tier=1, mp_cost=37, is_aoe=True,
        m_values={0: (200, 2.0), 50: (300, 1.5), 100: (375, 1.0), 200: (475, 0.0)},
        dint_cap=200,
    ),
}

# -ja spells (Tier IV AoE)
ELEMENTAL_JA = {
    'Stoneja': SpellData(
        name='Stoneja', element=Element.EARTH, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=750, tier=4, mp_cost=232, is_aoe=True,
        m_values={0: (750, 6.0), 50: (1050, 5.0), 100: (1300, 4.0), 200: (1700, 3.0), 300: (2000, 2.0), 400: (2200, 1.0), 500: (2300, 0.0)},
        dint_cap=500,
    ),
    'Waterja': SpellData(
        name='Waterja', element=Element.WATER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=800, tier=4, mp_cost=259, is_aoe=True,
        m_values={0: (800, 5.6), 50: (1080, 4.75), 100: (1317, 3.95), 200: (1712, 2.98), 300: (2010, 2.0), 400: (2210, 1.0), 500: (2310, 0.0)},
        dint_cap=500,
    ),
    'Aeroja': SpellData(
        name='Aeroja', element=Element.WIND, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=850, tier=4, mp_cost=290, is_aoe=True,
        m_values={0: (850, 5.2), 50: (1110, 4.5), 100: (1335, 3.9), 200: (1725, 2.96), 300: (2021, 2.0), 400: (2221, 1.0), 500: (2321, 0.0)},
        dint_cap=500,
    ),
    'Firaja': SpellData(
        name='Firaja', element=Element.FIRE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=900, tier=4, mp_cost=326, is_aoe=True,
        m_values={0: (900, 4.8), 50: (1140, 4.25), 100: (1352, 3.85), 200: (1737, 2.94), 300: (2031, 2.0), 400: (2231, 1.0), 500: (2331, 0.0)},
        dint_cap=500,
    ),
    'Blizzaja': SpellData(
        name='Blizzaja', element=Element.ICE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=950, tier=4, mp_cost=368, is_aoe=True,
        m_values={0: (950, 4.4), 50: (1170, 4.0), 100: (1370, 3.8), 200: (1750, 2.92), 300: (2042, 2.0), 400: (2242, 1.0), 500: (2342, 0.0)},
        dint_cap=500,
    ),
    'Thundaja': SpellData(
        name='Thundaja', element=Element.THUNDER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=1000, tier=4, mp_cost=418, is_aoe=True,
        m_values={0: (1000, 4.0), 50: (1200, 3.75), 100: (1387, 3.75), 200: (1762, 2.9), 300: (2052, 2.0), 400: (2252, 1.0), 500: (2352, 0.0)},
        dint_cap=500,
    ),
}

# =============================================================================
# Ancient Magic
# =============================================================================

ANCIENT_MAGIC = {
    'Flare': SpellData(
        name='Flare', element=Element.FIRE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=700, tier=5, mp_cost=315,
        m_values={0: (700, 2.0), 50: (800, 2.0), 100: (900, 2.0), 200: (1100, 2.0), 300: (1300, 2.0), 400: (1500, 2.0), 500: (1700, 2.0), 600: (1900, 0.0)},
        dint_cap=600,
    ),
    'Freeze': SpellData(
        name='Freeze', element=Element.ICE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=700, tier=5, mp_cost=315,
        m_values={0: (700, 2.0), 50: (800, 2.0), 100: (900, 2.0), 200: (1100, 2.0), 300: (1300, 2.0), 400: (1500, 2.0), 500: (1700, 2.0), 600: (1900, 0.0)},
        dint_cap=600,
    ),
    'Tornado': SpellData(
        name='Tornado', element=Element.WIND, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=700, tier=5, mp_cost=315,
        m_values={0: (700, 2.0), 50: (800, 2.0), 100: (900, 2.0), 200: (1100, 2.0), 300: (1300, 2.0), 400: (1500, 2.0), 500: (1700, 2.0), 600: (1900, 0.0)},
        dint_cap=600,
    ),
    'Quake': SpellData(
        name='Quake', element=Element.EARTH, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=700, tier=5, mp_cost=315,
        m_values={0: (700, 2.0), 50: (800, 2.0), 100: (900, 2.0), 200: (1100, 2.0), 300: (1300, 2.0), 400: (1500, 2.0), 500: (1700, 2.0), 600: (1900, 0.0)},
        dint_cap=600,
    ),
    'Burst': SpellData(
        name='Burst', element=Element.THUNDER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=700, tier=5, mp_cost=315,
        m_values={0: (700, 2.0), 50: (800, 2.0), 100: (900, 2.0), 200: (1100, 2.0), 300: (1300, 2.0), 400: (1500, 2.0), 500: (1700, 2.0), 600: (1900, 0.0)},
        dint_cap=600,
    ),
    'Flood': SpellData(
        name='Flood', element=Element.WATER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=700, tier=5, mp_cost=315,
        m_values={0: (700, 2.0), 50: (800, 2.0), 100: (900, 2.0), 200: (1100, 2.0), 300: (1300, 2.0), 400: (1500, 2.0), 500: (1700, 2.0), 600: (1900, 0.0)},
        dint_cap=600,
    ),
}

ANCIENT_MAGIC_II = {
    'Flare II': SpellData(
        name='Flare II', element=Element.FIRE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=800, tier=6, mp_cost=280,
        m_values={0: (800, 2.0), 50: (900, 2.0), 100: (1000, 2.0), 200: (1200, 2.0), 300: (1400, 2.0), 400: (1600, 2.0), 500: (1800, 2.0), 600: (2000, 0.0)},
        dint_cap=600,
    ),
    'Freeze II': SpellData(
        name='Freeze II', element=Element.ICE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=800, tier=6, mp_cost=280,
        m_values={0: (800, 2.0), 50: (900, 2.0), 100: (1000, 2.0), 200: (1200, 2.0), 300: (1400, 2.0), 400: (1600, 2.0), 500: (1800, 2.0), 600: (2000, 0.0)},
        dint_cap=600,
    ),
    'Tornado II': SpellData(
        name='Tornado II', element=Element.WIND, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=800, tier=6, mp_cost=280,
        m_values={0: (800, 2.0), 50: (900, 2.0), 100: (1000, 2.0), 200: (1200, 2.0), 300: (1400, 2.0), 400: (1600, 2.0), 500: (1800, 2.0), 600: (2000, 0.0)},
        dint_cap=600,
    ),
    'Quake II': SpellData(
        name='Quake II', element=Element.EARTH, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=800, tier=6, mp_cost=280,
        m_values={0: (800, 2.0), 50: (900, 2.0), 100: (1000, 2.0), 200: (1200, 2.0), 300: (1400, 2.0), 400: (1600, 2.0), 500: (1800, 2.0), 600: (2000, 0.0)},
        dint_cap=600,
    ),
    'Burst II': SpellData(
        name='Burst II', element=Element.THUNDER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=800, tier=6, mp_cost=280,
        m_values={0: (800, 2.0), 50: (900, 2.0), 100: (1000, 2.0), 200: (1200, 2.0), 300: (1400, 2.0), 400: (1600, 2.0), 500: (1800, 2.0), 600: (2000, 0.0)},
        dint_cap=600,
    ),
    'Flood II': SpellData(
        name='Flood II', element=Element.WATER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=800, tier=6, mp_cost=280,
        m_values={0: (800, 2.0), 50: (900, 2.0), 100: (1000, 2.0), 200: (1200, 2.0), 300: (1400, 2.0), 400: (1600, 2.0), 500: (1800, 2.0), 600: (2000, 0.0)},
        dint_cap=600,
    ),
}

# Comet (Dark element tier 6)
COMET = SpellData(
    name='Comet', element=Element.DARK, magic_type=MagicType.ELEMENTAL,
    skill_type='elemental', base_v=1000, tier=6, mp_cost=236,
    m_values={0: (1000, 4.0), 50: (1200, 3.75), 100: (1387, 3.5), 200: (1737, 3.0), 300: (2037, 2.0), 400: (2237, 1.0), 500: (2337, 0.0)},
    dint_cap=500,
)

# =============================================================================
# Complete Spell Database
# =============================================================================

ALL_SPELLS: Dict[str, SpellData] = {}

# =============================================================================
# Divine Magic (Light Element) - Uses dMND instead of dINT
# =============================================================================

BANISH_SPELLS = {
    'Banish': SpellData(
        name='Banish', element=Element.LIGHT, magic_type=MagicType.DIVINE,
        skill_type='divine', base_v=14, tier=1, mp_cost=15, cast_time=0.5,
        # Banish uses dMND, similar tier structure to Stone
        m_values={0: (14, 1.0), 50: (64, 1.0), 100: (114, 0.0)},
        dint_cap=100,
        properties={'attack_down_undead': True},
    ),
    'Banish II': SpellData(
        name='Banish II', element=Element.LIGHT, magic_type=MagicType.DIVINE,
        skill_type='divine', base_v=77, tier=2, mp_cost=57, cast_time=1.5,
        m_values={0: (77, 1.5), 50: (152, 1.25), 100: (214, 1.0), 200: (314, 0.0)},
        dint_cap=200,
        properties={'attack_down_undead': True},
    ),
    'Banish III': SpellData(
        name='Banish III', element=Element.LIGHT, magic_type=MagicType.DIVINE,
        skill_type='divine', base_v=198, tier=3, mp_cost=96, cast_time=3.0,
        # Comparable to Stone III (V=210, M=1.5)
        m_values={0: (198, 1.5), 50: (273, 1.25), 100: (335, 1.0), 200: (435, 0.5), 300: (485, 0.0)},
        dint_cap=300,
        properties={'attack_down_undead': True},
    ),
    'Banishga': SpellData(
        name='Banishga', element=Element.LIGHT, magic_type=MagicType.DIVINE,
        skill_type='divine', base_v=30, tier=1, mp_cost=41, cast_time=2.25,
        is_aoe=True,
        m_values={0: (30, 1.0), 50: (80, 1.0), 100: (130, 0.0)},
        dint_cap=100,
        properties={'attack_down_undead': True},
    ),
    'Banishga II': SpellData(
        name='Banishga II', element=Element.LIGHT, magic_type=MagicType.DIVINE,
        skill_type='divine', base_v=108, tier=2, mp_cost=120, cast_time=3.75,
        is_aoe=True,
        m_values={0: (108, 1.5), 50: (183, 1.25), 100: (245, 1.0), 200: (345, 0.0)},
        dint_cap=200,
        properties={'attack_down_undead': True},
    ),
}

HOLY_SPELLS = {
    'Holy': SpellData(
        name='Holy', element=Element.LIGHT, magic_type=MagicType.DIVINE,
        skill_type='divine', base_v=125, tier=4, mp_cost=100, cast_time=2.0,
        # Holy: ~125 base + 1*dMND, instant nuke
        m_values={0: (125, 1.0), 50: (175, 1.0), 100: (225, 0.75), 200: (300, 0.5), 300: (350, 0.0)},
        dint_cap=300,
        properties={'instant_cast_with_solace': True},
    ),
    'Holy II': SpellData(
        name='Holy II', element=Element.LIGHT, magic_type=MagicType.DIVINE,
        skill_type='divine', base_v=300, tier=5, mp_cost=150, cast_time=3.0,
        # Holy II: Higher base, 2 dMND per damage point
        m_values={0: (300, 2.0), 50: (400, 1.75), 100: (487, 1.5), 200: (637, 1.0), 300: (737, 0.5), 400: (787, 0.0)},
        dint_cap=400,
        properties={'divine_emblem_bonus': True, 'amnesia_on_undead': True},
    ),
}


# =============================================================================
# Dark Magic - Bio (DOT + Attack Down), Drain, Aspir
# =============================================================================

BIO_SPELLS = {
    'Bio': SpellData(
        name='Bio', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=10, tier=1, mp_cost=15, cast_time=2.0,
        # Bio DOT is skill-based, not INT-based
        # DOT = floor((skill + 59) / 27) for Bio III formula reference
        m_values={0: (10, 0.5), 50: (35, 0.25), 100: (47, 0.0)},
        dint_cap=100,
        properties={
            'dot': True,
            'dot_formula': 'floor((skill + 59) / 54)',  # Bio I approx
            'attack_down': 512,  # 5% attack down (512/1024)
        },
    ),
    'Bio II': SpellData(
        name='Bio II', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=30, tier=2, mp_cost=36, cast_time=2.25,
        m_values={0: (30, 0.75), 50: (67, 0.5), 100: (92, 0.25), 200: (117, 0.0)},
        dint_cap=200,
        properties={
            'dot': True,
            'dot_formula': 'floor((skill + 59) / 36)',  # Bio II approx
            'attack_down': 1024,  # 10% attack down
        },
    ),
    'Bio III': SpellData(
        name='Bio III', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=50, tier=3, mp_cost=54, cast_time=2.5,
        m_values={0: (50, 1.0), 50: (100, 0.75), 100: (137, 0.5), 200: (187, 0.25), 300: (212, 0.0)},
        dint_cap=300,
        properties={
            'dot': True,
            'dot_formula': 'floor((skill + 59) / 27)',  # Bio III exact
            'dot_cap': 17,
            'attack_down': 2130,  # 20.81% attack down (2130/10240)
        },
    ),
}

DRAIN_SPELLS = {
    'Drain': SpellData(
        name='Drain', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=0, tier=1, mp_cost=21, cast_time=3.0,
        # Drain potency is skill-based, calculated in magic_formulas.py
        m_values={0: (0, 0.0)},  # Not INT-based
        dint_cap=0,
        properties={
            'hp_drain': True,
            'potency_formula': 'skill_based',
            # At ≤300 skill: max = skill + 20
            # At >300: max = skill * 5/8 + 132.5
            'min_potency_ratio': 0.75,
        },
    ),
    'Drain II': SpellData(
        name='Drain II', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=0, tier=2, mp_cost=37, cast_time=4.0,
        m_values={0: (0, 0.0)},
        dint_cap=0,
        properties={
            'hp_drain': True,
            'potency_formula': 'skill_based',
            'potency_multiplier': 1.5,  # Higher than Drain I
            'min_potency_ratio': 0.75,
        },
    ),
    'Drain III': SpellData(
        name='Drain III', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=0, tier=3, mp_cost=62, cast_time=5.0,
        m_values={0: (0, 0.0)},
        dint_cap=0,
        properties={
            'hp_drain': True,
            'potency_formula': 'skill_based',
            'potency_multiplier': 2.0,
            'min_potency_ratio': 0.75,
        },
    ),
}

ASPIR_SPELLS = {
    'Aspir': SpellData(
        name='Aspir', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=0, tier=1, mp_cost=10, cast_time=3.0,
        m_values={0: (0, 0.0)},
        dint_cap=0,
        properties={
            'mp_drain': True,
            'potency_formula': 'skill_based',
            # At ≤300 skill: max = skill/3 + 20
            # At >300: max = skill * 0.4
            'min_potency_ratio': 0.5,
        },
    ),
    'Aspir II': SpellData(
        name='Aspir II', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=0, tier=2, mp_cost=10, cast_time=4.0,
        m_values={0: (0, 0.0)},
        dint_cap=0,
        properties={
            'mp_drain': True,
            'potency_formula': 'skill_based',
            # max = skill * 0.6
            'skill_multiplier': 0.6,
            'min_potency_ratio': 0.5,
        },
    ),
    'Aspir III': SpellData(
        name='Aspir III', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=0, tier=3, mp_cost=10, cast_time=5.0,
        m_values={0: (0, 0.0)},
        dint_cap=0,
        properties={
            'mp_drain': True,
            'potency_formula': 'skill_based',
            # max = skill * 0.8
            'skill_multiplier': 0.8,
            'min_potency_ratio': 0.5,
        },
    ),
}

# Stun and Absorb spells
DARK_UTILITY = {
    'Stun': SpellData(
        name='Stun', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=0, tier=1, mp_cost=25, cast_time=0.5,
        recast_time=45.0,
        m_values={0: (0, 0.0)},
        dint_cap=0,
        properties={
            'stun_duration': 5.0,  # Base duration in seconds
            'no_damage': True,
        },
    ),
    'Absorb-STR': SpellData(
        name='Absorb-STR', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=0, tier=1, mp_cost=33, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'absorb_stat': 'STR', 'no_damage': True},
    ),
    'Absorb-DEX': SpellData(
        name='Absorb-DEX', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=0, tier=1, mp_cost=33, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'absorb_stat': 'DEX', 'no_damage': True},
    ),
    'Absorb-VIT': SpellData(
        name='Absorb-VIT', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=0, tier=1, mp_cost=33, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'absorb_stat': 'VIT', 'no_damage': True},
    ),
    'Absorb-AGI': SpellData(
        name='Absorb-AGI', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=0, tier=1, mp_cost=33, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'absorb_stat': 'AGI', 'no_damage': True},
    ),
    'Absorb-INT': SpellData(
        name='Absorb-INT', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=0, tier=1, mp_cost=33, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'absorb_stat': 'INT', 'no_damage': True},
    ),
    'Absorb-MND': SpellData(
        name='Absorb-MND', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=0, tier=1, mp_cost=33, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'absorb_stat': 'MND', 'no_damage': True},
    ),
    'Absorb-CHR': SpellData(
        name='Absorb-CHR', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=0, tier=1, mp_cost=33, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'absorb_stat': 'CHR', 'no_damage': True},
    ),
    'Absorb-ACC': SpellData(
        name='Absorb-ACC', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=0, tier=1, mp_cost=50, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'absorb_stat': 'ACC', 'no_damage': True},
    ),
    'Absorb-TP': SpellData(
        name='Absorb-TP', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=0, tier=1, mp_cost=38, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'absorb_stat': 'TP', 'no_damage': True},
    ),
    'Absorb-Attri': SpellData(
        name='Absorb-Attri', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=0, tier=1, mp_cost=66, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'absorb_stat': 'ALL', 'no_damage': True},
    ),
}


# =============================================================================
# Enfeebling Magic - Potency-based debuffs
# =============================================================================

ENFEEBLING_SPELLS = {
    # MND-based enfeebles
    'Slow': SpellData(
        name='Slow', element=Element.EARTH, magic_type=MagicType.ENFEEBLING_MND,
        skill_type='enfeebling', base_v=0, tier=1, mp_cost=15, cast_time=2.0,
        m_values={0: (0, 0.0)},
        properties={
            'potency_type': 'slow',
            # Slow I: 7.3%-29.2% based on dMND (±75 cap)
            'min_potency': 730,   # 7.3% in basis points
            'max_potency': 2920,  # 29.2%
            'dstat_cap': 75,
            'dstat_floor': -75,
        },
    ),
    'Slow II': SpellData(
        name='Slow II', element=Element.EARTH, magic_type=MagicType.ENFEEBLING_MND,
        skill_type='enfeebling', base_v=0, tier=2, mp_cost=45, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={
            'potency_type': 'slow',
            # Slow II: 12.5%-35.56%
            'min_potency': 1250,
            'max_potency': 3556,
            'dstat_cap': 75,
            'dstat_floor': -75,
        },
    ),
    'Paralyze': SpellData(
        name='Paralyze', element=Element.ICE, magic_type=MagicType.ENFEEBLING_MND,
        skill_type='enfeebling', base_v=0, tier=1, mp_cost=6, cast_time=2.0,
        m_values={0: (0, 0.0)},
        properties={
            'potency_type': 'paralyze',
            # Paralyze I: 5%-25% based on dMND (±40 cap)
            'min_potency': 500,
            'max_potency': 2500,
            'dstat_cap': 40,
            'dstat_floor': -40,
        },
    ),
    'Paralyze II': SpellData(
        name='Paralyze II', element=Element.ICE, magic_type=MagicType.ENFEEBLING_MND,
        skill_type='enfeebling', base_v=0, tier=2, mp_cost=36, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={
            'potency_type': 'paralyze',
            # Paralyze II: 10%-30%
            'min_potency': 1000,
            'max_potency': 3000,
            'dstat_cap': 40,
            'dstat_floor': -40,
        },
    ),
    'Addle': SpellData(
        name='Addle', element=Element.DARK, magic_type=MagicType.ENFEEBLING_MND,
        skill_type='enfeebling', base_v=0, tier=1, mp_cost=24, cast_time=2.0,
        m_values={0: (0, 0.0)},
        properties={
            'potency_type': 'addle',  # Reduces magic accuracy
            'skill_based': True,
        },
    ),
    'Addle II': SpellData(
        name='Addle II', element=Element.DARK, magic_type=MagicType.ENFEEBLING_MND,
        skill_type='enfeebling', base_v=0, tier=2, mp_cost=48, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={
            'potency_type': 'addle',
            'skill_based': True,
        },
    ),
    'Silence': SpellData(
        name='Silence', element=Element.WIND, magic_type=MagicType.ENFEEBLING_MND,
        skill_type='enfeebling', base_v=0, tier=1, mp_cost=16, cast_time=2.5,
        m_values={0: (0, 0.0)},
        properties={'effect': 'silence', 'no_potency': True},
    ),
    
    # INT-based enfeebles
    'Blind': SpellData(
        name='Blind', element=Element.DARK, magic_type=MagicType.ENFEEBLING_INT,
        skill_type='enfeebling', base_v=0, tier=1, mp_cost=5, cast_time=1.5,
        m_values={0: (0, 0.0)},
        properties={
            'potency_type': 'blind',
            # Blind I: 5-50 accuracy reduction based on dINT (-73 to +120)
            'min_potency': 5,
            'max_potency': 50,
            'dstat_cap': 120,
            'dstat_floor': -73,
        },
    ),
    'Blind II': SpellData(
        name='Blind II', element=Element.DARK, magic_type=MagicType.ENFEEBLING_INT,
        skill_type='enfeebling', base_v=0, tier=2, mp_cost=31, cast_time=2.5,
        m_values={0: (0, 0.0)},
        properties={
            'potency_type': 'blind',
            # Blind II: 15-90
            'min_potency': 15,
            'max_potency': 90,
            'dstat_cap': 120,
            'dstat_floor': -73,
        },
    ),
    'Gravity': SpellData(
        name='Gravity', element=Element.WIND, magic_type=MagicType.ENFEEBLING_INT,
        skill_type='enfeebling', base_v=0, tier=1, mp_cost=24, cast_time=2.0,
        m_values={0: (0, 0.0)},
        properties={
            'effect': 'weight',
            'potency_type': 'gravity',
            'base_potency': 5000,  # 50% movement speed reduction
        },
    ),
    'Gravity II': SpellData(
        name='Gravity II', element=Element.WIND, magic_type=MagicType.ENFEEBLING_INT,
        skill_type='enfeebling', base_v=0, tier=2, mp_cost=54, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={
            'effect': 'weight',
            'potency_type': 'gravity',
            'base_potency': 7500,  # 75% movement speed reduction
        },
    ),
    'Poison': SpellData(
        name='Poison', element=Element.WATER, magic_type=MagicType.ENFEEBLING_INT,
        skill_type='enfeebling', base_v=0, tier=1, mp_cost=5, cast_time=1.5,
        m_values={0: (0, 0.0)},
        properties={'effect': 'poison', 'dot': True, 'base_dot': 1},
    ),
    'Poison II': SpellData(
        name='Poison II', element=Element.WATER, magic_type=MagicType.ENFEEBLING_INT,
        skill_type='enfeebling', base_v=0, tier=2, mp_cost=38, cast_time=2.5,
        m_values={0: (0, 0.0)},
        properties={'effect': 'poison', 'dot': True, 'base_dot': 3},
    ),
    'Sleep': SpellData(
        name='Sleep', element=Element.DARK, magic_type=MagicType.ENFEEBLING_INT,
        skill_type='enfeebling', base_v=0, tier=1, mp_cost=19, cast_time=2.5,
        m_values={0: (0, 0.0)},
        properties={'effect': 'sleep', 'base_duration': 60},
    ),
    'Sleep II': SpellData(
        name='Sleep II', element=Element.DARK, magic_type=MagicType.ENFEEBLING_INT,
        skill_type='enfeebling', base_v=0, tier=2, mp_cost=29, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'effect': 'sleep', 'base_duration': 90},
    ),
    'Dispel': SpellData(
        name='Dispel', element=Element.DARK, magic_type=MagicType.ENFEEBLING_INT,
        skill_type='enfeebling', base_v=0, tier=1, mp_cost=25, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'effect': 'dispel', 'no_potency': True},
    ),
    'Break': SpellData(
        name='Break', element=Element.EARTH, magic_type=MagicType.ENFEEBLING_INT,
        skill_type='enfeebling', base_v=0, tier=1, mp_cost=50, cast_time=5.0,
        m_values={0: (0, 0.0)},
        properties={'effect': 'petrify', 'base_duration': 30},
    ),
    'Breakga': SpellData(
        name='Breakga', element=Element.EARTH, magic_type=MagicType.ENFEEBLING_INT,
        skill_type='enfeebling', base_v=0, tier=2, mp_cost=135, cast_time=6.0,
        is_aoe=True,
        m_values={0: (0, 0.0)},
        properties={'effect': 'petrify', 'base_duration': 30},
    ),
    
    # Skill-based enfeebles (Distract/Frazzle)
    'Distract': SpellData(
        name='Distract', element=Element.LIGHT, magic_type=MagicType.ENFEEBLING_MND,
        skill_type='enfeebling', base_v=0, tier=1, mp_cost=12, cast_time=2.0,
        m_values={0: (0, 0.0)},
        properties={
            'effect': 'evasion_down',
            'potency_type': 'distract',
            # Base potency from skill, bonus from dMND
            'skill_based': True,
        },
    ),
    'Distract II': SpellData(
        name='Distract II', element=Element.LIGHT, magic_type=MagicType.ENFEEBLING_MND,
        skill_type='enfeebling', base_v=0, tier=2, mp_cost=36, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={
            'effect': 'evasion_down',
            'potency_type': 'distract',
            'skill_based': True,
        },
    ),
    'Distract III': SpellData(
        name='Distract III', element=Element.LIGHT, magic_type=MagicType.ENFEEBLING_MND,
        skill_type='enfeebling', base_v=0, tier=3, mp_cost=64, cast_time=4.0,
        m_values={0: (0, 0.0)},
        properties={
            'effect': 'evasion_down',
            'potency_type': 'distract',
            'skill_based': True,
        },
    ),
    'Frazzle': SpellData(
        name='Frazzle', element=Element.LIGHT, magic_type=MagicType.ENFEEBLING_MND,
        skill_type='enfeebling', base_v=0, tier=1, mp_cost=18, cast_time=2.0,
        m_values={0: (0, 0.0)},
        properties={
            'effect': 'magic_evasion_down',
            'potency_type': 'frazzle',
            'skill_based': True,
        },
    ),
    'Frazzle II': SpellData(
        name='Frazzle II', element=Element.LIGHT, magic_type=MagicType.ENFEEBLING_MND,
        skill_type='enfeebling', base_v=0, tier=2, mp_cost=48, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={
            'effect': 'magic_evasion_down',
            'potency_type': 'frazzle',
            'skill_based': True,
        },
    ),
    'Frazzle III': SpellData(
        name='Frazzle III', element=Element.LIGHT, magic_type=MagicType.ENFEEBLING_MND,
        skill_type='enfeebling', base_v=0, tier=3, mp_cost=78, cast_time=4.0,
        m_values={0: (0, 0.0)},
        properties={
            'effect': 'magic_evasion_down',
            'potency_type': 'frazzle',
            'skill_based': True,
        },
    ),
}

# Dia spells (Light-based DOT + Defense Down, counts as Enfeebling)
DIA_SPELLS = {
    'Dia': SpellData(
        name='Dia', element=Element.LIGHT, magic_type=MagicType.ENFEEBLING_MND,
        skill_type='enfeebling', base_v=5, tier=1, mp_cost=7, cast_time=1.0,
        m_values={0: (5, 0.5), 50: (30, 0.0)},
        dint_cap=50,
        properties={
            'dot': True,
            'dot_damage': 1,  # HP per tick
            'defense_down': 512,  # ~5%
        },
    ),
    'Dia II': SpellData(
        name='Dia II', element=Element.LIGHT, magic_type=MagicType.ENFEEBLING_MND,
        skill_type='enfeebling', base_v=25, tier=2, mp_cost=30, cast_time=1.5,
        m_values={0: (25, 0.75), 50: (62, 0.5), 100: (87, 0.0)},
        dint_cap=100,
        properties={
            'dot': True,
            'dot_damage': 2,
            'defense_down': 1024,  # ~10%
        },
    ),
    'Dia III': SpellData(
        name='Dia III', element=Element.LIGHT, magic_type=MagicType.ENFEEBLING_MND,
        skill_type='enfeebling', base_v=78, tier=3, mp_cost=45, cast_time=2.0,
        m_values={0: (78, 1.0), 50: (128, 0.75), 100: (165, 0.5), 200: (215, 0.0)},
        dint_cap=200,
        properties={
            'dot': True,
            'dot_damage': 3,
            'defense_down': 1536,  # ~15%
        },
    ),
    'Diaga': SpellData(
        name='Diaga', element=Element.LIGHT, magic_type=MagicType.ENFEEBLING_MND,
        skill_type='enfeebling', base_v=20, tier=1, mp_cost=17, cast_time=2.0,
        is_aoe=True,
        m_values={0: (20, 0.5), 50: (45, 0.0)},
        dint_cap=50,
        properties={
            'dot': True,
            'dot_damage': 1,
            'defense_down': 512,
        },
    ),
}


# =============================================================================
# Enspells - Based on Enhancing Magic Skill (NOT INT/MAB)
# =============================================================================

# Tier I Enspells: floor(6*skill/100) + 3 if skill <= 200
#                  floor(5*skill/100) + 5 if skill > 200
# Cap: 21 damage at 320 skill

ENSPELL_TIER_I = {
    'Enfire': SpellData(
        name='Enfire', element=Element.FIRE, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=12, cast_time=3.0,
        m_values={0: (0, 0.0)},  # Skill-based, not INT
        properties={
            'enspell': True,
            'enspell_tier': 1,
            # Tier I formula:
            # If skill <= 200: floor(6*skill/100) + 3
            # If skill > 200: floor(5*skill/100) + 5
            'damage_cap': 21,
        },
    ),
    'Enblizzard': SpellData(
        name='Enblizzard', element=Element.ICE, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=12, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'enspell': True, 'enspell_tier': 1, 'damage_cap': 21},
    ),
    'Enaero': SpellData(
        name='Enaero', element=Element.WIND, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=12, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'enspell': True, 'enspell_tier': 1, 'damage_cap': 21},
    ),
    'Enstone': SpellData(
        name='Enstone', element=Element.EARTH, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=12, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'enspell': True, 'enspell_tier': 1, 'damage_cap': 21},
    ),
    'Enthunder': SpellData(
        name='Enthunder', element=Element.THUNDER, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=12, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'enspell': True, 'enspell_tier': 1, 'damage_cap': 21},
    ),
    'Enwater': SpellData(
        name='Enwater', element=Element.WATER, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=12, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'enspell': True, 'enspell_tier': 1, 'damage_cap': 21},
    ),
}

# Tier II Enspells: Same base formula, but builds +1 per attack round
# Cap: 42 damage (2x Tier I cap)
# Only first hit of each attack round gets full damage
# Also applies -10 elemental resistance to ascendant element

ENSPELL_TIER_II = {
    'Enfire II': SpellData(
        name='Enfire II', element=Element.FIRE, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=2, mp_cost=24, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={
            'enspell': True,
            'enspell_tier': 2,
            'damage_cap': 42,  # 2x Tier I
            'builds_per_round': True,
            'resistance_down': 10,  # -10 Ice resistance
            'first_hit_only': True,
        },
    ),
    'Enblizzard II': SpellData(
        name='Enblizzard II', element=Element.ICE, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=2, mp_cost=24, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={
            'enspell': True, 'enspell_tier': 2, 'damage_cap': 42,
            'builds_per_round': True, 'resistance_down': 10, 'first_hit_only': True,
        },
    ),
    'Enaero II': SpellData(
        name='Enaero II', element=Element.WIND, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=2, mp_cost=24, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={
            'enspell': True, 'enspell_tier': 2, 'damage_cap': 42,
            'builds_per_round': True, 'resistance_down': 10, 'first_hit_only': True,
        },
    ),
    'Enstone II': SpellData(
        name='Enstone II', element=Element.EARTH, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=2, mp_cost=24, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={
            'enspell': True, 'enspell_tier': 2, 'damage_cap': 42,
            'builds_per_round': True, 'resistance_down': 10, 'first_hit_only': True,
        },
    ),
    'Enthunder II': SpellData(
        name='Enthunder II', element=Element.THUNDER, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=2, mp_cost=24, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={
            'enspell': True, 'enspell_tier': 2, 'damage_cap': 42,
            'builds_per_round': True, 'resistance_down': 10, 'first_hit_only': True,
        },
    ),
    'Enwater II': SpellData(
        name='Enwater II', element=Element.WATER, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=2, mp_cost=24, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={
            'enspell': True, 'enspell_tier': 2, 'damage_cap': 42,
            'builds_per_round': True, 'resistance_down': 10, 'first_hit_only': True,
        },
    ),
}

# Enlight/Endark - Based on Divine/Dark Magic Skill
# Starting potency based on skill, decays over time
# Gives Accuracy (Enlight) or Attack (Endark) equal to current damage

ENLIGHT_ENDARK = {
    'Enlight': SpellData(
        name='Enlight', element=Element.LIGHT, magic_type=MagicType.DIVINE,
        skill_type='divine', base_v=0, tier=1, mp_cost=24, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={
            'enspell': True,
            'skill_based': 'divine',
            'bonus_type': 'accuracy',  # Gives +ACC equal to damage
            'decays': True,
        },
    ),
    'Enlight II': SpellData(
        name='Enlight II', element=Element.LIGHT, magic_type=MagicType.DIVINE,
        skill_type='divine', base_v=0, tier=2, mp_cost=48, cast_time=4.0,
        m_values={0: (0, 0.0)},
        properties={
            'enspell': True,
            'skill_based': 'divine',
            'bonus_type': 'accuracy',
            'decays': True,
            'potency_multiplier': 1.5,
        },
    ),
    'Endark': SpellData(
        name='Endark', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=0, tier=1, mp_cost=24, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={
            'enspell': True,
            'skill_based': 'dark',
            'bonus_type': 'attack',  # Gives +ATK equal to damage
            'decays': True,
        },
    ),
    'Endark II': SpellData(
        name='Endark II', element=Element.DARK, magic_type=MagicType.DARK,
        skill_type='dark', base_v=0, tier=2, mp_cost=48, cast_time=4.0,
        m_values={0: (0, 0.0)},
        properties={
            'enspell': True,
            'skill_based': 'dark',
            'bonus_type': 'attack',
            'decays': True,
            'potency_multiplier': 1.5,
        },
    ),
}


# =============================================================================
# Helix Spells (Scholar DOT) - Base 46 + skill-based
# =============================================================================

HELIX_SPELLS = {
    # Helix I spells - values from wsdist get_dint_m_v.py
    # Note: Helix spells are DOT spells where each tick uses these values
    'Geohelix': SpellData(
        name='Geohelix', element=Element.EARTH, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=75, tier=1, mp_cost=32, cast_time=2.5,
        m_values={0: (75, 2.0), 50: (175, 1.0), 100: (225, 0.0)},
        dint_cap=100,
        properties={
            'helix': True,
            'dot': True,
            'dot_ticks': 10,  # ~7-9 seconds per tick
            'forces_weather_proc': True,
        },
    ),
    'Hydrohelix': SpellData(
        name='Hydrohelix', element=Element.WATER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=75, tier=1, mp_cost=32, cast_time=2.5,
        m_values={0: (75, 2.0), 50: (175, 1.0), 100: (225, 0.0)},
        dint_cap=100,
        properties={'helix': True, 'dot': True, 'dot_ticks': 10, 'forces_weather_proc': True},
    ),
    'Anemohelix': SpellData(
        name='Anemohelix', element=Element.WIND, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=75, tier=1, mp_cost=32, cast_time=2.5,
        m_values={0: (75, 2.0), 50: (175, 1.0), 100: (225, 0.0)},
        dint_cap=100,
        properties={'helix': True, 'dot': True, 'dot_ticks': 10, 'forces_weather_proc': True},
    ),
    'Pyrohelix': SpellData(
        name='Pyrohelix', element=Element.FIRE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=75, tier=1, mp_cost=32, cast_time=2.5,
        m_values={0: (75, 2.0), 50: (175, 1.0), 100: (225, 0.0)},
        dint_cap=100,
        properties={'helix': True, 'dot': True, 'dot_ticks': 10, 'forces_weather_proc': True},
    ),
    'Cryohelix': SpellData(
        name='Cryohelix', element=Element.ICE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=75, tier=1, mp_cost=32, cast_time=2.5,
        m_values={0: (75, 2.0), 50: (175, 1.0), 100: (225, 0.0)},
        dint_cap=100,
        properties={'helix': True, 'dot': True, 'dot_ticks': 10, 'forces_weather_proc': True},
    ),
    'Ionohelix': SpellData(
        name='Ionohelix', element=Element.THUNDER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=75, tier=1, mp_cost=32, cast_time=2.5,
        m_values={0: (75, 2.0), 50: (175, 1.0), 100: (225, 0.0)},
        dint_cap=100,
        properties={'helix': True, 'dot': True, 'dot_ticks': 10, 'forces_weather_proc': True},
    ),
    'Luminohelix': SpellData(
        name='Luminohelix', element=Element.LIGHT, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=75, tier=1, mp_cost=32, cast_time=2.5,
        m_values={0: (75, 2.0), 50: (175, 1.0), 100: (225, 0.0)},
        dint_cap=100,
        properties={'helix': True, 'dot': True, 'dot_ticks': 10, 'forces_weather_proc': True},
    ),
    'Noctohelix': SpellData(
        name='Noctohelix', element=Element.DARK, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=75, tier=1, mp_cost=32, cast_time=2.5,
        m_values={0: (75, 2.0), 50: (175, 1.0), 100: (225, 0.0)},
        dint_cap=100,
        properties={'helix': True, 'dot': True, 'dot_ticks': 10, 'forces_weather_proc': True},
    ),
    # Helix II versions - approximately 2x the values of Helix I
    # Note: wsdist doesn't have separate Helix II values, these are estimated
    'Geohelix II': SpellData(
        name='Geohelix II', element=Element.EARTH, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=150, tier=2, mp_cost=64, cast_time=3.0,
        m_values={0: (150, 3.0), 50: (300, 2.0), 100: (400, 1.0), 200: (500, 0.0)},
        dint_cap=200,
        properties={'helix': True, 'dot': True, 'dot_ticks': 10, 'forces_weather_proc': True},
    ),
    'Hydrohelix II': SpellData(
        name='Hydrohelix II', element=Element.WATER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=150, tier=2, mp_cost=64, cast_time=3.0,
        m_values={0: (150, 3.0), 50: (300, 2.0), 100: (400, 1.0), 200: (500, 0.0)},
        dint_cap=200,
        properties={'helix': True, 'dot': True, 'dot_ticks': 10, 'forces_weather_proc': True},
    ),
    'Anemohelix II': SpellData(
        name='Anemohelix II', element=Element.WIND, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=150, tier=2, mp_cost=64, cast_time=3.0,
        m_values={0: (150, 3.0), 50: (300, 2.0), 100: (400, 1.0), 200: (500, 0.0)},
        dint_cap=200,
        properties={'helix': True, 'dot': True, 'dot_ticks': 10, 'forces_weather_proc': True},
    ),
    'Pyrohelix II': SpellData(
        name='Pyrohelix II', element=Element.FIRE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=150, tier=2, mp_cost=64, cast_time=3.0,
        m_values={0: (150, 3.0), 50: (300, 2.0), 100: (400, 1.0), 200: (500, 0.0)},
        dint_cap=200,
        properties={'helix': True, 'dot': True, 'dot_ticks': 10, 'forces_weather_proc': True},
    ),
    'Cryohelix II': SpellData(
        name='Cryohelix II', element=Element.ICE, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=150, tier=2, mp_cost=64, cast_time=3.0,
        m_values={0: (150, 3.0), 50: (300, 2.0), 100: (400, 1.0), 200: (500, 0.0)},
        dint_cap=200,
        properties={'helix': True, 'dot': True, 'dot_ticks': 10, 'forces_weather_proc': True},
    ),
    'Ionohelix II': SpellData(
        name='Ionohelix II', element=Element.THUNDER, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=150, tier=2, mp_cost=64, cast_time=3.0,
        m_values={0: (150, 3.0), 50: (300, 2.0), 100: (400, 1.0), 200: (500, 0.0)},
        dint_cap=200,
        properties={'helix': True, 'dot': True, 'dot_ticks': 10, 'forces_weather_proc': True},
    ),
    'Luminohelix II': SpellData(
        name='Luminohelix II', element=Element.LIGHT, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=150, tier=2, mp_cost=64, cast_time=3.0,
        m_values={0: (150, 3.0), 50: (300, 2.0), 100: (400, 1.0), 200: (500, 0.0)},
        dint_cap=200,
        properties={'helix': True, 'dot': True, 'dot_ticks': 10, 'forces_weather_proc': True},
    ),
    'Noctohelix II': SpellData(
        name='Noctohelix II', element=Element.DARK, magic_type=MagicType.ELEMENTAL,
        skill_type='elemental', base_v=150, tier=2, mp_cost=64, cast_time=3.0,
        m_values={0: (150, 3.0), 50: (300, 2.0), 100: (400, 1.0), 200: (500, 0.0)},
        dint_cap=200,
        properties={'helix': True, 'dot': True, 'dot_ticks': 10, 'forces_weather_proc': True},
    ),
}


# =============================================================================
# Enhancing Magic - Buffs and Utility
# =============================================================================

ENHANCING_SPELLS = {
    # Phalanx - Damage reduction based on Enhancing Skill
    'Phalanx': SpellData(
        name='Phalanx', element=Element.LIGHT, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=21, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={
            'buff_type': 'phalanx',
            'skill_based': True,
            # Damage reduction = floor(Enhancing Skill / 10) - 2, cap 35
            'min_potency': 1,
            'max_potency': 35,
        },
    ),
    'Phalanx II': SpellData(
        name='Phalanx II', element=Element.LIGHT, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=2, mp_cost=42, cast_time=2.0,
        m_values={0: (0, 0.0)},
        properties={
            'buff_type': 'phalanx',
            'skill_based': True,
            'target_other': True,
            'min_potency': 1,
            'max_potency': 35,
        },
    ),
    
    # Haste - Attack speed increase
    'Haste': SpellData(
        name='Haste', element=Element.WIND, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=40, cast_time=2.0,
        m_values={0: (0, 0.0)},
        properties={
            'buff_type': 'haste',
            'haste_amount': 1500,  # 15% in basis points
        },
    ),
    'Haste II': SpellData(
        name='Haste II', element=Element.WIND, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=2, mp_cost=80, cast_time=2.5,
        m_values={0: (0, 0.0)},
        properties={
            'buff_type': 'haste',
            'haste_amount': 3000,  # 30%
        },
    ),
    
    # Refresh - MP recovery
    'Refresh': SpellData(
        name='Refresh', element=Element.WATER, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=40, cast_time=2.0,
        m_values={0: (0, 0.0)},
        properties={
            'buff_type': 'refresh',
            'mp_per_tick': 3,
        },
    ),
    'Refresh II': SpellData(
        name='Refresh II', element=Element.WATER, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=2, mp_cost=70, cast_time=2.5,
        m_values={0: (0, 0.0)},
        properties={
            'buff_type': 'refresh',
            'mp_per_tick': 5,
        },
    ),
    'Refresh III': SpellData(
        name='Refresh III', element=Element.WATER, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=3, mp_cost=100, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={
            'buff_type': 'refresh',
            'mp_per_tick': 9,
        },
    ),
    
    # Stoneskin - Damage absorption
    'Stoneskin': SpellData(
        name='Stoneskin', element=Element.EARTH, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=29, cast_time=4.0,
        m_values={0: (0, 0.0)},
        properties={
            'buff_type': 'stoneskin',
            'skill_based': True,
            # Absorption = floor((Enhancing Skill - 60) / 3) + floor(MND / 3)
            'base_absorption': 50,
            'max_absorption': 350,  # Cap without gear
        },
    ),
    
    # Aquaveil - Spell interruption resistance
    'Aquaveil': SpellData(
        name='Aquaveil', element=Element.WATER, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=12, cast_time=2.0,
        m_values={0: (0, 0.0)},
        properties={
            'buff_type': 'aquaveil',
            'interruption_rate_down': True,
        },
    ),
    
    # Temper - Multi-attack enhancement
    'Temper': SpellData(
        name='Temper', element=Element.FIRE, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=24, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={
            'buff_type': 'temper',
            'skill_based': True,
            # Triple Attack based on skill
        },
    ),
    'Temper II': SpellData(
        name='Temper II', element=Element.FIRE, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=2, mp_cost=48, cast_time=4.0,
        m_values={0: (0, 0.0)},
        properties={
            'buff_type': 'temper',
            'skill_based': True,
            'target_other': True,
        },
    ),
    
    # Gain spells - Stat boosts based on Enhancing skill
    'Gain-STR': SpellData(
        name='Gain-STR', element=Element.FIRE, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=16, cast_time=2.0,
        m_values={0: (0, 0.0)},
        properties={'buff_type': 'gain', 'stat': 'STR', 'skill_based': True},
    ),
    'Gain-DEX': SpellData(
        name='Gain-DEX', element=Element.THUNDER, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=16, cast_time=2.0,
        m_values={0: (0, 0.0)},
        properties={'buff_type': 'gain', 'stat': 'DEX', 'skill_based': True},
    ),
    'Gain-VIT': SpellData(
        name='Gain-VIT', element=Element.EARTH, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=16, cast_time=2.0,
        m_values={0: (0, 0.0)},
        properties={'buff_type': 'gain', 'stat': 'VIT', 'skill_based': True},
    ),
    'Gain-AGI': SpellData(
        name='Gain-AGI', element=Element.WIND, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=16, cast_time=2.0,
        m_values={0: (0, 0.0)},
        properties={'buff_type': 'gain', 'stat': 'AGI', 'skill_based': True},
    ),
    'Gain-INT': SpellData(
        name='Gain-INT', element=Element.ICE, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=16, cast_time=2.0,
        m_values={0: (0, 0.0)},
        properties={'buff_type': 'gain', 'stat': 'INT', 'skill_based': True},
    ),
    'Gain-MND': SpellData(
        name='Gain-MND', element=Element.WATER, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=16, cast_time=2.0,
        m_values={0: (0, 0.0)},
        properties={'buff_type': 'gain', 'stat': 'MND', 'skill_based': True},
    ),
    'Gain-CHR': SpellData(
        name='Gain-CHR', element=Element.LIGHT, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=16, cast_time=2.0,
        m_values={0: (0, 0.0)},
        properties={'buff_type': 'gain', 'stat': 'CHR', 'skill_based': True},
    ),
    
    # Regen spells
    'Regen': SpellData(
        name='Regen', element=Element.LIGHT, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=1, mp_cost=15, cast_time=2.0,
        m_values={0: (0, 0.0)},
        properties={'buff_type': 'regen', 'hp_per_tick': 5},
    ),
    'Regen II': SpellData(
        name='Regen II', element=Element.LIGHT, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=2, mp_cost=36, cast_time=2.5,
        m_values={0: (0, 0.0)},
        properties={'buff_type': 'regen', 'hp_per_tick': 12},
    ),
    'Regen III': SpellData(
        name='Regen III', element=Element.LIGHT, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=3, mp_cost=64, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'buff_type': 'regen', 'hp_per_tick': 20},
    ),
    'Regen IV': SpellData(
        name='Regen IV', element=Element.LIGHT, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=4, mp_cost=82, cast_time=3.5,
        m_values={0: (0, 0.0)},
        properties={'buff_type': 'regen', 'hp_per_tick': 26},
    ),
    'Regen V': SpellData(
        name='Regen V', element=Element.LIGHT, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=5, mp_cost=100, cast_time=4.0,
        m_values={0: (0, 0.0)},
        properties={'buff_type': 'regen', 'hp_per_tick': 33},
    ),
    
    # Protect/Shell
    'Protect V': SpellData(
        name='Protect V', element=Element.LIGHT, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=5, mp_cost=75, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'buff_type': 'protect', 'defense_bonus': 180},
    ),
    'Shell V': SpellData(
        name='Shell V', element=Element.LIGHT, magic_type=MagicType.ENHANCING,
        skill_type='enhancing', base_v=0, tier=5, mp_cost=75, cast_time=3.0,
        m_values={0: (0, 0.0)},
        properties={'buff_type': 'shell', 'magic_defense_bonus': 29},
    ),
}


# =============================================================================
# Healing Magic - Cure spells
# =============================================================================

HEALING_SPELLS = {
    'Cure': SpellData(
        name='Cure', element=Element.LIGHT, magic_type=MagicType.HEALING,
        skill_type='healing', base_v=10, tier=1, mp_cost=8, cast_time=2.0,
        m_values={0: (10, 1.0), 60: (70, 0.0)},
        dint_cap=60,
        properties={
            'heal_type': 'cure',
            'base_heal': 20,
            # Cure Potency and MND affect final healing
        },
    ),
    'Cure II': SpellData(
        name='Cure II', element=Element.LIGHT, magic_type=MagicType.HEALING,
        skill_type='healing', base_v=60, tier=2, mp_cost=24, cast_time=2.0,
        m_values={0: (60, 2.0), 60: (180, 1.0), 120: (240, 0.0)},
        dint_cap=120,
        properties={'heal_type': 'cure', 'base_heal': 90},
    ),
    'Cure III': SpellData(
        name='Cure III', element=Element.LIGHT, magic_type=MagicType.HEALING,
        skill_type='healing', base_v=130, tier=3, mp_cost=46, cast_time=2.5,
        m_values={0: (130, 2.5), 60: (280, 1.5), 120: (370, 0.5), 180: (400, 0.0)},
        dint_cap=180,
        properties={'heal_type': 'cure', 'base_heal': 190},
    ),
    'Cure IV': SpellData(
        name='Cure IV', element=Element.LIGHT, magic_type=MagicType.HEALING,
        skill_type='healing', base_v=270, tier=4, mp_cost=88, cast_time=3.0,
        m_values={0: (270, 3.0), 60: (450, 2.0), 120: (570, 1.0), 180: (630, 0.0)},
        dint_cap=180,
        properties={'heal_type': 'cure', 'base_heal': 380},
    ),
    'Cure V': SpellData(
        name='Cure V', element=Element.LIGHT, magic_type=MagicType.HEALING,
        skill_type='healing', base_v=450, tier=5, mp_cost=135, cast_time=3.0,
        m_values={0: (450, 3.5), 60: (660, 2.5), 120: (810, 1.5), 180: (900, 0.5), 240: (930, 0.0)},
        dint_cap=240,
        properties={'heal_type': 'cure', 'base_heal': 600},
    ),
    'Cure VI': SpellData(
        name='Cure VI', element=Element.LIGHT, magic_type=MagicType.HEALING,
        skill_type='healing', base_v=670, tier=6, mp_cost=227, cast_time=3.0,
        m_values={0: (670, 4.0), 60: (910, 3.0), 120: (1090, 2.0), 180: (1210, 1.0), 240: (1270, 0.0)},
        dint_cap=240,
        properties={'heal_type': 'cure', 'base_heal': 900},
    ),
    
    # Curaga (AoE healing)
    'Curaga': SpellData(
        name='Curaga', element=Element.LIGHT, magic_type=MagicType.HEALING,
        skill_type='healing', base_v=60, tier=1, mp_cost=60, cast_time=2.5,
        is_aoe=True,
        m_values={0: (60, 1.5), 60: (150, 0.75), 120: (195, 0.0)},
        dint_cap=120,
        properties={'heal_type': 'curaga', 'base_heal': 90},
    ),
    'Curaga II': SpellData(
        name='Curaga II', element=Element.LIGHT, magic_type=MagicType.HEALING,
        skill_type='healing', base_v=130, tier=2, mp_cost=120, cast_time=3.0,
        is_aoe=True,
        m_values={0: (130, 2.0), 60: (250, 1.25), 120: (325, 0.5), 180: (355, 0.0)},
        dint_cap=180,
        properties={'heal_type': 'curaga', 'base_heal': 190},
    ),
    'Curaga III': SpellData(
        name='Curaga III', element=Element.LIGHT, magic_type=MagicType.HEALING,
        skill_type='healing', base_v=270, tier=3, mp_cost=180, cast_time=3.0,
        is_aoe=True,
        m_values={0: (270, 2.5), 60: (420, 1.75), 120: (525, 1.0), 180: (585, 0.0)},
        dint_cap=180,
        properties={'heal_type': 'curaga', 'base_heal': 380},
    ),
    'Curaga IV': SpellData(
        name='Curaga IV', element=Element.LIGHT, magic_type=MagicType.HEALING,
        skill_type='healing', base_v=450, tier=4, mp_cost=260, cast_time=3.5,
        is_aoe=True,
        m_values={0: (450, 3.0), 60: (630, 2.25), 120: (765, 1.5), 180: (855, 0.75), 240: (900, 0.0)},
        dint_cap=240,
        properties={'heal_type': 'curaga', 'base_heal': 600},
    ),
    'Curaga V': SpellData(
        name='Curaga V', element=Element.LIGHT, magic_type=MagicType.HEALING,
        skill_type='healing', base_v=670, tier=5, mp_cost=366, cast_time=4.0,
        is_aoe=True,
        m_values={0: (670, 3.5), 60: (880, 2.75), 120: (1045, 2.0), 180: (1165, 1.0), 240: (1225, 0.0)},
        dint_cap=240,
        properties={'heal_type': 'curaga', 'base_heal': 900},
    ),
}


# =============================================================================
# Special Spells - Impact, Dispelga
# =============================================================================

SPECIAL_SPELLS = {
    # Impact - powerful enfeebling with damage component
    # Reduces all stats by ~20, Defense by ~10%, Magic Defense by 20%
    'Impact': SpellData(
        name='Impact', element=Element.DARK, magic_type=MagicType.ENFEEBLING_INT,
        skill_type='enfeebling', base_v=100, tier=1, mp_cost=324, cast_time=4.0,
        m_values={0: (100, 1.5), 50: (175, 1.0), 100: (225, 0.5), 200: (275, 0.0)},
        dint_cap=200,
        properties={
            'effect': 'impact_debuff',
            'stat_down': 20,  # All stats reduced
            'defense_down_pct': 10,
            'magic_defense_down_pct': 20,
            'skill_based': True,  # Potency affected by Enfeebling skill
            'requires_twilight_cloak': True,
        },
    ),
    
    # Dispelga - AoE dispel
    'Dispelga': SpellData(
        name='Dispelga', element=Element.DARK, magic_type=MagicType.ENFEEBLING_INT,
        skill_type='enfeebling', base_v=0, tier=1, mp_cost=74, cast_time=4.0,
        is_aoe=True,
        m_values={0: (0, 0.0)},
        properties={
            'effect': 'dispel',
            'no_potency': True,
            'requires_daybreak': True,  # Requires Daybreak weapon
        },
    ),
}


# =============================================================================
# Build Complete Spell Database
# =============================================================================

ALL_SPELLS: Dict[str, SpellData] = {}

# Add all elemental spells
for spell_dict in [
    ELEMENTAL_TIER_I, ELEMENTAL_TIER_II, ELEMENTAL_TIER_III,
    ELEMENTAL_TIER_IV, ELEMENTAL_TIER_V, ELEMENTAL_TIER_VI,
    ELEMENTAL_GA_TIER_I, ELEMENTAL_JA,
    ANCIENT_MAGIC, ANCIENT_MAGIC_II,
]:
    ALL_SPELLS.update(spell_dict)

ALL_SPELLS['Comet'] = COMET

# Add Divine magic (Banish, Holy)
ALL_SPELLS.update(BANISH_SPELLS)
ALL_SPELLS.update(HOLY_SPELLS)

# Add Dark magic (Bio, Drain, Aspir, Stun, Absorbs)
ALL_SPELLS.update(BIO_SPELLS)
ALL_SPELLS.update(DRAIN_SPELLS)
ALL_SPELLS.update(ASPIR_SPELLS)
ALL_SPELLS.update(DARK_UTILITY)

# Add Enfeebling magic
ALL_SPELLS.update(ENFEEBLING_SPELLS)
ALL_SPELLS.update(DIA_SPELLS)

# Add Enspells
ALL_SPELLS.update(ENSPELL_TIER_I)
ALL_SPELLS.update(ENSPELL_TIER_II)
ALL_SPELLS.update(ENLIGHT_ENDARK)

# Add Helix spells
ALL_SPELLS.update(HELIX_SPELLS)

# Add Enhancing magic (Phalanx, Haste, Refresh, etc.)
ALL_SPELLS.update(ENHANCING_SPELLS)

# Add Healing magic (Cure, Curaga)
ALL_SPELLS.update(HEALING_SPELLS)

# Add Special spells (Impact, Dispelga)
ALL_SPELLS.update(SPECIAL_SPELLS)


def get_spell(name: str) -> Optional[SpellData]:
    """Get spell data by name (case-insensitive)."""
    return ALL_SPELLS.get(name) or ALL_SPELLS.get(name.title())


def get_spells_by_element(element: Element) -> List[SpellData]:
    """Get all spells of a given element."""
    return [s for s in ALL_SPELLS.values() if s.element == element]


def get_spells_by_tier(tier: int) -> List[SpellData]:
    """Get all spells of a given tier."""
    return [s for s in ALL_SPELLS.values() if s.tier == tier]


# =============================================================================
# Skillchain Elements for Magic Bursting
# =============================================================================

SKILLCHAIN_ELEMENTS = {
    # Level 1 skillchains
    'Liquefaction': [Element.FIRE],
    'Impaction': [Element.THUNDER],
    'Detonation': [Element.WIND],
    'Scission': [Element.EARTH],
    'Reverberation': [Element.WATER],
    'Induration': [Element.ICE],
    'Transfixion': [Element.LIGHT],
    'Compression': [Element.DARK],
    
    # Level 2 skillchains
    'Fusion': [Element.FIRE, Element.LIGHT],
    'Fragmentation': [Element.THUNDER, Element.WIND],
    'Distortion': [Element.WATER, Element.ICE],
    'Gravitation': [Element.EARTH, Element.DARK],
    
    # Level 3 skillchains
    'Light': [Element.FIRE, Element.LIGHT, Element.THUNDER, Element.WIND],
    'Darkness': [Element.WATER, Element.ICE, Element.EARTH, Element.DARK],
    
    # Level 4 (Radiance/Umbra)
    'Radiance': [Element.FIRE, Element.LIGHT, Element.THUNDER, Element.WIND],
    'Umbra': [Element.WATER, Element.ICE, Element.EARTH, Element.DARK],
}


def can_magic_burst(spell: SpellData, skillchain: str) -> bool:
    """Check if a spell can magic burst a given skillchain."""
    if skillchain not in SKILLCHAIN_ELEMENTS:
        return False
    return spell.element in SKILLCHAIN_ELEMENTS[skillchain]
