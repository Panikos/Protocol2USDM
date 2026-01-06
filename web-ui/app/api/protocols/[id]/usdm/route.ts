import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';
import crypto from 'crypto';

const OUTPUT_DIR = process.env.PROTOCOL_OUTPUT_DIR || 
  path.join(process.cwd(), '..', 'output');

// Extract footnotes from USDM extension attributes
function extractFootnotesFromUSDM(usdm: Record<string, unknown>): string[] {
  const footnotes: string[] = [];
  const footnoteMap = new Map<string, string>(); // footnoteId -> text
  
  try {
    // Navigate to studyDesign extensions
    const study = usdm.study as Record<string, unknown> | undefined;
    const versions = (study?.versions as unknown[]) ?? [];
    const version = versions[0] as Record<string, unknown> | undefined;
    const studyDesigns = (version?.studyDesigns as Record<string, unknown>[]) ?? [];
    const studyDesign = studyDesigns[0];
    
    if (!studyDesign) return footnotes;
    
    // Look for extensionAttributes containing footnoteConditions
    const extensions = (studyDesign.extensionAttributes as Array<{
      url?: string;
      valueString?: string;
    }>) ?? [];
    
    for (const ext of extensions) {
      if (ext.url?.includes('footnoteConditions') && ext.valueString) {
        try {
          const conditions = JSON.parse(ext.valueString) as Array<{
            footnoteId?: string;
            text?: string;
          }>;
          
          // Build unique footnotes by footnoteId
          for (const cond of conditions) {
            if (cond.footnoteId && cond.text && !footnoteMap.has(cond.footnoteId)) {
              footnoteMap.set(cond.footnoteId, cond.text);
            }
          }
        } catch {
          // Skip malformed JSON
        }
      }
    }
    
    // Sort footnotes by their ID (numeric or alphabetic)
    const sortedEntries = Array.from(footnoteMap.entries()).sort((a, b) => {
      const aNum = parseFloat(a[0].replace(/[^\d.]/g, ''));
      const bNum = parseFloat(b[0].replace(/[^\d.]/g, ''));
      if (!isNaN(aNum) && !isNaN(bNum)) return aNum - bNum;
      return a[0].localeCompare(b[0]);
    });
    
    // Format as "id: text"
    for (const [id, text] of sortedEntries) {
      footnotes.push(`${id} ${text}`);
    }
  } catch {
    // Return empty array on error
  }
  
  return footnotes;
}

// Helper to safely load JSON file
async function loadJsonFile(filePath: string): Promise<unknown | null> {
  try {
    const content = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(content);
  } catch {
    return null;
  }
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: protocolId } = await params;
    const protocolDir = path.join(OUTPUT_DIR, protocolId);
    const usdmPath = path.join(protocolDir, 'protocol_usdm.json');
    
    // Read USDM file
    const content = await fs.readFile(usdmPath, 'utf-8');
    const usdm = JSON.parse(content);
    
    // Calculate revision hash
    const revision = crypto
      .createHash('sha256')
      .update(content)
      .digest('hex')
      .slice(0, 12);
    
    // Load provenance (use protocol_usdm_provenance.json as it has UUIDs matching final USDM)
    let provenance = await loadJsonFile(path.join(protocolDir, 'protocol_usdm_provenance.json')) as Record<string, unknown> | null;
    
    // Extract footnotes from USDM extension attributes and add to provenance
    const footnotes = extractFootnotesFromUSDM(usdm);
    
    // Always ensure provenance exists and has footnotes
    if (!provenance) {
      provenance = {};
    }
    if (footnotes.length > 0) {
      provenance.footnotes = footnotes;
    }
    
    // Load intermediate extraction files to supplement USDM
    const intermediateFiles = {
      eligibility: await loadJsonFile(path.join(protocolDir, '3_eligibility_criteria.json')),
      amendments: await loadJsonFile(path.join(protocolDir, '14_amendment_details.json')),
      scheduling: await loadJsonFile(path.join(protocolDir, '10_scheduling_logic.json')),
      executionModel: await loadJsonFile(path.join(protocolDir, '11_execution_model.json')),
      soaProvenance: await loadJsonFile(path.join(protocolDir, '9_final_soa_provenance.json')),
    };
    
    return NextResponse.json({
      usdm,
      revision,
      provenance,
      intermediateFiles,
      generatedAt: usdm.generatedAt,
    });
  } catch (error) {
    console.error('Error loading USDM:', error);
    return NextResponse.json(
      { error: 'Protocol not found' },
      { status: 404 }
    );
  }
}
