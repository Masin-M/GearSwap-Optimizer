"""
Buff Definitions for FFXI Gear Optimizer

This file centralizes all buff, debuff, and food definitions used by the optimizer.
To add new buffs, simply add entries to the appropriate dictionary below.

ORGANIZATION:
- PHYSICAL_BUFFS: Buffs for TP/WS optimization (melee, ranged)
- MAGIC_BUFFS: Buffs for magic optimization (nukes, enfeebles, heals)
- PHYSICAL_DEBUFFS: Enemy debuffs for physical damage
- MAGIC_DEBUFFS: Enemy debuffs for magic damage

STAT KEY REFERENCE:
Physical Stats:
    STR, DEX, VIT, AGI, INT, MND, CHR  - Primary stats
    attack              - Flat attack bonus
    attack_pct          - Attack % multiplier (0.25 = 25%)
    accuracy            - Flat accuracy bonus
    ranged_attack       - Flat ranged attack bonus
    ranged_attack_pct   - Ranged attack % multiplier
    ranged_accuracy     - Flat ranged accuracy bonus
    magic_haste         - Magic haste as fraction (307/1024 for Haste II)
    ja_haste            - Job ability haste (10 = 10%)
    store_tp            - Store TP bonus
    double_attack       - Double Attack %
    triple_attack       - Triple Attack %
    crit_rate           - Critical hit rate %
    pdl                 - Physical Damage Limit+
    
Magic Stats:
    INT, MND            - Primary magic stats
    magic_attack        - Magic Attack Bonus (flat)
    magic_attack_pct    - Magic Attack % multiplier
    magic_accuracy      - Magic Accuracy bonus
    magic_damage        - Magic Damage bonus
    magic_burst_bonus   - Magic Burst Bonus %

Debuff Stats (applied to enemy):
    defense_down_pct    - Defense reduction % (0.20 = 20%)
    evasion_down        - Flat evasion reduction
    magic_defense_down  - Magic Defense reduction
    magic_evasion_down  - Magic Evasion reduction

FOOD NOTE:
    Food stats listed here use the CAPS as flat values, assuming players
    will reach those caps. Percentage-based bonuses are converted to their
    maximum values. Pet and ranged effects are ignored.
"""

# =============================================================================
# PHYSICAL BUFFS (TP/WS Optimization)
# =============================================================================

