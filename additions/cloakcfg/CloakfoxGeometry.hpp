/* MPL-2.0: deterministic geometry presentation, shared by DOM geometry APIs. */
#pragma once

#include <algorithm>
#include <cstdint>

namespace CloakfoxGeometry {
class Presentation {
 public:
  explicit Presentation(uint32_t seed) {
    mX = Noise(seed);
    mY = Noise(seed);
    mWidth = Noise(seed);
    mHeight = Noise(seed);
  }

  template <typename Rect>
  void Apply(Rect* rect) const {
    // A true empty origin rectangle is observable even for non-rendered nodes.
    if (!rect->X() && !rect->Y() && !rect->Width() && !rect->Height()) return;
    // Each fragment gets the same owner-bound coefficients, independent of its
    // index. Carets and zero-area boxes must not acquire phantom dimensions.
    rect->SetRect(static_cast<float>(rect->X()) + mX,
                  static_cast<float>(rect->Y()) + mY,
                  rect->Width() == 0 ? 0 : std::max(0.0f, static_cast<float>(rect->Width()) + mWidth),
                  rect->Height() == 0 ? 0 : std::max(0.0f, static_cast<float>(rect->Height()) + mHeight));
  }

 private:
  static float Noise(uint32_t& seed) {
    seed = seed * 1664525u + 1013904223u;
    return (static_cast<float>(seed) / 4294967295.0f - 0.5f) * 0.4f;
  }
  float mX, mY, mWidth, mHeight;
};

// CSSOM bounding rectangles are the union of nonempty client rectangles, or
// the first client rectangle when every entry is empty. Union after applying
// protection: independently noising an accumulated native bound is incoherent.
template <typename List, typename Rect>
void BoundingFromClientRects(List* list, Rect* result) {
  if (!list || !list->Length()) return;
  auto* first = list->Item(0);
  double left = first->X(), top = first->Y();
  double right = left + first->Width(), bottom = top + first->Height();
  bool found = false;
  for (uint32_t i = 0; i < list->Length(); ++i) {
    auto* rect = list->Item(i);
    if (!rect->Width() || !rect->Height()) continue;
    if (!found) {
      left = rect->X(); top = rect->Y();
      right = left + rect->Width(); bottom = top + rect->Height();
      found = true;
    } else {
      left = std::min(left, rect->X()); top = std::min(top, rect->Y());
      right = std::max(right, rect->X() + rect->Width());
      bottom = std::max(bottom, rect->Y() + rect->Height());
    }
  }
  // DOMRect::SetRect narrows to float; its property setters retain doubles.
  // Union edges are sums of protected floats and need the extra precision.
  result->SetX(left);
  result->SetY(top);
  result->SetWidth(right - left);
  result->SetHeight(bottom - top);
}
}  // namespace CloakfoxGeometry
