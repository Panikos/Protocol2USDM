import json
import os
import re

# Simple dictionary mapping Activity Name keywords to Biomedical Concept Data
# In a production pipeline, this would query a CPT/CDISC API or use an LLM RAG.
CONCEPT_MAP = {
    "vital": {
        "id": "BC_VITALS",
        "name": "Vital Signs",
        "code": "C25298",
        "codeSystem": "CDISC"
    },
    "ecg": {
        "id": "BC_ECG",
        "name": "Electrocardiogram",
        "code": "C16236",
        "codeSystem": "CDISC"
    },
    "physical exam": {
        "id": "BC_PE",
        "name": "Physical Examination",
        "code": "C51984",
        "codeSystem": "CDISC"
    },
    "informed consent": {
        "id": "BC_CONSENT",
        "name": "Informed Consent",
        "code": "C16696",
        "codeSystem": "CDISC"
    },
    "hachinski": {
        "id": "BC_HACHINSKI",
        "name": "Hachinski Ischemic Scale",
        "code": "C100485",
        "codeSystem": "CDISC"
    },
    "mmse": {
        "id": "BC_MMSE",
        "name": "Mini-Mental State Examination",
        "code": "C100536",
        "codeSystem": "CDISC"
    },
    "adas": {
        "id": "BC_ADAS",
        "name": "ADAS-Cog",
        "code": "C100376",
        "codeSystem": "CDISC"
    },
    "cibic": {
        "id": "BC_CIBIC",
        "name": "CIBIC-Plus",
        "code": "C101662",
        "codeSystem": "CDISC"
    },
    "dad": {
        "id": "BC_DAD",
        "name": "Disability Assessment for Dementia",
        "code": "C101997",
        "codeSystem": "CDISC"
    },
    "laboratory": {
        "id": "BC_LABS",
        "name": "Clinical Laboratory Test",
        "code": "C25193",
        "codeSystem": "CDISC"
    },
    "urinalysis": {
        "id": "BC_URINE",
        "name": "Urinalysis",
        "code": "C25296",
        "codeSystem": "CDISC"
    },
    "randomis": {
        "id": "BC_RANDOM",
        "name": "Randomization",
        "code": "C15379",
        "codeSystem": "CDISC"
    }
}

def main():
    path = r"output\CDISC_Pilot_Study\9_reconciled_soa.json"
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    study = data.get('study', {})
    versions = study.get('versions', [])
    if not versions: return
    v1 = versions[0]
    designs = v1.get('studyDesigns', [])
    if not designs: 
        print("No studyDesigns found. Run align_structure.py first.")
        return
    design = designs[0]
    
    activities = design.get('activities', [])
    
    # Track unique concepts to add to StudyVersion
    concepts_to_add = {}
    
    updated_count = 0
    for act in activities:
        name = act.get('name', '').lower()
        
        # Find matches
        matched_bc = None
        for key, val in CONCEPT_MAP.items():
            if key in name:
                matched_bc = val
                break
        
        if matched_bc:
            # Add reference to activity
            act['biomedicalConceptIds'] = [matched_bc['id']]
            
            # Add to pool
            if matched_bc['id'] not in concepts_to_add:
                concepts_to_add[matched_bc['id']] = matched_bc
            updated_count += 1
            
    # Create BiomedicalConcept objects
    bc_objects = []
    for bc_id, info in concepts_to_add.items():
        bc_objects.append({
            "id": bc_id,
            "instanceType": "BiomedicalConcept",
            "name": info['name'],
            "label": info['name'],
            "synonyms": [],
            "reference": {
                "id": f"Code_{bc_id}",
                "code": info['code'],
                "codeSystem": info['codeSystem'],
                "decode": info['name'],
                "instanceType": "Code"
            }
        })
        
    # Add to Version
    v1['biomedicalConcepts'] = bc_objects
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        
    print(f"Enriched {updated_count} activities with {len(bc_objects)} Biomedical Concepts.")
    print(f"Saved to {path}")

if __name__ == "__main__":
    main()
