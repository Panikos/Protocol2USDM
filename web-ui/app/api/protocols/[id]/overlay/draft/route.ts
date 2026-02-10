import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';
import { OverlayDocSchema } from '@/lib/overlay/schema';
import { validateProtocolId } from '@/lib/sanitize';

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
    const idCheck = validateProtocolId(protocolId);
    if (!idCheck.valid) {
      return NextResponse.json({ error: idCheck.error }, { status: 400 });
    }
    const overlayPath = getOverlayPath(idCheck.sanitized, 'draft');
    
    try {
      const content = await fs.readFile(overlayPath, 'utf-8');
      const overlay = JSON.parse(content);
      return NextResponse.json(overlay);
    } catch {
      // No draft overlay exists
      return NextResponse.json(null);
    }
  } catch (error) {
    console.error('Error loading draft overlay:', error);
    return NextResponse.json(
      { error: 'Failed to load draft overlay' },
      { status: 500 }
    );
  }
}

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: protocolId } = await params;
    const idCheck = validateProtocolId(protocolId);
    if (!idCheck.valid) {
      return NextResponse.json({ error: idCheck.error }, { status: 400 });
    }
    const body = await request.json();
    
    // Validate overlay schema
    const validated = OverlayDocSchema.parse(body);
    validated.status = 'draft';
    validated.updatedAt = new Date().toISOString();
    
    // Ensure protocol directory exists
    const protocolDir = path.join(OUTPUT_DIR, idCheck.sanitized);
    await fs.mkdir(protocolDir, { recursive: true });
    
    // Save draft overlay
    const overlayPath = getOverlayPath(idCheck.sanitized, 'draft');
    await fs.writeFile(overlayPath, JSON.stringify(validated, null, 2));
    
    return NextResponse.json({ success: true, overlay: validated });
  } catch (error) {
    console.error('Error saving draft overlay:', error);
    return NextResponse.json(
      { error: 'Failed to save draft overlay' },
      { status: 500 }
    );
  }
}
