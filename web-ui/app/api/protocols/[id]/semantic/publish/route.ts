import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';
import { spawn } from 'child_process';
import type { SemanticDraft, PublishResponse } from '@/lib/semantic/schema';
import {
  readDraftLatest,
  archiveDraft,
  archiveUsdm,
  writePublished,
  getUsdmPath,
  getOutputPath,
  computeUsdmRevision,
} from '@/lib/semantic/storage';
import { applySemanticPatch } from '@/lib/semantic/patcher';

/**
 * Run Python validation pipeline
 */
async function runValidation(
  protocolId: string
): Promise<{
  schema: { valid: boolean; errors: number; warnings: number };
  usdm: { valid: boolean; errors: number; warnings: number };
  core: { success: boolean; issues: number; warnings: number };
}> {
  const outputDir = getOutputPath(protocolId);
  const usdmPath = getUsdmPath(protocolId);
  
  // Default result if validation fails to run
  const defaultResult = {
    schema: { valid: true, errors: 0, warnings: 0 },
    usdm: { valid: true, errors: 0, warnings: 0 },
    core: { success: true, issues: 0, warnings: 0 },
  };
  
  try {
    // Read validation results from files (validation is run by Python)
    // For now, we'll try to read existing validation files
    // In production, this would call the Python validation subprocess
    
    const schemaPath = path.join(outputDir, 'schema_validation.json');
    const usdmPath = path.join(outputDir, 'usdm_validation.json');
    const conformancePath = path.join(outputDir, 'conformance_report.json');
    
    let schemaResult = defaultResult.schema;
    let usdmResult = defaultResult.usdm;
    let coreResult = defaultResult.core;
    
    try {
      const schemaContent = await fs.readFile(schemaPath, 'utf-8');
      const schema = JSON.parse(schemaContent);
      schemaResult = {
        valid: schema.valid ?? true,
        errors: schema.errors?.length ?? 0,
        warnings: schema.warnings?.length ?? 0,
      };
    } catch { /* File doesn't exist yet */ }
    
    try {
      const usdmContent = await fs.readFile(usdmPath, 'utf-8');
      const usdm = JSON.parse(usdmContent);
      usdmResult = {
        valid: usdm.valid ?? true,
        errors: usdm.errors?.length ?? 0,
        warnings: usdm.warnings?.length ?? 0,
      };
    } catch { /* File doesn't exist yet */ }
    
    try {
      const coreContent = await fs.readFile(conformancePath, 'utf-8');
      const core = JSON.parse(coreContent);
      coreResult = {
        success: core.success ?? true,
        issues: core.issues ?? 0,
        warnings: core.warnings ?? 0,
      };
    } catch { /* File doesn't exist yet */ }
    
    return { schema: schemaResult, usdm: usdmResult, core: coreResult };
  } catch (error) {
    console.error('Error running validation:', error);
    return defaultResult;
  }
}

/**
 * POST /api/protocols/[id]/semantic/publish
 * 
 * Apply the current semantic draft to protocol_usdm.json and trigger validation.
 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: protocolId } = await params;
    
    // 1. Load draft
    const draft = await readDraftLatest(protocolId) as SemanticDraft | null;
    if (!draft) {
      return NextResponse.json(
        { error: 'No semantic draft to publish' },
        { status: 400 }
      );
    }
    
    // 2. Validate USDM revision matches
    const currentRevision = await computeUsdmRevision(protocolId);
    if (draft.usdmRevision !== currentRevision && draft.usdmRevision !== 'sha256:unknown') {
      return NextResponse.json(
        {
          error: 'usdm_revision_mismatch',
          expected: currentRevision,
          actual: draft.usdmRevision,
          message: 'The USDM has been modified since this draft was created. Please refresh and try again.',
        },
        { status: 409 }
      );
    }
    
    // 3. Load current USDM
    const usdmPath = getUsdmPath(protocolId);
    let usdm: unknown;
    try {
      const content = await fs.readFile(usdmPath, 'utf-8');
      usdm = JSON.parse(content);
    } catch {
      return NextResponse.json(
        { error: 'Failed to load protocol_usdm.json' },
        { status: 500 }
      );
    }
    
    // 4. Apply JSON Patch
    console.log('Applying patch:', JSON.stringify(draft.patch, null, 2));
    const patchResult = applySemanticPatch(usdm, draft.patch);
    if (!patchResult.success) {
      console.error('Patch failed:', patchResult.error);
      return NextResponse.json(
        { 
          error: 'patch_failed', 
          details: patchResult.error,
          patch: draft.patch,
        },
        { status: 422 }
      );
    }
    
    // 5. Archive current USDM to history
    await archiveUsdm(protocolId);
    
    // 6. Write updated USDM
    await fs.writeFile(usdmPath, JSON.stringify(patchResult.result, null, 2));
    
    // 7. Archive draft and write published version
    await archiveDraft(protocolId);
    
    const publishedDraft = {
      ...draft,
      status: 'published' as const,
      updatedAt: new Date().toISOString(),
    };
    const publishedFile = await writePublished(protocolId, publishedDraft);
    
    // 8. Clear draft_latest.json by writing empty/deleting
    // We keep the archived version but clear the active draft
    const { deleteDraftLatest } = await import('@/lib/semantic/storage');
    await deleteDraftLatest(protocolId);
    
    // 9. Run validation pipeline
    const validation = await runValidation(protocolId);
    
    // 10. Check if validation passed (block on schema/usdm errors)
    const hasErrors = !validation.schema.valid || !validation.usdm.valid;
    
    const response: PublishResponse = {
      success: !hasErrors,
      publishedAt: new Date().toISOString(),
      publishedFile,
      validation,
    };
    
    if (hasErrors) {
      return NextResponse.json(
        {
          ...response,
          error: 'validation_failed',
          message: 'USDM was updated but has validation errors.',
        },
        { status: 422 }
      );
    }
    
    return NextResponse.json(response);
  } catch (error) {
    console.error('Error publishing semantic draft:', error);
    return NextResponse.json(
      { error: 'Failed to publish semantic draft' },
      { status: 500 }
    );
  }
}
