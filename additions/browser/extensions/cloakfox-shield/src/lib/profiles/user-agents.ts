/**
 * User Agent Profile Database
 *
 * Comprehensive collection of realistic browser profiles for spoofing.
 * Each profile includes all related navigator properties for consistency.
 *
 * 150+ profiles covering Chrome, Firefox, Edge, Safari, Opera, Brave, Vivaldi
 * on Windows 10/11, macOS 14/15, Linux, Android 13/14/15, iOS 17/18, iPadOS.
 */

export interface UserAgentProfile {
  id: string;
  name: string;
  userAgent: string;
  platform: string;
  vendor: string;
  vendorSub: string;
  appVersion: string;
  appName: string;
  appCodeName: string;
  product: string;
  productSub: string;
  oscpu?: string;
  buildID?: string;

  // Client hints data
  brands?: { brand: string; version: string }[];
  mobile: boolean;
  platformName: string;
  platformVersion: string;
  architecture: string;
  bitness: string;
  model: string;
  fullVersionList?: { brand: string; version: string }[];
}

// ============================================================================
// HELPER: Chrome GREASE brand strings by version
// Chrome rotates the "Not A Brand" GREASE string each version
// ============================================================================
// 122: Not(A:Brand  |  123: Not:A-Brand  |  124: Not-A.Brand
// 125: Not.A/Brand  |  126: Not/A)Brand

// ============================================================================
// WINDOWS CHROME PROFILES (Chrome 122-126 on Win10/Win11)
// ============================================================================
const WINDOWS_CHROME_PROFILES: UserAgentProfile[] = [
  {
    id: 'win10-chrome-122',
    name: 'Chrome 122 (Windows 10)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '10.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '122' },
      { brand: 'Not(A:Brand', version: '24' },
      { brand: 'Google Chrome', version: '122' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '122.0.6261.112' },
      { brand: 'Not(A:Brand', version: '24.0.0.0' },
      { brand: 'Google Chrome', version: '122.0.6261.112' },
    ],
  },
  {
    id: 'win11-chrome-122',
    name: 'Chrome 122 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '122' },
      { brand: 'Not(A:Brand', version: '24' },
      { brand: 'Google Chrome', version: '122' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '122.0.6261.128' },
      { brand: 'Not(A:Brand', version: '24.0.0.0' },
      { brand: 'Google Chrome', version: '122.0.6261.128' },
    ],
  },
  {
    id: 'win10-chrome-123',
    name: 'Chrome 123 (Windows 10)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '10.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Google Chrome', version: '123' },
      { brand: 'Not:A-Brand', version: '8' },
      { brand: 'Chromium', version: '123' },
    ],
    fullVersionList: [
      { brand: 'Google Chrome', version: '123.0.6312.86' },
      { brand: 'Not:A-Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '123.0.6312.86' },
    ],
  },
  {
    id: 'win11-chrome-123',
    name: 'Chrome 123 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Google Chrome', version: '123' },
      { brand: 'Not:A-Brand', version: '8' },
      { brand: 'Chromium', version: '123' },
    ],
    fullVersionList: [
      { brand: 'Google Chrome', version: '123.0.6312.106' },
      { brand: 'Not:A-Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '123.0.6312.106' },
    ],
  },
  {
    id: 'win10-chrome-124',
    name: 'Chrome 124 (Windows 10)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '10.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '124' },
      { brand: 'Google Chrome', version: '124' },
      { brand: 'Not-A.Brand', version: '99' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '124.0.6367.118' },
      { brand: 'Google Chrome', version: '124.0.6367.118' },
      { brand: 'Not-A.Brand', version: '99.0.0.0' },
    ],
  },
  {
    id: 'win11-chrome-124',
    name: 'Chrome 124 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '124' },
      { brand: 'Google Chrome', version: '124' },
      { brand: 'Not-A.Brand', version: '99' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '124.0.6367.201' },
      { brand: 'Google Chrome', version: '124.0.6367.201' },
      { brand: 'Not-A.Brand', version: '99.0.0.0' },
    ],
  },
  {
    id: 'win10-chrome-125',
    name: 'Chrome 125 (Windows 10)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '10.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '125' },
      { brand: 'Not.A/Brand', version: '24' },
      { brand: 'Google Chrome', version: '125' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '125.0.6422.112' },
      { brand: 'Not.A/Brand', version: '24.0.0.0' },
      { brand: 'Google Chrome', version: '125.0.6422.112' },
    ],
  },
  {
    id: 'win11-chrome-125',
    name: 'Chrome 125 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '125' },
      { brand: 'Not.A/Brand', version: '24' },
      { brand: 'Google Chrome', version: '125' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '125.0.6422.141' },
      { brand: 'Not.A/Brand', version: '24.0.0.0' },
      { brand: 'Google Chrome', version: '125.0.6422.141' },
    ],
  },
  {
    id: 'win10-chrome-126',
    name: 'Chrome 126 (Windows 10)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '10.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Not/A)Brand', version: '8' },
      { brand: 'Chromium', version: '126' },
      { brand: 'Google Chrome', version: '126' },
    ],
    fullVersionList: [
      { brand: 'Not/A)Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '126.0.6478.114' },
      { brand: 'Google Chrome', version: '126.0.6478.114' },
    ],
  },
  {
    id: 'win11-chrome-126',
    name: 'Chrome 126 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Not/A)Brand', version: '8' },
      { brand: 'Chromium', version: '126' },
      { brand: 'Google Chrome', version: '126' },
    ],
    fullVersionList: [
      { brand: 'Not/A)Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '126.0.6478.126' },
      { brand: 'Google Chrome', version: '126.0.6478.126' },
    ],
  },
];

// ============================================================================
// WINDOWS FIREFOX PROFILES (Firefox 123-128 on Win10/Win11)
// ============================================================================
const WINDOWS_FIREFOX_PROFILES: UserAgentProfile[] = [
  {
    id: 'win10-firefox-123',
    name: 'Firefox 123 (Windows 10)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
    platform: 'Win32',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Windows)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Windows NT 10.0; Win64; x64',
    buildID: '20240213104200',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '10.0',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'win11-firefox-123',
    name: 'Firefox 123 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
    platform: 'Win32',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Windows)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Windows NT 10.0; Win64; x64',
    buildID: '20240213104200',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'win10-firefox-124',
    name: 'Firefox 124 (Windows 10)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
    platform: 'Win32',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Windows)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Windows NT 10.0; Win64; x64',
    buildID: '20240319110000',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '10.0',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'win11-firefox-124',
    name: 'Firefox 124 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
    platform: 'Win32',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Windows)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Windows NT 10.0; Win64; x64',
    buildID: '20240319110000',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'win10-firefox-125',
    name: 'Firefox 125 (Windows 10)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    platform: 'Win32',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Windows)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Windows NT 10.0; Win64; x64',
    buildID: '20240416100000',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '10.0',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'win11-firefox-125',
    name: 'Firefox 125 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    platform: 'Win32',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Windows)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Windows NT 10.0; Win64; x64',
    buildID: '20240416100000',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'win10-firefox-126',
    name: 'Firefox 126 (Windows 10)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
    platform: 'Win32',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Windows)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Windows NT 10.0; Win64; x64',
    buildID: '20240514120000',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '10.0',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'win11-firefox-126',
    name: 'Firefox 126 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
    platform: 'Win32',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Windows)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Windows NT 10.0; Win64; x64',
    buildID: '20240514120000',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'win10-firefox-127',
    name: 'Firefox 127 (Windows 10)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0',
    platform: 'Win32',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Windows)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Windows NT 10.0; Win64; x64',
    buildID: '20240611140000',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '10.0',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'win11-firefox-127',
    name: 'Firefox 127 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0',
    platform: 'Win32',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Windows)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Windows NT 10.0; Win64; x64',
    buildID: '20240611140000',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'win11-firefox-128',
    name: 'Firefox 128 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
    platform: 'Win32',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Windows)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Windows NT 10.0; Win64; x64',
    buildID: '20240709091000',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
];

