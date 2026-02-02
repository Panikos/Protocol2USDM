'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  FileText, 
  ChevronRight,
  Hash,
  CheckCircle2,
  XCircle,
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
  // USDM-compliant: narrativeContentItems at studyVersion level (per dataStructure.yml)
  const narrativeContents = (version?.narrativeContentItems as DocumentContent[]) ?? 
                            (version?.narrativeContents as DocumentContent[]) ?? [];
  
  // M11 Template sections mapping
  const m11Sections = [
    { number: '1', title: 'Protocol Summary', required: true },
    { number: '2', title: 'Introduction', required: true },
    { number: '3', title: 'Study Objectives and Endpoints', required: true },
    { number: '4', title: 'Study Design', required: true },
    { number: '5', title: 'Study Population', required: true },
    { number: '6', title: 'Study Intervention', required: true },
    { number: '7', title: 'Discontinuation of Study Intervention and Participant Discontinuation/Withdrawal', required: true },
    { number: '8', title: 'Study Assessments and Procedures', required: true },
    { number: '9', title: 'Statistical Considerations', required: true },
    { number: '10', title: 'Supporting Documentation', required: false },
    { number: '11', title: 'References', required: false },
    { number: '12', title: 'Appendices', required: false },
  ];

  // Check which sections are present
  const allContent = [...documentContents, ...narrativeContents];
  const presentSections = new Set(
    allContent
      .filter(c => c.sectionNumber)
      .map(c => c.sectionNumber?.split('.')[0])
  );

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

  return (
    <div className="space-y-6">
      {/* M11 Template Coverage */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Hash className="h-5 w-5" />
            M11 Template Coverage
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {m11Sections.map((section) => {
              const isPresent = presentSections.has(section.number);
              return (
                <div 
                  key={section.number}
                  className={cn(
                    'flex items-center gap-2 p-2 rounded',
                    isPresent ? 'bg-green-50' : section.required ? 'bg-red-50' : 'bg-muted'
                  )}
                >
                  {isPresent ? (
                    <CheckCircle2 className="h-4 w-4 text-green-600 flex-shrink-0" />
                  ) : (
                    <XCircle className={cn(
                      'h-4 w-4 flex-shrink-0',
                      section.required ? 'text-red-600' : 'text-muted-foreground'
                    )} />
                  )}
                  <span className="text-sm">
                    <strong>{section.number}.</strong> {section.title}
                  </span>
                  {section.required && !isPresent && (
                    <Badge variant="destructive" className="ml-auto text-xs">Required</Badge>
                  )}
                </div>
              );
            })}
          </div>
          
          <div className="mt-4 pt-4 border-t flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              Coverage: {presentSections.size} / {m11Sections.length} sections
            </span>
            <Badge variant={presentSections.size >= 9 ? 'default' : 'secondary'}>
              {((presentSections.size / m11Sections.length) * 100).toFixed(0)}%
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
          </div>
          {content.text && (
            <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
              {content.text.substring(0, 200)}...
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
