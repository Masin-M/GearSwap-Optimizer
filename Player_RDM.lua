-- Original: Motenten / Modified: Arislan
-- GearSwap Lua for RDM
-- Player: Player
-- Generated: 2026-01-17 22:03

-------------------------------------------------------------------------------------------------------------------
-- Default Keybinds (from Mote-Globals.lua)
-------------------------------------------------------------------------------------------------------------------
-- These are the default keybinds set up by Mote-Include. You can use these to swap modes in-game.
--
-- F9          = Cycle Offense Mode (Normal > LowAcc > MidAcc > HighAcc, etc.)
-- Ctrl+F9     = Cycle Hybrid Mode (Normal > DT, etc.)
-- Alt+F9      = Cycle Ranged Mode
-- Win+F9      = Cycle Weaponskill Mode (Normal > Acc, etc.)
--
-- F10         = Set Defense Mode to Physical
-- Ctrl+F10    = Cycle Physical Defense Mode
-- Alt+F10     = Toggle Kiting Mode (movement speed gear)
--
-- F11         = Set Defense Mode to Magical
-- Ctrl+F11    = Cycle Casting Mode (Normal > Resistant, etc.)
--
-- F12         = Update gear and display current state
-- Ctrl+F12    = Cycle Idle Mode (Normal > DT > Regen, etc.)
-- Alt+F12     = Reset Defense Mode to None
--
-- To use: Press the key in-game, or type commands like:
--   //gs c cycle OffenseMode
--   //gs c set HybridMode DT
--   //gs c toggle Kiting
-------------------------------------------------------------------------------------------------------------------

-------------------------------------------------------------------------------------------------------------------
-- Setup functions for this job. Generally should not be modified.
-------------------------------------------------------------------------------------------------------------------

-- Initialization function for this job file.
function get_sets()
    mote_include_version = 2

    -- Load and initialize the include file.
    include('Mote-Include.lua')
end

-- Setup vars that are user-independent. state.Buff vars initialized here will automatically be tracked.
function job_setup()
    state.Buff['Composure'] = buffactive['Composure'] or false
    state.Buff['Saboteur'] = buffactive['Saboteur'] or false
    state.Buff['Stymie'] = buffactive['Stymie'] or false

    -- Skill-based enfeebles (potency from Enfeebling skill)
    enfeebling_magic_skill = S{'Distract', 'Distract II', 'Distract III', 'Frazzle', 'Frazzle II', 'Frazzle III'}
    -- MND-based enfeebles
    enfeebling_magic_mnd = S{'Paralyze', 'Paralyze II', 'Slow', 'Slow II', 'Addle', 'Addle II', 'Silence'}
    -- INT-based enfeebles
    enfeebling_magic_int = S{'Blind', 'Blind II', 'Bind', 'Gravity', 'Gravity II', 'Dispel', 'Break', 'Breakga'}
    -- Sleep spells (special duration handling)
    enfeebling_magic_sleep = S{'Sleep', 'Sleep II', 'Sleepga', 'Sleepga II'}
    -- Skill-based enhancing (potency from Enhancing skill)
    enhancing_magic_skill = S{'Temper', 'Temper II', 'Phalanx', 'Phalanx II', 'Gain-STR', 'Gain-DEX', 'Gain-VIT', 'Gain-AGI', 'Gain-INT', 'Gain-MND', 'Gain-CHR'}

    -- Gear that should not be swapped
    no_swap_gear = S{"Warp Ring", "Dim. Ring (Dem)", "Dim. Ring (Holla)", "Dim. Ring (Mea)",
        "Trizek Ring", "Echad Ring", "Facility Ring", "Capacity Ring"}

end

-------------------------------------------------------------------------------------------------------------------
-- User setup functions for this job. Recommend that these be overridden in a sidecar file.
-------------------------------------------------------------------------------------------------------------------

-- Setup vars that are user-dependent. Can override this function in a sidecar file.
function user_setup()
    state.OffenseMode:options('Normal', 'Acc')
    state.HybridMode:options('Normal', 'DT')
    state.IdleMode:options('Normal', 'DT', 'Refresh')
    state.CastingMode:options('Normal', 'Resistant')

    state.MagicBurst = M(false, 'Magic Burst')

    state.WeaponLock = M(false, 'Weapon Lock')

    -- Additional local binds
    -- include('Global-Binds.lua') -- OK to remove this line

    -- Default macro book/set
    set_macro_page(1, 1)
