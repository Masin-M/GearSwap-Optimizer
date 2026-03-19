# FFXI Gear Optimizer - Set Builder Implementation Plan

## Overview

Add a "Set Builder" feature to the Compare tab that allows users to:
1. Manually select gear for each equipment slot
2. View aggregated stats from all selected items
3. Export the set as GearSwap Lua code

This will be implemented in phases, with Phase 1 focusing on a single set builder.

---

## Files Required for Implementation

### Primary Files (MUST upload)
- `app.js` - Main frontend JavaScript (add SetBuilder object)
- `index.html` - HTML structure (modify Compare tab content)
- `set_builder_implementation_plan.md` - This plan document

### Reference Files (helpful context)
- `api.py` - Backend API (reference only, likely no changes needed)
- `item_database.py` - Understanding item structure
- `inventory_loader.py` - Understanding inventory data flow
- `augment_parser.py` - Understanding stat names and formats

### Path Augment Files (for Phase 2)
- `path_augment_db.py` - Understanding path data structure
- `augment_tables.json` - The actual path data (8MB)
  - **Current location**: `/augment_data/augment_tables.json` (used by Python backend)
  - **Required for frontend**: Copy to `/static/data/augment_tables.json`
  - Both copies can coexist - backend uses its copy, frontend fetches from static

---

## Current Data Structures

### Item Format (from `/api/inventory` endpoint)
```javascript
{
  id: 12345,
  name: "Thibron",
  name2: "Thibron +1",      // Display name (with augment suffix)
  type: "Sword",            // Equipment type
  slot: "Main",             // Backend-mapped slot category
  item_level: 119,
  jobs: ["war", "pld", "drk", "run"],
  stats: {
    STR: 15,
    DEX: 12,
    "Store TP": 10,
    Attack: 25,
    Accuracy: 20,
    // ... all parsed stats
  }
}
```

### Slot Categories (Backend Mapping)
The backend `get_slot_from_type()` function maps item types to these slot categories:
- `Main` - All weapons (sword, axe, club, staff, dagger, katana, scythe, polearm, hand-to-hand, bow, gun)
- `Sub` - Grip, Shield (and weapons if dual wielding)
- `Range` - Ranged weapons (bow, gun, instrument) 
- `Ammo` - Ammunition items
- `Head`, `Body`, `Hands`, `Legs`, `Feet` - Armor pieces
- `Neck`, `Waist`, `Back` - Accessories
- `Ear` - Earrings (user assigns to ear1 or ear2)
- `Ring` - Rings (user assigns to ring1 or ring2)

### Equipment Slots (16 total)
```javascript
const EQUIPMENT_SLOTS = [
  'main', 'sub', 'range', 'ammo',
  'head', 'neck', 'ear1', 'ear2',
  'body', 'hands', 'ring1', 'ring2',
  'back', 'waist', 'legs', 'feet'
];
```

### Slot to API Filter Mapping
```javascript
const SLOT_TO_API_FILTER = {
  main: 'Main',
  sub: 'Sub',      // Note: Also includes weapons for DW
  range: 'Range',
  ammo: 'Ammo',
  head: 'Head',
  neck: 'Neck',
  ear1: 'Ear',     // Same filter for both ear slots
  ear2: 'Ear',
  body: 'Body',
  hands: 'Hands',
  ring1: 'Ring',   // Same filter for both ring slots
  ring2: 'Ring',
  back: 'Back',
  waist: 'Waist',
  legs: 'Legs',
  feet: 'Feet'
};
```

---

## Existing Code to Reuse

### From `InventoryBrowser` object (app.js)
- `loadItems()` - Fetches items via API with slot/job/search filters
- `filterAndDisplay()` - Client-side filtering
- `showItemModal(index)` - Displays item detail modal
- `displayAllStats(stats)` - Groups stats into Primary/Combat/Magic/Other
- `renderStatList(elementId, stats, keys)` - Renders stat key-value pairs

### API Endpoint
```
GET /api/inventory?slot={slot}&job={job}&show_all={bool}&search={query}
```
- `slot` - Filter by slot category (Main, Head, etc.)
- `job` - Filter by job that can equip (WAR, SAM, etc.)
- `show_all` - If true, shows ALL items from database (dream set mode)
- `search` - Text search filter

