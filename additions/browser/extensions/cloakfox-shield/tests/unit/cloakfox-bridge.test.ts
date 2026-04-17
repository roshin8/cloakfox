// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { configureCloakfoxSpoofing } from '../../src/inject/cloakfox-bridge';
import type { AssignedProfile, SpooferSettings } from '../../src/types';

const mockProfile: AssignedProfile = {
  userAgent: {
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/131.0',
    platform: 'Win32',
    oscpu: 'Windows NT 10.0; Win64; x64',
    appVersion: '5.0 (Windows)',
  },
  screen: {
    width: 1920,
    height: 1080,
    availWidth: 1920,
    availHeight: 1040,
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
    vendor: 'Google Inc. (NVIDIA)',
    renderer: 'ANGLE (NVIDIA, GeForce GTX 1060)',
  },
};

const allEnabledSettings: SpooferSettings = {
  graphics: { canvas: 'noise', webgl: 'noise' },
  audio: { context: 'noise' },
  navigator: { userAgent: 'spoof', platform: 'spoof', hardwareConcurrency: 'spoof' },
  hardware: { screen: 'spoof' },
  fonts: { enumeration: 'filter', metrics: 'noise' },
  network: { webrtc: 'spoof' },
  timing: { timezone: 'spoof' },
};

function setupWindowMocks(): Record<string, ReturnType<typeof vi.fn>> {
  const mocks: Record<string, ReturnType<typeof vi.fn>> = {};
  const methods = [
    'setCanvasSeed', 'setAudioFingerprintSeed', 'setNavigatorPlatform',
    'setNavigatorUserAgent', 'setNavigatorOscpu', 'setNavigatorHardwareConcurrency',
    'setScreenDimensions', 'setScreenColorDepth', 'setFontList',
    'setFontSpacingSeed', 'setWebGLVendor', 'setWebGLRenderer',
    'setWebRTCIPv4', 'setWebRTCIPv6', 'setTimezone', 'setSpeechVoices',
  ];
  for (const method of methods) {
    mocks[method] = vi.fn();
    (globalThis as Record<string, unknown>)[method] = mocks[method];
  }
  return mocks;
}

function clearWindowMocks(): void {
  const methods = [
    'setCanvasSeed', 'setAudioFingerprintSeed', 'setNavigatorPlatform',
    'setNavigatorUserAgent', 'setNavigatorOscpu', 'setNavigatorHardwareConcurrency',
    'setScreenDimensions', 'setScreenColorDepth', 'setFontList',
    'setFontSpacingSeed', 'setWebGLVendor', 'setWebGLRenderer',
    'setWebRTCIPv4', 'setWebRTCIPv6', 'setTimezone', 'setSpeechVoices',
  ];
  for (const method of methods) {
    delete (globalThis as Record<string, unknown>)[method];
  }
}

describe('configureCloakfoxSpoofing', () => {
  beforeEach(() => {
    clearWindowMocks();
  });

  it('calls all window.setXxx methods when all settings enabled', async () => {
    const mocks = setupWindowMocks();
    await configureCloakfoxSpoofing('seed-123', 'example.com', mockProfile, allEnabledSettings);

    expect(mocks['setCanvasSeed']).toHaveBeenCalledOnce();
    expect(mocks['setAudioFingerprintSeed']).toHaveBeenCalledOnce();
    expect(mocks['setNavigatorUserAgent']).toHaveBeenCalledWith(mockProfile.userAgent.userAgent);
    expect(mocks['setNavigatorPlatform']).toHaveBeenCalledWith(mockProfile.userAgent.platform);
    expect(mocks['setNavigatorOscpu']).toHaveBeenCalledWith(mockProfile.userAgent.oscpu);
    expect(mocks['setScreenDimensions']).toHaveBeenCalledWith(mockProfile.screen.width, mockProfile.screen.height);
    expect(mocks['setWebGLVendor']).toHaveBeenCalledWith(mockProfile.webgl.vendor);
    expect(mocks['setTimezone']).toHaveBeenCalledWith(mockProfile.timezone);
  });

  it('same container + same domain = same seeds', async () => {
    const mocks1 = setupWindowMocks();
    await configureCloakfoxSpoofing('seed-123', 'example.com', mockProfile, allEnabledSettings);
    const canvasSeed1 = mocks1['setCanvasSeed']!.mock.calls[0]![0];
    const audioSeed1 = mocks1['setAudioFingerprintSeed']!.mock.calls[0]![0];

    clearWindowMocks();
    const mocks2 = setupWindowMocks();
    await configureCloakfoxSpoofing('seed-123', 'example.com', mockProfile, allEnabledSettings);
    const canvasSeed2 = mocks2['setCanvasSeed']!.mock.calls[0]![0];
    const audioSeed2 = mocks2['setAudioFingerprintSeed']!.mock.calls[0]![0];

    expect(canvasSeed1).toBe(canvasSeed2);
    expect(audioSeed1).toBe(audioSeed2);
  });

  it('different domains = different seeds', async () => {
    const mocks1 = setupWindowMocks();
    await configureCloakfoxSpoofing('seed-123', 'example.com', mockProfile, allEnabledSettings);
    const canvasSeed1 = mocks1['setCanvasSeed']!.mock.calls[0]![0];

    clearWindowMocks();
    const mocks2 = setupWindowMocks();
    await configureCloakfoxSpoofing('seed-123', 'other.com', mockProfile, allEnabledSettings);
    const canvasSeed2 = mocks2['setCanvasSeed']!.mock.calls[0]![0];

    expect(canvasSeed1).not.toBe(canvasSeed2);
  });

  it('different containers = different seeds', async () => {
    const mocks1 = setupWindowMocks();
    await configureCloakfoxSpoofing('container-1-seed', 'example.com', mockProfile, allEnabledSettings);
    const canvasSeed1 = mocks1['setCanvasSeed']!.mock.calls[0]![0];

    clearWindowMocks();
    const mocks2 = setupWindowMocks();
    await configureCloakfoxSpoofing('container-2-seed', 'example.com', mockProfile, allEnabledSettings);
    const canvasSeed2 = mocks2['setCanvasSeed']!.mock.calls[0]![0];

    expect(canvasSeed1).not.toBe(canvasSeed2);
  });

  it('does not call setCanvasSeed when canvas is off', async () => {
    const mocks = setupWindowMocks();
    const settings: SpooferSettings = { ...allEnabledSettings, graphics: { canvas: 'off', webgl: 'noise' } };
    await configureCloakfoxSpoofing('seed-123', 'example.com', mockProfile, settings);

    expect(mocks['setCanvasSeed']).not.toHaveBeenCalled();
    expect(mocks['setWebGLVendor']).toHaveBeenCalled();
  });

  it('gracefully handles missing window.setXxx methods', async () => {
    // Don't set up any mocks — methods don't exist on window
    await expect(
      configureCloakfoxSpoofing('seed-123', 'example.com', mockProfile, allEnabledSettings)
    ).resolves.not.toThrow();
  });
});
