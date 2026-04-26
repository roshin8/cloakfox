# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Note: MOZ_APP_VENDOR and MOZ_APP_PROFILE must be set via imply_option() in browser/moz.configure
# See patches/librewolf/disable-data-reporting-at-compile-time.patch

MOZ_APP_NAME=cloakfox
MOZ_APP_BASENAME=Cloakfox
MOZ_APP_DISPLAYNAME=Cloakfox
MOZ_APP_REMOTINGNAME=cloakfox

# Network-facing UA brand: pin to vanilla "Firefox" so the User-Agent
# string reads `Firefox/<milestone>` instead of leaking the Cloakfox
# brand. nsHttpHandler::InitUserAgentComponents reads MOZ_APP_UA_NAME
# first and only falls back to MOZ_APP_NAME when this is empty.
# MOZ_APP_UA_VERSION is auto-set from the Firefox milestone via
# toolkit/moz.configure, so we don't override it here.
MOZ_APP_UA_NAME=Firefox
