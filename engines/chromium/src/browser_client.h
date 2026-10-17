#pragma once
#include <memory>
#include <mach/mach.h>
#include "container_paths.h"
#include "include/cef_app.h"

CefRefPtr<CefApp> CreateCompanionApp(std::shared_ptr<cloakfox::ContainerPaths> paths,
                                  bool enableProbe, bool testKeychain, int testQuicPort, bool windowless, bool sharedTexture, mach_port_t surfacePort);
void QuitCompanion();
void StopCompanionControl();
