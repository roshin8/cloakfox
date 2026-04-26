# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Note: MOZ_APP_VENDOR and MOZ_APP_PROFILE must be set via imply_option() in browser/moz.configure
# See patches/librewolf/disable-data-reporting-at-compile-time.patch

MOZ_APP_NAME=cloakfox
MOZ_APP_BASENAME=Cloakfox
MOZ_APP_DISPLAYNAME=Cloakfox
MOZ_APP_REMOTINGNAME=cloakfox

# MOZ_APP_UA_NAME=Firefox (pin UA brand to vanilla Firefox) is set
# via imply_option() in browser/moz.configure — see the librewolf
# disable-data-reporting-at-compile-time.patch. project_flag options
# can't be set from confvars; mach hard-errors if you try.
