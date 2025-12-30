'use client';

import { useState } from 'react';
import { 
  Code, 
  Copy, 
  Check, 
  Download, 
  Upload,
  ChevronDown,
  ChevronRight,
  AlertCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useOverlayStore } from '@/stores/overlayStore';
import { OverlayDocSchema } from '@/lib/overlay/schema';
import { cn } from '@/lib/utils';

interface OverlayDebugPanelProps {
  className?: string;
}

export function OverlayDebugPanel({ className }: OverlayDebugPanelProps) {
  const { draft, published, isDirty } = useOverlayStore();
  const [activeTab, setActiveTab] = useState<'draft' | 'published'>('draft');
  const [isExpanded, setIsExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);

  const currentOverlay = activeTab === 'draft' ? draft : published;

  // Copy to clipboard
  const handleCopy = async () => {
    if (!currentOverlay) return;
    await navigator.clipboard.writeText(JSON.stringify(currentOverlay, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Download JSON
  const handleDownload = () => {
    if (!currentOverlay) return;
    const blob = new Blob([JSON.stringify(currentOverlay, null, 2)], { 
      type: 'application/json' 
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `overlay_${activeTab}_${currentOverlay.protocolId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Import JSON
  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImportError(null);

    try {
      const text = await file.text();
      const json = JSON.parse(text);
      
      // Validate against schema
      const result = OverlayDocSchema.safeParse(json);
      if (!result.success) {
        setImportError(`Invalid overlay format: ${result.error.errors[0]?.message}`);
        return;
      }

      // Update draft with imported overlay
      const { loadOverlays } = useOverlayStore.getState();
      loadOverlays(
        result.data.protocolId,
        result.data.usdmRevision,
        published,
        result.data
      );
    } catch (err) {
      setImportError(err instanceof Error ? err.message : 'Failed to parse JSON');
    }

    // Reset file input
    e.target.value = '';
  };

  return (
    <Card className={cn('overflow-hidden', className)}>
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Code className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium">Overlay Debug</span>
          {isDirty && (
            <span className="px-1.5 py-0.5 text-xs bg-orange-100 text-orange-700 rounded">
              Dirty
            </span>
          )}
        </div>
        {isExpanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="border-t">
          {/* Tab selector */}
          <div className="flex items-center gap-2 p-3 border-b bg-muted/30">
            <Button
              variant={activeTab === 'draft' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setActiveTab('draft')}
            >
              Draft
              {isDirty && <span className="ml-1 w-2 h-2 rounded-full bg-orange-500" />}
            </Button>
            <Button
              variant={activeTab === 'published' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setActiveTab('published')}
            >
              Published
            </Button>
            
            <div className="flex-1" />
            
            {/* Actions */}
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCopy}
              disabled={!currentOverlay}
            >
              {copied ? (
                <Check className="h-4 w-4 text-green-600" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDownload}
              disabled={!currentOverlay}
            >
              <Download className="h-4 w-4" />
            </Button>
            <label className="cursor-pointer">
              <input
                type="file"
                accept=".json"
                onChange={handleImport}
                className="hidden"
              />
              <Button variant="ghost" size="sm" asChild>
                <span>
                  <Upload className="h-4 w-4" />
                </span>
              </Button>
            </label>
          </div>

          {/* Import error */}
          {importError && (
            <div className="flex items-center gap-2 p-3 bg-red-50 text-red-700 text-sm border-b">
              <AlertCircle className="h-4 w-4" />
              {importError}
            </div>
          )}

          {/* JSON viewer */}
          <div className="max-h-96 overflow-auto">
            {currentOverlay ? (
              <pre className="p-4 text-xs font-mono text-muted-foreground whitespace-pre-wrap">
                {JSON.stringify(currentOverlay, null, 2)}
              </pre>
            ) : (
              <div className="p-4 text-center text-muted-foreground">
                No {activeTab} overlay available
              </div>
            )}
          </div>

          {/* Stats */}
          {currentOverlay && (
            <div className="p-3 border-t bg-muted/30 text-xs text-muted-foreground">
              <div className="flex items-center gap-4">
                <span>
                  Nodes: {Object.keys(currentOverlay.payload.diagram.nodes).length}
                </span>
                <span>
                  Row order: {currentOverlay.payload.table.rowOrder?.length || 0}
                </span>
                <span>
                  Column order: {currentOverlay.payload.table.columnOrder?.length || 0}
                </span>
                <span className="flex-1" />
                <span>
                  Updated: {new Date(currentOverlay.updatedAt).toLocaleString()}
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

export default OverlayDebugPanel;
