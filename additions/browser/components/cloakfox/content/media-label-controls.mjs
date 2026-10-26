/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

export function initMediaWebsiteLabels(kind, { document, navigator, prefs, Option }) {
  const names = {
    camera: { one: "webcam", many: "webcams", title: "Webcam" },
    microphone: { one: "microphone", many: "microphones", title: "Microphone" },
    speaker: { one: "speaker", many: "speakers", title: "Speaker" },
  };
  if (!Object.hasOwn(names, kind)) throw new Error("Unsupported media device kind");
  const { one, many, title } = names[kind];
  const devicePref = `cloakfox.${kind}.website_label_map`;
  const deviceSelect = document.getElementById(`cfx-${kind}-website-device`);
  const deviceName = document.getElementById(`cfx-${kind}-device-name`);
  const deviceSave = document.getElementById(`cfx-${kind}-device-save`);
  const deviceReset = document.getElementById(`cfx-${kind}-device-reset`);
  const deviceRefresh = document.getElementById(`cfx-${kind}-device-refresh`);
  const deviceStatus = document.getElementById(`cfx-${kind}-device-status`);
  const validLabel = value => value.length <= 128 && !/[\u0000-\u001f\u007f]/.test(value);
  function readDeviceNames() {
    try {
      const parsed = JSON.parse(prefs.getStringPref(devicePref, "{}"));
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object" || Object.keys(parsed).length > 64) return Object.create(null);
      return Object.assign(Object.create(null), Object.fromEntries(Object.entries(parsed)
        .filter(([, value]) => typeof value === "string" && value.trim() && validLabel(value.trim()))));
    } catch (_error) { return Object.create(null); }
  }
  function showDeviceName() {
    deviceName.value = readDeviceNames()[deviceSelect.value] || "";
    deviceName.setCustomValidity("");
    deviceName.removeAttribute("aria-invalid");
    deviceStatus.textContent = deviceName.value ? "Saved name for this device." : "Using the fallback label.";
  }
  async function refreshDevices() {
    const previous = deviceSelect.value;
    deviceRefresh.disabled = true;
    deviceSelect.disabled = deviceName.disabled = deviceSave.disabled = deviceReset.disabled = true;
    try {
      const inventory = kind === "camera"
        ? await navigator.mediaDevices.getCloakfoxCameras()
        : (await navigator.mediaDevices.getCloakfoxAudioDevices()).filter(device =>
            device.kind === (kind === "microphone" ? "audioinput" : "audiooutput"));
      // PipeWire can return a permission-required placeholder with no stable ID.
      // Such an entry cannot support a saved name; never offer a no-op Save.
      const devices = inventory.filter(device => device.deviceId);
      deviceSelect.replaceChildren();
      const counts = new Map();
      for (const device of devices) counts.set(device.label, (counts.get(device.label) || 0) + 1);
      const seen = new Map();
      for (const device of devices) {
        const index = (seen.get(device.label) || 0) + 1;
        seen.set(device.label, index);
        const label = (device.label || title) + (counts.get(device.label) > 1 ? ` (${index})` : "");
        deviceSelect.append(new Option(label, device.deviceId));
      }
      if (!devices.length) {
        const needsAccess = inventory.length > 0;
        deviceSelect.append(new Option(needsAccess ? `${title} access required` : `No ${many} found`, ""));
        deviceStatus.textContent = needsAccess
          ? (kind === "speaker" ? "Speaker details are unavailable. Check the audio device connection, then refresh speakers."
            : `${title} details are hidden until ${kind} access is allowed. Allow ${kind} access in Cloakfox or system settings, then refresh ${many}.`)
          : `Connect a ${one}, then click Refresh ${many}.`;
        return;
      }
      if (devices.some(device => device.deviceId === previous)) deviceSelect.value = previous;
      deviceSelect.disabled = deviceName.disabled = deviceSave.disabled = deviceReset.disabled = false;
      showDeviceName();
    } catch (_error) {
      deviceSelect.replaceChildren(new Option(`${title}s unavailable`, ""));
      deviceStatus.textContent = `Could not list ${many}. Click Refresh ${many} to try again.`;
    } finally { deviceRefresh.disabled = false; }
  }
  deviceSelect.addEventListener("change", showDeviceName);
  deviceRefresh.addEventListener("click", refreshDevices);
  deviceName.addEventListener("input", () => {
    deviceName.setCustomValidity("");
    deviceName.removeAttribute("aria-invalid");
    deviceStatus.textContent = `Unsaved name. Click Save ${one} name to apply it.`;
  });
  function saveDeviceName(value) {
    if (deviceSelect.disabled || !deviceSelect.value) return;
    const label = value.trim();
    if (!validLabel(label)) {
      deviceName.setCustomValidity("Use up to 128 characters without control characters.");
      deviceName.setAttribute("aria-invalid", "true");
      deviceName.reportValidity();
      return;
    }
    const names = readDeviceNames();
    if (label) names[deviceSelect.value] = label;
    else delete names[deviceSelect.value];
    if (Object.keys(names).length > 64) {
      deviceStatus.textContent = `Save names for at most 64 ${many}.`;
      return;
    }
    prefs.setStringPref(devicePref, JSON.stringify(names));
    deviceName.value = label;
    deviceStatus.textContent = "Saved. Reload website tabs to apply.";
  }
  document.getElementById(`cfx-${kind}-device-form`).addEventListener("submit", event => {
    event.preventDefault(); saveDeviceName(deviceName.value);
  });
  deviceReset.addEventListener("click", () => saveDeviceName(""));
  refreshDevices();
  const websiteLabels = document.getElementById(`cfx-${kind}-website-label`);
  const websiteLabelPref = `cloakfox.${kind}.website_label_style`;
  const customLabelPref = `cloakfox.${kind}.website_label_custom`;
  const customForm = document.getElementById(`cfx-${kind}-website-custom-form`);
  const customInput = document.getElementById(`cfx-${kind}-website-custom`);
  const websiteStatus = document.getElementById(`cfx-${kind}-website-status`);
  const savedMessage = "Saved. Reload website tabs to apply.";
  const savedLabelStyle = prefs.getIntPref(websiteLabelPref, 0);
  websiteLabels.value = String([0, 1, 2, 3, 4].includes(savedLabelStyle) ? savedLabelStyle : 0);
  customInput.value = prefs.getStringPref(customLabelPref, "");
  customForm.hidden = websiteLabels.value !== "4";
  websiteLabels.addEventListener("change", () => {
    const style = Number(websiteLabels.value);
    if (![0, 1, 2, 3, 4].includes(style)) return;
    customForm.hidden = style !== 4;
    customInput.setCustomValidity("");
    customInput.removeAttribute("aria-invalid");
    if (style === 4) {
      websiteStatus.textContent = `Enter a custom name, then save the ${kind} label.`;
      customInput.focus();
      return;
    }
    prefs.setIntPref(websiteLabelPref, style);
    websiteStatus.textContent = savedMessage;
  });
  customInput.addEventListener("input", () => {
    customInput.setCustomValidity("");
    customInput.removeAttribute("aria-invalid");
    websiteStatus.textContent = `Unsaved custom label. Click Save ${kind} label to apply it.`;
  });
  customForm.addEventListener("submit", event => {
    event.preventDefault();
    const label = customInput.value.trim();
    if (!label || label.length > 128 || /[\u0000-\u001f\u007f]/.test(label)) {
      const message = `Enter a ${kind} label of 1–128 characters without control characters.`;
      customInput.setCustomValidity(message);
      customInput.setAttribute("aria-invalid", "true");
      websiteStatus.textContent = message;
      customInput.reportValidity();
      return;
    }
    prefs.setStringPref(customLabelPref, label);
    prefs.setIntPref(websiteLabelPref, 4);
    customInput.value = label;
    websiteStatus.textContent = savedMessage;
  });

}