// ============================================================================
// WINDOWS EDGE PROFILES (Edge 122-126 on Win10/Win11)
// ============================================================================
const WINDOWS_EDGE_PROFILES: UserAgentProfile[] = [
  {
    id: 'win10-edge-122',
    name: 'Edge 122 (Windows 10)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.2365.92',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.2365.92',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '10.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '122' },
      { brand: 'Not(A:Brand', version: '24' },
      { brand: 'Microsoft Edge', version: '122' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '122.0.6261.112' },
      { brand: 'Not(A:Brand', version: '24.0.0.0' },
      { brand: 'Microsoft Edge', version: '122.0.2365.92' },
    ],
  },
  {
    id: 'win11-edge-122',
    name: 'Edge 122 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.2365.92',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.2365.92',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '122' },
      { brand: 'Not(A:Brand', version: '24' },
      { brand: 'Microsoft Edge', version: '122' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '122.0.6261.128' },
      { brand: 'Not(A:Brand', version: '24.0.0.0' },
      { brand: 'Microsoft Edge', version: '122.0.2365.106' },
    ],
  },
  {
    id: 'win11-edge-123',
    name: 'Edge 123 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.2420.65',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.2420.65',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Microsoft Edge', version: '123' },
      { brand: 'Not:A-Brand', version: '8' },
      { brand: 'Chromium', version: '123' },
    ],
    fullVersionList: [
      { brand: 'Microsoft Edge', version: '123.0.2420.65' },
      { brand: 'Not:A-Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '123.0.6312.86' },
    ],
  },
  {
    id: 'win11-edge-124',
    name: 'Edge 124 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.2478.67',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.2478.67',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '124' },
      { brand: 'Microsoft Edge', version: '124' },
      { brand: 'Not-A.Brand', version: '99' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '124.0.6367.118' },
      { brand: 'Microsoft Edge', version: '124.0.2478.67' },
      { brand: 'Not-A.Brand', version: '99.0.0.0' },
    ],
  },
  {
    id: 'win10-edge-125',
    name: 'Edge 125 (Windows 10)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.2535.67',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.2535.67',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '10.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '125' },
      { brand: 'Not.A/Brand', version: '24' },
      { brand: 'Microsoft Edge', version: '125' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '125.0.6422.112' },
      { brand: 'Not.A/Brand', version: '24.0.0.0' },
      { brand: 'Microsoft Edge', version: '125.0.2535.67' },
    ],
  },
  {
    id: 'win11-edge-125',
    name: 'Edge 125 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.2535.85',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.2535.85',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '125' },
      { brand: 'Not.A/Brand', version: '24' },
      { brand: 'Microsoft Edge', version: '125' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '125.0.6422.141' },
      { brand: 'Not.A/Brand', version: '24.0.0.0' },
      { brand: 'Microsoft Edge', version: '125.0.2535.85' },
    ],
  },
  {
    id: 'win11-edge-126',
    name: 'Edge 126 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.2592.68',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.2592.68',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Not/A)Brand', version: '8' },
      { brand: 'Chromium', version: '126' },
      { brand: 'Microsoft Edge', version: '126' },
    ],
    fullVersionList: [
      { brand: 'Not/A)Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '126.0.6478.114' },
      { brand: 'Microsoft Edge', version: '126.0.2592.68' },
    ],
  },
];

// ============================================================================
// MACOS EDGE PROFILES
// ============================================================================
const MACOS_EDGE_PROFILES: UserAgentProfile[] = [
  {
    id: 'mac-edge-124',
    name: 'Edge 124 (macOS Sonoma)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.2478.67',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.2478.67',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '14.4.1',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '124' },
      { brand: 'Microsoft Edge', version: '124' },
      { brand: 'Not-A.Brand', version: '99' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '124.0.6367.118' },
      { brand: 'Microsoft Edge', version: '124.0.2478.67' },
      { brand: 'Not-A.Brand', version: '99.0.0.0' },
    ],
  },
  {
    id: 'mac-edge-125',
    name: 'Edge 125 (macOS Sonoma)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.2535.85',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.2535.85',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '14.5.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '125' },
      { brand: 'Not.A/Brand', version: '24' },
      { brand: 'Microsoft Edge', version: '125' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '125.0.6422.141' },
      { brand: 'Not.A/Brand', version: '24.0.0.0' },
      { brand: 'Microsoft Edge', version: '125.0.2535.85' },
    ],
  },
  {
    id: 'mac-edge-126',
    name: 'Edge 126 (macOS Sequoia)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.2592.68',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.2592.68',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '15.0.0',
    architecture: 'arm',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Not/A)Brand', version: '8' },
      { brand: 'Chromium', version: '126' },
      { brand: 'Microsoft Edge', version: '126' },
    ],
    fullVersionList: [
      { brand: 'Not/A)Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '126.0.6478.114' },
      { brand: 'Microsoft Edge', version: '126.0.2592.68' },
    ],
  },
];

