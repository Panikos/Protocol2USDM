'use client';

import { useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EditableField, EditableCodedValue, CDISC_TERMINOLOGIES } from '@/components/semantic';
import { designPath } from '@/lib/semantic/schema';
import { useEditModeStore } from '@/stores/editModeStore';
import { cn } from '@/lib/utils';
import { Calendar, ChevronDown, ChevronRight, Info } from 'lucide-react';

interface EpochTimelineChartProps {
  usdm: Record<string, unknown> | null;
  className?: string;
}

interface Epoch {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  type?: { decode?: string; code?: string };
}

interface Encounter {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  epochId?: string;
  scheduledAtId?: string;
  type?: { decode?: string; code?: string };
  scheduledDay?: number;
  [key: string]: unknown;
}

interface Arm {
  id: string;
  name?: string;
  label?: string;
}

// Color palette for epochs
const EPOCH_COLORS = [
  { bg: 'bg-blue-100', border: 'border-blue-300', text: 'text-blue-800', dot: 'bg-blue-500' },
  { bg: 'bg-emerald-100', border: 'border-emerald-300', text: 'text-emerald-800', dot: 'bg-emerald-500' },
  { bg: 'bg-purple-100', border: 'border-purple-300', text: 'text-purple-800', dot: 'bg-purple-500' },
  { bg: 'bg-amber-100', border: 'border-amber-300', text: 'text-amber-800', dot: 'bg-amber-500' },
  { bg: 'bg-rose-100', border: 'border-rose-300', text: 'text-rose-800', dot: 'bg-rose-500' },
  { bg: 'bg-cyan-100', border: 'border-cyan-300', text: 'text-cyan-800', dot: 'bg-cyan-500' },
  { bg: 'bg-orange-100', border: 'border-orange-300', text: 'text-orange-800', dot: 'bg-orange-500' },
  { bg: 'bg-indigo-100', border: 'border-indigo-300', text: 'text-indigo-800', dot: 'bg-indigo-500' },
];

