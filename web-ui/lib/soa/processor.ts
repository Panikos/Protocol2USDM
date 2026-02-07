/**
 * SoA Processor - Dedicated processor for Schedule of Activities edits
 * 
 * Handles USDM-aware editing operations:
 * - Cell marks (add/remove/modify X, ✓, O, etc.)
 * - Footnote superscripts on cells
 * - Activity (row) names and additions
 * - Encounter/Visit (column) names and additions
 * - Maintains USDM relationships (ScheduledActivityInstance)
 * - Tracks user-edited cells for visual highlighting
 */

import type { JsonPatchOp } from '@/lib/semantic/schema';

// ============================================================================
// Types
// ============================================================================

export type CellMark = 'X' | 'Xa' | 'Xb' | 'Xc' | 'O' | '−' | 'clear' | null;

export interface SoACellEdit {
  activityId: string;
  encounterId: string;
  mark: CellMark;
  footnoteRefs?: string[];
}

export interface SoAActivityEdit {
  activityId: string;
  name?: string;
  label?: string;
  groupId?: string;
}

export interface SoAEncounterEdit {
  encounterId: string;
  name?: string;
  epochId?: string;
  timing?: string;
}

export interface SoANewActivity {
  name: string;
  label?: string;
  groupId?: string;
  insertAfter?: string; // Activity ID to insert after
}

export interface SoANewEncounter {
  name: string;
  epochId: string;
  timing?: string;
  insertAfter?: string; // Encounter ID to insert after
}

export interface SoAEditResult {
  patches: JsonPatchOp[];
  userEditedCells: Set<string>; // "activityId|encounterId" format
  warnings: string[];
  errors: string[];
}

// Tracking for user-edited cells (persisted in extension attributes)
export interface UserEditTracker {
  editedCells: Map<string, { mark: CellMark; footnoteRefs: string[]; editedAt: string }>;
  editedActivities: Set<string>;
  editedEncounters: Set<string>;
}

// ============================================================================
// Cell Key Utilities
// ============================================================================

export function cellKey(activityId: string, encounterId: string): string {
  return `${activityId}|${encounterId}`;
}

export function parseCellKey(key: string): { activityId: string; encounterId: string } | null {
  const parts = key.split('|');
  if (parts.length !== 2) return null;
  return { activityId: parts[0], encounterId: parts[1] };
}

// ============================================================================
// UUID Generation
// ============================================================================

function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

// ============================================================================
// Main Processor Class
// ============================================================================

export class SoAProcessor {
  private usdm: Record<string, unknown>;
  private patches: JsonPatchOp[] = [];
  private warnings: string[] = [];
  private errors: string[] = [];
  private userEditedCells: Set<string> = new Set();

  constructor(usdm: Record<string, unknown>) {
    this.usdm = usdm;
  }

  // ============================================================================
  // Accessor Helpers
  // ============================================================================

  private getStudyDesign(): Record<string, unknown> | null {
    const study = this.usdm.study as Record<string, unknown> | undefined;
    const versions = study?.versions as unknown[] | undefined;
    const version = versions?.[0] as Record<string, unknown> | undefined;
    const studyDesigns = version?.studyDesigns as Record<string, unknown>[] | undefined;
    return studyDesigns?.[0] ?? null;
  }

  private getActivities(): Array<{ id: string; name: string; label?: string }> {
    const studyDesign = this.getStudyDesign();
    return (studyDesign?.activities as Array<{ id: string; name: string; label?: string }>) ?? [];
  }

  private getEncounters(): Array<{ id: string; name: string; epochId?: string }> {
    const studyDesign = this.getStudyDesign();
    return (studyDesign?.encounters as Array<{ id: string; name: string; epochId?: string }>) ?? [];
  }

  private getScheduleTimelines(): Array<{
    id: string;
    name?: string;
    instances?: Array<{
      id: string;
      instanceType?: string;
      activityIds?: string[];
      encounterId?: string;
      name?: string;
    }>;
  }> {
    const studyDesign = this.getStudyDesign();
    return (studyDesign?.scheduleTimelines as Array<{
      id: string;
      name?: string;
      instances?: Array<{
        id: string;
        instanceType?: string;
        activityIds?: string[];
        encounterId?: string;
        name?: string;
      }>;
    }>) ?? [];
  }

  private findActivityIndex(activityId: string): number {
    return this.getActivities().findIndex(a => a.id === activityId);
  }

  private findEncounterIndex(encounterId: string): number {
    return this.getEncounters().findIndex(e => e.id === encounterId);
  }

