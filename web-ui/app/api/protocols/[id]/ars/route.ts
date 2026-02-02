import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

const OUTPUT_DIR = process.env.PROTOCOL_OUTPUT_DIR || 
  path.join(process.cwd(), '..', 'output');

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: protocolId } = await params;
    const protocolDir = path.join(OUTPUT_DIR, protocolId);
    
    // Check if protocol directory exists
    try {
      await fs.access(protocolDir);
    } catch {
      return NextResponse.json(
        { error: 'Protocol not found' },
        { status: 404 }
      );
    }
    
    // Look for ARS file
    const arsPath = path.join(protocolDir, 'ars_reporting_event.json');
    
    try {
      await fs.access(arsPath);
    } catch {
      return NextResponse.json(
        { error: 'ARS data not available. Run extraction with --sap flag to generate.' },
        { status: 404 }
      );
    }
    
    // Read and return ARS data
    const arsContent = await fs.readFile(arsPath, 'utf-8');
    const arsData = JSON.parse(arsContent);
    
    return NextResponse.json(arsData);
  } catch (error) {
    console.error('Error fetching ARS data:', error);
    return NextResponse.json(
      { error: 'Failed to fetch ARS data' },
      { status: 500 }
    );
  }
}
