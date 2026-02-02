# LLM Parameter Tuning Report

**Date:** January 19, 2026  
**Protocol2USDM Version:** 6.5.0  
**Test Script:** `scripts/optimize_llm_params.py`

---

## Executive Summary

Systematic parameter optimization was performed across 4 task types and 4 LLM models to identify optimal configurations for clinical protocol extraction. **120+ individual tests** were executed with the following key findings:

- **Gemini 3 Flash**: Highly stable across all parameter variations - baseline config is optimal
- **Claude Sonnet 4**: Benefits from task-specific temperature tuning (0.1-0.3)
- **GPT 5.2**: Supports temperature (contrary to initial assumption), optimal at 0.1-0.3
- **Claude Opus 4**: Consistent performance, works well with temp=0.3

---

## Test Methodology

### Task Types Tested
| Task Type | Description | Test Prompt |
|-----------|-------------|-------------|
| **deterministic** | Factual extraction from structured content | Eligibility criteria extraction |
| **semantic** | Entity resolution and mapping | Visit reference to encounter mapping |
| **structured_gen** | Algorithm/state machine generation | Subject flow state machine |
| **narrative** | Document summarization | Protocol amendment summary |

### Parameters Tested
| Parameter | Values Tested | Notes |
|-----------|--------------|-------|
| `temperature` | 0.0, 0.1, 0.2, 0.3 | Controls randomness |
| `top_p` | 0.8, 0.9, 0.95, 1.0 | Nucleus sampling |
| `top_k` | null, 20, 40, 60 | Top-K sampling (not supported by OpenAI) |
| `max_tokens` | 4096, 8192, 16384 | Output length limit |

### Scoring Methodology
```
Score = Success Base (60%) + Completeness (30%) + Efficiency (10%)

- Success Base: 0.6 if JSON valid + expected keys + min items met
- Completeness: Up to 0.3 based on item count
- Efficiency: Up to 0.1 based on latency (<10s optimal)
```

---

## Results by Model

### Gemini 3 Flash Preview

| Task Type | Score | Best Params | Latency | Notes |
|-----------|-------|-------------|---------|-------|
| deterministic | **0.81** | baseline | 16-19s | All params work equally |
| semantic | **0.69** | baseline | 12-19s | Robust to param changes |
| structured_gen | **0.90** | baseline | 17-21s | Very stable |
| narrative | **0.66** | baseline | 14-16s | Stable |

**Key Finding:** Gemini 3 Flash is highly robust - current baseline parameters are optimal. No tuning needed.

---

### Claude Sonnet 4 (claude-sonnet-4-20250514)

| Task Type | Score | Best Params | Latency | Notes |
|-----------|-------|-------------|---------|-------|
| deterministic | **0.88** | temp=0.1, top_k=60 | 3-4s | Slight temp helps |
| semantic | **0.76** | temp=0.3 | 3-4s | Higher temp better |
| structured_gen | **0.95** | temp=0.1 | 5-6s | Lower temp optimal |
| narrative | - | - | - | Not tested |

**Key Finding:** Claude Sonnet benefits from task-specific temperature:
- Lower temp (0.1) for deterministic/structured tasks
- Higher temp (0.3) for semantic mapping

**Constraint:** Cannot use `temperature` and `top_p` together - use `top_p=null`.

---

### GPT 5.2

| Task Type | Score | Best Params | Latency | Notes |
|-----------|-------|-------------|---------|-------|
| deterministic | **0.87** | temp=0.3 | 3-6s | Higher temp improved |
| semantic | **0.77** | temp=0.3 | 2-5s | Higher temp better |
| structured_gen | **0.95** | temp=0.1 | 5-7s | Lower temp optimal |
| narrative | **0.73** | top_p=0.95 | 3-5s | Slightly higher top_p |

**Key Finding:** GPT 5.2 DOES support temperature (contrary to initial config). Optimal settings vary by task:
- Deterministic/Semantic: temp=0.3 (more flexibility helps)
- Structured gen: temp=0.1 (precision important)

---

### Claude Opus 4 (claude-opus-4-20250514)

