/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox Math actor — parent half.
 *
 * JSWindowActor requires a parent class even if all work happens
 * child-side. This module exists so ChromeUtils.registerWindowActor
 * doesn't complain about a missing parent module.
 */

export class CloakfoxMathParent extends JSWindowActorParent {}
