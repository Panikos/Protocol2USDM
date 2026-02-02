'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';
import { SoAImagesViewer } from './SoAImagesViewer';

interface SoAImagesTabProps {
  protocolId: string;
}

interface ImageData {
  filename: string;
  url: string;
  page?: number;
  name?: string;
}

export function SoAImagesTab({ protocolId }: SoAImagesTabProps) {
  const [images, setImages] = useState<ImageData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchImages() {
      try {
        const res = await fetch(`/api/protocols/${protocolId}/images`);
        if (res.ok) {
          const data = await res.json();
          setImages(data.images || []);
        }
      } catch {
        // Ignore errors
      } finally {
        setLoading(false);
      }
    }
    fetchImages();
  }, [protocolId]);

  if (loading) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Loader2 className="h-8 w-8 mx-auto mb-4 animate-spin text-muted-foreground" />
          <p className="text-muted-foreground">Loading images...</p>
        </CardContent>
      </Card>
    );
  }

  return <SoAImagesViewer images={images} />;
}

export default SoAImagesTab;
