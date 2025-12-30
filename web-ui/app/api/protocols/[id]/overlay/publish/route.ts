import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

const OUTPUT_DIR = process.env.PROTOCOL_OUTPUT_DIR || 
  path.join(process.cwd(), '..', 'output');

function getOverlayPath(protocolId: string, type: 'draft' | 'published'): string {
  return path.join(OUTPUT_DIR, protocolId, `overlay_${type}.json`);
}

export async function POST(
  request: Request,
  { params }: { params: { id: string } }
) {
  try {
    const protocolId = params.id;
    const draftPath = getOverlayPath(protocolId, 'draft');
    const publishedPath = getOverlayPath(protocolId, 'published');
    
    // Read draft overlay
    let draft;
    try {
      const content = await fs.readFile(draftPath, 'utf-8');
      draft = JSON.parse(content);
    } catch {
      return NextResponse.json(
        { error: 'No draft overlay to publish' },
        { status: 400 }
      );
    }
    
    // Update status and timestamp
    draft.status = 'published';
    draft.updatedAt = new Date().toISOString();
    
    // Save as published
    await fs.writeFile(publishedPath, JSON.stringify(draft, null, 2));
    
    return NextResponse.json({ 
      success: true, 
      overlay: draft,
      message: 'Draft promoted to published successfully'
    });
  } catch (error) {
    console.error('Error publishing overlay:', error);
    return NextResponse.json(
      { error: 'Failed to publish overlay' },
      { status: 500 }
    );
  }
}
