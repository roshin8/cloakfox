/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
#ifndef CLOAKFOX_ENGINE_HOST_H
#define CLOAKFOX_ENGINE_HOST_H
#include "nsICloakfoxEngineHost.h"
#include "nsIObserver.h"
#include "nsINamed.h"
#include "nsITimer.h"
#include <memory>
#ifdef __OBJC__
@class NSView, NSEvent;
// Preserve the selected native viewport when Gecko restores its ChildView.
bool CloakfoxRouteEngineKeyDown(NSView* parent, NSEvent* event);
#endif

class CloakfoxEngineHost final : public nsICloakfoxEngineHost,
                                public nsITimerCallback, public nsIObserver, public nsINamed {
 public:
  CloakfoxEngineHost();
  NS_DECL_ISUPPORTS
  NS_DECL_NSICLOAKFOXENGINEHOST
  NS_DECL_NSITIMERCALLBACK
  NS_DECL_NSIOBSERVER
  NS_DECL_NSINAMED
 private:
  ~CloakfoxEngineHost();
  struct HostState;
  std::unique_ptr<HostState> mState;
};
#endif
