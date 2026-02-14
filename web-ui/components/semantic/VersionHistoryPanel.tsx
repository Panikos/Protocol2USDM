'use client';

import { useState, useEffect } from 'react';
import { X, Clock, RotateCcw, FileText, ChevronDown, ChevronRight, AlertCircle, CheckCircle, Shield, ShieldAlert, Hash } from 'lucide-react';
import type { ChangeLogEntry } from '@/lib/semantic/schema';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { humanizePath } from '@/lib/semantic/humanizePath';

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
  const [activeTab, setActiveTab] = useState<'history' | 'changelog'>('history');
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedEntry, setExpandedEntry] = useState<string | null>(null);
  const [selectedEntry, setSelectedEntry] = useState<HistoryEntry | null>(null);
  const [entryDetails, setEntryDetails] = useState<Record<string, unknown> | null>(null);
  const [isReverting, setIsReverting] = useState(false);
  const [showRevertConfirm, setShowRevertConfirm] = useState<string | null>(null);
  const [changeLog, setChangeLog] = useState<ChangeLogEntry[]>([]);
  const [changeLogIntegrity, setChangeLogIntegrity] = useState<{ valid: boolean; message?: string } | null>(null);
  const [isLoadingLog, setIsLoadingLog] = useState(false);
  const [logError, setLogError] = useState<string | null>(null);

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

  // Load data when panel opens or tab changes
  useEffect(() => {
    if (isOpen && activeTab === 'history') {
      loadHistory();
    } else if (isOpen && activeTab === 'changelog') {
      loadChangeLog();
    }
  }, [isOpen, protocolId, activeTab]);

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

  const loadChangeLog = async () => {
    setIsLoadingLog(true);
    setLogError(null);
    try {
      const response = await fetch(`/api/protocols/${protocolId}/semantic/changelog`);
      if (response.ok) {
        const data = await response.json();
        setChangeLog(data.entries || []);
        setChangeLogIntegrity(data.integrity || null);
      } else {
        setLogError('Failed to load change log');
      }
    } catch (err) {
      setLogError(err instanceof Error ? err.message : 'Failed to load change log');
    } finally {
      setIsLoadingLog(false);
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

        {/* Tabs */}
        <div className="flex border-b">
          <button
            className={cn(
              'flex-1 py-2 text-sm font-medium border-b-2 transition-colors',
              activeTab === 'history'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            )}
            onClick={() => setActiveTab('history')}
          >
            <Clock className="h-4 w-4 inline mr-1.5" />
            Versions
          </button>
          <button
            className={cn(
              'flex-1 py-2 text-sm font-medium border-b-2 transition-colors',
              activeTab === 'changelog'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            )}
            onClick={() => setActiveTab('changelog')}
          >
            <Shield className="h-4 w-4 inline mr-1.5" />
            Audit Trail
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {activeTab === 'changelog' ? (
            <ChangeLogView
              entries={changeLog}
              integrity={changeLogIntegrity}
              isLoading={isLoadingLog}
              error={logError}
            />
          ) : isLoading ? (
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
          <Button variant="outline" className="w-full" onClick={activeTab === 'changelog' ? loadChangeLog : loadHistory}>
            <RotateCcw className="h-4 w-4 mr-2" />
            Refresh {activeTab === 'changelog' ? 'Audit Trail' : 'History'}
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

function ChangeLogView({
  entries,
  integrity,
  isLoading,
  error,
}: {
  entries: ChangeLogEntry[];
  integrity: { valid: boolean; message?: string } | null;
  isLoading: boolean;
  error: string | null;
}) {
  const [expandedVersion, setExpandedVersion] = useState<number | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin h-6 w-6 border-2 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-md text-red-700">
        <AlertCircle className="h-5 w-5" />
        <span>{error}</span>
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <Shield className="h-12 w-12 mx-auto mb-2 opacity-50" />
        <p>No audit trail yet</p>
        <p className="text-sm">Entries will appear after you publish changes</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Hash chain integrity banner */}
      {integrity && (
        <div className={cn(
          'flex items-center gap-2 p-3 rounded-md text-sm',
          integrity.valid
            ? 'bg-green-50 border border-green-200 text-green-700'
            : 'bg-red-50 border border-red-200 text-red-700'
        )}>
          {integrity.valid ? (
            <Shield className="h-5 w-5 flex-shrink-0" />
          ) : (
            <ShieldAlert className="h-5 w-5 flex-shrink-0" />
          )}
          <div>
            <span className="font-medium">
              {integrity.valid ? 'Hash chain verified' : 'Hash chain broken'}
            </span>
            {integrity.message && (
              <span className="block text-xs mt-0.5">{integrity.message}</span>
            )}
          </div>
        </div>
      )}

      {/* Entries (newest first) */}
      {[...entries].reverse().map((entry) => (
        <div key={entry.version} className="border rounded-lg overflow-hidden">
          <button
            className={cn(
              'w-full flex items-center justify-between p-3 text-left hover:bg-muted/50 transition-colors',
              expandedVersion === entry.version && 'bg-muted/50'
            )}
            onClick={() => setExpandedVersion(expandedVersion === entry.version ? null : entry.version)}
          >
            <div className="flex items-center gap-3">
              {expandedVersion === entry.version ? (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              )}
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs px-1.5 py-0.5 rounded font-medium bg-blue-100 text-blue-700">
                    v{entry.version}
                  </span>
                  {entry.validation?.forcedPublish && (
                    <span className="text-xs px-1.5 py-0.5 rounded font-medium bg-amber-100 text-amber-700">
                      Forced
                    </span>
                  )}
                  {entry.version === entries.length && (
                    <span className="text-xs text-muted-foreground">(current)</span>
                  )}
                </div>
                <div className="text-sm text-muted-foreground mt-1">
                  {new Date(entry.publishedAt).toLocaleString()}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {entry.validation && (
                entry.validation.schemaValid && entry.validation.usdmValid ? (
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

          {expandedVersion === entry.version && (
            <div className="border-t p-3 bg-muted/30 space-y-3">
              {/* Reason for change */}
              <div>
                <div className="text-xs font-medium text-muted-foreground mb-1">Reason for Change</div>
                <div className="text-sm bg-background border rounded-md p-2">{entry.reason}</div>
              </div>

              {/* Published by */}
              <div className="text-sm">
                <span className="text-muted-foreground">Published by:</span>{' '}
                <span className="font-medium">{entry.publishedBy}</span>
              </div>

              {/* Validation summary */}
              {entry.validation && (
                <div className="space-y-1">
                  <div className="text-xs font-medium text-muted-foreground">Validation</div>
                  <div className="flex flex-wrap gap-2">
                    <ValidationBadge label="Schema" valid={entry.validation.schemaValid} />
                    <ValidationBadge label="USDM" valid={entry.validation.usdmValid} />
                    {(entry.validation.errorCount > 0 || entry.validation.warningCount > 0) && (
                      <span className="text-xs text-muted-foreground">
                        {entry.validation.errorCount} errors, {entry.validation.warningCount} warnings
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Changed paths */}
              {entry.changedPaths.length > 0 && (
                <div className="space-y-1">
                  <div className="text-xs font-medium text-muted-foreground">Changes</div>
                  <div className="text-xs rounded p-2 max-h-40 overflow-auto space-y-1 bg-slate-50 dark:bg-slate-900 border">
                    {entry.changedPaths.map((p, i) => (
                      <div key={i} className="flex items-baseline gap-2">
                        <span className="text-foreground">{humanizePath(p)}</span>
                        <span className="text-muted-foreground font-mono text-[10px] truncate">{p}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Hash */}
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Hash className="h-3 w-3" />
                <span className="font-mono">{entry.hash.slice(0, 16)}...</span>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default VersionHistoryPanel;
