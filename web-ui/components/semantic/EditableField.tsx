'use client';

import { useState, useRef, useEffect, useMemo } from 'react';
import { Pencil, Check, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useSemanticStore } from '@/stores/semanticStore';
import { cn } from '@/lib/utils';
import type { JsonPatchOp } from '@/lib/semantic/schema';

interface EditableFieldProps {
  path: string;
  value: string | number | boolean | null | undefined;
  label?: string;
  type?: 'text' | 'textarea' | 'number' | 'boolean';
  className?: string;
  displayClassName?: string;
  editable?: boolean;
  placeholder?: string;
}

export function EditableField({
  path,
  value,
  label,
  type = 'text',
  className,
  displayClassName,
  editable = true,
  placeholder = 'Not specified',
}: EditableFieldProps) {
  const [isEditing, setIsEditing] = useState(false);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);
  const { addPatchOp, draft } = useSemanticStore();
  
  // Check if there's a pending patch for this path - use patched value if so
  const patchedValue = useMemo(() => {
    if (!draft?.patch) return value;
    // Find the last patch operation for this path
    const matchingOps = draft.patch.filter(op => op.path === path);
    if (matchingOps.length === 0) return value;
    const lastOp = matchingOps[matchingOps.length - 1];
    if (lastOp.op === 'remove') return null;
    return lastOp.value;
  }, [draft?.patch, path, value]);
  
  // Use patched value for display and editing
  const effectiveValue = patchedValue;
  const [editValue, setEditValue] = useState(String(effectiveValue ?? ''));
  
  // Update editValue when effectiveValue changes (e.g., after discard)
  useEffect(() => {
    if (!isEditing) {
      setEditValue(String(effectiveValue ?? ''));
    }
  }, [effectiveValue, isEditing]);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      if (inputRef.current instanceof HTMLInputElement) {
        inputRef.current.select();
      }
    }
  }, [isEditing]);

  const handleStartEdit = () => {
    if (!editable) return;
    setEditValue(String(effectiveValue ?? ''));
    setIsEditing(true);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditValue(String(effectiveValue ?? ''));
  };

  const handleSave = () => {
    let newValue: string | number | boolean | null = editValue;
    
    // Convert type
    if (type === 'number') {
      newValue = editValue === '' ? null : Number(editValue);
    } else if (type === 'boolean') {
      newValue = editValue === 'true';
    }
    
    // Only create patch if value changed from effective (patched) value
    if (newValue !== effectiveValue) {
      // Always use replace since we're updating from current state
      const op: JsonPatchOp = { op: 'replace', path, value: newValue };
      addPatchOp(op);
    }
    
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && type !== 'textarea') {
      e.preventDefault();
      handleSave();
    } else if (e.key === 'Escape') {
      handleCancel();
    }
  };

  const displayValue = effectiveValue === null || effectiveValue === undefined || effectiveValue === ''
    ? placeholder
    : String(effectiveValue);
  
  // Show visual indicator if value has been edited (differs from original)
  const hasBeenEdited = effectiveValue !== value;

  if (isEditing) {
    return (
      <div className={cn('flex items-start gap-2', className)}>
        {label && (
          <span className="text-sm font-medium text-muted-foreground min-w-[120px]">
            {label}:
          </span>
        )}
        <div className="flex-1 flex items-start gap-2">
          {type === 'textarea' ? (
            <textarea
              ref={inputRef as React.RefObject<HTMLTextAreaElement>}
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onKeyDown={handleKeyDown}
              className="flex-1 min-h-[80px] px-2 py-1 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              rows={3}
            />
          ) : type === 'boolean' ? (
            <select
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              className="flex-1 px-2 py-1 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          ) : (
            <input
              ref={inputRef as React.RefObject<HTMLInputElement>}
              type={type === 'number' ? 'number' : 'text'}
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onKeyDown={handleKeyDown}
              className="flex-1 px-2 py-1 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={handleSave}
          >
            <Check className="h-4 w-4 text-green-600" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={handleCancel}
          >
            <X className="h-4 w-4 text-red-600" />
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'group flex items-start gap-2',
        editable && 'cursor-pointer hover:bg-muted/50 rounded-md p-1 -m-1',
        className
      )}
      onClick={handleStartEdit}
    >
      {label && (
        <span className="text-sm font-medium text-muted-foreground min-w-[120px]">
          {label}:
        </span>
      )}
      <span
        className={cn(
          'flex-1 text-sm',
          (effectiveValue === null || effectiveValue === undefined || effectiveValue === '') && 'text-muted-foreground italic',
          hasBeenEdited && 'bg-amber-100 px-1 rounded border-l-2 border-amber-500',
          displayClassName
        )}
      >
        {displayValue}
      </span>
      {editable && (
        <Pencil className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
      )}
    </div>
  );
}

interface EditableListItemProps {
  path: string;
  value: string;
  index: number;
  onRemove?: () => void;
  className?: string;
}

export function EditableListItem({
  path,
  value,
  index,
  onRemove,
  className,
}: EditableListItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);
  const { addPatchOp } = useSemanticStore();

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleSave = () => {
    if (editValue !== value) {
      addPatchOp({ op: 'replace', path: `${path}/${index}`, value: editValue });
    }
    setIsEditing(false);
  };

  const handleRemove = () => {
    addPatchOp({ op: 'remove', path: `${path}/${index}` });
    onRemove?.();
  };

  if (isEditing) {
    return (
      <div className={cn('flex items-center gap-2', className)}>
        <input
          ref={inputRef}
          type="text"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSave();
            if (e.key === 'Escape') setIsEditing(false);
          }}
          className="flex-1 px-2 py-1 border rounded-md text-sm"
        />
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleSave}>
          <Check className="h-3 w-3" />
        </Button>
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setIsEditing(false)}>
          <X className="h-3 w-3" />
        </Button>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'group flex items-center gap-2 cursor-pointer hover:bg-muted/50 rounded px-2 py-1',
        className
      )}
      onClick={() => setIsEditing(true)}
    >
      <span className="flex-1 text-sm">{value}</span>
      <Pencil className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100" />
      {onRemove && (
        <Button
          variant="ghost"
          size="icon"
          className="h-5 w-5 opacity-0 group-hover:opacity-100"
          onClick={(e) => {
            e.stopPropagation();
            handleRemove();
          }}
        >
          <X className="h-3 w-3 text-destructive" />
        </Button>
      )}
    </div>
  );
}

