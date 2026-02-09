'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  FileText, 
  ChevronRight,
  Hash,
  CheckCircle2,
  XCircle,
  AlertCircle,
  FileCheck,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface DocumentStructureViewProps {
  usdm: Record<string, unknown> | null;
}

interface DocumentContent {
  id: string;
  name?: string;
  sectionNumber?: string;
  sectionTitle?: string;
  text?: string;
  childIds?: string[];
  instanceType?: string;
}

interface M11SectionData {
  m11Number: string;
  m11Title: string;
  required: boolean;
  text: string;
  hasContent: boolean;
  sourceSections: Array<{
    protocolSection: string;
    protocolTitle: string;
    matchScore: number;
    hasText?: boolean;
  }>;
}

type TextQuality = 'populated' | 'placeholder' | 'empty';

function getTextQuality(content: DocumentContent): TextQuality {
  const text = content.text || '';
  if (!text.trim()) return 'empty';
  const title = content.sectionTitle || content.name || '';
  if (text === title || text.length < 20) return 'placeholder';
  return 'populated';
}

export function DocumentStructureView({ usdm }: DocumentStructureViewProps) {
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

  // Extract document contents from study version
  const study = usdm.study as Record<string, unknown> | undefined;
  const versions = (study?.versions as unknown[]) ?? [];
  const version = versions[0] as Record<string, unknown> | undefined;
  
  const documentContents = (version?.documentContents as DocumentContent[]) ?? [];
  const narrativeContents = (version?.narrativeContentItems as DocumentContent[]) ?? 
                            (version?.narrativeContents as DocumentContent[]) ?? [];
  
  // M11 mapping from pipeline (if available)
  const m11Mapping = (usdm as Record<string, unknown>).m11Mapping as Record<string, unknown> | undefined;
  const m11MappedSections = (m11Mapping?.sections ?? {}) as Record<string, M11SectionData>;

  // M11 Template sections
  const m11Sections = [
    { number: '1', title: 'Protocol Summary', required: true },
    { number: '2', title: 'Introduction', required: true },
    { number: '3', title: 'Study Objectives and Endpoints', required: true },
    { number: '4', title: 'Study Design', required: true },
    { number: '5', title: 'Study Population', required: true },
    { number: '6', title: 'Study Intervention', required: true },
    { number: '7', title: 'Discontinuation', required: true },
    { number: '8', title: 'Study Assessments and Procedures', required: true },
    { number: '9', title: 'Statistical Considerations', required: true },
    { number: '10', title: 'Supporting Documentation', required: false },
    { number: '11', title: 'References', required: false },
    { number: '12', title: 'Appendices', required: false },
  ];

  // Check which sections are present and their quality
  const allContent = [...documentContents, ...narrativeContents];
  const presentSections = new Set(
    allContent
      .filter(c => c.sectionNumber)
      .map(c => c.sectionNumber?.split('.')[0])
  );

  // Compute quality stats
  const qualityCounts = { populated: 0, placeholder: 0, empty: 0 };
  allContent.forEach(c => {
    qualityCounts[getTextQuality(c)]++;
  });

  if (allContent.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <FileText className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No document structure found</p>
          <p className="text-sm text-muted-foreground mt-2">
            Document contents will appear here after extraction
          </p>
        </CardContent>
      </Card>
    );
  }

  // Build content map for hierarchy
  const contentMap = new Map(allContent.map(c => [c.id, c]));
  
  // Find root-level content (not referenced as children)
  const allChildIds = new Set(
    allContent.flatMap(c => c.childIds ?? [])
  );
  const rootContent = allContent.filter(c => !allChildIds.has(c.id));

  // Readiness score: weighted by text quality and required coverage
  const sectionsWithText = m11Sections.filter(s => {
    const mapped = m11MappedSections[s.number];
    if (mapped?.hasContent) return true;
    // Fallback to presence check with text quality
    const matchingContent = allContent.find(
      c => c.sectionNumber?.split('.')[0] === s.number && getTextQuality(c) === 'populated'
    );
    return !!matchingContent;
  });
  const readinessScore = Math.round((sectionsWithText.length / m11Sections.length) * 100);

  return (
    <div className="space-y-6">
      {/* Readiness Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold">{readinessScore}%</div>
            <div className="text-xs text-muted-foreground">M11 Readiness</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold text-green-600">{qualityCounts.populated}</div>
            <div className="text-xs text-muted-foreground">Populated</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold text-amber-500">{qualityCounts.placeholder}</div>
            <div className="text-xs text-muted-foreground">Placeholder</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold text-red-500">{qualityCounts.empty}</div>
            <div className="text-xs text-muted-foreground">Empty</div>
          </CardContent>
        </Card>
      </div>

      {/* M11 Template Coverage */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Hash className="h-5 w-5" />
            M11 Template Coverage
            {m11Mapping && (
              <Badge variant="outline" className="text-xs ml-2">
                {(m11Mapping.coverage as string) ?? ''}
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-2">
            {m11Sections.map((section) => {
              const mapped = m11MappedSections[section.number];
              const hasMappedContent = mapped?.hasContent;
              const hasMappedSources = (mapped?.sourceSections?.length ?? 0) > 0;
              const isPresent = hasMappedSources || presentSections.has(section.number);
              const hasText = hasMappedContent || allContent.some(
                c => c.sectionNumber?.split('.')[0] === section.number && getTextQuality(c) === 'populated'
              );

              let status: 'full' | 'mapped' | 'missing';
              if (hasText) status = 'full';
              else if (isPresent) status = 'mapped';
              else status = 'missing';

              return (
                <div 
                  key={section.number}
                  className={cn(
                    'flex items-center gap-2 p-2 rounded',
                    status === 'full' ? 'bg-green-50 dark:bg-green-950/30' :
                    status === 'mapped' ? 'bg-amber-50 dark:bg-amber-950/30' :
                    section.required ? 'bg-red-50 dark:bg-red-950/30' : 'bg-muted'
                  )}
                >
                  {status === 'full' ? (
                    <FileCheck className="h-4 w-4 text-green-600 flex-shrink-0" />
                  ) : status === 'mapped' ? (
                    <AlertCircle className="h-4 w-4 text-amber-500 flex-shrink-0" />
                  ) : (
                    <XCircle className={cn(
                      'h-4 w-4 flex-shrink-0',
                      section.required ? 'text-red-600' : 'text-muted-foreground'
                    )} />
                  )}
                  <span className="text-sm flex-1">
                    <strong>{section.number}.</strong> {section.title}
                  </span>
                  {/* Source attribution */}
                  {mapped?.sourceSections && mapped.sourceSections.length > 0 && (
                    <span className="text-xs text-muted-foreground hidden md:inline">
                      ← §{mapped.sourceSections.map(s => s.protocolSection).join(', §')}
                    </span>
                  )}
                  {/* Status badges */}
                  {status === 'full' && (
                    <Badge className="ml-auto text-xs bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">Content</Badge>
                  )}
                  {status === 'mapped' && (
                    <Badge variant="outline" className="ml-auto text-xs text-amber-600">Structure only</Badge>
                  )}
                  {section.required && status === 'missing' && (
                    <Badge variant="destructive" className="ml-auto text-xs">Required</Badge>
                  )}
                </div>
              );
            })}
          </div>
          
          <div className="mt-4 pt-4 border-t flex items-center justify-between text-sm">
            <div className="flex gap-4 text-muted-foreground">
              <span className="flex items-center gap-1">
                <FileCheck className="h-3 w-3 text-green-600" /> With content
              </span>
              <span className="flex items-center gap-1">
                <AlertCircle className="h-3 w-3 text-amber-500" /> Structure only
              </span>
              <span className="flex items-center gap-1">
                <XCircle className="h-3 w-3 text-red-500" /> Missing
              </span>
            </div>
            <Badge variant={readinessScore >= 75 ? 'default' : 'secondary'}>
              {readinessScore}% ready
            </Badge>
          </div>
        </CardContent>
      </Card>

      {/* Document Contents Tree */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Document Contents
            <Badge variant="secondary">{allContent.length}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-1 max-h-[500px] overflow-auto">
            {rootContent.map((content) => (
              <ContentNode 
                key={content.id} 
                content={content} 
                contentMap={contentMap}
                depth={0}
              />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function ContentNode({
  content,
  contentMap,
  depth,
}: {
  content: DocumentContent;
  contentMap: Map<string, DocumentContent>;
  depth: number;
}) {
  const children = (content.childIds ?? [])
    .map(id => contentMap.get(id))
    .filter(Boolean) as DocumentContent[];

  const indent = depth * 20;
  const quality = getTextQuality(content);

  return (
    <div>
      <div 
        className="flex items-start gap-2 py-1 px-2 hover:bg-muted rounded text-sm"
        style={{ marginLeft: indent }}
      >
        {children.length > 0 && (
          <ChevronRight className="h-4 w-4 mt-0.5 text-muted-foreground" />
        )}
        {children.length === 0 && (
          <span className="w-4" />
        )}
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            {content.sectionNumber && (
              <Badge variant="outline" className="text-xs">
                {content.sectionNumber}
              </Badge>
            )}
            <span className="font-medium truncate">
              {content.sectionTitle || content.name || 'Untitled'}
            </span>
            <span className={cn(
              'inline-block w-2 h-2 rounded-full flex-shrink-0',
              quality === 'populated' ? 'bg-green-500' :
              quality === 'placeholder' ? 'bg-amber-400' : 'bg-red-400'
            )} title={quality} />
          </div>
          {content.text && quality === 'populated' && (
            <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
              {content.text.substring(0, 200)}{content.text.length > 200 ? '...' : ''}
            </p>
          )}
        </div>
      </div>
      
      {children.map((child) => (
        <ContentNode
          key={child.id}
          content={child}
          contentMap={contentMap}
          depth={depth + 1}
        />
      ))}
    </div>
  );
}

export default DocumentStructureView;