  private findScheduledInstance(activityId: string, encounterId: string): {
    timelineIndex: number;
    instanceIndex: number;
  } | null {
    const timelines = this.getScheduleTimelines();
    for (let ti = 0; ti < timelines.length; ti++) {
      const instances = timelines[ti].instances ?? [];
      for (let ii = 0; ii < instances.length; ii++) {
        const inst = instances[ii];
        if (inst.instanceType !== 'ScheduledActivityInstance') continue;
        if (inst.encounterId === encounterId && inst.activityIds?.includes(activityId)) {
          return { timelineIndex: ti, instanceIndex: ii };
        }
      }
    }
    return null;
  }

  // ============================================================================
  // Cell Editing
  // ============================================================================

  /**
   * Edit a cell mark (add, modify, or remove)
   */
  editCell(edit: SoACellEdit): void {
    const { activityId, encounterId, mark, footnoteRefs } = edit;
    const key = cellKey(activityId, encounterId);

    // Validate activity exists
    const activityIdx = this.findActivityIndex(activityId);
    if (activityIdx === -1) {
      this.errors.push(`Activity ${activityId} not found`);
      return;
    }

    // Validate encounter exists
    const encounterIdx = this.findEncounterIndex(encounterId);
    if (encounterIdx === -1) {
      this.errors.push(`Encounter ${encounterId} not found`);
      return;
    }

    // Find existing scheduled instance
    const existing = this.findScheduledInstance(activityId, encounterId);

    if (mark && mark !== 'clear' && mark !== null) {
      // Add or update mark
      if (existing) {
        // Update existing instance - always add extension attributes for mark and userEdited
        this.addMarkExtension(existing.timelineIndex, existing.instanceIndex, mark, footnoteRefs);
      } else {
        // Create new ScheduledActivityInstance
        this.createScheduledInstance(activityId, encounterId, mark, footnoteRefs);
      }
      this.userEditedCells.add(key);
    } else {
      // Remove mark
      if (existing) {
        this.removeScheduledInstance(existing.timelineIndex, existing.instanceIndex);
        this.userEditedCells.add(key); // Track removal as edit
      }
    }
  }

  private addMarkExtension(timelineIdx: number, instanceIdx: number, mark: CellMark, footnoteRefs?: string[]): void {
    const basePath = `/study/versions/0/studyDesigns/0/scheduleTimelines/${timelineIdx}/instances/${instanceIdx}`;
    
    // Check if extensionAttributes exists on the instance
    const timelines = this.getScheduleTimelines();
    const instance = timelines[timelineIdx]?.instances?.[instanceIdx] as Record<string, unknown> | undefined;
    const hasExtensionAttributes = Array.isArray(instance?.extensionAttributes);
    
    const extensions: Array<{ id: string; url: string; valueString: string; instanceType: string }> = [
      {
        id: crypto.randomUUID(),
        url: 'https://usdm.cdisc.org/extensions/x-soaCellMark',
        valueString: mark as string,
        instanceType: 'ExtensionAttribute',
      },
      {
        id: crypto.randomUUID(),
        url: 'https://usdm.cdisc.org/extensions/x-userEdited',
        valueString: 'true',
        instanceType: 'ExtensionAttribute',
      },
    ];
    
    if (footnoteRefs && footnoteRefs.length > 0) {
      extensions.push({
        id: crypto.randomUUID(),
        url: 'https://usdm.cdisc.org/extensions/x-soaFootnoteRefs',
        valueString: JSON.stringify(footnoteRefs),
        instanceType: 'ExtensionAttribute',
      });
    }
    
    if (hasExtensionAttributes) {
      // Append to existing array
      for (const ext of extensions) {
        this.patches.push({
          op: 'add',
          path: `${basePath}/extensionAttributes/-`,
          value: ext,
        });
      }
    } else {
      // Create the array with the extensions
      this.patches.push({
        op: 'add',
        path: `${basePath}/extensionAttributes`,
        value: extensions,
      });
    }
  }

