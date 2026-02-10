'use client';

import { useEffect, useState, useMemo } from 'react';
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
  Microscope,
  Stethoscope,
  MapPin,
  FolderOpen,
  Database,
  Activity,
  FileBarChart,
  FileOutput,
  Pencil,
  Lock,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { TabGroup, TabButton } from '@/components/ui/tab-group';
import { ExportButton, ExportFormat } from '@/components/ui/export-button';
import { exportToCSV, exportToJSON, exportToPDF, formatUSDMForExport } from '@/lib/export/exportUtils';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { SoAView } from '@/components/soa';
import { TimelineView, ExecutionModelView, SAPDataView, ARSDataView } from '@/components/timeline';
import { ProvenanceView } from '@/components/provenance';
import {
  StudyMetadataView,
  EligibilityCriteriaView,
  ObjectivesEndpointsView,
  StudyDesignView,
  InterventionsView,
  AmendmentHistoryView,
  ExtensionsView,
  AdvancedEntitiesView,
  ProceduresDevicesView,
  StudySitesView,
  FootnotesView,
  ScheduleTimelineView,
} from '@/components/protocol';
import { QualityMetricsDashboard, ValidationResultsView } from '@/components/quality';
import { DocumentStructureView } from '@/components/intermediate';
import { DocumentsTab, IntermediateFilesTab } from '@/components/documents';
import { UnifiedDraftControls, VersionHistoryPanel, DiffView } from '@/components/semantic';
import { useSemanticStore, selectHasSemanticDraft } from '@/stores/semanticStore';
import { useProtocolStore } from '@/stores/protocolStore';
import { useOverlayStore } from '@/stores/overlayStore';
import { useUndoRedoShortcuts } from '@/hooks/useUndoRedoShortcuts';
import { useUnsavedChangesGuard } from '@/hooks/useUnsavedChangesGuard';
import { usePatchedUsdm } from '@/hooks/usePatchedUsdm';
import { useEditModeStore } from '@/stores/editModeStore';
import { cn } from '@/lib/utils';
import type { ProvenanceData } from '@/lib/provenance/types';

type TabId = 'overview' | 'eligibility' | 'objectives' | 'design' | 'interventions' | 'amendments' | 'extensions' | 'entities' | 'procedures' | 'sites' | 'footnotes' | 'quality' | 'validation' | 'document' | 'documents' | 'intermediate' | 'soa' | 'timeline' | 'provenance' | 'schedule';

