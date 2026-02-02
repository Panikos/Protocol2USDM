'use client';

import { useMemo } from 'react';
import { CheckCircle, AlertCircle, Eye, FileQuestion, BarChart3 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import type { ProvenanceData } from '@/lib/provenance/types';
import { calculateProvenanceStats, type ProvenanceStats as Stats } from '@/lib/provenance/types';
import { cn } from '@/lib/utils';

interface ProvenanceStatsProps {
  provenance: ProvenanceData | null;
  className?: string;
}

export function ProvenanceStats({ provenance, className }: ProvenanceStatsProps) {
  const stats = useMemo(() => {
    return calculateProvenanceStats(provenance);
  }, [provenance]);

  const items = [
    {
      label: 'Confirmed',
      value: stats.confirmed,
      icon: CheckCircle,
      color: 'text-green-600',
      bgColor: 'bg-green-50',
      description: 'Text + Vision agree',
    },
    {
      label: 'Text Only',
      value: stats.textOnly,
      icon: FileQuestion,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
      description: 'Not confirmed by vision',
    },
    {
      label: 'Needs Review',
      value: stats.needsReview,
      icon: AlertCircle,
      color: 'text-orange-600',
      bgColor: 'bg-orange-50',
      description: 'Vision-only or flagged',
    },
    {
      label: 'Orphaned',
      value: stats.orphaned,
      icon: Eye,
      color: 'text-red-600',
      bgColor: 'bg-red-50',
      description: 'No provenance data',
    },
  ];

  const confirmationRate = stats.total > 0 
    ? Math.round((stats.confirmed / stats.total) * 100) 
    : 0;

  return (
    <div className={cn('space-y-4', className)}>
      {/* Summary card */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-muted-foreground" />
              <h3 className="font-semibold">Provenance Summary</h3>
            </div>
            <div className="text-right">
              <p className="text-2xl font-bold">{confirmationRate}%</p>
              <p className="text-xs text-muted-foreground">Confirmation Rate</p>
            </div>
          </div>
          
          {/* Progress bar */}
          <div className="h-3 bg-muted rounded-full overflow-hidden flex">
            {stats.total > 0 && (
              <>
                <div 
                  className="bg-green-500 h-full transition-all"
                  style={{ width: `${(stats.confirmed / stats.total) * 100}%` }}
                />
                <div 
                  className="bg-blue-500 h-full transition-all"
                  style={{ width: `${(stats.textOnly / stats.total) * 100}%` }}
                />
                <div 
                  className="bg-orange-500 h-full transition-all"
                  style={{ width: `${(stats.needsReview / stats.total) * 100}%` }}
                />
                <div 
                  className="bg-red-500 h-full transition-all"
                  style={{ width: `${(stats.orphaned / stats.total) * 100}%` }}
                />
              </>
            )}
          </div>
          
          <p className="text-sm text-muted-foreground mt-2">
            {stats.total} total cells tracked
          </p>
        </CardContent>
      </Card>

      {/* Individual stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {items.map((item) => (
          <Card key={item.label} className={cn('border-l-4', item.color.replace('text-', 'border-'))}>
            <CardContent className="pt-4 pb-3">
              <div className="flex items-center gap-2 mb-1">
                <item.icon className={cn('h-4 w-4', item.color)} />
                <span className="text-sm font-medium">{item.label}</span>
              </div>
              <p className="text-2xl font-bold">{item.value}</p>
              <p className="text-xs text-muted-foreground">{item.description}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

// Compact inline stats for toolbar
export function ProvenanceStatsInline({ provenance }: { provenance: ProvenanceData | null }) {
  const stats = useMemo(() => calculateProvenanceStats(provenance), [provenance]);
  
  if (stats.total === 0) {
    return <span className="text-muted-foreground text-sm">No provenance data</span>;
  }

  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="flex items-center gap-1">
        <span className="w-2 h-2 rounded-full bg-green-500" />
        <span>{stats.confirmed}</span>
      </span>
      <span className="flex items-center gap-1">
        <span className="w-2 h-2 rounded-full bg-blue-500" />
        <span>{stats.textOnly}</span>
      </span>
      {stats.needsReview > 0 && (
        <span className="flex items-center gap-1 text-orange-600">
          <span className="w-2 h-2 rounded-full bg-orange-500" />
          <span>{stats.needsReview}</span>
        </span>
      )}
      {stats.orphaned > 0 && (
        <span className="flex items-center gap-1 text-red-600">
          <span className="w-2 h-2 rounded-full bg-red-500" />
          <span>{stats.orphaned}</span>
        </span>
      )}
    </div>
  );
}

export default ProvenanceStats;
