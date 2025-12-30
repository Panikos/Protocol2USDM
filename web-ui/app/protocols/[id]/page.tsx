'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { 
  FileText, 
  Table, 
  GitBranch, 
  Eye, 
  ArrowLeft, 
  Loader2,
  AlertCircle,
  ClipboardList,
  Target,
  Layers,
  Pill,
  FileEdit,
  BarChart3,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { DraftPublishControls } from '@/components/overlay/DraftPublishControls';
import { SoAView } from '@/components/soa';
import { TimelineView } from '@/components/timeline';
import { ProvenanceView } from '@/components/provenance';
import {
  StudyMetadataView,
  EligibilityCriteriaView,
  ObjectivesEndpointsView,
  StudyDesignView,
  InterventionsView,
  AmendmentHistoryView,
} from '@/components/protocol';
import { QualityMetricsDashboard } from '@/components/quality';
import { useProtocolStore } from '@/stores/protocolStore';
import { useOverlayStore } from '@/stores/overlayStore';
import { cn } from '@/lib/utils';
import type { ProvenanceData } from '@/lib/provenance/types';

type TabId = 'overview' | 'eligibility' | 'objectives' | 'design' | 'interventions' | 'amendments' | 'quality' | 'soa' | 'timeline' | 'provenance';

export default function ProtocolDetailPage() {
  const params = useParams();
  const protocolId = params.id as string;
  
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [provenance, setProvenance] = useState<ProvenanceData | null>(null);

  const { setProtocol, usdm, metadata } = useProtocolStore();
  const { loadOverlays, draft } = useOverlayStore();

  // Load protocol data
  useEffect(() => {
    async function loadProtocol() {
      setIsLoading(true);
      setError(null);

      try {
        // Load USDM
        const usdmRes = await fetch(`/api/protocols/${protocolId}/usdm`);
        if (!usdmRes.ok) throw new Error('Failed to load protocol');
        const { usdm, revision, provenance: provData } = await usdmRes.json();
        
        setProtocol(protocolId, usdm, revision);
        setProvenance(provData);

        // Load overlays
        const [publishedRes, draftRes] = await Promise.all([
          fetch(`/api/protocols/${protocolId}/overlay/published`),
          fetch(`/api/protocols/${protocolId}/overlay/draft`),
        ]);

        const published = publishedRes.ok ? await publishedRes.json() : null;
        const draftOverlay = draftRes.ok ? await draftRes.json() : null;

        loadOverlays(protocolId, revision, published, draftOverlay);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    }

    loadProtocol();
  }, [protocolId, setProtocol, loadOverlays]);

  const handleSaveDraft = async () => {
    if (!draft) return;
    await fetch(`/api/protocols/${protocolId}/overlay/draft`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(draft),
    });
    useOverlayStore.getState().markClean();
  };

  const handlePublish = async () => {
    await fetch(`/api/protocols/${protocolId}/overlay/publish`, {
      method: 'POST',
    });
    useOverlayStore.getState().promoteDraftToPublished();
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Card className="max-w-md">
          <CardContent className="pt-6 text-center">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-destructive" />
            <h2 className="text-lg font-semibold mb-2">Error Loading Protocol</h2>
            <p className="text-muted-foreground mb-4">{error}</p>
            <Link href="/protocols">
              <Button>Back to Protocols</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  const studyDesign = usdm?.study?.versions?.[0]?.studyDesigns?.[0];

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="border-b bg-white sticky top-0 z-50">
        <div className="container mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/protocols">
                <Button variant="ghost" size="sm">
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  Back
                </Button>
              </Link>
              <div className="border-l pl-4">
                <h1 className="text-lg font-semibold">{protocolId}</h1>
                <p className="text-xs text-muted-foreground">
                  USDM {metadata?.usdmVersion} • Generated {metadata?.generatedAt ? 
                    new Date(metadata.generatedAt).toLocaleDateString() : 'N/A'}
                </p>
              </div>
            </div>
            <DraftPublishControls 
              onSaveDraft={handleSaveDraft}
              onPublish={handlePublish}
            />
          </div>
        </div>

        {/* Tab navigation */}
        <div className="container mx-auto px-4">
          <nav className="flex gap-1 -mb-px">
            <TabButton 
              active={activeTab === 'overview'} 
              onClick={() => setActiveTab('overview')}
              icon={<FileText className="h-4 w-4" />}
            >
              Overview
            </TabButton>
            <TabButton 
              active={activeTab === 'eligibility'} 
              onClick={() => setActiveTab('eligibility')}
              icon={<ClipboardList className="h-4 w-4" />}
            >
              Eligibility
            </TabButton>
            <TabButton 
              active={activeTab === 'objectives'} 
              onClick={() => setActiveTab('objectives')}
              icon={<Target className="h-4 w-4" />}
            >
              Objectives
            </TabButton>
            <TabButton 
              active={activeTab === 'design'} 
              onClick={() => setActiveTab('design')}
              icon={<Layers className="h-4 w-4" />}
            >
              Design
            </TabButton>
            <TabButton 
              active={activeTab === 'interventions'} 
              onClick={() => setActiveTab('interventions')}
              icon={<Pill className="h-4 w-4" />}
            >
              Interventions
            </TabButton>
            <TabButton 
              active={activeTab === 'amendments'} 
              onClick={() => setActiveTab('amendments')}
              icon={<FileEdit className="h-4 w-4" />}
            >
              Amendments
            </TabButton>
            <TabButton 
              active={activeTab === 'quality'} 
              onClick={() => setActiveTab('quality')}
              icon={<BarChart3 className="h-4 w-4" />}
            >
              Quality
            </TabButton>
            <TabButton 
              active={activeTab === 'soa'} 
              onClick={() => setActiveTab('soa')}
              icon={<Table className="h-4 w-4" />}
            >
              SoA
            </TabButton>
            <TabButton 
              active={activeTab === 'timeline'} 
              onClick={() => setActiveTab('timeline')}
              icon={<GitBranch className="h-4 w-4" />}
            >
              Timeline
            </TabButton>
            <TabButton 
              active={activeTab === 'provenance'} 
              onClick={() => setActiveTab('provenance')}
              icon={<Eye className="h-4 w-4" />}
            >
              Provenance
            </TabButton>
          </nav>
        </div>
      </header>

      {/* Content */}
      <main className="container mx-auto px-4 py-6">
        {activeTab === 'overview' && (
          <StudyMetadataView usdm={usdm} />
        )}
        {activeTab === 'eligibility' && (
          <EligibilityCriteriaView usdm={usdm} />
        )}
        {activeTab === 'objectives' && (
          <ObjectivesEndpointsView usdm={usdm} />
        )}
        {activeTab === 'design' && (
          <StudyDesignView usdm={usdm} />
        )}
        {activeTab === 'interventions' && (
          <InterventionsView usdm={usdm} />
        )}
        {activeTab === 'amendments' && (
          <AmendmentHistoryView usdm={usdm} />
        )}
        {activeTab === 'quality' && (
          <QualityMetricsDashboard usdm={usdm} />
        )}
        {activeTab === 'soa' && (
          <SoATab provenance={provenance} />
        )}
        {activeTab === 'timeline' && (
          <TimelineTab />
        )}
        {activeTab === 'provenance' && (
          <ProvenanceTab provenance={provenance} />
        )}
      </main>
    </div>
  );
}

