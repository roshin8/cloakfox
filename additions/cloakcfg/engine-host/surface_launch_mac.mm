#include "surface_launch_mac.h"
#include <array>
#include <bsm/libbsm.h>
#include <servers/bootstrap.h>
#include <utility>
#include <unistd.h>

namespace cloakfox {
namespace {
constexpr mach_msg_id_t kHello = 0x43464831, kReply = 0x43464832;
constexpr uint32_t kVersion = 1;
struct HelloMessage { mach_msg_header_t header; uint32_t version, reserved; };
struct ReplyMessage {
  mach_msg_header_t header;
  mach_msg_body_t body;
  mach_msg_port_descriptor_t frames;
  uint32_t version, reserved;
};
template<typename Message> struct Received {
  alignas(Message) std::array<uint8_t, sizeof(Message) + MAX_TRAILER_SIZE> bytes{};
  mach_msg_header_t* header() { return reinterpret_cast<mach_msg_header_t*>(bytes.data()); }
  Message& message() { return *reinterpret_cast<Message*>(bytes.data()); }
  ~Received() { mach_msg_destroy(header()); }
  bool receive(mach_port_t port, mach_msg_timeout_t timeoutMs) {
    const auto status = mach_msg(header(), MACH_RCV_MSG | MACH_RCV_TIMEOUT |
        MACH_RCV_TRAILER_TYPE(MACH_MSG_TRAILER_FORMAT_0) |
        MACH_RCV_TRAILER_ELEMENTS(MACH_RCV_TRAILER_AUDIT),
        0, bytes.size(), port, timeoutMs, MACH_PORT_NULL);
    if (status != MACH_MSG_SUCCESS) { *header() = {}; return false; }
    return header()->msgh_size == sizeof(Message);
  }
  const audit_token_t* audit() {
    const auto* trailer = reinterpret_cast<const mach_msg_audit_trailer_t*>(
        bytes.data() + round_msg(sizeof(Message)));
    if (trailer->msgh_trailer_type != MACH_MSG_TRAILER_FORMAT_0 ||
        trailer->msgh_trailer_size < sizeof(mach_msg_audit_trailer_t)) return nullptr;
    return &trailer->msgh_audit;
  }
};
struct ReceiveRight {
  mach_port_t port = MACH_PORT_NULL;
  ~ReceiveRight() {
    if (MACH_PORT_VALID(port)) mach_port_mod_refs(mach_task_self(), port, MACH_PORT_RIGHT_RECEIVE, -1);
  }
};
void descriptor(mach_msg_port_descriptor_t& out, mach_port_t port) {
  out.name = port; out.type = MACH_MSG_PORT_DESCRIPTOR; out.disposition = MACH_MSG_TYPE_COPY_SEND;
}
bool validSend(const mach_msg_port_descriptor_t& port) {
  return port.type == MACH_MSG_PORT_DESCRIPTOR &&
      port.disposition == MACH_MSG_TYPE_PORT_SEND && MACH_PORT_VALID(port.name);
}
}
SurfaceHello::SurfaceHello(SurfaceHello&& other) noexcept
    : audit_(other.audit_), reply_(std::exchange(other.reply_, MACH_PORT_NULL)) {}
SurfaceHello::~SurfaceHello() {
  if (MACH_PORT_VALID(reply_)) mach_port_deallocate(mach_task_self(), reply_);
}
bool SurfaceHello::reply(mach_port_t frameReceiver) {
  if (!MACH_PORT_VALID(reply_) || !MACH_PORT_VALID(frameReceiver)) return false;
  ReplyMessage message{};
  message.header.msgh_bits = MACH_MSGH_BITS(MACH_MSG_TYPE_MOVE_SEND_ONCE, 0) | MACH_MSGH_BITS_COMPLEX;
  message.header.msgh_size = sizeof(message); message.header.msgh_id = kReply;
  message.header.msgh_remote_port = reply_;
  message.body.msgh_descriptor_count = 1;
  descriptor(message.frames, frameReceiver);
  message.version = kVersion;
  const auto status = mach_msg(&message.header, MACH_SEND_MSG | MACH_SEND_TIMEOUT,
      sizeof(message), 0, MACH_PORT_NULL, 0, MACH_PORT_NULL);
  if (status != MACH_MSG_SUCCESS) return false;
  reply_ = MACH_PORT_NULL;
  return true;
}
SurfaceLaunch::SurfaceLaunch() noexcept {
  std::array<uint8_t, 16> random;
  arc4random_buf(random.data(), random.size());
  name_ = "org.cloakfox.engine-host." + std::to_string(getpid()) + ".";
  constexpr char hex[] = "0123456789abcdef";
  for (const auto byte : random) { name_ += hex[byte >> 4]; name_ += hex[byte & 15]; }
  if (bootstrap_check_in(bootstrap_port, name_.c_str(), &port_) != KERN_SUCCESS)
    name_.clear();
}
SurfaceLaunch::~SurfaceLaunch() {
  if (MACH_PORT_VALID(port_)) mach_port_mod_refs(mach_task_self(), port_, MACH_PORT_RIGHT_RECEIVE, -1);
}
std::optional<SurfaceHello> SurfaceLaunch::accept(pid_t child, mach_msg_timeout_t timeoutMs) {
  if (child <= 0 || accepted_ || !MACH_PORT_VALID(port_)) return std::nullopt;
  Received<HelloMessage> received;
  if (!received.receive(port_, timeoutMs)) return std::nullopt;
  auto& message = received.message();
  const auto* audit = received.audit();
  if (message.header.msgh_id != kHello || message.version != kVersion || message.reserved ||
      (message.header.msgh_bits & MACH_MSGH_BITS_COMPLEX) || !audit ||
      audit_token_to_pid(*audit) != child ||
      MACH_MSGH_BITS_REMOTE(message.header.msgh_bits) != MACH_MSG_TYPE_PORT_SEND_ONCE ||
      !MACH_PORT_VALID(message.header.msgh_remote_port)) return std::nullopt;
  const auto reply = std::exchange(message.header.msgh_remote_port, MACH_PORT_NULL);
  accepted_ = true;
  return SurfaceHello(*audit, reply);
}
mach_port_t connectSurfaceHost(const char* name, mach_msg_timeout_t timeoutMs) {
  // Lookup confers no authority: the kernel audit token on the private reply
  // must still identify the direct parent. Keep the normal system bootstrap
  // namespace intact; libxpc caches it before main().
  mach_port_t destination = MACH_PORT_NULL;
  if (!name || bootstrap_look_up(bootstrap_port, name, &destination) != KERN_SUCCESS)
    return MACH_PORT_NULL;
  struct SendRight {
    mach_port_t port;
    ~SendRight() { mach_port_deallocate(mach_task_self(), port); }
  } destinationOwner{destination};
  ReceiveRight reply;
  if (mach_port_allocate(mach_task_self(), MACH_PORT_RIGHT_RECEIVE, &reply.port) != KERN_SUCCESS)
    return MACH_PORT_NULL;
  HelloMessage hello{};
  hello.header.msgh_bits = MACH_MSGH_BITS(MACH_MSG_TYPE_COPY_SEND, MACH_MSG_TYPE_MAKE_SEND_ONCE);
  hello.header.msgh_size = sizeof(hello); hello.header.msgh_id = kHello;
  hello.header.msgh_remote_port = destination; hello.header.msgh_local_port = reply.port;
  hello.version = kVersion;
  if (mach_msg(&hello.header, MACH_SEND_MSG | MACH_SEND_TIMEOUT, sizeof(hello),
      0, MACH_PORT_NULL, timeoutMs, MACH_PORT_NULL) != MACH_MSG_SUCCESS) return MACH_PORT_NULL;
  Received<ReplyMessage> received;
  if (!received.receive(reply.port, timeoutMs)) return MACH_PORT_NULL;
  auto& message = received.message();
  const auto* audit = received.audit();
  if (message.header.msgh_id != kReply || message.version != kVersion || message.reserved ||
      !(message.header.msgh_bits & MACH_MSGH_BITS_COMPLEX) ||
      message.header.msgh_remote_port != MACH_PORT_NULL || message.body.msgh_descriptor_count != 1 ||
      !audit || audit_token_to_pid(*audit) != getppid() ||
      !validSend(message.frames)) return MACH_PORT_NULL;
  return std::exchange(message.frames.name, MACH_PORT_NULL);
}
}
