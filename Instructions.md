# FFXI Gear Optimizer

A web-based gear optimization tool for Final Fantasy XI that helps players build optimal equipment sets for various scenarios including TP gain, weapon skills, magic, and damage mitigation.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Uploading Your Data](#uploading-your-data)
  - [Inventory CSV](#inventory-csv)
  - [Job Points CSV](#job-points-csv)
- [Character Configuration](#character-configuration)
- [Optimization Tabs](#optimization-tabs)
  - [TP Set](#tp-set)
  - [WS Set](#ws-set)
  - [Magic](#magic)
  - [DT Set](#dt-set)
  - [Lua Template](#lua-template)
  - [Inventory Browser](#inventory-browser)
  - [Compare](#compare)
- [Buff Configuration](#buff-configuration)
- [Results Panel](#results-panel)
- [Data Persistence](#data-persistence)
- [Tips & Best Practices](#tips--best-practices)

---

## Getting Started

1. Open the FFXI Gear Optimizer in your web browser
2. Upload your character's inventory data (see [Uploading Your Data](#uploading-your-data))
3. Select your Job and Sub Job from the sidebar
4. Choose your main weapon (and off-hand if applicable)
5. Navigate to the optimization tab you need (TP, WS, Magic, DT)
6. Configure your buffs and target settings
7. Click the **Optimize** button to generate your optimal gear set

---

## Uploading Your Data

Click the **Upload Data** button in the header to open the upload modal. There are two types of CSV files you can upload:

### Inventory CSV

This file contains your character's available gear and equipment.

**How to upload:**
1. Click the **Upload Data** button in the header
2. Drag and drop your `inventory_*.csv` file onto the upload dropzone, or click to browse
3. Wait for the file to process — you'll see a confirmation with item count

**File format:** The inventory CSV should be exported from your FFXI tools/addons and contain your character's equipment data.

**What happens after upload:**
- The sidebar will show your inventory summary
- Weapon dropdowns will populate with your available weapons
- The optimizer will only suggest gear you actually own
- Your character name and item count will appear in the summary section

### Job Points CSV

This file contains your Job Point and Gift bonus information for accurate stat calculations.

**How to upload:**
1. In the Upload Modal, find the "Job Points CSV" section
2. Drag and drop your `jobgifts_*.csv` file
3. The status indicator will show "Loaded" when complete

**Benefits of uploading Job Points:**
- Accurate Job Point gift bonuses applied to calculations
- Master Level eligibility detection
- Proper accuracy bonuses from JP gifts

---

## Character Configuration

Located in the left sidebar, these settings define your character's base configuration:

### Job Selection
Select your main job from the dropdown. All 22 FFXI jobs are supported:
- WAR, MNK, WHM, BLM, RDM, THF, PLD, DRK, BST, BRD, RNG
- SAM, NIN, DRG, SMN, BLU, COR, PUP, DNC, SCH, GEO, RUN

### Sub Job Selection
Select your support job. This affects:
- Dual Wield trait availability (NIN, DNC)
- Stat bonuses
- Simulation calculations

### Master Level
If your job has 2100+ Job Points, the Master Level slider becomes available:
- Range: 0-50
- Each level provides stat bonuses and HP bonuses
- The current bonus values are displayed below the slider

### Weapon Selection

**Main Weapon:** Search and select your primary weapon from your inventory. The dropdown shows:
- Weapon name
- Damage and delay values
- Item level

**Off-Hand/Sub:** Depending on your weapon type and Dual Wield settings:
- **Two-handed weapons:** Grip selection available
- **One-handed + DW:** Off-hand weapon selection
- **One-handed without DW:** Shield/grip selection

**Dual Wield Checkbox:** For jobs that don't natively have DW (or when not using /NIN or /DNC), enable this if you have DW from gear.

---

## Optimization Tabs

### TP Set

Optimize your gear for maximum TP gain per second.

**Priority Options:**
- **Pure TP:** Maximum TP/second (ignores damage)
- **Hybrid TP:** Balance between TP gain and damage output
- **Accuracy TP:** High accuracy with good TP gain
- **DT TP:** Survivability focus while maintaining TP
- **Refresh TP:** MP sustain for mages

**Configuration:**
- DW Trait (basis points) — Set your native Dual Wield trait value
- Target evasion/defense presets
- Target debuffs (Dia, Geo-Frailty, Angon, etc.)

### WS Set

Optimize gear for weapon skill damage.

**Key settings:**
- Weapon Skill selection (auto-detected based on weapon type)
- WS-specific modifiers
- TP value for calculation (1000-3000)

### Magic

Optimize for magical damage, accuracy, or healing.

**Options:**
- Spell type selection
- Magic Attack Bonus vs Magic Accuracy priority
- Elemental affinity bonuses

### DT Set

Build a survivability set focused on damage mitigation.

**Priorities:**
- Physical Damage Taken (PDT)
- Magical Damage Taken (MDT)
- Hybrid (balanced PDT/MDT)
- Specific damage type resistance

### Lua Template

Upload and automatically optimize GearSwap Lua files.

**How to use:**
1. Ensure inventory is loaded (check the requirements indicator)
2. Upload your GearSwap Lua template file
3. Configure weapons for each set type (TP, WS, Magic)
4. Click **Optimize All Placeholder Sets**
5. Download the optimized Lua file

**Features:**
- Detects placeholder sets automatically
- Applies appropriate optimization per set type
- Option to comment out weapons (prevents TP loss from swapping)
- Error reporting for any issues found

### Inventory Browser

Browse and search through your available items.

**Features:**
- **Search:** Type to filter items by name
- **Slot Filter:** Show only items for a specific equipment slot
- **Job Filter:** Show only items equippable by a specific job
- **Show All:** Toggle to view all game items (not just your inventory)

**Item Comparison:**

**Partially complete**
- Click an item to view detailed stats in a modal
- Use "Add to A" / "Add to B" buttons to compare two items side-by-side
- Clear comparison to start fresh

### Compare

**Coming Eventually**
View optimized sets side-by-side with simulated performance metrics.

---

## Buff Configuration

Each optimization tab includes a comprehensive buff configuration section:

### Food
Select from common endgame food options with stat bonuses displayed.

### BRD Songs (0-4 songs)
Add Bard songs:
- Marches (Haste)
- Minuets (Attack)
- Madrigals (Accuracy)
- Etudes (Stats)
- Aria of Passion (PDL)

### COR Rolls (0-2 rolls)
Add Corsair rolls:
- Chaos Roll (Attack %)
- Samurai Roll (Store TP)
- Fighter's Roll (Double Attack)
- And more...

### GEO Bubbles (0-3 bubbles)
Add Geomancer effects:
- Geo (full potency)
- Indi (self)
- Entrust (from another GEO)

### WHM Spells
Add White Mage buffs:
- Haste / Haste II
- Boost spells
- Gain spells
- Storm spells

### Job Abilities
Toggle job-specific abilities:
- Berserk, Aggressor, Warcry
- Hasso, Last Resort, Innin

### Target Debuffs
Add debuffs applied to the target for accurate calculations:
- Dia II/III
- Geo-Frailty, Geo-Torpor
- Angon, Armor Break
- Box Step, Distract III

---

## Results Panel

The right-side panel displays your optimization results:

### Gear Stats Section
Shows aggregated stats from your optimized set:

**Core Stats:** STR, DEX, VIT, AGI, INT, MND, CHR, Store TP

**Speed Stats:** Gear Haste, Dual Wield, DA, TA, QA

**Defensive Stats:** PDT, MDT

### Accuracy Breakdown
Detailed accuracy calculation showing:
- Accuracy from DEX
- Accuracy from weapon skill
- Accuracy from gear
- Accuracy from JP gifts
- Accuracy from buffs
- Total accuracy vs target evasion
- Hit rate percentage
- WS first hit rate

### GearSwap Lua Output
After optimization, a Lua code block is generated that you can:
- Copy to clipboard with one click
- Paste directly into your GearSwap files

---

## Data Persistence

Your inventory data is **cached in your browser** for convenience:

- Data persists across page reloads
- A notice appears when cached data is detected
- Click **Clear Cache** to remove stored data and upload fresh files

**Note:** Cached data is stored locally in your browser only — it is not uploaded to any server.

---

## Tips & Best Practices

1. **Upload Both CSVs:** For the most accurate calculations, upload both your inventory CSV and job points CSV.

2. **Check Requirements:** Before using the Lua Template optimizer, verify all requirements are met (green indicators).

3. **Start with Hybrid:** If unsure which priority to use, start with "Hybrid" options which balance multiple factors.

4. **Configure Buffs Accurately:** The optimizer's suggestions are only as good as the buff configuration. Match your actual in-game setup.

5. **Compare Results:** Use the Compare tab to evaluate different configurations before committing to a set.

6. **Review Accuracy:** Pay attention to the accuracy breakdown — being accuracy-capped is crucial for DPS.

7. **Export Lua Early:** Generate and save your Lua output frequently as you optimize different sets.

8. **Browser Storage:** Your data is cached locally. Clear the cache if you update your inventory in-game and need to re-upload.

---

## Keyboard Shortcuts

- **Escape:** Close any open modal
- **Tab:** Navigate between input fields

---

## Troubleshooting

**Weapons not appearing in dropdown:**
- Ensure your inventory CSV is uploaded
- Check that you've selected a job that can equip the weapon

**Master Level slider not visible:**
- Upload your Job Points CSV
- Ensure the selected job has 2100+ JP (required for Master Level)

**Optimization not running:**
- Verify a weapon is selected
- Check that inventory is loaded
- Ensure all required fields are filled

**Lua Template errors:**
- Review the error list at the bottom of the results
- Ensure your template file has proper set definitions
- Check that placeholder comments are formatted correctly

---

## Credits

FFXI Gear Optimizer — Built for the Final Fantasy XI community.

For bug reports or feature requests, please use the feedback system or contact the developer.
