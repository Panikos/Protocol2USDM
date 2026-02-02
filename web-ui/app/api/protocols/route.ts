import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

// Configure the output directory path
const OUTPUT_DIR = process.env.PROTOCOL_OUTPUT_DIR || 
  path.join(process.cwd(), '..', 'output');

interface ProtocolSummary {
  id: string;
  name: string;
  usdmVersion: string;
  generatedAt: string;
  activityCount: number;
  encounterCount: number;
}

export async function GET() {
  try {
    // Read output directory
    const entries = await fs.readdir(OUTPUT_DIR, { withFileTypes: true });
    
    const protocols: ProtocolSummary[] = [];
    
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      
      const protocolDir = path.join(OUTPUT_DIR, entry.name);
      const usdmPath = path.join(protocolDir, 'protocol_usdm.json');
      
      try {
        const content = await fs.readFile(usdmPath, 'utf-8');
        const usdm = JSON.parse(content);
        
        // Extract summary info
        const studyDesign = usdm.study?.versions?.[0]?.studyDesigns?.[0];
        
        protocols.push({
          id: entry.name,
          name: entry.name,
          usdmVersion: usdm.usdmVersion || '4.0',
          generatedAt: usdm.generatedAt || new Date().toISOString(),
          activityCount: studyDesign?.activities?.length || 0,
          encounterCount: studyDesign?.encounters?.length || 0,
        });
      } catch {
        // Skip directories without valid protocol_usdm.json
        continue;
      }
    }
    
    // Sort by generation date (newest first)
    protocols.sort((a, b) => 
      new Date(b.generatedAt).getTime() - new Date(a.generatedAt).getTime()
    );
    
    return NextResponse.json({ protocols });
  } catch (error) {
    console.error('Error loading protocols:', error);
    return NextResponse.json(
      { error: 'Failed to load protocols', protocols: [] },
      { status: 500 }
    );
  }
}