function TabButton({ 
  active, 
  onClick, 
  icon, 
  children 
}: { 
  active: boolean; 
  onClick: () => void; 
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors',
        active
          ? 'border-primary text-primary'
          : 'border-transparent text-muted-foreground hover:text-foreground hover:border-gray-300'
      )}
    >
      {icon}
      {children}
    </button>
  );
}

function OverviewTab({ 
  studyDesign, 
  metadata 
}: { 
  studyDesign: any; 
  metadata: any;
}) {
  const stats = [
    { label: 'Activities', value: studyDesign?.activities?.length ?? 0 },
    { label: 'Encounters', value: studyDesign?.encounters?.length ?? 0 },
    { label: 'Epochs', value: studyDesign?.epochs?.length ?? 0 },
    { label: 'Arms', value: studyDesign?.arms?.length ?? 0 },
  ];

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map(stat => (
          <Card key={stat.label}>
            <CardContent className="pt-6">
              <p className="text-3xl font-bold">{stat.value}</p>
              <p className="text-sm text-muted-foreground">{stat.label}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Study Design Info */}
      <Card>
        <CardHeader>
          <CardTitle>Study Design</CardTitle>
          <CardDescription>
            {studyDesign?.name ?? 'Unnamed study design'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="font-medium text-muted-foreground">Type</dt>
              <dd>{studyDesign?.instanceType ?? 'N/A'}</dd>
            </div>
            <div>
              <dt className="font-medium text-muted-foreground">Blinding</dt>
              <dd>{studyDesign?.blindingSchema?.standardCode?.decode ?? 'N/A'}</dd>
            </div>
            <div>
              <dt className="font-medium text-muted-foreground">Randomization</dt>
              <dd>{studyDesign?.randomizationType?.code ?? 'N/A'}</dd>
            </div>
            <div>
              <dt className="font-medium text-muted-foreground">USDM Version</dt>
              <dd>{metadata?.usdmVersion ?? 'N/A'}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {/* Arms */}
      {studyDesign?.arms?.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Study Arms ({studyDesign.arms.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {studyDesign.arms.map((arm: any) => (
                <div key={arm.id} className="p-3 bg-muted rounded-lg">
                  <h4 className="font-medium">{arm.name}</h4>
                  <p className="text-sm text-muted-foreground">{arm.description}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function SoATab({ provenance }: { provenance: ProvenanceData | null }) {
  return <SoAView provenance={provenance} />;
}

function TimelineTab() {
  return <TimelineView />;
}

function ProvenanceTab({ provenance }: { provenance: ProvenanceData | null }) {
  return <ProvenanceView provenance={provenance} />;
}
