#!/usr/bin/env python3
"""
Job Gifts Loader

Loads job gift/job point bonuses from CSV export and converts them
to wsdist-compatible stat formats.

The CSV is exported from the FFXI Point Tracker addon or similar tools.
"""

import csv
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass, field


# =============================================================================
# STAT NAME MAPPING
# =============================================================================

# Map CSV column names to wsdist stat names
# Some stats need to be converted from basis points (100 = 1%) to percentages
CSV_TO_WSDIST_STATS = {
    # Flat stats (no conversion needed)
    'accuracy': ('Accuracy', 1),
    'ranged_accuracy': ('Ranged Accuracy', 1),
    'attack': ('Attack', 1),
    'ranged_attack': ('Ranged Attack', 1),
    'defense': ('Defense', 1),
    'evasion': ('Evasion', 1),
    'magic_accuracy': ('Magic Accuracy', 1),
    'magic_attack': ('Magic Attack', 1),
    'magic_defense': ('Magic Defense', 1),
    'magic_evasion': ('Magic Evasion', 1),
    'magic_damage': ('Magic Damage', 1),
    'fencer_tp_bonus': ('Fencer TP Bonus', 1),
    'store_tp': ('Store TP', 1),
    'enspell_damage': ('EnSpell Damage', 1),
    'martial_arts': ('Martial Arts', 1),
    
    # Skill stats (flat)
    'blue_magic_skill': ('Blue Magic Skill', 1),
    'dark_magic_skill': ('Dark Magic Skill', 1),
    'divine_magic_skill': ('Divine Magic Skill', 1),
    'elemental_magic_skill': ('Elemental Magic Skill', 1),
    'enfeebling_magic_skill': ('Enfeebling Magic Skill', 1),
    'enhancing_magic_skill': ('Enhancing Magic Skill', 1),
    'geomancy_skill': ('Geomancy Skill', 1),
    'guarding_skill': ('Guarding Skill', 1),
    'handbell_skill': ('Handbell Skill', 1),
    'healing_magic_skill': ('Healing Magic Skill', 1),
    'ninjutsu_skill': ('Ninjutsu Skill', 1),
    'singing_skill': ('Singing Skill', 1),
    'string_instrument_skill': ('String Instrument Skill', 1),
    'summoning_magic_skill': ('Summoning Magic Skill', 1),
    'wind_instrument_skill': ('Wind Instrument Skill', 1),
    
    # Percentage stats (basis points -> percentage, divide by 100)
    'crit_damage': ('Crit Damage', 0.01),          # 1000 -> 10%
    'crit_rate': ('Crit Rate', 0.01),              # 1000 -> 10%
    'double_attack': ('DA', 0.01),                  # 1000 -> 10%
    'triple_attack': ('TA', 0.01),                  # 1000 -> 10%
    'dual_wield': ('Dual Wield', 0.01),             # 500 -> 5%
    'daken': ('Daken', 0.01),                       # 1400 -> 14%
    'ws_damage': ('Weapon Skill Damage', 0.01),     # 300 -> 3%, 500 -> 5%, 800 -> 8%
    'zanshin': ('Zanshin', 0.01),                   # 200 -> 2%
    'skillchain_bonus': ('Skillchain Bonus', 0.01), # 800 -> 8%
    'magic_burst_bonus': ('Magic Burst Damage Trait', 0.01),
    'fast_cast': ('Fast Cast', 0.01),
    'snapshot': ('Snapshot', 0.01),
    'true_shot': ('True Shot', 0.01),
    'velocity_shot': ('Velocity Shot', 0.01),
    'ranged_crit_damage': ('Ranged Crit Damage', 0.01),
    'counter': ('Counter', 0.01),
    'counter_damage': ('Counter Damage', 0.01),
    'subtle_blow': ('Subtle Blow', 0.01),
    'conserve_tp': ('Conserve TP', 0.01),
    'cure_potency': ('Cure Potency', 0.01),
    'regen': ('Regen', 0.01),
    'inquartata': ('Inquartata', 0.01),
    
    # Duration/time stats (basis points -> percentage)
    'ninjutsu_duration': ('Ninjutsu Duration', 0.01),
    'song_duration': ('Song Duration', 0.01),
    'elemental_celerity': ('Elemental Celerity', 0.01),
    'healing_cast_time': ('Healing Cast Time', 0.01),
    'song_cast_time': ('Song Cast Time', 0.01),
    
    # Special stats
    'barrage_shots': ('Barrage', 1),  # Extra shots
    'shield_mastery_tp': ('Shield Mastery TP', 1),
    'pet_accuracy': ('Pet Accuracy', 1),
    'pet_magic_accuracy': ('Pet Magic Accuracy', 1),
}