export default function ProtocolDetailPage() {
  const params = useParams();
  const protocolId = params.id as string;
  
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [provenance, setProvenance] = useState<ProvenanceData | null>(null);
  const [intermediateFiles, setIntermediateFiles] = useState<Record<string, unknown> | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  const { setProtocol, metadata } = useProtocolStore();
  const usdm = usePatchedUsdm();
  const { loadOverlays, draft } = useOverlayStore();
  const semanticDraft = useSemanticStore((state) => state.draft);
  const hasSemanticDraft = useSemanticStore(selectHasSemanticDraft);
  const { isEditMode, toggleEditMode } = useEditModeStore();

  // Ctrl+Z / Ctrl+Shift+Z for undo/redo on semantic patches
  useUndoRedoShortcuts();
  // Warn on tab close if unsaved changes
  useUnsavedChangesGuard();

  // Load protocol data
  useEffect(() => {
    async function loadProtocol() {
      setIsLoading(true);
      setError(null);

      try {
        // Load USDM
        const usdmRes = await fetch(`/api/protocols/${protocolId}/usdm`);
        if (!usdmRes.ok) throw new Error('Failed to load protocol');
        const { usdm, revision, provenance: provData, intermediateFiles: intFiles } = await usdmRes.json();
        
        setProtocol(protocolId, usdm, revision);
        setProvenance(provData);
        setIntermediateFiles(intFiles);

        // Load overlays
        const [publishedRes, draftRes] = await Promise.all([
          fetch(`/api/protocols/${protocolId}/overlay/published`),
          fetch(`/api/protocols/${protocolId}/overlay/draft`),
        ]);

        const published = publishedRes.ok ? await publishedRes.json() : null;
        const draftOverlay = draftRes.ok ? await draftRes.json() : null;

        loadOverlays(protocolId, revision, published, draftOverlay);

        // Load semantic draft
        try {
          const semanticDraftRes = await fetch(`/api/protocols/${protocolId}/semantic/draft`);
          const semanticDraft = semanticDraftRes.ok ? await semanticDraftRes.json() : null;
          useSemanticStore.getState().loadDraft(protocolId, revision, semanticDraft);
        } catch (semanticErr) {
          console.warn('Failed to load semantic draft:', semanticErr);
          // Initialize with empty state even if load fails
          useSemanticStore.getState().loadDraft(protocolId, revision, null);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    }

    loadProtocol();
  }, [protocolId, setProtocol, loadOverlays]);

  // Reload USDM from server (called after publish to show updated data)
  const handleReloadUsdm = async () => {
    try {
      // Add cache-busting timestamp to ensure fresh data after publish
      const usdmRes = await fetch(`/api/protocols/${protocolId}/usdm?t=${Date.now()}`, {
        cache: 'no-store',
      });
      if (!usdmRes.ok) throw new Error('Failed to reload protocol');
      const { usdm: newUsdm, revision: newRevision, provenance: provData } = await usdmRes.json();
      
      setProtocol(protocolId, newUsdm, newRevision);
      setProvenance(provData);
      
      // Update semantic store with new revision (no draft after publish)
      useSemanticStore.getState().loadDraft(protocolId, newRevision, null);
      
      // Clear SoA edit store AFTER USDM is reloaded so the view shows fresh data
      const { useSoAEditStore } = await import('@/stores/soaEditStore');
      useSoAEditStore.getState().reset();
    } catch (err) {
      console.error('Failed to reload USDM after publish:', err);
    }
  };

  const handleSaveDraft = async () => {
    // Access current draft from store state (not captured at render time)
    const currentDraft = useOverlayStore.getState().draft;
    if (!currentDraft) return;
    
    try {
      const response = await fetch(`/api/protocols/${protocolId}/overlay/draft`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentDraft),
      });
      
      if (response.ok) {
        useOverlayStore.getState().markClean();
      } else {
        console.error('Failed to save draft:', await response.text());
      }
    } catch (err) {
      console.error('Error saving draft:', err);
    }
  };

  const handlePublish = async () => {
    // First save the current draft
    const currentDraft = useOverlayStore.getState().draft;
    if (!currentDraft) return;
    
    try {
      // Save draft first to ensure latest changes are persisted
      await fetch(`/api/protocols/${protocolId}/overlay/draft`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentDraft),
      });
      
      // Then publish
      const response = await fetch(`/api/protocols/${protocolId}/overlay/publish`, {
        method: 'POST',
      });
      
      if (response.ok) {
        useOverlayStore.getState().promoteDraftToPublished();
      } else {
        console.error('Failed to publish:', await response.text());
      }
    } catch (err) {
      console.error('Error publishing:', err);
    }
  };

  const handleExport = (format: ExportFormat) => {
    if (!usdm) return;
    
    const exportData = formatUSDMForExport(usdm as Record<string, unknown>);
    const filename = `${protocolId}_${activeTab}`;
    
    switch (format) {
      case 'csv':
        // Export current tab data as CSV
        let csvData: Record<string, unknown>[] = [];
        if (activeTab === 'eligibility') csvData = exportData.eligibility;
        else if (activeTab === 'objectives') csvData = exportData.objectives;
        else if (activeTab === 'soa') csvData = exportData.activities;
        else csvData = [exportData.metadata];
        exportToCSV(csvData, { filename });
        break;
      case 'json':
        exportToJSON(usdm, { filename: `${protocolId}_usdm` });
        break;
      case 'pdf':
        exportToPDF('export-content', { 
          filename, 
          title: protocolId,
          subtitle: `${activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} Export`
        });
        break;
    }
  };

  // Tab group definitions
  const protocolTabs = [
    { id: 'overview', label: 'Overview', icon: <FileText className="h-4 w-4" /> },
    { id: 'eligibility', label: 'Eligibility', icon: <ClipboardList className="h-4 w-4" /> },
    { id: 'objectives', label: 'Objectives', icon: <Target className="h-4 w-4" /> },
    { id: 'design', label: 'Design', icon: <Layers className="h-4 w-4" /> },
    { id: 'interventions', label: 'Interventions', icon: <Pill className="h-4 w-4" /> },
    { id: 'amendments', label: 'Amendments', icon: <FileEdit className="h-4 w-4" /> },
  ];

  const advancedTabs = [
    { id: 'extensions', label: 'Extensions', icon: <Layers className="h-4 w-4" /> },
    { id: 'entities', label: 'Entities', icon: <Microscope className="h-4 w-4" /> },
    { id: 'procedures', label: 'Procedures', icon: <Stethoscope className="h-4 w-4" /> },
    { id: 'sites', label: 'Sites', icon: <MapPin className="h-4 w-4" /> },
    { id: 'footnotes', label: 'Footnotes', icon: <FileText className="h-4 w-4" /> },
    { id: 'schedule', label: 'Schedule', icon: <Activity className="h-4 w-4" /> },
  ];

  const qualityTabs = [
    { id: 'quality', label: 'Metrics', icon: <BarChart3 className="h-4 w-4" /> },
    { id: 'validation', label: 'Validation', icon: <AlertCircle className="h-4 w-4" /> },
  ];

  const dataTabs = [
    { id: 'documents', label: 'Documents', icon: <FileText className="h-4 w-4" /> },
    { id: 'intermediate', label: 'Intermediate', icon: <FolderOpen className="h-4 w-4" /> },
    { id: 'document', label: 'M11 Protocol', icon: <FileOutput className="h-4 w-4" /> },
    { id: 'soa', label: 'SoA Table', icon: <Table className="h-4 w-4" /> },
    { id: 'timeline', label: 'Timeline', icon: <GitBranch className="h-4 w-4" /> },
    { id: 'provenance', label: 'Provenance', icon: <Eye className="h-4 w-4" /> },
  ];

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
    <div className="h-screen flex flex-col bg-slate-50">
      {/* Header */}
      <header data-protocol-sticky-header className="border-b bg-white shrink-0 z-50 overflow-visible">
        <div className="container mx-auto px-4 py-3 overflow-visible">
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
                  {semanticDraft?.updatedAt && (
                    <> • Last Edited {new Date(semanticDraft.updatedAt).toLocaleString()}</>
                  )}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {/* Edit Mode Toggle */}
              <Button
                variant={isEditMode ? 'default' : 'outline'}
                size="sm"
                onClick={toggleEditMode}
                className={isEditMode ? 'bg-blue-600 hover:bg-blue-700 text-white' : ''}
              >
                {isEditMode ? (
                  <><Pencil className="h-4 w-4 mr-2" />Editing</>
                ) : (
                  <><Lock className="h-4 w-4 mr-2" />View Only</>
                )}
              </Button>

              {/* Draft controls (only visible in edit mode) */}
              {isEditMode && (
                <UnifiedDraftControls 
                  protocolId={protocolId}
                  onSaveOverlayDraft={handleSaveDraft}
                  onPublishOverlay={handlePublish}
                  onPublishSuccess={handleReloadUsdm}
                  onShowHistory={() => setShowHistory(true)}
                />
              )}
            </div>
          </div>
        </div>

        {/* Tab navigation */}
        <div className="container mx-auto px-4 overflow-visible">
          <nav className="flex items-center gap-1 -mb-px min-w-max pb-2 overflow-visible">
            <TabGroup
              label="Protocol"
              icon={<FolderOpen className="h-4 w-4" />}
              tabs={protocolTabs}
              activeTab={activeTab}
              onTabChange={(id) => setActiveTab(id as TabId)}
              defaultExpanded={false}
            />
            <TabGroup
              label="Advanced"
              icon={<Database className="h-4 w-4" />}
              tabs={advancedTabs}
              activeTab={activeTab}
              onTabChange={(id) => setActiveTab(id as TabId)}
            />
            <TabGroup
              label="Quality"
              icon={<Activity className="h-4 w-4" />}
              tabs={qualityTabs}
              activeTab={activeTab}
              onTabChange={(id) => setActiveTab(id as TabId)}
            />
            <TabGroup
              label="Data"
              icon={<Table className="h-4 w-4" />}
              tabs={dataTabs}
              activeTab={activeTab}
              onTabChange={(id) => setActiveTab(id as TabId)}
            />
            
            <div className="flex-1" />
            
            <ExportButton onExport={handleExport} />
          </nav>
        </div>
      </header>

      {/* Content */}
      <main id="export-content" className="flex-1 overflow-auto"><div className="container mx-auto px-4 py-6 relative z-0">
        <div className={cn(
          'flex gap-6',
          isEditMode && hasSemanticDraft ? 'flex-col lg:flex-row' : ''
        )}>
        <div className={cn('flex-1 min-w-0')}>
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
        {activeTab === 'extensions' && (
          <ExtensionsView usdm={usdm} />
        )}
        {activeTab === 'entities' && (
          <AdvancedEntitiesView usdm={usdm} />
        )}
        {activeTab === 'procedures' && (
          <ProceduresDevicesView usdm={usdm} />
        )}
        {activeTab === 'sites' && (
          <StudySitesView usdm={usdm} />
        )}
        {activeTab === 'footnotes' && (
          <FootnotesView usdm={usdm} />
        )}
        {activeTab === 'quality' && (
          <QualityMetricsDashboard usdm={usdm} />
        )}
        {activeTab === 'validation' && (
          <ValidationResultsView protocolId={protocolId} />
        )}
        {activeTab === 'documents' && (
          <DocumentsTab protocolId={protocolId} />
        )}
        {activeTab === 'intermediate' && (
          <IntermediateFilesTab protocolId={protocolId} />
        )}
        {activeTab === 'document' && (
          <DocumentStructureView usdm={usdm} protocolId={protocolId} />
        )}
        {activeTab === 'soa' && (
          <SoATab provenance={provenance} />
        )}
        {activeTab === 'timeline' && (
          <TimelineTab intermediateFiles={intermediateFiles} protocolId={protocolId} />
        )}
        {activeTab === 'provenance' && (
          <ProvenanceTab provenance={provenance} />
        )}
        {activeTab === 'schedule' && (
          <ScheduleTimelineView usdm={usdm} />
        )}
        </div>

        {/* DiffView sidebar — visible in edit mode when changes exist */}
        {isEditMode && hasSemanticDraft && (
          <div className="w-full lg:w-[380px] lg:shrink-0">
            <DiffView className="lg:sticky lg:top-4" />
          </div>
        )}
        </div>
      </div></main>

      {/* Version History Panel */}
      <VersionHistoryPanel
        protocolId={protocolId}
        isOpen={showHistory}
        onClose={() => setShowHistory(false)}
      />
    </div>
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

