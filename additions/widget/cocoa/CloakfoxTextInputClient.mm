/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
#import "CloakfoxTextInputClient.h"
#import <Carbon/Carbon.h>
#include <cmath>
namespace {
bool keys(id value, NSArray* names) {
  return [value isKindOfClass:[NSDictionary class]] && [value count]==names.count &&
      [[NSSet setWithArray:[value allKeys]] isEqualToSet:[NSSet setWithArray:names]];
}
bool boolean(id value) {
  return [value isKindOfClass:[NSNumber class]] && CFGetTypeID((CFTypeRef)value)==CFBooleanGetTypeID();
}
bool integer(id value, double low, double high) {
  if (![value isKindOfClass:[NSNumber class]] || boolean(value) || CFNumberIsFloatType((CFNumberRef)value)) return false;
  const double number=[value doubleValue];
  return std::isfinite(number) && number>=low && number<=high;
}
bool range(id value) {
  return value==[NSNull null] || ([value isKindOfClass:[NSArray class]] && [value count]==2 &&
      integer(value[0],0,INT32_MAX) && integer(value[1],0,INT32_MAX) && [value[1] longLongValue]>=[value[0] longLongValue]);
}
bool stateValid(id value) {
  if (!keys(value,@[@"field",@"editable",@"password",@"selection",@"composition",@"caret"]) ||
      !boolean(value[@"editable"]) || !boolean(value[@"password"])) return false;
  if (![value[@"editable"] boolValue]) return ![value[@"password"] boolValue] &&
      value[@"field"]==[NSNull null] && value[@"selection"]==[NSNull null] &&
      value[@"composition"]==[NSNull null] && value[@"caret"]==[NSNull null];
  id field=value[@"field"];
  if (!keys(field,@[@"document",@"node"])) return false;
  id document=field[@"document"];
  if (![document isKindOfClass:[NSString class]] ||
      ![document length] || [document length]>128 || !integer(field[@"node"],1,INT32_MAX) ||
      [document rangeOfCharacterFromSet:[[NSCharacterSet characterSetWithCharactersInString:@"0123456789abcdefABCDEF-"] invertedSet]].location!=NSNotFound ||
      !range(value[@"selection"]) || !range(value[@"composition"])) return false;
  id caret=value[@"caret"];
  if (![caret isKindOfClass:[NSArray class]] || [caret count]!=4) return false;
  for (NSUInteger i=0;i<4;++i) if(!integer(caret[i],i<2?-32768:0,i<2?32768:4096)) return false;
  return true;
}
NSString* plainText(id value) {
  if ([value isKindOfClass:[NSAttributedString class]]) value=[value string];
  if (![value isKindOfClass:[NSString class]] || [value length]>4096) return nil;
  for (NSUInteger i=0;i<[value length];++i) {
    const auto c=[value characterAtIndex:i];
    if ((c<32 && c!=9 && c!=10 && c!=13) || (c>=0x7f && c<=0x9f) || (c>=0xdc00 && c<=0xdfff)) return nil;
    if(c>=0xd800 && c<=0xdbff) {
      if(++i>=[value length]) return nil;
      const auto next=[value characterAtIndex:i];if(next<0xdc00 || next>0xdfff)return nil;
    }
  }
  return value;
}
}
@implementation CloakfoxTextInputClient
- (id)initWithOwner:(id<CloakfoxTextInputOwner>)owner {
  if ((self=[super init])) {_owner=owner;_pendingKeys=[[NSMutableArray alloc] init];_markedRange=_selection=NSMakeRange(NSNotFound,0);}
  return self;
}
- (void)dealloc {[self detach];[_state release];[_pendingKeys release];[super dealloc];}
- (BOOL)hasClient {return !_invalidated && [_state[@"editable"] boolValue];}
- (BOOL)needsEditingState {return _invalidated;}
- (BOOL)beginRefreshIfNeeded {
  if (!_invalidated || _refreshRequested) return NO;
  _refreshRequested=YES;return YES;
}
- (void)invalidateEditingState {
  [self cancelAndDeactivate];_invalidated=YES;_refreshRequested=NO;
  _retiredKeys+=_pendingKeys.count;
  [_pendingKeys removeAllObjects];
  // Pending type is conservatively secure. No input context may receive a
  // key until native type/focus metadata has been refreshed.
  if (_owner && [_owner canAcceptEngineTextInput] && !_secureInput)
    _secureInput=EnableSecureEventInput()==noErr;
}
- (BOOL)setEditingState:(NSDictionary*)state {
  if (!stateValid(state)) return NO;
  NSData* data=[NSJSONSerialization dataWithJSONObject:state options:0 error:nil];
  if (!data || data.length>2048) return NO;
  NSDictionary* copy=[NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
  if (!copy) return NO;
  if (![_state[@"field"] isEqual:copy[@"field"]] || ![_state[@"password"] isEqual:copy[@"password"]]) [self discardComposition];
  NSArray* pending=_invalidated && [_state[@"field"] isEqual:copy[@"field"]]?[_pendingKeys copy]:nil;
  if (!pending) _foreignFieldKeys+=_pendingKeys.count;
  [_pendingKeys removeAllObjects];
  [copy retain];[_state release];_state=copy;_invalidated=NO;_refreshRequested=NO;
  [self refreshActivity];
  if (!_invalidated && _owner && [_owner canAcceptEngineTextInput]) {
    for (NSEvent* event in pending) {
      if ([NSProcessInfo processInfo].systemUptime-event.timestamp<=0.5) [self handleKeyEvent:event];
      else ++_expiredKeys;
    }
  }
  [pending release];
  return YES;
}
- (void)discardComposition {
  if (_discarding) return;
  _discarding=YES;[_context discardMarkedText];_discarding=NO;
  [_marked release];_marked=nil;_markedRange=_selection=NSMakeRange(NSNotFound,0);
}
- (BOOL)send:(NSString*)action text:(NSString*)text selected:(NSRange)selected replacement:(NSRange)replacement {
  if (!_owner || ![self hasClient] || _discarding ||
      (![action isEqual:@"cancel"] && ![_owner canAcceptEngineTextInput])) return NO;
  NSMutableDictionary* command=[NSMutableDictionary dictionaryWithDictionary:@{@"action":action,@"field":_state[@"field"]}];
  if (text) command[@"text"]=[[text copy] autorelease];
  if ([action isEqual:@"set"]) {command[@"selectionStart"]=@(selected.location);command[@"selectionEnd"]=@(NSMaxRange(selected));}
  if (replacement.location!=NSNotFound) {
    if (replacement.location>INT32_MAX || replacement.length>INT32_MAX-replacement.location) return NO;
    command[@"replacement"]=@[@(replacement.location),@(NSMaxRange(replacement))];
  }
  return [_owner sendEngineTextInput:command];
}
- (void)cancelAndDeactivate {
  if ([self hasMarkedText]) [self send:@"cancel" text:nil selected:NSMakeRange(0,0) replacement:NSMakeRange(NSNotFound,0)];
  [self discardComposition];[_context deactivate];
  if (_secureInput) {DisableSecureEventInput();_secureInput=NO;}
}
- (void)refreshActivity {
  const BOOL active=_owner && [_owner canAcceptEngineTextInput];
  if (!active) {
    if (!_invalidated) [self invalidateEditingState];
    [_pendingKeys removeAllObjects];[self cancelAndDeactivate];return;
  }
  const BOOL secure=_invalidated || ([self hasClient] && [_state[@"password"] boolValue]);
  if (secure && !_secureInput) _secureInput=EnableSecureEventInput()==noErr;
  else if (!secure && _secureInput) {DisableSecureEventInput();_secureInput=NO;}
  if (secure) [_context deactivate];
}
- (void)detach {
  _owner=nil;[_pendingKeys removeAllObjects];[self discardComposition];[_context deactivate];[_context release];_context=nil;
  if (_secureInput) {DisableSecureEventInput();_secureInput=NO;}
}
- (NSTextInputContext*)inputContext {
  [self refreshActivity];
  if (!_owner || ![_owner canAcceptEngineTextInput] || ![self hasClient] || [_state[@"password"] boolValue]) return nil;
  if (!_context) _context=[[NSTextInputContext alloc] initWithClient:self];
  return _context;
}
- (BOOL)canRouteUncomposedKey:(NSEvent*)event {
  [self refreshActivity];
  // During the first click's type refresh, ordinary keyboard events still
  // belong to the selected browser. Do not bind them to an obsolete null
  // field and then discard them. This is the existing native keyboard path,
  // never an input-context/composition or unbound Unicode-commit fallback.
  if (!_invalidated || !_secureInput || !_owner || ![_owner canAcceptEngineTextInput] ||
      !_state || [_state[@"editable"] boolValue] || _state[@"field"]!=[NSNull null] ||
      (event.modifierFlags & (NSEventModifierFlagCommand|NSEventModifierFlagControl|NSEventModifierFlagOption)) ||
      !event.characters.length) return NO;
  for (NSUInteger i=0;i<event.characters.length;++i) {
    const auto c=[event.characters characterAtIndex:i];if(c<32 || c>126)return NO;
  }
  return YES;
}
- (BOOL)handleKeyEvent:(NSEvent*)event {
  [self refreshActivity];
  if (!_owner || ![_owner canAcceptEngineTextInput]) return NO;
  if (_invalidated) {if (_pendingKeys.count<16) {[_pendingKeys addObject:event];++_queuedKeys;}else ++_retiredKeys;return YES;}
  if (![self hasClient]) return NO;
  if (event.modifierFlags & (NSEventModifierFlagCommand|NSEventModifierFlagControl)) return NO;
  if ([_state[@"password"] boolValue]) {
    // Password input never goes through a third-party input context. Failure
    // to acquire secure input consumes the event without a raw fallback.
    if (_secureInput) {
      SEL edit=nullptr;
      switch(event.keyCode) {
        case 51:edit=@selector(deleteBackward:);break;case 117:edit=@selector(deleteForward:);break;
        case 36:case 76:edit=@selector(insertNewline:);break;
        case 48:edit=(event.modifierFlags & NSEventModifierFlagShift)?@selector(insertBacktab:):@selector(insertTab:);break;
        case 53:edit=@selector(cancelOperation:);break;
        case 123:edit=@selector(moveLeft:);break;case 124:edit=@selector(moveRight:);break;
        case 125:edit=@selector(moveDown:);break;case 126:edit=@selector(moveUp:);break;
      }
      if(edit)[_owner engineEditingCommand:edit];
      else [self insertText:event.characters replacementRange:NSMakeRange(NSNotFound,0)];
    }
    return YES;
  }
  const BOOL handled=[[self inputContext] handleEvent:event];
  if (!handled) ++_unhandledKeys;
  return handled;
}
- (NSDictionary*)routingDiagnostics {
  return @{@"queued":@(_queuedKeys),@"retired":@(_retiredKeys),
    @"foreignField":@(_foreignFieldKeys),@"expired":@(_expiredKeys),@"unhandled":@(_unhandledKeys)};
}
- (BOOL)hasMarkedText {return _marked.length>0;}
- (NSRange)markedRange {return [self hasMarkedText]?_markedRange:NSMakeRange(NSNotFound,0);}
- (NSRange)selectedRange {
  if ([self hasMarkedText]) return _selection;
  NSArray* range=_state[@"selection"];
  return [range isKindOfClass:[NSArray class]]?NSMakeRange([range[0] unsignedIntegerValue],[range[1] unsignedIntegerValue]-[range[0] unsignedIntegerValue]):NSMakeRange(NSNotFound,0);
}
- (NSArray*)validAttributesForMarkedText {return @[NSUnderlineStyleAttributeName,NSUnderlineColorAttributeName,NSMarkedClauseSegmentAttributeName];}
- (void)setMarkedText:(id)value selectedRange:(NSRange)selected replacementRange:(NSRange)replacement {
  NSString* text=plainText(value);
  if (!text || selected.location>text.length || selected.length>text.length-selected.location || [_state[@"password"] boolValue]) return;
  if (![self send:@"set" text:text selected:selected replacement:replacement]) return;
  NSUInteger base=replacement.location!=NSNotFound?replacement.location:_markedRange.location;
  if (base==NSNotFound) {
    const NSRange current=[self selectedRange];base=replacement.location!=NSNotFound?replacement.location:(current.location!=NSNotFound?current.location:0);
  }
  NSString* immutable=[text copy];[_marked release];_marked=immutable;
  _markedRange=NSMakeRange(base,text.length);_selection=NSMakeRange(base+selected.location,selected.length);
}
- (void)insertText:(id)value replacementRange:(NSRange)replacement {
  NSString* text=plainText(value);if (!text)return;
  if (!text.length) {if([self hasMarkedText])[self send:@"cancel" text:nil selected:NSMakeRange(0,0) replacement:NSMakeRange(NSNotFound,0)];}
  else [self send:@"commit" text:text selected:NSMakeRange(0,0) replacement:replacement];
  [self discardComposition];
}
- (void)insertText:(id)value {[self insertText:value replacementRange:NSMakeRange(NSNotFound,0)];}
- (void)unmarkText {
  if ([self hasMarkedText]) [self send:@"finish" text:nil selected:NSMakeRange(0,0) replacement:NSMakeRange(NSNotFound,0)];
  [self discardComposition];
}
- (void)doCommandBySelector:(SEL)selector {
  if (_discarding || !_owner || ![_owner canAcceptEngineTextInput]) return;
  if (selector==@selector(cancelOperation:) && [self hasMarkedText]) {[self cancelAndDeactivate];return;}
  if ([self hasMarkedText]) [self unmarkText];
  [_owner engineEditingCommand:selector];
}
- (NSAttributedString*)attributedSubstringForProposedRange:(NSRange)range actualRange:(NSRangePointer)actual {
  // Do not request surrounding field contents from the renderer for an IME.
  if (actual)*actual=NSMakeRange(NSNotFound,0);return nil;
}
- (NSUInteger)characterIndexForPoint:(NSPoint)point {return NSNotFound;}
- (NSRect)firstRectForCharacterRange:(NSRange)range actualRange:(NSRangePointer)actual {
  if (actual)*actual=range;
  if (!_owner || ![_owner canAcceptEngineTextInput] || ![self hasClient]) return NSZeroRect;
  NSArray* rect=_state[@"caret"];
  return [_owner engineTextInputScreenRect:NSMakeRect([rect[0] doubleValue],[rect[1] doubleValue],[rect[2] doubleValue],[rect[3] doubleValue])];
}
@end