// ============================================================================
// MACOS CHROME PROFILES (Chrome 122-126 on macOS 14 Sonoma / macOS 15 Sequoia)
// ============================================================================
const MACOS_CHROME_PROFILES: UserAgentProfile[] = [
  {
    id: 'mac-chrome-122-sonoma',
    name: 'Chrome 122 (macOS Sonoma)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '14.3.1',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '122' },
      { brand: 'Not(A:Brand', version: '24' },
      { brand: 'Google Chrome', version: '122' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '122.0.6261.112' },
      { brand: 'Not(A:Brand', version: '24.0.0.0' },
      { brand: 'Google Chrome', version: '122.0.6261.112' },
    ],
  },
  {
    id: 'mac-chrome-123-sonoma',
    name: 'Chrome 123 (macOS Sonoma)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '14.4.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Google Chrome', version: '123' },
      { brand: 'Not:A-Brand', version: '8' },
      { brand: 'Chromium', version: '123' },
    ],
    fullVersionList: [
      { brand: 'Google Chrome', version: '123.0.6312.86' },
      { brand: 'Not:A-Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '123.0.6312.86' },
    ],
  },
  {
    id: 'mac-chrome-124-sonoma',
    name: 'Chrome 124 (macOS Sonoma)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '14.4.1',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '124' },
      { brand: 'Google Chrome', version: '124' },
      { brand: 'Not-A.Brand', version: '99' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '124.0.6367.118' },
      { brand: 'Google Chrome', version: '124.0.6367.118' },
      { brand: 'Not-A.Brand', version: '99.0.0.0' },
    ],
  },
  {
    id: 'mac-chrome-125-sonoma',
    name: 'Chrome 125 (macOS Sonoma)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '14.5.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '125' },
      { brand: 'Not.A/Brand', version: '24' },
      { brand: 'Google Chrome', version: '125' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '125.0.6422.112' },
      { brand: 'Not.A/Brand', version: '24.0.0.0' },
      { brand: 'Google Chrome', version: '125.0.6422.112' },
    ],
  },
  {
    id: 'mac-chrome-125-sequoia',
    name: 'Chrome 125 (macOS Sequoia)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '15.0.0',
    architecture: 'arm',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '125' },
      { brand: 'Not.A/Brand', version: '24' },
      { brand: 'Google Chrome', version: '125' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '125.0.6422.141' },
      { brand: 'Not.A/Brand', version: '24.0.0.0' },
      { brand: 'Google Chrome', version: '125.0.6422.141' },
    ],
  },
  {
    id: 'mac-chrome-126-sonoma',
    name: 'Chrome 126 (macOS Sonoma)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '14.5.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Not/A)Brand', version: '8' },
      { brand: 'Chromium', version: '126' },
      { brand: 'Google Chrome', version: '126' },
    ],
    fullVersionList: [
      { brand: 'Not/A)Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '126.0.6478.114' },
      { brand: 'Google Chrome', version: '126.0.6478.114' },
    ],
  },
  {
    id: 'mac-chrome-126-sequoia',
    name: 'Chrome 126 (macOS Sequoia)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '15.0.0',
    architecture: 'arm',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Not/A)Brand', version: '8' },
      { brand: 'Chromium', version: '126' },
      { brand: 'Google Chrome', version: '126' },
    ],
    fullVersionList: [
      { brand: 'Not/A)Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '126.0.6478.126' },
      { brand: 'Google Chrome', version: '126.0.6478.126' },
    ],
  },
];

// ============================================================================
// MACOS SAFARI PROFILES (Safari 17, 17.4, 18 on macOS 14/15)
// ============================================================================
const MACOS_SAFARI_PROFILES: UserAgentProfile[] = [
  {
    id: 'mac-safari-17-sonoma',
    name: 'Safari 17.2 (macOS Sonoma)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    platform: 'MacIntel',
    vendor: 'Apple Computer, Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '14.2',
    architecture: '',
    bitness: '',
    model: '',
  },
  {
    id: 'mac-safari-17.3-sonoma',
    name: 'Safari 17.3 (macOS Sonoma)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15',
    platform: 'MacIntel',
    vendor: 'Apple Computer, Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '14.3',
    architecture: '',
    bitness: '',
    model: '',
  },
  {
    id: 'mac-safari-17.4-sonoma',
    name: 'Safari 17.4 (macOS Sonoma)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
    platform: 'MacIntel',
    vendor: 'Apple Computer, Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '14.4',
    architecture: '',
    bitness: '',
    model: '',
  },
  {
    id: 'mac-safari-17.5-sonoma',
    name: 'Safari 17.5 (macOS Sonoma)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
    platform: 'MacIntel',
    vendor: 'Apple Computer, Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '14.5',
    architecture: '',
    bitness: '',
    model: '',
  },
  {
    id: 'mac-safari-18-sequoia',
    name: 'Safari 18.0 (macOS Sequoia)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15',
    platform: 'MacIntel',
    vendor: 'Apple Computer, Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '15.0',
    architecture: '',
    bitness: '',
    model: '',
  },
  {
    id: 'mac-safari-18.1-sequoia',
    name: 'Safari 18.1 (macOS Sequoia)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15',
    platform: 'MacIntel',
    vendor: 'Apple Computer, Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '15.1',
    architecture: '',
    bitness: '',
    model: '',
  },
];

// ============================================================================
// MACOS FIREFOX PROFILES (Firefox 123-128 on macOS 14/15)
// ============================================================================
const MACOS_FIREFOX_PROFILES: UserAgentProfile[] = [
  {
    id: 'mac-firefox-123',
    name: 'Firefox 123 (macOS Sonoma)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0',
    platform: 'MacIntel',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Macintosh)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Intel Mac OS X 10.15',
    buildID: '20240213104200',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '10.15',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'mac-firefox-124',
    name: 'Firefox 124 (macOS Sonoma)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:124.0) Gecko/20100101 Firefox/124.0',
    platform: 'MacIntel',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Macintosh)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Intel Mac OS X 10.15',
    buildID: '20240319110000',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '10.15',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'mac-firefox-125',
    name: 'Firefox 125 (macOS)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0',
    platform: 'MacIntel',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Macintosh)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Intel Mac OS X 10.15',
    buildID: '20240416100000',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '10.15',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'mac-firefox-126',
    name: 'Firefox 126 (macOS)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0',
    platform: 'MacIntel',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Macintosh)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Intel Mac OS X 10.15',
    buildID: '20240514120000',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '10.15',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'mac-firefox-127',
    name: 'Firefox 127 (macOS)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0',
    platform: 'MacIntel',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Macintosh)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Intel Mac OS X 10.15',
    buildID: '20240611140000',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '10.15',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'mac-firefox-128',
    name: 'Firefox 128 (macOS)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0',
    platform: 'MacIntel',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Macintosh)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Intel Mac OS X 10.15',
    buildID: '20240709091000',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '10.15',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
];

// ============================================================================
// LINUX CHROME PROFILES (Chrome 122-126)
// ============================================================================
const LINUX_CHROME_PROFILES: UserAgentProfile[] = [
  {
    id: 'linux-chrome-122',
    name: 'Chrome 122 (Linux)',
    userAgent:
      'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    platform: 'Linux x86_64',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Linux',
    platformVersion: '',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '122' },
      { brand: 'Not(A:Brand', version: '24' },
      { brand: 'Google Chrome', version: '122' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '122.0.6261.112' },
      { brand: 'Not(A:Brand', version: '24.0.0.0' },
      { brand: 'Google Chrome', version: '122.0.6261.112' },
    ],
  },
  {
    id: 'linux-chrome-123',
    name: 'Chrome 123 (Linux)',
    userAgent:
      'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    platform: 'Linux x86_64',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Linux',
    platformVersion: '',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Google Chrome', version: '123' },
      { brand: 'Not:A-Brand', version: '8' },
      { brand: 'Chromium', version: '123' },
    ],
    fullVersionList: [
      { brand: 'Google Chrome', version: '123.0.6312.86' },
      { brand: 'Not:A-Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '123.0.6312.86' },
    ],
  },
  {
    id: 'linux-chrome-124',
    name: 'Chrome 124 (Linux)',
    userAgent:
      'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    platform: 'Linux x86_64',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Linux',
    platformVersion: '',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '124' },
      { brand: 'Google Chrome', version: '124' },
      { brand: 'Not-A.Brand', version: '99' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '124.0.6367.118' },
      { brand: 'Google Chrome', version: '124.0.6367.118' },
      { brand: 'Not-A.Brand', version: '99.0.0.0' },
    ],
  },
  {
    id: 'linux-chrome-125',
    name: 'Chrome 125 (Linux)',
    userAgent:
      'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    platform: 'Linux x86_64',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Linux',
    platformVersion: '',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '125' },
      { brand: 'Not.A/Brand', version: '24' },
      { brand: 'Google Chrome', version: '125' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '125.0.6422.112' },
      { brand: 'Not.A/Brand', version: '24.0.0.0' },
      { brand: 'Google Chrome', version: '125.0.6422.112' },
    ],
  },
  {
    id: 'linux-chrome-126',
    name: 'Chrome 126 (Linux)',
    userAgent:
      'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    platform: 'Linux x86_64',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Linux',
    platformVersion: '',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Not/A)Brand', version: '8' },
      { brand: 'Chromium', version: '126' },
      { brand: 'Google Chrome', version: '126' },
    ],
    fullVersionList: [
      { brand: 'Not/A)Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '126.0.6478.114' },
      { brand: 'Google Chrome', version: '126.0.6478.114' },
    ],
  },
];

