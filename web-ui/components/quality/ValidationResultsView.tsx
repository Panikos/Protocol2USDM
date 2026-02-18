'use client';

import { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, XCircle, AlertTriangle, Info, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ValidationResultsViewProps {
  protocolId: string;
  usdm?: Record<string, unknown> | null;
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

interface ValidationIssue {
  severity?: string;
  message?: string;
  location?: string;  // JSONPath-like location e.g. "study -> versions -> 0 -> ..."
  path?: string;      // Alternative path field
  type?: string;      // Issue type e.g. "missing", "string_type", "model_type"
  rule?: string;
}

interface SchemaValidation {
  valid?: boolean;
  schemaVersion?: string;
  validator?: string;
  summary?: {
    errorsCount?: number;
    warningsCount?: number;
  };
  issues?: ValidationIssue[];
}

interface USDMValidation {
  valid?: boolean;
  error_count?: number;
  warning_count?: number;
  usdm_version_expected?: string;
  usdm_version_found?: string;
  validator_type?: string;
  issues?: ValidationIssue[];
}

// Helper to format location path for readability
function formatLocation(location: string): { path: string; field: string; context: string } {
  // Convert "study -> versions -> 0 -> studyDesigns -> 0 -> InterventionalStudyDesign -> activities -> 15 -> definedProcedures -> 0 -> procedureType"
  // Into structured parts for better display
  const parts = location.split(' -> ');
  const field = parts[parts.length - 1] || 'unknown';
  
  // Extract meaningful context
  let context = '';
  let entityType = '';
  let entityIndex = '';
  
  for (let i = 0; i < parts.length - 1; i++) {
    const part = parts[i];
    const nextPart = parts[i + 1];
    
    // Look for entity types followed by index
    if (['activities', 'encounters', 'epochs', 'arms', 'timings', 'narrativeContentItems', 'definedProcedures', 'eligibilityCriteria'].includes(part)) {
      entityType = part;
      if (nextPart && /^\d+$/.test(nextPart)) {
        entityIndex = nextPart;
        context = `${entityType}[${entityIndex}]`;
      }
    }
  }
  
  // Build shortened path
  const shortPath = parts.slice(-3).join(' → ');
  
  return { path: shortPath, field, context };
}

// Helper to get actionable suggestion based on issue type
function getSuggestion(issue: ValidationIssue): string {
  const type = issue.type || '';
  const field = issue.location?.split(' -> ').pop() || '';
  
  switch (type) {
    case 'missing':
      return `Add the required '${field}' field to the parent object`;
    case 'string_type':
      return `Expected a string value for '${field}', but received an object or different type. Check if this should be a Code.decode value instead of a Code object.`;
    case 'model_type':
      return `'${field}' expects a specific object structure (e.g., Code). Ensure all required properties are present.`;
    case 'string_too_short':
      return `'${field}' cannot be empty - provide a meaningful value`;
    default:
      return '';
  }
}

interface CoreConformance {
  success?: boolean;
  engine?: string;
  error?: string;
  error_summary?: string;
  error_details?: string;
  issues?: number;
  warnings?: number;
  issues_list?: Array<{
    rule_id?: string;
    severity?: string;
    message?: string;
    dataset?: string;
    variable?: string;
    value?: string;
  }>;
}

interface ValidationData {
  extraction?: {
    success?: boolean;
    issues?: ExtractionIssue[];
  };
  schema?: SchemaValidation;
  usdm?: USDMValidation;
  core?: CoreConformance;
}

// Build a flat id→name lookup from all USDM entities
function buildIdNameMap(usdm: Record<string, unknown> | null | undefined): Map<string, string> {
  const map = new Map<string, string>();
  if (!usdm) return map;

  function walk(obj: unknown) {
    if (!obj || typeof obj !== 'object') return;
    if (Array.isArray(obj)) {
      for (const item of obj) walk(item);
      return;
    }
    const rec = obj as Record<string, unknown>;
    const id = rec.id as string | undefined;
    const name = (rec.name ?? rec.label ?? rec.text ?? rec.title) as string | undefined;
    if (id && typeof id === 'string' && name && typeof name === 'string') {
      // Only store if name is not itself a UUID
      if (!/^[0-9a-f]{8}-/.test(name)) {
        map.set(id, name.length > 60 ? name.slice(0, 57) + '…' : name);
      }
    }
    for (const val of Object.values(rec)) {
      walk(val);
    }
  }

  walk(usdm);
  return map;
}

// Replace UUIDs in a location string with human-readable names
function humanizeLocation(location: string, nameMap: Map<string, string>): string {
  // Match UUIDs (8-4-4-4-12 hex)
  return location.replace(
    /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi,
    (uuid) => {
      const name = nameMap.get(uuid);
      return name ? `${name}` : uuid;
    }
  );
}

export function ValidationResultsView({ protocolId, usdm }: ValidationResultsViewProps) {
  const [data, setData] = useState<ValidationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Build ID→name map once from USDM data
  const nameMap = useMemo(() => buildIdNameMap(usdm), [usdm]);

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

      {/* All Clear for Extraction */}
      {issues.length === 0 && isSuccess && !data.schema && !data.usdm && (
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

      {/* Schema Validation */}
      {data.schema && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {data.schema.valid ? (
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              ) : (
                <XCircle className="h-5 w-5 text-red-600" />
              )}
              Schema Validation
              {data.schema.schemaVersion && (
                <Badge variant="outline">v{data.schema.schemaVersion}</Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4 mb-4">
              <div className={cn(
                'text-xl font-bold',
                data.schema.valid ? 'text-green-600' : 'text-red-600'
              )}>
                {data.schema.valid ? 'VALID' : 'INVALID'}
              </div>
              {data.schema.validator && (
                <Badge variant="secondary">{data.schema.validator}</Badge>
              )}
              {data.schema.summary && (
                <div className="flex gap-2">
                  {(data.schema.summary.errorsCount ?? 0) > 0 && (
                    <Badge variant="destructive">
                      {data.schema.summary.errorsCount} Errors
                    </Badge>
                  )}
                  {(data.schema.summary.warningsCount ?? 0) > 0 && (
                    <Badge variant="secondary" className="bg-amber-100 text-amber-800">
                      {data.schema.summary.warningsCount} Warnings
                    </Badge>
                  )}
                </div>
              )}
            </div>
            
            {data.schema.issues && data.schema.issues.length > 0 && (
              <div className="space-y-3 max-h-[400px] overflow-auto">
                {data.schema.issues.map((issue, i) => {
                  const location = issue.location || issue.path || '';
                  const { path, field, context } = formatLocation(location);
                  const suggestion = getSuggestion(issue);
                  
                  return (
                    <div key={i} className={cn(
                      'p-4 rounded-lg text-sm border',
                      issue.severity === 'error' ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'
                    )}>
                      <div className="flex items-start justify-between gap-2">
                        <div className="font-medium flex items-center gap-2">
                          {issue.severity === 'error' ? (
                            <XCircle className="h-4 w-4 text-red-600 shrink-0" />
                          ) : (
                            <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
                          )}
                          <span className="text-foreground">{field}</span>
                          <span className="text-muted-foreground font-normal">— {issue.message}</span>
                        </div>
                        {issue.type && (
                          <Badge variant="outline" className="text-xs shrink-0">
                            {issue.type}
                          </Badge>
                        )}
                      </div>
                      
                      {context && (
                        <div className="mt-2 flex items-center gap-2">
                          <span className="text-xs text-muted-foreground">In:</span>
                          <Badge variant="secondary" className="text-xs font-mono">
                            {context}
                          </Badge>
                        </div>
                      )}
                      
                      {location && (
                        <div className="mt-2 text-xs text-muted-foreground font-mono bg-muted/50 p-2 rounded overflow-x-auto">
                          {humanizeLocation(location, nameMap)}
                        </div>
                      )}
                      
                      {suggestion && (
                        <div className="mt-2 text-xs text-blue-700 bg-blue-50 p-2 rounded border border-blue-200">
                          <span className="font-medium">💡 Suggestion:</span> {suggestion}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            
            {data.schema.valid && (!data.schema.issues || data.schema.issues.length === 0) && (
              <p className="text-sm text-muted-foreground">
                USDM output conforms to the schema specification.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* USDM Validation */}
      {data.usdm && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {data.usdm.valid ? (
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              ) : (
                <XCircle className="h-5 w-5 text-red-600" />
              )}
              USDM Conformance
              {data.usdm.usdm_version_found && (
                <Badge variant="outline">v{data.usdm.usdm_version_found}</Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4 mb-4">
              <div className={cn(
                'text-xl font-bold',
                data.usdm.valid ? 'text-green-600' : 'text-red-600'
              )}>
                {data.usdm.valid ? 'CONFORMANT' : 'NON-CONFORMANT'}
              </div>
              {data.usdm.validator_type && (
                <Badge variant="secondary">{data.usdm.validator_type}</Badge>
              )}
              <div className="flex gap-2">
                {(data.usdm.error_count ?? 0) > 0 && (
                  <Badge variant="destructive">
                    {data.usdm.error_count} Errors
                  </Badge>
                )}
                {(data.usdm.warning_count ?? 0) > 0 && (
                  <Badge variant="secondary" className="bg-amber-100 text-amber-800">
                    {data.usdm.warning_count} Warnings
                  </Badge>
                )}
              </div>
            </div>
            
            {data.usdm.usdm_version_expected && data.usdm.usdm_version_found && 
             data.usdm.usdm_version_expected.split('.').slice(0, 2).join('.') !== 
             data.usdm.usdm_version_found.split('.').slice(0, 2).join('.') && (
              <div className="p-2 bg-amber-50 border border-amber-200 rounded text-sm mb-4">
                <span className="font-medium">Version mismatch:</span>{' '}
                Expected {data.usdm.usdm_version_expected}, found {data.usdm.usdm_version_found}
              </div>
            )}
            
            {data.usdm.issues && data.usdm.issues.length > 0 && (
              <div className="space-y-3 max-h-[400px] overflow-auto">
                {data.usdm.issues.map((issue, i) => {
                  const location = issue.location || issue.path || '';
                  const { field, context } = formatLocation(location);
                  const suggestion = getSuggestion(issue);
                  
                  return (
                    <div key={i} className={cn(
                      'p-4 rounded-lg text-sm border',
                      issue.severity === 'error' ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'
                    )}>
                      <div className="flex items-start justify-between gap-2">
                        <div className="font-medium flex items-center gap-2">
                          {issue.severity === 'error' ? (
                            <XCircle className="h-4 w-4 text-red-600 shrink-0" />
                          ) : (
                            <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
                          )}
                          <span className="text-foreground">{field}</span>
                          <span className="text-muted-foreground font-normal">— {issue.message}</span>
                        </div>
                        {issue.type && (
                          <Badge variant="outline" className="text-xs shrink-0">
                            {issue.type}
                          </Badge>
                        )}
                      </div>
                      
                      {context && (
                        <div className="mt-2 flex items-center gap-2">
                          <span className="text-xs text-muted-foreground">In:</span>
                          <Badge variant="secondary" className="text-xs font-mono">
                            {context}
                          </Badge>
                        </div>
                      )}
                      
                      {location && (
                        <div className="mt-2 text-xs text-muted-foreground font-mono bg-muted/50 p-2 rounded overflow-x-auto">
                          {humanizeLocation(location, nameMap)}
                        </div>
                      )}
                      
                      {suggestion && (
                        <div className="mt-2 text-xs text-blue-700 bg-blue-50 p-2 rounded border border-blue-200">
                          <span className="font-medium">💡 Suggestion:</span> {suggestion}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            
            {data.usdm.valid && (!data.usdm.issues || data.usdm.issues.length === 0) && (
              <p className="text-sm text-muted-foreground">
                Output conforms to USDM {data.usdm.usdm_version_found || 'specification'}.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* CDISC CORE Conformance */}
      {data.core && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {data.core.success ? (
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              ) : (
                <XCircle className="h-5 w-5 text-red-600" />
              )}
              CDISC CORE Conformance
              {data.core.engine && (
                <Badge variant="outline">{data.core.engine}</Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.core.success ? (
              <>
                <div className="flex items-center gap-4 mb-4">
                  <div className="text-xl font-bold text-green-600">PASSED</div>
                  <div className="flex gap-2">
                    {(data.core.issues ?? 0) > 0 && (
                      <Badge variant="destructive">
                        {data.core.issues} Errors
                      </Badge>
                    )}
                    {(data.core.warnings ?? 0) > 0 && (
                      <Badge variant="secondary" className="bg-amber-100 text-amber-800">
                        {data.core.warnings} Warnings
                      </Badge>
                    )}
                    {(data.core.issues ?? 0) === 0 && (data.core.warnings ?? 0) === 0 && (
                      <Badge variant="secondary" className="bg-green-100 text-green-800">
                        No Issues
                      </Badge>
                    )}
                  </div>
                </div>
                
                {data.core.issues_list && data.core.issues_list.length > 0 && (
                  <div className="space-y-3 max-h-[400px] overflow-auto">
                    {data.core.issues_list.map((issue, i) => (
                      <div key={i} className={cn(
                        'p-4 rounded-lg text-sm border',
                        issue.severity === 'Error' ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'
                      )}>
                        <div className="flex items-start justify-between gap-2">
                          <div className="font-medium flex items-center gap-2">
                            {issue.severity === 'Error' ? (
                              <XCircle className="h-4 w-4 text-red-600 shrink-0" />
                            ) : (
                              <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
                            )}
                            <span className="text-foreground">{issue.rule_id}</span>
                          </div>
                          <Badge variant="outline" className="text-xs shrink-0">
                            {issue.severity}
                          </Badge>
                        </div>
                        
                        <div className="mt-2 text-muted-foreground">
                          {issue.message}
                        </div>
                        
                        {(issue.dataset || issue.variable) && (
                          <div className="mt-2 flex items-center gap-2 flex-wrap">
                            {issue.dataset && (
                              <Badge variant="secondary" className="text-xs font-mono">
                                Dataset: {issue.dataset}
                              </Badge>
                            )}
                            {issue.variable && (
                              <Badge variant="secondary" className="text-xs font-mono">
                                Variable: {issue.variable}
                              </Badge>
                            )}
                            {issue.value && (
                              <Badge variant="outline" className="text-xs font-mono">
                                Value: {issue.value}
                              </Badge>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                
                {(!data.core.issues_list || data.core.issues_list.length === 0) && (
                  <p className="text-sm text-muted-foreground">
                    USDM output passed all CDISC CORE conformance checks.
                  </p>
                )}
              </>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <div className="text-xl font-bold text-red-600">FAILED</div>
                </div>
                
                {data.core.error && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                    <div className="font-medium text-red-800">{data.core.error}</div>
                    {data.core.error_summary && (
                      <div className="text-sm text-red-700 mt-1">{data.core.error_summary}</div>
                    )}
                  </div>
                )}
                
                {data.core.error_details && (
                  <details className="text-xs">
                    <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                      Show error details
                    </summary>
                    <pre className="mt-2 p-2 bg-muted rounded overflow-x-auto text-muted-foreground">
                      {data.core.error_details}
                    </pre>
                  </details>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default ValidationResultsView;