end

function user_unload()
    -- Unbind keys here if needed
end

-- Define sets and vars used by this job file.
function init_gear_sets()

    ------------------------------------------------------------------------------------------------
    ---------------------------------------- Gear Variables ----------------------------------------
    ------------------------------------------------------------------------------------------------

    -- Augmented gear variables - define your augmented gear here
    gear.RDM_FC_Cape = { name="Sucellos's Cape", augments={'Fast Cast +10%'} }
    gear.RDM_WS_Cape = { name="Sucellos's Cape", augments={'Weapon skill damage +10%'} }
    gear.RDM_Nuke_Cape = { name="Sucellos's Cape", augments={'INT+20','Mag. Acc+20 /Mag. Dmg.+20','"Mag.Atk.Bns."+10'} }


    ------------------------------------------------------------------------------------------------
    ---------------------------------------- Precast Sets ------------------------------------------
    ------------------------------------------------------------------------------------------------

    -- Fast Cast (80% cap)
    sets.precast.FC = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- Cure Precast (Quick Magic)
    sets.precast.FC.Cure = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- Enhancing FC
    sets.precast.FC.Enhancing = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- Impact FC (Twilight Cloak body, no head)
    sets.precast.FC.Impact = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- Dispelga FC (requires Daybreak)
    sets.precast.FC.Dispelga = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }


    ------------------------------------------------------------------------------------------------
    ---------------------------------------- JA Sets ------------------------------------------
    ------------------------------------------------------------------------------------------------

    -- Chainspell duration
    sets.precast.JA['Chainspell'] = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- Saboteur potency
    sets.precast.JA['Saboteur'] = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }


    ------------------------------------------------------------------------------------------------
    ---------------------------------------- Enfeebling Sets ------------------------------------------
    ------------------------------------------------------------------------------------------------

    -- MND enfeebles (Macc + MND)
    sets.midcast.MndEnfeebles = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- MND enfeebles accuracy focus
    sets.midcast.MndEnfeebles.Resistant = set_combine(sets.midcast.MndEnfeebles, {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    })

    -- INT enfeebles (Macc + INT)
    sets.midcast.IntEnfeebles = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- INT enfeebles accuracy focus
    sets.midcast.IntEnfeebles.Resistant = set_combine(sets.midcast.IntEnfeebles, {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    })

    -- Sleep duration
    sets.midcast.Sleep = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- Sleep max duration (with Stymie)
    sets.midcast.SleepMaxDuration = set_combine(sets.midcast.Sleep, {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    })

    -- Dispelga (requires Daybreak main)
    sets.midcast.Dispelga = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }


    ------------------------------------------------------------------------------------------------
    ---------------------------------------- Enhancing Sets ------------------------------------------
    ------------------------------------------------------------------------------------------------

    -- Enhancing base
    sets.midcast['Enhancing Magic'] = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- Enhancing duration
    sets.midcast.EnhancingDuration = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- Enhancing skill (Temper, Phalanx, Gain)
    sets.midcast.EnhancingSkill = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- Phalanx potency
    sets.midcast.Phalanx = set_combine(sets.midcast.EnhancingSkill, {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    })

    -- Refresh potency
    sets.midcast.Refresh = set_combine(sets.midcast.EnhancingDuration, {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    })

    -- Stoneskin
    sets.midcast.Stoneskin = set_combine(sets.midcast.EnhancingDuration, {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    })

    -- Aquaveil
    sets.midcast.Aquaveil = set_combine(sets.midcast.EnhancingDuration, {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    })


    ------------------------------------------------------------------------------------------------
    ---------------------------------------- Elemental Sets ------------------------------------------
    ------------------------------------------------------------------------------------------------

    -- Nuking (MAB focus)
    sets.midcast['Elemental Magic'] = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- Nuking accuracy focus
    sets.midcast['Elemental Magic'].Resistant = set_combine(sets.midcast['Elemental Magic'], {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    })

    -- Magic Burst
    sets.midcast['Elemental Magic'].MB = set_combine(sets.midcast['Elemental Magic'], {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    })

    -- Magic Burst while engaged
    sets.midcast['Elemental Magic'].MB.Engaged = set_combine(sets.midcast['Elemental Magic'].MB, {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    })

    -- Impact (Twilight Cloak required)
    sets.midcast.Impact = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }


    ------------------------------------------------------------------------------------------------
    ---------------------------------------- Healing Sets ------------------------------------------
    ------------------------------------------------------------------------------------------------

    -- Cure potency
    sets.midcast.Cure = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- Curaga potency
    sets.midcast.Curaga = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }


    ------------------------------------------------------------------------------------------------
    ---------------------------------------- Buff Sets ------------------------------------------
    ------------------------------------------------------------------------------------------------

    -- Composure self-enhance bonus
    sets.buff.Composure = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- Saboteur enfeeble bonus
    sets.buff.Saboteur = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- Doom (Holy Water, cursna received)
    sets.buff.Doom = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }


    ------------------------------------------------------------------------------------------------
    ---------------------------------------- Idle Sets ------------------------------------------
    ------------------------------------------------------------------------------------------------

    -- Default idle
    sets.idle = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- Idle with DT focus
    sets.idle.DT = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- Idle with Refresh focus
    sets.idle.Refresh = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }


    ------------------------------------------------------------------------------------------------
    ---------------------------------------- Engaged Sets ------------------------------------------
    ------------------------------------------------------------------------------------------------

    -- Base engaged set
    sets.engaged = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- Accuracy focused
    sets.engaged.Acc = set_combine(sets.engaged, {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    })

    -- DT while engaged
    sets.engaged.DT = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- Enspell melee
    sets.engaged.Enspell = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    ------------------------------------------------------------------------------------------------
    ------------------------------------- Weapon Skill Sets ----------------------------------------
    ------------------------------------------------------------------------------------------------

    -- Default WS set
    sets.precast.WS = {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    }

    -- Black Halo
    sets.precast.WS['Black Halo'] = set_combine(sets.precast.WS, {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    })

    -- Chant du Cygne
    sets.precast.WS['Chant du Cygne'] = set_combine(sets.precast.WS, {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    })

    -- Death Blossom
    sets.precast.WS['Death Blossom'] = set_combine(sets.precast.WS, {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    })

    -- Requiescat
    sets.precast.WS['Requiescat'] = set_combine(sets.precast.WS, {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    })

    -- Sanguine Blade
    sets.precast.WS['Sanguine Blade'] = set_combine(sets.precast.WS, {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    })

    -- Savage Blade
    sets.precast.WS['Savage Blade'] = set_combine(sets.precast.WS, {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    })

    -- Seraph Blade
    sets.precast.WS['Seraph Blade'] = set_combine(sets.precast.WS, {
        --main="",
        --sub="",
        --range="",
        --ammo="",
        --head="",
        --neck="",
        --ear1="",
        --ear2="",
        --body="",
        --hands="",
        --ring1="",
        --ring2="",
        --back="",
        --waist="",
        --legs="",
        --feet="",
    })

