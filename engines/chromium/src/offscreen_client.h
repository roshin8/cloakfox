#pragma once
#include <array>
#include <cstdint>
#include <functional>
#include <vector>
#include "include/cef_render_handler.h"

namespace cloakfox {
// Browser-owned copy: CEF paint memory is valid only during the callback.
// This object stays native; the diagnostic protocol returns metadata only.
struct OffscreenFrame {
  int width = 0;
  int height = 0;
  uint64_t sequence = 0;
  bool accelerated = false;
  std::vector<uint8_t> bgra;
  std::array<uint8_t, 4> corner() const;
};

class OffscreenClient : public CefRenderHandler {
 public:
  void GetViewRect(CefRefPtr<CefBrowser>, CefRect& rect) override;
  void OnPopupShow(CefRefPtr<CefBrowser>, bool show) override;
  void OnPopupSize(CefRefPtr<CefBrowser>, const CefRect& rect) override;
  void OnPaint(CefRefPtr<CefBrowser>, PaintElementType,
               const RectList&, const void* buffer, int width, int height) override;
  void OnAcceleratedPaint(CefRefPtr<CefBrowser>, PaintElementType,
                          const RectList&, const CefAcceleratedPaintInfo&) override;
  void setViewport(int width, int height);
  void setSink(std::function<bool(const OffscreenFrame&)> sink);
  const CefRect& viewport() const { return viewport_; }
  const OffscreenFrame& frame() const { return frame_; }
  bool popupPainted() const;
  const CefRect& popupRect() const { return popupRect_; }
 private:
  void acceptPaint(PaintElementType type, std::vector<uint8_t> bytes,
                   int width, int height, bool accelerated);
  void compose();
  void discardPaint(PaintElementType type);
  void publish();
  void retry(uint64_t generation);
  bool retryPending_ = false;
  uint64_t sinkGeneration_ = 0, lastPublished_ = 0;
  OffscreenFrame frame_;
  OffscreenFrame viewFrame_, popupFrame_;
  CefRect popupRect_;
  bool popupVisible_ = false;
  CefRect viewport_{0, 0, 1000, 720};
  uint64_t paintSerial_ = 0;
  std::function<bool(const OffscreenFrame&)> sink_;
  IMPLEMENT_REFCOUNTING(OffscreenClient);
};
}
