/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
#include "CloakfoxEngineHost.h"
#include "surface_launch_mac.h"
#include "surface_transport_mac.h"
#include "mozilla/Preferences.h"
#include "mozilla/AppUnits.h"
#include "mozilla/dom/HTMLCanvasElement.h"
#include "mozilla/dom/CanvasRenderingContext2D.h"
#include "mozilla/dom/ImageBitmap.h"
#include "mozilla/dom/UnionTypes.h"
#include "mozilla/gfx/2D.h"
#include "mozilla/BasePrincipal.h"
#include "mozilla/dom/Document.h"
#include "mozilla/dom/Element.h"
#include "nsGlobalWindowOuter.h"
#include "nsFocusManager.h"
#include "nsContentUtils.h"
#include "nsIFrame.h"
#include "nsIObserverService.h"
#include "nsIWidget.h"
#include "nsPIDOMWindow.h"
#include "nsPrintfCString.h"
#include "nsServiceManagerUtils.h"
#include "nsThreadUtils.h"
#include <map>
#include <optional>
#define JSON_NOEXCEPTION
#include "../../cloakcfg/json.hpp"
#include <algorithm>
#include "nsXULAppAPI.h"
#include <cmath>
#import <Cocoa/Cocoa.h>
#import "CloakfoxTextInputClient.h"
#import <QuartzCore/QuartzCore.h>
#include <dispatch/dispatch.h>

