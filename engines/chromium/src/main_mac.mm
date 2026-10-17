// Portions Copyright (c) 2013 The Chromium Embedded Framework Authors.
// Cocoa event-loop integration follows CEF's BSD-licensed cefsimple example.
// See THIRD_PARTY_LICENSES/CEF-LICENSE.txt.
#import <Cocoa/Cocoa.h>
#include <iostream>
#include <unistd.h>
#include "browser_client.h"
#include "surface_launch_mac.h"
#include "include/cef_application_mac.h"
#include "include/cef_command_line.h"
#include "include/wrapper/cef_helpers.h"
#include "include/wrapper/cef_library_loader.h"

#if !defined(CEF_USE_SANDBOX)
#error "The Cloakfox companion requires CEF sandbox support"
#endif

@interface CloakfoxApplication : NSApplication <CefAppProtocol> {
  BOOL handlingSendEvent_;
}
@end
@implementation CloakfoxApplication
- (BOOL)isHandlingSendEvent { return handlingSendEvent_; }
- (void)setHandlingSendEvent:(BOOL)value { handlingSendEvent_ = value; }
- (void)sendEvent:(NSEvent*)event {
  CefScopedSendingEvent scope;
  [super sendEvent:event];
}
- (void)terminate:(id)sender { QuitCompanion(); }
@end

int main(int argc, char* argv[]) {
  struct SurfacePort {
    mach_port_t port = MACH_PORT_NULL;
    ~SurfacePort() { if (MACH_PORT_VALID(port)) mach_port_deallocate(mach_task_self(), port); }
  } surface;
  bool rawProbe = false, rawTestKeychain = false, hostRequested = false;
  std::string hostName;
  // Do not let Chromium command-line overrides bypass the companion's policy.
  for (int i = 1; i < argc; ++i) {
    const std::string arg(argv[i]);
    rawProbe |= arg == "--enable-probe";
    rawTestKeychain |= arg == "--test-keychain";
    if (arg.rfind("--host-rendezvous=", 0) == 0) {
      if (hostRequested) { std::cerr << "Duplicate native host rendezvous\n"; return 2; }
      hostRequested = true; hostName = arg.substr(std::string("--host-rendezvous=").size());
    }
    if (arg != "--enable-probe" && arg != "--test-keychain" && arg != "--windowless" && arg != "--shared-texture" &&
        arg.rfind("--profile-root=", 0) != 0 && arg.rfind("--test-quic-port=", 0) != 0 &&
        arg.rfind("--host-rendezvous=", 0) != 0) {
      std::cerr << "Unsupported launch option\n"; return 2;
    }
  }
  if (hostRequested) {
    const std::string prefix = "org.cloakfox.engine-host." + std::to_string(getppid()) + ".";
    if (!rawProbe || !rawTestKeychain || hostName.size() != prefix.size() + 32 ||
        hostName.rfind(prefix, 0) != 0 ||
        hostName.substr(prefix.size()).find_first_not_of("0123456789abcdef") != std::string::npos) {
      std::cerr << "Invalid native host rendezvous\n"; return 2;
    }
    // Authenticate before loading the large framework, initializing AppKit or
    // creating a profile. Cold dyld signature checks must not delay the hello.
    surface.port = cloakfox::connectSurfaceHost(hostName.c_str(), 5000);
    if (!MACH_PORT_VALID(surface.port)) { std::cerr << "Native host authentication failed\n"; return 2; }
  }
  CefScopedLibraryLoader loader;
  if (!loader.LoadInMain()) return 1;
  CefMainArgs args(argc, argv);
  @autoreleasepool {
    // The controller owns session restoration. Suppress AppKit's unrelated
    // crash-recovery modal using process-local defaults, not system settings.
    [[NSUserDefaults standardUserDefaults] registerDefaults:@{
      @"ApplePersistenceIgnoreState": @YES,
      @"NSQuitAlwaysKeepsWindows": @NO
    }];
    [CloakfoxApplication sharedApplication];
    if (![NSApp isKindOfClass:[CloakfoxApplication class]]) return 1;
    auto command = CefCommandLine::CreateCommandLine();
    command->InitFromArgv(argc, argv);
    try {
      const bool windowless = command->HasSwitch("windowless");
      const bool sharedTexture = command->HasSwitch("shared-texture");
      if (sharedTexture && !windowless) throw std::runtime_error("Shared texture requires windowless mode");
      if (windowless && (!command->HasSwitch("enable-probe") || !command->HasSwitch("test-keychain")))
        throw std::runtime_error("Windowless feasibility mode requires explicit test options");
      int testQuicPort = 0;
      if (command->HasSwitch("test-quic-port")) {
        const auto port = command->GetSwitchValue("test-quic-port").ToString();
        if (!command->HasSwitch("enable-probe") || !command->HasSwitch("test-keychain") ||
            port.empty() || port.size() > 5 || port.find_first_not_of("0123456789") != std::string::npos ||
            std::stoi(port) < 1 || std::stoi(port) > 65535)
          throw std::runtime_error("Invalid loopback QUIC test option");
        testQuicPort = std::stoi(port);
      }
      auto paths = std::make_shared<cloakfox::ContainerPaths>(command->GetSwitchValue("profile-root").ToString());
      paths->configureKeychainMode(command->HasSwitch("test-keychain"));
      CefSettings settings;
      // Chrome-style CEF requires each profile to be an immediate child of
      // user_data_dir; otherwise it silently falls back to OffTheRecord.
      CefString(&settings.root_cache_path) = paths->root() + "/containers";
      // The unconfigured global context must never select the last-used user
      // container before the controller supplies its immutable snapshot.
      CefString(&settings.cache_path) = paths->bootstrapCachePath();
      CefString(&settings.log_file) = paths->root() + "/chromium.log";
      settings.log_severity = LOGSEVERITY_WARNING;
      settings.no_sandbox = false;
      settings.windowless_rendering_enabled = windowless;
      settings.command_line_args_disabled = true;
      auto app = CreateCompanionApp(paths, command->HasSwitch("enable-probe"),
                                   command->HasSwitch("test-keychain"), testQuicPort, windowless, sharedTexture, surface.port);
      if (!CefInitialize(args, settings, app, nullptr)) return CefGetExitCode();
      CefRunMessageLoop();
      StopCompanionControl();
      CefShutdown();
    } catch (const std::exception& e) {
      std::cerr << e.what() << '\n'; return 2;
    }
  }
  return 0;
}
