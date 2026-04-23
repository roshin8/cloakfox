/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox Keyboard actor — empty parent half. JSWindowActor requires
 * a parent module even if all work happens child-side. */

export class CloakfoxKeyboardParent extends JSWindowActorParent {}
