// Portions Copyright (c) 2013 The Chromium Embedded Framework Authors.
// Views window/delegate integration adapted from the BSD-licensed cefsimple.
// See THIRD_PARTY_LICENSES/CEF-LICENSE.txt.
#include "browser_client.h"
#include "control_channel.h"
#include "persona_config.h"
#include "policy_contract.h"
#include "offscreen_client.h"
#include "surface_transport_mac.h"
#include <algorithm>
#include <iostream>
#include <map>
#include <mutex>
#include <optional>
#include <set>
#include <thread>
#include "include/base/cef_callback.h"
#include "include/cef_devtools_message_observer.h"
#include "include/cef_display_handler.h"
#include "include/cef_id_mappers.h"
#include "include/cef_parser.h"
#include "include/cef_request_context_handler.h"
#include "include/cef_task.h"
#include "include/cef_version.h"
#include "include/views/cef_browser_view.h"
#include "include/views/cef_box_layout.h"
#include "include/views/cef_label_button.h"
#include "include/views/cef_textfield.h"
#include "include/views/cef_window.h"
#include "include/wrapper/cef_closure_task.h"
#include "include/wrapper/cef_helpers.h"

namespace {
using Dictionary = CefRefPtr<CefDictionaryValue>;
Dictionary message() { return CefDictionaryValue::Create(); }
void emit(Dictionary data) {
  auto value = CefValue::Create();
  value->SetDictionary(data);
  std::cout << CefWriteJSON(value, JSON_WRITER_DEFAULT).ToString() << std::endl;
}
bool inputFields(Dictionary value, const std::set<std::string>& expected) {
  if (!value) return false;
  CefDictionaryValue::KeyList keys; value->GetKeys(keys);
  std::set<std::string> actual;
  for (const auto& key : keys) actual.insert(key.ToString());
  return actual == expected;
}
bool validInputState(Dictionary state) {
  if (!inputFields(state, {"field", "editable", "password", "selection", "composition", "caret"}) ||
      state->GetType("editable") != VTYPE_BOOL || state->GetType("password") != VTYPE_BOOL) return false;
  if (!state->GetBool("editable")) {
    if (state->GetBool("password")) return false;
    for (const auto* key : {"field", "selection", "composition", "caret"})
      if (state->GetType(key) != VTYPE_NULL) return false;
    return true;
  }
  if (state->GetType("field") != VTYPE_DICTIONARY) return false;
  const auto field = state->GetDictionary("field");
  if (!inputFields(field, {"document", "node"}) || field->GetType("document") != VTYPE_STRING ||
      field->GetType("node") != VTYPE_INT || field->GetInt("node") < 1) return false;
  const auto document = field->GetString("document").ToString();
  if (document.empty() || document.size() > 128 ||
      document.find_first_not_of("0123456789abcdefABCDEF-") != std::string::npos) return false;
  for (const auto* key : {"selection", "composition"}) {
    if (state->GetType(key) == VTYPE_NULL) continue;
    if (state->GetType(key) != VTYPE_LIST) return false;
    auto range = state->GetList(key);
    if (range->GetSize() != 2 || range->GetType(0) != VTYPE_INT || range->GetType(1) != VTYPE_INT ||
        range->GetInt(0) < 0 || range->GetInt(1) < range->GetInt(0)) return false;
  }
  if (state->GetType("caret") != VTYPE_LIST) return false;
  auto caret = state->GetList("caret");
  if (caret->GetSize() != 4) return false;
  for (int i = 0; i < 4; ++i) {
    if (caret->GetType(i) != VTYPE_INT) return false;
    const int value = caret->GetInt(i);
    if (value < (i < 2 ? -32768 : 0) || value > (i < 2 ? 32768 : 4096)) return false;
  }
  return true;
}
Dictionary idleInputState() {
  auto state = message(); state->SetBool("editable", false); state->SetBool("password", false);
  for (const auto* key : {"field", "selection", "composition", "caret"}) state->SetNull(key);
  return state;
}

Dictionary reply(int id, bool ok) {
  auto data = message(); data->SetInt("version", 1); data->SetInt("id", id);
  data->SetBool("ok", ok); return data;
}
bool navigable(const std::string& url) {
  CefURLParts parts;
  return url == "about:blank" || (CefParseURL(url, parts) &&
      (CefString(&parts.scheme) == "http" || CefString(&parts.scheme) == "https"));
}
void error(int id, const std::string& reason) {
  auto data = reply(id, false); data->SetString("error", reason); emit(data);
}

class WindowDelegate : public CefWindowDelegate, public CefButtonDelegate,
                       public CefTextfieldDelegate {
 public:
  using CefWindowDelegate::OnKeyEvent;
  explicit WindowDelegate(CefRefPtr<CefBrowserView> view) : view_(view) {}
  void OnWindowCreated(CefRefPtr<CefWindow> window) override {
    CefBoxLayoutSettings vertical;
    vertical.horizontal = false;
    auto layout = window->SetToBoxLayout(vertical);
    window->AddChildView(view_);
    layout->SetFlexForView(view_, 1);
    auto location = CefTextfield::CreateTextfield(this);
    location->SetID(4);
    location->SetPlaceholderText("HTTP(S) address");
    location->SetAccessibleName("Address");
    {
      auto toolbar = CefPanel::CreatePanel(nullptr);
      CefBoxLayoutSettings horizontal;
      horizontal.horizontal = true;
      auto row = toolbar->SetToBoxLayout(horizontal);
      int id = 1;
      for (const auto label : {"Back", "Forward", "Reload"}) {
        auto button = CefLabelButton::CreateLabelButton(this, label);
        button->SetID(id++); toolbar->AddChildView(button);
      }
      toolbar->AddChildView(location);
      row->SetFlexForView(location, 1);
      window->AddChildViewAt(toolbar, 0);
      window->Layout();
    }
    window->Show();
  }
  bool OnKeyEvent(CefRefPtr<CefTextfield> field, const CefKeyEvent& event) override {
    if (event.type != KEYEVENT_RAWKEYDOWN || event.windows_key_code != 13) return false;
    auto browser = view_ ? view_->GetBrowser() : nullptr;
    const auto url = field->GetText().ToString();
    if (browser && navigable(url)) browser->GetMainFrame()->LoadURL(url);
    return true;
  }
  void OnButtonPressed(CefRefPtr<CefButton> button) override {
    auto browser = view_ ? view_->GetBrowser() : nullptr;
    if (!browser) return;
    if (button->GetID() == 1) browser->GoBack();
    else if (button->GetID() == 2) browser->GoForward();
    else if (button->GetID() == 3) browser->Reload();
  }
  void OnWindowDestroyed(CefRefPtr<CefWindow>) override { view_ = nullptr; }
  bool CanClose(CefRefPtr<CefWindow>) override {
    auto browser = view_ ? view_->GetBrowser() : nullptr;
    return !browser || browser->GetHost()->TryCloseBrowser();
  }
  CefSize GetPreferredSize(CefRefPtr<CefView> view) override {
    // This delegate also serves navigation buttons. Only the window gets
    // window dimensions; buttons must retain their native preferred size.
    if (view->AsTextfield()) return CefSize(600, 32);
    return view->AsButton() ? CefSize() : CefSize(1000, 720);
  }
  cef_runtime_style_t GetWindowRuntimeStyle() override { return CEF_RUNTIME_STYLE_CHROME; }
 private:
  CefRefPtr<CefBrowserView> view_;
  IMPLEMENT_REFCOUNTING(WindowDelegate);
};
class ViewDelegate : public CefBrowserViewDelegate {
 public:
  cef_runtime_style_t GetBrowserRuntimeStyle() override { return CEF_RUNTIME_STYLE_CHROME; }
  ChromeToolbarType GetChromeToolbarType(CefRefPtr<CefBrowserView>) override {
    return CEF_CTT_NONE;
  }
  bool OnPopupBrowserViewCreated(CefRefPtr<CefBrowserView>,
      CefRefPtr<CefBrowserView> popup, bool) override {
    CefWindow::CreateTopLevelWindow(new WindowDelegate(popup)); return true;
  }
 private:
  IMPLEMENT_REFCOUNTING(ViewDelegate);
};

// Development host fixtures have one immutable permitted HTTP origin. This
// object is shared with IO-thread request-context handlers, including workers
// without a CefBrowser. Bind before native context creation; unbound denies.
class FixtureScope {
 public:
  explicit FixtureScope(bool restricted) : restricted_(restricted) {}
  bool bind(const std::string& url) {
    if (!restricted_) return true;
    CefURLParts parts;
    if (!CefParseURL(url, parts) || CefString(&parts.scheme) != "http" ||
        CefString(&parts.host) != "127.0.0.1" || CefString(&parts.port).empty() ||
        !CefString(&parts.username).empty() || !CefString(&parts.password).empty()) return false;
    const auto origin = CefString(&parts.origin).ToString();
    std::lock_guard<std::mutex> lock(mutex_);
    if (origin_.empty()) origin_ = origin;
    return origin_ == origin;
  }
  bool allowed(const std::string& url) const {
    if (!restricted_ || url == "about:blank") return true;
    CefURLParts parts;
    if (!CefParseURL(url, parts) || CefString(&parts.scheme) != "http" ||
        !CefString(&parts.username).empty() || !CefString(&parts.password).empty()) return false;
    std::lock_guard<std::mutex> lock(mutex_);
    return !origin_.empty() && CefString(&parts.origin).ToString() == origin_;
  }
  std::string origin() const {
    std::lock_guard<std::mutex> lock(mutex_);
    // CefParseURL exposes an origin URL with a trailing slash. Native policy
    // stores url::Origin::Serialize(), whose canonical form has no path.
    auto canonical = origin_;
    if (!canonical.empty() && canonical.back() == '/') canonical.pop_back();
    return canonical;
  }
  bool restricted() const { return restricted_; }
 private:
  const bool restricted_;
  mutable std::mutex mutex_;
  std::string origin_;
};
class Companion;
Companion* current = nullptr;
class ContextHandler : public CefRequestContextHandler, public CefResourceRequestHandler {
 public:
  ContextHandler(Companion* owner, std::string key, std::shared_ptr<FixtureScope> scope)
      : owner_(owner), key_(std::move(key)), scope_(std::move(scope)) {}
  CefRefPtr<CefResourceRequestHandler> GetResourceRequestHandler(CefRefPtr<CefBrowser>,
      CefRefPtr<CefFrame>, CefRefPtr<CefRequest>, bool, bool, const CefString&, bool&) override {
    return scope_->restricted() ? this : nullptr;
  }
  ReturnValue OnBeforeResourceLoad(CefRefPtr<CefBrowser>, CefRefPtr<CefFrame>,
      CefRefPtr<CefRequest> request, CefRefPtr<CefCallback>) override {
    return scope_->allowed(request->GetURL().ToString()) ? RV_CONTINUE : RV_CANCEL;
  }
  void OnResourceRedirect(CefRefPtr<CefBrowser>, CefRefPtr<CefFrame>, CefRefPtr<CefRequest>,
      CefRefPtr<CefResponse>, CefString& url) override {
    // The redirect callback cannot cancel directly. Replace an out-of-scope
    // destination with a non-network URL; it must never contact that origin.
    if (!scope_->allowed(url.ToString())) url = "about:blank";
  }
  void OnRequestContextInitialized(CefRefPtr<CefRequestContext> context) override;
 private:
  Companion* owner_;
  const std::string key_;
  const std::shared_ptr<FixtureScope> scope_;
  IMPLEMENT_REFCOUNTING(ContextHandler);
};
class Client : public CefClient, public CefLifeSpanHandler, public CefCommandHandler,
               public CefRequestHandler, public CefPermissionHandler, public CefDisplayHandler,
               public CefDevToolsMessageObserver {
 public:
  Client(Companion* owner, int requestId, std::string container, bool isPrivate, bool windowless, std::shared_ptr<FixtureScope> scope)
      : owner_(owner), requestId_(requestId), container_(std::move(container)),
        private_(isPrivate), scope_(std::move(scope)), offscreen_(windowless ? new cloakfox::OffscreenClient : nullptr) {}
  CefRefPtr<CefRenderHandler> GetRenderHandler() override { return offscreen_; }
  CefRefPtr<CefLifeSpanHandler> GetLifeSpanHandler() override { return this; }
  CefRefPtr<CefRequestHandler> GetRequestHandler() override { return this; }
  CefRefPtr<CefPermissionHandler> GetPermissionHandler() override { return this; }
  CefRefPtr<CefCommandHandler> GetCommandHandler() override { return this; }
  CefRefPtr<CefDisplayHandler> GetDisplayHandler() override { return this; }
  bool OnBeforeBrowse(CefRefPtr<CefBrowser>, CefRefPtr<CefFrame>, CefRefPtr<CefRequest> request,
      bool, bool) override { return !scope_->allowed(request->GetURL().ToString()); }
  bool OnBeforePopup(CefRefPtr<CefBrowser>, CefRefPtr<CefFrame>, int,
      const CefString&, const CefString&, WindowOpenDisposition, bool,
      const CefPopupFeatures&, CefWindowInfo&, CefRefPtr<CefClient>&,
      CefBrowserSettings&, CefRefPtr<CefDictionaryValue>&, bool*) override {
    // The feasibility controller has no trusted popup viewport allocator yet.
    // CEF's default reuses this Client, aliasing its paint/viewport state, and
    // creates a top-level window. Refuse that path until the native host owns
    // popup allocation. Existing Views-hosted popup behavior stays native.
    return offscreen_ != nullptr;
  }
  void OnAddressChange(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
                       const CefString& url) override {
    if (!frame->IsMain()) return;
    auto view = CefBrowserView::GetForBrowser(browser);
    auto window = view ? view->GetWindow() : nullptr;
    auto field = window ? window->GetViewForID(4) : nullptr;
    if (field && field->AsTextfield()) field->AsTextfield()->SetText(url);
  }
  bool OnChromeCommand(CefRefPtr<CefBrowser>, int command,
                       cef_window_open_disposition_t disposition) override {
    // Profile, incognito, new-window/tab and browser-management actions must
    // come from our controller, never bypass its container ownership checks.
    for (const auto name : {"IDC_BACK", "IDC_FORWARD", "IDC_RELOAD", "IDC_STOP",
         "IDC_RELOAD_BYPASSING_CACHE", "IDC_FOCUS_LOCATION", "IDC_CLOSE_WINDOW", "IDC_CLOSE_TAB"})
      if (command == cef_id_for_command_id_name(name)) return false;
    if (command == cef_id_for_command_id_name("IDC_OPEN_CURRENT_URL") &&
        disposition == CEF_WOD_CURRENT_TAB) return false;
    return true;
  }
  bool OnProcessMessageReceived(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
      CefProcessId source, CefRefPtr<CefProcessMessage> message) override;
  void OnAfterCreated(CefRefPtr<CefBrowser> browser) override;
  void OnBeforeClose(CefRefPtr<CefBrowser> browser) override;
  void OnRenderProcessTerminated(CefRefPtr<CefBrowser> browser,
      TerminationStatus status, int errorCode, const CefString&) override {
    auto data = message(); data->SetString("event", "crashed");
    data->SetInt("browser", browser->GetIdentifier());
    data->SetInt("status", status); data->SetInt("errorCode", errorCode); emit(data);
  }
  bool OnRequestMediaAccessPermission(CefRefPtr<CefBrowser>, CefRefPtr<CefFrame>,
      const CefString&, uint32_t, CefRefPtr<CefMediaAccessCallback> callback) override {
    callback->Cancel(); return true;
  }
  bool OnShowPermissionPrompt(CefRefPtr<CefBrowser>, uint64_t, const CefString&,
      uint32_t, CefRefPtr<CefPermissionPromptCallback> callback) override {
    callback->Continue(CEF_PERMISSION_RESULT_DENY); return true;
  }
  void OnDevToolsMethodResult(CefRefPtr<CefBrowser>, int id, bool success,
      const void* result, size_t size) override {
    auto data = reply(id, success);
    auto value = CefParseJSON(std::string(static_cast<const char*>(result), size),
                              JSON_PARSER_RFC);
    if (value) data->SetValue("result", value);
    emit(data);
  }
 private:
  Companion* owner_;
  int requestId_;
  const std::string container_;
  const bool private_;
  const std::shared_ptr<FixtureScope> scope_;
  CefRefPtr<cloakfox::OffscreenClient> offscreen_;
  std::map<int, CefRefPtr<CefRegistration>> observers_;
  IMPLEMENT_REFCOUNTING(Client);
};

class Companion : public CefApp, public CefBrowserProcessHandler {
 public:
  Companion(std::shared_ptr<cloakfox::ContainerPaths> paths, bool probe, bool testKeychain, int testQuicPort, bool windowless, bool sharedTexture, mach_port_t surfacePort)
      : paths_(std::move(paths)), probe_(probe), testKeychain_(testKeychain), testQuicPort_(testQuicPort), windowless_(windowless), sharedTexture_(sharedTexture), surfacePort_(surfacePort), fixtureScope_(std::make_shared<FixtureScope>(MACH_PORT_VALID(surfacePort))) { current = this; }
  ~Companion() override { current = nullptr; }
  CefRefPtr<CefBrowserProcessHandler> GetBrowserProcessHandler() override { return this; }
  void OnBeforeCommandLineProcessing(const CefString& processType,
                                    CefRefPtr<CefCommandLine> command) override {
    if (processType.empty()) {
      command->AppendSwitchWithValue("profile-directory", cloakfox::ContainerPaths::kBootstrapProfile);
      command->AppendSwitch("no-first-run");
      command->AppendSwitch("disable-background-networking");
      command->AppendSwitch("disable-component-update");
      // Non-official Chromium embeds experimental field-trial test cohorts.
      // Use stable feature defaults, matching official CEF distributions.
      command->AppendSwitch("disable-field-trial-config");
      if (testKeychain_) command->AppendSwitch("use-mock-keychain");
      if (testQuicPort_) {
        command->AppendSwitch("enable-quic");
        command->AppendSwitchWithValue("origin-to-force-quic-on", "127.0.0.1:" + std::to_string(testQuicPort_));
      }
    }
  }
  void OnContextInitialized() override {
    CEF_REQUIRE_UI_THREAD();
    auto ready = message(); ready->SetInt("version", 1);
    ready->SetString("event", "ready"); ready->SetString("engine", "chromium");
    ready->SetString("cefVersion", CEF_VERSION);
    ready->SetString("chromiumVersion", std::to_string(CHROME_VERSION_MAJOR) + "." +
        std::to_string(CHROME_VERSION_MINOR) + "." + std::to_string(CHROME_VERSION_BUILD) + "." +
        std::to_string(CHROME_VERSION_PATCH));
    auto global_context = CefRequestContext::GetGlobalContext();
    auto capability = global_context->GetPreference("cloakfox.canvas_readback_version");
    canvasVersion_ = capability && capability->GetType() == VTYPE_INT ? capability->GetInt() : 0;
    ready->SetInt("canvasReadbackVersion", canvasVersion_);
    const auto nativeVersion = [&global_context](const char* name) {
      auto value = global_context->GetPreference(name);
      return value && value->GetType() == VTYPE_INT ? value->GetInt() : 0;
    };
    identityVersion_ = nativeVersion("cloakfox.identity_privacy_version");
    ready->SetInt("identityPrivacyVersion", identityVersion_);
#if defined(CEF_CLOAKFOX_INITIAL_SNAPSHOT_VERSION)
    initialSnapshotVersion_ = nativeVersion("cloakfox.initial_snapshot_version") ==
        CEF_CLOAKFOX_INITIAL_SNAPSHOT_VERSION ? CEF_CLOAKFOX_INITIAL_SNAPSHOT_VERSION : 0;
#endif
    ready->SetInt("initialSnapshotVersion", initialSnapshotVersion_);
    fixtureNetworkVersion_ = initialSnapshotVersion_ == 1 ? nativeVersion("cloakfox.fixture_network_version") : 0;
    ready->SetInt("fixtureNetworkVersion", fixtureNetworkVersion_);
#if defined(CEF_CLOAKFOX_OWNED_IME_VERSION)
    ownedImeVersion_ = nativeVersion("cloakfox.owned_ime_version") == CEF_CLOAKFOX_OWNED_IME_VERSION ? CEF_CLOAKFOX_OWNED_IME_VERSION : 0;
#endif
    ready->SetInt("ownedImeVersion", ownedImeVersion_);
    ownedImeStateVersion_ = ownedImeVersion_ == 1 ? nativeVersion("cloakfox.owned_ime_state_version") : 0;
    ready->SetInt("ownedImeStateVersion", ownedImeStateVersion_);
    webgpuVersion_ = nativeVersion("cloakfox.webgpu_privacy_version");
    ready->SetInt("webgpuPrivacyVersion", webgpuVersion_);
    ready->SetInt("webgpuPixelReadbackVersion", nativeVersion("cloakfox.webgpu_pixel_readback_version"));
    ready->SetInt("webglPrivacyVersion", nativeVersion("cloakfox.webgl_privacy_version"));
    ready->SetInt("workerCanvasPrivacyVersion", nativeVersion("cloakfox.worker_canvas_privacy_version"));
    ready->SetInt("configSchemaVersion", 1);
    // Current complete-group ports are unavailable. Partial v1 hook versions
    // above must never be interpreted as schema2 or production readiness.
    ready->SetInt("requiredPolicySchemaVersion", cloakfox::kRequiredPolicySchemaVersion);
    auto policyGroups = CefDictionaryValue::Create();
    for (const auto* group : cloakfox::kRequiredPrivacyGroups) policyGroups->SetInt(group, 0);
    ready->SetDictionary("nativePolicyGroups", policyGroups);
    ready->SetBool("releaseEligible", false);
    auto configOptions = CefListValue::Create();
    if (canvasVersion_ == 1 && webgpuVersion_ == 1) {
      configOptions->SetString(0, "canvas");
      configOptions->SetString(1, "blockWebGPUReadback");
      if (identityVersion_ == 1 || identityVersion_ == 2) {
        configOptions->SetString(2, "navigator");
        configOptions->SetString(3, "language");
        configOptions->SetString(4, "timezone");
      }
    }
    ready->SetList("supportedPersonaOptions", configOptions);
    ready->SetBool("configRequiresRestart", true);
    ready->SetBool("windowless", windowless_);
    ready->SetBool("privacyPatched", false); ready->SetBool("probeEnabled", probe_);
    ready->SetBool("testKeychain", testKeychain_);
    ready->SetBool("testQuicRoute", testQuicPort_ != 0);
    emit(ready);
    // Inherited pipes are the only controller surface. No HTTP/CDP port or page binding.
    control_.start([this](std::string line) {
      CefPostTask(TID_UI, base::BindOnce(&Companion::dispatch, CefRefPtr<Companion>(this), std::move(line)));
    }, [this] {
      CefPostTask(TID_UI, base::BindOnce(&Companion::quit, CefRefPtr<Companion>(this)));
    });
  }
  void stopControl() { control_.stop(); }
  void created(CefRefPtr<CefBrowser> browser, int requestId,
               const std::string& container, bool isPrivate, CefRefPtr<cloakfox::OffscreenClient> offscreen) {
    if (offscreen) offscreenClients_[browser->GetIdentifier()] = offscreen;
    if (requestId > 0) --creatingWindows_;
    browsers_[browser->GetIdentifier()] = browser;
    const auto key = std::string(isPrivate ? "private:" : "persistent:") + container;
    browserContexts_[browser->GetIdentifier()] = key;
    if (requestId > 0) --contexts_.at(key).creating;
    auto data = reply(requestId, true); data->SetString("event", "opened");
    data->SetInt("browser", browser->GetIdentifier());
    data->SetBool("topLevelWindow", offscreen == nullptr);
    data->SetString("container", container); data->SetBool("private", isPrivate);
    data->SetBool("canvasEnabled", canvasVersion_ > 0 && contexts_.at(key).canvasEnabled);
    data->SetBool("webgpuReadbackBlocked", webgpuVersion_ > 0 && contexts_.at(key).blockWebGPUReadback);
    if (contexts_.at(key).config)
      data->SetInt("configRevision", contexts_.at(key).config->revision);
    if (requestId == 0) data->Remove("id");
    emit(data);
    if (closing_) browser->GetHost()->CloseBrowser(true);
  }
  bool inputRouteMatches(int browser, Dictionary data) const {
    const auto binding = surfaceRoutes_.find(browser);
    if (binding == surfaceRoutes_.end()) return !data->HasKey("token") && !data->HasKey("viewportRevision");
    std::string token; constexpr char hex[] = "0123456789abcdef";
    for (const auto byte : binding->second.token) { token += hex[byte >> 4]; token += hex[byte & 15]; }
    return data->GetType("token") == VTYPE_STRING && data->GetString("token") == token &&
        data->GetType("viewportRevision") == VTYPE_INT &&
        data->GetInt("viewportRevision") == static_cast<int>(binding->second.viewportRevision);
  }
  void finishIme(int id, bool applied, Dictionary state) {
    auto pending = imePending_.find(id);
    if (pending == imePending_.end()) return;
    const auto owner = pending->second;
    imePending_.erase(pending);
    bool current = browsers_.contains(owner.browser) && browserContexts_.contains(owner.browser);
    bool metadataCurrent=false;
    if (current) {
      const auto& context = contexts_.at(browserContexts_.at(owner.browser));
      current = context.config && context.config->revision == owner.revision;
      const auto route = surfaceRoutes_.find(owner.browser);
      current = current && (owner.route ? route != surfaceRoutes_.end() && route->second == *owner.route : route == surfaceRoutes_.end());
      auto focused=browsers_.at(owner.browser)->GetFocusedFrame();
      metadataCurrent=current && focused && focused->GetIdentifier()==owner.frame->GetIdentifier() &&
          owner.stateEpoch==imeTypeEpoch_[owner.browser] && stateMatchesNativeType(owner.browser,state);
    }
    auto data = reply(id, true);
    // The renderer has already checked the live field at operation delivery.
    // A later metadata epoch cannot undo a successful edit or invite a retry.
    data->SetBool("applied", current && applied && (!owner.query || metadataCurrent));
    if (metadataCurrent) data->SetDictionary("state", state);
    emit(data);
  }
  void timeoutIme(int id) { finishIme(id, false, idleInputState()); }
  void submitIme(int id, CefRefPtr<CefBrowser> browser, Dictionary command) {
    if (ownedImeVersion_ != 1 || imePending_.size() >= 32) { error(id, "Native editing hook unavailable or busy"); return; }
    auto frame = browser->GetFocusedFrame();
    if (!frame || !frame->IsValid()) frame = browser->GetMainFrame();
    if (!frame || !frame->IsValid()) {
      auto data = reply(id, true); data->SetBool("applied", false); data->SetDictionary("state", idleInputState()); emit(data); return;
    }
    const int browserId = browser->GetIdentifier();
    const auto& context = contexts_.at(browserContexts_.at(browserId));
    ImePending pending{browserId, context.config->revision, frame, std::nullopt,imeTypeEpoch_[browserId],command->GetString("action")=="query"};
    if (surfaceRoutes_.contains(browserId)) pending.route = surfaceRoutes_.at(browserId);
    imePending_.emplace(id, std::move(pending));
    auto request = CefProcessMessage::Create("cloakfox.owned-ime.request.v1");
    request->GetArgumentList()->SetInt(0, id);
    request->GetArgumentList()->SetDictionary(1, command->Copy(false));
    frame->SendProcessMessage(PID_RENDERER, request);
    CefPostDelayedTask(TID_UI, base::BindOnce(&Companion::timeoutIme,
        CefRefPtr<Companion>(this), id), 2500);
  }
  bool stateMatchesNativeType(int browser, Dictionary state) const {
    auto type=imeTypes_.find(browser);
    return type==imeTypes_.end() || (state->GetBool("editable")==type->second.editable &&
        state->GetBool("password")==type->second.password);
  }
  // A pointer-down can move focus before the renderer reports the new editing
  // type. Fence in-flight metadata replies for this browser so a stale
  // field/document result cannot be accepted as current, and let the trusted
  // host invalidate its cached state. The renderer's next type report (if any)
  // re-arms normal acceptance; the fence never restores an old focus.
  void fenceEditingOwnership(int browser) {
    ++imeTypeEpoch_[browser];
    if (browserContexts_.contains(browser) && contexts_.contains(browserContexts_.at(browser)))
      emitImeInvalidated(browser);
  }
  void emitImeInvalidated(int browser) {
    const auto& context=contexts_.at(browserContexts_.at(browser));
    if (!context.config) return;
    auto data=message();data->SetInt("version",1);data->SetString("event","ownedImeInvalidated");
    data->SetInt("browser",browser);data->SetInt("configRevision",context.config->revision);
    if (surfaceRoutes_.contains(browser)) {
      const auto& route=surfaceRoutes_.at(browser);std::string token;constexpr char hex[]="0123456789abcdef";
      for(auto byte:route.token){token+=hex[byte>>4];token+=hex[byte&15];}
      data->SetString("token",token);data->SetInt("viewportRevision",route.viewportRevision);
    }
    emit(data);
  }
  bool imeMessage(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
                   CefProcessId source, CefRefPtr<CefProcessMessage> packet) {
    const auto name = packet->GetName().ToString();
    if (name == "cloakfox.native-owned-ime-type.v1") {
      if (source!=PID_BROWSER || ownedImeStateVersion_!=1 || !probe_ || !windowless_ || !browser || !frame ||
          !browsers_.contains(browser->GetIdentifier()) || !browserContexts_.contains(browser->GetIdentifier())) return true;
      auto args=packet->GetArgumentList();
      if(args->GetSize()!=2 || args->GetType(0)!=VTYPE_BOOL || args->GetType(1)!=VTYPE_BOOL ||
          (args->GetBool(1) && !args->GetBool(0))) return true;
      const int browserId=browser->GetIdentifier();
      auto focused=browser->GetFocusedFrame();
      if(args->GetBool(0) && (!focused || focused->GetIdentifier()!=frame->GetIdentifier())) return true;
      const ImeType next{frame->GetIdentifier(),args->GetBool(0),args->GetBool(1)};
      auto old=imeTypes_.find(browserId);
      if(old==imeTypes_.end() || old->second.frame!=next.frame || old->second.editable!=next.editable || old->second.password!=next.password) {
        imeTypes_[browserId]=next;++imeTypeEpoch_[browserId];emitImeInvalidated(browserId);
      }
      return true;
    }
    if (name != "cloakfox.owned-ime.reply.v1" && name != "cloakfox.owned-ime.state.v1") return false;
    if (source != PID_RENDERER || !probe_ || !windowless_ || ownedImeVersion_ != 1 ||
        !browser || !frame || !frame->IsValid() || !frame->GetBrowser() ||
        frame->GetBrowser()->GetIdentifier() != browser->GetIdentifier() ||
        !browsers_.contains(browser->GetIdentifier())) return true;
    const auto args = packet->GetArgumentList();
    if (name == "cloakfox.owned-ime.reply.v1") {
      if (args->GetSize() != 3 || args->GetType(0) != VTYPE_INT || args->GetType(1) != VTYPE_BOOL ||
          args->GetType(2) != VTYPE_DICTIONARY || !validInputState(args->GetDictionary(2))) return true;
      auto pending = imePending_.find(args->GetInt(0));
      if (pending == imePending_.end() || pending->second.browser != browser->GetIdentifier() ||
          pending->second.frame->GetIdentifier() != frame->GetIdentifier()) return true;
      finishIme(args->GetInt(0), args->GetBool(1), args->GetDictionary(2));
    } else {
      if (args->GetSize() != 1 || args->GetType(0) != VTYPE_DICTIONARY ||
          !validInputState(args->GetDictionary(0))) return true;
      const auto state = args->GetDictionary(0);
      auto focused = browser->GetFocusedFrame();
      if ((focused && focused->GetIdentifier() != frame->GetIdentifier()) ||
          (state->GetBool("editable") && !focused) || !stateMatchesNativeType(browser->GetIdentifier(),state)) return true;
      const int browserId = browser->GetIdentifier();
      const auto& context = contexts_.at(browserContexts_.at(browserId));
      if (!context.config) return true;
      auto data = message(); data->SetInt("version", 1); data->SetString("event", "ownedImeState");
      data->SetInt("browser", browserId); data->SetInt("configRevision", context.config->revision);
      if (surfaceRoutes_.contains(browserId)) {
        const auto& route = surfaceRoutes_.at(browserId);
        std::string token; constexpr char hex[] = "0123456789abcdef";
        for (const auto byte : route.token) { token += hex[byte >> 4]; token += hex[byte & 15]; }
        data->SetString("token", token); data->SetInt("viewportRevision", route.viewportRevision);
      }
      data->SetDictionary("state", state->Copy(false)); emit(data);
    }
    return true;
  }
  void closed(int id) {
    imeTypes_.erase(id);imeTypeEpoch_.erase(id);
    std::vector<int> pendingInput;
    for (const auto& [requestId, owner] : imePending_) if (owner.browser == id) pendingInput.push_back(requestId);
    for (int requestId : pendingInput) finishIme(requestId, false, idleInputState());
    const auto key = browserContexts_.at(id);
    browserContexts_.erase(id);
    browsers_.erase(id);
    if (offscreenClients_.contains(id)) offscreenClients_.at(id)->setSink({});
    if (surfaceRoutes_.contains(id)) {
      retiredSurfaceTokens_.insert(surfaceRoutes_.at(id).token);
      surfaceRoutes_.erase(id);
    }
    offscreenClients_.erase(id);
    if (key.rfind("private:", 0) == 0) {
      bool live = false;
      for (const auto& [browserId, contextKey] : browserContexts_) live = live || contextKey == key;
      auto entry = contexts_.find(key);
      if (!live && entry != contexts_.end() && entry->second.pending.empty() && !entry->second.creating) {
        if (entry->second.config) {
          retiredPrivateSeeds_[key].insert(entry->second.config->seed);
          auto discarded = message(); discarded->SetString("event", "configDiscarded");
          discarded->SetString("container", entry->second.config->container);
          discarded->SetBool("private", true);
          discarded->SetInt("configRevision", entry->second.config->revision);
          emit(discarded);
        }
        contexts_.erase(entry);
      }
    }
    auto data = message(); data->SetString("event", "closed"); data->SetInt("browser", id); emit(data);
    bool pending = creatingWindows_ != 0;
    for (const auto& [key, entry] : contexts_) pending = pending || !entry.pending.empty();
    if (browsers_.empty() && !pending) {
      closing_ = true; contexts_.clear(); CefQuitMessageLoop();
    }
  }
  void quit() {
    CEF_REQUIRE_UI_THREAD();
    if (closing_) return;
    closing_ = true;
    for (auto& [key, entry] : contexts_) {
      for (const auto& request : entry.pending) error(request.id, "Companion is closing");
      if (entry.configRequest) { error(entry.configRequest, "Companion is closing"); entry.configRequest = 0; }
      entry.pending.clear();
    }
    if (browsers_.empty() && !creatingWindows_) { contexts_.clear(); CefQuitMessageLoop(); return; }
    // Alloy/windowless closure may synchronously call OnBeforeClose and erase
    // browsers_. Keep a stable snapshot and strong refs across those callbacks.
    const auto closingBrowsers = browsers_;
    for (const auto& [id, browser] : closingBrowsers) browser->GetHost()->CloseBrowser(true);
  }
  struct OpenRequest { int id; std::string url; std::string container; bool isPrivate; };
  struct ContextEntry {
    CefRefPtr<CefRequestContext> context;
    bool ready = false;
    CefRefPtr<CefDictionaryValue> initialSnapshotStatus;
    std::optional<cloakfox::PersonaConfig> config;
    int configRequest = 0;
    bool canvasEnabled = true;
    bool blockWebGPUReadback = false;
    int creating = 0;
    std::vector<OpenRequest> pending;
  };
  void openWindow(CefRefPtr<CefRequestContext> context, const OpenRequest& request) {
    CefBrowserSettings settings;
    ++creatingWindows_;
    const auto key = std::string(request.isPrivate ? "private:" : "persistent:") + request.container;
    ++contexts_.at(key).creating;
    if (windowless_) {
      CefWindowInfo info;
      info.SetAsWindowless(nullptr);
      info.shared_texture_enabled = sharedTexture_;
      if (!CefBrowserHost::CreateBrowser(info,
          new Client(this, request.id, request.container, request.isPrivate, true, fixtureScope_),
          request.url, settings, nullptr, context)) {
        --creatingWindows_; --contexts_.at(key).creating;
        error(request.id, "Cannot create windowless browser");
      }
      return;
    }
    auto view = CefBrowserView::CreateBrowserView(
        new Client(this, request.id, request.container, request.isPrivate, false, fixtureScope_),
        request.url, settings, nullptr, context, new ViewDelegate);
    if (!view) { --creatingWindows_; --contexts_.at(key).creating; error(request.id, "Cannot create browser view"); return; }
    CefWindow::CreateTopLevelWindow(new WindowDelegate(view));
  }
  void configApplied(int id, const ContextEntry& entry) {
    auto data = reply(id, true);
    data->SetString("event", "configApplied");
    data->SetString("engine", "chromium");
    data->SetString("container", entry.config->container);
    data->SetBool("private", entry.config->isPrivate);
    data->SetInt("configRevision", entry.config->revision);
    data->SetBool("canvasEnabled", entry.canvasEnabled);
    data->SetBool("webgpuReadbackBlocked", entry.blockWebGPUReadback);
    if (entry.initialSnapshotStatus)
      data->SetDictionary("initialSnapshotStatus", entry.initialSnapshotStatus->Copy(false));
    emit(data);
  }
  void contextReady(const std::string& key, CefRefPtr<CefRequestContext> context) {
    if (closing_ || !contexts_.count(key)) return;
    auto& entry = contexts_.at(key);
    entry.context = context;
    const auto applyBool = [&context](const char* name, bool value, CefString& failure) {
      auto setting = CefValue::Create(); setting->SetBool(value);
      return context->SetPreference(name, setting, failure);
    };
    CefString failure;
    bool configured = false;
#if defined(CEF_CLOAKFOX_INITIAL_SNAPSHOT_VERSION)
    if (entry.config && initialSnapshotVersion_ == CEF_CLOAKFOX_INITIAL_SNAPSHOT_VERSION) {
      auto status = CefGetInitialPrivacyStatus(context);
      CefDictionaryValue::KeyList keys;
      if (status) status->GetKeys(keys);
      std::set<std::string> actual;
      for (const auto& name : keys) actual.insert(name.ToString());
      configured = status && actual == std::set<std::string>{"schemaVersion","appliedBeforeServices","container","private","revision"} &&
          status->GetType("schemaVersion") == VTYPE_INT && status->GetInt("schemaVersion") == 1 &&
          status->GetType("appliedBeforeServices") == VTYPE_BOOL && status->GetBool("appliedBeforeServices") &&
          status->GetType("container") == VTYPE_STRING && status->GetString("container") == entry.config->container &&
          status->GetType("private") == VTYPE_BOOL && status->GetBool("private") == entry.config->isPrivate &&
          status->GetType("revision") == VTYPE_INT && status->GetInt("revision") == entry.config->revision;
      if (configured) entry.initialSnapshotStatus = status->Copy(false);
      else failure = "Native initial snapshot was not applied before services";
    } else
#endif
    {
    auto seed = CefValue::Create();
    if (entry.config) seed->SetString(entry.config->seed);
    auto identity = CefValue::Create();
    identity->SetDictionary(entry.config && entry.config->presentation ?
                           entry.config->presentation : CefDictionaryValue::Create());
    configured = !((identityVersion_ > 0 && !context->SetPreference("cloakfox.presentation", identity, failure)) ||
        (entry.config && !context->SetPreference("cloakfox.canvas_key", seed, failure)) ||
        (canvasVersion_ > 0 && !applyBool("cloakfox.canvas_enabled", entry.canvasEnabled, failure)) ||
        (webgpuVersion_ > 0 && !applyBool("cloakfox.webgpu_block_readback", entry.blockWebGPUReadback, failure)));
    }
    if (!configured) {
      for (const auto& request : entry.pending)
        error(request.id, "Cannot configure native privacy policy: " + failure.ToString());
      if (entry.configRequest) error(entry.configRequest, "Cannot configure native persona policy");
      contexts_.erase(key);
      return;
    }
    entry.ready = true;
    if (entry.configRequest) { configApplied(entry.configRequest, entry); entry.configRequest = 0; }
    auto pending = std::move(entry.pending);
    for (const auto& request : pending) openWindow(context, request);
  }
  void dispatch(const std::string& line) {
    CEF_REQUIRE_UI_THREAD();
    auto value = CefParseJSON(line, JSON_PARSER_RFC);
    auto data = value && value->GetType() == VTYPE_DICTIONARY ? value->GetDictionary() : nullptr;
    int id = data && data->GetType("id") == VTYPE_INT ? data->GetInt("id") : 0;
    if (!data || id <= 0 || data->GetType("version") != VTYPE_INT ||
        data->GetInt("version") != 1 || data->GetType("command") != VTYPE_STRING) {
      error(id, "Invalid protocol envelope"); return;
    }
    if (id <= lastId_) { error(id, "Replayed or out-of-order request"); return; }
    lastId_ = id;
    if (closing_) { error(id, "Companion is closing"); return; }
    const auto command = data->GetString("command").ToString();
    const std::map<std::string, std::vector<std::string>> fields{
      {"open", {"version", "id", "command", "container", "url", "private", "privacy", "configRevision"}},
      {"applyConfig", {"version", "id", "command", "config", "fixtureURL"}},
      {"quit", {"version", "id", "command"}},
      {"close", {"version", "id", "command", "browser"}},
      {"frame", {"version", "id", "command", "browser"}},
      {"textInputState", {"version", "id", "command", "browser", "configRevision", "token", "viewportRevision"}},
      {"viewport", {"version", "id", "command", "browser", "configRevision", "width", "height"}},
      {"surface", {"version", "id", "command", "browser", "configRevision", "viewportRevision", "token", "width", "height"}},
      {"input", {"version", "id", "command", "browser", "configRevision", "viewportRevision", "token", "kind", "x", "y", "character", "deltaX", "deltaY", "keyCode", "shift", "text", "action", "field", "selectionStart", "selectionEnd", "replacement"}},
      {"navigate", {"version", "id", "command", "browser", "url"}},
      {"cdp", {"version", "id", "command", "browser", "method", "params"}},
    };
    if (!fields.count(command)) { error(id, "Unknown command"); return; }
    CefDictionaryValue::KeyList keys;
    data->GetKeys(keys);
    const auto& allowed = fields.at(command);
    for (const auto& key : keys) {
      if (std::find(allowed.begin(), allowed.end(), key.ToString()) == allowed.end()) {
        error(id, "Unsupported command option"); return;
      }
    }
    if (command == "quit") { emit(reply(id, true)); quit(); return; }
    if (command == "applyConfig") {
      try {
        if (data->GetType("config") != VTYPE_DICTIONARY)
          throw std::runtime_error("Invalid config object");
        auto config = cloakfox::parsePersonaConfig(data->GetDictionary("config"), canvasVersion_, webgpuVersion_, identityVersion_);
        if (fixtureScope_->restricted()) {
          if (fixtureNetworkVersion_ != 1 || data->GetType("fixtureURL") != VTYPE_STRING ||
              !fixtureScope_->bind(data->GetString("fixtureURL").ToString()))
            throw std::runtime_error("Native fixture network gate or immutable origin unavailable");
        } else if (data->HasKey("fixtureURL")) {
          throw std::runtime_error("Fixture origin requires an authenticated native host");
        }
        const auto key = std::string(config.isPrivate ? "private:" : "persistent:") + config.container;
        if (config.isPrivate && retiredPrivateSeeds_[key].count(config.seed))
          throw std::runtime_error("Retired private persona; generate a fresh session snapshot");
        auto existing = contexts_.find(key);
        if (existing != contexts_.end()) {
          const auto& entry = existing->second;
          if (!entry.ready) throw std::runtime_error("Container configuration is initializing");
          if (!entry.config || !entry.config->snapshot->IsEqual(config.snapshot))
            throw std::runtime_error("Stale or changed config; restart companion before applying changes");
          configApplied(id, entry); return;
        }
        CefRequestContextSettings settings;
        if (!config.isPrivate) CefString(&settings.cache_path) = paths_->cachePath(config.container);
        if (config.presentation && config.presentation->GetBool("language"))
          CefString(&settings.accept_language_list) = config.presentation->GetString("languages");
#if defined(CEF_CLOAKFOX_INITIAL_SNAPSHOT_VERSION)
        if (initialSnapshotVersion_ != CEF_CLOAKFOX_INITIAL_SNAPSHOT_VERSION)
          throw std::runtime_error("Incompatible initial native snapshot hook");
        auto initial = CefDictionaryValue::Create();
        initial->SetInt("schemaVersion", 1);
        initial->SetString("container", config.container);
        initial->SetBool("private", config.isPrivate);
        initial->SetInt("revision", config.revision);
        initial->SetString("seed", config.seed);
        initial->SetBool("canvasEnabled", config.canvas);
        initial->SetBool("webgpuReadbackBlocked", config.blockWebGPUReadback);
        initial->SetDictionary("presentation", config.presentation ? config.presentation->Copy(false) : CefDictionaryValue::Create());
        if (fixtureScope_->restricted()) initial->SetString("fixtureOrigin", fixtureScope_->origin());
        auto encoded = CefValue::Create(); encoded->SetDictionary(initial);
        CefString(&settings.cloakfox_initial_snapshot) = CefWriteJSON(encoded, JSON_WRITER_DEFAULT);
#endif
        ContextEntry entry;
        entry.canvasEnabled = config.canvas;
        entry.blockWebGPUReadback = config.blockWebGPUReadback;
        entry.config = std::move(config);
        entry.configRequest = id;
        contexts_.emplace(key, std::move(entry));
        auto context = CefRequestContext::CreateContext(settings, new ContextHandler(this, key, fixtureScope_));
        if (!context) { contexts_.erase(key); throw std::runtime_error("Cannot create container context"); }
        contexts_.at(key).context = context;
      } catch (const std::exception& e) { error(id, e.what()); }
      return;
    }
    if (command == "open") {
      if (windowless_ && data->GetType("configRevision") != VTYPE_INT) {
        error(id, "Windowless browser requires acknowledged config"); return;
      }
      if (data->GetType("container") != VTYPE_STRING || data->GetType("url") != VTYPE_STRING ||
          (data->HasKey("private") && data->GetType("private") != VTYPE_BOOL)) {
        error(id, "Invalid open request"); return;
      }
      std::optional<bool> canvasEnabled;
      std::optional<bool> blockWebGPUReadback;
      if (data->HasKey("privacy")) {
        auto policy = data->GetType("privacy") == VTYPE_DICTIONARY
                          ? data->GetDictionary("privacy") : nullptr;
        if (!policy || policy->GetSize() == 0) {
          error(id, "Unsupported privacy policy"); return;
        }
        CefDictionaryValue::KeyList options;
        policy->GetKeys(options);
        for (const auto& option : options) {
          const auto name = option.ToString();
          if (policy->GetType(name) != VTYPE_BOOL ||
              (name == "canvas" ? canvasVersion_ == 0 :
               name == "blockWebGPUReadback" ? webgpuVersion_ == 0 : true)) {
            error(id, "Unsupported privacy policy"); return;
          }
          if (name == "canvas") canvasEnabled = policy->GetBool(name);
          else blockWebGPUReadback = policy->GetBool(name);
        }
      }
      const auto container = data->GetString("container").ToString();
      const auto url = data->GetString("url").ToString();
      if (!fixtureScope_->bind(url)) { error(id, "Navigation is outside the owned fixture origin"); return; }
      if (!navigable(url)) {
        error(id, "Only HTTP(S) navigation is supported"); return;
      }
      const bool isPrivate = data->GetBool("private");
      try {
        // Validate even private IDs; do not create their storage directories.
        if (!cloakfox::isValidContainerId(container))
          throw std::runtime_error("Invalid container ID");
        const auto key = std::string(isPrivate ? "private:" : "persistent:") + container;
        const auto found = contexts_.find(key);
        if (found != contexts_.end() && found->second.config) {
          const auto& configured = found->second;
          if (!configured.ready || data->HasKey("privacy") ||
              data->GetType("configRevision") != VTYPE_INT ||
              data->GetInt("configRevision") != configured.config->revision) {
            error(id, "Open requires acknowledged config revision and no legacy privacy policy"); return;
          }
        } else if (data->HasKey("configRevision")) {
          error(id, "Apply and acknowledge config before opening"); return;
        }
        auto& entry = contexts_[key];
        if (entry.context &&
            ((canvasEnabled && entry.canvasEnabled != *canvasEnabled) ||
             (blockWebGPUReadback && entry.blockWebGPUReadback != *blockWebGPUReadback))) {
          error(id, "Privacy policy conflicts with live container context"); return;
        }
        if (!entry.context) {
          entry.canvasEnabled = canvasEnabled.value_or(true);
          entry.blockWebGPUReadback = blockWebGPUReadback.value_or(false);
          CefRequestContextSettings settings;
          if (!isPrivate) CefString(&settings.cache_path) = paths_->cachePath(container);
          entry.context = CefRequestContext::CreateContext(settings, new ContextHandler(this, key, fixtureScope_));
          if (!entry.context) throw std::runtime_error("Cannot create container context");
        }
        OpenRequest request{id, url, container, isPrivate};
        if (entry.ready) openWindow(entry.context, request);
        else entry.pending.push_back(std::move(request));
      } catch (const std::exception& e) { error(id, e.what()); }
      return;
    }
    if (data->GetType("browser") != VTYPE_INT || !browsers_.count(data->GetInt("browser"))) {
      error(id, "Unknown browser"); return;
    }
    auto browser = browsers_.at(data->GetInt("browser"));
    if ((command == "viewport" || command == "input" || command == "textInputState" ||
        (command == "surface" && MACH_PORT_VALID(surfacePort_))) && probe_ && windowless_) {
      const auto found = offscreenClients_.find(browser->GetIdentifier());
      const auto& context = contexts_.at(browserContexts_.at(browser->GetIdentifier()));
      if (found == offscreenClients_.end() || !context.config ||
          data->GetType("configRevision") != VTYPE_INT ||
          data->GetInt("configRevision") != context.config->revision) {
        error(id, "Missing or stale windowless config revision"); return;
      }
      if (command == "textInputState") {
        if (!inputRouteMatches(browser->GetIdentifier(), data)) { error(id, "Missing or stale native input owner"); return; }
        auto query = message(); query->SetString("action", "query");
        submitIme(id, browser, query); return;
      }
      if (command == "viewport" || command == "surface") {
        if (data->GetType("width") != VTYPE_INT || data->GetType("height") != VTYPE_INT ||
            data->GetInt("width") < 1 || data->GetInt("height") < 1 ||
            data->GetInt("width") > 4096 || data->GetInt("height") > 4096) {
          error(id, "Invalid windowless viewport"); return;
        }
        if (command == "viewport" && surfaceRoutes_.contains(browser->GetIdentifier())) {
          error(id, "Native surface resize requires a new viewport revision"); return;
        }
        if (command == "surface") {
          const auto token = data->GetType("token") == VTYPE_STRING ? data->GetString("token").ToString() : "";
          if (token.size() != 32 || token.find_first_not_of("0123456789abcdef") != std::string::npos ||
              data->GetType("viewportRevision") != VTYPE_INT || data->GetInt("viewportRevision") <= 0) {
            error(id, "Invalid native surface ownership"); return;
          }
          cloakfox::SurfaceRoute route{};
          constexpr std::string_view hex = "0123456789abcdef";
          for (size_t i = 0; i < route.token.size(); ++i)
            route.token[i] = static_cast<uint8_t>((hex.find(token[i * 2]) << 4) | hex.find(token[i * 2 + 1]));
          if (route.token == cloakfox::SurfaceToken{} || retiredSurfaceTokens_.contains(route.token)) {
            error(id, "Retired or empty native surface owner"); return;
          }
          route.configRevision = context.config->revision;
          route.viewportRevision = data->GetInt("viewportRevision");
          route.width = data->GetInt("width"); route.height = data->GetInt("height");
          const auto browserId = browser->GetIdentifier();
          for (const auto& [other, active] : surfaceRoutes_) {
            if (other != browserId && active.token == route.token) {
              error(id, "Native surface belongs to another browser"); return;
            }
          }
          const auto previous = surfaceRoutes_.find(browserId);
          if (previous != surfaceRoutes_.end()) {
            if (previous->second == route) { emit(reply(id, true)); return; }
            if (previous->second.token != route.token ||
                previous->second.configRevision != route.configRevision ||
                route.viewportRevision <= previous->second.viewportRevision) {
              error(id, "Stale or changed native surface owner"); return;
            }
          }
          found->second->setSink({});
          browser->GetHost()->SendCaptureLostEvent();
          found->second->setViewport(route.width, route.height);
          surfaceRoutes_[browserId] = route;
          const auto port = surfacePort_;
          found->second->setSink([port, route](const cloakfox::OffscreenFrame& frame) {
            if (frame.width != static_cast<int>(route.width) || frame.height != static_cast<int>(route.height)) return true;
            return cloakfox::sendSurfaceBytes(port, route, frame.sequence, frame.bgra);
          });
        } else {
          browser->GetHost()->SendCaptureLostEvent();
          found->second->setViewport(data->GetInt("width"), data->GetInt("height"));
        }
        browser->GetHost()->WasResized();
        browser->GetHost()->Invalidate(PET_VIEW);
      } else if (data->GetType("kind") == VTYPE_STRING) {
        if (!inputRouteMatches(browser->GetIdentifier(), data)) { error(id, "Missing or stale native input owner"); return; }
        const auto kind = data->GetString("kind").ToString();
        if (kind != "editKey" && (data->HasKey("keyCode") || data->HasKey("shift"))) {
          error(id, "Unexpected editing key fields"); return;
        }
        if (kind != "ownedIme" && (data->HasKey("action") || data->HasKey("field") ||
            data->HasKey("selectionStart") || data->HasKey("selectionEnd") || data->HasKey("replacement"))) {
          error(id, "Unexpected native composition fields"); return;
        }
        if (kind != "commitText" && kind != "ownedIme" && data->HasKey("text")) {
          error(id, "Unexpected committed text field"); return;
        }
        if (kind == "ownedIme") {
#if defined(CEF_CLOAKFOX_OWNED_IME_VERSION)
          auto input = data->Copy(false);
          for (const auto* key : {"version", "id", "command", "browser", "configRevision", "token", "viewportRevision", "kind"}) input->Remove(key);
          if (!CefValidateOwnedInputCommand(input)) { error(id, "Invalid native composition command"); return; }
          submitIme(id, browser, input); return;
#else
          error(id, "Owned native composition hook unavailable"); return;
#endif
        } else if (kind == "commitText") {
          if (data->GetType("text") != VTYPE_STRING || data->HasKey("character") ||
              data->HasKey("keyCode") || data->HasKey("shift") || data->HasKey("x") || data->HasKey("y") ||
              data->HasKey("deltaX") || data->HasKey("deltaY")) {
            error(id, "Invalid committed text fields"); return;
          }
          const auto text = data->GetString("text");
          if (!text.length() || text.length() > 4096) { error(id, "Invalid committed text size"); return; }
          const auto units = text.ToString16();
          for (size_t i = 0; i < units.size(); ++i) {
            const auto unit = units[i];
            if ((unit < 32 && unit != 9 && unit != 10 && unit != 13) ||
                (unit >= 0x7f && unit <= 0x9f) || (unit >= 0xdc00 && unit <= 0xdfff)) {
              error(id, "Invalid committed text encoding"); return;
            }
            if (unit >= 0xd800 && unit <= 0xdbff) {
              if (++i >= units.size() || units[i] < 0xdc00 || units[i] > 0xdfff) {
                error(id, "Invalid committed text encoding"); return;
              }
            }
          }
          browser->GetHost()->ImeCommitText(text, CefRange::InvalidRange(), 0);
        } else if (kind == "selectAll") {
          CefDictionaryValue::KeyList keys;
          data->GetKeys(keys);
          for (const auto& key : keys) {
            const auto name=key.ToString();
            if (name!="version" && name!="id" && name!="command" && name!="browser" &&
                name!="configRevision" && name!="kind" && name!="token" && name!="viewportRevision") {
              error(id,"Unexpected editor command field");return;
            }
          }
          auto focused=browser->GetFocusedFrame();
          if (!focused || !focused->IsValid() || !focused->IsFocused()) {
            error(id,"No focused editor frame");return;
          }
          // Native selection only: no clipboard read, text extraction, script
          // injection or application-wide shortcut reaches this command.
          focused->SelectAll();
        } else if (kind == "editKey") {
          // This protocol only carries editing/navigation keys. Browser and OS
          // shortcuts remain with trusted chrome; arbitrary modifiers are not
          // accepted, even from an otherwise authenticated viewport owner.
          struct EditingKey { int code; int native; char16_t character; };
          static constexpr EditingKey editingKeys[] = {
            {8,51,8}, {9,48,9}, {13,36,13}, {27,53,27},
            {35,119,0xf72b}, {36,115,0xf729}, {37,123,0xf702},
            {38,126,0xf700}, {39,124,0xf703}, {40,125,0xf701}, {46,117,0xf728}
          };
          if (data->GetType("keyCode") != VTYPE_INT || data->GetType("shift") != VTYPE_BOOL ||
              data->HasKey("character") || data->HasKey("x") || data->HasKey("y") ||
              data->HasKey("deltaX") || data->HasKey("deltaY")) {
            error(id, "Invalid editing key fields"); return;
          }
          const EditingKey* editing = nullptr;
          for (const auto& candidate : editingKeys)
            if (candidate.code == data->GetInt("keyCode")) editing = &candidate;
          if (!editing) { error(id, "Unsupported editing key"); return; }
          CefKeyEvent key;
          key.type = KEYEVENT_RAWKEYDOWN;
          key.windows_key_code = editing->code;
          key.native_key_code = editing->native;
          key.character = key.unmodified_character = editing->character;
          key.modifiers = data->GetBool("shift") ? EVENTFLAG_SHIFT_DOWN : EVENTFLAG_NONE;
          browser->GetHost()->SendKeyEvent(key);
          // Return inserts text through Chromium's character event. A raw
          // keydown alone reaches handlers but leaves textareas unchanged.
          if (editing->code == 13) {
            key.type = KEYEVENT_CHAR;
            browser->GetHost()->SendKeyEvent(key);
          }
          key.type = KEYEVENT_KEYUP;
          browser->GetHost()->SendKeyEvent(key);
        } else if (kind == "char") {
          if (data->GetType("character") != VTYPE_INT || data->HasKey("x") || data->HasKey("y") ||
              data->HasKey("deltaX") || data->HasKey("deltaY") ||
              data->GetInt("character") < 32 || data->GetInt("character") > 126) {
            error(id, "Invalid feasibility character"); return;
          }
          CefKeyEvent key; key.type = KEYEVENT_CHAR;
          key.character = key.unmodified_character = static_cast<char16_t>(data->GetInt("character"));
          browser->GetHost()->SendKeyEvent(key);
        } else if (kind == "mouseDown" || kind == "mouseUp" || kind == "wheel") {
          const auto& viewport = found->second->viewport();
          if (data->GetType("x") != VTYPE_INT || data->GetType("y") != VTYPE_INT ||
              data->HasKey("character") || data->GetInt("x") < 0 || data->GetInt("y") < 0 ||
              data->GetInt("x") >= viewport.width || data->GetInt("y") >= viewport.height) {
            error(id, "Invalid feasibility mouse position"); return;
          }
          CefMouseEvent mouse; mouse.x = data->GetInt("x"); mouse.y = data->GetInt("y");
          if (kind == "wheel") {
            if (data->GetType("deltaX") != VTYPE_INT || data->GetType("deltaY") != VTYPE_INT ||
                data->GetInt("deltaX") < -4096 || data->GetInt("deltaX") > 4096 ||
                data->GetInt("deltaY") < -4096 || data->GetInt("deltaY") > 4096) {
              error(id, "Invalid feasibility wheel delta"); return;
            }
            browser->GetHost()->SendMouseWheelEvent(mouse, data->GetInt("deltaX"), data->GetInt("deltaY"));
          } else {
            if (data->HasKey("deltaX") || data->HasKey("deltaY")) {
              error(id, "Unexpected feasibility mouse delta"); return;
            }
            // Fence editing ownership synchronously before CEF processes the
            // pointer-down, so a metadata reply already in flight for the old
            // focus target cannot be accepted once the click may have moved it.
            if (kind == "mouseDown") fenceEditingOwnership(browser->GetIdentifier());
            browser->GetHost()->SetFocus(true);
            browser->GetHost()->SendMouseClickEvent(mouse, MBT_LEFT, kind == "mouseUp", 1);
          }
        } else { error(id, "Unsupported feasibility input kind"); return; }
      } else { error(id, "Missing feasibility input kind"); return; }
      emit(reply(id, true)); return;
    }
    if (command == "frame" && probe_ && windowless_) {
      const auto found = offscreenClients_.find(browser->GetIdentifier());
      if (found == offscreenClients_.end() || !found->second->frame().sequence) {
        error(id, "No owned paint available"); return;
      }
      const auto& frame = found->second->frame();
      const auto& context = contexts_.at(browserContexts_.at(browser->GetIdentifier()));
      if (!context.config) { error(id, "Missing frame config owner"); return; }
      auto result = reply(id, true);
      auto size = CefListValue::Create(); size->SetInt(0, frame.width); size->SetInt(1, frame.height);
      auto pixel = CefListValue::Create(); const auto corner = frame.corner();
      for (size_t i = 0; i < corner.size(); ++i) pixel->SetInt(i, corner[i]);
      result->SetString("paintSource", frame.accelerated ? "iosurface" : "cpu");
      result->SetList("size", size); result->SetList("cornerBGRA", pixel);
      result->SetBool("popupPainted", found->second->popupPainted());
      const auto& popup = found->second->popupRect();
      auto popupRect = CefListValue::Create();
      popupRect->SetInt(0, popup.x); popupRect->SetInt(1, popup.y);
      popupRect->SetInt(2, popup.width); popupRect->SetInt(3, popup.height);
      result->SetList("popupRect", popupRect);
      result->SetString("container", context.config->container);
      result->SetBool("private", context.config->isPrivate);
      result->SetInt("configRevision", context.config->revision);
      result->SetBool("topLevelWindow", browser->GetHost()->GetWindowHandle() != nullptr);
      emit(result); return;
    }
    if (command == "close") { emit(reply(id, true)); browser->GetHost()->CloseBrowser(true); return; }
    if (command == "navigate" && data->GetType("url") == VTYPE_STRING &&
        navigable(data->GetString("url").ToString())) {
      browser->GetMainFrame()->LoadURL(data->GetString("url")); emit(reply(id, true)); return;
    }
    if (command == "cdp" && probe_ && data->GetType("method") == VTYPE_STRING &&
        data->GetType("params") == VTYPE_DICTIONARY) {
      if (!browser->GetHost()->ExecuteDevToolsMethod(id, data->GetString("method"), data->GetDictionary("params")))
        error(id, "DevTools command rejected");
      return;
    }
    error(id, "Unknown or disabled command");
  }
 private:
  std::shared_ptr<cloakfox::ContainerPaths> paths_;
  cloakfox::ControlChannel control_;
  const bool probe_;
  const bool testKeychain_;
  const int testQuicPort_;
  const bool windowless_;
  const bool sharedTexture_;
  const mach_port_t surfacePort_;
  const std::shared_ptr<FixtureScope> fixtureScope_;
  int canvasVersion_ = 0;
  int webgpuVersion_ = 0;
  int identityVersion_ = 0;
  int initialSnapshotVersion_ = 0;
  int fixtureNetworkVersion_ = 0;
  int ownedImeVersion_ = 0, ownedImeStateVersion_ = 0;
  struct ImeType {CefString frame;bool editable,password;};
  std::map<int,ImeType> imeTypes_;
  std::map<int,uint64_t> imeTypeEpoch_;
  struct ImePending {
    int browser, revision;
    CefRefPtr<CefFrame> frame;
    std::optional<cloakfox::SurfaceRoute> route;
    uint64_t stateEpoch;
    bool query;
  };
  std::map<int, ImePending> imePending_;
  int lastId_ = 0;
  bool closing_ = false;
  int creatingWindows_ = 0;
  std::map<std::string, ContextEntry> contexts_;
  std::map<std::string, std::set<std::string>> retiredPrivateSeeds_;
  std::map<int, CefRefPtr<CefBrowser>> browsers_;
  std::map<int, CefRefPtr<cloakfox::OffscreenClient>> offscreenClients_;
  std::map<int, cloakfox::SurfaceRoute> surfaceRoutes_;
  std::set<cloakfox::SurfaceToken> retiredSurfaceTokens_;
  std::map<int, std::string> browserContexts_;
  IMPLEMENT_REFCOUNTING(Companion);
};
void ContextHandler::OnRequestContextInitialized(CefRefPtr<CefRequestContext> context) {
  owner_->contextReady(key_, context);
}
bool Client::OnProcessMessageReceived(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
    CefProcessId source, CefRefPtr<CefProcessMessage> packet) {
  return owner_->imeMessage(browser, frame, source, packet);
}
void Client::OnAfterCreated(CefRefPtr<CefBrowser> browser) {
  observers_[browser->GetIdentifier()] = browser->GetHost()->AddDevToolsMessageObserver(this);
  owner_->created(browser, requestId_, container_, private_, offscreen_);
  requestId_ = 0;
}
void Client::OnBeforeClose(CefRefPtr<CefBrowser> browser) {
  observers_.erase(browser->GetIdentifier()); owner_->closed(browser->GetIdentifier());
}
}
CefRefPtr<CefApp> CreateCompanionApp(std::shared_ptr<cloakfox::ContainerPaths> paths,
                                  bool enableProbe, bool testKeychain, int testQuicPort, bool windowless, bool sharedTexture, mach_port_t surfacePort) {
  return new Companion(std::move(paths), enableProbe, testKeychain, testQuicPort, windowless, sharedTexture, surfacePort);
}
void QuitCompanion() { if (current) current->quit(); }
void StopCompanionControl() { if (current) current->stopControl(); }
