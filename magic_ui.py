#!/usr/bin/env python3
"""
Magic Simulation UI

A terminal-based interface for testing magic damage simulation.
Similar to optimizer_ui.py but for magic gear instead of WS/TP.

Usage:
    python magic_ui.py [inventory_csv_path]
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

# =============================================================================
# PATH SETUP
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# =============================================================================
# IMPORTS
# =============================================================================

from models import Job, Slot, Stats, SLOT_NAMES
from inventory_loader import Inventory
from magic_simulation import (
    MagicSimulator,
    CasterStats,
    MagicTargetStats,
    MagicSimulationResult,
    MAGIC_TARGETS,
)
from magic_formulas import Element, MagicType
from spell_database import (
    SpellData, get_spell, ALL_SPELLS,
    ELEMENTAL_TIER_I, ELEMENTAL_TIER_II, ELEMENTAL_TIER_III,
    ELEMENTAL_TIER_IV, ELEMENTAL_TIER_V, ELEMENTAL_TIER_VI,
    ELEMENTAL_GA_TIER_I,
    ELEMENTAL_JA,
    ANCIENT_MAGIC, ANCIENT_MAGIC_II,
    BANISH_SPELLS, HOLY_SPELLS,
    BIO_SPELLS, DRAIN_SPELLS, ASPIR_SPELLS,
    HELIX_SPELLS,
)

# Magic optimizer imports
try:
    from magic_optimizer import (
        run_magic_optimization,
        display_magic_results,
        MagicOptimizationType,
    )
    MAGIC_OPTIMIZER_AVAILABLE = True
except ImportError:
    MAGIC_OPTIMIZER_AVAILABLE = False

# =============================================================================
# JOB DEFINITIONS (for magic-capable jobs)
# =============================================================================

# Jobs that would typically use magic
MAGIC_JOBS = [
    "BLM", "RDM", "WHM", "SCH", "GEO", "SMN",
    "BLU", "DRK", "PLD", "NIN", "RUN"
]

JOB_ENUM_MAP = {
    "WAR": Job.WAR, "MNK": Job.MNK, "WHM": Job.WHM, "BLM": Job.BLM,
    "RDM": Job.RDM, "THF": Job.THF, "PLD": Job.PLD, "DRK": Job.DRK,
    "BST": Job.BST, "BRD": Job.BRD, "RNG": Job.RNG, "SMN": Job.SMN,
    "SAM": Job.SAM, "NIN": Job.NIN, "DRG": Job.DRG, "BLU": Job.BLU,
    "COR": Job.COR, "PUP": Job.PUP, "DNC": Job.DNC, "SCH": Job.SCH,
    "GEO": Job.GEO, "RUN": Job.RUN,
}

ALL_JOBS = list(JOB_ENUM_MAP.keys())

# Armor slots for magic sets (no main/sub weapons typically)
MAGIC_ARMOR_SLOTS = [
    Slot.HEAD, Slot.NECK, Slot.LEFT_EAR, Slot.RIGHT_EAR,
    Slot.BODY, Slot.HANDS, Slot.LEFT_RING, Slot.RIGHT_RING,
    Slot.BACK, Slot.WAIST, Slot.LEGS, Slot.FEET,
    Slot.MAIN, Slot.SUB, Slot.RANGE, Slot.AMMO,
]

# =============================================================================
# SPELL CATEGORIES
# =============================================================================

SPELL_CATEGORIES = {
    "Elemental Tier I": ELEMENTAL_TIER_I,
    "Elemental Tier II": ELEMENTAL_TIER_II,
    "Elemental Tier III": ELEMENTAL_TIER_III,
    "Elemental Tier IV": ELEMENTAL_TIER_IV,
    "Elemental Tier V": ELEMENTAL_TIER_V,
    "Elemental Tier VI": ELEMENTAL_TIER_VI,
    "-ga Spells": ELEMENTAL_GA_TIER_I,
    "-ja Spells": ELEMENTAL_JA,
    "Ancient Magic": ANCIENT_MAGIC,
    "Ancient Magic II": ANCIENT_MAGIC_II,
    "Helix Spells": HELIX_SPELLS,
    "Divine (Banish)": BANISH_SPELLS,
    "Divine (Holy)": HOLY_SPELLS,
    "Dark (Bio)": BIO_SPELLS,
    "Dark (Drain)": DRAIN_SPELLS,
    "Dark (Aspir)": ASPIR_SPELLS,
}


# =============================================================================
# UI HELPERS
# =============================================================================

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_menu(title: str, options: List[str], show_back: bool = True) -> int:
    """
    Display a menu and get user selection.
    
    Returns:
        Selected index (0-based), or -1 for back/quit
    """
    print_header(title)
    print()
    
    for i, option in enumerate(options, 1):
        print(f"  {i:3d}. {option}")
    
    if show_back:
        print(f"\n    0. Back / Cancel")
    
    print()
    
    while True:
        try:
            choice = input("Enter choice: ").strip()
            if choice == "0" or choice.lower() in ("q", "quit", "back", "b"):
                return -1
            
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return idx
            else:
                print(f"Please enter a number between 1 and {len(options)}")
        except ValueError:
            print("Please enter a valid number")


def print_table(headers: List[str], rows: List[List[str]], widths: List[int] = None):
    """Print a formatted table."""
    if widths is None:
        widths = [max(len(str(h)), max(len(str(row[i])) for row in rows) if rows else 0) + 2
                  for i, h in enumerate(headers)]
    
    # Header
    header_str = "  ".join(f"{h:<{w}}" for h, w in zip(headers, widths))
    print(f"  {header_str}")
    print("  " + "-" * sum(widths))
    
    # Rows
    for row in rows:
        row_str = "  ".join(f"{str(c):<{w}}" for c, w in zip(row, widths))
        print(f"  {row_str}")


# =============================================================================
# STAT SUMMATION - Convert gear set to CasterStats
# =============================================================================

def sum_gear_stats(gear_items: Dict[Slot, Any]) -> Stats:
    """
    Sum up all stats from gear items into a single Stats object.
    
    Args:
        gear_items: Dict mapping Slot -> ItemInstance
        
    Returns:
        Stats object with combined stats from all gear
    """
    total = Stats()
    
    for slot, item in gear_items.items():
        if item is None:
            continue
        
        # Get stats from the item
        if hasattr(item, 'total_stats'):
            item_stats = item.total_stats
        elif hasattr(item, 'base_stats'):
            item_stats = item.base_stats
        else:
            continue
        
        # Add all stat fields
        for field_name in vars(total).keys():
            current_val = getattr(total, field_name)
            item_val = getattr(item_stats, field_name, 0)
            if isinstance(current_val, int) and isinstance(item_val, int):
                setattr(total, field_name, current_val + item_val)
    
    return total


def stats_to_caster_stats(
    stats: Stats,
    base_int: int = 130,
    base_mnd: int = 130,
    base_elemental_skill: int = 424,  # BLM master level base
    base_dark_skill: int = 404,
    base_enfeebling_skill: int = 424,
    base_divine_skill: int = 404,
    mbb_trait: int = 1300,  # BLM trait at 99
    mbb_jp: int = 0,
    mbb_gifts: int = 0,
) -> CasterStats:
    """
    Convert a Stats object (from gear) into a CasterStats object for simulation.
    
    Args:
        stats: Summed gear stats
        base_int: Base INT from job/race/level
        base_mnd: Base MND from job/race/level
        base_elemental_skill: Base elemental magic skill from job
        base_dark_skill: Base dark magic skill from job
        base_enfeebling_skill: Base enfeebling magic skill
        base_divine_skill: Base divine magic skill
        mbb_trait: Magic Burst Bonus from job trait (basis points)
        mbb_jp: Magic Burst Bonus from job points (basis points)
        mbb_gifts: Magic Burst Bonus from gifts (basis points)
        
    Returns:
        CasterStats ready for magic simulation
    """
    return CasterStats(
        # Primary stats = base + gear
        int_stat=base_int + stats.INT,
        mnd_stat=base_mnd + stats.MND,
        
        # Magic offense from gear
        mab=stats.magic_attack,
        magic_damage=stats.magic_damage,
        magic_accuracy=stats.magic_accuracy,
        
        # Skills = base + gear bonus
        elemental_magic_skill=base_elemental_skill + stats.elemental_magic_skill,
        dark_magic_skill=base_dark_skill + stats.dark_magic_skill,
        enfeebling_magic_skill=base_enfeebling_skill + stats.enfeebling_magic_skill,
        divine_magic_skill=base_divine_skill + stats.divine_magic_skill,
        
        # Magic Burst Bonus from gear (already in basis points)
        mbb_gear=stats.magic_burst_bonus,
        mbb_ii_gear=stats.magic_burst_damage_ii,
        mbb_trait=mbb_trait,
        mbb_jp=mbb_jp,
        mbb_gifts=mbb_gifts,
        
        # Fast cast from gear
        fast_cast=stats.fast_cast,
    )


# =============================================================================
# JOB STAT PRESETS
# =============================================================================

@dataclass
class JobMagicPreset:
    """Preset base stats for a job's magic capabilities."""
    base_int: int
    base_mnd: int
    elemental_skill: int
    dark_skill: int
    enfeebling_skill: int
    divine_skill: int
    mbb_trait: int  # basis points