PHYSICAL_BUFFS = {
    # -------------------------------------------------------------------------
    # BARD SONGS
    # -------------------------------------------------------------------------
    "brd": {
        # Marches (Haste)
        "Honor March": {
            "magic_haste": 126/1024,
            "attack": 168,
            "accuracy": 42,
            "songs": 1,
            "description": "Requires Marsyas horn"
        },
        "Victory March": {
            "magic_haste": 163/1024,
            "songs": 1,
            "description": "Best haste march"
        },
        "Advancing March": {
            "magic_haste": 108/1024,
            "songs": 1,
            "description": "Standard haste march"
        },
        
        # Minuets (Attack)
        "Minuet V": {"attack": 149, "songs": 1},
        "Minuet IV": {"attack": 137, "songs": 1},
        "Minuet III": {"attack": 121, "songs": 1},
        
        # Madrigals (Accuracy)
        "Blade Madrigal": {"accuracy": 60, "songs": 1},
        "Sword Madrigal": {"accuracy": 45, "songs": 1},
        
        # Etudes (Stats)
        "Herculean Etude": {"STR": 15, "songs": 1},
        "Uncanny Etude": {"DEX": 15, "songs": 1},
        "Vital Etude": {"VIT": 15, "songs": 1},
        "Swift Etude": {"AGI": 15, "songs": 1},
        "Sage Etude": {"INT": 15, "songs": 1},
        "Logical Etude": {"MND": 15, "songs": 1},
        
        # Other
        "Aria of Passion": {"pdl": 12, "songs": 1, "description": "Physical Damage Limit+"},
    },
    
    # -------------------------------------------------------------------------
    # CORSAIR ROLLS
    # -------------------------------------------------------------------------
    "cor": {
        # Attack Rolls
        "Chaos Roll XI": {"attack_pct": 0.3125, "description": "31.25% attack"},
        "Chaos Roll X": {"attack_pct": 0.1875, "description": "18.75% attack"},
        
        # TP Rolls
        "Samurai Roll XI": {"store_tp": 40},
        "Samurai Roll X": {"store_tp": 24},
        
        # Multi-Attack Rolls
        "Fighter's Roll XI": {"double_attack": 15},
        "Fighter's Roll X": {"double_attack": 7},
        
        # Crit Rolls
        "Rogue's Roll XI": {"crit_rate": 14},
        "Rogue's Roll X": {"crit_rate": 8},
        
        # Accuracy Rolls
        "Hunter's Roll XI": {"accuracy": 50, "ranged_accuracy": 50},
        "Hunter's Roll X": {"accuracy": 30, "ranged_accuracy": 30},
        
        # Regain
        "Tactician's Roll XI": {"regain": 40},
        "Tactician's Roll X": {"regain": 24},
    },
    
    # -------------------------------------------------------------------------
    # GEOMANCER BUBBLES
    # -------------------------------------------------------------------------
    "geo": {
        # Attack
        "Geo-Fury": {"attack_pct": 0.347, "description": "~35% attack with full potency"},
        "Indi-Fury": {"attack_pct": 0.20},
        "Entrust Indi-Fury": {"attack_pct": 0.20},
        
        # Accuracy
        "Geo-Precision": {"accuracy": 50},
        "Indi-Precision": {"accuracy": 30},
        
        # Haste
        "Geo-Haste": {"magic_haste": 299/1024},
        "Indi-Haste": {"magic_haste": 200/1024},
        "Entrust Indi-Haste": {"magic_haste": 200/1024},
        
        # Stats
        "Geo-STR": {"STR": 25},
        "Indi-STR": {"STR": 15},
        "Geo-DEX": {"DEX": 25},
        "Indi-DEX": {"DEX": 15},
        "Geo-VIT": {"VIT": 25},
        "Indi-VIT": {"VIT": 15},
        "Geo-AGI": {"AGI": 25},
        "Indi-AGI": {"AGI": 15},
    },
    
    # -------------------------------------------------------------------------
    # WHITE MAGE BUFFS
    # -------------------------------------------------------------------------
    "whm": {
        # Haste
        "Haste": {"magic_haste": 150/1024},
        "Haste II": {"magic_haste": 307/1024},
        
        # Boost Spells
        "Boost-STR": {"STR": 25},
        "Boost-DEX": {"DEX": 25},
        "Boost-VIT": {"VIT": 25},
        "Boost-AGI": {"AGI": 25},
        
        # Gain Spells (RDM)
        "Gain-STR": {"STR": 55},
        "Gain-DEX": {"DEX": 55},
        "Gain-VIT": {"VIT": 55},
        "Gain-AGI": {"AGI": 55},
        
        # Storms
        "Firestorm II": {"STR": 7},
        "Thunderstorm II": {"DEX": 7},
        "Sandstorm II": {"VIT": 7},
        "Windstorm II": {"AGI": 7},
        
        # Defense
        "Shell V": {"mdt": -29, "description": "-29% magic damage taken"},
    },
    
    # # -------------------------------------------------------------------------
    # # JOB ABILITIES
    # # -------------------------------------------------------------------------
    # "abilities": {
    #     # WAR
    #     "Berserk": {"attack_pct": 0.25, "job": "war"},
    #     "Warcry": {"attack_pct": 0.10, "job": "war", "description": "Party-wide"},
    #     "Aggressor": {"accuracy": 25, "job": "war"},
    #     "Mighty Strikes": {"crit_rate": 100, "job": "war", "description": "2HR"},
    #     "Blood Rage": {"crit_rate": 20, "job": "war"},
        
    #     # DRK
    #     "Last Resort": {"attack_pct": 0.25, "ja_haste": 15, "job": "drk"},
    #     "Endark II": {"attack": 125, "accuracy": 20, "job": "drk"},
        
    #     # SAM
    #     "Hasso": {"STR": 14, "ja_haste": 10, "accuracy": 10, "job": "sam"},
    #     # "Meditate": {"tp_bonus": 0, "job": "sam"},
    #     # "Sekkanoki": {"job": "sam"},
        
    #     # NIN
    #     "Sange": {"daken": 100, "job": "nin"},
    #     "Innin": {"crit_rate": 20, "accuracy": 20, "job": "nin"},
    #     "Yonin": {"enmity": 30, "job": "nin"},
        
    #     # MNK
    #     "Focus": {"crit_rate": 20, "accuracy": 100, "job": "mnk"},
    #     "Impetus": {"crit_rate": 50, "attack": 140, "job": "mnk"},
    #     "Footwork": {"kick_attacks": 20, "job": "mnk"},
        
    #     # THF
    #     # "Sneak Attack": {"job": "thf"},
    #     # "Trick Attack": {"job": "thf"},
    #     "Conspirator": {"accuracy": 45, "job": "thf"},
        
    #     # RNG
    #     "Sharpshot": {"ranged_accuracy": 40, "job": "rng"},
    #     "Velocity Shot": {"ranged_attack_pct": 0.15, "job": "rng"},
    #     "Double Shot": {"double_shot": 40, "job": "rng"},
        
    #     # COR
    #     "Triple Shot": {"triple_shot": 40, "job": "cor"},
        
    #     # DRG
    #     # "High Jump": {"job": "drg"},
    #     # "Spirit Jump": {"tp_bonus": 50, "job": "drg"},
        
    #     # PLD
    #     # "Divine Emblem": {"job": "pld"},
        
    #     # SMN Favors (party buffs from pets)
    #     "Ifrit's Favor": {"double_attack": 25, "job": "smn"},
    #     "Garuda's Favor": {"magic_haste": 0.05, "job": "smn"},
    #     "Ramuh's Favor": {"crit_rate": 23, "job": "smn"},
        
    #     # BST
    #     # "Sic": {"job": "bst"},
        
    #     # Misc
    #     "Haste Samba": {"ja_haste": 10, "job": "dnc"},
    #     "Haste Samba (sub)": {"ja_haste": 5, "job": "dnc"},
    # },
    
    # -------------------------------------------------------------------------
    # FOOD (Physical) - VERIFIED FROM BG-WIKI
    # All values are CAPS (maximum effect at high base stats)
    # -------------------------------------------------------------------------
    "food": {
        # Attack + Accuracy Foods
        "Grape Daifuku": {
            "STR": 2, "VIT": 3,
            "attack": 50, "accuracy": 80,
            "description": "Balanced attack/accuracy food (caps: Acc 80, Atk 50)"
        },
        
        # Pure Attack Foods
        "Red Curry Bun": {
            "STR": 7,
            "attack": 150,
            "description": "High attack food (23% cap 150), no accuracy"
        },
        "Red Curry Bun +1": {
            "STR": 8,
            "attack": 150,
            "description": "HQ high attack food (25% cap 150)"
        },
        
        # Accuracy Foods
        "Sublime Sushi": {
            "STR": 6, "DEX": 7,
            "accuracy": 100,
            "description": "Best accuracy food (10% cap 100)"
        },
        "Sublime Sushi +1": {
            "STR": 7, "DEX": 8,
            "accuracy": 105,
            "description": "HQ best accuracy food (11% cap 105)"
        },
        
        # Multi-purpose AoE Food (also has magic stats)
        "Altana's Repast": {
            "STR": 10, "DEX": 10, "VIT": 10, "AGI": 10,
            "attack": 70, "accuracy": 70,
            "store_tp": 6,
            "description": "AoE food with all stats"
        },
        "Altana's Repast +1": {
            "STR": 12, "DEX": 12, "VIT": 12, "AGI": 12,
            "attack": 80, "accuracy": 80,
            "store_tp": 7,
            "description": "HQ AoE food"
        },
        "Altana's Repast +2": {
            "STR": 15, "DEX": 15, "VIT": 15, "AGI": 15,
            "attack": 90, "accuracy": 90,
            "store_tp": 8,
            "description": "HQ2 AoE food"
        },
    },
}


