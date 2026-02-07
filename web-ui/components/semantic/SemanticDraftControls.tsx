'use client';

import { useState } from 'react';
import { Save, Upload, Trash2, AlertTriangle, CheckCircle, XCircle, FileEdit } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useSemanticStore, selectHasSemanticDraft } from '@/stores/semanticStore';
import { cn } from '@/lib/utils';
import type { PublishResponse } from '@/lib/semantic/schema';

interface SemanticDraftControlsProps {
  protocolId: string;
  className?: string;
}

export function SemanticDraftControls({
  protocolId,
  className,
}: SemanticDraftControlsProps) {
  const { 
    draft, 
    isDirty, 
    usdmRevision,
    lastPublishResult,
    markClean,
    clearDraft,
    setPublishResult,
    setError,
  } = useSemanticStore();
  
  const hasSemanticDraft = useSemanticStore(selectHasSemanticDraft);
  
  const [isSaving, setIsSaving] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [showDiscardConfirm, setShowDiscardConfirm] = useState(false);
  const [showPublishConfirm, setShowPublishConfirm] = useState(false);
  const [showPublishResult, setShowPublishResult] = useState(false);

  const handleSaveDraft = async () => {
    if (!draft) return;
    
    setIsSaving(true);
    try {
      const response = await fetch(`/api/protocols/${protocolId}/semantic/draft`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          protocolId,
          usdmRevision: usdmRevision ?? draft.usdmRevision,
          updatedBy: draft.updatedBy,
          patch: draft.patch,
        }),
      });
      
      if (response.ok) {
        markClean();
      } else {
        const error = await response.json();
        setError(error.message || 'Failed to save draft');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save draft');
    } finally {
      setIsSaving(false);
    }
  };

  const handlePublish = async () => {
    setIsPublishing(true);
    try {
      // Save draft first
      if (isDirty && draft) {
        await fetch(`/api/protocols/${protocolId}/semantic/draft`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            protocolId,
            usdmRevision: usdmRevision ?? draft.usdmRevision,
            updatedBy: draft.updatedBy,
            patch: draft.patch,
          }),
        });
      }
      
      // Then publish
      const response = await fetch(`/api/protocols/${protocolId}/semantic/publish`, {
        method: 'POST',
      });
      
      const result: PublishResponse = await response.json();
      setPublishResult(result);
      setShowPublishResult(true);
      
      if (result.success) {
        clearDraft();
      }
      
      setShowPublishConfirm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to publish');
    } finally {
      setIsPublishing(false);
    }
  };

  const handleDiscard = async () => {
    try {
      await fetch(`/api/protocols/${protocolId}/semantic/draft`, {
        method: 'DELETE',
      });
      clearDraft();
      setShowDiscardConfirm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to discard draft');
    }
  };

  // Don't show controls if no semantic changes
  if (!hasSemanticDraft && !isDirty) {
    return null;
  }

  return (
    <div className={cn('flex items-center gap-3', className)}>
      {/* Semantic draft badge */}
      <div className="flex items-center gap-2 px-2 py-1 bg-blue-50 border border-blue-200 rounded-md">
        <FileEdit className="h-4 w-4 text-blue-600" />
        <span className="text-sm font-medium text-blue-700">
          Semantic Draft
        </span>
        {draft?.patch && (
          <span className="text-xs text-blue-500">
            ({draft.patch.length} changes)
          </span>
        )}
      </div>

      {/* Unsaved indicator */}
      {isDirty && (
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
        disabled={!isDirty || isSaving}
      >
        <Save className="h-4 w-4 mr-2" />
        {isSaving ? 'Saving...' : 'Save'}
      </Button>

      {/* Publish with confirmation */}
      {showPublishConfirm ? (
        <div className="flex items-center gap-2 p-2 bg-muted rounded-md">
          <span className="text-sm">Publish semantic changes?</span>
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
          disabled={!hasSemanticDraft}
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
          disabled={!hasSemanticDraft}
        >
          <Trash2 className="h-4 w-4 mr-2" />
          Discard
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
