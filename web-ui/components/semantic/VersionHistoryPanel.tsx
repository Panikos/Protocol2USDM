'use client';

import { useState, useEffect } from 'react';
import { X, Clock, RotateCcw, FileText, ChevronDown, ChevronRight, AlertCircle, CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface HistoryEntry {
  id: string;
  timestamp: string;
  type: 'published' | 'draft';
  patchCount: number;
  updatedBy?: string;
  validation?: {
    schema: { valid: boolean };
    usdm: { valid: boolean };
    core: { success: boolean };
  };
}

interface VersionHistoryPanelProps {
  protocolId: string;
  isOpen: boolean;
  onClose: () => void;
}

export function VersionHistoryPanel({ protocolId, isOpen, onClose }: VersionHistoryPanelProps) {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedEntry, setExpandedEntry] = useState<string | null>(null);
  const [selectedEntry, setSelectedEntry] = useState<HistoryEntry | null>(null);
  const [entryDetails, setEntryDetails] = useState<Record<string, unknown> | null>(null);
  const [isReverting, setIsReverting] = useState(false);
  const [showRevertConfirm, setShowRevertConfirm] = useState<string | null>(null);

  // Load history when panel opens
  useEffect(() => {
    if (isOpen) {
      loadHistory();
    }
  }, [isOpen, protocolId]);

  const loadHistory = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/protocols/${protocolId}/semantic/history`);
      if (response.ok) {
        const data = await response.json();
        setHistory(data.history || []);
      } else {
        setError('Failed to load history');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load history');
    } finally {
      setIsLoading(false);
    }
  };

  const loadEntryDetails = async (entry: HistoryEntry) => {
    try {
      const response = await fetch(`/api/protocols/${protocolId}/semantic/history/${entry.id}`);
      if (response.ok) {
        const data = await response.json();
        setEntryDetails(data);
        setSelectedEntry(entry);
      }
    } catch (err) {
      console.error('Failed to load entry details:', err);
    }
  };

  const handleRevert = async (entryId: string) => {
    setIsReverting(true);
    try {
      const response = await fetch(`/api/protocols/${protocolId}/semantic/revert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ targetVersion: entryId }),
      });
      
      if (response.ok) {
        // Reload history and close confirm
        await loadHistory();
        setShowRevertConfirm(null);
        // Trigger page reload to pick up reverted USDM
        window.location.reload();
      } else {
        const error = await response.json();
        setError(error.message || 'Failed to revert');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to revert');
    } finally {
      setIsReverting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-start justify-end z-50">
      <div className="bg-white h-full w-full max-w-lg shadow-xl flex flex-col animate-in slide-in-from-right">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-muted-foreground" />
            <h2 className="text-lg font-semibold">Version History</h2>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin h-6 w-6 border-2 border-primary border-t-transparent rounded-full" />
            </div>
          ) : error ? (
            <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-md text-red-700">
              <AlertCircle className="h-5 w-5" />
              <span>{error}</span>
            </div>
          ) : history.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <FileText className="h-12 w-12 mx-auto mb-2 opacity-50" />
              <p>No version history yet</p>
              <p className="text-sm">History will appear after you publish changes</p>
            </div>
          ) : (
            <div className="space-y-2">
              {history.map((entry, index) => (
                <div key={entry.id} className="border rounded-lg overflow-hidden">
                  {/* Entry header */}
                  <button
                    className={cn(
                      'w-full flex items-center justify-between p-3 text-left hover:bg-muted/50 transition-colors',
                      expandedEntry === entry.id && 'bg-muted/50'
                    )}
                    onClick={() => {
                      setExpandedEntry(expandedEntry === entry.id ? null : entry.id);
                      if (expandedEntry !== entry.id) {
                        loadEntryDetails(entry);
                      }
                    }}
                  >
                    <div className="flex items-center gap-3">
                      {expandedEntry === entry.id ? (
                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      )}
                      <div>
                        <div className="flex items-center gap-2">
                          <span className={cn(
                            'text-xs px-1.5 py-0.5 rounded font-medium',
                            entry.type === 'published' 
                              ? 'bg-green-100 text-green-700' 
                              : 'bg-amber-100 text-amber-700'
                          )}>
                            {entry.type === 'published' ? 'Published' : 'Draft'}
                          </span>
                          {index === 0 && (
                            <span className="text-xs text-muted-foreground">(current)</span>
                          )}
                        </div>
                        <div className="text-sm text-muted-foreground mt-1">
                          {new Date(entry.timestamp).toLocaleString()}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {entry.validation && (
                        entry.validation.schema.valid && entry.validation.usdm.valid ? (
                          <CheckCircle className="h-4 w-4 text-green-500" />
                        ) : (
                          <AlertCircle className="h-4 w-4 text-amber-500" />
                        )
                      )}
                      <span className="text-xs text-muted-foreground">
                        {entry.patchCount} changes
                      </span>
                    </div>
                  </button>

                  {/* Expanded details */}
                  {expandedEntry === entry.id && (
                    <div className="border-t p-3 bg-muted/30">
                      <div className="space-y-3">
                        {entry.updatedBy && (
                          <div className="text-sm">
                            <span className="text-muted-foreground">Updated by:</span>{' '}
                            <span className="font-medium">{entry.updatedBy}</span>
                          </div>
                        )}
                        
                        {/* Validation status */}
                        {entry.validation && (
                          <div className="space-y-1">
                            <div className="text-sm font-medium">Validation</div>
                            <div className="flex flex-wrap gap-2">
                              <ValidationBadge 
                                label="Schema" 
                                valid={entry.validation.schema.valid} 
                              />
                              <ValidationBadge 
                                label="USDM" 
                                valid={entry.validation.usdm.valid} 
                              />
                              <ValidationBadge 
                                label="CDISC" 
                                valid={entry.validation.core.success} 
                              />
                            </div>
                          </div>
                        )}

                        {/* Patch preview */}
                        {selectedEntry?.id === entry.id && entryDetails && (
                          <div className="space-y-1">
                            <div className="text-sm font-medium">Changes</div>
                            <div className="max-h-48 overflow-auto text-xs bg-slate-900 text-slate-100 rounded p-2 font-mono">
                              <pre>{JSON.stringify(entryDetails, null, 2)}</pre>
                            </div>
                          </div>
                        )}

                        {/* Revert action */}
                        {index > 0 && entry.type === 'published' && (
                          <div className="pt-2">
                            {showRevertConfirm === entry.id ? (
                              <div className="flex items-center gap-2 p-2 bg-amber-50 border border-amber-200 rounded-md">
                                <span className="text-sm text-amber-800">
                                  Revert to this version?
                                </span>
                                <Button 
                                  variant="destructive" 
                                  size="sm"
                                  onClick={() => handleRevert(entry.id)}
                                  disabled={isReverting}
                                >
                                  {isReverting ? 'Reverting...' : 'Confirm'}
                                </Button>
                                <Button 
                                  variant="ghost" 
                                  size="sm"
                                  onClick={() => setShowRevertConfirm(null)}
                                >
                                  Cancel
                                </Button>
                              </div>
                            ) : (
                              <Button 
                                variant="outline" 
                                size="sm"
                                onClick={() => setShowRevertConfirm(entry.id)}
                              >
                                <RotateCcw className="h-4 w-4 mr-2" />
                                Revert to this version
                              </Button>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t p-4">
          <Button variant="outline" className="w-full" onClick={loadHistory}>
            <RotateCcw className="h-4 w-4 mr-2" />
            Refresh History
          </Button>
        </div>
      </div>
    </div>
  );
}

function ValidationBadge({ label, valid }: { label: string; valid: boolean }) {
  return (
    <span className={cn(
      'text-xs px-2 py-0.5 rounded flex items-center gap-1',
      valid ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
    )}>
      {valid ? (
        <CheckCircle className="h-3 w-3" />
      ) : (
        <AlertCircle className="h-3 w-3" />
      )}
      {label}
    </span>
  );
}

export default VersionHistoryPanel;
