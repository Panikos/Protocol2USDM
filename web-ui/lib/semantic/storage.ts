/**
 * Semantic Editing Storage Utilities
 * 
 * Manages the folder structure for semantic drafts, published versions, and history.
 * 
 * Storage layout:
 *   semantic/<protocolId>/
 *     drafts/
 *       draft_latest.json
 *       draft_<timestamp>.json
 *     published/
 *       published_latest.json
 *       published_<timestamp>.json
 *     history/
 *       protocol_usdm_<timestamp>.json
 */

import fs from 'fs/promises';
import path from 'path';
import crypto from 'crypto';
import { validateProtocolId, validateFilename, ensureWithinRoot } from '@/lib/sanitize';

import type { ChangeLogEntry, ChangeLog, JsonPatchOp } from '@/lib/semantic/schema';

const OUTPUT_DIR = process.env.PROTOCOL_OUTPUT_DIR || 
  path.join(process.cwd(), '..', 'output');

const SEMANTIC_DIR = process.env.SEMANTIC_DIR ||
  path.join(process.cwd(), '..', 'semantic');

/**
 * Get paths for a protocol's semantic storage
 */
export function getSemanticPaths(protocolId: string) {
  const idCheck = validateProtocolId(protocolId);
  if (!idCheck.valid) throw new Error(`Invalid protocol ID: ${idCheck.error}`);
  const base = path.join(SEMANTIC_DIR, idCheck.sanitized);
  return {
    base,
    drafts: path.join(base, 'drafts'),
    published: path.join(base, 'published'),
    history: path.join(base, 'history'),
    draftLatest: path.join(base, 'drafts', 'draft_latest.json'),
    publishedLatest: path.join(base, 'published', 'published_latest.json'),
  };
}

/**
 * Get path for a protocol's output directory
 */
export function getOutputPath(protocolId: string) {
  const idCheck = validateProtocolId(protocolId);
  if (!idCheck.valid) throw new Error(`Invalid protocol ID: ${idCheck.error}`);
  return path.join(OUTPUT_DIR, idCheck.sanitized);
}

/**
 * Get path to protocol_usdm.json for a protocol
 */
export function getUsdmPath(protocolId: string) {
  const idCheck = validateProtocolId(protocolId);
  if (!idCheck.valid) throw new Error(`Invalid protocol ID: ${idCheck.error}`);
  return path.join(OUTPUT_DIR, idCheck.sanitized, 'protocol_usdm.json');
}

/**
 * Ensure semantic folder structure exists for a protocol
 */
export async function ensureSemanticFolders(protocolId: string): Promise<void> {
  const paths = getSemanticPaths(protocolId);
  await fs.mkdir(paths.drafts, { recursive: true });
  await fs.mkdir(paths.published, { recursive: true });
  await fs.mkdir(paths.history, { recursive: true });
}

/**
 * Atomic JSON write: serialize → write to .tmp → rename.
 * Prevents partial/corrupt writes on crash.
 */
async function atomicWriteJson(targetPath: string, data: unknown): Promise<void> {
  const content = JSON.stringify(data, null, 2);
  const tmpPath = targetPath + '.tmp';
  await fs.writeFile(tmpPath, content, 'utf-8');
  await fs.rename(tmpPath, targetPath);
}

/**
 * Generate ISO timestamp for file naming
 */
// eslint-disable-next-line no-useless-escape
const TIMESTAMP_STRIP_RE = new RegExp('[\\-:.]', 'g');
const TIMESTAMP_FILENAME_RE = /_(\d{8}T\d{6}(?:\d{3})?Z(?:-\d{3})?)\.json$/;
const TIMESTAMP_TOKEN_RE = /^(\d{8}T\d{6}(?:\d{3})?Z)(?:-(\d{3}))?$/;

let _lastTimestampBase = '';
let _timestampSequence = 0;

