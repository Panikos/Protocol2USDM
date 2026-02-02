# Test Data for Prompt Benchmarking

This directory contains test cases for benchmarking prompt performance.

## Directory Structure

```
test_data/
├── simple/          # Simple protocols (2-3 visits, basic tables)
├── medium/          # Medium complexity (5-10 visits, standard SoA)
└── complex/         # Complex protocols (10+ visits, nested groups)
```

## How to Create Test Cases

For each PDF you want to test:

### Step 1: Add the PDF

```bash
# Copy your PDF to the appropriate directory
cp path/to/protocol.pdf test_data/medium/
```

### Step 2: Create Gold Standard

1. **Run the pipeline manually:**
   ```bash
   python main_v3.py test_data/medium/protocol.pdf --model gemini-3-flash-preview
   ```

2. **Copy the output as starting point:**
   ```bash
   cp output/protocol/9_final_soa.json test_data/medium/protocol_gold.json
   ```

3. **Manually review and correct the gold standard:**
   - Open `protocol_gold.json` in an editor
   - Verify all extracted data is correct
   - Fix any errors or missing data
   - Ensure it represents the "perfect" extraction
   - Save the corrected version

### Step 3: Verify

The benchmark tool will automatically find:
- `protocol.pdf` - Input file
- `protocol_gold.json` - Expected output (gold standard)

## Gold Standard Requirements

A good gold standard should:

✅ **Be manually verified** by a domain expert  
✅ **Be complete** - All entities extracted  
✅ **Be accurate** - All data matches the protocol  
✅ **Follow USDM v4.0** - Valid schema  
✅ **Have correct linkages** - All IDs reference correctly  

## Example Test Cases

### Simple Example

**File:** `test_data/simple/simple_protocol.pdf`
- 2-3 visits
- 5-10 activities
- No activity groups
- Single epoch

**Gold Standard:** `test_data/simple/simple_protocol_gold.json`

### Medium Example

**File:** `test_data/medium/CDISC_Pilot_Study.pdf`
- 10-15 visits
- 20-30 activities
- Optional activity groups
- 2-3 epochs

**Gold Standard:** `test_data/medium/CDISC_Pilot_Study_gold.json`

### Complex Example

**File:** `test_data/complex/Alexion_NCT04573309.pdf`
- 15+ visits
- 30+ activities
- Multiple activity groups
- Multiple epochs
- Complex visit windows

**Gold Standard:** `test_data/complex/Alexion_NCT04573309_gold.json`

## Running Benchmarks

### Model Comparison Benchmark

```bash
# Compare models across all protocols in input/
python benchmark_models.py --models gemini-3-flash-preview gemini-2.5-pro
```

**Output:**
- `benchmark_results/benchmark_report.json`
- `benchmark_results/benchmark_report.txt`
- Per-protocol outputs in `benchmark_results/<protocol>_<model>/`

### Single Protocol Test

```bash
python main_v3.py input/protocol.pdf --model gemini-3-flash-preview --full
```

**Output:**
- Complete extraction in `output/<protocol>/`
- Validation and conformance reports

## Metrics Tracked

For each test case, the benchmark measures:

1. **Schema Validation** - Does output validate?
2. **Completeness Score** - % of expected entities extracted
3. **Linkage Accuracy** - % of cross-references correct
4. **Field Population** - % of required fields filled
5. **Execution Time** - How long it takes
6. **Error Rate** - How often it fails

## Best Practices

### Test Set Size

- **Minimum:** 3 test cases (1 simple, 1 medium, 1 complex)
- **Recommended:** 5-10 test cases
- **Comprehensive:** 20+ test cases

### Gold Standard Quality

- Review by domain expert
- Independent verification
- Updated when USDM schema changes
- Version controlled

### Benchmark Frequency

- **Baseline:** Once (initial measurement)
- **During development:** Every 2 weeks (after prompt changes)
- **Pre-production:** Before deploying any change
- **Post-production:** Monthly (to track drift)

## Quick Start

1. **Copy your test PDFs:**
   ```bash
   cp input/CDISC_Pilot_Study.pdf test_data/medium/
   ```

2. **Create gold standards:**
   ```bash
   python main_v3.py test_data/medium/CDISC_Pilot_Study.pdf --model gemini-3-flash-preview
   cp output/CDISC_Pilot_Study/9_final_soa.json test_data/medium/CDISC_Pilot_Study_gold.json
   # Now manually review and correct the gold standard!
   ```

3. **Run benchmark:**
   ```bash
   python benchmark_models.py
   ```

4. **Review results:**
   - Check console output
   - Review `benchmark_results/benchmark_report.txt`
   - Identify areas for improvement

## Troubleshooting

### "No test cases found"

Ensure you have both:
- `<name>.pdf` 
- `<name>_gold.json`

In the same directory.

### "Gold standard validation failed"

Your gold standard JSON may be invalid. Validate it:

```bash
python validate_schema.py test_data/medium/protocol_gold.json
```

### "Completeness score is low"

Either:
- Your prompts need improvement, OR
- Your gold standard has more entities than can realistically be extracted

Review the gold standard to ensure it's achievable.

## Support

- Main docs: `README.md`, `USER_GUIDE.md`
- Quick reference: `QUICK_REFERENCE.md`

---

**Ready to benchmark!** Create your first gold standard and run your first test.

**Last Updated:** 2026-02-01
