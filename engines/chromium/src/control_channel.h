#pragma once
#include <atomic>
#include <functional>
#include <string>
#include <thread>

namespace cloakfox {
// Reads only inherited stdin. There is no socket, listening port or web binding.
class ControlChannel {
 public:
  using Message = std::function<void(std::string)>;
  using End = std::function<void()>;
  ControlChannel() = default;
  ~ControlChannel();
  void start(Message message, End end);
  void stop();
 private:
  std::atomic<bool> stopping_{false};
  std::thread reader_;
};
}
