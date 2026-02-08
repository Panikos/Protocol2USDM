/**
 * Centralized Input Sanitization
 * 
 * Validates and sanitizes user-controlled inputs (protocol IDs, filenames, etc.)
 * before they are used in filesystem paths or other security-sensitive contexts.
 * 
 * Deny-by-default: only explicitly allowed characters pass validation.
 */

import path from 'path';

/**
 * Validate a protocol ID (directory name from output folder).
 * Allowed: alphanumeric, hyphens, underscores, dots. No path separators.
 */
const SAFE_ID_RE = /^[a-zA-Z0-9_\-\.]+$/;

export function validateProtocolId(id: string): { valid: boolean; sanitized: string; error?: string } {
  if (!id || typeof id !== 'string') {
    return { valid: false, sanitized: '', error: 'Protocol ID is required' };
  }
  if (id.includes('..') || id.includes('/') || id.includes('\\')) {
    return { valid: false, sanitized: '', error: 'Protocol ID contains path traversal characters' };
  }
  if (!SAFE_ID_RE.test(id)) {
    return { valid: false, sanitized: '', error: 'Protocol ID contains invalid characters' };
  }
  return { valid: true, sanitized: id };
}

/**
 * Validate a filename (no directory components, no traversal).
 * Optionally restrict to specific extensions.
 */
export function validateFilename(
  filename: string,
  opts?: { allowedExtensions?: string[] }
): { valid: boolean; sanitized: string; error?: string } {
  if (!filename || typeof filename !== 'string') {
    return { valid: false, sanitized: '', error: 'Filename is required' };
  }
  
  // Block any path separators or traversal
  if (filename.includes('..') || filename.includes('/') || filename.includes('\\') || filename.includes('\0')) {
    return { valid: false, sanitized: '', error: 'Filename contains path traversal characters' };
  }
  
  // Ensure it's just a filename (no directory component)
  if (path.basename(filename) !== filename) {
    return { valid: false, sanitized: '', error: 'Filename contains directory components' };
  }
  
  // Check allowed extensions if specified
  if (opts?.allowedExtensions) {
    const ext = path.extname(filename).toLowerCase();
    if (!opts.allowedExtensions.includes(ext)) {
      return { valid: false, sanitized: '', error: `File extension ${ext} not allowed. Allowed: ${opts.allowedExtensions.join(', ')}` };
    }
  }
  
  return { valid: true, sanitized: filename };
}

/**
 * Ensure a resolved path stays within an expected root directory.
 * Prevents path traversal even if individual components pass validation.
 */
export function ensureWithinRoot(filePath: string, rootDir: string): { valid: boolean; resolved: string; error?: string } {
  const resolved = path.resolve(filePath);
  const resolvedRoot = path.resolve(rootDir);
  
  // On Windows, normalize to forward slashes for comparison
  const normalizedPath = resolved.replace(/\\/g, '/').toLowerCase();
  const normalizedRoot = resolvedRoot.replace(/\\/g, '/').toLowerCase();
  
  if (!normalizedPath.startsWith(normalizedRoot + '/') && normalizedPath !== normalizedRoot) {
    return { valid: false, resolved, error: `Path ${resolved} escapes root ${resolvedRoot}` };
  }
  
  return { valid: true, resolved };
}

/**
 * Validate a semantic history/version ID (timestamp-based filenames).
 * Pattern: word characters, hyphens, dots — no path separators.
 */
const SAFE_VERSION_RE = /^[a-zA-Z0-9_\-\.]+$/;

export function validateVersionId(versionId: string): { valid: boolean; sanitized: string; error?: string } {
  if (!versionId || typeof versionId !== 'string') {
    return { valid: false, sanitized: '', error: 'Version ID is required' };
  }
  if (versionId.includes('..') || versionId.includes('/') || versionId.includes('\\')) {
    return { valid: false, sanitized: '', error: 'Version ID contains path traversal characters' };
  }
  // Ensure .json extension if present
  const withJson = versionId.endsWith('.json') ? versionId : `${versionId}.json`;
  if (!SAFE_VERSION_RE.test(withJson.replace('.json', ''))) {
    return { valid: false, sanitized: '', error: 'Version ID contains invalid characters' };
  }
  return { valid: true, sanitized: withJson };
}