### Stat Grouping Logic (from `InventoryBrowser.displayAllStats`)
```javascript
const primaryStats = ['HP', 'MP', 'STR', 'DEX', 'VIT', 'AGI', 'INT', 'MND', 'CHR'];
const combatStats = ['DMG', 'Delay', 'Attack', 'Accuracy', 'Ranged Attack', 'Ranged Accuracy',
    'DA', 'TA', 'QA', 'Crit Rate', 'Crit Damage', 'Store TP', 'Weapon Skill Damage', 'PDL',
    'Skillchain Bonus', 'TP Bonus'];
const magicStats = ['Magic Attack', 'Magic Accuracy', 'Magic Damage', 'Magic Burst Bonus', 
    'Magic Burst Bonus II', 'Fast Cast', 'Quick Magic'];
// Everything else goes to "Other"
```

---

## Implementation Architecture

### New `SetBuilder` Object
```javascript
const SetBuilder = {
    // === Mode ===
    mode: 'inventory',          // 'inventory' or 'dream'
    
    // === State ===
    currentSet: {
        main: null, sub: null, range: null, ammo: null,
        head: null, neck: null, ear1: null, ear2: null,
        body: null, hands: null, ring1: null, ring2: null,
        back: null, waist: null, legs: null, feet: null
    },
    
    activeSlot: null,           // Slot currently being edited
    pickerItems: [],            // Cached items for picker modal
    
    // === Path Configuration (Dream Mode) ===
    pathConfig: {},             // { slot: { itemId, path, rank } }
    pathDatabase: null,         // Cached augment_tables.json (lazy loaded)
    pathDatabaseLoading: false, // Loading state flag
    
    // === Computed ===
    aggregatedStats: {},        // Sum of all item stats
    specialEffects: [],         // Non-numeric effects
    
    // === Core Methods ===
    init(),                     // Setup event listeners
    
    // === Mode Management ===
    setMode(mode),              // Switch between inventory/dream
    copyToDreamSet(),           // Copy inventory set to dream mode
    
    // === Slot Selection ===
    openSlotPicker(slot),       // Open modal to select item for slot
    selectItem(item),           // Called when item selected in picker
    clearSlot(slot),            // Remove item from slot
    
    // === Path Handling ===
    async ensurePathDatabase(), // Lazy load augment_tables.json
    hasPathAugment(itemId),     // Check if item has path options
    getItemPathInfo(itemId),    // Get available paths and max rank
    getPathStats(itemId, path, rank), // Get stats for specific path/rank
    getPathEligibleItems(),     // Get slots containing path items
    setPathConfig(slot, path, rank), // Update path config for slot
    
    // === Stats ===
    calculateStats(),           // Aggregate stats from all items + paths
    
    // === Rendering ===
    renderSlotGrid(),           // Render the 16 slot cards
    renderSlotCard(slot),       // Render single slot card
    renderAggregatedStats(),    // Render stats summary panel
    renderPickerModal(items),   // Render item selection modal
    renderPathConfigPanel(),    // Render path configuration (dream mode)
    
    // === Export ===
    generateLuaCode(),          // Convert set to GearSwap Lua
    copyLuaToClipboard(),       // Copy Lua to clipboard
    downloadLuaFile(),          // Download as .lua file
};
```

---

## UI Layout

