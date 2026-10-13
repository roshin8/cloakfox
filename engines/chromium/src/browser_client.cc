// Portions Copyright (c) 2013 The Chromium Embedded Framework Authors.
// Views window/delegate integration adapted from the BSD-licensed cefsimple.
// See THIRD_PARTY_LICENSES/CEF-LICENSE.txt.
#include "browser_client.h"
#include "control_channel.h"
#include <algorithm>
#include <iostream>
#include <map>
#include <thread>
#include "include/base/cef_callback.h"
#include "include/cef_devtools_message_observer.h"
#include "include/cef_parser.h"
#include "include/cef_request_context_handler.h"
#include "include/cef_task.h"
#include "include/cef_version.h"
#include "include/views/cef_browser_view.h"
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

class WindowDelegate : public CefWindowDelegate {
 public:
  explicit WindowDelegate(CefRefPtr<CefBrowserView> view) : view_(view) {}
  void OnWindowCreated(CefRefPtr<CefWindow> window) override {
    window->AddChildView(view_); window->Show();
  }
  void OnWindowDestroyed(CefRefPtr<CefWindow>) override { view_ = nullptr; }
  bool CanClose(CefRefPtr<CefWindow>) override {
    auto browser = view_->GetBrowser();
    return !browser || browser->GetHost()->TryCloseBrowser();
  }
  CefSize GetPreferredSize(CefRefPtr<CefView>) override { return CefSize(1000, 720); }
  cef_runtime_style_t GetWindowRuntimeStyle() override { return CEF_RUNTIME_STYLE_CHROME; }
 private:
  CefRefPtr<CefBrowserView> view_;
  IMPLEMENT_REFCOUNTING(WindowDelegate);
};
class ViewDelegate : public CefBrowserViewDelegate {
 public:
  cef_runtime_style_t GetBrowserRuntimeStyle() override { return CEF_RUNTIME_STYLE_CHROME; }
  ChromeToolbarType GetChromeToolbarType(CefRefPtr<CefBrowserView>) override {
    return CEF_CTT_NORMAL;
  }
  bool OnPopupBrowserViewCreated(CefRefPtr<CefBrowserView>,
      CefRefPtr<CefBrowserView> popup, bool) override {
    CefWindow::CreateTopLevelWindow(new WindowDelegate(popup)); return true;
  }
 private:
  IMPLEMENT_REFCOUNTING(ViewDelegate);
};

class Companion;
Companion* current = nullptr;
class ContextHandler : public CefRequestContextHandler {
 public:
  ContextHandler(Companion* owner, std::string key) : owner_(owner), key_(std::move(key)) {}
  void OnRequestContextInitialized(CefRefPtr<CefRequestContext> context) override;
 private:
  Companion* owner_;
  const std::string key_;
  IMPLEMENT_REFCOUNTING(ContextHandler);
};
class Client : public CefClient, public CefLifeSpanHandler,
               public CefRequestHandler, public CefPermissionHandler,
               public CefDevToolsMessageObserver {
 public:
  Client(Companion* owner, int requestId, std::string container, bool isPrivate)
      : owner_(owner), requestId_(requestId), container_(std::move(container)),
        private_(isPrivate) {}
  CefRefPtr<CefLifeSpanHandler> GetLifeSpanHandler() override { return this; }
  CefRefPtr<CefRequestHandler> GetRequestHandler() override { return this; }
  CefRefPtr<CefPermissionHandler> GetPermissionHandler() override { return this; }
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
  std::map<int, CefRefPtr<CefRegistration>> observers_;
  IMPLEMENT_REFCOUNTING(Client);
};

