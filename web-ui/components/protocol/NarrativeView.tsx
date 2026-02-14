'use client';

import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EditableField } from '@/components/semantic';
import { versionPath } from '@/lib/semantic/schema';
import { useSemanticStore } from '@/stores/semanticStore';
import { useEditModeStore } from '@/stores/editModeStore';
import { 
  FileText, 
  ChevronDown, 
  ChevronRight,
  BookOpen,
  Hash,
  Plus,
  Trash2,
  Link2,
} from 'lucide-react';
import type { InlineCrossReference } from '@/lib/types';

interface NarrativeViewProps {
  usdm: Record<string, unknown> | null;
  onNavigateToTab?: (tab: string) => void;
  targetSectionNumber?: string | null;
  onTargetSectionHandled?: () => void;
}

interface NarrativeContent {
  id: string;
  name?: string;
  sectionTitle?: string;
  sectionNumber?: string;
  text?: string;
  contentItemIds?: string[];
  instanceType?: string;
}

interface NarrativeContentItem {
  id: string;
  name?: string;
  text?: string;
  sequence?: number;
  instanceType?: string;
}

// Regex matching the same patterns as the backend reference_scanner.py
const CROSS_REF_PATTERN = /(?:see\s+|refer\s+to\s+|per\s+|as\s+(?:described|defined|specified|outlined|detailed)\s+in\s+)?(?:Section|Table|Figure|Appendix|Listing)\s+[\d]+(?:[\d.]*[a-zA-Z]?)?/gi;

function highlightCrossRefs(
  text: string,
  refsForSection: InlineCrossReference[],
): React.ReactNode[] {
  if (!text || refsForSection.length === 0) return [text];

  const parts: React.ReactNode[] = [];
  let lastIdx = 0;
  const matches = [...text.matchAll(CROSS_REF_PATTERN)];

  for (const match of matches) {
    const start = match.index!;
    const end = start + match[0].length;
    if (start > lastIdx) {
      parts.push(text.slice(lastIdx, start));
    }
    parts.push(
      <span
        key={`xref-${start}`}
        className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-400 text-xs font-medium cursor-default hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors"
        title={`Cross-reference: ${match[0]}`}
      >
        <Link2 className="h-3 w-3 shrink-0" />
        {match[0]}
      </span>
    );
    lastIdx = end;
  }
  if (lastIdx < text.length) {
    parts.push(text.slice(lastIdx));
  }
  return parts.length > 0 ? parts : [text];
}

