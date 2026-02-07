'use client';

import { useState, useEffect } from 'react';
import { FileJson, Download, Loader2, FolderOpen } from 'lucide-react';
import JsonView from 'react18-json-view';
import 'react18-json-view/src/style.css';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

interface IntermediateFile {
  filename: string;
  size: number;
  phase: string;
  updatedAt: string;
}

interface IntermediateFilesTabProps {
  protocolId: string;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getPhaseColor(phase: string): string {
  const colors: Record<string, string> = {
    soa: 'bg-blue-100 text-blue-800',
    metadata: 'bg-green-100 text-green-800',
    eligibility: 'bg-purple-100 text-purple-800',
    objectives: 'bg-orange-100 text-orange-800',
    studydesign: 'bg-cyan-100 text-cyan-800',
    interventions: 'bg-pink-100 text-pink-800',
    narrative: 'bg-yellow-100 text-yellow-800',
    advanced: 'bg-indigo-100 text-indigo-800',
    procedures: 'bg-teal-100 text-teal-800',
    scheduling: 'bg-lime-100 text-lime-800',
    execution: 'bg-amber-100 text-amber-800',
    sap: 'bg-rose-100 text-rose-800',
    sites: 'bg-emerald-100 text-emerald-800',
    docstructure: 'bg-sky-100 text-sky-800',
    amendments: 'bg-violet-100 text-violet-800',
    validation: 'bg-red-100 text-red-800',
    conformance: 'bg-red-100 text-red-800',
    terminology: 'bg-fuchsia-100 text-fuchsia-800',
    meta: 'bg-gray-100 text-gray-800',
    other: 'bg-gray-100 text-gray-800',
  };
  return colors[phase] || colors.other;
}


export function IntermediateFilesTab({ protocolId }: IntermediateFilesTabProps) {
  const [files, setFiles] = useState<IntermediateFile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<IntermediateFile | null>(null);
  const [fileData, setFileData] = useState<unknown>(null);
  const [fileLoading, setFileLoading] = useState(false);

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

  // Group files by phase and sort alphabetically
  const groupedFiles = files.reduce((acc, file) => {
    if (!acc[file.phase]) acc[file.phase] = [];
    acc[file.phase].push(file);
    return acc;
  }, {} as Record<string, IntermediateFile[]>);
  
  // Sort phases alphabetically
  const sortedPhases = Object.keys(groupedFiles).sort((a, b) => a.localeCompare(b));
  
  // Sort files within each phase alphabetically
  for (const phase of sortedPhases) {
    groupedFiles[phase].sort((a, b) => a.filename.localeCompare(b.filename));
  }

  return (
    <div className="grid md:grid-cols-3 gap-6">
      {/* File List */}
      <div className="md:col-span-1 space-y-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
          Extraction Artifacts ({files.length})
        </h3>
        
        {sortedPhases.map((phase) => {
          const phaseFiles = groupedFiles[phase];
          return (
          <div key={phase} className="space-y-1">
            <div className="flex items-center gap-2 mb-1">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${getPhaseColor(phase)}`}>
                {phase}
              </span>
              <span className="text-xs text-muted-foreground">({phaseFiles.length})</span>
            </div>
            {phaseFiles.map((file) => (
              <div
                key={file.filename}
                onClick={() => handleSelectFile(file)}
                className={`p-2 rounded-lg cursor-pointer transition-colors hover:bg-muted/50 ${
                  selectedFile?.filename === file.filename ? 'bg-muted ring-1 ring-primary' : ''
                }`}
              >
                <div className="flex items-center gap-2">
                  <FileJson className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{file.filename}</p>
                    <p className="text-xs text-muted-foreground">{formatFileSize(file.size)}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        );
        })}
      </div>

      {/* Preview Panel */}
      <div className="md:col-span-2">
        {selectedFile ? (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2 text-base">
                  <FileJson className="h-5 w-5" />
                  {selectedFile.filename}
                </CardTitle>
                <p className="text-sm text-muted-foreground mt-1">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${getPhaseColor(selectedFile.phase)}`}>
                    {selectedFile.phase}
                  </span>
                  <span className="ml-2">{formatFileSize(selectedFile.size)}</span>
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
                <div className="overflow-auto max-h-[500px] bg-slate-50 rounded-lg p-4">
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
