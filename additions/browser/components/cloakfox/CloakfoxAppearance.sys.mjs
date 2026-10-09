/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// Cosmetic macOS branding. The engine, profile identity and privacy preferences
// stay Cloakfox's. Only a private app copy is modified; never the installation.
import { AppConstants } from "resource://gre/modules/AppConstants.sys.mjs";
import { Subprocess } from "resource://gre/modules/Subprocess.sys.mjs";

const PREF = "cloakfox.appearance.firefox";
const MARKER = "cloakfox-appearance.json";
const SCHEMA = 1;
const ADDON_ID = "cloakfox-shield@cloakfox";
const ADDON_PATH = "/builtin-addons/cloakfox-shield/";
const FIREFOX_ADDON_PATH = "/builtin-addons/firefox-panel/";
let preparing;

function file(path) {
  const value = Cc["@mozilla.org/file/local;1"].createInstance(Ci.nsIFile);
  value.initWithPath(path);
  return value;
}

async function run(command, args, input) {
  const proc = await Subprocess.call({command, arguments: args, stderr: "pipe"});
  const read = async pipe => {
    let output = "", chunk;
    while ((chunk = await pipe.readString())) output += chunk;
    return output;
  };
  const output = read(proc.stdout), errors = read(proc.stderr);
  if (input !== undefined) await proc.stdin.write(input);
  try { await proc.stdin.close(); }
  catch (error) {
    // Fast helpers can exit and close stdin before our close request arrives.
    // Their exit status and output still determine success below.
    if (error.errorCode !== Subprocess.ERROR_END_OF_FILE) throw error;
  }
  const [{exitCode}, stdout, stderr] = await Promise.all([proc.wait(), output, errors]);
  if (exitCode) throw new Error(`${PathUtils.filename(command)} failed: ${stderr.trim()}`);
  return stdout;
}

async function readPlist(path) {
  return JSON.parse(await run("/usr/bin/plutil", ["-convert", "json", "-o", "-", path]));
}

async function writePlist(path, value) {
  await run("/usr/bin/plutil", ["-convert", "xml1", "-o", path, "-"], JSON.stringify(value));
}

export async function getAppearance() {
  if (AppConstants.platform !== "macosx") return {supported: false, active: false};
  const app = Services.dirsvc.get("XREExeF", Ci.nsIFile).parent.parent.parent.path;
  if (!app.endsWith(".app")) throw new Error("Appearance switching needs a macOS app bundle.");
  const marker = PathUtils.join(app, "Contents", "Resources", MARKER);
  const metadata = await IOUtils.exists(marker) ? await IOUtils.readJSON(marker) : null;
  if (metadata && (metadata.schema !== SCHEMA || !PathUtils.isAbsolute(metadata.sourceApp))) {
    throw new Error("This appearance copy has invalid source information.");
  }
  return {supported: true, active: !!metadata, app, sourceApp: metadata?.sourceApp || app};
}

const BRAND_IMAGES = [
  "about.png", "about-logo.png", "about-logo.svg", "about-logo@2x.png",
  "about-wordmark.svg", "firefox-wordmark.svg", "aboutDialog.css",
  "icon16.png", "icon32.png", "icon48.png", "icon64.png", "icon128.png",
];

function replacementAsset(entry, assets) {
  const name = entry.split("/").pop();
  if (entry.includes(ADDON_PATH) && /\/icons\/icon-(48|128)\.png$/.test(entry)) {
    return PathUtils.join(assets, name.replace("icon-", "icon"));
  }
  return entry.includes("/content/branding/") && BRAND_IMAGES.includes(name)
    ? PathUtils.join(assets, name) : null;
}

function isBrandText(entry) {
  return /\/branding\/brand\.(ftl|properties|dtd)$/.test(entry) ||
    entry.endsWith("/cloakfox/settings.html") ||
    entry.endsWith("/built_in_addons.json") ||
    (entry.includes(ADDON_PATH) &&
     /\/(manifest\.json|popup\.(html|css|js))$/.test(entry));
}