JOB_MAGIC_PRESETS = {
    Job.BLM: JobMagicPreset(
        base_int=165, base_mnd=120,
        elemental_skill=500, dark_skill=424, enfeebling_skill=424, divine_skill=0,
        mbb_trait=1600,  # 16% trait
    ),
    Job.RDM: JobMagicPreset(
        base_int=145, base_mnd=145,
        elemental_skill=424, dark_skill=373, enfeebling_skill=500, divine_skill=0,
        mbb_trait=0,
    ),
    Job.WHM: JobMagicPreset(
        base_int=125, base_mnd=165,
        elemental_skill=0, dark_skill=0, enfeebling_skill=404, divine_skill=500,
        mbb_trait=0,
    ),
    Job.SCH: JobMagicPreset(
        base_int=155, base_mnd=145,
        elemental_skill=449, dark_skill=404, enfeebling_skill=449, divine_skill=0,
        mbb_trait=800,  # 8% trait
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
}

# Default preset for jobs not specifically listed
DEFAULT_MAGIC_PRESET = JobMagicPreset(
    base_int=130, base_mnd=130,
    elemental_skill=354, dark_skill=354, enfeebling_skill=354, divine_skill=354,
    mbb_trait=0,
)


def get_job_preset(job: Job) -> JobMagicPreset:
    """Get the magic preset for a job."""
    return JOB_MAGIC_PRESETS.get(job, DEFAULT_MAGIC_PRESET)


# =============================================================================
# MAGIC UI CLASS
# =============================================================================

class MagicUI:
    """Terminal UI for magic simulation testing."""
    
    def __init__(self, inventory_path: str):
        self.inventory_path = inventory_path
        self.inventory: Optional[Inventory] = None
        
        # Current selections
        self.selected_job: Optional[Job] = None
        self.selected_gear: Dict[Slot, Any] = {}
        self.selected_spell: Optional[SpellData] = None
        self.selected_target: Optional[MagicTargetStats] = None
        self.selected_target_name: str = "apex_mob"
        
        # Simulation options
        self.magic_burst: bool = True
        self.num_casts: int = 1000
        self.skillchain_steps: int = 2
    
    def load_inventory(self) -> bool:
        """Load the inventory CSV."""
        try:
            self.inventory = Inventory()
            self.inventory.load_from_csv(self.inventory_path, equip_only=True)
            print(f"\n✓ Loaded {len(self.inventory.items)} equippable items")
            return True
        except FileNotFoundError:
            print(f"\n✗ Inventory file not found: {self.inventory_path}")
            return False
        except Exception as e:
            print(f"\n✗ Error loading inventory: {e}")
            return False
    
    def select_job(self) -> bool:
        """Job selection menu."""
        # Show magic-capable jobs first
        options = []
        job_list = []
        
        # Add magic jobs first
        for job_name in MAGIC_JOBS:
            if job_name in JOB_ENUM_MAP:
                options.append(f"{job_name} (Magic)")
                job_list.append(JOB_ENUM_MAP[job_name])
        
        # Add other jobs
        for job_name in ALL_JOBS:
            if job_name not in MAGIC_JOBS:
                options.append(job_name)
                job_list.append(JOB_ENUM_MAP[job_name])
        
        idx = print_menu("SELECT JOB", options)
        if idx < 0:
            return False
        
        self.selected_job = job_list[idx]
        print(f"\n✓ Selected: {self.selected_job.name}")
        
        # Clear gear when job changes
        self.selected_gear.clear()
        return True
    
    def get_slot_items(self, slot: Slot) -> List[Any]:
        """Get all items that can go in a slot for the selected job."""
        if not self.inventory or not self.selected_job:
            return []
        
        from models import SLOT_BITMASK
        slot_mask = SLOT_BITMASK.get(slot, 0)
        
        items = []
        for item in self.inventory.items:
            # Check if item can go in this slot
            if not (item.base.slots & slot_mask):
                continue
            
            # Check if job can equip
            if not item.base.can_equip(self.selected_job):
                continue
            
            items.append(item)
        
        return items
    
    def select_gear_slot(self, slot: Slot) -> bool:
        """Select gear for a specific slot."""
        items = self.get_slot_items(slot)
        
        if not items:
            print(f"\n✗ No items available for {SLOT_NAMES[slot]}")
            return False
        
        # Sort by magic stats (MAB, INT, MBB)
        def magic_score(item):
            stats = item.total_stats if hasattr(item, 'total_stats') else item.base_stats
            return (
                stats.magic_attack * 10 +
                stats.INT * 5 +
                stats.magic_burst_bonus +
                stats.magic_accuracy +
                stats.magic_damage * 10
            )
        
        items.sort(key=magic_score, reverse=True)
        
        # Build options
        options = []
        for item in items[:30]:  # Limit to top 30
            stats = item.total_stats if hasattr(item, 'total_stats') else item.base_stats
            stat_str = []
            if stats.magic_attack:
                stat_str.append(f"MAB+{stats.magic_attack}")
            if stats.INT:
                stat_str.append(f"INT+{stats.INT}")
            if stats.magic_burst_bonus:
                stat_str.append(f"MBB+{stats.magic_burst_bonus//100}%")
            if stats.magic_accuracy:
                stat_str.append(f"MAcc+{stats.magic_accuracy}")
            if stats.magic_damage:
                stat_str.append(f"MD+{stats.magic_damage}")
            
            stat_display = ", ".join(stat_str) if stat_str else "No magic stats"
            options.append(f"{item.name} ({stat_display})")
        
        # Add "None" option
        options.append("(Clear slot)")
        
        idx = print_menu(f"SELECT {SLOT_NAMES[slot].upper()}", options)
        if idx < 0:
            return False
        
        if idx == len(options) - 1:
            # Clear slot
            self.selected_gear.pop(slot, None)
            print(f"\n✓ Cleared {SLOT_NAMES[slot]}")
        else:
            self.selected_gear[slot] = items[idx]
            print(f"\n✓ Selected: {items[idx].name}")
        
        return True
    
    def select_all_gear(self):
        """Menu to select gear for all slots."""
        while True:
            options = []
            for slot in MAGIC_ARMOR_SLOTS:
                current = self.selected_gear.get(slot)
                if current:
                    options.append(f"{SLOT_NAMES[slot]}: {current.name}")
                else:
                    options.append(f"{SLOT_NAMES[slot]}: (empty)")
            
            options.append("--- Auto-Fill Best Magic Gear ---")
            options.append("--- Clear All ---")
            
            idx = print_menu("SELECT GEAR SLOT", options)
            if idx < 0:
                return
            
            if idx == len(MAGIC_ARMOR_SLOTS):
                # Auto-fill
                self.auto_fill_magic_gear()
            elif idx == len(MAGIC_ARMOR_SLOTS) + 1:
                # Clear all
                self.selected_gear.clear()
                print("\n✓ Cleared all gear")
            else:
                # Select specific slot
                slot = MAGIC_ARMOR_SLOTS[idx]
                self.select_gear_slot(slot)
    
    def auto_fill_magic_gear(self):
        """Auto-fill all slots with best magic gear."""
        if not self.selected_job:
            print("\n✗ Please select a job first")
            return
        
        print("\n  Auto-filling with best magic gear...")
        
        for slot in MAGIC_ARMOR_SLOTS:
            items = self.get_slot_items(slot)
            if not items:
                continue
            
            # Score by magic stats
            def magic_score(item):
                stats = item.total_stats if hasattr(item, 'total_stats') else item.base_stats
                return (
                    stats.magic_attack * 10 +
                    stats.INT * 5 +
                    stats.magic_burst_bonus +
                    stats.magic_accuracy +
                    stats.magic_damage * 10
                )
            
            items.sort(key=magic_score, reverse=True)
            
            # Handle rings (don't duplicate)
            if slot in (Slot.LEFT_RING, Slot.RIGHT_RING):
                other_slot = Slot.RIGHT_RING if slot == Slot.LEFT_RING else Slot.LEFT_RING
                other_item = self.selected_gear.get(other_slot)
                if other_item:
                    # Skip duplicates
                    for item in items:
                        if item.name != other_item.name:
                            self.selected_gear[slot] = item
                            break
                else:
                    self.selected_gear[slot] = items[0]
            # Handle ears (don't duplicate)
            elif slot in (Slot.LEFT_EAR, Slot.RIGHT_EAR):
                other_slot = Slot.RIGHT_EAR if slot == Slot.LEFT_EAR else Slot.LEFT_EAR
                other_item = self.selected_gear.get(other_slot)
                if other_item:
                    for item in items:
                        if item.name != other_item.name:
                            self.selected_gear[slot] = item
                            break
                else:
                    self.selected_gear[slot] = items[0]
            else:
                self.selected_gear[slot] = items[0]
        
        print("  ✓ Auto-fill complete")
    
    def select_spell(self) -> bool:
        """Spell selection menu."""
        # First select category
        categories = list(SPELL_CATEGORIES.keys())
        idx = print_menu("SELECT SPELL CATEGORY", categories)
        if idx < 0:
            return False
        
        category_name = categories[idx]
        spells = SPELL_CATEGORIES[category_name]
        
        # Build spell options
        spell_list = list(spells.values())
        options = []
        for spell in spell_list:
            element_str = spell.element.name if hasattr(spell, 'element') else "?"
            tier_str = f"T{spell.tier}" if hasattr(spell, 'tier') else ""
            options.append(f"{spell.name} ({element_str} {tier_str})")
        
        idx = print_menu(f"SELECT SPELL - {category_name}", options)
        if idx < 0:
            return False
        
        self.selected_spell = spell_list[idx]
        print(f"\n✓ Selected: {self.selected_spell.name}")
        return True
    
    def select_target(self) -> bool:
        """Target selection menu."""
        target_names = list(MAGIC_TARGETS.keys())
        options = []
        
        for name in target_names:
            target = MAGIC_TARGETS[name]
            options.append(f"{name} (INT:{target.int_stat} MEva:{target.magic_evasion} MDB:{target.magic_defense_bonus})")
        
        idx = print_menu("SELECT TARGET", options)
        if idx < 0:
            return False
        
        self.selected_target_name = target_names[idx]
        self.selected_target = MAGIC_TARGETS[self.selected_target_name]
        print(f"\n✓ Selected: {self.selected_target_name}")
        return True
    
    def toggle_magic_burst(self):
        """Toggle magic burst mode."""
        self.magic_burst = not self.magic_burst
        print(f"\n✓ Magic Burst: {'ON' if self.magic_burst else 'OFF'}")
    
    def show_current_selection(self):
        """Display current selections."""
        print("\n--- Current Selection ---")
        
        # Job
        job_str = self.selected_job.name if self.selected_job else '(not selected)'
        print(f"  Job:    {job_str}")
        
        # Gear count
        gear_count = len(self.selected_gear)
        print(f"  Gear:   {gear_count} pieces equipped")
        
        # Spell
        spell_str = self.selected_spell.name if self.selected_spell else '(not selected)'
        print(f"  Spell:  {spell_str}")
        
        # Target
        target_str = self.selected_target_name if self.selected_target else '(not selected)'
        print(f"  Target: {target_str}")
        
        # Options
        print(f"  Mode:   {'Magic Burst' if self.magic_burst else 'Free Nuke'}")
    
    def show_gear_summary(self):
        """Display current gear and total stats."""
        print_header("GEAR SUMMARY")
        
        if not self.selected_gear:
            print("\n  No gear equipped")
            return
        
        # Show equipped gear
        print("\n  Equipped:")
        for slot in MAGIC_ARMOR_SLOTS:
            item = self.selected_gear.get(slot)
            if item:
                print(f"    {SLOT_NAMES[slot]:12s}: {item.name}")
        
        # Calculate totals
        total_stats = sum_gear_stats(self.selected_gear)
        
        print("\n  Total Gear Stats:")
        print(f"    INT: +{total_stats.INT}")
        print(f"    MND: +{total_stats.MND}")
        print(f"    MAB: +{total_stats.magic_attack}")
        print(f"    Magic Damage: +{total_stats.magic_damage}")
        print(f"    Magic Accuracy: +{total_stats.magic_accuracy}")
        print(f"    Magic Burst Bonus: +{total_stats.magic_burst_bonus//100}%")
        print(f"    MBB II: +{total_stats.magic_burst_damage_ii//100}%")
        print(f"    Elemental Skill: +{total_stats.elemental_magic_skill}")
    
    def run_simulation(self):
        """Run the magic simulation with current selections."""
        if not self.selected_job:
            print("\n✗ Please select a job first")
            input("Press Enter to continue...")
            return
        
        if not self.selected_spell:
            print("\n✗ Please select a spell first")
            input("Press Enter to continue...")
            return
        
        if not self.selected_target:
            self.selected_target = MAGIC_TARGETS['apex_mob']
            self.selected_target_name = 'apex_mob'
        
        print_header("RUNNING MAGIC SIMULATION")
        
        # Get job preset
        preset = get_job_preset(self.selected_job)
        
        # Sum gear stats
        gear_stats = sum_gear_stats(self.selected_gear)
        
        # Convert to CasterStats
        caster = stats_to_caster_stats(
            stats=gear_stats,
            base_int=preset.base_int,
            base_mnd=preset.base_mnd,
            base_elemental_skill=preset.elemental_skill,
            base_dark_skill=preset.dark_skill,
            base_enfeebling_skill=preset.enfeebling_skill,
            base_divine_skill=preset.divine_skill,
            mbb_trait=preset.mbb_trait,
        )
        
        # Show stats
        print(f"\n  Job: {self.selected_job.name}")
        print(f"  Spell: {self.selected_spell.name} ({self.selected_spell.element.name})")
        print(f"  Target: {self.selected_target_name}")
        print(f"  Magic Burst: {'Yes' if self.magic_burst else 'No'}")
        
        print(f"\n  Caster Stats:")
        print(f"    Total INT: {caster.int_stat}")
        print(f"    Total MND: {caster.mnd_stat}")
        print(f"    MAB: {caster.mab}")
        print(f"    Magic Damage: {caster.magic_damage}")
        print(f"    Magic Accuracy: {caster.magic_accuracy}")
        print(f"    Elemental Skill: {caster.elemental_magic_skill}")
        print(f"    MBB Gear: {caster.mbb_gear//100}%")
        print(f"    MBB Trait: {caster.mbb_trait//100}%")
        
        # Run simulation
        print(f"\n  Running {self.num_casts} simulations...")
        
        sim = MagicSimulator(seed=42)
        result = sim.simulate_spell(
            spell_name=self.selected_spell.name,
            caster=caster,
            target=self.selected_target,
            magic_burst=self.magic_burst,
            skillchain_steps=self.skillchain_steps,
            num_casts=self.num_casts,
        )
        
        # Display results
        print_header("SIMULATION RESULTS")
        
        print(f"\n  Damage Statistics:")
        print(f"    Average:  {result.average_damage:,.0f}")
        print(f"    Min:      {result.min_damage:,}")
        print(f"    Max:      {result.max_damage:,}")
        
        print(f"\n  Resist Rates:")
        print(f"    Unresisted: {result.unresisted_rate*100:.1f}%")
        print(f"    1/2 Resist: {result.half_resist_rate*100:.1f}%")
        print(f"    1/4 Resist: {result.quarter_resist_rate*100:.1f}%")
        print(f"    1/8 Resist: {result.eighth_resist_rate*100:.1f}%")
        
        # Calculate expected damage
        expected = (
            result.average_damage * result.unresisted_rate +
            result.average_damage * 0.5 * result.half_resist_rate +
            result.average_damage * 0.25 * result.quarter_resist_rate +
            result.average_damage * 0.125 * result.eighth_resist_rate
        )
        print(f"\n  Expected Damage (with resists): {expected:,.0f}")
        
        input("\n  Press Enter to continue...")
    
    def compare_mb_vs_free(self):
        """Compare Magic Burst vs Free Nuke damage."""
        if not self.selected_job or not self.selected_spell:
            print("\n✗ Please select job and spell first")
            input("Press Enter to continue...")
            return
        
        if not self.selected_target:
            self.selected_target = MAGIC_TARGETS['apex_mob']
            self.selected_target_name = 'apex_mob'
        
        print_header("COMPARING MB vs FREE NUKE")
        
        # Get job preset and caster stats
        preset = get_job_preset(self.selected_job)
        gear_stats = sum_gear_stats(self.selected_gear)
        caster = stats_to_caster_stats(
            stats=gear_stats,
            base_int=preset.base_int,
            base_mnd=preset.base_mnd,
            base_elemental_skill=preset.elemental_skill,
            base_dark_skill=preset.dark_skill,
            base_enfeebling_skill=preset.enfeebling_skill,
            base_divine_skill=preset.divine_skill,
            mbb_trait=preset.mbb_trait,
        )
        
        sim = MagicSimulator(seed=42)
        
        # Free nuke
        free_result = sim.simulate_spell(
            spell_name=self.selected_spell.name,
            caster=caster,
            target=self.selected_target,
            magic_burst=False,
            num_casts=self.num_casts,
        )
        
        # Magic burst
        mb_result = sim.simulate_spell(
            spell_name=self.selected_spell.name,
            caster=caster,
            target=self.selected_target,
            magic_burst=True,
            skillchain_steps=2,
            num_casts=self.num_casts,
        )
        
        print(f"\n  Spell: {self.selected_spell.name}")
        print(f"  Target: {self.selected_target_name}")
        
        print(f"\n  Free Nuke:")
        print(f"    Average Damage: {free_result.average_damage:,.0f}")
        print(f"    Unresisted Rate: {free_result.unresisted_rate*100:.1f}%")
        
        print(f"\n  Magic Burst (2-step):")
        print(f"    Average Damage: {mb_result.average_damage:,.0f}")
        print(f"    Unresisted Rate: {mb_result.unresisted_rate*100:.1f}%")
        
        # Damage increase
        if free_result.average_damage > 0:
            increase = ((mb_result.average_damage / free_result.average_damage) - 1) * 100
            print(f"\n  MB Damage Increase: +{increase:.1f}%")
        
        input("\n  Press Enter to continue...")
    
    def run_magic_optimization(self):
        """Run beam search optimization to find best magic gear set."""
        if not self.selected_job:
            print("\n✗ Please select a job first")
            input("Press Enter to continue...")
            return
        
        if not self.selected_spell:
            print("\n✗ Please select a spell first")
            input("Press Enter to continue...")
            return
        
        if not self.selected_target:
            self.selected_target = MAGIC_TARGETS['apex_mob']
            self.selected_target_name = 'apex_mob'
        
        # Select optimization type
        opt_options = [
            "Damage - Maximize magic damage output",
            "Accuracy - Maximize spell hit rate",
            "Burst Damage - Maximize magic burst damage (prioritizes MBB)",
        ]
        
        idx = print_menu("SELECT OPTIMIZATION TYPE", opt_options)
        if idx < 0:
            return
        
        opt_types = [
            MagicOptimizationType.DAMAGE,
            MagicOptimizationType.ACCURACY,
            MagicOptimizationType.BURST_DAMAGE,
        ]
        opt_type = opt_types[idx]
        
        # Ask about weapon slots
        weapon_options = [
            "Exclude weapons (keep current weapons equipped)",
            "Include weapons (optimize all slots)",
        ]
        
        weapon_idx = print_menu("WEAPON SLOT HANDLING", weapon_options)
        if weapon_idx < 0:
            return
        
        include_weapons = (weapon_idx == 1)
        
        # Run optimization
        print_header("RUNNING MAGIC OPTIMIZATION")
        print(f"\n  Job: {self.selected_job.name}")
        print(f"  Spell: {self.selected_spell.name}")
        print(f"  Target: {self.selected_target_name}")
        print(f"  Type: {opt_type.value}")
        print(f"  Magic Burst: {'Yes' if self.magic_burst else 'No'}")
        print(f"  Include Weapons: {'Yes' if include_weapons else 'No'}")
        
        try:
            results = run_magic_optimization(
                inventory=self.inventory,
                job=self.selected_job,
                spell_name=self.selected_spell.name,
                optimization_type=opt_type,
                target=self.selected_target,
                magic_burst=self.magic_burst,
                skillchain_steps=self.skillchain_steps,
                include_weapons=include_weapons,
                beam_width=25,
                num_sim_casts=100,
            )
            
            # Display results
            display_magic_results(results, self.selected_spell.name, opt_type)
            
            # Offer to apply top result
            if results:
                print("\n" + "-"*70)
                apply = input("Apply top gear set to current selection? (y/n): ").strip().lower()
                if apply == 'y':
                    self._apply_optimized_gear(results[0][0])
                    print("\n✓ Gear set applied!")
            
        except Exception as e:
            print(f"\n✗ Optimization failed: {e}")
            import traceback
            traceback.print_exc()
        
        input("\nPress Enter to continue...")
    
    def _apply_optimized_gear(self, candidate):
        """Apply an optimized gear set candidate to current selection."""
        from beam_search_optimizer import WSDIST_TO_SLOT
        
        # Clear current gear
        self.selected_gear.clear()
        
        # Map wsdist slots back to our Slot enum and find matching items
        for wsdist_slot, gear_dict in candidate.gear.items():
            if gear_dict.get('Name', 'Empty') == 'Empty':
                continue
            
            slot_enum = WSDIST_TO_SLOT.get(wsdist_slot)
            if slot_enum is None:
                continue
            
            # Find the item in inventory by name
            gear_name = gear_dict.get('Name2', gear_dict.get('Name'))
            
            # Search for matching item
            for item in self.inventory.items:
                if item.name == gear_name or item.base.name == gear_name:
                    if item.base.can_equip(self.selected_job):
                        self.selected_gear[slot_enum] = item
                        break
    
    def main_menu(self):
        """Main menu loop."""
        while True:
            self.show_current_selection()
            
            options = [
                "Select Job",
                "Select Gear",
                "Select Spell",
                "Select Target",
                f"Toggle Magic Burst (Currently: {'ON' if self.magic_burst else 'OFF'})",
                "View Gear Summary",
                "Run Simulation",
                "Compare MB vs Free Nuke",
                "--- Optimize Magic Set ---" if MAGIC_OPTIMIZER_AVAILABLE else "(Optimizer not available)",
                "Quit"
            ]
            
            idx = print_menu("MAGIC SIMULATION", options, show_back=False)
            
            if idx == 0:  # Select Job
                if self.select_job():
                    self.selected_gear.clear()
            
            elif idx == 1:  # Select Gear
                if not self.selected_job:
                    print("\n⚠ Please select a job first")
                    input("Press Enter to continue...")
                else:
                    self.select_all_gear()
            
            elif idx == 2:  # Select Spell
                self.select_spell()
            
            elif idx == 3:  # Select Target
                self.select_target()
            
            elif idx == 4:  # Toggle MB
                self.toggle_magic_burst()
            
            elif idx == 5:  # View Gear Summary
                self.show_gear_summary()
                input("\nPress Enter to continue...")
            
            elif idx == 6:  # Run Simulation
                self.run_simulation()
            
            elif idx == 7:  # Compare MB vs Free
                self.compare_mb_vs_free()
            
            elif idx == 8:  # Optimize Magic Set
                if MAGIC_OPTIMIZER_AVAILABLE:
                    self.run_magic_optimization()
                else:
                    print("\n✗ Magic optimizer module not available")
                    input("Press Enter to continue...")
            
            elif idx == 9 or idx == -1:  # Quit
                print("\nGoodbye!")
                break
    
    def run(self):
        """Main entry point."""
        print_header("MAGIC SIMULATION UI")
        print(f"\n  Inventory: {self.inventory_path}")
        
        if not self.load_inventory():
            return
        
        self.main_menu()


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    # Default inventory path
    default_path = "inventory_full_Masinmanci_20260111_124357.csv"
    
    if len(sys.argv) > 1:
        inventory_path = sys.argv[1]
    else:
        inventory_path = default_path
    
    ui = MagicUI(inventory_path)
    ui.run()


if __name__ == "__main__":
    main()