export function initCameraExposure({ document, navigator, getContext, save }) {
  const mode = document.getElementById('cfx-camera-exposure-mode');
  const list = document.getElementById('cfx-camera-exposure-devices');
  const status = document.getElementById('cfx-camera-exposure-status');
  const refreshButton = document.getElementById('cfx-camera-exposure-refresh');
  const saveButton = document.getElementById('cfx-camera-exposure-save');
  let revision = 0, limit = 1, inputs = [];
  function sync() {
    const selected = inputs.filter(input => input.checked);
    const automatic = mode.value === 'automatic';
    list.hidden = automatic;
    for (const input of inputs) input.disabled = !input.checked && selected.length >= limit;
    saveButton.disabled = !automatic && selected.length > limit;
    status.textContent = automatic
      ? `Automatic: up to ${limit} ${limit === 1 ? "camera" : "cameras"}.`
      : selected.length > limit
        ? `${selected.length} selected, but the maximum is ${limit}. Uncheck cameras before saving.`
        : `${selected.length} of ${limit} selected. ${selected.length >= limit && limit > 0 ? "Uncheck one to choose another." : ""}`;
  }
  async function refresh() {
    const token = ++revision, context = getContext();
    mode.disabled = saveButton.disabled = refreshButton.disabled = true;
    try {
      const cameras = (await navigator.mediaDevices.getCloakfoxCameras()).filter(d => d.deviceId);
      if (token !== revision) return;
      limit = context.limit;
      mode.value = context.ids === null ? 'automatic' : 'choose';
      const ids = new Set(context.ids || []), devices = [...cameras];
      for (const id of ids) if (!devices.some(d => d.deviceId === id)) {
        devices.push({deviceId:id,label:'Disconnected camera'});
      }
      list.replaceChildren(); inputs = [];
      const counts = new Map(), seen = new Map();
      for (const device of devices) counts.set(device.label,(counts.get(device.label)||0)+1);
      for (const device of devices) {
        const row = document.createElement('label'); row.className = 'flag-row';
        const input = document.createElement('input'); input.type = 'checkbox';
        input.value = device.deviceId; input.checked = ids.has(device.deviceId);
        input.addEventListener('change',sync);
        const number = (seen.get(device.label)||0)+1; seen.set(device.label,number);
        const text = document.createElement('span');
        text.textContent = (device.label || 'Webcam') + (counts.get(device.label)>1 ? ` (${number})` : '');
        row.append(input,text); list.append(row); inputs.push(input);
      }
      mode.disabled = false; sync();
    } catch (_) {
      if (token === revision) status.textContent = 'Could not list cameras. Refresh to try again.';
    } finally { if (token === revision) refreshButton.disabled = false; }
  }
  mode.addEventListener('change',sync);
  refreshButton.addEventListener('click',refresh);
  document.getElementById('cfx-camera-exposure-form').addEventListener('submit',event => {
    event.preventDefault();
    if (mode.disabled || saveButton.disabled) return;
    save(mode.value === 'automatic' ? null : inputs.filter(input=>input.checked).map(input=>input.value));
    status.textContent = 'Saved for this container. Reload websites and stop existing camera streams to apply it.';
  });
  refresh();
  return refresh;
}

