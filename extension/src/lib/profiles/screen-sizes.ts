/**
 * Screen Size Profile Database
 *
 * Common screen resolutions organized by device type.
 * Based on StatCounter and similar analytics data.
 */

export interface ScreenProfile {
  id: string;
  name: string;
  width: number;
  height: number;
  availWidth: number;
  availHeight: number;
  colorDepth: number;
  pixelDepth: number;
  devicePixelRatio: number;
  // For touch devices
  maxTouchPoints?: number;
  // Category for filtering
  category: 'desktop' | 'laptop' | 'tablet' | 'mobile';
  // Usage percentage (approximate, for weighted random selection)
  popularity: number;
}

// Desktop monitors (external displays)
const DESKTOP_SCREENS: ScreenProfile[] = [
  {
    id: 'desktop-1920x1080',
    name: 'Full HD (1920x1080)',
    width: 1920,
    height: 1080,
    availWidth: 1920,
    availHeight: 1040, // Taskbar
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 1,
    category: 'desktop',
    popularity: 22,
  },
  {
    id: 'desktop-2560x1440',
    name: 'QHD (2560x1440)',
    width: 2560,
    height: 1440,
    availWidth: 2560,
    availHeight: 1400,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 1,
    category: 'desktop',
    popularity: 8,
  },
  {
    id: 'desktop-3840x2160',
    name: '4K UHD (3840x2160)',
    width: 3840,
    height: 2160,
    availWidth: 3840,
    availHeight: 2120,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 2,
    category: 'desktop',
    popularity: 3,
  },
  {
    id: 'desktop-1920x1200',
    name: 'WUXGA (1920x1200)',
    width: 1920,
    height: 1200,
    availWidth: 1920,
    availHeight: 1160,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 1,
    category: 'desktop',
    popularity: 2,
  },
  {
    id: 'desktop-2560x1080',
    name: 'Ultrawide FHD (2560x1080)',
    width: 2560,
    height: 1080,
    availWidth: 2560,
    availHeight: 1040,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 1,
    category: 'desktop',
    popularity: 2,
  },
  {
    id: 'desktop-3440x1440',
    name: 'Ultrawide QHD (3440x1440)',
    width: 3440,
    height: 1440,
    availWidth: 3440,
    availHeight: 1400,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 1,
    category: 'desktop',
    popularity: 1,
  },
  {
    id: 'desktop-1680x1050',
    name: 'WSXGA+ (1680x1050)',
    width: 1680,
    height: 1050,
    availWidth: 1680,
    availHeight: 1010,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 1,
    category: 'desktop',
    popularity: 2,
  },
  {
    id: 'desktop-1600x900',
    name: 'HD+ (1600x900)',
    width: 1600,
    height: 900,
    availWidth: 1600,
    availHeight: 860,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 1,
    category: 'desktop',
    popularity: 2,
  },
];