function brandText(entry, text) {
  if (entry.endsWith("/built_in_addons.json")) {
    const manifest = JSON.parse(text);
    const addon = manifest.builtins?.find(item => item.addon_id === ADDON_ID);
    if (!addon) throw new Error("The bundled toolbar extension is missing.");
    // A different resource root makes Gecko reload this built-in's metadata
    // and startup cache even with the same ID/version/build. Switching back
    // reloads the original root without clearing other add-ons or profile data.
    addon.res_url = "resource://builtin-addons/firefox-panel/";
    return JSON.stringify(manifest);
  }
  if (entry.includes(ADDON_PATH) && entry.endsWith("/manifest.json")) {
    const manifest = JSON.parse(text);
    if (manifest.browser_specific_settings?.gecko?.id !== ADDON_ID) {
      throw new Error("Unexpected bundled toolbar extension identity.");
    }
    manifest.name = "Firefox";
    manifest.description = "Controls for container settings.";
    manifest.browser_action.default_title = "Firefox";
    manifest.commands._execute_browser_action.description = "Open Firefox popup";
    delete manifest.author;
    delete manifest.homepage_url;
    return JSON.stringify(manifest);
  }
  text = text.replaceAll("Cloakfox", "Firefox");
  if (entry.includes(ADDON_PATH) && entry.endsWith("/popup.html")) {
    text = text.replace('<span class="brand-mark">⬢</span>',
                        '<img class="brand-mark" src="../icons/icon-48.png" alt="">');
  } else if (entry.includes(ADDON_PATH) && entry.endsWith("/popup.css")) {
    text += "\n.brand-mark { background: transparent; border-radius: 0; object-fit: contain; }\n";
  }
  return text;
}

async function brandArchive(path, assets, scratch) {
  // Packaged omni.ja is an optimized ZIP with its central directory first.
  // nsIZipWriter cannot safely edit that layout. Write a fresh ordinary ZIP.
  const reader = Cc["@mozilla.org/libjar/zip-reader;1"].createInstance(Ci.nsIZipReader);
  const writer = Cc["@mozilla.org/zipwriter;1"].createInstance(Ci.nsIZipWriter);
  const rebuilt = PathUtils.join(scratch, `${Services.uuid.generateUUID()}.ja`);
  reader.open(file(path));
  try {
    writer.open(file(rebuilt), 0x02 | 0x08 | 0x20); // WRONLY | CREATE | TRUNCATE
    try {
      const entries = reader.findEntries(null);
      while (entries.hasMore()) {
        const entry = entries.getNext();
        const brandedEntry = entry.replace(ADDON_PATH, FIREFOX_ADDON_PATH);
        const info = reader.getEntry(entry);
        if (info.isDirectory) {
          writer.addEntryDirectory(brandedEntry, info.lastModifiedTime, false);
          continue;
        }
        let asset = replacementAsset(entry, assets);
        if (!asset && isBrandText(entry)) {
          const stream = Cc["@mozilla.org/binaryinputstream;1"].createInstance(Ci.nsIBinaryInputStream);
          stream.setInputStream(reader.getInputStream(entry));
          let text;
          try { text = new TextDecoder().decode(Uint8Array.from(stream.readByteArray(stream.available()))); }
          finally { stream.close(); }
          asset = PathUtils.join(scratch, "brand.txt");
          await IOUtils.writeUTF8(asset, brandText(entry, text));
        }
        if (asset) {
          writer.addEntryFile(brandedEntry, Ci.nsIZipWriter.COMPRESSION_DEFAULT, file(asset), false);
        } else {
          const stream = reader.getInputStream(entry);
          try {
            writer.addEntryStream(brandedEntry, info.lastModifiedTime,
              Ci.nsIZipWriter.COMPRESSION_DEFAULT, stream, false);
          } finally { stream.close(); }
        }
      }
    } finally { writer.close(); }
  } finally { reader.close(); }
  await IOUtils.move(rebuilt, path);
}

