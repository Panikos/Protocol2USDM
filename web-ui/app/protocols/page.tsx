'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { FileText, Calendar, Tag, ArrowRight, Loader2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

interface ProtocolSummary {
  id: string;
  name: string;
  usdmVersion: string;
  generatedAt: string;
  activityCount: number;
  encounterCount: number;
}

export default function ProtocolsPage() {
  const [protocols, setProtocols] = useState<ProtocolSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadProtocols() {
      try {
        const response = await fetch('/api/protocols');
        if (!response.ok) throw new Error('Failed to load protocols');
        const data = await response.json();
        setProtocols(data.protocols ?? []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    }
    loadProtocols();
  }, []);

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="border-b bg-white sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-primary flex items-center justify-center">
                <FileText className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold">Protocol2USDM</h1>
                <p className="text-xs text-muted-foreground">Protocol Browser</p>
              </div>
            </Link>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h2 className="text-2xl font-bold mb-2">Available Protocols</h2>
          <p className="text-muted-foreground">
            Select a protocol to view its Schedule of Activities and timeline.
          </p>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        )}

        {error && (
          <Card className="border-destructive">
            <CardContent className="py-6">
              <p className="text-destructive">{error}</p>
              <Button
                variant="outline"
                className="mt-4"
                onClick={() => window.location.reload()}
              >
                Retry
              </Button>
            </CardContent>
          </Card>
        )}

        {!isLoading && !error && protocols.length === 0 && (
          <Card>
            <CardContent className="py-12 text-center">
              <FileText className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
              <h3 className="text-lg font-semibold mb-2">No Protocols Found</h3>
              <p className="text-muted-foreground mb-4">
                Run the extraction pipeline to generate protocol USDM files.
              </p>
              <code className="block bg-muted p-4 rounded-lg text-sm text-left max-w-xl mx-auto">
                python main_v2.py &quot;input/protocol.pdf&quot; --complete --output-dir output/my_protocol
              </code>
            </CardContent>
          </Card>
        )}

        {!isLoading && !error && protocols.length > 0 && (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {protocols.map((protocol) => (
              <ProtocolCard key={protocol.id} protocol={protocol} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

function ProtocolCard({ protocol }: { protocol: ProtocolSummary }) {
  return (
    <Card className="hover:shadow-lg transition-shadow">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-primary" />
          <span className="truncate">{protocol.name}</span>
        </CardTitle>
        <CardDescription className="flex items-center gap-4 text-xs">
          <span className="flex items-center gap-1">
            <Tag className="h-3 w-3" />
            USDM {protocol.usdmVersion}
          </span>
          <span className="flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            {new Date(protocol.generatedAt).toLocaleDateString()}
          </span>
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-4 text-sm text-muted-foreground mb-4">
          <span>{protocol.activityCount} activities</span>
          <span>{protocol.encounterCount} encounters</span>
        </div>
        <Link href={`/protocols/${protocol.id}`}>
          <Button className="w-full">
            View Protocol
            <ArrowRight className="h-4 w-4 ml-2" />
          </Button>
        </Link>
      </CardContent>
    </Card>
  );
}
