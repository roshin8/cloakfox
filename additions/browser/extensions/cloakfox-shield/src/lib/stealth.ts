/**
 * Stealth Utilities - Makes function overrides undetectable
 *
 * CreepJS and fingerprint.com detect overrides via:
 * 1. Function.prototype.toString() - returns source code instead of "[native code]"
 * 2. Object.getOwnPropertyDescriptor() - descriptor flags differ from native
 * 3. __proto__ = null trick - Proxy objects fail when prototype is nulled
 * 4. "Illegal invocation" error message checks
 * 5. Property count checks on prototypes
 *
 * This module must be loaded BEFORE any spoofers to patch toString first.
 */

// Map of overridden functions/getters to their native-looking toString output
const nativeStrings = new WeakMap<object, string>();

// Save pristine references before anything else touches them
const _toString = Function.prototype.toString;
const _apply = Reflect.apply;
const _defineProperty = Object.defineProperty;
const _getOwnPropertyDescriptor = Object.getOwnPropertyDescriptor;

/**
 * Step 1: Patch Function.prototype.toString to return native-looking strings
 * for our overridden functions. This MUST run before any spoofers.
 */
export function initStealth(): void {
  // Override toString using a Proxy so it preserves native-like behavior
  const handler: ProxyHandler<typeof _toString> = {
    apply(target, thisArg, args) {
      // Check if this function has a registered native string
      if (thisArg && nativeStrings.has(thisArg)) {
        return nativeStrings.get(thisArg);
      }
      // Fall through to original toString
      return _apply(target, thisArg, args);
    },
  };

  const toStringProxy = new Proxy(_toString, handler);

  // Register toString itself as native-looking
  nativeStrings.set(toStringProxy, 'function toString() { [native code] }');

  _defineProperty(Function.prototype, 'toString', {
    value: toStringProxy,
    writable: true,
    configurable: true,
  });
}

/**
 * Register a function as native-looking for toString detection.
 */
export function registerNative(fn: object, name: string): void {
  nativeStrings.set(fn, `function ${name}() { [native code] }`);
}

/**
 * Override a prototype method stealthily.
 * The replacement function receives (originalFn, thisArg, args).
 */
export function overrideMethod<T extends object>(
  proto: T,
  methodName: string,
  handler: (original: Function, thisArg: any, args: any[]) => any
): void {
  const original = (proto as any)[methodName];
  if (typeof original !== 'function') return;

  const proxy = new Proxy(original, {
    apply(_target, thisArg, args) {
      return handler(original, thisArg, args);
    },
  });

  // Preserve native-looking toString
  registerNative(proxy, methodName);

  _defineProperty(proto, methodName, {
    value: proxy,
    writable: true,
    configurable: true,
    enumerable: true,
  });
}

/**
 * Override a getter on a prototype stealthily.
 * The override lives on the PROTOTYPE (not instance) to match native behavior.
 * Preserves the original descriptor flags exactly.
 */
export function overrideGetter<T extends object>(
  proto: T,
  propName: string,
  handler: (originalGetter: () => any, thisArg: any) => any
): void {
  const desc = _getOwnPropertyDescriptor(proto, propName);
  if (!desc?.get) return;

  const originalGet = desc.get;

  const getterProxy = new Proxy(originalGet, {
    apply(_target, thisArg, _args) {
      return handler(originalGet, thisArg);
    },
  });

  registerNative(getterProxy, `get ${propName}`);

  _defineProperty(proto, propName, {
    get: getterProxy,
    set: desc.set,
    enumerable: desc.enumerable,
    configurable: desc.configurable,
  });
}

/**
 * Override a getter on a prototype and also add a setter (for read-only spoofing).
 * Used for properties like screen.width that need a fake value.
 */
export function overrideGetterWithValue<T extends object>(
  proto: T,
  propName: string,
  getValue: () => any
): void {
  const desc = _getOwnPropertyDescriptor(proto, propName);
  if (!desc) return;

  if (desc.get) {
    const getterProxy = new Proxy(desc.get, {
      apply() {
        return getValue();
      },
    });
    registerNative(getterProxy, `get ${propName}`);

    _defineProperty(proto, propName, {
      get: getterProxy,
      set: desc.set,
      enumerable: desc.enumerable,
      configurable: desc.configurable,
    });
  } else {
    // Data property - use getter to make it look native
    _defineProperty(proto, propName, {
      get() { return getValue(); },
      enumerable: desc.enumerable ?? true,
      configurable: desc.configurable ?? true,
    });
  }
}

/**
 * Override a property on an instance with a value, matching native descriptor shape.
 * Only use this for properties that are natively own properties (rare).
 */
export function overrideValue<T extends object>(
  obj: T,
  propName: string,
  value: any
): void {
  const desc = _getOwnPropertyDescriptor(obj, propName) ||
    _getOwnPropertyDescriptor(Object.getPrototypeOf(obj), propName);

  _defineProperty(obj, propName, {
    value,
    writable: desc?.writable ?? true,
    enumerable: desc?.enumerable ?? true,
    configurable: desc?.configurable ?? true,
  });
}
