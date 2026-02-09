'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { 
  FileText, 
  Hash,
  XCircle,
  AlertCircle,
  FileCheck,
  Download,
  FileOutput,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface DocumentStructureViewProps {
  usdm: Record<string, unknown> | null;
  protocolId?: string;
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

interface M11DocInfo {
  filename: string;
  size: number;
  updatedAt: string;
}

type TextQuality = 'populated' | 'placeholder' | 'empty';

function getTextQuality(content: DocumentContent): TextQuality {
  const text = content.text || '';
  if (!text.trim()) return 'empty';
  const title = content.sectionTitle || content.name || '';
  if (text === title || text.length < 20) return 'placeholder';
  return 'populated';
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function DocumentStructureView({ usdm, protocolId }: DocumentStructureViewProps) {
  const [m11Doc, setM11Doc] = useState<M11DocInfo | null>(null);
  const [docLoading, setDocLoading] = useState(false);

  // Fetch M11 document info
  useEffect(() => {
    if (!protocolId) return;
    setDocLoading(true);
    fetch(`/api/protocols/${protocolId}/documents`)
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (data?.documents) {
          const m11 = data.documents.find(
            (d: { filename: string }) => d.filename === 'm11_protocol.docx'
          );
          if (m11) setM11Doc({ filename: m11.filename, size: m11.size, updatedAt: m11.updatedAt });
        }
      })
      .catch(() => {})
      .finally(() => setDocLoading(false));
  }, [protocolId]);

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
  const narrativeSections = (version?.narrativeContents as DocumentContent[]) ?? [];
  const narrativeItems = (version?.narrativeContentItems as DocumentContent[]) ?? [];
  
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
  const allContent = [...documentContents, ...narrativeSections, ...narrativeItems];
  const presentSections = new Set(
    allContent
      .filter(c => c.sectionNumber)
      .map(c => c.sectionNumber?.split('.')[0])
  );

  // Readiness score
  const sectionsWithText = m11Sections.filter(s => {
    const mapped = m11MappedSections[s.number];
    if (mapped?.hasContent) return true;
    const matchingContent = allContent.find(
      c => c.sectionNumber?.split('.')[0] === s.number && getTextQuality(c) === 'populated'
    );
    return !!matchingContent;
  });
  const readinessScore = Math.round((sectionsWithText.length / m11Sections.length) * 100);
  const requiredWithText = m11Sections.filter(s => {
    if (!s.required) return false;
    const mapped = m11MappedSections[s.number];
    if (mapped?.hasContent) return true;
    return allContent.some(
      c => c.sectionNumber?.split('.')[0] === s.number && getTextQuality(c) === 'populated'
    );
  });

  return (
    <div className="space-y-6">
      {/* M11 Document Card */}
      <Card className={cn(
        'border-2',
        m11Doc ? 'border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20' : 'border-dashed'
      )}>
        <CardContent className="py-5">
          <div className="flex items-center gap-4">
            <div className={cn(
              'rounded-lg p-3',
              m11Doc ? 'bg-blue-100 dark:bg-blue-900' : 'bg-muted'
            )}>
              <FileOutput className={cn(
                'h-8 w-8',
                m11Doc ? 'text-blue-600 dark:text-blue-400' : 'text-muted-foreground'
              )} />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-lg font-semibold">
                ICH M11 Protocol Document
              </h3>
              {m11Doc ? (
                <p className="text-sm text-muted-foreground">
                  {m11Doc.filename} &bull; {formatFileSize(m11Doc.size)} &bull; Generated {new Date(m11Doc.updatedAt).toLocaleString()}
                </p>
              ) : docLoading ? (
                <p className="text-sm text-muted-foreground flex items-center gap-2">
                  <Loader2 className="h-3 w-3 animate-spin" /> Checking for document...
                </p>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No M11 document generated yet. Run the pipeline with --complete to generate.
                </p>
              )}
            </div>
            {m11Doc && protocolId && (
              <Button
                onClick={() => window.open(
                  `/api/protocols/${protocolId}/documents/${encodeURIComponent(m11Doc.filename)}?download=true`,
                  '_blank'
                )}
                className="shrink-0"
              >
                <Download className="h-4 w-4 mr-2" />
                Download DOCX
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Readiness Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className={cn(
              'text-2xl font-bold',
              readinessScore >= 75 ? 'text-green-600' :
              readinessScore >= 50 ? 'text-amber-500' : 'text-red-500'
            )}>{readinessScore}%</div>
            <div className="text-xs text-muted-foreground">M11 Readiness</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className="text-2xl font-bold">{sectionsWithText.length}<span className="text-base font-normal text-muted-foreground">/{m11Sections.length}</span></div>
            <div className="text-xs text-muted-foreground">Sections with Content</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className="text-2xl font-bold">{requiredWithText.length}<span className="text-base font-normal text-muted-foreground">/9</span></div>
            <div className="text-xs text-muted-foreground">Required Sections</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className="text-2xl font-bold text-muted-foreground">{allContent.length}</div>
            <div className="text-xs text-muted-foreground">Source Narrative Items</div>
          </CardContent>
        </Card>
      </div>

      {/* M11 Template Coverage */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Hash className="h-5 w-5" />
            M11 Section Coverage
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
    </div>
  );
}

export default DocumentStructureView;
