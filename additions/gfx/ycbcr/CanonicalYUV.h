/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
#ifndef MOZILLA_GFX_CANONICALYUV_H_
#define MOZILLA_GFX_CANONICALYUV_H_
#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>

#include "fdlibm.h"
namespace mozilla::gfx::canonical {
// Version 1 scalar color policy: fixed matrix coefficients and D65 primaries,
// bundled fdlibm transfer math, SDR reference white 100 nits. HDR is clipped at
// the SDR output boundary, never adjusted to monitor brightness or color space.
enum class AlphaOperation { None, Premultiply, Unpremultiply };
enum class Matrix { BT601, BT709, BT2020, Identity };
enum class Primaries { SRGB, BT601_525, BT2020, P3 };
enum class Transfer { BT709, SRGB, PQ, HLG, Linear };
struct ColorPolicy {
  Matrix matrix;
  Primaries primaries;
  Transfer transfer;
  bool fullRange;
};
inline double Clamp(double x) { return std::max(0.0, std::min(1.0, x)); }
inline double ToLinear(double x, Transfer transfer) {
  const double sign = x < 0 ? -1 : 1;
  x = x < 0 ? -x : x;
  switch (transfer) {
    case Transfer::SRGB:
      return sign *
             (x <= 0.04045 ? x / 12.92 : fdlibm_pow((x + 0.055) / 1.055, 2.4));
    case Transfer::BT709:
      return sign * fdlibm_pow(x, 2.4);
    case Transfer::Linear:
      return sign * x;
    case Transfer::PQ: {
      const double p = fdlibm_pow(Clamp(x), 32.0 / 2523.0);
      return 100.0 * fdlibm_pow(std::max(p - 3424.0 / 4096.0, 0.0) /
                                    (2413.0 / 128.0 - 2392.0 / 128.0 * p),
                                16384.0 / 2610.0);
    }
    case Transfer::HLG: {
      const double scene =
          x <= 0.5
              ? x * x / 3.0
              : (fdlibm_exp((x - 0.55991073) / 0.17883277) + 0.28466892) / 12.0;
      return 10.0 * fdlibm_pow(scene, 1.2);
    }
  }
  return 0;
}
inline uint8_t ToSRGB(double x) {
  x = Clamp(x);
  const double encoded =
      x <= 0.0031308 ? 12.92 * x : 1.055 * fdlibm_pow(x, 1.0 / 2.4) - 0.055;
  return uint8_t(Clamp(encoded) * 255.0 + 0.5);
}
inline uint32_t Sample(const uint8_t* data, int32_t stride, uint32_t x,
                       uint32_t y, unsigned depth, uint32_t skip) {
  const uint32_t bytes = depth == 8 ? 1 : 2;
  const uint8_t* pixel =
      data + ptrdiff_t(y) * stride + size_t(x) * (bytes + skip);
  if (bytes == 1) return *pixel;
  uint16_t value;
  memcpy(&value, pixel, sizeof(value));
  return value;
}
inline std::array<uint8_t, 3> Transform(double r, double g, double b,
                                        const ColorPolicy& p) {
  r = ToLinear(r, p.transfer);
  g = ToLinear(g, p.transfer);
  b = ToLinear(b, p.transfer);
  if (p.primaries == Primaries::BT2020) {
    const double rr = 1.660491002 * r - 0.587641139 * g - 0.072849863 * b;
    const double gg = -0.124550475 * r + 1.132899897 * g - 0.008349422 * b;
    const double bb = -0.018150763 * r - 0.100578898 * g + 1.118729661 * b;
    r = rr;
    g = gg;
    b = bb;
  } else if (p.primaries == Primaries::P3) {
    const double rr = 1.224940176 * r - 0.224940176 * g;
    const double gg = -0.042056955 * r + 1.042056955 * g;
    const double bb = -0.019637555 * r - 0.078636046 * g + 1.098273601 * b;
    r = rr;
    g = gg;
    b = bb;
  } else if (p.primaries == Primaries::BT601_525) {
    const double rr = 0.939542064 * r + 0.050181357 * g + 0.010276579 * b;
    const double gg = 0.017772223 * r + 0.965792862 * g + 0.016434915 * b;
    const double bb = -0.0016216 * r - 0.00436975 * g + 1.00599135 * b;
    r = rr;
    g = gg;
    b = bb;
  }
  return {ToSRGB(r), ToSRGB(g), ToSRGB(b)};
}
inline std::array<double, 3> Decode(uint32_t y, uint32_t cb, uint32_t cr,
                                      unsigned depth, const ColorPolicy& p) {
  const double scale = double(uint32_t(1) << (depth - 8));
  const double max = double((uint32_t(1) << depth) - 1);
  double yy = p.fullRange ? y / max : (double(y) - 16 * scale) / (219 * scale);
  const double u =
      (double(cb) - 128 * scale) / (p.fullRange ? max : 224 * scale);
  const double v =
      (double(cr) - 128 * scale) / (p.fullRange ? max : 224 * scale);
  double r, g, b;
  if (p.matrix == Matrix::Identity) {
    r = double(cr) / max;
    g = double(y) / max;
    b = double(cb) / max;
  } else {
    const double kr = p.matrix == Matrix::BT601   ? 0.299
                      : p.matrix == Matrix::BT709 ? 0.2126
                                                  : 0.2627;
    const double kb = p.matrix == Matrix::BT601   ? 0.114
                      : p.matrix == Matrix::BT709 ? 0.0722
                                                  : 0.0593;
    r = yy + 2 * (1 - kr) * v;
    b = yy + 2 * (1 - kb) * u;
    g = (yy - kr * r - kb * b) / (1 - kr - kb);
  }
  return {r, g, b};
}
inline std::array<uint8_t, 3> Convert(uint32_t y, uint32_t cb, uint32_t cr,
                                      unsigned depth, const ColorPolicy& p) {
  const auto rgb = Decode(y, cb, cr, depth, p);
  return Transform(rgb[0], rgb[1], rgb[2], p);
}
}  // namespace mozilla::gfx::canonical
#endif
