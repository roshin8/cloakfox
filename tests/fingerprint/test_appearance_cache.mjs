import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import vm from "node:vm";

// Execute the shipping module against real temporary files. Only platform
// helpers (plist/signing/Finder) are replaced; cache and replacement logic run.
async function harness(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "appearance-cache-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const source = path.join(root, "Cloakfox.app"), profile = path.join(root, "profile"), local = path.join(root, "cache");
  const put = async (name, value) => {
    const target = path.join(source, name);
    await fs.mkdir(path.dirname(target), { recursive: true }); await fs.writeFile(target, value);
  };
  await fs.mkdir(profile); await fs.mkdir(local);
  await put("Contents/Info.plist", JSON.stringify({ CFBundleName: "Cloakfox", CFBundleExecutable: "cloakfox", CFBundleIdentifier: "org.mozilla.cloakfox" }));
  await put("Contents/MacOS/cloakfox", "binary");
  await put("Contents/Resources/browser/appearance/firefox.icns", "icon");
  await put("Contents/Resources/payload", "original");
  let active = source, copies = 0, failSign = false, failInstall = false, revealed;
  const digest = async name => crypto.createHash("sha256").update(await fs.readFile(name)).digest("hex");
  const sealPath = app => path.join(app, "Contents/_CodeSignature/CodeResources");
  async function manifest(app) {
    const values = [];
    const walk = async dir => {
      for (const name of (await fs.readdir(dir)).sort()) {
        const p = path.join(dir, name);
        if (p === sealPath(app)) continue;
        if ((await fs.stat(p)).isDirectory()) await walk(p);
        else values.push([path.relative(app, p), await digest(p)]);
      }
    };
    await walk(app); return JSON.stringify(values);
  }
  const sign = async app => {
    await fs.mkdir(path.dirname(sealPath(app)), { recursive: true });
    await fs.writeFile(sealPath(app), await manifest(app));
  };
  await sign(source);
  const IOUtils = {
    exists: async p => !!(await fs.stat(p).catch(() => null)),
    readJSON: async p => JSON.parse(await fs.readFile(p, "utf8")),
    writeJSON: (p, v) => fs.writeFile(p, JSON.stringify(v)),
    readUTF8: p => fs.readFile(p, "utf8"), writeUTF8: (p, v) => fs.writeFile(p, v),
    computeHexDigest: digest,
    stat: async p => ({ type: (await fs.stat(p)).isDirectory() ? "directory" : "regular" }),
    getChildren: async p => (await fs.readdir(p)).map(n => path.join(p, n)),
    makeDirectory: (p, options = {}) => fs.mkdir(p, { recursive: !!options.ignoreExisting }),
    copy: (a, b) => fs.copyFile(a, b),
    remove: (p, options = {}) => fs.rm(p, { recursive: !!options.recursive, force: !!options.ignoreAbsent }),
    move: async (a, b, options = {}) => {
      if (failInstall && a.endsWith(".app") && b.endsWith("/Firefox.app")) {
        failInstall = false; throw new Error("installation failed");
      }
      if (options.noOverwrite && await IOUtils.exists(b)) throw new Error("destination exists");
      await fs.rename(a, b);
    },
  };
  const context = vm.createContext({
    IOUtils, AppConstants: { platform: "macosx" }, TextEncoder, TextDecoder,
    PathUtils: { join: path.join, parent: path.dirname, filename: path.basename, isAbsolute: path.isAbsolute,
      profileDir: profile, localProfileDir: local },
    Services: {
      dirsvc: { get: () => ({ parent: { parent: { parent: { path: active } } } }) },
      uuid: { generateUUID: () => crypto.randomUUID() }, appinfo: { version: "146.0.1" },
    },
    Ci: { nsIFile: {}, nsICryptoHash: {} },
    Cc: {
      "@mozilla.org/file/local;1": { createInstance: () => ({ initWithPath(p) { this.path = p; }, reveal() { revealed = this.path; } }) },
      "@mozilla.org/security/hash;1": { createInstance: () => ({
        SHA256: 1, init() { this.hash = crypto.createHash("sha256"); },
        update(bytes) { this.hash.update(bytes); }, finish() { return this.hash.digest("base64"); },
      }) },
    },
    platformRun: async (command, args, input) => {
      if (command === "/usr/bin/plutil") {
        if (input !== undefined) { await fs.writeFile(args[3], input); return ""; }
        return fs.readFile(args.at(-1), "utf8");
      }
      if (command === "/bin/cp") { copies++; await fs.cp(args.at(-2), args.at(-1), { recursive: true }); }
      else if (command === "/usr/bin/codesign") {
        const app = args.at(-1);
        if (args.includes("--sign")) {
          if (failSign) throw new Error("signing failed");
          await sign(app);
        } else if (await fs.readFile(sealPath(app), "utf8") !== await manifest(app)) throw new Error("invalid signature");
      } else assert.equal(command, "/usr/bin/xattr");
      return "";
    },
  });
  const code = await fs.readFile(new URL("../../additions/browser/components/cloakfox/CloakfoxAppearance.sys.mjs", import.meta.url), "utf8");
  vm.runInContext(code.replace(/^import .*;\n/gm, "").replace(/^export /gm, "") +
    "\nrun = platformRun; globalThis.api = {prepareAppearance, getAppearance, revealAppearance};", context);
  return { api: context.api, source, profile, local, put, signSource: () => sign(source),
    setActive(value) { active = value; }, setFailSign(value) { failSign = value; },
    failInstall() { failInstall = true; }, get copies() { return copies; }, get revealed() { return revealed; } };
}

