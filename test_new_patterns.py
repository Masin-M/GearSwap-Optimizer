#!/usr/bin/env python3
"""
Test script to validate the new stat parsing for wsdist compatibility.

This tests the new STAT_PATTERNS and STAT_LOOKUP entries.
"""

import sys
import re

# Test descriptions that should match the new patterns
TEST_DESCRIPTIONS = [
    # TP-related
    ('"TP Bonus"+500', {'tp_bonus': 500}),
    ('TP Bonus+250', {'tp_bonus': 250}),
    ('"Daken"+10', {'daken': 10}),
    ('Daken+5%', {'daken': 5}),
    ('"Martial Arts"+20', {'martial_arts': 20}),
    ('"Zanshin"+15', {'zanshin': 15}),
    ('"Kick Attacks"+10', {'kick_attacks': 10}),
    ('"Subtle Blow"+10', {'subtle_blow': 10}),
    ('"Subtle Blow II"+5', {'subtle_blow_ii': 5}),
    ('"Fencer"+2', {'fencer': 2}),
    ('"Conserve TP"+10', {'conserve_tp': 10}),
    ('"Regain"+5', {'regain': 5}),
    
    # Occasional attacks
    ('"OA2"+5', {'oa2': 5}),
    ('"OA3"+3', {'oa3': 3}),
    ('"FUA"+10', {'fua': 10}),
    
    # Damage modifiers
    ('"PDL"+5%', {'pdl': 500}),  # basis points
    ('Physical damage limit+3', {'pdl': 300}),
    ('"Skillchain Bonus"+10%', {'skillchain_bonus': 1000}),
    
    # Ranged
    ('"Double Shot"+5', {'double_shot': 5}),
    ('"Triple Shot"+3', {'triple_shot': 3}),
    ('"True Shot"+5', {'true_shot': 5}),
    ('"Recycle"+10', {'recycle': 10}),
    ('"Barrage"+1', {'barrage': 1}),
    
    # Magic
    ('Magic Accuracy Skill+228', {'magic_accuracy_skill': 228}),
    ('"Magic Burst Damage II"+10%', {'magic_burst_damage_ii': 1000}),
    
    # Job-specific
    ('"EnSpell Damage"+15', {'enspell_damage': 15}),
    ('"Ninjutsu Magic Attack"+20', {'ninjutsu_magic_attack': 20}),
    ('"Blood Pact Damage"+5%', {'blood_pact_damage': 500}),
    ('"Occult Acumen"+10', {'occult_acumen': 10}),
    
    # Elemental
    ('Fire Elemental Bonus+10', {'fire_elemental_bonus': 10}),
    ('Dark Elemental Bonus+5', {'dark_elemental_bonus': 5}),
]


# New STAT_PATTERNS to test (from item_database.py)
STAT_PATTERNS = [
    # TP Bonus
    (r'"TP Bonus"\s*[+]?\s*(\d+)', 'tp_bonus', 1),
    (r'TP Bonus\s*[+]?\s*(\d+)', 'tp_bonus', 1),
    
    # Daken
    (r'"Daken"\s*[+]?\s*(\d+)%?', 'daken', 1),
    (r'Daken\s*[+]?\s*(\d+)%?', 'daken', 1),
    
    # Martial Arts
    (r'"Martial Arts"\s*[+]?\s*(\d+)', 'martial_arts', 1),
    
    # Zanshin
    (r'"Zanshin"\s*[+]?\s*(\d+)%?', 'zanshin', 1),
    
    # Kick Attacks
    (r'"Kick Attacks"\s*[+]?\s*(\d+)%?', 'kick_attacks', 1),
    
    # Subtle Blow
    (r'"Subtle Blow"\s*[+]?\s*(\d+)', 'subtle_blow', 1),
    (r'"Subtle Blow II"\s*[+]?\s*(\d+)', 'subtle_blow_ii', 1),
    
    # Fencer
    (r'"Fencer"\s*[+]?\s*(\d+)', 'fencer', 1),
    
    # Conserve TP
    (r'"Conserve TP"\s*[+]?\s*(\d+)%?', 'conserve_tp', 1),
    
    # Regain
    (r'"Regain"\s*[+]?\s*(\d+)', 'regain', 1),
    
    # Occasional attacks
    (r'"OA2"\s*[+]?\s*(\d+)%?', 'oa2', 1),
    (r'"OA3"\s*[+]?\s*(\d+)%?', 'oa3', 1),
    (r'"FUA"\s*[+]?\s*(\d+)%?', 'fua', 1),
    
    # PDL
    (r'"PDL"\s*[+]?\s*(\d+)%?', 'pdl', 100),
    (r'Phys(?:ical)?\.?\s*(?:dmg|damage)\.?\s*limit\s*[+]?\s*(\d+)%?', 'pdl', 100),
    
    # Skillchain Bonus
    (r'"Skillchain Bonus"\s*[+]?\s*(\d+)%?', 'skillchain_bonus', 100),
    
    # Ranged
    (r'"Double Shot"\s*[+]?\s*(\d+)%?', 'double_shot', 1),
    (r'"Triple Shot"\s*[+]?\s*(\d+)%?', 'triple_shot', 1),
    (r'"True Shot"\s*[+]?\s*(\d+)%?', 'true_shot', 1),
    (r'"Recycle"\s*[+]?\s*(\d+)%?', 'recycle', 1),
    (r'"Barrage"\s*[+]?\s*(\d+)', 'barrage', 1),
    
    # Magic
    (r'Magic Accuracy Skill\s*[+]?\s*(\d+)', 'magic_accuracy_skill', 1),
    (r'"Magic Burst Damage II"\s*[+]?\s*(\d+)%?', 'magic_burst_damage_ii', 100),
    
    # Job-specific
    (r'"EnSpell Damage"\s*[+]?\s*(\d+)', 'enspell_damage', 1),
    (r'"Ninjutsu Magic Attack"\s*[+]?\s*(\d+)', 'ninjutsu_magic_attack', 1),
    (r'"Blood Pact Damage"\s*[+]?\s*(\d+)%?', 'blood_pact_damage', 100),
    (r'"Occult Acumen"\s*[+]?\s*(\d+)', 'occult_acumen', 1),
    
    # Elemental
    (r'Fire\s+Elemental\s+Bonus\s*[+]?\s*(\d+)', 'fire_elemental_bonus', 1),
    (r'Dark\s+Elemental\s+Bonus\s*[+]?\s*(\d+)', 'dark_elemental_bonus', 1),
]


def parse_test_description(text):
    """Parse stats from a test description."""
    results = {}
    
    for pattern, stat_name, multiplier in STAT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = int(match.group(1)) * multiplier
            results[stat_name] = value
    
    return results


def run_tests():
    """Run all pattern tests."""
    print("Testing new STAT_PATTERNS for wsdist compatibility...")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for desc, expected in TEST_DESCRIPTIONS:
        results = parse_test_description(desc)
        
        # Check if all expected stats were found
        success = True
        for stat, value in expected.items():
            if stat not in results:
                print(f"FAIL: '{desc}' - missing {stat}")
                success = False
            elif results[stat] != value:
                print(f"FAIL: '{desc}' - {stat}={results[stat]}, expected {value}")
                success = False
        
        if success:
            print(f"PASS: '{desc}' -> {results}")
            passed += 1
        else:
            failed += 1
    
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
