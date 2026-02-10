'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EditableField } from '@/components/semantic';
import { versionPath } from '@/lib/semantic/schema';
import { 
  FileText, 
  ChevronDown, 
  ChevronRight,
  BookOpen,
  Hash,
} from 'lucide-react';

interface NarrativeViewProps {
  usdm: Record<string, unknown> | null;
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

export function NarrativeView({ usdm }: NarrativeViewProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());

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

  const expandAll = () => {
    setExpandedSections(new Set(narrativeContents.map(nc => nc.id)));
  };

  const collapseAll = () => {
    setExpandedSections(new Set());
  };

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
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

              return (
                <div key={section.id || i} className="border rounded-lg overflow-hidden">
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
                    {items.length > 0 && (
                      <Badge variant="secondary" className="shrink-0">
                        {items.length} item{items.length !== 1 ? 's' : ''}
                      </Badge>
                    )}
                  </div>
                  
                  {isExpanded && (
                    <div className="px-4 pb-4 pt-2 bg-muted/30 border-t">
                      <div className="prose prose-sm dark:prose-invert max-w-none mb-4">
                        <EditableField
                          path={section.id ? versionPath('narrativeContents', section.id, 'text') : `/study/versions/0/narrativeContents/${i}/text`}
                          value={section.text || ''}
                          label=""
                          type="textarea"
                          className="whitespace-pre-wrap"
                          placeholder="No content"
                        />
                      </div>
                      
                      {items.length > 0 && (
                        <div className="space-y-3">
                          {items.map((item, ii) => (
                            <div key={item.id || ii} className="p-3 bg-background rounded border">
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
                          ))}
                        </div>
                      )}
                      
                      {!section.text && items.length === 0 && (
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