// Laptop screens (built-in displays)
const LAPTOP_SCREENS: ScreenProfile[] = [
  {
    id: 'laptop-1366x768',
    name: 'HD (1366x768)',
    width: 1366,
    height: 768,
    availWidth: 1366,
    availHeight: 728,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 1,
    category: 'laptop',
    popularity: 15,
  },
  {
    id: 'laptop-1536x864',
    name: 'HD+ Scaled (1536x864)',
    width: 1536,
    height: 864,
    availWidth: 1536,
    availHeight: 824,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 1.25,
    category: 'laptop',
    popularity: 5,
  },
  {
    id: 'laptop-1920x1080',
    name: 'Full HD Laptop (1920x1080)',
    width: 1920,
    height: 1080,
    availWidth: 1920,
    availHeight: 1040,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 1,
    category: 'laptop',
    popularity: 10,
  },
  {
    id: 'laptop-1440x900',
    name: 'WXGA+ (1440x900)',
    width: 1440,
    height: 900,
    availWidth: 1440,
    availHeight: 860,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 1,
    category: 'laptop',
    popularity: 4,
  },
  {
    id: 'laptop-1280x800',
    name: 'WXGA (1280x800)',
    width: 1280,
    height: 800,
    availWidth: 1280,
    availHeight: 760,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 1,
    category: 'laptop',
    popularity: 2,
  },
  // MacBook screens
  {
    id: 'macbook-pro-13',
    name: 'MacBook Pro 13"',
    width: 1280,
    height: 800,
    availWidth: 1280,
    availHeight: 775,
    colorDepth: 30,
    pixelDepth: 30,
    devicePixelRatio: 2,
    category: 'laptop',
    popularity: 3,
  },
  {
    id: 'macbook-pro-15',
    name: 'MacBook Pro 15"',
    width: 1440,
    height: 900,
    availWidth: 1440,
    availHeight: 875,
    colorDepth: 30,
    pixelDepth: 30,
    devicePixelRatio: 2,
    category: 'laptop',
    popularity: 2,
  },
  {
    id: 'macbook-pro-14',
    name: 'MacBook Pro 14" (M-series)',
    width: 1512,
    height: 982,
    availWidth: 1512,
    availHeight: 957,
    colorDepth: 30,
    pixelDepth: 30,
    devicePixelRatio: 2,
    category: 'laptop',
    popularity: 2,
  },
  {
    id: 'macbook-air-m2',
    name: 'MacBook Air M2/M3',
    width: 1470,
    height: 956,
    availWidth: 1470,
    availHeight: 931,
    colorDepth: 30,
    pixelDepth: 30,
    devicePixelRatio: 2,
    category: 'laptop',
    popularity: 2,
  },
];

// Tablet screens
const TABLET_SCREENS: ScreenProfile[] = [
  {
    id: 'ipad-2048x2732',
    name: 'iPad Pro 12.9"',
    width: 2048,
    height: 2732,
    availWidth: 2048,
    availHeight: 2732,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 2,
    maxTouchPoints: 5,
    category: 'tablet',
    popularity: 2,
  },
  {
    id: 'ipad-1668x2388',
    name: 'iPad Pro 11"',
    width: 1668,
    height: 2388,
    availWidth: 1668,
    availHeight: 2388,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 2,
    maxTouchPoints: 5,
    category: 'tablet',
    popularity: 2,
  },
  {
    id: 'ipad-1620x2160',
    name: 'iPad 10th Gen',
    width: 1620,
    height: 2160,
    availWidth: 1620,
    availHeight: 2160,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 2,
    maxTouchPoints: 5,
    category: 'tablet',
    popularity: 2,
  },
  {
    id: 'android-tablet-1920x1200',
    name: 'Android Tablet 10"',
    width: 1920,
    height: 1200,
    availWidth: 1920,
    availHeight: 1152,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 1.5,
    maxTouchPoints: 5,
    category: 'tablet',
    popularity: 1,
  },
  {
    id: 'android-tablet-2560x1600',
    name: 'Samsung Tab S9',
    width: 2560,
    height: 1600,
    availWidth: 2560,
    availHeight: 1552,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 2,
    maxTouchPoints: 10,
    category: 'tablet',
    popularity: 1,
  },
];

