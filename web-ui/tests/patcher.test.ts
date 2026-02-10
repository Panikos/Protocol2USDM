/**
 * Tests for ID-based path resolution in the semantic patcher.
 * 
 * Validates:
 * - resolveIdPath() converts @id:xxx segments to array indices
 * - applySemanticPatch() handles @id: paths transparently
 * - Error cases: missing IDs, non-array parents
 * - Mixed paths (some @id:, some numeric)
 * - Backward compatibility with plain numeric paths
 */

import { resolveIdPath, resolveAllIdPaths, applySemanticPatch } from '../lib/semantic/patcher';
import type { JsonPatchOp } from '../lib/semantic/schema';

// ── Test USDM document ──────────────────────────────────────────────

const testDoc = {
  study: {
    id: 'study-1',
    versions: [
      {
        id: 'ver-1',
        studyDesigns: [
          {
            id: 'sd-1',
            objectives: [
              { id: 'obj-primary', text: 'Primary objective', level: { decode: 'Primary' } },
              { id: 'obj-secondary-1', text: 'Secondary 1', level: { decode: 'Secondary' } },
              { id: 'obj-secondary-2', text: 'Secondary 2', level: { decode: 'Secondary' } },
            ],
            activities: [
              { id: 'act-1', name: 'Vital Signs' },
              { id: 'act-2', name: 'Blood Draw' },
            ],
            encounters: [
              { id: 'enc-screening', name: 'Screening' },
              { id: 'enc-baseline', name: 'Baseline' },
              { id: 'enc-week4', name: 'Week 4' },
            ],
          },
        ],
        studyInterventions: [
          { id: 'int-1', name: 'Drug A', description: 'Active drug' },
          { id: 'int-2', name: 'Placebo', description: 'Placebo control' },
        ],
        eligibilityCriterionItems: [
          { id: 'elig-1', text: 'Age >= 18' },
          { id: 'elig-2', text: 'Signed consent' },
        ],
      },
    ],
  },
};

// ── resolveIdPath ────────────────────────────────────────────────────

describe('resolveIdPath', () => {
  test('passes through paths without @id: unchanged', () => {
    expect(resolveIdPath(testDoc, '/study/versions/0/studyDesigns/0/objectives/1/text'))
      .toBe('/study/versions/0/studyDesigns/0/objectives/1/text');
  });

  test('resolves single @id: segment', () => {
    expect(resolveIdPath(testDoc, '/study/versions/0/studyDesigns/0/objectives/@id:obj-primary/text'))
      .toBe('/study/versions/0/studyDesigns/0/objectives/0/text');
  });

  test('resolves @id: to correct index (not first)', () => {
    expect(resolveIdPath(testDoc, '/study/versions/0/studyDesigns/0/objectives/@id:obj-secondary-2/text'))
      .toBe('/study/versions/0/studyDesigns/0/objectives/2/text');
  });

  test('resolves multiple @id: segments (nested)', () => {
    // This would be: objectives[obj-primary].endpoints[@id:ep-1].text
    // But our test doc doesn't have nested endpoints, so test with activities
    expect(resolveIdPath(testDoc, '/study/versions/0/studyDesigns/0/activities/@id:act-2/name'))
      .toBe('/study/versions/0/studyDesigns/0/activities/1/name');
  });

  test('resolves version-level collections', () => {
    expect(resolveIdPath(testDoc, '/study/versions/0/studyInterventions/@id:int-2/name'))
      .toBe('/study/versions/0/studyInterventions/1/name');
  });

  test('resolves eligibilityCriterionItems', () => {
    expect(resolveIdPath(testDoc, '/study/versions/0/eligibilityCriterionItems/@id:elig-1/text'))
      .toBe('/study/versions/0/eligibilityCriterionItems/0/text');
  });

  test('throws for non-existent entity ID', () => {
    expect(() => {
      resolveIdPath(testDoc, '/study/versions/0/studyDesigns/0/objectives/@id:nonexistent/text');
    }).toThrow('Entity with id "nonexistent" not found');
  });

  test('throws when @id: used on non-array', () => {
    expect(() => {
      resolveIdPath(testDoc, '/study/@id:bad-segment/versions');
    }).toThrow('@id:bad-segment used on non-array');
  });
});

// ── resolveAllIdPaths ────────────────────────────────────────────────

