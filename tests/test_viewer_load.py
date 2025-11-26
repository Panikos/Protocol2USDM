#!/usr/bin/env python3
"""Test script for Streamlit viewer data loading."""

import sys
sys.path.insert(0, '.')
from soa_streamlit_viewer import get_file_inventory, get_timeline

def test_viewer_loading(output_dir):
    """Test that viewer can load and parse output files."""
    print(f"Testing viewer with: {output_dir}")
    print("=" * 50)
    
    # Test file inventory
    inventory = get_file_inventory(output_dir)
    
    print("\n=== File Inventory ===")
    print(f"Final SoA found: {inventory['final_soa'] is not None}")
    
    if inventory['final_soa']:
        print(f"  Display name: {inventory['final_soa']['display_name']}")
    
    print(f"\nPrimary outputs: {list(inventory['primary_outputs'].keys())}")
    print(f"Post-processed: {list(inventory['post_processed'].keys())}")
    print(f"Intermediate data: {list(inventory['intermediate_data'].keys())}")
    print(f"Config files: {list(inventory['configs'].keys())}")
    print(f"Images found: {len(inventory['images'])}")
    
    # Test timeline extraction
    if inventory['final_soa']:
        content = inventory['final_soa']['content']
        timeline = get_timeline(content)
        
        print("\n=== Timeline Contents ===")
        if timeline:
            print(f"Activities: {len(timeline.get('activities', []))}")
            print(f"PlannedTimepoints: {len(timeline.get('plannedTimepoints', []))}")
            print(f"Encounters: {len(timeline.get('encounters', []))}")
            print(f"Epochs: {len(timeline.get('epochs', []))}")
            print(f"ActivityGroups: {len(timeline.get('activityGroups', []))}")
            print(f"ActivityTimepoints: {len(timeline.get('activityTimepoints', []))}")
        else:
            print("ERROR: Could not extract timeline!")
        
        # Check provenance
        print("\n=== Provenance ===")
        if 'p2uProvenance' in content:
            prov = content['p2uProvenance']
            print(f"Provenance attached: Yes")
            print(f"  Keys: {list(prov.keys())}")
            if 'activities' in prov:
                print(f"  Activity sources: {len(prov.get('activities', {}))}")
            if 'activityTimepoints' in prov:
                print(f"  Cell-level provenance: {len(prov.get('activityTimepoints', {}))}")
        else:
            print("Provenance attached: No")
    
    print("\n" + "=" * 50)
    print("Test complete!")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_viewer_loading(sys.argv[1])
    else:
        # Test all available outputs
        test_dirs = [
            "output/EliLilly_GPT51_test",
            "output/EliLilly_Gemini_test",
            "output/CDISC_Pilot_Study",
        ]
        
        for test_dir in test_dirs:
            import os
            if os.path.exists(test_dir):
                test_viewer_loading(test_dir)
                print("\n")