// Mobile phone screens
const MOBILE_SCREENS: ScreenProfile[] = [
  // iPhone screens (sorted by popularity)
  {
    id: 'iphone-393x852',
    name: 'iPhone 16/15/14 Pro',
    width: 393,
    height: 852,
    availWidth: 393,
    availHeight: 852,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 3,
    maxTouchPoints: 5,
    category: 'mobile',
    popularity: 8,
  },
  {
    id: 'iphone-390x844',
    name: 'iPhone 14/13/12',
    width: 390,
    height: 844,
    availWidth: 390,
    availHeight: 844,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 3,
    maxTouchPoints: 5,
    category: 'mobile',
    popularity: 5,
  },
  {
    id: 'iphone-430x932',
    name: 'iPhone 16 Pro Max/15 Pro Max',
    width: 430,
    height: 932,
    availWidth: 430,
    availHeight: 932,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 3,
    maxTouchPoints: 5,
    category: 'mobile',
    popularity: 5,
  },
  {
    id: 'iphone-430x932',
    name: 'iPhone 15 Pro Max',
    width: 430,
    height: 932,
    availWidth: 430,
    availHeight: 932,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 3,
    maxTouchPoints: 5,
    category: 'mobile',
    popularity: 3,
  },
  {
    id: 'iphone-375x812',
    name: 'iPhone X/XS/11 Pro',
    width: 375,
    height: 812,
    availWidth: 375,
    availHeight: 812,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 3,
    maxTouchPoints: 5,
    category: 'mobile',
    popularity: 2,
  },
  {
    id: 'iphone-414x896',
    name: 'iPhone XR/11',
    width: 414,
    height: 896,
    availWidth: 414,
    availHeight: 896,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 2,
    maxTouchPoints: 5,
    category: 'mobile',
    popularity: 2,
  },
  // Android screens
  {
    id: 'android-360x800',
    name: 'Android (360x800)',
    width: 360,
    height: 800,
    availWidth: 360,
    availHeight: 752,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 3,
    maxTouchPoints: 5,
    category: 'mobile',
    popularity: 4,
  },
  {
    id: 'android-412x915',
    name: 'Samsung Galaxy S23',
    width: 412,
    height: 915,
    availWidth: 412,
    availHeight: 867,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 2.625,
    maxTouchPoints: 10,
    category: 'mobile',
    popularity: 3,
  },
  {
    id: 'android-360x780',
    name: 'Pixel 7',
    width: 360,
    height: 780,
    availWidth: 360,
    availHeight: 732,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 2.75,
    maxTouchPoints: 5,
    category: 'mobile',
    popularity: 2,
  },
  {
    id: 'android-384x854',
    name: 'Pixel 8 Pro',
    width: 384,
    height: 854,
    availWidth: 384,
    availHeight: 806,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 2.8125,
    maxTouchPoints: 5,
    category: 'mobile',
    popularity: 2,
  },
  {
    id: 'android-393x873',
    name: 'Samsung Galaxy S24 Ultra',
    width: 393,
    height: 873,
    availWidth: 393,
    availHeight: 825,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 2.75,
    maxTouchPoints: 10,
    category: 'mobile',
    popularity: 3,
  },
  {
    id: 'android-412x892',
    name: 'Samsung Galaxy S24',
    width: 412,
    height: 892,
    availWidth: 412,
    availHeight: 844,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 2.625,
    maxTouchPoints: 10,
    category: 'mobile',
    popularity: 3,
  },
  {
    id: 'android-412x924',
    name: 'Pixel 9',
    width: 412,
    height: 924,
    availWidth: 412,
    availHeight: 876,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 2.625,
    maxTouchPoints: 5,
    category: 'mobile',
    popularity: 2,
  },
  {
    id: 'android-448x998',
    name: 'Pixel 9 Pro XL',
    width: 448,
    height: 998,
    availWidth: 448,
    availHeight: 950,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 2.625,
    maxTouchPoints: 5,
    category: 'mobile',
    popularity: 1,
  },
  {
    id: 'android-360x640',
    name: 'Android Generic (360x640)',
    width: 360,
    height: 640,
    availWidth: 360,
    availHeight: 592,
    colorDepth: 24,
    pixelDepth: 24,
    devicePixelRatio: 2,
    maxTouchPoints: 5,
    category: 'mobile',
    popularity: 3,
  },
];

// All screen profiles combined
export const ALL_SCREENS: ScreenProfile[] = [
  ...DESKTOP_SCREENS,
  ...LAPTOP_SCREENS,
  ...TABLET_SCREENS,
  ...MOBILE_SCREENS,
];

// Profiles by category
// Sort each category by resolution (largest to smallest)
const sortByRes = (a: ScreenProfile, b: ScreenProfile) => (b.width * b.height) - (a.width * a.height);

export const SCREENS_BY_CATEGORY = {
  desktop: [...DESKTOP_SCREENS].sort(sortByRes),
  laptop: [...LAPTOP_SCREENS].sort(sortByRes),
  tablet: [...TABLET_SCREENS].sort(sortByRes),
  mobile: [...MOBILE_SCREENS].sort(sortByRes),
};

// Desktop + Laptop combined (non-touch)
export const NON_TOUCH_SCREENS: ScreenProfile[] = [...DESKTOP_SCREENS, ...LAPTOP_SCREENS];

