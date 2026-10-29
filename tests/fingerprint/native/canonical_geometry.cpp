#include "CloakfoxCanonicalGeometry.hpp"
#include <cassert>
using namespace CloakfoxCanonicalGeometry;
int main() {
  enum class Platform { Android, Linux, Ios, Macos, Windows };
  for (auto host : {Platform::Android,Platform::Linux,Platform::Ios,Platform::Macos,Platform::Windows}) {
    for (auto query : {Platform::Android,Platform::Linux,Platform::Ios,Platform::Macos,Platform::Windows}) {
      assert((query == LayoutPlatform(true,host,Platform::Windows)) == (query == Platform::Windows));
      assert((query == LayoutPlatform(false,host,Platform::Windows)) == (query == host));
    }
  }

  auto cfg = nlohmann::json::parse(R"({"geometry:canonical":true,"fingerprint:secret":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=","canvas:seed":42})");
  assert(Requested(cfg, 7));
  assert(!Requested(nlohmann::json::object(), 7));
  for (auto bad : {nlohmann::json(-1), nlohmann::json(0), nlohmann::json(4.5), nlohmann::json("42"), nlohmann::json(uint64_t(UINT32_MAX)+1)}) {
    auto changed=cfg; changed["canvas:seed"]=bad; assert(!Requested(changed,7));
  }
  { auto changed=cfg; changed["fingerprint:secret"]="bad"; assert(!Requested(changed,7)); }
  cfg["geometry:canonical"] = "true"; assert(!Requested(cfg, 7));
  cfg["geometry:canonical"] = true;
  cfg["rendering:geometry_profile"] = {{"version",1},{"id","canonical-v1"},{"owner",7}};
  assert(Requested(cfg,7)); assert(!Requested(cfg,8));
  cfg["rendering:geometry_profile"]["unknown"] = true; assert(!Requested(cfg,7));
  Lifecycle state;
  assert(!state.Ready());
  state.Capture(true); state.Capture(false); assert(state.Normalized() && state.Valid()); assert(!state.Ready());
  state.Complete(false); assert(!state.Ready());
  state.Complete(true); assert(state.Ready());
  state.BeginLayout(); assert(!state.Ready() && state.Valid());
  state.Complete(true); assert(state.Ready());
  state.Revoke(); assert(state.Normalized() && !state.Valid()); assert(!state.Ready());
  state.Complete(true); assert(!state.Ready()); // no resurrection of old caches
  Lifecycle disabled; disabled.Capture(false); disabled.Complete(true);
  assert(!disabled.Normalized() && !disabled.Ready());
}