### Compare Tab Structure
```
┌─────────────────────────────────────────────────────────────────────┐
│ Set Builder                                              [Export Lua]│
├─────────────────────────────────────────────────────────────────────┤
│ Mode: [Inventory ▼]  [Dream ▼]                 [Copy to Dream Set]  │
│ Job: WAR (from sidebar)                                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  EQUIPMENT GRID (4x4)                                               │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                    │
│  │  Main   │ │   Sub   │ │  Range  │ │  Ammo   │                    │
│  │ [icon]  │ │ [icon]  │ │ [icon]  │ │ [icon]  │                    │
│  │ Naegling│ │Blurred+1│ │  Empty  │ │Chrono   │                    │
│  │   [x]   │ │   [x]   │ │         │ │   [x]   │                    │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘                    │
│                                                                      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                    │
│  │  Head   │ │  Neck   │ │  Ear 1  │ │  Ear 2  │                    │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘                    │
│                                                                      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                    │
│  │  Body   │ │  Hands  │ │ Ring 1  │ │ Ring 2  │                    │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘                    │
│                                                                      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                    │
│  │  Back   │ │  Waist  │ │  Legs   │ │  Feet   │                    │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘                    │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│ PATH CONFIGURATION (Dream Mode only, shows when path items present) │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ [Head] Nyame Helm                                                │ │
│ │ Path: [A●] [B ] [C ] [D ]    Rank: [━━━━━━━━━━●] 15/15          │ │
│ │ Stats: STR+25 VIT+35 INT+40 MND+24 DT-7%                         │ │
│ ├─────────────────────────────────────────────────────────────────┤ │
│ │ [Body] Nyame Mail                                                │ │
│ │ Path: [A ] [B●] [C ] [D ]    Rank: [━━━━━━━━━━●] 15/15          │ │
│ │ Stats: STR+30 VIT+30 DEX+30 Attack+30 DT-9%                      │ │
│ └─────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│ AGGREGATED STATS                                                     │
│ ┌─────────────────────────┐ ┌─────────────────────────┐             │
│ │ Primary Stats           │ │ Combat Stats            │             │
│ │ HP:  +312               │ │ Store TP: +52           │             │
│ │ STR: +142               │ │ DA: +21%                │             │
│ │ DEX: +118               │ │ TA: +8%                 │             │
│ │ VIT: +95                │ │ Accuracy: +186          │             │
│ │ AGI: +87                │ │ Attack: +142            │             │
│ │ INT: +45                │ │ Crit Rate: +8%          │             │
│ │ MND: +52                │ │ WSD: +10%               │             │
│ │ CHR: +38                │ │ PDL: +5%                │             │
│ └─────────────────────────┘ └─────────────────────────┘             │
│ ┌─────────────────────────┐ ┌─────────────────────────┐             │
│ │ Magic Stats             │ │ Defensive / Other       │             │
│ │ Magic Attack: +45       │ │ DT: -21%                │             │
│ │ Magic Acc: +32          │ │ PDT: -5%                │             │
│ │ Fast Cast: +12%         │ │ MDT: -3%                │             │
│ │                         │ │ Haste: +26%             │             │
│ └─────────────────────────┘ └─────────────────────────┘             │
│ ┌───────────────────────────────────────────────────────┐           │
│ │ Special Effects                                       │           │
│ │ • "Subtle Blow +10"                                   │           │
│ │ • "Enhances Dual Wield"                               │           │
│ │ • "Set bonus: 3/5 pieces"                             │           │
│ └───────────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────┘
```

