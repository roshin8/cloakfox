/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// WebGPU policy is enforced by native Navigator/WorkerNavigator getters. A
// document actor runs too late for synchronous initial about:blank reads and
// replacing its accessor would contradict that native realm. Retain the actor
// registration for compatibility with existing documents, without page changes.
export class CloakfoxWebGPUChild extends JSWindowActorChild {
  handleEvent(_event) {}
}
