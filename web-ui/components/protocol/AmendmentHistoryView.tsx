'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EditableField } from '@/components/semantic';
import { EditableCodedValue, CDISC_TERMINOLOGIES } from '@/components/semantic/EditableCodedValue';
import { FileEdit, Calendar, ArrowRight } from 'lucide-react';

interface AmendmentHistoryViewProps {
  usdm: Record<string, unknown> | null;
}

interface Amendment {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  summary?: string;
  number?: string | number;
  scope?: Record<string, unknown>;
  effectiveDate?: string;
  date?: string;
  reason?: string;
  changes?: unknown[];
  primaryReason?: Record<string, unknown>;
  secondaryReasons?: Record<string, unknown>[];
  impacts?: unknown[];
  previousVersion?: string;
  newVersion?: string;
}

/** Safely extract a human-readable string from a value that might be a string, Code object, or nested structure. */
function toDisplayString(val: unknown): string {
  if (val == null) return '';
  if (typeof val === 'string') return val;
  if (typeof val === 'number' || typeof val === 'boolean') return String(val);
  if (typeof val === 'object') {
    const obj = val as Record<string, unknown>;
    // StudyAmendmentReason → otherReason or code.decode
    if (obj.otherReason && typeof obj.otherReason === 'string') return obj.otherReason;
    // Code object → decode
    if (obj.decode && typeof obj.decode === 'string') return obj.decode;
    // Nested code.decode
    if (obj.code && typeof obj.code === 'object') {
      const code = obj.code as Record<string, unknown>;
      if (code.decode && typeof code.decode === 'string') return code.decode;
    }
    // StudyChange → description or text
    if (obj.description && typeof obj.description === 'string') return obj.description;
    if (obj.text && typeof obj.text === 'string') return obj.text;
    if (obj.name && typeof obj.name === 'string') return obj.name;
    return JSON.stringify(val);
  }
  return String(val);
}

export function AmendmentHistoryView({ usdm }: AmendmentHistoryViewProps) {

  if (!usdm) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">No USDM data available</p>
        </CardContent>
      </Card>
    );
  }

  // USDM-compliant: amendments are at studyVersion.amendments (per dataStructure.yml)
  const study = usdm.study as Record<string, unknown> | undefined;
  const versions = (study?.versions as unknown[]) ?? [];
  const version = versions[0] as Record<string, unknown> | undefined;
  
  // Prioritize USDM-compliant location (studyVersion.amendments)
  const amendments = (version?.amendments as Amendment[]) ?? 
    (usdm.studyAmendments as Amendment[]) ?? 
    (study?.studyAmendments as Amendment[]) ?? [];

  if (amendments.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <div className="text-muted-foreground">
            <FileEdit className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No amendments found in USDM data</p>
            <p className="text-sm mt-2">This may be the original protocol version</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileEdit className="h-5 w-5" />
            Amendment History
            <Badge variant="secondary">{amendments.length}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative">
            {/* Timeline line */}
            <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-border" />
            
            <div className="space-y-6">
              {amendments.map((amendment, i) => {
                const displayDate = amendment.effectiveDate || amendment.date;
                const displaySummary = amendment.summary || amendment.description;
                
                return (
                  <div key={amendment.id || i} className="relative pl-10">
                    {/* Timeline dot */}
                    <div className="absolute left-2.5 top-1 w-3 h-3 rounded-full bg-primary border-2 border-background" />
                    
                    <div className="p-4 border rounded-lg bg-card">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1">
                          <EditableField
                            path={amendment.id ? `/study/versions/0/amendments/@id:${amendment.id}/name` : `/study/versions/0/amendments/${i}/name`}
                            value={amendment.label || amendment.name || `Amendment ${amendment.number || i + 1}`}
                            label=""
                            className="font-medium"
                            placeholder="Amendment name"
                          />
                          {displayDate && (
                            <div className="flex items-center gap-1 text-sm text-muted-foreground mt-1">
                              <Calendar className="h-3 w-3" />
                              {displayDate}
                            </div>
                          )}
                          {amendment.previousVersion && amendment.newVersion && (
                            <div className="text-xs text-muted-foreground mt-1">
                              Version: {amendment.previousVersion} → {amendment.newVersion}
                            </div>
                          )}
                        </div>
                        <div className="flex gap-2">
                          {amendment.scope && (
                            <EditableCodedValue
                              path={amendment.id ? `/study/versions/0/amendments/@id:${amendment.id}/scope` : `/study/versions/0/amendments/${i}/scope`}
                              value={amendment.scope}
                              options={CDISC_TERMINOLOGIES.geographicScopeType ?? []}
                              showCode
                              placeholder="Scope"
                            />
                          )}
                          {amendment.number && (
                            <Badge>#{amendment.number}</Badge>
                          )}
                        </div>
                      </div>
                      
                      <EditableField
                        path={amendment.id ? `/study/versions/0/amendments/@id:${amendment.id}/summary` : `/study/versions/0/amendments/${i}/summary`}
                        value={displaySummary || ''}
                        label=""
                        type="textarea"
                        className="text-sm text-muted-foreground mb-3"
                        placeholder="No summary"
                      />
                      
                      {amendment.primaryReason && (
                        <div className="mb-2 flex items-center gap-2">
                          <span className="text-sm font-medium">Primary Reason:</span>
                          <EditableCodedValue
                            path={amendment.id ? `/study/versions/0/amendments/@id:${amendment.id}/primaryReason` : `/study/versions/0/amendments/${i}/primaryReason`}
                            value={amendment.primaryReason}
                            options={CDISC_TERMINOLOGIES.amendmentReason ?? []}
                            showCode
                            placeholder="Reason"
                          />
                        </div>
                      )}
                      
                      {amendment.secondaryReasons && amendment.secondaryReasons.length > 0 && (
                        <div className="mb-2">
                          <span className="text-sm font-medium">Secondary Reasons: </span>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {amendment.secondaryReasons.map((reason, ri) => (
                              <Badge key={ri} variant="outline" className="text-xs">
                                {toDisplayString(reason)}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {amendment.changes && amendment.changes.length > 0 && (
                        <div className="mt-3 pt-3 border-t">
                          <span className="text-sm font-medium">Changes:</span>
                          <ul className="mt-2 space-y-1">
                            {amendment.changes.map((change, ci) => (
                              <li key={ci} className="flex items-start gap-2 text-sm">
                                <ArrowRight className="h-3 w-3 mt-1 text-muted-foreground" />
                                {toDisplayString(change)}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default AmendmentHistoryView;