### Item Picker Modal
```
┌─────────────────────────────────────────────────────────────────────┐
│ Select Head Item                                              [X]   │
├─────────────────────────────────────────────────────────────────────┤
│ Search: [________________]                                          │
├─────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ [icon] Malignance Chapeau       iLvl 119                        │ │
│ │        STR+29 DEX+38 VIT+25 AGI+43 Acc+50 Atk+40 Haste+6%       │ │
│ ├─────────────────────────────────────────────────────────────────┤ │
│ │ [icon] Nyame Helm               iLvl 119                        │ │
│ │        STR+25 VIT+35 INT+40 MND+24 DT-7% Magic Def+123          │ │
│ ├─────────────────────────────────────────────────────────────────┤ │
│ │ [icon] Sakpata's Helm           iLvl 119                        │ │
│ │        STR+33 VIT+40 Acc+45 Atk+45 DT-8% Haste+3%               │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│ [1] [2] [3] ... [10]  (pagination if needed)                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Path Augment Handling

### Overview
Some items (particularly Ambuscade and Odyssey gear) have **Path Augments** (A/B/C/D) with different stat distributions at various ranks (1-15 or 1-25). This requires special handling depending on the mode:

| Mode | Item Source | Path Handling |
|------|-------------|---------------|
| **Inventory Mode** | User's uploaded CSV | Paths already resolved (rank column + path string parsed on load) |
| **Dream Mode** | Full item database | User manually selects Path and Rank via configuration panel |

### Architecture Decisions

**Client-Side Path Lookup (Option A)**
- Load `augment_tables.json` (~8MB) to client when first needed
- All path lookups happen in browser JavaScript
- Since app runs as local executable, file is read from disk (fast)
- Cache in `AppState.pathAugmentData` - load once, use everywhere

### Lazy Loading Strategy
```javascript
// Don't load on app init - wait until needed
async loadPathDatabase() {
    if (this.pathDatabase) return this.pathDatabase;
    
    const response = await fetch('/static/data/augment_tables.json');
    this.pathDatabase = await response.json();
    return this.pathDatabase;
}
```

Load triggers:
1. User switches to Dream Mode for the first time
2. User clicks "Configure Paths" button
3. User uses "Copy to Dream Set" feature

### Per-Set Mode Toggle
Each set builder instance has a mode selector:
- **Inventory Mode**: Items from user's uploaded inventory (paths pre-resolved)
- **Dream Mode**: Items from full database (paths configurable)

Switching modes:
- Inventory → Dream: Prompt "Copy items to Dream Mode?" (keeps items, enables path config)
- Dream → Inventory: Prompt "This will clear items not in your inventory. Continue?"

### Path Configuration Panel
Only visible when:
1. Set is in Dream Mode, AND
2. At least one item in the set has path augments

Panel shows each path-eligible item with:
- Item name and slot
- Path dropdown (A/B/C/D) - only shows paths that exist for that item
- Rank slider (1 to max_rank, varies by item)
- Live stat preview for selected path/rank

### Data Structure for Paths
```javascript
const SetBuilder = {
    mode: 'inventory',  // 'inventory' or 'dream'
    
    currentSet: {
        main: null, sub: null, /* ... */
    },
    
    // Path overrides for Dream Mode (keyed by slot)
    pathConfig: {
        // Only populated for items that have paths
        head: { itemId: 28576, path: 'A', rank: 15 },
        body: { itemId: 28556, path: 'B', rank: 25 },
    },
    
    // Cached path database (lazy loaded)
    pathDatabase: null,
    
    // Path helper methods
    async ensurePathDatabase(),           // Load if not loaded
    getItemPathInfo(itemId),              // Returns { paths: ['A','B','C','D'], maxRank: 15 }
    getPathStats(itemId, path, rank),     // Returns stat object for path/rank
    hasPathAugment(itemId),               // Quick check if item has paths
    getPathEligibleItems(),               // Returns slots with path items
};
```

### Path Stats Resolution
When calculating aggregated stats in Dream Mode:
```javascript
calculateStats() {
    this.aggregatedStats = {};
    
    for (const slot of EQUIPMENT_SLOTS) {
        const item = this.currentSet[slot];
        if (!item) continue;
        
        let itemStats = { ...item.stats };  // Base stats
        
        // In Dream Mode, apply path stats if configured
        if (this.mode === 'dream' && this.pathConfig[slot]) {
            const { path, rank } = this.pathConfig[slot];
            const pathStats = this.getPathStats(item.id, path, rank);
            if (pathStats) {
                // Merge path stats into item stats
                for (const [stat, value] of Object.entries(pathStats)) {
                    itemStats[stat] = (itemStats[stat] || 0) + value;
                }
            }
        }
        
        // Aggregate into totals
        for (const [stat, value] of Object.entries(itemStats)) {
            if (typeof value === 'number') {
                this.aggregatedStats[stat] = (this.aggregatedStats[stat] || 0) + value;
            }
        }
    }
}
```

### Copy to Dream Set Feature
Button: "Copy to Dream Set"
- Creates a duplicate of current inventory set in dream mode
- For path items: attempts to preserve current path/rank from inventory data
- Allows "what if" scenarios: "What if I had Rank 25 instead of Rank 15?"

### Updated UI Layout with Path Panel
```
┌─────────────────────────────────────────────────────────────────────┐
│ Set Builder                                              [Export Lua]│
├─────────────────────────────────────────────────────────────────────┤
│ Mode: [Inventory ▼] / [Dream ▼]                [Copy to Dream Set]  │
│ ☐ Show All Items (only in Dream Mode)                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  EQUIPMENT GRID (4x4)                                               │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                    │
│  │  Main   │ │   Sub   │ │  Range  │ │  Ammo   │                    │
│  │ Naegling│ │Blurred+1│ │  Empty  │ │Chrono   │                    │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘                    │
│  (... remaining slots ...)                                          │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│ PATH CONFIGURATION (Dream Mode only, if path items present)         │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ [Head] Nyame Helm                                                │ │
│ │ Path: [A ▼] [B] [C] [D]    Rank: [●━━━━━━━━━━━━━] 1-15  [15]    │ │
│ │ Preview: STR+25 VIT+35 INT+40 DT-7%                              │ │
│ ├─────────────────────────────────────────────────────────────────┤ │
│ │ [Body] Nyame Mail                                                │ │
│ │ Path: [A] [B ▼] [C] [D]    Rank: [━━━━━━━━━━━━━●] 1-15  [15]    │ │
│ │ Preview: STR+30 VIT+30 Attack+30 DT-9%                           │ │
│ └─────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│ AGGREGATED STATS                                                     │
│ (... stats panels ...)                                               │
└─────────────────────────────────────────────────────────────────────┘
```

### augment_tables.json Structure (Reference)
```json
{
  "metadata": { "version": "1.0", "item_count": 150 },
  "items": {
    "28576": {
      "name": "Nyame Helm",
      "item_type": "Head",
      "max_rank": 15,
      "paths": {
        "A": {
          "tiers": {
            "1": { "stats": { "STR": 10, "VIT": 15 } },
            "15": { "stats": { "STR": 25, "VIT": 35, "DT": -7 } }
          }
        },
        "B": { /* ... */ },
        "C": { /* ... */ },
        "D": { /* ... */ }
      }
    }
  }
}
```

### Implementation Phases for Paths
- **Phase 1**: Build core Set Builder without path handling (Inventory Mode only)
- **Phase 1.5**: Add Dream Mode toggle and "Show All Items" 
- **Phase 2**: Add path configuration panel and augment_tables.json loading
- **Phase 3**: Comparison features (Set A vs Set B, including mixed modes)

---

## Implementation Steps

### Phase 1: Core Set Builder (Inventory Mode)

#### Step 1: HTML Structure
Add to Compare tab (`#tab-compare`):
- Header with title, mode toggle, and export button
- Equipment slot grid (4 columns × 4 rows)
- Aggregated stats panel
- Item picker modal (can reuse/modify existing item-modal)

