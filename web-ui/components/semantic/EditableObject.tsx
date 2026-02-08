'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Pencil, Save, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EditableField } from './EditableField';
import { useSemanticStore } from '@/stores/semanticStore';
import { useEditModeStore } from '@/stores/editModeStore';
import { cn } from '@/lib/utils';

/**
 * Field descriptor — defines how a single property of an entity should render.
 */
export interface FieldDescriptor {
  /** Property key on the entity object */
  key: string;
  /** Display label */
  label: string;
  /** Field type for EditableField */
  type?: 'text' | 'textarea' | 'number' | 'boolean';
  /** Placeholder text */
  placeholder?: string;
  /** Whether this field is editable (default true) */
  editable?: boolean;
  /** If true, field is hidden when value is empty and not in edit mode */
  hideWhenEmpty?: boolean;
  /** Custom render function — overrides default EditableField rendering */
  render?: (value: unknown, path: string) => React.ReactNode;
}

export interface EditableObjectProps {
  /** JSON Patch path prefix, e.g. "/study/versions/0/studyDesigns/0/arms/0" */
  basePath: string;
  /** The entity data object */
  data: Record<string, unknown>;
  /** Field descriptors defining which fields to show and how */
  fields: FieldDescriptor[];
  /** Card title */
  title?: string;
  /** Optional icon element for the card header */
  icon?: React.ReactNode;
  /** Whether the card is collapsible (default false) */
  collapsible?: boolean;
  /** Whether to start collapsed (default false) */
  defaultCollapsed?: boolean;
  /** Additional class name */
  className?: string;
  /** If true, renders fields inline without a Card wrapper */
  inline?: boolean;
  /** Number of columns for the field grid (default 2) */
  columns?: 1 | 2 | 3 | 4;
}

export function EditableObject({
  basePath,
  data,
  fields,
  title,
  icon,
  collapsible = false,
  defaultCollapsed = false,
  className,
  inline = false,
  columns = 2,
}: EditableObjectProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const isEditMode = useEditModeStore((s) => s.isEditMode);

  const gridClass = {
    1: 'grid-cols-1',
    2: 'grid-cols-1 md:grid-cols-2',
    3: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-4',
  }[columns];

  const renderFields = () => {
    const visibleFields = fields.filter((f) => {
      if (f.hideWhenEmpty && !isEditMode) {
        const val = data[f.key];
        return val !== undefined && val !== null && val !== '';
      }
      return true;
    });

    return (
      <div className={cn('grid gap-3', gridClass)}>
        {visibleFields.map((field) => {
          const fieldPath = `${basePath}/${field.key}`;
          const value = data[field.key];

          if (field.render) {
            return (
              <div key={field.key}>
                {field.render(value, fieldPath)}
              </div>
            );
          }

          // Convert value to a type EditableField accepts
          const scalarValue =
            value === undefined || value === null
              ? null
              : typeof value === 'object'
                ? JSON.stringify(value)
                : (value as string | number | boolean);

          return (
            <EditableField
              key={field.key}
              path={fieldPath}
              value={scalarValue}
              label={field.label}
              type={field.type ?? 'text'}
              placeholder={field.placeholder ?? 'Not specified'}
              editable={field.editable ?? true}
            />
          );
        })}
      </div>
    );
  };

  // Inline mode — no card wrapper
  if (inline) {
    return <div className={className}>{renderFields()}</div>;
  }

  // Card mode
  return (
    <Card className={className}>
      {title && (
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
          </CardTitle>
        </CardHeader>
      )}
      {!collapsed && (
        <CardContent className={title ? '' : 'pt-6'}>
          {renderFields()}
        </CardContent>
      )}
    </Card>
  );
}

export default EditableObject;
