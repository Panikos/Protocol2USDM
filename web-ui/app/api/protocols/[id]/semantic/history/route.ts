import { NextResponse } from 'next/server';
import { getHistoryEntries, listSemanticFiles } from '@/lib/semantic/storage';

/**
 * GET /api/protocols/[id]/semantic/history
 * 
 * List all published versions with metadata for the version history panel.
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: protocolId } = await params;
    
    // Get detailed history entries (published versions with metadata)
    const history = await getHistoryEntries(protocolId);
    
    // Also get raw file lists for backward compatibility
    const [published, drafts, usdmSnapshots] = await Promise.all([
      listSemanticFiles(protocolId, 'published'),
      listSemanticFiles(protocolId, 'drafts'),
      listSemanticFiles(protocolId, 'history'),
    ]);
    
    return NextResponse.json({
      history,
      published,
      drafts,
      usdmSnapshots,
    });
  } catch (error) {
    console.error('Error loading semantic history:', error);
    return NextResponse.json(
      { error: 'Failed to load semantic history' },
      { status: 500 }
    );
  }
}