#### Step 2: SetBuilder.init()
- Setup click handlers for each slot card
- Setup mode toggle handler
- Setup export button handler
- Initialize empty set state

#### Step 3: SetBuilder.openSlotPicker(slot)
```javascript
async openSlotPicker(slot) {
    this.activeSlot = slot;
    const apiFilter = SLOT_TO_API_FILTER[slot];
    const job = AppState.selectedJob || '';
    const showAll = (this.mode === 'dream');
    
    // Fetch items from API
    const url = `/api/inventory?slot=${apiFilter}&job=${job}&show_all=${showAll}`;
    const response = await API.fetch(url);
    
    this.pickerItems = response.items || [];
    this.renderPickerModal();
    // Show modal
}
```

#### Step 4: SetBuilder.selectItem(item)
```javascript
selectItem(item) {
    if (this.activeSlot) {
        this.currentSet[this.activeSlot] = item;
        
        // In dream mode, check if item has paths and init config
        if (this.mode === 'dream' && this.hasPathAugment(item.id)) {
            const pathInfo = this.getItemPathInfo(item.id);
            this.pathConfig[this.activeSlot] = {
                itemId: item.id,
                path: pathInfo.paths[0],  // Default to first path
                rank: pathInfo.maxRank     // Default to max rank
            };
        }
        
        this.calculateStats();
        this.renderSlotCard(this.activeSlot);
        this.renderAggregatedStats();
        this.renderPathConfigPanel();  // Update path panel if needed
        this.closePickerModal();
    }
}
```