# =============================================================================
# MAGIC BUFFS (Magic Optimization)
# =============================================================================

MAGIC_BUFFS = {
    # -------------------------------------------------------------------------
    # BARD SONGS (Magic)
    # -------------------------------------------------------------------------
    "brd": {
        # Etudes for mages
        "Sage Etude": {"INT": 15, "songs": 1},
        "Learned Etude": {"INT": 10, "songs": 1},
        "Logical Etude": {"MND": 15, "songs": 1},
        "Spirited Etude": {"MND": 10, "songs": 1},
        
        # Carols (magic defense for party)
        "Ice Carol II": {"magic_evasion": 50, "songs": 1},
        "Lightning Carol II": {"magic_evasion": 50, "songs": 1},
    },
    
    # -------------------------------------------------------------------------
    # CORSAIR ROLLS (Magic)
    # -------------------------------------------------------------------------
    "cor": {
        # MAB Rolls
        "Wizard's Roll XI": {"magic_attack": 50, "description": "Best MAB roll"},
        "Wizard's Roll X": {"magic_attack": 30},
        
        # Magic Accuracy Rolls
        "Warlock's Roll XI": {"magic_accuracy": 52},
        "Warlock's Roll X": {"magic_accuracy": 32},
        
        # Refresh/MP
        "Evoker's Roll XI": {"refresh": 7},
        "Evoker's Roll X": {"refresh": 5},
    },
    
    # -------------------------------------------------------------------------
    # GEOMANCER BUBBLES (Magic)
    # -------------------------------------------------------------------------
    "geo": {
        # MAB
        "Geo-Acumen": {
            "magic_attack_pct": 35,
            "description": "35% MAB with full potency"
        },
        "Indi-Acumen": {"magic_attack_pct": 20},
        "Entrust Indi-Acumen": {"magic_attack_pct": 20},
        
        # Magic Accuracy
        "Geo-Focus": {"magic_accuracy": 75},
        "Indi-Focus": {"magic_accuracy": 45},
        "Entrust Indi-Focus": {"magic_accuracy": 45},
        
        # Stats
        "Geo-INT": {"INT": 25},
        "Indi-INT": {"INT": 15},
        "Geo-MND": {"MND": 25},
        "Indi-MND": {"MND": 15},
        
        # Refresh
        "Geo-Refresh": {"refresh": 5},
        "Indi-Refresh": {"refresh": 3},
    },
    


    #Can reactivate when i add these to the simulator.
    # -------------------------------------------------------------------------
    # SCHOLAR ABILITIES
    # -------------------------------------------------------------------------
    # "sch": {
    #     "Ebullience": {
    #         "magic_damage_mult": 40,
    #         "description": "+40% magic damage on next spell"
    #     },
    #     "Immanence": {
    #         "skillchain_enabled": True,
    #         "description": "Enables magic skillchain"
    #     },
    #     "Dark Arts": {
    #         "description": "Enhances dark/elemental magic"
    #     },
    #     "Light Arts": {
    #         "description": "Enhances healing/enhancing magic"
    #     },
    #     "Klimaform": {
    #         "magic_attack": 25,
    #         "description": "Weather-based MAB"
    #     },
    # },
    


    #Currently not implemented as it's very niche and would require a large refactor in terms of parsing to add this to the parser and stat storage
    #format. Also, this is one of those things that the gear is so few and far between, it could easily be managed by the individual.
    # -------------------------------------------------------------------------
    # WHITE MAGE BUFFS (Magic)
    # -------------------------------------------------------------------------
    # "whm": {
    #     # Storms (stat + weather)
    #     "Firestorm II": {"STR": 7, "description": "+Fire weather"},
    #     "Thunderstorm II": {"DEX": 7, "description": "+Thunder weather"},
    #     "Hailstorm II": {"INT": 7, "description": "+Ice weather"},
    #     "Voidstorm II": {"INT": 7, "description": "+Dark weather"},
    #     "Aurorastorm II": {"MND": 7, "description": "+Light weather"},
    # },
    
    # -------------------------------------------------------------------------
    # FOOD (Magic) - VERIFIED FROM BG-WIKI
    # All values are CAPS (maximum effect at high base stats)
    # -------------------------------------------------------------------------
    "food": {
        # Magic Attack Bonus Foods (NO Magic Accuracy)
        "Cehuetzi Snow Cone": {
            "INT": 5, "MND": 5,
            "magic_attack": 13,
            "description": "Best MAB food (MAB+13, no M.Acc)"
        },
        "Apingaut Snow Cone": {
            "INT": 6, "MND": 6,
            "magic_attack": 14,
            "description": "HQ MAB food (MAB+14, no M.Acc)"
        },
        "Cyclical Coalescence": {
            "INT": 7, "MND": 7,
            "magic_attack": 15,
            "description": "HQ2 best MAB food (MAB+15, no M.Acc)"
        },
        
        # Magic Accuracy Foods (NO Magic Attack Bonus)
        "Tropical Crepe": {
            "INT": 2, "MND": 2,
            "magic_accuracy": 90,
            "description": "Best M.Acc food (20% cap 90, no MAB)"
        },
        "Crepe des Rois": {
            "INT": 2, "MND": 2,
            "magic_accuracy": 95,
            "description": "HQ best M.Acc food (21% cap 95, no MAB)"
        },
        "Pear Crepe": {
            "INT": 2,
            "magic_accuracy": 45,
            "description": "Budget M.Acc food (20% cap 45, no MAB)"
        },
        "Crepe Belle Helene": {
            "INT": 3, "MND": 3,
            "magic_accuracy": 50,
            "description": "HQ budget M.Acc (21% cap 50, no MAB)"
        },
        
        # Hybrid MAB + M.Acc Foods (lower stats but both)
        "Fruit Parfait": {
            "INT": 3, "MND": 2,
            "magic_attack": 6, "magic_accuracy": 3,
            "description": "Low hybrid MAB+6/M.Acc+3"
        },
        "Queen's Crown": {
            "INT": 4, "MND": 3,
            "magic_attack": 7, "magic_accuracy": 4,
            "description": "HQ hybrid MAB+7/M.Acc+4"
        },
        
        # Multi-purpose AoE Food
        "Altana's Repast": {
            "INT": 10, "MND": 10,
            "magic_attack": 10, "magic_accuracy": 70,
            "description": "AoE food (MAB+10, M.Acc+70)"
        },
        "Altana's Repast +1": {
            "INT": 12, "MND": 12,
            "magic_attack": 11, "magic_accuracy": 80,
            "description": "HQ AoE food"
        },
        "Altana's Repast +2": {
            "INT": 15, "MND": 15,
            "magic_attack": 12, "magic_accuracy": 90,
            "description": "HQ2 AoE food"
        },
    },
}