async function brandLooseDirectory(path, assets) {
  if (!(await IOUtils.exists(path))) return;
  for (const child of await IOUtils.getChildren(path)) {
    const stat = await IOUtils.stat(child);
    if (stat.type === "directory") await brandLooseDirectory(child, assets);
    else if (isBrandText(child)) {
      const text = await IOUtils.readUTF8(child);
      await IOUtils.writeUTF8(child, brandText(child, text));
    } else {
      const replacement = replacementAsset(child, assets);
      if (replacement) await IOUtils.copy(replacement, child);
    }
  }
}

async function buildFirefoxCopy(status) {
  const source = status.sourceApp;
  const infoPath = PathUtils.join(source, "Contents", "Info.plist");
  const info = await readPlist(infoPath);
  if (info.CFBundleName !== "Cloakfox") throw new Error("The source must be a Cloakfox app bundle.");
  // Recreate on every switch from the current source. Dev-build JS and resource
  // changes need not update the build ID or Info.plist timestamp.
  const cache = PathUtils.join(PathUtils.localProfileDir, "cloakfox-appearance");
  const root = PathUtils.join(cache, Services.uuid.generateUUID().toString());
  if (root.startsWith(source + "/")) throw new Error("The profile must be outside the application bundle.");
  const app = PathUtils.join(root, "Firefox.app");
  const executable = PathUtils.join(app, "Contents", "MacOS", "firefox");
  await IOUtils.makeDirectory(root, {ignoreExisting: true});
  const stage = PathUtils.join(root, `${Services.uuid.generateUUID()}.app`);
  const scratch = PathUtils.join(root, `${Services.uuid.generateUUID()}.scratch`);
  await IOUtils.makeDirectory(scratch);
  try {
    // Materialize dev-build symlinks as well as packaged apps. Writing through
    // a copied symlink could otherwise modify the original source or bundle.
    // This is a newly created local app, not the downloaded source: do not
    // inherit its quarantine/provenance metadata or resource forks.
    await run("/bin/cp", ["-R", "-L", "-X", source, stage]);
    const resources = PathUtils.join(stage, "Contents", "Resources");
    const assets = PathUtils.join(resources, "browser", "appearance");
    await IOUtils.copy(PathUtils.join(assets, "firefox.icns"), PathUtils.join(resources, "firefox.icns"));
    for (const child of await IOUtils.getChildren(resources)) {
      if (child.endsWith(".lproj")) {
        const strings = PathUtils.join(child, "InfoPlist.strings");
        if (await IOUtils.exists(strings)) {
          const localized = await readPlist(strings);
          localized.CFBundleName = localized.CFBundleDisplayName = "Firefox";
          await writePlist(strings, localized);
        }
      }
    }
    await IOUtils.move(PathUtils.join(stage, "Contents", "MacOS", info.CFBundleExecutable),
                       PathUtils.join(stage, "Contents", "MacOS", "firefox"));
    info.CFBundleName = info.CFBundleDisplayName = "Firefox";
    info.CFBundleExecutable = "firefox";
    info.CFBundleIdentifier += ".appearance.firefox";
    info.CFBundleGetInfoString = `Firefox ${Services.appinfo.version}`;
    delete info.CFBundleIconName; // The original asset catalog must not win.
    await writePlist(PathUtils.join(stage, "Contents", "Info.plist"), info);
    for (const archive of [PathUtils.join(resources, "omni.ja"), PathUtils.join(resources, "browser", "omni.ja")]) {
      if (await IOUtils.exists(archive)) await brandArchive(archive, assets, scratch);
    }
    await brandLooseDirectory(PathUtils.join(resources, "browser", "chrome"), assets);
    await brandLooseDirectory(PathUtils.join(resources, "browser", "localization"), assets);
    // Development builds keep the same jar entries as loose files.
    const looseAddon = PathUtils.join(resources, "browser", "chrome", "browser",
                                     "builtin-addons", "cloakfox-shield");
    if (await IOUtils.exists(looseAddon)) {
      await IOUtils.move(looseAddon, PathUtils.join(PathUtils.parent(looseAddon), "firefox-panel"));
    }
    await IOUtils.writeJSON(PathUtils.join(resources, MARKER), {schema: SCHEMA, sourceApp: source});
    // A changed Info.plist invalidates the copied signature. Sign this local
    // variant, retaining executable entitlements; never alter the source app.
    await run("/usr/bin/codesign", ["--force", "--deep", "--sign", "-", "--preserve-metadata=entitlements,flags", stage]);
    // macOS also quarantines files newly created by a quarantining browser.
    // Clear that marker on this locally generated, signed copy only (the
    // native restart launcher applies the same treatment to local relaunches).
    await run("/usr/bin/xattr", ["-dr", "com.apple.quarantine", stage]);
    await IOUtils.move(stage, app, {noOverwrite: true});
    // Renaming into a browser-created directory can attach a new marker.
    await run("/usr/bin/xattr", ["-dr", "com.apple.quarantine", root]);
    for (const old of await IOUtils.getChildren(cache)) {
      if (old === root || status.app.startsWith(old + "/")) continue;
      const oldMarker = PathUtils.join(old, "Firefox.app", "Contents", "Resources", MARKER);
      if (await IOUtils.exists(oldMarker)) {
        const saved = await IOUtils.readJSON(oldMarker);
        if (saved.schema === SCHEMA && saved.sourceApp === source) {
          await IOUtils.remove(old, {recursive: true});
        }
      }
    }
    return {app, executable};
  } finally {
    await IOUtils.remove(stage, {recursive: true, ignoreAbsent: true});
    await IOUtils.remove(scratch, {recursive: true, ignoreAbsent: true});
  }
}