#### Step 5: SetBuilder.calculateStats()
```javascript
calculateStats() {
    this.aggregatedStats = {};
    this.specialEffects = [];
    
    for (const slot of EQUIPMENT_SLOTS) {
        const item = this.currentSet[slot];
        if (!item || !item.stats) continue;
        
        // Start with base item stats
        let itemStats = { ...item.stats };
        
        // In Dream Mode, overlay path stats if configured
        if (this.mode === 'dream' && this.pathConfig[slot]) {
            const { path, rank } = this.pathConfig[slot];
            const pathStats = this.getPathStats(item.id, path, rank);
            if (pathStats) {
                for (const [stat, value] of Object.entries(pathStats)) {
                    if (typeof value === 'number') {
                        itemStats[stat] = (itemStats[stat] || 0) + value;
                    }
                }
            }
        }
        
        // Aggregate into totals
        for (const [stat, value] of Object.entries(itemStats)) {
            if (typeof value === 'number') {
                this.aggregatedStats[stat] = (this.aggregatedStats[stat] || 0) + value;
            } else if (typeof value === 'string') {
                this.specialEffects.push(value);
            }
        }
    }
}
```

#### Step 6: Rendering Functions
- `renderSlotGrid()` - Creates 16 slot cards
- `renderSlotCard(slot)` - Updates single card with item or "Empty"
- `renderAggregatedStats()` - Groups and displays totals
- `renderPickerModal()` - Shows searchable item list

### Phase 1.5: Dream Mode Toggle

#### Step 7: Mode Management
```javascript
setMode(newMode) {
    if (newMode === this.mode) return;
    
    if (newMode === 'dream' && this.mode === 'inventory') {
        // Switching to dream - offer to copy current set
        if (this.hasAnyItems()) {
            if (confirm('Copy current items to Dream Mode?')) {
                this.mode = 'dream';
                // Items stay, path config will be populated as needed
            } else {
                this.mode = 'dream';
                this.clearAllSlots();
            }
        } else {
            this.mode = 'dream';
        }
        // Load path database in background
        this.ensurePathDatabase();
        
    } else if (newMode === 'inventory' && this.mode === 'dream') {
        // Switching to inventory - warn about losing dream items
        if (confirm('Switch to Inventory Mode? Items not in your inventory will be cleared.')) {
            this.mode = 'inventory';
            this.pathConfig = {};  // Clear path configs
            // TODO: Filter out items not in inventory
        }
    }
    
    this.renderModeToggle();
    this.renderSlotGrid();
    this.renderPathConfigPanel();
}
```

#### Step 8: Copy to Dream Set
```javascript
copyToDreamSet() {
    if (this.mode !== 'inventory') return;
    
    // Switch to dream mode, keeping items
    this.mode = 'dream';
    
    // Load path database
    this.ensurePathDatabase().then(() => {
        // Initialize path config for any path items
        for (const slot of EQUIPMENT_SLOTS) {
            const item = this.currentSet[slot];
            if (item && this.hasPathAugment(item.id)) {
                const pathInfo = this.getItemPathInfo(item.id);
                // Try to preserve existing path/rank from inventory item if available
                this.pathConfig[slot] = {
                    itemId: item.id,
                    path: item._pathLetter || pathInfo.paths[0],
                    rank: item._pathRank || pathInfo.maxRank
                };
            }
        }
        this.renderPathConfigPanel();
        this.calculateStats();
        this.renderAggregatedStats();
    });
    
    this.renderModeToggle();
}
```

### Phase 2: Path Configuration Panel

#### Step 9: Lazy Load Path Database
```javascript
async ensurePathDatabase() {
    if (this.pathDatabase) return this.pathDatabase;
    if (this.pathDatabaseLoading) {
        // Wait for existing load to complete
        while (this.pathDatabaseLoading) {
            await new Promise(r => setTimeout(r, 100));
        }
        return this.pathDatabase;
    }
    
    this.pathDatabaseLoading = true;
    try {
        const response = await fetch('/static/data/augment_tables.json');
        this.pathDatabase = await response.json();
    } catch (error) {
        console.error('Failed to load path database:', error);
        this.pathDatabase = { items: {} };
    }
    this.pathDatabaseLoading = false;
    return this.pathDatabase;
}
```

