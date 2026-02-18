import { NextRequest, NextResponse } from 'next/server';

const OPENFDA_LABEL_URL = 'https://api.fda.gov/drug/label.json';

/**
 * OpenFDA Drug Label API proxy.
 * Public API — no authentication required.
 * Searches by generic name first, then brand name as fallback.
 *
 * Based on the pattern from USDM2Synthetic sister project.
 * Docs: https://open.fda.gov/apis/drug/label/
 */
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ drugName: string }> }
) {
  try {
    const { drugName } = await params;
    const name = decodeURIComponent(drugName).trim();

    if (!name) {
      return NextResponse.json({ error: 'Drug name is required' }, { status: 400 });
    }

    // Search by generic name first
    let data = await searchLabel(`openfda.generic_name:"${name}"`);

    // Fallback: brand name
    if (!data) {
      data = await searchLabel(`openfda.brand_name:"${name}"`);
    }

    // Fallback: free-text substance name (handles investigational compounds)
    if (!data) {
      data = await searchLabel(`openfda.substance_name:"${name}"`);
    }

    if (!data) {
      return NextResponse.json({ error: `No FDA label found for "${name}"` }, { status: 404 });
    }

    const openfda = (data.openfda ?? {}) as Record<string, unknown>;

    const result = {
      brand_name: first(openfda['brand_name']),
      generic_name: first(openfda['generic_name']),
      manufacturer: first(openfda['manufacturer_name']),
      product_type: first(openfda['product_type']),
      route: (openfda['route'] as string[]) ?? [],
      substance_name: (openfda['substance_name'] as string[]) ?? [],
      pharmacologic_class: (openfda['pharm_class_epc'] as string[]) ?? [],
      mechanism_of_action: (openfda['pharm_class_moa'] as string[]) ?? [],
      indications: truncate(extractText(data.indications_and_usage), 800),
      dosage_and_administration: truncate(extractText(data.dosage_and_administration), 600),
      boxed_warning: truncate(extractText(data.boxed_warning), 500),
      warnings: truncate(extractText(data.warnings), 500),
      contraindications: truncate(extractText(data.contraindications), 500),
      adverse_reactions: truncate(extractText(data.adverse_reactions), 600),
      clinical_pharmacology: truncate(extractText(data.clinical_pharmacology), 600),
      drug_interactions: truncate(extractText(data.drug_interactions), 500),
    };

    return NextResponse.json(result, {
      headers: { 'Cache-Control': 'public, max-age=86400, s-maxage=86400' },
    });
  } catch (error) {
    console.error('OpenFDA label API error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch label' },
      { status: 500 }
    );
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function searchLabel(search: string): Promise<Record<string, unknown> | null> {
  try {
    const url = `${OPENFDA_LABEL_URL}?search=${encodeURIComponent(search)}&limit=1`;
    const res = await fetch(url, {
      headers: { Accept: 'application/json' },
      next: { revalidate: 86400 }, // cache 24h
    });
    if (!res.ok) return null;
    const json = await res.json();
    const results = json?.results;
    return Array.isArray(results) && results.length > 0 ? results[0] : null;
  } catch {
    return null;
  }
}

function first(arr: unknown): string {
  if (Array.isArray(arr) && arr.length > 0) return String(arr[0]);
  return '';
}

function extractText(field: unknown): string {
  if (!field) return '';
  if (Array.isArray(field)) return field.join(' ');
  return String(field);
}

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + '…';
}