export function getTimestamp(): string {
  const base = new Date().toISOString().replace(TIMESTAMP_STRIP_RE, ''); // YYYYMMDDTHHMMSSmmmZ
  if (base === _lastTimestampBase) {
    _timestampSequence += 1;
  } else {
    _lastTimestampBase = base;
    _timestampSequence = 0;
  }

  if (_timestampSequence === 0) {
    return base;
  }
  return `${base}-${String(_timestampSequence).padStart(3, '0')}`;
}

function parseTimestampToken(token: string): string {
  const core = token.split('-')[0];
  const match = core.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(\d{3})?Z$/);
  if (!match) {
    return token;
  }

  const [, year, month, day, hour, minute, second, millis] = match;
  return `${year}-${month}-${day}T${hour}:${minute}:${second}${millis ? `.${millis}` : ''}Z`;
}

function parseTimestampOrder(token: string): { epochMs: number; sequence: number } | null {
  const match = token.match(TIMESTAMP_TOKEN_RE);
  if (!match) {
    return null;
  }

  const iso = parseTimestampToken(match[1]);
  const epochMs = Date.parse(iso);
  if (Number.isNaN(epochMs)) {
    return null;
  }

  return {
    epochMs,
    sequence: Number.parseInt(match[2] ?? '0', 10),
  };
}

function compareTimestampOrder(
  a: { epochMs: number; sequence: number },
  b: { epochMs: number; sequence: number }
): number {
  if (a.epochMs !== b.epochMs) {
    return a.epochMs - b.epochMs;
  }
  return a.sequence - b.sequence;
}

/**
 * Compute SHA256 hash of USDM file for revision tracking
 */
export async function computeUsdmRevision(protocolId: string): Promise<string> {
  const usdmPath = getUsdmPath(protocolId);
  try {
    const content = await fs.readFile(usdmPath, 'utf-8');
    const hash = crypto.createHash('sha256').update(content).digest('hex');
    return `sha256:${hash.slice(0, 16)}`;
  } catch {
    return 'sha256:unknown';
  }
}

/**
 * Archive existing draft by copying to timestamped file
 */
export async function archiveDraft(protocolId: string): Promise<string | null> {
  const paths = getSemanticPaths(protocolId);
  
  try {
    const exists = await fs.access(paths.draftLatest).then(() => true).catch(() => false);
    if (!exists) return null;
    
    const timestamp = getTimestamp();
    const archivePath = path.join(paths.drafts, `draft_${timestamp}.json`);
    await fs.copyFile(paths.draftLatest, archivePath);
    return `draft_${timestamp}.json`;
  } catch {
    return null;
  }
}

/**
 * Archive USDM before publish by copying to history
 */
export async function archiveUsdm(protocolId: string): Promise<string | null> {
  const paths = getSemanticPaths(protocolId);
  const usdmPath = getUsdmPath(protocolId);
  
  try {
    const exists = await fs.access(usdmPath).then(() => true).catch(() => false);
    if (!exists) return null;
    
    const timestamp = getTimestamp();
    const archivePath = path.join(paths.history, `protocol_usdm_${timestamp}.json`);
    await fs.copyFile(usdmPath, archivePath);
    return `protocol_usdm_${timestamp}.json`;
  } catch {
    return null;
  }
}

/**
 * List all files in a semantic subdirectory
 */
export async function listSemanticFiles(
  protocolId: string, 
  subdir: 'drafts' | 'published' | 'history'
): Promise<Array<{ filename: string; timestamp: string; size: number }>> {
  const paths = getSemanticPaths(protocolId);
  const dirPath = paths[subdir];
  
  try {
    const files = await fs.readdir(dirPath);
    const results = await Promise.all(
      files
        .filter(f => f.endsWith('.json') && !f.includes('latest'))
        .map(async (filename) => {
          const filePath = path.join(dirPath, filename);
          const stat = await fs.stat(filePath);
          // Extract timestamp from filename
          const match = filename.match(TIMESTAMP_FILENAME_RE);
          const timestamp = match ? parseTimestampToken(match[1]) : stat.mtime.toISOString();
          return { filename, timestamp, size: stat.size };
        })
    );
    return results.sort((a, b) => {
      const aMs = Date.parse(a.timestamp);
      const bMs = Date.parse(b.timestamp);
      if (!Number.isNaN(aMs) && !Number.isNaN(bMs)) {
        return bMs - aMs;
      }
      return b.timestamp.localeCompare(a.timestamp);
    });
  } catch {
    return [];
  }
}