  private updateCellFootnotes(timelineIdx: number, instanceIdx: number, footnoteRefs: string[]): void {
    const basePath = `/study/versions/0/studyDesigns/0/scheduleTimelines/${timelineIdx}/instances/${instanceIdx}`;
    
    // Check if extensionAttributes exists on the instance
    const timelines = this.getScheduleTimelines();
    const instance = timelines[timelineIdx]?.instances?.[instanceIdx] as Record<string, unknown> | undefined;
    const hasExtensionAttributes = Array.isArray(instance?.extensionAttributes);
    
    const ext = {
      id: crypto.randomUUID(),
      url: 'https://usdm.cdisc.org/extensions/x-soaFootnoteRefs',
      valueString: JSON.stringify(footnoteRefs),
      instanceType: 'ExtensionAttribute',
    };
    
    if (hasExtensionAttributes) {
      this.patches.push({
        op: 'add',
        path: `${basePath}/extensionAttributes/-`,
        value: ext,
      });
    } else {
      this.patches.push({
        op: 'add',
        path: `${basePath}/extensionAttributes`,
        value: [ext],
      });
    }
  }

  private createScheduledInstance(
    activityId: string,
    encounterId: string,
    mark: CellMark,
    footnoteRefs?: string[]
  ): void {
    const timelines = this.getScheduleTimelines();
    if (timelines.length === 0) {
      // Create a timeline if none exists
      this.patches.push({
        op: 'add',
        path: '/study/versions/0/studyDesigns/0/scheduleTimelines/-',
        value: {
          id: generateUUID(),
          instanceType: 'ScheduleTimeline',
          name: 'Main Timeline',
          mainTimeline: true,
          instances: [],
        },
      });
      this.warnings.push('Created new ScheduleTimeline as none existed');
    }

    const timelineIdx = 0; // Use first timeline
    const instanceId = generateUUID();
    
    const newInstance: Record<string, unknown> = {
      id: instanceId,
      instanceType: 'ScheduledActivityInstance',
      activityIds: [activityId],
      encounterId: encounterId,
      name: `Activity at Visit`,
      extensionAttributes: [
        {
          id: crypto.randomUUID(),
          url: 'https://usdm.cdisc.org/extensions/x-userEdited',
          valueString: 'true',
          instanceType: 'ExtensionAttribute',
        },
        {
          id: crypto.randomUUID(),
          url: 'https://usdm.cdisc.org/extensions/x-soaCellMark',
          valueString: mark || 'X',
          instanceType: 'ExtensionAttribute',
        },
      ],
    };

    // Add footnote refs if provided
    if (footnoteRefs && footnoteRefs.length > 0) {
      (newInstance.extensionAttributes as Array<Record<string, unknown>>).push({
        id: crypto.randomUUID(),
        url: 'https://usdm.cdisc.org/extensions/x-soaFootnoteRefs',
        valueString: JSON.stringify(footnoteRefs),
        instanceType: 'ExtensionAttribute',
      });
    }

    this.patches.push({
      op: 'add',
      path: `/study/versions/0/studyDesigns/0/scheduleTimelines/${timelineIdx}/instances/-`,
      value: newInstance,
    });
  }

  private removeScheduledInstance(timelineIdx: number, instanceIdx: number): void {
    this.patches.push({
      op: 'remove',
      path: `/study/versions/0/studyDesigns/0/scheduleTimelines/${timelineIdx}/instances/${instanceIdx}`,
    });
  }

  // ============================================================================
  // Activity Editing
  // ============================================================================

  /**
   * Edit an activity's name or other properties
   */
  editActivity(edit: SoAActivityEdit): void {
    const idx = this.findActivityIndex(edit.activityId);
    if (idx === -1) {
      this.errors.push(`Activity ${edit.activityId} not found`);
      return;
    }

    const basePath = `/study/versions/0/studyDesigns/0/activities/${idx}`;

    if (edit.name !== undefined) {
      this.patches.push({
        op: 'replace',
        path: `${basePath}/name`,
        value: edit.name,
      });
    }

    if (edit.label !== undefined) {
      this.patches.push({
        op: 'replace',
        path: `${basePath}/label`,
        value: edit.label,
      });
    }
  }

  /**
   * Add a new activity (row)
   */
  addActivity(newActivity: SoANewActivity): string {
    const activityId = generateUUID();
    const activities = this.getActivities();
    
    let insertIdx = activities.length;
    if (newActivity.insertAfter) {
      const afterIdx = activities.findIndex(a => a.id === newActivity.insertAfter);
      if (afterIdx >= 0) {
        insertIdx = afterIdx + 1;
      }
    }

    const activity: Record<string, unknown> = {
      id: activityId,
      instanceType: 'Activity',
      name: newActivity.name,
      label: newActivity.label ?? newActivity.name,
      extensionAttributes: [
        {
          url: 'https://usdm.cdisc.org/extensions/x-userEdited',
          valueString: 'true',
        },
        {
          url: 'https://usdm.cdisc.org/extensions/x-activitySource',
          valueString: 'user',
        },
      ],
    };

    // Use splice-like insert by adding at position
    if (insertIdx >= activities.length) {
      this.patches.push({
        op: 'add',
        path: '/study/versions/0/studyDesigns/0/activities/-',
        value: activity,
      });
    } else {
      this.patches.push({
        op: 'add',
        path: `/study/versions/0/studyDesigns/0/activities/${insertIdx}`,
        value: activity,
      });
    }

    // If group specified, add to activity group
    if (newActivity.groupId) {
      this.addActivityToGroup(activityId, newActivity.groupId);
    }

    return activityId;
  }