| Task Type | Score | Best Params | Latency | Notes |
|-----------|-------|-------------|---------|-------|
| deterministic | **0.85** | temp=0.3 | 5-6s | Consistent |
| semantic | **0.75** | temp=0.3 | 4-5s | Consistent |
| structured_gen | **0.93** | temp=0.3 | 7s | Very consistent |
| narrative | - | - | - | Not tested |

**Key Finding:** Claude Opus 4 is remarkably consistent across all parameter variations. Default temp=0.3 works well for all tasks.

**Warning:** `max_tokens=16384` causes API timeout errors - keep at 8192 or below.

---

## Comparative Analysis

### Best Model by Task Type

| Task Type | Best Model | Score | Runner-up | Score |
|-----------|-----------|-------|-----------|-------|
| **deterministic** | Claude Sonnet 4 | 0.88 | GPT 5.2 | 0.87 |
| **semantic** | GPT 5.2 | 0.77 | Claude Sonnet 4 | 0.76 |
| **structured_gen** | Claude Sonnet 4 / GPT 5.2 | 0.95 | Claude Opus 4 | 0.93 |
| **narrative** | GPT 5.2 | 0.73 | Gemini 3 Flash | 0.66 |

### Cost-Performance Trade-off

| Model | Avg Score | Avg Latency | Cost (per 1M tokens) | Value Rating |
|-------|-----------|-------------|---------------------|--------------|
| Gemini 3 Flash | 0.77 | 16s | $0.075 in / $0.30 out | ⭐⭐⭐⭐⭐ Best value |
| Claude Sonnet 4 | 0.86 | 4s | $3.00 in / $15.00 out | ⭐⭐⭐⭐ Good balance |
| GPT 5.2 | 0.83 | 4s | ~$2.00 in / $10.00 out | ⭐⭐⭐⭐ Good balance |
| Claude Opus 4 | 0.84 | 6s | $15.00 in / $75.00 out | ⭐⭐ Premium |

---

## Recommended Configuration

Based on testing, the following optimized parameters have been applied to `llm_config.yaml`:

### Provider Overrides

```yaml
provider_overrides:
  openai:
    deterministic:
      temperature: 0.3   # OPTIMIZED
    semantic:
      temperature: 0.3   # OPTIMIZED
    structured_gen:
      temperature: 0.1   # OPTIMIZED
    narrative:
      top_p: 0.95        # OPTIMIZED

  gemini:
    # Baseline params optimal - no changes needed

  claude:
    deterministic:
      temperature: 0.1   # OPTIMIZED
      top_k: 60          # OPTIMIZED
    semantic:
      temperature: 0.3   # OPTIMIZED
    structured_gen:
      temperature: 0.1   # OPTIMIZED
```

### Model-Specific Overrides

```yaml
model_overrides:
  gpt-5.2: {}            # Supports temperature (verified)
  claude-opus-4:
    temperature: 0.3     # OPTIMIZED
  claude-opus-4-20250514:
    temperature: 0.3     # OPTIMIZED
```

---

## Critical Findings

### 1. max_tokens Must Be High for SoA Extraction
- **Issue:** SoA extraction with 36 activities + 200+ timepoints requires large output
- **Fix:** Increased `deterministic.max_tokens` from 16384 to **65536**
- **Result:** Resolved "Missing 'activities' key" errors

### 2. Claude Models Cannot Use temperature + top_p Together
- **Issue:** API error when both parameters are set
- **Fix:** Set `top_p: null` for all Claude task types

### 3. GPT 5.2 Supports Temperature
- **Issue:** Config incorrectly set `temperature: null`
- **Fix:** Removed override, allowing provider defaults to apply

### 4. Claude Opus Has max_tokens Limit
- **Issue:** `max_tokens: 16384` causes streaming timeout
- **Fix:** Keep max_tokens ≤ 8192 for Claude Opus

---

## Test Artifacts

- **Optimization Script:** `scripts/optimize_llm_params.py`
- **Results JSON:** `optimization_results.json`
- **Updated Config:** `llm_config.yaml`

---

## Recommendations for Future Tuning

1. **Add narrative tests for Claude models** - not yet tested
2. **Test with longer extraction prompts** - current tests use simplified prompts
3. **Add latency tracking per extractor** - identify slow extractors
4. **Consider Bayesian optimization** - more efficient than grid search for fine-tuning

---

*Report generated: January 19, 2026*
