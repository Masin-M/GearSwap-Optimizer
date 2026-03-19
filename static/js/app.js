/**
 * FFXI Gear Set Optimizer - Frontend Application
 * 
 * Handles UI interactions and API communication
 */

// =============================================================================
// STATE MANAGEMENT
// =============================================================================

const AppState = {
    // Status
    inventoryLoaded: false,
    jobGiftsLoaded: false,
    wsdistAvailable: false,
    
    // Buff data caches
    physicalBuffData: null,  // Cache for physical buffs from API
    magicBuffData: null,     // Cache for magic buffs from API
    
    // Selections
    selectedJob: null,
    selectedSubJob: 'war',
    selectedMainWeapon: null,
    selectedSubWeapon: null,
    selectedRangedWeapon: null,
    selectedAmmo: null,
    selectedWeaponskill: null,
    
    // Data caches
    weapons: [],
    offhand: [],
    rangedWeapons: [],
    ammoItems: [],
    weaponskills: [],
    
    // Dropdown references (for setting input text programmatically)
    dropdowns: {
        mainWeapon: null,
        subWeapon: null,
        rangedWeapon: null,
        ammo: null,
    },
    
    // Master level
    masterLevel: 0,
    hasDualWield: false,
    
    // Results
    currentResults: null,
    currentResultType: null,  // 'tp', 'ws', 'dt', or 'magic'
    currentDTType: 'pure_dt', // tracks which DT sub-type was last run
    currentMagicResult: null,
    currentStats: null,
    currentTab: 'tp',
    
    // TP Tab State (separate from WS)
    tp: {
        buffs: {
            brd: [],
            cor: [],
            geo: [],
            whm: [],
        },
        abilities: [],
        food: '',
        debuffs: [],
        target: 'apex_toad',
        beamWidth: 10000,
    },
    
    // WS Tab State (separate from TP)
    ws: {
        buffs: {
            brd: [],
            cor: [],
            geo: [],
            whm: [],
        },
        abilities: [],
        food: '',
        debuffs: [],
        target: 'apex_toad',
        beamWidth: 10000,
        useSimulation: true,
        mode: 'melee',  // 'melee' or 'ranged'
    },
    
    // Shared custom physical buffs (used by both TP and WS tabs)
    customPhysicalBuffs: {
        STR: 0,
        DEX: 0,
        VIT: 0,
        AGI: 0,
        attack: 0,
        attack_pct: 0,
        accuracy: 0,
        magic_haste: 0,
        store_tp: 0,
        double_attack: 0,
        triple_attack: 0,
        crit_rate: 0,
        pdl: 0,
    },
    
    // Magic state (already separate)
    magic: {
        selectedCategory: null,
        selectedSpell: null,
        spellData: null,
        optimizationType: 'damage',
        magicBurst: true,
        skillchainSteps: 2,
        includeWeapons: false,
        target: 'apex_mob',
        beamWidth: 10000,
        buffs: {
            brd: [],
            geo: [],
            cor: [],
            sch: [],
            whm: [],
            food: null,
        },
        debuffs: [],
        customBuffs: {
            INT: 0,
            MND: 0,
            VIT: 0,
            magic_attack: 0,
            magic_accuracy: 0,
            magic_damage: 0,
            cure_potency: 0,
        },
        slowMode: false,
        slowMaxIterations: 3,
        slowTopN: 3,
    },
    
    // Magic caches
    spellCategories: [],
    spellsByCategory: {},
};

// =============================================================================
// LOCAL STORAGE PERSISTENCE
// =============================================================================

const STORAGE_KEYS = {
    JOB: 'ffxi_selected_job',
    SUBJOB: 'ffxi_selected_subjob',
    MAIN_WEAPON: 'ffxi_main_weapon',
    SUB_WEAPON: 'ffxi_sub_weapon',
    RANGED_WEAPON: 'ffxi_ranged_weapon',
    AMMO: 'ffxi_selected_ammo',
    MASTER_LEVEL: 'ffxi_master_level',
    INVENTORY_DATA: 'ffxi_inventory_data',
    INVENTORY_CHAR: 'ffxi_inventory_char',
    JOB_GIFTS_DATA: 'ffxi_job_gifts_data',
};

function saveToLocalStorage(key, value) {
    try {
        if (value === null || value === undefined) {
            localStorage.removeItem(key);
        } else if (typeof value === 'object') {
            localStorage.setItem(key, JSON.stringify(value));
        } else {
            localStorage.setItem(key, value);
        }
    } catch (e) {
        console.warn('Failed to save to localStorage:', e);
    }
}

function loadFromLocalStorage(key, defaultValue = null) {
    try {
        const value = localStorage.getItem(key);
        if (value === null) return defaultValue;
        
        // Try to parse as JSON, fallback to raw value
        try {
            return JSON.parse(value);
        } catch {
            return value;
        }
    } catch (e) {
        console.warn('Failed to load from localStorage:', e);
        return defaultValue;
    }
}

function clearStoredInventory() {
    localStorage.removeItem(STORAGE_KEYS.INVENTORY_DATA);
    localStorage.removeItem(STORAGE_KEYS.INVENTORY_CHAR);
}

function clearStoredJobGifts() {
    localStorage.removeItem(STORAGE_KEYS.JOB_GIFTS_DATA);
}

// Helper to update DW hint based on main/sub job
function updateDWHint() {
    const dwHint = document.getElementById('dw-hint');
    const mainJob = AppState.selectedJob?.toUpperCase() || '';
    const subjob = AppState.selectedSubJob?.toUpperCase() || '';
    
    if (dwHint) {
        // Jobs that provide DW as main job (THF only gets DW as main, not sub)
        const dwMainJobs = ['NIN', 'DNC', 'BLU', 'THF'];
        // Jobs that provide DW as sub job
        const dwSubJobs = ['NIN', 'DNC'];
        
        if (dwMainJobs.includes(mainJob)) {
            dwHint.textContent = `${mainJob} has native Dual Wield trait`;
            dwHint.classList.add('text-ffxi-green');
            dwHint.classList.remove('text-ffxi-text-dim');
        } else if (dwSubJobs.includes(subjob)) {
            dwHint.textContent = `/${subjob} provides Dual Wield trait`;
            dwHint.classList.add('text-ffxi-green');
            dwHint.classList.remove('text-ffxi-text-dim');
        } else {
            dwHint.textContent = 'Enable if using /NIN, /DNC, or DW from gear';
            dwHint.classList.remove('text-ffxi-green');
            dwHint.classList.add('text-ffxi-text-dim');
        }
    }
}

function handleClearCache() {
    // Clear all cached data
    clearStoredInventory();
    clearStoredJobGifts();
    localStorage.removeItem(STORAGE_KEYS.JOB);
    localStorage.removeItem(STORAGE_KEYS.SUBJOB);
    localStorage.removeItem(STORAGE_KEYS.MAIN_WEAPON);
    localStorage.removeItem(STORAGE_KEYS.SUB_WEAPON);
    localStorage.removeItem(STORAGE_KEYS.MASTER_LEVEL);
    
    // Update UI
    updateCachedDataNotice();
    showToast('Cache cleared. Reload page to reset all selections.', 'info');
}

function updateCachedDataNotice() {
    const notice = document.getElementById('cached-data-notice');
    const cachedInventory = loadFromLocalStorage(STORAGE_KEYS.INVENTORY_DATA);
    const cachedJobGifts = loadFromLocalStorage(STORAGE_KEYS.JOB_GIFTS_DATA);
    
    if (notice) {
        // Check if we have cached data (inventory is now a CSV string, job gifts is an object)
        const hasInventory = cachedInventory && typeof cachedInventory === 'string' && cachedInventory.length > 0;
        const hasJobGifts = cachedJobGifts && typeof cachedJobGifts === 'object' && Object.keys(cachedJobGifts).length > 0;
        
        if (hasInventory || hasJobGifts) {
            notice.classList.remove('hidden');
            
            // Update the notice text to show what's cached
            const noticeText = notice.querySelector('p.text-ffxi-blue');
            if (noticeText) {
                const parts = [];
                if (hasInventory) {
                    parts.push('Inventory');
                }
                if (hasJobGifts) {
                    parts.push('Job Points');
                }
                noticeText.textContent = `📦 ${parts.join(' & ')} data cached in browser`;
            }
        } else {
            notice.classList.add('hidden');
        }
    }
}

// =============================================================================
// API FUNCTIONS
// =============================================================================

const API = {
    baseUrl: '',
    
    async fetch(endpoint, options = {}) {
        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers,
                },
            });
            return await response.json();
        } catch (error) {
            console.error(`API Error: ${endpoint}`, error);
            showToast(`API Error: ${error.message}`, 'error');
            throw error;
        }
    },
    
    async getStatus() {
        return this.fetch('/api/status');
    },
    
    async uploadInventory(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${this.baseUrl}/api/upload/inventory`, {
            method: 'POST',
            body: formData,
        });
        return response.json();
    },
    
    async uploadJobGifts(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${this.baseUrl}/api/upload/jobgifts`, {
            method: 'POST',
            body: formData,
        });
        return response.json();
    },
    
    async getJobs() {
        return this.fetch('/api/jobs');
    },
    
    async getWeapons(job) {
        return this.fetch(`/api/weapons/${job}`);
    },
    
    async getRangedWeapons(job) {
        return this.fetch(`/api/ranged-weapons/${job}`);
    },
    
    async getOffhand(job, mainSkill) {
        const params = mainSkill ? `?main_skill=${encodeURIComponent(mainSkill)}` : '';
        return this.fetch(`/api/offhand/${job}${params}`);
    },
    
    async getWeaponskills(skillType) {
        return this.fetch(`/api/weaponskills?skill_type=${encodeURIComponent(skillType)}`);
    },
    
    async getBuffs() {
        return this.fetch('/api/buffs/full');
    },
    
    async getPhysicalBuffs() {
        return this.fetch('/api/buffs/physical');
    },
    
    async getTargets() {
        return this.fetch('/api/targets');
    },
    
    async getTpTypes() {
        return this.fetch('/api/tp-types');
    },
    
    async optimizeWS(params) {
        return this.fetch('/api/optimize/ws', {
            method: 'POST',
            body: JSON.stringify(params),
        });
    },
    
    async optimizeTP(params) {
        return this.fetch('/api/optimize/tp', {
            method: 'POST',
            body: JSON.stringify(params),
        });
    },
    
    async getDtTypes() {
        return this.fetch('/api/dt-types');
    },
    
    async optimizeDT(params) {
        return this.fetch('/api/optimize/dt', {
            method: 'POST',
            body: JSON.stringify(params),
        });
    },
    
    async getInventory(job = null) {
        const params = job ? `?job=${job}` : '';
        return this.fetch(`/api/inventory${params}`);
    },
    
    async calculateStats(params) {
        return this.fetch('/api/stats/calculate', {
            method: 'POST',
            body: JSON.stringify(params),
        });
    },
    
    // Magic API functions
    async getSpells() {
        return this.fetch('/api/spells');
    },
    
    async getSpellCategories() {
        return this.fetch('/api/spells/categories');
    },
    
    async getSpellsByCategory(categoryId) {
        return this.fetch(`/api/spells/category/${encodeURIComponent(categoryId)}`);
    },
    
    async getSpellDetails(spellName) {
        return this.fetch(`/api/spell/${encodeURIComponent(spellName)}`);
    },
    
    async getMagicOptimizationTypes(spellName = null) {
        const params = spellName ? `?spell_name=${encodeURIComponent(spellName)}` : '';
        return this.fetch(`/api/magic/optimization-types${params}`);
    },
    
    async getMagicTargets() {
        return this.fetch('/api/magic/targets');
    },
    
    async getMagicBuffs() {
        return this.fetch('/api/buffs/magic');
    },
    
    async optimizeMagic(params) {
        return this.fetch('/api/optimize/magic', {
            method: 'POST',
            body: JSON.stringify(params),
        });
    },
    
    async simulateMagic(params) {
        return this.fetch('/api/magic/simulate', {
            method: 'POST',
            body: JSON.stringify(params),
        });
    },

    async simulateTP(params) {
        return this.fetch('/api/simulate/tp', {
            method: 'POST',
            body: JSON.stringify(params),
        });
    },

    async simulateWS(params) {
        return this.fetch('/api/simulate/ws', {
            method: 'POST',
            body: JSON.stringify(params),
        });
    },
    
    async calculateMagicStats(params) {
        return this.fetch('/api/stats/calculate/magic', {
            method: 'POST',
            body: JSON.stringify(params),
        });
    },
};

// =============================================================================
// DYNAMIC BUFF POPULATION FUNCTIONS
// =============================================================================

/**
 * Populate all physical buff selectors (TP and WS tabs) from API data.
 * Call this during initialization after fetching buff data.
 */
async function populatePhysicalBuffSelectors() {
    try {
        // Fetch physical buff data from API
        const data = await API.getPhysicalBuffs();
        if (!data || !data.buffs) {
            console.error('Failed to load physical buff data');
            return;
        }
        
        // Cache the data
        AppState.physicalBuffData = data;
        
        // Populate selectors for both TP and WS tabs
        ['tp', 'ws'].forEach(tabPrefix => {
            populateFoodSelector(tabPrefix, data.buffs.food);
            populateBrdSelector(tabPrefix, data.buffs.brd);
            populateCorSelector(tabPrefix, data.buffs.cor);
            populateGeoSelector(tabPrefix, data.buffs.geo);
            populateWhmSelector(tabPrefix, data.buffs.whm);
            populateDebuffSelector(tabPrefix, data.debuffs);
            populateTargetSelector(tabPrefix, data.targets);
            populateAbilitiesSelector(tabPrefix);
        });
        
        console.log('Physical buff selectors populated');
        
    } catch (error) {
        console.error('Error populating physical buff selectors:', error);
    }
}

/**
 * Populate food selector
 */
function populateFoodSelector(tabPrefix, foods) {
    const select = document.getElementById(`${tabPrefix}-food-select`);
    if (!select || !foods) return;
    
    select.innerHTML = '<option value="">No Food</option>';
    
    for (const [name, stats] of Object.entries(foods)) {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = formatFoodLabel(name, stats);
        select.appendChild(option);
    }
}

/**
 * Format food option label with stats
 */
function formatFoodLabel(name, stats) {
    const parts = [];
    if (stats.STR) parts.push(`STR+${stats.STR}`);
    if (stats.DEX) parts.push(`DEX+${stats.DEX}`);
    if (stats.VIT) parts.push(`VIT+${stats.VIT}`);
    if (stats.AGI) parts.push(`AGI+${stats.AGI}`);
    if (stats.attack) parts.push(`Atk+${stats.attack}`);
    if (stats.accuracy) parts.push(`Acc+${stats.accuracy}`);
    
    if (parts.length > 0) {
        return `${name} (${parts.join(' ')})`;
    }
    return name;
}

/**
 * Populate BRD song selector with optgroups
 */
function populateBrdSelector(tabPrefix, brdSongs) {
    const select = document.getElementById(`${tabPrefix}-brd-song-add`);
    if (!select || !brdSongs) return;
    
    select.innerHTML = '<option value="">Add song...</option>';
    
    // Group songs by type
    const groups = {
        'Marches': [],
        'Minuets': [],
        'Madrigals': [],
        'Etudes': [],
        'Other': []
    };
    
    for (const [name, stats] of Object.entries(brdSongs)) {
        const entry = { name, stats };
        
        if (name.includes('March')) {
            groups['Marches'].push(entry);
        } else if (name.includes('Minuet')) {
            groups['Minuets'].push(entry);
        } else if (name.includes('Madrigal')) {
            groups['Madrigals'].push(entry);
        } else if (name.includes('Etude')) {
            groups['Etudes'].push(entry);
        } else {
            groups['Other'].push(entry);
        }
    }
    
    // Create optgroups
    for (const [groupName, songs] of Object.entries(groups)) {
        if (songs.length === 0) continue;
        
        const optgroup = document.createElement('optgroup');
        optgroup.label = groupName;
        
        for (const song of songs) {
            const option = document.createElement('option');
            option.value = song.name;
            option.textContent = formatBrdLabel(song.name, song.stats);
            optgroup.appendChild(option);
        }
        
        select.appendChild(optgroup);
    }
}

/**
 * Format BRD song label
 */
function formatBrdLabel(name, stats) {
    const parts = [];
    if (stats.magic_haste) {
        const hastePct = Math.round(stats.magic_haste * 100);
        parts.push(`Haste+${hastePct}%`);
    }
    if (stats.attack) parts.push(`Atk+${stats.attack}`);
    if (stats.accuracy) parts.push(`Acc+${stats.accuracy}`);
    if (stats.STR) parts.push(`STR+${stats.STR}`);
    if (stats.DEX) parts.push(`DEX+${stats.DEX}`);
    if (stats.VIT) parts.push(`VIT+${stats.VIT}`);
    if (stats.AGI) parts.push(`AGI+${stats.AGI}`);
    if (stats.pdl) parts.push(`PDL+${stats.pdl}`);
    
    if (parts.length > 0) {
        return `${name} (${parts.join(' ')})`;
    }
    return name;
}

/**
 * Populate COR roll selector
 */
function populateCorSelector(tabPrefix, corRolls) {
    const select = document.getElementById(`${tabPrefix}-cor-roll-add`);
    if (!select || !corRolls) return;
    
    select.innerHTML = '<option value="">Add roll...</option>';
    
    for (const [name, stats] of Object.entries(corRolls)) {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = formatCorLabel(name, stats);
        select.appendChild(option);
    }
}

/**
 * Format COR roll label
 */
function formatCorLabel(name, stats) {
    const parts = [];
    if (stats.attack_pct) {
        const atkPct = Math.round(stats.attack_pct * 100);
        parts.push(`Atk+${atkPct}%`);
    }
    if (stats.store_tp) parts.push(`STP+${stats.store_tp}`);
    if (stats.double_attack) parts.push(`DA+${stats.double_attack}%`);
    if (stats.crit_rate) parts.push(`Crit+${stats.crit_rate}%`);
    if (stats.accuracy) parts.push(`Acc+${stats.accuracy}`);
    if (stats.magic_attack) parts.push(`MAB+${stats.magic_attack}`);
    if (stats.regain) parts.push(`Regain+${stats.regain}`);
    
    if (parts.length > 0) {
        return `${name} (${parts.join(' ')})`;
    }
    return name;
}

/**
 * Populate GEO bubble selector with optgroups
 */
function populateGeoSelector(tabPrefix, geoBubbles) {
    const select = document.getElementById(`${tabPrefix}-geo-bubble-add`);
    if (!select || !geoBubbles) return;
    
    select.innerHTML = '<option value="">Add bubble...</option>';
    
    // Group bubbles by type
    const groups = {
        'Geo (Full)': [],
        'Indi': [],
        'Entrust': []
    };
    
    for (const [name, stats] of Object.entries(geoBubbles)) {
        const entry = { name, stats };
        
        if (name.startsWith('Geo-')) {
            groups['Geo (Full)'].push(entry);
        } else if (name.startsWith('Entrust')) {
            groups['Entrust'].push(entry);
        } else if (name.startsWith('Indi-')) {
            groups['Indi'].push(entry);
        }
    }
    
    // Create optgroups
    for (const [groupName, bubbles] of Object.entries(groups)) {
        if (bubbles.length === 0) continue;
        
        const optgroup = document.createElement('optgroup');
        optgroup.label = groupName;
        
        for (const bubble of bubbles) {
            const option = document.createElement('option');
            option.value = bubble.name;
            option.textContent = formatGeoLabel(bubble.name, bubble.stats);
            optgroup.appendChild(option);
        }
        
        select.appendChild(optgroup);
    }
}

/**
 * Format GEO bubble label
 */
function formatGeoLabel(name, stats) {
    const parts = [];
    if (stats.attack_pct) {
        const atkPct = Math.round(stats.attack_pct * 100);
        parts.push(`Atk+${atkPct}%`);
    }
    if (stats.magic_haste) {
        const hastePct = Math.round(stats.magic_haste * 100);
        parts.push(`Haste+${hastePct}%`);
    }
    if (stats.accuracy) parts.push(`Acc+${stats.accuracy}`);
    if (stats.STR) parts.push(`STR+${stats.STR}`);
    if (stats.DEX) parts.push(`DEX+${stats.DEX}`);
    if (stats.VIT) parts.push(`VIT+${stats.VIT}`);
    if (stats.AGI) parts.push(`AGI+${stats.AGI}`);
    if (stats.magic_attack) parts.push(`MAB+${stats.magic_attack}`);
    
    if (parts.length > 0) {
        return `${name} (${parts.join(' ')})`;
    }
    return name;
}

/**
 * Populate WHM spell selector
 */
function populateWhmSelector(tabPrefix, whmSpells) {
    const select = document.getElementById(`${tabPrefix}-whm-spell-add`);
    if (!select || !whmSpells) return;
    
    select.innerHTML = '<option value="">Add spell...</option>';
    
    // Group spells by type
    const groups = {
        'Haste': [],
        'Boost': [],
        'Gain': [],
        'Storms': [],
        'Other': []
    };
    
    for (const [name, stats] of Object.entries(whmSpells)) {
        const entry = { name, stats };
        
        if (name.includes('Haste')) {
            groups['Haste'].push(entry);
        } else if (name.startsWith('Boost-')) {
            groups['Boost'].push(entry);
        } else if (name.startsWith('Gain-')) {
            groups['Gain'].push(entry);
        } else if (name.includes('storm')) {
            groups['Storms'].push(entry);
        } else {
            groups['Other'].push(entry);
        }
    }
    
    // Create optgroups
    for (const [groupName, spells] of Object.entries(groups)) {
        if (spells.length === 0) continue;
        
        const optgroup = document.createElement('optgroup');
        optgroup.label = groupName;
        
        for (const spell of spells) {
            const option = document.createElement('option');
            option.value = spell.name;
            option.textContent = formatWhmLabel(spell.name, spell.stats);
            optgroup.appendChild(option);
        }
        
        select.appendChild(optgroup);
    }
}

/**
 * Format WHM spell label
 */
function formatWhmLabel(name, stats) {
    const parts = [];
    if (stats.magic_haste) {
        const hastePct = Math.round(stats.magic_haste * 100);
        parts.push(`Haste+${hastePct}%`);
    }
    if (stats.STR) parts.push(`STR+${stats.STR}`);
    if (stats.DEX) parts.push(`DEX+${stats.DEX}`);
    if (stats.VIT) parts.push(`VIT+${stats.VIT}`);
    if (stats.AGI) parts.push(`AGI+${stats.AGI}`);
    if (stats.mdt) parts.push(`MDT${stats.mdt}%`);
    
    if (parts.length > 0) {
        return `${name} (${parts.join(' ')})`;
    }
    return name;
}

/**
 * Populate Job Abilities selector based on main/sub job
 * This is called when job selection changes
 */
function populateAbilitiesSelector(tabPrefix) {
    const select = document.getElementById(`${tabPrefix}-ability-add`);
    if (!select) return;
    
    const abilities = AppState.physicalBuffData?.abilities;
    if (!abilities) {
        select.innerHTML = '<option value="">No abilities data</option>';
        return;
    }
    
    const mainJob = AppState.selectedJob?.toLowerCase() || '';
    const subJob = AppState.selectedSubJob?.toLowerCase() || '';
    
    select.innerHTML = '<option value="">Add ability...</option>';
    
    if (!mainJob) {
        select.innerHTML = '<option value="">Select a job first...</option>';
        return;
    }
    
    // Group abilities by job
    const mainJobAbilities = [];
    const subJobAbilities = [];
    
    for (const [name, info] of Object.entries(abilities)) {
        const abilityJob = info.job?.toLowerCase();
        
        // Skip 2HR abilities
        if (info.is_2hr) continue;
        
        // Check if available for main job
        if (abilityJob === mainJob) {
            mainJobAbilities.push({ name, info });
            continue;
        }
        
        // Check if available for sub job (not main_only)
        if (abilityJob === subJob && !info.main_only) {
            subJobAbilities.push({ name, info, fromSub: true });
        }
    }
    
    // Add main job abilities group
    if (mainJobAbilities.length > 0) {
        const optgroup = document.createElement('optgroup');
        optgroup.label = `${mainJob.toUpperCase()} Abilities`;
        
        for (const ability of mainJobAbilities) {
            const option = document.createElement('option');
            option.value = ability.name;
            option.textContent = ability.name;
            if (ability.info.description) {
                option.title = ability.info.description;
            }
            optgroup.appendChild(option);
        }
        
        select.appendChild(optgroup);
    }
    
    // Add sub job abilities group
    if (subJobAbilities.length > 0) {
        const optgroup = document.createElement('optgroup');
        optgroup.label = `${subJob.toUpperCase()} (Sub) Abilities`;
        
        for (const ability of subJobAbilities) {
            const option = document.createElement('option');
            option.value = ability.name;
            option.textContent = `${ability.name}`;
            if (ability.info.description) {
                option.title = ability.info.description;
            }
            optgroup.appendChild(option);
        }
        
        select.appendChild(optgroup);
    }
    
    // If no abilities available
    if (mainJobAbilities.length === 0 && subJobAbilities.length === 0) {
        select.innerHTML = '<option value="">No abilities for this job combo</option>';
    }
}

/**
 * Add an ability to the list for a tab
 */
function addTabAbilityToList(tabPrefix, abilityName) {
    if (AppState[tabPrefix].abilities.includes(abilityName)) {
        showToast(`${abilityName} is already added`, 'warning');
        return;
    }
    
    AppState[tabPrefix].abilities.push(abilityName);
    
    const list = document.getElementById(`${tabPrefix}-abilities-list`);
    if (list) {
        const abilities = AppState.physicalBuffData?.abilities || {};
        const abilityInfo = abilities[abilityName] || {};
        
        const item = document.createElement('div');
        item.className = 'ability-item flex items-center justify-between bg-ffxi-dark rounded px-2 py-1';
        item.dataset.abilityName = abilityName;
        item.dataset.tabPrefix = tabPrefix;
        
        const textContainer = document.createElement('div');
        textContainer.className = 'flex flex-col';
        
        const nameSpan = document.createElement('span');
        nameSpan.className = 'text-xs text-ffxi-text';
        nameSpan.textContent = abilityName;
        
        textContainer.appendChild(nameSpan);
        
        // Add description as subtitle if available
        if (abilityInfo.description) {
            const descSpan = document.createElement('span');
            descSpan.className = 'text-xs text-ffxi-text-dim truncate max-w-[200px]';
            descSpan.textContent = abilityInfo.description;
            descSpan.title = abilityInfo.description;
            textContainer.appendChild(descSpan);
        }
        
        const btn = document.createElement('button');
        btn.className = 'text-ffxi-red hover:text-red-400 text-sm ml-2 flex-shrink-0';
        btn.textContent = '×';
        btn.addEventListener('click', () => removeTabAbilityFromList(tabPrefix, abilityName));
        
        item.appendChild(textContainer);
        item.appendChild(btn);
        list.appendChild(item);
    }
}

/**
 * Remove an ability from the list for a tab
 */
function removeTabAbilityFromList(tabPrefix, abilityName) {
    AppState[tabPrefix].abilities = AppState[tabPrefix].abilities.filter(a => a !== abilityName);
    
    const list = document.getElementById(`${tabPrefix}-abilities-list`);
    const escapedName = CSS.escape(abilityName);
    const item = list?.querySelector(`[data-ability-name="${escapedName}"]`);
    if (item) item.remove();
}

/**
 * Clear all abilities for a tab (used when job changes)
 */
function clearTabAbilities(tabPrefix) {
    AppState[tabPrefix].abilities = [];
    const list = document.getElementById(`${tabPrefix}-abilities-list`);
    if (list) {
        list.innerHTML = '';
    }
}

/**
 * Refresh abilities selectors for all tabs (call when job changes)
 */
function refreshAbilitiesSelectors() {
    ['tp', 'ws'].forEach(tabPrefix => {
        // Clear existing abilities since job changed
        clearTabAbilities(tabPrefix);
        // Repopulate the dropdown
        populateAbilitiesSelector(tabPrefix);
    });
}

/**
 * Populate debuff selector
 */
function populateDebuffSelector(tabPrefix, debuffs) {
    const select = document.getElementById(`${tabPrefix}-debuff-add`);
    if (!select || !debuffs) return;
    
    select.innerHTML = '<option value="">Add debuff...</option>';
    
    // Process each debuff category
    for (const [category, categoryDebuffs] of Object.entries(debuffs)) {
        const optgroup = document.createElement('optgroup');
        optgroup.label = category.toUpperCase();
        
        for (const [name, stats] of Object.entries(categoryDebuffs)) {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = formatDebuffLabel(name, stats);
            optgroup.appendChild(option);
        }
        
        select.appendChild(optgroup);
    }
}

/**
 * Format debuff label
 */
function formatDebuffLabel(name, stats) {
    const parts = [];
    if (stats.defense_down_pct) {
        const defPct = Math.round(stats.defense_down_pct * 100);
        parts.push(`Def-${defPct}%`);
    }
    if (stats.evasion_down) parts.push(`Eva-${stats.evasion_down}`);
    if (stats.magic_defense_down) parts.push(`MDef-${stats.magic_defense_down}`);
    
    if (parts.length > 0) {
        return `${name} (${parts.join(' ')})`;
    }
    return name;
}

/**
 * Populate target selector
 */
function populateTargetSelector(tabPrefix, targets) {
    const select = document.getElementById(`${tabPrefix}-target-preset`);
    if (!select || !targets) return;
    
    select.innerHTML = '';
    
    for (const [id, target] of Object.entries(targets)) {
        const option = document.createElement('option');
        option.value = id;
        option.textContent = `${target.name} (Lv${target.level})`;
        select.appendChild(option);
    }
    
    // Set default
    if (targets['apex_toad']) {
        select.value = 'apex_toad';
    }
}

/**
 * Populate all magic buff selectors from API data.
 * Call this during magic tab initialization.
 */
async function populateMagicBuffSelectors() {
    try {
        // Fetch magic buff data from API
        const data = await API.getMagicBuffs();
        if (!data || !data.buffs) {
            console.error('Failed to load magic buff data');
            return;
        }
        
        // Cache the data
        AppState.magicBuffData = data;
        
        // Populate magic-specific selectors (matching new HTML IDs)
        populateMagicFoodSelector(data.buffs.food);
        populateMagicBrdSelector(data.buffs.brd);
        populateMagicCorSelector(data.buffs.cor);
        populateMagicGeoSelector(data.buffs.geo);
        populateMagicSchSelector(data.buffs.sch);
        populateMagicWhmSelector(data.buffs.whm);
        populateMagicDebuffSelector(data.debuffs);
        populateMagicTargetSelector(data.targets);
        
        console.log('Magic buff selectors populated');
        
    } catch (error) {
        console.error('Error populating magic buff selectors:', error);
    }
}

/**
 * Populate magic food selector
 */
function populateMagicFoodSelector(foods) {
    const select = document.getElementById('magic-food-select');
    if (!select || !foods) return;
    
    select.innerHTML = '<option value="">No Food</option>';
    
    for (const [name, stats] of Object.entries(foods)) {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = formatMagicFoodLabel(name, stats);
        select.appendChild(option);
    }
}

/**
 * Format magic food label
 */
function formatMagicFoodLabel(name, stats) {
    const parts = [];
    if (stats.INT) parts.push(`INT+${stats.INT}`);
    if (stats.MND) parts.push(`MND+${stats.MND}`);
    if (stats.magic_attack) parts.push(`MAB+${stats.magic_attack}`);
    if (stats.magic_accuracy) parts.push(`M.Acc+${stats.magic_accuracy}`);
    
    if (parts.length > 0) {
        return `${name} (${parts.join(' ')})`;
    }
    return name;
}

/**
 * Populate magic BRD selector
 */
function populateMagicBrdSelector(songs) {
    const select = document.getElementById('magic-brd-song-add');
    if (!select || !songs) return;
    
    select.innerHTML = '<option value="">Add song...</option>';
    
    for (const [name, stats] of Object.entries(songs)) {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = formatMagicBrdLabel(name, stats);
        select.appendChild(option);
    }
}

function formatMagicBrdLabel(name, stats) {
    const parts = [];
    if (stats.INT) parts.push(`INT+${stats.INT}`);
    if (stats.MND) parts.push(`MND+${stats.MND}`);
    
    if (parts.length > 0) {
        return `${name} (${parts.join(' ')})`;
    }
    return name;
}

/**
 * Populate magic COR selector
 */
function populateMagicCorSelector(rolls) {
    const select = document.getElementById('magic-cor-roll-add');
    if (!select || !rolls) return;
    
    select.innerHTML = '<option value="">Add roll...</option>';
    
    for (const [name, stats] of Object.entries(rolls)) {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = formatMagicCorLabel(name, stats);
        select.appendChild(option);
    }
}

function formatMagicCorLabel(name, stats) {
    const parts = [];
    if (stats.magic_attack) parts.push(`MAB+${stats.magic_attack}`);
    if (stats.magic_accuracy) parts.push(`M.Acc+${stats.magic_accuracy}`);
    if (stats.refresh) parts.push(`Refresh+${stats.refresh}`);
    
    if (parts.length > 0) {
        return `${name} (${parts.join(' ')})`;
    }
    return name;
}

/**
 * Populate magic GEO selector
 */
function populateMagicGeoSelector(bubbles) {
    const select = document.getElementById('magic-geo-bubble-add');
    if (!select || !bubbles) return;
    
    select.innerHTML = '<option value="">Add bubble...</option>';
    
    // Group by type
    const groups = {
        'Geo (Full)': [],
        'Indi': [],
        'Entrust': []
    };
    
    for (const [name, stats] of Object.entries(bubbles)) {
        const entry = { name, stats };
        
        if (name.startsWith('Geo-')) {
            groups['Geo (Full)'].push(entry);
        } else if (name.startsWith('Entrust')) {
            groups['Entrust'].push(entry);
        } else if (name.startsWith('Indi-')) {
            groups['Indi'].push(entry);
        }
    }
    
    for (const [groupName, items] of Object.entries(groups)) {
        if (items.length === 0) continue;
        
        const optgroup = document.createElement('optgroup');
        optgroup.label = groupName;
        
        for (const item of items) {
            const option = document.createElement('option');
            option.value = item.name;
            option.textContent = formatMagicGeoLabel(item.name, item.stats);
            optgroup.appendChild(option);
        }
        
        select.appendChild(optgroup);
    }
}

function formatMagicGeoLabel(name, stats) {
    const parts = [];
    if (stats.magic_attack_pct) parts.push(`MAB+${stats.magic_attack_pct}%`);
    if (stats.magic_accuracy) parts.push(`M.Acc+${stats.magic_accuracy}`);
    if (stats.INT) parts.push(`INT+${stats.INT}`);
    if (stats.MND) parts.push(`MND+${stats.MND}`);
    if (stats.refresh) parts.push(`Refresh+${stats.refresh}`);
    
    if (parts.length > 0) {
        return `${name} (${parts.join(' ')})`;
    }
    return name;
}

/**
 * Populate SCH abilities selector
 */
function populateMagicSchSelector(abilities) {
    const select = document.getElementById('magic-sch-ability-add');
    if (!select || !abilities) return;
    
    select.innerHTML = '<option value="">Add ability...</option>';
    
    for (const [name, stats] of Object.entries(abilities)) {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = formatSchLabel(name, stats);
        select.appendChild(option);
    }
}

function formatSchLabel(name, stats) {
    if (stats.description) {
        return `${name} (${stats.description})`;
    }
    
    const parts = [];
    if (stats.magic_damage_mult) parts.push(`+${stats.magic_damage_mult}% dmg`);
    if (stats.magic_attack) parts.push(`MAB+${stats.magic_attack}`);
    
    if (parts.length > 0) {
        return `${name} (${parts.join(' ')})`;
    }
    return name;
}

/**
 * Populate WHM spells selector for magic tab
 */
function populateMagicWhmSelector(spells) {
    const select = document.getElementById('magic-whm-spell-add');
    if (!select) return;
    
    select.innerHTML = '<option value="">Add spell...</option>';
    
    if (!spells) return;
    
    for (const [name, stats] of Object.entries(spells)) {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = formatMagicWhmLabel(name, stats);
        select.appendChild(option);
    }
}

function formatMagicWhmLabel(name, stats) {
    if (stats.description) {
        return `${name} (${stats.description})`;
    }
    
    const parts = [];
    if (stats.INT) parts.push(`INT+${stats.INT}`);
    if (stats.MND) parts.push(`MND+${stats.MND}`);
    if (stats.magic_attack) parts.push(`MAB+${stats.magic_attack}`);
    
    if (parts.length > 0) {
        return `${name} (${parts.join(' ')})`;
    }
    return name;
}

/**
 * Populate magic debuff selector
 */
function populateMagicDebuffSelector(debuffs) {
    const select = document.getElementById('magic-debuff-add');
    if (!select || !debuffs) return;
    
    select.innerHTML = '<option value="">Add debuff...</option>';
    
    for (const [category, categoryDebuffs] of Object.entries(debuffs)) {
        const optgroup = document.createElement('optgroup');
        optgroup.label = category.toUpperCase();
        
        for (const [name, stats] of Object.entries(categoryDebuffs)) {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = formatMagicDebuffLabel(name, stats);
            optgroup.appendChild(option);
        }
        
        select.appendChild(optgroup);
    }
}

function formatMagicDebuffLabel(name, stats) {
    const parts = [];
    if (stats.magic_evasion_down) parts.push(`M.Eva-${stats.magic_evasion_down}`);
    if (stats.magic_defense_down) parts.push(`M.Def-${stats.magic_defense_down}`);
    
    if (parts.length > 0) {
        return `${name} (${parts.join(' ')})`;
    }
    return name;
}

/**
 * Populate magic target selector.
 * Accepts either an array of target objects (from /api/magic/targets)
 * or a plain object keyed by id (legacy).
 */
function populateMagicTargetSelector(targets) {
    const select = document.getElementById('magic-target-select');
    if (!select || !targets) return;

    // Normalise to array
    const list = Array.isArray(targets)
        ? targets
        : Object.entries(targets).map(([id, t]) => ({ id, ...t }));

    if (list.length === 0) return;

    select.innerHTML = '';

    const SORTIE_FLOOR_IDS    = ['sortie_ghatjot','sortie_leshonn','sortie_skomora','sortie_degei'];
    const SORTIE_BASEMENT_IDS = ['sortie_dhartok','sortie_gartell','sortie_triboulex','sortie_aita'];
    const sortieIds = new Set([...SORTIE_FLOOR_IDS, ...SORTIE_BASEMENT_IDS, 'sortie_boss']);

    // Generic targets (non-Sortie), sorted by MEva
    const generic = list.filter(t => !sortieIds.has(t.id)).sort((a, b) => a.magic_evasion - b.magic_evasion);
    generic.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.id;
        opt.textContent = `${t.name} (${t.magic_evasion} MEva)`;
        select.appendChild(opt);
    });

    // Sortie floor bosses
    const floorBosses = list.filter(t => SORTIE_FLOOR_IDS.includes(t.id));
    if (floorBosses.length > 0) {
        const grp = document.createElement('optgroup');
        grp.label = 'Sortie Floor Bosses (2000 Gal)';
        floorBosses.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.textContent = `${t.name} (${t.magic_evasion} MEva)`;
            grp.appendChild(opt);
        });
        select.appendChild(grp);
    }

    // Sortie basement bosses
    const basementBosses = list.filter(t => SORTIE_BASEMENT_IDS.includes(t.id));
    if (basementBosses.length > 0) {
        const grp = document.createElement('optgroup');
        grp.label = 'Sortie Basement Bosses (10000 Gal)';
        basementBosses.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.textContent = `${t.name} (${t.magic_evasion} MEva)`;
            grp.appendChild(opt);
        });
        select.appendChild(grp);
    }

    // Set default to apex_mob
    const apexOpt = list.find(t => t.id === 'apex_mob');
    if (apexOpt) select.value = 'apex_mob';
}

/**
 * Look up a physical buff's stats by name.
 * @param {string} category - 'brd', 'cor', 'geo', 'whm', 'food', 'abilities'
 * @param {string} name - Buff name
 * @returns {object|null} Buff stats or null if not found
 */
function getPhysicalBuffStats(category, name) {
    if (!AppState.physicalBuffData?.buffs?.[category]) return null;
    return AppState.physicalBuffData.buffs[category][name] || null;
}

/**
 * Look up a magic buff's stats by name.
 * @param {string} category - 'brd', 'cor', 'geo', 'sch', 'whm', 'food'
 * @param {string} name - Buff name
 * @returns {object|null} Buff stats or null if not found
 */
function getMagicBuffStats(category, name) {
    if (!AppState.magicBuffData?.buffs?.[category]) return null;
    return AppState.magicBuffData.buffs[category][name] || null;
}

// =============================================================================
// UI HELPERS
// =============================================================================

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type} animate-slide-in`;
    
    const colors = {
        success: 'bg-ffxi-green',
        error: 'bg-ffxi-red',
        warning: 'bg-yellow-600',
        info: 'bg-ffxi-blue',
    };
    
    toast.innerHTML = `
        <div class="${colors[type] || colors.info} px-4 py-3 rounded shadow-lg">
            <p class="text-white text-sm">${message}</p>
        </div>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('animate-slide-out');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function updateStatusIndicator(status) {
    const indicator = document.getElementById('status-indicator');
    if (!indicator) return;
    
    if (status === 'ready') {
        indicator.textContent = 'Ready';
        indicator.className = 'text-xs px-2 py-1 rounded bg-ffxi-green/20 text-ffxi-green';
    } else if (status === 'loading') {
        indicator.textContent = 'Loading...';
        indicator.className = 'text-xs px-2 py-1 rounded bg-ffxi-accent/20 text-ffxi-accent';
    } else if (status === 'cached') {
        indicator.textContent = 'Cached Data';
        indicator.className = 'text-xs px-2 py-1 rounded bg-ffxi-blue/20 text-ffxi-blue';
    } else {
        indicator.textContent = 'No Inventory';
        indicator.className = 'text-xs px-2 py-1 rounded bg-ffxi-dark text-ffxi-text-dim';
    }
}

function populateSelect(selectId, options, placeholder = 'Select...') {
    const select = document.getElementById(selectId);
    if (!select) return;
    
    select.innerHTML = `<option value="">${placeholder}</option>`;
    
    for (const opt of options) {
        const option = document.createElement('option');
        option.value = opt.value;
        option.textContent = opt.label;
        if (opt.disabled) option.disabled = true;
        select.appendChild(option);
    }
}

function createSearchableDropdown(containerId, options, onSelect, placeholder = 'Search...') {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    container.innerHTML = `
        <div class="searchable-dropdown">
            <input type="text" 
                   class="input-field w-full" 
                   placeholder="${placeholder}"
                   autocomplete="off">
            <div class="dropdown-list hidden"></div>
        </div>
    `;
    
    const input = container.querySelector('input');
    const list = container.querySelector('.dropdown-list');
    
    function renderOptions(filter = '') {
        const filtered = options.filter(opt => 
            opt.label.toLowerCase().includes(filter.toLowerCase())
        );
        
        list.innerHTML = filtered.slice(0, 50).map(opt => `
            <div class="dropdown-item" data-value="${opt.value}">
                <span class="font-medium">${opt.label}</span>
                ${opt.sublabel ? `<span class="text-xs text-ffxi-text-dim ml-2">${opt.sublabel}</span>` : ''}
            </div>
        `).join('');
        
        // Add click handlers
        list.querySelectorAll('.dropdown-item').forEach(item => {
            item.addEventListener('click', () => {
                const value = item.dataset.value;
                const opt = options.find(o => o.value === value);
                if (opt) {
                    input.value = opt.label;
                    list.classList.add('hidden');
                    onSelect(opt);
                }
            });
        });
    }
    
    input.addEventListener('focus', () => {
        renderOptions(input.value);
        list.classList.remove('hidden');
    });
    
    input.addEventListener('input', () => {
        renderOptions(input.value);
        list.classList.remove('hidden');
    });
    
    input.addEventListener('blur', () => {
        // Delay to allow click on dropdown item
        setTimeout(() => {
            // Guard: if the input was removed from the DOM (dropdown recreated), do nothing
            if (!document.contains(input)) return;
            list.classList.add('hidden');
            // If the input is empty or doesn't match any option, clear the selection
            const trimmed = input.value.trim();
            if (trimmed === '') {
                onSelect(null);
            } else {
                const match = options.find(o => o.label.toLowerCase() === trimmed.toLowerCase());
                if (!match) {
                    // Text doesn't match any valid option — clear it
                    input.value = '';
                    onSelect(null);
                }
            }
        }, 200);
    });
    
    renderOptions();
    
    return {
        setValue(label) {
            input.value = label || '';
        },
        clear() {
            input.value = '';
        }
    };
}

// =============================================================================
// INITIALIZATION
// =============================================================================

async function initializeApp() {
    console.log('Initializing FFXI Gear Optimizer...');
    
    // Restore saved data from localStorage first
    await restoreSavedData();
    
    // Check API status
    try {
        const status = await API.getStatus();
        AppState.inventoryLoaded = status.inventory_loaded;
        AppState.jobGiftsLoaded = status.job_gifts_loaded;
        AppState.wsdistAvailable = status.wsdist_available;
        
        if (status.inventory_loaded) {
            updateStatusIndicator('ready');
            updateInventorySummary(status.item_count, status.inventory_filename);
        } else {
            // Check if we have cached inventory data to reload
            const cachedInventory = loadFromLocalStorage(STORAGE_KEYS.INVENTORY_DATA);
            if (cachedInventory) {
                updateStatusIndicator('cached');
                // Try to reload from cache
                await reloadCachedInventory();
            } else {
                updateStatusIndicator('no_inventory');
            }
        }
        
        // Check for cached job gifts if not loaded
        if (!status.job_gifts_loaded) {
            const cachedJobGifts = loadFromLocalStorage(STORAGE_KEYS.JOB_GIFTS_DATA);
            if (cachedJobGifts) {
                await reloadCachedJobGifts();
            }
        } else {
            // Update job gifts upload status indicator
            const jpStatus = document.getElementById('jobgifts-upload-status');
            if (jpStatus) {
                jpStatus.textContent = 'Loaded';
                jpStatus.className = 'text-xs px-2 py-0.5 rounded bg-ffxi-green/20 text-ffxi-green';
            }
        }
        
    } catch (error) {
        console.error('Failed to connect to API:', error);
        showToast('Failed to connect to server', 'error');
    }
    
    // Load buff data and populate selectors
    await populatePhysicalBuffSelectors();
    
    // Setup event listeners
    setupEventListeners();
    
    // Initialize inventory browser
    InventoryBrowser.init();
    
    // Initialize Lua optimizer
    LuaOptimizer.init();
    
    // Initialize Set Builder
    SetBuilder.init();
    
    // Restore job/weapon selections after event listeners are set up
    await restoreSelections();
    
    // Hide loading overlay
    const overlay = document.getElementById('loading-overlay');
    const app = document.getElementById('app');
    if (overlay && app) {
        overlay.classList.add('hidden');
        app.classList.remove('opacity-0');
    }
}

async function restoreSavedData() {
    // Restore sub job
    const savedSubJob = loadFromLocalStorage(STORAGE_KEYS.SUBJOB);
    if (savedSubJob) {
        AppState.selectedSubJob = savedSubJob.toLowerCase();
        const subjobSelect = document.getElementById('subjob-select');
        if (subjobSelect) {
            subjobSelect.value = savedSubJob.toUpperCase();
        }
    }
    
    // Restore master level
    const savedMasterLevel = loadFromLocalStorage(STORAGE_KEYS.MASTER_LEVEL);
    if (savedMasterLevel !== null) {
        AppState.masterLevel = parseInt(savedMasterLevel) || 0;
    }
}

async function restoreSelections() {
    // Only restore job if we have inventory loaded
    if (!AppState.inventoryLoaded) return;
    
    const savedJob = loadFromLocalStorage(STORAGE_KEYS.JOB);
    if (savedJob) {
        const jobSelect = document.getElementById('job-select');
        if (jobSelect) {
            jobSelect.value = savedJob;
            // Trigger the job change handler to load weapons
            await handleJobChange({ target: { value: savedJob } });
            
            // After weapons are loaded, try to restore weapon selection
            const savedMainWeapon = loadFromLocalStorage(STORAGE_KEYS.MAIN_WEAPON);
            if (savedMainWeapon && AppState.weapons.length > 0) {
                // Find the weapon in the loaded weapons
                const weapon = AppState.weapons.find(w => w.name === savedMainWeapon);
                if (weapon) {
                    // Programmatically select the weapon
                    await handleMainWeaponSelect({
                        value: weapon.name,
                        label: weapon.name2 || weapon.name,
                        data: weapon
                    });
                    // Set the dropdown input text
                    if (AppState.dropdowns.mainWeapon) {
                        AppState.dropdowns.mainWeapon.setValue(weapon.name2 || weapon.name);
                    }
                }
            }
            
            // Restore ranged weapon selection
            const savedRanged = loadFromLocalStorage(STORAGE_KEYS.RANGED_WEAPON);
            if (savedRanged && AppState.rangedWeapons.length > 0) {
                const ranged = AppState.rangedWeapons.find(w => w.name === savedRanged);
                if (ranged) {
                    handleRangedWeaponSelect({
                        value: ranged.name,
                        label: ranged.name2 || ranged.name,
                        data: ranged
                    });
                    if (AppState.dropdowns.rangedWeapon) {
                        AppState.dropdowns.rangedWeapon.setValue(ranged.name2 || ranged.name);
                    }
                }
            }
            
            // Restore ammo selection
            const savedAmmo = loadFromLocalStorage(STORAGE_KEYS.AMMO);
            if (savedAmmo && AppState.ammoItems.length > 0) {
                const ammo = AppState.ammoItems.find(a => a.name === savedAmmo);
                if (ammo) {
                    handleAmmoSelect({
                        value: ammo.name,
                        label: ammo.name2 || ammo.name,
                        data: {
                            ...ammo,
                            _raw: {
                                Name: ammo.name,
                                Name2: ammo.name2,
                                Type: ammo.type,
                                'Item Level': ammo.item_level,
                                Jobs: ammo.jobs,
                                ...ammo.stats,
                            },
                        }
                    });
                    if (AppState.dropdowns.ammo) {
                        AppState.dropdowns.ammo.setValue(ammo.name2 || ammo.name);
                    }
                }
            }
        }
    }
    
    // Update DW hint after job/subjob is restored
    updateDWHint();
    
    // Update SetBuilder's job display after restoration
    // (The DOM event listener doesn't fire for programmatic changes)
    if (typeof SetBuilder !== 'undefined' && SetBuilder.updateJobDisplay) {
        SetBuilder.updateJobDisplay();
    }
}

async function reloadCachedInventory() {
    const cachedData = loadFromLocalStorage(STORAGE_KEYS.INVENTORY_DATA);
    const cachedChar = loadFromLocalStorage(STORAGE_KEYS.INVENTORY_CHAR);
    
    if (!cachedData) return false;
    
    // Check if it's the new format (CSV string) or old format (array of items)
    if (typeof cachedData !== 'string') {
        // Old format - clear it and ask user to re-upload
        console.warn('Old cache format detected, clearing...');
        clearStoredInventory();
        showToast('Cache format updated. Please re-upload your inventory.', 'info');
        return false;
    }
    
    try {
        // Send cached CSV content to API to reload
        // The API will re-parse it just like the original upload
        const response = await fetch('/api/upload/inventory/reload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                csv_content: cachedData,
                character_name: cachedChar 
            }),
        });
        
        const result = await response.json();
        
        if (result.success) {
            AppState.inventoryLoaded = true;
            // Clear cached earring abbreviations so they rebuild from new inventory
            empyreanEarringAbbrevPrefixes.clear();
            updateStatusIndicator('ready');
            updateInventorySummary(result.item_count, cachedChar || 'Cached');
            showToast('Restored inventory from cache', 'success');
            return true;
        } else {
            console.warn('Failed to reload cached inventory:', result.error);
            // Clear invalid cache
            clearStoredInventory();
        }
    } catch (error) {
        console.warn('Failed to reload cached inventory:', error);
        // Clear invalid cache
        clearStoredInventory();
    }
    
    return false;
}

async function reloadCachedJobGifts() {
    const cachedData = loadFromLocalStorage(STORAGE_KEYS.JOB_GIFTS_DATA);
    
    if (!cachedData) return false;
    
    try {
        // Send cached data to API to reload
        const response = await fetch('/api/upload/jobgifts/reload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ gifts: cachedData }),
        });
        
        const result = await response.json();
        
        if (result.success) {
            AppState.jobGiftsLoaded = true;
            
            // Update upload status indicator
            const status = document.getElementById('jobgifts-upload-status');
            if (status) {
                status.textContent = 'Cached';
                status.className = 'text-xs px-2 py-0.5 rounded bg-ffxi-blue/20 text-ffxi-blue';
            }
            
            showToast('Restored job points from cache', 'success');
            
            // Refresh jobs to show JP info
            await refreshJobInfo();
            return true;
        }
    } catch (error) {
        console.warn('Failed to reload cached job gifts:', error);
    }
    
    return false;
}

function setupEventListeners() {
    // Job selection
    const jobSelect = document.getElementById('job-select');
    if (jobSelect) {
        jobSelect.addEventListener('change', handleJobChange);
    }
    
    // Sub Job selection
    const subjobSelect = document.getElementById('subjob-select');
    if (subjobSelect) {
        subjobSelect.addEventListener('change', handleSubJobChange);
    }
    
    // Master level controls
    const mlSlider = document.getElementById('master-level-slider');
    const mlInput = document.getElementById('master-level-input');
    console.log('Master level elements:', { mlSlider, mlInput });
    if (mlSlider && mlInput) {
        mlSlider.addEventListener('input', (e) => {
            console.log('Slider changed to:', e.target.value);
            mlInput.value = e.target.value;
            updateMasterLevelBonuses(parseInt(e.target.value));
        });
        mlInput.addEventListener('change', (e) => {
            const val = Math.max(0, Math.min(50, parseInt(e.target.value) || 0));
            console.log('Input changed to:', val);
            e.target.value = val;
            mlSlider.value = val;
            updateMasterLevelBonuses(val);
        });
    }
    
    // Dual wield checkbox
    const dwCheckbox = document.getElementById('has-dual-wield');
    if (dwCheckbox) {
        dwCheckbox.addEventListener('change', (e) => {
            AppState.hasDualWield = e.target.checked;
        });
    }
    
    // WS Select
    const wsSelect = document.getElementById('ws-select');
    if (wsSelect) {
        wsSelect.addEventListener('change', handleWeaponskillChange);
    }
    
    // WS TP Level slider
    const wsTpSlider = document.getElementById('ws-tp-level');
    const wsTpDisplay = document.getElementById('ws-tp-display');
    if (wsTpSlider && wsTpDisplay) {
        wsTpSlider.addEventListener('input', (e) => {
            wsTpDisplay.textContent = `${e.target.value} TP`;
        });
    }
    
    // Upload button
    const uploadBtn = document.getElementById('btn-upload');
    if (uploadBtn) {
        uploadBtn.addEventListener('click', () => {
            const modal = document.getElementById('upload-modal');
            if (modal) modal.classList.remove('hidden');
        });
    }
    
    // Modal close buttons
    document.getElementById('btn-cancel-upload')?.addEventListener('click', () => {
        document.getElementById('upload-modal')?.classList.add('hidden');
    });
    
    // File upload dropzones
    setupFileUpload('upload-dropzone', 'file-input', handleInventoryUpload);
    setupFileUpload('jobgifts-dropzone', 'jobgifts-file-input', handleJobGiftsUpload);
    
    // Clear cache button
    document.getElementById('btn-clear-cache')?.addEventListener('click', handleClearCache);
    
    // Update cached data notice visibility
    updateCachedDataNotice();
    
    // Tab navigation
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => handleTabChange(btn.dataset.tab));
    });
    
    // Optimize buttons
    document.getElementById('btn-optimize-tp')?.addEventListener('click', runTPOptimization);
    document.getElementById('btn-optimize-ws')?.addEventListener('click', runWSOptimization);
    document.getElementById('btn-optimize-magic')?.addEventListener('click', runMagicOptimization);
    document.getElementById('btn-optimize-dt')?.addEventListener('click', runDTOptimization);

    // Slow mode toggles — show/hide advanced settings
    document.getElementById('tp-slow-mode')?.addEventListener('change', (e) => {
        document.getElementById('tp-slow-advanced')?.classList.toggle('hidden', !e.target.checked);
    });
    document.getElementById('ws-slow-mode')?.addEventListener('change', (e) => {
        document.getElementById('ws-slow-advanced')?.classList.toggle('hidden', !e.target.checked);
    });
    document.getElementById('magic-slow-mode')?.addEventListener('change', (e) => {
        document.getElementById('magic-slow-advanced')?.classList.toggle('hidden', !e.target.checked);
    });
    
    // DT type description update
    document.getElementById('dt-set-type')?.addEventListener('change', updateDTTypeDescription);
    
    // Populate DT set type dropdown dynamically from API
    populateDTTypeDropdown();
    
    // Copy Lua button
    document.getElementById('btn-copy-lua')?.addEventListener('click', copyLuaToClipboard);
    
    // Stats panel toggle
    document.getElementById('btn-toggle-stats')?.addEventListener('click', toggleStatsPanel);
    
    // Setup tab-specific buff selectors
    setupTabBuffSelectors('tp');
    setupTabBuffSelectors('ws');
    
    // Setup custom buff panels
    setupCustomBuffPanels();
    
    // WS Simulation toggle
    const wsSimToggle = document.getElementById('ws-use-simulation');
    if (wsSimToggle) {
        wsSimToggle.addEventListener('change', (e) => {
            AppState.ws.useSimulation = e.target.checked;
        });
    }
    
    // Setup magic tab
    setupMagicTab();
}

// =============================================================================
// TAB-SPECIFIC BUFF/DEBUFF MANAGEMENT
// =============================================================================

function setupTabBuffSelectors(tabPrefix) {
    // Food selector
    const foodSelect = document.getElementById(`${tabPrefix}-food-select`);
    if (foodSelect) {
        foodSelect.addEventListener('change', (e) => {
            AppState[tabPrefix].food = e.target.value;
        });
    }
    
    // BRD Songs
    const brdSelect = document.getElementById(`${tabPrefix}-brd-song-add`);
    if (brdSelect) {
        brdSelect.addEventListener('change', (e) => {
            if (e.target.value && AppState[tabPrefix].buffs.brd.length < 4) {
                addTabBuffToList(tabPrefix, 'brd', e.target.value);
                e.target.value = '';
                updateTabBuffCount(tabPrefix, 'brd');
            } else if (AppState[tabPrefix].buffs.brd.length >= 4) {
                showToast('Maximum 4 songs allowed', 'warning');
                e.target.value = '';
            }
        });
    }
    
    // COR Rolls
    const corSelect = document.getElementById(`${tabPrefix}-cor-roll-add`);
    if (corSelect) {
        corSelect.addEventListener('change', (e) => {
            if (e.target.value && AppState[tabPrefix].buffs.cor.length < 2) {
                addTabBuffToList(tabPrefix, 'cor', e.target.value);
                e.target.value = '';
                updateTabBuffCount(tabPrefix, 'cor');
            } else if (AppState[tabPrefix].buffs.cor.length >= 2) {
                showToast('Maximum 2 rolls allowed', 'warning');
                e.target.value = '';
            }
        });
    }
    
    // GEO Bubbles
    const geoSelect = document.getElementById(`${tabPrefix}-geo-bubble-add`);
    if (geoSelect) {
        geoSelect.addEventListener('change', (e) => {
            if (e.target.value && AppState[tabPrefix].buffs.geo.length < 3) {
                addTabBuffToList(tabPrefix, 'geo', e.target.value);
                e.target.value = '';
                updateTabBuffCount(tabPrefix, 'geo');
            } else if (AppState[tabPrefix].buffs.geo.length >= 3) {
                showToast('Maximum 3 bubbles allowed', 'warning');
                e.target.value = '';
            }
        });
    }
    
    // WHM Spells
    const whmSelect = document.getElementById(`${tabPrefix}-whm-spell-add`);
    if (whmSelect) {
        whmSelect.addEventListener('change', (e) => {
            if (e.target.value) {
                addTabBuffToList(tabPrefix, 'whm', e.target.value);
                e.target.value = '';
            }
        });
    }
    
    // Job Abilities (dropdown-based, not checkboxes)
    const abilitySelect = document.getElementById(`${tabPrefix}-ability-add`);
    if (abilitySelect) {
        abilitySelect.addEventListener('change', (e) => {
            if (e.target.value) {
                addTabAbilityToList(tabPrefix, e.target.value);
                e.target.value = '';
            }
        });
    }
    
    // Target selector
    const targetSelect = document.getElementById(`${tabPrefix}-target-preset`);
    if (targetSelect) {
        targetSelect.addEventListener('change', (e) => {
            AppState[tabPrefix].target = e.target.value;
        });
    }
    
    // Debuffs
    const debuffSelect = document.getElementById(`${tabPrefix}-debuff-add`);
    if (debuffSelect) {
        debuffSelect.addEventListener('change', (e) => {
            if (e.target.value) {
                addTabDebuffToList(tabPrefix, e.target.value);
                e.target.value = '';
            }
        });
    }
}

function addTabBuffToList(tabPrefix, category, buffName) {
    if (AppState[tabPrefix].buffs[category].includes(buffName)) {
        showToast(`${buffName} is already added`, 'warning');
        return;
    }
    
    AppState[tabPrefix].buffs[category].push(buffName);
    
    const listId = {
        brd: `${tabPrefix}-brd-songs-list`,
        cor: `${tabPrefix}-cor-rolls-list`,
        geo: `${tabPrefix}-geo-bubbles-list`,
        whm: `${tabPrefix}-whm-spells-list`,
    }[category];
    
    const list = document.getElementById(listId);
    if (list) {
        const item = document.createElement('div');
        item.className = 'buff-item flex items-center justify-between bg-ffxi-dark rounded px-2 py-1';
        item.dataset.buffName = buffName;
        item.dataset.category = category;
        item.dataset.tabPrefix = tabPrefix;
        
        const span = document.createElement('span');
        span.className = 'text-xs';
        span.textContent = buffName;
        
        const btn = document.createElement('button');
        btn.className = 'text-ffxi-red hover:text-red-400 text-sm ml-2';
        btn.textContent = '×';
        btn.addEventListener('click', () => removeTabBuffFromList(tabPrefix, category, buffName));
        
        item.appendChild(span);
        item.appendChild(btn);
        list.appendChild(item);
    }
}

function removeTabBuffFromList(tabPrefix, category, buffName) {
    AppState[tabPrefix].buffs[category] = AppState[tabPrefix].buffs[category].filter(b => b !== buffName);
    
    const listId = {
        brd: `${tabPrefix}-brd-songs-list`,
        cor: `${tabPrefix}-cor-rolls-list`,
        geo: `${tabPrefix}-geo-bubbles-list`,
        whm: `${tabPrefix}-whm-spells-list`,
    }[category];
    
    const list = document.getElementById(listId);
    const escapedName = CSS.escape(buffName);
    const item = list?.querySelector(`[data-buff-name="${escapedName}"]`);
    if (item) item.remove();
    
    updateTabBuffCount(tabPrefix, category);
}

function updateTabBuffCount(tabPrefix, category) {
    const countId = {
        brd: `${tabPrefix}-brd-song-count`,
        cor: `${tabPrefix}-cor-roll-count`,
        geo: `${tabPrefix}-geo-bubble-count`,
    }[category];
    
    const maxCount = { brd: 4, cor: 2, geo: 3 }[category];
    
    const countEl = document.getElementById(countId);
    if (countEl) {
        countEl.textContent = `${AppState[tabPrefix].buffs[category].length}/${maxCount}`;
    }
}

function addTabDebuffToList(tabPrefix, debuffName) {
    if (AppState[tabPrefix].debuffs.includes(debuffName)) {
        showToast(`${debuffName} is already added`, 'warning');
        return;
    }
    
    AppState[tabPrefix].debuffs.push(debuffName);
    
    const list = document.getElementById(`${tabPrefix}-debuffs-list`);
    if (list) {
        const item = document.createElement('div');
        item.className = 'debuff-item flex items-center justify-between bg-ffxi-dark rounded px-2 py-1';
        item.dataset.debuffName = debuffName;
        item.dataset.tabPrefix = tabPrefix;
        
        const span = document.createElement('span');
        span.className = 'text-xs';
        span.textContent = debuffName;
        
        const btn = document.createElement('button');
        btn.className = 'text-ffxi-red hover:text-red-400 text-sm ml-2';
        btn.textContent = '×';
        btn.addEventListener('click', () => removeTabDebuffFromList(tabPrefix, debuffName));
        
        item.appendChild(span);
        item.appendChild(btn);
        list.appendChild(item);
    }
}

function removeTabDebuffFromList(tabPrefix, debuffName) {
    AppState[tabPrefix].debuffs = AppState[tabPrefix].debuffs.filter(d => d !== debuffName);
    
    const list = document.getElementById(`${tabPrefix}-debuffs-list`);
    const escapedName = CSS.escape(debuffName);
    const item = list?.querySelector(`[data-debuff-name="${escapedName}"]`);
    if (item) item.remove();
}

// =============================================================================
// CUSTOM BUFF PANELS
// =============================================================================

function setupCustomBuffPanels() {
    // Setup toggle buttons for TP and WS tabs
    ['tp', 'ws'].forEach(tabPrefix => {
        const toggleBtn = document.getElementById(`${tabPrefix}-custom-buffs-toggle`);
        const panel = document.getElementById(`${tabPrefix}-custom-buffs-panel`);
        const toggleText = document.getElementById(`${tabPrefix}-custom-buffs-toggle-text`);
        
        if (toggleBtn && panel && toggleText) {
            toggleBtn.addEventListener('click', () => {
                panel.classList.toggle('hidden');
                toggleText.textContent = panel.classList.contains('hidden') ? 'Show' : 'Hide';
            });
        }
        
        // Setup clear button
        const clearBtn = document.getElementById(`${tabPrefix}-custom-buffs-clear`);
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                clearPhysicalCustomBuffs();
                syncPhysicalCustomBuffInputs();
            });
        }
        
        // Setup input handlers - these sync between TP and WS tabs
        setupPhysicalCustomBuffInputs(tabPrefix);
    });
    
    // Setup magic custom buffs panel
    const magicToggleBtn = document.getElementById('magic-custom-buffs-toggle');
    const magicPanel = document.getElementById('magic-custom-buffs-panel');
    const magicToggleText = document.getElementById('magic-custom-buffs-toggle-text');
    
    if (magicToggleBtn && magicPanel && magicToggleText) {
        magicToggleBtn.addEventListener('click', () => {
            magicPanel.classList.toggle('hidden');
            magicToggleText.textContent = magicPanel.classList.contains('hidden') ? 'Show' : 'Hide';
        });
    }
    
    // Magic custom buffs clear button
    const magicClearBtn = document.getElementById('magic-custom-buffs-clear');
    if (magicClearBtn) {
        magicClearBtn.addEventListener('click', () => {
            clearMagicCustomBuffs();
            syncMagicCustomBuffInputs();
        });
    }
    
    // Magic custom buff inputs
    setupMagicCustomBuffInputs();
}

function setupPhysicalCustomBuffInputs(tabPrefix) {
    const inputMappings = [
        { id: `${tabPrefix}-custom-str`, stat: 'STR' },
        { id: `${tabPrefix}-custom-dex`, stat: 'DEX' },
        { id: `${tabPrefix}-custom-vit`, stat: 'VIT' },
        { id: `${tabPrefix}-custom-agi`, stat: 'AGI' },
        { id: `${tabPrefix}-custom-attack`, stat: 'attack' },
        { id: `${tabPrefix}-custom-attack-pct`, stat: 'attack_pct' },
        { id: `${tabPrefix}-custom-accuracy`, stat: 'accuracy' },
        { id: `${tabPrefix}-custom-haste`, stat: 'magic_haste' },
        { id: `${tabPrefix}-custom-stp`, stat: 'store_tp' },
        { id: `${tabPrefix}-custom-da`, stat: 'double_attack' },
        { id: `${tabPrefix}-custom-ta`, stat: 'triple_attack' },
        { id: `${tabPrefix}-custom-crit`, stat: 'crit_rate' },
        { id: `${tabPrefix}-custom-pdl`, stat: 'pdl' },
    ];
    
    inputMappings.forEach(({ id, stat }) => {
        const input = document.getElementById(id);
        if (input) {
            input.addEventListener('change', (e) => {
                const value = parseFloat(e.target.value) || 0;
                // Clamp to max value from input's max attribute
                const max = parseFloat(input.max) || 999;
                const clampedValue = Math.min(Math.max(0, value), max);
                e.target.value = clampedValue;
                
                // Update shared state
                AppState.customPhysicalBuffs[stat] = clampedValue;
                
                // Sync to other tab
                const otherTab = tabPrefix === 'tp' ? 'ws' : 'tp';
                const otherInput = document.getElementById(`${otherTab}-custom-${id.split('-custom-')[1]}`);
                if (otherInput) {
                    otherInput.value = clampedValue;
                }
            });
        }
    });
}

function setupMagicCustomBuffInputs() {
    const inputMappings = [
        { id: 'magic-custom-int', stat: 'INT' },
        { id: 'magic-custom-mnd', stat: 'MND' },
        { id: 'magic-custom-vit', stat: 'VIT' },
        { id: 'magic-custom-mab', stat: 'magic_attack' },
        { id: 'magic-custom-macc', stat: 'magic_accuracy' },
        { id: 'magic-custom-mdmg', stat: 'magic_damage' },
        { id: 'magic-custom-cure-potency', stat: 'cure_potency' },
    ];
    
    inputMappings.forEach(({ id, stat }) => {
        const input = document.getElementById(id);
        if (input) {
            input.addEventListener('change', (e) => {
                const value = parseFloat(e.target.value) || 0;
                const max = parseFloat(input.max) || 999;
                const clampedValue = Math.min(Math.max(0, value), max);
                e.target.value = clampedValue;
                
                AppState.magic.customBuffs[stat] = clampedValue;
            });
        }
    });
}

function clearPhysicalCustomBuffs() {
    AppState.customPhysicalBuffs = {
        STR: 0, DEX: 0, VIT: 0, AGI: 0,
        attack: 0, attack_pct: 0, accuracy: 0,
        magic_haste: 0, store_tp: 0,
        double_attack: 0, triple_attack: 0,
        crit_rate: 0, pdl: 0,
    };
}

function clearMagicCustomBuffs() {
    AppState.magic.customBuffs = {
        INT: 0, MND: 0, VIT: 0,
        magic_attack: 0, magic_accuracy: 0,
        magic_damage: 0,
        cure_potency: 0,
    };
}

function syncPhysicalCustomBuffInputs() {
    // Sync state to all physical custom buff inputs (both TP and WS tabs)
    ['tp', 'ws'].forEach(tabPrefix => {
        const inputMappings = [
            { id: `${tabPrefix}-custom-str`, stat: 'STR' },
            { id: `${tabPrefix}-custom-dex`, stat: 'DEX' },
            { id: `${tabPrefix}-custom-vit`, stat: 'VIT' },
            { id: `${tabPrefix}-custom-agi`, stat: 'AGI' },
            { id: `${tabPrefix}-custom-attack`, stat: 'attack' },
            { id: `${tabPrefix}-custom-attack-pct`, stat: 'attack_pct' },
            { id: `${tabPrefix}-custom-accuracy`, stat: 'accuracy' },
            { id: `${tabPrefix}-custom-haste`, stat: 'magic_haste' },
            { id: `${tabPrefix}-custom-stp`, stat: 'store_tp' },
            { id: `${tabPrefix}-custom-da`, stat: 'double_attack' },
            { id: `${tabPrefix}-custom-ta`, stat: 'triple_attack' },
            { id: `${tabPrefix}-custom-crit`, stat: 'crit_rate' },
            { id: `${tabPrefix}-custom-pdl`, stat: 'pdl' },
        ];
        
        inputMappings.forEach(({ id, stat }) => {
            const input = document.getElementById(id);
            if (input) {
                input.value = AppState.customPhysicalBuffs[stat] || 0;
            }
        });
    });
}

function syncMagicCustomBuffInputs() {
    const inputMappings = [
        { id: 'magic-custom-int', stat: 'INT' },
        { id: 'magic-custom-mnd', stat: 'MND' },
        { id: 'magic-custom-vit', stat: 'VIT' },
        { id: 'magic-custom-mab', stat: 'magic_attack' },
        { id: 'magic-custom-macc', stat: 'magic_accuracy' },
        { id: 'magic-custom-mdmg', stat: 'magic_damage' },
        { id: 'magic-custom-cure-potency', stat: 'cure_potency' },
    ];
    
    inputMappings.forEach(({ id, stat }) => {
        const input = document.getElementById(id);
        if (input) {
            input.value = AppState.magic.customBuffs[stat] || 0;
        }
    });
}

function getPhysicalCustomBuffsForPayload() {
    // Only return non-zero values
    const nonZero = {};
    for (const [key, value] of Object.entries(AppState.customPhysicalBuffs)) {
        if (value !== 0) {
            nonZero[key] = value;
        }
    }
    return Object.keys(nonZero).length > 0 ? nonZero : null;
}

function getMagicCustomBuffsForPayload() {
    // Only return non-zero values
    const nonZero = {};
    for (const [key, value] of Object.entries(AppState.magic.customBuffs)) {
        if (value !== 0) {
            nonZero[key] = value;
        }
    }
    return Object.keys(nonZero).length > 0 ? nonZero : null;
}

function toggleStatsPanel() {
    const content = document.getElementById('stats-content');
    const btn = document.getElementById('btn-toggle-stats');
    if (content && btn) {
        content.classList.toggle('hidden');
        btn.textContent = content.classList.contains('hidden') ? '[expand]' : '[collapse]';
    }
}

function setupFileUpload(dropzoneId, inputId, handler) {
    const dropzone = document.getElementById(dropzoneId);
    const input = document.getElementById(inputId);
    
    if (!dropzone || !input) return;
    
    dropzone.addEventListener('click', () => input.click());
    
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('border-ffxi-accent');
    });
    
    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('border-ffxi-accent');
    });
    
    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('border-ffxi-accent');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handler(files[0]);
        }
    });
    
    input.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handler(e.target.files[0]);
        }
    });
}

// =============================================================================
// BUFF SELECTORS
// =============================================================================

// Stats display is now handled inline

// =============================================================================
// EVENT HANDLERS
// =============================================================================

async function handleInventoryUpload(file) {
    showToast('Uploading inventory...', 'info');
    updateStatusIndicator('loading');
    
    try {
        const result = await API.uploadInventory(file);
        
        if (result.success) {
            AppState.inventoryLoaded = true;
            // Clear cached earring abbreviations so they rebuild from new inventory
            empyreanEarringAbbrevPrefixes.clear();
            updateStatusIndicator('ready');
            updateInventorySummary(result.item_count, result.filename);
            
            // Update upload status
            const status = document.getElementById('inventory-upload-status');
            if (status) {
                status.textContent = 'Loaded';
                status.className = 'text-xs px-2 py-0.5 rounded bg-ffxi-green/20 text-ffxi-green';
            }
            
            showToast(result.message, 'success');
            
            // Cache inventory data to localStorage for persistence
            await cacheInventoryData(result.filename);
            
            // Update Lua optimizer requirements
            LuaOptimizer.updateRequirements();
            
            // Reload weapons if job is selected
            if (AppState.selectedJob) {
                await loadWeapons(AppState.selectedJob);
                await loadRangedWeapons(AppState.selectedJob);
                await loadAmmoItems(AppState.selectedJob);
            }
        } else {
            showToast(`Upload failed: ${result.error}`, 'error');
            updateStatusIndicator('no_inventory');
        }
    } catch (error) {
        showToast(`Upload failed: ${error.message}`, 'error');
        updateStatusIndicator('no_inventory');
    }
}

async function cacheInventoryData(filename) {
    try {
        // Fetch the raw CSV content from the API for caching
        // This ensures we can fully reconstruct the inventory on reload
        const response = await fetch('/api/inventory/raw');
        const data = await response.json();
        
        if (data.success && data.csv_content) {
            // Store the raw CSV content - it can be re-parsed on reload
            saveToLocalStorage(STORAGE_KEYS.INVENTORY_DATA, data.csv_content);
            saveToLocalStorage(STORAGE_KEYS.INVENTORY_CHAR, filename);
            console.log(`Cached inventory CSV (${data.csv_content.length} bytes) to localStorage`);
            
            // Update the cached data notice
            updateCachedDataNotice();
        } else {
            console.warn('Could not cache inventory - raw CSV not available');
        }
    } catch (error) {
        console.warn('Failed to cache inventory data:', error);
    }
}

async function handleJobGiftsUpload(file) {
    showToast('Uploading job gifts...', 'info');
    
    try {
        const result = await API.uploadJobGifts(file);
        
        if (result.success) {
            AppState.jobGiftsLoaded = true;
            
            // Update upload status
            const status = document.getElementById('jobgifts-upload-status');
            if (status) {
                status.textContent = 'Loaded';
                status.className = 'text-xs px-2 py-0.5 rounded bg-ffxi-green/20 text-ffxi-green';
            }
            
            showToast(result.message, 'success');
            
            // Cache job gifts data to localStorage
            await cacheJobGiftsData();
            
            // Refresh jobs to show JP info
            await refreshJobInfo();
        } else {
            showToast(`Upload failed: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast(`Upload failed: ${error.message}`, 'error');
    }
}

async function cacheJobGiftsData() {
    try {
        // Fetch the full job gifts data from the API
        const response = await API.fetch('/api/jobgifts');
        if (response.gifts && Object.keys(response.gifts).length > 0) {
            saveToLocalStorage(STORAGE_KEYS.JOB_GIFTS_DATA, response.gifts);
            console.log(`Cached job gifts for ${Object.keys(response.gifts).length} jobs to localStorage`);
            
            // Update the cached data notice
            updateCachedDataNotice();
        }
    } catch (error) {
        console.warn('Failed to cache job gifts data:', error);
    }
}

async function refreshJobInfo() {
    try {
        const data = await API.getJobs();
        
        // Update job select with JP info
        const jobSelect = document.getElementById('job-select');
        if (jobSelect && data.jobs) {
            const currentValue = jobSelect.value;
            
            jobSelect.innerHTML = '<option value="">Select Job...</option>';
            for (const job of data.jobs) {
                const option = document.createElement('option');
                option.value = job.code;
                let label = `${job.code}`;
                if (job.jp_spent > 0) {
                    label += ` (${job.jp_spent} JP)`;
                }
                option.textContent = label;
                jobSelect.appendChild(option);
            }
            
            jobSelect.value = currentValue;
        }
    } catch (error) {
        console.error('Failed to refresh job info:', error);
    }
}

async function handleJobChange(e) {
    const job = e.target.value;
    AppState.selectedJob = job;
    
    // Save to localStorage
    saveToLocalStorage('ffxi_selected_job', job);
    
    // Update DW hint based on new main job
    updateDWHint();
    
    // Reset dependent selections
    AppState.selectedMainWeapon = null;
    AppState.selectedSubWeapon = null;
    AppState.selectedRangedWeapon = null;
    AppState.selectedWeaponskill = null;
    
    // Clear weapon containers
    clearWeaponSelections();
    
    // Refresh abilities selectors based on new job
    refreshAbilitiesSelectors();
    
    if (!job) {
        hideMasterLevelSection();
        return;
    }
    
    // Check for master level eligibility from JP data
    // Only show master level section if job has 2100 JP
    if (AppState.jobGiftsLoaded) {
        const jobs = await API.getJobs();
        const jobData = jobs.jobs?.find(j => j.code === job);
        if (jobData?.has_master) {
            showMasterLevelSection();
        } else {
            hideMasterLevelSection();
        }
    } else {
        // If no JP data loaded, hide master level section
        hideMasterLevelSection();
    }
    
    // Load weapons
    await loadWeapons(job);
    // Load ranged weapons and ammo
    await loadRangedWeapons(job);
    await loadAmmoItems(job);
}

function handleSubJobChange(e) {
    const subjob = e.target.value;
    AppState.selectedSubJob = subjob.toLowerCase();
    
    // Save to localStorage
    saveToLocalStorage(STORAGE_KEYS.SUBJOB, subjob);
    
    // Update DW hint based on sub job
    updateDWHint();
    
    // Refresh abilities selectors based on new sub job
    refreshAbilitiesSelectors();
}

async function loadWeapons(job) {
    if (!AppState.inventoryLoaded) {
        showToast('Please upload inventory first', 'warning');
        return;
    }
    
    try {
        const data = await API.getWeapons(job);
        AppState.weapons = data.weapons || [];
        
        // Setup main weapon dropdown
        const options = AppState.weapons.map(w => ({
            value: w.name,
            label: w.name2 || w.name,
            sublabel: `${w.skill_type} D${w.damage} Delay${w.delay} iLv${w.item_level}`,
            data: w,
        }));
        
        const dropdown = createSearchableDropdown(
            'main-weapon-container',
            options,
            handleMainWeaponSelect,
            'Search weapons...'
        );
        AppState.dropdowns.mainWeapon = dropdown;
        
    } catch (error) {
        showToast(`Failed to load weapons: ${error.message}`, 'error');
    }
}

async function handleMainWeaponSelect(option) {
    // Handle clearing the selection
    if (!option) {
        AppState.selectedMainWeapon = null;
        saveToLocalStorage(STORAGE_KEYS.MAIN_WEAPON, null);
        const infoDiv = document.getElementById('weapon-info');
        if (infoDiv) infoDiv.classList.add('hidden');
        // Hide sub item section since no weapon is selected
        const subSection = document.getElementById('sub-item-section');
        if (subSection) subSection.classList.add('hidden');
        const dwSection = document.getElementById('dw-checkbox-section');
        if (dwSection) dwSection.classList.add('hidden');
        AppState.selectedSubWeapon = null;
        return;
    }

    AppState.selectedMainWeapon = option.data;
    
    // Save to localStorage
    saveToLocalStorage(STORAGE_KEYS.MAIN_WEAPON, option.data?.name);
    
    // Show weapon info
    const infoDiv = document.getElementById('weapon-info');
    if (infoDiv && option.data) {
        const w = option.data;
        infoDiv.innerHTML = `
            <div class="text-xs space-y-1">
                <div><span class="text-ffxi-text-dim">Type:</span> ${w.skill_type}</div>
                <div><span class="text-ffxi-text-dim">DMG:</span> ${w.damage} <span class="text-ffxi-text-dim">Delay:</span> ${w.delay}</div>
            </div>
        `;
        infoDiv.classList.remove('hidden');
    }
    
    // Determine if dual wield is available
    const twoHandedSkills = ['Great Sword', 'Great Axe', 'Scythe', 'Polearm', 'Staff', 'Great Katana'];
    const is2H = twoHandedSkills.includes(option.data.skill_type);
    const isH2H = option.data.skill_type === 'Hand-to-Hand';
    
    // Show/hide dual wield checkbox
    const dwSection = document.getElementById('dw-checkbox-section');
    if (dwSection) {
        if (!is2H && !isH2H) {
            dwSection.classList.remove('hidden');
        } else {
            dwSection.classList.add('hidden');
        }
    }
    
    // Show sub item section
    const subSection = document.getElementById('sub-item-section');
    const subLabel = document.getElementById('sub-section-label');
    
    if (isH2H) {
        // H2H doesn't use sub slot
        if (subSection) subSection.classList.add('hidden');
        AppState.selectedSubWeapon = { Name: 'Empty', Name2: 'Empty', Type: 'None' };
    } else {
        if (subSection) subSection.classList.remove('hidden');
        if (subLabel) {
            subLabel.textContent = is2H ? 'Grip' : 'Off-Hand';
        }
        
        // Load offhand options
        await loadOffhand(AppState.selectedJob, option.data.skill_type);
    }
    
    // Load weaponskills
    await loadWeaponskills(option.data.skill_type);
}

async function loadOffhand(job, mainSkill) {
    try {
        const data = await API.getOffhand(job, mainSkill);
        AppState.offhand = data.offhand || [];
        
        const options = AppState.offhand.map(item => ({
            value: item.name,
            label: item.name2 || item.name,
            sublabel: item.type !== 'None' ? `${item.type} ${item.skill_type || ''}` : '',
            data: item,
        }));
        
        AppState.dropdowns.subWeapon = createSearchableDropdown(
            'sub-item-container',
            options,
            handleSubWeaponSelect,
            'Search off-hand...'
        );
        
    } catch (error) {
        showToast(`Failed to load off-hand items: ${error.message}`, 'error');
    }
}

function handleSubWeaponSelect(option) {
    if (!option) {
        AppState.selectedSubWeapon = null;
        return;
    }
    AppState.selectedSubWeapon = option.data;
}

async function loadRangedWeapons(job) {
    if (!AppState.inventoryLoaded) return;
    
    try {
        const data = await API.getRangedWeapons(job);
        AppState.rangedWeapons = data.ranged_weapons || [];
        
        const options = AppState.rangedWeapons.map(w => ({
            value: w.name,
            label: w.name2 || w.name,
            sublabel: `${w.skill_type} D${w.damage} Delay${w.delay} iLv${w.item_level}`,
            data: w,
        }));
        
        // Always include an "Empty" option
        options.unshift({
            value: 'Empty',
            label: 'None',
            sublabel: 'No ranged weapon',
            data: { name: 'Empty', name2: 'Empty', type: 'None', _raw: { Name: 'Empty', Name2: 'Empty', Type: 'None' } },
        });
        
        AppState.dropdowns.rangedWeapon = createSearchableDropdown(
            'ranged-weapon-container',
            options,
            handleRangedWeaponSelect,
            'Search ranged weapons...'
        );
        
    } catch (error) {
        console.warn(`Failed to load ranged weapons: ${error.message}`);
    }
}

function handleRangedWeaponSelect(option) {
    if (!option) {
        AppState.selectedRangedWeapon = null;
        saveToLocalStorage(STORAGE_KEYS.RANGED_WEAPON, null);
        document.getElementById('ranged-weapon-info')?.classList.add('hidden');
        return;
    }

    const isEmpty = option.value === 'Empty' || !option.data?.skill_type;
    
    if (isEmpty) {
        AppState.selectedRangedWeapon = null;
        saveToLocalStorage(STORAGE_KEYS.RANGED_WEAPON, null);
        document.getElementById('ranged-weapon-info')?.classList.add('hidden');
        
        // If currently in ranged WS mode, reset the WS selector
        if (AppState.ws.mode === 'ranged') {
            const wsSelect = document.getElementById('ws-select');
            if (wsSelect) {
                wsSelect.innerHTML = '<option value="">Select a ranged weapon first...</option>';
                wsSelect.disabled = true;
            }
        }
        return;
    }
    
    AppState.selectedRangedWeapon = option.data;
    saveToLocalStorage(STORAGE_KEYS.RANGED_WEAPON, option.data?.name);
    
    // Show ranged weapon info
    const infoDiv = document.getElementById('ranged-weapon-info');
    if (infoDiv && option.data) {
        const w = option.data;
        infoDiv.innerHTML = `<span class="text-ffxi-text-dim">Type:</span> ${w.skill_type} &nbsp; <span class="text-ffxi-text-dim">DMG:</span> ${w.damage} <span class="text-ffxi-text-dim">Delay:</span> ${w.delay}`;
        infoDiv.classList.remove('hidden');
    }
    
    // If currently in ranged WS mode, reload the WS dropdown
    if (AppState.ws.mode === 'ranged') {
        loadWeaponskills(option.data.skill_type);
    }
}

async function loadAmmoItems(job) {
    if (!AppState.inventoryLoaded) return;
    
    try {
        const data = await API.fetch(`/api/inventory?slot=ammo&job=${job}`);
        AppState.ammoItems = data.items || [];
        
        const options = AppState.ammoItems.map(item => ({
            value: item.name,
            label: item.name2 || item.name,
            sublabel: `iLv${item.item_level || 0}`,
            data: {
                ...item,
                _raw: {
                    Name: item.name,
                    Name2: item.name2,
                    Type: item.type,
                    'Item Level': item.item_level,
                    Jobs: item.jobs,
                    ...item.stats,
                },
            },
        }));
        
        options.unshift({
            value: 'Empty',
            label: 'None',
            sublabel: 'No ammo',
            data: { name: 'Empty', _raw: null },
        });
        
        AppState.dropdowns.ammo = createSearchableDropdown(
            'ammo-container',
            options,
            handleAmmoSelect,
            'Search ammo...'
        );
        
    } catch (error) {
        console.warn(`Failed to load ammo items: ${error.message}`);
    }
}

function handleAmmoSelect(option) {
    if (!option) {
        AppState.selectedAmmo = null;
        saveToLocalStorage(STORAGE_KEYS.AMMO, null);
        document.getElementById('ammo-info')?.classList.add('hidden');
        return;
    }

    const isEmpty = option.value === 'Empty' || !option.data?._raw;
    
    if (isEmpty) {
        AppState.selectedAmmo = null;
        saveToLocalStorage(STORAGE_KEYS.AMMO, null);
        document.getElementById('ammo-info')?.classList.add('hidden');
        return;
    }
    
    AppState.selectedAmmo = option.data;
    saveToLocalStorage(STORAGE_KEYS.AMMO, option.data?.name);
    
    const infoDiv = document.getElementById('ammo-info');
    if (infoDiv) {
        infoDiv.textContent = `iLv${option.data.item_level || 0}`;
        infoDiv.classList.remove('hidden');
    }
}

function handleWSModeToggle(mode) {
    AppState.ws.mode = mode;
    
    const meleeBtn = document.getElementById('ws-mode-melee');
    const rangedBtn = document.getElementById('ws-mode-ranged');
    const hint = document.getElementById('ws-mode-hint');
    
    const activeStyle = 'background:#c9a227;color:#0a0e14;border-color:#c9a227;';
    const inactiveStyle = 'background:#12171f;color:#8b9298;border-color:#1e2630;';
    
    if (mode === 'melee') {
        if (meleeBtn) meleeBtn.setAttribute('style', activeStyle);
        if (rangedBtn) rangedBtn.setAttribute('style', inactiveStyle);
        if (hint) hint.textContent = 'Optimizing for melee weaponskill';
        
        // Repopulate WS dropdown from main weapon
        if (AppState.selectedMainWeapon?.skill_type) {
            loadWeaponskills(AppState.selectedMainWeapon.skill_type);
        } else {
            const wsSelect = document.getElementById('ws-select');
            if (wsSelect) {
                wsSelect.innerHTML = '<option value="">Select a main weapon first...</option>';
                wsSelect.disabled = true;
            }
        }
    } else {
        if (meleeBtn) meleeBtn.setAttribute('style', inactiveStyle);
        if (rangedBtn) rangedBtn.setAttribute('style', activeStyle);
        if (hint) hint.textContent = 'Optimizing for ranged weaponskill';
        
        // Repopulate WS dropdown from ranged weapon
        if (AppState.selectedRangedWeapon?.skill_type) {
            loadWeaponskills(AppState.selectedRangedWeapon.skill_type);
        } else {
            const wsSelect = document.getElementById('ws-select');
            if (wsSelect) {
                wsSelect.innerHTML = '<option value="">Select a ranged weapon first...</option>';
                wsSelect.disabled = true;
            }
        }
    }
    
    // Clear current WS selection since we changed mode
    AppState.selectedWeaponskill = null;
}

async function loadWeaponskills(skillType) {
    try {
        const data = await API.getWeaponskills(skillType);
        AppState.weaponskills = data.weaponskills || [];
        
        const wsSelect = document.getElementById('ws-select');
        if (wsSelect) {
            wsSelect.innerHTML = '<option value="">Select Weaponskill...</option>';
            wsSelect.disabled = false;
            
            for (const ws of AppState.weaponskills) {
                const option = document.createElement('option');
                option.value = ws.name;
                const hits = ws.hits > 1 ? `${ws.hits}hit` : '1hit';
                option.textContent = `${ws.name} (${ws.ws_type}, ${hits})`;
                wsSelect.appendChild(option);
            }
        }
    } catch (error) {
        showToast(`Failed to load weaponskills: ${error.message}`, 'error');
    }
}

function handleWeaponskillChange(e) {
    const wsName = e.target.value;
    AppState.selectedWeaponskill = AppState.weaponskills.find(ws => ws.name === wsName);
}

function handleTabChange(tab) {
    const previousTab = AppState.currentTab;
    AppState.currentTab = tab;
    
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });
    
    // Update tab panels
    document.querySelectorAll('.tab-panel').forEach(panel => {
        panel.classList.toggle('hidden', panel.id !== `tab-${tab}`);
    });
    
    // Hide/show results panel based on tab
    // Compare tab has its own inline stats comparison, Inventory tab doesn't need it
    const resultsPanel = document.getElementById('results-panel');
    if (resultsPanel) {
        const hidePanelTabs = ['compare', 'inventory'];
        resultsPanel.classList.toggle('hidden', hidePanelTabs.includes(tab));
    }
    
    // If switching from magic to a melee tab, restore the melee stats panel format
    if (previousTab === 'magic' && (tab === 'tp' || tab === 'ws')) {
        restoreMeleeStatsPanel();
    }
    
    // Load inventory items when switching to inventory tab
    if (tab === 'inventory' && InventoryBrowser.items.length === 0) {
        InventoryBrowser.loadItems();
    }
    
    // Clear current results when switching tabs (they'll be repopulated when optimization runs)
    // AppState.currentResults = null;
}

function restoreMeleeStatsPanel() {
    // Restore the accuracy breakdown section to its original melee format
    const accBreakdownSection = document.getElementById('acc-breakdown-section');
    if (accBreakdownSection) {
        accBreakdownSection.innerHTML = `
            <h4 class="text-xs uppercase tracking-wider text-ffxi-accent mb-2">⚔️ Accuracy vs <span id="acc-target-name">Target</span></h4>
            
            <div class="space-y-2">
                <div class="text-xs">
                    <div class="text-ffxi-text-dim mb-1">Accuracy Components</div>
                    <div class="space-y-0.5 pl-2">
                        <div class="flex justify-between">
                            <span class="text-ffxi-text-dim">From DEX (<span id="acc-dex-val">0</span>)</span>
                            <span id="acc-from-dex" class="text-ffxi-text">+0</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-ffxi-text-dim">From <span id="acc-skill-type">Skill</span> (<span id="acc-skill-val">0</span>)</span>
                            <span id="acc-from-skill" class="text-ffxi-text">+0</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-ffxi-text-dim">From Gear</span>
                            <span id="acc-from-gear" class="text-ffxi-text">+0</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-ffxi-text-dim">From JP Gifts</span>
                            <span id="acc-from-jp" class="text-ffxi-text">+0</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-ffxi-text-dim">From Buffs</span>
                            <span id="acc-from-buffs" class="text-ffxi-text">+0</span>
                        </div>
                        <div class="flex justify-between border-t border-ffxi-border pt-1 mt-1">
                            <span class="text-ffxi-text font-medium">Total Accuracy</span>
                            <span id="acc-total" class="text-ffxi-accent font-bold">0</span>
                        </div>
                    </div>
                </div>
                
                <div class="text-xs">
                    <div class="text-ffxi-text-dim mb-1">vs Target</div>
                    <div class="space-y-0.5 pl-2">
                        <div class="flex justify-between">
                            <span class="text-ffxi-text-dim">Target Evasion</span>
                            <span id="target-eva" class="text-ffxi-text">0</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-ffxi-text-dim">Acc Differential</span>
                            <span id="acc-diff" class="text-ffxi-text">0</span>
                        </div>
                        <div class="flex justify-between border-t border-ffxi-border pt-1 mt-1">
                            <span class="text-ffxi-text font-medium">Hit Rate</span>
                            <span id="hit-rate" class="text-ffxi-green">95.0%</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-ffxi-text font-medium">WS Hit Rate</span>
                            <span id="ws-hit-rate" class="text-ffxi-green">95.0%</span>
                        </div>
                    </div>
                </div>
                
                <div id="acc-status" class="text-center py-1 rounded text-xs font-medium bg-ffxi-green/20 text-ffxi-green">
                    ✓ Accuracy Capped!
                </div>
            </div>
        `;
    }
}

// =============================================================================
// OPTIMIZATION
// =============================================================================

async function runTPOptimization() {
    if (!validateOptimizationInputs()) return;
    
    const tpPriority = document.getElementById('tp-priority')?.value || 'hybrid_tp';
    
    const tpSlowMode = document.getElementById('tp-slow-mode')?.checked ?? false;
    const tpSlowMaxIterations = parseInt(document.getElementById('tp-slow-max-iterations')?.value || 3);
    const tpSlowTopN = parseInt(document.getElementById('tp-slow-top-n')?.value || 3);

    showToast(tpSlowMode ? 'Running deep TP optimization (slow mode)...' : 'Running TP optimization...', 'info');
    showOptimizationProgress();
    
    // Build buffs object with custom buffs if set
    const buffs = { ...AppState.tp.buffs };
    const customBuffs = getPhysicalCustomBuffsForPayload();
    if (customBuffs) {
        buffs.custom = customBuffs;
    }
    
    try {
        const result = await API.optimizeTP({
            job: AppState.selectedJob,
            sub_job: AppState.selectedSubJob,
            main_weapon: AppState.selectedMainWeapon._raw,
            sub_weapon: AppState.selectedSubWeapon?._raw || { Name: 'Empty', Type: 'None' },
            ranged_weapon: AppState.selectedRangedWeapon?._raw || null,
            ammo: AppState.selectedAmmo?._raw || null,
            tp_type: tpPriority,
            target: AppState.tp.target,
            use_simulation: true,
            beam_width: 10,
            master_level: AppState.masterLevel,
            buffs: buffs,
            abilities: AppState.tp.abilities,
            food: AppState.tp.food,
            debuffs: AppState.tp.debuffs,
            slow_mode: tpSlowMode,
            slow_max_iterations: tpSlowMaxIterations,
            slow_top_n_per_slot: tpSlowTopN,
        });
        
        if (result.success) {
            displayTPResults(result.results);
            showToast('TP optimization complete!', 'success');
        } else {
            showToast(`Optimization failed: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast(`Optimization failed: ${error.message}`, 'error');
    }
    
    hideOptimizationProgress();
}

async function runWSOptimization() {
    if (!validateOptimizationInputs()) return;
    
    if (!AppState.selectedWeaponskill) {
        showToast('Please select a weaponskill', 'warning');
        return;
    }
    
    // Validate ranged weapon when in ranged mode
    const isRangedMode = AppState.ws.mode === 'ranged';
    if (isRangedMode && !AppState.selectedRangedWeapon) {
        showToast('Please select a ranged weapon for ranged WS optimization', 'warning');
        return;
    }
    
    // Ammo is required for ranged WS optimization
    if (isRangedMode && !AppState.selectedAmmo) {
        showToast('Please select an ammo item in the sidebar for ranged WS optimization', 'warning');
        return;
    }
    
    const wsSlowMode = document.getElementById('ws-slow-mode')?.checked ?? false;
    const wsSlowMaxIterations = parseInt(document.getElementById('ws-slow-max-iterations')?.value || 3);
    const wsSlowTopN = parseInt(document.getElementById('ws-slow-top-n')?.value || 3);

    showToast(wsSlowMode ? 'Running deep WS optimization (slow mode)...' : 'Running WS optimization...', 'info');
    showOptimizationProgress();
    
    // Get TP level from slider
    const tpLevel = parseInt(document.getElementById('ws-tp-level')?.value || 1000);
    
    // Build buffs object with custom buffs if set
    const buffs = { ...AppState.ws.buffs };
    const customBuffs = getPhysicalCustomBuffsForPayload();
    if (customBuffs) {
        buffs.custom = customBuffs;
    }
    
    try {
        const result = await API.optimizeWS({
            job: AppState.selectedJob,
            sub_job: AppState.selectedSubJob,
            main_weapon: AppState.selectedMainWeapon._raw,
            sub_weapon: AppState.selectedSubWeapon?._raw || { Name: 'Empty', Type: 'None' },
            ranged_weapon: AppState.selectedRangedWeapon?._raw || null,
            ammo: isRangedMode ? AppState.selectedAmmo._raw : null,
            weaponskill: AppState.selectedWeaponskill.name,
            target: AppState.ws.target,
            use_simulation: AppState.ws.useSimulation,
            beam_width: 10,
            master_level: AppState.masterLevel,
            min_tp: tpLevel,
            buffs: buffs,
            abilities: AppState.ws.abilities,
            food: AppState.ws.food,
            debuffs: AppState.ws.debuffs,
            slow_mode: wsSlowMode,
            slow_max_iterations: wsSlowMaxIterations,
            slow_top_n_per_slot: wsSlowTopN,
        });
        
        if (result.success) {
            displayWSResults(result.results);
            if (result.error) {
                // success=true but error field set means simulation warnings (e.g. zero-damage sets)
                showToast(`WS optimization complete (with warnings: ${result.error})`, 'warning');
            } else {
                showToast('WS optimization complete!', 'success');
            }
        } else {
            showToast(`Optimization failed: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast(`Optimization failed: ${error.message}`, 'error');
    }
    
    hideOptimizationProgress();
}

function validateOptimizationInputs() {
    if (!AppState.inventoryLoaded) {
        showToast('Please upload inventory first', 'warning');
        return false;
    }
    
    if (!AppState.selectedJob) {
        showToast('Please select a job', 'warning');
        return false;
    }
    
    if (!AppState.selectedMainWeapon) {
        showToast('Please select a main weapon', 'warning');
        return false;
    }
    
    return true;
}

function showOptimizationProgress() {
    const content = document.getElementById('results-content');
    if (content) {
        content.innerHTML = `
            <div class="text-center py-8">
                <div class="loading-spinner mx-auto mb-4"></div>
                <p class="text-ffxi-accent">Optimizing gear sets...</p>
                <p class="text-ffxi-text-dim text-sm mt-2">This may take a moment</p>
            </div>
        `;
    }
}

function hideOptimizationProgress() {
    // Results display will replace the progress indicator
}

function displayTPResults(results) {
    AppState.currentResults = results;
    AppState.currentResultType = 'tp';
    
    const content = document.getElementById('results-content');
    if (!content || !results.length) {
        if (content) {
            content.innerHTML = '<div class="text-center text-ffxi-text-dim py-8">No results found</div>';
        }
        return;
    }
    
    let html = '<div class="space-y-4">';
    
    for (const result of results) {
        const timeToWS = result.time_to_ws?.toFixed(2) || '?';
        const wsPerMin = result.time_to_ws ? (60 / result.time_to_ws).toFixed(2) : '?';
        const tpPerRound = result.tp_per_round?.toFixed(1) || '?';
        const dps = result.dps?.toFixed(0) || '?';
        
        html += `
            <div class="result-card bg-ffxi-dark rounded-lg p-4 border border-ffxi-border hover:border-ffxi-accent transition-colors cursor-pointer"
                 onclick="showResultDetails(${result.rank - 1})">
                <div class="flex items-center justify-between mb-3">
                    <span class="text-ffxi-accent font-display text-lg">#${result.rank}</span>
                    <span class="text-ffxi-green font-bold">${timeToWS}s to WS</span>
                </div>
                <div class="grid grid-cols-3 gap-2 text-xs text-ffxi-text-dim mb-3">
                    <div>
                        <span class="block text-ffxi-text">${wsPerMin}</span>
                        WS/min
                    </div>
                    <div>
                        <span class="block text-ffxi-text">${tpPerRound}</span>
                        TP/Round
                    </div>
                    <div>
                        <span class="block text-ffxi-text">${dps}</span>
                        TP DPS
                    </div>
                </div>
                <div class="text-xs text-ffxi-text-dim">
                    ${formatGearSummary(result.gear)}
                </div>
            </div>
        `;
    }
    
    html += '</div>';
    content.innerHTML = html;
    
    // Show Lua section
    document.getElementById('lua-section')?.classList.remove('hidden');
    generateLuaOutput(results[0]);
    
    // Show stats for first result
    calculateAndDisplayStats(results[0]);
}

function displayWSResults(results) {
    AppState.currentResults = results;
    AppState.currentResultType = 'ws';
    
    const content = document.getElementById('results-content');
    if (!content || !results.length) {
        if (content) {
            content.innerHTML = '<div class="text-center text-ffxi-text-dim py-8">No results found</div>';
        }
        return;
    }
    
    let html = '<div class="space-y-4">';
    
    for (const result of results) {
        const damage = result.damage?.toFixed(0) || '?';
        
        html += `
            <div class="result-card bg-ffxi-dark rounded-lg p-4 border border-ffxi-border hover:border-ffxi-accent transition-colors cursor-pointer"
                 onclick="showResultDetails(${result.rank - 1})">
                <div class="flex items-center justify-between mb-3">
                    <span class="text-ffxi-accent font-display text-lg">#${result.rank}</span>
                    <span class="text-ffxi-green font-bold">${parseInt(damage).toLocaleString()} damage</span>
                </div>
                <div class="text-xs mb-2">
                    <span class="text-ffxi-text-dim">Score:</span> 
                    <span class="text-ffxi-text">${result.score?.toFixed(1)}</span>
                </div>
                <div class="text-xs text-ffxi-text-dim">
                    ${formatGearSummary(result.gear)}
                </div>
            </div>
        `;
    }
    
    html += '</div>';
    content.innerHTML = html;
    
    // Show Lua section
    document.getElementById('lua-section')?.classList.remove('hidden');
    generateLuaOutput(results[0]);
    
    // Show stats for first result
    calculateAndDisplayStats(results[0]);
}

function formatGearSummary(gear) {
    const slots = ['head', 'body', 'hands', 'legs', 'feet'];
    const items = slots
        .filter(s => gear[s] && gear[s].name !== 'Empty')
        .map(s => gear[s].name2 || gear[s].name)
        .slice(0, 3);
    
    return items.join(', ') + (items.length < Object.keys(gear).length ? '...' : '');
}

// =============================================================================
// DT SET OPTIMIZATION
// =============================================================================

const DT_TYPE_DESCRIPTIONS = {
    pure_dt: "Maximum damage reduction. Caps DT/PDT/MDT at -50% each. Secondary: HP, Defense, Evasion.",
    dt_tp: "Survivability while building TP. Caps DT first (-50%), then maximizes TP generation stats.",
    dt_refresh: "Mage idle set. Caps DT, then prioritizes Refresh and MP for sustain.",
    dt_regen: "HP recovery set. Caps DT, then prioritizes Regen and HP for downtime.",
    pdt_only: "Physical damage focus. Maximizes PDT and DT for physical-heavy content.",
    mdt_only: "Magical damage focus. Maximizes MDT and DT for magical-heavy content.",
    pdt_eva:  "Physical avoidance. Jointly maximizes PDT/DT and Evasion/AGI — reduces how often physical attacks land and how much they hurt.",
    mdt_meva: "Magical avoidance. Jointly maximizes MDT/DT and Magic Evasion/MND — reduces how often magic lands and how much damage it deals.",
    enmity: "Greedy enmity set. Locks the highest-enmity item per slot, fills the rest with DT. Combine with your pure DT set for a balanced hate set.",
    passive_refresh: "Greedy passive refresh set. Locks the highest gear-refresh item per slot, fills the rest with DT. Combine with your DT set.",
    passive_regen: "Greedy passive regen set. Locks the highest gear-regen item per slot, fills the rest with DT. Combine with your DT set.",
    sird: "Greedy Spell Interruption Rate Down set. Finds the best SIRD item per slot and maximizes toward the 102% cap.",
    hp_ehp: "EHP-maximising DP. Jointly optimises HP and DT/PDT/MDT via integer DP over all reachable (DT,PDT,MDT) states. Ranked by min(physical EHP, magical EHP) — the conservative worst-case.",
};

// Group labels for the DT dropdown optgroups
const DT_TYPE_GROUPS = {
    'Standard DT':     ['pure_dt', 'pdt_only', 'mdt_only', 'pdt_eva', 'mdt_meva'],
    'DT + Offense':    ['dt_tp'],
    'DT + Sustain':    ['dt_refresh', 'dt_regen'],
    'HP / EHP':        ['hp_ehp'],
    'Passive Stats':   ['enmity', 'passive_refresh', 'passive_regen', 'sird'],
    'Other':           ['fast_cast', 'generic_ws'],
};

// Human-readable labels for each type
const DT_TYPE_LABELS = {
    pure_dt:         'Pure DT',
    dt_tp:           'DT + TP',
    dt_refresh:      'DT + Refresh',
    dt_regen:        'DT + Regen',
    pdt_only:        'PDT Only',
    mdt_only:        'MDT Only',
    pdt_eva:         'PDT-EVA',
    mdt_meva:        'MDT-MEVA',
    fast_cast:       'Fast Cast',
    generic_ws:      'Generic WS',
    enmity:          'Enmity',
    passive_refresh: 'Passive Refresh',
    passive_regen:   'Passive Regen',
    sird:            'Spell Interruption Rate Down',
    hp_ehp:          'Effective HP (EHP)',
};

async function populateDTTypeDropdown() {
    const select = document.getElementById('dt-set-type');
    if (!select) return;

    // Try to populate from the API so labels/types always match the backend.
    // Fall back to the static list if the request fails.
    let typeIds;
    try {
        const data = await API.getDtTypes();
        typeIds = (data.dt_types || []).map(t => t.id);
    } catch {
        typeIds = Object.values(DT_TYPE_GROUPS).flat();
    }

    // Build a set for quick lookup
    const available = new Set(typeIds);

    // Preserve the current selection (may have been set via HTML default)
    const currentVal = select.value || 'pure_dt';

    select.innerHTML = '';

    for (const [groupLabel, ids] of Object.entries(DT_TYPE_GROUPS)) {
        const groupIds = ids.filter(id => available.has(id));
        if (groupIds.length === 0) continue;

        const optgroup = document.createElement('optgroup');
        optgroup.label = groupLabel;

        for (const id of groupIds) {
            const opt = document.createElement('option');
            opt.value = id;
            opt.textContent = DT_TYPE_LABELS[id] || id;
            optgroup.appendChild(opt);
        }
        select.appendChild(optgroup);
    }

    // Restore selection
    if ([...select.options].some(o => o.value === currentVal)) {
        select.value = currentVal;
    }

    updateDTTypeDescription();
}

function updateDTTypeDescription() {
    const select = document.getElementById('dt-set-type');
    const descElement = document.getElementById('dt-type-description');
    if (select && descElement) {
        const description = DT_TYPE_DESCRIPTIONS[select.value] || '';
        descElement.textContent = description;
    }
}

async function runDTOptimization() {
    if (!AppState.selectedJob) {
        showToast('Please select a job first', 'warning');
        return;
    }
    
    const dtType = document.getElementById('dt-set-type')?.value || 'pure_dt';
    const includeWeapons = document.getElementById('dt-include-weapons')?.checked || false;
    
    // Greedy types don't use weapons or TP parameters
    const GREEDY_TYPES = ['enmity', 'passive_refresh', 'passive_regen', 'sird', 'hp_ehp', 'pdt_eva', 'mdt_meva'];
    const isGreedy = GREEDY_TYPES.includes(dtType);
    
    // Get TP-related parameters from TP tab state for TP calculations
    const tpState = AppState.tp;
    
    console.log('=== DT OPTIMIZATION REQUEST ===');
    console.log('Job:', AppState.selectedJob);
    console.log('DT Type:', dtType, isGreedy ? '(greedy)' : '');
    console.log('Main Weapon:', AppState.selectedMainWeapon);
    console.log('================================');
    
    const typeLabel = {
        enmity: 'enmity',
        passive_refresh: 'passive refresh',
        passive_regen: 'passive regen',
        sird: 'spell interruption rate down',
    }[dtType] || 'DT';
    showToast(`Running ${typeLabel} optimization...`, 'info');
    showOptimizationProgress();
    
    const requestPayload = {
        job: AppState.selectedJob,
        dt_type: dtType,
        main_weapon: isGreedy ? null : (AppState.selectedMainWeapon?._raw || null),
        sub_weapon: isGreedy ? null : (AppState.selectedSubWeapon?._raw || null),
        include_weapons: isGreedy ? false : includeWeapons,
        beam_width: 25,
        // TP calculation parameters (only relevant for non-greedy types)
        sub_job: AppState.selectedSubJob || 'war',
        master_level: AppState.masterLevel || 0,
        target: 'apex_leech',
        buffs: isGreedy ? {} : (tpState.buffs || {}),
        abilities: isGreedy ? [] : (tpState.abilities || []),
        food: isGreedy ? '' : (tpState.food || ''),
        debuffs: isGreedy ? [] : (tpState.debuffs || []),
    };
    
    try {
        const result = await API.optimizeDT(requestPayload);
        
        if (result.success) {
            displayDTResults(result.results, dtType);
            showToast(`${typeLabel.charAt(0).toUpperCase() + typeLabel.slice(1)} optimization complete!`, 'success');
        } else {
            showToast(`Optimization failed: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast(`Optimization failed: ${error.message}`, 'error');
    }
    
    hideOptimizationProgress();
}

function displayDTResults(results, dtType) {
    console.log('displayDTResults called with results:', results, 'dtType:', dtType);
    if (results && results.length > 0) {
        console.log('First result time_to_ws:', results[0].time_to_ws, 'type:', typeof results[0].time_to_ws);
    }
    
    AppState.currentResults = results;
    AppState.currentResultType = 'dt';
    AppState.currentDTType = dtType || 'pure_dt';
    
    const content = document.getElementById('results-content');
    if (!content || !results.length) {
        if (content) {
            content.innerHTML = '<div class="text-center text-ffxi-text-dim py-8">No results found</div>';
        }
        return;
    }
    
    const GREEDY_TYPES = ['enmity', 'passive_refresh', 'passive_regen', 'sird', 'hp_ehp', 'pdt_eva', 'mdt_meva'];
    const isGreedy = GREEDY_TYPES.includes(dtType);
    
    // Labels for the primary stat on greedy sets
    const GREEDY_LABELS = {
        enmity:          { key: 'enmity',  label: 'Enmity',  color: 'text-yellow-400' },
        passive_refresh: { key: 'refresh', label: 'Refresh', color: 'text-blue-400'   },
        passive_regen:   { key: 'regen',   label: 'Regen',   color: 'text-green-400'  },
        sird:            { key: 'spell_interruption_rate_down', label: 'SIRD', color: 'text-teal-400' },
        hp_ehp:          { key: 'ehp',     label: 'EHP',     color: 'text-purple-400' },
        pdt_eva:         { key: 'evasion', label: 'Evasion', color: 'text-orange-400' },
        mdt_meva:        { key: 'magic_evasion', label: 'M.Eva', color: 'text-cyan-400' },
    };
    const greedyMeta = GREEDY_LABELS[dtType];
    
    let html = '<div class="space-y-4">';
    
    for (const result of results) {
        const dtPct = result.dt_pct?.toFixed(1) || '0';
        const pdtPct = result.pdt_pct?.toFixed(1) || '0';
        const mdtPct = result.mdt_pct?.toFixed(1) || '0';
        const physReduction = result.physical_reduction?.toFixed(1) || '0';
        const magReduction = result.magical_reduction?.toFixed(1) || '0';
        
        const dtCapped = result.dt_capped || result.dt_pct <= -50;
        const pdtCapped = result.pdt_pct <= -50;
        const mdtCapped = result.mdt_pct <= -50;
        
        const hasTPMetrics = typeof result.time_to_ws === 'number' && !isNaN(result.time_to_ws);
        const timeToWS = hasTPMetrics ? result.time_to_ws.toFixed(2) : '?';
        const wsPerMin = hasTPMetrics ? (60 / result.time_to_ws).toFixed(2) : '?';
        const tpPerRound = typeof result.tp_per_round === 'number' ? result.tp_per_round.toFixed(1) : '?';
        
        // Primary stat display for greedy sets
        let primaryBadge = '';
        if (greedyMeta) {
            if (dtType === 'hp_ehp') {
                const ehpVal = result.ehp != null ? Math.round(result.ehp).toLocaleString() : '?';
                primaryBadge = `<span class="${greedyMeta.color} font-bold">EHP ${ehpVal}</span>
                                <span class="text-ffxi-text-dim mx-1">|</span>`;
            } else if (dtType === 'sird') {
                const sirdVal = result.spell_interruption_rate_down || 0;
                const sirdCapped = sirdVal >= 102;
                primaryBadge = `<span class="${sirdCapped ? 'text-ffxi-green' : greedyMeta.color} font-bold">SIRD ${sirdVal}% / 102%${sirdCapped ? ' ✓' : ''}</span>
                                <span class="text-ffxi-text-dim mx-1">|</span>`;
            } else {
                const primaryVal = result[greedyMeta.key] || 0;
                primaryBadge = `<span class="${greedyMeta.color} font-bold">${greedyMeta.label} +${primaryVal}</span>
                                <span class="text-ffxi-text-dim mx-1">|</span>`;
            }
        }
        
        html += `
            <div class="result-card bg-ffxi-dark rounded-lg p-4 border border-ffxi-border hover:border-ffxi-accent transition-colors cursor-pointer"
                 onclick="showResultDetails(${result.rank - 1})">
                <div class="flex items-center justify-between mb-3">
                    <span class="text-ffxi-accent font-display text-lg">#${result.rank}</span>
                    <div class="text-right">
                        ${primaryBadge}
                        <span class="text-ffxi-green font-bold">${physReduction}% Phys</span>
                        <span class="text-ffxi-text-dim mx-1">|</span>
                        <span class="text-ffxi-accent font-bold">${magReduction}% Mag</span>
                    </div>
                </div>
                ${dtType === 'hp_ehp' ? `
                <div class="grid grid-cols-2 gap-2 text-xs mb-3">
                    <div class="p-2 rounded ${pdtCapped ? 'bg-ffxi-green/20' : 'bg-ffxi-dark-lighter'}">
                        <span class="block text-ffxi-text font-bold">${pdtPct}%</span>
                        <span class="text-ffxi-text-dim">eff. PDT ${pdtCapped ? '✓' : ''}</span>
                    </div>
                    <div class="p-2 rounded ${mdtCapped ? 'bg-ffxi-green/20' : 'bg-ffxi-dark-lighter'}">
                        <span class="block text-ffxi-text font-bold">${mdtPct}%</span>
                        <span class="text-ffxi-text-dim">eff. MDT ${mdtCapped ? '✓' : ''}</span>
                    </div>
                </div>
                ` : `
                <div class="grid grid-cols-3 gap-2 text-xs mb-3">
                    <div class="p-2 rounded ${dtCapped ? 'bg-ffxi-green/20' : 'bg-ffxi-dark-lighter'}">
                        <span class="block text-ffxi-text font-bold">${dtPct}%</span>
                        <span class="text-ffxi-text-dim">DT ${dtCapped ? '✓' : ''}</span>
                    </div>
                    <div class="p-2 rounded ${pdtCapped ? 'bg-ffxi-green/20' : 'bg-ffxi-dark-lighter'}">
                        <span class="block text-ffxi-text font-bold">${pdtPct}%</span>
                        <span class="text-ffxi-text-dim">PDT ${pdtCapped ? '✓' : ''}</span>
                    </div>
                    <div class="p-2 rounded ${mdtCapped ? 'bg-ffxi-green/20' : 'bg-ffxi-dark-lighter'}">
                        <span class="block text-ffxi-text font-bold">${mdtPct}%</span>
                        <span class="text-ffxi-text-dim">MDT ${mdtCapped ? '✓' : ''}</span>
                    </div>
                </div>
                `}
                ${hasTPMetrics ? `
                <div class="grid grid-cols-3 gap-2 text-xs text-ffxi-text-dim mb-3 border-t border-ffxi-border pt-3">
                    <div>
                        <span class="block text-ffxi-yellow font-bold">${timeToWS}s</span>
                        Time to WS
                    </div>
                    <div>
                        <span class="block text-ffxi-text">${wsPerMin}</span>
                        WS/min
                    </div>
                    <div>
                        <span class="block text-ffxi-text">${tpPerRound}</span>
                        TP/Round
                    </div>
                </div>
                ` : ''}
                <div class="grid grid-cols-4 gap-2 text-xs text-ffxi-text-dim mb-3">
                    <div>
                        <span class="block text-ffxi-text">${result.hp || 0}</span>
                        HP
                    </div>
                    <div>
                        <span class="block text-ffxi-text">${result.defense || 0}</span>
                        Defense
                    </div>
                    <div>
                        <span class="block ${dtType === 'passive_refresh' ? 'text-blue-400 font-bold' : 'text-ffxi-text'}">${result.refresh || 0}</span>
                        Refresh
                    </div>
                    <div>
                        <span class="block ${dtType === 'passive_regen' ? 'text-green-400 font-bold' : 'text-ffxi-text'}">${result.regen || 0}</span>
                        Regen
                    </div>
                </div>
                ${dtType === 'enmity' ? `
                <div class="text-xs text-ffxi-text-dim border-t border-ffxi-border pt-2">
                    <span class="text-ffxi-text-dim">Enmity: </span>
                    <span class="text-yellow-400 font-bold">+${result.enmity || 0}</span>
                </div>
                ` : ''}
                ${dtType === 'sird' ? `
                <div class="text-xs text-ffxi-text-dim border-t border-ffxi-border pt-2">
                    <span class="text-ffxi-text-dim">SIRD: </span>
                    <span class="${(result.spell_interruption_rate_down || 0) >= 102 ? 'text-ffxi-green' : 'text-teal-400'} font-bold">${result.spell_interruption_rate_down || 0}% / 102%</span>
                </div>
                ` : ''}
                <div class="text-xs text-ffxi-text-dim">
                    ${formatGearSummary(result.gear)}
                </div>
            </div>
        `;
    }
    
    html += '</div>';
    content.innerHTML = html;
    
    if (results.length > 0) {
        document.getElementById('lua-section')?.classList.remove('hidden');
        generateLuaOutput(results[0]);
        displayDTStats(results[0], dtType);
    }
}

function displayDTStats(result, dtType) {
    console.log('displayDTStats called with result:', result, 'dtType:', dtType);
    
    const statsContent = document.getElementById('stats-content');
    if (!statsContent) {
        console.warn('stats-content element not found');
        return;
    }
    
    const hasTPMetrics = typeof result.time_to_ws === 'number' && !isNaN(result.time_to_ws);
    const timeToWS = hasTPMetrics ? result.time_to_ws.toFixed(2) : '?';
    const wsPerMin = hasTPMetrics ? (60 / result.time_to_ws).toFixed(2) : '?';
    const tpPerRound = typeof result.tp_per_round === 'number' ? result.tp_per_round.toFixed(1) : '?';
    const dps = typeof result.dps === 'number' ? result.dps.toFixed(0) : '?';
    
    const mainWeaponName = result.gear?.main?.name2 || result.gear?.main?.name || 'Unknown';
    const hasWeaponInGear = result.gear?.main && result.gear.main.name !== 'Empty';
    
    // Greedy-type primary stat block
    const GREEDY_STATS = {
        enmity:          { key: 'enmity',  label: 'Enmity',  color: 'text-yellow-400' },
        passive_refresh: { key: 'refresh', label: 'Refresh', color: 'text-blue-400'   },
        passive_regen:   { key: 'regen',   label: 'Regen',   color: 'text-green-400'  },
        sird:            { key: 'spell_interruption_rate_down', label: 'SIRD', color: 'text-teal-400' },
        hp_ehp:          { key: 'ehp',     label: 'EHP',     color: 'text-purple-400' },
        pdt_eva:         { key: 'evasion', label: 'Evasion', color: 'text-orange-400' },
        mdt_meva:        { key: 'magic_evasion', label: 'M.Eva', color: 'text-cyan-400' },
    };
    const greedyMeta = GREEDY_STATS[dtType];

    let greedyBlock = '';
    if (greedyMeta) {
        if (dtType === 'hp_ehp') {
            const ehpVal = result.ehp != null ? Math.round(result.ehp).toLocaleString() : '?';
            const physEHP = result.hp && result.physical_reduction != null
                ? Math.round(result.hp / (1 - result.physical_reduction / 100)).toLocaleString()
                : '?';
            const magEHP = result.hp && result.magical_reduction != null
                ? Math.round(result.hp / (1 - result.magical_reduction / 100)).toLocaleString()
                : '?';
            greedyBlock = `
                <div class="border-t border-ffxi-border my-2 pt-2">
                    <div class="text-purple-400 font-medium mb-1">Effective HP</div>
                    <div class="flex justify-between">
                        <span class="text-ffxi-text-dim">EHP (worst-case):</span>
                        <span class="text-purple-400 font-bold">${ehpVal}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-ffxi-text-dim">Phys EHP:</span>
                        <span class="text-ffxi-green">${physEHP}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-ffxi-text-dim">Magic EHP:</span>
                        <span class="text-ffxi-accent">${magEHP}</span>
                    </div>
                    <div class="text-ffxi-text-dim text-xs mt-1">
                        PDT/MDT include DT contribution.<br>
                        Ranked by min(Phys EHP, Magic EHP).
                    </div>
                </div>
            `;
        } else if (dtType === 'sird') {
            const sirdVal = result.spell_interruption_rate_down || 0;
            const sirdCapped = sirdVal >= 102;
            greedyBlock = `
                <div class="border-t border-ffxi-border my-2 pt-2">
                    <div class="text-teal-400 font-medium mb-1">Spell Interruption Rate Down</div>
                    <div class="flex justify-between">
                        <span class="text-ffxi-text-dim">SIRD:</span>
                        <span class="${sirdCapped ? 'text-ffxi-green' : 'text-teal-400'} font-bold">${sirdVal}% / 102%${sirdCapped ? ' ✓' : ''}</span>
                    </div>
                    <div class="text-ffxi-text-dim text-xs mt-1">
                        Greedy: best SIRD item per slot.<br>Cap is 102% — spells cannot be interrupted.
                    </div>
                </div>
            `;
        } else {
            greedyBlock = `
                <div class="border-t border-ffxi-border my-2 pt-2">
                    <div class="${greedyMeta.color} font-medium mb-1">${greedyMeta.label} Stats</div>
                    <div class="flex justify-between">
                        <span class="text-ffxi-text-dim">${greedyMeta.label}:</span>
                        <span class="${greedyMeta.color} font-bold">+${result[greedyMeta.key] || 0}</span>
                    </div>
                    <div class="text-ffxi-text-dim text-xs mt-1">
                        Greedy: best ${greedyMeta.label.toLowerCase()} item per slot,<br>remaining slots filled with DT.
                    </div>
                </div>
            `;
        }
    }
    statsContent.innerHTML = `
        <div class="text-xs space-y-1">
            <div class="text-ffxi-accent font-medium mb-2">DT Stats</div>
            ${dtType === 'hp_ehp' ? `
            <div class="flex justify-between">
                <span class="text-ffxi-text-dim">eff. PDT:</span>
                <span class="text-ffxi-text ${result.pdt_pct <= -50 ? 'text-ffxi-green' : ''}">${result.pdt_pct?.toFixed(1)}%</span>
            </div>
            <div class="flex justify-between">
                <span class="text-ffxi-text-dim">eff. MDT:</span>
                <span class="text-ffxi-text ${result.mdt_pct <= -50 ? 'text-ffxi-green' : ''}">${result.mdt_pct?.toFixed(1)}%</span>
            </div>
            <div class="text-ffxi-text-dim text-xs mt-1">DT contribution folded into PDT &amp; MDT.</div>
            ` : `
            <div class="flex justify-between">
                <span class="text-ffxi-text-dim">DT:</span>
                <span class="text-ffxi-text ${result.dt_capped || result.dt_pct <= -50 ? 'text-ffxi-green' : ''}">${result.dt_pct?.toFixed(1)}%</span>
            </div>
            <div class="flex justify-between">
                <span class="text-ffxi-text-dim">PDT:</span>
                <span class="text-ffxi-text ${result.pdt_pct <= -50 ? 'text-ffxi-green' : ''}">${result.pdt_pct?.toFixed(1)}%</span>
            </div>
            <div class="flex justify-between">
                <span class="text-ffxi-text-dim">MDT:</span>
                <span class="text-ffxi-text ${result.mdt_pct <= -50 ? 'text-ffxi-green' : ''}">${result.mdt_pct?.toFixed(1)}%</span>
            </div>
            `}
            <div class="border-t border-ffxi-border my-2 pt-2">
                <div class="flex justify-between">
                    <span class="text-ffxi-text-dim">Physical Reduction:</span>
                    <span class="text-ffxi-green font-bold">${result.physical_reduction?.toFixed(1)}%</span>
                </div>
                <div class="flex justify-between">
                    <span class="text-ffxi-text-dim">Magical Reduction:</span>
                    <span class="text-ffxi-accent font-bold">${result.magical_reduction?.toFixed(1)}%</span>
                </div>
            </div>
            ${greedyBlock}
            ${hasTPMetrics ? `
            <div class="border-t border-ffxi-border my-2 pt-2">
                <div class="text-ffxi-yellow font-medium mb-1">TP vs Apex Leech</div>
                ${hasWeaponInGear ? `<div class="text-ffxi-text-dim mb-1">Using: ${mainWeaponName}</div>` : ''}
                <div class="flex justify-between">
                    <span class="text-ffxi-text-dim">Time to WS:</span>
                    <span class="text-ffxi-yellow font-bold">${timeToWS}s</span>
                </div>
                <div class="flex justify-between">
                    <span class="text-ffxi-text-dim">WS/min:</span>
                    <span class="text-ffxi-text">${wsPerMin}</span>
                </div>
                <div class="flex justify-between">
                    <span class="text-ffxi-text-dim">TP/Round:</span>
                    <span class="text-ffxi-text">${tpPerRound}</span>
                </div>
                <div class="flex justify-between">
                    <span class="text-ffxi-text-dim">TP Phase DPS:</span>
                    <span class="text-ffxi-text">${dps}</span>
                </div>
            </div>
            ` : `
            <div class="border-t border-ffxi-border my-2 pt-2">
                <div class="text-ffxi-text-dim text-center py-2">
                    ${hasWeaponInGear ? 'TP calculation unavailable' : 'Select a weapon or enable "Include Weapons" to see TP metrics'}
                </div>
            </div>
            `}
            <div class="border-t border-ffxi-border my-2 pt-2">
                <div class="flex justify-between">
                    <span class="text-ffxi-text-dim">HP:</span>
                    <span class="text-ffxi-text">${result.hp || 0}</span>
                </div>
                <div class="flex justify-between">
                    <span class="text-ffxi-text-dim">Defense:</span>
                    <span class="text-ffxi-text">${result.defense || 0}</span>
                </div>
                <div class="flex justify-between">
                    <span class="text-ffxi-text-dim">Evasion:</span>
                    <span class="text-ffxi-text">${result.evasion || 0}</span>
                </div>
                <div class="flex justify-between">
                    <span class="text-ffxi-text-dim">Magic Evasion:</span>
                    <span class="text-ffxi-text">${result.magic_evasion || 0}</span>
                </div>
                <div class="flex justify-between">
                    <span class="text-ffxi-text-dim">Refresh:</span>
                    <span class="text-ffxi-text">${result.refresh || 0}</span>
                </div>
                <div class="flex justify-between">
                    <span class="text-ffxi-text-dim">Regen:</span>
                    <span class="text-ffxi-text">${result.regen || 0}</span>
                </div>
                ${result.enmity ? `
                <div class="flex justify-between">
                    <span class="text-ffxi-text-dim">Enmity:</span>
                    <span class="text-yellow-400">+${result.enmity}</span>
                </div>
                ` : ''}
                ${result.spell_interruption_rate_down ? `
                <div class="flex justify-between">
                    <span class="text-ffxi-text-dim">SIRD:</span>
                    <span class="${result.spell_interruption_rate_down >= 102 ? 'text-ffxi-green' : 'text-teal-400'}">${result.spell_interruption_rate_down}%</span>
                </div>
                ` : ''}
            </div>
        </div>
    `;
}

function showResultDetails(index) {
    if (!AppState.currentResults || !AppState.currentResults[index]) return;
    
    const result = AppState.currentResults[index];
    
    // Generate Lua output
    generateLuaOutput(result);
    
    // Handle stats display based on result type
    if (AppState.currentResultType === 'dt') {
        // DT results have their own stats format
        displayDTStats(result, AppState.currentDTType);
    } else {
        // TP/WS results use wsdist calculation
        calculateAndDisplayStats(result);
    }
    
    // Scroll to Lua section on mobile
    document.getElementById('lua-section')?.scrollIntoView({ behavior: 'smooth' });
}

async function calculateAndDisplayStats(result) {
    console.log('calculateAndDisplayStats called with result:', result);
    if (!result || !result.gear) {
        console.warn('calculateAndDisplayStats: No result or gear data');
        return;
    }
    
    // Build the gearset in wsdist format
    const gearset = {};
    for (const [slot, item] of Object.entries(result.gear)) {
        if (item && item.name !== 'Empty') {
            // We need the full item data, use what we have
            gearset[slot] = {
                Name: item.name,
                Name2: item.name2 || item.name,
                ...item,
            };
        } else {
            gearset[slot] = { Name: 'Empty', Name2: 'Empty', Type: 'None' };
        }
    }
    
    // Add weapons from state
    if (AppState.selectedMainWeapon?._raw) {
        gearset.main = AppState.selectedMainWeapon._raw;
    }
    if (AppState.selectedSubWeapon?._raw) {
        gearset.sub = AppState.selectedSubWeapon._raw;
    }
    
    console.log('Built gearset for stats calculation:', gearset);
    
    // Get the current tab's state for buffs/debuffs/target
    let tabState;
    if (AppState.currentTab === 'ws') {
        tabState = AppState.ws;
    } else if (AppState.currentTab === 'tp') {
        tabState = AppState.tp;
    } else if (AppState.currentTab === 'magic') {
        // Magic tab uses its own state structure
        tabState = {
            buffs: AppState.magic.buffs,
            abilities: [],
            food: AppState.magic.buffs.food || '',
            target: AppState.magic.target,
            debuffs: AppState.magic.debuffs,
        };
    } else {
        // Default fallback
        tabState = AppState.tp;
    }
    
    try {
        // Build buffs object, including custom buffs
        let buffs = { ...tabState.buffs };
        
        // Add custom buffs based on current tab
        if (AppState.currentTab === 'magic') {
            // Magic tab uses magic custom buffs
            const magicCustomBuffs = getMagicCustomBuffsForPayload();
            if (magicCustomBuffs) {
                buffs.custom = magicCustomBuffs;
            }
        } else {
            // TP/WS tabs use physical custom buffs
            const physicalCustomBuffs = getPhysicalCustomBuffsForPayload();
            if (physicalCustomBuffs) {
                buffs.custom = physicalCustomBuffs;
            }
        }
        
        const requestPayload = {
            job: AppState.selectedJob,
            sub_job: AppState.selectedSubJob || 'war',
            master_level: AppState.masterLevel,
            gearset: gearset,
            buffs: buffs,
            abilities: tabState.abilities,
            food: tabState.food,
            target: tabState.target,
            debuffs: tabState.debuffs,
        };
        console.log('Sending stats calculation request:', requestPayload);
        
        const response = await API.calculateStats(requestPayload);
        
        console.log('Stats calculation response:', response);
        
        if (response.success && response.stats) {
            displayStats(response.stats);
        } else {
            console.error('Stats calculation failed:', response.error);
        }
    } catch (error) {
        console.error('Failed to calculate stats:', error);
    }
}

function displayStats(stats) {
    console.log('displayStats called with:', stats);
    
    const statsContent = document.getElementById('stats-content');
    if (!statsContent) {
        console.warn('stats-content element not found');
        return;
    }
    
    // Build the HTML structure dynamically
    const mlText = stats.master_level > 0 ? ` ML${stats.master_level}` : '';
    const jpStatus = stats.jp_spent > 0 ? `<span class="text-ffxi-green text-xs">✓ ${stats.jp_spent} JP</span>` : '';
    
    // Primary stats
    const primaryStats = stats.primary_stats || {};
    
    // TP stats
    const tpStats = stats.tp_stats || {};
    const gearHaste = ((tpStats.gear_haste ?? 0) / 100).toFixed(1);
    const dualWield = ((tpStats.dual_wield ?? 0) / 100).toFixed(0);
    const doubleAttack = ((tpStats.double_attack ?? 0) / 100).toFixed(0);
    const tripleAttack = ((tpStats.triple_attack ?? 0) / 100).toFixed(0);
    const quadAttack = ((tpStats.quad_attack ?? 0) / 100).toFixed(0);
    
    // Offensive stats
    const offStats = stats.offensive_stats || {};
    const critRate = ((offStats.crit_rate ?? 0) / 100).toFixed(0);
    const critDmg = ((offStats.crit_damage ?? 0) / 100).toFixed(0);
    const wsDamage = ((offStats.ws_damage ?? 0) / 100).toFixed(0);
    const pdl = ((offStats.pdl ?? 0) / 100).toFixed(0);
    
    // Defensive stats
    const defStats = stats.defensive_stats || {};
    const dt = ((defStats.dt ?? 0) / 100).toFixed(0);
    const pdt = ((defStats.pdt ?? 0) / 100).toFixed(0);
    const mdt = ((defStats.mdt ?? 0) / 100).toFixed(0);
    
    // Accuracy breakdown
    const accBreakdown = stats.accuracy_breakdown || {};
    const vsTarget = stats.vs_target || {};
    const accDiff = vsTarget.acc_differential ?? 0;
    const accDiffStr = accDiff >= 0 ? `+${accDiff}` : accDiff;
    
    // Accuracy status
    let accStatusHtml = '';
    if (vsTarget.acc_capped) {
        accStatusHtml = '<div class="text-center py-1 rounded text-xs font-medium bg-ffxi-green/20 text-ffxi-green">✓ Accuracy Capped!</div>';
    } else if ((vsTarget.hit_rate ?? 0) >= 90) {
        accStatusHtml = '<div class="text-center py-1 rounded text-xs font-medium bg-yellow-500/20 text-yellow-400">◎ Near Cap</div>';
    } else {
        accStatusHtml = '<div class="text-center py-1 rounded text-xs font-medium bg-ffxi-red/20 text-ffxi-red">✗ Need more accuracy</div>';
    }
    
    statsContent.innerHTML = `
        <div class="text-xs space-y-3">
            <!-- Header -->
            <div class="flex justify-between items-center">
                <span class="text-ffxi-accent font-medium">${stats.job || ''}${mlText}/${stats.sub_job || ''}</span>
                ${jpStatus}
            </div>
            
            <!-- Primary Stats -->
            <div class="border-t border-ffxi-border pt-2">
                <div class="text-ffxi-text-dim mb-1 font-medium">Primary Stats</div>
                <div class="grid grid-cols-4 gap-1">
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">STR</span><span class="text-ffxi-text">${primaryStats.STR ?? 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">DEX</span><span class="text-ffxi-text">${primaryStats.DEX ?? 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">VIT</span><span class="text-ffxi-text">${primaryStats.VIT ?? 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">AGI</span><span class="text-ffxi-text">${primaryStats.AGI ?? 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">INT</span><span class="text-ffxi-text">${primaryStats.INT ?? 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">MND</span><span class="text-ffxi-text">${primaryStats.MND ?? 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">CHR</span><span class="text-ffxi-text">${primaryStats.CHR ?? 0}</span></div>
                </div>
            </div>
            
            <!-- TP Stats -->
            <div class="border-t border-ffxi-border pt-2">
                <div class="text-ffxi-text-dim mb-1 font-medium">TP Stats</div>
                <div class="grid grid-cols-2 gap-1">
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">Store TP</span><span class="text-ffxi-text">${tpStats.store_tp ?? 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">Gear Haste</span><span class="text-ffxi-text">${gearHaste}%</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">Dual Wield</span><span class="text-ffxi-text">${dualWield}%</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">DA</span><span class="text-ffxi-text">${doubleAttack}%</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">TA</span><span class="text-ffxi-text">${tripleAttack}%</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">QA</span><span class="text-ffxi-text">${quadAttack}%</span></div>
                </div>
            </div>
            
            <!-- Offensive Stats -->
            <div class="border-t border-ffxi-border pt-2">
                <div class="text-ffxi-text-dim mb-1 font-medium">Offensive</div>
                <div class="grid grid-cols-2 gap-1">
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">Accuracy</span><span class="text-ffxi-text">${offStats.accuracy ?? 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">Attack</span><span class="text-ffxi-text">${offStats.attack ?? 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">Crit Rate</span><span class="text-ffxi-text">${critRate}%</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">Crit Dmg</span><span class="text-ffxi-text">${critDmg}%</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">WS Damage</span><span class="text-ffxi-text">${wsDamage}%</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">PDL</span><span class="text-ffxi-text">${pdl}%</span></div>
                </div>
            </div>
            
            <!-- Defensive Stats -->
            <div class="border-t border-ffxi-border pt-2">
                <div class="text-ffxi-text-dim mb-1 font-medium">Defensive</div>
                <div class="grid grid-cols-2 gap-1">
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">HP</span><span class="text-ffxi-text">${defStats.hp ?? 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">Defense</span><span class="text-ffxi-text">${defStats.defense ?? 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">Evasion</span><span class="text-ffxi-text">${defStats.evasion ?? 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">DT</span><span class="text-ffxi-text">${dt}%</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">PDT</span><span class="text-ffxi-text">${pdt}%</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">MDT</span><span class="text-ffxi-text">${mdt}%</span></div>
                </div>
            </div>
            
            <!-- Accuracy vs Target -->
            <div class="border-t border-ffxi-border pt-2">
                <div class="text-ffxi-text-dim mb-1 font-medium">vs ${vsTarget.target_name || 'Target'} (Lv${vsTarget.target_level || 0})</div>
                <div class="space-y-1">
                    <div class="flex justify-between">
                        <span class="text-ffxi-text-dim">Your Accuracy</span>
                        <span class="text-ffxi-text">${accBreakdown.total ?? 0}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-ffxi-text-dim">Target Evasion</span>
                        <span class="text-ffxi-text">${vsTarget.target_evasion ?? 0}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-ffxi-text-dim">Acc Differential</span>
                        <span class="text-ffxi-text ${accDiff >= 0 ? 'text-ffxi-green' : 'text-ffxi-red'}">${accDiffStr}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-ffxi-text-dim">Hit Rate</span>
                        <span class="text-ffxi-text">${vsTarget.hit_rate ?? 0}%</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-ffxi-text-dim">WS Hit Rate</span>
                        <span class="text-ffxi-text">${vsTarget.ws_hit_rate ?? 0}%</span>
                    </div>
                </div>
                <div class="mt-2">
                    ${accStatusHtml}
                </div>
            </div>
        </div>
    `;
    
    console.log('displayStats completed successfully');
}

/**
 * Format a gear item for Lua output.
 * Uses proper GearSwap syntax with augments table when augments are present.
 * 
 * @param {Object} item - The gear item with name, augments, etc.
 * @returns {string} Formatted Lua string for the item
 */
function formatLuaItem(item) {
    if (!item) return '"Empty"';
    
    // Get base name (not name2 which may include augment suffix)
    const name = item.name || 'Empty';
    if (name === 'Empty') return '"Empty"';
    
    // Check for augments (_augments is our convention, also check augments/Augments)
    const augments = item._augments || item.augments || item.Augments;
    
    if (!augments || !Array.isArray(augments) || augments.length === 0) {
        // Simple item - just the name
        return `"${name}"`;
    }
    
    // Augmented item - use table syntax with single quotes for augments
    // { name="Item Name", augments={'aug1', 'aug2'} }
    const augStr = augments
        .filter(a => a && a !== 'none' && a !== '')
        .map(a => `'${a}'`)
        .join(', ');
    
    if (!augStr) {
        return `"${name}"`;
    }
    
    return `{ name="${name}", augments={${augStr}} }`;
}

function generateLuaOutput(result) {
    if (!result || !result.gear) return;
    
    const luaOutput = document.getElementById('lua-output');
    if (!luaOutput) return;
    
    let setName;
    if (AppState.currentTab === 'tp') {
        setName = 'sets.engaged';
    } else if (AppState.currentTab === 'ws') {
        const wsName = AppState.selectedWeaponskill?.name || 'WS';
        setName = `sets.precast.WS["${wsName}"]`;
    } else if (AppState.currentTab === 'magic') {
        // Magic tab uses its own function
        return;
    } else {
        setName = 'sets.engaged';
    }
    
    let lua = `${setName} = {\n`;
    
    const slotOrder = ['main', 'sub', 'ranged', 'ammo', 'head', 'neck', 'ear1', 'ear2', 
                       'body', 'hands', 'ring1', 'ring2', 'back', 'waist', 'legs', 'feet'];

    // Fix empyrean earring slot order: shallow copy so we don't mutate result.gear
    const gear = { ...result.gear };
    const ear1Name = gear['ear1']?.name || '';
    if (isEmpyreanEarring(ear1Name)) {
        const tmp = gear['ear1'];
        gear['ear1'] = gear['ear2'] || null;
        gear['ear2'] = tmp;
    }
    
    for (const slot of slotOrder) {
        if (gear[slot] && gear[slot].name !== 'Empty') {
            const luaSlot = slot === 'ear1' ? 'left_ear' : 
                           slot === 'ear2' ? 'right_ear' :
                           slot === 'ring1' ? 'left_ring' :
                           slot === 'ring2' ? 'right_ring' : slot;
            const itemStr = formatLuaItem(gear[slot]);
            lua += `    ${luaSlot}=${itemStr},\n`;
        }
    }
    
    lua += '}';
    
    luaOutput.textContent = lua;
}

function copyLuaToClipboard() {
    const luaOutput = document.getElementById('lua-output');
    if (!luaOutput) return;
    
    navigator.clipboard.writeText(luaOutput.textContent)
        .then(() => showToast('Copied to clipboard!', 'success'))
        .catch(() => showToast('Failed to copy', 'error'));
}

// =============================================================================
// UI STATE HELPERS
// =============================================================================

function clearWeaponSelections() {
    // Clear main weapon
    const mainContainer = document.getElementById('main-weapon-container');
    if (mainContainer) {
        mainContainer.innerHTML = '<input type="text" class="input-field w-full" placeholder="Select job first..." disabled>';
    }
    
    // Clear sub weapon
    const subContainer = document.getElementById('sub-item-container');
    if (subContainer) {
        subContainer.innerHTML = '<input type="text" class="input-field w-full" placeholder="Select main weapon first..." disabled>';
    }
    
    // Hide sections
    document.getElementById('sub-item-section')?.classList.add('hidden');
    document.getElementById('dw-checkbox-section')?.classList.add('hidden');
    document.getElementById('weapon-info')?.classList.add('hidden');
    
    // Reset WS select
    const wsSelect = document.getElementById('ws-select');
    if (wsSelect) {
        wsSelect.innerHTML = '<option value="">Select weapon first...</option>';
        wsSelect.disabled = true;
    }
}

function updateInventorySummary(count, filename) {
    const summary = document.getElementById('inventory-summary');
    if (summary) {
        summary.innerHTML = `
            <p class="text-ffxi-text">${count} items</p>
            <p class="text-xs text-ffxi-text-dim truncate">${filename}</p>
        `;
    }
    
    // Update character summary in modal
    const charItems = document.getElementById('char-items');
    if (charItems) charItems.textContent = count;
    
    const charSummary = document.getElementById('character-summary');
    if (charSummary) charSummary.classList.remove('hidden');
}

function showMasterLevelSection() {
    const section = document.getElementById('master-level-section');
    if (section) section.classList.remove('hidden');
}

function hideMasterLevelSection() {
    const section = document.getElementById('master-level-section');
    if (section) section.classList.add('hidden');
    AppState.masterLevel = 0;
}

function updateMasterLevelBonuses(level) {
    AppState.masterLevel = level;
    
    const statBonus = document.getElementById('ml-stat-bonus');
    const hpBonus = document.getElementById('ml-hp-bonus');
    
    if (statBonus) statBonus.textContent = level;
    if (hpBonus) hpBonus.textContent = level * 25;
}

// =============================================================================
// MAGIC TAB FUNCTIONS
// =============================================================================

async function setupMagicTab() {
    // Load and populate magic buff selectors from API
    await populateMagicBuffSelectors();
    
    // Load spell categories
    const categorySelect = document.getElementById('magic-category-select');
    if (!categorySelect) return;
    
    try {
        const { categories } = await API.getSpells();
        if (categories && categories.length > 0) {
            AppState.spellCategories = categories;
            
            // Populate category dropdown
            categorySelect.innerHTML = '<option value="">Select Category...</option>';
            categories.forEach(cat => {
                const option = document.createElement('option');
                option.value = cat.id;
                option.textContent = `${cat.name} (${cat.spells.length})`;
                categorySelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Failed to load spell categories:', error);
    }
    
    // Category selection handler
    categorySelect.addEventListener('change', handleMagicCategoryChange);
    
    // Spell selection handler
    const spellSelect = document.getElementById('magic-spell-select');
    if (spellSelect) {
        spellSelect.addEventListener('change', handleMagicSpellChange);
    }
    
    // Optimization type handler
    const optTypeSelect = document.getElementById('magic-opt-type');
    if (optTypeSelect) {
        optTypeSelect.addEventListener('change', handleMagicOptTypeChange);
    }
    
    // Magic burst toggle
    const mbToggle = document.getElementById('magic-burst-toggle');
    if (mbToggle) {
        mbToggle.addEventListener('change', (e) => {
            AppState.magic.magicBurst = e.target.checked;
            // Show/hide skillchain steps based on MB state
            const scSection = document.getElementById('magic-sc-steps-section');
            if (scSection) {
                scSection.style.display = e.target.checked ? 'block' : 'none';
            }
        });
    }
    
    // Skillchain steps
    const scStepsSelect = document.getElementById('magic-sc-steps');
    if (scStepsSelect) {
        scStepsSelect.addEventListener('change', (e) => {
            AppState.magic.skillchainSteps = parseInt(e.target.value);
        });
    }
    
    // Include weapons toggle
    const weaponsToggle = document.getElementById('magic-include-weapons');
    if (weaponsToggle) {
        weaponsToggle.addEventListener('change', (e) => {
            AppState.magic.includeWeapons = e.target.checked;
        });
    }
    
    // Target selection - load dynamically from API
    const targetSelect = document.getElementById('magic-target-select');
    if (targetSelect) {
        // Load targets from API and render with Sortie boss grouping
        try {
            const { targets } = await API.getMagicTargets();
            if (targets && targets.length > 0) {
                const SORTIE_FLOOR_IDS    = ['sortie_ghatjot','sortie_leshonn','sortie_skomora','sortie_degei'];
                const SORTIE_BASEMENT_IDS = ['sortie_dhartok','sortie_gartell','sortie_triboulex','sortie_aita'];
                const sortieIds = new Set([...SORTIE_FLOOR_IDS, ...SORTIE_BASEMENT_IDS, 'sortie_boss']);

                targetSelect.innerHTML = '';

                // Generic targets sorted by MEva
                const generic = targets.filter(t => !sortieIds.has(t.id)).sort((a, b) => a.magic_evasion - b.magic_evasion);
                generic.forEach(t => {
                    const opt = document.createElement('option');
                    opt.value = t.id;
                    opt.textContent = `${t.name} (${t.magic_evasion} MEva)`;
                    targetSelect.appendChild(opt);
                });

                // Sortie floor bosses
                const floorBosses = targets.filter(t => SORTIE_FLOOR_IDS.includes(t.id));
                if (floorBosses.length > 0) {
                    const grp = document.createElement('optgroup');
                    grp.label = 'Sortie Floor Bosses (2000 Gal)';
                    floorBosses.forEach(t => {
                        const opt = document.createElement('option');
                        opt.value = t.id;
                        opt.textContent = `${t.name} (${t.magic_evasion} MEva)`;
                        grp.appendChild(opt);
                    });
                    targetSelect.appendChild(grp);
                }

                // Sortie basement bosses
                const basementBosses = targets.filter(t => SORTIE_BASEMENT_IDS.includes(t.id));
                if (basementBosses.length > 0) {
                    const grp = document.createElement('optgroup');
                    grp.label = 'Sortie Basement Bosses (10000 Gal)';
                    basementBosses.forEach(t => {
                        const opt = document.createElement('option');
                        opt.value = t.id;
                        opt.textContent = `${t.name} (${t.magic_evasion} MEva)`;
                        grp.appendChild(opt);
                    });
                    targetSelect.appendChild(grp);
                }

                // Set default selection
                if (AppState.magic.target && targets.find(t => t.id === AppState.magic.target)) {
                    targetSelect.value = AppState.magic.target;
                } else {
                    const defaultTarget = targets.find(t => t.id === 'apex_mob');
                    if (defaultTarget) {
                        targetSelect.value = 'apex_mob';
                        AppState.magic.target = 'apex_mob';
                    } else {
                        AppState.magic.target = targets[0].id;
                    }
                }
            }
        } catch (error) {
            console.error('Failed to load magic targets:', error);
        }

        // Add change handler
        targetSelect.addEventListener('change', (e) => {
            AppState.magic.target = e.target.value;
        });
    }
    
    // Magic food selector
    const foodSelect = document.getElementById('magic-food-select');
    if (foodSelect) {
        foodSelect.addEventListener('change', (e) => {
            AppState.magic.buffs.food = e.target.value || null;
        });
    }
    
    // Magic BRD song selector
    const brdSelect = document.getElementById('magic-brd-song-add');
    if (brdSelect) {
        brdSelect.addEventListener('change', (e) => {
            if (e.target.value && AppState.magic.buffs.brd.length < 4) {
                addMagicBuffToList('brd', e.target.value);
                e.target.value = '';
            } else if (AppState.magic.buffs.brd.length >= 4) {
                showToast('Maximum 4 songs allowed', 'warning');
                e.target.value = '';
            }
        });
    }
    
    // Magic COR roll selector
    const corSelect = document.getElementById('magic-cor-roll-add');
    if (corSelect) {
        corSelect.addEventListener('change', (e) => {
            if (e.target.value && AppState.magic.buffs.cor.length < 2) {
                addMagicBuffToList('cor', e.target.value);
                e.target.value = '';
            } else if (AppState.magic.buffs.cor.length >= 2) {
                showToast('Maximum 2 rolls allowed', 'warning');
                e.target.value = '';
            }
        });
    }
    
    // Magic GEO bubble selector
    const geoSelect = document.getElementById('magic-geo-bubble-add');
    if (geoSelect) {
        geoSelect.addEventListener('change', (e) => {
            if (e.target.value && AppState.magic.buffs.geo.length < 3) {
                addMagicBuffToList('geo', e.target.value);
                e.target.value = '';
            } else if (AppState.magic.buffs.geo.length >= 3) {
                showToast('Maximum 3 bubbles allowed', 'warning');
                e.target.value = '';
            }
        });
    }
    
    // Magic SCH ability selector
    const schSelect = document.getElementById('magic-sch-ability-add');
    if (schSelect) {
        schSelect.addEventListener('change', (e) => {
            if (e.target.value) {
                addMagicBuffToList('sch', e.target.value);
                e.target.value = '';
            }
        });
    }
    
    // Magic WHM spell selector
    const whmSelect = document.getElementById('magic-whm-spell-add');
    if (whmSelect) {
        whmSelect.addEventListener('change', (e) => {
            if (e.target.value) {
                addMagicBuffToList('whm', e.target.value);
                e.target.value = '';
            }
        });
    }
    
    // Magic debuff selector
    const debuffSelect = document.getElementById('magic-debuff-add');
    if (debuffSelect) {
        debuffSelect.addEventListener('change', handleMagicDebuffAdd);
    }
    
    // Inject the healing-specific custom buff row (VIT + Cure Potency) into the
    // magic custom buffs panel if it doesn't already exist.
    // The row stays hidden until a Healing spell is selected.
    if (!document.getElementById('magic-healing-buffs')) {
        const panel = document.getElementById('magic-custom-buffs-panel');
        if (panel) {
            const healingRow = document.createElement('div');
            healingRow.id = 'magic-healing-buffs';
            healingRow.className = 'hidden border-t border-ffxi-border pt-2 mt-2';
            healingRow.innerHTML = `
                <div class="text-ffxi-text-dim text-xs font-medium mb-2 flex items-center gap-1">
                    <span class="text-pink-400">💚</span> Healing Buffs
                </div>
                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="text-ffxi-text-dim text-xs block mb-1">
                            VIT
                            <span class="text-ffxi-text-dim ml-1 opacity-60" title="VIT contributes floor(VIT/4) to the cure power formula">(?)</span>
                        </label>
                        <input id="magic-custom-vit" type="number" min="0" max="999" value="0"
                               class="w-full bg-ffxi-dark border border-ffxi-border rounded px-2 py-1 text-xs text-ffxi-text text-right focus:border-pink-400 focus:outline-none">
                    </div>
                    <div>
                        <label class="text-ffxi-text-dim text-xs block mb-1">
                            Cure Potency+
                            <span class="text-ffxi-text-dim ml-1 opacity-60" title="Cure Potency in basis points, e.g. 3000 = +30% (caps at 5000)">(?)</span>
                        </label>
                        <input id="magic-custom-cure-potency" type="number" min="0" max="5000" value="0"
                               class="w-full bg-ffxi-dark border border-ffxi-border rounded px-2 py-1 text-xs text-ffxi-text text-right focus:border-pink-400 focus:outline-none">
                    </div>
                </div>
            `;
            panel.appendChild(healingRow);
            
            // Wire up the new inputs now that they exist in the DOM
            setupMagicCustomBuffInputs();
        }
    }
}

async function handleMagicCategoryChange(e) {
    const categoryId = e.target.value;
    const spellSelect = document.getElementById('magic-spell-select');
    
    if (!categoryId) {
        spellSelect.disabled = true;
        spellSelect.innerHTML = '<option value="">Select spell category first...</option>';
        hideMagicSpellInfo();
        AppState.magic.selectedCategory = null;
        return;
    }
    
    try {
        const { spells } = await API.getSpellsByCategory(categoryId);
        AppState.spellsByCategory[categoryId] = spells;
        
        // Populate spell dropdown
        spellSelect.disabled = false;
        spellSelect.innerHTML = '<option value="">Select Spell...</option>';
        spells.forEach(spell => {
            const option = document.createElement('option');
            option.value = spell.name;
            option.textContent = `${spell.name} (${spell.element})`;
            spellSelect.appendChild(option);
        });
        
        AppState.magic.selectedCategory = categoryId;
    } catch (error) {
        console.error('Failed to load spells:', error);
        showToast('Failed to load spells', 'error');
    }
}

async function handleMagicSpellChange(e) {
    const spellName = e.target.value;
    
    if (!spellName) {
        hideMagicSpellInfo();
        AppState.magic.selectedSpell = null;
        AppState.magic.spellData = null;
        return;
    }
    
    try {
        const spellData = await API.getSpellDetails(spellName);
        AppState.magic.selectedSpell = spellName;
        AppState.magic.spellData = spellData;
        
        // Update spell info display
        showMagicSpellInfo(spellData);
        
        // Update optimization types based on spell
        updateMagicOptTypes(spellData);
        
        // Update MB toggle hint based on spell type
        updateMagicBurstHint(spellData);
        
        // Show/hide healing-specific buff inputs
        updateHealingBuffVisibility(spellData);
        
    } catch (error) {
        console.error('Failed to load spell details:', error);
        showToast('Failed to load spell details', 'error');
    }
}

function showMagicSpellInfo(spell) {
    const infoPanel = document.getElementById('magic-spell-info');
    if (!infoPanel) return;
    
    // Element styling based on element type
    const elementColors = {
        'FIRE': 'text-red-400',
        'ICE': 'text-blue-300',
        'WIND': 'text-green-300',
        'EARTH': 'text-yellow-600',
        'THUNDER': 'text-purple-400',
        'WATER': 'text-blue-400',
        'LIGHT': 'text-yellow-300',
        'DARK': 'text-gray-400',
    };
    
    document.getElementById('spell-element').textContent = spell.element;
    document.getElementById('spell-element').className = elementColors[spell.element] || 'text-ffxi-accent';
    document.getElementById('spell-type').textContent = spell.magic_type;
    document.getElementById('spell-mp').textContent = spell.mp_cost;
    document.getElementById('spell-cast').textContent = spell.cast_time;
    document.getElementById('spell-base-v').textContent = spell.base_v || '-';
    document.getElementById('spell-dint-cap').textContent = spell.dint_cap || '-';
    
    infoPanel.classList.remove('hidden');
}

function hideMagicSpellInfo() {
    const infoPanel = document.getElementById('magic-spell-info');
    if (infoPanel) infoPanel.classList.add('hidden');
}

function updateMagicOptTypes(spell) {
    const optSelect = document.getElementById('magic-opt-type');
    if (!optSelect) return;
    
    // Store current selection
    const currentValue = optSelect.value;
    
    // Update available types based on spell
    const validTypes = spell.valid_optimization_types || ['damage', 'accuracy', 'burst', 'potency'];
    
    // Enable/disable options based on validity
    Array.from(optSelect.options).forEach(opt => {
        opt.disabled = !validTypes.includes(opt.value);
    });
    
    // If current selection is no longer valid, switch to first valid type
    if (!validTypes.includes(currentValue)) {
        optSelect.value = validTypes[0] || 'damage';
        AppState.magic.optimizationType = optSelect.value;
    }
}

function updateMagicBurstHint(spell) {
    const hintEl = document.getElementById('magic-burst-hint');
    if (!hintEl) return;
    
    const magicType = spell.magic_type.toUpperCase();
    
    if (magicType.includes('ENFEEBLING')) {
        hintEl.textContent = 'Adds +100 M.Acc to help land debuffs';
    } else if (magicType.includes('ENHANCING') || magicType.includes('HEALING')) {
        hintEl.textContent = 'Magic burst not applicable for this spell type';
    } else {
        hintEl.textContent = 'Adds +100 M.Acc and MBB damage multipliers';
    }
}

function updateHealingBuffVisibility(spell) {
    const isHealing = spell?.magic_type?.toUpperCase().includes('HEALING');
    
    // Show/hide the healing-specific buff row (VIT + Cure Potency)
    const healingBuffRow = document.getElementById('magic-healing-buffs');
    if (healingBuffRow) {
        healingBuffRow.classList.toggle('hidden', !isHealing);
    }
    
    // When switching away from healing, clear the healing-specific fields so they
    // don't silently affect non-healing optimization runs
    if (!isHealing) {
        AppState.magic.customBuffs.VIT = 0;
        AppState.magic.customBuffs.cure_potency = 0;
        const vitInput = document.getElementById('magic-custom-vit');
        const cpInput  = document.getElementById('magic-custom-cure-potency');
        if (vitInput) vitInput.value = 0;
        if (cpInput)  cpInput.value  = 0;
    }
}

function handleMagicOptTypeChange(e) {
    AppState.magic.optimizationType = e.target.value;
    
    const descEl = document.getElementById('magic-opt-description');
    if (!descEl) return;
    
    const descriptions = {
        'damage': 'Maximize magic damage output (INT, MAB, Magic Damage)',
        'burst': 'Maximize magic burst damage (MBB, MBB II, MAB)',
        'accuracy': 'Maximize magic accuracy for landing spells (M.Acc, Skill)',
        'potency': 'Maximize spell effect potency (Cure Potency, HP/MP per tick, Skill, Effect+)',
    };
    
    descEl.textContent = descriptions[e.target.value] || '';
}

/**
 * Add a magic buff to the list (similar to physical tabs pattern)
 */
function addMagicBuffToList(category, buffName) {
    if (AppState.magic.buffs[category].includes(buffName)) {
        showToast(`${buffName} is already added`, 'warning');
        return;
    }
    
    AppState.magic.buffs[category].push(buffName);
    
    // Find the appropriate list element
    const listIdMap = {
        'brd': 'magic-brd-songs-list',
        'cor': 'magic-cor-rolls-list',
        'geo': 'magic-geo-bubbles-list',
        'sch': 'magic-sch-abilities-list',
        'whm': 'magic-whm-spells-list',
    };
    
    const list = document.getElementById(listIdMap[category]);
    if (!list) return;
    
    // Create buff item element
    const item = document.createElement('div');
    item.className = 'flex items-center justify-between bg-ffxi-dark rounded px-2 py-1 text-sm';
    item.dataset.category = category;
    item.dataset.buffName = buffName;
    
    // Get buff stats for display (if available)
    const stats = getMagicBuffStats(category, buffName);
    const statsText = formatMagicBuffStatsCompact(stats);
    
    const span = document.createElement('span');
    span.className = 'text-ffxi-text';
    span.textContent = buffName;
    if (statsText) {
        span.innerHTML = `${buffName} <span class="text-ffxi-text-dim text-xs">(${statsText})</span>`;
    }
    
    const btn = document.createElement('button');
    btn.className = 'text-ffxi-red hover:text-red-400 text-sm ml-2';
    btn.textContent = '×';
    btn.addEventListener('click', () => removeMagicBuffFromList(category, buffName));
    
    item.appendChild(span);
    item.appendChild(btn);
    list.appendChild(item);
    
    // Update counter if applicable
    updateMagicBuffCounter(category);
}

/**
 * Remove a magic buff from the list
 */
function removeMagicBuffFromList(category, buffName) {
    AppState.magic.buffs[category] = AppState.magic.buffs[category].filter(b => b !== buffName);
    
    // Find and remove from UI
    const listIdMap = {
        'brd': 'magic-brd-songs-list',
        'cor': 'magic-cor-rolls-list',
        'geo': 'magic-geo-bubbles-list',
        'sch': 'magic-sch-abilities-list',
        'whm': 'magic-whm-spells-list',
    };
    
    const list = document.getElementById(listIdMap[category]);
    if (list) {
        const items = list.querySelectorAll('div');
        items.forEach(item => {
            if (item.dataset.category === category && item.dataset.buffName === buffName) {
                item.remove();
            }
        });
    }
    
    // Update counter if applicable
    updateMagicBuffCounter(category);
}

/**
 * Update buff counter display for magic tab
 */
function updateMagicBuffCounter(category) {
    const maxCounts = {
        'brd': 4,
        'cor': 2,
        'geo': 3,
    };
    
    const counterIdMap = {
        'brd': 'magic-brd-song-count',
        'cor': 'magic-cor-roll-count',
        'geo': 'magic-geo-bubble-count',
    };
    
    if (!maxCounts[category]) return;
    
    const countEl = document.getElementById(counterIdMap[category]);
    if (countEl) {
        countEl.textContent = `${AppState.magic.buffs[category].length}/${maxCounts[category]}`;
    }
}

/**
 * Format magic buff stats for compact display
 */
function formatMagicBuffStatsCompact(stats) {
    if (!stats) return '';
    
    const parts = [];
    if (stats.INT) parts.push(`INT+${stats.INT}`);
    if (stats.MND) parts.push(`MND+${stats.MND}`);
    if (stats.magic_attack) parts.push(`MAB+${stats.magic_attack}`);
    if (stats.magic_attack_pct) parts.push(`MAB+${stats.magic_attack_pct}%`);
    if (stats.magic_accuracy) parts.push(`M.Acc+${stats.magic_accuracy}`);
    if (stats.magic_damage_mult) parts.push(`+${stats.magic_damage_mult}%dmg`);
    if (stats.refresh) parts.push(`Refresh+${stats.refresh}`);
    
    return parts.join(' ');
}

// Legacy function kept for compatibility - redirects to new function
function removeMagicBuff(category, buffName) {
    removeMagicBuffFromList(category, buffName);
}

function handleMagicDebuffAdd(e) {
    const debuffName = e.target.value;
    if (!debuffName) return;
    
    if (!AppState.magic.debuffs.includes(debuffName)) {
        AppState.magic.debuffs.push(debuffName);
        addMagicDebuffToUI(debuffName);
    } else {
        showToast(`${debuffName} is already added`, 'warning');
    }
    
    e.target.value = '';
}

function addMagicDebuffToUI(debuffName) {
    const list = document.getElementById('magic-debuffs-list');
    if (!list) return;
    
    const item = document.createElement('div');
    item.className = 'buff-item flex items-center justify-between bg-ffxi-dark rounded px-2 py-1';
    item.dataset.debuffName = debuffName;
    
    const span = document.createElement('span');
    span.className = 'text-xs';
    span.textContent = debuffName;
    
    const btn = document.createElement('button');
    btn.className = 'text-ffxi-red hover:text-red-400 text-sm ml-2';
    btn.textContent = '×';
    btn.addEventListener('click', () => removeMagicDebuff(debuffName));
    
    item.appendChild(span);
    item.appendChild(btn);
    list.appendChild(item);
}

function removeMagicDebuff(debuffName) {
    AppState.magic.debuffs = AppState.magic.debuffs.filter(d => d !== debuffName);
    
    // Remove from UI
    const list = document.getElementById('magic-debuffs-list');
    if (list) {
        const items = list.querySelectorAll('.buff-item');
        items.forEach(item => {
            if (item.dataset.debuffName === debuffName) {
                item.remove();
            }
        });
    }
}

async function runMagicOptimization() {
    if (!AppState.magic.selectedSpell) {
        showToast('Please select a spell first', 'warning');
        return;
    }
    
    if (!AppState.selectedJob) {
        showToast('Please select a job first', 'warning');
        return;
    }
    
    if (!AppState.inventoryLoaded) {
        showToast('Please upload inventory first', 'warning');
        return;
    }
    
    showToast(document.getElementById('magic-slow-mode')?.checked ? 'Running deep magic optimization (slow mode)...' : 'Running magic optimization...', 'info');
    showOptimizationProgress();
    
    // Build buffs object for API
    const buffs = {
        brd: AppState.magic.buffs.brd || [],
        geo: AppState.magic.buffs.geo || [],
        cor: AppState.magic.buffs.cor || [],
        sch: AppState.magic.buffs.sch || [],
        whm: AppState.magic.buffs.whm || [],
    };
    
    if (AppState.magic.buffs.food) {
        buffs.food = AppState.magic.buffs.food;
    }
    
    // Add custom magic buffs if set
    const customBuffs = getMagicCustomBuffsForPayload();
    if (customBuffs) {
        buffs.custom = customBuffs;
    }
    
    const magicSlowMode = document.getElementById('magic-slow-mode')?.checked ?? false;
    const magicSlowMaxIterations = parseInt(document.getElementById('magic-slow-max-iterations')?.value || 3);
    const magicSlowTopN = parseInt(document.getElementById('magic-slow-top-n')?.value || 3);

    // Build request payload
    const payload = {
        job: AppState.selectedJob,
        sub_job: AppState.selectedSubJob || 'rdm',
        spell_name: AppState.magic.selectedSpell,
        optimization_type: AppState.magic.optimizationType,
        magic_burst: AppState.magic.magicBurst,
        skillchain_steps: AppState.magic.skillchainSteps,
        target: AppState.magic.target,
        include_weapons: AppState.magic.includeWeapons,
        beam_width: AppState.magic.beamWidth,
        buffs: buffs,
        debuffs: AppState.magic.debuffs,
        master_level: AppState.masterLevel,
        slow_mode: magicSlowMode,
        slow_max_iterations: magicSlowMaxIterations,
        slow_top_n_per_slot: magicSlowTopN,
    };
    
    // If not including weapons in optimization, pass the selected weapons as fixed
    if (!AppState.magic.includeWeapons) {
        if (AppState.selectedMainWeapon?._raw) {
            payload.main_weapon = AppState.selectedMainWeapon._raw;
        }
        if (AppState.selectedSubWeapon?._raw) {
            payload.sub_weapon = AppState.selectedSubWeapon._raw;
        }
    }
    
    try {
        const result = await API.optimizeMagic(payload);
        
        if (result.success) {
            displayMagicResults(result);
            showToast('Magic optimization complete!', 'success');
        } else {
            showToast(`Optimization failed: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast(`Optimization failed: ${error.message}`, 'error');
    }
    
    hideOptimizationProgress();
}

function displayMagicResults(result) {
    // Store the full result for later reference
    AppState.currentMagicResult = result;
    AppState.currentResults = result.results;
    
    // Display in the main results panel (right side)
    const content = document.getElementById('results-content');
    if (!content || !result.results.length) {
        if (content) {
            content.innerHTML = '<div class="text-center text-ffxi-text-dim py-8">No results found</div>';
        }
        return;
    }
    
    let html = '<div class="space-y-4" id="magic-results-container">';
    
    for (const gearset of result.results) {
        // Determine what score means based on optimization type
        let scoreLabel = 'Score';
        let scoreValue = gearset.score?.toFixed(1) || '-';
        
        if (result.optimization_type === 'accuracy') {
            scoreLabel = 'Hit Rate';
            scoreValue = `${(gearset.hit_rate * 100)?.toFixed(1) || gearset.score?.toFixed(1)}%`;
        } else if (result.optimization_type === 'damage' || result.optimization_type === 'burst') {
            scoreLabel = 'Avg Damage';
            scoreValue = gearset.damage?.toFixed(0) || gearset.score?.toFixed(0) || '-';
        } else if (result.optimization_type === 'potency') {
            // Use human-readable description when available (e.g. "1,247 HP healed", "12 HP/tick")
            if (gearset.potency_description) {
                scoreLabel = 'Potency';
                scoreValue = gearset.potency_description;
            } else {
                scoreLabel = 'Potency Score';
                scoreValue = gearset.potency_score?.toFixed(1) || gearset.score?.toFixed(1) || '-';
            }
        }
        
        // Build quick stats summary
        const stats = gearset.stats || {};
        
        // First result gets selected styling by default
        const isFirst = gearset.rank === 1;
        const selectedClass = isFirst ? 'ring-2 ring-ffxi-accent border-ffxi-accent' : '';
        
        html += `
            <div class="magic-result-card result-card bg-ffxi-dark rounded-lg p-4 border border-ffxi-border hover:border-ffxi-accent transition-colors cursor-pointer ${selectedClass}"
                 data-result-index="${gearset.rank - 1}"
                 onclick="showMagicResultDetails(${gearset.rank - 1})">
                <div class="flex items-center justify-between mb-3">
                    <span class="text-ffxi-accent font-display text-lg">#${gearset.rank}</span>
                    <span class="text-ffxi-green font-bold">${scoreValue} ${scoreLabel === 'Avg Damage' ? 'dmg' : ''}</span>
                </div>
                <div class="text-xs text-ffxi-text-dim mb-2">
                    ${result.spell_name} ${result.magic_burst ? '(MB)' : ''}
                </div>
                <div class="grid grid-cols-4 gap-1 text-xs mb-2">
                    <div><span class="text-ffxi-text-dim">INT:</span> ${stats.INT || '-'}</div>
                    <div><span class="text-ffxi-text-dim">MAB:</span> ${stats.magic_attack || '-'}</div>
                    <div><span class="text-ffxi-text-dim">M.Dmg:</span> ${stats.magic_damage || '-'}</div>
                    <div><span class="text-ffxi-text-dim">MBB:</span> ${stats.magic_burst_bonus || '-'}</div>
                </div>
                <div class="text-xs text-ffxi-text-dim">
                    ${formatGearSummary(gearset.gear)}
                </div>
            </div>
        `;
    }
    
    html += '</div>';
    content.innerHTML = html;
    
    // Show Lua section and generate for first result
    document.getElementById('lua-section')?.classList.remove('hidden');
    generateMagicLuaOutput(result.results[0], result);
    
    // Show magic stats for first result
    displayMagicStats(result.results[0], result);
    
    // Also show in the inline magic results section (in the center panel)
    const resultsContainer = document.getElementById('magic-results');
    const resultsList = document.getElementById('magic-results-list');
    
    if (resultsContainer && resultsList) {
        resultsList.innerHTML = '<p class="text-ffxi-text-dim text-sm">Results shown in right panel. Click a result to view details and GearSwap Lua.</p>';
        resultsContainer.classList.remove('hidden');
    }
}

function showMagicResultDetails(index) {
    if (!AppState.currentResults || !AppState.currentResults[index]) return;
    
    const result = AppState.currentResults[index];
    const fullResult = AppState.currentMagicResult;
    
    // Update visual selection on result cards
    const allCards = document.querySelectorAll('.magic-result-card');
    allCards.forEach(card => {
        const cardIndex = parseInt(card.dataset.resultIndex);
        if (cardIndex === index) {
            card.classList.add('ring-2', 'ring-ffxi-accent', 'border-ffxi-accent');
        } else {
            card.classList.remove('ring-2', 'ring-ffxi-accent', 'border-ffxi-accent');
        }
    });
    
    // Generate LUA and display stats for this result
    generateMagicLuaOutput(result, fullResult);
    displayMagicStats(result, fullResult);
    
    // Ensure Lua section is visible
    const luaSection = document.getElementById('lua-section');
    if (luaSection) {
        luaSection.classList.remove('hidden');
        // Scroll to Lua section so user can see the output
        luaSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

function generateMagicLuaOutput(gearset, fullResult) {
    if (!gearset || !gearset.gear) return;
    
    const luaOutput = document.getElementById('lua-output');
    if (!luaOutput) return;
    
    // Generate appropriate set name based on spell
    const spellName = fullResult?.spell_name || 'Magic';
    const isBurst = fullResult?.magic_burst;
    
    // Format spell name for Lua (replace spaces with underscores, handle Roman numerals)
    const luaSpellName = spellName.replace(/\s+/g, '_');
    
    let setName;
    if (isBurst) {
        setName = `sets.midcast['${spellName}'].MB`;
    } else {
        setName = `sets.midcast['${spellName}']`;
    }
    
    let lua = `${setName} = {\n`;
    
    const slotOrder = ['main', 'sub', 'ranged', 'ammo', 'head', 'neck', 'ear1', 'ear2', 
                       'body', 'hands', 'ring1', 'ring2', 'back', 'waist', 'legs', 'feet'];

    // Fix empyrean earring slot order: shallow copy so we don't mutate gearset.gear
    const gear = { ...gearset.gear };
    const ear1Name = gear['ear1']?.name || '';
    if (isEmpyreanEarring(ear1Name)) {
        const tmp = gear['ear1'];
        gear['ear1'] = gear['ear2'] || null;
        gear['ear2'] = tmp;
    }
    
    for (const slot of slotOrder) {
        if (gear[slot] && gear[slot].name !== 'Empty') {
            const luaSlot = slot === 'ear1' ? 'left_ear' : 
                           slot === 'ear2' ? 'right_ear' :
                           slot === 'ring1' ? 'left_ring' :
                           slot === 'ring2' ? 'right_ring' : slot;
            const itemStr = formatLuaItem(gear[slot]);
            lua += `    ${luaSlot}=${itemStr},\n`;
        }
    }
    
    lua += '}';
    
    luaOutput.textContent = lua;
}

function displayMagicStats(gearset, fullResult) {
    if (!gearset || !gearset.stats) return;
    
    const stats = gearset.stats;
    const statsContent = document.getElementById('stats-content');
    
    if (!statsContent) {
        console.warn('stats-content element not found');
        return;
    }
    
    // Build magic-specific stats panel
    const mlText = AppState.masterLevel > 0 ? ` ML${AppState.masterLevel}` : '';
    const spellName = fullResult?.spell_name || 'Magic';
    const isBurst = fullResult?.magic_burst;
    
    // Detect healing spell from stored spell data
    const isHealing = AppState.magic.spellData?.magic_type?.toUpperCase().includes('HEALING');
    
    // Cure Potency: stored as basis points (e.g. 3000 = 30%)
    const curePotencyPct = stats.cure_potency ? (stats.cure_potency / 100).toFixed(1) : '0.0';
    
    statsContent.innerHTML = `
        <div class="text-xs space-y-3">
            <!-- Header -->
            <div class="flex justify-between items-center">
                <span class="text-ffxi-accent font-medium">${AppState.selectedJob || 'BLM'}${mlText}/${AppState.selectedSubJob || 'RDM'}</span>
                <span class="text-ffxi-purple text-xs">✨ Magic</span>
            </div>
            
            <!-- Primary Stats (INT/MND focused) -->
            <div class="border-t border-ffxi-border pt-2">
                <div class="text-ffxi-text-dim mb-1 font-medium">Primary Stats</div>
                <div class="grid grid-cols-4 gap-1">
                    <div class="flex justify-between bg-ffxi-purple/10 px-1 rounded"><span class="text-ffxi-text-dim">INT</span><span class="text-ffxi-purple font-medium">${stats.INT || 0}</span></div>
                    <div class="flex justify-between ${isHealing ? 'bg-pink-500/10' : 'bg-ffxi-purple/10'} px-1 rounded"><span class="text-ffxi-text-dim">MND</span><span class="${isHealing ? 'text-pink-400' : 'text-ffxi-purple'} font-medium">${stats.MND || 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">STR</span><span class="text-ffxi-text">${stats.STR || 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">DEX</span><span class="text-ffxi-text">${stats.DEX || 0}</span></div>
                    <div class="flex justify-between ${isHealing ? 'bg-pink-500/10' : ''} px-1 rounded"><span class="text-ffxi-text-dim">VIT</span><span class="${isHealing ? 'text-pink-400 font-medium' : 'text-ffxi-text'}">${stats.VIT || 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">AGI</span><span class="text-ffxi-text">${stats.AGI || 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">CHR</span><span class="text-ffxi-text">${stats.CHR || 0}</span></div>
                </div>
            </div>
            
            ${isHealing ? `
            <!-- Healing Stats (shown instead of Magic Burst for healing spells) -->
            <div class="border-t border-ffxi-border pt-2">
                <div class="text-ffxi-text-dim mb-1 font-medium">Healing</div>
                <div class="grid grid-cols-2 gap-1">
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">Healing Skill</span><span class="text-pink-400 font-medium">${stats.healing_magic_skill || 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">Cure Potency</span><span class="text-pink-400 font-medium">+${curePotencyPct}%</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">Fast Cast</span><span class="text-ffxi-text">${stats.fast_cast || 0}%</span></div>
                </div>
            </div>
            ` : `
            <!-- Magic Offense (not shown for healing) -->
            <div class="border-t border-ffxi-border pt-2">
                <div class="text-ffxi-text-dim mb-1 font-medium">Magic Offense</div>
                <div class="grid grid-cols-2 gap-1">
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">M.Atk Bonus</span><span class="text-ffxi-text">${stats.magic_attack || 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">M.Damage</span><span class="text-ffxi-text">${stats.magic_damage || 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">M.Accuracy</span><span class="text-ffxi-text">${stats.magic_accuracy || 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">Fast Cast</span><span class="text-ffxi-text">${stats.fast_cast || 0}%</span></div>
                </div>
            </div>
            
            <!-- Magic Burst -->
            <div class="border-t border-ffxi-border pt-2">
                <div class="text-ffxi-text-dim mb-1 font-medium">Magic Burst</div>
                <div class="grid grid-cols-2 gap-1">
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">MBB (cap 40%)</span><span class="text-ffxi-text">${stats.magic_burst_bonus || 0}%</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">MBB II</span><span class="text-ffxi-text">${stats.magic_burst_damage_ii || 0}%</span></div>
                </div>
            </div>
            `}
            
            <!-- Magic Skills -->
            <div class="border-t border-ffxi-border pt-2">
                <div class="text-ffxi-text-dim mb-1 font-medium">Magic Skills</div>
                <div class="grid grid-cols-2 gap-1">
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">Elemental</span><span class="text-ffxi-text">${stats.elemental_magic_skill || 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">Dark</span><span class="text-ffxi-text">${stats.dark_magic_skill || 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">Enfeebling</span><span class="text-ffxi-text">${stats.enfeebling_magic_skill || 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">Enhancing</span><span class="text-ffxi-text">${stats.enhancing_magic_skill || 0}</span></div>
                    <div class="flex justify-between ${isHealing ? 'bg-pink-500/10 rounded px-1' : ''}"><span class="text-ffxi-text-dim">Healing</span><span class="${isHealing ? 'text-pink-400 font-medium' : 'text-ffxi-text'}">${stats.healing_magic_skill || 0}</span></div>
                    <div class="flex justify-between"><span class="text-ffxi-text-dim">Divine</span><span class="text-ffxi-text">${stats.divine_magic_skill || 0}</span></div>
                </div>
            </div>
            
            <!-- Spell Info -->
            <div class="border-t border-ffxi-border pt-2">
                <div class="text-ffxi-text-dim mb-1 font-medium">✨ ${spellName}</div>
                <div class="space-y-1">
                    ${isHealing ? `
                    <div class="text-center py-1 rounded text-xs font-medium bg-pink-500/20 text-pink-400">
                        💚 Healing Set
                    </div>
                    ${gearset.potency_description ? `
                    <div class="flex justify-between mt-2">
                        <span class="text-ffxi-text-dim">HP Healed</span>
                        <span class="text-pink-400 font-bold">${gearset.potency_description}</span>
                    </div>
                    ` : ''}
                    ` : `
                    ${isBurst ? `
                    <div class="text-center py-1 rounded text-xs font-medium bg-ffxi-purple/20 text-ffxi-purple">
                        ✨ Magic Burst Set
                    </div>
                    ` : `
                    <div class="text-center py-1 rounded text-xs font-medium bg-ffxi-blue/20 text-ffxi-blue">
                        Free Nuke Set
                    </div>
                    `}
                    ${gearset.damage ? `
                    <div class="flex justify-between mt-2">
                        <span class="text-ffxi-text-dim">Expected Damage</span>
                        <span class="text-ffxi-accent font-bold">${Math.round(gearset.damage).toLocaleString()}</span>
                    </div>
                    ` : ''}
                    ${gearset.hit_rate !== undefined ? `
                    <div class="flex justify-between">
                        <span class="text-ffxi-text-dim">Unresisted Rate</span>
                        <span class="text-ffxi-text">${(gearset.hit_rate * 100).toFixed(1)}%</span>
                    </div>
                    ` : ''}
                    `}
                </div>
            </div>
        </div>
    `;
    
    console.log('displayMagicStats completed successfully');
}


// =============================================================================
// INVENTORY BROWSER
// =============================================================================

const InventoryBrowser = {
    items: [],
    filteredItems: [],
    currentPage: 1,
    itemsPerPage: 50,
    compareSlotA: null,
    compareSlotB: null,
    currentModalItem: null,
    selectedStatFilters: [],  // Array of stat names to filter by (AND logic)
    selectedEffectFilters: [], // Array of effect types to filter by (OR logic)
    availableEffectTypes: [],  // Effect types found in inventory
    sortMode: 'alpha',         // 'alpha' or 'value'
    
    async init() {
        this.setupEventListeners();
        this.populateJobFilter();
        await this.loadEffectTypes();
    },
    
    setupEventListeners() {
        // Search - local filter for inventory, server reload for show_all
        const searchInput = document.getElementById('inventory-search');
        if (searchInput) {
            searchInput.addEventListener('input', debounce(() => {
                const showAll = document.getElementById('inventory-show-all')?.checked;
                if (showAll) {
                    // Server-side search for large dataset
                    this.loadItems();
                } else {
                    // Local filter for inventory items
                    this.filterAndDisplay();
                }
            }, 500));
        }
        
        // Slot filter
        const slotFilter = document.getElementById('inventory-slot-filter');
        if (slotFilter) {
            slotFilter.addEventListener('change', () => {
                const showAll = document.getElementById('inventory-show-all')?.checked;
                if (showAll) {
                    // Reload from server for large dataset
                    this.loadItems();
                } else {
                    // Client-side filter for inventory items
                    this.filterAndDisplay();
                }
            });
        }
        
        // Job filter
        const jobFilter = document.getElementById('inventory-job-filter');
        if (jobFilter) {
            jobFilter.addEventListener('change', () => this.filterAndDisplay());
        }
        
        // Stat filter - adds to list of selected stats
        const statFilter = document.getElementById('inventory-stat-filter');
        if (statFilter) {
            statFilter.addEventListener('change', () => {
                const selectedStat = statFilter.value;
                if (selectedStat && !this.selectedStatFilters.includes(selectedStat)) {
                    this.selectedStatFilters.push(selectedStat);
                    this.renderStatTags();
                    this.filterAndDisplay();
                }
                // Reset dropdown to placeholder
                statFilter.value = '';
            });
        }
        
        // Effect filter - adds to list of selected effects (Pet, Latent Effect, etc.)
        const effectFilter = document.getElementById('inventory-effect-filter');
        if (effectFilter) {
            effectFilter.addEventListener('change', () => {
                const selectedEffect = effectFilter.value;
                if (selectedEffect && !this.selectedEffectFilters.includes(selectedEffect)) {
                    this.selectedEffectFilters.push(selectedEffect);
                    this.renderEffectTags();
                    this.filterAndDisplay();
                }
                // Reset dropdown to placeholder
                effectFilter.value = '';
            });
        }
        
        // Show all checkbox
        const showAllCheckbox = document.getElementById('inventory-show-all');
        if (showAllCheckbox) {
            showAllCheckbox.addEventListener('change', () => this.loadItems());
        }
        
        // Pagination
        document.getElementById('btn-prev-page')?.addEventListener('click', () => this.prevPage());
        document.getElementById('btn-next-page')?.addEventListener('click', () => this.nextPage());
        
        // Clear compare
        document.getElementById('btn-clear-compare')?.addEventListener('click', () => this.clearCompare());
        
        // Modal buttons
        document.getElementById('btn-close-item-modal')?.addEventListener('click', () => this.closeModal());
        document.getElementById('btn-add-compare-a')?.addEventListener('click', () => this.addToCompare('a'));
        document.getElementById('btn-add-compare-b')?.addEventListener('click', () => this.addToCompare('b'));
        
        // Sort mode toggle
        document.getElementById('btn-inventory-sort-toggle')?.addEventListener('change', (e) => {
            this.sortMode = e.target.value;
            this.filterAndDisplay();
        });

        // Close modal on backdrop click
        const modal = document.getElementById('item-modal');
        if (modal) {
            modal.querySelector('.modal-backdrop')?.addEventListener('click', () => this.closeModal());
        }
    },
    
    populateJobFilter() {
        const jobFilter = document.getElementById('inventory-job-filter');
        if (!jobFilter) return;
        
        const jobs = ['WAR', 'MNK', 'WHM', 'BLM', 'RDM', 'THF', 'PLD', 'DRK', 
                      'BST', 'BRD', 'RNG', 'SAM', 'NIN', 'DRG', 'SMN', 'BLU', 
                      'COR', 'PUP', 'DNC', 'SCH', 'GEO', 'RUN'];
        
        jobs.forEach(job => {
            const option = document.createElement('option');
            option.value = job;
            option.textContent = job;
            jobFilter.appendChild(option);
        });
    },
    
    async loadItems() {
        const showAll = document.getElementById('inventory-show-all')?.checked;
        const job = document.getElementById('inventory-job-filter')?.value || '';
        const search = document.getElementById('inventory-search')?.value || '';
        const slotFilter = document.getElementById('inventory-slot-filter')?.value || '';
        
        // Show loading indicator
        const grid = document.getElementById('inventory-grid');
        if (grid) {
            grid.innerHTML = '<p class="text-ffxi-text-dim col-span-full text-center py-8">Loading items...</p>';
        }
        
        try {
            let url = '/api/inventory';
            const params = new URLSearchParams();
            if (job) params.append('job', job);
            if (showAll) params.append('show_all', 'true');
            if (search && showAll) params.append('search', search); // Server-side search for large dataset
            if (slotFilter && showAll) params.append('slot', slotFilter); // Server-side slot filter for large dataset
            if (params.toString()) url += '?' + params.toString();
            
            const response = await API.fetch(url);
            
            if (response.error) {
                showToast(response.error, 'error');
                this.items = [];
            } else {
                this.items = response.items || [];
            }
            
            // Extract and populate stat filter options
            this.populateStatFilter();
            
            // Refresh effect types from inventory
            await this.loadEffectTypes();
            
            this.currentPage = 1;
            this.filterAndDisplay();
        } catch (error) {
            console.error('Failed to load inventory:', error);
            showToast('Failed to load items', 'error');
            this.items = [];
            this.filterAndDisplay();
        }
    },
    
    // Extract unique stat names from loaded items and populate dropdown
    populateStatFilter() {
        const statFilter = document.getElementById('inventory-stat-filter');
        if (!statFilter) return;
        
        // Collect all unique stat names
        const statNames = new Set();
        this.items.forEach(item => {
            if (item.stats) {
                Object.keys(item.stats).forEach(statName => {
                    // Skip internal fields
                    if (!statName.startsWith('_')) {
                        statNames.add(statName);
                    }
                });
            }
        });
        
        // Sort alphabetically
        const sortedStats = [...statNames].sort((a, b) => a.localeCompare(b));
        
        // Clear and repopulate
        statFilter.innerHTML = '<option value="">+ Add Stat Filter</option>';
        sortedStats.forEach(stat => {
            const option = document.createElement('option');
            option.value = stat;
            option.textContent = SetBuilder.normalizePathStatKey(stat);
            statFilter.appendChild(option);
        });
        
        // Re-render existing tags
        this.renderStatTags();
    },
    
    // Render selected stat filters as removable tags
    renderStatTags() {
        const container = document.getElementById('inventory-stat-tags');
        const wrapper = document.getElementById('inventory-stat-tags-container');
        if (!container) return;
        
        if (this.selectedStatFilters.length === 0) {
            container.innerHTML = '';
            if (wrapper) wrapper.classList.add('hidden');
            return;
        }
        
        if (wrapper) wrapper.classList.remove('hidden');
        
        container.innerHTML = this.selectedStatFilters.map(stat => {
            const displayName = SetBuilder.normalizePathStatKey(stat);
            return `
            <span class="inline-flex items-center gap-1 px-2 py-1 rounded bg-ffxi-accent/20 text-ffxi-accent text-sm">
                ${displayName}
                <button onclick="InventoryBrowser.removeStatFilter('${stat.replace(/'/g, "\\'")}')" 
                        class="hover:text-ffxi-red ml-1" title="Remove filter">
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </span>
        `}).join('');
    },
    
    // Remove a stat from the filter list
    removeStatFilter(stat) {
        this.selectedStatFilters = this.selectedStatFilters.filter(s => s !== stat);
        this.renderStatTags();
        this.filterAndDisplay();
    },
    
    // Clear all stat filters
    clearStatFilters() {
        this.selectedStatFilters = [];
        this.renderStatTags();
        this.filterAndDisplay();
    },
    
    // Load available effect types from API
    async loadEffectTypes() {
        try {
            const response = await API.fetch('/api/inventory/effect-types');
            if (response.effect_types) {
                this.availableEffectTypes = response.effect_types;
                this.populateEffectFilter();
            }
        } catch (error) {
            console.error('Failed to load effect types:', error);
        }
    },
    
    // Populate effect filter dropdown
    populateEffectFilter() {
        const effectFilter = document.getElementById('inventory-effect-filter');
        if (!effectFilter) return;
        
        // Clear and repopulate
        effectFilter.innerHTML = '<option value="">+ Add Effect Filter</option>';
        this.availableEffectTypes.forEach(effect => {
            const option = document.createElement('option');
            option.value = effect;
            option.textContent = effect;
            effectFilter.appendChild(option);
        });
    },
    
    // Render selected effect filters as removable tags
    renderEffectTags() {
        const container = document.getElementById('inventory-effect-tags');
        const wrapper = document.getElementById('inventory-effect-tags-container');
        if (!container) return;
        
        if (this.selectedEffectFilters.length === 0) {
            container.innerHTML = '';
            if (wrapper) wrapper.classList.add('hidden');
            return;
        }
        
        if (wrapper) wrapper.classList.remove('hidden');
        
        container.innerHTML = this.selectedEffectFilters.map(effect => `
            <span class="inline-flex items-center gap-1 px-2 py-1 rounded bg-purple-500/20 text-purple-400 text-sm">
                ${effect}
                <button onclick="InventoryBrowser.removeEffectFilter('${effect.replace(/'/g, "\\'")}')" 
                        class="hover:text-ffxi-red ml-1" title="Remove filter">
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </span>
        `).join('');
    },
    
    // Remove an effect from the filter list
    removeEffectFilter(effect) {
        this.selectedEffectFilters = this.selectedEffectFilters.filter(e => e !== effect);
        this.renderEffectTags();
        this.filterAndDisplay();
    },
    
    // Clear all effect filters
    clearEffectFilters() {
        this.selectedEffectFilters = [];
        this.renderEffectTags();
        this.filterAndDisplay();
    },

    // Toggle between alphabetical and value-based sorting
    toggleSortMode() {
        this.sortMode = this.sortMode === 'alpha' ? 'value' : 'alpha';
        this.filterAndDisplay();
    },
    
    filterAndDisplay() {
        const search = document.getElementById('inventory-search')?.value?.toLowerCase().trim() || '';
        const slotFilter = document.getElementById('inventory-slot-filter')?.value || '';
        const jobFilter = document.getElementById('inventory-job-filter')?.value?.toLowerCase() || '';
        
        this.filteredItems = this.items.filter(item => {
            // Name search - substring match on name/name2/name_log (full unabbreviated name)
            if (search) {
                const nameLower = item.name.toLowerCase();
                const name2Lower = item.name2?.toLowerCase() || '';
                const nameLogLower = item.name_log?.toLowerCase() || '';
                if (!nameLower.includes(search) && !name2Lower.includes(search) && !nameLogLower.includes(search)) {
                    return false;
                }
            }
            
            // Stat filters - item must have ALL selected stats (AND logic)
            if (this.selectedStatFilters.length > 0) {
                if (!item.stats) return false;
                
                // Check that item has every selected stat
                for (const stat of this.selectedStatFilters) {
                    if (!(stat in item.stats)) {
                        return false;
                    }
                }
            }
            
            // Effect filters - item must have AT LEAST ONE selected effect (OR logic)
            if (this.selectedEffectFilters.length > 0) {
                const itemEffects = item.effects || [];
                const hasMatchingEffect = this.selectedEffectFilters.some(effect => 
                    itemEffects.includes(effect)
                );
                if (!hasMatchingEffect) return false;
            }
            
            // Slot filter
            if (slotFilter) {
                const itemSlot = (item.slot || '').toLowerCase();
                const filterLower = slotFilter.toLowerCase();
                
                // Handle special cases
                if (filterLower === 'ear') {
                    if (itemSlot !== 'ear') return false;
                } else if (filterLower === 'ring') {
                    if (itemSlot !== 'ring') return false;
                } else if (filterLower === 'ranged' || filterLower === 'range') {
                    if (itemSlot !== 'range' && itemSlot !== 'ranged') return false;
                } else {
                    if (itemSlot !== filterLower) return false;
                }
            }
            
            // Job filter
            if (jobFilter && item.jobs) {
                const canEquip = item.jobs.some(j => j.toLowerCase() === jobFilter);
                if (!canEquip) return false;
            }
            
            return true;
        });
        
        // Sort filtered results based on current sort mode
        if (this.sortMode === 'value' && this.selectedStatFilters.length > 0) {
            // Sort descending by sum of selected stat values
            this.filteredItems.sort((a, b) => {
                const aVal = this.selectedStatFilters.reduce((sum, stat) => {
                    const v = a.stats?.[stat];
                    return sum + (typeof v === 'number' ? v : 0);
                }, 0);
                const bVal = this.selectedStatFilters.reduce((sum, stat) => {
                    const v = b.stats?.[stat];
                    return sum + (typeof v === 'number' ? v : 0);
                }, 0);
                return bVal - aVal;
            });
        } else {
            // Default alphabetical sort
            this.filteredItems.sort((a, b) => {
                const nameA = (a.name2 || a.name).toLowerCase();
                const nameB = (b.name2 || b.name).toLowerCase();
                return nameA.localeCompare(nameB);
            });
        }
        
        this.displayItems();
    },
    
    displayItems() {
        const grid = document.getElementById('inventory-grid');
        if (!grid) return;
        
        const totalPages = Math.ceil(this.filteredItems.length / this.itemsPerPage);
        const start = (this.currentPage - 1) * this.itemsPerPage;
        const end = start + this.itemsPerPage;
        const pageItems = this.filteredItems.slice(start, end);
        
        // Update count
        const countEl = document.getElementById('inventory-count');
        if (countEl) {
            countEl.textContent = `${this.filteredItems.length} items`;
        }
        
        // Update pagination
        const pagination = document.getElementById('inventory-pagination');
        const pageInfo = document.getElementById('page-info');
        if (pagination && pageInfo) {
            if (totalPages > 1) {
                pagination.classList.remove('hidden');
                pageInfo.textContent = `Page ${this.currentPage} of ${totalPages}`;
                document.getElementById('btn-prev-page').disabled = this.currentPage === 1;
                document.getElementById('btn-next-page').disabled = this.currentPage === totalPages;
            } else {
                pagination.classList.add('hidden');
            }
        }
        
        if (pageItems.length === 0) {
            grid.innerHTML = `<p class="text-ffxi-text-dim col-span-full text-center py-8">
                No items found. Try adjusting filters or upload an inventory.
            </p>`;
            return;
        }
        
        // Pass the actual index in filteredItems (not just page-relative index)
        grid.innerHTML = pageItems.map((item, pageIndex) => {
            const filteredIndex = start + pageIndex;
            return this.renderItemCard(item, filteredIndex);
        }).join('');
    },
    
    renderItemCard(item, filteredIndex) {
        const iconUrl = `/static/icons/${item.id}.png`;
        const displayName = item.name2 || item.name;
        const ilvl = item.item_level || item.stats?.['Item Level'] || 0;
        
        // Get key stats for preview
        const stats = item.stats || {};
        const statPreview = [];
        
        // For weapons, show DMG and Delay first
        if (stats['DMG']) statPreview.push(`DMG:${stats['DMG']}`);
        if (stats['Delay']) statPreview.push(`Dly:${stats['Delay']}`);
        
        // Weapon skills (important for accuracy)
        const weaponSkills = ['Sword Skill', 'Great Sword Skill', 'Axe Skill', 'Great Axe Skill',
            'Polearm Skill', 'Scythe Skill', 'Katana Skill', 'Great Katana Skill',
            'Club Skill', 'Staff Skill', 'Dagger Skill', 'Hand-to-Hand Skill',
            'Marksmanship Skill', 'Archery Skill'];
        weaponSkills.forEach(skill => {
            if (stats[skill]) {
                const shortName = skill.replace(' Skill', '').replace('Great ', 'G.');
                statPreview.push(`${shortName}+${stats[skill]}`);
            }
        });
        
        // Primary stats
        ['STR', 'DEX', 'VIT', 'AGI', 'INT', 'MND', 'CHR'].forEach(stat => {
            if (stats[stat]) statPreview.push(`${stat}+${stats[stat]}`);
        });
        
        // Combat stats
        if (stats['Attack']) statPreview.push(`Atk+${stats['Attack']}`);
        if (stats['Accuracy']) statPreview.push(`Acc+${stats['Accuracy']}`);
        if (stats['Magic Attack']) statPreview.push(`MAB+${stats['Magic Attack']}`);
        if (stats['Magic Accuracy']) statPreview.push(`M.Acc+${stats['Magic Accuracy']}`);
        
        const previewText = statPreview.slice(0, 5).join(' ') || 'No stats';
        
        // Use filteredIndex to ensure we show the exact item clicked
        return `
            <div class="item-card bg-ffxi-dark rounded p-3 border border-ffxi-border hover:border-ffxi-accent transition-colors cursor-pointer"
                 onclick="InventoryBrowser.showItemModal(${filteredIndex})">
                <div class="flex items-start gap-3">
                    <div class="w-10 h-10 bg-ffxi-darker rounded flex items-center justify-center flex-shrink-0">
                        <img src="${iconUrl}" alt="" class="w-8 h-8 object-contain" 
                             onerror="this.parentElement.innerHTML='<span class=\\'text-ffxi-text-dim text-xs\\'>?</span>'">
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="text-sm text-ffxi-text truncate font-medium">${displayName}</div>
                        <div class="text-xs text-ffxi-text-dim">iLvl ${ilvl} • ${item.type || 'Unknown'}</div>
                        <div class="text-xs text-ffxi-text-dim mt-1 truncate">${previewText}</div>
                    </div>
                </div>
            </div>
        `;
    },
    
    showItemModal(filteredIndex) {
        // Use the index into filteredItems to get the exact item clicked
        const item = this.filteredItems[filteredIndex];
        if (!item) return;
        
        this.currentModalItem = item;
        
        const modal = document.getElementById('item-modal');
        const iconImg = modal.querySelector('#item-modal-icon img');
        
        // Set basic info
        document.getElementById('item-modal-name').textContent = item.name2 || item.name;
        document.getElementById('item-modal-type').textContent = item.type || 'Unknown';
        document.getElementById('item-modal-ilvl').textContent = `iLvl ${item.item_level || 0}`;
        
        // Set icon
        iconImg.src = `/static/icons/${item.id}.png`;
        iconImg.style.display = 'block';
        
        // Set jobs
        const jobsList = item.jobs?.map(j => j.toUpperCase()).join(' ') || 'All Jobs';
        document.getElementById('item-modal-jobs-list').textContent = jobsList;
        
        // Display ALL stats from the item
        const stats = item.stats || {};
        this.displayAllStats(stats);
        
        modal.classList.remove('hidden');
    },
    
    displayAllStats(stats) {
        // Get all stat keys and sort them into logical groups
        const allKeys = Object.keys(stats).filter(k => 
            stats[k] !== undefined && stats[k] !== 0 && stats[k] !== '' && stats[k] !== null
        );
        
        // Define groupings for organization (stats not in these go to "Other")
        const primaryStats = ['HP', 'MP', 'STR', 'DEX', 'VIT', 'AGI', 'INT', 'MND', 'CHR'];
        const combatStats = ['DMG', 'Delay', 'Attack', 'Accuracy', 'Ranged Attack', 'Ranged Accuracy',
            'DA', 'TA', 'QA', 'Crit Rate', 'Crit Damage', 'Store TP', 'Weapon Skill Damage', 'PDL',
            'Skillchain Bonus', 'TP Bonus'];
        const magicStats = ['Magic Attack', 'Magic Accuracy', 'Magic Damage', 'Magic Burst Bonus', 
            'Magic Burst Bonus II', 'Fast Cast', 'Quick Magic'];
        
        // Categorize stats
        const primary = [], combat = [], magic = [], other = [];
        const used = new Set();
        
        // Primary stats
        primaryStats.forEach(key => {
            if (allKeys.includes(key)) {
                primary.push(key);
                used.add(key);
            }
        });
        
        // Combat stats (including any skill stats)
        allKeys.forEach(key => {
            if (used.has(key)) return;
            if (combatStats.includes(key) || key.endsWith(' Skill')) {
                combat.push(key);
                used.add(key);
            }
        });
        
        // Magic stats (including magic skills)
        allKeys.forEach(key => {
            if (used.has(key)) return;
            if (magicStats.includes(key) || key.includes('Magic') || key.includes('Ninjutsu') || 
                key.includes('Singing') || key.includes('Instrument') || key.includes('Geomancy') ||
                key.includes('Handbell') || key.includes('Summoning') || key.includes('Blue Magic') ||
                key === 'cure_potency' || key === 'cure_potency_ii' ||
                key === 'regen_potency' || key === 'regen_effect_duration' ||
                key === 'refresh_potency' || key === 'refresh_effect_duration' ||
                key === 'drain_aspir_potency' || key === 'enfeebling_effect' ||
                key === 'refresh' || key === 'regen') {
                magic.push(key);
                used.add(key);
            }
        });
        
        // Everything else goes to Other
        allKeys.forEach(key => {
            if (!used.has(key)) {
                other.push(key);
            }
        });
        
        // Render each category
        this.renderStatList('item-modal-primary-stats', stats, primary);
        this.renderStatList('item-modal-combat-stats', stats, combat);
        this.renderStatList('item-modal-magic-stats', stats, magic);
        this.renderStatList('item-modal-other-stats', stats, other);
    },
    
    renderStatList(elementId, stats, keys) {
        const container = document.getElementById(elementId);
        if (!container) return;
        
        if (keys.length === 0) {
            container.innerHTML = '<div class="text-ffxi-text-dim text-xs">None</div>';
            return;
        }
        
        const html = keys.map(key => {
            const value = stats[key];
            const displayKey = SetBuilder.normalizePathStatKey(key);
            const displayValue = SetBuilder.formatStatValue(key, value);
            return `<div class="flex justify-between">
                <span class="text-ffxi-text-dim">${displayKey}</span>
                <span class="text-ffxi-text">${displayValue}</span>
            </div>`;
        }).join('');
        
        container.innerHTML = html;
    },
    
    closeModal() {
        document.getElementById('item-modal')?.classList.add('hidden');
    },
    
    addToCompare(slot) {
        if (!this.currentModalItem) return;
        
        if (slot === 'a') {
            this.compareSlotA = this.currentModalItem;
            this.renderCompareSlot('compare-slot-a', this.currentModalItem);
        } else {
            this.compareSlotB = this.currentModalItem;
            this.renderCompareSlot('compare-slot-b', this.currentModalItem);
        }
        
        this.closeModal();
        this.updateCompareHighlights();
    },
    
    renderCompareSlot(slotId, item) {
        const slot = document.getElementById(slotId);
        if (!slot || !item) return;
        
        const iconUrl = `/static/icons/${item.id}.png`;
        
        slot.innerHTML = `
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 bg-ffxi-darker rounded flex items-center justify-center flex-shrink-0">
                    <img src="${iconUrl}" alt="" class="w-8 h-8 object-contain"
                         onerror="this.parentElement.innerHTML='<span class=\\'text-ffxi-text-dim text-xs\\'>?</span>'">
                </div>
                <div class="min-w-0">
                    <div class="text-sm font-medium text-ffxi-text truncate">${item.name2 || item.name}</div>
                    <div class="text-xs text-ffxi-text-dim">iLvl ${item.item_level || 0}</div>
                </div>
            </div>
        `;
        slot.classList.remove('border-dashed');
        slot.classList.add('border-solid');
    },
    
    updateCompareHighlights() {
        const diffTable = document.getElementById('compare-diff-table');
        if (!diffTable) return;

        if (!this.compareSlotA || !this.compareSlotB) {
            diffTable.classList.add('hidden');
            return;
        }

        const statsA = this.compareSlotA.stats || {};
        const statsB = this.compareSlotB.stats || {};

        // Collect all stat keys from both items
        const allKeys = new Set([...Object.keys(statsA), ...Object.keys(statsB)]);

        // Group stats the same way the item modal does
        const primaryStats = ['HP', 'MP', 'STR', 'DEX', 'VIT', 'AGI', 'INT', 'MND', 'CHR'];
        const combatStats = ['DMG', 'Delay', 'Attack', 'Accuracy', 'Ranged Attack', 'Ranged Accuracy',
            'DA', 'TA', 'QA', 'Crit Rate', 'Crit Damage', 'Store TP', 'Weapon Skill Damage', 'PDL',
            'Skillchain Bonus', 'TP Bonus'];
        const magicStats = ['Magic Attack', 'Magic Accuracy', 'Magic Damage', 'Magic Burst Bonus',
            'Magic Burst Bonus II', 'Fast Cast', 'Quick Magic'];

        const groups = { 'Primary': [], 'Combat': [], 'Magic': [], 'Other': [] };
        const used = new Set();

        primaryStats.forEach(k => { if (allKeys.has(k)) { groups['Primary'].push(k); used.add(k); } });
        allKeys.forEach(k => {
            if (used.has(k)) return;
            if (combatStats.includes(k) || k.endsWith(' Skill')) { groups['Combat'].push(k); used.add(k); }
        });
        allKeys.forEach(k => {
            if (used.has(k)) return;
            if (magicStats.includes(k) || k.includes('Magic') || k.includes('Ninjutsu') ||
                k.includes('Singing') || k.includes('Instrument') || k.includes('Geomancy') ||
                k.includes('Handbell') || k.includes('Summoning') || k.includes('Blue Magic'))
            { groups['Magic'].push(k); used.add(k); }
        });
        allKeys.forEach(k => { if (!used.has(k)) groups['Other'].push(k); });

        // Sort each group alphabetically
        Object.values(groups).forEach(arr => arr.sort((a, b) => a.localeCompare(b)));

        // Build the diff table HTML
        let html = '<table class="w-full text-xs border-collapse">';
        html += '<thead><tr class="border-b border-ffxi-border">';
        html += '<th class="text-left py-1.5 px-2 text-ffxi-text-dim font-normal w-[45%]">Stat</th>';
        html += '<th class="text-right py-1.5 px-2 text-ffxi-text-dim font-normal w-[22%]">Slot A</th>';
        html += '<th class="text-right py-1.5 px-2 text-ffxi-text-dim font-normal w-[22%]">Slot B</th>';
        html += '<th class="text-right py-1.5 px-2 text-ffxi-text-dim font-normal w-[11%]">Diff</th>';
        html += '</tr></thead><tbody>';

        let hasAnyRow = false;
        for (const [groupName, keys] of Object.entries(groups)) {
            const visibleKeys = keys.filter(k => {
                const a = statsA[k] ?? 0;
                const b = statsB[k] ?? 0;
                return a !== 0 || b !== 0;
            });
            if (visibleKeys.length === 0) continue;

            // Group header
            html += `<tr><td colspan="4" class="pt-2.5 pb-1 px-2 text-ffxi-accent font-medium text-xs uppercase tracking-wider">${groupName}</td></tr>`;

            for (const key of visibleKeys) {
                hasAnyRow = true;
                const a = statsA[key] ?? 0;
                const b = statsB[key] ?? 0;
                const diff = b - a;

                // For Delay, lower is better; for everything else, higher is better
                const lowerIsBetter = key === 'Delay';
                let diffClass = 'text-ffxi-text-dim';
                let diffStr = '—';
                if (diff !== 0) {
                    const isGood = lowerIsBetter ? diff < 0 : diff > 0;
                    diffClass = isGood ? 'text-green-400' : 'text-red-400';
                    diffStr = (diff > 0 ? '+' : '') + diff;
                }

                const aClass = a !== 0 ? 'text-ffxi-text' : 'text-ffxi-text-dim';
                const bClass = b !== 0 ? 'text-ffxi-text' : 'text-ffxi-text-dim';

                html += `<tr class="border-b border-ffxi-border/30 hover:bg-ffxi-darker/50">`;
                html += `<td class="py-1 px-2 text-ffxi-text-dim">${key}</td>`;
                html += `<td class="py-1 px-2 text-right ${aClass}">${a || '—'}</td>`;
                html += `<td class="py-1 px-2 text-right ${bClass}">${b || '—'}</td>`;
                html += `<td class="py-1 px-2 text-right font-medium ${diffClass}">${diffStr}</td>`;
                html += '</tr>';
            }
        }

        html += '</tbody></table>';

        if (!hasAnyRow) {
            html = '<p class="text-ffxi-text-dim text-sm text-center py-4">No stats to compare</p>';
        }

        diffTable.innerHTML = html;
        diffTable.classList.remove('hidden');
    },
    
    clearCompare() {
        this.compareSlotA = null;
        this.compareSlotB = null;
        
        const slotA = document.getElementById('compare-slot-a');
        const slotB = document.getElementById('compare-slot-b');
        const diffTable = document.getElementById('compare-diff-table');
        
        if (slotA) {
            slotA.innerHTML = '<p class="text-ffxi-text-dim text-sm text-center py-6">Click an item to add to Slot A</p>';
            slotA.classList.add('border-dashed');
            slotA.classList.remove('border-solid');
        }
        if (slotB) {
            slotB.innerHTML = '<p class="text-ffxi-text-dim text-sm text-center py-6">Click an item to add to Slot B</p>';
            slotB.classList.add('border-dashed');
            slotB.classList.remove('border-solid');
        }
        if (diffTable) {
            diffTable.innerHTML = '';
            diffTable.classList.add('hidden');
        }
    },
    
    prevPage() {
        if (this.currentPage > 1) {
            this.currentPage--;
            this.displayItems();
        }
    },
    
    nextPage() {
        const totalPages = Math.ceil(this.filteredItems.length / this.itemsPerPage);
        if (this.currentPage < totalPages) {
            this.currentPage++;
            this.displayItems();
        }
    }
};

// Debounce helper
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}


// =============================================================================
// SET BUILDER
// =============================================================================

const EQUIPMENT_SLOTS = [
    'main', 'sub', 'range', 'ammo',
    'head', 'neck', 'ear1', 'ear2',
    'body', 'hands', 'ring1', 'ring2',
    'back', 'waist', 'legs', 'feet'
];

const SLOT_TO_API_FILTER = {
    main: 'Main',
    sub: 'Sub',
    range: 'Range',
    ammo: 'Ammo',
    head: 'Head',
    neck: 'Neck',
    ear1: 'Ear',
    ear2: 'Ear',
    body: 'Body',
    hands: 'Hands',
    ring1: 'Ring',
    ring2: 'Ring',
    back: 'Back',
    waist: 'Waist',
    legs: 'Legs',
    feet: 'Feet'
};

const SLOT_DISPLAY_NAMES = {
    main: 'Main Hand',
    sub: 'Off Hand',
    range: 'Range',
    ammo: 'Ammo',
    head: 'Head',
    neck: 'Neck',
    ear1: 'Ear 1',
    ear2: 'Ear 2',
    body: 'Body',
    hands: 'Hands',
    ring1: 'Ring 1',
    ring2: 'Ring 2',
    back: 'Back',
    waist: 'Waist',
    legs: 'Legs',
    feet: 'Feet'
};

/**
 * Extract the substring enclosed in balanced braces starting at `start`.
 * Returns the full "{...}" string, or null if unbalanced.
 */
function extractBalancedBraces(str, start) {
    let depth = 0;
    for (let i = start; i < str.length; i++) {
        if (str[i] === '{') depth++;
        else if (str[i] === '}') {
            depth--;
            if (depth === 0) return str.slice(start, i + 1);
        }
    }
    return null;
}

/**
 * Parse a GearSwap Lua gear set into a plain object keyed by internal slot names.
 * Handles both simple `slot="Name"` and augmented `slot={ name="Name", augments={...} }` forms.
 * Returns { slotName: { name, augments: [] } } or null on failure.
 */
function parseLuaGearSet(luaText) {
    // Strip single-line Lua comments
    const text = luaText.replace(/--[^\n]*/g, '');

    // Find the outermost { } block
    const braceStart = text.indexOf('{');
    if (braceStart === -1) return null;
    const body = extractBalancedBraces(text, braceStart);
    if (!body) return null;
    const inner = body.slice(1, -1);

    // Reverse mapping: GearSwap slot name → internal slot key
    const LUA_TO_SLOT = {
        main: 'main', sub: 'sub', range: 'range', ammo: 'ammo',
        head: 'head', neck: 'neck', left_ear: 'ear1', right_ear: 'ear2',
        body: 'body', hands: 'hands', left_ring: 'ring1', right_ring: 'ring2',
        back: 'back', waist: 'waist', legs: 'legs', feet: 'feet',
    };

    const result = {};
    let pos = 0;

    while (pos < inner.length) {
        // Skip whitespace and commas
        while (pos < inner.length && /[\s,]/.test(inner[pos])) pos++;
        if (pos >= inner.length) break;

        // Match identifier=
        const identMatch = inner.slice(pos).match(/^(\w+)\s*=\s*/);
        if (!identMatch) { pos++; continue; }
        const luaSlot = identMatch[1];
        const slot = LUA_TO_SLOT[luaSlot];
        pos += identMatch[0].length;

        if (inner[pos] === '"') {
            // Simple string: "Item Name"
            const strMatch = inner.slice(pos).match(/^"([^"]*)"/);
            if (strMatch) {
                if (slot) result[slot] = { name: strMatch[1], augments: [] };
                pos += strMatch[0].length;
            } else { pos++; }
        } else if (inner[pos] === '{') {
            // Table: { name="...", augments={'a', 'b'} }
            const tableStr = extractBalancedBraces(inner, pos);
            if (tableStr) {
                if (slot) {
                    const nameM = tableStr.match(/name\s*=\s*"([^"]+)"/);
                    const augments = [];
                    // augments table is always flat, so [^}]* is safe here
                    const augM = tableStr.match(/augments\s*=\s*\{([^}]*)\}/);
                    if (augM) {
                        const augPat = /'([^']*)'/g;
                        let am;
                        while ((am = augPat.exec(augM[1])) !== null) {
                            if (am[1]) augments.push(am[1]);
                        }
                    }
                    if (nameM) result[slot] = { name: nameM[1], augments };
                }
                pos += tableStr.length;
            } else { pos++; }
        } else {
            pos++;
        }
    }

    return Object.keys(result).length > 0 ? result : null;
}

/**
 * Parse augments out of an inventory item's name2 field.
 * name2 format: "Item Name (aug1; aug2; aug3)"
 * Returns { baseName, augments } where augments is an array (may be empty).
 */
function parseItemName2(item) {
    const name2 = item.name2 || item.name || '';
    const baseName = item.name || name2;

    // Check for an explicit augments array first (optimizer results have these)
    const existing = item._augments || item.augments || item.Augments;
    if (Array.isArray(existing) && existing.length > 0) {
        const filtered = existing.filter(a => a && a !== 'none' && a !== '');
        if (filtered.length > 0) return { baseName, augments: filtered };
    }

    // Fall back to parsing from name2: "Base Name (aug1; aug2; aug3)"
    const match = name2.match(/^(.+?)\s*\((.+)\)$/);
    if (match) {
        const augStr = match[2];
        const augments = augStr.split(';').map(a => a.trim()).filter(a => a.length > 0);
        if (augments.length > 0) return { baseName, augments };
    }

    return { baseName, augments: [] };
}

// GearSwap slot name mapping
const SLOT_TO_LUA = {
    main: 'main',
    sub: 'sub',
    range: 'range',
    ammo: 'ammo',
    head: 'head',
    neck: 'neck',
    ear1: 'left_ear',
    ear2: 'right_ear',
    body: 'body',
    hands: 'hands',
    ring1: 'left_ring',
    ring2: 'right_ring',
    back: 'back',
    waist: 'waist',
    legs: 'legs',
    feet: 'feet'
};

const SetBuilder = {
    // === Dual Set State (Phase 3) ===
    sets: {
        A: {
            items: {
                main: null, sub: null, range: null, ammo: null,
                head: null, neck: null, ear1: null, ear2: null,
                body: null, hands: null, ring1: null, ring2: null,
                back: null, waist: null, legs: null, feet: null
            },
            pathConfig: {},
            stats: {},
            mode: 'inventory'
        },
        B: {
            items: {
                main: null, sub: null, range: null, ammo: null,
                head: null, neck: null, ear1: null, ear2: null,
                body: null, hands: null, ring1: null, ring2: null,
                back: null, waist: null, legs: null, feet: null
            },
            pathConfig: {},
            stats: {},
            mode: 'inventory'
        }
    },
    activeSet: 'A',  // Which set is currently being edited

    // Per-set custom stats (set bonuses / augments not tracked by the optimizer)
    customStats: {
        A: { store_tp: 0, tp_bonus: 0, double_attack: 0, triple_attack: 0, quad_attack: 0, ws_damage: 0, ws_accuracy: 0, crit_rate: 0, crit_damage: 0 },
        B: { store_tp: 0, tp_bonus: 0, double_attack: 0, triple_attack: 0, quad_attack: 0, ws_damage: 0, ws_accuracy: 0, crit_rate: 0, crit_damage: 0 },
    },

    // Convenience getters for backward compatibility
    get currentSet() { return this.sets[this.activeSet].items; },
    get currentPathConfig() { return this.sets[this.activeSet].pathConfig; },
    get currentMode() { return this.sets[this.activeSet].mode; },
    get currentStats() { return this.sets[this.activeSet].stats; },
    
    // Convenience setter for mode
    set currentModeValue(val) { this.sets[this.activeSet].mode = val; },
    
    activeSlot: null,           // Slot currently being edited
    pickerItems: [],            // Items available for current slot
    filteredPickerItems: [],    // Filtered items for display
    
    // === Path Configuration (Dream Mode - Phase 2) ===
    pathDatabase: null,
    pathDatabaseLoading: false,

    // Maps every known augment-table key variant to the canonical wsdist key used
    // by item.stats.  Without this, e.g. path key "attack" and item key "Attack"
    // land in separate rows of the comparison panel.
    PATH_STAT_KEY_MAP: {
        damage:'DMG', Damage:'DMG', dmg:'DMG',
        delay:'Delay',
        str:'STR', dex:'DEX', vit:'VIT', agi:'AGI',
        int:'INT', mnd:'MND', chr:'CHR', hp:'HP', mp:'MP',
        attack:'Attack', atk:'Attack',
        accuracy:'Accuracy', acc:'Accuracy',
        ranged_attack:'Ranged Attack', ranged_accuracy:'Ranged Accuracy',
        store_tp:'Store TP', stp:'Store TP',
        da:'DA', double_attack:'DA',
        ta:'TA', triple_attack:'TA',
        qa:'QA', quad_attack:'QA',
        crit_rate:'Crit Rate', crit:'Crit Rate',
        crit_damage:'Crit Damage',
        ws_damage:'Weapon Skill Damage', weapon_skill_damage:'Weapon Skill Damage',
        ws_accuracy:'WS Accuracy', weapon_skill_accuracy:'WS Accuracy',
        pdl:'PDL',
        skillchain_bonus:'Skillchain Bonus', sc_bonus:'Skillchain Bonus',
        tp_bonus:'TP Bonus',
        dt:'DT', pdt:'PDT', mdt:'MDT',
        gear_haste:'Gear Haste', haste:'Gear Haste',
        dual_wield:'Dual Wield', dw:'Dual Wield',
        magic_attack:'Magic Attack', mab:'Magic Attack',
        magic_accuracy:'Magic Accuracy', macc:'Magic Accuracy',
        magic_damage:'Magic Damage',
        magic_burst_bonus:'Magic Burst Bonus', mbb:'Magic Burst Bonus',
        magic_burst_bonus_ii:'Magic Burst Bonus II',
        fast_cast:'Fast Cast', fc:'Fast Cast',
        quick_magic:'Quick Magic',
        // Cure / healing
        cure_potency:'Cure Potency',
        cure_potency_ii:'Cure Potency II',
        // Passive resource recovery (idle/DT sets)
        refresh:'Refresh',
        regen:'Regen',
        // Midcast spell potency / duration
        regen_potency:'"Regen" Potency',
        regen_effect_duration:'"Regen" Effect Duration',
        refresh_potency:'"Refresh" Potency',
        refresh_effect_duration:'"Refresh" Effect Duration',
        // Dark magic
        drain_aspir_potency:'"Drain"/"Aspir" Potency',
        enmity:'Enmity',
        spell_interruption_rate_down:"Spell Interruption Rate Down",
        enfeebling_effect:"Enfeebling Magic Effect",
        enhancing_duration: "Enhancing Magic Duration",
        enfeebling_duration: "Enfeebling Magic Duration",
    },
    /** Normalize a single path stat key to its canonical wsdist form. */
    normalizePathStatKey(key) {
        if (this.PATH_STAT_KEY_MAP[key]) return this.PATH_STAT_KEY_MAP[key];
        // Generic snake_case → Title Case fallback for any unmapped key
        if (key.includes('_')) {
            return key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
        }
        return key;
    },

    /** Apply key normalization to a raw path stats object, summing any collisions. */
    normalizePathStats(rawStats) {
        if (!rawStats) return null;
        const out = {};
        for (const [k, v] of Object.entries(rawStats)) {
            const canonical = this.normalizePathStatKey(k);
            if (typeof v === 'number') {
                out[canonical] = (out[canonical] || 0) + v;
            } else {
                out[canonical] = v;
            }
        }
        return out;
    },

    // Stats stored in basis points (100 = 1%) that should display as percentages
    BASIS_POINT_STATS: new Set([
        'enhancing_duration', 'enfeebling_duration',
    ]),

    /** Format a stat value for display, converting basis-point stats to percentages. */
    formatStatValue(key, value) {
        if (typeof value !== 'number') {
            return Array.isArray(value) ? value.join(', ') : value;
        }
        if (this.BASIS_POINT_STATS.has(key)) {
            const pct = value / 100;
            return (pct > 0 ? '+' : '') + pct + '%';
        }
        return value > 0 ? `+${value}` : `${value}`;
    },
    
    // === Path Database Methods ===
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
            if (!response.ok) throw new Error('Failed to fetch');
            this.pathDatabase = await response.json();
            console.log('Path database loaded:', Object.keys(this.pathDatabase.items).length, 'items');
        } catch (error) {
            console.error('Failed to load path database:', error);
            showToast('Path augment data not available', 'warning');
            this.pathDatabase = { items: {} };
        }
        this.pathDatabaseLoading = false;
        return this.pathDatabase;
    },
    
    hasPathAugment(itemId) {
        if (!this.pathDatabase) return false;
        return String(itemId) in this.pathDatabase.items;
    },
    
    getItemPathInfo(itemId) {
        if (!this.pathDatabase || !this.pathDatabase.items[String(itemId)]) {
            return null;
        }
        const item = this.pathDatabase.items[String(itemId)];
        return {
            name: item.name,
            paths: Object.keys(item.paths).sort(),
            maxRank: item.max_rank || 15
        };
    },
    
    getPathStats(itemId, path, rank) {
        if (!this.pathDatabase) return null;
        const item = this.pathDatabase.items[String(itemId)];
        if (!item || !item.paths[path]) return null;
        
        // Find the tier at or below the requested rank
        const tiers = item.paths[path].tiers;
        let bestTier = null;
        let bestRank = 0;
        
        for (const tierRank of Object.keys(tiers)) {
            const r = parseInt(tierRank);
            if (r <= rank && r > bestRank) {
                bestRank = r;
                bestTier = tiers[tierRank];
            }
        }
        
        return bestTier ? bestTier.stats : null;
    },
    
    getPathEligibleItems() {
        const eligible = [];
        for (const slot of EQUIPMENT_SLOTS) {
            const item = this.currentSet[slot];
            if (item && this.hasPathAugment(item.id)) {
                eligible.push({ slot, item });
            }
        }
        return eligible;
    },
    
    // === Initialization ===
    init() {
        // Update job display when job changes
        this.updateJobDisplay();
        
        // Listen for job changes
        const jobSelect = document.getElementById('job-select');
        if (jobSelect) {
            jobSelect.addEventListener('change', () => {
                this.updateJobDisplay();
                // Invalidate inventory cache when job changes
                this.inventoryCache = null;
                this.inventoryCacheJob = null;
                // Re-validate current set if in inventory mode
                if (this.currentMode === 'inventory') {
                    this.validateCurrentSet();
                }
            });
        }
        
        // Listen for sub-job changes (affects dual wield eligibility)
        const subjobSelect = document.getElementById('subjob-select');
        if (subjobSelect) {
            subjobSelect.addEventListener('change', () => {
                this.updateJobDisplay();
                // Invalidate inventory cache when subjob changes (affects DW options)
                this.inventoryCache = null;
                this.inventoryCacheJob = null;
            });
        }
        
        // Initialize set tabs
        this.updateSetTabs();
        
        // Initialize slot cards
        this.renderAllSlots();
        
        // Initialize comparison stats
        this.renderComparisonStats();
        
        // Setup search debounce for picker
        const pickerSearch = document.getElementById('picker-search');
        if (pickerSearch) {
            pickerSearch.addEventListener('input', debounce(() => this.filterPickerItems(), 200));
        }
        
        // Setup export set name change handler
        const exportSetName = document.getElementById('export-set-name');
        if (exportSetName) {
            exportSetName.addEventListener('input', () => this.updateLuaPreview());
        }
        
        // Initialize WS dropdown
        this.refreshWSDropdown();

        // Setup per-set custom stats panel
        this.setupCustomStatsPanel();
    },
    
    // === Set Switching (Phase 3) ===
    async switchSet(setId) {
        if (setId !== 'A' && setId !== 'B') return;
        
        this.activeSet = setId;
        
        // Update tab UI
        this.updateSetTabs();
        
        // Update mode dropdown to match this set's mode
        const modeSelect = document.getElementById('set-builder-mode');
        if (modeSelect) {
            modeSelect.value = this.sets[setId].mode;
        }
        
        // Validate inventory items if in inventory mode
        if (this.sets[setId].mode === 'inventory') {
            await this.validateSetItems(setId);
        }
        
        // Re-render everything for the new active set
        this.renderAllSlots();
        this.renderPathConfigPanel();
        this.renderComparisonStats();
    },
    
    updateSetTabs() {
        const tabA = document.getElementById('tab-set-a');
        const tabB = document.getElementById('tab-set-b');
        
        if (tabA) {
            tabA.classList.toggle('active', this.activeSet === 'A');
        }
        if (tabB) {
            tabB.classList.toggle('active', this.activeSet === 'B');
        }
        
        // Update header to show which set is active
        const header = document.getElementById('set-builder-header');
        if (header) {
            header.textContent = `Set Builder - Set ${this.activeSet}`;
        }
    },
    
    // === Copy Between Sets (Phase 3) ===
    copySetAToB() {
        // Deep copy items only (not pathConfig - let user configure paths fresh)
        this.sets.B.items = JSON.parse(JSON.stringify(this.sets.A.items));
        // Don't copy pathConfig - each set manages its own path augments
        // Don't change mode - keep destination set's mode
        
        // Recalculate Set B stats
        this.calculateStatsForSet('B');
        
        // Validate if Set B is in inventory mode
        if (this.sets.B.mode === 'inventory') {
            this.validateSetItems('B');
        }
        
        // Update UI - if we're viewing Set B, re-render slots
        if (this.activeSet === 'B') {
            this.renderAllSlots();
        }
        this.renderComparisonStats();
        showToast('Set A copied to Set B', 'success');
    },
    
    copySetBToA() {
        // Deep copy items only (not pathConfig - let user configure paths fresh)
        this.sets.A.items = JSON.parse(JSON.stringify(this.sets.B.items));
        // Don't copy pathConfig - each set manages its own path augments
        // Don't change mode - keep destination set's mode
        
        // Recalculate Set A stats
        this.calculateStatsForSet('A');
        
        // Validate if Set A is in inventory mode
        if (this.sets.A.mode === 'inventory') {
            this.validateSetItems('A');
        }
        
        // If currently viewing Set A, re-render slots
        if (this.activeSet === 'A') {
            this.renderAllSlots();
        }
        
        // Update UI
        this.renderComparisonStats();
        showToast('Set B copied to Set A', 'success');
    },
    
    // === Inventory Validation ===
    inventoryCache: null,  // Cache of inventory item IDs
    inventoryCacheJob: null,  // Job the cache was built for
    missingItems: { A: new Set(), B: new Set() },  // Track missing items per set
    
    async loadInventoryCache(forceRefresh = false) {
        const currentJob = AppState.selectedJob || '';
        
        // Return cached if same job and not forcing refresh
        if (!forceRefresh && this.inventoryCache && this.inventoryCacheJob === currentJob) {
            return this.inventoryCache;
        }
        
        try {
            // Fetch all inventory items (no slot filter to get everything)
            let url = '/api/inventory';
            if (currentJob) url += `?job=${currentJob}`;
            
            const response = await API.fetch(url);
            
            if (response.error) {
                console.error('Failed to load inventory cache:', response.error);
                return new Set();
            }
            
            // Build a Set of item IDs for fast lookup
            this.inventoryCache = new Set();
            for (const item of (response.items || [])) {
                this.inventoryCache.add(item.id);
                // Also add by name for fuzzy matching
                if (item.name) this.inventoryCache.add(item.name.toLowerCase());
                if (item.name2) this.inventoryCache.add(item.name2.toLowerCase());
            }
            this.inventoryCacheJob = currentJob;
            
            return this.inventoryCache;
        } catch (error) {
            console.error('Error loading inventory cache:', error);
            return new Set();
        }
    },
    
    async validateSetItems(setId) {
        const set = this.sets[setId];
        
        // Only validate if in inventory mode
        if (set.mode !== 'inventory') {
            this.missingItems[setId] = new Set();
            return;
        }
        
        // Load inventory cache
        await this.loadInventoryCache();
        
        if (!this.inventoryCache) {
            this.missingItems[setId] = new Set();
            return;
        }
        
        // Check each equipped item
        const missing = new Set();
        for (const slot of EQUIPMENT_SLOTS) {
            const item = set.items[slot];
            if (!item) continue;
            
            // Check if item exists in inventory by ID or name
            const hasItem = this.inventoryCache.has(item.id) ||
                           (item.name && this.inventoryCache.has(item.name.toLowerCase())) ||
                           (item.name2 && this.inventoryCache.has(item.name2.toLowerCase()));
            
            if (!hasItem) {
                missing.add(slot);
            }
        }
        
        this.missingItems[setId] = missing;
        
        // Re-render slots if this is the active set
        if (this.activeSet === setId) {
            this.renderAllSlots();
        }
    },
    
    async validateCurrentSet() {
        await this.validateSetItems(this.activeSet);
    },
    
    // === Mode Management ===
    async setMode(mode) {
        this.sets[this.activeSet].mode = mode;
        const modeSelect = document.getElementById('set-builder-mode');
        if (modeSelect) {
            modeSelect.value = mode;
        }
        
        // Clear path config when switching to inventory mode
        if (mode === 'inventory') {
            this.sets[this.activeSet].pathConfig = {};
            // Validate items exist in inventory
            await this.validateSetItems(this.activeSet);
        } else if (mode === 'dream') {
            // Clear missing items tracking for dream mode
            this.missingItems[this.activeSet] = new Set();
            // Pre-load path database when entering dream mode
            await this.ensurePathDatabase();
        }
        
        // Update displays — await the path panel so configs are initialized
        // before calculateStatsForSet reads them
        this.renderAllSlots();
        await this.renderPathConfigPanel();
        this.calculateStatsForSet(this.activeSet);
        this.renderComparisonStats();
        
        showToast(`Set ${this.activeSet} switched to ${mode === 'dream' ? 'Dream Set' : 'Inventory'} mode`, 'info');
    },
    
    async copyToDreamSet() {
        // Switch to dream mode and keep current items
        await this.setMode('dream');
        // Pre-load path database for smoother experience
        await this.ensurePathDatabase();
        // Re-render path panel now that database is loaded
        this.renderPathConfigPanel();
        showToast('Set copied to Dream mode. You can now add any item from the database.', 'success');
    },
    
    // === Job Display ===
    updateJobDisplay() {
        const jobSpan = document.getElementById('set-builder-job');
        if (jobSpan) {
            const mainJob = AppState.selectedJob || 'Select a job';
            const subJob = AppState.selectedSubJob ? `/${AppState.selectedSubJob.toUpperCase()}` : '';
            const dwStatus = this.canDualWield() ? ' <span class="text-ffxi-green text-xs">(DW)</span>' : '';
            jobSpan.innerHTML = `${mainJob}${subJob}${dwStatus}`;
        }
    },
    
    // === Slot Management ===
    async openSlotPicker(slot) {
        // Block sub slot if main weapon is hand-to-hand (2H can use grips)
        if (slot === 'sub') {
            const mainWeapon = this.currentSet.main;
            if (mainWeapon && this.isHandToHand(mainWeapon)) {
                showToast('Hand-to-hand weapons use both hands - off-hand slot is unavailable', 'warning');
                return;
            }
        }
        
        this.activeSlot = slot;
        
        // Update modal title
        const titleEl = document.getElementById('picker-modal-title');
        if (titleEl) {
            titleEl.textContent = `Select ${SLOT_DISPLAY_NAMES[slot] || slot}`;
        }
        
        // Clear search
        const searchInput = document.getElementById('picker-search');
        if (searchInput) {
            searchInput.value = '';
        }
        
        // Show modal
        const modal = document.getElementById('set-builder-picker-modal');
        if (modal) {
            modal.classList.remove('hidden');
        }
        
        // Inject hover preview panel
        this.initPickerPreview();
        
        // Load items for this slot
        await this.loadSlotItems(slot);
    },
    
    async loadSlotItems(slot) {
        const grid = document.getElementById('picker-items-grid');
        if (grid) {
            grid.innerHTML = '<p class="text-ffxi-text-dim col-span-full text-center py-8">Loading items...</p>';
        }
        
        try {
            const apiSlot = SLOT_TO_API_FILTER[slot];
            const job = AppState.selectedJob || '';
            const showAll = this.currentMode === 'dream';
            
            let url = `/api/inventory?slot=${apiSlot}`;
            if (job) url += `&job=${job}`;
            if (showAll) url += '&show_all=true';
            
            const response = await API.fetch(url);
            
            if (response.error) {
                showToast(response.error, 'error');
                this.pickerItems = [];
            } else {
                this.pickerItems = response.items || [];
            }
            
            // For sub slot with dual wield capability, also fetch one-handed main weapons
            if (slot === 'sub' && this.canDualWield()) {
                // Check if main hand has a 2H weapon - if so, don't show DW options
                const mainWeapon = this.currentSet.main;
                if (!mainWeapon || !this.isTwoHandedWeapon(mainWeapon)) {
                    let mainUrl = `/api/inventory?slot=Main`;
                    if (job) mainUrl += `&job=${job}`;
                    if (showAll) mainUrl += '&show_all=true';
                    
                    const mainResponse = await API.fetch(mainUrl);
                    
                    if (!mainResponse.error && mainResponse.items) {
                        // Filter to only one-handed weapons and add to picker items
                        const oneHandedWeapons = mainResponse.items.filter(item => this.isOneHandedWeapon(item));
                        
                        // Add a marker to identify these as dual-wield options
                        oneHandedWeapons.forEach(item => {
                            item._isDualWieldOption = true;
                        });
                        
                        // Combine: sub items first, then one-handed weapons
                        // Use a Set to avoid duplicates by item ID
                        const existingIds = new Set(this.pickerItems.map(i => i.id));
                        const uniqueWeapons = oneHandedWeapons.filter(w => !existingIds.has(w.id));
                        this.pickerItems = [...this.pickerItems, ...uniqueWeapons];
                    }
                }
            }
            
            // For sub slot, filter based on main hand weapon
            if (slot === 'sub') {
                const mainWeapon = this.currentSet.main;
                const mainIs2H = mainWeapon && this.isTwoHandedWeapon(mainWeapon);
                const mainIs1H = mainWeapon && !this.isTwoHandedWeapon(mainWeapon) && !this.isHandToHand(mainWeapon);
                
                this.pickerItems = this.pickerItems.filter(item => {
                    // If main hand has 2H weapon, only allow grips
                    if (mainIs2H) {
                        return item.type === 'Grip';
                    }
                    
                    // If main hand has 1H weapon, exclude grips
                    if (mainIs1H && item.type === 'Grip') {
                        return false;
                    }
                    
                    // Otherwise, normal filtering:
                    // Allow normal sub-slot items (shields, grips, etc.)
                    if (item.slot === 'Sub') return true;
                    // For Main slot items (dual-wield weapons), ensure they're one-handed
                    if (item.slot === 'Main') return this.isOneHandedWeapon(item);
                    // Allow other items (shouldn't happen, but be safe)
                    return true;
                });
            }
            
            this.filteredPickerItems = [...this.pickerItems];
            this.renderPickerItems();
            
        } catch (error) {
            console.error('Failed to load slot items:', error);
            showToast('Failed to load items', 'error');
            this.pickerItems = [];
            this.filteredPickerItems = [];
            this.renderPickerItems();
        }
    },
    
    filterPickerItems() {
        const searchInput = document.getElementById('picker-search');
        const search = (searchInput?.value || '').toLowerCase().trim();
        
        if (!search) {
            this.filteredPickerItems = [...this.pickerItems];
        } else {
            this.filteredPickerItems = this.pickerItems.filter(item => {
                const name = (item.name || '').toLowerCase();
                const name2 = (item.name2 || '').toLowerCase();
                const nameLog = (item.name_log || '').toLowerCase();
                return name.includes(search) || name2.includes(search) || nameLog.includes(search);
            });
        }
        
        this.renderPickerItems();
    },
    
    renderPickerItems() {
        const grid = document.getElementById('picker-items-grid');
        const countEl = document.getElementById('picker-item-count');
        
        if (countEl) {
            countEl.textContent = this.filteredPickerItems.length;
        }
        
        if (!grid) return;
        
        if (this.filteredPickerItems.length === 0) {
            grid.innerHTML = `<p class="text-ffxi-text-dim col-span-full text-center py-8">
                No items found. ${this.currentMode === 'inventory' ? 'Try enabling Dream Set mode for all items.' : ''}
            </p>`;
            return;
        }
        
        // Render items (limit to first 100 for performance)
        const itemsToShow = this.filteredPickerItems.slice(0, 100);
        
        grid.innerHTML = itemsToShow.map((item, index) => {
            const iconUrl = `/static/icons/${item.id}.png`;
            const displayName = item.name2 || item.name;
            const ilvl = item.item_level || item.stats?.['Item Level'] || 0;
            
            // Get a few key stats for preview
            const stats = item.stats || {};
            const statPreview = [];
            if (stats['DMG']) statPreview.push(`DMG:${stats['DMG']}`);
            if (stats['Delay']) statPreview.push(`Dly:${stats['Delay']}`);
            if (stats['STR']) statPreview.push(`STR+${stats['STR']}`);
            if (stats['DEX']) statPreview.push(`DEX+${stats['DEX']}`);
            if (stats['Attack']) statPreview.push(`Atk+${stats['Attack']}`);
            if (stats['Accuracy']) statPreview.push(`Acc+${stats['Accuracy']}`);
            
            return `
                <div class="picker-item-card" onclick="SetBuilder.selectItem(${index})" onmouseenter="SetBuilder.showPickerPreview(${index})" onmouseleave="SetBuilder.hidePickerPreview()">
                    <div class="flex items-start gap-2">
                        <div class="w-10 h-10 bg-ffxi-darker rounded flex items-center justify-center flex-shrink-0">
                            <img src="${iconUrl}" alt="" class="w-8 h-8 object-contain" 
                                 onerror="this.parentElement.innerHTML='<span class=\\'text-ffxi-text-dim text-xs\\'>?</span>'">
                        </div>
                        <div class="flex-1 min-w-0">
                            <div class="text-sm text-ffxi-text truncate font-medium">${displayName}</div>
                            <div class="text-xs text-ffxi-text-dim">iLvl ${ilvl} • ${item.type || 'Unknown'}</div>
                            <div class="text-xs text-ffxi-text-dim mt-0.5 truncate">${statPreview.slice(0, 4).join(' ') || 'No stats'}</div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        
        if (this.filteredPickerItems.length > 100) {
            grid.innerHTML += `<p class="text-ffxi-text-dim col-span-full text-center py-2 text-xs">
                Showing first 100 items. Use search to find more.
            </p>`;
        }
    },
    
    async selectItem(index) {
        const item = this.filteredPickerItems[index];
        if (!item || !this.activeSlot) return;
        
        // Prevent invalid items in sub slot
        if (this.activeSlot === 'sub') {
            if (this.isTwoHandedWeapon(item)) {
                showToast('Two-handed weapons cannot be equipped in the off-hand', 'warning');
                return;
            }
            if (this.isHandToHand(item)) {
                showToast('Hand-to-hand weapons cannot be equipped in the off-hand', 'warning');
                return;
            }
            
            const mainWeapon = this.currentSet.main;
            // If main hand has 2H weapon, only allow grips
            if (mainWeapon && this.isTwoHandedWeapon(mainWeapon) && item.type !== 'Grip') {
                showToast('Two-handed weapons can only be paired with grips', 'warning');
                return;
            }
            // If main hand has 1H weapon, block grips
            if (mainWeapon && !this.isTwoHandedWeapon(mainWeapon) && !this.isHandToHand(mainWeapon) && item.type === 'Grip') {
                showToast('Grips can only be used with two-handed weapons', 'warning');
                return;
            }
        }
        
        // Set the item in the current slot
        this.currentSet[this.activeSlot] = item;
        
        // Handle main weapon changes that affect sub slot
        if (this.activeSlot === 'main') {
            // Hand-to-Hand weapons - always clear sub slot
            if (this.isHandToHand(item)) {
                this.currentSet.sub = null;
                delete this.currentPathConfig['sub'];
            }
            // Two-handed weapons - clear sub slot if it's not a grip
            else if (this.isTwoHandedWeapon(item)) {
                const subItem = this.currentSet.sub;
                if (subItem && subItem.type !== 'Grip') {
                    this.currentSet.sub = null;
                    delete this.currentPathConfig['sub'];
                }
            }
            // One-handed weapons - clear sub slot if it's a grip
            else {
                const subItem = this.currentSet.sub;
                if (subItem && subItem.type === 'Grip') {
                    this.currentSet.sub = null;
                    delete this.currentPathConfig['sub'];
                }
            }
        }
        
        // Store slot before closing modal (closePickerModal sets activeSlot to null)
        const slotToRender = this.activeSlot;
        const isMainSlot = this.activeSlot === 'main';
        
        // Initialize path config for dream mode items with path augments
        if (this.currentMode === 'dream') {
            await this.ensurePathDatabase();
            if (this.hasPathAugment(item.id)) {
                const pathInfo = this.getItemPathInfo(item.id);
                if (pathInfo) {
                    this.currentPathConfig[slotToRender] = {
                        itemId: item.id,
                        path: pathInfo.paths[0],
                        rank: pathInfo.maxRank
                    };
                }
            } else {
                // Clear any previous path config for this slot if item doesn't have paths
                delete this.currentPathConfig[slotToRender];
            }
        } else {
            // Clear path config in inventory mode
            delete this.currentPathConfig[slotToRender];
        }
        
        // Close modal
        this.closePickerModal();
        
        // Update display
        this.renderSlotCard(slotToRender);
        if (isMainSlot) {
            this.renderSlotCard('sub');  // Update sub slot if main changed
        }
        
        // Recalculate stats and update displays
        this.calculateStatsForSet(this.activeSet);
        this.renderComparisonStats();
        this.renderPathConfigPanel();
        // Refresh WS dropdown if main or range slot changed (skill type may differ)
        if (slotToRender === 'main' || slotToRender === 'range') this.refreshWSDropdown();
    },
    
    isTwoHandedWeapon(item) {
        if (!item) return false;
        // Check stats['Skill Type'] for weapons from inventory API
        const skillType = item.stats?.['Skill Type'] || item.skill_type || '';
        const twoHandedSkills = ['Great Sword', 'Great Axe', 'Scythe', 'Polearm', 'Staff', 'Great Katana'];
        if (twoHandedSkills.includes(skillType)) return true;
        
        // Fallback: check type field (lowercase) for other items
        const type = (item.type || '').toLowerCase();
        const twoHandedTypes = ['great sword', 'great axe', 'scythe', 'polearm', 'staff', 'great katana'];
        return twoHandedTypes.some(t => type.includes(t));
    },
    
    isOneHandedWeapon(item) {
        if (!item) return false;
        
        // Must be a main-hand weapon (API returns slot field)
        if (item.slot !== 'Main') return false;
        
        // Check stats['Skill Type'] for weapons from inventory API
        const skillType = item.stats?.['Skill Type'] || item.skill_type || '';
        
        // Exclude two-handed weapons
        const twoHandedSkills = ['Great Sword', 'Great Axe', 'Scythe', 'Polearm', 'Staff', 'Great Katana'];
        if (twoHandedSkills.includes(skillType)) return false;
        
        // Exclude hand-to-hand (can't go in sub slot)
        if (skillType === 'Hand-to-Hand') return false;
        
        // If it's a main slot item and not 2H or H2H, it's valid for DW
        return true;
    },
    
    isHandToHand(item) {
        if (!item) return false;
        // Check stats['Skill Type'] for weapons from inventory API
        const skillType = item.stats?.['Skill Type'] || item.skill_type || '';
        if (skillType === 'Hand-to-Hand') return true;
        // Fallback to type field
        const type = (item.type || '').toLowerCase();
        return type.includes('hand-to-hand');
    },
    
    canDualWield() {
        // Jobs that have native dual wield
        // Note: THF only gets DW as main job, not as sub job
        const dualWieldMainJobs = ['NIN', 'DNC', 'BLU', 'THF'];
        const dualWieldSubJobs = ['NIN', 'DNC'];
        
        const mainJob = (AppState.selectedJob || '').toUpperCase();
        const subJob = (AppState.selectedSubJob || '').toUpperCase();
        
        return dualWieldMainJobs.includes(mainJob) || dualWieldSubJobs.includes(subJob);
    },
    
    clearCurrentSlot() {
        if (!this.activeSlot) return;
        this.clearSlot(this.activeSlot);
        this.closePickerModal();
    },
    
    clearSlot(slot) {
        this.currentSet[slot] = null;
        // Clear path config for this slot
        delete this.currentPathConfig[slot];
        // Clear from missing items
        this.missingItems[this.activeSet]?.delete(slot);
        
        this.renderSlotCard(slot);
        this.calculateStatsForSet(this.activeSet);
        this.renderComparisonStats();
        this.renderPathConfigPanel();
    },
    
    clearAllSlots() {
        for (const slot of EQUIPMENT_SLOTS) {
            this.currentSet[slot] = null;
        }
        // Clear all path config for active set
        this.sets[this.activeSet].pathConfig = {};
        // Clear missing items for active set
        this.missingItems[this.activeSet] = new Set();
        
        this.renderAllSlots();
        this.calculateStatsForSet(this.activeSet);
        this.renderComparisonStats();
        this.renderPathConfigPanel();
        showToast(`Set ${this.activeSet} cleared`, 'info');
    },
    
    clearBothSets() {
        // Clear Set A
        for (const slot of EQUIPMENT_SLOTS) {
            this.sets.A.items[slot] = null;
        }
        this.sets.A.pathConfig = {};
        this.sets.A.stats = {};
        this.missingItems.A = new Set();
        
        // Clear Set B
        for (const slot of EQUIPMENT_SLOTS) {
            this.sets.B.items[slot] = null;
        }
        this.sets.B.pathConfig = {};
        this.sets.B.stats = {};
        this.missingItems.B = new Set();
        
        // Update UI
        this.renderAllSlots();
        this.renderComparisonStats();
        this.renderPathConfigPanel();
        showToast('Both sets cleared', 'info');
    },
    
    closePickerModal() {
        const modal = document.getElementById('set-builder-picker-modal');
        if (modal) {
            modal.classList.add('hidden');
        }
        this.destroyPickerPreview();
        this.activeSlot = null;
    },
    
    initPickerPreview() {
        this.destroyPickerPreview();
        const panel = document.createElement('div');
        panel.id = 'picker-hover-preview';
        panel.style.cssText = `
            position: fixed;
            width: 260px;
            max-height: 80vh;
            overflow-y: auto;
            background: #12171f;
            border: 1px solid #1e2630;
            border-radius: 0.5rem;
            padding: 0.75rem;
            z-index: 1001;
            display: none;
            pointer-events: none;
        `;
        document.body.appendChild(panel);
    },

    destroyPickerPreview() {
        const panel = document.getElementById('picker-hover-preview');
        if (panel) panel.remove();
    },

    showPickerPreview(index) {
        const panel = document.getElementById('picker-hover-preview');
        if (!panel) return;

        const item = this.filteredPickerItems[index];
        if (!item) return;

        // Position to the left of the modal content
        const modalContent = document.querySelector('#set-builder-picker-modal .modal-content');
        if (!modalContent) return;
        const rect = modalContent.getBoundingClientRect();

        // Only show if there's at least 280px of space to the left
        if (rect.left < 280) return;

        panel.style.left = `${rect.left - 268}px`;
        panel.style.top = `${rect.top}px`;

        // Build content
        const displayName = item.name2 || item.name;
        const ilvl = item.item_level || item.stats?.['Item Level'] || 0;
        const stats = item.stats || {};
        const map = SetBuilder.PATH_STAT_KEY_MAP || {};

        const primaryKeys = ['HP', 'MP', 'STR', 'DEX', 'VIT', 'AGI', 'INT', 'MND', 'CHR'];
        const combatKeys  = ['DMG', 'Delay', 'Attack', 'Accuracy', 'Ranged Attack', 'Ranged Accuracy',
                              'DA', 'TA', 'QA', 'Crit Rate', 'Crit Damage', 'Store TP',
                              'Weapon Skill Damage', 'PDL', 'Skillchain Bonus', 'TP Bonus'];
        const magicKeys   = ['Magic Attack', 'Magic Accuracy', 'Magic Damage', 'Magic Burst Bonus',
                              'Magic Burst Bonus II', 'Fast Cast', 'Quick Magic'];

        const allKeys = Object.keys(stats).filter(k =>
            stats[k] !== undefined && stats[k] !== 0 && stats[k] !== '' && stats[k] !== null
            && !k.startsWith('_') && k !== 'Item Level'
        );

        const used = new Set();
        const primary = [], combat = [], magic = [], other = [];

        primaryKeys.forEach(k => { if (allKeys.includes(k)) { primary.push(k); used.add(k); } });
        allKeys.forEach(k => {
            if (used.has(k)) return;
            if (combatKeys.includes(k) || k.endsWith(' Skill')) { combat.push(k); used.add(k); }
        });
        allKeys.forEach(k => {
            if (used.has(k)) return;
            if (magicKeys.includes(k) || k.includes('Magic') || k.includes('Ninjutsu') ||
                k.includes('Singing') || k.includes('Geomancy') || k.includes('Summoning') ||
                k === 'cure_potency' || k === 'cure_potency_ii' ||
                k === 'regen_potency' || k === 'regen_effect_duration' ||
                k === 'refresh_potency' || k === 'refresh_effect_duration' ||
                k === 'drain_aspir_potency' || k === 'enfeebling_effect' ||
                k === 'refresh' || k === 'regen') {
                magic.push(k); used.add(k);
            }
        });
        allKeys.forEach(k => { if (!used.has(k)) other.push(k); });

        const renderGroup = (label, keys) => {
            if (keys.length === 0) return '';
            const rows = keys.map(k => {
                const val = stats[k];
                const displayVal = SetBuilder.formatStatValue(k, val);
                const displayKey = SetBuilder.normalizePathStatKey(k);
                return `<div style="display:flex;justify-content:space-between;gap:8px;margin-bottom:2px">
                            <span style="color:#8b9298;font-size:11px">${displayKey}</span>
                            <span style="color:#e8e6e3;font-size:11px;white-space:nowrap">${displayVal}</span>
                        </div>`;
            }).join('');
            return `<div style="margin-bottom:8px">
                        <div style="color:#8b9298;font-size:10px;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px;border-bottom:1px solid #1e2630;padding-bottom:2px">${label}</div>
                        ${rows}
                    </div>`;
        };

        const iconUrl = `/static/icons/${item.id}.png`;
        panel.innerHTML = `
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;border-bottom:1px solid #1e2630;padding-bottom:8px">
                <img src="${iconUrl}" style="width:32px;height:32px;object-fit:contain" onerror="this.style.display='none'">
                <div>
                    <div style="color:#e8e6e3;font-size:13px;font-weight:600">${displayName}</div>
                    <div style="color:#8b9298;font-size:11px">iLvl ${ilvl} • ${item.type || 'Unknown'}</div>
                </div>
            </div>
            ${renderGroup('Primary', primary)}
            ${renderGroup('Combat', combat)}
            ${renderGroup('Magic', magic)}
            ${renderGroup('Other', other)}
        `;

        panel.style.display = 'block';
    },

    hidePickerPreview() {
        const panel = document.getElementById('picker-hover-preview');
        if (panel) panel.style.display = 'none';
    },

    // === Rendering ===
    renderAllSlots() {
        for (const slot of EQUIPMENT_SLOTS) {
            this.renderSlotCard(slot);
        }
    },
    
    renderSlotCard(slot) {
        const card = document.querySelector(`.slot-card[data-slot="${slot}"]`);
        if (!card) return;
        
        const item = this.currentSet[slot];
        const iconDiv = card.querySelector('.slot-icon');
        const nameDiv = card.querySelector('.slot-name');
        
        if (!iconDiv || !nameDiv) return;
        
        // Check if sub slot should be blocked (H2H weapon in main - 2H can use grips)
        if (slot === 'sub') {
            const mainWeapon = this.currentSet.main;
            const isBlocked = mainWeapon && this.isHandToHand(mainWeapon);
            
            if (isBlocked) {
                card.classList.remove('filled', 'missing-item', 'empty');
                card.classList.add('empty');
                card.style.opacity = '0.5';
                card.style.cursor = 'not-allowed';
                
                iconDiv.innerHTML = '<span class="text-ffxi-text-dim text-lg">🚫</span>';
                nameDiv.textContent = 'Blocked';
                nameDiv.classList.add('empty');
                nameDiv.classList.remove('missing');
                nameDiv.title = 'Hand-to-hand weapon equipped';
                return;
            } else {
                // Reset blocked styling
                card.style.opacity = '';
                card.style.cursor = '';
            }
        }
        
        // Check if this item is missing from inventory (only in inventory mode)
        const isMissing = this.currentMode === 'inventory' && 
                         this.missingItems[this.activeSet]?.has(slot);
        
        if (item) {
            // Filled slot
            card.classList.add('filled');
            card.classList.remove('empty');
            card.classList.toggle('missing-item', isMissing);
            
            const iconUrl = `/static/icons/${item.id}.png`;
            iconDiv.innerHTML = `<img src="${iconUrl}" alt="" class="w-8 h-8 object-contain" 
                onerror="this.parentElement.innerHTML='<span class=\\'text-ffxi-text-dim text-xs\\'>?</span>'">`;
            
            const displayName = item.name2 || item.name;
            // Truncate long names
            nameDiv.textContent = displayName.length > 18 ? displayName.substring(0, 16) + '...' : displayName;
            nameDiv.classList.remove('empty');
            nameDiv.classList.toggle('missing', isMissing);
            nameDiv.title = isMissing ? `${displayName} (NOT IN INVENTORY)` : displayName;
        } else {
            // Empty slot
            card.classList.remove('filled', 'missing-item');
            card.classList.add('empty');
            
            iconDiv.innerHTML = '<span class="text-ffxi-text-dim">?</span>';
            nameDiv.textContent = 'Empty';
            nameDiv.classList.add('empty');
            nameDiv.classList.remove('missing');
            nameDiv.title = '';
        }
    },
    
    // === Stats Calculation ===
    calculateStatsForSet(setId) {
        const set = this.sets[setId];
        set.stats = {};
        
        for (const slot of EQUIPMENT_SLOTS) {
            const item = set.items[slot];
            if (!item || !item.stats) continue;
            
            // Add base item stats
            for (const [stat, value] of Object.entries(item.stats)) {
                if (stat.startsWith('_')) continue;  // Skip internal fields
                
                if (typeof value === 'number') {
                    set.stats[stat] = (set.stats[stat] || 0) + value;
                } else if (typeof value === 'string' && !set.stats[stat]) {
                    // For non-numeric stats, just keep first occurrence
                    set.stats[stat] = value;
                }
            }
            
            // Add path stats in Dream mode
            if (set.mode === 'dream' && set.pathConfig[slot]) {
                const config = set.pathConfig[slot];
                // Only apply if config matches current item
                if (String(config.itemId) === String(item.id)) {
                    const rawPathStats = this.getPathStats(config.itemId, config.path, config.rank);
                    const pathStats = this.normalizePathStats(rawPathStats);
                    if (pathStats) {
                        for (const [stat, value] of Object.entries(pathStats)) {
                            if (typeof value === 'number') {
                                set.stats[stat] = (set.stats[stat] || 0) + value;
                            }
                        }
                    }
                }
            }
        }

        // Apply reforged artifact set bonus (accuracy / ranged acc / magic acc)
        this._applyArtifactSetBonus(setId);

        // Apply derived stat contributions (STR→Attack, DEX→Acc, AGI→Ranged Acc)
        this._applyDerivedStats(setId);

        // Apply per-set custom stats entered by the user
        this._mergeCustomStats(setId);
    },

    // -------------------------------------------------------------------------
    // Derived Stat Contributions
    // -------------------------------------------------------------------------
    // Applies standard FFXI base-stat contributions to combat stats:
    //   Attack        += STR  (1:1)
    //   Ranged Attack += STR  (1:1)
    //   Accuracy      += floor(DEX * 0.75)
    //   Ranged Accuracy += floor(AGI * 0.75)
    // These are added on top of any gear-direct values so the displayed totals
    // reflect what the game actually uses. A disclaimer is shown in the stats
    // panel so users know these contributions are already included.
    _applyDerivedStats(setId) {
        const stats = this.sets[setId].stats;

        const str = stats['STR'] || 0;
        const dex = stats['DEX'] || 0;
        const agi = stats['AGI'] || 0;

        if (str !== 0) {
            stats['Attack']        = (stats['Attack']        || 0) + str;
            stats['Ranged Attack'] = (stats['Ranged Attack'] || 0) + str;
        }
        if (dex !== 0) {
            stats['Accuracy'] = (stats['Accuracy'] || 0) + Math.floor(dex * 0.75);
        }
        if (agi !== 0) {
            stats['Ranged Accuracy'] = (stats['Ranged Accuracy'] || 0) + Math.floor(agi * 0.75);
        }
    },

    // -------------------------------------------------------------------------
    // Reforged Artifact Set Bonus
    // -------------------------------------------------------------------------
    // Rules:
    //   - Count equipped reforged artifact armor pieces (head/body/hands/legs/feet)
    //     whose name starts with the job's set prefix, plus Regal Earring / Regal Ring
    //     in any ear or ring slot.
    //   - Cap the count at 5.
    //   - If count >= 2: add (count * 15) to Accuracy, Ranged Accuracy, Magic Accuracy.
    //   - Examples: 2 pcs → +30, 3 pcs → +45, 4 pcs → +60, 5 pcs → +75.
    _ARTIFACT_PREFIXES: {
        WAR: "pummeler's",
        MNK: "anchorite's",
        WHM: "theophany",
        BLM: "spaekona's",
        RDM: "atrophy",
        THF: "pillager's",
        PLD: "reverence",
        DRK: "ignominy",
        BST: "totemic",
        BRD: "brioso",
        RNG: "orion",
        SAM: "wakido",
        NIN: "hachiya",
        DRG: "vishap",
        SMN: "convoker's",
        BLU: "assimilator's",
        COR: "laksamana's",
        PUP: "foire",
        DNC: "maxixi",
        SCH: "academic's",
        GEO: "azimuth",
        RUN: "runeist",
    },

    _applyArtifactSetBonus(setId) {
        const set = this.sets[setId];
        const job = (AppState.selectedJob || '').toUpperCase();
        const prefix = (this._ARTIFACT_PREFIXES[job] || '').toLowerCase();

        let pieceCount = 0;

        // Count matching artifact armor pieces in the five body-armor slots.
        if (prefix) {
            for (const slot of ['head', 'body', 'hands', 'legs', 'feet']) {
                const item = set.items[slot];
                if (!item) continue;
                const name = (item.name_log || item.name2 || item.name || '').toLowerCase();
                if (name.startsWith(prefix)) pieceCount++;
            }
        }

        // Count Regal Earring / Regal Ring across both ear and ring slots.
        const regalItems = new Set(['regal earring', 'regal ring']);
        for (const slot of ['ear1', 'ear2', 'ring1', 'ring2']) {
            const item = set.items[slot];
            if (!item) continue;
            const name = (item.name_log || item.name2 || item.name || '').toLowerCase();
            if (regalItems.has(name)) pieceCount++;
        }

        if (pieceCount < 2) return;

        const bonus = Math.min(pieceCount, 5) * 15;
        set.stats['Accuracy']         = (set.stats['Accuracy']         || 0) + bonus;
        set.stats['Ranged Accuracy']  = (set.stats['Ranged Accuracy']  || 0) + bonus;
        set.stats['Magic Accuracy']   = (set.stats['Magic Accuracy']   || 0) + bonus;
    },

    // Calculate stats for both sets
    calculateAllStats() {
        this.calculateStatsForSet('A');
        this.calculateStatsForSet('B');
    },

    // Merge customStats[setId] into set.stats — called at end of calculateStatsForSet
    _mergeCustomStats(setId) {
        const set = this.sets[setId];
        const custom = this.customStats[setId];
        if (!custom) return;
        for (const [key, value] of Object.entries(custom)) {
            if (typeof value !== 'number' || value === 0) continue;
            const canonical = this.normalizePathStatKey(key);
            set.stats[canonical] = (set.stats[canonical] || 0) + value;
        }
    },
    
    // === Stats Comparison Rendering (Phase 3) ===
    renderComparisonStats() {
        const container = document.getElementById('set-builder-stats');
        if (!container) return;
        
        const statsA = this.sets.A.stats || {};
        const statsB = this.sets.B.stats || {};
        
        // Get all unique stat keys from both sets
        const allKeys = new Set([...Object.keys(statsA), ...Object.keys(statsB)]);
        
        // Categorize stats
        const primaryStats = ['HP', 'MP', 'STR', 'DEX', 'VIT', 'AGI', 'INT', 'MND', 'CHR'];
        const combatStats = ['DMG', 'Delay', 'Attack', 'Accuracy', 'Ranged Attack', 'Ranged Accuracy',
            'DA', 'TA', 'QA', 'Crit Rate', 'Crit Damage', 'Store TP', 'TP Bonus', 'Weapon Skill Damage', 'WS Accuracy', 'PDL',
            'Skillchain Bonus', 'DT', 'PDT', 'MDT', 'Gear Haste', 'Dual Wield'];
        const magicStats = ['Magic Attack', 'Magic Accuracy', 'Magic Damage', 'Magic Burst Bonus', 
            'Magic Burst Bonus II', 'Fast Cast', 'Quick Magic', 'Cure Potency', 'Cure Potency II',
            '"Regen" Potency', '"Regen" Effect Duration', '"Refresh" Potency', '"Refresh" Effect Duration',
            '"Drain"/"Aspir" Potency', 'Refresh', 'Regen', 'Enmity'];
        
        const used = new Set();
        const categories = {
            Primary: [],
            Combat: [],
            Magic: [],
            Other: []
        };
        
        // Sort into primary
        for (const key of primaryStats) {
            if (allKeys.has(key)) {
                categories.Primary.push(key);
                used.add(key);
            }
        }
        
        // Sort into combat
        for (const key of allKeys) {
            if (used.has(key)) continue;
            if (combatStats.includes(key) || key.endsWith(' Skill')) {
                categories.Combat.push(key);
                used.add(key);
            }
        }
        
        // Sort into magic
        for (const key of allKeys) {
            if (used.has(key)) continue;
            if (magicStats.includes(key) || key.includes('Magic') || key.includes('Ninjutsu') || 
                key.includes('Singing') || key.includes('Instrument') || key.includes('Geomancy') ||
                key.includes('Handbell') || key.includes('Summoning') || key.includes('Blue Magic')) {
                categories.Magic.push(key);
                used.add(key);
            }
        }
        
        // Everything else goes to other
        for (const key of allKeys) {
            if (!used.has(key)) {
                categories.Other.push(key);
            }
        }
        
        // Build HTML
        let html = `
            <div class="comparison-header grid grid-cols-4 gap-2 text-xs text-ffxi-text-dim mb-3 px-2">
                <span>Stat</span>
                <span class="text-right">Set A</span>
                <span class="text-right">Set B</span>
                <span class="text-right">Diff</span>
            </div>
        `;
        
        for (const [category, keys] of Object.entries(categories)) {
            if (keys.length === 0) continue;
            
            html += `
                <div class="mb-4">
                    <h4 class="text-xs uppercase tracking-wider text-ffxi-accent mb-2">${category}</h4>
                    <div class="space-y-1">
                        ${keys.map(key => this.renderComparisonRow(key, statsA[key], statsB[key])).join('')}
                    </div>
                </div>
            `;
        }
        
        if (allKeys.size === 0) {
            html = '<p class="text-ffxi-text-dim text-center py-4">No stats to compare. Select items in Set A or Set B.</p>';
        } else {
            html += `
                <div class="mt-4 px-2 py-2 rounded bg-ffxi-dark border border-ffxi-accent border-opacity-30 text-xs text-ffxi-text-dim leading-relaxed">
                    <span class="text-ffxi-accent font-semibold">Note: </span>
                    Displayed Attack and Ranged Attack include a +STR contribution (1:1).
                    Accuracy includes +&#x230A;DEX&nbsp;&times;&nbsp;0.75&#x230B; and
                    Ranged Accuracy includes +&#x230A;AGI&nbsp;&times;&nbsp;0.75&#x230B;.
                    Reforged artifact set bonuses (+15 per piece, 2–5 pieces) are also applied to
                    Accuracy, Ranged Accuracy, and Magic Accuracy automatically.
                    Do not add these manually.
                </div>
            `;
        }
        
        container.innerHTML = html;
    },
    
    renderComparisonRow(statName, valueA, valueB) {
        const a = typeof valueA === 'number' ? valueA : 0;
        const b = typeof valueB === 'number' ? valueB : 0;
        const diff = b - a;
        
        // Determine if this stat is "better" when higher or lower
        const displayName = SetBuilder.normalizePathStatKey(statName);
        const lowerIsBetter = ['Delay', 'DT', 'PDT', 'MDT'].includes(statName);
        
        let diffClass = 'text-ffxi-text-dim';
        let diffText = '-';
        
        if (diff !== 0) {
            const isBetter = lowerIsBetter ? diff < 0 : diff > 0;
            diffClass = isBetter ? 'text-green-400' : 'text-red-400';
            diffText = SetBuilder.formatStatValue(statName, diff);
        }
        
        // Format display values
        const displayA = typeof valueA === 'number' ? SetBuilder.formatStatValue(statName, valueA) : (valueA || '-');
        const displayB = typeof valueB === 'number' ? SetBuilder.formatStatValue(statName, valueB) : (valueB || '-');
        
        return `
            <div class="grid grid-cols-4 gap-2 text-xs bg-ffxi-dark px-2 py-1 rounded">
                <span class="text-ffxi-text-dim truncate" title="${displayName}">${displayName}</span>
                <span class="text-ffxi-text text-right">${displayA}</span>
                <span class="text-ffxi-text text-right">${displayB}</span>
                <span class="${diffClass} text-right font-medium">${diffText}</span>
            </div>
        `;
    },
    
    // ==========================================================================
    // TP Simulation
    // ==========================================================================

    buildGearsetPayload(setId) {
        const set = this.sets[setId];
        const items = set.items;
        const payload = {};
        for (const slot of EQUIPMENT_SLOTS) {
            if (!items[slot]) continue;

            // Deep-clone so we never mutate stored set state
            const item = JSON.parse(JSON.stringify(items[slot]));

            // In dream mode, merge normalized path augment stats into item.stats
            // so the simulator sees the fully-augmented version of each piece
            if (set.mode === 'dream' && set.pathConfig[slot]) {
                const config = set.pathConfig[slot];
                if (String(config.itemId) === String(item.id)) {
                    const rawPathStats = this.getPathStats(config.itemId, config.path, config.rank);
                    const pathStats = this.normalizePathStats(rawPathStats);
                    if (pathStats) {
                        item.stats = item.stats || {};
                        for (const [stat, value] of Object.entries(pathStats)) {
                            if (typeof value === 'number') {
                                item.stats[stat] = (item.stats[stat] || 0) + value;
                            }
                        }
                    }
                }
            }

            payload[slot] = item;
        }
        return payload;
    },

    // Returns a display label for a set, appending "(Dream)" in dream mode
    getSetLabel(setId) {
        return this.sets[setId].mode === 'dream'
            ? `Set ${setId} (Dream)`
            : `Set ${setId}`;
    },

    // ==========================================================================
    // Custom Stats Panel (per-set)
    // ==========================================================================

    setupCustomStatsPanel() {
        // Toggle panel visibility
        const toggleBtn  = document.getElementById('sb-custom-stats-toggle');
        const panel      = document.getElementById('sb-custom-stats-panel');
        const toggleText = document.getElementById('sb-custom-stats-toggle-text');
        if (toggleBtn && panel && toggleText) {
            toggleBtn.addEventListener('click', () => {
                panel.classList.toggle('hidden');
                toggleText.textContent = panel.classList.contains('hidden') ? 'Show' : 'Hide';
            });
        }

        // Input definitions for each set
        const statInputs = [
            { id: 'stp',         stat: 'store_tp' },
            { id: 'tp-bonus',    stat: 'tp_bonus' },
            { id: 'da',          stat: 'double_attack' },
            { id: 'ta',          stat: 'triple_attack' },
            { id: 'qa',          stat: 'quad_attack' },
            { id: 'ws-damage',   stat: 'ws_damage' },
            { id: 'ws-accuracy', stat: 'ws_accuracy' },
            { id: 'crit',        stat: 'crit_rate' },
            { id: 'crit-damage', stat: 'crit_damage' },
        ];

        ['A', 'B'].forEach(setId => {
            const prefix = `sb-${setId.toLowerCase()}-custom`;
            statInputs.forEach(({ id, stat }) => {
                const input = document.getElementById(`${prefix}-${id}`);
                if (input) {
                    input.addEventListener('change', (e) => {
                        const max = parseFloat(input.max) || 9999;
                        const val = Math.min(Math.max(0, parseFloat(e.target.value) || 0), max);
                        e.target.value = val;
                        this.customStats[setId][stat] = val;
                        this.calculateStatsForSet(setId);
                        this.renderComparisonStats();
                    });
                }
            });
        });
    },

    clearCustomStats(setId) {
        const blank = { store_tp: 0, tp_bonus: 0, double_attack: 0, triple_attack: 0, quad_attack: 0, ws_damage: 0, ws_accuracy: 0, crit_rate: 0, crit_damage: 0 };
        this.customStats[setId] = { ...blank };

        const prefix = `sb-${setId.toLowerCase()}-custom`;
        const inputIds = ['stp', 'tp-bonus', 'da', 'ta', 'qa', 'ws-damage', 'ws-accuracy', 'crit', 'crit-damage'];
        inputIds.forEach(id => {
            const input = document.getElementById(`${prefix}-${id}`);
            if (input) input.value = 0;
        });

        this.calculateStatsForSet(setId);
        this.renderComparisonStats();
    },

    getCustomStatsForPayload(setId) {
        const stats = this.customStats[setId];
        const nonZero = {};
        for (const [key, value] of Object.entries(stats)) {
            if (value !== 0) nonZero[key] = value;
        }
        return Object.keys(nonZero).length > 0 ? nonZero : null;
    },

    async runTPSimulation() {
        const btn  = document.getElementById('btn-simulate-tp');
        const panel = document.getElementById('tp-sim-results');

        if (!AppState.selectedJob) { showToast('Select a job first.', 'warning'); return; }
        if (!this.sets.A.items.main && !this.sets.B.items.main) {
            showToast('Equip a weapon in the main slot of at least one set.', 'warning'); return;
        }

        if (btn) { btn.disabled = true; btn.innerHTML = `<svg class="w-4 h-4 inline mr-1 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>Simulating…`; }
        if (panel) { panel.classList.remove('hidden'); panel.innerHTML = `<div class="text-ffxi-text-dim text-center py-6 text-sm animate-pulse">Running TP simulation…</div>`; }

        try {
            const resp = await API.simulateTP({
                job: AppState.selectedJob,
                sub_job: AppState.selectedSubJob || 'war',
                master_level: AppState.masterLevel || 0,
                set_a: this.buildGearsetPayload('A'),
                set_b: this.buildGearsetPayload('B'),
                set_a_label: this.getSetLabel('A'),
                set_b_label: this.getSetLabel('B'),
                set_a_custom_stats: this.getCustomStatsForPayload('A'),
                set_b_custom_stats: this.getCustomStatsForPayload('B'),
            });
            this.renderTPSimResults(resp);
        } catch (err) {
            if (panel) panel.innerHTML = `<div class="text-ffxi-red text-center py-4 text-sm">Simulation failed: ${err.message}</div>`;
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = `<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>Simulate TP`; }
        }
    },

    renderTPSimResults(response) {
        const panel = document.getElementById('tp-sim-results');
        if (!panel) return;

        if (!response.success) {
            panel.innerHTML = `<div class="flex items-start gap-2 text-ffxi-red text-sm p-4 bg-ffxi-dark rounded-lg border border-red-500/30"><svg class="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg><span>${response.error || 'Unknown error'}</span></div>`;
            return;
        }

        const a = response.set_a, b = response.set_b;
        const cond = response.conditions || {};
        let winnerA = false, winnerB = false;
        if (!a.skipped && !b.skipped) {
            if (a.time_to_ws < b.time_to_ws) winnerA = true;
            else if (b.time_to_ws < a.time_to_ws) winnerB = true;
        }

        const buildCard = (set, isWinner) => {
            if (set.skipped) return `<div class="flex-1 bg-ffxi-dark rounded-lg border border-ffxi-border p-4 opacity-60"><div class="text-xs uppercase tracking-wider text-ffxi-text-dim mb-1">${set.label}</div><div class="text-ffxi-text-dim text-sm italic">${set.error || 'No weapon equipped'}</div></div>`;
            const border = isWinner ? 'border-ffxi-accent' : 'border-ffxi-border';
            const badge  = isWinner ? `<span class="ml-2 text-xs bg-ffxi-accent text-ffxi-dark px-2 py-0.5 rounded-full font-semibold">Faster</span>` : '';
            const timeColor = isWinner ? 'text-ffxi-accent' : 'text-ffxi-text';
            return `<div class="flex-1 bg-ffxi-dark rounded-lg border ${border} p-4">
                <div class="flex items-center justify-between mb-1"><span class="text-xs uppercase tracking-wider text-ffxi-text-dim">${set.label}</span>${badge}</div>
                <div class="text-xs text-ffxi-text-dim mb-3 truncate" title="${set.weapon}">${set.weapon}</div>
                <div class="space-y-2">
                    <div class="flex justify-between items-center"><span class="text-xs text-ffxi-text-dim">Time to WS</span><span class="text-lg font-mono font-bold ${timeColor}">${set.time_to_ws.toFixed(2)}s</span></div>
                    <div class="flex justify-between items-center"><span class="text-xs text-ffxi-text-dim">TP / Round</span><span class="text-sm font-mono text-ffxi-text">${set.tp_per_round.toFixed(1)}</span></div>
                    <div class="flex justify-between items-center"><span class="text-xs text-ffxi-text-dim">DPS</span><span class="text-sm font-mono text-ffxi-text">${Math.round(set.dps).toLocaleString()}</span></div>
                </div>
            </div>`;
        };

        let deltaHtml = '';
        if (!a.skipped && !b.skipped) {
            const delta = b.time_to_ws - a.time_to_ws;
            const sign = delta > 0 ? '+' : '';
            const col  = delta === 0 ? 'text-ffxi-text-dim' : (delta > 0 ? 'text-ffxi-accent' : 'text-red-400');
            const who  = delta > 0 ? 'Set A is faster' : (delta < 0 ? 'Set B is faster' : 'identical');
            deltaHtml = `<div class="mt-3 pt-3 border-t border-ffxi-border flex items-center justify-center gap-3 text-sm"><span class="text-ffxi-text-dim">Difference:</span><span class="font-mono font-semibold ${col}">${sign}${delta.toFixed(2)}s</span><span class="text-ffxi-text-dim">(${who})</span></div>`;
        }

        panel.innerHTML = `<div class="border-t border-ffxi-border pt-4 mt-4">
            <div class="flex items-center justify-between mb-3">
                <h3 class="text-xs uppercase tracking-wider text-ffxi-accent font-semibold">TP Simulation Results</h3>
                <span class="text-xs text-ffxi-text-dim">${cond.target || 'Training Dummy'} · ${cond.magic_haste || '43.75% M.Haste'} · No JA Haste</span>
            </div>
            <div class="flex gap-3">${buildCard(a, winnerA)}${buildCard(b, winnerB)}</div>
            ${deltaHtml}
        </div>`;
    },

    // ==========================================================================
    // WS Simulation
    // ==========================================================================

    /** Detect the skill type of the weapon in main slot of the given set. */
    getMainWeaponSkillType(setId) {
        const main = this.sets[setId].items.main;
        if (!main) return null;
        return main.stats?.['Skill Type'] || main.skill_type || null;
    },

    /** Detect the skill type of the weapon in the range slot of the given set. */
    getRangedWeaponSkillType(setId) {
        const range = this.sets[setId].items.range;
        if (!range) return null;
        return range.stats?.['Skill Type'] || range.skill_type || null;
    },

    /**
     * Build the WS option list for the Set Builder dropdown.
     * Prefers the weapon in Set A's main slot, falls back to Set B.
     * Caches the last list to avoid redundant rebuilds.
     */
    async refreshWSDropdown() {
        const select = document.getElementById('sb-ws-select');
        if (!select) return;

        // Collect all relevant skill types from BOTH main and range slots of both sets
        const skillTypes = new Set();
        for (const setId of ['A', 'B']) {
            const mainST  = this.getMainWeaponSkillType(setId);
            const rangeST = this.getRangedWeaponSkillType(setId);
            if (mainST)  skillTypes.add(mainST);
            if (rangeST) skillTypes.add(rangeST);
        }

        if (skillTypes.size === 0) {
            select.innerHTML = '<option value="">— equip a weapon first —</option>';
            select.disabled = true;
            return;
        }

        // Fetch WS for any skill types not yet in the cache
        for (const st of skillTypes) {
            const cached = AppState.weaponskills.filter(ws => ws.weapon_type === st);
            if (cached.length === 0) {
                try {
                    const data = await API.getWeaponskills(st);
                    (data.weaponskills || []).forEach(ws => {
                        if (!AppState.weaponskills.find(w => w.name === ws.name)) {
                            AppState.weaponskills.push(ws);
                        }
                    });
                } catch (e) { /* ignore */ }
            }
        }

        const filtered = AppState.weaponskills
            .filter(ws => skillTypes.has(ws.weapon_type))
            .sort((a, b) => a.name.localeCompare(b.name));

        select.innerHTML = '<option value="">Select weaponskill…</option>';
        filtered.forEach(ws => {
            const opt = document.createElement('option');
            opt.value = ws.name;
            opt.textContent = `${ws.name} (${ws.ws_type})`;
            // Pre-select if user already chose one in the WS tab
            if (AppState.selectedWeaponskill?.name === ws.name) opt.selected = true;
            select.appendChild(opt);
        });
        select.disabled = filtered.length === 0;
    },

    async runWSSimulation() {
        const btn    = document.getElementById('btn-simulate-ws');
        const panel  = document.getElementById('ws-sim-results');
        const select = document.getElementById('sb-ws-select');
        const wsName = select?.value;

        if (!AppState.selectedJob) { showToast('Select a job first.', 'warning'); return; }
        if (!wsName) { showToast('Select a weaponskill from the dropdown.', 'warning'); return; }

        // Look up the selected WS to determine if it's a ranged weaponskill
        const RANGED_WEAPON_TYPES = ['Archery', 'Marksmanship'];
        const selectedWS = AppState.weaponskills.find(ws => ws.name === wsName);
        const isRangedWS = selectedWS && RANGED_WEAPON_TYPES.includes(selectedWS.weapon_type);

        if (isRangedWS) {
            // Ranged WS requires a ranged weapon + ammo in at least one set
            const setAHasRanged = this.sets.A.items.range && this.sets.A.items.ammo;
            const setBHasRanged = this.sets.B.items.range && this.sets.B.items.ammo;
            if (!setAHasRanged && !setBHasRanged) {
                showToast('Ranged weaponskill requires a ranged weapon and ammo equipped in at least one set.', 'warning');
                return;
            }
        } else {
            const hasAnyWeapon = this.sets.A.items.main || this.sets.B.items.main;
            if (!hasAnyWeapon) {
                showToast('Equip a weapon in the main slot of at least one set.', 'warning');
                return;
            }
        }

        if (btn) { btn.disabled = true; btn.innerHTML = `<svg class="w-4 h-4 inline mr-1 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>Simulating…`; }
        if (panel) { panel.classList.remove('hidden'); panel.innerHTML = `<div class="text-ffxi-text-dim text-center py-6 text-sm animate-pulse">Running WS simulation (low buff + high buff)…</div>`; }

        try {
            const tpVal = parseInt(document.getElementById('sb-ws-tp')?.value || 1000);
            const resp = await API.simulateWS({
                job: AppState.selectedJob,
                sub_job: AppState.selectedSubJob || 'war',
                master_level: AppState.masterLevel || 0,
                weaponskill: wsName,
                tp: tpVal,
                set_a: this.buildGearsetPayload('A'),
                set_b: this.buildGearsetPayload('B'),
                set_a_label: this.getSetLabel('A'),
                set_b_label: this.getSetLabel('B'),
                set_a_custom_stats: this.getCustomStatsForPayload('A'),
                set_b_custom_stats: this.getCustomStatsForPayload('B'),
            });
            this.renderWSSimResults(resp, wsName);
        } catch (err) {
            if (panel) panel.innerHTML = `<div class="text-ffxi-red text-center py-4 text-sm">Simulation failed: ${err.message}</div>`;
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = `<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>Simulate WS`; }
        }
    },

    renderWSSimResults(response, wsName) {
        const panel = document.getElementById('ws-sim-results');
        if (!panel) return;

        if (!response.success) {
            panel.innerHTML = `<div class="flex items-start gap-2 text-ffxi-red text-sm p-4 bg-ffxi-dark rounded-lg border border-red-500/30"><svg class="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg><span>${response.error || 'Unknown error'}</span></div>`;
            return;
        }

        const a = response.set_a, b = response.set_b;

        const fmtDmg = v => v != null ? Math.round(v).toLocaleString() : '—';
        const fmtHR  = v => v != null ? `${(v * 100).toFixed(1)}%` : '—';

        const deltaBadge = (dA, dB) => {
            if (dA == null || dB == null) return '';
            const diff = dB - dA;
            const pct  = dA > 0 ? ((diff / dA) * 100).toFixed(1) : '—';
            const sign = diff >= 0 ? '+' : '';
            const col  = diff > 0 ? 'text-ffxi-accent' : (diff < 0 ? 'text-red-400' : 'text-ffxi-text-dim');
            return `<span class="text-xs font-mono ${col}">${sign}${Math.round(diff).toLocaleString()} (${sign}${pct}%)</span>`;
        };

        const winClass = (dA, dB) => {
            if (dA == null || dB == null) return ['', ''];
            if (dA > dB) return ['text-ffxi-accent font-bold', 'text-ffxi-text'];
            if (dB > dA) return ['text-ffxi-text', 'text-ffxi-accent font-bold'];
            return ['text-ffxi-text', 'text-ffxi-text'];
        };

        const rowLow  = (a.low_buff  || {}), rowHigh = (a.high_buff || {});
        const bLow    = (b.low_buff  || {}), bHigh  = (b.high_buff || {});

        const [lcA, lcB] = winClass(rowLow.damage,  bLow.damage);
        const [hcA, hcB] = winClass(rowHigh.damage, bHigh.damage);

        const skipA = a.skipped, skipB = b.skipped;

        const cellA_low  = skipA ? `<td class="px-3 py-2 text-ffxi-text-dim italic text-xs" colspan="1">${a.error || 'No weapon'}</td>` : `<td class="px-3 py-2 text-right font-mono ${lcA}">${fmtDmg(rowLow.damage)}</td>`;
        const cellB_low  = skipB ? `<td class="px-3 py-2 text-ffxi-text-dim italic text-xs" colspan="1">${b.error || 'No weapon'}</td>` : `<td class="px-3 py-2 text-right font-mono ${lcB}">${fmtDmg(bLow.damage)}</td>`;
        const cellA_high = skipA ? `<td class="px-3 py-2 text-ffxi-text-dim italic text-xs" colspan="1">—</td>` : `<td class="px-3 py-2 text-right font-mono ${hcA}">${fmtDmg(rowHigh.damage)}</td>`;
        const cellB_high = skipB ? `<td class="px-3 py-2 text-ffxi-text-dim italic text-xs" colspan="1">—</td>` : `<td class="px-3 py-2 text-right font-mono ${hcB}">${fmtDmg(bHigh.damage)}</td>`;

        const deltaLow  = (!skipA && !skipB) ? `<td class="px-3 py-2 text-right">${deltaBadge(rowLow.damage,  bLow.damage)}</td>`  : `<td class="px-3 py-2 text-ffxi-text-dim text-right">—</td>`;
        const deltaHigh = (!skipA && !skipB) ? `<td class="px-3 py-2 text-right">${deltaBadge(rowHigh.damage, bHigh.damage)}</td>` : `<td class="px-3 py-2 text-ffxi-text-dim text-right">—</td>`;

        // Hit-rate row
        const hrLowA  = skipA ? '—' : fmtHR(rowLow.hit_rate);
        const hrLowB  = skipB ? '—' : fmtHR(bLow.hit_rate);
        const hrHighA = skipA ? '—' : fmtHR(rowHigh.hit_rate);
        const hrHighB = skipB ? '—' : fmtHR(bHigh.hit_rate);

        const condLow  = response.conditions?.low_buff  || {};
        const condHigh = response.conditions?.high_buff || {};

        panel.innerHTML = `
        <div class="border-t border-ffxi-border pt-4 mt-4">
            <div class="flex items-center justify-between mb-3">
                <h3 class="text-xs uppercase tracking-wider text-ffxi-accent font-semibold">WS Simulation — ${wsName}</h3>
                <span class="text-xs text-ffxi-text-dim">vs ${condLow.target || 'Apex Toad (ilvl 132)'}</span>
            </div>

            <!-- Weapons in use -->
            <div class="flex gap-4 mb-3 text-xs text-ffxi-text-dim">
                <span><span class="text-ffxi-text">Set A:</span> ${a.weapon || 'No weapon'}</span>
                <span><span class="text-ffxi-text">Set B:</span> ${b.weapon || 'No weapon'}</span>
            </div>

            <!-- Result table -->
            <div class="overflow-x-auto">
                <table class="w-full text-sm border-collapse">
                    <thead>
                        <tr class="border-b border-ffxi-border">
                            <th class="px-3 py-2 text-left text-xs uppercase tracking-wider text-ffxi-text-dim w-28">Condition</th>
                            <th class="px-3 py-2 text-right text-xs uppercase tracking-wider text-ffxi-text-dim">Set A</th>
                            <th class="px-3 py-2 text-right text-xs uppercase tracking-wider text-ffxi-text-dim">Set B</th>
                            <th class="px-3 py-2 text-right text-xs uppercase tracking-wider text-ffxi-text-dim">B vs A</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-ffxi-border/50">
                        <!-- Low buff row -->
                        <tr class="bg-ffxi-dark/40">
                            <td class="px-3 py-3">
                                <div class="text-ffxi-text font-medium text-xs">Low Buff</div>
                                <div class="text-ffxi-text-dim text-xs mt-0.5">No buffs / bare gear</div>
                            </td>
                            ${cellA_low}${cellB_low}${deltaLow}
                        </tr>
                        <!-- Low buff hit rate -->
                        <tr class="bg-ffxi-dark/20">
                            <td class="px-3 py-1.5 pl-5 text-xs text-ffxi-text-dim">Hit Rate</td>
                            <td class="px-3 py-1.5 text-right text-xs text-ffxi-text-dim font-mono">${hrLowA}</td>
                            <td class="px-3 py-1.5 text-right text-xs text-ffxi-text-dim font-mono">${hrLowB}</td>
                            <td class="px-3 py-1.5"></td>
                        </tr>
                        <!-- High buff row -->
                        <tr class="bg-ffxi-dark/40">
                            <td class="px-3 py-3">
                                <div class="text-ffxi-text font-medium text-xs">High Buff</div>
                                <div class="text-ffxi-text-dim text-xs mt-0.5">BRD/COR/GEO + Berserk/Warcry</div>
                            </td>
                            ${cellA_high}${cellB_high}${deltaHigh}
                        </tr>
                        <!-- High buff hit rate -->
                        <tr class="bg-ffxi-dark/20">
                            <td class="px-3 py-1.5 pl-5 text-xs text-ffxi-text-dim">Hit Rate</td>
                            <td class="px-3 py-1.5 text-right text-xs text-ffxi-text-dim font-mono">${hrHighA}</td>
                            <td class="px-3 py-1.5 text-right text-xs text-ffxi-text-dim font-mono">${hrHighB}</td>
                            <td class="px-3 py-1.5"></td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <!-- Buff legend -->
            <div class="mt-3 grid grid-cols-2 gap-2 text-xs text-ffxi-text-dim border-t border-ffxi-border pt-3">
                <div>
                    <div class="text-ffxi-text mb-1">High Buff stack:</div>
                    <div>${(condHigh.buffs_summary || []).join(' · ') || 'Minuet V+IV · Blade Madrigal · Chaos Roll · Hunter\'s Roll · Geo-Fury · Berserk · Warcry'}</div>
                </div>
                <div>
                    <div class="text-ffxi-text mb-1">Debuffs:</div>
                    <div>${(condHigh.debuffs_summary || []).join(' · ') || 'Dia III · Geo-Frailty'}</div>
                </div>
            </div>
        </div>`;
    },

    // === Path Configuration (Phase 2) ===
    async renderPathConfigPanel() {
        const btn = document.getElementById('set-builder-path-config-btn');
        const countBadge = document.getElementById('path-config-count');
        
        if (!btn) return;
        
        // Only show in dream mode
        if (this.currentMode !== 'dream') {
            btn.classList.add('hidden');
            return;
        }
        
        // Ensure path database is loaded
        await this.ensurePathDatabase();
        
        // Get items that have path augments
        const pathItems = this.getPathEligibleItems();
        
        if (pathItems.length === 0) {
            btn.classList.add('hidden');
            return;
        }
        
        // Show button with count
        btn.classList.remove('hidden');
        if (countBadge) {
            countBadge.textContent = pathItems.length;
        }
        
        // Also update modal content if it's open
        this.renderPathConfigModalContent();
    },
    
    renderPathConfigModalContent() {
        const container = document.getElementById('path-config-items');
        if (!container) return;
        
        const pathItems = this.getPathEligibleItems();
        
        if (pathItems.length === 0) {
            container.innerHTML = '<p class="text-ffxi-text-dim text-center py-4">No path-augmented items in your set.</p>';
            return;
        }
        
        let html = '';
        
        let configsWereInitialized = false;

        for (const { slot, item } of pathItems) {
            const pathInfo = this.getItemPathInfo(item.id);
            if (!pathInfo) continue;
            
            // Get or initialize config for this slot; use String() to guard against
            // number/string id type mismatches across JSON serialization
            if (!this.currentPathConfig[slot] ||
                String(this.currentPathConfig[slot].itemId) !== String(item.id)) {
                this.currentPathConfig[slot] = {
                    itemId: item.id,
                    path: pathInfo.paths[0],
                    rank: pathInfo.maxRank
                };
                configsWereInitialized = true;
            }
            const config = this.currentPathConfig[slot];
            const currentStats = this.getPathStats(item.id, config.path, config.rank);
            
            // Format slot name for display
            const slotDisplayName = SLOT_DISPLAY_NAMES[slot] || slot;
            
            html += `
                <div class="bg-ffxi-dark rounded-lg p-4 border border-ffxi-border">
                    <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 bg-ffxi-darker rounded flex items-center justify-center flex-shrink-0">
                                <img src="/static/icons/${item.id}.png" alt="" class="w-8 h-8 object-contain" 
                                     onerror="this.parentElement.innerHTML='<span class=\\'text-ffxi-text-dim text-xs\\'>?</span>'">
                            </div>
                            <div>
                                <div class="text-ffxi-text font-medium">${item.name2 || item.name}</div>
                                <div class="text-xs text-ffxi-text-dim">${slotDisplayName}</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="flex items-center gap-6 mb-3">
                        <div class="flex items-center gap-2">
                            <span class="text-xs text-ffxi-text-dim">Path:</span>
                            <div class="flex gap-1">
                                ${pathInfo.paths.map(p => `
                                    <button class="px-3 py-1 text-sm rounded transition-colors ${config.path === p 
                                        ? 'bg-ffxi-accent text-ffxi-dark font-medium' 
                                        : 'bg-ffxi-panel text-ffxi-text-dim hover:text-ffxi-text hover:bg-ffxi-border'}"
                                            onclick="SetBuilder.setPathConfig('${slot}', '${p}', ${config.rank})">
                                        ${p}
                                    </button>
                                `).join('')}
                            </div>
                        </div>
                        <div class="flex items-center gap-3 flex-1">
                            <span class="text-xs text-ffxi-text-dim">Rank:</span>
                            <input type="range" min="1" max="${pathInfo.maxRank}" value="${config.rank}"
                                   class="flex-1 accent-ffxi-accent h-2 cursor-pointer"
                                   oninput="this.nextElementSibling.textContent = this.value"
                                   onchange="SetBuilder.setPathConfig('${slot}', '${config.path}', parseInt(this.value))">
                            <span class="text-sm text-ffxi-accent font-medium w-8 text-center">${config.rank}</span>
                            <span class="text-xs text-ffxi-text-dim">/ ${pathInfo.maxRank}</span>
                        </div>
                    </div>
                    
                    <div class="bg-ffxi-panel rounded p-2">
                        <div class="text-xs text-ffxi-text-dim mb-1">Path ${config.path} R${config.rank} Stats:</div>
                        <div class="flex flex-wrap gap-x-3 gap-y-1 text-sm">
                            ${currentStats 
                                ? Object.entries(this.normalizePathStats(currentStats)).map(([k,v]) => 
                                    `<span class="text-ffxi-green">${k}: ${v > 0 ? '+' : ''}${v}</span>`
                                  ).join('') 
                                : '<span class="text-ffxi-text-dim">No stats at this rank</span>'}
                        </div>
                    </div>
                </div>
            `;
        }
        
        container.innerHTML = html;

        // If we auto-initialized any new configs, recalculate so the comparison
        // panel immediately reflects the path augments
        if (configsWereInitialized) {
            this.calculateStatsForSet(this.activeSet);
            this.renderComparisonStats();
        }
    },
    
    openPathConfigModal() {
        const modal = document.getElementById('set-builder-path-modal');
        if (modal) {
            modal.classList.remove('hidden');
            // Update the set label
            const setLabel = document.getElementById('path-config-set-label');
            if (setLabel) {
                setLabel.textContent = this.activeSet;
            }
            this.renderPathConfigModalContent();
        }
    },
    
    closePathConfigModal() {
        const modal = document.getElementById('set-builder-path-modal');
        if (modal) {
            modal.classList.add('hidden');
        }
    },
    
    setPathConfig(slot, path, rank) {
        const item = this.currentSet[slot];
        if (!item) return;
        
        this.currentPathConfig[slot] = { itemId: item.id, path, rank };
        this.calculateStatsForSet(this.activeSet);
        this.renderComparisonStats();
        this.renderPathConfigModalContent();  // Update modal content
    },
    
    // === Export ===
    showExportModal() {
        const filledSlots = EQUIPMENT_SLOTS.filter(slot => this.currentSet[slot] !== null);
        
        if (filledSlots.length === 0) {
            showToast(`No items in Set ${this.activeSet} to export`, 'error');
            return;
        }
        
        const modal = document.getElementById('set-builder-export-modal');
        if (modal) {
            modal.classList.remove('hidden');
        }
        
        // Update export modal title to show which set
        const modalTitle = document.getElementById('export-modal-title');
        if (modalTitle) {
            modalTitle.textContent = `Export Set ${this.activeSet} as GearSwap Lua`;
        }
        
        this.updateLuaPreview();
    },
    
    closeExportModal() {
        const modal = document.getElementById('set-builder-export-modal');
        if (modal) {
            modal.classList.add('hidden');
        }
    },

    showImportModal() {
        const modal = document.getElementById('set-builder-import-modal');
        if (!modal) return;

        // Pre-select the inactive set as the default import target
        const targetSel = document.getElementById('import-target-set');
        if (targetSel) targetSel.value = this.activeSet === 'A' ? 'B' : 'A';

        // Reset textarea and results
        const ta = document.getElementById('import-lua-textarea');
        if (ta) ta.value = '';
        const results = document.getElementById('import-lua-results');
        if (results) { results.classList.add('hidden'); results.innerHTML = ''; }

        modal.classList.remove('hidden');
        if (ta) ta.focus();
    },

    closeImportModal() {
        const modal = document.getElementById('set-builder-import-modal');
        if (modal) modal.classList.add('hidden');
    },

    async importFromLua() {
        const luaText = document.getElementById('import-lua-textarea')?.value || '';
        const targetSetId = document.getElementById('import-target-set')?.value || this.activeSet;

        if (!luaText.trim()) {
            showToast('Paste a Lua gear set first.', 'warning');
            return;
        }

        const parsed = parseLuaGearSet(luaText);
        if (!parsed) {
            showToast('Could not parse any gear slots — check the format.', 'error');
            return;
        }

        const btn = document.getElementById('btn-do-import-lua');
        if (btn) { btn.disabled = true; btn.textContent = 'Importing…'; }

        const targetSet = this.sets[targetSetId];
        const isDream = targetSet.mode === 'dream';
        const job = AppState.selectedJob;

        const found = [], notFound = [];

        // Cache API responses by (apiSlot, isDream) to minimise round-trips
        const apiCache = {};

        for (const [slot, parsedItem] of Object.entries(parsed)) {
            const apiSlot = SLOT_TO_API_FILTER[slot];
            if (!apiSlot) continue;

            const cacheKey = `${apiSlot}-${isDream}`;
            if (!apiCache[cacheKey]) {
                try {
                    let url = `/api/inventory?slot=${apiSlot}`;
                    if (job) url += `&job=${job}`;
                    if (isDream) url += '&show_all=true';
                    const resp = await API.fetch(url);
                    apiCache[cacheKey] = resp.items || [];
                } catch (e) {
                    apiCache[cacheKey] = [];
                }
            }

            // For the sub slot, also search Main-hand weapons (dual-wield offhands
            // like Tauret are stored under slot=Main, not slot=Sub)
            if (slot === 'sub') {
                const mainCacheKey = `Main-${isDream}`;
                if (!apiCache[mainCacheKey]) {
                    try {
                        let url = `/api/inventory?slot=Main`;
                        if (job) url += `&job=${job}`;
                        if (isDream) url += '&show_all=true';
                        const resp = await API.fetch(url);
                        apiCache[mainCacheKey] = resp.items || [];
                    } catch (e) {
                        apiCache[mainCacheKey] = [];
                    }
                }
                // Merge in one-handed main weapons, deduped by id
                const existingIds = new Set(apiCache[cacheKey].map(i => i.id));
                const oneHanders = apiCache[mainCacheKey].filter(
                    i => !existingIds.has(i.id) && this.isOneHandedWeapon(i)
                );
                apiCache[cacheKey] = [...apiCache[cacheKey], ...oneHanders];
            }

            const items = apiCache[cacheKey];
            const targetName = parsedItem.name.toLowerCase().trim();
            const match = items.find(i => (i.name || '').toLowerCase().trim() === targetName);

            if (match) {
                const item = JSON.parse(JSON.stringify(match));

                if (parsedItem.augments.length > 0) {
                    // Path augment (dream mode): wire up pathConfig
                    const pathAug = parsedItem.augments.find(a => /^Path:\s*[A-Z]$/i.test(a.trim()));
                    if (pathAug && isDream) {
                        const path = pathAug.trim().replace(/^Path:\s*/i, '');
                        await this.ensurePathDatabase();
                        if (this.hasPathAugment(item.id)) {
                            const pathInfo = this.getItemPathInfo(item.id);
                            targetSet.pathConfig[slot] = {
                                itemId: item.id,
                                path,
                                rank: pathInfo?.maxRank ?? 15,
                            };
                        }
                    } else {
                        // Regular augments — store for Lua export and display
                        item._augments = parsedItem.augments;
                    }
                }

                targetSet.items[slot] = item;
                found.push({ slot, name: match.name2 || match.name });
            } else {
                notFound.push({ slot, name: parsedItem.name });
            }
        }

        // Switch to the imported set and refresh everything
        this.switchSet(targetSetId);
        this.calculateAllStats();
        this.renderAllSlots();
        this.renderComparisonStats();
        this.refreshWSDropdown();
        this.renderPathConfigPanel();

        // Render results summary inside the modal
        const resultsDiv = document.getElementById('import-lua-results');
        if (resultsDiv) {
            resultsDiv.classList.remove('hidden');
            let html = '';
            if (found.length > 0) {
                html += `<div class="text-ffxi-green text-xs font-medium mb-1">✓ ${found.length} item${found.length !== 1 ? 's' : ''} equipped</div>`;
            }
            if (notFound.length > 0) {
                const hint = !isDream ? ' — try switching to <strong>Dream Set</strong> mode' : '';
                html += `<div class="text-ffxi-red text-xs font-medium mb-1">✗ ${notFound.length} item${notFound.length !== 1 ? 's' : ''} not found${hint}:</div>`;
                html += '<ul class="text-xs text-ffxi-text-dim ml-3 space-y-0.5">';
                for (const { slot, name } of notFound) {
                    html += `<li>${SLOT_DISPLAY_NAMES[slot] || slot}: ${name}</li>`;
                }
                html += '</ul>';
            }
            resultsDiv.innerHTML = html;
        }

        if (btn) { btn.disabled = false; btn.textContent = 'Import'; }

        if (notFound.length === 0) {
            showToast(`Set ${targetSetId} imported from Lua!`, 'success');
            this.closeImportModal();
        } else {
            showToast(`${found.length} equipped, ${notFound.length} not found.`, 'warning');
        }
    },
    
    generateLuaCode() {
        const setNameInput = document.getElementById('export-set-name');
        const setName = setNameInput?.value || 'my_set';

        // Determine the active set's mode and pathConfig
        const activeSet = this.sets[this.activeSet];
        const isDream = activeSet?.mode === 'dream';
        const pathConfig = activeSet?.pathConfig || {};

        const lines = [`sets.${setName} = {`];

        // Fix empyrean earring slot order: these are right-ear only items.
        // Work on a shallow copy so we never mutate the live set state.
        const exportItems = { ...this.currentSet };
        const ear1Name = exportItems['ear1']?.name || '';
        if (isEmpyreanEarring(ear1Name)) {
            const tmp = exportItems['ear1'];
            exportItems['ear1'] = exportItems['ear2'] || null;
            exportItems['ear2'] = tmp;
        }

        for (const slot of EQUIPMENT_SLOTS) {
            const item = exportItems[slot];
            if (!item || item.name === 'Empty' || !item.name) continue;

            const luaSlot = SLOT_TO_LUA[slot];

            // Dream mode path config takes priority over name2 augments
            let augments = null;
            if (isDream && pathConfig[slot] && String(pathConfig[slot].itemId) === String(item.id)) {
                augments = [`Path: ${pathConfig[slot].path}`];
            } else {
                const parsed = parseItemName2(item);
                if (parsed.augments.length > 0) augments = parsed.augments;
            }

            let itemStr;
            if (augments && augments.length > 0) {
                const augStr = augments.map(a => `'${a}'`).join(', ');
                itemStr = `{ name="${item.name}", augments={${augStr}} }`;
            } else {
                itemStr = `"${item.name}"`;
            }

            lines.push(`    ${luaSlot}=${itemStr},`);
        }

        lines.push('}');
        return lines.join('\n');
    },
    
    updateLuaPreview() {
        const codeEl = document.getElementById('export-lua-code');
        if (codeEl) {
            codeEl.textContent = this.generateLuaCode();
        }
    },
    
    copyLuaToClipboard() {
        const code = this.generateLuaCode();
        navigator.clipboard.writeText(code).then(() => {
            showToast('Lua code copied to clipboard!', 'success');
        }).catch(err => {
            console.error('Failed to copy:', err);
            showToast('Failed to copy to clipboard', 'error');
        });
    },
    
    downloadLuaFile() {
        const setNameInput = document.getElementById('export-set-name');
        const setName = setNameInput?.value || 'my_set';
        const code = this.generateLuaCode();
        
        const blob = new Blob([code], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `${setName}.lua`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showToast('Lua file downloaded!', 'success');
    }
};


// =============================================================================
// LUA TEMPLATE OPTIMIZATION
// =============================================================================

// =============================================================================
// EMPYREAN EARRING HELPERS
// Job-specific empyrean earrings (named after the reforged 119+ set) are
// right-ear only. Detect them so we can swap any wrongly-ordered ear pairs.
// =============================================================================

const EMPYREAN_EARRING_PREFIXES = new Set([
    'boii', 'bhikku', 'ebers', 'wicce', 'lethargy',
    "skulker's", "chevalier's", "heathen's", 'nukumi',
    'fili', 'amini', 'kasuga', 'hattori', "peltast's",
    "beckoner's", 'hashishin', "chasseur's", 'karagoz',
    'maculele', 'arbatel', 'azimuth', 'erilaz',
]);

// Abbreviated first-words discovered from inventory (e.g. "chas." for "chasseur's").
// Populated by buildEmpyreanEarringAbbrevs() before optimization runs.
const empyreanEarringAbbrevPrefixes = new Set();

/**
 * Scan the user's inventory for earring items whose full name (name_log)
 * matches an empyrean earring prefix.  For each match, record the first word
 * of the abbreviated name so isEmpyreanEarring() can recognise both forms.
 *
 * Example: name_log="Chasseur's Earring +2", name="Chas. Earring +2"
 *   → "chasseur's" matches EMPYREAN_EARRING_PREFIXES
 *   → "chas." is added to empyreanEarringAbbrevPrefixes
 */
async function buildEmpyreanEarringAbbrevs() {
    // Skip if we already built the set (inventory hasn't changed)
    if (empyreanEarringAbbrevPrefixes.size > 0) return;

    try {
        const response = await API.fetch('/api/inventory?slot=Ear&search=earring');
        const items = response?.items || [];

        for (const item of items) {
            const nameLog = (item.name_log || '').toLowerCase();
            const name = (item.name || '').toLowerCase();
            if (!nameLog.includes('earring') || !name.includes('earring')) continue;

            // Check if the full (unabbreviated) name matches a known empyrean prefix
            const fullFirstWord = nameLog.split(/\s+/)[0];
            if (!EMPYREAN_EARRING_PREFIXES.has(fullFirstWord)) continue;

            // The abbreviated first word is a new alias for this empyrean earring
            const abbrevFirstWord = name.split(/\s+/)[0];
            if (abbrevFirstWord && !EMPYREAN_EARRING_PREFIXES.has(abbrevFirstWord)) {
                empyreanEarringAbbrevPrefixes.add(abbrevFirstWord);
            }
        }
    } catch (err) {
        console.warn('Failed to build empyrean earring abbreviations:', err);
    }
}

function isEmpyreanEarring(name) {
    if (!name || !name.toLowerCase().includes('earring')) return false;
    const firstWord = name.toLowerCase().split(/\s+/)[0];
    return EMPYREAN_EARRING_PREFIXES.has(firstWord)
        || empyreanEarringAbbrevPrefixes.has(firstWord);
}

/**
 * Given a content string, swap every left_ear/ear1 that holds an empyrean
 * earring with its paired right_ear/ear2.  Used to fix non-placeholder sets
 * that are preserved verbatim from the original template.
 */
function fixEmpyreanEarsInContent(content) {
    // Match: (left_ear|ear1) = "Name" or { name="Name", augments={...} }
    // We need to capture both the left and right ear values and potentially swap them.
    // Strategy: find all set blocks and within each fix the ear order.
    return content.replace(
        // Match a set block from opening { to its closing }
        // We'll do a line-pair approach instead: find left_ear/ear1 lines where
        // the value is an empyrean earring and swap with the adjacent right_ear/ear2 line.
        /([ \t]*)(left_ear|ear1)([ \t]*=[ \t]*)(\{[^}]*\}|"[^"]*")(,?)(\r?\n)([ \t]*)(right_ear|ear2)([ \t]*=[ \t]*)(\{[^}]*\}|"[^"]*")(,?)/g,
        (match, li, lKey, lEq, lVal, lComma, nl, ri, rKey, rEq, rVal, rComma) => {
            // Extract name from lVal
            let lName = '';
            if (lVal.startsWith('"')) {
                lName = lVal.slice(1, -1);
            } else {
                const nm = lVal.match(/name\s*=\s*"([^"]+)"/);
                lName = nm ? nm[1] : '';
            }
            if (!isEmpyreanEarring(lName)) return match; // not an empyrean earring, leave as-is
            // Swap: put left value in right slot and vice versa
            return `${li}${lKey}${lEq}${rVal}${lComma}${nl}${ri}${rKey}${rEq}${lVal}${rComma}`;
        }
    );
}

const LuaOptimizer = {
    selectedFile: null,
    optimizedContent: null,
    optimizedSets: null,  // Store results for details view
    parsedData: null,     // Store parsed Lua data
    originalContent: null, // Store original Lua file content for template replacement
    selectedWeapons: {    // Store selected weapons - separate melee and magic (legacy static inputs)
        melee: { main: null, sub: null },
        magic: { main: null, sub: null },
        ranged: null,
        ammo: null
    },
    weaponSelections: {}, // Dynamic weapon selections from the parsed weapon section
                          // Shape: { typeKey: { main, sub, range, ammo } }
    weaponCache: {},      // Cache for weapon search results
    
    init() {
        this.setupDropzone();
        this.setupButtons();
        this.setupSimulationToggle();
        this.setupWeaponSearch();
        this.updateRequirements();
    },
    
    setupSimulationToggle() {
        const checkbox = document.getElementById('lua-use-simulation');
        const simOptions = document.getElementById('lua-sim-options');
        
        if (checkbox && simOptions) {
            // Initial state
            simOptions.style.opacity = checkbox.checked ? '1' : '0.5';
            simOptions.style.pointerEvents = checkbox.checked ? 'auto' : 'none';
            
            checkbox.addEventListener('change', () => {
                simOptions.style.opacity = checkbox.checked ? '1' : '0.5';
                simOptions.style.pointerEvents = checkbox.checked ? 'auto' : 'none';
            });
        }
    },
    
    setupWeaponSearch() {
        // Setup searchable dropdowns for each weapon slot
        // Format: [inputId, slotFilter, weaponCategory, subSlot]
        const slots = [
            ['melee-main', 'main', 'melee', 'main'],
            ['melee-sub', 'sub', 'melee', 'sub'],
            ['magic-main', 'main', 'magic', 'main'],
            ['magic-sub', 'sub', 'magic', 'sub'],
            ['ranged', 'range', 'shared', 'ranged'],
            ['ammo', 'ammo', 'shared', 'ammo'],
        ];
        
        slots.forEach(([slotId, slotFilter, category, subSlot]) => {
            const input = document.getElementById(`lua-weapon-${slotId}`);
            const dropdown = document.getElementById(`lua-weapon-${slotId}-dropdown`);
            
            if (!input || !dropdown) return;
            
            let debounceTimer;
            
            input.addEventListener('input', (e) => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    this.searchWeapons(slotId, slotFilter, e.target.value);
                }, 200);
            });
            
            input.addEventListener('focus', () => {
                if (input.value.length >= 2) {
                    this.searchWeapons(slotId, slotFilter, input.value);
                }
            });
            
            // Close dropdown when clicking outside
            document.addEventListener('click', (e) => {
                if (!input.contains(e.target) && !dropdown.contains(e.target)) {
                    dropdown.classList.add('hidden');
                }
            });
            
            // Clear button functionality - clear on empty
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    dropdown.classList.add('hidden');
                }
                if (e.key === 'Backspace' && input.value === '') {
                    this.clearWeaponSelection(slotId, category, subSlot);
                }
            });
        });
    },
    
    async searchWeapons(slotId, slotFilter, query) {
        const dropdown = document.getElementById(`lua-weapon-${slotId}-dropdown`);
        if (!dropdown) return;
        
        if (query.length < 2) {
            dropdown.classList.add('hidden');
            return;
        }
        
        try {
            // Search inventory for weapons
            const response = await fetch(`/api/inventory/search?q=${encodeURIComponent(query)}&slot=${slotFilter}&limit=15`);
            
            if (!response.ok) {
                // Fallback: search all items if slot-specific search fails
                const fallbackResponse = await fetch(`/api/inventory/search?q=${encodeURIComponent(query)}&limit=15`);
                if (!fallbackResponse.ok) {
                    dropdown.classList.add('hidden');
                    return;
                }
                const data = await fallbackResponse.json();
                this.renderWeaponDropdown(slotId, data.items || []);
                return;
            }
            
            const data = await response.json();
            this.renderWeaponDropdown(slotId, data.items || []);
            
        } catch (error) {
            console.error('Weapon search error:', error);
            dropdown.classList.add('hidden');
        }
    },
    
    renderWeaponDropdown(slotId, items) {
        const dropdown = document.getElementById(`lua-weapon-${slotId}-dropdown`);
        if (!dropdown) return;
        
        if (items.length === 0) {
            dropdown.innerHTML = '<div class="dropdown-item text-ffxi-text-dim">No items found</div>';
            dropdown.classList.remove('hidden');
            return;
        }
        
        dropdown.innerHTML = items.map(item => `
            <div class="dropdown-item" onclick="LuaOptimizer.selectWeapon('${slotId}', ${JSON.stringify(item).replace(/"/g, '&quot;')})">
                <div class="font-medium text-sm">${item.name || item.Name}</div>
                <div class="text-xs text-ffxi-text-dim">
                    ${item.skill || item['Skill Type'] || ''} 
                    ${item.damage ? `DMG:${item.damage}` : item.Damage ? `DMG:${item.Damage}` : ''}
                    ${item.delay ? `Delay:${item.delay}` : item.Delay ? `Delay:${item.Delay}` : ''}
                </div>
            </div>
        `).join('');
        
        dropdown.classList.remove('hidden');
    },
    
    selectWeapon(slotId, item) {
        const input = document.getElementById(`lua-weapon-${slotId}`);
        const hiddenInput = document.getElementById(`lua-weapon-${slotId}-id`);
        const dropdown = document.getElementById(`lua-weapon-${slotId}-dropdown`);
        
        if (input) {
            input.value = item.name || item.Name;
            input.classList.add('text-ffxi-accent');
        }
        if (hiddenInput) {
            hiddenInput.value = JSON.stringify(item);
        }
        if (dropdown) {
            dropdown.classList.add('hidden');
        }
        
        // Store in appropriate category
        if (slotId.startsWith('melee-')) {
            const subSlot = slotId.replace('melee-', '');
            this.selectedWeapons.melee[subSlot] = item;
        } else if (slotId.startsWith('magic-')) {
            const subSlot = slotId.replace('magic-', '');
            this.selectedWeapons.magic[subSlot] = item;
        } else if (slotId === 'ranged') {
            this.selectedWeapons.ranged = item;
        } else if (slotId === 'ammo') {
            this.selectedWeapons.ammo = item;
        }
    },
    
    clearWeaponSelection(slotId, category, subSlot) {
        const input = document.getElementById(`lua-weapon-${slotId}`);
        const hiddenInput = document.getElementById(`lua-weapon-${slotId}-id`);
        
        if (input) {
            input.value = '';
            input.classList.remove('text-ffxi-accent');
        }
        if (hiddenInput) {
            hiddenInput.value = '';
        }
        
        // Clear from appropriate category
        if (category === 'melee') {
            this.selectedWeapons.melee[subSlot] = null;
        } else if (category === 'magic') {
            this.selectedWeapons.magic[subSlot] = null;
        } else if (subSlot === 'ranged') {
            this.selectedWeapons.ranged = null;
        } else if (subSlot === 'ammo') {
            this.selectedWeapons.ammo = null;
        }
    },
    
    setupDropzone() {
        const dropzone = document.getElementById('lua-dropzone');
        const fileInput = document.getElementById('lua-file-input');
        
        if (!dropzone || !fileInput) return;
        
        // Click to open file browser
        dropzone.addEventListener('click', () => fileInput.click());
        
        // File selection
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFile(e.target.files[0]);
            }
        });
        
        // Drag and drop
        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('border-ffxi-accent');
        });
        
        dropzone.addEventListener('dragleave', () => {
            dropzone.classList.remove('border-ffxi-accent');
        });
        
        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('border-ffxi-accent');
            
            if (e.dataTransfer.files.length > 0) {
                const file = e.dataTransfer.files[0];
                if (file.name.endsWith('.lua')) {
                    this.handleFile(file);
                } else {
                    showToast('Please drop a .lua file', 'error');
                }
            }
        });
    },
    
    setupButtons() {
        const parseBtn = document.getElementById('btn-lua-parse');
        const optimizeBtn = document.getElementById('btn-lua-optimize');
        const downloadBtn = document.getElementById('btn-lua-download');
        const closeDetailsBtn = document.getElementById('btn-close-set-details');
        
        if (parseBtn) {
            parseBtn.addEventListener('click', () => this.parseLuaFile());
        }
        
        if (optimizeBtn) {
            optimizeBtn.addEventListener('click', () => this.runOptimization());
        }
        
        if (downloadBtn) {
            downloadBtn.addEventListener('click', () => this.downloadResult());
        }
        
        if (closeDetailsBtn) {
            closeDetailsBtn.addEventListener('click', () => this.hideSetDetails());
        }
    },
    
    handleFile(file) {
        this.selectedFile = file;
        this.parsedData = null;
        this.originalContent = null;  // Reset original content
        this.weaponSelections = {};
        this.selectedWeapons = {
            melee: { main: null, sub: null },
            magic: { main: null, sub: null },
            ranged: null,
            ammo: null
        };
        
        // Read and store the original file content for template replacement
        const reader = new FileReader();
        reader.onload = (e) => {
            this.originalContent = e.target.result;
        };
        reader.readAsText(file);
        
        // Update dropzone appearance
        const dropzone = document.getElementById('lua-dropzone');
        dropzone.innerHTML = `
            <svg class="w-12 h-12 mx-auto mb-3 text-ffxi-green" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            <p class="text-ffxi-text mb-1">${file.name}</p>
            <p class="text-ffxi-text-dim text-sm">${(file.size / 1024).toFixed(1)} KB - Click to change</p>
            <input type="file" id="lua-file-input" class="hidden" accept=".lua">
        `;
        
        // Re-setup file input
        const newFileInput = document.getElementById('lua-file-input');
        newFileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFile(e.target.files[0]);
            }
        });
        
        // Hide weapon section until parsed
        this.hideWeaponSection();
        this.updateParseButton();
        this.hideResults();
    },
    
    updateRequirements() {
        const invReq = document.getElementById('lua-req-inventory');
        if (invReq) {
            if (AppState.inventoryLoaded) {
                invReq.classList.remove('bg-ffxi-red');
                invReq.classList.add('bg-ffxi-green');
            } else {
                invReq.classList.remove('bg-ffxi-green');
                invReq.classList.add('bg-ffxi-red');
            }
        }
        this.updateParseButton();
    },
    
    updateParseButton() {
        const btn = document.getElementById('btn-lua-parse');
        if (btn) {
            btn.disabled = !this.selectedFile || !AppState.inventoryLoaded;
        }
    },
    
    hideWeaponSection() {
        const section = document.getElementById('lua-weapon-section');
        if (section) {
            section.classList.add('hidden');
            section.innerHTML = ''; // Clear dynamic content
        }
    },
    
    showWeaponSection() {
        // Deprecated - use showDynamicWeaponSection instead
        const section = document.getElementById('lua-weapon-section');
        if (section) section.classList.remove('hidden');
    },
    
    async parseLuaFile() {
        if (!this.selectedFile || !AppState.inventoryLoaded) {
            return;
        }
        
        this.showStatus('Parsing Lua file...');
        
        try {
            const formData = new FormData();
            formData.append('file', this.selectedFile);
            
            const response = await fetch('/api/lua/parse', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.parsedData = result;
                this.showParsedResults(result);
                // showDynamicWeaponSection is called from showParsedResults
                
                // Build toast message with weapon info
                const weaponCount = result.required_weapon_types?.length || 0;
                let toastMsg = `Found ${result.placeholder_sets} placeholder sets`;
                if (weaponCount > 0) {
                    toastMsg += ` (${weaponCount} weapon type${weaponCount > 1 ? 's' : ''} needed)`;
                }
                showToast(toastMsg, 'success');
            } else {
                this.showError(result.error || 'Failed to parse Lua file');
                showToast('Parse failed', 'error');
            }
            
        } catch (error) {
            this.showError(`Error: ${error.message}`);
            showToast(`Error: ${error.message}`, 'error');
        }
        
        setTimeout(() => this.hideStatus(), 1000);
    },
    
    showParsedResults(result) {
        const countEl = document.getElementById('lua-parsed-count');
        const setsEl = document.getElementById('lua-parsed-sets');
        
        if (countEl) {
            countEl.textContent = result.placeholder_sets || 0;
        }
        
        if (setsEl && result.sets) {
            const placeholders = result.sets.filter(s => s.is_placeholder);
            setsEl.innerHTML = placeholders.map(set => {
                // Use API-provided set_type instead of inferring
                const badge = this.getSetTypeBadgeFromType(set.set_type);
                
                // Show additional info based on type
                let extraInfo = '';
                if (set.ws_name && set.weapon_type) {
                    extraInfo = `<span class="text-xs text-ffxi-text-dim">${set.weapon_type}</span>`;
                } else if (set.representative_spell) {
                    extraInfo = `<span class="text-xs text-purple-400">${set.representative_spell}</span>`;
                }
                
                return `
                    <div class="flex justify-between items-center py-1">
                        <div class="flex flex-col truncate max-w-[60%]">
                            <span class="text-ffxi-text truncate" title="${set.name}">${this.truncateSetName(set.name)}</span>
                            ${extraInfo ? `<span class="text-xs">${extraInfo}</span>` : ''}
                        </div>
                        ${badge}
                    </div>
                `;
            }).join('');
        }
        
        // Update job override if detected
        if (result.job) {
            const jobSelect = document.getElementById('lua-job-override');
            if (jobSelect) {
                jobSelect.value = result.job;
            }
        }
        
        // Store parse result for optimization
        this.parsedData = result;
        
        // Show dynamic weapon section based on required weapons
        this.showDynamicWeaponSection(result.required_weapons, result.required_weapon_types);
    },
    
    showDynamicWeaponSection(requiredWeapons, requiredWeaponTypes) {
        const section = document.getElementById('lua-weapon-section');
        if (!section) return;
        
        let html = `<h4 class="font-semibold text-ffxi-text mb-3">Weapon Configuration</h4>`;
        
        const RANGED_WS_TYPES = ['Archery', 'Marksmanship'];
        
        // ── WS weapon type blocks ──────────────────────────────────────────────
        if (requiredWeaponTypes && requiredWeaponTypes.length > 0) {
            const hasDTSetsForNote = this.parsedData?.sets?.some(s =>
                s.is_placeholder && (s.set_type === 'dt' || s.set_type === 'fc' || s.set_type === 'other')
            );
            const dtNote = hasDTSetsForNote
                ? '<span class="text-xs text-ffxi-text-dim ml-2">(Also used for DT/Idle TP simulation)</span>'
                : '';
            
            html += `
                <div class="mb-4">
                    <div class="text-sm text-ffxi-text-dim mb-2">Weapons for Weaponskills:${dtNote}</div>
                    <div class="grid gap-3">
            `;
            
            for (const weaponType of requiredWeaponTypes) {
                const wsNames  = requiredWeapons[weaponType] || [];
                const wsLabel  = wsNames.join(', ');
                const slotKey  = weaponType.toLowerCase().replace(/ /g, '-');
                const isRanged = RANGED_WS_TYPES.includes(weaponType);
                
                html += `
                    <div class="bg-ffxi-dark p-3 rounded">
                        <div class="flex justify-between items-center mb-2">
                            <span class="text-ffxi-accent font-medium">${weaponType}</span>
                            <span class="text-xs text-ffxi-text-dim">${wsLabel}</span>
                        </div>
                        <div class="grid grid-cols-2 gap-2">
                            <div>
                                <label class="text-xs text-ffxi-text-dim block mb-0.5">
                                    Main Hand${isRanged ? ' <span class="text-ffxi-text-dim">(optional)</span>' : ''}
                                </label>
                                <div id="lua-ws-${slotKey}-main-container"></div>
                            </div>
                            <div>
                                <label class="text-xs text-ffxi-text-dim block mb-0.5">Sub / Grip</label>
                                <div id="lua-ws-${slotKey}-sub-container"></div>
                            </div>
                            <div>
                                <label class="text-xs text-ffxi-text-dim block mb-0.5">
                                    Range${isRanged
                                        ? ' <span class="text-ffxi-red text-xs">*required</span>'
                                        : ' <span class="text-ffxi-text-dim">(optional)</span>'}
                                </label>
                                <div id="lua-ws-${slotKey}-range-container"></div>
                            </div>
                            <div>
                                <label class="text-xs text-ffxi-text-dim block mb-0.5">
                                    Ammo${isRanged
                                        ? ' <span class="text-ffxi-red text-xs">*required</span>'
                                        : ' <span class="text-ffxi-text-dim">(optional)</span>'}
                                </label>
                                <div id="lua-ws-${slotKey}-ammo-container"></div>
                            </div>
                        </div>
                        <div class="text-xs text-ffxi-text-dim mt-1.5">
                            ${isRanged
                                ? '* Range and Ammo are required for ranged weaponskills'
                                : 'Range/Ammo lock those slots if provided; leave empty to let optimizer fill them freely'}
                        </div>
                    </div>
                `;
            }
            
            html += `</div></div>`;
        }
        
        // ── Magic weapons ──────────────────────────────────────────────────────
        const hasMagicSets = this.parsedData?.sets?.some(s =>
            s.is_placeholder && ['magic_damage', 'magic_burst', 'magic_accuracy'].includes(s.set_type)
        );
        if (hasMagicSets) {
            html += `
                <div class="mb-4">
                    <div class="text-sm text-ffxi-text-dim mb-2">Weapons for Magic Sets:</div>
                    <div class="bg-ffxi-dark p-3 rounded">
                        <div class="grid grid-cols-2 gap-2">
                            <div>
                                <label class="text-xs text-ffxi-text-dim block mb-0.5">Main Hand (Staff/Club)</label>
                                <div id="lua-ws-magic-main-container"></div>
                            </div>
                            <div>
                                <label class="text-xs text-ffxi-text-dim block mb-0.5">Sub (Grip/Shield)</label>
                                <div id="lua-ws-magic-sub-container"></div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }
        
        // ── DT-alongside-WS weapons ────────────────────────────────────────────
        const hasWSWeapons = requiredWeaponTypes && requiredWeaponTypes.length > 0;
        const hasTPSets    = this.parsedData?.sets?.some(s => s.is_placeholder && s.set_type === 'tp');
        const hasDTSets    = this.parsedData?.sets?.some(s =>
            s.is_placeholder && (s.set_type === 'dt' || s.set_type === 'fc' || s.set_type === 'other')
        );
        
        if (hasDTSets && hasWSWeapons) {
            html += `
                <div class="mb-4">
                    <div class="text-sm text-ffxi-text-dim mb-1">Weapons for DT/Idle Sets (TP Simulation):</div>
                    <div class="text-xs text-ffxi-text-dim mb-2">(Leave empty to use WS weapons above)</div>
                    <div class="bg-ffxi-dark p-3 rounded">
                        <div class="grid grid-cols-2 gap-2">
                            <div>
                                <label class="text-xs text-ffxi-text-dim block mb-0.5">Main Hand (optional)</label>
                                <div id="lua-ws-dt-main-container"></div>
                            </div>
                            <div>
                                <label class="text-xs text-ffxi-text-dim block mb-0.5">Sub Hand (optional)</label>
                                <div id="lua-ws-dt-sub-container"></div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }
        
        // ── Melee fallback (no WS weapons shown) ──────────────────────────────
        const hasAnyPlaceholders = this.parsedData?.sets?.some(s => s.is_placeholder);
        const needsMeleeWeapons  = ((hasTPSets || hasDTSets) && !hasWSWeapons) ||
                                   (hasAnyPlaceholders && !hasWSWeapons && !hasMagicSets);
        if (needsMeleeWeapons) {
            let setTypeLabels = [];
            if (hasTPSets) setTypeLabels.push('TP');
            if (hasDTSets) setTypeLabels.push('DT/Idle');
            if (setTypeLabels.length === 0) setTypeLabels.push('TP/DT');
            
            html += `
                <div class="mb-4">
                    <div class="text-sm text-ffxi-text-dim mb-1">Weapons for ${setTypeLabels.join(' & ')} Sets:</div>
                    <div class="text-xs text-ffxi-text-dim mb-2">(Optional - used for TP simulation)</div>
                    <div class="bg-ffxi-dark p-3 rounded">
                        <div class="grid grid-cols-2 gap-2">
                            <div>
                                <label class="text-xs text-ffxi-text-dim block mb-0.5">Main Hand</label>
                                <div id="lua-ws-melee-main-container"></div>
                            </div>
                            <div>
                                <label class="text-xs text-ffxi-text-dim block mb-0.5">Sub Hand</label>
                                <div id="lua-ws-melee-sub-container"></div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }
        
        // ── Optimize button ────────────────────────────────────────────────────
        html += `
            <button id="btn-lua-optimize" class="btn-primary w-full mt-4">
                <svg class="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
                </svg>
                Optimize All Placeholder Sets
            </button>
        `;
        
        section.innerHTML = html;
        section.classList.remove('hidden');
        
        const optimizeBtn = document.getElementById('btn-lua-optimize');
        if (optimizeBtn) {
            optimizeBtn.addEventListener('click', () => this.runOptimization());
        }
        
        // Populate all container divs with job-filtered, show-on-focus dropdowns
        const job = document.getElementById('lua-job-override')?.value || this.parsedData?.job || '';
        if (job) {
            this.populateLuaWeaponDropdowns(job, requiredWeaponTypes || [], requiredWeapons || {});
        }
    },
    
    async populateLuaWeaponDropdowns(job, requiredWeaponTypes, requiredWeapons) {
        // Fetch all four data sets in parallel for this job
        let weapons = [], offhand = [], rangedWeapons = [], ammoItems = [];
        try {
            const [wRes, oRes, rRes, aRes] = await Promise.all([
                fetch(`/api/weapons/${job}`).then(r => r.json()),
                fetch(`/api/offhand/${job}`).then(r => r.json()),
                fetch(`/api/ranged-weapons/${job}`).then(r => r.json()),
                fetch(`/api/inventory?slot=ammo&job=${job}`).then(r => r.json()),
            ]);
            weapons      = wRes.weapons      || [];
            offhand      = oRes.offhand       || [];
            rangedWeapons = rRes.ranged_weapons || [];
            // /api/inventory items don't carry _raw — construct it like loadAmmoItems does
            ammoItems = (aRes.items || []).map(item => ({
                ...item,
                _raw: {
                    Name: item.name,
                    Name2: item.name2,
                    Type: item.type,
                    'Item Level': item.item_level,
                    Jobs: item.jobs,
                    ...(item.stats || {}),
                },
            }));
        } catch (e) {
            console.error('Failed to load weapons for Lua weapon section:', e);
            return;
        }
        
        // Option-list builders
        const weaponOpts = (items) => items.map(w => ({
            value: w.name,
            label: w.name2 || w.name,
            sublabel: [
                w.skill_type,
                w.damage  ? `D${w.damage}`     : '',
                w.delay   ? `Dly${w.delay}`    : '',
                w.item_level ? `iLv${w.item_level}` : '',
            ].filter(Boolean).join(' '),
            data: w,
        }));
        const ammoOpts = (items) => items.map(item => ({
            value: item.name,
            label: item.name2 || item.name,
            sublabel: item.item_level ? `iLv${item.item_level}` : '',
            data: item,
        }));
        
        const RANGED_WS_TYPES = ['Archery', 'Marksmanship'];
        
        // ── WS weapon type blocks ────────────────────────────────────────────
        for (const weaponType of requiredWeaponTypes) {
            const slotKey  = weaponType.toLowerCase().replace(/ /g, '-');
            const isRanged = RANGED_WS_TYPES.includes(weaponType);
            
            // Main: filter to the specific weapon type for melee; all weapons for ranged WS
            const mainItems = isRanged
                ? weapons
                : weapons.filter(w => w.skill_type === weaponType);
            
            // Range: filter by skill type for ranged WS; all ranged weapons for melee
            const rangeItems = isRanged
                ? rangedWeapons.filter(w => w.skill_type === weaponType)
                : rangedWeapons;
            
            this._createLuaSlotDropdown(`lua-ws-${slotKey}-main-container`,  weaponOpts(mainItems),   'main',  weaponType, isRanged ? 'Main Hand (optional)' : 'Main Hand');
            this._createLuaSlotDropdown(`lua-ws-${slotKey}-sub-container`,   weaponOpts(offhand),     'sub',   weaponType, 'Sub / Grip');
            this._createLuaSlotDropdown(`lua-ws-${slotKey}-range-container`, weaponOpts(rangeItems),  'range', weaponType, isRanged ? 'Range (required)' : 'Range (optional)');
            this._createLuaSlotDropdown(`lua-ws-${slotKey}-ammo-container`,  ammoOpts(ammoItems),     'ammo',  weaponType, isRanged ? 'Ammo (required)' : 'Ammo (optional)');
        }
        
        // ── Magic weapons ────────────────────────────────────────────────────
        if (document.getElementById('lua-ws-magic-main-container')) {
            this._createLuaSlotDropdown('lua-ws-magic-main-container', weaponOpts(weapons), 'main', 'magic', 'Main Hand (Staff/Club)');
            this._createLuaSlotDropdown('lua-ws-magic-sub-container',  weaponOpts(offhand), 'sub',  'magic', 'Sub (Grip/Shield)');
        }
        
        // ── DT weapons ───────────────────────────────────────────────────────
        if (document.getElementById('lua-ws-dt-main-container')) {
            this._createLuaSlotDropdown('lua-ws-dt-main-container', weaponOpts(weapons), 'main', 'dt', 'Main Hand (optional)');
            this._createLuaSlotDropdown('lua-ws-dt-sub-container',  weaponOpts(offhand), 'sub',  'dt', 'Sub Hand (optional)');
        }
        
        // ── Melee fallback weapons ───────────────────────────────────────────
        if (document.getElementById('lua-ws-melee-main-container')) {
            this._createLuaSlotDropdown('lua-ws-melee-main-container', weaponOpts(weapons), 'main', 'melee', 'Main Hand');
            this._createLuaSlotDropdown('lua-ws-melee-sub-container',  weaponOpts(offhand), 'sub',  'melee', 'Sub Hand');
        }
    },
    
    _createLuaSlotDropdown(containerId, options, slot, weaponType, placeholder) {
        const typeKey = weaponType.toLowerCase().replace(/ /g, '-');
        
        // Ensure the selections map has an entry for this weapon type
        if (!this.weaponSelections[typeKey]) {
            this.weaponSelections[typeKey] = { main: null, sub: null, range: null, ammo: null };
        }
        
        createSearchableDropdown(containerId, options, (opt) => {
            if (!this.weaponSelections[typeKey]) {
                this.weaponSelections[typeKey] = { main: null, sub: null, range: null, ammo: null };
            }
            this.weaponSelections[typeKey][slot] = opt ? opt.data : null;
        }, placeholder);
    },
    
    getSetTypeBadgeFromType(setType) {
        const badges = {
            'ws': '<span class="text-xs bg-ffxi-red/30 text-ffxi-red px-1.5 py-0.5 rounded">WS</span>',
            'tp': '<span class="text-xs bg-ffxi-blue/30 text-ffxi-blue px-1.5 py-0.5 rounded">TP</span>',
            'magic_damage': '<span class="text-xs bg-purple-500/30 text-purple-400 px-1.5 py-0.5 rounded">Magic</span>',
            'magic_burst': '<span class="text-xs bg-purple-500/30 text-purple-400 px-1.5 py-0.5 rounded">MB</span>',
            'magic_accuracy': '<span class="text-xs bg-cyan-500/30 text-cyan-400 px-1.5 py-0.5 rounded">M.Acc</span>',
            'enhancing': '<span class="text-xs bg-emerald-500/30 text-emerald-400 px-1.5 py-0.5 rounded">Enh</span>',
            'healing': '<span class="text-xs bg-pink-500/30 text-pink-400 px-1.5 py-0.5 rounded">Cure</span>',
            'dt': '<span class="text-xs bg-ffxi-green/30 text-ffxi-green px-1.5 py-0.5 rounded">DT</span>',
            'fc': '<span class="text-xs bg-yellow-500/30 text-yellow-400 px-1.5 py-0.5 rounded">FC</span>',
            'other': '<span class="text-xs bg-ffxi-border text-ffxi-text-dim px-1.5 py-0.5 rounded">Other</span>',
        };
        return badges[setType] || badges['other'];
    },
    
    inferSetType(setName) {
        // Keep for backwards compatibility
        const name = setName.toLowerCase();
        if (name.includes('ws[') || name.includes('precast.ws')) return 'ws';
        if (name.includes('engaged')) return 'tp';
        if (name.includes('midcast') && (name.includes('nuke') || name.includes('elemental'))) return 'magic';
        if (name.includes('.mb') || name.includes('burst')) return 'mb';
        if (name.includes('idle') || name.includes('dt')) return 'dt';
        if (name.includes('fc') || (name.includes('precast') && !name.includes('ws'))) return 'fc';
        return 'other';
    },
    
    async runOptimization() {
        if (!this.selectedFile || !AppState.inventoryLoaded || !this.parsedData) {
            showToast('Please parse a Lua file first', 'error');
            return;
        }
        
        // Show status
        this.showStatus('Starting optimization...');
        this.hideResults();
        
        try {
            // Build abbreviated empyrean earring prefixes from inventory so
            // isEmpyreanEarring() can recognise short names like "Chas. Earring"
            await buildEmpyreanEarringAbbrevs();
            
            const jobOverride = document.getElementById('lua-job-override')?.value;
            const beamWidth = parseInt(document.getElementById('lua-beam-width')?.value || '50');
            const masterLevel = parseInt(document.getElementById('lua-master-level')?.value || '50');
            const subJob = document.getElementById('lua-sub-job')?.value || 'war';
            
            // Get placeholder sets to optimize
            const placeholders = this.parsedData.sets.filter(s => s.is_placeholder);
            const totalSets = placeholders.length;
            
            // Collect selected weapons by type
            const weaponsByType = this.collectSelectedWeapons();
            
            // Results tracking
            const optimizedSets = [];
            const errors = [];
            let completed = 0;
            
            // Process each placeholder set
            for (const set of placeholders) {
                completed++;
                this.updateStatus(`Optimizing ${completed}/${totalSets}: ${this.truncateSetName(set.name)}`, (completed / totalSets) * 100);
                
                try {
                    const result = await this.optimizeSet(set, {
                        job: jobOverride || this.parsedData.job,
                        beamWidth,
                        masterLevel,
                        subJob,
                        weaponsByType,
                    });
                    
                    if (result) {
                        optimizedSets.push(result);
                    } else {
                        errors.push(`No result for ${set.name}`);
                    }
                } catch (err) {
                    errors.push(`Error optimizing ${set.name}: ${err.message}`);
                }
            }
            
            // Generate Lua output
            this.optimizedSets = optimizedSets;
            this.generateLuaContent(optimizedSets);
            
            // Show results
            this.showResults({
                success: true,
                job: jobOverride || this.parsedData.job,
                sets_optimized: optimizedSets.length,
                sets_skipped: errors.length,
                optimized_sets: optimizedSets,
                errors: errors,
            });
            
            this.updateStatus('Complete!', 100);
            showToast(`Optimized ${optimizedSets.length} sets!`, 'success');
            
        } catch (error) {
            this.showError(`Error: ${error.message}`);
            showToast(`Error: ${error.message}`, 'error');
        }
        
        setTimeout(() => this.hideStatus(), 1500);
    },
    
    collectSelectedWeapons() {
        // weaponSelections is populated directly by _createLuaSlotDropdown callbacks
        // Shape: { typeKey: { main, sub, range, ammo } }
        return this.weaponSelections;
    },
    
    async optimizeSet(set, options) {
        const { job, beamWidth, masterLevel, subJob, weaponsByType } = options;
        
        // Determine which endpoint to call based on set_type
        switch (set.set_type) {
            case 'ws':
                // Check if we have a specific weaponskill name
                if (set.ws_name) {
                    return this.optimizeWSSet(set, options);
                }
                // No specific WS name - use generic WS optimizer (beam search for WS damage stats)
                return this.optimizeGenericWSSet(set, options);
            case 'tp':
                return this.optimizeTPSet(set, options);
            case 'magic_damage':
            case 'magic_burst':
                return this.optimizeMagicSet(set, options);
            case 'magic_accuracy':
                // Only use magic sim if we have a real spell, otherwise use DT optimizer
                if (set.representative_spell) {
                    return this.optimizeMagicSet(set, options);
                }
                return this.optimizeDTSet(set, options);
            case 'enhancing':
            case 'enhancing_skill':
                // Enhancing magic - maximize Enhancing Magic Skill
                return this.optimizeEnhancingSkillSet(set, options);
            case 'enhancing_duration':
            case 'ja_composure':
                // Enhancing Duration sets (Composure, etc.)
                return this.optimizeEnhancingDurationSet(set, options);
            case 'ja_saboteur':
                // Saboteur - maximize enfeebling potency (use magic accuracy for now)
                return this.optimizeDTSet(set, options);  // TODO: Create saboteur-specific profile
            case 'ja_generic':
                // Generic JA sets - use DT for survivability
                return this.optimizeDTSet(set, options);
            case 'healing':
                // Healing magic - use cure potency profile
                return this.optimizeHealingSet(set, options);
            case 'sird':
                // SIRD overlay - Spell Interruption Rate Down (set_combine with base midcast set)
                return this.optimizeSIRDSet(set, options);
            case 'fc':
                // Fast Cast precast sets - use FC optimizer
                return this.optimizeFCSet(set, options);
            case 'dt':
                return this.optimizeDTSet(set, options);
            default:
                // For 'other' sets, use DT optimizer with generic profile
                return this.optimizeDTSet(set, options);
        }
    },
    
    // Default buffs for Lua template optimization
    DEFAULT_BUFFS: {
        brd: ['Victory March'],
        cor: [],
        geo: [],
        whm: ['Haste II'],
    },
    DEFAULT_DEBUFFS: ['Dia III', 'Distract III'],
    DEFAULT_FOOD: 'Grape Daifuku',
    DEFAULT_TARGET: 'apex_toad',
    
    async optimizeWSSet(set, options) {
        const { job, beamWidth, masterLevel, subJob, weaponsByType } = options;
        
        // Get weapons for this WS's weapon type
        const weaponType = set.weapon_type?.toLowerCase().replace(/ /g, '-') || 'melee';
        const weapons = weaponsByType[weaponType] || weaponsByType['melee'] || {};
        
        // Ranged WS (Archery / Marksmanship): requires range+ammo, main/sub are ignored
        if (set.is_ranged_ws) {
            if (!weapons.range) {
                console.log(`Skipping ranged WS set ${set.name}: no ranged weapon selected for type ${set.weapon_type}`);
                return null;
            }
            if (!weapons.ammo) {
                console.log(`Skipping ranged WS set ${set.name}: no ammo selected for type ${set.weapon_type}`);
                return null;
            }
            
            const rangedWeapon = weapons.range._raw || weapons.range;
            const ammo = weapons.ammo._raw || weapons.ammo;
            // Use real melee weapons if available — they contribute stats even during ranged WS
            // (e.g. COR with sword equipped while firing a gun WS)
            // Fall back to a safe empty weapon dict that includes Skill Type
            const emptyWeapon = { Name: 'Empty', Name2: 'Empty', Type: 'None', 'Skill Type': 'None' };
            let meleeMain = emptyWeapon;
            let meleeSub = emptyWeapon;
            // Check for melee weapons in weaponsByType
            if (weaponsByType['melee']?.main) {
                meleeMain = weaponsByType['melee'].main._raw || weaponsByType['melee'].main;
                meleeSub = weaponsByType['melee'].sub?._raw || weaponsByType['melee'].sub || emptyWeapon;
            } else {
                // Fall back to any weapon type that has a main weapon
                for (const [typeName, typeWeapons] of Object.entries(weaponsByType)) {
                    if (typeName !== weaponType && typeWeapons?.main) {
                        meleeMain = typeWeapons.main._raw || typeWeapons.main;
                        meleeSub = typeWeapons.sub?._raw || typeWeapons.sub || emptyWeapon;
                        break;
                    }
                }
            }
            
            const response = await fetch('/api/optimize/ws', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    job: job,
                    sub_job: subJob || 'war',
                    weaponskill: set.ws_name,
                    main_weapon: meleeMain,
                    sub_weapon: meleeSub,
                    ranged_weapon: rangedWeapon,
                    ammo: ammo,
                    target: this.DEFAULT_TARGET,
                    use_simulation: true,
                    beam_width: beamWidth,
                    master_level: masterLevel,
                    min_tp: 2000,
                    buffs: this.DEFAULT_BUFFS,
                    abilities: [],
                    food: this.DEFAULT_FOOD,
                    debuffs: this.DEFAULT_DEBUFFS,
                }),
            });
            
            const result = await response.json();
            
            if (result.success && result.results?.length > 0) {
                const best = result.results[0];
                return {
                    name: set.name,
                    profile_type: set.inferred_profile_type,
                    items: this.extractGearItems(best.gear),
                    score: best.beam_score || best.score || 0,
                    is_ranged_ws: true,
                    optimization_type: 'ws_simulation',
                    simulation_value: best.damage,
                    simulation_details: {
                        damage: best.damage,
                        ws_name: set.ws_name,
                        hit_rate: best.hit_rate,
                    },
                };
            }
            
            if (!result.success) {
                console.error(`Ranged WS optimization failed for ${set.name}:`, result.error);
            }
            return null;
        }
        
        // Melee WS: main weapon is required
        if (!weapons.main) {
            console.log(`Skipping WS set ${set.name}: no weapon selected for type ${weaponType}`);
            return null;
        }
        
        const mainWeapon = weapons.main._raw || weapons.main;
        const subWeapon = weapons.sub?._raw || weapons.sub || { Name: 'Empty', Name2: 'Empty', Type: 'None' };
        
        // Ranged/ammo locking logic for melee WS:
        // - Neither provided  → null/null  (optimizer fills ammo freely)
        // - One or both provided → lock both (pass whatever was given, or null for the missing one)
        const hasRange = !!weapons.range;
        const hasAmmo = !!weapons.ammo;
        let rangedWeapon = null;
        let lockedAmmo = null;
        if (hasRange || hasAmmo) {
            rangedWeapon = hasRange ? (weapons.range._raw || weapons.range) : null;
            lockedAmmo = hasAmmo ? (weapons.ammo._raw || weapons.ammo) : null;
        }
        
        const response = await fetch('/api/optimize/ws', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                job: job,
                sub_job: subJob || 'war',
                weaponskill: set.ws_name,
                main_weapon: mainWeapon,
                sub_weapon: subWeapon,
                ranged_weapon: rangedWeapon,
                ammo: lockedAmmo,
                target: this.DEFAULT_TARGET,
                use_simulation: true,
                beam_width: beamWidth,
                master_level: masterLevel,
                min_tp: 2000,
                buffs: this.DEFAULT_BUFFS,
                abilities: [],
                food: this.DEFAULT_FOOD,
                debuffs: this.DEFAULT_DEBUFFS,
            }),
        });
        
        const result = await response.json();
        
        if (result.success && result.results?.length > 0) {
            const best = result.results[0];
            return {
                name: set.name,
                profile_type: set.inferred_profile_type,
                items: this.extractGearItems(best.gear),
                score: best.beam_score || best.score || 0,
                is_ranged_ws: false,
                optimization_type: 'ws_simulation',
                simulation_value: best.damage,
                simulation_details: { 
                    damage: best.damage, 
                    ws_name: set.ws_name,
                    hit_rate: best.hit_rate,
                },
            };
        }
        
        // Log the error if optimization failed
        if (!result.success) {
            console.error(`WS optimization failed for ${set.name}:`, result.error);
        }
        return null;
    },
    
    async optimizeGenericWSSet(set, options) {
        const { job, beamWidth } = options;
        
        // Generic WS set - no specific weaponskill, just maximize WS damage stats
        // Uses DT endpoint with generic_ws profile type
        console.log(`Optimizing generic WS set ${set.name} with beam search for WS damage stats`);
        
        const response = await fetch('/api/optimize/dt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                job: job,
                dt_type: 'generic_ws',  // Uses the new GENERIC_WS profile
                beam_width: beamWidth,
                include_weapons: false,  // Weapons usually locked for WS sets
            }),
        });
        
        const result = await response.json();
        
        if (result.success && result.results?.length > 0) {
            const best = result.results[0];
            return {
                name: set.name,
                profile_type: set.inferred_profile_type,
                items: this.extractGearItems(best.gear),
                score: best.score || 0,
                optimization_type: 'beam_only',
                simulation_value: best.score,
                simulation_details: {
                    note: 'Generic WS set - maximized WS Damage % and Physical Damage Limit+',
                    profile: 'generic_ws',
                },
            };
        }
        
        // Log the error if optimization failed
        if (!result.success) {
            console.error(`Generic WS optimization failed for ${set.name}:`, result.error);
        }
        return null;
    },
    
    async optimizeTPSet(set, options) {
        const { job, beamWidth, masterLevel, subJob, weaponsByType } = options;
        
        // Find first available weapon set for TP
        // Priority: 'melee' key, then any weapon type that has a main weapon
        let weapons = null;
        
        if (weaponsByType['melee']?.main) {
            weapons = weaponsByType['melee'];
        } else {
            // Find first weapon type that has a main weapon selected
            for (const [typeName, typeWeapons] of Object.entries(weaponsByType)) {
                if (typeWeapons?.main) {
                    weapons = typeWeapons;
                    console.log(`TP set using weapons from type: ${typeName}`);
                    break;
                }
            }
        }
        
        // Skip if no main weapon is selected anywhere
        if (!weapons?.main) {
            console.log(`Skipping TP set ${set.name}: no weapon selected in any category`);
            console.log('Available weapon types:', Object.keys(weaponsByType));
            return null;
        }
        
        // Use _raw if available (pure wsdist dict), otherwise use the item directly
        const mainWeapon = weapons.main._raw || weapons.main;
        const subWeapon = weapons.sub?._raw || weapons.sub || { Name: 'Empty', Name2: 'Empty', Type: 'None' };
        
        // Infer TP type from set name
        const nameLower = set.name.toLowerCase();
        let tpType = 'hybrid_tp';  // Default to hybrid (balanced)
        
        if (nameLower.includes('acc') || nameLower.includes('highacc') || nameLower.includes('midacc')) {
            tpType = 'acc_tp';
        } else if (nameLower.includes('dt') || nameLower.includes('defense') || nameLower.includes('tank')) {
            tpType = 'dt_tp';
        } else if (nameLower.includes('refresh') || nameLower.includes('mage')) {
            tpType = 'refresh_tp';
        } else if (nameLower.includes('pure') || nameLower.includes('speed') || nameLower.includes('haste')) {
            tpType = 'pure_tp';
        }
        // Default to hybrid_tp for engaged sets without modifiers
        
        console.log(`TP set ${set.name}: using mode ${tpType}`);
        
        const response = await fetch('/api/optimize/tp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                job: job,
                sub_job: subJob || 'war',
                tp_type: tpType,
                main_weapon: mainWeapon,
                sub_weapon: subWeapon,
                target: this.DEFAULT_TARGET,
                use_simulation: true,
                beam_width: beamWidth,
                master_level: masterLevel,
                buffs: this.DEFAULT_BUFFS,
                abilities: [],
                food: this.DEFAULT_FOOD,
                debuffs: this.DEFAULT_DEBUFFS,
            }),
        });
        
        const result = await response.json();
        
        if (result.success && result.results?.length > 0) {
            const best = result.results[0];
            return {
                name: set.name,
                profile_type: set.inferred_profile_type,
                items: this.extractGearItems(best.gear),
                score: best.beam_score || best.score || 0,
                optimization_type: 'tp_simulation',
                simulation_value: best.time_to_ws,
                simulation_details: { 
                    time_to_ws: best.time_to_ws,
                    tp_per_round: best.tp_per_round,
                    dps: best.dps,
                    tp_mode: tpType,
                },
            };
        }
        
        // Log the error if optimization failed
        if (!result.success) {
            console.error(`TP optimization failed for ${set.name}:`, result.error);
        }
        return null;
    },
    
    async optimizeMagicSet(set, options) {
        const { job, beamWidth, masterLevel, weaponsByType } = options;
        
        // Use magic weapons
        const weapons = weaponsByType['magic'] || {};
        
        // Use the backend-provided optimization_type directly — it accounts for
        // spell category AND path suffix (.Resistant, .MaxDuration, .MB, etc.).
        // Do NOT re-derive this from set_type + spell_type; that logic was the
        // source of the api/frontend disagreement (e.g. .Resistant enfeeble sets
        // always getting 'potency' instead of 'accuracy').
        const optType = set.optimization_type || 'damage';
        
        const response = await fetch('/api/optimize/magic', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                job: job,
                spell_name: set.representative_spell || 'Thunder VI',
                optimization_type: optType,
                magic_burst: set.set_type === 'magic_burst',
                skillchain_steps: set.set_type === 'magic_burst' ? 2 : 0,
                target: 'apex_mob',
                main_weapon: weapons.main || null,
                sub_weapon: weapons.sub || null,
                include_weapons: !weapons.main,
                beam_width: beamWidth,
                buffs: {},
                debuffs: [],
            }),
        });
        
        const result = await response.json();
        
        if (result.success && result.results?.length > 0) {
            const best = result.results[0];
            return {
                name: set.name,
                profile_type: set.inferred_profile_type,
                items: this.extractGearItems(best.gear),
                score: best.beam_score || 0,
                optimization_type: set.set_type,
                simulation_value: best.damage || best.potency_score,
                simulation_details: { 
                    damage: best.damage, 
                    spell_name: set.representative_spell,
                    magic_burst: set.set_type === 'magic_burst',
                    optimization_mode: optType,
                },
            };
        }
        return null;
    },
    
    async optimizeSIRDSet(set, options) {
        const { job, beamWidth } = options;
        
        const response = await fetch('/api/optimize/dt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                job: job,
                dt_type: 'sird',
                beam_width: beamWidth,
                include_weapons: false,
            }),
        });
        
        const result = await response.json();
        
        if (result.success && result.results?.length > 0) {
            const best = result.results[0];
            return {
                name: set.name,
                profile_type: set.inferred_profile_type,
                items: this.extractGearItems(best.gear),
                score: best.score || 0,
                base_set_name: set.base_set_name,
                optimization_type: 'sird',
                simulation_value: best.spell_interruption_rate_down || 0,
                simulation_details: {
                    sird_pct: best.spell_interruption_rate_down || 0,
                    sird_capped: (best.spell_interruption_rate_down || 0) >= 102,
                },
            };
        }
        
        if (!result.success) {
            console.error(`SIRD optimization failed for ${set.name}:`, result.error);
        }
        return null;
    },
    
    async optimizeDTSet(set, options) {
        const { job, beamWidth, masterLevel, subJob, weaponsByType } = options;
        
        // Determine DT type based on set name
        let dtType = 'pure_dt';  // API expects lowercase key
        const nameLower = set.name.toLowerCase();
        if (nameLower.includes('mdt')) dtType = 'mdt_only';
        else if (nameLower.includes('pdt')) dtType = 'pdt_only';
        else if (set.set_type === 'fc') dtType = 'pure_dt'; // FC uses same endpoint
        
        // Find available weapons for TP calculation
        // Priority: dt-specific weapons > melee weapons > any WS weapon type
        let weapons = null;
        let mainWeapon = null;
        let subWeapon = null;
        
        if (weaponsByType) {
            // First check for DT-specific weapons
            if (weaponsByType['dt']?.main) {
                weapons = weaponsByType['dt'];
                console.log('DT set using DT-specific weapons');
            }
            // Then check for melee weapons
            else if (weaponsByType['melee']?.main) {
                weapons = weaponsByType['melee'];
                console.log('DT set using melee weapons');
            } 
            // Finally fall back to any weapon type with a main weapon
            else {
                for (const [typeName, typeWeapons] of Object.entries(weaponsByType)) {
                    if (typeWeapons?.main) {
                        weapons = typeWeapons;
                        console.log(`DT set using weapons from type: ${typeName}`);
                        break;
                    }
                }
            }
            
            if (weapons?.main) {
                mainWeapon = weapons.main._raw || weapons.main;
                subWeapon = weapons.sub?._raw || weapons.sub || { Name: 'Empty', Name2: 'Empty', Type: 'None' };
            }
        }
        
        const response = await fetch('/api/optimize/dt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                job: job,
                dt_type: dtType,
                beam_width: beamWidth,
                // Pass weapons for TP calculation
                main_weapon: mainWeapon,
                sub_weapon: subWeapon,
                // Pass other TP-related parameters
                master_level: masterLevel || 0,
                sub_job: subJob || 'war',
                target: this.DEFAULT_TARGET,
                buffs: this.DEFAULT_BUFFS,
                abilities: [],
                food: this.DEFAULT_FOOD,
                debuffs: this.DEFAULT_DEBUFFS,
            }),
        });
        
        const result = await response.json();
        
        if (result.success && result.results?.length > 0) {
            const best = result.results[0];
            return {
                name: set.name,
                profile_type: set.inferred_profile_type,
                items: this.extractGearItems(best.gear),
                score: best.score || 0,
                optimization_type: set.set_type === 'fc' ? 'fc_capped' : 'dt_capped',
                simulation_value: best.physical_reduction || best.dt_pct || 0,
                simulation_details: {
                    physical_reduction: best.physical_reduction,
                    magical_reduction: best.magical_reduction,
                    time_to_ws: best.time_to_ws,
                    tp_per_round: best.tp_per_round,
                    dt_capped: best.dt_capped,
                },
            };
        }
        return null;
    },
    
    async optimizeEnhancingSkillSet(set, options) {
        const { job, beamWidth } = options;
        
        // Use backend-provided spell and optimization_type.
        // Backend always provides representative_spell for enhancing sets now;
        // fall back to 'Phalanx' only as a last-resort safety net.
        const representativeSpell = set.representative_spell || 'Phalanx';
        const optType = set.optimization_type || 'potency';
        
        const response = await fetch('/api/optimize/magic', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                job: job,
                spell_name: representativeSpell,
                optimization_type: optType,
                magic_burst: false,
                include_weapons: false,
                beam_width: beamWidth,
                target: 'apex_mob',
                buffs: {},
                debuffs: [],
            }),
        });
        
        const result = await response.json();
        
        if (result.success && result.results?.length > 0) {
            const best = result.results[0];
            return {
                name: set.name,
                profile_type: set.inferred_profile_type,
                items: this.extractGearItems(best.gear),
                score: best.score || 0,
                optimization_type: 'enhancing_skill',
                simulation_value: best.potency_score || best.score || 0,
                simulation_details: {
                    note: 'Maximized Enhancing Magic Skill',
                    spell: representativeSpell,
                    optimization_mode: optType,
                },
            };
        }
        return null;
    },
    
    async optimizeEnhancingDurationSet(set, options) {
        const { job, beamWidth } = options;
        
        // Use backend-provided spell and optimization_type.
        // Backend provides the correct duration-focused spell (e.g. Haste for duration sets).
        const representativeSpell = set.representative_spell || 'Haste';
        const optType = set.optimization_type || 'potency';
        
        const response = await fetch('/api/optimize/magic', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                job: job,
                spell_name: representativeSpell,
                optimization_type: optType,
                magic_burst: false,
                include_weapons: false,
                beam_width: beamWidth,
                target: 'apex_mob',
                buffs: {},
                debuffs: [],
            }),
        });
        
        const result = await response.json();
        
        if (result.success && result.results?.length > 0) {
            const best = result.results[0];
            return {
                name: set.name,
                profile_type: set.inferred_profile_type,
                items: this.extractGearItems(best.gear),
                score: best.score || 0,
                optimization_type: 'enhancing_duration',
                simulation_value: best.potency_score || best.score || 0,
                simulation_details: {
                    note: 'Maximized Enhancing Duration %',
                    spell: representativeSpell,
                    optimization_mode: optType,
                },
            };
        }
        return null;
    },

    async optimizeHealingSet(set, options) {
        const { job, beamWidth } = options;
        
        // Use backend-provided spell and optimization_type.
        // Healing sets always use potency, but we let the backend be authoritative.
        const representativeSpell = set.representative_spell || 'Cure IV';
        const optType = set.optimization_type || 'potency';
        
        const response = await fetch('/api/optimize/magic', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                job: job,
                spell_name: representativeSpell,
                optimization_type: optType,
                magic_burst: false,
                include_weapons: false,
                beam_width: beamWidth,
                target: 'apex_mob',
                buffs: {},
                debuffs: [],
            }),
        });
        
        const result = await response.json();
        
        if (result.success && result.results?.length > 0) {
            const best = result.results[0];
            return {
                name: set.name,
                profile_type: set.inferred_profile_type,
                items: this.extractGearItems(best.gear),
                score: best.score || 0,
                optimization_type: 'healing',
                simulation_value: best.potency_score || best.score || 0,
                simulation_details: {
                    note: 'Maximized Cure Potency and MND',
                    spell: representativeSpell,
                    optimization_mode: optType,
                },
            };
        }
        return null;
    },
    
    async optimizeFCSet(set, options) {
        const { job, beamWidth } = options;
        
        // Fast Cast precast sets - maximize Fast Cast (caps at 80%)
        const response = await fetch('/api/optimize/dt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                job: job,
                dt_type: 'fast_cast',  // Use Fast Cast profile
                beam_width: beamWidth,
            }),
        });
        
        const result = await response.json();
        
        if (result.success && result.results?.length > 0) {
            const best = result.results[0];
            const fcValue = best.fast_cast || 0;
            const fcCapped = best.fast_cast_capped || fcValue >= 80;
            
            return {
                name: set.name,
                profile_type: set.inferred_profile_type,
                items: this.extractGearItems(best.gear),
                score: best.score || 0,
                optimization_type: 'fast_cast',
                simulation_value: fcValue,  // Show FC % as the main value
                simulation_details: {
                    fast_cast: fcValue,
                    fast_cast_capped: fcCapped,
                    note: fcCapped ? 'Fast Cast capped at 80%' : `Fast Cast: ${fcValue}%`,
                },
            };
        }
        return null;
    },
    
    extractGearItems(gear) {
        // Returns full item objects (not just names) to preserve augment data
        const items = {};
        const slots = ['main', 'sub', 'range', 'ammo', 'head', 'neck', 'ear1', 'ear2',
                       'body', 'hands', 'ring1', 'ring2', 'back', 'waist', 'legs', 'feet'];
        
        // The API returns the ranged slot as 'ranged' (wsdist convention),
        // but GearSwap Lua uses 'range'. Map API keys to Lua slot names.
        const apiKeyMap = { 'range': 'ranged' };
        
        for (const slot of slots) {
            // Check the slot name itself, then the API alias if one exists
            const apiKey = apiKeyMap[slot];
            const item = gear && (gear[slot] || (apiKey && gear[apiKey]));
            if (item) {
                const name = item.name || item.Name || 'Empty';
                if (name !== 'Empty') {
                    // Store the full item object to preserve augments
                    items[slot] = item;
                }
            }
        }
        return items;
    },
    
    generateLuaContent(optimizedSets) {
        // If we don't have the original content, fall back to simple list
        if (!this.originalContent) {
            console.warn('No original content available, generating simple list');
            this.generateSimpleLuaList(optimizedSets);
            return;
        }
        
        // Fix any empyrean earrings that are in the wrong ear in non-placeholder
        // sets — these are preserved verbatim from the original template, so we
        // must correct them here before doing template replacement.
        let content = fixEmpyreanEarsInContent(this.originalContent);
        
        // Replace each placeholder set in the original content
        for (const set of optimizedSets) {
            content = this.replaceSetInContent(content, set.name, set.items, set.is_ranged_ws, set.base_set_name);
        }
        
        this.optimizedContent = content;
    },
    
    // Helper: Replace a single set's content in the Lua file
    replaceSetInContent(content, setName, items, isRangedWS = false, baseSetName = null) {
        // Build the gear string for this set
        const gearString = this.buildGearString(items, isRangedWS);
        
        // Find the set definition in the content
        // Set names can be like:
        //   sets.precast.FC
        //   sets.engaged.LowAcc.DT
        //   sets.precast.WS['Tachi: Shoha']
        //   sets.precast.JA['Meikyo Shisui']
        
        // First, escape all special regex characters
        let searchPattern = setName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        
        // Then apply our flexible matching rules
        searchPattern = searchPattern
            .replace(/\\\./g, '\\s*\\.\\s*')           // Allow whitespace around dots
            .replace(/\\\['/g, "\\s*\\[\\s*['\"]")     // Allow either quote type for ['
            .replace(/'\\]/g, "['\"]\\s*\\]\\s*");     // Allow either quote type for ']
        
        // Match the set assignment: setName = ... {
        // This handles both direct assignment and set_combine
        const regex = new RegExp(searchPattern + '\\s*=\\s*', 'g');
        
        const match = regex.exec(content);
        if (!match) {
            console.warn(`Could not find set "${setName}" in original content`);
            return content;
        }
        
        // Found the set name, now find where the gear table starts
        const assignmentEnd = match.index + match[0].length;
        
        // Look at what comes after the '='
        // It could be:
        //   { ... }                           -- direct assignment
        //   set_combine(base_set, { ... })    -- set_combine
        
        // Find the opening brace of the GEAR TABLE (not the set_combine args)
        let gearTableStart = -1;
        let isSetCombine = false;
        let pos = assignmentEnd;
        
        // Skip whitespace
        while (pos < content.length && /\s/.test(content[pos])) pos++;
        
        if (content[pos] === '{') {
            // Direct assignment: sets.x = { ... }
            gearTableStart = pos;
        } else if (content.substring(pos, pos + 11) === 'set_combine') {
            isSetCombine = true;
            // set_combine pattern: sets.x = set_combine(base, { ... })
            // Find the opening '(' of set_combine
            pos = content.indexOf('(', pos);
            if (pos === -1) {
                console.warn(`Malformed set_combine for "${setName}"`);
                return content;
            }
            
            // Now find the '{' that starts the gear table
            // It's after "set_combine(base_set, " - we need to skip past the base set reference
            // The gear table { comes after a comma
            let parenDepth = 1;
            pos++; // skip the '('
            
            while (pos < content.length && parenDepth > 0) {
                const char = content[pos];
                
                // Skip strings
                if (char === '"' || char === "'") {
                    const quote = char;
                    pos++;
                    while (pos < content.length && content[pos] !== quote) {
                        if (content[pos] === '\\') pos++; // skip escaped chars
                        pos++;
                    }
                }
                // Skip comments
                else if (char === '-' && content[pos + 1] === '-') {
                    pos = content.indexOf('\n', pos);
                    if (pos === -1) pos = content.length;
                }
                // Found the gear table opening brace
                else if (char === '{') {
                    gearTableStart = pos;
                    break;
                }
                // Track parens in case of nested calls
                else if (char === '(') {
                    parenDepth++;
                }
                else if (char === ')') {
                    parenDepth--;
                }
                
                pos++;
            }
        }
        
        if (gearTableStart === -1) {
            console.warn(`Could not find gear table start for "${setName}"`);
            return content;
        }
        
        // Find the matching closing brace
        const gearTableEnd = this.findMatchingBrace(content, gearTableStart);
        
        if (gearTableEnd <= gearTableStart) {
            console.warn(`Could not find gear table end for "${setName}"`);
            return content;
        }
        
        // --- SIRD / set_combine output ---
        // When baseSetName is provided, replace the entire right-hand side of the
        // assignment with set_combine(baseSetName, { <gear> })
        if (baseSetName) {
            // Find the full statement end: after the gear table '}', skip optional ')' for existing set_combine
            let stmtEnd = gearTableEnd + 1; // position after '}'
            if (isSetCombine) {
                // Skip whitespace and closing paren of the original set_combine(...)
                let p = stmtEnd;
                while (p < content.length && /\s/.test(content[p])) p++;
                if (p < content.length && content[p] === ')') {
                    stmtEnd = p + 1;
                }
            }
            
            const before = content.substring(0, assignmentEnd);
            const after = content.substring(stmtEnd);
            return before + `set_combine(${baseSetName}, {\n${gearString}\n    })` + after;
        }
        
        // --- Standard replacement: swap content between braces ---
        const before = content.substring(0, gearTableStart + 1);
        const after = content.substring(gearTableEnd);
        
        return before + '\n' + gearString + '\n    ' + after;
    },
    
    // Helper: Find the matching closing brace
    findMatchingBrace(content, openPos) {
        let depth = 1;
        let pos = openPos + 1;
        let inString = false;
        let stringChar = null;
        
        while (pos < content.length && depth > 0) {
            const char = content[pos];
            const prevChar = pos > 0 ? content[pos - 1] : '';
            
            // Handle string literals (single and double quotes)
            if ((char === '"' || char === "'") && prevChar !== '\\') {
                if (!inString) {
                    inString = true;
                    stringChar = char;
                } else if (char === stringChar) {
                    inString = false;
                    stringChar = null;
                }
            }
            
            // Handle Lua long strings [[ ]]
            if (char === '[' && content[pos + 1] === '[' && !inString) {
                const endLong = content.indexOf(']]', pos + 2);
                if (endLong !== -1) {
                    pos = endLong + 1;
                    continue;
                }
            }
            
            // Handle Lua comments
            if (char === '-' && content[pos + 1] === '-' && !inString) {
                // Skip to end of line
                const endLine = content.indexOf('\n', pos);
                if (endLine !== -1) {
                    pos = endLine;
                    continue;
                }
            }
            
            // Count braces (only if not in string)
            if (!inString) {
                if (char === '{') depth++;
                if (char === '}') depth--;
            }
            
            pos++;
        }
        
        return pos - 1; // Position of the closing brace
    },
    
    // Helper: Build the gear string from items (now accepts full item objects)
    buildGearString(items, isRangedWS = false) {
        const slotOrder = ['main', 'sub', 'range', 'ammo', 'head', 'neck', 'ear1', 'ear2',
                          'body', 'hands', 'ring1', 'ring2', 'back', 'waist', 'legs', 'feet'];
        
        // Map our slot names to GearSwap slot names
        const slotMap = {
            'ear1': 'left_ear',
            'ear2': 'right_ear', 
            'ring1': 'left_ring',
            'ring2': 'right_ring'
        };
        
        // Fix empyrean earring slot order: these are right-ear only items.
        // If the optimizer placed one in ear1 (left), swap with ear2.
        const ear1Name = items['ear1']?.name || items['ear1']?.Name || (typeof items['ear1'] === 'string' ? items['ear1'] : '');
        if (isEmpyreanEarring(ear1Name)) {
            const tmp = items['ear1'];
            items['ear1'] = items['ear2'] || null;
            items['ear2'] = tmp;
        }
        
        // Check if we should comment out weapons
        const commentWeapons = document.getElementById('lua-comment-weapons')?.checked ?? true;
        
        // Weapon slots to comment out:
        // - main, sub, range are always commented (swapping loses TP)
        // - ammo is also commented for ranged WS (it's the "ammo" consumed by the WS)
        const weaponSlots = new Set(['main', 'sub', 'range']);
        if (isRangedWS) {
            weaponSlots.add('ammo');
        }
        
        const lines = [];
        for (const slot of slotOrder) {
            if (items[slot]) {
                const luaSlot = slotMap[slot] || slot;
                // Use formatLuaItem to properly handle augmented items
                const itemStr = formatLuaItem(items[slot]);
                // Comment out weapon slots if option is checked
                if (commentWeapons && weaponSlots.has(slot)) {
                    lines.push(`        -- ${luaSlot}=${itemStr},`);
                } else {
                    lines.push(`        ${luaSlot}=${itemStr},`);
                }
            }
        }
        
        return lines.join('\n');
    },
    
    // Fallback: Generate simple list when original content not available
    generateSimpleLuaList(optimizedSets) {
        // Check if we should comment out weapons
        const commentWeapons = document.getElementById('lua-comment-weapons')?.checked ?? true;
        
        let lua = '-- Generated by FFXI Gear Optimizer\n';
        lua += '-- NOTE: Original template not available. Copy these sets into your Lua file manually.\n\n';
        
        for (const set of optimizedSets) {
            lua += `-- ${set.name}\n`;
            lua += `-- Profile: ${set.profile_type}\n`;
            
            // SIRD sets use set_combine with their base midcast set
            if (set.base_set_name) {
                lua += `${set.name} = set_combine(${set.base_set_name}, {\n`;
            } else {
                lua += '{\n';
            }
            
            const slotOrder = ['main', 'sub', 'range', 'ammo', 'head', 'neck', 'ear1', 'ear2',
                               'body', 'hands', 'ring1', 'ring2', 'back', 'waist', 'legs', 'feet'];
            
            for (const slot of slotOrder) {
                if (set.items[slot]) {
                    const luaSlot = slot === 'ear1' ? 'left_ear' : 
                                   slot === 'ear2' ? 'right_ear' :
                                   slot === 'ring1' ? 'left_ring' :
                                   slot === 'ring2' ? 'right_ring' : slot;
                    // Use formatLuaItem to properly handle augmented items
                    const itemStr = formatLuaItem(set.items[slot]);
                    // Comment out weapon slots if option is checked
                    // main, sub, range are always weapon slots; ammo is also a weapon slot for ranged WS
                    const isWeaponSlot = slot === 'main' || slot === 'sub' || slot === 'range'
                        || (slot === 'ammo' && set.is_ranged_ws);
                    if (commentWeapons && isWeaponSlot) {
                        lua += `    -- ${luaSlot}=${itemStr},\n`;
                    } else {
                        lua += `    ${luaSlot}=${itemStr},\n`;
                    }
                }
            }
            
            if (set.base_set_name) {
                lua += '})\n\n';
            } else {
                lua += '}\n\n';
            }
        }
        
        this.optimizedContent = lua;
    },
    
    showStatus(text) {
        const statusDiv = document.getElementById('lua-status');
        const statusText = document.getElementById('lua-status-text');
        const spinner = document.getElementById('lua-spinner');
        
        if (statusDiv) statusDiv.classList.remove('hidden');
        if (statusText) statusText.textContent = text;
        if (spinner) spinner.style.display = 'block';
    },
    
    updateStatus(text, progress) {
        const statusText = document.getElementById('lua-status-text');
        const progressBar = document.getElementById('lua-progress');
        
        if (statusText) statusText.textContent = text;
        if (progressBar) progressBar.style.width = `${progress}%`;
    },
    
    hideStatus() {
        const statusDiv = document.getElementById('lua-status');
        if (statusDiv) statusDiv.classList.add('hidden');
    },
    
    showResults(result) {
        const resultsDiv = document.getElementById('lua-results');
        if (resultsDiv) resultsDiv.classList.remove('hidden');
        
        // Show download button
        const downloadBtn = document.getElementById('btn-lua-download');
        if (downloadBtn) downloadBtn.style.display = 'inline-flex';
        
        // Update summary
        document.getElementById('lua-result-job').textContent = result.job || '-';
        document.getElementById('lua-result-optimized').textContent = result.sets_optimized || 0;
        document.getElementById('lua-result-skipped').textContent = result.sets_skipped || 0;
        
        // Populate sets list with simulation info
        const setsList = document.getElementById('lua-sets-list');
        if (setsList && result.optimized_sets) {
            setsList.innerHTML = result.optimized_sets.map((set, index) => {
                const optType = set.optimization_type || 'beam_only';
                const badge = this.getOptTypeBadge(optType);
                const simValue = this.formatSimValue(set.simulation_value, optType);
                
                // Get spell name for magic sets
                const spellInfo = (set.simulation_details?.spell_name && 
                    (optType === 'magic_damage' || optType === 'magic_burst' || optType === 'magic_accuracy'))
                    ? `<span class="text-purple-400 text-xs">${set.simulation_details.spell_name}</span>` : '';
                
                return `
                <div class="bg-ffxi-dark px-3 py-2 rounded cursor-pointer hover:bg-ffxi-darker transition-colors"
                     onclick="LuaOptimizer.showSetDetails(${index})">
                    <div class="flex justify-between items-center mb-1">
                        <span class="text-ffxi-text text-sm font-medium truncate max-w-[55%]" title="${set.name}">${this.truncateSetName(set.name)}</span>
                        ${badge}
                    </div>
                    <div class="flex justify-between items-center text-xs">
                        <span class="text-ffxi-text-dim">${set.profile_type} ${spellInfo}</span>
                        ${simValue ? `<span class="text-ffxi-accent">${simValue}</span>` : ''}
                    </div>
                </div>
            `}).join('');
        }
        
        // Show errors if any
        const errorsDiv = document.getElementById('lua-errors');
        const errorsList = document.getElementById('lua-errors-list');
        if (result.errors && result.errors.length > 0) {
            if (errorsDiv) errorsDiv.classList.remove('hidden');
            if (errorsList) {
                errorsList.innerHTML = result.errors.map(err => `
                    <div class="text-ffxi-red">${err}</div>
                `).join('');
            }
        } else {
            if (errorsDiv) errorsDiv.classList.add('hidden');
        }
    },
    
    getOptTypeBadge(optType) {
        const badges = {
            'ws_simulation': '<span class="text-xs bg-ffxi-red/30 text-ffxi-red px-2 py-0.5 rounded">WS Sim</span>',
            'tp_simulation': '<span class="text-xs bg-ffxi-blue/30 text-ffxi-blue px-2 py-0.5 rounded">TP Sim</span>',
            'magic_damage': '<span class="text-xs bg-purple-500/30 text-purple-400 px-2 py-0.5 rounded">Magic Sim</span>',
            'magic_burst': '<span class="text-xs bg-purple-500/30 text-purple-400 px-2 py-0.5 rounded">MB Sim</span>',
            'magic_accuracy': '<span class="text-xs bg-cyan-500/30 text-cyan-400 px-2 py-0.5 rounded">M.Acc</span>',
            'healing': '<span class="text-xs bg-pink-500/30 text-pink-400 px-2 py-0.5 rounded">Cure</span>',
            'enhancing_skill': '<span class="text-xs bg-green-500/30 text-green-400 px-2 py-0.5 rounded">Enh Skill</span>',
            'enhancing_duration': '<span class="text-xs bg-green-500/30 text-green-400 px-2 py-0.5 rounded">Enh Dur</span>',
            'dt_capped': '<span class="text-xs bg-ffxi-green/30 text-ffxi-green px-2 py-0.5 rounded">DT Cap</span>',
            'sird': '<span class="text-xs bg-teal-500/30 text-teal-400 px-2 py-0.5 rounded">SIRD</span>',
            'fc_capped': '<span class="text-xs bg-yellow-500/30 text-yellow-400 px-2 py-0.5 rounded">FC Cap</span>',
            'beam_only': '<span class="text-xs bg-ffxi-border text-ffxi-text-dim px-2 py-0.5 rounded">Beam</span>',
        };
        return badges[optType] || badges['beam_only'];
    },
    
    formatSimValue(value, optType) {
        if (value === null || value === undefined) return '';
        
        switch (optType) {
            case 'ws_simulation':
            case 'magic_damage':
            case 'magic_burst':
                return `${Math.round(value).toLocaleString()} dmg`;
            case 'magic_accuracy':
                return `${Math.round(value)} M.Acc`;
            case 'healing':
                return `${Math.round(value)} HP`;
            case 'enhancing_skill':
            case 'enhancing_duration':
                return `Score: ${Math.round(value)}`;
            case 'tp_simulation':
                return `${value.toFixed(2)}s to WS`;
            case 'dt_capped':
            case 'fc_capped':
                return `${value.toFixed(1)}% eff`;
            case 'sird':
                return `${Math.round(value)}% SIRD`;
            default:
                return `Score: ${Math.round(value)}`;
        }
    },
    
    truncateSetName(name) {
        // Extract the last meaningful part of the set name
        const parts = name.split('.');
        if (parts.length > 2) {
            return parts.slice(-2).join('.');
        }
        return name.length > 30 ? name.substring(0, 27) + '...' : name;
    },
    
    showSetDetails(index) {
        if (!this.optimizedSets || !this.optimizedSets[index]) return;
        
        const set = this.optimizedSets[index];
        const detailsDiv = document.getElementById('lua-set-details');
        const nameEl = document.getElementById('lua-set-details-name');
        const contentEl = document.getElementById('lua-set-details-content');
        
        if (!detailsDiv || !contentEl) return;
        
        nameEl.textContent = set.name;
        
        // Build details content
        let html = `
            <div class="grid grid-cols-2 gap-2 mb-3">
                <div><span class="text-ffxi-text-dim">Profile:</span> <span class="text-ffxi-text">${set.profile_type}</span></div>
                <div><span class="text-ffxi-text-dim">Type:</span> ${this.getOptTypeBadge(set.optimization_type)}</div>
                <div><span class="text-ffxi-text-dim">Beam Score:</span> <span class="text-ffxi-text">${Math.round(set.score).toLocaleString()}</span></div>
                <div><span class="text-ffxi-text-dim">Sim Value:</span> <span class="text-ffxi-accent">${this.formatSimValue(set.simulation_value, set.optimization_type)}</span></div>
            </div>
        `;
        
        // Add simulation details if present
        if (set.simulation_details) {
            const details = set.simulation_details;
            
            // Cap validation details
            if (details.cap_validation) {
                html += `<div class="border-t border-ffxi-border pt-2 mt-2">
                    <div class="font-semibold text-ffxi-text mb-1">Cap Validation:</div>`;
                for (const [stat, cap] of Object.entries(details.cap_validation)) {
                    const color = cap.is_capped ? 'text-ffxi-green' : 'text-ffxi-text';
                    const overflow = cap.total > cap.cap ? ` <span class="text-yellow-400">(+${cap.total - cap.cap} overcap)</span>` : '';
                    html += `<div class="${color}">${stat}: ${cap.total}/${cap.cap} (${cap.efficiency_pct.toFixed(1)}%)${overflow}</div>`;
                }
                html += `</div>`;
            }
            
            // TP simulation details
            if (details.time_to_ws !== undefined) {
                html += `<div class="border-t border-ffxi-border pt-2 mt-2">
                    <div class="font-semibold text-ffxi-text mb-1">TP Simulation:</div>
                    <div>Time to WS: <span class="text-ffxi-accent">${details.time_to_ws.toFixed(2)}s</span></div>
                    ${details.tp_per_round ? `<div>TP/Round: ${details.tp_per_round.toFixed(1)}</div>` : ''}
                    ${details.dps ? `<div>DPS: ${Math.round(details.dps).toLocaleString()}</div>` : ''}
                </div>`;
            }
            
            // WS simulation details
            if (details.hit_rate !== undefined && set.optimization_type === 'ws_simulation') {
                html += `<div class="border-t border-ffxi-border pt-2 mt-2">
                    <div class="font-semibold text-ffxi-text mb-1">WS Simulation:</div>
                    <div>Damage: <span class="text-ffxi-accent">${Math.round(set.simulation_value).toLocaleString()}</span></div>
                    <div>Hit Rate: ${(details.hit_rate * 100).toFixed(1)}%</div>
                </div>`;
            }
            
            // Magic simulation details
            if (details.spell_name && (set.optimization_type === 'magic_damage' || set.optimization_type === 'magic_burst')) {
                html += `<div class="border-t border-ffxi-border pt-2 mt-2">
                    <div class="font-semibold text-ffxi-text mb-1">Magic Simulation:</div>
                    <div>Spell: <span class="text-ffxi-accent">${details.spell_name}</span></div>
                    <div>Damage: <span class="text-ffxi-accent">${Math.round(set.simulation_value).toLocaleString()}</span></div>
                    ${details.magic_burst ? '<div>Mode: <span class="text-purple-400">Magic Burst</span></div>' : '<div>Mode: Free Nuke</div>'}
                    ${details.unresisted_rate !== undefined ? `<div>Unresisted Rate: ${(details.unresisted_rate * 100).toFixed(1)}%</div>` : ''}
                </div>`;
            }
        }
        
        // Gear list
        html += `<div class="border-t border-ffxi-border pt-2 mt-2">
            <div class="font-semibold text-ffxi-text mb-1">Gear:</div>
            <div class="grid grid-cols-2 gap-1 text-ffxi-text-dim">`;
        
        const slotOrder = ['main', 'sub', 'range', 'ammo', 'head', 'neck', 'ear1', 'ear2', 
                          'body', 'hands', 'ring1', 'ring2', 'back', 'waist', 'legs', 'feet'];
        
        for (const slot of slotOrder) {
            if (set.items[slot]) {
                // set.items[slot] is now a full item object, extract display name
                const item = set.items[slot];
                const displayName = typeof item === 'string' ? item : (item.name2 || item.name || item.Name || 'Unknown');
                html += `<div><span class="text-ffxi-text">${slot}:</span> ${displayName}</div>`;
            }
        }
        html += `</div></div>`;
        
        contentEl.innerHTML = html;
        detailsDiv.classList.remove('hidden');
    },
    
    hideSetDetails() {
        const detailsDiv = document.getElementById('lua-set-details');
        if (detailsDiv) detailsDiv.classList.add('hidden');
    },
    
    hideResults() {
        const resultsDiv = document.getElementById('lua-results');
        if (resultsDiv) resultsDiv.classList.add('hidden');
    },
    
    showError(message) {
        this.hideStatus();
        const resultsDiv = document.getElementById('lua-results');
        const errorsDiv = document.getElementById('lua-errors');
        const errorsList = document.getElementById('lua-errors-list');
        
        if (resultsDiv) resultsDiv.classList.remove('hidden');
        
        // Clear success data
        document.getElementById('lua-result-job').textContent = '-';
        document.getElementById('lua-result-optimized').textContent = '0';
        document.getElementById('lua-result-skipped').textContent = '0';
        document.getElementById('lua-sets-list').innerHTML = '';
        
        // Show error
        if (errorsDiv) errorsDiv.classList.remove('hidden');
        if (errorsList) {
            errorsList.innerHTML = `<div class="text-ffxi-red">${message}</div>`;
        }
        
        // Hide download button on error
        const downloadBtn = document.getElementById('btn-lua-download');
        if (downloadBtn) downloadBtn.style.display = 'none';
    },
    
    downloadResult() {
        if (!this.optimizedSets) {
            return;
        }
        
        // Regenerate content at download time to respect current checkbox state
        this.generateLuaContent(this.optimizedSets);
        
        if (!this.optimizedContent) {
            return;
        }
        
        // Create blob and download
        const blob = new Blob([this.optimizedContent], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = this.selectedFile.name.replace('.lua', '_optimized.lua');
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
};


// =============================================================================
// INITIALIZE ON DOM READY
// =============================================================================

document.addEventListener('DOMContentLoaded', initializeApp);

// Make functions available globally for onclick handlers
window.removeBuffFromList = removeTabBuffFromList;
window.removeDebuffFromList = removeTabDebuffFromList;
window.showResultDetails = showResultDetails;
window.showMagicResultDetails = showMagicResultDetails;
window.removeMagicBuff = removeMagicBuff;
window.removeMagicDebuff = removeMagicDebuff;
window.handleWSModeToggle = handleWSModeToggle;
window.InventoryBrowser = InventoryBrowser;
window.LuaOptimizer = LuaOptimizer;
window.SetBuilder = SetBuilder;