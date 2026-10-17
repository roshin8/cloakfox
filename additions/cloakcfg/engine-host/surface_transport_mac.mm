#include "surface_transport_mac.h"
#include <algorithm>
#include <cstring>

namespace cloakfox {
namespace {
constexpr mach_msg_id_t kFrameMessage = 0x43465331;
constexpr uint32_t kVersion = 1;
constexpr uint32_t kBGRA = 0x42475241;
constexpr size_t kBudget = 64 * 1024 * 1024;
struct FrameMessage {
  mach_msg_header_t header;
  mach_msg_body_t body;
  mach_msg_port_descriptor_t surface;
  uint32_t version;
  uint32_t reserved;
  SurfaceRoute route;
  uint64_t sequence;
};
struct ReceivedMessage {
  alignas(FrameMessage) std::array<uint8_t, sizeof(FrameMessage) + MAX_TRAILER_SIZE> bytes{};
  mach_msg_header_t* header() {
    return reinterpret_cast<mach_msg_header_t*>(bytes.data());
  }
  ~ReceivedMessage() { mach_msg_destroy(header()); }
};
struct SurfaceRelease {
  IOSurfaceRef surface;
  ~SurfaceRelease() { CFRelease(surface); }
};
struct SurfaceReadLock {
  IOSurfaceRef surface;
  ~SurfaceReadLock() { IOSurfaceUnlock(surface, kIOSurfaceLockReadOnly, nullptr); }
};
bool dimensions(uint32_t width, uint32_t height) {
  return width && height && width <= 4096 && height <= 4096;
}
bool validRoute(const SurfaceRoute& route) {
  return route.configRevision && route.viewportRevision &&
      std::any_of(route.token.begin(), route.token.end(), [](auto b) { return b != 0; }) &&
      dimensions(route.width, route.height);
}
}

SurfaceReceiver::SurfaceReceiver(const audit_token_t& expectedSender) noexcept
    : expectedSender_(expectedSender) {
  if (mach_port_allocate(mach_task_self(), MACH_PORT_RIGHT_RECEIVE, &port_) != KERN_SUCCESS)
    return;
  if (mach_port_insert_right(mach_task_self(), port_, port_, MACH_MSG_TYPE_MAKE_SEND) != KERN_SUCCESS) {
    mach_port_mod_refs(mach_task_self(), port_, MACH_PORT_RIGHT_RECEIVE, -1);
    port_ = MACH_PORT_NULL;
  }
}
SurfaceReceiver::~SurfaceReceiver() {
  // Destroy queued descriptors too; a helper cannot keep an orphan receiver alive.
  if (MACH_PORT_VALID(port_)) {
    mach_port_mod_refs(mach_task_self(), port_, MACH_PORT_RIGHT_RECEIVE, -1);
    mach_port_deallocate(mach_task_self(), port_);
  }
}
bool SurfaceReceiver::attach(const SurfaceRoute& route) {
  if (!MACH_PORT_VALID(port_) || !validRoute(route) || slots_.contains(route.token) || retired_.contains(route.token)) return false;
  slots_.emplace(route.token, Slot{route});
  return true;
}
bool SurfaceReceiver::resize(const SurfaceToken& token, uint64_t configRevision,
                             uint64_t viewportRevision, uint32_t width, uint32_t height) {
  const auto found = slots_.find(token);
  if (found == slots_.end() || !dimensions(width, height) ||
      found->second.route.configRevision != configRevision ||
      viewportRevision <= found->second.route.viewportRevision) return false;
  found->second.route.viewportRevision = viewportRevision;
  found->second.route.width = width; found->second.route.height = height;
  return true;
}
void SurfaceReceiver::detach(const SurfaceToken& token) {
  if (slots_.erase(token)) retired_.insert(token);
}
std::optional<SurfaceSnapshot> SurfaceReceiver::receive(mach_msg_timeout_t timeoutMs) {
  ReceivedMessage received;
  auto* header = received.header();
  const auto status = mach_msg(header,
      MACH_RCV_MSG | MACH_RCV_TIMEOUT |
          MACH_RCV_TRAILER_TYPE(MACH_MSG_TRAILER_FORMAT_0) |
          MACH_RCV_TRAILER_ELEMENTS(MACH_RCV_TRAILER_AUDIT),
      0, received.bytes.size(), port_, timeoutMs, MACH_PORT_NULL);
  if (status != MACH_MSG_SUCCESS) {
    // No successfully received rights to destroy after timeout/receive error.
    *header = {};
    return std::nullopt;
  }
  if (header->msgh_size != sizeof(FrameMessage) || header->msgh_id != kFrameMessage ||
      !(header->msgh_bits & MACH_MSGH_BITS_COMPLEX) || header->msgh_remote_port != MACH_PORT_NULL)
    return std::nullopt;
  const auto* trailer = reinterpret_cast<const mach_msg_audit_trailer_t*>(
      received.bytes.data() + round_msg(header->msgh_size));
  if (trailer->msgh_trailer_type != MACH_MSG_TRAILER_FORMAT_0 ||
      trailer->msgh_trailer_size < sizeof(mach_msg_audit_trailer_t) ||
      std::memcmp(&trailer->msgh_audit, &expectedSender_, sizeof(expectedSender_)) != 0)
    return std::nullopt;
  const auto& message = *reinterpret_cast<const FrameMessage*>(header);
  if (message.body.msgh_descriptor_count != 1 ||
      message.surface.type != MACH_MSG_PORT_DESCRIPTOR ||
      message.surface.disposition != MACH_MSG_TYPE_PORT_SEND ||
      message.surface.name == MACH_PORT_NULL || message.version != kVersion ||
      message.reserved || !message.sequence || !validRoute(message.route)) return std::nullopt;
  const auto found = slots_.find(message.route.token);
  if (found == slots_.end() || found->second.route != message.route ||
      message.sequence <= found->second.lastSequence) return std::nullopt;
  // Do not map a supplied capability until both the kernel sender identity and
  // trusted tab/configuration/viewport ownership have passed validation.
  IOSurfaceRef surface = IOSurfaceLookupFromMachPort(message.surface.name);
  if (!surface) return std::nullopt;
  const SurfaceRelease release{surface};
  const auto width = IOSurfaceGetWidth(surface), height = IOSurfaceGetHeight(surface);
  const auto row = IOSurfaceGetBytesPerRow(surface);
  if (width != message.route.width || height != message.route.height ||
      IOSurfaceGetPlaneCount(surface) || IOSurfaceGetPixelFormat(surface) != kBGRA ||
      IOSurfaceGetBytesPerElement(surface) != 4 || row < width * 4 ||
      row > kBudget / height || IOSurfaceGetAllocSize(surface) < row * height ||
      IOSurfaceLock(surface, kIOSurfaceLockReadOnly, nullptr) != KERN_SUCCESS) return std::nullopt;
  const SurfaceReadLock lock{surface};
  const auto* pixels = static_cast<const uint8_t*>(IOSurfaceGetBaseAddress(surface));
  if (!pixels) return std::nullopt;
  SurfaceSnapshot result{message.route, message.sequence, std::vector<uint8_t>(width * height * 4)};
  for (size_t y = 0; y < height; ++y)
    std::copy_n(pixels + y * row, width * 4, result.bgra.data() + y * width * 4);
  found->second.lastSequence = message.sequence;
  return result;
}
bool sendSurface(mach_port_t destination, const SurfaceRoute& route,
                 uint64_t sequence, IOSurfaceRef surface) {
  if (!surface || !MACH_PORT_VALID(destination)) return false;
  auto port = IOSurfaceCreateMachPort(surface);
  if (!MACH_PORT_VALID(port)) return false;
  FrameMessage message{};
  message.header.msgh_bits = MACH_MSGH_BITS(MACH_MSG_TYPE_COPY_SEND, 0) | MACH_MSGH_BITS_COMPLEX;
  message.header.msgh_size = sizeof(message);
  message.header.msgh_remote_port = destination;
  message.header.msgh_id = kFrameMessage;
  message.body.msgh_descriptor_count = 1;
  message.surface.name = port;
  message.surface.disposition = MACH_MSG_TYPE_COPY_SEND;
  message.surface.type = MACH_MSG_PORT_DESCRIPTOR;
  message.version = kVersion; message.route = route; message.sequence = sequence;
  const auto status = mach_msg(&message.header, MACH_SEND_MSG | MACH_SEND_TIMEOUT,
      sizeof(message), 0, MACH_PORT_NULL, 0, MACH_PORT_NULL);
  // COPY_SEND leaves our original right owned here on success and failure.
  mach_port_deallocate(mach_task_self(), port);
  return status == MACH_MSG_SUCCESS;
}
bool sendSurfaceBytes(mach_port_t destination, const SurfaceRoute& route,
                      uint64_t sequence, const std::vector<uint8_t>& bgra) {
  if (!validRoute(route) || !sequence || bgra.size() != size_t(route.width) * route.height * 4)
    return false;
  const int64_t numbers[] = {route.width, route.height, int64_t(route.width) * 4, 4, kBGRA};
  const void* keys[] = {kIOSurfaceWidth, kIOSurfaceHeight, kIOSurfaceBytesPerRow,
                       kIOSurfaceBytesPerElement, kIOSurfacePixelFormat};
  CFNumberRef values[5];
  for (int i = 0; i < 5; ++i) values[i] = CFNumberCreate(nullptr, kCFNumberSInt64Type, &numbers[i]);
  auto properties = CFDictionaryCreate(nullptr, keys, reinterpret_cast<const void**>(values),
      5, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
  auto surface = IOSurfaceCreate(properties);
  CFRelease(properties);
  for (auto value : values) CFRelease(value);
  if (!surface) return false;
  const SurfaceRelease release{surface};
  if (IOSurfaceLock(surface, 0, nullptr) != KERN_SUCCESS) return false;
  auto* pixels = static_cast<uint8_t*>(IOSurfaceGetBaseAddress(surface));
  if (!pixels) { IOSurfaceUnlock(surface, 0, nullptr); return false; }
  const size_t row = IOSurfaceGetBytesPerRow(surface), sourceRow = size_t(route.width) * 4;
  for (size_t y = 0; y < route.height; ++y)
    std::copy_n(bgra.data() + y * sourceRow, sourceRow, pixels + y * row);
  IOSurfaceUnlock(surface, 0, nullptr);
  return sendSurface(destination, route, sequence, surface);
}
}