export async function prepareAppearance(enabled) {
  const status = await getAppearance();
  if (!status.supported) throw new Error("Application appearance switching is currently available on macOS.");
  if (!enabled) {
    const info = await readPlist(PathUtils.join(status.sourceApp, "Contents", "Info.plist"));
    const executable = PathUtils.join(status.sourceApp, "Contents", "MacOS", info.CFBundleExecutable);
    if (!(await IOUtils.exists(executable))) throw new Error("The original Cloakfox app is unavailable.");
    return {app: status.sourceApp, executable};
  }
  if (!preparing) preparing = buildFirefoxCopy(status).finally(() => { preparing = null; });
  return preparing;
}

export async function restartAppearance() {
  const cancel = Cc["@mozilla.org/supports-PRBool;1"].createInstance(Ci.nsISupportsPRBool);
  Services.obs.notifyObservers(cancel, "quit-application-requested", "restart");
  if (cancel.data) return {cancelled: true};
  const enabled = Services.prefs.getBoolPref(PREF, false);
  const target = await prepareAppearance(enabled);
  if (enabled !== Services.prefs.getBoolPref(PREF, false)) {
    throw new Error("The appearance setting changed while preparing. Try restarting again.");
  }
  Services.prefs.savePrefFile(null);
  Services.env.set("CLOAKFOX_RESTART_BUNDLE", target.app);
  let granted = false;
  const observer = () => { granted = true; };
  Services.obs.addObserver(observer, "quit-application-granted");
  try {
    Services.startup.quit(Ci.nsIAppStartup.eAttemptQuit | Ci.nsIAppStartup.eRestart);
  } finally {
    Services.obs.removeObserver(observer, "quit-application-granted");
    if (!granted) Services.env.set("CLOAKFOX_RESTART_BUNDLE", "");
  }
  return {cancelled: !granted, ...target};
}

export function initCloakfoxAppearance() {
  if (AppConstants.platform !== "macosx") return;
  const restored = () => {
    Services.obs.removeObserver(restored, "sessionstore-windows-restored");
    getAppearance().then(status => {
      // Starting the original app again honors the saved appearance. Wait for
      // session restoration before requesting another restart so tabs survive.
      if (status.active !== Services.prefs.getBoolPref(PREF, false)) return restartAppearance();
      return null;
    }).catch(error => Cu.reportError(`Cloakfox appearance: ${error.message}`));
  };
  Services.obs.addObserver(restored, "sessionstore-windows-restored");
}