# =============================================================================
# JOB ABILITIES
# =============================================================================
# These abilities are passed to create_player as {"AbilityName": True/False}
# Each ability has a "job" field indicating which job(s) can use it.
# "main_only" means only available as main job, not sub job.
# "description" provides tooltip info for the UI.
#
# NOTE: Party buffs (SMN Favors, Haste Samba from others) are commented out.
# We may implement them separately as "Party Buffs" later.

PHYSICAL_ABILITIES = {
    # =========================================================================
    # WAR - Warrior
    # =========================================================================
    "Berserk": {
        "job": "war",
        "main_only": False,
        "description": "+25% Attack (+10% more as WAR main, +8.5% with Conqueror)",
    },
    "Warcry": {
        "job": "war",
        "main_only": False,
        "description": "Party-wide Attack boost",
    },
    "Aggressor": {
        "job": "war",
        "main_only": False,
        "description": "+25 Accuracy (traded for Evasion)",
    },
    "Blood Rage": {
        "job": "war",
        "main_only": True,
        "description": "+20% Crit Rate for party",
    },
    "Mighty Strikes": {
        "job": "war",
        "main_only": True,
        "description": "2HR - 100% Crit Rate",
        "is_2hr": True,
    },
    
    # =========================================================================
    # MNK - Monk
    # =========================================================================
    "Focus": {
        "job": "mnk",
        "main_only": False,
        "description": "+20% Crit Rate, +100 Accuracy (+20 more as MNK main)",
    },
    "Impetus": {
        "job": "mnk",
        "main_only": True,
        "description": "+50% Crit Rate, +140 Attack (at full potency). Bhikku body adds Crit Dmg/Acc.",
    },
    "Footwork": {
        "job": "mnk",
        "main_only": True,
        "description": "+20% Kick Attacks rate, enhances kick damage",
    },
    
    # =========================================================================
    # THF - Thief
    # =========================================================================
    "Conspirator": {
        "job": "thf",
        "main_only": True,
        "description": "+45 Accuracy, +50 Subtle Blow (assumes 6 on enmity list). Skulker's body adds Attack.",
    },
    # "Sneak Attack": {
    #     "job": "thf",
    #     "main_only": False,
    #     "description": "Next attack from behind is critical + DEX bonus",
    # },
    # "Trick Attack": {
    #     "job": "thf",
    #     "main_only": False,
    #     "description": "Next attack from behind ally adds AGI to damage",
    # },
    
    # =========================================================================
    # DRK - Dark Knight
    # =========================================================================
    "Last Resort": {
        "job": "drk",
        "main_only": False,
        "description": "+25% Attack (+10% more as DRK main). +15 JA Haste with 2H weapon (+10 more as DRK main).",
    },
    "Endark II": {
        "job": "drk",
        "main_only": True,
        "description": "+125 Attack, +20 Accuracy (at 600 Dark Magic skill, 80% potency assumed)",
    },
    
    # =========================================================================
    # RNG - Ranger
    # =========================================================================
    "Sharpshot": {
        "job": "rng",
        "main_only": False,
        "description": "+40 Ranged Accuracy (+40 Ranged Attack as RNG main)",
    },
    "Velocity Shot": {
        "job": "rng",
        "main_only": True,
        "description": "+15% Ranged Attack, -15 JA Haste. Amini body/Belenus cape add more.",
    },
    "Double Shot": {
        "job": "rng",
        "main_only": True,
        "description": "+40% Double Shot rate. Arcadian body converts half to Triple Shot.",
    },
    "Barrage": {
        "job": "rng",
        "main_only": True,
        "description": "+60 Ranged Attack during Barrage",
    },
    "Hover Shot": {
        "job": "rng",
        "main_only": True,
        "description": "+100 Ranged Accuracy, doubles ranged damage",
    },
    
    # =========================================================================
    # SAM - Samurai
    # =========================================================================
    "Hasso": {
        "job": "sam",
        "main_only": False,
        "description": "+STR (14+20 as SAM main), +10 JA Haste, +10 Accuracy. Requires 2H weapon.",
    },
    # "Meditate": handled separately as TP gain
    # "Sekkanoki": WS-specific, handled in WS code
    
    # =========================================================================
    # NIN - Ninja
    # =========================================================================
    "Innin": {
        "job": "nin",
        "main_only": True,
        "description": "+20% Crit Rate (at 70% potency), +20 Accuracy, +5 SC/MB bonus. From behind enemy.",
    },
    "Sange": {
        "job": "nin",
        "main_only": True,
        "description": "100% Daken rate, +100 Ranged Accuracy. Requires Shuriken.",
    },
    "Futae": {
        "job": "nin",
        "main_only": True,
        "description": "+100 Ninjutsu Magic Damage",
    },
    "Yonin": {
        "job": "nin",
        "main_only": True,
        "description": "+30 Enmity (tank stance). In front of enemy.",
    },
    
    # =========================================================================
    # COR - Corsair
    # =========================================================================
    "Triple Shot": {
        "job": "cor",
        "main_only": True,
        "description": "+40% Triple Shot rate. Lanun hands convert half to Quad Shot.",
    },
    
    # =========================================================================
    # DNC - Dancer
    # =========================================================================
    "Building Flourish": {
        "job": "dnc",
        "main_only": True,
        "description": "+25% Attack, +10% Crit Rate, +40 Accuracy, +WSD from gifts",
    },
    "Climactic Flourish": {
        "job": "dnc",
        "main_only": True,
        "description": "+25% Attack, +10% Crit Rate, +40 Accuracy, +20% WSD. First hit is crit.",
    },
    "Striking Flourish": {
        "job": "dnc",
        "main_only": True,
        "description": "First hit is crit with bonus damage",
    },
    "Ternary Flourish": {
        "job": "dnc",
        "main_only": True,
        "description": "Guarantees TA on first hit",
    },
    "Saber Dance": {
        "job": "dnc",
        "main_only": True,
        "description": "+25% Double Attack (minimum potency)",
    },
    "Closed Position": {
        "job": "dnc",
        "main_only": True,
        "description": "Store TP bonus with Horos feet (+3 STP per merit)",
    },
    
    # =========================================================================
    # PLD - Paladin
    # =========================================================================
    "Divine Emblem": {
        "job": "pld",
        "main_only": True,
        "description": "+40 Magic Damage for divine spells",
    },
    "Enlight II": {
        "job": "pld",
        "main_only": True,
        "description": "+120 Accuracy at 600 Divine skill (80% potency assumed)",
    },
    
    # =========================================================================
    # RDM - Red Mage
    # =========================================================================
    "Composure": {
        "job": "rdm",
        "main_only": True,
        "description": "+70 Accuracy, +200% EnSpell damage",
    },
    "Temper II": {
        "job": "rdm",
        "main_only": True,
        "description": "Triple Attack based on Enhancing skill (up to +40% at 700 skill)",
        "requires_skill": "Enhancing Skill",
    },
    
    # =========================================================================
    # BLM - Black Mage
    # =========================================================================
    "Manafont": {
        "job": "blm",
        "main_only": True,
        "description": "2HR - +60 Magic Damage",
        "is_2hr": True,
    },
    "Manawell": {
        "job": "blm",
        "main_only": True,
        "description": "+20 Magic Damage",
    },
    
    # =========================================================================
    # SCH - Scholar
    # =========================================================================
    "Ebullience": {
        "job": "sch",
        "main_only": True,
        "description": "+40 Magic Damage, next spell has bonus damage",
    },
    "Enlightenment": {
        "job": "sch",
        "main_only": True,
        "description": "+20 INT, +20 MND",
    },
    "Klimaform": {
        "job": "sch",
        "main_only": False,
        "description": "+15 Magic Accuracy. SCH Empy feet add damage.",
    },
    
    # =========================================================================
    # GEO - Geomancer
    # =========================================================================
    "Theurgic Focus": {
        "job": "geo",
        "main_only": True,
        "description": "+50 -ra Magic Attack, +60 -ra Magic Damage",
    },
    
    # =========================================================================
    # RUN - Rune Fencer
    # =========================================================================
    "Swordplay": {
        "job": "run",
        "main_only": False,
        "description": "+60 Accuracy, +60 Evasion (at 90% potency)",
    },
    "Temper": {
        "job": "run",
        "main_only": True,
        "description": "Double Attack based on Enhancing skill (minimum +5%)",
        "requires_skill": "Enhancing Skill",
    },
    
    # =========================================================================
    # BST - Beastmaster
    # =========================================================================
    "Rage": {
        "job": "bst",
        "main_only": True,
        "description": "+50% Attack for pet",
    },
    "Frenzied Rage": {
        "job": "bst",
        "main_only": True,
        "description": "+25% Attack",
    },
    
    # =========================================================================
    # DRG - Dragoon
    # =========================================================================
    # DRG abilities are mostly pet/jump related, handled implicitly in create_player
    # The wyvern bonus is auto-applied when main job is DRG
    
    # =========================================================================
    # PARTY BUFFS (commented out - may implement separately later)
    # =========================================================================
    # "Ifrit's Favor": {
    #     "job": "smn",
    #     "main_only": True,
    #     "party_buff": True,
    #     "description": "Party-wide +25% Double Attack",
    # },
    # "Garuda's Favor": {
    #     "job": "smn",
    #     "main_only": True,
    #     "party_buff": True,
    #     "description": "Party-wide +5% Magic Haste",
    # },
    # "Ramuh's Favor": {
    #     "job": "smn",
    #     "main_only": True,
    #     "party_buff": True,
    #     "description": "Party-wide +23% Crit Rate",
    # },
    # "Haste Samba": {
    #     "job": "dnc",
    #     "main_only": True,
    #     "party_buff": True,
    #     "description": "Party-wide +10% JA Haste (5% as sub)",
    # },
}


