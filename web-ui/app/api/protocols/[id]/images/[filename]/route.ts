import { NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';

const OUTPUT_DIR = process.env.PROTOCOL_OUTPUT_DIR || path.join(process.cwd(), '..', 'output');

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string; filename: string }> }
) {
  const { id, filename } = await params;

  // Try multiple image directories: SoA images, then protocol figures
  const candidates = [
    path.join(OUTPUT_DIR, id, '3_soa_images', filename),
    path.join(OUTPUT_DIR, id, 'figures', filename),
  ];

  let imageBuffer: Buffer | null = null;
  for (const candidate of candidates) {
    try {
      imageBuffer = await fs.readFile(candidate);
      break;
    } catch {
      // Try next candidate
    }
  }

  try {
    if (!imageBuffer) throw new Error('Not found');
    const body = new Uint8Array(imageBuffer);

    // Determine content type
    const ext = path.extname(filename).toLowerCase();
    const contentTypes: Record<string, string> = {
      '.png': 'image/png',
      '.jpg': 'image/jpeg',
      '.jpeg': 'image/jpeg',
      '.gif': 'image/gif',
      '.webp': 'image/webp',
    };
    const contentType = contentTypes[ext] || 'application/octet-stream';

    return new NextResponse(body, {
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'public, max-age=31536000, immutable',
      },
    });
  } catch {
    return NextResponse.json(
      { error: 'Image not found' },
      { status: 404 }
    );
  }
}
