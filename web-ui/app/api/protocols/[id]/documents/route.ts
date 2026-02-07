import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

const OUTPUT_DIR = process.env.PROTOCOL_OUTPUT_DIR || 
  path.join(process.cwd(), '..', 'output');

const INPUT_DIR = process.env.PROTOCOL_INPUT_DIR ||
  path.join(process.cwd(), '..', 'input');

interface DocumentInfo {
  filename: string;
  type: 'protocol' | 'sap' | 'sites' | 'other';
  mimeType: string;
  size: number;
  updatedAt: string;
  path: string;
}

/**
 * Detect document type from filename
 */
function detectDocumentType(filename: string): DocumentInfo['type'] {
  const lower = filename.toLowerCase();
  if (lower.includes('sap')) return 'sap';
  if (lower.includes('site')) return 'sites';
  if (lower.includes('protocol') || lower.endsWith('.pdf')) return 'protocol';
  return 'other';
}

/**
 * Get MIME type from extension
 */
function getMimeType(filename: string): string {
  const ext = path.extname(filename).toLowerCase();
  const mimeTypes: Record<string, string> = {
    '.pdf': 'application/pdf',
    '.csv': 'text/csv',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.xls': 'application/vnd.ms-excel',
    '.json': 'application/json',
    '.txt': 'text/plain',
  };
  return mimeTypes[ext] || 'application/octet-stream';
}

/**
 * GET /api/protocols/[id]/documents
 * 
 * List source documents (protocol PDF, SAP, sites CSV/XLSX).
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: protocolId } = await params;
    const documents: DocumentInfo[] = [];
    
    // Check output directory for run_manifest.json to find input files
    const outputDir = path.join(OUTPUT_DIR, protocolId);
    const manifestPath = path.join(outputDir, 'run_manifest.json');
    
    try {
      const manifestContent = await fs.readFile(manifestPath, 'utf-8');
      const manifest = JSON.parse(manifestContent);
      
      // Add input files from manifest
      if (manifest.input_file) {
        const inputPath = manifest.input_file;
        try {
          const stat = await fs.stat(inputPath);
          documents.push({
            filename: path.basename(inputPath),
            type: 'protocol',
            mimeType: getMimeType(inputPath),
            size: stat.size,
            updatedAt: stat.mtime.toISOString(),
            path: inputPath,
          });
        } catch { /* File not accessible */ }
      }
      
      if (manifest.sap_file) {
        const sapPath = manifest.sap_file;
        try {
          const stat = await fs.stat(sapPath);
          documents.push({
            filename: path.basename(sapPath),
            type: 'sap',
            mimeType: getMimeType(sapPath),
            size: stat.size,
            updatedAt: stat.mtime.toISOString(),
            path: sapPath,
          });
        } catch { /* File not accessible */ }
      }
      
      if (manifest.sites_file) {
        const sitesPath = manifest.sites_file;
        try {
          const stat = await fs.stat(sitesPath);
          documents.push({
            filename: path.basename(sitesPath),
            type: 'sites',
            mimeType: getMimeType(sitesPath),
            size: stat.size,
            updatedAt: stat.mtime.toISOString(),
            path: sitesPath,
          });
        } catch { /* File not accessible */ }
      }
    } catch {
      // No manifest, try multiple fallback strategies
    }
    
    // If no documents found, try fallback strategies
    if (documents.length === 0) {
      // Strategy 1: Look in input/trial/<trialId> directories
      try {
        const trialDirs = await fs.readdir(path.join(INPUT_DIR, 'trial'));
        for (const dir of trialDirs) {
          // Match by NCT number or protocol ID prefix
          const nctMatch = protocolId.match(/NCT\d+/)?.[0];
          if ((nctMatch && dir.includes(nctMatch)) || 
              protocolId.includes(dir) || 
              dir.includes(protocolId.split('_')[0])) {
            const trialPath = path.join(INPUT_DIR, 'trial', dir);
            const files = await fs.readdir(trialPath);
            
            for (const file of files) {
              const filePath = path.join(trialPath, file);
              const stat = await fs.stat(filePath);
              if (stat.isFile()) {
                documents.push({
                  filename: file,
                  type: detectDocumentType(file),
                  mimeType: getMimeType(file),
                  size: stat.size,
                  updatedAt: stat.mtime.toISOString(),
                  path: filePath,
                });
              }
            }
            break; // Found matching trial directory
          }
        }
      } catch { /* Input directory not accessible */ }
      
      // Strategy 2: Check provenance.json in output folder for source references
      if (documents.length === 0) {
        try {
          const provenancePath = path.join(outputDir, 'provenance.json');
          const provenanceContent = await fs.readFile(provenancePath, 'utf-8');
          const provenance = JSON.parse(provenanceContent);
          
          // Check for source file references
          const sourceFile = provenance.source_file || provenance.sourceFile || provenance.inputFile;
          if (sourceFile) {
            // Try absolute path first, then relative to input
            const possiblePaths = [
              sourceFile,
              path.join(INPUT_DIR, sourceFile),
              path.join(INPUT_DIR, 'trial', sourceFile),
            ];
            
            for (const filePath of possiblePaths) {
              try {
                const stat = await fs.stat(filePath);
                if (stat.isFile()) {
                  documents.push({
                    filename: path.basename(filePath),
                    type: detectDocumentType(filePath),
                    mimeType: getMimeType(filePath),
                    size: stat.size,
                    updatedAt: stat.mtime.toISOString(),
                    path: filePath,
                  });
                  break;
                }
              } catch { /* Path not valid */ }
            }
          }
        } catch { /* No provenance file */ }
      }
      
      // Strategy 3: Look directly in input folder for matching files
      if (documents.length === 0) {
        try {
          const inputFiles = await fs.readdir(INPUT_DIR);
          const nctMatch = protocolId.match(/NCT\d+/)?.[0];
          
          for (const file of inputFiles) {
            const filePath = path.join(INPUT_DIR, file);
            const stat = await fs.stat(filePath);
            if (stat.isFile() && nctMatch && file.includes(nctMatch)) {
              documents.push({
                filename: file,
                type: detectDocumentType(file),
                mimeType: getMimeType(file),
                size: stat.size,
                updatedAt: stat.mtime.toISOString(),
                path: filePath,
              });
            }
          }
        } catch { /* Input directory not accessible */ }
      }
    }
    
    return NextResponse.json({ documents });
  } catch (error) {
    console.error('Error listing documents:', error);
    return NextResponse.json(
      { error: 'Failed to list documents' },
      { status: 500 }
    );
  }
}
