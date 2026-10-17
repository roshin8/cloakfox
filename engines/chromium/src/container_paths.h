#pragma once
#include <string>

namespace cloakfox {
bool isValidContainerId(const std::string& id);
// Owns an exclusive process lock for the prototype profile root.
class ContainerPaths {
 public:
  // Never a user container: public IDs are strictly positive decimal strings.
  static constexpr const char* kBootstrapProfile = "Default";
  explicit ContainerPaths(const std::string& root);
  ~ContainerPaths();
  ContainerPaths(const ContainerPaths&) = delete;
  ContainerPaths& operator=(const ContainerPaths&) = delete;
  std::string cachePath(const std::string& containerId) const;
  std::string bootstrapCachePath() const;
  void configureKeychainMode(bool testKeychain) const;
  const std::string& root() const { return root_; }
 private:
  std::string root_;
  int rootFd_ = -1;
  int containersFd_ = -1;
  int lockFd_ = -1;
};
}
