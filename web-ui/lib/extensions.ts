/**
 * Extension Attribute Helpers
 *
 * Centralizes reading/writing USDM ExtensionAttributes so that consumers
 * don't need inline type casts or knowledge of the value-field contract.
 *
 * The USDM spec supports multiple value fields on ExtensionAttribute:
 *   valueString, valueBoolean, valueInteger, valueId, valueQuantity,
 *   valueRange, valueCode, valueAliasCode, valueExtensionClass
 *
 * During the current transition period both the legacy `valueString`-only
 * pattern and the full multi-field pattern are supported transparently.
 */

import type { ExtensionAttribute } from '@/lib/types';

// ---------------------------------------------------------------------------
// Read helpers
// ---------------------------------------------------------------------------

/**
 * Find the first extension attribute matching a URL suffix.
 * Matches both full URL and bare suffix (e.g. 'x-userEdited').
 */
export function findExt(
  exts: ExtensionAttribute[] | unknown[] | undefined | null,
  urlSuffix: string,
): ExtensionAttribute | undefined {
  if (!Array.isArray(exts)) return undefined;
  return (exts as ExtensionAttribute[]).find(
    (e) => e?.url?.endsWith(urlSuffix) || e?.url?.includes(urlSuffix),
  );
}

/**
 * Get the string value of an extension by URL suffix.
 * Returns undefined if extension not found or has no string value.
 */
export function getExtString(
  exts: ExtensionAttribute[] | unknown[] | undefined | null,
  urlSuffix: string,
): string | undefined {
  const ext = findExt(exts, urlSuffix);
  if (!ext) return undefined;
  // Prefer valueString; fall back to string coercion of other value fields
  if (ext.valueString != null) return ext.valueString;
  if (ext.valueBoolean != null) return String(ext.valueBoolean);
  if (ext.valueInteger != null) return String(ext.valueInteger);
  if (ext.valueId != null) return ext.valueId;
  return undefined;
}

/**
 * Get the boolean value of an extension by URL suffix.
 */
export function getExtBoolean(
  exts: ExtensionAttribute[] | unknown[] | undefined | null,
  urlSuffix: string,
): boolean | undefined {
  const ext = findExt(exts, urlSuffix);
  if (!ext) return undefined;
  if (ext.valueBoolean != null) return ext.valueBoolean;
  if (ext.valueString != null) return ext.valueString === 'true';
  return undefined;
}

/**
 * Check whether an extension with the given URL suffix exists.
 */
export function hasExt(
  exts: ExtensionAttribute[] | unknown[] | undefined | null,
  urlSuffix: string,
): boolean {
  return findExt(exts, urlSuffix) !== undefined;
}

/**
 * Get all extension attributes matching a URL suffix.
 */
export function findAllExts(
  exts: ExtensionAttribute[] | unknown[] | undefined | null,
  urlSuffix: string,
): ExtensionAttribute[] {
  if (!Array.isArray(exts)) return [];
  return (exts as ExtensionAttribute[]).filter(
    (e) => e?.url?.endsWith(urlSuffix) || e?.url?.includes(urlSuffix),
  );
}

// ---------------------------------------------------------------------------
// Write helpers
// ---------------------------------------------------------------------------

/**
 * Build a new ExtensionAttribute with a string value.
 */
export function makeStringExt(url: string, value: string): ExtensionAttribute {
  return {
    id: crypto.randomUUID(),
    url,
    valueString: value,
    instanceType: 'ExtensionAttribute',
  };
}

/**
 * Build a new ExtensionAttribute with a boolean value.
 * Writes both valueBoolean (spec) and valueString (legacy compat).
 */
export function makeBooleanExt(url: string, value: boolean): ExtensionAttribute {
  return {
    id: crypto.randomUUID(),
    url,
    valueBoolean: value,
    valueString: String(value), // legacy compat — remove after full migration
    instanceType: 'ExtensionAttribute',
  };
}

// ---------------------------------------------------------------------------
// Constants — canonical extension URLs
// ---------------------------------------------------------------------------

export const EXT_URLS = {
  CELL_MARK: 'https://usdm.cdisc.org/extensions/x-soaCellMark',
  USER_EDITED: 'https://usdm.cdisc.org/extensions/x-userEdited',
  FOOTNOTE_REFS: 'https://usdm.cdisc.org/extensions/x-soaFootnoteRefs',
  ACTIVITY_SOURCE: 'https://usdm.cdisc.org/extensions/x-activitySource',
  ACTIVITY_GROUP: 'https://usdm.cdisc.org/extensions/x-activityGroup',
  INSTANCE_SOURCE: 'https://usdm.cdisc.org/extensions/x-instanceSource',
  EPOCH_CATEGORY: 'https://usdm.cdisc.org/extensions/x-epochCategory',
} as const;