// ============================================================================
// LINUX FIREFOX PROFILES (Firefox 123-128 on Ubuntu/Fedora)
// ============================================================================
const LINUX_FIREFOX_PROFILES: UserAgentProfile[] = [
  {
    id: 'linux-firefox-123',
    name: 'Firefox 123 (Ubuntu)',
    userAgent:
      'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0',
    platform: 'Linux x86_64',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (X11)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Linux x86_64',
    buildID: '20240213104200',
    mobile: false,
    platformName: 'Linux',
    platformVersion: '',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'linux-firefox-124',
    name: 'Firefox 124 (Linux)',
    userAgent:
      'Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0',
    platform: 'Linux x86_64',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (X11)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Linux x86_64',
    buildID: '20240319110000',
    mobile: false,
    platformName: 'Linux',
    platformVersion: '',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'linux-firefox-125-fedora',
    name: 'Firefox 125 (Fedora)',
    userAgent:
      'Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0',
    platform: 'Linux x86_64',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (X11)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Linux x86_64',
    buildID: '20240416100000',
    mobile: false,
    platformName: 'Linux',
    platformVersion: '',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'linux-firefox-126',
    name: 'Firefox 126 (Linux)',
    userAgent:
      'Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0',
    platform: 'Linux x86_64',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (X11)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Linux x86_64',
    buildID: '20240514120000',
    mobile: false,
    platformName: 'Linux',
    platformVersion: '',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'linux-firefox-127-ubuntu',
    name: 'Firefox 127 (Ubuntu)',
    userAgent:
      'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0',
    platform: 'Linux x86_64',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (X11)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Linux x86_64',
    buildID: '20240611140000',
    mobile: false,
    platformName: 'Linux',
    platformVersion: '',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
  {
    id: 'linux-firefox-128',
    name: 'Firefox 128 (Linux)',
    userAgent:
      'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0',
    platform: 'Linux x86_64',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (X11)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Linux x86_64',
    buildID: '20240709091000',
    mobile: false,
    platformName: 'Linux',
    platformVersion: '',
    architecture: 'x86_64',
    bitness: '64',
    model: '',
  },
];

// ============================================================================
// OPERA PROFILES (Opera 108-112 on Windows 11 and macOS)
// Opera version maps: 108=Cr122, 109=Cr123, 110=Cr124, 111=Cr125, 112=Cr126
// ============================================================================
const OPERA_PROFILES: UserAgentProfile[] = [
  {
    id: 'win11-opera-108',
    name: 'Opera 108 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 OPR/108.0.0.0',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 OPR/108.0.0.0',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '122' },
      { brand: 'Not(A:Brand', version: '24' },
      { brand: 'Opera', version: '108' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '122.0.6261.112' },
      { brand: 'Not(A:Brand', version: '24.0.0.0' },
      { brand: 'Opera', version: '108.0.5067.24' },
    ],
  },
  {
    id: 'mac-opera-108',
    name: 'Opera 108 (macOS Sonoma)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 OPR/108.0.0.0',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 OPR/108.0.0.0',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '14.3.1',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '122' },
      { brand: 'Not(A:Brand', version: '24' },
      { brand: 'Opera', version: '108' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '122.0.6261.112' },
      { brand: 'Not(A:Brand', version: '24.0.0.0' },
      { brand: 'Opera', version: '108.0.5067.24' },
    ],
  },
  {
    id: 'win11-opera-109',
    name: 'Opera 109 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 OPR/109.0.0.0',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 OPR/109.0.0.0',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Opera', version: '109' },
      { brand: 'Not:A-Brand', version: '8' },
      { brand: 'Chromium', version: '123' },
    ],
    fullVersionList: [
      { brand: 'Opera', version: '109.0.5097.33' },
      { brand: 'Not:A-Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '123.0.6312.86' },
    ],
  },
  {
    id: 'win11-opera-110',
    name: 'Opera 110 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 OPR/110.0.0.0',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 OPR/110.0.0.0',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '124' },
      { brand: 'Opera', version: '110' },
      { brand: 'Not-A.Brand', version: '99' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '124.0.6367.118' },
      { brand: 'Opera', version: '110.0.5130.23' },
      { brand: 'Not-A.Brand', version: '99.0.0.0' },
    ],
  },
  {
    id: 'mac-opera-110',
    name: 'Opera 110 (macOS Sonoma)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 OPR/110.0.0.0',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 OPR/110.0.0.0',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '14.4.1',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '124' },
      { brand: 'Opera', version: '110' },
      { brand: 'Not-A.Brand', version: '99' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '124.0.6367.118' },
      { brand: 'Opera', version: '110.0.5130.23' },
      { brand: 'Not-A.Brand', version: '99.0.0.0' },
    ],
  },
  {
    id: 'win11-opera-111',
    name: 'Opera 111 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 OPR/111.0.0.0',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 OPR/111.0.0.0',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '125' },
      { brand: 'Not.A/Brand', version: '24' },
      { brand: 'Opera', version: '111' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '125.0.6422.112' },
      { brand: 'Not.A/Brand', version: '24.0.0.0' },
      { brand: 'Opera', version: '111.0.5168.25' },
    ],
  },
  {
    id: 'mac-opera-111',
    name: 'Opera 111 (macOS Sequoia)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 OPR/111.0.0.0',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 OPR/111.0.0.0',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '15.0.0',
    architecture: 'arm',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '125' },
      { brand: 'Not.A/Brand', version: '24' },
      { brand: 'Opera', version: '111' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '125.0.6422.141' },
      { brand: 'Not.A/Brand', version: '24.0.0.0' },
      { brand: 'Opera', version: '111.0.5168.25' },
    ],
  },
  {
    id: 'win11-opera-112',
    name: 'Opera 112 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 OPR/112.0.0.0',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 OPR/112.0.0.0',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Not/A)Brand', version: '8' },
      { brand: 'Chromium', version: '126' },
      { brand: 'Opera', version: '112' },
    ],
    fullVersionList: [
      { brand: 'Not/A)Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '126.0.6478.114' },
      { brand: 'Opera', version: '112.0.5197.30' },
    ],
  },
  {
    id: 'mac-opera-112',
    name: 'Opera 112 (macOS Sequoia)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 OPR/112.0.0.0',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 OPR/112.0.0.0',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '15.0.0',
    architecture: 'arm',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Not/A)Brand', version: '8' },
      { brand: 'Chromium', version: '126' },
      { brand: 'Opera', version: '112' },
    ],
    fullVersionList: [
      { brand: 'Not/A)Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '126.0.6478.126' },
      { brand: 'Opera', version: '112.0.5197.30' },
    ],
  },
];