  private addActivityToGroup(activityId: string, groupId: string): void {
    const studyDesign = this.getStudyDesign();
    const groups = (studyDesign?.activityGroups as Array<{ id: string; activityIds?: string[] }>) ?? [];
    const groupIdx = groups.findIndex(g => g.id === groupId);
    
    if (groupIdx === -1) {
      this.warnings.push(`Activity group ${groupId} not found`);
      return;
    }

    this.patches.push({
      op: 'add',
      path: `/study/versions/0/studyDesigns/0/activityGroups/${groupIdx}/activityIds/-`,
      value: activityId,
    });
  }

  // ============================================================================
  // Encounter Editing
  // ============================================================================

  /**
   * Edit an encounter's name or other properties
   */
  editEncounter(edit: SoAEncounterEdit): void {
    const idx = this.findEncounterIndex(edit.encounterId);
    if (idx === -1) {
      this.errors.push(`Encounter ${edit.encounterId} not found`);
      return;
    }

    const basePath = `/study/versions/0/studyDesigns/0/encounters/${idx}`;

    if (edit.name !== undefined) {
      this.patches.push({
        op: 'replace',
        path: `${basePath}/name`,
        value: edit.name,
      });
    }

    if (edit.epochId !== undefined) {
      this.patches.push({
        op: 'replace',
        path: `${basePath}/epochId`,
        value: edit.epochId,
      });
    }
  }

  /**
   * Add a new encounter (column/visit)
   */
  addEncounter(newEncounter: SoANewEncounter): string {
    const encounterId = generateUUID();
    const encounters = this.getEncounters();
    
    let insertIdx = encounters.length;
    if (newEncounter.insertAfter) {
      const afterIdx = encounters.findIndex(e => e.id === newEncounter.insertAfter);
      if (afterIdx >= 0) {
        insertIdx = afterIdx + 1;
      }
    }

    const encounter: Record<string, unknown> = {
      id: encounterId,
      instanceType: 'Encounter',
      name: newEncounter.name,
      epochId: newEncounter.epochId,
      extensionAttributes: [
        {
          url: 'https://usdm.cdisc.org/extensions/x-userEdited',
          valueString: 'true',
        },
      ],
    };

    if (newEncounter.timing) {
      (encounter as Record<string, unknown>).timing = {
        windowLabel: newEncounter.timing,
      };
    }

    if (insertIdx >= encounters.length) {
      this.patches.push({
        op: 'add',
        path: '/study/versions/0/studyDesigns/0/encounters/-',
        value: encounter,
      });
    } else {
      this.patches.push({
        op: 'add',
        path: `/study/versions/0/studyDesigns/0/encounters/${insertIdx}`,
        value: encounter,
      });
    }

    return encounterId;
  }

  // ============================================================================
  // Batch Operations
  // ============================================================================

  /**
   * Process multiple cell edits at once
   */
  editCells(edits: SoACellEdit[]): void {
    for (const edit of edits) {
      this.editCell(edit);
    }
  }

  // ============================================================================
  // Result
  // ============================================================================

  /**
   * Get the result of all operations
   */
  getResult(): SoAEditResult {
    return {
      patches: this.patches,
      userEditedCells: this.userEditedCells,
      warnings: this.warnings,
      errors: this.errors,
    };
  }

  /**
   * Reset processor state
   */
  reset(): void {
    this.patches = [];
    this.warnings = [];
    this.errors = [];
    this.userEditedCells = new Set();
  }
}

// ============================================================================
// Validation Utilities
// ============================================================================

/**
 * Validate USDM relationships for SoA structure
 */
