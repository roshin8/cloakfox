/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
import { Subprocess } from "resource://gre/modules/Subprocess.sys.mjs";
import { setTimeout } from "resource://gre/modules/Timer.sys.mjs";

const sessions = new Map();
const owners = new WeakMap();
const native = () => Cc["@cloakfox.org/engine-host;1"].getService(Ci.nsICloakfoxEngineHost);

function geometry(window, browser) {
  const rect = browser.getBoundingClientRect();
  const width = Math.max(1, Math.round(rect.width));
  const height = Math.max(1, Math.round(rect.height));
  // Match the bounded native transport and CEF surface exactly. Silently
  // clamping here would stretch pixels without scaling native input.
  if (!Number.isFinite(width) || !Number.isFinite(height) || width > 4096 || height > 4096) {
    throw new Error("Native viewport exceeds surface bounds");
  }
  return [Math.round(rect.x), Math.round(rect.y), width, height,
    window.gBrowser.selectedBrowser === browser];
}

function exactKeys(value, keys) {
  return value && typeof value === "object" && !Array.isArray(value) &&
    Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value,key));
}
function validEditingState(value) {
  if (!exactKeys(value,["field","editable","password","selection","composition","caret"]) ||
      typeof value.editable !== "boolean" || typeof value.password !== "boolean") return false;
  if (!value.editable) return !value.password &&
    ["field","selection","composition","caret"].every(key => value[key] === null);
  const field=value.field;
  if (!exactKeys(field,["document","node"]) || typeof field.document !== "string" ||
      !/^[0-9a-fA-F-]{1,128}$/.test(field.document) || !Number.isInteger(field.node) ||
      field.node < 1 || field.node > 2147483647) return false;
  for (const key of ["selection","composition"]) {
    const range=value[key];
    if (range === null) continue;
    if (!Array.isArray(range) || range.length !== 2 ||
        !range.every(n => Number.isInteger(n) && n >= 0 && n <= 2147483647) || range[1] < range[0]) return false;
  }
  return Array.isArray(value.caret) && value.caret.length === 4 && value.caret.every((n,index) =>
    Number.isInteger(n) && n >= (index < 2 ? -32768 : 0) && n <= (index < 2 ? 32768 : 4096));
}

