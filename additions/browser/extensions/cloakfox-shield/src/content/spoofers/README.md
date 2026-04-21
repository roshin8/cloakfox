# ISOLATED-world spoofers (Phase 3)

**Status:** scaffolded 2026-04-21 with one proof-of-concept
(`example-native-getter.ts`). Rest of the JS spoofers in
`src/inject/spoofers/` still run in MAIN world and install visible
prototype overrides — see PENDING.md for the migration list.

## Why ISOLATED

After the stealth pass (commits 0515533ae5 … 67f6ffcbce), Cloakfox's
*presence* is undetectable from page MAIN:

- Every C++ WebIDL setter is `[Func="IsCloakfoxShieldCaller"]` —
  invisible unless the caller principal contains the addon.
- The ISOLATED→MAIN config bridge is a documentElement attribute
  removed synchronously before any page `<script>` runs.
- No sessionStorage, no postMessage, no CustomEvent, no window globals.

What's still detectable is the *JS spoofer machinery itself* — when
`initCanvasSpoofer` / `initNavigatorSpoofer` / … run in MAIN, they
install `Object.defineProperty` getters that leak via:

- `Object.getOwnPropertyDescriptor(navigator, 'userAgent').get.toString()`
  — unless `Function.prototype.toString` is patched (arms race).
- Descriptor placement: a getter on the instance when it was native on
  the prototype, or vice-versa.
- Stack traces from thrown errors inside the getter include the
  extension's bundled file path.
- Proxy trap coherence failures (`Object.prototype.toString`,
  structured clone, etc.).

## Pattern

Move each JS spoofer to `content/spoofers/` and use Firefox's
`exportFunction(func, targetScope)` to plant the getter from ISOLATED
into MAIN's compartment. The exported function:

- Has `.toString()` returning `function <name>() { [native code] }`
  (when created with a `name` property before export — verify per-case).
- Carries no closure-over-extension-file references; stack traces point
  into the page's own code, not `moz-extension://...`.
- Is immune to the `overrideGetter.toString` inspection class entirely.

### Template (from `example-native-getter.ts`)

```ts
declare const exportFunction: any;

export function installGetterInMain(
  pageWin: any,
  targetProto: any,      // e.g. pageWin.Navigator.prototype
  name: string,
  valueFn: () => any,
): void {
  const exported = exportFunction(valueFn, pageWin);
  Object.defineProperty(targetProto, name, {
    get: exported,
    configurable: true,
    enumerable: true,
  });
}
```

### Skip gating

`content/index.ts` populates the `handled` set in the bridge payload
before writing the attribute; MAIN's `initializeSpoofers` skips any
signal present in `preCoreHandled`. Same mechanism C++ uses today.
Each migrated spoofer adds its signal name to `handled` here so MAIN
won't double-install.

## Migration list

See PENDING.md §"Phase 3 JS→ISOLATED migration" for the full per-file
list and priority ordering.
