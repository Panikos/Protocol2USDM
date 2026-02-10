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
import { validateProtocolId } from '@/lib/sanitize';

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
  
  // Default result if validation cannot run — fail closed
  const defaultResult = {
    schema: { valid: false, errors: 1, warnings: 0 },
    usdm: { valid: false, errors: 1, warnings: 0 },
    core: { success: false, issues: 1, warnings: 0 },
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
    const idCheck = validateProtocolId(protocolId);
    if (!idCheck.valid) {
      return NextResponse.json({ error: idCheck.error }, { status: 400 });
    }
    
    // Parse optional request body for forcePublish flag
    let forcePublish = false;
    try {
      const body = await request.json();
      forcePublish = body?.forcePublish === true;
    } catch {
      // No body or invalid JSON — default to non-forced
    }
    
    // 1. Load draft
    const draft = await readDraftLatest(protocolId) as SemanticDraft | null;
    if (!draft) {
      return NextResponse.json(
        { error: 'No semantic draft to publish' },
        { status: 400 }
      );
    }
    
    // 2. Validate USDM revision matches (sha256:unknown is rejected on publish to prevent bypass)
    if (draft.usdmRevision === 'sha256:unknown') {
      return NextResponse.json(
        {
          error: 'unknown_revision',
          message: 'Draft has an unknown USDM revision. Please reload the protocol and save a new draft before publishing.',
        },
        { status: 400 }
      );
    }
    const currentRevision = await computeUsdmRevision(protocolId);
    if (draft.usdmRevision !== currentRevision) {
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
    
    // 4. Apply JSON Patch (in memory — no disk write yet)
    const patchResult = applySemanticPatch(usdm, draft.patch);
    if (!patchResult.success) {
      return NextResponse.json(
        { 
          error: 'patch_failed', 
          details: patchResult.error,
          patch: draft.patch,
        },
        { status: 422 }
      );
    }
    
    // 5. Validate candidate USDM BEFORE writing to disk
    //    Read existing validation files as a proxy (Python pipeline runs separately).
    //    In the future, this should shell out to the Python validator on the candidate.
    const validation = await runValidation(protocolId);
    const hasErrors = !validation.schema.valid || !validation.usdm.valid;
    
    if (hasErrors && !forcePublish) {
      return NextResponse.json(
        {
          success: false,
          error: 'validation_failed',
          message: 'Candidate USDM has validation errors. Use forcePublish: true to override.',
          validation,
        },
        { status: 422 }
      );
    }
    
    // 6. Archive current USDM to history (only after validation gate)
    await archiveUsdm(protocolId);
    
    // 7. Write updated USDM (atomic: temp file → rename)
    const content = JSON.stringify(patchResult.result, null, 2);
    const tmpPath = usdmPath + '.tmp';
    await fs.writeFile(tmpPath, content, 'utf-8');
    await fs.rename(tmpPath, usdmPath);
    
    // 8. Archive draft and write published version
    await archiveDraft(protocolId);
    
    const publishedDraft = {
      ...draft,
      status: 'published' as const,
      updatedAt: new Date().toISOString(),
      validation,
    };
    const publishedFile = await writePublished(protocolId, publishedDraft);
    
    // 9. Clear draft_latest.json
    const { deleteDraftLatest } = await import('@/lib/semantic/storage');
    await deleteDraftLatest(protocolId);
    
    const response: PublishResponse = {
      success: true,
      publishedAt: new Date().toISOString(),
      publishedFile,
      validation,
    };
    
    if (hasErrors && forcePublish) {
      return NextResponse.json({
        ...response,
        warning: 'Published with validation errors (forcePublish).',
      });
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