export function NarrativeView({ usdm, onNavigateToTab, targetSectionNumber, onTargetSectionHandled }: NarrativeViewProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [highlightedSectionId, setHighlightedSectionId] = useState<string | null>(null);
  const sectionDomRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const { addPatchOp } = useSemanticStore();
  const isEditMode = useEditModeStore((s) => s.isEditMode);

  // Build cross-reference lookup by source section
  const crossRefs = useMemo(() => {
    if (!usdm) return [] as InlineCrossReference[];
    return (usdm.inlineCrossReferences as InlineCrossReference[] | undefined) ?? [];
  }, [usdm]);

  const refsBySection = useMemo(() => {
    const map = new Map<string, InlineCrossReference[]>();
    for (const ref of crossRefs) {
      const key = ref.sourceSection;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(ref);
    }
    return map;
  }, [crossRefs]);

  if (!usdm) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <FileText className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No USDM data available</p>
        </CardContent>
      </Card>
    );
  }

  // Extract data from USDM structure
  const study = usdm.study as Record<string, unknown> | undefined;
  const versions = (study?.versions as unknown[]) ?? [];
  const version = versions[0] as Record<string, unknown> | undefined;

  // Get narrative contents and items
  const narrativeContents = (version?.narrativeContents as NarrativeContent[]) ?? [];
  const narrativeContentItems = (version?.narrativeContentItems as NarrativeContentItem[]) ?? [];

  // Build item lookup map
  const itemMap = new Map(narrativeContentItems.map(item => [item.id, item]));

  // Sort sections by section number
  const sortedSections = [...narrativeContents].sort((a, b) => {
    const numA = a.sectionNumber || '999';
    const numB = b.sectionNumber || '999';
    return numA.localeCompare(numB, undefined, { numeric: true });
  });

  const hasData = narrativeContents.length > 0 || narrativeContentItems.length > 0;

  if (!hasData) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <FileText className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No narrative content found</p>
          <p className="text-sm text-muted-foreground mt-2">
            Protocol narrative sections will appear here when available
          </p>
        </CardContent>
      </Card>
    );
  }

  const toggleSection = (id: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedSections(newExpanded);
  };

  const handleAddSection = () => {
    const newSection: NarrativeContent = {
      id: `nc_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      sectionTitle: '',
      sectionNumber: '',
      text: '',
      contentItemIds: [],
      instanceType: 'NarrativeContent',
    };
    addPatchOp({ op: 'add', path: '/study/versions/0/narrativeContents/-', value: newSection });
  };

  const handleRemoveSection = (sectionId: string) => {
    addPatchOp({ op: 'remove', path: versionPath('narrativeContents', sectionId) });
  };

  const handleAddContentItem = (sectionId: string) => {
    const newItem: NarrativeContentItem = {
      id: `nci_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      name: '',
      text: '',
      sequence: 0,
      instanceType: 'NarrativeContentItem',
    };
    // Add the item to narrativeContentItems
    addPatchOp({ op: 'add', path: '/study/versions/0/narrativeContentItems/-', value: newItem });
    // Link it to the section
    addPatchOp({ op: 'add', path: `${versionPath('narrativeContents', sectionId)}/contentItemIds/-`, value: newItem.id });
  };

  const handleRemoveContentItem = (itemId: string) => {
    addPatchOp({ op: 'remove', path: versionPath('narrativeContentItems', itemId) });
  };

  // Auto-expand and scroll to target section when navigated from cross-references
  useEffect(() => {
    if (!targetSectionNumber || sortedSections.length === 0) return;

    // Find the section that matches the target section number (exact or prefix match)
    const target = sortedSections.find(
      s => s.sectionNumber === targetSectionNumber
    ) || sortedSections.find(
      s => s.sectionNumber?.startsWith(targetSectionNumber + '.')
    ) || sortedSections.find(
      s => targetSectionNumber.startsWith(s.sectionNumber + '.')
    );

    if (target) {
      // Expand the section
      setExpandedSections(prev => {
        const next = new Set(prev);
        next.add(target.id);
        return next;
      });

      // Highlight it briefly
      setHighlightedSectionId(target.id);
      setTimeout(() => setHighlightedSectionId(null), 2500);

      // Scroll to it after a tick (so it's rendered expanded)
      requestAnimationFrame(() => {
        const el = sectionDomRefs.current.get(target.id);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    }

    onTargetSectionHandled?.();
  }, [targetSectionNumber]); // eslint-disable-line react-hooks/exhaustive-deps

  const expandAll = () => {
    setExpandedSections(new Set(narrativeContents.map(nc => nc.id)));
  };

  const collapseAll = () => {
    setExpandedSections(new Set());
  };

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-blue-600" />
              <div>
                <div className="text-2xl font-bold">{narrativeContents.length}</div>
                <div className="text-xs text-muted-foreground">Sections</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-purple-600" />
              <div>
                <div className="text-2xl font-bold">{narrativeContentItems.length}</div>
                <div className="text-xs text-muted-foreground">Content Items</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Link2 className="h-5 w-5 text-amber-600" />
              <div>
                <div className="text-2xl font-bold">{crossRefs.length}</div>
                <div className="text-xs text-muted-foreground">Cross-References</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 justify-between w-full">
              <button 
                onClick={expandAll}
                className="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400"
              >
                Expand All
              </button>
              <span className="text-muted-foreground">|</span>
              <button 
                onClick={collapseAll}
                className="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400"
              >
                Collapse All
              </button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Narrative Sections */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BookOpen className="h-5 w-5" />
            Protocol Narrative
            <Badge variant="secondary">{narrativeContents.length} sections</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {sortedSections.map((section, i) => {
              const isExpanded = expandedSections.has(section.id);
              const items = (section.contentItemIds ?? [])
                .map(id => itemMap.get(id))
                .filter(Boolean) as NarrativeContentItem[];
              
              // Sort items by sequence
              items.sort((a, b) => (a.sequence || 0) - (b.sequence || 0));

              const sectionRefs = refsBySection.get(section.sectionNumber || '') ?? [];

              return (
                <div
                  key={section.id || i}
                  ref={(el) => { if (el) sectionDomRefs.current.set(section.id, el); }}
                  className={`border rounded-lg overflow-hidden transition-all duration-500 ${
                    highlightedSectionId === section.id
                      ? 'ring-2 ring-blue-500 ring-offset-2 bg-blue-50/50 dark:bg-blue-950/30'
                      : ''
                  }`}
                >
                  <div
                    onClick={() => toggleSection(section.id)}
                    className="w-full p-3 flex items-center gap-3 hover:bg-muted/50 transition-colors text-left cursor-pointer"
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && toggleSection(section.id)}
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4 shrink-0" />
                    ) : (
                      <ChevronRight className="h-4 w-4 shrink-0" />
                    )}
                    {section.sectionNumber && (
                      <Badge variant="outline" className="shrink-0 font-mono">
                        <Hash className="h-3 w-3 mr-1" />
                        {section.sectionNumber}
                      </Badge>
                    )}
                    <span className="font-medium flex-1" onClick={e => e.stopPropagation()}>
                      <EditableField
                        path={section.id ? versionPath('narrativeContents', section.id, 'sectionTitle') : `/study/versions/0/narrativeContents/${i}/sectionTitle`}
                        value={section.sectionTitle || section.name || `Section ${i + 1}`}
                        label=""
                        placeholder="Section title"
                      />
                    </span>
                    {sectionRefs.length > 0 && (
                      <Badge variant="outline" className="shrink-0 text-blue-700 dark:text-blue-400 border-blue-300 dark:border-blue-800">
                        <Link2 className="h-3 w-3 mr-0.5" />
                        {sectionRefs.length}
                      </Badge>
                    )}
                    {items.length > 0 && (
                      <Badge variant="secondary" className="shrink-0">
                        {items.length} item{items.length !== 1 ? 's' : ''}
                      </Badge>
                    )}
                    {isEditMode && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 shrink-0 text-destructive hover:text-destructive"
                        onClick={(e) => { e.stopPropagation(); handleRemoveSection(section.id); }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                  
                  {isExpanded && (
                    <div className="px-4 pb-4 pt-2 bg-muted/30 border-t">
                      <div className="prose prose-sm dark:prose-invert max-w-none mb-4">
                        {isEditMode ? (
                          <EditableField
                            path={section.id ? versionPath('narrativeContents', section.id, 'text') : `/study/versions/0/narrativeContents/${i}/text`}
                            value={section.text || ''}
                            label=""
                            type="textarea"
                            className="whitespace-pre-wrap"
                            placeholder="No content"
                          />
                        ) : (
                          <p className="whitespace-pre-wrap text-sm leading-relaxed">
                            {sectionRefs.length > 0
                              ? highlightCrossRefs(section.text || '', sectionRefs)
                              : (section.text || <span className="text-muted-foreground italic">No content</span>)}
                          </p>
                        )}
                      </div>
                      
                      {items.length > 0 && (
                        <div className="space-y-3">
                          {items.map((item, ii) => (
                            <div key={item.id || ii} className="p-3 bg-background rounded border group/nci">
                              <div className="flex items-start gap-2">
                                <div className="flex-1">
                                  <EditableField
                                    path={versionPath('narrativeContentItems', item.id, 'name')}
                                    value={item.name || ''}
                                    label=""
                                    className="font-medium text-sm mb-1"
                                    placeholder="Item name"
                                  />
                                  <EditableField
                                    path={versionPath('narrativeContentItems', item.id, 'text')}
                                    value={item.text || ''}
                                    label=""
                                    type="textarea"
                                    className="text-sm text-muted-foreground whitespace-pre-wrap"
                                    placeholder="No content"
                                  />
                                </div>
                                {isEditMode && (
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-6 w-6 shrink-0 opacity-0 group-hover/nci:opacity-100 transition-opacity text-destructive hover:text-destructive"
                                    onClick={() => handleRemoveContentItem(item.id)}
                                  >
                                    <Trash2 className="h-3 w-3" />
                                  </Button>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                      
                      {isEditMode && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleAddContentItem(section.id)}
                          className="mt-3 w-full border-dashed text-xs"
                        >
                          <Plus className="h-3 w-3 mr-1" />
                          Add Content Item
                        </Button>
                      )}

                      {!section.text && items.length === 0 && !isEditMode && (
                        <p className="text-sm text-muted-foreground italic">
                          No content available for this section
                        </p>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {isEditMode && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleAddSection}
              className="mt-3 w-full border-dashed"
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Section
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Standalone Content Items (not linked to sections) */}
      {narrativeContentItems.filter(item => 
        !narrativeContents.some(nc => nc.contentItemIds?.includes(item.id))
      ).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Additional Content Items
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {narrativeContentItems
                .filter(item => !narrativeContents.some(nc => nc.contentItemIds?.includes(item.id)))
                .map((item, i) => (
                  <div key={item.id || i} className="p-3 bg-muted rounded-lg">
                    {item.name && (
                      <div className="font-medium text-sm mb-1">{item.name}</div>
                    )}
                    {item.text && (
                      <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                        {item.text.length > 500 ? item.text.substring(0, 500) + '...' : item.text}
                      </p>
                    )}
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default NarrativeView;
