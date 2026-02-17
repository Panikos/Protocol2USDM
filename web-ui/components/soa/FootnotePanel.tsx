'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';
import { EditableField } from '@/components/semantic';

/** USDM-aligned SoA footnote object matching CommentAnnotation / x-soaFootnotes structure */
export interface SoAFootnote {
  id: string;
  text: string;
  marker?: string;
}

interface FootnotePanelProps {
  footnotes: SoAFootnote[];
  selectedFootnoteRefs?: string[];
  className?: string;
  /** Base path for editable footnotes, e.g. '/study/versions/0/studyDesigns/0/extensionAttributes' */
  editBasePath?: string;
}

// Build a map of marker -> footnote for quick lookup
function buildFootnoteMap(footnotes: SoAFootnote[]): Map<string, { footnote: SoAFootnote; index: number }> {
  const map = new Map<string, { footnote: SoAFootnote; index: number }>();
  footnotes.forEach((fn, index) => {
    const marker = fn.marker?.toLowerCase();
    if (marker) {
      map.set(marker, { footnote: fn, index });
    }
  });
  return map;
}

export function FootnotePanel({ 
  footnotes, 
  selectedFootnoteRefs,
  className,
  editBasePath,
}: FootnotePanelProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  if (footnotes.length === 0) {
    return null;
  }

  // Build letter -> footnote mapping
  const footnoteMap = buildFootnoteMap(footnotes);

  return (
    <div className={cn('border rounded-lg bg-white', className)}>
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium">
            Schedule of Activities Footnotes
          </span>
          <span className="text-sm text-muted-foreground">
            ({footnotes.length})
          </span>
        </div>
        {isExpanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="px-3 pb-3 border-t">
          <div className="mt-3 space-y-2 text-sm">
            {footnotes.map((fn, index) => {
              const marker = fn.marker?.toLowerCase();
              // Check if this footnote is selected (match by marker or numeric index)
              const isHighlighted = selectedFootnoteRefs?.some(ref => 
                ref.toLowerCase() === marker || 
                ref === `${index + 1}`
              );
              
              return (
                <div
                  key={fn.id || index}
                  className={cn(
                    'p-2 rounded transition-colors',
                    isHighlighted 
                      ? 'bg-blue-50 border border-blue-200' 
                      : 'bg-muted/30'
                  )}
                >
                  {marker ? (
                    <span className="font-medium text-blue-700 mr-2">
                      [{marker}]
                    </span>
                  ) : (
                    <span className="font-medium text-blue-700 mr-2">
                      [{index + 1}]
                    </span>
                  )}
                  {editBasePath ? (
                    <EditableField
                      path={`${editBasePath}/${index}`}
                      value={fn.text}
                      type="textarea"
                      className="text-muted-foreground inline"
                      placeholder="Footnote text"
                    />
                  ) : (
                    <span className="text-muted-foreground">{fn.text}</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// Compact inline footnote display
export function FootnoteTooltip({ 
  refs, 
  footnotes 
}: { 
  refs: string[]; 
  footnotes: SoAFootnote[];
}) {
  if (refs.length === 0) return null;

  // Build marker -> footnote mapping for lookup
  const footnoteMap = buildFootnoteMap(footnotes);

  return (
    <div className="max-w-sm p-2 text-xs bg-popover border rounded-md shadow-lg">
      {refs.map((ref, i) => {
        // Try to find by marker first, then by numeric index
        const refLower = ref.toLowerCase();
        const byMarker = footnoteMap.get(refLower);
        const byIndex = parseInt(ref, 10) - 1;
        const text = byMarker?.footnote.text || footnotes[byIndex]?.text || `Footnote [${ref}] - not found in extracted footnotes`;
        
        return (
          <div key={ref} className={cn(i > 0 && 'mt-2 pt-2 border-t')}>
            <span className="font-medium text-blue-700">[{ref}]</span>{' '}
            <span className="text-muted-foreground">{text}</span>
          </div>
        );
      })}
    </div>
  );
}

export default FootnotePanel;
