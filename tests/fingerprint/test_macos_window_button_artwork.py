"""Render real inactive AppKit controls without activating or showing a window."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

@unittest.skipUnless(sys.platform == 'darwin', 'AppKit rendering requires macOS')
class WindowButtonArtworkTest(unittest.TestCase):
    def test_exact_active_bitmap_replay_and_native_disabled_state(self):
        patch = (ROOT/'patches/cloakfox-macos-colored-window-buttons.patch').read_text()
        source = '\n'.join(line[1:] for line in patch.splitlines() if line.startswith('+') and not line.startswith('+++'))
        start = source.index('@interface CloakfoxWindowButtonArtwork')
        end = source.index('\n@end', source.index('@implementation CloakfoxWindowButtonArtwork', start)) + len('\n@end')
        code = '#import <Cocoa/Cocoa.h>\n#include <cassert>\nnamespace mozilla { struct Preferences { inline static bool enabled=true; static bool GetBool(const char*,bool) { return enabled; } }; }\n'+source[start:end]+r'''

@interface ArtworkTestWindow : NSWindow
@property BOOL testKey;
@end
@implementation ArtworkTestWindow
- (BOOL)isKeyWindow { return self.testKey; }
@end
static NSBitmapImageRep* Render(NSView* view, NSBitmapImageRep* expected) {
  NSImage* image=[[NSImage alloc] initWithSize:view.bounds.size];
  [image lockFocus];
  if (expected) [expected drawInRect:view.bounds];
  else [(CloakfoxWindowButtonArtwork*)view drawRect:view.bounds];
  [image unlockFocus];
  return [[[NSBitmapImageRep alloc] initWithData:image.TIFFRepresentation] autorelease];
}
int main() { @autoreleasepool {
  [NSApplication sharedApplication];
  ArtworkTestWindow* w = [[ArtworkTestWindow alloc] initWithContentRect:NSMakeRect(0,0,320,160)
      styleMask:15 backing:NSBackingStoreBuffered defer:NO];
  assert(!w.mainWindow);
  for (NSInteger kind=0;kind<3;kind++) {
    NSButton* b=[w standardWindowButton:(NSWindowButton)kind];
    auto* artwork=[[CloakfoxWindowButtonArtwork alloc] initWithFrame:b.bounds];
    [b addSubview:artwork];
    assert([artwork hitTest:NSMakePoint(5,5)]==nil);
    assert(!artwork.isAccessibilityElement);
    w.testKey=YES;
    [artwork captureActiveArtwork];
    NSBitmapImageRep* expected=[artwork valueForKey:@"mActiveArtwork"];
    assert(expected);
    w.testKey=NO;
    auto* reference=Render(artwork,expected);
    auto* actual=Render(artwork,nil);
    assert(reference.pixelsWide==actual.pixelsWide && reference.pixelsHigh==actual.pixelsHigh);
    assert([[reference representationUsingType:NSBitmapImageFileTypePNG properties:@{}]
        isEqual:[actual representationUsingType:NSBitmapImageFileTypePNG properties:@{}]]);
    mozilla::Preferences::enabled=false;
    auto* off=Render(artwork,nil);
    assert([off colorAtX:off.pixelsWide/2 y:off.pixelsHigh/2].alphaComponent<0.01);
    mozilla::Preferences::enabled=true;
    b.enabled=NO;
    auto* disabled=Render(artwork,nil);
    assert([disabled colorAtX:disabled.pixelsWide/2 y:disabled.pixelsHigh/2].alphaComponent<0.01);
  }
  assert(!w.keyWindow && !w.mainWindow);
}}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp,'artwork.mm');src.write_text(code)
            binary=Path(tmp,'artwork')
            subprocess.run(['xcrun','clang++','-std=c++17','-framework','Cocoa',str(src),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)

if __name__=='__main__': unittest.main()
