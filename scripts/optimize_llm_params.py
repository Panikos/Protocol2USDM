"""
LLM Parameter Optimization Script

Tests different parameter combinations for each task type and model to find optimal settings.
Measures: JSON validity, extraction completeness, response time, cost.

Usage:
    python scripts/optimize_llm_params.py --task deterministic --model gemini-3-flash-preview
    python scripts/optimize_llm_params.py --task semantic --model claude-sonnet-4
    python scripts/optimize_llm_params.py --all  # Run full optimization suite
"""

import argparse
import json
import time
import sys
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.llm_client import get_llm_client, LLMConfig
from core.json_utils import parse_llm_json

# =============================================================================
# TEST PROMPTS FOR EACH TASK TYPE
# =============================================================================
# These are representative prompts that exercise each task type's requirements

TEST_PROMPTS = {
    "deterministic": {
        "name": "Eligibility Extraction",
        "system": "You are a clinical trial protocol expert extracting eligibility criteria.",
        "user": """Extract eligibility criteria from this protocol excerpt:

INCLUSION CRITERIA:
1. Age 18-75 years at screening
2. Confirmed diagnosis of Wilson's disease based on:
   - Serum ceruloplasmin < 20 mg/dL, AND
   - 24-hour urinary copper excretion > 100 μg/day
3. Currently on stable zinc therapy for ≥ 3 months

EXCLUSION CRITERIA:
1. ALT or AST > 5× ULN
2. Total bilirubin > 3× ULN  
3. History of hepatic decompensation
4. Pregnant or breastfeeding

Return JSON with this structure:
{
  "inclusion": [{"id": "inc_1", "text": "...", "category": "..."}],
  "exclusion": [{"id": "exc_1", "text": "...", "category": "..."}]
}""",
        "expected_keys": ["inclusion", "exclusion"],
        "min_items": {"inclusion": 3, "exclusion": 4}
    },
    
    "semantic": {
        "name": "Entity Resolution",
        "system": "You are resolving abstract visit names to actual protocol encounters.",
        "user": """Map these visit references to the closest matching encounter:

VISIT REFERENCES TO RESOLVE:
- "Baseline visit"
- "Week 4 assessment"  
- "End of treatment"

AVAILABLE ENCOUNTERS:
- enc_1: "Screening" (Day -28 to -1)
- enc_2: "Day 1/Baseline" (Day 1)
- enc_3: "Week 2" (Day 14 ±3)
- enc_4: "Week 4" (Day 28 ±3)
- enc_5: "Week 8" (Day 56 ±5)
- enc_6: "Week 12/EOT" (Day 84 ±5)
- enc_7: "Follow-up" (Day 112 ±7)

Return JSON:
{
  "mappings": [
    {"reference": "...", "encounterId": "enc_X", "confidence": 0.0-1.0, "reasoning": "..."}
  ]
}""",
        "expected_keys": ["mappings"],
        "min_items": {"mappings": 3}
    },
    
    "structured_gen": {
        "name": "State Machine Generation",
        "system": "You are generating a subject state machine for a clinical trial.",
        "user": """Generate a state machine for subject flow through this study:

STUDY PHASES:
1. Screening (up to 28 days)
2. Run-in (7 days, single-blind placebo)
3. Treatment (12 weeks, randomized)
4. Follow-up (4 weeks post-treatment)

TRANSITIONS:
- Screen fail → Exit (ineligible)
- Run-in fail → Exit (non-compliant)
- Treatment → Early termination (AE, withdrawal)
- Treatment completion → Follow-up
- Follow-up completion → Study complete

Return JSON:
{
  "states": [{"id": "...", "name": "...", "type": "initial|intermediate|terminal"}],
  "transitions": [{"from": "...", "to": "...", "trigger": "...", "condition": "..."}]
}""",
        "expected_keys": ["states", "transitions"],
        "min_items": {"states": 5, "transitions": 5}
    },
    
    "narrative": {
        "name": "Amendment Summary",
        "system": "You are summarizing protocol amendments for regulatory submission.",
        "user": """Summarize these protocol amendments:

AMENDMENT 1 (v2.0, 15-Mar-2024):
- Changed primary endpoint from Week 8 to Week 12
- Added exploratory biomarker endpoint (serum copper)
- Updated exclusion criterion: ALT/AST from 3× to 5× ULN
- Rationale: Allow more time for treatment effect, expand patient population

AMENDMENT 2 (v3.0, 01-Aug-2024):
- Added new study site in Germany
- Increased sample size from 80 to 100
- Added optional MRI substudy
- Rationale: Enhance enrollment, strengthen efficacy signal

Return JSON:
{
  "amendments": [
    {
      "version": "...",
      "date": "...",
      "changes": ["..."],
      "rationale": "...",
      "impact": "minor|moderate|substantial"
    }
  ]
}""",
        "expected_keys": ["amendments"],
        "min_items": {"amendments": 2}
    }
}

