'use client';

import { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Link2,
  ArrowRight,
  Filter,
  FileText,
  Table,
  Image,
  BookOpen,
  List,
  Hash,
  Search,
} from 'lucide-react';
import type { InlineCrossReference, ProtocolFigure, ReferenceType } from '@/lib/types';

interface CrossReferencesViewProps {
  usdm: Record<string, unknown> | null;
  onNavigateToSection?: (sectionNumber: string) => void;
}

const REF_TYPE_CONFIG: Record<ReferenceType, { icon: React.ReactNode; color: string; bgColor: string }> = {
  Section: { icon: <FileText className="h-3.5 w-3.5" />, color: 'text-blue-700 dark:text-blue-400', bgColor: 'bg-blue-50 dark:bg-blue-950/40' },
  Table: { icon: <Table className="h-3.5 w-3.5" />, color: 'text-emerald-700 dark:text-emerald-400', bgColor: 'bg-emerald-50 dark:bg-emerald-950/40' },
  Figure: { icon: <Image className="h-3.5 w-3.5" />, color: 'text-purple-700 dark:text-purple-400', bgColor: 'bg-purple-50 dark:bg-purple-950/40' },
  Appendix: { icon: <BookOpen className="h-3.5 w-3.5" />, color: 'text-amber-700 dark:text-amber-400', bgColor: 'bg-amber-50 dark:bg-amber-950/40' },
  Listing: { icon: <List className="h-3.5 w-3.5" />, color: 'text-rose-700 dark:text-rose-400', bgColor: 'bg-rose-50 dark:bg-rose-950/40' },
  Other: { icon: <Link2 className="h-3.5 w-3.5" />, color: 'text-gray-700 dark:text-gray-400', bgColor: 'bg-gray-50 dark:bg-gray-950/40' },
};

