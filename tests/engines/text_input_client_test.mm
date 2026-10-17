#import <Cocoa/Cocoa.h>
#import "CloakfoxTextInputClient.h"
#include <cassert>

@interface InputOwner : NSObject <CloakfoxTextInputOwner> {
 @public BOOL active;
 @public NSMutableArray* commands;
}
@end
@implementation InputOwner
- (id)init {if ((self=[super init])) {active=YES;commands=[[NSMutableArray alloc] init];}return self;}
- (void)dealloc {[commands release];[super dealloc];}
- (BOOL)canAcceptEngineTextInput {return active;}
- (BOOL)sendEngineTextInput:(NSDictionary*)command {if(!active)return NO;[commands addObject:command];return YES;}
- (NSRect)engineTextInputScreenRect:(NSRect)rect {return NSOffsetRect(rect,100,200);}
- (void)engineEditingCommand:(SEL)selector {}
@end
@interface ReentrantContext : NSObject {
 @public CloakfoxTextInputClient* client;
 @public NSUInteger calls;
}
@end
@implementation ReentrantContext
- (void)discardMarkedText {if (++calls<=2) [client unmarkText];}
- (void)deactivate {}
@end
int main() {
 @autoreleasepool {
  InputOwner* owner=[[InputOwner alloc] init];
  CloakfoxTextInputClient* client=[[CloakfoxTextInputClient alloc] initWithOwner:owner];
  NSDictionary* field=@{@"document":@"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",@"node":@7};
  NSDictionary* state=@{@"field":field,@"editable":@YES,@"password":@NO,@"selection":@[@3,@3],@"composition":[NSNull null],@"caret":@[@8,@12,@0,@18]};
  assert([client setEditingState:state]);
  NSMutableDictionary* malformed=[[state mutableCopy] autorelease];malformed[@"field"]=[NSNull null];
  assert(![client setEditingState:malformed]);
  [client setMarkedText:@"に" selectedRange:NSMakeRange(1,0) replacementRange:NSMakeRange(NSNotFound,0)];
  assert([client hasMarkedText]);assert([client markedRange].location==3);
  assert([owner->commands.lastObject[@"action"] isEqual:@"set"]);
  assert([owner->commands.lastObject[@"field"] isEqual:field]);
  [client insertText:@"日本語 😀" replacementRange:NSMakeRange(NSNotFound,0)];
  assert(![client hasMarkedText]);
  assert([owner->commands.lastObject[@"action"] isEqual:@"commit"]);
  assert([owner->commands.lastObject[@"text"] isEqual:@"日本語 😀"]);
  [client setMarkedText:@"é" selectedRange:NSMakeRange(1,0) replacementRange:NSMakeRange(NSNotFound,0)];
  [client unmarkText];assert(![client hasMarkedText]);assert([owner->commands.lastObject[@"action"] isEqual:@"finish"]);
  NSMutableDictionary* changed=[[state mutableCopy] autorelease];changed[@"field"]=@{@"document":field[@"document"],@"node":@8};
  [client setMarkedText:@"x" selectedRange:NSMakeRange(1,0) replacementRange:NSMakeRange(NSNotFound,0)];
  const auto count=owner->commands.count;assert([client setEditingState:changed]);assert(![client hasMarkedText]);assert(owner->commands.count==count);
  changed[@"value"]=@"private";assert(![client setEditingState:changed]);[changed removeObjectForKey:@"value"];
  changed[@"caret"]=@[@0,@0,@4097,@20];assert(![client setEditingState:changed]);
  assert([client setEditingState:state]);
  NSRange actual;NSRect caret=[client firstRectForCharacterRange:NSMakeRange(3,0) actualRange:&actual];
  assert(caret.origin.x==108 && caret.origin.y==212 && caret.size.height==18);
  assert([client attributedSubstringForProposedRange:NSMakeRange(0,10) actualRange:&actual]==nil);
  [client setMarkedText:@"first" selectedRange:NSMakeRange(5,0) replacementRange:NSMakeRange(10,0)];
  [client setMarkedText:@"four" selectedRange:NSMakeRange(4,0) replacementRange:NSMakeRange(20,2)];
  assert([client markedRange].location==20 && [client selectedRange].location==24);
  [client discardComposition];
  assert([client respondsToSelector:@selector(invalidateEditingState)]);
  [client invalidateEditingState];
  assert([client inputContext]==nil);
  const auto beforeInvalid=owner->commands.count;
  [client setMarkedText:@"BLOCKED" selectedRange:NSMakeRange(0,0) replacementRange:NSMakeRange(NSNotFound,0)];
  assert(owner->commands.count==beforeInvalid);
  assert([client setEditingState:state]);
  NSEvent* pendingKey=[NSEvent keyEventWithType:NSEventTypeKeyDown location:NSZeroPoint modifierFlags:0
      timestamp:[NSProcessInfo processInfo].systemUptime windowNumber:0 context:nil characters:@"x" charactersIgnoringModifiers:@"x" isARepeat:NO keyCode:7];
  [client invalidateEditingState];
  const auto beforeQueue=owner->commands.count;
  assert([client handleKeyEvent:pendingKey]);assert(owner->commands.count==beforeQueue);
  NSMutableDictionary* password=[[state mutableCopy] autorelease];password[@"password"]=@YES;
  assert([client setEditingState:password]);assert([client inputContext]==nil);
  assert(owner->commands.count==beforeQueue+1);
  assert([owner->commands.lastObject[@"action"] isEqual:@"commit"]);
  assert([owner->commands.lastObject[@"text"] isEqual:@"x"]);
  [client invalidateEditingState];assert([client handleKeyEvent:pendingKey]);
  password[@"field"]=@{@"document":field[@"document"],@"node":@9};
  const auto beforeOtherField=owner->commands.count;
  assert([client setEditingState:password]);assert(owner->commands.count==beforeOtherField);
  NSDictionary* diagnostics=[client routingDiagnostics];
  assert([diagnostics[@"queued"] unsignedIntegerValue]==2);
  assert([diagnostics[@"foreignField"] unsignedIntegerValue]==1);
  assert(diagnostics.count==5); // Counters only; no keys, field IDs or text.
  NSDictionary* noField=@{@"field":[NSNull null],@"editable":@NO,@"password":@NO,
      @"selection":[NSNull null],@"composition":[NSNull null],@"caret":[NSNull null]};
  assert([client setEditingState:noField]);[client invalidateEditingState];
  assert([client canRouteUncomposedKey:pendingKey]);
  assert([client inputContext]==nil);
  NSEvent* optionKey=[NSEvent keyEventWithType:NSEventTypeKeyDown location:NSZeroPoint modifierFlags:NSEventModifierFlagOption
      timestamp:[NSProcessInfo processInfo].systemUptime windowNumber:0 context:nil characters:@"x" charactersIgnoringModifiers:@"x" isARepeat:NO keyCode:7];
  assert(![client canRouteUncomposedKey:optionKey]);
  NSEvent* unicodeKey=[NSEvent keyEventWithType:NSEventTypeKeyDown location:NSZeroPoint modifierFlags:0
      timestamp:[NSProcessInfo processInfo].systemUptime windowNumber:0 context:nil characters:@"é" charactersIgnoringModifiers:@"e" isARepeat:NO keyCode:14];
  assert(![client canRouteUncomposedKey:unicodeKey]);
  owner->active=NO;assert(![client canRouteUncomposedKey:pendingKey]);owner->active=YES;
  assert([client setEditingState:state]);[client invalidateEditingState];
  assert(![client canRouteUncomposedKey:pendingKey]);
  assert([client setEditingState:state]);
  const auto beforeInactive=owner->commands.count;
  owner->active=NO;
  [client insertText:@"WRONG" replacementRange:NSMakeRange(NSNotFound,0)];assert(owner->commands.count==beforeInactive);
  assert([client inputContext]==nil);
  owner->active=YES;
  assert([client setEditingState:state]);
  NSMutableString* changing=[NSMutableString stringWithString:@"old"];
  [client setMarkedText:changing selectedRange:NSMakeRange(3,0) replacementRange:NSMakeRange(NSNotFound,0)];
  [changing appendString:@" mutation"];
  assert([client markedRange].length==3);
  assert([owner->commands.lastObject[@"text"] isEqual:@"old"]);
  ReentrantContext* context=[[ReentrantContext alloc] init];context->client=client;
  [client setValue:context forKey:@"context"];
  [client discardComposition];assert(context->calls==1);
  [client detach];[context release];[owner release];[client release];
 }
}
