/**
 * Apple Pay Spoofer
 *
 * Spoofs ApplePaySession to prevent fingerprinting via Apple Pay availability detection.
 * This is Safari-specific but should be normalized across browsers.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize Apple Pay spoofing
 */
export function initApplePaySpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Check if ApplePaySession exists (Safari only)
  if ('ApplePaySession' in window) {
    const OriginalApplePaySession = (window as any).ApplePaySession;

    // Spoof canMakePayments
    if (OriginalApplePaySession.canMakePayments) {
      const originalCanMakePayments = OriginalApplePaySession.canMakePayments;

      OriginalApplePaySession.canMakePayments = function (): boolean {
        logAccess('ApplePaySession.canMakePayments', { spoofed: true });

        if (mode === 'block') {
          return false;
        }

        return originalCanMakePayments.call(OriginalApplePaySession);
      };
    }

    // Spoof canMakePaymentsWithActiveCard
    if (OriginalApplePaySession.canMakePaymentsWithActiveCard) {
      const originalCanMakePaymentsWithActiveCard =
        OriginalApplePaySession.canMakePaymentsWithActiveCard;

      OriginalApplePaySession.canMakePaymentsWithActiveCard = function (
        merchantIdentifier: string
      ): Promise<boolean> {
        logAccess('ApplePaySession.canMakePaymentsWithActiveCard', { spoofed: true });

        if (mode === 'block') {
          return Promise.resolve(false);
        }

        return originalCanMakePaymentsWithActiveCard.call(
          OriginalApplePaySession,
          merchantIdentifier
        );
      };
    }

    // Spoof supportsVersion
    if (OriginalApplePaySession.supportsVersion) {
      const originalSupportsVersion = OriginalApplePaySession.supportsVersion;

      OriginalApplePaySession.supportsVersion = function (version: number): boolean {
        logAccess('ApplePaySession.supportsVersion', { spoofed: true });

        if (mode === 'block') {
          return false;
        }

        return originalSupportsVersion.call(OriginalApplePaySession, version);
      };
    }

  } else {
    // For non-Safari browsers, we might want to add a fake ApplePaySession
    // to normalize the fingerprint (all browsers look the same - no Apple Pay)
    // This is optional and might not be needed
    if (mode === 'noise') {
      try {
        (window as any).ApplePaySession = undefined;
      } catch {
        // Can't set
      }
    }
  }

  // Also handle PaymentRequest API for Apple Pay detection
  if ('PaymentRequest' in window) {
    const OriginalPaymentRequest = (window as any).PaymentRequest;

    const PaymentRequestProxy = function (
      this: any,
      methodData: PaymentMethodData[],
      details: PaymentDetailsInit,
      options?: PaymentOptions
    ) {
      logAccess('PaymentRequest', { spoofed: mode === 'block' });

      // Filter out Apple Pay if blocking
      if (mode === 'block') {
        methodData = methodData.filter(
          (method) =>
            !method.supportedMethods.includes('https://apple.com/apple-pay')
        );
      }

      return new OriginalPaymentRequest(methodData, details, options);
    };

    PaymentRequestProxy.prototype = OriginalPaymentRequest.prototype;

    try {
      (window as any).PaymentRequest = PaymentRequestProxy;
    } catch {
      // Can't override
    }
  }
}
