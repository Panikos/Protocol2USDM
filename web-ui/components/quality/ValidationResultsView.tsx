'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, XCircle, AlertTriangle, Info, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ValidationResultsViewProps {
  protocolId: string;
}

interface ExtractionIssue {
  issue_type: string;
  activity_id?: string;
  activity_name?: string;
  timepoint_id?: string;
  timepoint_name?: string;
  confidence?: number;
  details?: string;
}

interface ValidationData {
  extraction?: {
    success?: boolean;
    issues?: ExtractionIssue[];
  };
  schema?: {
    valid?: boolean;
    errors?: { message: string; path?: string }[];
  };
  usdm?: unknown;
}

export function ValidationResultsView({ protocolId }: ValidationResultsViewProps) {
  const [data, setData] = useState<ValidationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchValidation() {
      try {
        const res = await fetch(`/api/protocols/${protocolId}/validation`);
        if (!res.ok) {
          if (res.status === 404) {
            setError('No validation data available');
          } else {
            setError('Failed to load validation data');
          }
          return;
        }
        const json = await res.json();
        setData(json);
      } catch {
        setError('Failed to load validation data');
      } finally {
        setLoading(false);
      }
    }
    fetchValidation();
  }, [protocolId]);

  if (loading) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Loader2 className="h-8 w-8 mx-auto mb-4 animate-spin text-muted-foreground" />
          <p className="text-muted-foreground">Loading validation results...</p>
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Info className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">{error || 'No validation data available'}</p>
          <p className="text-sm text-muted-foreground mt-2">
            Validation results will appear here after running extraction
          </p>
        </CardContent>
      </Card>
    );
  }

  const extractionData = data.extraction;
  const issues = extractionData?.issues ?? [];
  const isSuccess = extractionData?.success ?? true;

  // Group issues by type
  const hallucinations = issues.filter(i => i.issue_type === 'possible_hallucination');
  const missedTicks = issues.filter(i => i.issue_type === 'missed_tick');
  const otherIssues = issues.filter(i => 
    i.issue_type !== 'possible_hallucination' && i.issue_type !== 'missed_tick'
  );

  return (
    <div className="space-y-6">
      {/* Extraction Status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {isSuccess && issues.length === 0 ? (
              <CheckCircle2 className="h-5 w-5 text-green-600" />
            ) : issues.length > 0 ? (
              <AlertTriangle className="h-5 w-5 text-amber-600" />
            ) : (
              <XCircle className="h-5 w-5 text-red-600" />
            )}
            Extraction Validation
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <div className={cn(
              'text-2xl font-bold',
              isSuccess ? 'text-green-600' : 'text-red-600'
            )}>
              {isSuccess ? 'SUCCESS' : 'FAILED'}
            </div>
            <div className="flex gap-2">
              {hallucinations.length > 0 && (
                <Badge variant="secondary" className="bg-amber-100 text-amber-800">
                  {hallucinations.length} Possible Hallucinations
                </Badge>
              )}
              {missedTicks.length > 0 && (
                <Badge variant="secondary" className="bg-blue-100 text-blue-800">
                  {missedTicks.length} Missed Ticks
                </Badge>
              )}
              {otherIssues.length > 0 && (
                <Badge variant="outline">{otherIssues.length} Other</Badge>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Hallucinations */}
      {hallucinations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-600" />
              Possible Hallucinations
              <Badge variant="secondary">{hallucinations.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-[400px] overflow-auto">
              {hallucinations.map((issue, i) => (
                <div key={i} className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="font-medium">{issue.activity_name}</span>
                      <span className="text-muted-foreground"> at </span>
                      <span className="font-medium">{issue.timepoint_name}</span>
                    </div>
                    {issue.confidence !== undefined && (
                      <Badge variant="outline" className="text-xs">
                        {(issue.confidence * 100).toFixed(0)}% conf
                      </Badge>
                    )}
                  </div>
                  {issue.details && (
                    <p className="text-xs text-muted-foreground mt-1">{issue.details}</p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Missed Ticks */}
      {missedTicks.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Info className="h-5 w-5 text-blue-600" />
              Missed Ticks
              <Badge variant="secondary">{missedTicks.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-[400px] overflow-auto">
              {missedTicks.map((issue, i) => (
                <div key={i} className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="font-medium">{issue.activity_name}</span>
                      <span className="text-muted-foreground"> at </span>
                      <span className="font-medium">{issue.timepoint_name}</span>
                    </div>
                    {issue.confidence !== undefined && (
                      <Badge variant="outline" className="text-xs">
                        {(issue.confidence * 100).toFixed(0)}% conf
                      </Badge>
                    )}
                  </div>
                  {issue.details && (
                    <p className="text-xs text-muted-foreground mt-1">{issue.details}</p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* All Clear */}
      {issues.length === 0 && isSuccess && (
        <Card>
          <CardContent className="py-8 text-center">
            <CheckCircle2 className="h-12 w-12 mx-auto mb-4 text-green-600" />
            <p className="text-lg font-medium text-green-600">No validation issues found!</p>
            <p className="text-sm text-muted-foreground mt-2">
              Extraction completed without detected problems
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default ValidationResultsView;