def get_abilities_for_jobs(main_job: str, sub_job: str = None, include_2hr: bool = False) -> dict:
    """
    Get abilities available for the given main job and optional sub job.
    
    Args:
        main_job: Main job (e.g., "nin", "war")
        sub_job: Sub job (e.g., "war", "sam")
        include_2hr: Whether to include 2-hour abilities
        
    Returns:
        Dict of ability_name -> ability_info for available abilities
    """
    main_job = main_job.lower()
    sub_job = sub_job.lower() if sub_job else None
    
    available = {}
    
    for name, info in PHYSICAL_ABILITIES.items():
        ability_job = info["job"]
        
        # Skip 2HR abilities if not requested
        if info.get("is_2hr") and not include_2hr:
            continue
        
        # Check if ability is available for main job
        if ability_job == main_job:
            available[name] = info
            continue
        
        # Check if ability is available for sub job (if not main_only)
        if sub_job and ability_job == sub_job and not info.get("main_only", False):
            available[name] = {**info, "from_sub": True}
            continue
    
    return available

# =============================================================================
# PHYSICAL DEBUFFS (Applied to Enemy)
# =============================================================================

PHYSICAL_DEBUFFS = {
    # -------------------------------------------------------------------------
    # DIA (WHM/RDM)
    # -------------------------------------------------------------------------
    "dia": {
        "Dia": {"defense_down_pct": 0.101, "description": "10.1% defense down"},
        "Dia II": {"defense_down_pct": 0.152, "description": "15.2% defense down"},
        "Dia III": {"defense_down_pct": 0.203, "description": "20.3% defense down"},
    },
    
    # -------------------------------------------------------------------------
    # GEO DEBUFFS
    # -------------------------------------------------------------------------
    "geo": {
        "Geo-Frailty": {"defense_down_pct": 0.10, "description": "~15% def down"},
        "Indi-Frailty": {"defense_down_pct": 0.10},
        "Geo-Torpor": {"evasion_down": 50},
        "Indi-Torpor": {"evasion_down": 30},
    },
    
    # -------------------------------------------------------------------------
    # COR DEBUFFS
    # -------------------------------------------------------------------------
    "cor": {
        "Light Shot": {"defense_down_pct": 0.027, "description": "Stacks with Dia"},
    },
    
    # -------------------------------------------------------------------------
    # MISC DEBUFFS
    # -------------------------------------------------------------------------
    "misc": {
        "Angon": {
            "defense_down_pct": 0.20,
            "job": "drg",
            "description": "20% def down, DRG ability"
        },
        "Armor Break": {
            "defense_down_pct": 0.25,
            "job": "war",
            "description": "25% def down, WAR WS"
        },
        "Box Step": {
            "defense_down_pct": 0.23,
            "job": "dnc",
            "description": "23% def down at 5 steps"
        },
        "Box Step (sub)": {
            "defense_down_pct": 0.13,
            "job": "dnc",
            "description": "13% def down as subjob"
        },
        "Corrosive Ooze": {
            "defense_down_pct": 0.05,
            "description": "5% def down, BLU spell"
        },
        "Distract III": {
            "evasion_down": 130,
            "job": "rdm",
            "description": "High evasion down"
        },
        "Distract II": {
            "evasion_down": 50,
            "job": "rdm",
        },
        "Distract": {
            "evasion_down": 35,
            "job": "rdm",
        },
        "Swooping Frenzy": {
            "defense_down_pct": 0.25,
            "magic_defense_down": 25,
            "description": "BLU spell, both def types"
        },
        "Tenebral Crush": {
            "defense_down_pct": 0.20,
            "description": "20% def down, BLU spell"
        },
    },
}


