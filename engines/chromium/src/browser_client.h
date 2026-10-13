#pragma once
#include <memory>
#include "container_paths.h"
#include "include/cef_app.h"

CefRefPtr<CefApp> CreateCompanionApp(std::shared_ptr<cloakfox::ContainerPaths> paths,
                                  bool enableProbe, bool testKeychain, int testQuicPort);
void QuitCompanion();
void StopCompanionControl();
