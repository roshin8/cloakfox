#include "offscreen_client.h"
#include "include/base/cef_callback.h"
#include <algorithm>
#include <IOSurface/IOSurface.h>
#include "include/wrapper/cef_helpers.h"
#include "include/wrapper/cef_closure_task.h"
#include "include/cef_task.h"

namespace cloakfox {
namespace {
struct ReadLock {
  IOSurfaceRef surface;
  ~ReadLock() { IOSurfaceUnlock(surface, kIOSurfaceLockReadOnly, nullptr); }
};
}
std::array<uint8_t, 4> OffscreenFrame::corner() const {
  if (bgra.size() < 4) return {};
  std::array<uint8_t, 4> result;
  std::copy_n(bgra.end() - 4, 4, result.begin());
  return result;
}

void OffscreenClient::GetViewRect(CefRefPtr<CefBrowser>, CefRect& rect) {
  rect = viewport_;
}

void OffscreenClient::setViewport(int width, int height) {
  CEF_REQUIRE_UI_THREAD();
  viewport_ = CefRect(0, 0, width, height);
  frame_ = {};
  viewFrame_ = {};
  popupFrame_ = {};
  popupRect_ = {};
  popupVisible_ = false;
}
void OffscreenClient::OnPopupShow(CefRefPtr<CefBrowser>, bool show) {
  CEF_REQUIRE_UI_THREAD();
  popupVisible_ = show;
  if (!show) popupFrame_ = {};
  compose();
}
void OffscreenClient::OnPopupSize(CefRefPtr<CefBrowser>, const CefRect& rect) {
  CEF_REQUIRE_UI_THREAD();
  popupFrame_ = {};
  if (rect.width <= 0 || rect.height <= 0 || rect.width > 4096 || rect.height > 4096 ||
      rect.x < -32768 || rect.x > 32768 || rect.y < -32768 || rect.y > 32768) {
    popupVisible_ = false;
    popupRect_ = {};
  } else {
    popupRect_ = rect;
  }
  compose();
}
bool OffscreenClient::popupPainted() const {
  return popupVisible_ && !popupFrame_.bgra.empty() &&
      popupRect_.x < viewFrame_.width && popupRect_.y < viewFrame_.height &&
      popupRect_.x + popupRect_.width > 0 && popupRect_.y + popupRect_.height > 0;
}
void OffscreenClient::acceptPaint(PaintElementType type, std::vector<uint8_t> bytes,
                                 int width, int height, bool accelerated) {
  if (type != PET_VIEW && type != PET_POPUP) return;
  if (type == PET_VIEW && (width != viewport_.width || height != viewport_.height)) return;
  if (type == PET_POPUP && (!popupVisible_ || width != popupRect_.width || height != popupRect_.height)) return;
  auto& target = type == PET_VIEW ? viewFrame_ : popupFrame_;
  target.width = width;
  target.height = height;
  target.accelerated = accelerated;
  target.bgra = std::move(bytes);
  compose();
}
void OffscreenClient::compose() {
  CEF_REQUIRE_UI_THREAD();
  if (viewFrame_.bgra.empty()) return;
  // Both source widgets belong to this browser. Never reuse the previously
  // composited image as a base: hiding/moving the popup must erase its pixels.
  frame_ = viewFrame_;
  if (popupPainted()) {
    const int left = std::max(0, popupRect_.x), top = std::max(0, popupRect_.y);
    const int right = std::min(frame_.width, popupRect_.x + popupRect_.width);
    const int bottom = std::min(frame_.height, popupRect_.y + popupRect_.height);
    for (int y = top; y < bottom; ++y) {
      for (int x = left; x < right; ++x) {
        auto* destination = frame_.bgra.data() + (size_t(y) * frame_.width + x) * 4;
        const auto* source = popupFrame_.bgra.data() +
            (size_t(y - popupRect_.y) * popupFrame_.width + (x - popupRect_.x)) * 4;
        const unsigned alpha = source[3];
        if (!alpha) continue;
        for (int channel = 0; channel < 4; ++channel)
          destination[channel] = static_cast<uint8_t>(std::min(255u,
              unsigned(source[channel]) + (unsigned(destination[channel]) * (255 - alpha) + 127) / 255));
      }
    }
  }
  frame_.sequence = ++paintSerial_;
  publish();
}
void OffscreenClient::discardPaint(PaintElementType type) {
  popupFrame_ = {};
  if (type == PET_POPUP) {
    compose();
  } else {
    // A later popup callback must not resurrect a rejected view image.
    viewFrame_ = {};
    frame_ = {};
  }
}
void OffscreenClient::setSink(std::function<bool(const OffscreenFrame&)> sink) {
  CEF_REQUIRE_UI_THREAD();
  ++sinkGeneration_;
  retryPending_ = false;
  lastPublished_ = 0;
  sink_ = std::move(sink);
  publish();
}
void OffscreenClient::publish() {
  CEF_REQUIRE_UI_THREAD();
  if (!sink_ || !frame_.sequence || frame_.sequence == lastPublished_) return;
  if (sink_(frame_)) { lastPublished_ = frame_.sequence; return; }
  if (retryPending_) return;
  // Coalesce into the one already-owned latest frame. Never queue pixel copies
  // or block the CEF UI thread when the authenticated receiver is backpressured.
  retryPending_ = true;
  const uint64_t generation = sinkGeneration_;
  CefPostDelayedTask(TID_UI, base::BindOnce(&OffscreenClient::retry,
      CefRefPtr<OffscreenClient>(this), generation), 16);
}
void OffscreenClient::retry(uint64_t generation) {
  CEF_REQUIRE_UI_THREAD();
  if (generation != sinkGeneration_) return;
  retryPending_ = false;
  publish();
}

void OffscreenClient::OnPaint(CefRefPtr<CefBrowser>, PaintElementType type,
                              const RectList&, const void* buffer,
                              int width, int height) {
  CEF_REQUIRE_UI_THREAD();
  // Bound before multiplication/allocation, for both owned widget types.
  if ((type != PET_VIEW && type != PET_POPUP) || !buffer || width <= 0 || height <= 0 ||
      width > 4096 || height > 4096) return;
  const size_t length = size_t(width) * size_t(height) * 4;
  const auto* bytes = static_cast<const uint8_t*>(buffer);
  acceptPaint(type, std::vector<uint8_t>(bytes, bytes + length), width, height, false);
}

void OffscreenClient::OnAcceleratedPaint(CefRefPtr<CefBrowser>, PaintElementType type,
                                         const RectList&, const CefAcceleratedPaintInfo& info) {
  CEF_REQUIRE_UI_THREAD();
  if (type != PET_VIEW && type != PET_POPUP) return;
  const auto surface = static_cast<IOSurfaceRef>(info.shared_texture_io_surface);
  if (!surface || info.format != CEF_COLOR_TYPE_BGRA_8888 ||
      IOSurfaceGetPlaneCount(surface) != 0) { discardPaint(type); return; }
  const size_t width = IOSurfaceGetWidth(surface), height = IOSurfaceGetHeight(surface);
  const size_t row = IOSurfaceGetBytesPerRow(surface);
  constexpr size_t budget = 64 * 1024 * 1024;
  if (!width || !height || width > 4096 || height > 4096 ||
      IOSurfaceGetBytesPerElement(surface) != 4 || row < width * 4 ||
      row > budget / height || IOSurfaceGetAllocSize(surface) < row * height ||
      IOSurfaceLock(surface, kIOSurfaceLockReadOnly, nullptr) != 0) { discardPaint(type); return; }
  const ReadLock lock{surface};
  const auto* bytes = static_cast<const uint8_t*>(IOSurfaceGetBaseAddress(surface));
  if (bytes) {
    // No CEF surface or pointer survives this callback. Copy row padding out
    // while the surface remains locked and before CEF reuses its pool entry.
    std::vector<uint8_t> pixels(width * height * 4);
    for (size_t y = 0; y < height; ++y)
      std::copy_n(bytes + y * row, width * 4, pixels.data() + y * width * 4);
    acceptPaint(type, std::move(pixels), static_cast<int>(width), static_cast<int>(height), true);
  } else { discardPaint(type); }
}
}
