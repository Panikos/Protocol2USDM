"""
Superscript Extraction and Normalization Utilities

Gemini 3 extracts superscript footnote references embedded in entity names.
This is valuable data but causes downstream matching issues.

This module:
1. Extracts superscripts from names (e.g., "UNS¹ EOS or ETᵃ" → "UNS EOS or ET", ["1", "a"])
2. Normalizes different superscript representations
3. Provides clean names for matching while preserving footnote references

Unicode superscripts mapping:
- ⁰¹²³⁴⁵⁶⁷⁸⁹ → 0123456789
- ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ → abcdefghijklmnoprstuvwxyz
"""

import re
from typing import Tuple, List, Optional
from dataclasses import dataclass

# Unicode superscript mappings
SUPERSCRIPT_MAP = {
    # Numbers
    '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
    '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
    # Lowercase letters
    'ᵃ': 'a', 'ᵇ': 'b', 'ᶜ': 'c', 'ᵈ': 'd', 'ᵉ': 'e',
    'ᶠ': 'f', 'ᵍ': 'g', 'ʰ': 'h', 'ⁱ': 'i', 'ʲ': 'j',
    'ᵏ': 'k', 'ˡ': 'l', 'ᵐ': 'm', 'ⁿ': 'n', 'ᵒ': 'o',
    'ᵖ': 'p', 'ʳ': 'r', 'ˢ': 's', 'ᵗ': 't', 'ᵘ': 'u',
    'ᵛ': 'v', 'ʷ': 'w', 'ˣ': 'x', 'ʸ': 'y', 'ᶻ': 'z',
    # Common symbols
    '†': 'dagger', '‡': 'double_dagger', '§': 'section',
    '*': 'asterisk', '※': 'reference',
}

# Reverse map for detection
SUPERSCRIPT_CHARS = set(SUPERSCRIPT_MAP.keys())

# Pattern for trailing lowercase letters that might be footnote refs (e.g., "unitf" → "unit", "f")
# Only match single letters at end of word that look like footnote refs
TRAILING_LETTER_PATTERN = re.compile(r'^(.+?)([a-z])$')


@dataclass
class SuperscriptResult:
    """Result of superscript extraction."""
    clean_name: str
    footnote_refs: List[str]
    original_name: str
    had_superscripts: bool


def extract_superscripts(name: str) -> SuperscriptResult:
    """
    Extract superscript footnote references from a name.
    
    Args:
        name: Entity name potentially containing superscripts
        
    Returns:
        SuperscriptResult with clean name and extracted footnote references
        
    Examples:
        "UNS¹ EOS or ETᵃ" → clean="UNS EOS or ET", refs=["1", "a"]
        "Discharge from unitᶠ" → clean="Discharge from unit", refs=["f"]
        "Physical examination" → clean="Physical examination", refs=[]
    """
    if not name:
        return SuperscriptResult(
            clean_name="",
            footnote_refs=[],
            original_name=name,
            had_superscripts=False
        )
    
    clean_chars = []
    footnote_refs = []
    had_superscripts = False
    
    i = 0
    while i < len(name):
        char = name[i]
        
        if char in SUPERSCRIPT_CHARS:
            # Found a superscript character
            had_superscripts = True
            ref = SUPERSCRIPT_MAP[char]
            footnote_refs.append(ref)
            # Don't add to clean_chars
        else:
            clean_chars.append(char)
        
        i += 1
    
    clean_name = ''.join(clean_chars).strip()
    
    # NOTE: We do NOT try to detect trailing regular letters as footnote refs
    # This is too error-prone (e.g., "examination" → "examinatio" + "n")
    # The LLM should extract proper unicode superscripts (ᵃᵇᶜ etc.)
    # If it doesn't, that's a prompt issue to fix upstream
    
    return SuperscriptResult(
        clean_name=clean_name,
        footnote_refs=footnote_refs,
        original_name=name,
        had_superscripts=had_superscripts
    )


def normalize_name_for_matching(name: str) -> str:
    """
    Get a normalized name suitable for fuzzy matching.
    
    Removes superscripts and normalizes whitespace/case.
    
    Args:
        name: Entity name
        
    Returns:
        Normalized name for matching
    """
    result = extract_superscripts(name)
    # Normalize whitespace and lowercase for matching
    normalized = ' '.join(result.clean_name.lower().split())
    return normalized


def process_entity_names(entities: list, name_field: str = 'name') -> list:
    """
    Process a list of entities, extracting superscripts and adding footnoteRefs.
    
    Args:
        entities: List of entity dicts
        name_field: Field containing the name (default 'name')
        
    Returns:
        Entities with clean names and footnoteRefs added
    """
    for entity in entities:
        if name_field in entity:
            original = entity[name_field]
            result = extract_superscripts(original)
            
            if result.had_superscripts:
                # Store clean name
                entity[name_field] = result.clean_name
                # Preserve original with superscripts
                entity['originalName'] = original
                # Add footnote references
                if result.footnote_refs:
                    existing_refs = entity.get('footnoteRefs', [])
                    entity['footnoteRefs'] = existing_refs + result.footnote_refs
    
    return entities


def clean_epoch_names(epochs: list) -> list:
    """Clean epoch names, preserving footnote references."""
    return process_entity_names(epochs, 'name')