// Touch screens (tablet + mobile)
export const TOUCH_SCREENS: ScreenProfile[] = [...TABLET_SCREENS, ...MOBILE_SCREENS];

/**
 * Get a screen profile by ID
 */
export function getScreenById(id: string): ScreenProfile | undefined {
  return ALL_SCREENS.find((s) => s.id === id);
}

/**
 * Get a random screen profile using PRNG
 * Uses weighted random selection based on popularity
 */
export function getRandomScreen(
  prng: { nextFloat: () => number; nextInt: (min: number, max: number) => number },
  filter?: { category?: 'desktop' | 'laptop' | 'tablet' | 'mobile'; touch?: boolean }
): ScreenProfile {
  let screens = ALL_SCREENS;

  if (filter?.category && filter.category in SCREENS_BY_CATEGORY) {
    screens = SCREENS_BY_CATEGORY[filter.category];
  } else if (filter?.touch === true) {
    screens = TOUCH_SCREENS;
  } else if (filter?.touch === false) {
    screens = NON_TOUCH_SCREENS;
  }

  // Fallback
  if (screens.length === 0) {
    screens = ALL_SCREENS;
  }

  // Calculate total popularity
  const totalPopularity = screens.reduce((sum, s) => sum + s.popularity, 0);

  // Weighted random selection
  let random = prng.nextFloat() * totalPopularity;

  for (const screen of screens) {
    random -= screen.popularity;
    if (random <= 0) {
      return screen;
    }
  }

  // Fallback to last screen
  return screens[screens.length - 1];
}

/**
 * Get screen dimensions that are consistent with a user agent profile
 */
export function getScreenForUserAgent(
  prng: { nextFloat: () => number; nextInt: (min: number, max: number) => number },
  mobile: boolean,
  platformName: string
): ScreenProfile {
  // Mobile device
  if (mobile) {
    if (platformName === 'iOS') {
      // iOS device - return iPhone or iPad screen
      const iosScreens = MOBILE_SCREENS.filter(
        (s) => s.id.startsWith('iphone') || s.id.startsWith('ipad')
      );
      return getRandomScreen(prng, { touch: true });
    }

    if (platformName === 'Android') {
      const androidScreens = [...MOBILE_SCREENS, ...TABLET_SCREENS].filter((s) =>
        s.id.startsWith('android')
      );
      if (androidScreens.length > 0) {
        const index = prng.nextInt(0, androidScreens.length - 1);
        return androidScreens[index];
      }
    }

    return getRandomScreen(prng, { touch: true });
  }

  // Desktop device
  if (platformName === 'macOS') {
    // MacBook or Mac desktop
    const macScreens = LAPTOP_SCREENS.filter((s) => s.id.startsWith('macbook'));
    if (macScreens.length > 0 && prng.nextFloat() > 0.3) {
      const index = prng.nextInt(0, macScreens.length - 1);
      return macScreens[index];
    }
  }

  // Windows or Linux - desktop or laptop
  const category = prng.nextFloat() > 0.5 ? 'desktop' : 'laptop';
  return getRandomScreen(prng, { category });
}

/**
 * Apply slight variations to a screen profile for uniqueness
 * This helps avoid exact matches while staying realistic
 */
export function varyScreenProfile(
  screen: ScreenProfile,
  prng: { nextInt: (min: number, max: number) => number; nextFloat: () => number }
): ScreenProfile {
  // Only vary availHeight (simulates different taskbar/dock sizes)
  const taskbarVariation = prng.nextInt(-20, 20);
  const newAvailHeight = Math.max(screen.availHeight + taskbarVariation, screen.height - 100);

  // Slight DPR variation for non-integer ratios
  let newDpr = screen.devicePixelRatio;
  if (screen.devicePixelRatio !== Math.floor(screen.devicePixelRatio)) {
    // Non-integer DPR - can vary slightly
    const dprVariation = (prng.nextFloat() - 0.5) * 0.1;
    newDpr = Math.round((screen.devicePixelRatio + dprVariation) * 100) / 100;
  }

  return {
    ...screen,
    availHeight: newAvailHeight,
    devicePixelRatio: newDpr,
  };
}
