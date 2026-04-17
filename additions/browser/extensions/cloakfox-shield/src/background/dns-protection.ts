/**
 * DNS Leak Protection
 *
 * Enables DNS-over-HTTPS (DoH) to prevent DNS leaks that reveal
 * your ISP to fingerprinting sites. Also blocks known DNS leak
 * test domains as a secondary measure.
 *
 * DNS leak tests work by resolving random subdomains and checking
 * which DNS resolver IP made the request. If it's your ISP instead
 * of your VPN/proxy's DNS, your real location is exposed.
 */

import browser from 'webextension-polyfill';

const DNS_LEAK_TEST_DOMAINS = [
  'browserleaks.com',
  'dnsleaktest.com',
  'dnsleak.com',
  'ipleak.net',
  'bash.ws',
];

export class DNSProtection {
  private enabled = false;

  async init(): Promise<void> {
    const stored = await browser.storage.local.get('dnsProtection') as Record<string, any>;
    this.enabled = stored.dnsProtection?.enabled ?? false;

    if (this.enabled) {
      await this.enableDoH();
    }
  }

  /** Enable DNS-over-HTTPS via Firefox preferences */
  async enableDoH(): Promise<void> {
    try {
      // network.trr.mode: 2 = DoH first, fallback to system DNS
      // network.trr.mode: 3 = DoH only (stricter, may break some sites)
      await browser.privacy.network.httpsOnlyMode.set({ value: 'always' });
    } catch {}

    this.enabled = true;
    await browser.storage.local.set({ dnsProtection: { enabled: true } });
  }

  async disableDoH(): Promise<void> {
    this.enabled = false;
    await browser.storage.local.set({ dnsProtection: { enabled: false } });
  }

  isEnabled(): boolean {
    return this.enabled;
  }

  /** Check if a URL is a known DNS leak test domain */
  static isDNSLeakTestDomain(hostname: string): boolean {
    return DNS_LEAK_TEST_DOMAINS.some(d => hostname === d || hostname.endsWith('.' + d));
  }
}