# =============================================================================
# PARAMETER SEARCH SPACE
# =============================================================================

PARAM_GRID = {
    "temperature": [0.0, 0.1, 0.2, 0.3],
    "top_p": [0.8, 0.9, 0.95, 1.0],
    "top_k": [None, 20, 40, 60],  # None = disabled
    "max_tokens": [4096, 8192, 16384],
}

# Recommended starting points per task type
TASK_BASELINES = {
    "deterministic": {"temperature": 0.0, "top_p": 0.95, "top_k": None, "max_tokens": 8192},
    "semantic": {"temperature": 0.1, "top_p": 0.9, "top_k": 40, "max_tokens": 4096},
    "structured_gen": {"temperature": 0.2, "top_p": 0.85, "top_k": 40, "max_tokens": 8192},
    "narrative": {"temperature": 0.3, "top_p": 0.9, "top_k": None, "max_tokens": 8192},
}

# Provider-specific constraints
PROVIDER_CONSTRAINTS = {
    "openai": {"top_k": None},  # OpenAI doesn't support top_k
    "claude": {"top_p_with_temp": False},  # Claude can't use both temp and top_p
    "gemini": {},  # Gemini supports all parameters
}

# =============================================================================
# TEST RESULT TRACKING
# =============================================================================

@dataclass
class TestResult:
    """Result of a single parameter test."""
    task_type: str
    model: str
    params: Dict[str, Any]
    
    # Success metrics
    json_valid: bool
    has_expected_keys: bool
    meets_min_items: bool
    
    # Quality metrics
    response_length: int
    item_counts: Dict[str, int]
    
    # Performance metrics
    latency_ms: int
    input_tokens: int
    output_tokens: int
    
    # Error info
    error: Optional[str] = None
    
    @property
    def success(self) -> bool:
        return self.json_valid and self.has_expected_keys and self.meets_min_items
    
    @property
    def score(self) -> float:
        """Composite score: success (60%) + completeness (30%) + efficiency (10%)"""
        if not self.json_valid:
            return 0.0
        
        base = 0.6 if self.success else 0.3
        
        # Completeness bonus
        completeness = 0.0
        if self.item_counts:
            total_items = sum(self.item_counts.values())
            completeness = min(0.3, total_items * 0.03)  # Up to 0.3 for 10+ items
        
        # Efficiency (prefer lower latency)
        efficiency = max(0, 0.1 - (self.latency_ms / 100000))  # Up to 0.1 for <10s
        
        return base + completeness + efficiency


def detect_provider(model_name: str) -> str:
    """Detect provider from model name."""
    model_lower = model_name.lower()
    if "gemini" in model_lower:
        return "gemini"
    elif "claude" in model_lower:
        return "claude"
    elif any(x in model_lower for x in ["gpt", "o1", "o3"]):
        return "openai"
    return "unknown"


