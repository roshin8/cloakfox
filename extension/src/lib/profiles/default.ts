import type { AssignedProfile } from '@/types';

/** Default profile used as fallback when no container context is available */
export const DEFAULT_PROFILE: AssignedProfile = {
  userAgent: {
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/146.0',
    platform: 'MacIntel',
    oscpu: 'Intel Mac OS X 10.15',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/146.0',
  },
  screen: {
    width: 1920,
    height: 1080,
    availWidth: 1920,
    availHeight: 1055,
    colorDepth: 24,
    pixelDepth: 24,
  },
  hardwareConcurrency: 8,
  deviceMemory: 8,
  maxTouchPoints: 0,
  language: 'en-US',
  languages: ['en-US', 'en'],
  timezone: 'America/New_York',
  webgl: {
    vendor: 'Google Inc. (Apple)',
    renderer: 'ANGLE (Apple, ANGLE Metal Renderer: Apple M1, Unspecified Version)',
  },
};