export function CrossReferencesView({ usdm, onNavigateToSection }: CrossReferencesViewProps) {
  const [filterType, setFilterType] = useState<ReferenceType | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const crossRefs = useMemo(() => {
    if (!usdm) return [];
    return (usdm.inlineCrossReferences as InlineCrossReference[] | undefined) ?? [];
  }, [usdm]);

  // Build lookup: targetLabel (e.g. "Figure 1") → ProtocolFigure title
  const figureTitleMap = useMemo(() => {
    if (!usdm) return new Map<string, ProtocolFigure>();
    const figs = (usdm.protocolFigures as ProtocolFigure[] | undefined) ?? [];
    const map = new Map<string, ProtocolFigure>();
    for (const fig of figs) {
      if (fig.label) map.set(fig.label, fig);
    }
    return map;
  }, [usdm]);

  const filteredRefs = useMemo(() => {
    let refs = crossRefs;
    if (filterType !== 'all') {
      refs = refs.filter(r => r.referenceType === filterType);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      refs = refs.filter(r =>
        r.targetLabel.toLowerCase().includes(q) ||
        r.sourceSection.toLowerCase().includes(q) ||
        (r.contextText?.toLowerCase().includes(q))
      );
    }
    return refs;
  }, [crossRefs, filterType, searchQuery]);

  // Count by type
  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const ref of crossRefs) {
      counts[ref.referenceType] = (counts[ref.referenceType] || 0) + 1;
    }
    return counts;
  }, [crossRefs]);

  // Group by source section
  const groupedRefs = useMemo(() => {
    const groups: Record<string, InlineCrossReference[]> = {};
    for (const ref of filteredRefs) {
      const key = ref.sourceSection;
      if (!groups[key]) groups[key] = [];
      groups[key].push(ref);
    }
    return Object.entries(groups).sort(([a], [b]) =>
      a.localeCompare(b, undefined, { numeric: true })
    );
  }, [filteredRefs]);

  if (!usdm) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Link2 className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No USDM data available</p>
        </CardContent>
      </Card>
    );
  }

  if (crossRefs.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Link2 className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No cross-references extracted</p>
          <p className="text-sm text-muted-foreground mt-2">
            Run the pipeline with the document structure phase enabled to extract inline references.
          </p>
        </CardContent>
      </Card>
    );
  }

  const resolvedCount = crossRefs.filter(r => r.targetId).length;

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Link2 className="h-5 w-5 text-blue-600" />
              <div>
                <div className="text-2xl font-bold">{crossRefs.length}</div>
                <div className="text-xs text-muted-foreground">Total References</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <ArrowRight className="h-5 w-5 text-green-600" />
              <div>
                <div className="text-2xl font-bold">{resolvedCount}</div>
                <div className="text-xs text-muted-foreground">Resolved Links</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Hash className="h-5 w-5 text-purple-600" />
              <div>
                <div className="text-2xl font-bold">{Object.keys(typeCounts).length}</div>
                <div className="text-xs text-muted-foreground">Reference Types</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-amber-600" />
              <div>
                <div className="text-2xl font-bold">{groupedRefs.length}</div>
                <div className="text-xs text-muted-foreground">Source Sections</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Filter:</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <Button
                variant={filterType === 'all' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilterType('all')}
                className="h-7 text-xs"
              >
                All ({crossRefs.length})
              </Button>
              {(Object.keys(typeCounts) as ReferenceType[]).sort().map(type => {
                const cfg = REF_TYPE_CONFIG[type];
                return (
                  <Button
                    key={type}
                    variant={filterType === type ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setFilterType(type)}
                    className="h-7 text-xs gap-1"
                  >
                    {cfg.icon}
                    {type} ({typeCounts[type]})
                  </Button>
                );
              })}
            </div>
            <div className="flex-1" />
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search references..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="h-8 pl-8 pr-3 text-sm border rounded-md bg-background w-48 focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Grouped references */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Link2 className="h-5 w-5" />
            Cross-References
            <Badge variant="secondary">{filteredRefs.length} refs</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {groupedRefs.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No references match the current filter.
            </p>
          ) : (
            <div className="space-y-4">
              {groupedRefs.map(([section, refs]) => (
                <div key={section} className="border rounded-lg overflow-hidden">
                  <div className="px-4 py-2 bg-muted/50 border-b">
                    <span className="text-sm font-medium">
                      <Badge variant="outline" className="mr-2 font-mono">
                        <Hash className="h-3 w-3 mr-0.5" />{section}
                      </Badge>
                      References from Section {section}
                    </span>
                  </div>
                  <div className="divide-y">
                    {refs.map(ref => {
                      const cfg = REF_TYPE_CONFIG[ref.referenceType] || REF_TYPE_CONFIG.Other;
                      return (
                        <div
                          key={ref.id}
                          className="px-4 py-3 flex items-start gap-3 hover:bg-muted/30 transition-colors"
                        >
                          <div className={`mt-0.5 p-1.5 rounded ${cfg.bgColor}`}>
                            <span className={cfg.color}>{cfg.icon}</span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-medium text-sm">{ref.targetLabel}</span>
                              <Badge variant="outline" className="text-xs">
                                {ref.referenceType}
                              </Badge>
                              {ref.targetId ? (
                                <Badge variant="default" className="text-xs bg-green-600 hover:bg-green-700">
                                  Linked
                                </Badge>
                              ) : (
                                <Badge variant="secondary" className="text-xs">
                                  Unresolved
                                </Badge>
                              )}
                            </div>
                            {/* Show linked figure/table title when available */}
                            {(() => {
                              const linked = figureTitleMap.get(ref.targetLabel);
                              return linked?.title ? (
                                <p className="text-sm text-foreground mb-1">
                                  <span className="font-medium">{linked.title}</span>
                                  {linked.pageNumber != null && (
                                    <span className="text-xs text-muted-foreground ml-2">
                                      (p. {linked.pageNumber + 1})
                                    </span>
                                  )}
                                </p>
                              ) : null;
                            })()}
                            {ref.contextText && ref.contextText.length > 15 && (
                              <p className="text-sm text-muted-foreground leading-relaxed">
                                &ldquo;{ref.contextText}&rdquo;
                              </p>
                            )}
                          </div>
                          {ref.targetSection && onNavigateToSection && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="shrink-0 h-7 text-xs gap-1"
                              onClick={() => onNavigateToSection(ref.targetSection!)}
                            >
                              Go to <ArrowRight className="h-3 w-3" />
                            </Button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default CrossReferencesView;
