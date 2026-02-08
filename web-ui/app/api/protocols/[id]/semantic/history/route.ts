import { NextResponse } from 'next/server';
import { getHistoryEntries, listSemanticFiles } from '@/lib/semantic/storage';
import { validateProtocolId } from '@/lib/sanitize';

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
    const idCheck = validateProtocolId(protocolId);
    if (!idCheck.valid) {
      return NextResponse.json({ error: idCheck.error }, { status: 400 });
    }
    
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