using namespace mozilla;
namespace {
struct Slot;
nsresult gate(nsPIDOMWindowOuter* window) {
  if (!NS_IsMainThread() || !XRE_IsParentProcess() ||
      !Preferences::GetBool("cloakfox.engine_host.test.enabled", false) || !window ||
      window->Closed() || !window->GetDoc() || !window->GetDoc()->NodePrincipal()->IsSystemPrincipal())
    return NS_ERROR_NOT_AVAILABLE;
  return NS_OK;
}
std::string hexToken(const cloakfox::SurfaceToken& token) {
  constexpr char hex[]="0123456789abcdef";
  std::string out;
  for(auto byte:token){out+=hex[byte>>4];out+=hex[byte&15];}
  return out;
}
std::optional<nlohmann::json> parseInputState(const nsACString& encoded) {
  if (encoded.IsEmpty() || encoded.Length()>2048) return std::nullopt;
  auto state=nlohmann::json::parse(encoded.BeginReading(),encoded.EndReading(),nullptr,false);
  if (!state.is_object() || state.size()!=6) return std::nullopt;
  for (const auto* key:{"field","editable","password","selection","composition","caret"})
    if (!state.contains(key)) return std::nullopt;
  if (!state["editable"].is_boolean() || !state["password"].is_boolean()) return std::nullopt;
  if (!state["editable"].get<bool>()) {
    if (state["password"].get<bool>()) return std::nullopt;
    for (const auto* key:{"field","selection","composition","caret"})
      if (!state[key].is_null()) return std::nullopt;
    return state;
  }
  const auto& field=state["field"];
  if (!field.is_object() || field.size()!=2 || !field.contains("document") || !field.contains("node") ||
      !field["document"].is_string() || !field["node"].is_number_integer() ||
      field["node"]<1 || field["node"]>INT32_MAX) return std::nullopt;
  const auto document=field["document"].get<std::string>();
  if (document.empty() || document.size()>128 ||
      document.find_first_not_of("0123456789abcdefABCDEF-")!=std::string::npos) return std::nullopt;
  for (const auto* key:{"selection","composition"}) {
    const auto& range=state[key];
    if (range.is_null()) continue;
    if (!range.is_array() || range.size()!=2) return std::nullopt;
    for (const auto& offset:range)
      if (!offset.is_number_integer() || offset<0 || offset>INT32_MAX) return std::nullopt;
    if (range[1]<range[0]) return std::nullopt;
  }
  const auto& caret=state["caret"];
  if (!caret.is_array() || caret.size()!=4) return std::nullopt;
  for (size_t i=0;i<4;++i)
    if (!caret[i].is_number_integer() || caret[i]<(i<2?-32768:0) || caret[i]>(i<2?32768:4096)) return std::nullopt;
  return state;
}
nsCString routeJSON(const cloakfox::SurfaceRoute& route) {
  return nsPrintfCString("{\"token\":\"%s\",\"configRevision\":%llu,\"viewportRevision\":%llu,\"width\":%u,\"height\":%u}",
      hexToken(route.token).c_str(),(unsigned long long)route.configRevision,
      (unsigned long long)route.viewportRevision,route.width,route.height);
}
}
@interface CloakfoxViewport : NSView <CloakfoxTextInputOwner> {
 @public Slot* owner;
 @public CloakfoxTextInputClient* textClient;
}
@end
namespace {
struct Launch {
  RefPtr<nsPIDOMWindowOuter> window;
  std::unique_ptr<cloakfox::SurfaceLaunch> endpoint;
  std::unique_ptr<cloakfox::SurfaceReceiver> receiver;
  dispatch_source_t deathWatch=nullptr;
  uint32_t pid=0;
  ~Launch(){if(deathWatch){dispatch_source_cancel(deathWatch);dispatch_release(deathWatch);}}
};
struct Slot {
  Launch* launch=nullptr;
  RefPtr<dom::Element> browser;
  RefPtr<dom::HTMLCanvasElement> canvas;
  RefPtr<dom::CanvasRenderingContext2D> canvasContext;
  nsCOMPtr<nsIObserver> observer;
  std::optional<nlohmann::json> editingState;
  cloakfox::SurfaceRoute route;
  CloakfoxViewport* view=nil;
  NSView* parent=nil;
  std::array<uint8_t,4> corner{};
  bool painted=false,requestedVisible=true;
  int32_t originX=0, originY=0;
  NSRect clipBounds=NSZeroRect;
  uint64_t sequence=0, pointerEvents=0, keyboardEvents=0;
  ~Slot(){
    if(view){[view->textClient detach];view->owner=nullptr;}
    if(canvasContext)canvasContext->ResetBitmap();
    if(view){view->owner=nullptr;view.layer.contents=nil;[view removeFromSuperview];[view release];}
    if(launch && launch->receiver)launch->receiver->detach(route.token);
    [parent release];
  }
  bool visible() const {
    auto* frame=browser->GetPrimaryFrame();
    auto* canvasFrame=canvas ? canvas->GetPrimaryFrame() : nullptr;
    return browser->OwnerDoc()==launch->window->GetDoc() && (!canvas || (canvas->IsInComposedDoc() && canvas->OwnerDoc()==browser->OwnerDoc() &&
        canvas->GetParentElement()==browser->GetParentElement() && canvasFrame && canvasFrame->IsVisibleConsideringAncestors())) && requestedVisible && !launch->window->Closed() && browser->IsInComposedDoc() &&
        frame && frame->IsVisibleConsideringAncestors() && painted && view.window && !NSIsEmptyRect(clipBounds);
  }
  MOZ_CAN_RUN_SCRIPT_BOUNDARY void focusBrowser() {
    RefPtr<dom::Element> target=browser;
    if(auto* manager=nsFocusManager::GetFocusManager())
      manager->SetFocus(target,nsIFocusManager::FLAG_NOSCROLL);
  }
  bool browserFocused() const { return browser->OwnerDoc()->GetActiveElement()==browser; }
  void input(const char* kind,int x,int y,int a=0,int b=0) {
    if(!visible())return;
    nsCString extra;
    if(strcmp(kind,"char")==0)extra=nsPrintfCString(",\"character\":%d",a);
    else if(strcmp(kind,"editKey")==0)extra=nsPrintfCString(",\"keyCode\":%d,\"shift\":%s",a,b?"true":"false");
    else if(strcmp(kind,"selectAll")==0) {} // No text, coordinates or modifiers.
    else {
      x=std::clamp(x,0,int(route.width)-1);y=std::clamp(y,0,int(route.height)-1);
      extra=nsPrintfCString(",\"x\":%d,\"y\":%d",x,y);
      if(strcmp(kind,"wheel")==0)extra.Append(nsPrintfCString(",\"deltaX\":%d,\"deltaY\":%d",a,b));
    }
    const auto data=nsPrintfCString("{\"token\":\"%s\",\"configRevision\":%llu,\"viewportRevision\":%llu,\"kind\":\"%s\"%s}",
        hexToken(route.token).c_str(),(unsigned long long)route.configRevision,
        (unsigned long long)route.viewportRevision,kind,extra.get());
    nsCOMPtr<nsIObserver> target=observer;
    NS_DispatchToMainThread(NS_NewRunnableFunction("CloakfoxNativeInput",[target,data]{
      target->Observe(nullptr,"cloakfox-engine-input",NS_ConvertUTF8toUTF16(data).get());
    }));
  }
  void commitText(NSString* text) {
    if (!visible() || !browserFocused() || !text.length || text.length>4096) return;
    // Serialize Cocoa text rather than interpolating it into a JSON string.
    // No text is logged; the private observer still revalidates this route at
    // delivery and again when writing the queued native request.
    NSDictionary* message=@{@"token":[NSString stringWithUTF8String:hexToken(route.token).c_str()],
      @"configRevision":@(route.configRevision),@"viewportRevision":@(route.viewportRevision),
      @"kind":@"commitText",@"text":text};
    NSData* encoded=[NSJSONSerialization dataWithJSONObject:message options:0 error:nil];
    if (!encoded) return;
    nsCString data(static_cast<const char*>(encoded.bytes),encoded.length);
    nsCOMPtr<nsIObserver> target=observer;
    NS_DispatchToMainThread(NS_NewRunnableFunction("CloakfoxNativeText",[target,data]{
      target->Observe(nullptr,"cloakfox-engine-input",NS_ConvertUTF8toUTF16(data).get());
    }));
  }
};
bool drawCanvasFrame(Slot& slot,const cloakfox::SurfaceSnapshot& frame) {
  if (slot.launch->window->Closed() || !slot.browser->IsInComposedDoc() || slot.browser->OwnerDoc()!=slot.launch->window->GetDoc() ||
      !slot.canvas->IsInComposedDoc() || slot.canvas->OwnerDoc()!=slot.browser->OwnerDoc() ||
      slot.canvas->GetParentElement()!=slot.browser->GetParentElement()) return false;
  nsCOMPtr<nsIGlobalObject> global=slot.canvas->OwnerDoc()->GetScopeObject();
  if (!global) return false;
  IgnoredErrorResult error;
  if (slot.canvas->Width()!=frame.route.width) slot.canvas->SetWidth(frame.route.width,error);
  if (slot.canvas->Height()!=frame.route.height) slot.canvas->SetHeight(frame.route.height,error);
  RefPtr<gfx::DataSourceSurface> surface=gfx::Factory::CreateDataSourceSurface(gfx::IntSize(frame.route.width,frame.route.height),gfx::SurfaceFormat::B8G8R8A8);
  if (!surface) return false;
  gfx::DataSourceSurface::MappedSurface map;
  if (!surface->Map(gfx::DataSourceSurface::WRITE,&map)) return false;
  for (uint32_t row=0;row<frame.route.height;++row)
    std::copy_n(frame.bgra.data()+row*frame.route.width*4,frame.route.width*4,map.mData+row*map.mStride);
  surface->Unmap();
  RefPtr<dom::ImageBitmap> bitmap=dom::ImageBitmap::CreateFromSourceSurface(global,surface,error);
  if (!bitmap) return false;
  dom::CanvasImageSource source;source.SetAsImageBitmap()=bitmap;
  slot.canvasContext->ClearRect(0,0,frame.route.width,frame.route.height);
  slot.canvasContext->DrawImage(source,0.0,0.0,error);
  return !error.Failed();
}
void setFrame(Slot& slot,const cloakfox::SurfaceSnapshot& frame) {
  if (slot.canvas) {
    if (!drawCanvasFrame(slot,frame)) {
      slot.canvasContext->ResetBitmap();
      slot.painted=false;slot.view.hidden=YES;return;
    }
  } else {
  auto* bytes=new std::vector<uint8_t>(frame.bgra);
  CGDataProviderRef provider=CGDataProviderCreateWithData(bytes,bytes->data(),bytes->size(),
      [](void* info,const void*,size_t){delete static_cast<std::vector<uint8_t>*>(info);});
  if(!provider){delete bytes;return;}
  CGColorSpaceRef color=CGColorSpaceCreateWithName(kCGColorSpaceSRGB);
  CGImageRef image=CGImageCreate(frame.route.width,frame.route.height,8,32,frame.route.width*4,color,
      kCGBitmapByteOrder32Little|kCGImageAlphaPremultipliedFirst,provider,nullptr,false,kCGRenderingIntentDefault);
  CGColorSpaceRelease(color);CGDataProviderRelease(provider);
  if(!image)return;
  [CATransaction begin];[CATransaction setDisableActions:YES];
  slot.view.layer.contents=(id)image;
  [CATransaction commit];CGImageRelease(image);
  }
  std::copy_n(frame.bgra.end()-4,4,slot.corner.begin());
  slot.sequence=frame.sequence;slot.painted=true;
  slot.view.hidden=!slot.visible();
}
bool bounds(int32_t x,int32_t y,uint32_t width,uint32_t height) {
  return x>=-32768 && y>=-32768 && x<=32768 && y<=32768 && width && height && width<=4096 && height<=4096;
}
void refreshClip(Slot& slot) {
  // Gecko may letterbox a larger fixed-size browser inside its browserStack.
  // Match that real layout clip without changing the protected page dimensions.
  auto* parentElement=slot.browser->GetParentElement();
  auto* frame=parentElement ? parentElement->GetPrimaryFrame() : nullptr;
  NSRect clip=NSZeroRect;
  if (frame) {
    const auto rect=frame->GetBoundingClientRect();
    const auto scale=AppUnitsPerCSSPixel();
    NSRect stack=NSMakeRect(double(rect.x)/scale,double(rect.y)/scale,
        double(rect.width)/scale,double(rect.height)/scale);
    NSRect browser=NSMakeRect(slot.originX,slot.originY,slot.route.width,slot.route.height);
    const NSRect intersection=NSIntersectionRect(stack,browser);
    if (!NSIsEmptyRect(intersection)) clip=NSOffsetRect(intersection,-slot.originX,-slot.originY);
  }
  slot.clipBounds=clip;
  [CATransaction begin];[CATransaction setDisableActions:YES];
  slot.view.layer.mask.frame=NSRectToCGRect(clip);
  [CATransaction commit];
}
void move(Slot& slot,int32_t x,int32_t y) {
  slot.originX=x;slot.originY=y;
  const auto height=slot.route.height;
  const CGFloat top=slot.parent.isFlipped?y:NSHeight(slot.parent.bounds)-y-height;
  slot.view.frame=NSMakeRect(x,top,slot.route.width,height);
  refreshClip(slot);
}
}
@implementation CloakfoxViewport
- (id)initWithFrame:(NSRect)frame {
  if ((self=[super initWithFrame:frame])) textClient=[[CloakfoxTextInputClient alloc] initWithOwner:self];
  return self;
}
- (void)dealloc {[textClient detach];[textClient release];[super dealloc];}
- (BOOL)canAcceptEngineTextInput {
  return owner && owner->visible() && owner->browserFocused() && self.window.isKeyWindow && self.window.firstResponder==self;
}
- (BOOL)sendEngineTextInput:(NSDictionary*)command {
  if (!owner || (![[command objectForKey:@"action"] isEqual:@"cancel"] && ![self canAcceptEngineTextInput])) return NO;
  NSMutableDictionary* message=[[command mutableCopy] autorelease];
  message[@"token"]=[NSString stringWithUTF8String:hexToken(owner->route.token).c_str()];
  message[@"configRevision"]=@(owner->route.configRevision);
  message[@"viewportRevision"]=@(owner->route.viewportRevision);
  message[@"kind"]=@"ownedIme";
  NSData* encoded=[NSJSONSerialization dataWithJSONObject:message options:0 error:nil];
  if (!encoded || encoded.length>32768) return NO;
  nsCString data(static_cast<const char*>(encoded.bytes),encoded.length);
  nsCOMPtr<nsIObserver> target=owner->observer;
  NS_DispatchToMainThread(NS_NewRunnableFunction("CloakfoxOwnedText",[target,data]{
    target->Observe(nullptr,"cloakfox-engine-input",NS_ConvertUTF8toUTF16(data).get());
  }));
  return YES;
}
- (NSRect)engineTextInputScreenRect:(NSRect)rect {
  if (![self canAcceptEngineTextInput]) return NSZeroRect;
  return [self.window convertRectToScreen:[self convertRect:rect toView:nil]];
}
- (void)engineEditingCommand:(SEL)selector {
  if (![self canAcceptEngineTextInput]) return;
  int key=0;bool shift=false;
  if(selector==@selector(deleteBackward:))key=8;
  else if(selector==@selector(deleteForward:))key=46;
  else if(selector==@selector(insertTab:))key=9;
  else if(selector==@selector(insertBacktab:)){key=9;shift=true;}
  else if(selector==@selector(insertNewline:))key=13;
  else if(selector==@selector(cancelOperation:))key=27;
  else if(selector==@selector(moveLeft:))key=37;
  else if(selector==@selector(moveRight:))key=39;
  else if(selector==@selector(moveUp:))key=38;
  else if(selector==@selector(moveDown:))key=40;
  else if(selector==@selector(moveToBeginningOfLine:))key=36;
  else if(selector==@selector(moveToEndOfLine:))key=35;
  else if(selector==@selector(moveLeftAndModifySelection:)){key=37;shift=true;}
  else if(selector==@selector(moveRightAndModifySelection:)){key=39;shift=true;}
  else if(selector==@selector(moveUpAndModifySelection:)){key=38;shift=true;}
  else if(selector==@selector(moveDownAndModifySelection:)){key=40;shift=true;}
  if(key)owner->input("editKey",0,0,key,shift);
}
- (NSTextInputContext*)inputContext {return [textClient inputContext];}
- (BOOL)resignFirstResponder {[textClient invalidateEditingState];return [super resignFirstResponder];}
- (BOOL)isFlipped{return YES;}
- (BOOL)isOpaque{return owner && !owner->canvas;}
- (BOOL)acceptsFirstResponder{return YES;}
- (BOOL)acceptsFirstMouse:(NSEvent*)event{return YES;}
- (NSView*)hitTest:(NSPoint)point {
  if (!owner || !owner->visible() ||
      !NSPointInRect([self convertPoint:point fromView:self.superview],owner->clipBounds)) return nil;
  if (owner->canvas) {
    [[self retain] autorelease];
    RefPtr<dom::HTMLCanvasElement> canvas=owner->canvas;
    RefPtr<dom::Element> browser=owner->browser;
    const float y=self.superview.isFlipped ? point.y : NSHeight(self.superview.bounds)-point.y;
    RefPtr<dom::Element> hit=browser->OwnerDoc()->ElementFromPoint(point.x,y);
    if (!owner || owner->canvas!=canvas || !owner->visible() || hit!=canvas) return nil;
  }
  return [super hitTest:point];
}
- (void)mouseDown:(NSEvent*)event {
  if(!owner)return;
  // Native input must also update Gecko's logical chrome focus. Otherwise
  // window activation restores its old ChildView responder after this click,
  // so the first key is routed to the hidden Gecko content instead of CEF.
  [[self retain] autorelease];
  ++owner->pointerEvents;
  owner->focusBrowser();
  if(!owner || !owner->visible())return;
  [self.window makeFirstResponder:self];
  dispatch_async(dispatch_get_main_queue(),^{
    if(self->owner && self->owner->visible() && self->owner->browserFocused() &&
        self.window.isKeyWindow && self.window.firstResponder==self->owner->parent)
      [self.window makeFirstResponder:self];
  });
  NSPoint p=[self convertPoint:event.locationInWindow fromView:nil];
  owner->input("mouseDown",int(p.x),int(p.y));
}
- (void)mouseUp:(NSEvent*)event {
  if(!owner)return;
  NSPoint p=[self convertPoint:event.locationInWindow fromView:nil];
  owner->input("mouseUp",int(p.x),int(p.y));
}
- (BOOL)performKeyEquivalent:(NSEvent*)event {
  const auto flags=event.modifierFlags & (NSEventModifierFlagCommand|NSEventModifierFlagShift|
      NSEventModifierFlagControl|NSEventModifierFlagOption);
  if ([self canAcceptEngineTextInput] && flags==NSEventModifierFlagCommand &&
      event.charactersIgnoringModifiers.length==1 &&
      [event.charactersIgnoringModifiers caseInsensitiveCompare:@"a"]==NSOrderedSame) {
    [self selectAll:nil];return YES;
  }
  if(owner && owner->visible() && flags==NSEventModifierFlagCommand &&
      event.charactersIgnoringModifiers.length==1 &&
      [event.charactersIgnoringModifiers caseInsensitiveCompare:@"l"]==NSOrderedSame){
    NSView* parent=[owner->parent retain];
    owner->input("focusLocation",0,0);
    [self.window makeFirstResponder:parent];
    [parent release];
    return YES;
  }
  return [super performKeyEquivalent:event];
}
- (void)selectAll:(id)sender {
  if ([self canAcceptEngineTextInput]) owner->input("selectAll",0,0);
}
- (void)keyDown:(NSEvent*)event {
  if(!owner)return;
  // Chrome input (for example the location bar) must never reach the page,
  // even if Cocoa has not yet updated a stale native first responder.
  if(!owner->visible() || !owner->browserFocused() ||
      (event.modifierFlags & (NSEventModifierFlagCommand|NSEventModifierFlagControl)) ||
      ((event.modifierFlags & NSEventModifierFlagOption) && ![textClient hasClient] && ![textClient needsEditingState])){
    NSView* parent=[owner->parent retain];
    [self.window makeFirstResponder:parent];
    [parent keyDown:event];
    [parent release];
    return;
  }
  ++owner->keyboardEvents;
  if ([textClient needsEditingState] && ![textClient canRouteUncomposedKey:event]) {
    [textClient handleKeyEvent:event];return;
  }
  int editing=0;
  switch(event.keyCode) {
    case 51:editing=8;break;
    case 48:editing=9;break;
    case 36:case 76:editing=13;break;
    case 53:editing=27;break;
    case 119:editing=35;break;
    case 115:editing=36;break;
    case 123:editing=37;break;
    case 126:editing=38;break;
    case 124:editing=39;break;
    case 125:editing=40;break;
    case 117:editing=46;break;
  }
  if ([textClient hasMarkedText] && [textClient handleKeyEvent:event]) return;
  if(editing) {
    owner->input("editKey",0,0,editing,(event.modifierFlags & NSEventModifierFlagShift)!=0);
    return;
  }
  if ([textClient hasClient]) { [textClient handleKeyEvent:event]; return; }
  NSString* text=event.characters;
  // AppKit encodes unsupported function/navigation keys in this private-use
  // range. They are commands, never committed Unicode text.
  for(NSUInteger i=0;i<text.length;++i) {
    const auto c=[text characterAtIndex:i];
    if(c>=0xf700 && c<=0xf8ff)return;
  }
  for(NSUInteger i=0;i<text.length;++i) {
    if([text characterAtIndex:i]>126) {owner->commitText(text);return;}
  }
  for(NSUInteger i=0;i<text.length;++i){const auto c=[text characterAtIndex:i];if(c>=32&&c<=126)owner->input("char",0,0,c);}
}
- (void)scrollWheel:(NSEvent*)event {
  if(!owner)return;
  NSPoint p=[self convertPoint:event.locationInWindow fromView:nil];
  const int x=std::clamp(int(std::round(event.scrollingDeltaX)),-4096,4096);
  const int y=std::clamp(int(std::round(event.scrollingDeltaY)),-4096,4096);
  owner->input("wheel",int(p.x),int(p.y),x,y);
}
@end

