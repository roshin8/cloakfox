// Runs in a fresh xpcshell process with a private profile database. It never
// changes the user's profiles.ini or launches their browser.
var Services = {
  dirsvc: Cc["@mozilla.org/file/directory_service;1"].getService(Ci.nsIProperties),
  env: Cc["@mozilla.org/process/environment;1"].getService(Ci.nsIEnvironment),
};
function assert(value, message) { if (!value) throw new Error(message); }
function dir(parent, name) {
  const child = parent.clone(); child.append(name);
  child.create(Ci.nsIFile.DIRECTORY_TYPE, 0o700); return child;
}
function write(parent, name, text) {
  const target = parent.clone(); target.append(name);
  const stream = Cc["@mozilla.org/network/file-output-stream;1"].createInstance(Ci.nsIFileOutputStream);
  stream.init(target, 0x02 | 0x08 | 0x20, 0o600, 0);
  stream.write(text, text.length); stream.close(); return target;
}
const testRoot = Services.dirsvc.get("TmpD", Ci.nsIFile).clone();
testRoot.append("cloakfox-profile-binding");
testRoot.createUnique(Ci.nsIFile.DIRECTORY_TYPE, 0o700);
try {
  const mode = Services.env.get("CLOAKFOX_PROFILE_CASE");
  const data = dir(testRoot, "data"), localData = dir(testRoot, "cache");
  const provider = Cc["@mozilla.org/xre/directory-provider;1"].getService(Ci.nsIXREDirProvider);
  provider.setUserDataDirectory(data, false); provider.setUserDataDirectory(localData, true);
  Services.dirsvc.set("UAppData", data);
  const profiles = dir(data, "Profiles"), caches = dir(localData, "Profiles");
  Services.dirsvc.set("DefProfRt", profiles); Services.dirsvc.set("DefProfLRt", caches);
  const root = dir(profiles, "original with spaces"), local = dir(caches, "original with spaces");
  const other = dir(profiles, "other"), otherLocal = dir(caches, "other");
  const app = dir(testRoot, "Firefox.app"), contents = dir(app, "Contents");
  const macos = dir(contents, "MacOS"), resources = dir(contents, "Resources");
  const exe = write(macos, "firefox", "");
  Services.dirsvc.set("XREExeF", exe);
  const binding = write(resources, "cloakfox-profile.ini", mode === "invalid"
    ? "[CloakfoxProfile]\nRoot=/missing-cloakfox-profile\nLocal=/missing-cloakfox-cache\n"
    : `[CloakfoxProfile]\nRoot=${root.path}\nLocal=${local.path}\n`);
  if (mode === "absent") binding.remove(false);
  write(data, "profiles.ini", "[General]\nStartWithLastProfile=1\nVersion=2\n" +
    "[Profile0]\nName=Original\nIsRelative=1\nPath=Profiles/original with spaces\nDefault=1\n" +
    "[Profile1]\nName=Other\nIsRelative=1\nPath=Profiles/other\n");
  Services.env.set("XRE_PROFILE_PATH", ""); Services.env.set("XRE_PROFILE_LOCAL_PATH", "");
  if (mode === "environment") {
    Services.env.set("XRE_PROFILE_PATH", other.path);
    Services.env.set("XRE_PROFILE_LOCAL_PATH", otherLocal.path);
  }
  const service = Cc["@mozilla.org/toolkit/profile-service;1"].getService(Ci.nsIToolkitProfileService);
  const selected = {}, selectedLocal = {}, profile = {};
  const args = mode === "argument" ? ["xpcshell", "-profile", other.path]
    : mode === "named" ? ["xpcshell", "-P", "Other"]
    : mode === "manager" ? ["xpcshell", "-profilemanager"] : ["xpcshell"];
  if (mode === "invalid" || mode === "manager") {
    let error;
    try { service.selectStartupProfile(args, false, "default", "", selected, selectedLocal, profile); }
    catch (e) { error = e; }
    assert(error?.result === 0x805800c9, "A broken binding must open the profile manager, not create a profile");
  } else {
    const created = service.selectStartupProfile(args, false, "default", "", selected, selectedLocal, profile);
    if (mode === "absent") {
      assert(created, "An ordinary source app retains Gecko's first-run behavior");
    } else {
      assert(!created, "Appearance reopen must not create a new profile");
      assert(selected.value.equals(mode === "bound" ? root : other), "Selected wrong profile");
      assert(selectedLocal.value.equals(mode === "bound" ? local : otherLocal), "Selected wrong cache");
      assert(Array.from(service.profiles).length === 2, "Profile registry gained another profile");
    }
  }
  print(`PASS — appearance startup: ${mode}`);
} finally { testRoot.remove(true); }
