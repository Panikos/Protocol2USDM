'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FootnotePanelProps {
  footnotes: string[];
  selectedFootnoteRefs?: string[];
  className?: string;
}

// Extract footnote letter prefix (e.g., "a" from "a. Some text" or "aa" from "aa. Some text")
function extractFootnoteLetter(footnote: string): string | null {
  // Match patterns like "a.", "b.", "aa.", "bb.", "u." at the start
  const match = footnote.match(/^([a-z]+)\./i);
  return match ? match[1].toLowerCase() : null;
}

// Build a map of letter -> footnote text for quick lookup
function buildFootnoteMap(footnotes: string[]): Map<string, { text: string; index: number }> {
  const map = new Map<string, { text: string; index: number }>();
  footnotes.forEach((footnote, index) => {
    const letter = extractFootnoteLetter(footnote);
    if (letter) {
      map.set(letter, { text: footnote, index });
    }
  });
  return map;
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
            {footnotes.map((footnote, index) => {
              // Extract letter prefix for matching with cell superscripts
              const letter = extractFootnoteLetter(footnote);
              // Check if this footnote is selected (match by letter or numeric index)
              const isHighlighted = selectedFootnoteRefs?.some(ref => 
                ref === letter || 
                ref === `${index + 1}` ||
                ref.toLowerCase() === letter
              );
              
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
                  {letter ? (
                    <span className="font-medium text-blue-700 mr-2">
                      [{letter}]
                    </span>
                  ) : (
                    <span className="font-medium text-blue-700 mr-2">
                      [{index + 1}]
                    </span>
                  )}
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

  // Build letter -> footnote mapping for lookup
  const footnoteMap = buildFootnoteMap(footnotes);

  return (
    <div className="max-w-sm p-2 text-xs bg-popover border rounded-md shadow-lg">
      {refs.map((ref, i) => {
        // Try to find by letter first, then by numeric index
        const refLower = ref.toLowerCase();
        const byLetter = footnoteMap.get(refLower);
        const byIndex = parseInt(ref, 10) - 1;
        const text = byLetter?.text || footnotes[byIndex] || `Footnote [${ref}] - not found in extracted footnotes`;
        
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