#### Step 10: Path Helper Methods
```javascript
hasPathAugment(itemId) {
    if (!this.pathDatabase) return false;
    return itemId in this.pathDatabase.items;
}

getItemPathInfo(itemId) {
    if (!this.pathDatabase || !this.pathDatabase.items[itemId]) {
        return null;
    }
    const item = this.pathDatabase.items[itemId];
    return {
        name: item.name,
        paths: Object.keys(item.paths),
        maxRank: item.max_rank || 15
    };
}

getPathStats(itemId, path, rank) {
    if (!this.pathDatabase) return null;
    const item = this.pathDatabase.items[itemId];
    if (!item || !item.paths[path]) return null;
    
    const tier = item.paths[path].tiers[rank.toString()];
    return tier ? tier.stats : null;
}

getPathEligibleItems() {
    const eligible = [];
    for (const slot of EQUIPMENT_SLOTS) {
        const item = this.currentSet[slot];
        if (item && this.hasPathAugment(item.id)) {
            eligible.push({ slot, item });
        }
    }
    return eligible;
}
```

#### Step 11: Path Configuration Panel Rendering
```javascript
renderPathConfigPanel() {
    const container = document.getElementById('set-builder-path-config');
    if (!container) return;
    
    // Only show in dream mode with path items
    const pathItems = this.getPathEligibleItems();
    if (this.mode !== 'dream' || pathItems.length === 0) {
        container.classList.add('hidden');
        return;
    }
    
    container.classList.remove('hidden');
    
    let html = '<h3 class="text-sm uppercase tracking-wider text-ffxi-accent mb-3">Path Configuration</h3>';
    
    for (const { slot, item } of pathItems) {
        const pathInfo = this.getItemPathInfo(item.id);
        const config = this.pathConfig[slot] || { path: pathInfo.paths[0], rank: pathInfo.maxRank };
        const currentStats = this.getPathStats(item.id, config.path, config.rank);
        
        html += `
            <div class="bg-ffxi-dark rounded p-3 mb-2">
                <div class="flex items-center justify-between mb-2">
                    <span class="text-ffxi-text font-medium">[${slot}] ${item.name2 || item.name}</span>
                </div>
                <div class="flex items-center gap-4 mb-2">
                    <div class="flex items-center gap-1">
                        <span class="text-xs text-ffxi-text-dim">Path:</span>
                        ${pathInfo.paths.map(p => `
                            <button class="px-2 py-0.5 text-xs rounded ${config.path === p ? 'bg-ffxi-accent text-ffxi-dark' : 'bg-ffxi-panel text-ffxi-text-dim'}"
                                    onclick="SetBuilder.setPathConfig('${slot}', '${p}', ${config.rank})">
                                ${p}
                            </button>
                        `).join('')}
                    </div>
                    <div class="flex items-center gap-2 flex-1">
                        <span class="text-xs text-ffxi-text-dim">Rank:</span>
                        <input type="range" min="1" max="${pathInfo.maxRank}" value="${config.rank}"
                               class="flex-1 accent-ffxi-accent"
                               onchange="SetBuilder.setPathConfig('${slot}', '${config.path}', parseInt(this.value))">
                        <span class="text-xs text-ffxi-text w-6 text-center">${config.rank}</span>
                    </div>
                </div>
                <div class="text-xs text-ffxi-text-dim">
                    ${currentStats ? Object.entries(currentStats).map(([k,v]) => `${k}:${v > 0 ? '+' : ''}${v}`).join(' ') : 'No stats'}
                </div>
            </div>
        `;
    }
    
    container.innerHTML = html;
}

setPathConfig(slot, path, rank) {
    const item = this.currentSet[slot];
    if (!item) return;
    
    this.pathConfig[slot] = { itemId: item.id, path, rank };
    this.calculateStats();
    this.renderAggregatedStats();
    this.renderPathConfigPanel();
}
```

### Phase 3: Comparison Mode (Future)
- Add Set A / Set B tabs or side-by-side layout
- Support mixed modes (Set A: Inventory, Set B: Dream)
- "Copy A → B" button
- Stat diff highlighting (green for better, red for worse)

### Phase 4: Lua Export (Future)
```javascript
generateLuaCode() {
    const lines = ['sets.my_set = {'];
    
    for (const slot of EQUIPMENT_SLOTS) {
        const item = this.currentSet[slot];
        if (item) {
            const luaSlot = slot; // May need mapping for ear1->left_ear etc
            const itemName = item.name2 || item.name;
            lines.push(`    ${luaSlot}="${itemName}",`);
        }
    }
    
    lines.push('}');
    return lines.join('\n');
}
```

