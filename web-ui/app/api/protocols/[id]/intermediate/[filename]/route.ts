import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';
import { validateProtocolId, validateFilename, ensureWithinRoot } from '@/lib/sanitize';

const OUTPUT_DIR = process.env.PROTOCOL_OUTPUT_DIR || 
  path.join(process.cwd(), '..', 'output');

/**
 * GET /api/protocols/[id]/intermediate/[filename]
 * 
 * Return JSON file contents for preview, with download header option.
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string; filename: string }> }
) {
  try {
    const { id: protocolId, filename } = await params;
    const url = new URL(request.url);
    const download = url.searchParams.get('download') === 'true';
    
    // Validate inputs
    const idCheck = validateProtocolId(protocolId);
    if (!idCheck.valid) {
      return NextResponse.json({ error: idCheck.error }, { status: 400 });
    }
    const fnCheck = validateFilename(filename, { allowedExtensions: ['.json'] });
    if (!fnCheck.valid) {
      return NextResponse.json({ error: fnCheck.error }, { status: 400 });
    }
    
    const filePath = path.join(OUTPUT_DIR, idCheck.sanitized, fnCheck.sanitized);
    const rootCheck = ensureWithinRoot(filePath, path.join(OUTPUT_DIR, idCheck.sanitized));
    if (!rootCheck.valid) {
      return NextResponse.json({ error: 'Invalid file path' }, { status: 400 });
    }
    
    // Check file exists
    try {
      await fs.access(filePath);
    } catch {
      return NextResponse.json(
        { error: 'File not found' },
        { status: 404 }
      );
    }
    
    // Read file
    const content = await fs.readFile(filePath, 'utf-8');
    const stat = await fs.stat(filePath);
    
    // For download, return with attachment header
    if (download) {
      return new NextResponse(content, {
        headers: {
          'Content-Type': 'application/json',
          'Content-Disposition': `attachment; filename="${filename}"`,
          'Content-Length': stat.size.toString(),
        },
      });
    }
    
    // For preview, parse and return as JSON response
    try {
      const data = JSON.parse(content);
      return NextResponse.json({
        filename,
        size: stat.size,
        updatedAt: stat.mtime.toISOString(),
        data,
      });
    } catch {
      // If JSON is invalid, return raw content
      return NextResponse.json({
        filename,
        size: stat.size,
        updatedAt: stat.mtime.toISOString(),
        error: 'Invalid JSON',
        raw: content.slice(0, 1000) + (content.length > 1000 ? '...' : ''),
      });
    }
  } catch (error) {
    console.error('Error serving intermediate file:', error);
    return NextResponse.json(
      { error: 'Failed to serve intermediate file' },
      { status: 500 }
    );
  }
}
