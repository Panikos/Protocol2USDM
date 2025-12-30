import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';
import crypto from 'crypto';

const OUTPUT_DIR = process.env.PROTOCOL_OUTPUT_DIR || 
  path.join(process.cwd(), '..', 'output');

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: protocolId } = await params;
    const usdmPath = path.join(OUTPUT_DIR, protocolId, 'protocol_usdm.json');
    
    // Read USDM file
    const content = await fs.readFile(usdmPath, 'utf-8');
    const usdm = JSON.parse(content);
    
    // Calculate revision hash
    const revision = crypto
      .createHash('sha256')
      .update(content)
      .digest('hex')
      .slice(0, 12);
    
    // Try to load provenance
    let provenance = null;
    const provenancePath = path.join(OUTPUT_DIR, protocolId, 'protocol_usdm_provenance.json');
    try {
      const provContent = await fs.readFile(provenancePath, 'utf-8');
      provenance = JSON.parse(provContent);
    } catch {
      // Provenance file may not exist
    }
    
    return NextResponse.json({
      usdm,
      revision,
      provenance,
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
