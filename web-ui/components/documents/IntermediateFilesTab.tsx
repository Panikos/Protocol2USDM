'use client';

import { useState, useEffect, useMemo } from 'react';
import {
  FileJson, FileText, Download, Loader2, FolderOpen,
  LayoutGrid, List, ArrowUpDown, Clock, SortAsc, HardDrive,
} from 'lucide-react';
import JsonView from 'react18-json-view';
import 'react18-json-view/src/style.css';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

interface IntermediateFile {
  filename: string;
  size: number;
  phase: string;
  updatedAt: string;
  order: number;
}

interface IntermediateFilesTabProps {
  protocolId: string;
}

type ViewMode = 'grouped' | 'flat';
type SortKey = 'order' | 'name' | 'size' | 'date';

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getPhaseColor(phase: string): string {
  const colors: Record<string, string> = {
    soa: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
    metadata: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
    eligibility: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
    objectives: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300',
    studydesign: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300',
    interventions: 'bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-300',
    narrative: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
    advanced: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300',
    procedures: 'bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-300',
    scheduling: 'bg-lime-100 text-lime-800 dark:bg-lime-900/30 dark:text-lime-300',
    execution: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300',
    sap: 'bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-300',
    sites: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300',
    docstructure: 'bg-sky-100 text-sky-800 dark:bg-sky-900/30 dark:text-sky-300',
    amendments: 'bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-300',
    output: 'bg-blue-200 text-blue-900 dark:bg-blue-800/40 dark:text-blue-200',
    validation: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
    conformance: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
    terminology: 'bg-fuchsia-100 text-fuchsia-800 dark:bg-fuchsia-900/30 dark:text-fuchsia-300',
    provenance: 'bg-stone-100 text-stone-800 dark:bg-stone-900/30 dark:text-stone-300',
    meta: 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300',
    other: 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300',
  };
  return colors[phase] || colors.other;
}

function getFileIcon(filename: string) {
  if (filename.endsWith('.docx')) return FileText;
  return FileJson;
}

function isBinaryFile(filename: string) {
  return filename.endsWith('.docx');
}

const SORT_OPTIONS: { key: SortKey; label: string; icon: React.ElementType }[] = [
  { key: 'order', label: 'Pipeline Order', icon: ArrowUpDown },
  { key: 'name', label: 'Alphabetical', icon: SortAsc },
  { key: 'size', label: 'Size', icon: HardDrive },
  { key: 'date', label: 'Modified', icon: Clock },
];

function sortFiles(files: IntermediateFile[], key: SortKey): IntermediateFile[] {
  const sorted = [...files];
  switch (key) {
    case 'order':
      return sorted.sort((a, b) => a.order - b.order || a.filename.localeCompare(b.filename));
    case 'name':
      return sorted.sort((a, b) => a.filename.localeCompare(b.filename));
    case 'size':
      return sorted.sort((a, b) => b.size - a.size);
    case 'date':
      return sorted.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
    default:
      return sorted;
  }
}

// Pipeline phase display order for grouped view
const PHASE_ORDER = [
  'metadata', 'eligibility', 'soa', 'objectives', 'studydesign',
  'interventions', 'narrative', 'advanced', 'procedures', 'scheduling',
  'execution', 'sap', 'sites', 'docstructure', 'amendments',
  'output', 'validation', 'conformance', 'terminology', 'provenance', 'meta', 'other',
];


