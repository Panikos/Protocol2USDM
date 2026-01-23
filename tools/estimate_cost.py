"""Estimate token usage and cost for protocol extraction on Claude Opus 4.5"""

# Claude Opus 4.5 pricing (per million tokens) - Jan 2026
INPUT_COST = 15.0   # $15 per 1M input tokens
OUTPUT_COST = 75.0  # $75 per 1M output tokens

# Estimated tokens per extraction phase based on typical protocol complexity
# Format: (input_tokens, output_tokens)
phases = {
    "SoA Header Analysis (vision)": (50000, 8000),   # 4-7 images + prompt
    "SoA Text Extraction": (30000, 15000),           # Full SoA text + schema
    "SoA Validation (vision)": (60000, 5000),        # Multiple image comparisons
    "Find SoA Pages": (5000, 1000),                  # Page detection
    "Metadata": (8000, 3000),
    "Eligibility": (15000, 8000),
    "Objectives & Endpoints": (12000, 6000),
    "Study Design": (20000, 5000),
    "Interventions": (25000, 10000),
    "Narrative Structure": (10000, 4000),
    "Advanced Entities": (20000, 6000),
    "Procedures & Devices": (15000, 8000),
    "Scheduling Logic": (12000, 5000),
    "Document Structure": (15000, 4000),
    "Amendment Details": (10000, 3000),
    "Execution Model (10 sub-steps)": (100000, 30000),  # Multiple LLM calls
}

total_input = sum(p[0] for p in phases.values())
total_output = sum(p[1] for p in phases.values())
total = total_input + total_output

input_cost = (total_input / 1_000_000) * INPUT_COST
output_cost = (total_output / 1_000_000) * OUTPUT_COST
total_cost = input_cost + output_cost

print("=" * 70)
print("ESTIMATED TOKEN USAGE & COST PER PROTOCOL (Claude Opus 4.5)")
print("=" * 70)
print()
print("Phase Breakdown:")
print("-" * 70)
for phase, (inp, out) in phases.items():
    phase_cost = (inp/1e6 * INPUT_COST) + (out/1e6 * OUTPUT_COST)
    print(f"  {phase:40} {inp:>7,} in / {out:>6,} out  ${phase_cost:>6.2f}")
print("-" * 70)
print()
print(f"  Total Input Tokens:  {total_input:>12,}")
print(f"  Total Output Tokens: {total_output:>12,}")
print(f"  Total Tokens:        {total:>12,}")
print()
print(f"  Input Cost:  ${input_cost:>8.2f}  (@$15/1M tokens)")
print(f"  Output Cost: ${output_cost:>8.2f}  (@$75/1M tokens)")
print(f"  ─────────────────────────")
print(f"  TOTAL COST:  ${total_cost:>8.2f} per protocol")
print()
print("Note: Estimates based on typical 70-120 page protocol complexity.")
print("      Actual usage varies by protocol size and SoA table complexity.")
