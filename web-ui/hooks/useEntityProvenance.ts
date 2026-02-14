import { createContext, useContext } from 'react';
import type { EntityProvenanceData, EntityProvenanceRecord } from '@/lib/provenance/types';

/**
 * Context for entity-level provenance data.
 * Wrap a subtree with EntityProvenanceProvider to make lookups available.
 */
export const EntityProvenanceContext = createContext<EntityProvenanceData | null>(null);

/**
 * Look up provenance for a specific entity ID.
 * Returns null if no provenance data is available or entity not found.
 */
export function useEntityProvenance(entityId: string | undefined): EntityProvenanceRecord | null {
  const data = useContext(EntityProvenanceContext);
  if (!data || !entityId) return null;
  return data.entities[entityId] ?? null;
}

/**
 * Get the full entity provenance data object.
 */
export function useEntityProvenanceData(): EntityProvenanceData | null {
  return useContext(EntityProvenanceContext);
}
