/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

 "use strict";

 var { AppConstants } = ChromeUtils.importESModule(
   "resource://gre/modules/AppConstants.sys.mjs"
 );

 async function init(aEvent) {
   if (aEvent.target != document) {
     return;
   }

   document.getElementById("closeAboutDialog").addEventListener("command", () => {
     window.close();
   });

   var distroId = Services.prefs.getCharPref("distribution.id", "");
   if (distroId) {
     var distroAbout = Services.prefs.getStringPref("distribution.about", "");
     // If there is about text, we always show it.
     if (distroAbout) {
       var distroField = document.getElementById("distribution");
       distroField.value = distroAbout;
       distroField.style.display = "block";
     }
     // If it's not a mozilla distribution, show the rest,
     // unless about text exists, then we always show.
     if (!distroId.startsWith("mozilla-") || distroAbout) {
       var distroVersion = Services.prefs.getCharPref(
         "distribution.version",
         ""
       );
       if (distroVersion) {
         distroId += " - " + distroVersion;
       }

       var distroIdField = document.getElementById("distributionId");
       distroIdField.value = distroId;
       distroIdField.style.display = "block";
     }
   }

   // Display current version number
   let versionField = document.getElementById("versionNumber");
   versionField.textContent = AppConstants.MOZ_APP_VERSION_DISPLAY;

   window.sizeToContent();

   if (AppConstants.platform == "macosx") {
     window.moveTo(
       screen.availWidth / 2 - window.outerWidth / 2,
       screen.availHeight / 5
     );
   }
 }

 // Chrome documents disallow inline event handlers under Firefox 155's CSP.
 window.addEventListener("load", init, { once: true });
