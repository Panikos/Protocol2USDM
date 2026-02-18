'use client';

import { useState, useEffect, useCallback } from 'react';

/**
 * Drug label information from OpenFDA.
 * Matches the shape returned by /api/openfda/label/[drugName].
 */
export interface DrugInfo {
  brand_name: string;
  generic_name: string;
  manufacturer: string;
  product_type: string;
  route: string[];
  substance_name: string[];
  pharmacologic_class: string[];
  mechanism_of_action: string[];
  indications: string;
  dosage_and_administration: string;
  boxed_warning: string;
  warnings: string;
  contraindications: string;
  adverse_reactions: string;
  clinical_pharmacology: string;
  drug_interactions: string;
}

interface UseDrugInfoResult {
  data: DrugInfo | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

// In-memory cache shared across all hook instances (SPA lifetime)
const cache = new Map<string, DrugInfo>();
const inflight = new Map<string, Promise<DrugInfo | null>>();

/**
 * React hook to fetch FDA drug label information via the local
 * /api/openfda/label/[drugName] proxy route.
 *
 * Features:
 * - SPA-level in-memory cache (avoids redundant fetches)
 * - De-duplicates concurrent requests for the same drug
 * - Gracefully returns null for investigational compounds not in FDA DB
 */
export function useDrugInfo(drugName: string | undefined): UseDrugInfoResult {
  const key = (drugName ?? '').trim().toLowerCase();
  const [data, setData] = useState<DrugInfo | null>(key ? cache.get(key) ?? null : null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchInfo = useCallback(async () => {
    if (!key) return;

    // Cache hit
    if (cache.has(key)) {
      setData(cache.get(key)!);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // De-dup: if another instance is already fetching, await it
      let promise = inflight.get(key);
      if (!promise) {
        promise = (async () => {
          const res = await fetch(`/api/openfda/label/${encodeURIComponent(key)}`);
          if (!res.ok) return null;
          return (await res.json()) as DrugInfo;
        })();
        inflight.set(key, promise);
      }

      const result = await promise;
      inflight.delete(key);

      if (result) {
        cache.set(key, result);
        setData(result);
      } else {
        setData(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch drug info');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [key]);

  useEffect(() => {
    fetchInfo();
  }, [fetchInfo]);

  return { data, loading, error, refetch: fetchInfo };
}