/**
 * Read draft_latest.json if it exists
 */
export async function readDraftLatest(protocolId: string): Promise<unknown | null> {
  const paths = getSemanticPaths(protocolId);
  try {
    const content = await fs.readFile(paths.draftLatest, 'utf-8');
    return JSON.parse(content);
  } catch {
    return null;
  }
}

/**
 * Write draft_latest.json
 */
export async function writeDraftLatest(protocolId: string, draft: unknown): Promise<void> {
  const paths = getSemanticPaths(protocolId);
  await ensureSemanticFolders(protocolId);
  await atomicWriteJson(paths.draftLatest, draft);
}

/**
 * Delete draft_latest.json
 */
export async function deleteDraftLatest(protocolId: string): Promise<boolean> {
  const paths = getSemanticPaths(protocolId);
  try {
    await fs.unlink(paths.draftLatest);
    return true;
  } catch {
    return false;
  }
}

/**
 * Read published_latest.json if it exists
 */
export async function readPublishedLatest(protocolId: string): Promise<unknown | null> {
  const paths = getSemanticPaths(protocolId);
  try {
    const content = await fs.readFile(paths.publishedLatest, 'utf-8');
    return JSON.parse(content);
  } catch {
    return null;
  }
}

/**
 * Write published_latest.json and timestamped version
 */
export async function writePublished(protocolId: string, published: unknown): Promise<string> {
  const paths = getSemanticPaths(protocolId);
  await ensureSemanticFolders(protocolId);
  
  const timestamp = getTimestamp();
  const timestampedPath = path.join(paths.published, `published_${timestamp}.json`);
  
  await atomicWriteJson(paths.publishedLatest, published);
  await atomicWriteJson(timestampedPath, published);
  
  return `published_${timestamp}.json`;
}

/**
 * Read a specific semantic file by path
 */
export async function readSemanticFile(
  protocolId: string,
  subdir: 'drafts' | 'published' | 'history',
  filename: string
): Promise<unknown | null> {
  const fnCheck = validateFilename(filename, { allowedExtensions: ['.json'] });
  if (!fnCheck.valid) return null;
  const paths = getSemanticPaths(protocolId);
  const filePath = path.join(paths[subdir], fnCheck.sanitized);
  // Verify resolved path stays within expected directory
  const rootCheck = ensureWithinRoot(filePath, paths[subdir]);
  if (!rootCheck.valid) return null;
  try {
    const content = await fs.readFile(rootCheck.resolved, 'utf-8');
    return JSON.parse(content);
  } catch {
    return null;
  }
}

/**
 * Read a specific USDM snapshot from history
 */
export async function readUsdmSnapshot(protocolId: string, filename: string): Promise<unknown | null> {
  return readSemanticFile(protocolId, 'history', filename);
}

/**
 * Get detailed history entries with metadata
 */
export interface HistoryEntry {
  id: string;
  filename: string;
  timestamp: string;
  type: 'published' | 'draft' | 'usdm_snapshot';
  patchCount: number;
  updatedBy?: string;
  validation?: {
    schema: { valid: boolean; errors: number; warnings: number };
    usdm: { valid: boolean; errors: number; warnings: number };
    core: { success: boolean; issues: number; warnings: number };
  };
}

