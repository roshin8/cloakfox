"""Compile the production guard for pointer-first CSS hover departures."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class HoverRetention(unittest.TestCase):
    def test_pointer_and_mouse_phases_share_private_departure_policy(self):
        root = Path(__file__).resolve().parents[2]
        patch = (root / "patches/cloakfox-pointer-hover-retention.patch").read_text()
        after = "\n".join(line[1:] for line in patch.splitlines()
                          if line.startswith(("+", " ")) and not line.startswith("+++"))
        start = after.index("const bool retainHover")
        end = after.index(";", start) + 1
        guard = after[start:end]
        bookkeeping = next(line.strip() for line in after.splitlines()
                           if 'wrapper->DidDispatchOutAndOrLeaveEvent(' in line)
        start = after.index("const bool returningFromOutside")
        end = after.index(";", start) + 1
        return_guard = after[start:end]
        source = r'''
#include <cassert>
#include <initializer_list>
struct PolicyDoc {
  bool policy;
  bool ShouldMaskWindowActivity() { return policy; }
};
struct PresContext {
  PolicyDoc doc;
  PolicyDoc* Document() { return &doc; }
};
struct Wrapper {
  bool retained = false;
  void DidDispatchOutAndOrLeaveEvent(bool value) { retained = value; }
};
struct MouseEvent {
  bool trusted, hover;
  struct { bool mOnlySystemGroupDispatchInContent; } mFlags;
  bool mCloakfoxClearRetainedHover;
  bool IsTrusted() { return trusted; }
  bool InputSourceSupportsHover() { return hover; }
};
bool retain(bool isPointer, bool moving, bool trusted, bool hover,
            bool boundary, bool clear, bool policy) {
  bool aMovingInto = moving;
  MouseEvent event{trusted, hover, {boundary}, clear};
  auto* aMouseEvent = &event;
  PresContext context{{policy}};
  auto* mPresContext = &context;
''' + guard + r'''
  return retainHover;
}
bool retainedBoundaryTarget(bool retainHover, bool isPointer) {
  Wrapper held;
  auto* wrapper = &held;
''' + bookkeeping + r'''
  return held.retained;
}
bool pendingMouseReturn(bool isPointer, bool held, bool marker, bool trusted, bool policy) {
  bool mCloakfoxHoverRetained = held;
  bool mCloakfoxMouseEntryFromOutside = marker;
  MouseEvent event{trusted, true, {false}, false};
  auto* aMouseEvent = &event;
  PresContext context{{policy}};
  auto* mPresContext = &context;
''' + return_guard + r'''
  return returningFromOutside;
}
int main() {
  // Pointer entry has already replaced CSS state, while the following mouse
  // entry must still clear the held hover chain in the departed OOP subtree.
  assert(pendingMouseReturn(false, false, true, true, true));
  assert(pendingMouseReturn(false, true, false, true, true));
  assert(!pendingMouseReturn(false, false, false, true, true)); // marker consumed
  assert(!pendingMouseReturn(true, false, true, true, true)); // pointer phase
  assert(!pendingMouseReturn(false, false, true, false, true)); // untrusted
  assert(!pendingMouseReturn(false, false, true, true, false)); // native/system/off
  // Gecko 157 dispatches hover-capable pointer leave before mouse leave.
  // Either phase must retain the chain before the later phase can see it.
  for (bool pointer : {false, true}) {
    assert(retain(pointer, false, true, true, true, false, true));
    // Preserve mouse targets for CSS reconciliation, but never stale pointer
    // targets that suppress later iframe-to-parent boundary dispatch.
    assert(retainedBoundaryTarget(true, pointer) == !pointer);
    assert(!retainedBoundaryTarget(false, pointer));
    assert(!retain(pointer, true, true, true, true, false, true)); // in-page move
    assert(!retain(pointer, false, false, true, true, false, true)); // untrusted
    assert(!retain(pointer, false, true, false, true, false, true)); // no hover
    assert(!retain(pointer, false, true, true, false, false, true)); // ordinary exit
    assert(!retain(pointer, false, true, true, true, true, true)); // reconciliation
    assert(!retain(pointer, false, true, true, true, false, false)); // policy off
  }
}
'''
        with tempfile.TemporaryDirectory(prefix="cloakfox-hover-guard-", dir="/tmp") as tmp:
            cpp, binary = Path(tmp) / "guard.cpp", Path(tmp) / "guard"
            cpp.write_text(source)
            subprocess.run(["c++", "-std=c++17", str(cpp), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()