// ============================================================================
// BRAVE PROFILES (Brave 1.64-1.68 on Windows 11 and macOS)
// Brave 1.64=Cr122, 1.65=Cr123, 1.66=Cr125, 1.67=Cr126, 1.68=Cr126
// Brave UA is identical to Chrome (no Brave token in UA string)
// ============================================================================
const BRAVE_PROFILES: UserAgentProfile[] = [
  {
    id: 'win11-brave-1.64',
    name: 'Brave 1.64 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '122' },
      { brand: 'Not(A:Brand', version: '24' },
      { brand: 'Brave', version: '122' },
    ],
  },
  {
    id: 'mac-brave-1.64',
    name: 'Brave 1.64 (macOS Sonoma)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '14.3.1',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '122' },
      { brand: 'Not(A:Brand', version: '24' },
      { brand: 'Brave', version: '122' },
    ],
  },
  {
    id: 'win11-brave-1.65',
    name: 'Brave 1.65 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Brave', version: '123' },
      { brand: 'Not:A-Brand', version: '8' },
      { brand: 'Chromium', version: '123' },
    ],
  },
  {
    id: 'win11-brave-1.66',
    name: 'Brave 1.66 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '125' },
      { brand: 'Not.A/Brand', version: '24' },
      { brand: 'Brave', version: '125' },
    ],
  },
  {
    id: 'mac-brave-1.66',
    name: 'Brave 1.66 (macOS Sequoia)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '15.0.0',
    architecture: 'arm',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '125' },
      { brand: 'Not.A/Brand', version: '24' },
      { brand: 'Brave', version: '125' },
    ],
  },
  {
    id: 'win11-brave-1.67',
    name: 'Brave 1.67 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Not/A)Brand', version: '8' },
      { brand: 'Chromium', version: '126' },
      { brand: 'Brave', version: '126' },
    ],
  },
  {
    id: 'mac-brave-1.67',
    name: 'Brave 1.67 (macOS Sequoia)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '15.0.0',
    architecture: 'arm',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Not/A)Brand', version: '8' },
      { brand: 'Chromium', version: '126' },
      { brand: 'Brave', version: '126' },
    ],
  },
  {
    id: 'win11-brave-1.68',
    name: 'Brave 1.68 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Not/A)Brand', version: '8' },
      { brand: 'Chromium', version: '126' },
      { brand: 'Brave', version: '126' },
    ],
  },
];

// ============================================================================
// VIVALDI PROFILES (Vivaldi 6.6-6.8 on Windows 11 and macOS)
// Vivaldi 6.6=Cr122, 6.7=Cr124, 6.8=Cr126
// Vivaldi does NOT expose itself in UA string (looks like Chrome)
// But does expose in Client Hints brands
// ============================================================================
const VIVALDI_PROFILES: UserAgentProfile[] = [
  {
    id: 'win11-vivaldi-6.6',
    name: 'Vivaldi 6.6 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '122' },
      { brand: 'Not(A:Brand', version: '24' },
      { brand: 'Vivaldi', version: '6' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '122.0.6261.112' },
      { brand: 'Not(A:Brand', version: '24.0.0.0' },
      { brand: 'Vivaldi', version: '6.6.3271.57' },
    ],
  },
  {
    id: 'mac-vivaldi-6.6',
    name: 'Vivaldi 6.6 (macOS Sonoma)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '14.3.1',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '122' },
      { brand: 'Not(A:Brand', version: '24' },
      { brand: 'Vivaldi', version: '6' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '122.0.6261.112' },
      { brand: 'Not(A:Brand', version: '24.0.0.0' },
      { brand: 'Vivaldi', version: '6.6.3271.57' },
    ],
  },
  {
    id: 'win11-vivaldi-6.7',
    name: 'Vivaldi 6.7 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '124' },
      { brand: 'Not-A.Brand', version: '99' },
      { brand: 'Vivaldi', version: '6' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '124.0.6367.118' },
      { brand: 'Not-A.Brand', version: '99.0.0.0' },
      { brand: 'Vivaldi', version: '6.7.3329.35' },
    ],
  },
  {
    id: 'mac-vivaldi-6.7',
    name: 'Vivaldi 6.7 (macOS Sonoma)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '14.4.1',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Chromium', version: '124' },
      { brand: 'Not-A.Brand', version: '99' },
      { brand: 'Vivaldi', version: '6' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '124.0.6367.118' },
      { brand: 'Not-A.Brand', version: '99.0.0.0' },
      { brand: 'Vivaldi', version: '6.7.3329.35' },
    ],
  },
  {
    id: 'win11-vivaldi-6.8',
    name: 'Vivaldi 6.8 (Windows 11)',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    platform: 'Win32',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Not/A)Brand', version: '8' },
      { brand: 'Chromium', version: '126' },
      { brand: 'Vivaldi', version: '6' },
    ],
    fullVersionList: [
      { brand: 'Not/A)Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '126.0.6478.114' },
      { brand: 'Vivaldi', version: '6.8.3381.44' },
    ],
  },
  {
    id: 'mac-vivaldi-6.8',
    name: 'Vivaldi 6.8 (macOS Sequoia)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    platform: 'MacIntel',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '15.0.0',
    architecture: 'arm',
    bitness: '64',
    model: '',
    brands: [
      { brand: 'Not/A)Brand', version: '8' },
      { brand: 'Chromium', version: '126' },
      { brand: 'Vivaldi', version: '6' },
    ],
    fullVersionList: [
      { brand: 'Not/A)Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '126.0.6478.126' },
      { brand: 'Vivaldi', version: '6.8.3381.44' },
    ],
  },
];

