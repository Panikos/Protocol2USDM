'use client';

import { useState } from 'react';
import { Plus, Trash2, GripVertical, ChevronDown, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EditableField } from './EditableField';
import { useSemanticStore } from '@/stores/semanticStore';
import { useEditModeStore } from '@/stores/editModeStore';
import { cn } from '@/lib/utils';

/**
 * Describes how to render each item in the list.
 */
export interface ListItemDescriptor {
  /** Property key used as the display label for each item */
  labelKey: string;
  /** Optional secondary info key */
  subtitleKey?: string;
  /** Custom render function for each item */
  render?: (item: unknown, index: number, path: string) => React.ReactNode;
}

export interface EditableListProps {
  /** JSON Patch path to the array, e.g. "/study/versions/0/studyDesigns/0/arms" */
  basePath: string;
  /** The array data */
  items: unknown[];
  /** How to render each item */
  itemDescriptor: ListItemDescriptor;
  /** Card title */
  title?: string;
  /** Optional icon element */
  icon?: React.ReactNode;
  /** Whether the card is collapsible */
  collapsible?: boolean;
  /** Start collapsed */
  defaultCollapsed?: boolean;
  /** Template object used when adding a new item */
  newItemTemplate?: Record<string, unknown>;
  /** Whether reordering is enabled (default false — future feature) */
  reorderable?: boolean;
  /** Max items allowed (undefined = unlimited) */
  maxItems?: number;
  /** Additional class name */
  className?: string;
  /** Label for the add button */
  addLabel?: string;
}

export function EditableList({
  basePath,
  items,
  itemDescriptor,
  title,
  icon,
  collapsible = false,
  defaultCollapsed = false,
  newItemTemplate,
  reorderable = false,
  maxItems,
  className,
  addLabel = 'Add Item',
}: EditableListProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const { addPatchOp, beginGroup, endGroup } = useSemanticStore();
  const isEditMode = useEditModeStore((s) => s.isEditMode);

  const canAdd = isEditMode && newItemTemplate && (maxItems === undefined || items.length < maxItems);

  const handleAdd = () => {
    if (!newItemTemplate) return;
    // Generate a unique ID for the new item
    const newItem = {
      ...newItemTemplate,
      id: `new_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    };
    addPatchOp({ op: 'add', path: `${basePath}/-`, value: newItem });
  };

  const handleRemove = (index: number) => {
    addPatchOp({ op: 'remove', path: `${basePath}/${index}` });
  };

  const handleMoveUp = (index: number) => {
    if (index === 0) return;
    beginGroup();
    // Swap by removing and re-inserting
    const item = items[index];
    addPatchOp({ op: 'remove', path: `${basePath}/${index}` });
    addPatchOp({ op: 'add', path: `${basePath}/${index - 1}`, value: item });
    endGroup();
  };

  const handleMoveDown = (index: number) => {
    if (index >= items.length - 1) return;
    beginGroup();
    const item = items[index];
    addPatchOp({ op: 'remove', path: `${basePath}/${index}` });
    addPatchOp({ op: 'add', path: `${basePath}/${index + 1}`, value: item });
    endGroup();
  };

  const renderItem = (item: unknown, index: number) => {
    const itemPath = `${basePath}/${index}`;
    const itemObj = (item && typeof item === 'object' ? item : {}) as Record<string, unknown>;

    if (itemDescriptor.render) {
      return itemDescriptor.render(item, index, itemPath);
    }

    const label = String(itemObj[itemDescriptor.labelKey] ?? `Item ${index + 1}`);
    const subtitle = itemDescriptor.subtitleKey
      ? String(itemObj[itemDescriptor.subtitleKey] ?? '')
      : undefined;

    return (
      <div className="flex-1 min-w-0">
        <EditableField
          path={`${itemPath}/${itemDescriptor.labelKey}`}
          value={label}
          placeholder={`Item ${index + 1}`}
        />
        {subtitle && (
          <p className="text-xs text-muted-foreground mt-0.5 truncate">{subtitle}</p>
        )}
      </div>
    );
  };

  const content = (
    <>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground italic py-2">
          No items
        </p>
      ) : (
        <div className="space-y-1">
          {items.map((item, index) => (
            <div
              key={(item as Record<string, unknown>)?.id as string || index}
              className={cn(
                'flex items-center gap-2 p-2 rounded-md',
                'border border-transparent',
                isEditMode && 'hover:border-border hover:bg-muted/30',
                'group'
              )}
            >
              {/* Reorder grip */}
              {reorderable && isEditMode && (
                <div className="flex flex-col gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-5 w-5"
                    onClick={() => handleMoveUp(index)}
                    disabled={index === 0}
                  >
                    <ChevronDown className="h-3 w-3 rotate-180" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-5 w-5"
                    onClick={() => handleMoveDown(index)}
                    disabled={index >= items.length - 1}
                  >
                    <ChevronDown className="h-3 w-3" />
                  </Button>
                </div>
              )}

              {/* Index badge */}
              <Badge variant="outline" className="h-6 min-w-[1.75rem] justify-center text-xs shrink-0">
                {index + 1}
              </Badge>

              {/* Item content */}
              {renderItem(item, index)}

              {/* Remove button */}
              {isEditMode && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-destructive hover:text-destructive"
                  onClick={() => handleRemove(index)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Add button */}
      {canAdd && (
        <Button
          variant="outline"
          size="sm"
          onClick={handleAdd}
          className="mt-3 w-full border-dashed"
        >
          <Plus className="h-4 w-4 mr-2" />
          {addLabel}
        </Button>
      )}
    </>
  );

  // No card wrapper if no title
  if (!title) {
    return <div className={className}>{content}</div>;
  }

  return (
    <Card className={className}>
      <CardHeader
        className={cn(
          'pb-3',
          collapsible && 'cursor-pointer select-none'
        )}
        onClick={collapsible ? () => setCollapsed(!collapsed) : undefined}
      >
        <CardTitle className="flex items-center gap-2 text-base">
          {collapsible && (
            collapsed ? (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            )
          )}
          {icon}
          {title}
          <Badge variant="secondary" className="ml-auto">{items.length}</Badge>
        </CardTitle>
      </CardHeader>
      {!collapsed && (
        <CardContent>{content}</CardContent>
      )}
    </Card>
  );
}

export default EditableList;
