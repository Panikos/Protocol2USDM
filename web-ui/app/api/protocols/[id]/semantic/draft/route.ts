import { NextResponse } from 'next/server';
import { 
  SemanticDraftSchema, 
  SaveDraftRequestSchema,
  validatePatchPaths,
  createEmptySemanticDraft,
} from '@/lib/semantic/schema';
import {
  readDraftLatest,
  writeDraftLatest,
  deleteDraftLatest,
  archiveDraft,
  computeUsdmRevision,
  ensureSemanticFolders,
  getUsdmPath,
} from '@/lib/semantic/storage';
import { dryRunPatch } from '@/lib/semantic/patcher';
import { validateProtocolId } from '@/lib/sanitize';
import fs from 'fs/promises';

/**
 * GET /api/protocols/[id]/semantic/draft
 * 
 * Returns the current semantic draft or null if none exists.
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
    const draft = await readDraftLatest(protocolId);
    return NextResponse.json(draft);
  } catch (error) {
    console.error('Error loading semantic draft:', error);
    return NextResponse.json(
      { error: 'Failed to load semantic draft' },
      { status: 500 }
    );
  }
}

/**
 * PUT /api/protocols/[id]/semantic/draft
 * 
 * Save or update the current semantic draft.
 * Archives previous draft before overwriting.
 */
export async function PUT(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: protocolId } = await params;
    const idCheck = validateProtocolId(protocolId);
    if (!idCheck.valid) {
      return NextResponse.json({ error: idCheck.error }, { status: 400 });
    }
    
    let body;
    try {
      body = await request.json();
    } catch (jsonError) {
      return NextResponse.json(
        { error: 'Invalid JSON in request body', details: String(jsonError) },
        { status: 400 }
      );
    }
    
    // Validate request body
    const parseResult = SaveDraftRequestSchema.safeParse(body);
    if (!parseResult.success) {
      return NextResponse.json(
        { error: 'Invalid request body', details: parseResult.error.errors },
        { status: 400 }
      );
    }
    
    const { usdmRevision, updatedBy, patch } = parseResult.data;
    
    // Validate USDM revision matches current
    const currentRevision = await computeUsdmRevision(protocolId);
    if (usdmRevision !== currentRevision && usdmRevision !== 'sha256:unknown') {
      return NextResponse.json(
        { 
          error: 'usdm_revision_mismatch', 
          expected: currentRevision, 
          actual: usdmRevision,
          message: 'The USDM has been modified since this draft was created. Please refresh and try again.'
        },
        { status: 409 }
      );
    }
    
    // Validate patch paths (no immutable fields)
    const pathValidation = validatePatchPaths(patch);
    if (!pathValidation.valid) {
      return NextResponse.json(
        { error: 'Invalid patch paths', details: pathValidation.errors },
        { status: 400 }
      );
    }
    
    // Ensure folders exist
    await ensureSemanticFolders(protocolId);
    
    // Archive existing draft if present
    const archivedFile = await archiveDraft(protocolId);
    
    // Load existing draft to preserve createdAt, or create new
    const existingDraft = await readDraftLatest(protocolId);
    const now = new Date().toISOString();
    
    const draft = {
      version: 1,
      protocolId,
      usdmRevision: currentRevision,
      status: 'draft' as const,
      createdAt: existingDraft && typeof existingDraft === 'object' && 'createdAt' in existingDraft 
        ? (existingDraft as { createdAt: string }).createdAt 
        : now,
      updatedAt: now,
      updatedBy,
      patch,
    };
    
    // Validate full draft schema
    const draftValidation = SemanticDraftSchema.safeParse(draft);
    if (!draftValidation.success) {
      return NextResponse.json(
        { error: 'Draft validation failed', details: draftValidation.error.errors },
        { status: 400 }
      );
    }
    
    // Write draft
    await writeDraftLatest(protocolId, draftValidation.data);
    
    // Dry-run patch validation (non-blocking — save always succeeds)
    let dryRunWarning: string | undefined;
    try {
      const usdmPath = getUsdmPath(protocolId);
      const usdmContent = await fs.readFile(usdmPath, 'utf-8');
      const usdm = JSON.parse(usdmContent);
      const dryResult = dryRunPatch(usdm, patch);
      if (!dryResult.wouldSucceed) {
        dryRunWarning = dryResult.error;
      }
    } catch {
      // Dry-run failure is non-fatal — USDM may not exist yet
    }
    
    return NextResponse.json({ 
      success: true, 
      archivedPrevious: archivedFile,
      draft: draftValidation.data,
      ...(dryRunWarning ? { dryRunWarning } : {}),
    });
  } catch (error) {
    console.error('Error saving semantic draft:', error);
    return NextResponse.json(
      { error: 'Failed to save semantic draft' },
      { status: 500 }
    );
  }
}

/**
 * DELETE /api/protocols/[id]/semantic/draft
 * 
 * Discard the current semantic draft.
 */
export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: protocolId } = await params;
    const idCheck = validateProtocolId(protocolId);
    if (!idCheck.valid) {
      return NextResponse.json({ error: idCheck.error }, { status: 400 });
    }
    
    // Archive before deleting
    await archiveDraft(protocolId);
    
    // Delete the draft
    const deleted = await deleteDraftLatest(protocolId);
    
    return NextResponse.json({ 
      success: true, 
      deleted,
    });
  } catch (error) {
    console.error('Error deleting semantic draft:', error);
    return NextResponse.json(
      { error: 'Failed to delete semantic draft' },
      { status: 500 }
    );
  }
}
