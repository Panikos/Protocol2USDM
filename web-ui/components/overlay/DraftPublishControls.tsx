'use client';

import { useState } from 'react';
import { Save, Upload, RotateCcw, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useOverlayStore } from '@/stores/overlayStore';
import { cn } from '@/lib/utils';

interface DraftPublishControlsProps {
  onSaveDraft: () => Promise<void>;
  onPublish: () => Promise<void>;
  className?: string;
}

export function DraftPublishControls({
  onSaveDraft,
  onPublish,
  className,
}: DraftPublishControlsProps) {
  const { isDirty, needsReconciliation, resetToPublished, draft } =
    useOverlayStore();
  const [isSaving, setIsSaving] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [showPublishConfirm, setShowPublishConfirm] = useState(false);

  const handleSaveDraft = async () => {
    setIsSaving(true);
    try {
      await onSaveDraft();
    } finally {
      setIsSaving(false);
    }
  };

  const handlePublish = async () => {
    setIsPublishing(true);
    try {
      await onPublish();
      setShowPublishConfirm(false);
    } finally {
      setIsPublishing(false);
    }
  };

  const handleReset = () => {
    resetToPublished();
    setShowResetConfirm(false);
  };

  return (
    <div className={cn('flex items-center gap-3', className)}>
      {/* Status indicator */}
      <DirtyStateIndicator isDirty={isDirty} status={draft?.status ?? 'draft'} />

      {/* Reconciliation warning */}
      {needsReconciliation && (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-amber-50 border border-amber-200 rounded-md text-amber-800 text-sm">
          <AlertTriangle className="h-4 w-4" />
          <span>USDM updated since last publish</span>
        </div>
      )}

      {/* Action buttons */}
      <Button
        variant="outline"
        size="sm"
        onClick={handleSaveDraft}
        disabled={!isDirty || isSaving}
      >
        <Save className="h-4 w-4 mr-2" />
        {isSaving ? 'Saving...' : 'Save Draft'}
      </Button>

      {/* Publish with confirmation */}
      {showPublishConfirm ? (
        <div className="flex items-center gap-2 p-2 bg-muted rounded-md">
          <span className="text-sm">Publish changes?</span>
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
          disabled={!isDirty}
        >
          <Upload className="h-4 w-4 mr-2" />
          Publish
        </Button>
      )}

      {/* Reset with confirmation */}
      {showResetConfirm ? (
        <div className="flex items-center gap-2 p-2 bg-muted rounded-md">
          <span className="text-sm text-destructive">Discard changes?</span>
          <Button variant="destructive" size="sm" onClick={handleReset}>
            Discard
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowResetConfirm(false)}
          >
            Cancel
          </Button>
        </div>
      ) : (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowResetConfirm(true)}
          disabled={!isDirty}
        >
          <RotateCcw className="h-4 w-4 mr-2" />
          Reset
        </Button>
      )}
    </div>
  );
}

interface DirtyStateIndicatorProps {
  isDirty: boolean;
  status: 'draft' | 'published';
}

function DirtyStateIndicator({ isDirty, status }: DirtyStateIndicatorProps) {
  return (
    <div className="flex items-center gap-2">
      {/* Status badge */}
      <span
        className={cn(
          'px-2 py-0.5 text-xs font-medium rounded-full border',
          status === 'published'
            ? 'bg-green-50 text-green-700 border-green-200'
            : 'bg-amber-50 text-amber-700 border-amber-200'
        )}
      >
        {status === 'published' ? 'Published' : 'Draft'}
      </span>

      {/* Dirty indicator */}
      {isDirty && (
        <div className="flex items-center gap-1.5 text-orange-600">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-orange-500"></span>
          </span>
          <span className="text-xs font-medium">Unsaved</span>
        </div>
      )}
    </div>
  );
}

export { DirtyStateIndicator };
