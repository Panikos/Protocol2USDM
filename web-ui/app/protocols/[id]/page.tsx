'use client';

import { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
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
  Link2,
  Image,
  BookOpen,
  Cpu,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { TabGroup, TabButton } from '@/components/ui/tab-group';
import { ExportButton, ExportFormat } from '@/components/ui/export-button';
import { exportToCSV, exportToJSON, exportToPDF, formatUSDMForExport } from '@/lib/export/exportUtils';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { SoAView } from '@/components/soa';
import { TimelineView, ExecutionModelView, SAPDataView, ARSDataView } from '@/components/timeline';
import { ProvenanceView, ExtractionProvenanceView, IntegrityReportView } from '@/components/provenance';
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
  CrossReferencesView,
  FiguresGalleryView,
  NarrativeView,
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
import { useAutoSave } from '@/hooks/useAutoSave';
import { usePatchedUsdm } from '@/hooks/usePatchedUsdm';
import { useEditModeStore } from '@/stores/editModeStore';
import { toast } from '@/stores/toastStore';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { KeyboardShortcutsPanel } from '@/components/ui/keyboard-shortcuts';
import { cn } from '@/lib/utils';
import { EntityProvenanceContext } from '@/hooks/useEntityProvenance';
import type { ProvenanceData, ExtractionProvenanceData, EntityProvenanceData, IntegrityReport } from '@/lib/provenance/types';

type TabId = 'overview' | 'eligibility' | 'objectives' | 'design' | 'interventions' | 'amendments' | 'narrative' | 'extensions' | 'entities' | 'procedures' | 'sites' | 'footnotes' | 'references' | 'figures' | 'quality' | 'validation' | 'document' | 'documents' | 'intermediate' | 'soa' | 'timeline' | 'provenance' | 'schedule';

const VALID_TABS: Set<string> = new Set([
  'overview','eligibility','objectives','design','interventions','amendments','narrative',
  'extensions','entities','procedures','sites','footnotes','references','figures',
  'quality','validation','document','documents','intermediate','soa','timeline',
  'provenance','schedule',
]);

export default function ProtocolDetailPage() {
  const params = useParams();
  const protocolId = params.id as string;
  const searchParams = useSearchParams();
  const router = useRouter();

  // Read initial tab from URL ?tab= param
  const urlTab = searchParams.get('tab') ?? 'overview';
  const initialTab: TabId = VALID_TABS.has(urlTab) ? (urlTab as TabId) : 'overview';
  const [activeTab, setActiveTabState] = useState<TabId>(initialTab);

  // Wrapper that also updates the URL
  const setActiveTab = (tab: TabId) => {
    setActiveTabState(tab);
    const url = new URL(window.location.href);
    url.searchParams.set('tab', tab);
    router.replace(url.pathname + url.search, { scroll: false });
  };
  const [targetSectionNumber, setTargetSectionNumber] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [provenance, setProvenance] = useState<ProvenanceData | null>(null);
  const [extractionProvenance, setExtractionProvenance] = useState<ExtractionProvenanceData | null>(null);
  const [entityProvenance, setEntityProvenance] = useState<EntityProvenanceData | null>(null);
  const [integrityReport, setIntegrityReport] = useState<IntegrityReport | null>(null);
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
  // Auto-save drafts every 30s and on tab blur
  useAutoSave(protocolId);

  // Load protocol data
  useEffect(() => {
    async function loadProtocol() {
      setIsLoading(true);
      setError(null);

      try {
        // Load USDM
        const usdmRes = await fetch(`/api/protocols/${protocolId}/usdm`);
        if (!usdmRes.ok) throw new Error('Failed to load protocol');
        const { usdm, revision, provenance: provData, extractionProvenance: extProv, entityProvenance: entProv, integrityReport: intReport, intermediateFiles: intFiles } = await usdmRes.json();
        
        setProtocol(protocolId, usdm, revision);
        setProvenance(provData);
        setExtractionProvenance(extProv ?? null);
        setEntityProvenance(entProv ?? null);
        setIntegrityReport(intReport ?? null);
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
      const { usdm: newUsdm, revision: newRevision, provenance: provData, extractionProvenance: extProv, entityProvenance: entProv, integrityReport: intReport } = await usdmRes.json();
      
      setProtocol(protocolId, newUsdm, newRevision);
      setProvenance(provData);
      setExtractionProvenance(extProv ?? null);
      setEntityProvenance(entProv ?? null);
      setIntegrityReport(intReport ?? null);
      
      // Update semantic store with new revision (no draft after publish)
      useSemanticStore.getState().loadDraft(protocolId, newRevision, null);
      
      // Clear SoA edit store AFTER USDM is reloaded so the view shows fresh data
      const { useSoAEditStore } = await import('@/stores/soaEditStore');
      useSoAEditStore.getState().reset();
    } catch (err) {
      console.error('Failed to reload USDM after publish:', err);
      toast.error('Failed to reload protocol after publish. Please refresh the page.');
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
        const errText = await response.text();
        console.error('Failed to save draft:', errText);
        toast.error('Failed to save draft');
      }
    } catch (err) {
      console.error('Error saving draft:', err);
      toast.error('Failed to save draft');
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
        const errText = await response.text();
        console.error('Failed to publish:', errText);
        toast.error('Failed to publish changes');
      }
    } catch (err) {
      console.error('Error publishing:', err);
      toast.error('Failed to publish changes');
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

  // Tabs that support semantic editing
  const EDITABLE_TABS: Set<TabId> = new Set([
    'overview', 'eligibility', 'objectives', 'design', 'interventions',
    'amendments', 'narrative', 'soa', 'document',
  ]);
  const isTabEditable = EDITABLE_TABS.has(activeTab);

  // Tab group definitions
  const protocolTabs = [
    { id: 'overview', label: 'Overview', icon: <FileText className="h-4 w-4" /> },
    { id: 'eligibility', label: 'Eligibility', icon: <ClipboardList className="h-4 w-4" /> },
    { id: 'objectives', label: 'Objectives', icon: <Target className="h-4 w-4" /> },
    { id: 'design', label: 'Design', icon: <Layers className="h-4 w-4" /> },
    { id: 'interventions', label: 'Interventions', icon: <Pill className="h-4 w-4" /> },
    { id: 'amendments', label: 'Amendments', icon: <FileEdit className="h-4 w-4" /> },
    { id: 'narrative', label: 'Narrative', icon: <BookOpen className="h-4 w-4" /> },
  ];

  const advancedTabs = [
    { id: 'extensions', label: 'Extensions', icon: <Layers className="h-4 w-4" /> },
    { id: 'entities', label: 'Entities', icon: <Microscope className="h-4 w-4" /> },
    { id: 'procedures', label: 'Procedures', icon: <Stethoscope className="h-4 w-4" /> },
    { id: 'sites', label: 'Sites', icon: <MapPin className="h-4 w-4" /> },
    { id: 'footnotes', label: 'Footnotes', icon: <FileText className="h-4 w-4" /> },
    { id: 'references', label: 'References', icon: <Link2 className="h-4 w-4" /> },
    { id: 'figures', label: 'Figures', icon: <Image className="h-4 w-4" /> },
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
    <div className="h-screen flex flex-col bg-slate-50 dark:bg-slate-950">
      {/* Skip navigation link — F14 */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-[100] focus:top-2 focus:left-2 focus:bg-primary focus:text-primary-foreground focus:px-4 focus:py-2 focus:rounded-md"
      >
        Skip to main content
      </a>
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
              <div className="flex items-center gap-1.5">
                <Button
                  variant={isEditMode ? 'default' : 'outline'}
                  size="sm"
                  onClick={toggleEditMode}
                  className={isEditMode ? 'bg-primary hover:bg-primary/90 text-primary-foreground' : ''}
                >
                  {isEditMode ? (
                    <><Pencil className="h-4 w-4 mr-2" />Editing</>
                  ) : (
                    <><Lock className="h-4 w-4 mr-2" />View Only</>
                  )}
                </Button>
                {isEditMode && !isTabEditable && (
                  <span className="text-xs text-muted-foreground bg-muted px-2 py-1 rounded">
                    Read-only tab
                  </span>
                )}
              </div>

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
              <ThemeToggle />
            </div>
          </div>
        </div>

        {/* Tab navigation */}
        <div className="container mx-auto px-4 overflow-visible">
          <nav className="flex items-center gap-1 -mb-px pb-2 overflow-x-auto scrollbar-hide">
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
      <main id="main-content" className="flex-1 overflow-auto"><div className="container mx-auto px-4 py-6 relative z-0">
        <EntityProvenanceContext.Provider value={entityProvenance}>
        <div className={cn(
          'flex gap-6',
          isEditMode && hasSemanticDraft ? 'flex-col lg:flex-row' : ''
        )}>
        <div className={cn('flex-1 min-w-0')}>
        <ErrorBoundary key={activeTab} section={activeTab}>
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
        {activeTab === 'narrative' && (
          <NarrativeView usdm={usdm} onNavigateToTab={(tab) => setActiveTab(tab as TabId)} targetSectionNumber={targetSectionNumber} onTargetSectionHandled={() => setTargetSectionNumber(null)} />
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
          <ValidationResultsView protocolId={protocolId} usdm={usdm} />
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
          <ProvenanceTab provenance={provenance} extractionProvenance={extractionProvenance} entityProvenance={entityProvenance} integrityReport={integrityReport} />
        )}
        {activeTab === 'references' && (
          <CrossReferencesView
            usdm={usdm}
            onNavigateToSection={(sectionNumber) => {
              setTargetSectionNumber(sectionNumber);
              setActiveTab('narrative');
            }}
          />
        )}
        {activeTab === 'figures' && (
          <FiguresGalleryView usdm={usdm} protocolId={protocolId} />
        )}
        {activeTab === 'schedule' && (
          <ScheduleTimelineView usdm={usdm} />
        )}
        </ErrorBoundary>
        </div>

        {/* DiffView sidebar — visible in edit mode when changes exist */}
        {isEditMode && hasSemanticDraft && (
          <div className="w-full lg:w-[380px] lg:shrink-0">
            <DiffView className="lg:sticky lg:top-4" />
          </div>
        )}
        </div>
        </EntityProvenanceContext.Provider>
      </div></main>

      {/* Version History Panel */}
      <VersionHistoryPanel
        protocolId={protocolId}
        isOpen={showHistory}
        onClose={() => setShowHistory(false)}
      />

      {/* Keyboard shortcuts help (press ?) */}
      <KeyboardShortcutsPanel />
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

function ProvenanceTab({
  provenance,
  extractionProvenance,
  entityProvenance,
  integrityReport,
}: {
  provenance: ProvenanceData | null;
  extractionProvenance: ExtractionProvenanceData | null;
  entityProvenance: EntityProvenanceData | null;
  integrityReport: IntegrityReport | null;
}) {
  const [viewMode, setViewMode] = useState<'soa' | 'extraction' | 'integrity'>(
    extractionProvenance ? 'extraction' : 'soa'
  );

  return (
    <div className="space-y-4">
      {/* View toggle */}
      <div className="flex items-center gap-2 p-1 bg-muted rounded-lg w-fit">
        <Button
          variant={viewMode === 'extraction' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setViewMode('extraction')}
          className="flex items-center gap-2"
        >
          <Cpu className="h-4 w-4" />
          Extraction Pipeline
        </Button>
        <Button
          variant={viewMode === 'integrity' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setViewMode('integrity')}
          className="flex items-center gap-2"
        >
          <AlertCircle className="h-4 w-4" />
          Integrity
          {integrityReport && integrityReport.summary.errors > 0 && (
            <span className="ml-1 inline-flex items-center justify-center h-4 min-w-[1rem] px-1 rounded-full bg-red-500 text-white text-[10px] font-bold">
              {integrityReport.summary.errors}
            </span>
          )}
        </Button>
        <Button
          variant={viewMode === 'soa' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setViewMode('soa')}
          className="flex items-center gap-2"
        >
          <Eye className="h-4 w-4" />
          SoA Cell Provenance
        </Button>
      </div>

      {viewMode === 'extraction' && (
        <ExtractionProvenanceView
          extractionProvenance={extractionProvenance}
          entityProvenance={entityProvenance}
        />
      )}
      {viewMode === 'integrity' && (
        <IntegrityReportView report={integrityReport} />
      )}
      {viewMode === 'soa' && (
        <ProvenanceView provenance={provenance} />
      )}
    </div>
  );
}
