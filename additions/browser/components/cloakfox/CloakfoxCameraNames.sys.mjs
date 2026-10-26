/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// Browser UI only. Never change raw device names, IDs, or website labels.
export const CAMERA_NAMES_PREF = 'cloakfox.camera.nicknames';
const unsafe = /[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/u;

export function serializeCameraNicknames(rows) {
  if (rows.length > 64) throw new Error('Save at most 64 camera nicknames.');
  const names = Object.create(null);
  for (const [rawName, rawNickname] of rows) {
    const name = rawName.trim();
    const nickname = rawNickname.trim();
    if (!name || name.length > 256 || unsafe.test(name)) {
      throw new Error('Enter the original camera name (up to 256 characters).');
    }
    if (!nickname || nickname.length > 80 || unsafe.test(nickname)) {
      throw new Error('Enter a nickname of 1–80 characters without control characters.');
    }
    if (Object.hasOwn(names, name)) throw new Error(`Each original camera name can appear only once: ${name}`);
    names[name] = nickname;
  }
  return JSON.stringify(names);
}

export function parseCameraNicknames(value) {
  try {
    const names = JSON.parse(value);
    if (!names || Array.isArray(names) || typeof names !== 'object') return {};
    return JSON.parse(serializeCameraNicknames(Object.entries(names)));
  } catch (_error) {
    return {};
  }
}

export function cameraDisplayName(name, names) {
  const nickname = Object.hasOwn(names, name) ? names[name] : '';
  return nickname && nickname !== name ? `${nickname} · ${name}` : name;
}

export function getCameraDisplayName(name) {
  return cameraDisplayName(name, parseCameraNicknames(
    Services.prefs.getStringPref(CAMERA_NAMES_PREF, '{}')
  ));
}