export function validateSoAStructure(usdm: Record<string, unknown>): {
  valid: boolean;
  issues: string[];
} {
  const issues: string[] = [];
  
  const study = usdm.study as Record<string, unknown> | undefined;
  const versions = study?.versions as unknown[] | undefined;
  const version = versions?.[0] as Record<string, unknown> | undefined;
  const studyDesigns = version?.studyDesigns as Record<string, unknown>[] | undefined;
  const studyDesign = studyDesigns?.[0];

  if (!studyDesign) {
    issues.push('No study design found');
    return { valid: false, issues };
  }

  const activities = (studyDesign.activities as Array<{ id: string }>) ?? [];
  const encounters = (studyDesign.encounters as Array<{ id: string; epochId?: string }>) ?? [];
  const epochs = (studyDesign.epochs as Array<{ id: string }>) ?? [];
  const timelines = (studyDesign.scheduleTimelines as Array<{
    instances?: Array<{
      activityIds?: string[];
      encounterId?: string;
    }>;
  }>) ?? [];

  const activityIds = new Set(activities.map(a => a.id));
  const encounterIds = new Set(encounters.map(e => e.id));
  const epochIds = new Set(epochs.map(e => e.id));

  // Check encounters have valid epochId
  for (const enc of encounters) {
    if (enc.epochId && !epochIds.has(enc.epochId)) {
      issues.push(`Encounter references non-existent epoch: ${enc.epochId}`);
    }
  }

  // Check scheduled instances have valid references
  for (const timeline of timelines) {
    for (const instance of timeline.instances ?? []) {
      for (const actId of instance.activityIds ?? []) {
        if (!activityIds.has(actId)) {
          issues.push(`Scheduled instance references non-existent activity: ${actId}`);
        }
      }
      if (instance.encounterId && !encounterIds.has(instance.encounterId)) {
        issues.push(`Scheduled instance references non-existent encounter: ${instance.encounterId}`);
      }
    }
  }

  return {
    valid: issues.length === 0,
    issues,
  };
}

// ============================================================================
// User Edit Tracking
// ============================================================================

/**
 * Check if a cell was user-edited based on extension attributes
 */
export function isUserEditedCell(
  usdm: Record<string, unknown>,
  activityId: string,
  encounterId: string
): boolean {
  const study = usdm.study as Record<string, unknown> | undefined;
  const versions = study?.versions as unknown[] | undefined;
  const version = versions?.[0] as Record<string, unknown> | undefined;
  const studyDesigns = version?.studyDesigns as Record<string, unknown>[] | undefined;
  const studyDesign = studyDesigns?.[0];

  if (!studyDesign) return false;

  const timelines = (studyDesign.scheduleTimelines as Array<{
    instances?: Array<{
      activityIds?: string[];
      encounterId?: string;
      extensionAttributes?: Array<{ url?: string; valueString?: string }>;
    }>;
  }>) ?? [];

  for (const timeline of timelines) {
    for (const instance of timeline.instances ?? []) {
      if (instance.encounterId !== encounterId) continue;
      if (!instance.activityIds?.includes(activityId)) continue;
      
      // Check for user-edited extension
      for (const ext of instance.extensionAttributes ?? []) {
        if (ext.url?.includes('x-userEdited') && ext.valueString === 'true') {
          return true;
        }
      }
    }
  }

  return false;
}

/**
 * Get the mark type from a cell (including special marks like Xa, Xb, etc.)
 */
export function getCellMark(
  usdm: Record<string, unknown>,
  activityId: string,
  encounterId: string
): CellMark {
  const study = usdm.study as Record<string, unknown> | undefined;
  const versions = study?.versions as unknown[] | undefined;
  const version = versions?.[0] as Record<string, unknown> | undefined;
  const studyDesigns = version?.studyDesigns as Record<string, unknown>[] | undefined;
  const studyDesign = studyDesigns?.[0];

  if (!studyDesign) return null;

  const timelines = (studyDesign.scheduleTimelines as Array<{
    instances?: Array<{
      activityIds?: string[];
      encounterId?: string;
      extensionAttributes?: Array<{ url?: string; valueString?: string }>;
    }>;
  }>) ?? [];

  for (const timeline of timelines) {
    for (const instance of timeline.instances ?? []) {
      if (instance.encounterId !== encounterId) continue;
      if (!instance.activityIds?.includes(activityId)) continue;
      
      // Check for custom mark extension
      for (const ext of instance.extensionAttributes ?? []) {
        if (ext.url?.includes('x-soaCellMark') && ext.valueString) {
          return ext.valueString as CellMark;
        }
      }
      
      // Default to X if instance exists
      return 'X';
    }
  }

  return null;
}

export default SoAProcessor;