// ============================================================================
// ANDROID CHROME PROFILES (Chrome 122-126 on Android 13, 14, 15)
// ============================================================================
const ANDROID_CHROME_PROFILES: UserAgentProfile[] = [
  {
    id: 'android13-chrome-122',
    name: 'Chrome 122 (Android 13 Pixel 7)',
    userAgent:
      'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36',
    platform: 'Linux armv81',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'Android',
    platformVersion: '13.0.0',
    architecture: '',
    bitness: '',
    model: 'Pixel 7',
    brands: [
      { brand: 'Chromium', version: '122' },
      { brand: 'Not(A:Brand', version: '24' },
      { brand: 'Google Chrome', version: '122' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '122.0.6261.119' },
      { brand: 'Not(A:Brand', version: '24.0.0.0' },
      { brand: 'Google Chrome', version: '122.0.6261.119' },
    ],
  },
  {
    id: 'android14-chrome-123',
    name: 'Chrome 123 (Android 14 Pixel 8)',
    userAgent:
      'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.99 Mobile Safari/537.36',
    platform: 'Linux armv81',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.99 Mobile Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'Android',
    platformVersion: '14.0.0',
    architecture: '',
    bitness: '',
    model: 'Pixel 8',
    brands: [
      { brand: 'Google Chrome', version: '123' },
      { brand: 'Not:A-Brand', version: '8' },
      { brand: 'Chromium', version: '123' },
    ],
    fullVersionList: [
      { brand: 'Google Chrome', version: '123.0.6312.99' },
      { brand: 'Not:A-Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '123.0.6312.99' },
    ],
  },
  {
    id: 'android14-chrome-124-samsung',
    name: 'Chrome 124 (Android 14 Galaxy S24)',
    userAgent:
      'Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.123 Mobile Safari/537.36',
    platform: 'Linux armv81',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.123 Mobile Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'Android',
    platformVersion: '14.0.0',
    architecture: '',
    bitness: '',
    model: 'SM-S921B',
    brands: [
      { brand: 'Chromium', version: '124' },
      { brand: 'Google Chrome', version: '124' },
      { brand: 'Not-A.Brand', version: '99' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '124.0.6367.123' },
      { brand: 'Google Chrome', version: '124.0.6367.123' },
      { brand: 'Not-A.Brand', version: '99.0.0.0' },
    ],
  },
  {
    id: 'android14-chrome-125',
    name: 'Chrome 125 (Android 14 Pixel 8 Pro)',
    userAgent:
      'Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.113 Mobile Safari/537.36',
    platform: 'Linux armv81',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.113 Mobile Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'Android',
    platformVersion: '14.0.0',
    architecture: '',
    bitness: '',
    model: 'Pixel 8 Pro',
    brands: [
      { brand: 'Chromium', version: '125' },
      { brand: 'Not.A/Brand', version: '24' },
      { brand: 'Google Chrome', version: '125' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '125.0.6422.113' },
      { brand: 'Not.A/Brand', version: '24.0.0.0' },
      { brand: 'Google Chrome', version: '125.0.6422.113' },
    ],
  },
  {
    id: 'android15-chrome-126',
    name: 'Chrome 126 (Android 15 Pixel 9)',
    userAgent:
      'Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.122 Mobile Safari/537.36',
    platform: 'Linux armv81',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.122 Mobile Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'Android',
    platformVersion: '15.0.0',
    architecture: '',
    bitness: '',
    model: 'Pixel 9',
    brands: [
      { brand: 'Not/A)Brand', version: '8' },
      { brand: 'Chromium', version: '126' },
      { brand: 'Google Chrome', version: '126' },
    ],
    fullVersionList: [
      { brand: 'Not/A)Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '126.0.6478.122' },
      { brand: 'Google Chrome', version: '126.0.6478.122' },
    ],
  },
  {
    id: 'android14-chrome-126-samsung',
    name: 'Chrome 126 (Android 14 Galaxy S24 Ultra)',
    userAgent:
      'Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.122 Mobile Safari/537.36',
    platform: 'Linux armv81',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.122 Mobile Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'Android',
    platformVersion: '14.0.0',
    architecture: '',
    bitness: '',
    model: 'SM-S928B',
    brands: [
      { brand: 'Not/A)Brand', version: '8' },
      { brand: 'Chromium', version: '126' },
      { brand: 'Google Chrome', version: '126' },
    ],
    fullVersionList: [
      { brand: 'Not/A)Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '126.0.6478.122' },
      { brand: 'Google Chrome', version: '126.0.6478.122' },
    ],
  },
  {
    id: 'android13-chrome-125-oneplus',
    name: 'Chrome 125 (Android 13 OnePlus 11)',
    userAgent:
      'Mozilla/5.0 (Linux; Android 13; CPH2449) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.113 Mobile Safari/537.36',
    platform: 'Linux armv81',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Linux; Android 13; CPH2449) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.113 Mobile Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'Android',
    platformVersion: '13.0.0',
    architecture: '',
    bitness: '',
    model: 'CPH2449',
    brands: [
      { brand: 'Chromium', version: '125' },
      { brand: 'Not.A/Brand', version: '24' },
      { brand: 'Google Chrome', version: '125' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '125.0.6422.113' },
      { brand: 'Not.A/Brand', version: '24.0.0.0' },
      { brand: 'Google Chrome', version: '125.0.6422.113' },
    ],
  },
];

// ============================================================================
// ANDROID TABLET CHROME PROFILES
// ============================================================================
const ANDROID_TABLET_PROFILES: UserAgentProfile[] = [
  {
    id: 'android14-tablet-chrome-125',
    name: 'Chrome 125 (Android 14 Tab S9)',
    userAgent:
      'Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.113 Safari/537.36',
    platform: 'Linux armv81',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.113 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Android',
    platformVersion: '14.0.0',
    architecture: '',
    bitness: '',
    model: 'SM-X710',
    brands: [
      { brand: 'Chromium', version: '125' },
      { brand: 'Not.A/Brand', version: '24' },
      { brand: 'Google Chrome', version: '125' },
    ],
    fullVersionList: [
      { brand: 'Chromium', version: '125.0.6422.113' },
      { brand: 'Not.A/Brand', version: '24.0.0.0' },
      { brand: 'Google Chrome', version: '125.0.6422.113' },
    ],
  },
  {
    id: 'android14-tablet-chrome-126',
    name: 'Chrome 126 (Android 14 Pixel Tablet)',
    userAgent:
      'Mozilla/5.0 (Linux; Android 14; Pixel Tablet) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.122 Safari/537.36',
    platform: 'Linux armv81',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Linux; Android 14; Pixel Tablet) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.122 Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'Android',
    platformVersion: '14.0.0',
    architecture: '',
    bitness: '',
    model: 'Pixel Tablet',
    brands: [
      { brand: 'Not/A)Brand', version: '8' },
      { brand: 'Chromium', version: '126' },
      { brand: 'Google Chrome', version: '126' },
    ],
    fullVersionList: [
      { brand: 'Not/A)Brand', version: '8.0.0.0' },
      { brand: 'Chromium', version: '126.0.6478.122' },
      { brand: 'Google Chrome', version: '126.0.6478.122' },
    ],
  },
];

// ============================================================================
// SAMSUNG INTERNET PROFILES (Samsung Internet 24, 25)
// ============================================================================
const SAMSUNG_INTERNET_PROFILES: UserAgentProfile[] = [
  {
    id: 'samsung-24-s23',
    name: 'Samsung Internet 24 (Galaxy S23)',
    userAgent:
      'Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/24.0 Chrome/122.0.6261.105 Mobile Safari/537.36',
    platform: 'Linux armv81',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/24.0 Chrome/122.0.6261.105 Mobile Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'Android',
    platformVersion: '14.0.0',
    architecture: '',
    bitness: '',
    model: 'SM-S911B',
    brands: [
      { brand: 'Chromium', version: '122' },
      { brand: 'Not(A:Brand', version: '24' },
      { brand: 'Samsung Internet', version: '24' },
    ],
  },
  {
    id: 'samsung-25-s24',
    name: 'Samsung Internet 25 (Galaxy S24)',
    userAgent:
      'Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/25.0 Chrome/121.0.6167.101 Mobile Safari/537.36',
    platform: 'Linux armv81',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/25.0 Chrome/121.0.6167.101 Mobile Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'Android',
    platformVersion: '14.0.0',
    architecture: '',
    bitness: '',
    model: 'SM-S921B',
    brands: [
      { brand: 'Not A(Brand', version: '99' },
      { brand: 'Samsung Internet', version: '25' },
      { brand: 'Chromium', version: '121' },
    ],
  },
  {
    id: 'samsung-25-s24ultra',
    name: 'Samsung Internet 25 (Galaxy S24 Ultra)',
    userAgent:
      'Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/25.0 Chrome/121.0.6167.101 Mobile Safari/537.36',
    platform: 'Linux armv81',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/25.0 Chrome/121.0.6167.101 Mobile Safari/537.36',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'Android',
    platformVersion: '14.0.0',
    architecture: '',
    bitness: '',
    model: 'SM-S928B',
    brands: [
      { brand: 'Not A(Brand', version: '99' },
      { brand: 'Samsung Internet', version: '25' },
      { brand: 'Chromium', version: '121' },
    ],
  },
];

// ============================================================================
// FIREFOX MOBILE PROFILES (Firefox 124-128 on Android 14)
// ============================================================================
const FIREFOX_MOBILE_PROFILES: UserAgentProfile[] = [
  {
    id: 'android-firefox-124',
    name: 'Firefox 124 (Android 14)',
    userAgent:
      'Mozilla/5.0 (Android 14; Mobile; rv:124.0) Gecko/124.0 Firefox/124.0',
    platform: 'Linux armv81',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Android 14)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Linux armv81',
    buildID: '20240319110000',
    mobile: true,
    platformName: 'Android',
    platformVersion: '14.0',
    architecture: '',
    bitness: '',
    model: '',
  },
  {
    id: 'android-firefox-125',
    name: 'Firefox 125 (Android 14)',
    userAgent:
      'Mozilla/5.0 (Android 14; Mobile; rv:125.0) Gecko/125.0 Firefox/125.0',
    platform: 'Linux armv81',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Android 14)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Linux armv81',
    buildID: '20240416100000',
    mobile: true,
    platformName: 'Android',
    platformVersion: '14.0',
    architecture: '',
    bitness: '',
    model: '',
  },
  {
    id: 'android-firefox-126',
    name: 'Firefox 126 (Android 14)',
    userAgent:
      'Mozilla/5.0 (Android 14; Mobile; rv:126.0) Gecko/126.0 Firefox/126.0',
    platform: 'Linux armv81',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Android 14)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Linux armv81',
    buildID: '20240514120000',
    mobile: true,
    platformName: 'Android',
    platformVersion: '14.0',
    architecture: '',
    bitness: '',
    model: '',
  },
  {
    id: 'android-firefox-127',
    name: 'Firefox 127 (Android 14)',
    userAgent:
      'Mozilla/5.0 (Android 14; Mobile; rv:127.0) Gecko/127.0 Firefox/127.0',
    platform: 'Linux armv81',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Android 14)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Linux armv81',
    buildID: '20240611140000',
    mobile: true,
    platformName: 'Android',
    platformVersion: '14.0',
    architecture: '',
    bitness: '',
    model: '',
  },
  {
    id: 'android-firefox-128',
    name: 'Firefox 128 (Android 14)',
    userAgent:
      'Mozilla/5.0 (Android 14; Mobile; rv:128.0) Gecko/128.0 Firefox/128.0',
    platform: 'Linux armv81',
    vendor: '',
    vendorSub: '',
    appVersion: '5.0 (Android 14)',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20100101',
    oscpu: 'Linux armv81',
    buildID: '20240709091000',
    mobile: true,
    platformName: 'Android',
    platformVersion: '14.0',
    architecture: '',
    bitness: '',
    model: '',
  },
];

