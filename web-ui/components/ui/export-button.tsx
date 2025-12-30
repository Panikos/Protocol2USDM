'use client';

import { useState } from 'react';
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
  const [isOpen, setIsOpen] = useState(false);

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
    <div className={cn('relative', className)}>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setIsOpen(!isOpen)}
        disabled={disabled}
      >
        <Download className="h-4 w-4" />
        <span className="ml-2">Export</span>
        <ChevronDown className="h-3 w-3 ml-1" />
      </Button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute right-0 top-full mt-1 z-50 min-w-[140px] bg-background border rounded-lg shadow-lg py-1">
            {formats.map((format) => (
              <button
                key={format}
                onClick={() => {
                  onExport(format);
                  setIsOpen(false);
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              >
                {formatIcons[format]}
                <span>{formatLabels[format]}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default ExportButton;
