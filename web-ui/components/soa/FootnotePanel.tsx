'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FootnotePanelProps {
  footnotes: string[];
  selectedFootnoteRefs?: string[];
  className?: string;
}

export function FootnotePanel({ 
  footnotes, 
  selectedFootnoteRefs,
  className 
}: FootnotePanelProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  if (footnotes.length === 0) {
    return null;
  }

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
            {footnotes.map((footnote, index) => {
              const refId = `${index + 1}`;
              const isHighlighted = selectedFootnoteRefs?.includes(refId);
              
              return (
                <div
                  key={index}
                  className={cn(
                    'p-2 rounded transition-colors',
                    isHighlighted 
                      ? 'bg-blue-50 border border-blue-200' 
                      : 'bg-muted/30'
                  )}
                >
                  <span className="font-medium text-blue-700 mr-2">
                    [{refId}]
                  </span>
                  <span className="text-muted-foreground">{footnote}</span>
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
  footnotes: string[];
}) {
  if (refs.length === 0) return null;

  const content = refs
    .map((ref) => {
      const index = parseInt(ref, 10) - 1;
      return footnotes[index] || `Footnote ${ref}`;
    })
    .join('\n\n');

  return (
    <div className="max-w-sm p-2 text-xs bg-popover border rounded-md shadow-lg">
      {refs.map((ref, i) => {
        const index = parseInt(ref, 10) - 1;
        const text = footnotes[index] || `Footnote ${ref}`;
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
