'use client';

import { useState, useEffect, useCallback } from 'react';
import { FileText, Download, File, Table2, Loader2, Maximize2, X as XIcon } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface DocumentInfo {
  filename: string;
  type: 'protocol' | 'sap' | 'sites' | 'other';
  mimeType: string;
  size: number;
  updatedAt: string;
  path: string;
}

interface CSVPreview {
  headers: string[];
  rows: string[][];
}

interface DocumentsTabProps {
  protocolId: string;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getDocumentIcon(type: DocumentInfo['type']) {
  switch (type) {
    case 'protocol':
    case 'sap':
      return <FileText className="h-5 w-5 text-red-500" />;
    case 'sites':
      return <Table2 className="h-5 w-5 text-green-500" />;
    default:
      return <File className="h-5 w-5 text-gray-500" />;
  }
}

function getDocumentLabel(type: DocumentInfo['type']): string {
  switch (type) {
    case 'protocol':
      return 'Protocol Document';
    case 'sap':
      return 'Statistical Analysis Plan';
    case 'sites':
      return 'Study Sites';
    default:
      return 'Document';
  }
}

// ---------------------------------------------------------------------------
// Reusable CSV table component
// ---------------------------------------------------------------------------
function CSVTable({ headers, rows, className }: {
  headers: string[];
  rows: string[][];
  className?: string;
}) {
  return (
    <div className={cn('overflow-auto border rounded-lg', className)}>
      <table className="w-full text-sm">
        <thead className="bg-muted sticky top-0">
          <tr>
            {headers.map((header, i) => (
              <th key={i} className="px-3 py-2 text-left font-medium whitespace-nowrap">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t hover:bg-muted/30">
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-2 whitespace-nowrap">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Fullscreen overlay
// ---------------------------------------------------------------------------
function FullscreenOverlay({ children, title, onClose }: {
  children: React.ReactNode;
  title: string;
  onClose: () => void;
}) {
  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  // Prevent body scroll
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  return (
    <div className="fixed inset-0 z-50 bg-background/95 backdrop-blur-sm flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b bg-background shrink-0">
        <h2 className="font-semibold truncate">{title}</h2>
        <Button variant="ghost" size="icon" onClick={onClose} className="shrink-0">
          <XIcon className="h-5 w-5" />
        </Button>
      </div>
      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {children}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export function DocumentsTab({ protocolId }: DocumentsTabProps) {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDoc, setSelectedDoc] = useState<DocumentInfo | null>(null);
  const [preview, setPreview] = useState<CSVPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    async function loadDocuments() {
      try {
        const response = await fetch(`/api/protocols/${protocolId}/documents`);
        if (!response.ok) throw new Error('Failed to load documents');
        const data = await response.json();
        setDocuments(data.documents ?? []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    }
    loadDocuments();
  }, [protocolId]);

  const handlePreview = async (doc: DocumentInfo) => {
    setSelectedDoc(doc);
    setPreview(null);
    
    if (doc.mimeType === 'text/csv') {
      setPreviewLoading(true);
      try {
        const response = await fetch(
          `/api/protocols/${protocolId}/documents/${encodeURIComponent(doc.filename)}?preview=true`
        );
        if (response.ok) {
          const data = await response.json();
          setPreview(data.preview);
        }
      } catch {
        // Preview failed, that's okay
      } finally {
        setPreviewLoading(false);
      }
    }
  };

  const handleDownload = (doc: DocumentInfo) => {
    window.open(
      `/api/protocols/${protocolId}/documents/${encodeURIComponent(doc.filename)}`,
      '_blank'
    );
  };

  const getDocUrl = useCallback((doc: DocumentInfo) =>
    `/api/protocols/${protocolId}/documents/${encodeURIComponent(doc.filename)}`,
    [protocolId]
  );

  const closeFullscreen = useCallback(() => setIsFullscreen(false), []);

  // Render the document content (shared between inline and fullscreen)
  const renderContent = (doc: DocumentInfo, fullscreen: boolean) => {
    if (previewLoading) {
      return (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      );
    }
    if (preview) {
      return <CSVTable headers={preview.headers} rows={preview.rows} className={fullscreen ? 'max-h-none' : 'max-h-96'} />;
    }
    if (doc.mimeType === 'application/pdf') {
      return (
        <div className="border rounded-lg overflow-hidden">
          <iframe
            src={getDocUrl(doc)}
            className={cn('w-full', fullscreen ? 'h-[calc(100vh-8rem)]' : 'h-[600px]')}
            title={doc.filename}
          />
        </div>
      );
    }
    return (
      <div className="text-center py-12 bg-muted/30 rounded-lg">
        <File className="h-16 w-16 mx-auto mb-4 text-muted-foreground" />
        <p className="text-muted-foreground">
          Preview not available. Use download to access this file.
        </p>
      </div>
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

  if (documents.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <FileText className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
          <h3 className="text-lg font-semibold mb-2">No Source Documents</h3>
          <p className="text-muted-foreground">
            Source documents (protocol PDF, SAP, sites) were not found for this extraction.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <div className="grid md:grid-cols-3 gap-6">
        {/* Document List */}
        <div className="md:col-span-1 space-y-3">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
            Source Documents
          </h3>
          {documents.map((doc) => (
            <Card
              key={doc.filename}
              className={`cursor-pointer transition-colors hover:bg-muted/50 ${
                selectedDoc?.filename === doc.filename ? 'ring-2 ring-primary' : ''
              }`}
              onClick={() => handlePreview(doc)}
            >
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  {getDocumentIcon(doc.type)}
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{doc.filename}</p>
                    <p className="text-xs text-muted-foreground">
                      {getDocumentLabel(doc.type)} • {formatFileSize(doc.size)}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Preview Panel */}
        <div className="md:col-span-2">
          {selectedDoc ? (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    {getDocumentIcon(selectedDoc.type)}
                    {selectedDoc.filename}
                  </CardTitle>
                  <p className="text-sm text-muted-foreground mt-1">
                    {getDocumentLabel(selectedDoc.type)} • {formatFileSize(selectedDoc.size)} • 
                    Updated {new Date(selectedDoc.updatedAt).toLocaleDateString()}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => setIsFullscreen(true)}>
                    <Maximize2 className="h-4 w-4 mr-2" />
                    Fullscreen
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => handleDownload(selectedDoc)}>
                    <Download className="h-4 w-4 mr-2" />
                    Download
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {renderContent(selectedDoc, false)}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="py-12 text-center">
                <FileText className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                <p className="text-muted-foreground">
                  Select a document to preview
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Fullscreen overlay */}
      {isFullscreen && selectedDoc && (
        <FullscreenOverlay title={selectedDoc.filename} onClose={closeFullscreen}>
          {renderContent(selectedDoc, true)}
        </FullscreenOverlay>
      )}
    </>
  );
}
