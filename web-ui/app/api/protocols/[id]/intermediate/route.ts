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
    '9_procedures': 'procedures',
    '10_scheduling': 'scheduling',
    '11_execution': 'execution',
    '11_sap': 'sap',
    '12_study_sites': 'sites',
    '13_document': 'docstructure',
    '14_amendment': 'amendments',
    'schema_validation': 'validation',
    'usdm_validation': 'validation',
    'conformance_report': 'conformance',
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
      
      for (const entry of entries) {
        if (entry.isFile() && entry.name.endsWith('.json')) {
          // Skip the main USDM file and provenance (those are primary, not intermediate)
          if (entry.name === 'protocol_usdm.json') continue;
          if (entry.name === 'protocol_usdm_provenance.json') continue;
          if (entry.name.startsWith('overlay_')) continue;
          
          const filePath = path.join(outputDir, entry.name);
          const stat = await fs.stat(filePath);
          
          files.push({
            filename: entry.name,
            size: stat.size,
            phase: getPhaseFromFilename(entry.name),
            updatedAt: stat.mtime.toISOString(),
          });
        }
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