# =============================================================================
# MAGIC DEBUFFS (Applied to Enemy)
# =============================================================================

MAGIC_DEBUFFS = {
    # -------------------------------------------------------------------------
    # GEO DEBUFFS (Magic)
    # -------------------------------------------------------------------------
    "geo": {
        "Geo-Languor": {
            "magic_evasion_down": 50,
            "description": "Magic eva down @900 skill"
        },
        "Indi-Languor": {"magic_evasion_down": 50},
        "Geo-Malaise": {
            "magic_defense_down": 15,
            "description": "Magic def down @900 skill"
        },
        "Indi-Malaise": {"magic_defense_down": 15},
    },
    
    # -------------------------------------------------------------------------
    # RDM DEBUFFS
    # -------------------------------------------------------------------------
    "rdm": {
        "Frazzle III": {"magic_evasion_down": 130},
        "Frazzle II": {"magic_evasion_down": 50},
        "Frazzle": {"magic_evasion_down": 35},
    },
}


# =============================================================================
# CUSTOM BUFF CAPS (for UI validation)
# =============================================================================

CUSTOM_BUFF_CAPS = {
    # Physical
    "physical": {
        "STR": {"min": 0, "max": 200},
        "DEX": {"min": 0, "max": 200},
        "VIT": {"min": 0, "max": 200},
        "AGI": {"min": 0, "max": 200},
        "attack": {"min": 0, "max": 500},
        "attack_pct": {"min": 0, "max": 100},  # Displayed as %, stored as decimal
        "accuracy": {"min": 0, "max": 500},
        "magic_haste": {"min": 0, "max": 44},  # Cap is ~43.75%
        "store_tp": {"min": 0, "max": 100},
        "double_attack": {"min": 0, "max": 80},
        "triple_attack": {"min": 0, "max": 50},
        "crit_rate": {"min": 0, "max": 100},
        "pdl": {"min": 0, "max": 50},
    },
    # Magic
    "magic": {
        "INT": {"min": 0, "max": 200},
        "MND": {"min": 0, "max": 200},
        "magic_attack": {"min": 0, "max": 200},
        "magic_accuracy": {"min": 0, "max": 500},
        "magic_damage": {"min": 0, "max": 200},
    },
}


