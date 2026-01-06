'use client';

import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { FileText, Table, BookOpen } from 'lucide-react';

interface FootnotesViewProps {
  usdm: Record<string, unknown> | null;
}

interface CommentAnnotation {
  id: string;
  text?: string;
  annotationType?: string;
  sourceSection?: string;
  pageNumber?: number;
  instanceType?: string;
}

interface FootnoteCondition {
  id: string;
  footnoteId?: string;
  text?: string;
  conditionType?: string;
  appliesToActivityIds?: string[];
}

interface FootnoteGroup {
  source: string;
  footnotes: { id: string; text: string; pageNumber?: number }[];
}

export function FootnotesView({ usdm }: FootnotesViewProps) {
  // Extract all footnotes from USDM
  const footnoteGroups = useMemo(() => {
    const groups: FootnoteGroup[] = [];
    
    if (!usdm) return groups;
    
    // 1. Extract CommentAnnotation footnotes from root level
    const annotations = (usdm.commentAnnotations as CommentAnnotation[]) ?? [];
    const annotationFootnotes = annotations.filter(a => a.annotationType === 'Footnote');
    
    // Separate SoA footnotes from other footnotes
    const soaFootnotes: { id: string; text: string; pageNumber?: number }[] = [];
    const otherSectionMap = new Map<string, { id: string; text: string; pageNumber?: number }[]>();
    
    for (const fn of annotationFootnotes) {
      if (!fn.text) continue;
      const section = fn.sourceSection || 'General';
      
      // Check if this is a SoA-related footnote
      const isSoA = section.toLowerCase().includes('schedule of activities') ||
                    section.toLowerCase().includes('soa') ||
                    section.toLowerCase().includes('table 1') ||
                    section.toLowerCase().includes('table 2');
      
      if (isSoA) {
        soaFootnotes.push({
          id: fn.id,
          text: fn.text,
          pageNumber: fn.pageNumber,
        });
      } else {
        if (!otherSectionMap.has(section)) {
          otherSectionMap.set(section, []);
        }
        otherSectionMap.get(section)!.push({
          id: fn.id,
          text: fn.text,
          pageNumber: fn.pageNumber,
        });
      }
    }
    
    // Add SoA footnotes as first group if any (will be merged with execution model footnotes later)
    if (soaFootnotes.length > 0) {
      groups.push({ source: 'Schedule of Activities (from document)', footnotes: soaFootnotes });
    }
    
    // Add other section groups
    for (const [source, footnotes] of otherSectionMap) {
      groups.push({ source, footnotes });
    }
    
    // 2. Extract SOA footnotes from extension attributes
    const study = usdm.study as Record<string, unknown> | undefined;
    const versions = (study?.versions as unknown[]) ?? [];
    const version = versions[0] as Record<string, unknown> | undefined;
    const studyDesigns = (version?.studyDesigns as Record<string, unknown>[]) ?? [];
    const studyDesign = studyDesigns[0];
    
    if (studyDesign) {
      const extensions = (studyDesign.extensionAttributes as Array<{
        url?: string;
        valueString?: string;
      }>) ?? [];
      
      for (const ext of extensions) {
        if (ext.url?.includes('footnoteConditions') && ext.valueString) {
          try {
            const conditions = JSON.parse(ext.valueString) as FootnoteCondition[];
            const footnoteMap = new Map<string, string>();
            
            for (const cond of conditions) {
              if (cond.footnoteId && cond.text && !footnoteMap.has(cond.footnoteId)) {
                footnoteMap.set(cond.footnoteId, cond.text);
              }
            }
            
            // Sort by footnote ID
            const sortedEntries = Array.from(footnoteMap.entries()).sort((a, b) => {
              const aNum = parseFloat(a[0].replace(/[^\d.]/g, ''));
              const bNum = parseFloat(b[0].replace(/[^\d.]/g, ''));
              if (!isNaN(aNum) && !isNaN(bNum)) return aNum - bNum;
              return a[0].localeCompare(b[0]);
            });
            
            if (sortedEntries.length > 0) {
              groups.unshift({
                source: 'Schedule of Activities',
                footnotes: sortedEntries.map(([id, text]) => ({
                  id,
                  text: `${id} ${text}`,
                })),
              });
            }
          } catch {
            // Skip malformed JSON
          }
        }
      }
    }
    
    return groups;
  }, [usdm]);
  
  const totalFootnotes = footnoteGroups.reduce((sum, g) => sum + g.footnotes.length, 0);
  
  if (totalFootnotes === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <FileText className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No footnotes found in protocol</p>
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
            <FileText className="h-5 w-5" />
            Protocol Footnotes
            <Badge variant="secondary">{totalFootnotes} total</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Footnotes extracted from various sections of the protocol document, 
            including tables, figures, and narrative content.
          </p>
        </CardContent>
      </Card>
      
      {/* Footnote Groups */}
      {footnoteGroups.map((group, groupIndex) => (
        <Card key={groupIndex}>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              {group.source === 'Schedule of Activities' ? (
                <Table className="h-4 w-4" />
              ) : (
                <BookOpen className="h-4 w-4" />
              )}
              {group.source}
              <Badge variant="outline" className="ml-auto">
                {group.footnotes.length}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="space-y-2">
              {group.footnotes.map((fn, fnIndex) => (
                <div
                  key={fn.id || fnIndex}
                  className="p-3 bg-muted/30 rounded-lg text-sm"
                >
                  <div className="flex items-start gap-2">
                    <span className="text-muted-foreground font-mono text-xs shrink-0">
                      {fnIndex + 1}.
                    </span>
                    <span className="text-foreground">{fn.text}</span>
                  </div>
                  {fn.pageNumber && (
                    <div className="mt-1 text-xs text-muted-foreground">
                      Page {fn.pageNumber}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
