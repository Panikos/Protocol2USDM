import { NextResponse } from 'next/server';
import { readSemanticFile } from '@/lib/semantic/storage';

/**
 * GET /api/protocols/[id]/semantic/history/[historyId]
 * 
 * Get details of a specific history entry (published version).
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string; historyId: string }> }
) {
  try {
    const { id: protocolId, historyId } = await params;
    
    // The historyId is the filename without .json extension
    const filename = historyId.endsWith('.json') ? historyId : `${historyId}.json`;
    
    // Read the published file
    const data = await readSemanticFile(protocolId, 'published', filename);
    
    if (!data) {
      return NextResponse.json(
        { error: 'History entry not found' },
        { status: 404 }
      );
    }
    
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error loading history entry:', error);
    return NextResponse.json(
      { error: 'Failed to load history entry' },
      { status: 500 }
    );
  }
}
