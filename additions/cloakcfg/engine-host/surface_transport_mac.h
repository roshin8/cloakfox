#pragma once
#include <IOSurface/IOSurface.h>
#include <mach/mach.h>
#include <array>
#include <cstdint>
#include <map>
#include <optional>
#include <set>
#include <vector>

namespace cloakfox {
using SurfaceToken = std::array<uint8_t, 16>;
struct SurfaceRoute {
  SurfaceToken token{};
  uint64_t configRevision = 0;
  uint64_t viewportRevision = 0;
  uint32_t width = 0, height = 0;
  bool operator==(const SurfaceRoute&) const = default;
};
struct SurfaceSnapshot {
  SurfaceRoute route;
  uint64_t sequence;
  std::vector<uint8_t> bgra;
};

// Native-only boundary. The host must establish expectedSender using its
// authenticated launch handshake and revoke the receiver on helper death.
// No bootstrap registration, global IOSurface IDs, or page-facing bindings.
// Callers serialize all access to a receiver on one owning thread.
class SurfaceReceiver {
 public:
  explicit SurfaceReceiver(const audit_token_t& expectedSender) noexcept;
  ~SurfaceReceiver();
  SurfaceReceiver(const SurfaceReceiver&) = delete;
  SurfaceReceiver& operator=(const SurfaceReceiver&) = delete;
  mach_port_t port() const { return port_; }
  bool attach(const SurfaceRoute& route);
  bool resize(const SurfaceToken&, uint64_t configRevision,
              uint64_t viewportRevision, uint32_t width, uint32_t height);
  void detach(const SurfaceToken& token);
  std::optional<SurfaceSnapshot> receive(mach_msg_timeout_t timeoutMs);
 private:
  struct Slot { SurfaceRoute route; uint64_t lastSequence = 0; };
  const audit_token_t expectedSender_;
  mach_port_t port_ = MACH_PORT_NULL;
  std::map<SurfaceToken, Slot> slots_;
  std::set<SurfaceToken> retired_;
};

// Copies a send right into one bounded message; never transfers the sender's
// receive right. The surface must stay valid for the duration of this call.
bool sendSurface(mach_port_t destination, const SurfaceRoute& route,
                 uint64_t sequence, IOSurfaceRef surface);
bool sendSurfaceBytes(mach_port_t destination, const SurfaceRoute& route,
                      uint64_t sequence, const std::vector<uint8_t>& bgra);
}
