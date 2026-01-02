import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';
import crypto from 'crypto';

const OUTPUT_DIR = process.env.PROTOCOL_OUTPUT_DIR || 
  path.join(process.cwd(), '..', 'output');

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
    
    // Load provenance
    const provenance = await loadJsonFile(path.join(protocolDir, 'protocol_usdm_provenance.json'));
    
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
