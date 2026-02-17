'use client';

import { useMemo } from 'react';
import { ProvenanceExplorer } from './ProvenanceExplorer';
import { usePatchedStudyDesign } from '@/hooks/usePatchedUsdm';
import type { ProvenanceData } from '@/lib/provenance/types';
import { Card, CardContent } from '@/components/ui/card';

interface ProvenanceViewProps {
  provenance: ProvenanceData | null;
}

export function ProvenanceView({ provenance }: ProvenanceViewProps) {
  // Use patched study design to show draft changes
  const studyDesign = usePatchedStudyDesign();

  // Extract activities and encounters from study design
  const { activities, encounters } = useMemo(() => {
    if (!studyDesign) {
      return { activities: [], encounters: [] };
    }

    const activities = (studyDesign.activities || [])
      .filter(a => !a.childIds || a.childIds.length === 0) // Exclude parent group activities
      .map(a => ({
        id: a.id,
        name: a.label || a.name,
      }));

    const encounters = (studyDesign.encounters || []).map(e => ({
      id: e.id,
      name: e.timing?.windowLabel || e.name,
    }));

    return { activities, encounters };
  }, [studyDesign]);

  if (!studyDesign) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">No study design data available</p>
        </CardContent>
      </Card>
    );
  }

  if (!provenance) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">
            No provenance data available for this protocol.
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            Run the extraction pipeline with vision validation to generate provenance data.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <ProvenanceExplorer
      provenance={provenance}
      activities={activities}
      encounters={encounters}
    />
  );
}

export default ProvenanceView;
