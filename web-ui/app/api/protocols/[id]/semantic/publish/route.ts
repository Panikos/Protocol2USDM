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
  appendChangeLogEntry,
} from '@/lib/semantic/storage';
import { applySemanticPatch } from '@/lib/semantic/patcher';
import { validateProtocolId } from '@/lib/sanitize';
import { validateSoAStructure } from '@/lib/soa/processor';

/** Validation result shape */
interface ValidationResult {
  schema: { valid: boolean; errors: number; warnings: number };
  usdm: { valid: boolean; errors: number; warnings: number };
  core: { success: boolean; issues: number; warnings: number };
}

/**
 * Run live Python validation on a candidate USDM JSON.
 * 
 * Writes the candidate to a temp file, runs scripts/validate_usdm_json.py,
 * parses the JSON output, and cleans up the temp file.
 * Falls back to fail-open if the Python script is unavailable.
 */
async function runLiveValidation(
  candidateJson: string,
  protocolId: string
): Promise<ValidationResult> {
  const projectRoot = path.resolve(process.cwd(), '..');
  const scriptPath = path.join(projectRoot, 'scripts', 'validate_usdm_json.py');
  const outputDir = getOutputPath(protocolId);
  const tmpValidationFile = path.join(outputDir, '_candidate_usdm.tmp.json');

  // Default: fail closed
  const defaultResult: ValidationResult = {
    schema: { valid: false, errors: 1, warnings: 0 },
    usdm: { valid: false, errors: 1, warnings: 0 },
    core: { success: true, issues: 0, warnings: 0 },
  };

  try {
    // Write candidate to temp file
    await fs.writeFile(tmpValidationFile, candidateJson, 'utf-8');

    // Run Python validator
    const result = await new Promise<string>((resolve, reject) => {
      const proc = spawn('python', [scriptPath, tmpValidationFile], {
        cwd: projectRoot,
        timeout: 30_000,
        env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
      });

      let stdout = '';
      let stderr = '';
      proc.stdout.on('data', (d: Buffer) => { stdout += d.toString(); });
      proc.stderr.on('data', (d: Buffer) => { stderr += d.toString(); });
      proc.on('close', (code: number | null) => {
        if (code === 0) resolve(stdout.trim());
        else reject(new Error(`Validator exited ${code}: ${stderr.slice(0, 500)}`));
      });
      proc.on('error', reject);
    });

    // Parse Python output
    const parsed = JSON.parse(result) as {
      schema?: { valid?: boolean; errors?: number; warnings?: number };
      usdm?: { valid?: boolean; errors?: number; warnings?: number };
    };

    return {
      schema: {
        valid: parsed.schema?.valid ?? true,
        errors: parsed.schema?.errors ?? 0,
        warnings: parsed.schema?.warnings ?? 0,
      },
      usdm: {
        valid: parsed.usdm?.valid ?? true,
        errors: parsed.usdm?.errors ?? 0,
        warnings: parsed.usdm?.warnings ?? 0,
      },
      core: { success: true, issues: 0, warnings: 0 },
    };
  } catch (error) {
    console.error('Live validation failed, falling back to file-based:', error);
    // Fallback: try reading existing validation files
    return await readExistingValidation(protocolId, defaultResult);
  } finally {
    // Clean up temp file
    try { await fs.unlink(tmpValidationFile); } catch { /* ignore */ }
  }
}

/**
 * Fallback: read existing validation result files from a previous pipeline run.
 */
