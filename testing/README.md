# Testing & Benchmarking

This directory contains testing and benchmarking scripts for the Protocol2USDM pipeline.

## Files

| File | Purpose |
|------|---------|
| `benchmark.py` | Core benchmarking utilities |
| `benchmark_models.py` | Benchmark different LLM models for extraction quality |
| `compare_golden_vs_extracted.py` | Compare extracted output against golden standard |
| `test_golden_comparison.py` | Unit tests for golden standard comparison |
| `test_pipeline_steps.py` | End-to-end pipeline step tests |
| `test_claude.py` | Claude model-specific tests |
| `test_gpt51_vision.py` | GPT vision capability tests |
| `audit_extraction_gaps.py` | Audit extraction completeness gaps |

## Running Tests

```bash
# Run all pipeline tests
python -m pytest testing/

# Run specific test
python testing/test_pipeline_steps.py

# Run golden comparison
python testing/compare_golden_vs_extracted.py
```

## Unit Tests

For unit tests of core modules, see the `tests/` directory.