export async function getHistoryEntries(protocolId: string): Promise<HistoryEntry[]> {
  const paths = getSemanticPaths(protocolId);
  const entries: HistoryEntry[] = [];
  
  // Get published versions
  try {
    const publishedFiles = await fs.readdir(paths.published);
    for (const filename of publishedFiles) {
      if (!filename.endsWith('.json') || filename.includes('latest')) continue;
      
      const filePath = path.join(paths.published, filename);
      const stat = await fs.stat(filePath);
      const content = await fs.readFile(filePath, 'utf-8');
      const data = JSON.parse(content) as Record<string, unknown>;
      
      // Extract timestamp from filename
      const match = filename.match(TIMESTAMP_FILENAME_RE);
      const timestamp = match ? parseTimestampToken(match[1]) : stat.mtime.toISOString();
      
      entries.push({
        id: filename.replace('.json', ''),
        filename,
        timestamp,
        type: 'published',
        patchCount: Array.isArray(data.patch) ? data.patch.length : 0,
        updatedBy: data.updatedBy as string | undefined,
        validation: data.validation as HistoryEntry['validation'] | undefined,
      });
    }
  } catch {
    // Published folder may not exist
  }
  
  // Sort by timestamp descending
  return entries.sort((a, b) => {
    const aMs = Date.parse(a.timestamp);
    const bMs = Date.parse(b.timestamp);
    if (!Number.isNaN(aMs) && !Number.isNaN(bMs)) {
      return bMs - aMs;
    }
    return b.timestamp.localeCompare(a.timestamp);
  });
}

/**
 * Restore USDM from a history snapshot
 */
export async function restoreUsdmFromSnapshot(
  protocolId: string,
  snapshotFilename: string
): Promise<{ success: boolean; error?: string }> {
  const fnCheck = validateFilename(snapshotFilename, { allowedExtensions: ['.json'] });
  if (!fnCheck.valid) return { success: false, error: fnCheck.error };
  const paths = getSemanticPaths(protocolId);
  const snapshotPath = path.join(paths.history, fnCheck.sanitized);
  const rootCheck = ensureWithinRoot(snapshotPath, paths.history);
  if (!rootCheck.valid) return { success: false, error: 'Invalid snapshot path' };
  const usdmPath = getUsdmPath(protocolId);
  
  try {
    // Read snapshot
    const exists = await fs.access(rootCheck.resolved).then(() => true).catch(() => false);
    if (!exists) {
      return { success: false, error: 'Snapshot not found' };
    }
    
    // Archive current USDM first
    await archiveUsdm(protocolId);
    
    // Atomic restore: read snapshot, write to temp, rename
    const content = await fs.readFile(rootCheck.resolved, 'utf-8');
    JSON.parse(content); // validate JSON before writing
    const tmpPath = usdmPath + '.tmp';
    await fs.writeFile(tmpPath, content);
    await fs.rename(tmpPath, usdmPath);
    
    return { success: true };
  } catch (error) {
    return { 
      success: false, 
      error: error instanceof Error ? error.message : 'Unknown error' 
    };
  }
}

/**
 * Get the USDM snapshot filename that corresponds to a published version
 * (the snapshot taken just before that publish)
 */
export async function findSnapshotForPublish(
  protocolId: string,
  publishedFilename: string
): Promise<string | null> {
  const paths = getSemanticPaths(protocolId);
  
  // Extract timestamp from published filename
  const match = publishedFilename.match(TIMESTAMP_FILENAME_RE);
  if (!match) return null;
  
  const publishTimestamp = match[1];
  const publishOrder = parseTimestampOrder(publishTimestamp);
  if (!publishOrder) {
    return null;
  }
  
  // Find the closest USDM snapshot before this publish
  try {
    const snapshots = await fs.readdir(paths.history);
    const sortedSnapshots = snapshots
      .filter(f => f.startsWith('protocol_usdm_') && f.endsWith('.json'))
      .map(f => {
        const m = f.match(TIMESTAMP_FILENAME_RE);
        const timestamp = m ? m[1] : '';
        const order = timestamp ? parseTimestampOrder(timestamp) : null;
        return { filename: f, order };
      })
      .filter(s => s.order && compareTimestampOrder(s.order, publishOrder) <= 0)
      .sort((a, b) => compareTimestampOrder(b.order!, a.order!));
    
    return sortedSnapshots.length > 0 ? sortedSnapshots[0].filename : null;
  } catch {
    return null;
  }
}

// ── Audit Trail (P3) ─────────────────────────────────────────────

/**
 * Compute SHA-256 hash of a string.
 */