bool CloakfoxRouteEngineKeyDown(NSView* parent, NSEvent* event) {
  if (!NS_IsMainThread() || !parent.window.isKeyWindow) return false;
  const auto flags=event.modifierFlags & (NSEventModifierFlagCommand|NSEventModifierFlagShift|
      NSEventModifierFlagControl|NSEventModifierFlagOption);
  const bool location=flags==NSEventModifierFlagCommand &&
      event.charactersIgnoringModifiers.length==1 &&
      [event.charactersIgnoringModifiers caseInsensitiveCompare:@"l"]==NSOrderedSame;
  const bool selection=flags==NSEventModifierFlagCommand &&
      event.charactersIgnoringModifiers.length==1 &&
      [event.charactersIgnoringModifiers caseInsensitiveCompare:@"a"]==NSOrderedSame;
  // Unsupported browser shortcuts stay in Gecko. Decline before responder
  // changes so forwarding from the viewport cannot re-enter this route.
  if (!location && !selection && (flags & (NSEventModifierFlagCommand|NSEventModifierFlagControl)))
    return false;
  CloakfoxViewport* target=nil;
  for (NSView* child in parent.subviews) {
    if (![child isKindOfClass:[CloakfoxViewport class]]) continue;
    auto* view=static_cast<CloakfoxViewport*>(child);
    if (!view->owner || !view->owner->visible() || !view->owner->browserFocused()) continue;
    if (target) return false;
    target=view;
  }
  if (target && (flags & NSEventModifierFlagOption) && ![target->textClient hasClient] && ![target->textClient needsEditingState]) return false;
  if (target) {
    // Retain across event dispatch: a chrome shortcut may close the owner.
    [[target retain] autorelease];
    [parent.window makeFirstResponder:target];
    if (![target performKeyEquivalent:event]) [target keyDown:event];
    return true;
  }
  return false;
}

