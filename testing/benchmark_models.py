#!/usr/bin/env python3
"""
Model Benchmarking Utility

Compares extraction quality between different LLM models by running
the full pipeline on all protocols in the input folder.

Usage:
    python benchmark_models.py
    python benchmark_models.py --models gpt-5.1 gemini-3-pro-preview
    python benchmark_models.py --input-dir input --output-dir benchmark_results
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
import logging

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    """Results from a single pipeline run."""
    model: str
    protocol: str
    success: bool
    activities: int = 0
    timepoints: int = 0
    ticks: int = 0
    epochs: int = 0
    encounters: int = 0
    enriched_activities: int = 0
    schema_valid: bool = False
    conformance_issues: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)


@dataclass
class BenchmarkReport:
    """Aggregated benchmark results."""
    timestamp: str
    models: List[str]
    protocols: List[str]
    results: List[RunResult] = field(default_factory=list)
    
    def to_dict(self):
        return {
            'timestamp': self.timestamp,
            'models': self.models,
            'protocols': self.protocols,
            'results': [r.to_dict() for r in self.results]
        }


def run_pipeline_for_model(pdf_path: str, model: str, output_base: str) -> RunResult:
    """Run the full pipeline for a single protocol with a specific model."""
    from extraction import run_from_files, PipelineConfig
    from extraction.pipeline import enrich_terminology, validate_schema, run_cdisc_conformance
    
    protocol_name = Path(pdf_path).stem
    output_dir = os.path.join(output_base, f"{protocol_name}_{model.replace('.', '_')}")
    
    result = RunResult(
        model=model,
        protocol=protocol_name,
        success=False
    )
    
    start_time = time.time()
    
    try:
        logger.info(f"  Running {model} on {protocol_name}...")
        
        # Configure pipeline
        config = PipelineConfig(
            model_name=model,
            validate_with_vision=True,
            save_intermediate=True,
        )
        
        # Run extraction
        pipeline_result = run_from_files(
            pdf_path=pdf_path,
            output_dir=output_dir,
            config=config,
        )
        
        if not pipeline_result.success:
            result.error = "; ".join(pipeline_result.errors) if pipeline_result.errors else "Unknown error"
            result.duration_seconds = time.time() - start_time
            return result
        
        result.success = True
        result.activities = pipeline_result.activities_count
        result.timepoints = pipeline_result.timepoints_count
        result.ticks = pipeline_result.ticks_count
        
        # Load final output for additional metrics
        if pipeline_result.output_path and os.path.exists(pipeline_result.output_path):
            with open(pipeline_result.output_path) as f:
                soa_data = json.load(f)
            
            timeline = soa_data.get('study', {}).get('versions', [{}])[0].get('timeline', {})
            result.epochs = len(timeline.get('epochs', []))
            result.encounters = len(timeline.get('encounters', []))
            
            # Run post-processing steps
            try:
                enrich_result = enrich_terminology(pipeline_result.output_path)
                result.enriched_activities = enrich_result.get('enriched', 0)
            except Exception as e:
                logger.warning(f"    Enrichment failed: {e}")
            
            try:
                schema_result = validate_schema(pipeline_result.output_path)
                result.schema_valid = schema_result.get('valid', False)
            except Exception as e:
                logger.warning(f"    Schema validation failed: {e}")
            
            try:
                conform_result = run_cdisc_conformance(pipeline_result.output_path, output_dir)
                if conform_result.get('success'):
                    # Load conformance report to count issues
                    report_path = conform_result.get('output')
                    if report_path and os.path.exists(report_path):
                        with open(report_path) as f:
                            conf_data = json.load(f)
                        result.conformance_issues = len(conf_data.get('Issue_Details', []))
            except Exception as e:
                logger.warning(f"    Conformance check failed: {e}")
        
    except Exception as e:
        result.error = str(e)
        logger.error(f"    Pipeline failed: {e}")
    
    result.duration_seconds = time.time() - start_time
    return result


def generate_comparison_report(report: BenchmarkReport) -> str:
    """Generate a human-readable comparison report."""
    lines = []
    lines.append("=" * 80)
    lines.append("MODEL BENCHMARK COMPARISON REPORT")
    lines.append(f"Generated: {report.timestamp}")
    lines.append("=" * 80)
    lines.append("")
    
    # Group results by protocol
    by_protocol = {}
    for r in report.results:
        if r.protocol not in by_protocol:
            by_protocol[r.protocol] = {}
        by_protocol[r.protocol][r.model] = r
    
    # Summary table
    lines.append("SUMMARY BY PROTOCOL")
    lines.append("-" * 80)
    
    header = f"{'Protocol':<30} | {'Model':<20} | {'Acts':>5} | {'TPs':>5} | {'Ticks':>6} | {'Time':>6}"
    lines.append(header)
    lines.append("-" * 80)
    
    for protocol in sorted(by_protocol.keys()):
        for model in report.models:
            r = by_protocol[protocol].get(model)
            if r:
                status = "✓" if r.success else "✗"
                lines.append(
                    f"{protocol[:30]:<30} | {model[:20]:<20} | {r.activities:>5} | "
                    f"{r.timepoints:>5} | {r.ticks:>6} | {r.duration_seconds:>5.1f}s"
                )
    
    lines.append("")
    lines.append("=" * 80)
    lines.append("AGGREGATE METRICS")
    lines.append("-" * 80)
    
    # Aggregate by model
    model_stats = {m: {'success': 0, 'total': 0, 'activities': 0, 'ticks': 0, 'time': 0.0, 'schema_pass': 0} 
                   for m in report.models}
    
    for r in report.results:
        model_stats[r.model]['total'] += 1
        model_stats[r.model]['time'] += r.duration_seconds
        if r.success:
            model_stats[r.model]['success'] += 1
            model_stats[r.model]['activities'] += r.activities
            model_stats[r.model]['ticks'] += r.ticks
        if r.schema_valid:
            model_stats[r.model]['schema_pass'] += 1
    
    lines.append(f"{'Model':<25} | {'Success':>8} | {'Activities':>10} | {'Ticks':>8} | {'Schema Pass':>11} | {'Avg Time':>10}")
    lines.append("-" * 80)
    
    for model in report.models:
        stats = model_stats[model]
        success_rate = f"{stats['success']}/{stats['total']}"
        avg_time = stats['time'] / stats['total'] if stats['total'] > 0 else 0
        lines.append(
            f"{model:<25} | {success_rate:>8} | {stats['activities']:>10} | "
            f"{stats['ticks']:>8} | {stats['schema_pass']:>11} | {avg_time:>9.1f}s"
        )
    
    lines.append("")
    
    # Determine winner
    lines.append("=" * 80)
    lines.append("RECOMMENDATION")
    lines.append("-" * 80)
    
    best_model = None
    best_score = -1
    
    for model in report.models:
        stats = model_stats[model]
        # Score: success rate * 40 + schema pass rate * 30 + tick density * 30
        if stats['total'] > 0:
            success_rate = stats['success'] / stats['total']
            schema_rate = stats['schema_pass'] / stats['total']
            tick_density = stats['ticks'] / max(stats['activities'], 1) if stats['activities'] > 0 else 0
            score = success_rate * 40 + schema_rate * 30 + min(tick_density / 10, 1) * 30
            
            if score > best_score:
                best_score = score
                best_model = model
    
    if best_model:
        lines.append(f"Best performing model: {best_model}")
        lines.append(f"Composite score: {best_score:.1f}/100")
    else:
        lines.append("Could not determine best model (no successful runs)")
    
    lines.append("=" * 80)
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Benchmark LLM models on protocol extraction")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gpt-5.1", "gemini-3-pro-preview"],
        help="Models to benchmark"
    )
    parser.add_argument(
        "--input-dir",
        default="input",
        help="Directory containing protocol PDFs"
    )
    parser.add_argument(
        "--output-dir",
        default="benchmark_results",
        help="Directory for benchmark outputs"
    )
    parser.add_argument(
        "--protocols",
        nargs="*",
        help="Specific protocols to test (PDF filenames without extension)"
    )
    
    args = parser.parse_args()
    
    # Find all protocols
    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        sys.exit(1)
    
    pdf_files = list(input_dir.glob("*.pdf"))
    
    if args.protocols:
        pdf_files = [f for f in pdf_files if f.stem in args.protocols]
    
    if not pdf_files:
        logger.error("No PDF files found to benchmark")
        sys.exit(1)
    
    logger.info(f"Found {len(pdf_files)} protocols to benchmark")
    logger.info(f"Models: {', '.join(args.models)}")
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Initialize report
    report = BenchmarkReport(
        timestamp=datetime.now().isoformat(),
        models=args.models,
        protocols=[f.stem for f in pdf_files]
    )
    
    # Run benchmarks
    total_runs = len(pdf_files) * len(args.models)
    current_run = 0
    
    for pdf_file in pdf_files:
        logger.info(f"\nProcessing: {pdf_file.name}")
        
        for model in args.models:
            current_run += 1
            logger.info(f"[{current_run}/{total_runs}] {model}")
            
            result = run_pipeline_for_model(
                str(pdf_file),
                model,
                str(output_dir)
            )
            report.results.append(result)
            
            if result.success:
                logger.info(f"    ✓ {result.activities} activities, {result.ticks} ticks in {result.duration_seconds:.1f}s")
            else:
                logger.warning(f"    ✗ Failed: {result.error}")
    
    # Generate and save report
    report_json_path = output_dir / "benchmark_report.json"
    with open(report_json_path, 'w') as f:
        json.dump(report.to_dict(), f, indent=2)
    logger.info(f"\nJSON report saved to: {report_json_path}")
    
    # Generate text report
    text_report = generate_comparison_report(report)
    report_txt_path = output_dir / "benchmark_report.txt"
    with open(report_txt_path, 'w') as f:
        f.write(text_report)
    
    # Print report
    print("\n")
    print(text_report)
    
    logger.info(f"\nBenchmark complete. Results in: {output_dir}")


if __name__ == "__main__":
    main()
