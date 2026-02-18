import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

const OUTPUT_DIR = process.env.PROTOCOL_OUTPUT_DIR || 
  path.join(process.cwd(), '..', 'output');

interface IntermediateFile {
  filename: string;
  size: number;
  phase: string;
  updatedAt: string;
  order: number;
}

/**
 * Map filename patterns to phases
 */
function getPhaseFromFilename(filename: string): string {
  const phaseMap: Record<string, string> = {
    '2_study_metadata': 'metadata',
    '3_eligibility': 'eligibility',
    '4_header_structure': 'soa',
    '4_objectives': 'objectives',
    '5_raw_text_soa': 'soa',
    '5_study_design': 'studydesign',
    '6_interventions': 'interventions',
    '6_validation': 'soa',
    '7_narrative': 'narrative',
    '8_advanced': 'advanced',
    '9_final_soa': 'soa',
    '9_final_soa_provenance': 'soa',
    '9_procedures': 'procedures',
    '10_scheduling': 'scheduling',
    '11_execution': 'execution',
    '11_sap': 'sap',
    '12_study_sites': 'sites',
    '13_document': 'docstructure',
    '14_amendment': 'amendments',
    '14_sap': 'sap',
    '15_sites': 'sites',
    'protocol_usdm.json': 'output',
    'protocol_usdm_provenance': 'output',
    'm11_protocol': 'output',
    'm11_conformance': 'conformance',
    'ars_reporting_event': 'sap',
    'schema_validation': 'validation',
    'usdm_validation': 'validation',
    'conformance_report': 'conformance',
    'integrity_report': 'validation',
    'processing_report': 'meta',
    'entity_stats': 'meta',
    'token_usage': 'meta',
    'run_manifest': 'meta',
    'terminology_enrichment': 'terminology',
    'id_mapping': 'meta',
    'extraction_provenance': 'provenance',
    'entity_provenance': 'provenance',
  };
  
  for (const [pattern, phase] of Object.entries(phaseMap)) {
    if (filename.includes(pattern)) {
      return phase;
    }
  }
  
  return 'other';
}

/**
 * Extract a numeric creation-order from filename prefix (e.g., "9_final_soa.json" → 9).
 * Non-prefixed files get a high order value based on their category.
 */
function getCreationOrder(filename: string): number {
  // Numbered prefix files: 2_xxx, 3_xxx, ..., 15_xxx
  const prefixMatch = filename.match(/^(\d+)_/);
  if (prefixMatch) return parseInt(prefixMatch[1], 10);

  // Post-pipeline outputs ordered after extraction phases
  const lateOrder: Record<string, number> = {
    'protocol_usdm.json': 100,
    'protocol_usdm_provenance.json': 101,
    'm11_protocol.docx': 102,
    'm11_conformance_report.json': 103,
    'ars_reporting_event.json': 104,
    'schema_validation.json': 110,
    'usdm_validation.json': 111,
    'conformance_report.json': 112,
    'integrity_report.json': 113,
    'terminology_enrichment.json': 120,
    'id_mapping.json': 130,
    'extraction_provenance.json': 131,
    'entity_stats.json': 132,
    'processing_report.json': 133,
    'token_usage.json': 140,
    'run_manifest.json': 141,
  };
  return lateOrder[filename] ?? 200;
}

/**
 * GET /api/protocols/[id]/intermediate
 * 
 * List intermediate JSON artifacts.
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: protocolId } = await params;
    const outputDir = path.join(OUTPUT_DIR, protocolId);
    
    // List all JSON files in the output directory
    const files: IntermediateFile[] = [];
    
    try {
      const entries = await fs.readdir(outputDir, { withFileTypes: true });
      
      const ALLOWED_EXTENSIONS = new Set(['.json', '.docx']);
      for (const entry of entries) {
        if (!entry.isFile()) continue;
        const ext = path.extname(entry.name).toLowerCase();
        if (!ALLOWED_EXTENSIONS.has(ext)) continue;
        if (entry.name.startsWith('overlay_')) continue;

        const filePath = path.join(outputDir, entry.name);
        const stat = await fs.stat(filePath);

        files.push({
          filename: entry.name,
          size: stat.size,
          phase: getPhaseFromFilename(entry.name),
          updatedAt: stat.mtime.toISOString(),
          order: getCreationOrder(entry.name),
        });
      }
    } catch {
      // Directory doesn't exist or not accessible
      return NextResponse.json({ files: [] });
    }
    
    // Sort by filename (preserves phase number ordering)
    files.sort((a, b) => a.filename.localeCompare(b.filename));
    
    return NextResponse.json({ files });
  } catch (error) {
    console.error('Error listing intermediate files:', error);
    return NextResponse.json(
      { error: 'Failed to list intermediate files' },
      { status: 500 }
    );
  }
}