struct CloakfoxEngineHost::HostState {
  std::map<std::string,std::unique_ptr<Launch>> launches;
  std::map<std::string,std::unique_ptr<Slot>> slots;
  nsCOMPtr<nsITimer> timer;
  bool observingShutdown=false;
};
NS_IMPL_ISUPPORTS(CloakfoxEngineHost,nsICloakfoxEngineHost,nsITimerCallback,nsIObserver,nsINamed)
CloakfoxEngineHost::CloakfoxEngineHost():mState(std::make_unique<HostState>()){}
CloakfoxEngineHost::~CloakfoxEngineHost(){if(mState->timer)mState->timer->Cancel();}
NS_IMETHODIMP CloakfoxEngineHost::CreateLaunch(mozIDOMWindowProxy* owner,nsACString& result) {
  auto* window=nsPIDOMWindowOuter::From(owner);NS_ENSURE_SUCCESS(gate(window),NS_ERROR_NOT_AVAILABLE);
  {
    auto launch=std::make_unique<Launch>();launch->window=window;
    launch->endpoint=std::make_unique<cloakfox::SurfaceLaunch>();
    NS_ENSURE_TRUE(!launch->endpoint->name().empty(),NS_ERROR_NOT_AVAILABLE);
    result.Assign(launch->endpoint->name().c_str());
    mState->launches.emplace(launch->endpoint->name(),std::move(launch));
    if(!mState->timer){
      NS_NewTimerWithCallback(getter_AddRefs(mState->timer),this,16,nsITimer::TYPE_REPEATING_SLACK);
      nsCOMPtr<nsIObserverService> observers=do_GetService("@mozilla.org/observer-service;1");
      if(observers && !mState->observingShutdown){observers->AddObserver(this,"xpcom-shutdown",false);mState->observingShutdown=true;}
    }
    return NS_OK;
  }
}
NS_IMETHODIMP CloakfoxEngineHost::AcceptLaunch(mozIDOMWindowProxy* owner,const nsACString& name,uint32_t pid) {
  auto* window=nsPIDOMWindowOuter::From(owner);NS_ENSURE_SUCCESS(gate(window),NS_ERROR_NOT_AVAILABLE);
  const auto found=mState->launches.find(std::string(name.BeginReading(),name.Length()));
  NS_ENSURE_TRUE(found!=mState->launches.end() && found->second->window==window && !found->second->receiver,NS_ERROR_INVALID_ARG);
  {
    auto hello=found->second->endpoint->accept(pid,5000);
    NS_ENSURE_TRUE(hello,NS_ERROR_NOT_AVAILABLE);
    auto receiver=std::make_unique<cloakfox::SurfaceReceiver>(hello->audit());
    NS_ENSURE_TRUE(MACH_PORT_VALID(receiver->port()) && hello->reply(receiver->port()),NS_ERROR_FAILURE);
    auto watch=dispatch_source_create(DISPATCH_SOURCE_TYPE_PROC,pid,DISPATCH_PROC_EXIT,dispatch_get_main_queue());
    NS_ENSURE_TRUE(watch,NS_ERROR_FAILURE);
    RefPtr<CloakfoxEngineHost> self=this;
    const nsCString launchName(name);
    dispatch_source_set_event_handler(watch,^{self->CloseLaunch(launchName);});
    found->second->receiver=std::move(receiver);
    found->second->deathWatch=watch;
    found->second->pid=pid;
    dispatch_resume(watch);
    return NS_OK;
  }
}
NS_IMETHODIMP CloakfoxEngineHost::Attach(mozIDOMWindowProxy* owner,dom::Element* browser,
    const nsACString& name,uint32_t revision,int32_t x,int32_t y,uint32_t width,uint32_t height,
    nsIObserver* observer,nsACString& result) {
  auto* window=nsPIDOMWindowOuter::From(owner);NS_ENSURE_SUCCESS(gate(window),NS_ERROR_NOT_AVAILABLE);
  NS_ENSURE_TRUE(browser && browser->IsInComposedDoc() && browser->OwnerDoc()==window->GetDoc() && browser->NodePrincipal()->IsSystemPrincipal() &&
      bounds(x,y,width,height) && observer && revision>0,NS_ERROR_INVALID_ARG);
  for (const auto& entry : mState->slots) {
    NS_ENSURE_TRUE(entry.second->browser != browser, NS_ERROR_ALREADY_INITIALIZED);
  }
  const auto found=mState->launches.find(std::string(name.BeginReading(),name.Length()));
  NS_ENSURE_TRUE(found!=mState->launches.end() && found->second->window==window && found->second->receiver,NS_ERROR_INVALID_ARG);
  nsCOMPtr<nsIWidget> widget=nsGlobalWindowOuter::Cast(window)->GetMainWidget();NS_ENSURE_TRUE(widget,NS_ERROR_NOT_AVAILABLE);
  auto* parent=static_cast<NSView*>(widget->GetNativeData(NS_NATIVE_WIDGET));NS_ENSURE_TRUE(parent,NS_ERROR_NOT_AVAILABLE);
  {
    auto slot=std::make_unique<Slot>();slot->browser=browser;slot->launch=found->second.get();slot->observer=observer;
    arc4random_buf(slot->route.token.data(),slot->route.token.size());
    slot->route.configRevision=revision;slot->route.viewportRevision=1;slot->route.width=width;slot->route.height=height;
    NS_ENSURE_TRUE(slot->launch->receiver->attach(slot->route),NS_ERROR_FAILURE);
    slot->parent=[parent retain];slot->view=[[CloakfoxViewport alloc]initWithFrame:NSZeroRect];
    slot->view->owner=slot.get();slot->view.wantsLayer=YES;slot->view.hidden=YES;
    slot->view.layer.contentsGravity=kCAGravityResize;
    CALayer* mask=[CALayer layer];mask.backgroundColor=CGColorGetConstantColor(kCGColorBlack);
    slot->view.layer.mask=mask;
    move(*slot,x,y);[parent addSubview:slot->view];
    result=routeJSON(slot->route);
    mState->slots.emplace(hexToken(slot->route.token),std::move(slot));
    return NS_OK;
  }
}
NS_IMETHODIMP CloakfoxEngineHost::SetCanvas(const nsACString& token,dom::Element* element) {
  NS_ENSURE_TRUE(NS_IsMainThread(),NS_ERROR_NOT_AVAILABLE);
  const auto found=mState->slots.find(std::string(token.BeginReading(),token.Length()));
  NS_ENSURE_TRUE(found!=mState->slots.end(),NS_ERROR_INVALID_ARG);
  auto& slot=*found->second;
  auto* canvas=dom::HTMLCanvasElement::FromNodeOrNull(element);
  NS_ENSURE_TRUE(canvas && canvas->IsInComposedDoc() &&
      canvas->OwnerDoc()==slot.browser->OwnerDoc() && canvas->NodePrincipal()->IsSystemPrincipal() &&
      canvas->GetParentElement()==slot.browser->GetParentElement() && !slot.canvas,NS_ERROR_INVALID_ARG);
  nsCOMPtr<nsISupports> context;
  NS_ENSURE_SUCCESS(canvas->GetContext(u"2d"_ns,getter_AddRefs(context)),NS_ERROR_FAILURE);
  NS_ENSURE_TRUE(context,NS_ERROR_FAILURE);
  slot.canvas=canvas;slot.canvasContext=static_cast<dom::CanvasRenderingContext2D*>(context.get());
  slot.view.layer.contents=nil;slot.painted=false;
  return NS_OK;
}
NS_IMETHODIMP CloakfoxEngineHost::UpdateViewport(const nsACString& token,int32_t x,int32_t y,
    uint32_t width,uint32_t height,bool visible,nsACString& result) {
  NS_ENSURE_TRUE(NS_IsMainThread() && bounds(x,y,width,height),NS_ERROR_INVALID_ARG);
  const auto found=mState->slots.find(std::string(token.BeginReading(),token.Length()));NS_ENSURE_TRUE(found!=mState->slots.end(),NS_ERROR_INVALID_ARG);
  auto& slot=*found->second;
  if(slot.route.width!=width || slot.route.height!=height){
    NS_ENSURE_TRUE(slot.route.viewportRevision<INT32_MAX,NS_ERROR_FAILURE);
    const auto next=slot.route.viewportRevision+1;
    NS_ENSURE_TRUE(slot.launch->receiver->resize(slot.route.token,slot.route.configRevision,next,width,height),NS_ERROR_FAILURE);
    slot.route.viewportRevision=next;slot.route.width=width;slot.route.height=height;
    [slot.view->textClient cancelAndDeactivate];
    slot.editingState.reset();
    [slot.view->textClient setEditingState:@{@"field":[NSNull null],@"editable":@NO,@"password":@NO,@"selection":[NSNull null],@"composition":[NSNull null],@"caret":[NSNull null]}];
    // Old pixels belong to the retired viewport epoch. Clear the owned
    // compositor bitmap even if a replacement paint never arrives.
    if(slot.canvasContext)slot.canvasContext->ResetBitmap();
    slot.painted=false;slot.view.layer.contents=nil;
  }
  slot.requestedVisible=visible;move(slot,x,y);slot.view.hidden=!slot.visible();result=routeJSON(slot.route);return NS_OK;
}
NS_IMETHODIMP CloakfoxEngineHost::SetInputState(const nsACString& token,uint32_t configRevision,
    uint32_t viewportRevision,const nsACString& encoded) {
  NS_ENSURE_TRUE(NS_IsMainThread(),NS_ERROR_NOT_AVAILABLE);
  const auto found=mState->slots.find(std::string(token.BeginReading(),token.Length()));
  NS_ENSURE_TRUE(found!=mState->slots.end(),NS_ERROR_INVALID_ARG);
  auto& slot=*found->second;
  NS_ENSURE_SUCCESS(gate(slot.launch->window),NS_ERROR_NOT_AVAILABLE);
  NS_ENSURE_TRUE(slot.route.configRevision==configRevision && slot.route.viewportRevision==viewportRevision,
      NS_ERROR_NOT_AVAILABLE);
  auto state=parseInputState(encoded);
  NS_ENSURE_TRUE(state,NS_ERROR_INVALID_ARG);
  const auto serialized=state->dump();
  NSData* bytes=[NSData dataWithBytes:serialized.data() length:serialized.size()];
  id metadata=[NSJSONSerialization JSONObjectWithData:bytes options:0 error:nil];
  NS_ENSURE_TRUE([slot.view->textClient setEditingState:metadata],NS_ERROR_INVALID_ARG);
  slot.editingState=std::move(state);
  return NS_OK;
}
NS_IMETHODIMP CloakfoxEngineHost::InvalidateInputState(const nsACString& token,uint32_t configRevision,uint32_t viewportRevision) {
  NS_ENSURE_TRUE(NS_IsMainThread(),NS_ERROR_NOT_AVAILABLE);
  const auto found=mState->slots.find(std::string(token.BeginReading(),token.Length()));
  NS_ENSURE_TRUE(found!=mState->slots.end(),NS_ERROR_INVALID_ARG);
  auto& slot=*found->second;
  NS_ENSURE_SUCCESS(gate(slot.launch->window),NS_ERROR_NOT_AVAILABLE);
  NS_ENSURE_TRUE(slot.route.configRevision==configRevision && slot.route.viewportRevision==viewportRevision,NS_ERROR_NOT_AVAILABLE);
  slot.editingState.reset();[slot.view->textClient invalidateEditingState];return NS_OK;
}
NS_IMETHODIMP CloakfoxEngineHost::State(const nsACString& token,nsACString& result) {
  NS_ENSURE_TRUE(NS_IsMainThread(),NS_ERROR_NOT_AVAILABLE);
  const auto found=mState->slots.find(std::string(token.BeginReading(),token.Length()));NS_ENSURE_TRUE(found!=mState->slots.end(),NS_ERROR_INVALID_ARG);
  auto& slot=*found->second;
  result=nsPrintfCString("{\"presentation\":\"%s\",\"painted\":%s,\"visible\":%s,\"nativeWindowMatches\":%s,\"pointerEvents\":%llu,\"keyboardEvents\":%llu,\"nativeKeyboardFocus\":%s,\"parentKeyboardFocus\":%s,\"helperPid\":%u,\"nativeWindowId\":%ld,\"configRevision\":%llu,\"viewportRevision\":%llu,\"inputClientReady\":%s,\"sequence\":%llu,\"viewWidth\":%d,\"viewHeight\":%d,\"clipWidth\":%d,\"clipHeight\":%d,\"cornerBGRA\":[%u,%u,%u,%u]}",
      slot.canvas?"gecko-compositor":"native-view",slot.painted?"true":"false",(!slot.view.hidden&&slot.visible())?"true":"false",
      (slot.view.window && slot.view.window==slot.parent.window)?"true":"false",(unsigned long long)slot.pointerEvents,(unsigned long long)slot.keyboardEvents,
      (slot.view.window.firstResponder==slot.view)?"true":"false",(slot.view.window.firstResponder==slot.parent)?"true":"false",slot.launch->pid,(long)slot.view.window.windowNumber,(unsigned long long)slot.route.configRevision,
      (unsigned long long)slot.route.viewportRevision,(slot.editingState && (*slot.editingState)["editable"].get<bool>())?"true":"false",
      (unsigned long long)slot.sequence,int(NSWidth(slot.view.frame)),int(NSHeight(slot.view.frame)),int(NSWidth(slot.clipBounds)),int(NSHeight(slot.clipBounds)),slot.corner[0],slot.corner[1],slot.corner[2],slot.corner[3]);
  // This service is chrome-only and test-pref gated. Export bounded counters
  // for native input acceptance, never event text or renderer field IDs.
  NSData* diagnostics=[NSJSONSerialization dataWithJSONObject:[slot.view->textClient routingDiagnostics] options:0 error:nil];
  if (diagnostics) {
    result.Truncate(result.Length()-1);result.AppendLiteral(",\"inputRouting\":");
    result.Append(static_cast<const char*>(diagnostics.bytes),diagnostics.length);result.Append('}');
  }
  return NS_OK;
}
NS_IMETHODIMP CloakfoxEngineHost::Close(const nsACString& token) {
  NS_ENSURE_TRUE(NS_IsMainThread(),NS_ERROR_NOT_AVAILABLE);mState->slots.erase(std::string(token.BeginReading(),token.Length()));return NS_OK;
}
NS_IMETHODIMP CloakfoxEngineHost::CloseLaunch(const nsACString& name) {
  NS_ENSURE_TRUE(NS_IsMainThread(),NS_ERROR_NOT_AVAILABLE);
  const std::string key(name.BeginReading(),name.Length());const auto found=mState->launches.find(key);
  if(found==mState->launches.end())return NS_OK;
  for(auto it=mState->slots.begin();it!=mState->slots.end();){
    if(it->second->launch==found->second.get())it=mState->slots.erase(it);else ++it;
  }
  mState->launches.erase(found);
  if(mState->launches.empty() && mState->timer){mState->timer->Cancel();mState->timer=nullptr;}
  return NS_OK;
}
NS_IMETHODIMP CloakfoxEngineHost::Notify(nsITimer*) {
  // Frame publication may resize a chrome canvas. Defer DOM reactions until
  // no map entry/reference is in use, so owner closure cannot re-enter a draw.
  nsAutoScriptBlocker scriptBlocker;
  {
    for(auto& [name,launch]:mState->launches){
      if(!launch->receiver)continue;
      // Bound per-tick copying even if a producer fills the Mach queue.
      for(int i=0;i<4;++i){
        auto frame=launch->receiver->receive(0);if(!frame)break;
        const auto found=mState->slots.find(hexToken(frame->route.token));
        if(found!=mState->slots.end() && found->second->route==frame->route && found->second->launch==launch.get())
          setFrame(*found->second,*frame);
      }
    }
    for(auto& [token,slot]:mState->slots){refreshClip(*slot);slot->view.hidden=!slot->visible();[slot->view->textClient refreshActivity];
      if ([slot->view canAcceptEngineTextInput] && [slot->view->textClient beginRefreshIfNeeded]) slot->input("refreshInput",0,0);
    }
  }
  return NS_OK;
}
NS_IMETHODIMP CloakfoxEngineHost::Observe(nsISupports*,const char* topic,const char16_t*) {
  if(strcmp(topic,"xpcom-shutdown")==0){
    if(mState->timer){mState->timer->Cancel();mState->timer=nullptr;}
    mState->slots.clear();mState->launches.clear();
  }
  return NS_OK;
}

NS_IMETHODIMP CloakfoxEngineHost::GetName(nsACString& name) { name.AssignLiteral("CloakfoxEngineHost"); return NS_OK; }
