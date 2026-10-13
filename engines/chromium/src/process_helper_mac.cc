// Copyright (c) 2013 The Chromium Embedded Framework Authors. All rights reserved.
// CEF BSD license: see THIRD_PARTY_LICENSES/CEF-LICENSE.txt.
#include "include/cef_app.h"
#include "include/cef_sandbox_mac.h"
#include "include/wrapper/cef_library_loader.h"
#if !defined(CEF_USE_SANDBOX)
#error "Cloakfox requires sandboxed helpers"
#endif
int main(int argc, char* argv[]) {
  CefScopedSandboxContext sandbox;
  if (!sandbox.Initialize(argc, argv)) return 1;
  CefScopedLibraryLoader loader;
  if (!loader.LoadInHelper()) return 1;
  return CefExecuteProcess(CefMainArgs(argc, argv), nullptr, nullptr);
}
