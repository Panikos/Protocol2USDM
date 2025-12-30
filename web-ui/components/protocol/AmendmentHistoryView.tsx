'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { FileEdit, Calendar, ArrowRight } from 'lucide-react';

interface AmendmentHistoryViewProps {
  usdm: Record<string, unknown> | null;
}

interface Amendment {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  number?: string | number;
  scope?: { decode?: string };
  date?: string;
  reason?: string;
  changes?: string[];
  primaryReason?: { decode?: string };
  secondaryReasons?: { decode?: string }[];
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

  // Extract amendments from study version
  const study = usdm.study as Record<string, unknown> | undefined;
  const versions = (study?.versions as unknown[]) ?? [];
  const version = versions[0] as Record<string, unknown> | undefined;
  
  const amendments = (version?.amendments as Amendment[]) ?? [];

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
              {amendments.map((amendment, i) => (
                <div key={amendment.id || i} className="relative pl-10">
                  {/* Timeline dot */}
                  <div className="absolute left-2.5 top-1 w-3 h-3 rounded-full bg-primary border-2 border-background" />
                  
                  <div className="p-4 border rounded-lg bg-card">
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <h4 className="font-medium">
                          {amendment.label || amendment.name || `Amendment ${amendment.number || i + 1}`}
                        </h4>
                        {amendment.date && (
                          <div className="flex items-center gap-1 text-sm text-muted-foreground mt-1">
                            <Calendar className="h-3 w-3" />
                            {amendment.date}
                          </div>
                        )}
                      </div>
                      <div className="flex gap-2">
                        {amendment.scope?.decode && (
                          <Badge variant="outline">{amendment.scope.decode}</Badge>
                        )}
                        {amendment.number && (
                          <Badge>#{amendment.number}</Badge>
                        )}
                      </div>
                    </div>
                    
                    {amendment.description && (
                      <p className="text-sm text-muted-foreground mb-3">
                        {amendment.description}
                      </p>
                    )}
                    
                    {amendment.primaryReason?.decode && (
                      <div className="mb-2">
                        <span className="text-sm font-medium">Primary Reason: </span>
                        <Badge variant="secondary">{amendment.primaryReason.decode}</Badge>
                      </div>
                    )}
                    
                    {amendment.secondaryReasons && amendment.secondaryReasons.length > 0 && (
                      <div className="mb-2">
                        <span className="text-sm font-medium">Secondary Reasons: </span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {amendment.secondaryReasons.map((reason, ri) => (
                            <Badge key={ri} variant="outline" className="text-xs">
                              {reason.decode}
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
                              {change}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default AmendmentHistoryView;