def apply_provider_constraints(params: dict, provider: str) -> dict:
    """Apply provider-specific parameter constraints."""
    params = params.copy()
    constraints = PROVIDER_CONSTRAINTS.get(provider, {})
    
    if constraints.get("top_k") is None:
        params["top_k"] = None
    
    if not constraints.get("top_p_with_temp", True):
        # Claude: if temperature is set, don't use top_p
        if params.get("temperature", 0) > 0:
            params["top_p"] = None
    
    return params


def run_single_test(
    task_type: str,
    model: str,
    params: dict,
    num_runs: int = 1
) -> TestResult:
    """Run a single parameter configuration test."""
    test_config = TEST_PROMPTS[task_type]
    provider = detect_provider(model)
    params = apply_provider_constraints(params, provider)
    
    # Build LLM config
    config = LLMConfig(
        temperature=params.get("temperature", 0.0),
        top_p=params.get("top_p"),
        top_k=params.get("top_k"),
        max_tokens=params.get("max_tokens", 8192),
        json_mode=True,
    )
    
    try:
        client = get_llm_client(model)
        messages = [
            {"role": "system", "content": test_config["system"]},
            {"role": "user", "content": test_config["user"]}
        ]
        
        # Run test
        start = time.time()
        response = client.generate(messages, config)
        latency = int((time.time() - start) * 1000)
        
        # Parse response
        data = parse_llm_json(response.content, fallback={})
        json_valid = bool(data)
        
        # Check expected keys
        expected_keys = test_config["expected_keys"]
        has_expected_keys = all(k in data for k in expected_keys)
        
        # Check minimum items
        min_items = test_config["min_items"]
        item_counts = {}
        meets_min = True
        for key, min_count in min_items.items():
            actual = len(data.get(key, []))
            item_counts[key] = actual
            if actual < min_count:
                meets_min = False
        
        # Token usage
        usage = response.usage or {}
        
        return TestResult(
            task_type=task_type,
            model=model,
            params=params,
            json_valid=json_valid,
            has_expected_keys=has_expected_keys,
            meets_min_items=meets_min,
            response_length=len(response.content),
            item_counts=item_counts,
            latency_ms=latency,
            input_tokens=usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0),
            output_tokens=usage.get("output_tokens", 0) or usage.get("completion_tokens", 0),
        )
        
    except Exception as e:
        return TestResult(
            task_type=task_type,
            model=model,
            params=params,
            json_valid=False,
            has_expected_keys=False,
            meets_min_items=False,
            response_length=0,
            item_counts={},
            latency_ms=0,
            input_tokens=0,
            output_tokens=0,
            error=str(e),
        )


def optimize_task_type(
    task_type: str,
    model: str,
    strategy: str = "grid",  # "grid" or "bayesian"
    max_tests: int = 20,
) -> List[TestResult]:
    """
    Optimize parameters for a specific task type and model.
    
    Strategies:
    - grid: Systematic grid search with early stopping
    - bayesian: Bayesian optimization (future)
    """
    results = []
    provider = detect_provider(model)
    
    print(f"\n{'='*60}")
    print(f"Optimizing: {task_type} on {model}")
    print(f"{'='*60}")
    
    # Start with baseline
    baseline = TASK_BASELINES[task_type].copy()
    print(f"\nBaseline params: {baseline}")
    
    baseline_result = run_single_test(task_type, model, baseline)
    results.append(baseline_result)
    print(f"  Baseline: {'✓' if baseline_result.success else '✗'} (score: {baseline_result.score:.2f})")
    
    if baseline_result.error:
        print(f"  Error: {baseline_result.error}")
    
    # Grid search: vary one parameter at a time from baseline
    best_params = baseline.copy()
    best_score = baseline_result.score
    
    for param_name, values in PARAM_GRID.items():
        if len(results) >= max_tests:
            break
            
        print(f"\nTesting {param_name}...")
        
        for value in values:
            if len(results) >= max_tests:
                break
                
            # Skip if same as baseline
            if best_params.get(param_name) == value:
                continue
            
            # Skip invalid combinations
            if param_name == "top_k" and provider == "openai":
                continue
            if param_name == "top_p" and provider == "claude" and best_params.get("temperature", 0) > 0:
                continue
            
            test_params = best_params.copy()
            test_params[param_name] = value
            
            result = run_single_test(task_type, model, test_params)
            results.append(result)
            
            status = "✓" if result.success else "✗"
            print(f"  {param_name}={value}: {status} (score: {result.score:.2f}, latency: {result.latency_ms}ms)")
            
            if result.error:
                print(f"    Error: {result.error[:50]}...")
            
            # Update best if improved
            if result.score > best_score:
                best_score = result.score
                best_params[param_name] = value
                print(f"    ^ New best!")
    
    print(f"\n{'='*60}")
    print(f"Best params for {task_type} on {model}:")
    print(f"  {best_params}")
    print(f"  Score: {best_score:.2f}")
    print(f"{'='*60}")
    
    return results


