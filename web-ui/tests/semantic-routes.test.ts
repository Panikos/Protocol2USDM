import { EventEmitter } from 'events';
import fs from 'fs/promises';
import { spawn } from 'child_process';

declare const jest: any;
declare const describe: any;
declare const test: any;
declare const expect: any;
declare const beforeEach: any;

const mockStorage = {
  readDraftLatest: jest.fn(),
  writeDraftLatest: jest.fn(),
  deleteDraftLatest: jest.fn(),
  archiveDraft: jest.fn(),
  archiveUsdm: jest.fn(),
  writePublished: jest.fn(),
  getUsdmPath: jest.fn(),
  getOutputPath: jest.fn(),
  computeUsdmRevision: jest.fn(),
  appendChangeLogEntry: jest.fn(),
  ensureSemanticFolders: jest.fn(),
};

const mockApplySemanticPatch = jest.fn();
const mockDryRunPatch = jest.fn();
const mockValidateSoAStructure = jest.fn();

jest.mock('next/server', () => ({
  NextResponse: {
    json: (body: unknown, init?: { status?: number }) =>
      new Response(JSON.stringify(body), {
        status: init?.status ?? 200,
        headers: { 'content-type': 'application/json' },
      }),
  },
}));

jest.mock('@/lib/semantic/storage', () => ({
  readDraftLatest: mockStorage.readDraftLatest,
  writeDraftLatest: mockStorage.writeDraftLatest,
  deleteDraftLatest: mockStorage.deleteDraftLatest,
  archiveDraft: mockStorage.archiveDraft,
  archiveUsdm: mockStorage.archiveUsdm,
  writePublished: mockStorage.writePublished,
  getUsdmPath: mockStorage.getUsdmPath,
  getOutputPath: mockStorage.getOutputPath,
  computeUsdmRevision: mockStorage.computeUsdmRevision,
  appendChangeLogEntry: mockStorage.appendChangeLogEntry,
  ensureSemanticFolders: mockStorage.ensureSemanticFolders,
}));

jest.mock('@/lib/semantic/patcher', () => ({
  applySemanticPatch: mockApplySemanticPatch,
  dryRunPatch: mockDryRunPatch,
}));

jest.mock('@/lib/soa/processor', () => ({
  validateSoAStructure: mockValidateSoAStructure,
}));

jest.mock('fs/promises', () => ({
  __esModule: true,
  default: {
    readFile: jest.fn(),
    writeFile: jest.fn(),
    rename: jest.fn(),
    unlink: jest.fn(),
  },
}));

jest.mock('child_process', () => ({
  spawn: jest.fn(),
}));

import { PUT as draftPut } from '@/app/api/protocols/[id]/semantic/draft/route';
import { POST as publishPost } from '@/app/api/protocols/[id]/semantic/publish/route';

const fsMock = fs as unknown as any;

const spawnMock = spawn as unknown as any;

function mockSpawnValidationFailure(): void {
  spawnMock.mockImplementation(() => {
    const proc = new EventEmitter() as EventEmitter & {
      stdout: EventEmitter;
      stderr: EventEmitter;
    };
    proc.stdout = new EventEmitter();
    proc.stderr = new EventEmitter();

    process.nextTick(() => {
      proc.stderr.emit('data', Buffer.from('validator failed'));
      proc.emit('close', 1);
    });

    return proc;
  });
}

function mockSpawnValidationSuccess(): void {
  spawnMock.mockImplementation(() => {
    const proc = new EventEmitter() as EventEmitter & {
      stdout: EventEmitter;
      stderr: EventEmitter;
    };
    proc.stdout = new EventEmitter();
    proc.stderr = new EventEmitter();

    process.nextTick(() => {
      proc.stdout.emit('data', Buffer.from(JSON.stringify({
        schema: { valid: true, errors: 0, warnings: 0 },
        usdm: { valid: true, errors: 0, warnings: 0 },
      })));
      proc.emit('close', 0);
    });

    return proc;
  });
}