class FixtureSession {
  constructor(window, browser) {
    this.window = window;
    this.browser = browser;
    this.serial = 0;
    this.buffer = "";
    this.queue = Promise.resolve();
    this.closed = false;
  }
  watchOwner() {
    this.onUnload = () => this.close();
    this.onTabClose = event => { if (event.target.linkedBrowser === this.browser) this.close(); };
    this.window.addEventListener("unload", this.onUnload, {once: true});
    this.window.gBrowser.tabContainer.addEventListener("TabClose", this.onTabClose);
  }
  assertOwner() {
    if (this.closed || this.window.closed || !this.browser.isConnected ||
        this.browser.ownerDocument !== this.window.document) throw new Error("Native viewport owner closed");
  }
  async stopProcess() {
    if (!this.process) return;
    await this.process.stdin.close().catch(() => {});
    await this.process.kill().catch(() => {});
  }
  async line() {
    for (;;) {
      const newline = this.buffer.indexOf("\n");
      if (newline >= 0) {
        if (newline > 1024 * 1024) throw new Error("Oversized native response");
        const line = this.buffer.slice(0, newline);
        this.buffer = this.buffer.slice(newline + 1);
        return JSON.parse(line);
      }
      if (this.buffer.length > 1024 * 1024) throw new Error("Oversized native response");
      const chunk = await this.process.stdout.readString();
      if (!chunk) throw new Error("Native engine disconnected");
      this.buffer += chunk;
    }
  }
  startReading() {
    if (this.reader) return;
    this.reader=(async () => {
      while (!this.closed) {
        const packet=await this.line();
        if (this.closed) return;
        if (packet.event === "crashed") throw new Error("Native renderer crashed");
        if (packet.event === "ownedImeInvalidated") {this.invalidateInputState(packet);continue;}
        if (packet.event === "ownedImeState") { this.applyInputState(packet); continue; }
        if (!Object.hasOwn(packet,"id")) continue;
        if (!this.pending || packet.id !== this.pending.id || packet.version !== 1 || typeof packet.ok !== "boolean")
          throw new Error("Unexpected native acknowledgement");
        const pending=this.pending;this.pending=null;
        if (packet.ok) pending.resolve(packet);
        else pending.reject(new Error(packet.error || "Native operation rejected"));
      }
    })().catch(async error => {
      const pending=this.pending;this.pending=null;pending?.reject(error);
      if (!this.closed) await this.close();
    });
  }
  invalidateInputState(packet) {
    if (packet.version!==1 || packet.browser!==this.browserId || !this.ownsInput(packet)) return;
    native().invalidateInputState(this.route.token,this.route.configRevision,this.route.viewportRevision);
    this.inputState=null;
    if (this.inputRefresh) this.inputRefreshDirty=true;
    else this.refreshInputState().catch(()=>this.close());
  }
  applyInputState(packet) {
    if (this.closed || !this.route || packet.browser !== this.browserId || packet.token !== this.route.token ||
        packet.configRevision !== this.route.configRevision || packet.viewportRevision !== this.route.viewportRevision) return;
    if (packet.version !== 1 || !validEditingState(packet.state)) throw new Error("Invalid native editing state");
    if (!this.ownsInput(packet)) return;
    const encoded=JSON.stringify(packet.state);
    this.inputState=JSON.parse(encoded);
    native().setInputState(this.route.token,this.route.configRevision,this.route.viewportRevision,encoded);
  }
  request(command, fields = {}) {
    const operation = this.queue.then(async () => {
      if (this.closed) throw new Error("Native viewport is closed");
      // The RPC queue can delay input past a tab/focus/viewport transition.
      if (command === "input" && !this.ownsInput(fields)) return {ignored: true};
      const id = ++this.serial;
      let pending;
      const response=new Promise((resolve,reject) => { pending={id,resolve,reject}; });
      this.pending=pending;
      this.startReading();
      try {
        const [packet]=await Promise.all([response,Promise.resolve().then(() =>
          this.process.stdin.write(JSON.stringify({version:1,id,command,...fields})+"\n"))]);
        if (Object.hasOwn(packet,"state")) this.applyInputState({version:1,event:"ownedImeState",
          browser:fields.browser,token:fields.token,configRevision:fields.configRevision,
          viewportRevision:fields.viewportRevision,state:packet.state});
        return packet;
      } finally { if (this.pending === pending) this.pending=null; }
    });
    this.queue = operation.catch(() => {});
    return operation;
  }
  ownsInput(input) {
    return !this.closed && this.route && input.token === this.route.token &&
      input.configRevision === this.route.configRevision &&
      input.viewportRevision === this.route.viewportRevision &&
      !this.window.closed && this.browser.isConnected &&
      this.browser.ownerDocument === this.window.document &&
      ((input.kind === "ownedIme" && input.action === "cancel") || (
      this.window.gBrowser.selectedBrowser === this.browser &&
      Services.focus.activeWindow === this.window &&
      this.window.document.activeElement === this.browser &&
      !this.window.windowUtils.isInModalState() &&
      !this.browser.hasAttribute("tabmodalPromptShowing")));
  }
  observe(_subject, topic, data) {
    if (this.closed || topic !== "cloakfox-engine-input") return;
    const input = JSON.parse(data);
    // A valid route can outlive a tab/focus change without a new revision.
    if (!this.ownsInput(input)) return;
    if (input.kind === "refreshInput") {
      this.refreshInputState().catch(()=>this.close());return;
    }
    if (input.kind === "focusLocation") {
      this.window.gURLBar.select();
      return;
    }
    this.request("input", {browser: this.browserId, ...input})
      .then(() => this.refreshInputState()).catch(() => this.close());
  }
  async refreshInputState() {
    if (!this.ownedIme || !this.ownsInput(this.route)) return;
    if (this.inputRefresh) {this.inputRefreshDirty=true;return this.inputRefresh;}
    const refresh=(async()=>{
      let missing=0;
      do {
        this.inputRefreshDirty=false;
        if (!this.ownsInput(this.route)) break;
        const packet=await this.request("textInputState", {browser:this.browserId,token:this.route.token,
          configRevision:this.route.configRevision,viewportRevision:this.route.viewportRevision});
        if ((!packet || !Object.hasOwn(packet,"state")) && !this.inputRefreshDirty && this.ownsInput(this.route)) {
          native().invalidateInputState(this.route.token,this.route.configRevision,this.route.viewportRevision);
          this.inputState=null;
          if (++missing>=3) throw new Error("Native editing metadata unavailable");
          // Native focus/type may retire an in-flight query. Keep the context
          // invalidated and bound the retry; never restore cached type data.
          await new Promise(resolve=>setTimeout(resolve,10));
          this.inputRefreshDirty=true;
        }
      } while(this.inputRefreshDirty && !this.closed);
    })();
    this.inputRefresh=refresh;
    try {return await refresh;} finally {if(this.inputRefresh===refresh)this.inputRefresh=null;}
  }
  QueryInterface = ChromeUtils.generateQI(["nsIObserver"]);
  createCanvas() {
    this.canvasStack = this.browser.parentElement;
    this.stackPosition = this.canvasStack.style.getPropertyValue("position");
    this.stackPositionPriority = this.canvasStack.style.getPropertyPriority("position");
    this.canvasStack.style.setProperty("position", "relative");
    this.canvas = this.window.document.createElementNS("http://www.w3.org/1999/xhtml", "canvas");
    this.canvas.setAttribute("aria-hidden", "true");
    this.canvas.setAttribute("data-cloakfox-native-viewport", "");
    this.canvas.style.cssText = "position:absolute;grid-area:1 / 1;display:block;z-index:1;pointer-events:auto;max-width:none;max-height:none";
    this.canvasStack.appendChild(this.canvas);
    this.updateCanvas();
    native().setCanvas(this.route.token, this.canvas);
  }
  updateCanvas() {
    if (!this.canvas) return;
    const r = this.browser.getBoundingClientRect();
    const p = this.canvasStack.getBoundingClientRect();
    this.canvas.hidden = this.window.gBrowser.selectedBrowser !== this.browser;
    if (this.canvas.hidden) return;
    // XUL browserStack uses a shared grid area, already positioned by the
    // letterbox track. Applying its window offset again would double-center it.
    const [, , width, height] = geometry(this.window, this.browser);
    Object.assign(this.canvas.style, {left: "0px", top: "0px",
      width: `${width}px`, height: `${height}px`,
      clipPath: `inset(${Math.max(0,p.top-r.top)}px ${Math.max(0,r.right-p.right)}px ${Math.max(0,r.bottom-p.bottom)}px ${Math.max(0,p.left-r.left)}px)`});
  }
  async resize() {
    if (this.closed || !this.route) return;
    this.updateCanvas();
    const [x, y, width, height, visible] = geometry(this.window, this.browser);
    // Hidden XUL browsers have an empty layout rect. Hide the native slot while
    // retaining its last real renderer size; a tab switch is not a 1px resize.
    const route = JSON.parse(native().updateViewport(this.route.token,
      visible ? x : 0, visible ? y : 0,
      visible ? width : this.route.width, visible ? height : this.route.height, visible));
    if (route.viewportRevision !== this.route.viewportRevision) {
      this.route = route;
      await this.request("surface", {browser: this.browserId, ...route});
    }
    if (visible) await this.refreshInputState();
  }
  async close() {
    if (this.closed) return;
    this.closed = true;
    const pending=this.pending;this.pending=null;pending?.reject(new Error("Native viewport is closed"));
    if (owners.get(this.browser) === this) owners.delete(this.browser);
    if (this.token) sessions.delete(this.token);
    if (this.route) {
      sessions.delete(this.route.token);
      try { native().close(this.route.token); } catch {}
    }
    if (this.name) { try { native().closeLaunch(this.name); } catch {} }
    this.canvas?.remove();
    if (this.canvasStack?.style.getPropertyValue("position") === "relative") {
      if (this.stackPosition) this.canvasStack.style.setProperty("position", this.stackPosition, this.stackPositionPriority);
      else this.canvasStack.style.removeProperty("position");
    }
    this.resizeObserver?.disconnect();
    this.window?.removeEventListener("resize", this.onResize);
    this.window?.removeEventListener("unload", this.onUnload);
    this.window?.gBrowser?.tabContainer?.removeEventListener("TabSelect", this.onResize);
    this.window?.gBrowser?.tabContainer?.removeEventListener("TabClose", this.onTabClose);
    await this.stopProcess();
  }
}

