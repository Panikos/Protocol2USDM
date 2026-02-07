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

const OUTPUT_DIR = process.env.PROTOCOL_OUTPUT_DIR || 
  path.join(process.cwd(), '..', 'output');

const SEMANTIC_DIR = process.env.SEMANTIC_DIR ||
  path.join(process.cwd(), '..', 'semantic');

/**
 * Get paths for a protocol's semantic storage
 */
export function getSemanticPaths(protocolId: string) {
  const base = path.join(SEMANTIC_DIR, protocolId);
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
  return path.join(OUTPUT_DIR, protocolId);
}

/**
 * Get path to protocol_usdm.json for a protocol
 */
export function getUsdmPath(protocolId: string) {
  return path.join(OUTPUT_DIR, protocolId, 'protocol_usdm.json');
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
 * Generate ISO timestamp for file naming
 */
export function getTimestamp(): string {
  return new Date().toISOString().replace(/[:.]/g, '').replace('T', 'T').slice(0, 15) + 'Z';
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
          const match = filename.match(/_(\d{8}T\d{6}Z)\.json$/);
          const timestamp = match ? match[1] : stat.mtime.toISOString();
          return { filename, timestamp, size: stat.size };
        })
    );
    return results.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
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
  await fs.writeFile(paths.draftLatest, JSON.stringify(draft, null, 2));
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
  
  const content = JSON.stringify(published, null, 2);
  await fs.writeFile(paths.publishedLatest, content);
  await fs.writeFile(timestampedPath, content);
  
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
  const paths = getSemanticPaths(protocolId);
  const filePath = path.join(paths[subdir], filename);
  try {
    const content = await fs.readFile(filePath, 'utf-8');
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
      const match = filename.match(/_(\d{8}T\d{6}Z)\.json$/);
      const timestamp = match 
        ? `${match[1].slice(0, 4)}-${match[1].slice(4, 6)}-${match[1].slice(6, 8)}T${match[1].slice(9, 11)}:${match[1].slice(11, 13)}:${match[1].slice(13, 15)}Z`
        : stat.mtime.toISOString();
      
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
  return entries.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
}

/**
 * Restore USDM from a history snapshot
 */
export async function restoreUsdmFromSnapshot(
  protocolId: string,
  snapshotFilename: string
): Promise<{ success: boolean; error?: string }> {
  const paths = getSemanticPaths(protocolId);
  const snapshotPath = path.join(paths.history, snapshotFilename);
  const usdmPath = getUsdmPath(protocolId);
  
  try {
    // Read snapshot
    const exists = await fs.access(snapshotPath).then(() => true).catch(() => false);
    if (!exists) {
      return { success: false, error: 'Snapshot not found' };
    }
    
    // Archive current USDM first
    await archiveUsdm(protocolId);
    
    // Copy snapshot to protocol_usdm.json
    await fs.copyFile(snapshotPath, usdmPath);
    
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
  const match = publishedFilename.match(/_(\d{8}T\d{6}Z)\.json$/);
  if (!match) return null;
  
  const publishTimestamp = match[1];
  
  // Find the closest USDM snapshot before this publish
  try {
    const snapshots = await fs.readdir(paths.history);
    const sortedSnapshots = snapshots
      .filter(f => f.startsWith('protocol_usdm_') && f.endsWith('.json'))
      .map(f => {
        const m = f.match(/_(\d{8}T\d{6}Z)\.json$/);
        return { filename: f, timestamp: m ? m[1] : '' };
      })
      .filter(s => s.timestamp && s.timestamp <= publishTimestamp)
      .sort((a, b) => b.timestamp.localeCompare(a.timestamp));
    
    return sortedSnapshots.length > 0 ? sortedSnapshots[0].filename : null;
  } catch {
    return null;
  }
}
