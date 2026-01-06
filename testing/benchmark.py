#!/usr/bin/env python3
"""
Comprehensive USDM Benchmark Tool

Compares extracted USDM output against golden standard files with:
- Per-entity precision, recall, and F1 scores
- Semantic matching with configurable thresholds
- Support for all USDM 4.0 entities including execution model
- JSON and human-readable reports
- Automatic path detection for timestamped outputs

Usage:
    python testing/benchmark.py <golden_file> <extracted_file_or_dir>
    python testing/benchmark.py input/Alexion_NCT04573309_Wilsons_golden.json output/Alexion_NCT04573309_Wilsons_20260102_221333/
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# =============================================================================
# Configuration
# =============================================================================

SIMILARITY_THRESHOLD = 0.70  # Minimum similarity for a match (lowered for semantic matching)
SUBSTRING_MIN_LENGTH = 8    # Minimum length for substring matching
KEYWORD_MATCH_BONUS = 0.25  # Bonus for keyword overlap


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class EntityMatch:
    """Represents a match between golden and extracted entities."""
    golden_id: str
    golden_value: str
    extracted_id: Optional[str]
    extracted_value: Optional[str]
    similarity: float
    matched: bool


@dataclass
class EntityMetrics:
    """Metrics for a single entity type."""
    entity_type: str
    golden_count: int
    extracted_count: int
    true_positives: int
    matches: List[EntityMatch] = field(default_factory=list)
    unmatched_golden: List[Dict] = field(default_factory=list)
    unmatched_extracted: List[Dict] = field(default_factory=list)
    
    @property
    def precision(self) -> float:
        if self.extracted_count == 0:
            return 0.0
        return self.true_positives / self.extracted_count
    
    @property
    def recall(self) -> float:
        if self.golden_count == 0:
            return 1.0  # All extracted are correct if golden is empty
        return self.true_positives / self.golden_count
    
    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)


@dataclass
class BenchmarkResult:
    """Complete benchmark result."""
    golden_file: str
    extracted_file: str
    timestamp: str
    entity_metrics: Dict[str, EntityMetrics] = field(default_factory=dict)
    validation_status: Optional[Dict] = None
    
    @property
    def overall_f1(self) -> float:
        if not self.entity_metrics:
            return 0.0
        scores = [m.f1 for m in self.entity_metrics.values() if m.golden_count > 0]
        return sum(scores) / len(scores) if scores else 0.0


# =============================================================================
# Utility Functions
# =============================================================================

def load_json(path: Path) -> Dict:
    """Load JSON file with error handling."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load {path}: {e}")
        return {}


def normalize_text(text: Any) -> str:
    """Normalize text for comparison."""
    if text is None:
        return ""
    s = str(text).strip().lower()
    # Normalize common placeholders
    if s in ['tbd', '-', 'n/a', 'none', 'unknown', '']:
        return ""
    # Remove extra whitespace
    s = re.sub(r'\s+', ' ', s)
    return s


