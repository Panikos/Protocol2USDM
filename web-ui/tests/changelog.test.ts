/**
 * Tests for the audit trail hash chain (P3).
 */
import { computeEntryHash } from '../lib/semantic/storage';
import type { ChangeLogEntry, ChangeLog } from '../lib/semantic/schema';

// We can't import verifyChangeLogIntegrity directly since it uses Node crypto,
// so we inline the verification logic for testing.
function verifyChain(log: ChangeLog): { valid: boolean; brokenAt?: number; message?: string } {
  for (let i = 0; i < log.entries.length; i++) {
    const entry = log.entries[i];
    const expectedPrevHash = i === 0 ? '' : log.entries[i - 1].hash;

    if (entry.previousHash !== expectedPrevHash) {
      return { valid: false, brokenAt: i, message: `previousHash mismatch at ${i}` };
    }

    const { hash: _stored, ...rest } = entry;
    const computed = computeEntryHash(rest);
    if (computed !== entry.hash) {
      return { valid: false, brokenAt: i, message: `hash mismatch at ${i}` };
    }
  }
  return { valid: true };
}

function makeEntry(
  version: number,
  previousHash: string,
  reason: string = `Change v${version}`
): ChangeLogEntry {
  const withoutHash: Omit<ChangeLogEntry, 'hash'> = {
    version,
    publishedAt: new Date().toISOString(),
    publishedBy: 'test-user',
    reason,
    patchCount: 1,
    changedPaths: ['/study/versions/0/titles'],
    usdmHash: 'abc123',
    previousHash,
    validation: {
      schemaValid: true,
      usdmValid: true,
      errorCount: 0,
      warningCount: 0,
      forcedPublish: false,
    },
  };
  return { ...withoutHash, hash: computeEntryHash(withoutHash) };
}

describe('Audit Trail Hash Chain', () => {
  test('single entry chain is valid', () => {
    const entry = makeEntry(1, '');
    const log: ChangeLog = { protocolId: 'test', entries: [entry] };
    expect(verifyChain(log)).toEqual({ valid: true });
  });

  test('multi-entry chain is valid', () => {
    const e1 = makeEntry(1, '');
    const e2 = makeEntry(2, e1.hash);
    const e3 = makeEntry(3, e2.hash);
    const log: ChangeLog = { protocolId: 'test', entries: [e1, e2, e3] };
    expect(verifyChain(log)).toEqual({ valid: true });
  });

  test('detects tampered entry (modified reason)', () => {
    const e1 = makeEntry(1, '');
    const e2 = makeEntry(2, e1.hash);
    // Tamper with e2's reason without recomputing hash
    e2.reason = 'TAMPERED';
    const log: ChangeLog = { protocolId: 'test', entries: [e1, e2] };
    const result = verifyChain(log);
    expect(result.valid).toBe(false);
    expect(result.brokenAt).toBe(1);
  });

  test('detects broken chain (wrong previousHash)', () => {
    const e1 = makeEntry(1, '');
    const e2 = makeEntry(2, 'wrong-hash');
    const log: ChangeLog = { protocolId: 'test', entries: [e1, e2] };
    const result = verifyChain(log);
    expect(result.valid).toBe(false);
    expect(result.brokenAt).toBe(1);
  });

  test('empty log is valid', () => {
    const log: ChangeLog = { protocolId: 'test', entries: [] };
    expect(verifyChain(log)).toEqual({ valid: true });
  });

  test('hash is deterministic', () => {
    const base: Omit<ChangeLogEntry, 'hash'> = {
      version: 1,
      publishedAt: '2025-01-01T00:00:00.000Z',
      publishedBy: 'user',
      reason: 'test',
      patchCount: 1,
      changedPaths: ['/a'],
      usdmHash: 'x',
      previousHash: '',
    };
    const h1 = computeEntryHash(base);
    const h2 = computeEntryHash(base);
    expect(h1).toBe(h2);
    expect(h1).toHaveLength(64); // SHA-256 hex
  });

  test('different inputs produce different hashes', () => {
    const base: Omit<ChangeLogEntry, 'hash'> = {
      version: 1,
      publishedAt: '2025-01-01T00:00:00.000Z',
      publishedBy: 'user',
      reason: 'test',
      patchCount: 1,
      changedPaths: ['/a'],
      usdmHash: 'x',
      previousHash: '',
    };
    const h1 = computeEntryHash(base);
    const h2 = computeEntryHash({ ...base, reason: 'different' });
    expect(h1).not.toBe(h2);
  });
});