// ============================================================================
// OPERA MOBILE PROFILES
// ============================================================================
const OPERA_MOBILE_PROFILES: UserAgentProfile[] = [
  {
    id: 'android-opera-80',
    name: 'Opera Mobile 80 (Android 14)',
    userAgent:
      'Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36 OPR/80.0.4170.74',
    platform: 'Linux armv81',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36 OPR/80.0.4170.74',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'Android',
    platformVersion: '14.0.0',
    architecture: '',
    bitness: '',
    model: 'SM-S921B',
    brands: [
      { brand: 'Chromium', version: '122' },
      { brand: 'Not(A:Brand', version: '24' },
      { brand: 'Opera', version: '80' },
    ],
  },
  {
    id: 'android-opera-81',
    name: 'Opera Mobile 81 (Android 14)',
    userAgent:
      'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.123 Mobile Safari/537.36 OPR/81.0.4292.50',
    platform: 'Linux armv81',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.123 Mobile Safari/537.36 OPR/81.0.4292.50',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'Android',
    platformVersion: '14.0.0',
    architecture: '',
    bitness: '',
    model: 'Pixel 8',
    brands: [
      { brand: 'Chromium', version: '124' },
      { brand: 'Not-A.Brand', version: '99' },
      { brand: 'Opera', version: '81' },
    ],
  },
];

// ============================================================================
// EDGE MOBILE PROFILES
// ============================================================================
const EDGE_MOBILE_PROFILES: UserAgentProfile[] = [
  {
    id: 'android-edge-124',
    name: 'Edge Mobile 124 (Android 14)',
    userAgent:
      'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.123 Mobile Safari/537.36 EdgA/124.0.2478.62',
    platform: 'Linux armv81',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.123 Mobile Safari/537.36 EdgA/124.0.2478.62',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'Android',
    platformVersion: '14.0.0',
    architecture: '',
    bitness: '',
    model: 'Pixel 8',
    brands: [
      { brand: 'Chromium', version: '124' },
      { brand: 'Microsoft Edge', version: '124' },
      { brand: 'Not-A.Brand', version: '99' },
    ],
  },
  {
    id: 'android-edge-126',
    name: 'Edge Mobile 126 (Android 14)',
    userAgent:
      'Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.122 Mobile Safari/537.36 EdgA/126.0.2592.56',
    platform: 'Linux armv81',
    vendor: 'Google Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.122 Mobile Safari/537.36 EdgA/126.0.2592.56',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'Android',
    platformVersion: '14.0.0',
    architecture: '',
    bitness: '',
    model: 'SM-S921B',
    brands: [
      { brand: 'Not/A)Brand', version: '8' },
      { brand: 'Chromium', version: '126' },
      { brand: 'Microsoft Edge', version: '126' },
    ],
  },
];

