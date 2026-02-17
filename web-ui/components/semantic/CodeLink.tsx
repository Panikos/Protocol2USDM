'use client';

import { ExternalLink } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const EVS_BASE_URL = 'https://evsexplore.semantics.cancer.gov/evsexplore/concept/ncit';

// ---- Code-system detection & URL builders ----

interface CodeSystemInfo {
  label: string;
  url: string | null;
  color: string; // tailwind text-color class for the system label
}

const MESH_BROWSER = 'https://meshb.nlm.nih.gov/record/ui?ui=';
const SNOMED_BROWSER = 'https://browser.ihtsdotools.org/?perspective=full&conceptId1=';
const LOINC_BROWSER = 'https://loinc.org/';

function detectCodeSystem(
  code: string,
  codeSystem?: string | null,
): CodeSystemInfo | null {
  const c = code.trim();
  const cs = (codeSystem || '').toLowerCase();

  // NCI C-code
  if (/^C\d{3,}$/i.test(c)) {
    return {
      label: 'NCI',
      url: `${EVS_BASE_URL}/${c}`,
      color: 'text-blue-600',
    };
  }

  // MeSH descriptor
  if (cs.includes('mesh') || /^D\d{5,}$/.test(c)) {
    return {
      label: 'MeSH',
      url: `${MESH_BROWSER}${c}`,
      color: 'text-emerald-600',
    };
  }

  // SNOMED CT
  if (cs.includes('snomed') || /^\d{6,18}$/.test(c) && cs.includes('snomed')) {
    return {
      label: 'SNOMED',
      url: `${SNOMED_BROWSER}${c}`,
      color: 'text-violet-600',
    };
  }

  // LOINC
  if (cs.includes('loinc') || /^\d{1,5}-\d$/.test(c)) {
    return {
      label: 'LOINC',
      url: `${LOINC_BROWSER}${c}`,
      color: 'text-amber-600',
    };
  }

  // CPT (numeric, typically 5 digits, codeSystem says CPT)
  if (cs.includes('cpt') || cs.includes('current procedural')) {
    return { label: 'CPT', url: null, color: 'text-orange-600' };
  }

  // ICD-10
  if (cs.includes('icd') || /^[A-Z]\d{2}(\.\d{1,4})?$/.test(c)) {
    return { label: 'ICD', url: null, color: 'text-rose-600' };
  }

  return null;
}

/**
 * Build the NCI EVS Explore URL for a given C-code.
 * Returns null if the code doesn't look like a valid NCI C-code.
 */
export function evsUrl(code: string | undefined | null): string | null {
  if (!code) return null;
  const trimmed = String(code).trim();
  if (/^C\d{3,}$/i.test(trimmed)) {
    return `${EVS_BASE_URL}/${trimmed}`;
  }
  return null;
}

export interface CodeLinkProps {
  /** The code string, e.g. "C85826" or "36415" */
  code: string | undefined | null;
  /** Optional decode text to show alongside the code */
  decode?: string;
  /** Code system identifier (e.g. "CPT", "http://www.nlm.nih.gov/mesh") */
  codeSystem?: string | null;
  /** If true, show only the code badge (no decode text) */
  codeOnly?: boolean;
  /** Badge variant */
  variant?: 'outline' | 'default' | 'secondary' | 'destructive';
  /** Additional class name for the badge */
  className?: string;
}

/**
 * Renders a coded value as a Badge.
 * - NCI C-codes → clickable link to EVS Explore
 * - MeSH descriptors → clickable link to MeSH Browser
 * - Other recognized systems (CPT, LOINC, SNOMED, ICD) → labeled badge
 * - Unknown → plain badge
 */
export function CodeLink({
  code,
  decode,
  codeSystem,
  codeOnly = false,
  variant = 'outline',
  className,
}: CodeLinkProps) {
  if (!code && !decode) return null;

  const csInfo = code ? detectCodeSystem(code, codeSystem) : null;
  const displayText = codeOnly ? code : (decode || code);

  // Linkable code system (NCI, MeSH, SNOMED, LOINC)
  if (csInfo?.url) {
    return (
      <a
        href={csInfo.url}
        target="_blank"
        rel="noopener noreferrer"
        title={`View ${code} on ${csInfo.label}${decode ? ` — ${decode}` : ''}`}
        onClick={(e) => e.stopPropagation()}
        className="inline-flex"
      >
        <Badge
          variant={variant}
          className={cn(
            'text-xs cursor-pointer hover:bg-primary/10 hover:border-primary/50 transition-colors gap-1',
            className
          )}
        >
          <span className={cn('font-semibold', csInfo.color)}>{csInfo.label}</span>
          {displayText}
          <ExternalLink className="h-2.5 w-2.5 opacity-50" />
        </Badge>
      </a>
    );
  }

  // Non-linkable but recognized code system (CPT, ICD)
  if (csInfo) {
    return (
      <Badge variant={variant} className={cn('text-xs gap-1', className)}>
        <span className={cn('font-semibold', csInfo.color)}>{csInfo.label}</span>
        {displayText}
      </Badge>
    );
  }

  // Unknown / no code system — plain badge (backward-compatible)
  return (
    <Badge variant={variant} className={cn('text-xs', className)}>
      {displayText}
    </Badge>
  );
}

export default CodeLink;
