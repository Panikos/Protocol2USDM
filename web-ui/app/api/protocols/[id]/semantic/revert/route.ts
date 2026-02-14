import { NextResponse } from 'next/server';
import { 
  findSnapshotForPublish, 
  restoreUsdmFromSnapshot, 
  archiveUsdm,
  readSemanticFile,
  getSemanticPaths,
  getUsdmPath,
  appendChangeLogEntry,
} from '@/lib/semantic/storage';
import fs from 'fs/promises';
import { validateProtocolId, validateVersionId } from '@/lib/sanitize';

/**
 * POST /api/protocols/[id]/semantic/revert
 * 
 * Revert to a previous published version by restoring the USDM snapshot
 * that was taken before that publish.
 * 
 * Body: { targetVersion: string }
 * 
 * The targetVersion is the ID of the published version to revert to
 * (e.g., "published_20260207T120000Z").
 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: protocolId } = await params;
    const idCheck = validateProtocolId(protocolId);
    if (!idCheck.valid) {
      return NextResponse.json({ error: idCheck.error }, { status: 400 });
    }
    
    const body = await request.json();
    const { targetVersion } = body;
    
    if (!targetVersion) {
      return NextResponse.json(
        { error: 'targetVersion is required' },
        { status: 400 }
      );
    }
    
    // Validate targetVersion to prevent path traversal
    const versionCheck = validateVersionId(targetVersion);
    if (!versionCheck.valid) {
      return NextResponse.json({ error: versionCheck.error }, { status: 400 });
    }
    
    // Get the published file to find associated USDM snapshot
    const publishedFilename = versionCheck.sanitized;
    
    // Read the published version to get the patches that were applied
    const publishedData = await readSemanticFile(protocolId, 'published', publishedFilename);
    if (!publishedData) {
      return NextResponse.json(
        { error: 'Published version not found' },
        { status: 404 }
      );
    }
    
    // Find the USDM snapshot that was taken before this publish
    const snapshotFilename = await findSnapshotForPublish(protocolId, publishedFilename);
    
    if (!snapshotFilename) {
      // If no snapshot found, we can't revert
      // This might happen for the first publish or if history was cleaned
      return NextResponse.json(
        { error: 'No USDM snapshot found for this version. Cannot revert.' },
        { status: 400 }
      );
    }
    
    // Archive current USDM before reverting
    const currentArchive = await archiveUsdm(protocolId);
    
    // Restore the snapshot
    const result = await restoreUsdmFromSnapshot(protocolId, snapshotFilename);
    
    if (!result.success) {
      return NextResponse.json(
        { error: result.error || 'Failed to restore snapshot' },
        { status: 500 }
      );
    }
    
    // Write audit trail entry for the revert
    try {
      const revertedBy = typeof body?.revertedBy === 'string' ? body.revertedBy.trim() : 'ui-user';
      const reason = typeof body?.reason === 'string' ? body.reason.trim() : `Reverted to ${snapshotFilename}`;
      // Read the restored USDM for hashing
      const restoredContent = await fs.readFile(getUsdmPath(protocolId), 'utf-8');
      await appendChangeLogEntry(protocolId, {
        publishedBy: revertedBy,
        reason: `[REVERT] ${reason}`,
        patch: [],
        candidateJson: restoredContent,
        validation: {
          schemaValid: true,
          usdmValid: true,
          errorCount: 0,
          warningCount: 0,
          forcedPublish: false,
        },
      });
    } catch (auditErr) {
      console.error('Failed to write revert audit trail:', auditErr);
    }
    
    return NextResponse.json({
      success: true,
      message: `Reverted to snapshot ${snapshotFilename}`,
      archivedCurrent: currentArchive,
      restoredSnapshot: snapshotFilename,
    });
  } catch (error) {
    console.error('Error reverting:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to revert' },
      { status: 500 }
    );
  }
}
