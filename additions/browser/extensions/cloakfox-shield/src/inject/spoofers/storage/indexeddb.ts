/**
 * IndexedDB Spoofer
 *
 * IndexedDB database structure and capabilities can be
 * used for fingerprinting.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize IndexedDB spoofing
 */
export function initIndexedDBSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  if (typeof indexedDB === 'undefined') return;

  // Spoof databases() method (reveals all database names)
  if (indexedDB.databases) {
    const originalDatabases = indexedDB.databases.bind(indexedDB);

    indexedDB.databases = async function (): Promise<IDBDatabaseInfo[]> {
      logAccess('indexedDB.databases', { spoofed: mode !== 'block', value: 'spoofed' });

      if (mode === 'block') {
        return []; // Hide all databases
      }

      // Return original but log access
      return originalDatabases();
    };
  }

  // Track open() calls
  const originalOpen = indexedDB.open.bind(indexedDB);

  indexedDB.open = function (
    name: string,
    version?: number
  ): IDBOpenDBRequest {
    logAccess('indexedDB.open', { spoofed: true, value: 'spoofed' });
    return originalOpen(name, version);
  };

  // Track deleteDatabase() calls
  const originalDeleteDatabase = indexedDB.deleteDatabase.bind(indexedDB);

  indexedDB.deleteDatabase = function (name: string): IDBOpenDBRequest {
    logAccess('indexedDB.deleteDatabase', { spoofed: true, value: 'spoofed' });
    return originalDeleteDatabase(name);
  };

}