def clean_activity_names(activities: list) -> list:
    """Clean activity names, preserving footnote references."""
    return process_entity_names(activities, 'name')


def clean_encounter_names(encounters: list) -> list:
    """Clean encounter names, preserving footnote references."""
    return process_entity_names(encounters, 'name')


def validate_footnote_refs(entities: list, footnotes: list) -> dict:
    """
    Validate that footnote references in entities match actual footnotes.
    
    This catches vision/OCR errors where superscripts are misread
    (e.g., "d" read as "1").
    
    Args:
        entities: List of entity dicts with potential footnoteRefs
        footnotes: List of footnote strings (e.g., ["a. ...", "b. ...", "c. ..."])
        
    Returns:
        Dict with validation results and corrections
    """
    # Extract valid footnote keys from footnotes list
    valid_keys = set()
    for fn in footnotes:
        if isinstance(fn, str) and fn:
            # Extract the letter/number at start (e.g., "a." → "a")
            match = re.match(r'^([a-zA-Z0-9])[.\s)]', fn.strip())
            if match:
                valid_keys.add(match.group(1).lower())
    
    results = {
        'valid_keys': list(valid_keys),
        'invalid_refs': [],
        'corrections': [],
    }
    
    if not valid_keys:
        return results
    
    # Common OCR misreads for superscripts
    OCR_CORRECTIONS = {
        '1': ['i', 'l'],  # 1 often misread as i or l
        'l': ['1', 'i'],
        'i': ['1', 'l'],
        '0': ['o'],
        'o': ['0'],
        '5': ['s'],
        's': ['5'],
    }
    
    for entity in entities:
        refs = entity.get('footnoteRefs', [])
        corrected_refs = []
        
        for ref in refs:
            ref_lower = ref.lower()
            
            if ref_lower in valid_keys:
                # Valid reference
                corrected_refs.append(ref_lower)
            else:
                # Try to find a correction
                found_correction = False
                
                # Check OCR corrections
                if ref_lower in OCR_CORRECTIONS:
                    for possible in OCR_CORRECTIONS[ref_lower]:
                        if possible in valid_keys:
                            corrected_refs.append(possible)
                            results['corrections'].append({
                                'entity': entity.get('name', entity.get('id')),
                                'original': ref,
                                'corrected': possible,
                            })
                            found_correction = True
                            break
                
                if not found_correction:
                    results['invalid_refs'].append({
                        'entity': entity.get('name', entity.get('id')),
                        'ref': ref,
                    })
                    # Keep the original even if invalid
                    corrected_refs.append(ref_lower)
        
        if corrected_refs != refs:
            entity['footnoteRefs'] = corrected_refs
    
    return results


def normalize_soa_with_footnotes(usdm_data: dict) -> dict:
    """
    Normalize superscripts in USDM data and validate against footnotes.
    
    This is the main entry point for post-processing USDM output.
    
    Args:
        usdm_data: USDM JSON data
        
    Returns:
        Dict with normalization results
    """
    results = {
        'epochs_cleaned': 0,
        'encounters_cleaned': 0,
        'activities_cleaned': 0,
        'footnote_corrections': [],
    }
    
    try:
        sd = usdm_data.get('study', {}).get('versions', [{}])[0].get('studyDesigns', [{}])[0]
        
        # Get footnotes (stored in notes as CommentAnnotation)
        footnotes = []
        for note in sd.get('notes', []):
            if isinstance(note, dict) and note.get('text'):
                footnotes.append(note['text'])
        
        # Clean and validate epochs
        if 'epochs' in sd:
            clean_epoch_names(sd['epochs'])
            results['epochs_cleaned'] = len(sd['epochs'])
            if footnotes:
                val_result = validate_footnote_refs(sd['epochs'], footnotes)
                results['footnote_corrections'].extend(val_result.get('corrections', []))
        
        # Clean and validate encounters
        if 'encounters' in sd:
            clean_encounter_names(sd['encounters'])
            results['encounters_cleaned'] = len(sd['encounters'])
            if footnotes:
                val_result = validate_footnote_refs(sd['encounters'], footnotes)
                results['footnote_corrections'].extend(val_result.get('corrections', []))
        
        # Clean and validate activities
        if 'activities' in sd:
            clean_activity_names(sd['activities'])
            results['activities_cleaned'] = len(sd['activities'])
            if footnotes:
                val_result = validate_footnote_refs(sd['activities'], footnotes)
                results['footnote_corrections'].extend(val_result.get('corrections', []))
                
    except Exception as e:
        results['error'] = str(e)
    
    return results


# Test cases
if __name__ == "__main__":
    test_cases = [
        "UNS¹ EOS or ETᵃ",
        "Discharge from unitᶠ",
        "Physical examination",
        "Follicle-stimulating hormone (post-menopausal females onlyʰ)",
        "Medical history/demographicsⁱ",
        "WD historyʲ",
        "Prior WD treatmentʲ",
        "Screening",
        "24-hour urine for Cu and Moⁿ",
        "Feces for Cu and Moᵒ",
    ]
    
    print("Superscript Extraction Tests:")
    print("-" * 60)
    for name in test_cases:
        result = extract_superscripts(name)
        print(f"Original: {name}")
        print(f"  Clean:  {result.clean_name}")
        print(f"  Refs:   {result.footnote_refs}")
        print()