# =============================================================================
# TARGET PRESETS (Physical)
# =============================================================================

PHYSICAL_TARGETS = {
    "training_dummy": {
        "name": "Training Dummy",
        "level": 1,
        "defense": 100,
        "evasion": 100,
        "VIT": 50, "AGI": 50,
    },
    "apex_leech": {
        "name": "Apex Leech",
        "level": 129,
        "defense": 1142,
        "evasion": 1043,
        "VIT": 254, "AGI": 298,
    },
    "apex_toad": {
        "name": "Apex Toad",
        "level": 132,
        "defense": 1239,
        "evasion": 1133,
        "VIT": 270, "AGI": 348,
    },
    "apex_crab": {
        "name": "Apex Crab",
        "level": 135,
        "defense": 1338,
        "evasion": 1224,
        "VIT": 289, "AGI": 340,
    },
    "odyssey_normal": {
        "name": "Odyssey (Normal)",
        "level": 140,
        "defense": 1530,
        "evasion": 1383,
        "VIT": 356, "AGI": 343,
    },
    "odyssey_boss": {
        "name": "Odyssey (Boss)",
        "level": 145,
        "defense": 1704,
        "evasion": 1551,
        "VIT": 381, "AGI": 440,
    },
    "dynamis_wave3": {
        "name": "Dynamis Wave 3",
        "level": 147,
        "defense": 1791,
        "evasion": 1628,
        "VIT": 399, "AGI": 443,
    },
}


