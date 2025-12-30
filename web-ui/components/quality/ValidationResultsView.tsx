'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, XCircle, AlertTriangle, Info } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ValidationResultsViewProps {
  validationData: ValidationResult | null;
}

interface ValidationResult {
  valid?: boolean;
  schemaValid?: boolean;
  errors?: ValidationIssue[];
  warnings?: ValidationIssue[];
  info?: ValidationIssue[];
  summary?: {
    totalIssues?: number;
    criticalCount?: number;
    warningCount?: number;
    infoCount?: number;
  };
}

interface ValidationIssue {
  type?: string;
  severity?: 'error' | 'warning' | 'info';
  message: string;
  path?: string;
  code?: string;
  suggestion?: string;
}

export function ValidationResultsView({ validationData }: ValidationResultsViewProps) {
  if (!validationData) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Info className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No validation data available</p>
          <p className="text-sm text-muted-foreground mt-2">
            Validation results will appear here after running schema validation
          </p>
        </CardContent>
      </Card>
    );
  }

  const isValid = validationData.valid ?? validationData.schemaValid ?? true;
  const errors = validationData.errors ?? [];
  const warnings = validationData.warnings ?? [];
  const infoItems = validationData.info ?? [];

  const allIssues = [
    ...errors.map(e => ({ ...e, severity: 'error' as const })),
    ...warnings.map(w => ({ ...w, severity: 'warning' as const })),
    ...infoItems.map(i => ({ ...i, severity: 'info' as const })),
  ];

  return (
    <div className="space-y-6">
      {/* Validation Status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {isValid ? (
              <CheckCircle2 className="h-5 w-5 text-green-600" />
            ) : (
              <XCircle className="h-5 w-5 text-red-600" />
            )}
            Validation Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <div className={cn(
              'text-2xl font-bold',
              isValid ? 'text-green-600' : 'text-red-600'
            )}>
              {isValid ? 'VALID' : 'INVALID'}
            </div>
            <div className="flex gap-2">
              {errors.length > 0 && (
                <Badge variant="destructive">{errors.length} Errors</Badge>
              )}
              {warnings.length > 0 && (
                <Badge variant="secondary" className="bg-amber-100 text-amber-800">
                  {warnings.length} Warnings
                </Badge>
              )}
              {infoItems.length > 0 && (
                <Badge variant="outline">{infoItems.length} Info</Badge>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Issues List */}
      {allIssues.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Validation Issues ({allIssues.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {allIssues.map((issue, i) => (
                <div 
                  key={i} 
                  className={cn(
                    'p-3 rounded-lg border',
                    issue.severity === 'error' && 'bg-red-50 border-red-200',
                    issue.severity === 'warning' && 'bg-amber-50 border-amber-200',
                    issue.severity === 'info' && 'bg-blue-50 border-blue-200'
                  )}
                >
                  <div className="flex items-start gap-2">
                    {issue.severity === 'error' && <XCircle className="h-4 w-4 text-red-600 mt-0.5" />}
                    {issue.severity === 'warning' && <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5" />}
                    {issue.severity === 'info' && <Info className="h-4 w-4 text-blue-600 mt-0.5" />}
                    
                    <div className="flex-1">
                      <p className="text-sm font-medium">{issue.message}</p>
                      
                      {issue.path && (
                        <p className="text-xs text-muted-foreground mt-1">
                          Path: <code className="bg-muted px-1 rounded">{issue.path}</code>
                        </p>
                      )}
                      
                      {issue.code && (
                        <Badge variant="outline" className="mt-1 text-xs">
                          {issue.code}
                        </Badge>
                      )}
                      
                      {issue.suggestion && (
                        <p className="text-xs text-muted-foreground mt-2 italic">
                          💡 {issue.suggestion}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* All Valid Message */}
      {allIssues.length === 0 && isValid && (
        <Card>
          <CardContent className="py-8 text-center">
            <CheckCircle2 className="h-12 w-12 mx-auto mb-4 text-green-600" />
            <p className="text-lg font-medium text-green-600">All validations passed!</p>
            <p className="text-sm text-muted-foreground mt-2">
              No issues found in the USDM structure
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default ValidationResultsView;