# wsdist's hardcoded job mastery stats for comparison/reference
# We can use this to calculate deltas or validate the CSV
WSDIST_DEFAULT_JOB_MASTERY = {
    "war": {"Accuracy": 26, "Ranged Accuracy": 26, "Attack": 70, "Ranged Attack": 70, 
            "Magic Accuracy": 36, "Fencer TP Bonus": 230, "Crit Rate": 10, "Crit Damage": 10,
            "DA": 10, "Evasion": 36, "Magic Evasion": 36, "Weapon Skill Damage": 3},
    "mnk": {"Accuracy": 41, "Ranged Accuracy": 41, "Attack": 40, "Ranged Attack": 40, 
            "Magic Accuracy": 36, "Evasion": 42, "Magic Evasion": 36, "Subtle Blow": 10,
            "Martial Arts": 10, "Kick Attacks Attack": 40, "Kick Attacks Accuracy": 20},
    "whm": {"Accuracy": 14, "Ranged Accuracy": 14, "Magic Accuracy": 70, "Magic Attack": 22,
            "Magic Defense": 50, "Divine Magic Skill": 36},
    "blm": {"Magic Burst Damage Trait": 43, "Magic Accuracy": 52, "Magic Damage": 43, 
            "Magic Defense": 14, "Magic Attack": 50, "Magic Evasion": 42,
            "Elemental Magic Skill": 36, "Dark Magic Skill": 36},
    "rdm": {"Magic Attack": 48, "Magic Accuracy": 90, "Magic Defense": 28, "Magic Evasion": 56,
            "Accuracy": 22, "Ranged Accuracy": 22, "EnSpell Damage": 23},
    "thf": {"Sneak Attack Bonus": 20, "Trick Attack Bonus": 20, "Attack": 50, "Ranged Attack": 50,
            "Evasion": 70, "Accuracy": 36, "Ranged Accuracy": 36, "Magic Evasion": 36,
            "Magic Accuracy": 36, "TA": 8, "Crit Damage": 8, "Dual Wield": 5, "TA Attack": 20},
    "pld": {"Accuracy": 28, "Ranged Accuracy": 28, "Attack": 28, "Ranged Attack": 28,
            "Evasion": 22, "Magic Evasion": 42, "Divine Magic Skill": 36, "Magic Accuracy": 42},
    "drk": {"Attack": 106, "Ranged Attack": 106, "Evasion": 22, "Magic Evasion": 36,
            "Accuracy": 22, "Ranged Accuracy": 22, "Magic Accuracy": 42, "Dark Magic Skill": 36,
            "Crit Damage": 8, "Weapon Skill Damage": 8},
    "bst": {"Attack": 70, "Ranged Attack": 70, "Accuracy": 36, "Ranged Accuracy": 36,
            "Magic Evasion": 36, "Magic Accuracy": 36, "Fencer TP Bonus": 230, "Evasion": 36},
    "brd": {"Evasion": 22, "Accuracy": 21, "Ranged Accuracy": 21, "Magic Defense": 15,
            "Magic Evasion": 36, "Magic Accuracy": 36},
    "rng": {"Double Shot": 20, "Attack": 70, "Ranged Attack": 70, "Evasion": 14,
            "Accuracy": 70, "Ranged Accuracy": 70, "Magic Evasion": 36, "Conserve TP": 15,
            "True Shot": 8, "Ranged Crit Damage": 8, "Barrage": 1, "Barrage Ranged Attack": 60},
    "smn": {"Magic Defense": 22, "Magic Evasion": 22, "Evasion": 22, "Summoning Magic Skill": 36},
    "sam": {"Attack": 70, "Ranged Attack": 70, "Evasion": 36, "Accuracy": 36,
            "Ranged Accuracy": 36, "Magic Evasion": 36, "Zanshin": 10, "Zanshin Attack": 40,
            "Store TP": 8, "Skillchain Bonus": 8},
    "nin": {"Ninjutsu Magic Damage": 40, "Ninjutsu Magic Accuracy": 20, "Attack": 70,
            "Ranged Attack": 70, "Evasion": 64, "Accuracy": 56, "Ranged Accuracy": 56,
            "Magic Attack": 28, "Magic Evasion": 50, "Magic Accuracy": 50, "Ninjutsu Skill": 36,
            "Daken": 14, "Weapon Skill Damage": 5},
    "drg": {"Attack": 70, "Ranged Attack": 70, "Evasion": 36, "Accuracy": 64,
            "Ranged Accuracy": 64, "Magic Evasion": 36, "Crit Damage": 8},
    "blu": {"Attack": 70, "Ranged Attack": 70, "Evasion": 36, "Accuracy": 36,
            "Ranged Accuracy": 36, "Magic Defense": 36, "Magic Attack": 36, 
            "Magic Evasion": 36, "Blue Magic Skill": 36},
    "cor": {"Triple Shot": 20, "True Shot": 6, "Ranged Accuracy": 56, "Attack": 36,
            "Ranged Attack": 36, "Accuracy": 36, "Evasion": 22, "Magic Attack": 14,
            "Magic Evasion": 36, "Magic Accuracy": 36, "Quick Draw Damage": 40},
    "pup": {"Martial Arts": 40, "Attack": 42, "Ranged Attack": 42, "Evasion": 56,
            "Accuracy": 50, "Ranged Accuracy": 50, "Magic Evasion": 36, "Magic Accuracy": 36},
    "dnc": {"Flourish CHR%": 20, "Building Flourish WSD": 20, "Attack": 42, "Ranged Attack": 42,
            "Evasion": 64, "Accuracy": 64, "Ranged Accuracy": 64, "Magic Evasion": 36,
            "Magic Accuracy": 36, "Subtle Blow": 13, "Crit Damage": 8, "Skillchain Bonus": 8,
            "Dual Wield": 5},
    "sch": {"Magic Defense": 22, "Magic Attack": 36, "Magic Evasion": 42, "Magic Accuracy": 42,
            "Dark Magic Skill": 36, "Elemental Magic Skill": 36, "Magic Burst Damage Trait": 13},
    "geo": {"Magic Accuracy": 70, "Magic Attack": 62, "Magic Defense": 28, "Magic Evasion": 50,
            "Elemental Magic Skill": 36, "Dark Magic Skill": 36, "Magic Damage": 13},
    "run": {"Lunge Bonus": 20, "Attack": 50, "Ranged Attack": 50, "Evasion": 56,
            "Accuracy": 56, "Ranged Accuracy": 56, "Magic Defense": 56, "Magic Evasion": 70,
            "Magic Accuracy": 36},
}


