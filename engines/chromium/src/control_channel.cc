#include "control_channel.h"
#include <cerrno>
#include <poll.h>
#include <unistd.h>

namespace cloakfox {
ControlChannel::~ControlChannel() { stop(); }
void ControlChannel::start(Message message, End end) {
  reader_ = std::thread([this, message = std::move(message), end = std::move(end)] {
    std::string pending;
    char buffer[4096];
    while (!stopping_) {
      struct pollfd input { STDIN_FILENO, POLLIN, 0 };
      const int ready = poll(&input, 1, 100);
      if (stopping_) break;
      if (ready < 0 && errno == EINTR) continue;
      if (ready < 0) break;
      if (!ready) continue;
      const ssize_t size = read(STDIN_FILENO, buffer, sizeof(buffer));
      if (size < 0 && errno == EINTR) continue;
      if (size <= 0) break;
      for (ssize_t i = 0; i < size; ++i) {
        if (buffer[i] == '\n') { message(std::move(pending)); pending.clear(); }
        else pending.push_back(buffer[i]);
        if (pending.size() > 1024 * 1024) { end(); return; }
      }
    }
    if (!stopping_) { if (!pending.empty()) message(std::move(pending)); end(); }
  });
}
void ControlChannel::stop() {
  stopping_ = true;
  if (reader_.joinable()) reader_.join();
}
}