def similarity(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings."""
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)
    
    # Both empty = perfect match
    if not a_norm and not b_norm:
        return 1.0
    # One empty = no match
    if not a_norm or not b_norm:
        return 0.0
    # Exact match
    if a_norm == b_norm:
        return 1.0
    
    # Sequence matcher similarity
    seq_ratio = SequenceMatcher(None, a_norm, b_norm).ratio()
    
    # Bonus for substring containment
    if len(a_norm) >= SUBSTRING_MIN_LENGTH and len(b_norm) >= SUBSTRING_MIN_LENGTH:
        if a_norm in b_norm or b_norm in a_norm:
            seq_ratio = max(seq_ratio, 0.85)
    
    # Bonus for keyword overlap (important for semantic matching)
    a_words = set(a_norm.split())
    b_words = set(b_norm.split())
    if a_words and b_words:
        overlap = len(a_words & b_words)
        total = min(len(a_words), len(b_words))
        if total > 0 and overlap / total >= 0.5:
            seq_ratio = max(seq_ratio, 0.6 + (overlap / total) * 0.3)
    
    return seq_ratio


def extract_text_value(entity: Dict, keys: List[str] = None) -> str:
    """Extract the primary text value from an entity."""
    if keys is None:
        keys = ['text', 'name', 'label', 'description', 'decode']
    
    for key in keys:
        if key in entity and entity[key]:
            return str(entity[key])
    
    # Fallback to string representation
    return str(entity)


def find_best_match(
    target: Dict,
    candidates: List[Dict],
    used_indices: Set[int],
    text_keys: List[str] = None,
    entity_type: str = None
) -> Tuple[Optional[int], Optional[Dict], float]:
    """Find the best matching candidate for a target entity."""
    best_idx = None
    best_match = None
    best_score = 0.0
    
    for i, candidate in enumerate(candidates):
        if i in used_indices:
            continue
        
        score = compute_entity_similarity(target, candidate, text_keys, entity_type)
        
        if score > best_score:
            best_score = score
            best_idx = i
            best_match = candidate
    
    return best_idx, best_match, best_score


def compute_entity_similarity(
    target: Dict,
    candidate: Dict,
    text_keys: List[str] = None,
    entity_type: str = None
) -> float:
    """Compute similarity between entities with type-specific strategies."""
    
    # Entity-specific matching strategies
    if entity_type == 'eligibilityCriteria':
        # Match by identifier (criterion number) + category
        t_id = target.get('identifier', '')
        c_id = candidate.get('identifier', '')
        if t_id and c_id and t_id == c_id:
            # Same identifier = match, verify category
            t_cat = target.get('category', {}).get('decode', '')
            c_cat = candidate.get('category', {}).get('decode', '')
            if normalize_text(t_cat) == normalize_text(c_cat):
                return 1.0
            return 0.9  # Same identifier, different category
        return 0.0  # Different identifiers
    
    elif entity_type == 'encounters':
        # Match by extracting day numbers and keywords
        t_name = normalize_text(target.get('name', '') + ' ' + target.get('label', ''))
        c_name = normalize_text(candidate.get('name', ''))
        
        # Extract day numbers (e.g., "Day -21" -> -21)
        t_days = set(re.findall(r'day\s*(-?\d+)', t_name))
        c_days = set(re.findall(r'(-?\d+)', c_name))
        if t_days and c_days and t_days & c_days:
            return 0.9  # Same day reference
        
        # Check for keyword match (screening, baseline, etc.)
        keywords = ['screening', 'baseline', 'treatment', 'follow', 'end', 'visit']
        for kw in keywords:
            if kw in t_name and kw in c_name:
                return 0.8
        
        return similarity(t_name, c_name)
    
    elif entity_type == 'epochs':
        # Match by name keywords - normalize heavily
        t_name = normalize_text(target.get('name', '') + ' ' + target.get('label', ''))
        c_name = normalize_text(candidate.get('name', ''))
        
        # Remove trailing letters/annotations (e.g., "screening a" -> "screening")
        t_clean = re.sub(r'\s+[a-z]$', '', t_name).strip()
        c_clean = re.sub(r'\s+[a-z]$', '', c_name).strip()
        
        # Check for exact keyword match after cleaning
        keywords = ['screening', 'treatment', 'follow', 'baseline', 'washout', 'titration', 'inpatient', 'outpatient']
        for kw in keywords:
            if kw in t_clean and kw in c_clean:
                return 0.85
        
        # Check if one starts with the other
        if t_clean.startswith(c_clean) or c_clean.startswith(t_clean):
            return 0.8
        
        # Map abbreviations
        abbrev_map = {
            'check in': ['c-i', 'checkin', 'check-in'],
            'follow-up': ['follow up', 'followup', 'eos', 'end of study'],
            'treatment': ['inpatient', 'op', 'outpatient'],
        }
        for full, abbrevs in abbrev_map.items():
            if full in t_clean:
                for abbr in abbrevs:
                    if abbr in c_clean:
                        return 0.8
        
        return similarity(t_clean, c_clean)
    
    elif entity_type == 'studyArms':
        # Match by description keywords and dose numbers
        t_text = normalize_text(target.get('description', '') + ' ' + target.get('name', '') + ' ' + target.get('label', ''))
        c_text = normalize_text(candidate.get('description', '') + ' ' + candidate.get('name', ''))
        
        # Extract dose numbers (e.g., "15mg" -> 15, "30 mg/day" -> 30)
        t_doses = set(re.findall(r'(\d+)\s*mg', t_text))
        c_doses = set(re.findall(r'(\d+)\s*mg', c_text))
        if t_doses and c_doses and len(t_doses & c_doses) >= 2:
            return 0.95  # Multiple matching doses = strong match
        if t_doses and c_doses and t_doses & c_doses:
            return 0.85  # At least one matching dose
        
        # Check for treatment keyword
        if 'treatment' in t_text and 'treatment' in c_text:
            return 0.8
        
        # Check type codes
        t_type = target.get('type', {}).get('decode', '')
        c_type = candidate.get('type', {}).get('decode', '')
        if t_type and c_type:
            # Both are arm types
            if 'arm' in normalize_text(t_type) and 'arm' in normalize_text(c_type):
                return 0.75
        
        return similarity(t_text, c_text)
    
    elif entity_type == 'indications':
        # Match by name/description containing disease terms
        t_text = normalize_text(target.get('name', '') + ' ' + target.get('description', ''))
        c_text = normalize_text(candidate.get('name', '') + ' ' + candidate.get('description', ''))
        
        # Extract disease keywords
        disease_terms = ['wilson', 'diabetes', 'cancer', 'disease', 'syndrome', 'disorder']
        for term in disease_terms:
            if term in t_text and term in c_text:
                return 0.85
        
        return similarity(t_text, c_text)
    
    elif entity_type == 'timings':
        # Match by value (ISO 8601 duration) and label/valueLabel
        t_value = target.get('value', '')
        c_value = candidate.get('value', '')
        
        # Exact value match = strong match
        if t_value and c_value and t_value == c_value:
            return 0.9
        
        # Match by valueLabel (e.g., "42 Days" vs "Day 42")
        t_label = normalize_text(target.get('valueLabel', '') + ' ' + target.get('label', ''))
        c_label = normalize_text(candidate.get('valueLabel', '') + ' ' + candidate.get('label', ''))
        
        # Extract day numbers
        t_days = set(re.findall(r'(\d+)', t_label))
        c_days = set(re.findall(r'(\d+)', c_label))
        if t_days and c_days and t_days & c_days:
            return 0.8
        
        # Match by keywords
        keywords = ['screening', 'baseline', 'treatment', 'follow', 'end', 'visit', 'day']
        for kw in keywords:
            if kw in t_label and kw in c_label:
                return 0.75
        
        return similarity(t_label, c_label)
    
    elif entity_type == 'abbreviations':
        # Match by abbreviatedText or expandedText
        t_abbr = normalize_text(target.get('abbreviatedText', ''))
        c_abbr = normalize_text(candidate.get('abbreviatedText', ''))
        
        # Exact abbreviation match
        if t_abbr and c_abbr and t_abbr == c_abbr:
            return 1.0
        
        # Match expanded text
        t_exp = normalize_text(target.get('expandedText', ''))
        c_exp = normalize_text(candidate.get('expandedText', ''))
        if t_exp and c_exp:
            return similarity(t_exp, c_exp)
        
        return similarity(t_abbr, c_abbr)
    
    # Default: use text-based similarity
    target_text = extract_text_value(target, text_keys)
    candidate_text = extract_text_value(candidate, text_keys)
    return similarity(target_text, candidate_text)


# =============================================================================
# USDM Entity Extractors
# =============================================================================

def get_study_version(data: Dict) -> Dict:
    """Get the first study version from USDM data."""
    study = data.get('study', data)
    versions = study.get('versions', [])
    return versions[0] if versions else {}


def get_study_design(data: Dict) -> Dict:
    """Get the first study design from USDM data."""
    version = get_study_version(data)
    designs = version.get('studyDesigns', [])
    return designs[0] if designs else {}


def extract_entities(data: Dict) -> Dict[str, List[Dict]]:
    """Extract all comparable entities from USDM data structure."""
    version = get_study_version(data)
    design = get_study_design(data)
    
    entities = {
        # Study Version level
        'studyIdentifiers': version.get('studyIdentifiers', []),
        'studyTitles': version.get('titles', version.get('studyTitles', [])),
        'eligibilityCriteria': design.get('eligibilityCriteria', []),
        'eligibilityCriterionItems': version.get('eligibilityCriterionItems', []),
        'studyAmendments': version.get('studyAmendments', version.get('amendments', [])),
        'analysisPopulations': version.get('analysisPopulations', []),
        
        # Study Design level
        'objectives': design.get('objectives', []),
        'endpoints': [],  # Extract from objectives
        'studyArms': design.get('studyArms', design.get('arms', [])),
        'epochs': design.get('epochs', []),
        'encounters': design.get('encounters', []),
        'activities': design.get('activities', []),
        'studyInterventions': design.get('studyInterventions', []),
        'administrableProducts': version.get('administrableProducts', []),
        'studyCells': design.get('studyCells', []),
        'scheduleTimelines': design.get('scheduleTimelines', []),
        
        # Execution model entities
        'timings': design.get('timings', []),
        'conditions': design.get('conditions', []),
        
        # Narrative/supporting entities
        'abbreviations': version.get('abbreviations', data.get('abbreviations', [])),
        'procedures': version.get('procedures', design.get('procedures', [])),
        'biomedicalConcepts': design.get('biomedicalConcepts', []),
        
        # Population
        'population': [design.get('population')] if design.get('population') else [],
        'indications': design.get('indications', []),
    }
    
    # Extract endpoints - first from top-level, then from objectives
    entities['endpoints'] = design.get('endpoints', []).copy()
    for obj in design.get('objectives', []):
        for ep in obj.get('endpoints', []):
            entities['endpoints'].append(ep)
    
    # Extract timings from scheduleTimelines
    for timeline in design.get('scheduleTimelines', []):
        for timing in timeline.get('timings', []):
            entities['timings'].append(timing)
    
    return entities


# =============================================================================
# Comparison Logic
# =============================================================================

def compare_entity_lists(
    entity_type: str,
    golden_list: List[Dict],
    extracted_list: List[Dict],
    text_keys: List[str] = None
) -> EntityMetrics:
    """Compare two lists of entities and compute metrics."""
    metrics = EntityMetrics(
        entity_type=entity_type,
        golden_count=len(golden_list),
        extracted_count=len(extracted_list),
        true_positives=0
    )
    
    used_extracted = set()
    
    # Match golden entities to extracted
    for g_entity in golden_list:
        g_id = g_entity.get('id', '')
        g_text = extract_text_value(g_entity, text_keys)
        
        idx, match, score = find_best_match(
            g_entity, extracted_list, used_extracted, text_keys, entity_type
        )
        
        if idx is not None and score >= SIMILARITY_THRESHOLD:
            used_extracted.add(idx)
            metrics.true_positives += 1
            metrics.matches.append(EntityMatch(
                golden_id=g_id,
                golden_value=g_text,
                extracted_id=match.get('id', ''),
                extracted_value=extract_text_value(match, text_keys),
                similarity=score,
                matched=True
            ))
        else:
            metrics.unmatched_golden.append(g_entity)
            metrics.matches.append(EntityMatch(
                golden_id=g_id,
                golden_value=g_text,
                extracted_id=None,
                extracted_value=None,
                similarity=score if idx is not None else 0.0,
                matched=False
            ))
    
    # Record unmatched extracted entities
    for i, e_entity in enumerate(extracted_list):
        if i not in used_extracted:
            metrics.unmatched_extracted.append(e_entity)
    
    return metrics


def run_benchmark(golden_path: Path, extracted_path: Path) -> BenchmarkResult:
    """Run full benchmark comparison."""
    result = BenchmarkResult(
        golden_file=str(golden_path),
        extracted_file=str(extracted_path),
        timestamp=datetime.now().isoformat()
    )
    
    # Load data
    golden_data = load_json(golden_path)
    extracted_data = load_json(extracted_path)
    
    if not golden_data:
        print(f"Error: Could not load golden file: {golden_path}")
        return result
    
    if not extracted_data:
        print(f"Error: Could not load extracted file: {extracted_path}")
        return result
    
    # Extract entities
    golden_entities = extract_entities(golden_data)
    extracted_entities = extract_entities(extracted_data)
    
    # Compare each entity type
    entity_configs = {
        'studyIdentifiers': ['text', 'studyIdentifier'],
        'studyTitles': ['text', 'title'],
        'eligibilityCriteria': ['text', 'name', 'description'],
        'eligibilityCriterionItems': ['text', 'description'],
        'objectives': ['text', 'name', 'description'],
        'endpoints': ['text', 'name', 'description'],
        'studyArms': ['name', 'description', 'label'],
        'epochs': ['name', 'label'],
        'encounters': ['name', 'label'],
        'activities': ['name', 'label', 'description'],
        'studyInterventions': ['name', 'description'],
        'administrableProducts': ['name', 'description'],
        'studyAmendments': ['number', 'summary'],
        'analysisPopulations': ['name', 'text', 'description'],
        'abbreviations': ['abbreviatedText', 'expandedText'],
        'procedures': ['name', 'description'],
        'timings': ['name', 'label', 'valueLabel'],
        'indications': ['name', 'description'],
    }
    
    for entity_type, text_keys in entity_configs.items():
        g_list = golden_entities.get(entity_type, [])
        e_list = extracted_entities.get(entity_type, [])
        
        # Skip if both are empty
        if not g_list and not e_list:
            continue
        
        metrics = compare_entity_lists(entity_type, g_list, e_list, text_keys)
        result.entity_metrics[entity_type] = metrics
    
    # Load validation status if available
    validation_path = extracted_path.parent / 'usdm_validation.json'
    if validation_path.exists():
        result.validation_status = load_json(validation_path)
    
    return result


# =============================================================================
# Reporting
# =============================================================================

def print_report(result: BenchmarkResult, verbose: bool = False):
    """Print human-readable benchmark report."""
    print("\n" + "=" * 80)
    print("  USDM BENCHMARK REPORT")
    print("=" * 80)
    print(f"  Golden:    {result.golden_file}")
    print(f"  Extracted: {result.extracted_file}")
    print(f"  Timestamp: {result.timestamp}")
    print()
    
    # Summary table
    print("  ENTITY METRICS")
    print("  " + "-" * 76)
    print(f"  {'Entity':<28} {'Golden':>7} {'Extracted':>10} {'TP':>5} {'Prec':>7} {'Recall':>7} {'F1':>7}")
    print("  " + "-" * 76)
    
    total_golden = 0
    total_extracted = 0
    total_tp = 0
    
    for entity_type, metrics in sorted(result.entity_metrics.items()):
        if metrics.golden_count == 0 and metrics.extracted_count == 0:
            continue
        
        total_golden += metrics.golden_count
        total_extracted += metrics.extracted_count
        total_tp += metrics.true_positives
        
        status = "✅" if metrics.f1 >= 0.8 else "⚠️" if metrics.f1 >= 0.5 else "❌"
        
        print(f"  {entity_type:<28} {metrics.golden_count:>7} {metrics.extracted_count:>10} "
              f"{metrics.true_positives:>5} {metrics.precision:>6.1%} {metrics.recall:>6.1%} "
              f"{metrics.f1:>6.1%} {status}")
    
    print("  " + "-" * 76)
    
    # Overall metrics
    overall_prec = total_tp / total_extracted if total_extracted > 0 else 0
    overall_recall = total_tp / total_golden if total_golden > 0 else 0
    overall_f1 = 2 * overall_prec * overall_recall / (overall_prec + overall_recall) if (overall_prec + overall_recall) > 0 else 0
    
    print(f"  {'OVERALL':<28} {total_golden:>7} {total_extracted:>10} "
          f"{total_tp:>5} {overall_prec:>6.1%} {overall_recall:>6.1%} {overall_f1:>6.1%}")
    print()
    
    # Validation status
    if result.validation_status:
        errors = result.validation_status.get('errors', [])
        print(f"  Validation: {'✅ PASSED' if len(errors) == 0 else f'❌ {len(errors)} errors'}")
    
    print()
    
    # Verbose output - show unmatched entities
    if verbose:
        print("  DETAILED MATCHES")
        print("  " + "-" * 76)
        
        for entity_type, metrics in sorted(result.entity_metrics.items()):
            if metrics.unmatched_golden or metrics.unmatched_extracted:
                print(f"\n  {entity_type}:")
                
                if metrics.unmatched_golden:
                    print(f"    Missing from extracted ({len(metrics.unmatched_golden)}):")
                    for entity in metrics.unmatched_golden[:5]:
                        text = extract_text_value(entity)[:60]
                        print(f"      - {text}")
                    if len(metrics.unmatched_golden) > 5:
                        print(f"      ... and {len(metrics.unmatched_golden) - 5} more")
                
                if metrics.unmatched_extracted:
                    print(f"    Extra in extracted ({len(metrics.unmatched_extracted)}):")
                    for entity in metrics.unmatched_extracted[:5]:
                        text = extract_text_value(entity)[:60]
                        print(f"      + {text}")
                    if len(metrics.unmatched_extracted) > 5:
                        print(f"      ... and {len(metrics.unmatched_extracted) - 5} more")
    
    # Summary grade
    print("=" * 80)
    grade = "A" if overall_f1 >= 0.9 else "B" if overall_f1 >= 0.75 else "C" if overall_f1 >= 0.6 else "D" if overall_f1 >= 0.4 else "F"
    print(f"  OVERALL GRADE: {grade} ({overall_f1:.1%} F1)")
    print("=" * 80)


def save_json_report(result: BenchmarkResult, output_path: Path):
    """Save benchmark result as JSON."""
    report = {
        'golden_file': result.golden_file,
        'extracted_file': result.extracted_file,
        'timestamp': result.timestamp,
        'overall_f1': result.overall_f1,
        'validation_status': result.validation_status,
        'entity_metrics': {}
    }
    
    for entity_type, metrics in result.entity_metrics.items():
        report['entity_metrics'][entity_type] = {
            'golden_count': metrics.golden_count,
            'extracted_count': metrics.extracted_count,
            'true_positives': metrics.true_positives,
            'precision': metrics.precision,
            'recall': metrics.recall,
            'f1': metrics.f1,
            'unmatched_golden_count': len(metrics.unmatched_golden),
            'unmatched_extracted_count': len(metrics.unmatched_extracted),
        }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    
    print(f"  JSON report saved to: {output_path}")


# =============================================================================
# Main Entry Point
# =============================================================================

def find_protocol_usdm(path: Path) -> Path:
    """Find protocol_usdm.json in a directory or return the path if it's a file."""
    if path.is_file():
        return path
    
    # Look for protocol_usdm.json
    usdm_file = path / 'protocol_usdm.json'
    if usdm_file.exists():
        return usdm_file
    
    # Look for timestamped subdirectories
    subdirs = sorted([d for d in path.iterdir() if d.is_dir()], reverse=True)
    for subdir in subdirs:
        usdm_file = subdir / 'protocol_usdm.json'
        if usdm_file.exists():
            return usdm_file
    
    raise FileNotFoundError(f"Could not find protocol_usdm.json in {path}")


def main():
    parser = argparse.ArgumentParser(
        description='Benchmark extracted USDM against golden standard',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python testing/benchmark.py input/Alexion_golden.json output/Alexion_20260102/
  python testing/benchmark.py golden.json extracted.json --verbose
  python testing/benchmark.py golden.json output/ --output benchmark_report.json
        """
    )
    
    parser.add_argument('golden', type=Path, help='Path to golden standard JSON file')
    parser.add_argument('extracted', type=Path, help='Path to extracted USDM file or directory')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed matches')
    parser.add_argument('-o', '--output', type=Path, help='Save JSON report to file')
    parser.add_argument('--threshold', type=float, default=0.75, 
                        help='Similarity threshold for matching (default: 0.75)')
    
    args = parser.parse_args()
    
    # Set threshold
    global SIMILARITY_THRESHOLD
    SIMILARITY_THRESHOLD = args.threshold
    
    # Validate paths
    if not args.golden.exists():
        print(f"Error: Golden file not found: {args.golden}")
        sys.exit(1)
    
    try:
        extracted_path = find_protocol_usdm(args.extracted)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Run benchmark
    print(f"\nRunning benchmark...")
    print(f"  Golden:    {args.golden}")
    print(f"  Extracted: {extracted_path}")
    
    result = run_benchmark(args.golden, extracted_path)
    
    # Print report
    print_report(result, verbose=args.verbose)
    
    # Save JSON report if requested
    if args.output:
        save_json_report(result, args.output)
    else:
        # Auto-save to extracted directory
        report_path = extracted_path.parent / 'benchmark_report.json'
        save_json_report(result, report_path)
    
    # Exit with appropriate code
    sys.exit(0 if result.overall_f1 >= 0.5 else 1)


if __name__ == '__main__':
    main()
