/**
 * Convert raw USDM JSON Patch paths into human-readable descriptions.
 *
 * Examples:
 *   /study/versions/0/studyDesigns/0/activities/3/name
 *     → "Activity name"
 *   /study/versions/0/studyDesigns/0/encounters/@id:abc123/name
 *     → "Encounter name"
 *   /study/versions/0/studyDesigns/0/scheduleTimelines/0/instances/5
 *     → "Scheduled instance"
 *   /study/versions/0/eligibilityCriterionItems/2/text
 *     → "Eligibility criterion text"
 */

const SEGMENT_LABELS: Record<string, string> = {
  study: 'Study',
  versions: 'Version',
  studyDesigns: 'Study Design',
  activities: 'Activity',
  encounters: 'Encounter',
  epochs: 'Epoch',
  arms: 'Arm',
  studyCells: 'Study Cell',
  elements: 'Element',
  objectives: 'Objective',
  endpoints: 'Endpoint',
  estimands: 'Estimand',
  population: 'Population',
  eligibilityCriterionItems: 'Eligibility Criterion',
  narrativeContentItems: 'Narrative Content',
  studyInterventions: 'Intervention',
  administrableProducts: 'Product',
  scheduleTimelines: 'Timeline',
  instances: 'Scheduled Instance',
  timings: 'Timing',
  abbreviations: 'Abbreviation',
  amendments: 'Amendment',
  extensionAttributes: 'Extension',
  analysisPopulations: 'Analysis Population',
  indications: 'Indication',
  activityGroups: 'Activity Group',
  definedProcedures: 'Procedure',
  conditions: 'Condition',
};

const FIELD_LABELS: Record<string, string> = {
  name: 'name',
  label: 'label',
  text: 'text',
  description: 'description',
  epochId: 'epoch',
  armId: 'arm',
  encounterId: 'encounter',
  activityIds: 'activities',
  instanceType: 'type',
  level: 'level',
  category: 'category',
  decode: 'value',
  code: 'code',
};

export function humanizePath(path: string): string {
  const segments = path.split('/').filter(Boolean);
  const parts: string[] = [];
  let lastEntity = '';

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];

    // Skip numeric indices and @id: segments
    if (/^\d+$/.test(seg) || seg === '-') continue;
    if (seg.startsWith('@id:')) continue;

    // Check if this is a known entity collection
    if (SEGMENT_LABELS[seg]) {
      lastEntity = SEGMENT_LABELS[seg];
      // Only add to parts if it's a meaningful entity (not study/versions/studyDesigns)
      if (!['Study', 'Version', 'Study Design'].includes(lastEntity)) {
        parts.push(lastEntity);
      }
    } else if (FIELD_LABELS[seg]) {
      // This is a terminal field
      parts.push(FIELD_LABELS[seg]);
    } else if (seg.length > 0 && !['0', '1', '2'].includes(seg)) {
      // Unknown segment — include as-is
      parts.push(seg);
    }
  }

  if (parts.length === 0) return path;
  return parts.join(' → ');
}

/**
 * Humanize a list of changed paths, deduplicating and sorting.
 */
export function humanizeChangedPaths(paths: string[]): string[] {
  const humanized = paths.map(humanizePath);
  return [...new Set(humanized)].sort();
}
