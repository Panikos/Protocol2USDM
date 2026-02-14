'use client';

import { useState, useEffect, useCallback } from 'react';

const STORAGE_KEY = 'protocol2usdm_user_identity';
const DEFAULT_USER = 'anonymous';

/**
 * Hook for managing user identity via localStorage.
 * 
 * On first launch, returns 'anonymous'. The UI should prompt the user
 * to enter their name. All audit records are tagged with this identity.
 */
export function useUserIdentity() {
  const [username, setUsernameState] = useState<string>(DEFAULT_USER);
  const [isLoaded, setIsLoaded] = useState(false);

  // Load from localStorage on mount (client-side only)
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        setUsernameState(stored);
      }
    } catch {
      // localStorage unavailable (SSR or privacy mode)
    }
    setIsLoaded(true);
  }, []);

  const setUsername = useCallback((name: string) => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setUsernameState(trimmed);
    try {
      localStorage.setItem(STORAGE_KEY, trimmed);
    } catch {
      // localStorage unavailable
    }
  }, []);

  const isAnonymous = username === DEFAULT_USER;
  const needsIdentity = isLoaded && isAnonymous;

  return { username, setUsername, isLoaded, isAnonymous, needsIdentity };
}

/**
 * Get the current username synchronously (for non-React contexts like stores).
 * Falls back to 'anonymous' if localStorage is unavailable.
 */
export function getCurrentUsername(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) || DEFAULT_USER;
  } catch {
    return DEFAULT_USER;
  }
}
