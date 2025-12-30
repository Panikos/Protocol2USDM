/**
 * Export utilities for generating PDF and Excel files from protocol data
 */

export interface ExportOptions {
  filename: string;
  title?: string;
  subtitle?: string;
}

/**
 * Export data to CSV format and trigger download
 */
export function exportToCSV(
  data: Record<string, unknown>[],
  options: ExportOptions
): void {
  if (!data || data.length === 0) {
    console.warn('No data to export');
    return;
  }

  // Get all unique keys from the data
  const headers = [...new Set(data.flatMap(row => Object.keys(row)))];

  // Build CSV content
  const csvRows: string[] = [];

  // Add header row
  csvRows.push(headers.map(h => `"${h}"`).join(','));

  // Add data rows
  for (const row of data) {
    const values = headers.map(header => {
      const value = row[header];
      if (value === null || value === undefined) return '""';
      if (typeof value === 'object') return `"${JSON.stringify(value).replace(/"/g, '""')}"`;
      return `"${String(value).replace(/"/g, '""')}"`;
    });
    csvRows.push(values.join(','));
  }

  const csvContent = csvRows.join('\n');
  downloadFile(csvContent, `${options.filename}.csv`, 'text/csv;charset=utf-8;');
}

/**
 * Export data to JSON format and trigger download
 */
export function exportToJSON(
  data: unknown,
  options: ExportOptions
): void {
  const jsonContent = JSON.stringify(data, null, 2);
  downloadFile(jsonContent, `${options.filename}.json`, 'application/json');
}

/**
 * Export HTML content to a printable format (triggers print dialog for PDF)
 */
export function exportToPDF(
  elementId: string,
  options: ExportOptions
): void {
  const element = document.getElementById(elementId);
  if (!element) {
    console.warn(`Element with id "${elementId}" not found`);
    return;
  }

  // Create a new window for printing
  const printWindow = window.open('', '_blank');
  if (!printWindow) {
    console.warn('Could not open print window');
    return;
  }

  // Build print document
  printWindow.document.write(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>${options.title || options.filename}</title>
      <style>
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          padding: 20px;
          max-width: 1200px;
          margin: 0 auto;
        }
        h1 { font-size: 24px; margin-bottom: 8px; }
        h2 { font-size: 18px; color: #666; margin-bottom: 24px; }
        table { width: 100%; border-collapse: collapse; margin: 16px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #f5f5f5; font-weight: 600; }
        .card { border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin: 16px 0; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
        @media print {
          body { padding: 0; }
          .no-print { display: none !important; }
        }
      </style>
    </head>
    <body>
      ${options.title ? `<h1>${options.title}</h1>` : ''}
      ${options.subtitle ? `<h2>${options.subtitle}</h2>` : ''}
      ${element.innerHTML}
    </body>
    </html>
  `);

  printWindow.document.close();
  printWindow.focus();

  // Wait for content to load then print
  setTimeout(() => {
    printWindow.print();
  }, 250);
}

/**
 * Helper to download a file
 */
function downloadFile(content: string, filename: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);

  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();

  // Cleanup
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Format USDM data for export
 */
export function formatUSDMForExport(usdm: Record<string, unknown>): {
  metadata: Record<string, unknown>;
  eligibility: Record<string, unknown>[];
  objectives: Record<string, unknown>[];
  activities: Record<string, unknown>[];
  encounters: Record<string, unknown>[];
} {
  const study = usdm.study as Record<string, unknown> | undefined;
  const versions = (study?.versions as unknown[]) ?? [];
  const version = versions[0] as Record<string, unknown> | undefined;
  const studyDesigns = (version?.studyDesigns as Record<string, unknown>[]) ?? [];
  const studyDesign = studyDesigns[0] ?? {};

  // Extract metadata
  const metadata = {
    studyTitle: version?.studyTitle ?? '',
    studyAcronym: version?.studyAcronym ?? '',
    studyPhase: version?.studyPhase ?? '',
    protocolVersion: version?.protocolVersion ?? '',
  };

  // Extract eligibility criteria
  const populations = (studyDesign.population as Record<string, unknown>) ?? {};
  const criteria = (populations.criteria as Record<string, unknown>[]) ?? [];
  const eligibility = criteria.map(c => ({
    category: c.category ?? '',
    text: c.text ?? c.description ?? '',
  }));

  // Extract objectives
  const objectivesRaw = (studyDesign.objectives as Record<string, unknown>[]) ?? [];
  const objectives = objectivesRaw.map(o => ({
    level: o.objectiveLevel ?? '',
    text: o.objectiveDescription ?? '',
  }));

  // Extract activities
  const activitiesRaw = (studyDesign.activities as Record<string, unknown>[]) ?? [];
  const activities = activitiesRaw.map(a => ({
    id: a.id ?? '',
    name: a.name ?? a.activityName ?? '',
    description: a.description ?? '',
  }));

  // Extract encounters
  const timelines = (studyDesign.scheduleTimelines as Record<string, unknown>[]) ?? [];
  const encounters: Record<string, unknown>[] = [];
  for (const timeline of timelines) {
    const instances = (timeline.instances as Record<string, unknown>[]) ?? [];
    for (const inst of instances) {
      encounters.push({
        id: inst.id ?? '',
        name: inst.name ?? inst.scheduledInstanceName ?? '',
        type: inst.instanceType ?? '',
      });
    }
  }

  return { metadata, eligibility, objectives, activities, encounters };
}