export function EpochTimelineChart({ usdm, className }: EpochTimelineChartProps) {
  const [hoveredEncounter, setHoveredEncounter] = useState<string | null>(null);
  const [selectedEncounter, setSelectedEncounter] = useState<string | null>(null);
  const isEditMode = useEditModeStore((s) => s.isEditMode);

  const data = useMemo(() => {
    if (!usdm) return null;

    const study = usdm.study as Record<string, unknown> | undefined;
    const versions = (study?.versions as unknown[]) ?? [];
    const version = versions[0] as Record<string, unknown> | undefined;
    const studyDesigns = (version?.studyDesigns as Record<string, unknown>[]) ?? [];
    const design = studyDesigns[0];
    if (!design) return null;

    const epochs = (design.epochs as Epoch[]) ?? [];
    const encounters = (design.encounters as Encounter[]) ?? [];
    const arms = (design.arms as Arm[]) ?? [];
    const scheduleTimelines = (design.scheduleTimelines as { instances?: { encounterId?: string; epochId?: string }[] }[]) ?? [];

    if (epochs.length === 0) return null;

    // Resolve encounter→epoch linkage via ScheduledActivityInstance bridge
    // USDM v4.0: encounters don't have epochId directly
    const epochIds = new Set(epochs.map(e => e.id));
    const resolvedEpoch = new Map<string, string>();
    for (const tl of scheduleTimelines) {
      for (const inst of tl.instances ?? []) {
        const encId = inst.encounterId;
        const epId = inst.epochId;
        if (encId && epId && epochIds.has(epId) && !resolvedEpoch.has(encId)) {
          resolvedEpoch.set(encId, epId);
        }
      }
    }

    const getEpochId = (enc: Encounter): string | undefined =>
      enc.epochId || resolvedEpoch.get(enc.id);

    // Group encounters by epoch
    const encountersByEpoch = new Map<string, Encounter[]>();
    const unassigned: Encounter[] = [];

    for (const enc of encounters) {
      const epochId = getEpochId(enc);
      if (epochId && epochIds.has(epochId)) {
        const list = encountersByEpoch.get(epochId) ?? [];
        list.push(enc);
        encountersByEpoch.set(epochId, list);
      } else {
        unassigned.push(enc);
      }
    }

    // Sort encounters within each epoch by scheduledDay if available
    for (const [, encs] of encountersByEpoch) {
      encs.sort((a, b) => (a.scheduledDay ?? 0) - (b.scheduledDay ?? 0));
    }

    return { epochs, encounters, arms, encountersByEpoch, unassigned, resolvedEpoch };
  }, [usdm]);

  if (!data) {
    return null;
  }

  const { epochs, encounters, encountersByEpoch, unassigned, resolvedEpoch } = data;
  const selectedEnc = selectedEncounter
    ? encounters.find(e => e.id === selectedEncounter)
    : null;
  const selectedEncEpochId = selectedEnc
    ? (selectedEnc.epochId || resolvedEpoch.get(selectedEnc.id))
    : undefined;
  const selectedEncEpochIndex = selectedEncEpochId
    ? epochs.findIndex(ep => ep.id === selectedEncEpochId)
    : -1;
  const selectedEncIndex = selectedEnc
    ? encounters.findIndex(e => e.id === selectedEnc.id)
    : -1;

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Calendar className="h-5 w-5" />
          Study Timeline
          <Badge variant="secondary">{epochs.length} epochs</Badge>
          <Badge variant="outline">{encounters.length} encounters</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Epoch bars with encounters */}
          <div className="relative">
            {/* Timeline axis line */}
            <div className="absolute left-0 right-0 top-0 bottom-0 flex items-center pointer-events-none">
              <div className="w-full h-px bg-border" />
            </div>

            <div className="flex gap-1 overflow-x-auto pb-2">
              {epochs.map((epoch, ei) => {
                const color = EPOCH_COLORS[ei % EPOCH_COLORS.length];
                const epEncounters = encountersByEpoch.get(epoch.id) ?? [];
                const epochWidth = Math.max(epEncounters.length * 64, 120);

                return (
                  <div
                    key={epoch.id}
                    className="shrink-0"
                    style={{ minWidth: epochWidth }}
                  >
                    {/* Epoch label */}
                    <div className={cn(
                      'rounded-t-lg border px-3 py-1.5 text-center text-xs font-medium',
                      color.bg, color.border, color.text
                    )}>
                      {epoch.name || epoch.label || `Epoch ${ei + 1}`}
                      {epoch.type?.decode && (
                        <div className="text-[10px] opacity-70 mt-0.5">{epoch.type.decode}</div>
                      )}
                    </div>

                    {/* Encounter markers */}
                    <div className={cn(
                      'border-x border-b rounded-b-lg px-2 py-3 min-h-[60px]',
                      color.border,
                      'bg-gradient-to-b from-white to-gray-50 dark:from-gray-900 dark:to-gray-950'
                    )}>
                      {epEncounters.length === 0 ? (
                        <div className="text-[10px] text-muted-foreground text-center italic">
                          No encounters
                        </div>
                      ) : (
                        <div className="flex gap-1 justify-center flex-wrap">
                          {epEncounters.map((enc) => {
                            const isHovered = hoveredEncounter === enc.id;
                            const isSelected = selectedEncounter === enc.id;
                            return (
                              <button
                                key={enc.id}
                                className={cn(
                                  'relative flex flex-col items-center gap-0.5 p-1 rounded transition-all',
                                  'hover:bg-white/80 dark:hover:bg-gray-800/80 hover:shadow-sm',
                                  isSelected && 'ring-2 ring-primary bg-white dark:bg-gray-800 shadow-sm',
                                )}
                                onMouseEnter={() => setHoveredEncounter(enc.id)}
                                onMouseLeave={() => setHoveredEncounter(null)}
                                onClick={() => setSelectedEncounter(
                                  selectedEncounter === enc.id ? null : enc.id
                                )}
                              >
                                {/* Dot */}
                                <div className={cn(
                                  'w-3 h-3 rounded-full border-2 border-white shadow-sm',
                                  color.dot,
                                  isHovered && 'scale-125',
                                  'transition-transform'
                                )} />
                                {/* Name */}
                                <span className={cn(
                                  'text-[9px] leading-tight max-w-[56px] truncate text-center',
                                  isSelected ? 'font-medium' : 'text-muted-foreground'
                                )}>
                                  {enc.name || enc.label || 'Visit'}
                                </span>
                                {/* Day badge */}
                                {enc.scheduledDay != null && (
                                  <span className="text-[8px] text-muted-foreground">
                                    D{enc.scheduledDay}
                                  </span>
                                )}
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* Unassigned encounters */}
              {unassigned.length > 0 && (
                <div className="shrink-0" style={{ minWidth: Math.max(unassigned.length * 64, 100) }}>
                  <div className="rounded-t-lg border px-3 py-1.5 text-center text-xs font-medium bg-gray-100 border-gray-300 text-gray-600">
                    Unassigned
                  </div>
                  <div className="border-x border-b rounded-b-lg px-2 py-3 min-h-[60px] border-gray-300 bg-gray-50/50">
                    <div className="flex gap-1 justify-center flex-wrap">
                      {unassigned.map((enc) => (
                        <button
                          key={enc.id}
                          className={cn(
                            'flex flex-col items-center gap-0.5 p-1 rounded transition-all',
                            'hover:bg-white hover:shadow-sm',
                            selectedEncounter === enc.id && 'ring-2 ring-primary bg-white shadow-sm',
                          )}
                          onClick={() => setSelectedEncounter(
                            selectedEncounter === enc.id ? null : enc.id
                          )}
                        >
                          <div className="w-3 h-3 rounded-full border-2 border-white shadow-sm bg-gray-400" />
                          <span className="text-[9px] leading-tight max-w-[56px] truncate text-muted-foreground">
                            {enc.name || enc.label || 'Visit'}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Selected encounter detail panel */}
          {selectedEnc && (
            <div className="p-4 bg-muted/30 rounded-lg border space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="font-medium flex items-center gap-2">
                  <Info className="h-4 w-4" />
                  {selectedEnc.name || selectedEnc.label || 'Encounter'}
                </h4>
                <button
                  className="text-xs text-muted-foreground hover:text-foreground"
                  onClick={() => setSelectedEncounter(null)}
                >
                  Close
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <EditableField
                  path={designPath('encounters', selectedEnc.id, 'name')}
                  value={selectedEnc.name || ''}
                  label="Name"
                  placeholder="Encounter name"
                />
                {selectedEnc.type && (
                  <EditableCodedValue
                    path={designPath('encounters', selectedEnc.id, 'type')}
                    value={selectedEnc.type}
                    label="Type"
                    options={CDISC_TERMINOLOGIES.encounterType}
                  />
                )}
                {selectedEnc.scheduledDay != null && (
                  <EditableField
                    path={designPath('encounters', selectedEnc.id, 'scheduledDay')}
                    value={String(selectedEnc.scheduledDay)}
                    label="Scheduled Day"
                    type="number"
                  />
                )}
                {selectedEnc.description && (
                  <EditableField
                    path={designPath('encounters', selectedEnc.id, 'description')}
                    value={selectedEnc.description}
                    label="Description"
                    type="textarea"
                  />
                )}
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default EpochTimelineChart;
