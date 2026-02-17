import { NextResponse } from 'next/server';
import { readChangeLog, verifyChangeLogIntegrity } from '@/lib/semantic/storage';
import { validateProtocolId } from '@/lib/sanitize';

/**
 * GET /api/protocols/[id]/semantic/changelog
 * 
 * Returns the full change log for a protocol, including hash chain integrity check.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: protocolId } = await params;
    const idCheck = validateProtocolId(protocolId);
    if (!idCheck.valid) {
      return NextResponse.json({ error: idCheck.error }, { status: 400 });
    }

    const log = await readChangeLog(protocolId);
    const integrity = verifyChangeLogIntegrity(log);

    return NextResponse.json({
      protocolId: log.protocolId,
      entryCount: log.entries.length,
      integrity,
      entries: log.entries,
    });
  } catch (error) {
    console.error('Error reading change log:', error);
    return NextResponse.json(
      { error: 'Failed to read change log' },
      { status: 500 }
    );
  }
}
