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
} from '@/lib/semantic/storage';

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
    
    let body;
    try {
      body = await request.json();
    } catch (jsonError) {
      console.error('JSON parse error:', jsonError);
      return NextResponse.json(
        { error: 'Invalid JSON in request body', details: String(jsonError) },
        { status: 400 }
      );
    }
    
    console.log('Received draft save request:', { protocolId, patchCount: body?.patch?.length });
    
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
    
    return NextResponse.json({ 
      success: true, 
      archivedPrevious: archivedFile,
      draft: draftValidation.data,
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
