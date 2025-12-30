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

  try {
    // Check if directory exists
    await fs.access(protocolDir);

    // Try to load validation files in order of preference
    const validationFiles = [
      '6_validation_result.json',
      'schema_validation.json',
      'usdm_validation.json',
    ];

    const validationData: {
      extraction?: unknown;
      schema?: unknown;
      usdm?: unknown;
    } = {};

    for (const filename of validationFiles) {
      const filePath = path.join(protocolDir, filename);
      try {
        const content = await fs.readFile(filePath, 'utf-8');
        const data = JSON.parse(content);
        
        if (filename === '6_validation_result.json') {
          validationData.extraction = data;
        } else if (filename === 'schema_validation.json') {
          validationData.schema = data;
        } else if (filename === 'usdm_validation.json') {
          validationData.usdm = data;
        }
      } catch {
        // File doesn't exist or can't be parsed, skip
      }
    }

    if (Object.keys(validationData).length === 0) {
      return NextResponse.json(
        { error: 'No validation data found' },
        { status: 404 }
      );
    }

    return NextResponse.json(validationData);
  } catch {
    return NextResponse.json(
      { error: 'Protocol not found' },
      { status: 404 }
    );
  }
}