class Companion : public CefApp, public CefBrowserProcessHandler {
 public:
  Companion(std::shared_ptr<cloakfox::ContainerPaths> paths, bool probe, bool testKeychain, int testQuicPort)
      : paths_(std::move(paths)), probe_(probe), testKeychain_(testKeychain), testQuicPort_(testQuicPort) { current = this; }
  ~Companion() override { current = nullptr; }
  CefRefPtr<CefBrowserProcessHandler> GetBrowserProcessHandler() override { return this; }
  void OnBeforeCommandLineProcessing(const CefString& processType,
                                    CefRefPtr<CefCommandLine> command) override {
    if (processType.empty()) {
      command->AppendSwitch("no-first-run");
      command->AppendSwitch("disable-background-networking");
      command->AppendSwitch("disable-component-update");
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
               const std::string& container, bool isPrivate) {
    if (requestId > 0) --creatingWindows_;
    browsers_[browser->GetIdentifier()] = browser;
    const auto key = std::string(isPrivate ? "private:" : "persistent:") + container;
    browserContexts_[browser->GetIdentifier()] = key;
    if (requestId > 0) --contexts_.at(key).creating;
    auto data = reply(requestId, true); data->SetString("event", "opened");
    data->SetInt("browser", browser->GetIdentifier());
    data->SetString("container", container); data->SetBool("private", isPrivate);
    if (requestId == 0) data->Remove("id");
    emit(data);
    if (closing_) browser->GetHost()->CloseBrowser(true);
  }
  void closed(int id) {
    const auto key = browserContexts_.at(id);
    browserContexts_.erase(id);
    browsers_.erase(id);
    if (key.rfind("private:", 0) == 0) {
      bool live = false;
      for (const auto& [browserId, contextKey] : browserContexts_) live = live || contextKey == key;
      auto entry = contexts_.find(key);
      if (!live && entry != contexts_.end() && entry->second.pending.empty() && !entry->second.creating)
        contexts_.erase(entry);
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
      entry.pending.clear();
    }
    if (browsers_.empty() && !creatingWindows_) { contexts_.clear(); CefQuitMessageLoop(); return; }
    for (const auto& [id, browser] : browsers_) browser->GetHost()->CloseBrowser(true);
  }
  struct OpenRequest { int id; std::string url; std::string container; bool isPrivate; };
  struct ContextEntry {
    CefRefPtr<CefRequestContext> context;
    bool ready = false;
    int creating = 0;
    std::vector<OpenRequest> pending;
  };
  void openWindow(CefRefPtr<CefRequestContext> context, const OpenRequest& request) {
    CefBrowserSettings settings;
    ++creatingWindows_;
    const auto key = std::string(request.isPrivate ? "private:" : "persistent:") + request.container;
    ++contexts_.at(key).creating;
    auto view = CefBrowserView::CreateBrowserView(
        new Client(this, request.id, request.container, request.isPrivate),
        request.url, settings, nullptr, context, new ViewDelegate);
    if (!view) { --creatingWindows_; --contexts_.at(key).creating; error(request.id, "Cannot create browser view"); return; }
    CefWindow::CreateTopLevelWindow(new WindowDelegate(view));
  }
  void contextReady(const std::string& key, CefRefPtr<CefRequestContext> context) {
    if (closing_ || !contexts_.count(key)) return;
    auto& entry = contexts_.at(key);
    entry.context = context;
    entry.ready = true;
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
      {"open", {"version", "id", "command", "container", "url", "private"}},
      {"quit", {"version", "id", "command"}},
      {"close", {"version", "id", "command", "browser"}},
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
    if (command == "open") {
      if (data->GetType("container") != VTYPE_STRING || data->GetType("url") != VTYPE_STRING ||
          (data->HasKey("private") && data->GetType("private") != VTYPE_BOOL)) {
        error(id, "Invalid open request"); return;
      }
      const auto container = data->GetString("container").ToString();
      const auto url = data->GetString("url").ToString();
      if (!navigable(url)) {
        error(id, "Only HTTP(S) navigation is supported"); return;
      }
      const bool isPrivate = data->GetBool("private");
      try {
        // Validate even private IDs; do not create their storage directories.
        if (!cloakfox::isValidContainerId(container))
          throw std::runtime_error("Invalid container ID");
        const auto key = std::string(isPrivate ? "private:" : "persistent:") + container;
        auto& entry = contexts_[key];
        if (!entry.context) {
          CefRequestContextSettings settings;
          if (!isPrivate) CefString(&settings.cache_path) = paths_->cachePath(container);
          entry.context = CefRequestContext::CreateContext(settings, new ContextHandler(this, key));
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
  int lastId_ = 0;
  bool closing_ = false;
  int creatingWindows_ = 0;
  std::map<std::string, ContextEntry> contexts_;
  std::map<int, CefRefPtr<CefBrowser>> browsers_;
  std::map<int, std::string> browserContexts_;
  IMPLEMENT_REFCOUNTING(Companion);
};
void ContextHandler::OnRequestContextInitialized(CefRefPtr<CefRequestContext> context) {
  owner_->contextReady(key_, context);
}
void Client::OnAfterCreated(CefRefPtr<CefBrowser> browser) {
  observers_[browser->GetIdentifier()] = browser->GetHost()->AddDevToolsMessageObserver(this);
  owner_->created(browser, requestId_, container_, private_);
  requestId_ = 0;
}
void Client::OnBeforeClose(CefRefPtr<CefBrowser> browser) {
  observers_.erase(browser->GetIdentifier()); owner_->closed(browser->GetIdentifier());
}
}
CefRefPtr<CefApp> CreateCompanionApp(std::shared_ptr<cloakfox::ContainerPaths> paths,
                                  bool enableProbe, bool testKeychain, int testQuicPort) {
  return new Companion(std::move(paths), enableProbe, testKeychain, testQuicPort);
}
void QuitCompanion() { if (current) current->quit(); }
void StopCompanionControl() { if (current) current->stopControl(); }