end

-------------------------------------------------------------------------------------------------------------------
-- Job-specific hooks for spell mapping.
-------------------------------------------------------------------------------------------------------------------

-- Return custom spell map for spells not in default Mote mappings.
function job_get_spell_map(spell, default_spell_map)
    -- Frazzle/Distract use MND set but benefit from skill
    if enfeebling_magic_skill:contains(spell.english) then
        return 'MndEnfeebles'
    end
    -- MND-based enfeebles
    if enfeebling_magic_mnd:contains(spell.english) then
        return 'MndEnfeebles'
    end
    -- INT-based enfeebles
    if enfeebling_magic_int:contains(spell.english) then
        return 'IntEnfeebles'
    end
    -- Sleep spells with duration focus
    if enfeebling_magic_sleep:contains(spell.english) then
        return 'Sleep'
    end
    -- Skill-based enhancing
    if enhancing_magic_skill:contains(spell.english) then
        return 'EnhancingSkill'
    end

    return default_spell_map
end

-------------------------------------------------------------------------------------------------------------------
-- Job-specific hooks for standard casting events.
-------------------------------------------------------------------------------------------------------------------

-- Set eventArgs.handled to true if we don't want any automatic gear equipping to be done.
-- Set eventArgs.useMidcastGear to true if we want midcast gear equipped on precast.
function job_precast(spell, action, spellMap, eventArgs)
    -- Impact requires Twilight Cloak (no head slot)
    if spell.english == 'Impact' then
        equip(sets.precast.FC.Impact)
    end

    -- Dispelga requires Daybreak
    if spell.english == 'Dispelga' then
        equip(sets.precast.FC.Dispelga)
    end

