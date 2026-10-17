// Copyright (c) 2013 The Chromium Embedded Framework Authors. All rights reserved.
// CEF BSD license: see THIRD_PARTY_LICENSES/CEF-LICENSE.txt.
#include "include/cef_app.h"
#include "include/cef_render_process_handler.h"
#include "include/cef_frame.h"
#include "include/cef_process_message.h"
#include <set>
#include "include/cef_sandbox_mac.h"
#include "include/wrapper/cef_library_loader.h"
#if !defined(CEF_USE_SANDBOX)
#error "Cloakfox requires sandboxed helpers"
#endif
namespace {
// Private CEF process messages only. No V8 binding, DOM visitor or page script.
class OwnedInputRenderer : public CefApp, public CefRenderProcessHandler {
 public:
  CefRefPtr<CefRenderProcessHandler> GetRenderProcessHandler() override { return this; }
  bool OnProcessMessageReceived(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
      CefProcessId source, CefRefPtr<CefProcessMessage> message) override {
#if defined(CEF_CLOAKFOX_OWNED_IME_VERSION)
    if (source != PID_BROWSER || message->GetName() != "cloakfox.owned-ime.request.v1") return false;
    auto args = message->GetArgumentList();
    if (!frame || !frame->IsValid() || args->GetSize() != 2 || args->GetType(0) != VTYPE_INT ||
        args->GetInt(0) < 1 || args->GetType(1) != VTYPE_DICTIONARY) return true;
    subscribed_.insert(browser->GetIdentifier());
    auto command = args->GetDictionary(1);
    const bool query = command->GetSize() == 1 && command->GetType("action") == VTYPE_STRING &&
        command->GetString("action") == "query";
    const bool applied = query || CefPerformOwnedInput(frame, command);
    auto reply = CefProcessMessage::Create("cloakfox.owned-ime.reply.v1");
    reply->GetArgumentList()->SetInt(0, args->GetInt(0));
    reply->GetArgumentList()->SetBool(1, applied);
    reply->GetArgumentList()->SetDictionary(2, CefGetOwnedInputState(frame));
    frame->SendProcessMessage(PID_BROWSER, reply);
    return true;
#else
    return false;
#endif
  }
  void OnFocusedNodeChanged(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
                            CefRefPtr<CefDOMNode>) override {
#if defined(CEF_CLOAKFOX_OWNED_IME_VERSION)
    if (!subscribed_.contains(browser->GetIdentifier())) return;
    if (!frame) frame = browser->GetMainFrame();
    if (!frame || !frame->IsValid()) return;
    auto state = CefGetOwnedInputState(frame);
    if (!state) return;
    auto event = CefProcessMessage::Create("cloakfox.owned-ime.state.v1");
    event->GetArgumentList()->SetDictionary(0, state);
    frame->SendProcessMessage(PID_BROWSER, event);
#endif
  }
  void OnBrowserDestroyed(CefRefPtr<CefBrowser> browser) override { subscribed_.erase(browser->GetIdentifier()); }
 private:
  std::set<int> subscribed_;
  IMPLEMENT_REFCOUNTING(OwnedInputRenderer);
};
}
int main(int argc, char* argv[]) {
  CefScopedSandboxContext sandbox;
  if (!sandbox.Initialize(argc, argv)) return 1;
  CefScopedLibraryLoader loader;
  if (!loader.LoadInHelper()) return 1;
  return CefExecuteProcess(CefMainArgs(argc, argv), new OwnedInputRenderer, nullptr);
}
