'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  Image as ImageIcon, 
  ChevronLeft, 
  ChevronRight, 
  ZoomIn, 
  ZoomOut,
  Maximize2,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface SoAImagesViewerProps {
  images: SoAImage[];
}

interface SoAImage {
  url: string;
  page?: number;
  name?: string;
  type?: string;
}

export function SoAImagesViewer({ images }: SoAImagesViewerProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [isFullscreen, setIsFullscreen] = useState(false);

  if (!images || images.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <ImageIcon className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No SoA images available</p>
          <p className="text-sm text-muted-foreground mt-2">
            Images will appear here after extraction
          </p>
        </CardContent>
      </Card>
    );
  }

  const currentImage = images[currentIndex];

  const handlePrev = () => {
    setCurrentIndex((prev) => (prev > 0 ? prev - 1 : images.length - 1));
    setZoom(1);
  };

  const handleNext = () => {
    setCurrentIndex((prev) => (prev < images.length - 1 ? prev + 1 : 0));
    setZoom(1);
  };

  const handleZoomIn = () => setZoom((z) => Math.min(z + 0.25, 3));
  const handleZoomOut = () => setZoom((z) => Math.max(z - 0.25, 0.5));

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <ImageIcon className="h-5 w-5" />
              SoA Page Images
              <Badge variant="secondary">{images.length}</Badge>
            </CardTitle>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={handleZoomOut} disabled={zoom <= 0.5}>
                <ZoomOut className="h-4 w-4" />
              </Button>
              <span className="text-sm text-muted-foreground w-12 text-center">
                {(zoom * 100).toFixed(0)}%
              </span>
              <Button variant="outline" size="sm" onClick={handleZoomIn} disabled={zoom >= 3}>
                <ZoomIn className="h-4 w-4" />
              </Button>
              <Button variant="outline" size="sm" onClick={() => setIsFullscreen(true)}>
                <Maximize2 className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* Image Display */}
          <div className="relative bg-muted rounded-lg overflow-hidden">
            <div 
              className="overflow-auto max-h-[600px] flex items-center justify-center p-4"
              style={{ minHeight: '400px' }}
            >
              <img
                src={currentImage.url}
                alt={currentImage.name || `Page ${currentImage.page || currentIndex + 1}`}
                className="transition-transform"
                style={{ transform: `scale(${zoom})`, transformOrigin: 'center' }}
              />
            </div>
          </div>

          {/* Navigation */}
          <div className="flex items-center justify-between mt-4">
            <Button variant="outline" onClick={handlePrev} disabled={images.length <= 1}>
              <ChevronLeft className="h-4 w-4 mr-1" />
              Previous
            </Button>
            
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                Page {currentIndex + 1} of {images.length}
              </span>
              {currentImage.page && (
                <Badge variant="outline">Original Page {currentImage.page}</Badge>
              )}
            </div>

            <Button variant="outline" onClick={handleNext} disabled={images.length <= 1}>
              Next
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>

          {/* Thumbnail Strip */}
          {images.length > 1 && (
            <div className="flex gap-2 mt-4 overflow-x-auto pb-2">
              {images.map((img, i) => (
                <button
                  key={i}
                  onClick={() => { setCurrentIndex(i); setZoom(1); }}
                  className={cn(
                    'flex-shrink-0 w-16 h-20 rounded border-2 overflow-hidden transition-colors',
                    i === currentIndex ? 'border-primary' : 'border-transparent hover:border-muted-foreground'
                  )}
                >
                  <img
                    src={img.url}
                    alt={`Thumbnail ${i + 1}`}
                    className="w-full h-full object-cover"
                  />
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Fullscreen Modal */}
      {isFullscreen && (
        <div className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center">
          <Button
            variant="ghost"
            size="sm"
            className="absolute top-4 right-4 text-white hover:bg-white/20"
            onClick={() => setIsFullscreen(false)}
          >
            <X className="h-6 w-6" />
          </Button>
          
          <Button
            variant="ghost"
            size="lg"
            className="absolute left-4 text-white hover:bg-white/20"
            onClick={handlePrev}
          >
            <ChevronLeft className="h-8 w-8" />
          </Button>

          <img
            src={currentImage.url}
            alt={currentImage.name || `Page ${currentIndex + 1}`}
            className="max-h-[90vh] max-w-[90vw] object-contain"
          />

          <Button
            variant="ghost"
            size="lg"
            className="absolute right-4 text-white hover:bg-white/20"
            onClick={handleNext}
          >
            <ChevronRight className="h-8 w-8" />
          </Button>

          <div className="absolute bottom-4 text-white text-sm">
            Page {currentIndex + 1} of {images.length}
          </div>
        </div>
      )}
    </>
  );
}

export default SoAImagesViewer;