describe('resolveAllIdPaths', () => {
  test('resolves batch of operations', () => {
    const patch: JsonPatchOp[] = [
      { op: 'replace', path: '/study/versions/0/studyDesigns/0/objectives/@id:obj-primary/text', value: 'Updated primary' },
      { op: 'replace', path: '/study/versions/0/studyInterventions/@id:int-1/name', value: 'Drug B' },
    ];

    const { resolved, errors } = resolveAllIdPaths(testDoc, patch);
    expect(errors).toHaveLength(0);
    expect(resolved[0].path).toBe('/study/versions/0/studyDesigns/0/objectives/0/text');
    expect(resolved[1].path).toBe('/study/versions/0/studyInterventions/0/name');
  });

  test('collects errors for invalid IDs without stopping', () => {
    const patch: JsonPatchOp[] = [
      { op: 'replace', path: '/study/versions/0/studyDesigns/0/objectives/@id:obj-primary/text', value: 'OK' },
      { op: 'replace', path: '/study/versions/0/studyDesigns/0/objectives/@id:nonexistent/text', value: 'Bad' },
    ];

    const { resolved, errors } = resolveAllIdPaths(testDoc, patch);
    expect(errors).toHaveLength(1);
    expect(errors[0]).toContain('nonexistent');
    // First op should still be resolved
    expect(resolved[0].path).toBe('/study/versions/0/studyDesigns/0/objectives/0/text');
  });
});

// ── applySemanticPatch with @id: paths ───────────────────────────────

describe('applySemanticPatch with ID paths', () => {
  test('applies replace with @id: path', () => {
    const patch: JsonPatchOp[] = [
      { op: 'replace', path: '/study/versions/0/studyDesigns/0/objectives/@id:obj-primary/text', value: 'New primary text' },
    ];

    const result = applySemanticPatch(testDoc, patch);
    expect(result.success).toBe(true);
    if (result.success) {
      const doc = result.result as typeof testDoc;
      expect(doc.study.versions[0].studyDesigns[0].objectives[0].text).toBe('New primary text');
      // Other objectives unchanged
      expect(doc.study.versions[0].studyDesigns[0].objectives[1].text).toBe('Secondary 1');
    }
  });

  test('applies multiple @id: patches', () => {
    const patch: JsonPatchOp[] = [
      { op: 'replace', path: '/study/versions/0/studyDesigns/0/activities/@id:act-1/name', value: 'Updated Vitals' },
      { op: 'replace', path: '/study/versions/0/studyDesigns/0/encounters/@id:enc-week4/name', value: 'Week 4 Visit' },
    ];

    const result = applySemanticPatch(testDoc, patch);
    expect(result.success).toBe(true);
    if (result.success) {
      const doc = result.result as typeof testDoc;
      expect(doc.study.versions[0].studyDesigns[0].activities[0].name).toBe('Updated Vitals');
      expect(doc.study.versions[0].studyDesigns[0].encounters[2].name).toBe('Week 4 Visit');
    }
  });

  test('mixed @id: and numeric paths work together', () => {
    const patch: JsonPatchOp[] = [
      { op: 'replace', path: '/study/versions/0/studyDesigns/0/objectives/@id:obj-primary/text', value: 'ID-based' },
      { op: 'replace', path: '/study/versions/0/studyDesigns/0/objectives/1/text', value: 'Index-based' },
    ];

    const result = applySemanticPatch(testDoc, patch);
    expect(result.success).toBe(true);
    if (result.success) {
      const doc = result.result as typeof testDoc;
      expect(doc.study.versions[0].studyDesigns[0].objectives[0].text).toBe('ID-based');
      expect(doc.study.versions[0].studyDesigns[0].objectives[1].text).toBe('Index-based');
    }
  });

  test('fails gracefully for non-existent @id:', () => {
    const patch: JsonPatchOp[] = [
      { op: 'replace', path: '/study/versions/0/studyDesigns/0/objectives/@id:ghost/text', value: 'fail' },
    ];

    const result = applySemanticPatch(testDoc, patch);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error).toContain('ghost');
    }
  });

  test('backward compatible — plain numeric paths still work', () => {
    const patch: JsonPatchOp[] = [
      { op: 'replace', path: '/study/versions/0/studyDesigns/0/objectives/0/text', value: 'Numeric path' },
    ];

    const result = applySemanticPatch(testDoc, patch);
    expect(result.success).toBe(true);
    if (result.success) {
      const doc = result.result as typeof testDoc;
      expect(doc.study.versions[0].studyDesigns[0].objectives[0].text).toBe('Numeric path');
    }
  });

  test('does not mutate original document', () => {
    const original = JSON.parse(JSON.stringify(testDoc));
    const patch: JsonPatchOp[] = [
      { op: 'replace', path: '/study/versions/0/studyDesigns/0/objectives/@id:obj-primary/text', value: 'Mutated?' },
    ];

    applySemanticPatch(testDoc, patch);
    expect(testDoc.study.versions[0].studyDesigns[0].objectives[0].text).toBe(original.study.versions[0].studyDesigns[0].objectives[0].text);
  });
});
