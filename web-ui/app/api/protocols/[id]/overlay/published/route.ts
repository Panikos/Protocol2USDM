import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

const OUTPUT_DIR = process.env.PROTOCOL_OUTPUT_DIR || 
  path.join(process.cwd(), '..', 'output');

function getOverlayPath(protocolId: string, type: 'draft' | 'published'): string {
  return path.join(OUTPUT_DIR, protocolId, `overlay_${type}.json`);
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: protocolId } = await params;
    const overlayPath = getOverlayPath(protocolId, 'published');
    
    try {
      const content = await fs.readFile(overlayPath, 'utf-8');
      const overlay = JSON.parse(content);
      return NextResponse.json(overlay);
    } catch {
      // No published overlay exists
      return NextResponse.json(null);
    }
  } catch (error) {
    console.error('Error loading published overlay:', error);
    return NextResponse.json(
      { error: 'Failed to load published overlay' },
      { status: 500 }
    );
  }
}
