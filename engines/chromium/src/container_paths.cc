#include "container_paths.h"
#include <filesystem>
#include <stdexcept>
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

namespace cloakfox {
namespace {
void privateDirectory(int fd) {
  struct stat info{};
  if (fd < 0 || fstat(fd, &info) || !S_ISDIR(info.st_mode) ||
      info.st_uid != geteuid() || (info.st_mode & 0777) != 0700)
    throw std::runtime_error("Profile directories must be owned by this user with mode 0700");
}
int openPrivateChild(int parent, const char* name) {
  if (mkdirat(parent, name, 0700) && errno != EEXIST)
    throw std::runtime_error("Cannot create profile directory");
  const int fd = openat(parent, name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
  try { privateDirectory(fd); } catch (...) { if (fd >= 0) close(fd); throw; }
  return fd;
}
}
bool isValidContainerId(const std::string& id) {
  if (id.empty() || id.front() == '0' || id.size() > 10) return false;
  for (const char c : id) if (c < '0' || c > '9') return false;
  return id.size() < 10 || id <= "2147483647";
}
ContainerPaths::ContainerPaths(const std::string& root) {
  if (!std::filesystem::path(root).is_absolute())
    throw std::runtime_error("Profile root must be absolute");
  rootFd_ = open(root.c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
  try {
    privateDirectory(rootFd_);
    root_ = std::filesystem::canonical(root).string();
    lockFd_ = openat(rootFd_, ".cloakfox-owner", O_RDWR | O_CREAT | O_NOFOLLOW | O_CLOEXEC, 0600);
    struct stat info{};
    if (lockFd_ < 0 || fstat(lockFd_, &info) || !S_ISREG(info.st_mode) ||
        info.st_uid != geteuid() || (info.st_mode & 0777) != 0600 ||
        flock(lockFd_, LOCK_EX | LOCK_NB))
      throw std::runtime_error("Profile root is unsafe or already owned by another companion");
    containersFd_ = openPrivateChild(rootFd_, "containers");
  } catch (...) {
    if (containersFd_ >= 0) close(containersFd_);
    if (lockFd_ >= 0) close(lockFd_);
    if (rootFd_ >= 0) close(rootFd_);
    throw;
  }
}
ContainerPaths::~ContainerPaths() {
  if (containersFd_ >= 0) close(containersFd_);
  if (lockFd_ >= 0) close(lockFd_);
  if (rootFd_ >= 0) close(rootFd_);
}
std::string ContainerPaths::cachePath(const std::string& id) const {
  if (!isValidContainerId(id)) throw std::runtime_error("Invalid container ID");
  const int fd = openPrivateChild(containersFd_, id.c_str());
  close(fd);
  return root_ + "/containers/" + id;
}
void ContainerPaths::configureKeychainMode(bool testKeychain) const {
  const std::string expected = testKeychain ? "test\n" : "native\n";
  int fd = openat(rootFd_, ".keychain-mode", O_RDWR | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
  const bool created = fd >= 0;
  if (created && !std::filesystem::is_empty(root_ + "/containers")) {
    close(fd); unlinkat(rootFd_, ".keychain-mode", 0);
    throw std::runtime_error("Unmarked existing profile: use a fresh prototype root");
  }
  if (!created && errno == EEXIST)
    fd = openat(rootFd_, ".keychain-mode", O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
  struct stat info{};
  if (fd < 0 || fstat(fd, &info) || !S_ISREG(info.st_mode) || info.st_nlink != 1 ||
      info.st_uid != geteuid() || (info.st_mode & 0777) != 0600) {
    if (fd >= 0) close(fd);
    throw std::runtime_error("Unsafe keychain mode record");
  }
  if (created) {
    const bool failed = write(fd, expected.data(), expected.size()) != static_cast<ssize_t>(expected.size()) || fsync(fd);
    close(fd);
    if (failed) throw std::runtime_error("Cannot persist keychain mode");
  } else {
    char content[16];
    const ssize_t length = read(fd, content, sizeof(content));
    close(fd);
    if (length < 0 || std::string(content, static_cast<size_t>(length)) != expected)
      throw std::runtime_error("Profile keychain mode cannot change; use a fresh profile root");
  }
}
}
