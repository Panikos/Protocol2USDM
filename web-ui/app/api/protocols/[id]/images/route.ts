import { NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';

const OUTPUT_DIR = process.env.PROTOCOL_OUTPUT_DIR || path.join(process.cwd(), '..', 'output');

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const protocolDir = path.join(OUTPUT_DIR, id);

  // Scan multiple image directories
  const imageDirs = [
    { dir: path.join(protocolDir, '3_soa_images'), category: 'soa' as const },
    { dir: path.join(protocolDir, 'figures'), category: 'figure' as const },
  ];

  const allImages: Array<{
    filename: string;
    url: string;
    page?: number;
    name: string;
    category: 'soa' | 'figure';
  }> = [];

  for (const { dir, category } of imageDirs) {
    try {
      await fs.access(dir);
      const files = await fs.readdir(dir);
      const imageFiles = files
        .filter(f => /\.(png|jpg|jpeg|gif|webp)$/i.test(f))
        .sort((a, b) => {
          const numA = parseInt(a.match(/(\d+)/)?.[1] || '0');
          const numB = parseInt(b.match(/(\d+)/)?.[1] || '0');
          return numA - numB;
        });

      for (const filename of imageFiles) {
        const pageMatch = filename.match(/p(\d{3})/i) || filename.match(/page[_-]?(\d+)/i);
        const page = pageMatch ? parseInt(pageMatch[1]) : undefined;

        allImages.push({
          filename,
          url: `/api/protocols/${id}/images/${filename}`,
          page,
          name: filename.replace(/\.[^.]+$/, ''),
          category,
        });
      }
    } catch {
      // Directory doesn't exist — skip
    }
  }

  return NextResponse.json({ images: allImages });
}