function sha256(data: string): string {
  return crypto.createHash('sha256').update(data, 'utf-8').digest('hex');
}

/**
 * Compute the hash for a change log entry.
 * Covers all fields except `hash` itself, creating a tamper-evident chain.
 */
export function computeEntryHash(entry: Omit<ChangeLogEntry, 'hash'>): string {
  const payload = JSON.stringify({
    version: entry.version,
    publishedAt: entry.publishedAt,
    publishedBy: entry.publishedBy,
    reason: entry.reason,
    patchCount: entry.patchCount,
    changedPaths: entry.changedPaths,
    usdmHash: entry.usdmHash,
    previousHash: entry.previousHash,
    validation: entry.validation,
  });
  return sha256(payload);
}

/**
 * Get the path to the change log file for a protocol.
 */
function getChangeLogPath(protocolId: string): string {
  const paths = getSemanticPaths(protocolId);
  return path.join(paths.base, 'changelog.json');
}

/**
 * Read the change log for a protocol.
 */
export async function readChangeLog(protocolId: string): Promise<ChangeLog> {
  const logPath = getChangeLogPath(protocolId);
  try {
    const content = await fs.readFile(logPath, 'utf-8');
    return JSON.parse(content) as ChangeLog;
  } catch {
    return { protocolId, entries: [] };
  }
}

/**
 * Build and append a new change log entry after a successful publish.
 */
export async function appendChangeLogEntry(
  protocolId: string,
  params: {
    publishedBy: string;
    reason: string;
    patch: JsonPatchOp[];
    candidateJson: string;
    validation: ChangeLogEntry['validation'];
  }
): Promise<ChangeLogEntry> {
  await ensureSemanticFolders(protocolId);
  const log = await readChangeLog(protocolId);

  const previousEntry = log.entries.length > 0 ? log.entries[log.entries.length - 1] : null;
  const previousHash = previousEntry?.hash ?? '';

  // Extract unique top-level changed paths (first 20)
  const changedPaths = [
    ...new Set(params.patch.map(op => {
      const segments = op.path.split('/').filter(Boolean);
      return '/' + segments.slice(0, 4).join('/');
    }))
  ].slice(0, 20);

  const entryWithoutHash: Omit<ChangeLogEntry, 'hash'> = {
    version: (previousEntry?.version ?? 0) + 1,
    publishedAt: new Date().toISOString(),
    publishedBy: params.publishedBy,
    reason: params.reason,
    patchCount: params.patch.length,
    changedPaths,
    usdmHash: sha256(params.candidateJson),
    previousHash,
    validation: params.validation,
  };

  const entry: ChangeLogEntry = {
    ...entryWithoutHash,
    hash: computeEntryHash(entryWithoutHash),
  };

  log.entries.push(entry);

  const logPath = getChangeLogPath(protocolId);
  const content = JSON.stringify(log, null, 2);
  const tmpPath = logPath + '.tmp';
  await fs.writeFile(tmpPath, content, 'utf-8');
  await fs.rename(tmpPath, logPath);

  return entry;
}

/**
 * Verify the integrity of the change log hash chain.
 * Returns the first broken entry index, or -1 if chain is valid.
 */
export function verifyChangeLogIntegrity(log: ChangeLog): {
  valid: boolean;
  brokenAt?: number;
  message?: string;
} {
  for (let i = 0; i < log.entries.length; i++) {
    const entry = log.entries[i];
    const expectedPrevHash = i === 0 ? '' : log.entries[i - 1].hash;

    if (entry.previousHash !== expectedPrevHash) {
      return {
        valid: false,
        brokenAt: i,
        message: `Entry ${i} (v${entry.version}): previousHash mismatch`,
      };
    }

    const { hash: _storedHash, ...rest } = entry;
    const computedHash = computeEntryHash(rest);
    if (computedHash !== entry.hash) {
      return {
        valid: false,
        brokenAt: i,
        message: `Entry ${i} (v${entry.version}): hash mismatch (tampered?)`,
      };
    }
  }

  return { valid: true };
}
