#pragma once
#include <string>

namespace cloakfox {
bool isValidContainerId(const std::string& id);
// Owns an exclusive process lock for the prototype profile root.
class ContainerPaths {
 public:
  explicit ContainerPaths(const std::string& root);
  ~ContainerPaths();
  ContainerPaths(const ContainerPaths&) = delete;
  ContainerPaths& operator=(const ContainerPaths&) = delete;
  std::string cachePath(const std::string& containerId) const;
  void configureKeychainMode(bool testKeychain) const;
  const std::string& root() const { return root_; }
 private:
  std::string root_;
  int rootFd_ = -1;
  int containersFd_ = -1;
  int lockFd_ = -1;
};
}
