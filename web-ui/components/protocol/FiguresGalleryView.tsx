'use client';

import { useState, useMemo, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Image as ImageIcon,
  Table,
  BarChart3,
  Maximize2,
  X,
  Hash,
  Filter,
  ChevronLeft,
  ChevronRight,
  FileText,
  Search,
} from 'lucide-react';
import type { ProtocolFigure, FigureContentType } from '@/lib/types';

interface FiguresGalleryViewProps {
  usdm: Record<string, unknown> | null;
  protocolId: string;
}

const CONTENT_TYPE_CONFIG: Record<FigureContentType, { icon: React.ReactNode; color: string }> = {
  Figure: { icon: <ImageIcon className="h-4 w-4" />, color: 'text-purple-600' },
  Table: { icon: <Table className="h-4 w-4" />, color: 'text-emerald-600' },
  Diagram: { icon: <BarChart3 className="h-4 w-4" />, color: 'text-blue-600' },
  Chart: { icon: <BarChart3 className="h-4 w-4" />, color: 'text-amber-600' },
  Flowchart: { icon: <BarChart3 className="h-4 w-4" />, color: 'text-rose-600' },
  Image: { icon: <ImageIcon className="h-4 w-4" />, color: 'text-gray-600' },
};

// Strip TOC dotted-leader artifacts from titles (safety net for pre-existing data)
function cleanTitle(title: string | undefined | null): string | null {
  if (!title) return null;
  let t = title.replace(/\.{3,}\s*\d+\s*$/, '').replace(/\.{2,}\s*$/, '');
  t = t.replace(/\s+/g, ' ').trim();
  return t || null;
}

