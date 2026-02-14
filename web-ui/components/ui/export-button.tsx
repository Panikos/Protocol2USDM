'use client';

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Download, FileJson, FileSpreadsheet, FileText, ChevronDown } from 'lucide-react';
import { Button } from './button';
import { cn } from '@/lib/utils';

export type ExportFormat = 'csv' | 'json' | 'pdf';

interface ExportButtonProps {
  onExport: (format: ExportFormat) => void;
  formats?: ExportFormat[];
  disabled?: boolean;
  className?: string;
}

const formatIcons: Record<ExportFormat, React.ReactNode> = {
  csv: <FileSpreadsheet className="h-4 w-4" />,
  json: <FileJson className="h-4 w-4" />,
  pdf: <FileText className="h-4 w-4" />,
};

const formatLabels: Record<ExportFormat, string> = {
  csv: 'Export CSV',
  json: 'Export JSON',
  pdf: 'Export PDF',
};

export function ExportButton({
  onExport,
  formats = ['csv', 'json', 'pdf'],
  disabled = false,
  className,
}: ExportButtonProps) {
  if (formats.length === 1) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => onExport(formats[0])}
        disabled={disabled}
        className={className}
      >
        {formatIcons[formats[0]]}
        <span className="ml-2">{formatLabels[formats[0]]}</span>
      </Button>
    );
  }

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <Button
          variant="outline"
          size="sm"
          disabled={disabled}
          className={className}
        >
          <Download className="h-4 w-4" />
          <span className="ml-2">Export</span>
          <ChevronDown className="h-3 w-3 ml-1" />
        </Button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={4}
          className="z-50 min-w-[140px] bg-popover border border-border rounded-lg shadow-lg py-1 animate-in fade-in-0 zoom-in-95"
        >
          {formats.map((format) => (
            <DropdownMenu.Item
              key={format}
              onSelect={() => onExport(format)}
              className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-accent focus:bg-accent focus:text-foreground cursor-pointer outline-none transition-colors"
            >
              {formatIcons[format]}
              <span>{formatLabels[format]}</span>
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

export default ExportButton;