end

-- Run after default midcast() is done.
-- Use to apply additional gear on top of what Mote selected.
function job_post_midcast(spell, action, spellMap, eventArgs)
    if spell.skill == 'Enfeebling Magic' then
        -- Saboteur potency bonus for MND enfeebles
        if enfeebling_magic_mnd:contains(spell.english) and state.Buff['Saboteur'] then
            equip(sets.buff.Saboteur)
        end
        -- Max sleep duration with Saboteur + Stymie
        if enfeebling_magic_sleep:contains(spell.english) and state.Buff['Saboteur'] and state.Buff['Stymie'] then
            equip(sets.midcast.SleepMaxDuration)
        end
    end

    if spell.skill == 'Enhancing Magic' then
        -- Composure extends self-buff duration
        if spell.target.type == 'SELF' and state.Buff['Composure'] then
            equip(sets.buff.Composure)
        end
    end

    if spell.skill == 'Elemental Magic' then
        -- Magic Burst gear when MB mode active
        if state.MagicBurst.value then
            equip(sets.midcast['Elemental Magic'].MB)
        end
        -- Magic Burst gear while engaged
        if state.MagicBurst.value and player.status == 'Engaged' then
            equip(sets.midcast['Elemental Magic'].MB.Engaged)
        end
    end

end

function job_aftercast(spell, action, spellMap, eventArgs)
    -- Aftercast is mainly handled by Mote-Include (returns to idle/engaged)
end

-------------------------------------------------------------------------------------------------------------------
-- Job-specific hooks for non-casting events.
-------------------------------------------------------------------------------------------------------------------

function job_buff_change(buff, gain)
    -- Update tracked buffs and re-equip gear if needed
    if state.Buff[buff] ~= nil then
        state.Buff[buff] = gain
        if not midaction() then
            handle_equipping_gear(player.status)
        end
    end

    -- Doom handling
    if buff == 'Doom' then
        if gain then
            equip(sets.buff.Doom)
            send_command('@input /p Doomed.')
            disable('ring1', 'ring2', 'waist')
        else
            enable('ring1', 'ring2', 'waist')
            handle_equipping_gear(player.status)
        end
    end
end

function job_state_change(stateField, newValue, oldValue)
    -- Handle Weapon Lock toggle
    if stateField == 'Weapon Lock' then
        if newValue == true then
            disable('main', 'sub', 'range')
        else
            enable('main', 'sub', 'range')
        end
    end
end

-------------------------------------------------------------------------------------------------------------------
-- User code that supplements standard library decisions.
-------------------------------------------------------------------------------------------------------------------

function job_handle_equipping_gear(playerStatus, eventArgs)
    check_rings()
    check_moving()
end

-- Prevent swapping out special rings
function check_rings()
    if no_swap_gear:contains(player.equipment.ring1) then
        disable('ring1')
    else
        enable('ring1')
    end
    if no_swap_gear:contains(player.equipment.ring2) then
        disable('ring2')
    else
        enable('ring2')
    end
end

-- Movement speed gear
function check_moving()
    if state.DefenseMode.value == 'None' and state.Kiting.value then
        equip(sets.Kiting)
    end
end

-------------------------------------------------------------------------------------------------------------------
-- Utility functions specific to this job.
-------------------------------------------------------------------------------------------------------------------

-- Select obi based on weather/day
function get_obi(spell)
    if spell.element and (spell.element == world.weather_element or spell.element == world.day_element) then
        return {waist="Hachirin-no-Obi"}
    end
    return {}
end
