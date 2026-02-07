import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

const OUTPUT_DIR = process.env.PROTOCOL_OUTPUT_DIR || 
  path.join(process.cwd(), '..', 'output');

const INPUT_DIR = process.env.PROTOCOL_INPUT_DIR ||
  path.join(process.cwd(), '..', 'input');

/**
 * Find document path by searching manifest and input directories
 */
async function findDocumentPath(protocolId: string, filename: string): Promise<string | null> {
  // Check manifest first
  const outputDir = path.join(OUTPUT_DIR, protocolId);
  const manifestPath = path.join(outputDir, 'run_manifest.json');
  
  try {
    const manifestContent = await fs.readFile(manifestPath, 'utf-8');
    const manifest = JSON.parse(manifestContent);
    
    // Check if filename matches any manifest paths
    for (const key of ['input_file', 'sap_file', 'sites_file']) {
      const filePath = manifest[key];
      if (filePath && path.basename(filePath) === filename) {
        return filePath;
      }
    }
  } catch { /* No manifest */ }
  
  // Search input/trial directories
  try {
    const trialDirs = await fs.readdir(path.join(INPUT_DIR, 'trial'));
    for (const dir of trialDirs) {
      const filePath = path.join(INPUT_DIR, 'trial', dir, filename);
      try {
        await fs.access(filePath);
        return filePath;
      } catch { /* File not in this dir */ }
    }
  } catch { /* Input dir not accessible */ }
  
  return null;
}

/**
 * Parse CSV content for preview
 */
function parseCSVPreview(content: string, maxRows: number = 100): { headers: string[]; rows: string[][] } {
  const lines = content.split('\n').filter(line => line.trim());
  const headers = lines[0]?.split(',').map(h => h.trim().replace(/^"|"$/g, '')) || [];
  const rows = lines.slice(1, maxRows + 1).map(line => 
    line.split(',').map(cell => cell.trim().replace(/^"|"$/g, ''))
  );
  return { headers, rows };
}

/**
 * GET /api/protocols/[id]/documents/[filename]
 * 
 * Stream file for download or preview.
 * Query params:
 *   - preview=true: return preview-friendly response
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string; filename: string }> }
) {
  try {
    const { id: protocolId, filename } = await params;
    const url = new URL(request.url);
    const preview = url.searchParams.get('preview') === 'true';
    
    // Find the document
    const filePath = await findDocumentPath(protocolId, filename);
    if (!filePath) {
      return NextResponse.json(
        { error: 'Document not found' },
        { status: 404 }
      );
    }
    
    // Get file stats
    const stat = await fs.stat(filePath);
    const ext = path.extname(filename).toLowerCase();
    
    // For preview mode, return structured data
    if (preview) {
      if (ext === '.csv') {
        const content = await fs.readFile(filePath, 'utf-8');
        const parsed = parseCSVPreview(content);
        return NextResponse.json({
          type: 'csv',
          filename,
          size: stat.size,
          preview: parsed,
        });
      }
      
      if (ext === '.json') {
        const content = await fs.readFile(filePath, 'utf-8');
        const data = JSON.parse(content);
        return NextResponse.json({
          type: 'json',
          filename,
          size: stat.size,
          preview: data,
        });
      }
      
      // For PDF and other files, return metadata only
      return NextResponse.json({
        type: ext.slice(1),
        filename,
        size: stat.size,
        message: 'Preview not available for this file type. Use download.',
      });
    }
    
    // For download, stream the file
    const content = await fs.readFile(filePath);
    
    const mimeTypes: Record<string, string> = {
      '.pdf': 'application/pdf',
      '.csv': 'text/csv',
      '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      '.xls': 'application/vnd.ms-excel',
      '.json': 'application/json',
      '.txt': 'text/plain',
    };
    
    const contentType = mimeTypes[ext] || 'application/octet-stream';
    
    return new NextResponse(content, {
      headers: {
        'Content-Type': contentType,
        'Content-Disposition': `attachment; filename="${filename}"`,
        'Content-Length': stat.size.toString(),
      },
    });
  } catch (error) {
    console.error('Error serving document:', error);
    return NextResponse.json(
      { error: 'Failed to serve document' },
      { status: 500 }
    );
  }
}