---

## Edge Cases to Handle

### Weapons
- Two-handed weapons (staff, great sword, etc.) should clear the sub slot
- Dual wield: Sub slot should also show Main-type weapons
- Hand-to-hand: Uses main slot, sub should be empty

### Sub Slot Logic
When main weapon is selected:
1. Check weapon type
2. If 2H weapon → sub options = grips only
3. If 1H weapon + DW possible → sub options = grips, shields, AND 1H weapons
4. If 1H weapon + no DW → sub options = grips, shields only

### Duplicate Items
- Ears and Rings: Same item CAN be in both slots (e.g., two Telos Earrings)
- This is intentional for "dream set" mode

### Job Filtering
- Use `AppState.selectedJob` from sidebar
- If no job selected, show all items (with warning?)

---

## Testing Checklist

### Phase 1: Core Set Builder
- [ ] Can select item for each of 16 slots
- [ ] Can clear item from slot
- [ ] Stats aggregate correctly (sum all numeric values)
- [ ] Special effects display in Other section
- [ ] Job filter applies correctly
- [ ] Search works in picker modal
- [ ] Slot cards update visually when item selected
- [ ] Stats panel updates when any slot changes

### Phase 1.5: Mode Management
- [ ] Mode toggle switches between Inventory/Dream
- [ ] "Copy to Dream Set" button works
- [ ] Dream mode shows all items from database
- [ ] Inventory mode shows only user's inventory items
- [ ] Switching modes prompts appropriately

### Phase 2: Path Configuration
- [ ] `augment_tables.json` loads lazily (only when needed)
- [ ] Path config panel appears when path items are in set
- [ ] Path config panel hidden when no path items
- [ ] Path buttons (A/B/C/D) update correctly
- [ ] Rank slider updates stats in real-time
- [ ] Path stats correctly added to aggregated totals
- [ ] Items not in path database handled gracefully

### Phase 3+: Comparison & Export
- [ ] Export generates valid Lua syntax
- [ ] Copy to clipboard works
- [ ] Download as file works

---

## Notes for Development

### AppState Integration
- Use `AppState.selectedJob` for job filtering
- DO NOT use sidebar weapon selection (set builder is independent)
- Store path database in `SetBuilder.pathDatabase` (not AppState) to keep it scoped
- May want to save/load sets to localStorage in future

### Styling
- Follow existing Tailwind classes used in app
- Use `ffxi-*` color scheme (ffxi-panel, ffxi-accent, ffxi-border, etc.)
- Match existing card/modal styling from Inventory tab

### Performance
- Cache API responses where possible
- Consider pagination for Dream Mode item picker (thousands of items)
- Debounce search input
- Path database: Load ONCE when first needed, then cache permanently

### Path Augment Considerations
- `augment_tables.json` must be copied to `/static/data/` for client access
  - **Setup**: `cp augment_data/augment_tables.json static/data/augment_tables.json`
  - Create `/static/data/` directory if it doesn't exist
- Items in Inventory Mode already have paths resolved (from CSV rank + path columns)
- Dream Mode items start with base stats; path stats are ADDED via pathConfig
- Not all items have all 4 paths (some only have A/B, some A/B/C/D)
- Max rank varies by item (typically 15 or 25)
- Handle missing items in path database gracefully (show item, skip path config)

---

## Questions Resolved

1. **Sidebar weapon inheritance**: NO - Set Builder is independent
2. **Dropdown type**: Click-to-open modal with search (like inventory browser)
3. **Stats to display**: All stats, grouped like item modal (Primary/Combat/Magic/Other)
4. **Save/load sets**: Not in Phase 1 (future enhancement)
5. **Duplicate items**: Allowed (user responsibility, needed for dream sets)
6. **Path augments**: 
   - Inventory Mode: Paths pre-resolved from CSV data
   - Dream Mode: User configures via Path Config Panel
   - `augment_tables.json` loaded client-side (lazy, cached)
7. **Mode switching**: Per-set toggle with "Copy to Dream Set" feature
8. **Comparison modes**: Future phase will support mixed modes (Inventory vs Dream)
