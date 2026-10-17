// Removing path validation, no-follow checks or the profile lock must fail here.
#include "container_paths.h"
#include <cassert>
#include <filesystem>
#include <iostream>
#include <sys/stat.h>
#include <unistd.h>

using cloakfox::ContainerPaths;
template<class F> void rejects(F action) {
  bool threw = false;
  try { action(); } catch (const std::exception&) { threw = true; }
  assert(threw);
}
int main() {
  char pattern[] = "/tmp/cloakfox-paths-XXXXXX";
  const std::filesystem::path root = std::filesystem::canonical(mkdtemp(pattern));
  {
    ContainerPaths paths(root.string());
    paths.configureKeychainMode(true);
    paths.configureKeychainMode(true);
    rejects([&] { paths.configureKeychainMode(false); });
    const auto a = paths.cachePath("1");
    const auto b = paths.cachePath("2");
    assert(a == root.string() + "/containers/1");
    assert(b == root.string() + "/containers/2");
    assert(paths.cachePath("1") == a);
    const auto bootstrap=paths.bootstrapCachePath();
    assert(bootstrap!=a && bootstrap!=b && paths.bootstrapCachePath()==bootstrap);
    rejects([&] { paths.cachePath(ContainerPaths::kBootstrapProfile); });
    std::filesystem::remove(bootstrap);
    std::filesystem::create_directory_symlink(root,bootstrap);
    rejects([&] { paths.bootstrapCachePath(); });
    std::filesystem::remove(bootstrap);
    assert(paths.bootstrapCachePath()==bootstrap);
    for (const auto id : {"", "0", "01", "-1", "1/2", "../escape", "2147483648", "1x"})
      rejects([&] { paths.cachePath(id); });
    rejects([&] { ContainerPaths duplicate(root.string()); });
    std::filesystem::create_directory_symlink(root, root / "containers/3");
    rejects([&] { paths.cachePath("3"); });
    struct stat info{};
    assert(stat(a.c_str(), &info) == 0);
    assert((info.st_mode & 0777) == 0700);
  }
  { ContainerPaths afterRelease(root.string());
    afterRelease.configureKeychainMode(true);
    rejects([&] { afterRelease.configureKeychainMode(false); });
    assert(!afterRelease.cachePath("1").empty()); }
  const auto link = root.string() + "-link";
  std::filesystem::create_directory_symlink(root, link);
  rejects([&] { ContainerPaths symlink(link); });
  std::filesystem::remove(link);
  chmod(root.c_str(), 0755);
  rejects([&] { ContainerPaths publicRoot(root.string()); });
  chmod(root.c_str(), 0700);
  std::filesystem::remove_all(root);
  std::cout << "PASS: container path boundaries, private directories and exclusive ownership\n";
}