export function IntermediateFilesTab({ protocolId }: IntermediateFilesTabProps) {
  const [files, setFiles] = useState<IntermediateFile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<IntermediateFile | null>(null);
  const [fileData, setFileData] = useState<unknown>(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('grouped');
  const [sortKey, setSortKey] = useState<SortKey>('order');

  useEffect(() => {
    async function loadFiles() {
      try {
        const response = await fetch(`/api/protocols/${protocolId}/intermediate`);
        if (!response.ok) throw new Error('Failed to load intermediate files');
        const data = await response.json();
        setFiles(data.files ?? []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    }
    loadFiles();
  }, [protocolId]);

  const handleSelectFile = async (file: IntermediateFile) => {
    // Binary files go straight to download
    if (isBinaryFile(file.filename)) {
      handleDownload(file);
      return;
    }
    setSelectedFile(file);
    setFileData(null);
    setFileLoading(true);
    
    try {
      const response = await fetch(
        `/api/protocols/${protocolId}/intermediate/${encodeURIComponent(file.filename)}`
      );
      if (response.ok) {
        const result = await response.json();
        setFileData(result.data);
      }
    } catch {
      // Preview failed
    } finally {
      setFileLoading(false);
    }
  };

  const handleDownload = (file: IntermediateFile) => {
    window.open(
      `/api/protocols/${protocolId}/intermediate/${encodeURIComponent(file.filename)}?download=true`,
      '_blank'
    );
  };

  // Sorted flat list
  const sortedFiles = useMemo(() => sortFiles(files, sortKey), [files, sortKey]);

  // Grouped view data
  const { groupedFiles, sortedPhases } = useMemo(() => {
    const grouped = files.reduce((acc, file) => {
      if (!acc[file.phase]) acc[file.phase] = [];
      acc[file.phase].push(file);
      return acc;
    }, {} as Record<string, IntermediateFile[]>);

    // Sort phases by pipeline order
    const phases = Object.keys(grouped).sort((a, b) => {
      const ai = PHASE_ORDER.indexOf(a);
      const bi = PHASE_ORDER.indexOf(b);
      return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    });

    // Sort files within each phase by order
    for (const phase of phases) {
      grouped[phase].sort((a, b) => a.order - b.order || a.filename.localeCompare(b.filename));
    }

    return { groupedFiles: grouped, sortedPhases: phases };
  }, [files]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <Card className="border-destructive">
        <CardContent className="py-6">
          <p className="text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (files.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <FolderOpen className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
          <h3 className="text-lg font-semibold mb-2">No Intermediate Files</h3>
          <p className="text-muted-foreground">
            No extraction artifacts found for this protocol.
          </p>
        </CardContent>
      </Card>
    );
  }

  const FileRow = ({ file }: { file: IntermediateFile }) => {
    const Icon = getFileIcon(file.filename);
    const binary = isBinaryFile(file.filename);
    return (
      <div
        onClick={() => handleSelectFile(file)}
        className={`p-2 rounded-lg cursor-pointer transition-colors hover:bg-muted/50 ${
          selectedFile?.filename === file.filename ? 'bg-muted ring-1 ring-primary' : ''
        }`}
      >
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-muted-foreground flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">
              {file.filename}
              {binary && (
                <span className="ml-1.5 text-[10px] font-normal text-muted-foreground">(download)</span>
              )}
            </p>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>{formatFileSize(file.size)}</span>
              {viewMode === 'flat' && (
                <span className={`px-1.5 py-0 rounded text-[10px] font-medium ${getPhaseColor(file.phase)}`}>
                  {file.phase}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="grid md:grid-cols-3 gap-6">
      {/* File List */}
      <div className="md:col-span-1 space-y-3">
        {/* Header with view toggle and sort */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
              Pipeline Artifacts ({files.length})
            </h3>
            <div className="flex items-center gap-1">
              <Button
                variant={viewMode === 'grouped' ? 'secondary' : 'ghost'}
                size="icon"
                className="h-7 w-7"
                onClick={() => setViewMode('grouped')}
                title="Grouped by phase"
              >
                <LayoutGrid className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant={viewMode === 'flat' ? 'secondary' : 'ghost'}
                size="icon"
                className="h-7 w-7"
                onClick={() => setViewMode('flat')}
                title="Flat list"
              >
                <List className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>

          {/* Sort controls — shown in flat mode */}
          {viewMode === 'flat' && (
            <div className="flex flex-wrap gap-1">
              {SORT_OPTIONS.map((opt) => {
                const SIcon = opt.icon;
                return (
                  <button
                    key={opt.key}
                    onClick={() => setSortKey(opt.key)}
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                      sortKey === opt.key
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground hover:bg-muted/80'
                    }`}
                  >
                    <SIcon className="h-3 w-3" />
                    {opt.label}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* File list body */}
        <div className="space-y-1 max-h-[600px] overflow-y-auto pr-1">
          {viewMode === 'grouped' ? (
            sortedPhases.map((phase) => {
              const phaseFiles = groupedFiles[phase];
              return (
                <div key={phase} className="space-y-1 mb-3">
                  <div className="flex items-center gap-2 mb-1 sticky top-0 bg-background/95 backdrop-blur-sm py-0.5 z-10">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${getPhaseColor(phase)}`}>
                      {phase}
                    </span>
                    <span className="text-xs text-muted-foreground">({phaseFiles.length})</span>
                  </div>
                  {phaseFiles.map((file) => (
                    <FileRow key={file.filename} file={file} />
                  ))}
                </div>
              );
            })
          ) : (
            sortedFiles.map((file, idx) => (
              <div key={file.filename} className="flex items-center gap-1">
                {sortKey === 'order' && (
                  <span className="text-[10px] text-muted-foreground w-5 text-right flex-shrink-0">
                    {idx + 1}.
                  </span>
                )}
                <div className="flex-1 min-w-0">
                  <FileRow file={file} />
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Preview Panel */}
      <div className="md:col-span-2">
        {selectedFile ? (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2 text-base">
                  {(() => { const Icon = getFileIcon(selectedFile.filename); return <Icon className="h-5 w-5" />; })()}
                  {selectedFile.filename}
                </CardTitle>
                <p className="text-sm text-muted-foreground mt-1">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${getPhaseColor(selectedFile.phase)}`}>
                    {selectedFile.phase}
                  </span>
                  <span className="ml-2">{formatFileSize(selectedFile.size)}</span>
                  <span className="ml-2 text-xs">
                    {new Date(selectedFile.updatedAt).toLocaleString()}
                  </span>
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={() => handleDownload(selectedFile)}>
                <Download className="h-4 w-4 mr-2" />
                Download
              </Button>
            </CardHeader>
            <CardContent>
              {fileLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : fileData ? (
                <div className="overflow-auto max-h-[500px] bg-slate-50 dark:bg-slate-900/50 rounded-lg p-4">
                  <JsonView 
                    src={fileData as object} 
                    collapsed={2}
                    enableClipboard
                    collapseStringsAfterLength={100}
                  />
                </div>
              ) : (
                <div className="text-center py-12 bg-muted/30 rounded-lg">
                  <FileJson className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                  <p className="text-muted-foreground">
                    Unable to load preview. Use download to access the file.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="py-12 text-center">
              <FileJson className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
              <p className="text-muted-foreground">
                Select a file to preview its contents
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