export const CloakfoxEngineHost = {
  async openFixture(window, browser, helper, profileRoot, configJSON, url, geckoCompositor = true, presentation = "same-window") {
    if (!Services.prefs.getBoolPref("cloakfox.engine_host.test.enabled", false) ||
        !window.document.nodePrincipal.isSystemPrincipal || browser.ownerDocument !== window.document ||
        window.closed || !browser.isConnected) {
      throw new Error("Native fixture host is unavailable");
    }
    if (typeof geckoCompositor !== "boolean" ||
        !["same-window", "separate-window"].includes(presentation)) throw new Error("Invalid presentation mode");
    const windowless = presentation === "same-window";
    window = browser.ownerDocument.defaultView;
    const address = new URL(url);
    if (address.protocol !== "http:" || address.hostname !== "127.0.0.1" || !address.port ||
        address.username || address.password) throw new Error("Only an owned loopback fixture is allowed");
    const config = JSON.parse(configJSON);
    if (owners.has(browser)) throw new Error("Browser already owns a native viewport");
    const session = new FixtureSession(window, browser);
    // Reserve before the first await, including process startup and native attach.
    owners.set(browser, session);
    try {
      session.watchOwner();
      session.assertOwner();
      session.name = native().createLaunch(window);
      const launchArgs = ["--profile-root=" + profileRoot, "--enable-probe", "--test-keychain",
        "--host-rendezvous=" + session.name];
      if (windowless) launchArgs.push("--windowless", "--shared-texture");
      session.process = await Subprocess.call({command: helper, arguments: launchArgs, stderr: "pipe"});
      // The owner may close while Subprocess.call is awaiting worker startup.
      // close() has already revoked its native launch; dispose this late child.
      if (session.closed) { await session.stopProcess(); throw new Error("Native viewport owner closed"); }
      session.process.wait().then(() => session.close(), () => session.close());
      session.assertOwner();
      // Drain bounded process diagnostics without logging personas or requests.
      session.stderrDrain = (async () => { while (await session.process.stderr.readString()) {} })().catch(() => {});
      native().acceptLaunch(window, session.name, session.process.pid);
      const ready = await session.line();
      if (ready.event !== "ready" || ready.windowless !== windowless) throw new Error("Unexpected native engine");
      if (ready.fixtureNetworkVersion !== 1) throw new Error("Native fixture network gate is unavailable");
      session.ownedIme = ready.ownedImeVersion === 1;
      if (windowless && session.ownedIme && ready.ownedImeStateVersion !== 1)
        throw new Error("Native editing-state invalidation is unavailable");
      await session.request("applyConfig", {config, fixtureURL: url});
      const opened = await session.request("open", {container: config.containerId, private: config.private,
        configRevision: config.revision, url});
      session.assertOwner();
      session.browserId = opened.browser;
      if (opened.configRevision !== config.revision || opened.container !== config.containerId ||
          opened.private !== config.private || opened.topLevelWindow !== !windowless) {
        throw new Error("Unexpected native browser owner or presentation");
      }
      if (!windowless) {
        // A native Views window owns input/composition itself. It has the same
        // authenticated launch, immutable fixture origin and config gate, but
        // must never create a Gecko overlay or silently serve as a fallback.
        session.token = crypto.randomUUID().replaceAll("-", "");
        session.metadata = {presentation, topLevelWindow: true, helperPid: session.process.pid,
          configRevision: config.revision};
        sessions.set(session.token, session);
        return session.token;
      }
      const [x, y, width, height] = geometry(window, browser);
      session.route = JSON.parse(native().attach(window, browser, session.name, config.revision,
        x, y, width, height, session));
      session.token = session.route.token;
      sessions.set(session.route.token, session);
      if (geckoCompositor) session.createCanvas();
      await session.request("surface", {browser: session.browserId, ...session.route});
      session.onResize = () => session.resize().catch(() => session.close());
      session.resizeObserver = new window.ResizeObserver(session.onResize);
      session.resizeObserver.observe(browser);
      window.addEventListener("resize", session.onResize);
      window.gBrowser.tabContainer.addEventListener("TabSelect", session.onResize);
      const deadline = ChromeUtils.now() + 20000;
      while (!JSON.parse(native().state(session.route.token)).painted) {
        if (ChromeUtils.now() >= deadline || session.closed) throw new Error("Native viewport paint timed out");
        await new Promise(resolve => setTimeout(resolve, 25));
      }
      const metadata = await session.request("frame", {browser: session.browserId});
      if (metadata.topLevelWindow !== false || metadata.configRevision !== config.revision ||
          metadata.paintSource !== "iosurface") throw new Error("Unexpected native presentation");
      session.metadata = {topLevelWindow: metadata.topLevelWindow, paintSource: metadata.paintSource};
      await session.refreshInputState();
      return session.route.token;
    } catch (error) {
      await session.close();
      throw error;
    }
  },
  state(token) {
    const session = sessions.get(token);
    if (!session) throw new Error("Unknown native viewport");
    if (!session.route) return {...session.metadata};
    return {...JSON.parse(native().state(token)), ...session.metadata};
  },
  async close(token) { await sessions.get(token)?.close(); },
};
