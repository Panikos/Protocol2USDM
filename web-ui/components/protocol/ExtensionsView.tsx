'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  Puzzle, 
  ChevronDown, 
  ChevronRight,
  ExternalLink,
  Code,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface ExtensionsViewProps {
  usdm: Record<string, unknown> | null;
}

interface ExtensionAttribute {
  id?: string;
  name?: string;
  url?: string;
  value?: unknown;
  valueString?: string;
  valueCode?: string;
  valueInteger?: number;
  valueBoolean?: boolean;
  valueQuantity?: { value: number; unit: string };
  instanceType?: string;
}

interface EntityWithExtensions {
  id: string;
  name?: string;
  label?: string;
  instanceType?: string;
  extensionAttributes?: ExtensionAttribute[];
}

export function ExtensionsView({ usdm }: ExtensionsViewProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['studyDesign']));

  if (!usdm) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Puzzle className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No USDM data available</p>
        </CardContent>
      </Card>
    );
  }

  // Recursively find all entities with extensionAttributes
  const entitiesWithExtensions: { path: string; entity: EntityWithExtensions }[] = [];
  
  const findExtensions = (obj: unknown, path: string) => {
    if (!obj || typeof obj !== 'object') return;
    
    if (Array.isArray(obj)) {
      obj.forEach((item, i) => findExtensions(item, `${path}[${i}]`));
    } else {
      const entity = obj as Record<string, unknown>;
      if (entity.extensionAttributes && Array.isArray(entity.extensionAttributes) && entity.extensionAttributes.length > 0) {
        entitiesWithExtensions.push({
          path,
          entity: entity as EntityWithExtensions,
        });
      }
      Object.entries(entity).forEach(([key, value]) => {
        if (key !== 'extensionAttributes') {
          findExtensions(value, `${path}.${key}`);
        }
      });
    }
  };
  
  findExtensions(usdm, 'root');

  // Group by extension URL for summary
  const extensionsByUrl = new Map<string, { count: number; values: unknown[] }>();
  entitiesWithExtensions.forEach(({ entity }) => {
    entity.extensionAttributes?.forEach(ext => {
      const url = ext.url || 'unknown';
      const existing = extensionsByUrl.get(url) || { count: 0, values: [] };
      existing.count++;
      if (ext.value !== undefined) existing.values.push(ext.value);
      extensionsByUrl.set(url, existing);
    });
  });

  const toggleSection = (section: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  if (entitiesWithExtensions.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Puzzle className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No USDM extensions found</p>
          <p className="text-sm text-muted-foreground mt-2">
            Extensions allow custom data to be added to USDM entities
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Puzzle className="h-5 w-5" />
            USDM Extensions Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div className="p-3 bg-muted rounded-lg">
              <div className="text-2xl font-bold">{entitiesWithExtensions.length}</div>
              <div className="text-xs text-muted-foreground">Entities with Extensions</div>
            </div>
            <div className="p-3 bg-muted rounded-lg">
              <div className="text-2xl font-bold">{extensionsByUrl.size}</div>
              <div className="text-xs text-muted-foreground">Unique Extension Types</div>
            </div>
            <div className="p-3 bg-muted rounded-lg">
              <div className="text-2xl font-bold">
                {Array.from(extensionsByUrl.values()).reduce((sum, e) => sum + e.count, 0)}
              </div>
              <div className="text-xs text-muted-foreground">Total Extensions</div>
            </div>
          </div>

          {/* Extension Types */}
          <div className="space-y-2">
            <h4 className="font-medium text-sm">Extension Types:</h4>
            <div className="flex flex-wrap gap-2">
              {Array.from(extensionsByUrl.entries()).map(([url, data]) => {
                const shortName = url.split('/').pop() || url;
                return (
                  <Badge key={url} variant="secondary" className="text-xs">
                    {shortName} ({data.count})
                  </Badge>
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Detailed Extensions by Entity */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Code className="h-5 w-5" />
            Extensions by Entity
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 max-h-[600px] overflow-auto">
            {entitiesWithExtensions.map(({ path, entity }, i) => {
              const isExpanded = expandedSections.has(path);
              const entityName = entity.label || entity.name || entity.instanceType || 'Entity';
              
              return (
                <div key={i} className="border rounded-lg">
                  <button
                    onClick={() => toggleSection(path)}
                    className="w-full flex items-center gap-2 p-3 hover:bg-muted/50 text-left"
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                    <span className="font-medium">{entityName}</span>
                    <Badge variant="outline" className="text-xs">
                      {entity.instanceType}
                    </Badge>
                    <Badge variant="secondary" className="ml-auto text-xs">
                      {entity.extensionAttributes?.length} ext
                    </Badge>
                  </button>
                  
                  {isExpanded && (
                    <div className="px-3 pb-3 space-y-2">
                      {entity.extensionAttributes?.map((ext, j) => (
                        <div key={j} className="p-2 bg-muted rounded text-sm">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-xs truncate">
                                  {ext.url?.split('/').pop() || ext.name || 'Extension'}
                                </span>
                              </div>
                              {ext.url && (
                                <a 
                                  href={ext.url} 
                                  target="_blank" 
                                  rel="noopener noreferrer"
                                  className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                                >
                                  {ext.url}
                                  <ExternalLink className="h-3 w-3" />
                                </a>
                              )}
                            </div>
                          </div>
                          
                          {ext.value !== undefined && (
                            <div className="mt-2 p-2 bg-background rounded text-xs font-mono overflow-x-auto">
                              <pre className="whitespace-pre-wrap">
                                {typeof ext.value === 'object' 
                                  ? JSON.stringify(ext.value, null, 2)
                                  : String(ext.value)
                                }
                              </pre>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default ExtensionsView;