def generate_config_recommendations(all_results: List[TestResult]) -> dict:
    """Generate recommended config updates based on test results."""
    recommendations = {
        "task_types": {},
        "provider_overrides": {},
        "model_overrides": {},
    }
    
    # Group results by task type and model
    by_task_model = {}
    for r in all_results:
        key = (r.task_type, r.model)
        if key not in by_task_model:
            by_task_model[key] = []
        by_task_model[key].append(r)
    
    # Find best params for each combination
    for (task_type, model), results in by_task_model.items():
        best = max(results, key=lambda r: r.score)
        provider = detect_provider(model)
        
        if best.success:
            # Add to recommendations
            if task_type not in recommendations["task_types"]:
                recommendations["task_types"][task_type] = {}
            
            if provider not in recommendations["provider_overrides"]:
                recommendations["provider_overrides"][provider] = {}
            if task_type not in recommendations["provider_overrides"][provider]:
                recommendations["provider_overrides"][provider][task_type] = {}
            
            # Recommend params that differ from baseline
            baseline = TASK_BASELINES[task_type]
            for param, value in best.params.items():
                if value != baseline.get(param):
                    recommendations["provider_overrides"][provider][task_type][param] = value
    
    return recommendations


def main():
    parser = argparse.ArgumentParser(description="Optimize LLM parameters")
    parser.add_argument("--task", choices=list(TEST_PROMPTS.keys()), help="Task type to optimize")
    parser.add_argument("--model", default="gemini-3-flash-preview", help="Model to test")
    parser.add_argument("--all", action="store_true", help="Run full optimization suite")
    parser.add_argument("--max-tests", type=int, default=15, help="Max tests per task/model")
    parser.add_argument("--output", default="optimization_results.json", help="Output file")
    args = parser.parse_args()
    
    all_results = []
    
    if args.all:
        # Full optimization: all tasks × both models
        models = ["gemini-3-flash-preview", "claude-sonnet-4"]
        tasks = list(TEST_PROMPTS.keys())
        
        for model in models:
            for task in tasks:
                results = optimize_task_type(task, model, max_tests=args.max_tests)
                all_results.extend(results)
    elif args.task:
        results = optimize_task_type(args.task, args.model, max_tests=args.max_tests)
        all_results.extend(results)
    else:
        print("Specify --task or --all")
        return
    
    # Generate recommendations
    recommendations = generate_config_recommendations(all_results)
    
    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "results": [asdict(r) for r in all_results],
        "recommendations": recommendations,
        "summary": {
            "total_tests": len(all_results),
            "successful": sum(1 for r in all_results if r.success),
            "by_task": {
                task: {
                    "tests": sum(1 for r in all_results if r.task_type == task),
                    "success_rate": sum(1 for r in all_results if r.task_type == task and r.success) / 
                                   max(1, sum(1 for r in all_results if r.task_type == task))
                }
                for task in TEST_PROMPTS.keys()
            }
        }
    }
    
    output_path = Path(args.output)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n\nResults saved to: {output_path}")
    print(f"\nRecommended config updates:")
    print(json.dumps(recommendations, indent=2))


if __name__ == "__main__":
    main()
