'use client';

import { useState, useMemo } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Info,
  CheckCircle,
  ChevronRight,
  Filter,
  Shield,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { IntegrityReport, IntegrityFinding } from '@/lib/provenance/types';

interface IntegrityReportViewProps {
  report: IntegrityReport | null;
}

const SEVERITY_CONFIG = {
  error: {
    icon: AlertCircle,
    color: 'text-red-600 dark:text-red-400',
    bg: 'bg-red-50 dark:bg-red-950/30',
    border: 'border-red-200 dark:border-red-900',
    badge: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
    label: 'Error',
  },
  warning: {
    icon: AlertTriangle,
    color: 'text-amber-600 dark:text-amber-400',
    bg: 'bg-amber-50 dark:bg-amber-950/30',
    border: 'border-amber-200 dark:border-amber-900',
    badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
    label: 'Warning',
  },
  info: {
    icon: Info,
    color: 'text-blue-600 dark:text-blue-400',
    bg: 'bg-blue-50 dark:bg-blue-950/30',
    border: 'border-blue-200 dark:border-blue-900',
    badge: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
    label: 'Info',
  },
} as const;

const RULE_LABELS: Record<string, string> = {
  dangling_reference: 'Dangling Reference',
  orphan_entity: 'Orphan Entity',
  arm_not_in_cell: 'Arm Missing Cell',
  epoch_not_in_cell: 'Epoch Missing Cell',
  estimand_endpoint_mismatch: 'Estimand→Endpoint Mismatch',
  unnamed_activities: 'Unnamed Activities',
  uncategorized_criteria: 'Uncategorized Criteria',
  unleveled_objectives: 'Unleveled Objectives',
  untyped_interventions: 'Untyped Interventions',
  duplicate_id: 'Duplicate ID',
};

export function IntegrityReportView({ report }: IntegrityReportViewProps) {
  const [severityFilter, setSeverityFilter] = useState<string | null>(null);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  const filteredFindings = useMemo(() => {
    if (!report) return [];
    if (!severityFilter) return report.findings;
    return report.findings.filter((f) => f.severity === severityFilter);
  }, [report, severityFilter]);

  if (!report) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Shield className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">
            No integrity report available.
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            Run the pipeline to generate a referential integrity report.
          </p>
        </CardContent>
      </Card>
    );
  }

  const { summary } = report;
  const isClean = summary.errors === 0 && summary.warnings === 0;

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <Card>
        <CardContent className="py-4">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              {isClean ? (
                <CheckCircle className="h-5 w-5 text-green-500" />
              ) : (
                <Shield className="h-5 w-5 text-amber-500" />
              )}
              <span className="font-medium">
                {isClean
                  ? 'All integrity checks passed'
                  : `${summary.totalFindings} finding${summary.totalFindings !== 1 ? 's' : ''}`}
              </span>
            </div>

            <div className="flex items-center gap-2 ml-auto">
              <Button
                variant={severityFilter === null ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setSeverityFilter(null)}
              >
                All ({summary.totalFindings})
              </Button>
              {summary.errors > 0 && (
                <Button
                  variant={severityFilter === 'error' ? 'default' : 'ghost'}
                  size="sm"
                  onClick={() => setSeverityFilter('error')}
                  className="text-red-600"
                >
                  <AlertCircle className="h-3.5 w-3.5 mr-1" />
                  {summary.errors}
                </Button>
              )}
              {summary.warnings > 0 && (
                <Button
                  variant={severityFilter === 'warning' ? 'default' : 'ghost'}
                  size="sm"
                  onClick={() => setSeverityFilter('warning')}
                  className="text-amber-600"
                >
                  <AlertTriangle className="h-3.5 w-3.5 mr-1" />
                  {summary.warnings}
                </Button>
              )}
              {summary.info > 0 && (
                <Button
                  variant={severityFilter === 'info' ? 'default' : 'ghost'}
                  size="sm"
                  onClick={() => setSeverityFilter('info')}
                  className="text-blue-600"
                >
                  <Info className="h-3.5 w-3.5 mr-1" />
                  {summary.info}
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Findings list */}
      {filteredFindings.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Filter className="h-4 w-4" />
              Findings
              {severityFilter && (
                <Badge variant="outline" className="ml-2 capitalize">
                  {severityFilter}
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {filteredFindings.map((finding, idx) => (
                <FindingRow
                  key={idx}
                  finding={finding}
                  isExpanded={expandedIdx === idx}
                  onToggle={() =>
                    setExpandedIdx(expandedIdx === idx ? null : idx)
                  }
                />
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function FindingRow({
  finding,
  isExpanded,
  onToggle,
}: {
  finding: IntegrityFinding;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const config = SEVERITY_CONFIG[finding.severity];
  const Icon = config.icon;
  const ruleLabel = RULE_LABELS[finding.rule] || finding.rule;

  return (
    <div className={cn('border rounded-lg', config.border)}>
      <button
        onClick={onToggle}
        className={cn(
          'w-full flex items-center gap-2 px-3 py-2 text-left transition-colors',
          config.bg,
          'hover:opacity-80'
        )}
      >
        <ChevronRight
          className={cn(
            'h-3.5 w-3.5 text-muted-foreground transition-transform shrink-0',
            isExpanded && 'rotate-90'
          )}
        />
        <Icon className={cn('h-4 w-4 shrink-0', config.color)} />
        <span className="text-sm flex-1 truncate">{finding.message}</span>
        <Badge className={cn('text-[10px] shrink-0', config.badge)}>
          {ruleLabel}
        </Badge>
        {finding.entityType && (
          <span className="text-xs text-muted-foreground shrink-0">
            {finding.entityType}
          </span>
        )}
      </button>

      {isExpanded && (
        <div className="px-4 pb-3 pt-2 border-t text-sm space-y-1.5">
          {finding.entityIds && finding.entityIds.length > 0 && (
            <div>
              <span className="text-xs text-muted-foreground">Entity IDs: </span>
              <span className="font-mono text-xs">
                {finding.entityIds.join(', ')}
              </span>
            </div>
          )}
          {finding.details &&
            Object.entries(finding.details).map(([key, val]) => (
              <div key={key}>
                <span className="text-xs text-muted-foreground">{key}: </span>
                <span className="font-mono text-xs">
                  {typeof val === 'string' ? val : JSON.stringify(val)}
                </span>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

export default IntegrityReportView;