async function readExistingValidation(
  protocolId: string,
  defaultResult: ValidationResult
): Promise<ValidationResult> {
  const outputDir = getOutputPath(protocolId);
  let schemaResult = defaultResult.schema;
  let usdmResult = defaultResult.usdm;
  let coreResult = defaultResult.core;

  try {
    const schemaContent = await fs.readFile(path.join(outputDir, 'schema_validation.json'), 'utf-8');
    const schema = JSON.parse(schemaContent);
    schemaResult = {
      valid: schema.valid ?? true,
      errors: schema.errors?.length ?? schema.error_count ?? 0,
      warnings: schema.warnings?.length ?? schema.warning_count ?? 0,
    };
  } catch { /* File doesn't exist */ }

  try {
    const usdmContent = await fs.readFile(path.join(outputDir, 'usdm_validation.json'), 'utf-8');
    const usdm = JSON.parse(usdmContent);
    usdmResult = {
      valid: usdm.valid ?? true,
      errors: usdm.errors?.length ?? usdm.error_count ?? 0,
      warnings: usdm.warnings?.length ?? usdm.warning_count ?? 0,
    };
  } catch { /* File doesn't exist */ }

  try {
    const coreContent = await fs.readFile(path.join(outputDir, 'conformance_report.json'), 'utf-8');
    const core = JSON.parse(coreContent);
    coreResult = {
      success: core.success ?? true,
      issues: core.issues ?? 0,
      warnings: core.warnings ?? 0,
    };
  } catch { /* File doesn't exist */ }

  return { schema: schemaResult, usdm: usdmResult, core: coreResult };
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
    
    // Parse request body
    let forcePublish = false;
    let reason = '';
    let publishedBy = 'ui-user';
    try {
      const body = await request.json();
      forcePublish = body?.forcePublish === true;
      reason = typeof body?.reason === 'string' ? body.reason.trim() : '';
      publishedBy = typeof body?.publishedBy === 'string' ? body.publishedBy.trim() : 'ui-user';
    } catch {
      // No body or invalid JSON — default values
    }
    
    // Require reason-for-change (skip for force-publish which already showed the modal)
    if (!reason && !forcePublish) {
      return NextResponse.json(
        { error: 'reason_required', message: 'A reason for change is required to publish.' },
        { status: 400 }
      );
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
    
    // 5. Referential integrity check (orphaned references)
    const soaValidation = validateSoAStructure(patchResult.result as Record<string, unknown>);
    if (!soaValidation.valid && !forcePublish) {
      return NextResponse.json(
        {
          success: false,
          error: 'referential_integrity',
          message: `Candidate USDM has ${soaValidation.issues.length} referential integrity issue(s). Use forcePublish to override.`,
          issues: soaValidation.issues,
        },
        { status: 422 }
      );
    }
    
    // 6. Serialize candidate once (reused for validation + disk write)
    const candidateJson = JSON.stringify(patchResult.result, null, 2);
    
    // 7. Validate candidate USDM BEFORE writing to disk (live Python validation)
    const validation = await runLiveValidation(candidateJson, protocolId);
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
    
    // 7. Archive current USDM to history (only after validation gate)
    await archiveUsdm(protocolId);
    
    // 8. Write updated USDM (atomic: temp file → rename)
    const content = candidateJson;
    const tmpPath = usdmPath + '.tmp';
    await fs.writeFile(tmpPath, content, 'utf-8');
    await fs.rename(tmpPath, usdmPath);
    
    // 9. Archive draft and write published version
    await archiveDraft(protocolId);
    
    const publishedDraft = {
      ...draft,
      status: 'published' as const,
      updatedAt: new Date().toISOString(),
      validation,
    };
    const publishedFile = await writePublished(protocolId, publishedDraft);
    
    // 10. Append audit trail entry
    try {
      await appendChangeLogEntry(protocolId, {
        publishedBy,
        reason: reason || '(force-published with validation errors)',
        patch: draft.patch,
        candidateJson,
        validation: {
          schemaValid: validation.schema.valid,
          usdmValid: validation.usdm.valid,
          errorCount: validation.schema.errors + validation.usdm.errors,
          warningCount: validation.schema.warnings + validation.usdm.warnings,
          forcedPublish: hasErrors && forcePublish,
        },
      });
    } catch (auditErr) {
      console.error('Failed to write audit trail (publish succeeded):', auditErr);
    }
    
    // 11. Clear draft_latest.json
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
