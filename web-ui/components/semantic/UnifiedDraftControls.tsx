'use client';

import { useState } from 'react';
import { Save, Upload, Trash2, AlertTriangle, CheckCircle, XCircle, FileEdit, History, Undo2, Redo2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useSemanticStore, selectHasSemanticDraft, selectCanUndo, selectCanRedo } from '@/stores/semanticStore';
import { useOverlayStore } from '@/stores/overlayStore';
import { cn } from '@/lib/utils';
import { toast } from '@/stores/toastStore';
import type { PublishResponse } from '@/lib/semantic/schema';

interface UnifiedDraftControlsProps {
  protocolId: string;
  onSaveOverlayDraft?: () => Promise<void>;
  onPublishOverlay?: () => Promise<void>;
  onPublishSuccess?: () => Promise<void>;
  onShowHistory?: () => void;
  className?: string;
}

export function UnifiedDraftControls({
  protocolId,
  onSaveOverlayDraft,
  onPublishOverlay,
  onPublishSuccess,
  onShowHistory,
  className,
}: UnifiedDraftControlsProps) {
  // Semantic store
  const { 
    draft: semanticDraft, 
    isDirty: semanticIsDirty, 
    usdmRevision,
    lastPublishResult,
    markClean: markSemanticClean,
    clearDraft: clearSemanticDraft,
    setPublishResult,
    setError,
  } = useSemanticStore();
  
  const hasSemanticDraft = useSemanticStore(selectHasSemanticDraft);
  const canUndo = useSemanticStore(selectCanUndo);
  const canRedo = useSemanticStore(selectCanRedo);
  const undo = useSemanticStore(state => state.undo);
  const redo = useSemanticStore(state => state.redo);
  
  // Overlay store
  const { 
    isDirty: overlayIsDirty, 
    resetToPublished: resetOverlay,
  } = useOverlayStore();
  
  const [isSaving, setIsSaving] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [showDiscardConfirm, setShowDiscardConfirm] = useState(false);
  const [showPublishConfirm, setShowPublishConfirm] = useState(false);
  const [showPublishResult, setShowPublishResult] = useState(false);

  // Combined state
  const hasAnyChanges = hasSemanticDraft || semanticIsDirty || overlayIsDirty;
  const semanticChangeCount = semanticDraft?.patch?.length ?? 0;
  const isUnsaved = semanticIsDirty || overlayIsDirty;

  const handleSaveDraft = async () => {
    // Access current state directly (not captured at render time)
    const semanticState = useSemanticStore.getState();
    const currentDraft = semanticState.draft;
    const currentIsDirty = semanticState.isDirty;
    const currentRevision = semanticState.usdmRevision;
    const overlayState = useOverlayStore.getState();
    const currentOverlayDirty = overlayState.isDirty;
    
    if (!currentDraft && !currentOverlayDirty) return;
    
    setIsSaving(true);
    try {
      // Save semantic draft
      if (currentDraft && currentDraft.patch.length > 0) {
        const requestBody = {
          protocolId,
          usdmRevision: currentRevision ?? currentDraft.usdmRevision,
          updatedBy: currentDraft.updatedBy || 'ui-user',
          patch: currentDraft.patch,
        };
        const response = await fetch(`/api/protocols/${protocolId}/semantic/draft`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestBody),
        });
        
        if (response.ok) {
          useSemanticStore.getState().markClean();
          toast.success('Draft saved');
        } else {
          const responseText = await response.text();
          console.error('Save draft error - status:', response.status, 'body:', responseText);
          try {
            const errorData = JSON.parse(responseText);
            const msg = errorData.message || errorData.error || `Save failed (${response.status})`;
            setError(msg);
            toast.error(msg);
          } catch {
            const msg = `Save failed: ${response.status} - ${responseText.slice(0, 100)}`;
            setError(msg);
            toast.error(msg);
          }
          return;
        }
      }
      
      // Save overlay draft
      if (currentOverlayDirty && onSaveOverlayDraft) {
        await onSaveOverlayDraft();
      }
    } catch (err) {
      console.error('Save draft exception:', err);
      const msg = err instanceof Error ? err.message : 'Failed to save draft';
      setError(msg);
      toast.error(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const handlePublish = async () => {
    setIsPublishing(true);
    try {
      // Save drafts first
      await handleSaveDraft();
      
      // Access current state directly
      const semanticState = useSemanticStore.getState();
      const currentDraft = semanticState.draft;
      const overlayState = useOverlayStore.getState();
      
      // Publish semantic changes
      if (currentDraft && currentDraft.patch.length > 0) {
        const response = await fetch(`/api/protocols/${protocolId}/semantic/publish`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        });
        
        const result = await response.json();
        
        // Handle validation gate — offer force-publish
        if (!response.ok && result.error === 'validation_failed') {
          toast.error('Validation errors found. Publishing anyway...');
          const forceResponse = await fetch(`/api/protocols/${protocolId}/semantic/publish`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ forcePublish: true }),
          });
          const forceResult = await forceResponse.json();
          setPublishResult(forceResult as PublishResponse);
          setShowPublishResult(true);
          if (forceResult.success) {
            useSemanticStore.getState().clearDraft();
            toast.success('Changes published (with validation warnings)');
            if (onPublishSuccess) await onPublishSuccess();
          } else {
            setShowPublishConfirm(false);
            setIsPublishing(false);
            return;
          }
        } else {
          setPublishResult(result as PublishResponse);
          setShowPublishResult(true);
          if (result.success) {
            useSemanticStore.getState().clearDraft();
            toast.success('Changes published successfully');
            if (onPublishSuccess) await onPublishSuccess();
          } else {
            setShowPublishConfirm(false);
            setIsPublishing(false);
            return;
          }
        }
      }
      
      // Publish overlay changes
      if (overlayState.isDirty && onPublishOverlay) {
        await onPublishOverlay();
      }
      
      setShowPublishConfirm(false);
    } catch (err) {
      console.error('Publish error:', err);
      const msg = err instanceof Error ? err.message : 'Failed to publish';
      setError(msg);
      toast.error(msg);
    } finally {
      setIsPublishing(false);
    }
  };

  const handleDiscard = async () => {
    try {
      // Access current state directly
      const semanticState = useSemanticStore.getState();
      const currentDraft = semanticState.draft;
      const overlayState = useOverlayStore.getState();
      
      // Discard semantic draft
      if (currentDraft && currentDraft.patch.length > 0) {
        await fetch(`/api/protocols/${protocolId}/semantic/draft`, {
          method: 'DELETE',
        });
        useSemanticStore.getState().clearDraft();
      }
      
      // Discard overlay changes
      if (overlayState.isDirty) {
        overlayState.resetToPublished();
      }
      
      toast.info('Draft discarded');
      setShowDiscardConfirm(false);
    } catch (err) {
      console.error('Discard error:', err);
      const msg = err instanceof Error ? err.message : 'Failed to discard draft';
      setError(msg);
      toast.error(msg);
    }
  };

  // Don't show controls if no changes
  if (!hasAnyChanges && !isUnsaved) {
    return (
      <div className={cn('flex items-center gap-3', className)}>
        {onShowHistory && (
          <Button variant="ghost" size="sm" onClick={onShowHistory}>
            <History className="h-4 w-4 mr-2" />
            History
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className={cn('flex items-center gap-3', className)}>
      {/* Draft badge */}
      <div className="flex items-center gap-2 px-2 py-1 bg-blue-50 border border-blue-200 rounded-md">
        <FileEdit className="h-4 w-4 text-blue-600" />
        <span className="text-sm font-medium text-blue-700">
          Draft
        </span>
        {semanticChangeCount > 0 && (
          <span className="text-xs text-blue-500">
            ({semanticChangeCount} changes)
          </span>
        )}
      </div>

      {/* Undo / Redo */}
      <div className="flex items-center border rounded-md">
        <Button
          variant="ghost"
          size="sm"
          onClick={undo}
          disabled={!canUndo}
          className="h-8 px-2 rounded-r-none"
          title="Undo (Ctrl+Z)"
        >
          <Undo2 className="h-4 w-4" />
        </Button>
        <div className="w-px h-5 bg-border" />
        <Button
          variant="ghost"
          size="sm"
          onClick={redo}
          disabled={!canRedo}
          className="h-8 px-2 rounded-l-none"
          title="Redo (Ctrl+Shift+Z)"
        >
          <Redo2 className="h-4 w-4" />
        </Button>
      </div>

      {/* Unsaved indicator */}
      {isUnsaved && (
        <div className="flex items-center gap-1.5 text-orange-600">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-orange-500"></span>
          </span>
          <span className="text-xs font-medium">Unsaved</span>
        </div>
      )}

      {/* Save Draft */}
      <Button
        variant="outline"
        size="sm"
        onClick={handleSaveDraft}
        disabled={!isUnsaved || isSaving}
      >
        <Save className="h-4 w-4 mr-2" />
        {isSaving ? 'Saving...' : 'Save'}
      </Button>

      {/* Publish with confirmation */}
      {showPublishConfirm ? (
        <div className="flex items-center gap-2 p-2 bg-muted rounded-md">
          <span className="text-sm">Publish all changes?</span>
          <Button size="sm" onClick={handlePublish} disabled={isPublishing}>
            {isPublishing ? 'Publishing...' : 'Confirm'}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowPublishConfirm(false)}
          >
            Cancel
          </Button>
        </div>
      ) : (
        <Button
          size="sm"
          onClick={() => setShowPublishConfirm(true)}
          disabled={!hasAnyChanges}
        >
          <Upload className="h-4 w-4 mr-2" />
          Publish
        </Button>
      )}

      {/* Discard with confirmation */}
      {showDiscardConfirm ? (
        <div className="flex items-center gap-2 p-2 bg-muted rounded-md">
          <span className="text-sm text-destructive">Discard all changes?</span>
          <Button variant="destructive" size="sm" onClick={handleDiscard}>
            Discard
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowDiscardConfirm(false)}
          >
            Cancel
          </Button>
        </div>
      ) : (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowDiscardConfirm(true)}
          disabled={!hasAnyChanges}
        >
          <Trash2 className="h-4 w-4 mr-2" />
          Discard
        </Button>
      )}

      {/* History button */}
      {onShowHistory && (
        <Button variant="ghost" size="sm" onClick={onShowHistory}>
          <History className="h-4 w-4 mr-2" />
          History
        </Button>
      )}

      {/* Publish result modal */}
      {showPublishResult && lastPublishResult && (
        <PublishResultModal
          result={lastPublishResult}
          onClose={() => setShowPublishResult(false)}
        />
      )}
    </div>
  );
}

