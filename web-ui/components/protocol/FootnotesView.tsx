'use client';

import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EditableField } from '@/components/semantic';
import { FileText, Table, BookOpen, List } from 'lucide-react';

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
  footnotes: { id: string; text: string; pageNumber?: number; originalIndex?: number; editable?: boolean; editPath?: string }[];
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
    type FootnoteItem = { id: string; text: string; pageNumber?: number; originalIndex?: number; editable?: boolean; editPath?: string };
    const soaFootnotes: FootnoteItem[] = [];
    const otherSectionMap = new Map<string, FootnoteItem[]>();
    
    for (const fn of annotationFootnotes) {
      if (!fn.text) continue;
      const section = fn.sourceSection || 'General';
      
      // Check if this is a SoA-related footnote
      const isSoA = section.toLowerCase().includes('schedule of activities') ||
                    section.toLowerCase().includes('soa') ||
                    section.toLowerCase().includes('table 1') ||
                    section.toLowerCase().includes('table 2');
      
      // Find original index in commentAnnotations array
      const originalIndex = annotationFootnotes.indexOf(fn);
      
      if (isSoA) {
        soaFootnotes.push({
          id: fn.id,
          text: fn.text,
          pageNumber: fn.pageNumber,
          originalIndex,
          editable: true,
        });
      } else {
        if (!otherSectionMap.has(section)) {
          otherSectionMap.set(section, []);
        }
        otherSectionMap.get(section)!.push({
          id: fn.id,
          text: fn.text,
          pageNumber: fn.pageNumber,
          originalIndex,
          editable: true,
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
      
      // First check for authoritative SoA footnotes (from header_structure vision extraction)
      for (let extIdx = 0; extIdx < extensions.length; extIdx++) {
        const ext = extensions[extIdx];
        if (ext.url?.includes('soaFootnotes') && ext.valueString) {
          try {
            const soaFns = JSON.parse(ext.valueString) as string[];
            if (soaFns.length > 0) {
              groups.unshift({
                source: 'Schedule of Activities',
                footnotes: soaFns.map((text, idx) => ({
                  id: `soa_fn_${idx + 1}`,
                  text,
                  editable: true,
                  editPath: `/study/versions/0/studyDesigns/0/extensionAttributes/${extIdx}/valueString`,
                })),
              });
            }
          } catch {
            // Skip malformed JSON
          }
        }
      }
      
      // NOTE: Removed x-executionModel-footnoteConditions - authoritative SoA footnotes come from x-soaFootnotes
    }
    
    // 3. Add abbreviations from StudyVersion (reuse version from above)
    const abbreviations = (version?.abbreviations as Array<{
      id?: string;
      abbreviatedText?: string;
      expandedText?: string;
    }>) ?? [];
    
    if (abbreviations.length > 0) {
      groups.push({
        source: 'Protocol Abbreviations',
        footnotes: abbreviations.map((ab, idx) => ({
          id: ab.id || `abbrev_${idx}`,
          text: `${ab.abbreviatedText}: ${ab.expandedText}`,
          editable: true,
          editPath: `/study/versions/0/abbreviations/${idx}/expandedText`,
        })),
      });
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
              ) : group.source === 'Protocol Abbreviations' ? (
                <List className="h-4 w-4" />
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
                    {fn.editable ? (
                      <EditableField
                        path={fn.editPath || `/commentAnnotations/${fn.originalIndex}/text`}
                        value={fn.text}
                        label=""
                        type="textarea"
                        className="text-foreground flex-1"
                        placeholder="Footnote text"
                      />
                    ) : (
                      <span className="text-foreground">{fn.text}</span>
                    )}
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