test("unchanged source reuses one signed app and its owning profile", async t => {
  const h = await harness(t);
  const [a, b] = await Promise.all([h.api.prepareAppearance(true), h.api.prepareAppearance(true)]);
  assert.deepEqual(a, b); assert.equal(h.copies, 1);
  const seal = path.join(a.app, "Contents/_CodeSignature/CodeResources");
  const before = await fs.stat(seal);
  assert.deepEqual(await h.api.prepareAppearance(true), a);
  assert.equal((await fs.stat(seal)).mtimeMs, before.mtimeMs); assert.equal(h.copies, 1);
  assert.equal(a.app, path.join(h.local, "cloakfox-appearance/Firefox.app"));
  assert.equal(await fs.readFile(path.join(a.app, "Contents/Resources/cloakfox-profile.ini"), "utf8"),
    `[CloakfoxProfile]\nRoot=${h.profile}\nLocal=${h.local}\n`);
  h.setActive(a.app); await h.api.revealAppearance(); assert.equal(h.revealed, a.app);
});

test("sealed and loose payload updates rebuild at the same path", async t => {
  const h = await harness(t), a = await h.api.prepareAppearance(true);
  await h.put("Contents/Resources/payload", "updated signed app"); await h.signSource();
  assert.deepEqual(await h.api.prepareAppearance(true), a); assert.equal(h.copies, 2);
  await h.put("Contents/Resources/payload", "loose development edit");
  assert.deepEqual(await h.api.prepareAppearance(true), a); assert.equal(h.copies, 3);
  assert.equal(await fs.readFile(path.join(a.app, "Contents/Resources/payload"), "utf8"), "loose development edit");
  await h.api.prepareAppearance(true); assert.equal(h.copies, 3);
});

test("failed signing and failed installation retain the working copy", async t => {
  const h = await harness(t), a = await h.api.prepareAppearance(true);
  const marker = path.join(a.app, "Contents/Resources/cloakfox-appearance.json");
  const before = await fs.readFile(marker, "utf8");
  await h.put("Contents/Resources/payload", "update"); await h.signSource();
  h.setFailSign(true); await assert.rejects(h.api.prepareAppearance(true), /signing failed/);
  h.setFailSign(false); h.failInstall(); await assert.rejects(h.api.prepareAppearance(true), /installation failed/);
  assert.equal(await fs.readFile(marker, "utf8"), before);
  assert.deepEqual(await fs.readdir(path.dirname(a.app)), ["Firefox.app"]);
  await h.api.prepareAppearance(true);
  assert.equal(await fs.readFile(path.join(a.app, "Contents/Resources/payload"), "utf8"), "update");
});

test("an active app cannot be replaced; a damaged inactive copy is rebuilt", async t => {
  const h = await harness(t), a = await h.api.prepareAppearance(true);
  await fs.writeFile(path.join(a.app, "Contents/Resources/payload"), "damage");
  h.setActive(a.app); await assert.rejects(h.api.prepareAppearance(true), /Restart in Cloakfox appearance/);
  assert.equal(h.copies, 1);
  h.setActive(h.source); await h.api.prepareAppearance(true); assert.equal(h.copies, 2);
  assert.equal(await fs.readFile(path.join(a.app, "Contents/Resources/payload"), "utf8"), "original");
});
