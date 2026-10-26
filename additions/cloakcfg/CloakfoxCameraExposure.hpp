/* MPL-2.0: physical camera exposure for one document/container snapshot. */
#pragma once
#include "json.hpp"
#include <algorithm>
#include <cstdint>
#include <string>
#include <vector>

class CloakfoxCameraExposure {
 public:
  explicit CloakfoxCameraExposure(const nlohmann::json& cfg, bool microphone = false) {
    const auto enabled = cfg.find("mediaDevices:enabled");
    mEnabled = enabled != cfg.end() && enabled->is_boolean() && enabled->get<bool>();
    const auto limit = cfg.find(microphone ? "mediaDevices:micros" : "mediaDevices:webcams");
    mLimit = limit != cfg.end() && limit->is_number_unsigned()
                 ? uint32_t(std::min(limit->get<uint64_t>(), uint64_t(64))) : 1;
    const auto selection = cfg.find(microphone ? "mediaDevices:microphoneDevices" : "mediaDevices:cameraDevices");
    if (selection != cfg.end() && selection->is_string() &&
        !selection->get_ref<const std::string&>().empty()) {
      mExplicit = true;
      const auto ids = nlohmann::json::parse(selection->get<std::string>(), nullptr, false);
      if (ids.is_array() && ids.size() <= 64 &&
          std::all_of(ids.begin(), ids.end(), [](const auto& id) {
            return id.is_string() && !id.template get<std::string>().empty();
          })) {
        for (const auto& id : ids) mSelected.push_back(id.get<std::string>());
      }
    } else if (!microphone) {
      // Preserve existing single-camera selections until edited in settings.
      const auto old = cfg.find("mediaDevices:cameraDevice");
      if (old != cfg.end() && old->is_string() && !old->get<std::string>().empty()) {
        mExplicit = true;
        mSelected.push_back(old->get<std::string>());
      }
    }
  }
  bool AllowCamera(const std::string& rawId) {
    if (!mEnabled) return true;
    // A missing selected camera must not silently fall back to another camera.
    if (mExplicit && std::find(mSelected.begin(), mSelected.end(), rawId) == mSelected.end()) return false;
    return mCount++ < mLimit;
  }
 private:
  bool mEnabled = false;
  uint32_t mLimit = 1;
  uint32_t mCount = 0;
  bool mExplicit = false;
  std::vector<std::string> mSelected;
};
