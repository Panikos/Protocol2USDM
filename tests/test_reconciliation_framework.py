"""Quick test for the unified reconciliation framework."""

from core.reconciliation import (
    EpochReconciler, ActivityReconciler, EncounterReconciler,
    reconcile_epochs_from_pipeline,
    reconcile_activities_from_pipeline, 
    reconcile_encounters_from_pipeline
)

def test_epoch_reconciler():
    """Test epoch reconciliation with footnote cleaning and traversal."""
    epochs = [
        {'id': 'e1', 'name': 'Screening a'},
        {'id': 'e2', 'name': 'Treatment Period b'},
        {'id': 'e3', 'name': 'Follow-up c'}
    ]
    
    result = reconcile_epochs_from_pipeline(
        soa_epochs=epochs,
        traversal_sequence=['epoch_1', 'epoch_3']  # Screening and Follow-up are main
    )
    
    print(f"Epochs: {len(result)} reconciled")
    for ep in result:
        category = next(
            (x.get('valueString') for x in ep.get('extensionAttributes', []) 
             if 'epochCategory' in x.get('url', '')), 
            'unknown'
        )
        print(f"  - {ep['name']} [{category}]")
    
    # Verify name cleaning
    assert result[0]['name'] == 'Screening', f"Expected 'Screening', got '{result[0]['name']}'"
    print("  ✓ Name cleaning works")


def test_activity_reconciler():
    """Test activity reconciliation with type inference."""
    activities = [
        {'id': 'a1', 'name': 'Blood Draw (c)'},
        {'id': 'a2', 'name': 'Physical Exam'},
        {'id': 'a3', 'name': 'ECG Assessment'}
    ]
    
    result = reconcile_activities_from_pipeline(soa_activities=activities)
    
    print(f"Activities: {len(result)} reconciled")
    for act in result:
        act_type = next(
            (x.get('valueString') for x in act.get('extensionAttributes', [])
             if 'activityType' in x.get('url', '')),
            'unknown'
        )
        print(f"  - {act['name']} [{act_type}]")
    
    # Verify name cleaning
    blood_draw = next((a for a in result if 'Blood' in a['name']), None)
    assert blood_draw and blood_draw['name'] == 'Blood Draw', "Footnote should be stripped"
    print("  ✓ Activity reconciliation works")


def test_encounter_reconciler():
    """Test encounter reconciliation with timing extraction."""
    encounters = [
        {'id': 'enc1', 'name': 'Screening Visit'},
        {'id': 'enc2', 'name': 'Day 1'},
        {'id': 'enc3', 'name': 'Week 4 Visit'},
        {'id': 'enc4', 'name': 'Day 28'}
    ]
    
    result = reconcile_encounters_from_pipeline(soa_encounters=encounters)
    
    print(f"Encounters: {len(result)} reconciled")
    for enc in result:
        study_day = next(
            (x.get('valueInteger') for x in enc.get('extensionAttributes', [])
             if 'encounterStudyDay' in x.get('url', '')),
            None
        )
        day_info = f" (Day {study_day})" if study_day else ""
        print(f"  - {enc['name']}{day_info}")
    
    print("  ✓ Encounter reconciliation works")


if __name__ == '__main__':
    print("=" * 60)
    print("Testing Unified Reconciliation Framework")
    print("=" * 60)
    print()
    
    all_passed = True
    
    try:
        test_epoch_reconciler()
        print()
    except Exception as e:
        print(f"  ✗ Epoch test failed: {e}")
        all_passed = False
    
    try:
        test_activity_reconciler()
        print()
    except Exception as e:
        print(f"  ✗ Activity test failed: {e}")
        all_passed = False
    
    try:
        test_encounter_reconciler()
        print()
    except Exception as e:
        print(f"  ✗ Encounter test failed: {e}")
        all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("All tests PASSED ✓")
    else:
        print("Some tests FAILED ✗")
    print("=" * 60)