interface PublishResultModalProps {
  result: PublishResponse;
  onClose: () => void;
}

function PublishResultModal({ result, onClose }: PublishResultModalProps) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <div className="flex items-center gap-3 mb-4">
          {result.success ? (
            <CheckCircle className="h-8 w-8 text-green-500" />
          ) : (
            <XCircle className="h-8 w-8 text-red-500" />
          )}
          <h2 className="text-lg font-semibold">
            {result.success ? 'Published Successfully' : 'Publish Failed'}
          </h2>
        </div>

        {result.validation && (
          <div className="space-y-3 mb-6">
            <ValidationRow
              label="Schema Validation"
              valid={result.validation.schema.valid}
              errors={result.validation.schema.errors}
              warnings={result.validation.schema.warnings}
            />
            <ValidationRow
              label="USDM Validation"
              valid={result.validation.usdm.valid}
              errors={result.validation.usdm.errors}
              warnings={result.validation.usdm.warnings}
            />
            <ValidationRow
              label="CDISC Conformance"
              valid={result.validation.core.success}
              errors={result.validation.core.issues}
              warnings={result.validation.core.warnings}
            />
          </div>
        )}

        {result.error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm mb-4">
            {result.error}
          </div>
        )}

        <div className="flex justify-end">
          <Button onClick={onClose}>Close</Button>
        </div>
      </div>
    </div>
  );
}

function ValidationRow({
  label,
  valid,
  errors,
  warnings,
}: {
  label: string;
  valid: boolean;
  errors: number;
  warnings: number;
}) {
  return (
    <div className="flex items-center justify-between py-2 border-b">
      <span className="text-sm">{label}</span>
      <div className="flex items-center gap-2">
        {valid ? (
          <span className="flex items-center gap-1 text-green-600 text-sm">
            <CheckCircle className="h-4 w-4" />
            Passed
          </span>
        ) : (
          <span className="flex items-center gap-1 text-red-600 text-sm">
            <XCircle className="h-4 w-4" />
            {errors} errors
          </span>
        )}
        {warnings > 0 && (
          <span className="flex items-center gap-1 text-amber-600 text-sm">
            <AlertTriangle className="h-4 w-4" />
            {warnings}
          </span>
        )}
      </div>
    </div>
  );
}

export default UnifiedDraftControls;