# =============================================================================
# JOB GIFTS DATA CLASS
# =============================================================================

@dataclass
class JobGifts:
    """Job gifts/job points for a single job."""
    job: str
    jp_spent: int = 0
    stats: Dict[str, float] = field(default_factory=dict)
    
    def get_wsdist_stats(self) -> Dict[str, float]:
        """
        Get stats in wsdist format.
        
        Returns dict with wsdist stat names and values ready to apply.
        """
        return self.stats.copy()
    
    def get_stat(self, stat_name: str, default: float = 0) -> float:
        """Get a specific stat value."""
        return self.stats.get(stat_name, default)


@dataclass 
class JobGiftsCollection:
    """Collection of job gifts for all jobs."""
    gifts: Dict[str, JobGifts] = field(default_factory=dict)
    
    def get_job(self, job: str) -> Optional[JobGifts]:
        """Get job gifts for a specific job."""
        return self.gifts.get(job.upper())
    
    def get_wsdist_stats(self, job: str) -> Dict[str, float]:
        """Get wsdist-format stats for a job."""
        job_gifts = self.get_job(job)
        if job_gifts:
            return job_gifts.get_wsdist_stats()
        return {}


# =============================================================================
# LOADER FUNCTION
# =============================================================================

def load_job_gifts(csv_path: str) -> JobGiftsCollection:
    """
    Load job gifts from CSV file.
    
    Args:
        csv_path: Path to the job gifts CSV file
        
    Returns:
        JobGiftsCollection with all job gifts loaded
    """
    collection = JobGiftsCollection()
    
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Job gifts file not found: {csv_path}")
    
    with open(path, 'r', newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            job = row.get('job', '').upper().strip()
            if not job:
                continue
            
            # Parse JP spent
            jp_spent = int(row.get('jp_spent', 0) or 0)
            
            # Convert stats
            stats = {}
            for csv_col, (wsdist_name, multiplier) in CSV_TO_WSDIST_STATS.items():
                value_str = row.get(csv_col, '0')
                try:
                    value = float(value_str) if value_str else 0
                except ValueError:
                    value = 0
                
                if value != 0:
                    # Apply multiplier (converts basis points to percentage)
                    converted_value = value * multiplier
                    stats[wsdist_name] = converted_value
            
            # Create job gifts object
            job_gifts = JobGifts(
                job=job,
                jp_spent=jp_spent,
                stats=stats,
            )
            
            collection.gifts[job] = job_gifts
    
    return collection


def apply_job_gifts_to_player(player, job_gifts: JobGifts):
    """
    Apply job gifts to a wsdist player object.
    
    This modifies the player's stats dict to use the actual job gifts
    instead of wsdist's hardcoded defaults.
    
    Args:
        player: wsdist player object (from create_player)
        job_gifts: JobGifts object with the player's actual gifts
    """
    job = player.main_job.lower()
    
    # Get the default stats wsdist would have applied
    default_stats = WSDIST_DEFAULT_JOB_MASTERY.get(job, {})
    
    # Get the actual stats from job gifts
    actual_stats = job_gifts.get_wsdist_stats()
    
    # Calculate and apply the delta for each stat
    for stat_name, actual_value in actual_stats.items():
        default_value = default_stats.get(stat_name, 0)
        delta = actual_value - default_value
        
        if delta != 0:
            current = player.stats.get(stat_name, 0)
            player.stats[stat_name] = current + delta
    
    # Also subtract default stats that aren't in actual (player doesn't have those gifts)
    for stat_name, default_value in default_stats.items():
        if stat_name not in actual_stats:
            current = player.stats.get(stat_name, 0)
            player.stats[stat_name] = current - default_value


def get_job_gifts_summary(job_gifts: JobGifts) -> str:
    """Get a human-readable summary of job gifts."""
    lines = [f"{job_gifts.job} (JP Spent: {job_gifts.jp_spent})"]
    
    for stat_name, value in sorted(job_gifts.stats.items()):
        if value != 0:
            # Format percentage stats nicely
            if stat_name in ('DA', 'TA', 'Crit Rate', 'Crit Damage', 'Dual Wield', 
                            'Weapon Skill Damage', 'Daken', 'Zanshin', 'Skillchain Bonus'):
                lines.append(f"  {stat_name}: {value:.0f}%")
            else:
                lines.append(f"  {stat_name}: {value:.0f}")
    
    return '\n'.join(lines)


# =============================================================================
# MAIN (for testing)
# =============================================================================

if __name__ == "__main__":
    import sys
    
    # Default path
    csv_path = ""
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    
    print(f"Loading job gifts from: {csv_path}")
    print()
    
    try:
        collection = load_job_gifts(csv_path)
        
        print(f"Loaded gifts for {len(collection.gifts)} jobs")
        print()
        
        # Show jobs with JP spent
        for job_name, job_gifts in sorted(collection.gifts.items()):
            if job_gifts.jp_spent > 0:
                print(get_job_gifts_summary(job_gifts))
                print()
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