export function initMicrophoneExposure({ document, navigator, getContext, save }) {
  const mode = document.getElementById('cfx-microphone-exposure-mode');
  const list = document.getElementById('cfx-microphone-exposure-devices');
  const status = document.getElementById('cfx-microphone-exposure-status');
  const refreshButton = document.getElementById('cfx-microphone-exposure-refresh');
  const saveButton = document.getElementById('cfx-microphone-exposure-save');
  let revision = 0, limit = 1, inputs = [];
  function sync() {
    const selected = inputs.filter(input => input.checked);
    const automatic = mode.value === 'automatic';
    list.hidden = automatic;
    for (const input of inputs) input.disabled = !input.checked && selected.length >= limit;
    saveButton.disabled = !automatic && selected.length > limit;
    status.textContent = automatic
      ? `Automatic: up to ${limit} ${limit === 1 ? "microphone" : "microphones"}.`
      : selected.length > limit
        ? `${selected.length} selected, but the maximum is ${limit}. Uncheck microphones before saving.`
        : `${selected.length} of ${limit} selected. ${selected.length >= limit && limit > 0 ? "Uncheck one to choose another." : ""}`;
  }
  async function refresh() {
    const token = ++revision, context = getContext();
    mode.disabled = saveButton.disabled = refreshButton.disabled = true;
    try {
      const microphones = (await navigator.mediaDevices.getCloakfoxAudioDevices()).filter(d => d.deviceId && d.kind === 'audioinput');
      if (token !== revision) return;
      limit = context.limit;
      mode.value = context.ids === null ? 'automatic' : 'choose';
      const ids = new Set(context.ids || []), devices = [...microphones];
      for (const id of ids) if (!devices.some(d => d.deviceId === id)) {
        devices.push({deviceId:id,label:'Disconnected microphone'});
      }
      list.replaceChildren(); inputs = [];
      const counts = new Map(), seen = new Map();
      for (const device of devices) counts.set(device.label,(counts.get(device.label)||0)+1);
      for (const device of devices) {
        const row = document.createElement('label'); row.className = 'flag-row';
        const input = document.createElement('input'); input.type = 'checkbox';
        input.value = device.deviceId; input.checked = ids.has(device.deviceId);
        input.addEventListener('change',sync);
        const number = (seen.get(device.label)||0)+1; seen.set(device.label,number);
        const text = document.createElement('span');
        text.textContent = (device.label || 'Microphone') + (counts.get(device.label)>1 ? ` (${number})` : '');
        row.append(input,text); list.append(row); inputs.push(input);
      }
      mode.disabled = false; sync();
    } catch (_) {
      if (token === revision) status.textContent = 'Could not list microphones. Refresh to try again.';
    } finally { if (token === revision) refreshButton.disabled = false; }
  }
  mode.addEventListener('change',sync);
  refreshButton.addEventListener('click',refresh);
  document.getElementById('cfx-microphone-exposure-form').addEventListener('submit',event => {
    event.preventDefault();
    if (mode.disabled || saveButton.disabled) return;
    save(mode.value === 'automatic' ? null : inputs.filter(input=>input.checked).map(input=>input.value));
    status.textContent = 'Saved for this container. Reload websites and stop existing microphone streams to apply it.';
  });
  refresh();
  return refresh;
}