export function FiguresGalleryView({ usdm, protocolId }: FiguresGalleryViewProps) {
  const [filterType, setFilterType] = useState<FigureContentType | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [lightboxIdx, setLightboxIdx] = useState<number | null>(null);
  const [imageErrors, setImageErrors] = useState<Set<string>>(new Set());
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  // Extract figures from USDM
  const figures = useMemo(() => {
    if (!usdm) return [];
    // Try direct field first, then extension attribute
    let figs = usdm.protocolFigures as ProtocolFigure[] | undefined;
    if (!figs || figs.length === 0) {
      const study = usdm.study as Record<string, unknown> | undefined;
      const versions = (study?.versions as Record<string, unknown>[]) ?? [];
      const version = versions[0];
      const extAttrs = (version?.extensionAttributes as Array<{ url?: string; valueString?: string }>) ?? [];
      for (const ext of extAttrs) {
        if (ext.url?.includes('protocol-figures') && ext.valueString) {
          try {
            figs = JSON.parse(ext.valueString);
          } catch { /* skip */ }
          break;
        }
      }
    }
    return figs ?? [];
  }, [usdm]);

  const filteredFigures = useMemo(() => {
    let figs = figures;
    if (filterType !== 'all') {
      figs = figs.filter(f => f.contentType === filterType);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      figs = figs.filter(f =>
        f.label.toLowerCase().includes(q) ||
        (f.title?.toLowerCase().includes(q)) ||
        (f.sectionNumber?.toLowerCase().includes(q))
      );
    }
    return figs;
  }, [figures, filterType, searchQuery]);

  // Type counts
  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const fig of figures) {
      counts[fig.contentType] = (counts[fig.contentType] || 0) + 1;
    }
    return counts;
  }, [figures]);

  // Build image URL from imagePath
  const getImageUrl = (fig: ProtocolFigure): string | null => {
    if (!fig.imagePath) return null;
    // imagePath is like "figures/figure_1_p012.png" — extract just the filename
    const filename = fig.imagePath.split('/').pop();
    if (!filename) return null;
    return `/api/protocols/${protocolId}/images/${filename}`;
  };

  // Keyboard navigation for lightbox
  useEffect(() => {
    if (lightboxIdx === null) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setLightboxIdx(null);
      if (e.key === 'ArrowLeft' && lightboxIdx > 0) setLightboxIdx(lightboxIdx - 1);
      if (e.key === 'ArrowRight' && lightboxIdx < filteredFigures.length - 1) setLightboxIdx(lightboxIdx + 1);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [lightboxIdx, filteredFigures.length]);

  if (!usdm) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <ImageIcon className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No USDM data available</p>
        </CardContent>
      </Card>
    );
  }

  if (figures.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <ImageIcon className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No figures or tables extracted</p>
          <p className="text-sm text-muted-foreground mt-2">
            Run the pipeline with the document structure phase enabled to extract protocol figures and tables.
          </p>
        </CardContent>
      </Card>
    );
  }

  const withImages = figures.filter(f => f.imagePath).length;

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <ImageIcon className="h-5 w-5 text-purple-600" />
              <div>
                <div className="text-2xl font-bold">{figures.length}</div>
                <div className="text-xs text-muted-foreground">Total Items</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Maximize2 className="h-5 w-5 text-green-600" />
              <div>
                <div className="text-2xl font-bold">{withImages}</div>
                <div className="text-xs text-muted-foreground">With Images</div>
              </div>
            </div>
          </CardContent>
        </Card>
        {Object.entries(typeCounts).slice(0, 2).map(([type, count]) => {
          const cfg = CONTENT_TYPE_CONFIG[type as FigureContentType] || CONTENT_TYPE_CONFIG.Image;
          return (
            <Card key={type}>
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <span className={cfg.color}>{cfg.icon}</span>
                  <div>
                    <div className="text-2xl font-bold">{count}</div>
                    <div className="text-xs text-muted-foreground">{type}s</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Filter:</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <Button
                variant={filterType === 'all' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilterType('all')}
                className="h-7 text-xs"
              >
                All ({figures.length})
              </Button>
              {(Object.keys(typeCounts) as FigureContentType[]).sort().map(type => {
                const cfg = CONTENT_TYPE_CONFIG[type];
                return (
                  <Button
                    key={type}
                    variant={filterType === type ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setFilterType(type)}
                    className="h-7 text-xs gap-1"
                  >
                    {cfg.icon}
                    {type} ({typeCounts[type]})
                  </Button>
                );
              })}
            </div>
            <div className="flex-1" />
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search figures..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="h-8 pl-8 pr-3 text-sm border rounded-md bg-background w-48 focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Gallery grid */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ImageIcon className="h-5 w-5" />
            Protocol Figures &amp; Tables
            <Badge variant="secondary">{filteredFigures.length} items</Badge>
            <div className="ml-auto flex gap-1">
              <Button
                variant={viewMode === 'grid' ? 'default' : 'outline'}
                size="sm"
                className="h-7 text-xs"
                onClick={() => setViewMode('grid')}
              >
                Grid
              </Button>
              <Button
                variant={viewMode === 'list' ? 'default' : 'outline'}
                size="sm"
                className="h-7 text-xs"
                onClick={() => setViewMode('list')}
              >
                List
              </Button>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {filteredFigures.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No items match the current filter.
            </p>
          ) : (
            viewMode === 'list' ? (
              <div className="divide-y border rounded-lg overflow-hidden">
                {filteredFigures.map((fig, idx) => {
                  const imgUrl = getImageUrl(fig);
                  const cfg = CONTENT_TYPE_CONFIG[fig.contentType] || CONTENT_TYPE_CONFIG.Image;
                  const title = cleanTitle(fig.title);
                  return (
                    <div key={fig.id} className="flex items-center gap-4 px-4 py-3 hover:bg-muted/30 transition-colors">
                      <div className={`p-2 rounded ${cfg.color}`}>{cfg.icon}</div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="font-medium text-sm">{fig.label}</span>
                          <Badge variant="outline" className="text-xs">{fig.contentType}</Badge>
                          {fig.sectionNumber && (
                            <Badge variant="secondary" className="text-xs"><Hash className="h-3 w-3 mr-0.5" />{fig.sectionNumber}</Badge>
                          )}
                        </div>
                        {title && <p className="text-sm text-muted-foreground">{title}</p>}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {fig.pageNumber !== undefined && (
                          <span className="text-xs text-muted-foreground">p. {fig.pageNumber + 1}</span>
                        )}
                        {imgUrl && (
                          <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setLightboxIdx(idx)}>
                            <Maximize2 className="h-3.5 w-3.5 mr-1" /> View
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredFigures.map((fig, idx) => {
                const imgUrl = getImageUrl(fig);
                const cfg = CONTENT_TYPE_CONFIG[fig.contentType] || CONTENT_TYPE_CONFIG.Image;
                const hasError = imageErrors.has(fig.id);

                return (
                  <div
                    key={fig.id}
                    className="border rounded-lg overflow-hidden group hover:shadow-md transition-shadow bg-card"
                  >
                    {/* Image area */}
                    <div
                      className="relative aspect-[4/3] bg-muted/50 flex items-center justify-center cursor-pointer"
                      onClick={() => imgUrl && !hasError && setLightboxIdx(idx)}
                    >
                      {imgUrl && !hasError ? (
                        <>
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={imgUrl}
                            alt={fig.title || fig.label}
                            className="w-full h-full object-contain"
                            loading="lazy"
                            onError={() => setImageErrors(prev => new Set(prev).add(fig.id))}
                          />
                          <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
                            <Maximize2 className="h-6 w-6 text-white opacity-0 group-hover:opacity-80 transition-opacity drop-shadow" />
                          </div>
                        </>
                      ) : (
                        <div className="text-center p-4">
                          <span className={cfg.color}>{cfg.icon}</span>
                          <p className="text-xs text-muted-foreground mt-2">
                            {hasError ? 'Image unavailable' : 'No image rendered'}
                          </p>
                        </div>
                      )}
                    </div>

                    {/* Metadata */}
                    <div className="p-3 space-y-1.5">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs shrink-0">
                          <span className={cfg.color}>{cfg.icon}</span>
                          <span className="ml-1">{fig.contentType}</span>
                        </Badge>
                        {fig.sectionNumber && (
                          <Badge variant="secondary" className="text-xs shrink-0">
                            <Hash className="h-3 w-3 mr-0.5" />
                            {fig.sectionNumber}
                          </Badge>
                        )}
                        {fig.pageNumber !== undefined && (
                          <span className="text-xs text-muted-foreground ml-auto">
                            p.{fig.pageNumber + 1}
                          </span>
                        )}
                      </div>
                      <h3 className="font-medium text-sm leading-snug">{fig.label}</h3>
                      {cleanTitle(fig.title) && (
                        <p className="text-sm text-muted-foreground leading-snug line-clamp-2">{cleanTitle(fig.title)}</p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
            )
          )}
        </CardContent>
      </Card>

      {/* Lightbox overlay */}
      {lightboxIdx !== null && filteredFigures[lightboxIdx] && (() => {
        const fig = filteredFigures[lightboxIdx];
        const imgUrl = getImageUrl(fig);
        return (
          <div
            className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center"
            onClick={() => setLightboxIdx(null)}
            role="dialog"
            aria-modal="true"
            aria-label={`${fig.label}: ${fig.title || ''}`}
          >
            <div
              className="relative max-w-[90vw] max-h-[90vh] flex flex-col"
              onClick={e => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-center justify-between px-4 py-2 bg-black/60 rounded-t-lg text-white">
                <div>
                  <span className="font-medium">{fig.label}</span>
                  {fig.title && <span className="text-white/70 ml-2">— {fig.title}</span>}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-white/60">
                    {lightboxIdx + 1} / {filteredFigures.length}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-white hover:bg-white/20"
                    onClick={() => setLightboxIdx(null)}
                  >
                    <X className="h-5 w-5" />
                  </Button>
                </div>
              </div>

              {/* Image */}
              {imgUrl && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={imgUrl}
                  alt={fig.title || fig.label}
                  className="max-w-full max-h-[80vh] object-contain bg-white rounded-b-lg"
                />
              )}

              {/* Nav arrows */}
              {lightboxIdx > 0 && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute left-[-48px] top-1/2 -translate-y-1/2 h-10 w-10 text-white hover:bg-white/20 rounded-full"
                  onClick={() => setLightboxIdx(lightboxIdx - 1)}
                >
                  <ChevronLeft className="h-6 w-6" />
                </Button>
              )}
              {lightboxIdx < filteredFigures.length - 1 && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute right-[-48px] top-1/2 -translate-y-1/2 h-10 w-10 text-white hover:bg-white/20 rounded-full"
                  onClick={() => setLightboxIdx(lightboxIdx + 1)}
                >
                  <ChevronRight className="h-6 w-6" />
                </Button>
              )}
            </div>
          </div>
        );
      })()}
    </div>
  );
}

export default FiguresGalleryView;