function TimelineTab({ intermediateFiles, protocolId }: { intermediateFiles: Record<string, unknown> | null; protocolId: string }) {
  const [viewMode, setViewMode] = useState<'execution' | 'sap' | 'ars' | 'graph'>('execution');
  
  // Extract execution model data from intermediate files
  const executionModel = useMemo(() => {
    const execFile = intermediateFiles?.executionModel as { data?: Record<string, unknown> } | null;
    return execFile?.data ?? null;
  }, [intermediateFiles]);

  return (
    <div className="space-y-4">
      {/* View Toggle */}
      <div className="flex items-center gap-2 p-1 bg-muted rounded-lg w-fit">
        <Button
          variant={viewMode === 'execution' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setViewMode('execution')}
          className="flex items-center gap-2"
        >
          <Activity className="h-4 w-4" />
          Execution Model
        </Button>
        <Button
          variant={viewMode === 'sap' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setViewMode('sap')}
          className="flex items-center gap-2"
        >
          <BarChart3 className="h-4 w-4" />
          SAP Data
        </Button>
        <Button
          variant={viewMode === 'ars' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setViewMode('ars')}
          className="flex items-center gap-2"
        >
          <FileBarChart className="h-4 w-4" />
          CDISC ARS
        </Button>
        <Button
          variant={viewMode === 'graph' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setViewMode('graph')}
          className="flex items-center gap-2"
        >
          <GitBranch className="h-4 w-4" />
          Graph View
        </Button>
      </div>

      {/* Content */}
      {viewMode === 'execution' && <ExecutionModelView />}
      {viewMode === 'sap' && <SAPDataView />}
      {viewMode === 'ars' && <ARSDataView protocolId={protocolId} />}
      {viewMode === 'graph' && <TimelineView executionModel={executionModel} />}
    </div>
  );
}

function ProvenanceTab({ provenance }: { provenance: ProvenanceData | null }) {
  return <ProvenanceView provenance={provenance} />;
}
