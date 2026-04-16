import { useState, useEffect, useCallback } from 'react';
import browser from 'webextension-polyfill';
import type { ContainerIdentity } from '@/types';
import { MSG_GET_ALL_CONTAINERS, MSG_GET_CONTAINER_INFO } from '@/constants';
import { popupLogger } from '@/lib/logger';

/**
 * Container info for the current tab
 */
interface CurrentContainerInfo {
  containerId: string;
  containerName: string;
  containerColor: string;
  containerIcon: string;
}

/**
 * Return type for useContainers hook
 */
interface UseContainersReturn {
  /** All available containers */
  containers: ContainerIdentity[];
  /** Current tab's container info */
  currentContainer: CurrentContainerInfo | null;
  /** Loading state */
  loading: boolean;
  /** Error message if any */
  error: string | null;
  /** Refresh containers list */
  refresh: () => Promise<void>;
}

/**
 * Hook for managing Firefox containers
 *
 * Provides access to all containers and the current tab's container info.
 *
 * @example
 * ```tsx
 * const { containers, currentContainer, loading } = useContainers();
 * ```
 */
export function useContainers(): UseContainersReturn {
  const [containers, setContainers] = useState<ContainerIdentity[]>([]);
  const [currentContainer, setCurrentContainer] = useState<CurrentContainerInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchContainers = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // Get all containers
      const allContainers = await browser.runtime.sendMessage({
        type: MSG_GET_ALL_CONTAINERS,
      }) as ContainerIdentity[];
      setContainers(allContainers);

      // Get current tab's container
      const containerInfo = await browser.runtime.sendMessage({
        type: MSG_GET_CONTAINER_INFO,
      }) as CurrentContainerInfo;
      setCurrentContainer(containerInfo);

      popupLogger.debug('Containers loaded:', { count: allContainers.length });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load containers';
      setError(message);
      popupLogger.error('Failed to load containers:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchContainers();
  }, [fetchContainers]);

  return {
    containers,
    currentContainer,
    loading,
    error,
    refresh: fetchContainers,
  };
}

export default useContainers;
