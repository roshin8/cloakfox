#pragma once
#include <mach/mach.h>
#include <optional>
#include <string>
#include <sys/types.h>

namespace cloakfox {
// A per-launch Mach rendezvous authenticates the kernel sender against the
// live spawned child's PID. The response binds subsequent frames to its full
// audit token. Names are not authentication secrets; page code has no binding.
class SurfaceHello {
 public:
  SurfaceHello(audit_token_t audit, mach_port_t reply) : audit_(audit), reply_(reply) {}
  SurfaceHello(SurfaceHello&& other) noexcept;
  ~SurfaceHello();
  SurfaceHello(const SurfaceHello&) = delete;
  SurfaceHello& operator=(const SurfaceHello&) = delete;
  const audit_token_t& audit() const { return audit_; }
  bool reply(mach_port_t frameReceiver);
 private:
  audit_token_t audit_;
  mach_port_t reply_;
};
class SurfaceLaunch {
 public:
  SurfaceLaunch() noexcept;
  ~SurfaceLaunch();
  SurfaceLaunch(const SurfaceLaunch&) = delete;
  SurfaceLaunch& operator=(const SurfaceLaunch&) = delete;
  const std::string& name() const { return name_; }
  std::optional<SurfaceHello> accept(pid_t child, mach_msg_timeout_t timeoutMs);
 private:
  mach_port_t port_ = MACH_PORT_NULL;
  std::string name_;
  bool accepted_ = false;
};
// Caller owns the returned send right. Null means no authenticated connection;
// the helper must exit without initializing Chromium or navigating any page.
mach_port_t connectSurfaceHost(const char* name, mach_msg_timeout_t timeoutMs);
}