// ============================================================================
// IOS SAFARI PROFILES (iOS 17.3, 17.4, 18.0 + iPadOS 17, 18)
// ============================================================================
const IOS_SAFARI_PROFILES: UserAgentProfile[] = [
  {
    id: 'ios-safari-17.3',
    name: 'Safari (iOS 17.3)',
    userAgent:
      'Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1',
    platform: 'iPhone',
    vendor: 'Apple Computer, Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'iOS',
    platformVersion: '17.3',
    architecture: '',
    bitness: '',
    model: 'iPhone',
  },
  {
    id: 'ios-safari-17.4',
    name: 'Safari (iOS 17.4)',
    userAgent:
      'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
    platform: 'iPhone',
    vendor: 'Apple Computer, Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'iOS',
    platformVersion: '17.4',
    architecture: '',
    bitness: '',
    model: 'iPhone',
  },
  {
    id: 'ios-safari-17.5',
    name: 'Safari (iOS 17.5)',
    userAgent:
      'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
    platform: 'iPhone',
    vendor: 'Apple Computer, Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'iOS',
    platformVersion: '17.5',
    architecture: '',
    bitness: '',
    model: 'iPhone',
  },
  {
    id: 'ios-safari-18.0',
    name: 'Safari (iOS 18.0)',
    userAgent:
      'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1',
    platform: 'iPhone',
    vendor: 'Apple Computer, Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'iOS',
    platformVersion: '18.0',
    architecture: '',
    bitness: '',
    model: 'iPhone',
  },
  {
    id: 'ios-safari-18.1',
    name: 'Safari (iOS 18.1)',
    userAgent:
      'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1',
    platform: 'iPhone',
    vendor: 'Apple Computer, Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'iOS',
    platformVersion: '18.1',
    architecture: '',
    bitness: '',
    model: 'iPhone',
  },
  // iPadOS profiles
  {
    id: 'ipad-safari-17',
    name: 'Safari (iPadOS 17)',
    userAgent:
      'Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
    platform: 'iPad',
    vendor: 'Apple Computer, Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'iOS',
    platformVersion: '17.4',
    architecture: '',
    bitness: '',
    model: 'iPad',
  },
  {
    id: 'ipad-safari-17.5',
    name: 'Safari (iPadOS 17.5)',
    userAgent:
      'Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
    platform: 'iPad',
    vendor: 'Apple Computer, Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'iOS',
    platformVersion: '17.5',
    architecture: '',
    bitness: '',
    model: 'iPad',
  },
  {
    id: 'ipad-safari-18',
    name: 'Safari (iPadOS 18)',
    userAgent:
      'Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1',
    platform: 'iPad',
    vendor: 'Apple Computer, Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: true,
    platformName: 'iOS',
    platformVersion: '18.0',
    architecture: '',
    bitness: '',
    model: 'iPad',
  },
  // iPadOS Desktop mode (reports as Mac)
  {
    id: 'ipad-safari-17-desktop',
    name: 'Safari (iPadOS 17 Desktop Mode)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
    platform: 'MacIntel',
    vendor: 'Apple Computer, Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '17.4',
    architecture: '',
    bitness: '',
    model: '',
  },
  {
    id: 'ipad-safari-18-desktop',
    name: 'Safari (iPadOS 18 Desktop Mode)',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15',
    platform: 'MacIntel',
    vendor: 'Apple Computer, Inc.',
    vendorSub: '',
    appVersion:
      '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15',
    appName: 'Netscape',
    appCodeName: 'Mozilla',
    product: 'Gecko',
    productSub: '20030107',
    mobile: false,
    platformName: 'macOS',
    platformVersion: '18.0',
    architecture: '',
    bitness: '',
    model: '',
  },
];

// ============================================================================
// ALL PROFILES COMBINED (150+ profiles)
// ============================================================================
export const ALL_PROFILES: UserAgentProfile[] = [
  ...WINDOWS_CHROME_PROFILES,
  ...WINDOWS_FIREFOX_PROFILES,
  ...WINDOWS_EDGE_PROFILES,
  ...MACOS_EDGE_PROFILES,
  ...MACOS_CHROME_PROFILES,
  ...MACOS_SAFARI_PROFILES,
  ...MACOS_FIREFOX_PROFILES,
  ...LINUX_CHROME_PROFILES,
  ...LINUX_FIREFOX_PROFILES,
  ...OPERA_PROFILES,
  ...BRAVE_PROFILES,
  ...VIVALDI_PROFILES,
  ...ANDROID_CHROME_PROFILES,
  ...ANDROID_TABLET_PROFILES,
  ...SAMSUNG_INTERNET_PROFILES,
  ...FIREFOX_MOBILE_PROFILES,
  ...OPERA_MOBILE_PROFILES,
  ...EDGE_MOBILE_PROFILES,
  ...IOS_SAFARI_PROFILES,
];

// ============================================================================
// PROFILES BY CATEGORY FOR UI SELECTION
// ============================================================================
export const PROFILES_BY_OS = {
  windows: [
    ...WINDOWS_CHROME_PROFILES,
    ...WINDOWS_FIREFOX_PROFILES,
    ...WINDOWS_EDGE_PROFILES,
  ],
  macos: [
    ...MACOS_CHROME_PROFILES,
    ...MACOS_SAFARI_PROFILES,
    ...MACOS_FIREFOX_PROFILES,
    ...MACOS_EDGE_PROFILES,
  ],
  linux: [...LINUX_CHROME_PROFILES, ...LINUX_FIREFOX_PROFILES],
  android: [
    ...ANDROID_CHROME_PROFILES,
    ...ANDROID_TABLET_PROFILES,
    ...SAMSUNG_INTERNET_PROFILES,
    ...FIREFOX_MOBILE_PROFILES,
    ...OPERA_MOBILE_PROFILES,
    ...EDGE_MOBILE_PROFILES,
  ],
  ios: [...IOS_SAFARI_PROFILES],
};

export const PROFILES_BY_BROWSER = {
  chrome: [
    ...WINDOWS_CHROME_PROFILES,
    ...MACOS_CHROME_PROFILES,
    ...LINUX_CHROME_PROFILES,
    ...ANDROID_CHROME_PROFILES,
    ...ANDROID_TABLET_PROFILES,
  ],
  firefox: [
    ...WINDOWS_FIREFOX_PROFILES,
    ...MACOS_FIREFOX_PROFILES,
    ...LINUX_FIREFOX_PROFILES,
    ...FIREFOX_MOBILE_PROFILES,
  ],
  safari: [...MACOS_SAFARI_PROFILES, ...IOS_SAFARI_PROFILES],
  edge: [...WINDOWS_EDGE_PROFILES, ...MACOS_EDGE_PROFILES, ...EDGE_MOBILE_PROFILES],
  opera: [...OPERA_PROFILES, ...OPERA_MOBILE_PROFILES],
  brave: [...BRAVE_PROFILES],
  vivaldi: [...VIVALDI_PROFILES],
  samsung: [...SAMSUNG_INTERNET_PROFILES],
};

// Desktop-only profiles (for when mobile doesn't make sense)
export const DESKTOP_PROFILES: UserAgentProfile[] = ALL_PROFILES.filter((p) => !p.mobile);

// Mobile-only profiles
export const MOBILE_PROFILES: UserAgentProfile[] = ALL_PROFILES.filter((p) => p.mobile);

/**
 * Get a profile by ID
 */
export function getProfileById(id: string): UserAgentProfile | undefined {
  return ALL_PROFILES.find((p) => p.id === id);
}

/**
 * Get a random profile using PRNG
 */
export function getRandomProfile(
  prng: { nextInt: (min: number, max: number) => number },
  filter?: { mobileOnly?: boolean; desktopOnly?: boolean; os?: string; browser?: string }
): UserAgentProfile {
  let profiles = ALL_PROFILES;

  if (filter?.mobileOnly) {
    profiles = MOBILE_PROFILES;
  } else if (filter?.desktopOnly) {
    profiles = DESKTOP_PROFILES;
  }

  if (filter?.os && filter.os in PROFILES_BY_OS) {
    profiles = profiles.filter((p) =>
      PROFILES_BY_OS[filter.os as keyof typeof PROFILES_BY_OS].includes(p)
    );
  }

  if (filter?.browser && filter.browser in PROFILES_BY_BROWSER) {
    profiles = profiles.filter((p) =>
      PROFILES_BY_BROWSER[filter.browser as keyof typeof PROFILES_BY_BROWSER].includes(p)
    );
  }

  // Fallback to all profiles if filter results in empty
  if (profiles.length === 0) {
    profiles = ALL_PROFILES;
  }

  const index = prng.nextInt(0, profiles.length - 1);
  return profiles[index];
}