# =============================================================================
# TARGET PRESETS (Magic)
# =============================================================================

MAGIC_TARGETS = {
    "training_dummy": {
        "name": "Training Dummy",
        "level": 1,
        "int_stat": 100,
        "mnd_stat": 100,
        "magic_evasion": 300,
        "magic_defense_bonus": 0,
    },
    "apex_mob": {
        "name": "Apex Mob",
        "level": 129,
        "int_stat": 200,
        "mnd_stat": 200,
        "magic_evasion": 600,
        "magic_defense_bonus": 30,
    },
    "ambuscade_vd": {
        "name": "Ambuscade VD",
        "level": 135,
        "int_stat": 220,
        "mnd_stat": 220,
        "magic_evasion": 650,
        "magic_defense_bonus": 25,
    },
    "odyssey_nm": {
        "name": "Odyssey NM (Low)",
        "level": 140,
        "int_stat": 250,
        "mnd_stat": 250,
        "magic_evasion": 750,
        "magic_defense_bonus": 50,
    },
    "sortie_boss": {
        "name": "Sortie Boss",
        "level": 145,
        "int_stat": 280,
        "mnd_stat": 280,
        "magic_evasion": 800,
        "magic_defense_bonus": 40,
    },
    "odyssey_v15": {
        "name": "Odyssey V15",
        "level": 145,
        "int_stat": 290,
        "mnd_stat": 290,
        "magic_evasion": 1000,
        "magic_defense_bonus": 60,
    },
    "odyssey_v20": {
        "name": "Odyssey V20",
        "level": 148,
        "int_stat": 320,
        "mnd_stat": 320,
        "magic_evasion": 1100,
        "magic_defense_bonus": 70,
    },
    "odyssey_v25": {
        "name": "Odyssey V25",
        "level": 150,
        "int_stat": 350,
        "mnd_stat": 350,
        "magic_evasion": 1200,
        "magic_defense_bonus": 80,
    },
    "high_resist": {
        "name": "High Resist Target",
        "level": 150,
        "int_stat": 300,
        "mnd_stat": 300,
        "magic_evasion": 900,
        "magic_defense_bonus": 60,
    },
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_physical_buff_sources():
    """Get list of buff source categories for physical UI."""
    return ["brd", "cor", "geo", "whm", "abilities", "food"]


def get_magic_buff_sources():
    """Get list of buff source categories for magic UI."""
    return ["brd", "cor", "geo", "sch", "whm", "food"]


def get_physical_debuff_sources():
    """Get list of debuff source categories for physical UI."""
    return ["dia", "geo", "cor", "misc"]


def get_magic_debuff_sources():
    """Get list of debuff source categories for magic UI."""
    return ["geo", "rdm", "blu"]


def get_buff_by_name(buff_name: str, buff_type: str = "physical") -> dict:
    """
    Look up a buff by name across all sources.
    
    Args:
        buff_name: Name of the buff (e.g., "Minuet V")
        buff_type: "physical" or "magic"
    
    Returns:
        Dict with buff stats, or empty dict if not found
    """
    buffs = PHYSICAL_BUFFS if buff_type == "physical" else MAGIC_BUFFS
    
    for source, source_buffs in buffs.items():
        if buff_name in source_buffs:
            return source_buffs[buff_name]
    
    return {}


def get_debuff_by_name(debuff_name: str, debuff_type: str = "physical") -> dict:
    """
    Look up a debuff by name across all sources.
    
    Args:
        debuff_name: Name of the debuff (e.g., "Dia III")
        debuff_type: "physical" or "magic"
    
    Returns:
        Dict with debuff stats, or empty dict if not found
    """
    debuffs = PHYSICAL_DEBUFFS if debuff_type == "physical" else MAGIC_DEBUFFS
    
    for source, source_debuffs in debuffs.items():
        if debuff_name in source_debuffs:
            return source_debuffs[debuff_name]
    
    return {}


def get_all_physical_buffs_flat() -> dict:
    """Get all physical buffs as a flat dictionary (buff_name -> stats)."""
    result = {}
    for source, buffs in PHYSICAL_BUFFS.items():
        for name, stats in buffs.items():
            result[name] = {**stats, "_source": source}
    return result


def get_all_magic_buffs_flat() -> dict:
    """Get all magic buffs as a flat dictionary (buff_name -> stats)."""
    result = {}
    for source, buffs in MAGIC_BUFFS.items():
        for name, stats in buffs.items():
            result[name] = {**stats, "_source": source}
    return result