describe('semantic draft/publish routes', () => {
  beforeEach(() => {
    jest.clearAllMocks();

    mockStorage.getUsdmPath.mockReturnValue('/tmp/protocol_usdm.json');
    mockStorage.getOutputPath.mockReturnValue('/tmp/output/protocol-1');
    mockStorage.writePublished.mockResolvedValue('published_20260214T120000000Z.json');
    mockStorage.archiveDraft.mockResolvedValue('draft_20260214T120000000Z.json');
    mockStorage.archiveUsdm.mockResolvedValue('protocol_usdm_20260214T120000000Z.json');
    mockStorage.appendChangeLogEntry.mockResolvedValue({});
    mockStorage.deleteDraftLatest.mockResolvedValue(true);
    mockStorage.writeDraftLatest.mockResolvedValue(undefined);
    mockStorage.ensureSemanticFolders.mockResolvedValue(undefined);

    fsMock.readFile.mockImplementation(async (filePath: string) => {
      if (filePath === '/tmp/protocol_usdm.json') {
        return JSON.stringify({
          study: { versions: [{ studyDesigns: [{}] }] },
        });
      }
      return '{}';
    });

    mockApplySemanticPatch.mockReturnValue({
      success: true,
      result: { study: { versions: [{ studyDesigns: [{}] }] } },
    });
    mockValidateSoAStructure.mockReturnValue({ valid: true, issues: [] });
    mockDryRunPatch.mockReturnValue({ wouldSucceed: true });
  });

  test('PUT /draft returns 409 when usdmRevision mismatches current', async () => {
    mockStorage.computeUsdmRevision.mockResolvedValue('sha256:current');

    const req = new Request('http://localhost/api/protocols/protocol-1/semantic/draft', {
      method: 'PUT',
      body: JSON.stringify({
        protocolId: 'protocol-1',
        usdmRevision: 'sha256:stale',
        updatedBy: 'tester',
        patch: [],
      }),
    });

    const res = await draftPut(req, { params: Promise.resolve({ id: 'protocol-1' }) });
    const body = await res.json();

    expect(res.status).toBe(409);
    expect(body.error).toBe('usdm_revision_mismatch');
    expect(mockStorage.writeDraftLatest).not.toHaveBeenCalled();
  });

  test('PUT /draft saves draft and returns dryRunWarning when patch dry-run fails', async () => {
    mockStorage.computeUsdmRevision.mockResolvedValue('sha256:current');
    mockStorage.readDraftLatest.mockResolvedValue({
      createdAt: '2026-02-01T00:00:00.000Z',
    });
    mockDryRunPatch.mockReturnValue({ wouldSucceed: false, error: 'dry run failed' });

    const req = new Request('http://localhost/api/protocols/protocol-1/semantic/draft', {
      method: 'PUT',
      body: JSON.stringify({
        protocolId: 'protocol-1',
        usdmRevision: 'sha256:current',
        updatedBy: 'tester',
        patch: [
          { op: 'replace', path: '/study/versions/0/studyDesigns/0/name', value: 'Updated' },
        ],
      }),
    });

    const res = await draftPut(req, { params: Promise.resolve({ id: 'protocol-1' }) });
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.success).toBe(true);
    expect(body.dryRunWarning).toBe('dry run failed');
    expect(mockStorage.writeDraftLatest).toHaveBeenCalledTimes(1);
    expect(mockStorage.archiveDraft).toHaveBeenCalledTimes(1);
  });

  test('POST /publish requires reason unless forcePublish is true', async () => {
    const req = new Request('http://localhost/api/protocols/protocol-1/semantic/publish', {
      method: 'POST',
      body: JSON.stringify({}),
    });

    const res = await publishPost(req, { params: Promise.resolve({ id: 'protocol-1' }) });
    const body = await res.json();

    expect(res.status).toBe(400);
    expect(body.error).toBe('reason_required');
    expect(mockStorage.readDraftLatest).not.toHaveBeenCalled();
  });

  test('POST /publish rejects draft with unknown revision', async () => {
    mockStorage.readDraftLatest.mockResolvedValue({
      version: 1,
      protocolId: 'protocol-1',
      usdmRevision: 'sha256:unknown',
      status: 'draft',
      createdAt: '2026-02-14T00:00:00.000Z',
      updatedAt: '2026-02-14T00:00:00.000Z',
      updatedBy: 'tester',
      patch: [],
    });

    const req = new Request('http://localhost/api/protocols/protocol-1/semantic/publish', {
      method: 'POST',
      body: JSON.stringify({ reason: 'test publish' }),
    });

    const res = await publishPost(req, { params: Promise.resolve({ id: 'protocol-1' }) });
    const body = await res.json();

    expect(res.status).toBe(400);
    expect(body.error).toBe('unknown_revision');
    expect(mockStorage.computeUsdmRevision).not.toHaveBeenCalled();
  });

  test('POST /publish returns 409 on usdm revision mismatch', async () => {
    mockStorage.readDraftLatest.mockResolvedValue({
      version: 1,
      protocolId: 'protocol-1',
      usdmRevision: 'sha256:stale',
      status: 'draft',
      createdAt: '2026-02-14T00:00:00.000Z',
      updatedAt: '2026-02-14T00:00:00.000Z',
      updatedBy: 'tester',
      patch: [],
    });
    mockStorage.computeUsdmRevision.mockResolvedValue('sha256:current');

    const req = new Request('http://localhost/api/protocols/protocol-1/semantic/publish', {
      method: 'POST',
      body: JSON.stringify({ reason: 'test publish' }),
    });

    const res = await publishPost(req, { params: Promise.resolve({ id: 'protocol-1' }) });
    const body = await res.json();

    expect(res.status).toBe(409);
    expect(body.error).toBe('usdm_revision_mismatch');
    expect(mockStorage.archiveUsdm).not.toHaveBeenCalled();
  });

  test('POST /publish blocks on referential integrity issues when not force publishing', async () => {
    mockStorage.computeUsdmRevision.mockResolvedValue('sha256:rev1');
    mockStorage.readDraftLatest.mockResolvedValue({
      version: 1,
      protocolId: 'protocol-1',
      usdmRevision: 'sha256:rev1',
      status: 'draft',
      createdAt: '2026-02-14T00:00:00.000Z',
      updatedAt: '2026-02-14T00:00:00.000Z',
      updatedBy: 'tester',
      patch: [
        { op: 'replace', path: '/study/versions/0/studyDesigns/0/name', value: 'Updated' },
      ],
    });
    mockValidateSoAStructure.mockReturnValue({
      valid: false,
      issues: [{ message: 'orphan reference' }],
    });

    const req = new Request('http://localhost/api/protocols/protocol-1/semantic/publish', {
      method: 'POST',
      body: JSON.stringify({ reason: 'test publish' }),
    });

    const res = await publishPost(req, { params: Promise.resolve({ id: 'protocol-1' }) });
    const body = await res.json();

    expect(res.status).toBe(422);
    expect(body.error).toBe('referential_integrity');
    expect(mockStorage.archiveUsdm).not.toHaveBeenCalled();
    expect(mockStorage.writePublished).not.toHaveBeenCalled();
  });

  test('POST /publish returns patch_failed when patch application fails', async () => {
    mockStorage.computeUsdmRevision.mockResolvedValue('sha256:rev1');
    mockStorage.readDraftLatest.mockResolvedValue({
      version: 1,
      protocolId: 'protocol-1',
      usdmRevision: 'sha256:rev1',
      status: 'draft',
      createdAt: '2026-02-14T00:00:00.000Z',
      updatedAt: '2026-02-14T00:00:00.000Z',
      updatedBy: 'tester',
      patch: [
        { op: 'replace', path: '/study/versions/0/studyDesigns/0/name', value: 'Updated' },
      ],
    });
    mockApplySemanticPatch.mockReturnValue({ success: false, error: 'invalid pointer' });

    const req = new Request('http://localhost/api/protocols/protocol-1/semantic/publish', {
      method: 'POST',
      body: JSON.stringify({ reason: 'test publish' }),
    });

    const res = await publishPost(req, { params: Promise.resolve({ id: 'protocol-1' }) });
    const body = await res.json();

    expect(res.status).toBe(422);
    expect(body.error).toBe('patch_failed');
    expect(mockStorage.archiveUsdm).not.toHaveBeenCalled();
  });

  test('POST /publish blocks when live validation fails and forcePublish is false', async () => {
    mockStorage.computeUsdmRevision.mockResolvedValue('sha256:rev1');
    mockStorage.readDraftLatest.mockResolvedValue({
      version: 1,
      protocolId: 'protocol-1',
      usdmRevision: 'sha256:rev1',
      status: 'draft',
      createdAt: '2026-02-14T00:00:00.000Z',
      updatedAt: '2026-02-14T00:00:00.000Z',
      updatedBy: 'tester',
      patch: [
        { op: 'replace', path: '/study/versions/0/studyDesigns/0/name', value: 'Updated' },
      ],
    });
    mockSpawnValidationFailure();

    const req = new Request('http://localhost/api/protocols/protocol-1/semantic/publish', {
      method: 'POST',
      body: JSON.stringify({ reason: 'test publish' }),
    });

    const res = await publishPost(req, { params: Promise.resolve({ id: 'protocol-1' }) });
    const body = await res.json();

    expect(res.status).toBe(422);
    expect(body.error).toBe('validation_failed');
    expect(mockStorage.archiveUsdm).not.toHaveBeenCalled();
  });

  test('POST /publish allows forcePublish even when live validation fails', async () => {
    mockStorage.computeUsdmRevision.mockResolvedValue('sha256:rev1');
    mockStorage.readDraftLatest.mockResolvedValue({
      version: 1,
      protocolId: 'protocol-1',
      usdmRevision: 'sha256:rev1',
      status: 'draft',
      createdAt: '2026-02-14T00:00:00.000Z',
      updatedAt: '2026-02-14T00:00:00.000Z',
      updatedBy: 'tester',
      patch: [
        { op: 'replace', path: '/study/versions/0/studyDesigns/0/name', value: 'Updated' },
      ],
    });
    mockSpawnValidationFailure();

    const req = new Request('http://localhost/api/protocols/protocol-1/semantic/publish', {
      method: 'POST',
      body: JSON.stringify({ forcePublish: true, reason: 'override' }),
    });

    const res = await publishPost(req, { params: Promise.resolve({ id: 'protocol-1' }) });
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.success).toBe(true);
    expect(body.warning).toContain('forcePublish');
    expect(mockStorage.archiveUsdm).toHaveBeenCalledTimes(1);
    expect(mockStorage.writePublished).toHaveBeenCalledTimes(1);
  });

  test('POST /publish succeeds on clean validation and writes audit trail', async () => {
    mockStorage.computeUsdmRevision.mockResolvedValue('sha256:rev1');
    mockStorage.readDraftLatest.mockResolvedValue({
      version: 1,
      protocolId: 'protocol-1',
      usdmRevision: 'sha256:rev1',
      status: 'draft',
      createdAt: '2026-02-14T00:00:00.000Z',
      updatedAt: '2026-02-14T00:00:00.000Z',
      updatedBy: 'tester',
      patch: [
        { op: 'replace', path: '/study/versions/0/studyDesigns/0/name', value: 'Updated' },
      ],
    });
    mockSpawnValidationSuccess();

    const req = new Request('http://localhost/api/protocols/protocol-1/semantic/publish', {
      method: 'POST',
      body: JSON.stringify({ reason: 'approved', publishedBy: 'qa-user' }),
    });

    const res = await publishPost(req, { params: Promise.resolve({ id: 'protocol-1' }) });
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.success).toBe(true);
    expect(mockStorage.archiveUsdm).toHaveBeenCalledTimes(1);
    expect(mockStorage.archiveDraft).toHaveBeenCalledTimes(1);
    expect(mockStorage.writePublished).toHaveBeenCalledTimes(1);
    expect(mockStorage.deleteDraftLatest).toHaveBeenCalledTimes(1);
    expect(mockStorage.appendChangeLogEntry).toHaveBeenCalledWith(
      'protocol-1',
      expect.objectContaining({
        publishedBy: 'qa-user',
        reason: 'approved',
      }),
    );
  });
});
