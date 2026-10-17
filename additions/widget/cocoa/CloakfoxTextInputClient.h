/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
#import <Cocoa/Cocoa.h>
@protocol CloakfoxTextInputOwner <NSObject>
- (BOOL)canAcceptEngineTextInput;
// Only a route-bound cancellation may be accepted after focus is lost.
- (BOOL)sendEngineTextInput:(NSDictionary*)command;
- (NSRect)engineTextInputScreenRect:(NSRect)rect;
- (void)engineEditingCommand:(SEL)selector;
@end
@interface CloakfoxTextInputClient : NSObject <NSTextInputClient> {
  id<CloakfoxTextInputOwner> _owner; // Explicitly detached before its view dies.
  NSDictionary* _state;
  NSTextInputContext* _context;
  NSString* _marked;
  NSRange _markedRange, _selection;
  BOOL _discarding, _secureInput, _invalidated, _refreshRequested;
  NSMutableArray* _pendingKeys;
  NSUInteger _queuedKeys, _retiredKeys, _foreignFieldKeys, _expiredKeys, _unhandledKeys;
}
- (id)initWithOwner:(id<CloakfoxTextInputOwner>)owner;
- (BOOL)setEditingState:(NSDictionary*)state;
- (BOOL)hasClient;
- (void)invalidateEditingState;
- (BOOL)needsEditingState;
- (BOOL)beginRefreshIfNeeded;
- (NSTextInputContext*)inputContext;
- (BOOL)handleKeyEvent:(NSEvent*)event;
- (BOOL)canRouteUncomposedKey:(NSEvent*)event;
// Privileged development-host counters; never include key text or field IDs.
- (NSDictionary*)routingDiagnostics;
- (void)discardComposition;
- (void)cancelAndDeactivate;
- (void)refreshActivity;
- (void)detach;
@end
