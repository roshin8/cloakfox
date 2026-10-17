// Native IPC boundary tests. No CEF, browser profile, page or global surface ID.
#include "surface_transport_mac.h"
#include "surface_launch_mac.h"
#include <IOSurface/IOSurface.h>
#include <mach/mach.h>
#include <sys/wait.h>
#include <spawn.h>
extern char** environ;
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <unistd.h>

using namespace cloakfox;
namespace {
IOSurfaceRef makeSurface(uint32_t width, uint32_t height) {
  const int64_t w=width,h=height,row=width*4,element=4,format=0x42475241;
  CFNumberRef values[5];
  const int64_t numbers[]={w,h,row,element,format};
  const void* keys[]={kIOSurfaceWidth,kIOSurfaceHeight,kIOSurfaceBytesPerRow,
                     kIOSurfaceBytesPerElement,kIOSurfacePixelFormat};
  for(int i=0;i<5;++i) values[i]=CFNumberCreate(nullptr,kCFNumberSInt64Type,&numbers[i]);
  auto properties=CFDictionaryCreate(nullptr,keys,(const void**)values,5,
      &kCFTypeDictionaryKeyCallBacks,&kCFTypeDictionaryValueCallBacks);
  auto surface=IOSurfaceCreate(properties);
  CFRelease(properties);for(auto value:values)CFRelease(value);
  assert(surface);
  assert(IOSurfaceLock(surface,0,nullptr)==KERN_SUCCESS);
  auto pixels=static_cast<uint8_t*>(IOSurfaceGetBaseAddress(surface));
  for(uint32_t y=0;y<height;++y)for(uint32_t x=0;x<width;++x) {
    auto p=pixels+y*IOSurfaceGetBytesPerRow(surface)+x*4;
    p[0]=91;p[1]=37;p[2]=13;p[3]=255;
  }
  assert(IOSurfaceUnlock(surface,0,nullptr)==KERN_SUCCESS);
  return surface;
}
// Construct adversarial wire packets independently of the sender helper.
// The kernel still transfers real rights; receiver validation is not mocked.
struct RawFrame {
  mach_msg_header_t header{};
  mach_msg_body_t body{};
  mach_msg_port_descriptor_t surface{};
  uint32_t version=1,reserved=0;
  SurfaceRoute route;
  uint64_t sequence=99;
  std::array<uint8_t,256> oversized{};
};
void malformed(mach_port_t destination,IOSurfaceRef surface,const SurfaceRoute& route,int variant) {
  RawFrame packet{};packet.route=route;
  const auto port=IOSurfaceCreateMachPort(surface);assert(MACH_PORT_VALID(port));
  packet.header.msgh_bits=MACH_MSGH_BITS(MACH_MSG_TYPE_COPY_SEND,0)|MACH_MSGH_BITS_COMPLEX;
  packet.header.msgh_id=0x43465331;
  packet.header.msgh_remote_port=destination;
  packet.header.msgh_size=offsetof(RawFrame,oversized);
  packet.body.msgh_descriptor_count=1;
  packet.surface.name=port;
  packet.surface.type=MACH_MSG_PORT_DESCRIPTOR;
  packet.surface.disposition=MACH_MSG_TYPE_COPY_SEND;
  switch(variant) {
    case 0:packet.header.msgh_id++;break;
    case 1:packet.version++;break;
    case 2:packet.reserved=1;break;
    case 3:packet.body.msgh_descriptor_count=0;break;
    case 4:packet.header.msgh_bits &= ~MACH_MSGH_BITS_COMPLEX;break;
    case 5:packet.header.msgh_size+=4;break;
    case 6:packet.header.msgh_size=sizeof(packet);break;
    case 7:packet.surface.name=mach_task_self();break;
    default:assert(false);
  }
  assert(mach_msg(&packet.header,MACH_SEND_MSG|MACH_SEND_TIMEOUT,packet.header.msgh_size,
      0,MACH_PORT_NULL,0,MACH_PORT_NULL)==MACH_MSG_SUCCESS);
  mach_port_deallocate(mach_task_self(),port);
}
}
int main(int argc,char** argv) {
  const SurfaceRoute initialRoute{{1,2,3,4},7,1,16,8};
  if(argc==3 && (std::strcmp(argv[1],"--child")==0 || std::strcmp(argv[1],"--denied-child")==0)) {
    const bool denied=std::strcmp(argv[1],"--denied-child")==0;
    const auto destination=connectSurfaceHost(argv[2],denied?500:5000);
    if(denied) {
      if(MACH_PORT_VALID(destination)){mach_port_deallocate(mach_task_self(),destination);return 7;}
      return 0;
    }
    if(!MACH_PORT_VALID(destination)){fprintf(stderr,"Child host handshake failed\n");return 2;}
    auto childSurface=makeSurface(16,8);
    const bool sent=sendSurface(destination,initialRoute,1,childSurface);
    CFRelease(childSurface);mach_port_deallocate(mach_task_self(),destination);
    return sent?0:6;
  }
  alarm(20); // A broken peer must fail this test, never hang the suite.
  // Kernel audit tokens, never a claimed PID in the wire envelope, identify
  // the helper. Bootstrap/launch authentication belongs to the host layer.
  audit_token_t expected{};
  mach_msg_type_number_t count=TASK_AUDIT_TOKEN_COUNT;
  assert(task_info(mach_task_self(),TASK_AUDIT_TOKEN,reinterpret_cast<task_info_t>(&expected),&count)==KERN_SUCCESS);
  SurfaceReceiver receiver(expected);
  SurfaceRoute route{{1,2,3,4},7,1,16,8};
  assert(receiver.attach(route));
  assert(!receiver.attach(route));
  auto surface=makeSurface(16,8);
  assert(sendSurface(receiver.port(),route,1,surface));
  auto frame=receiver.receive(100);
  assert(frame && frame->route.token==route.token && frame->sequence==1);
  assert(frame->bgra.size()==16*8*4 && frame->bgra[0]==91 && frame->bgra.back()==255);
  // The owned snapshot must survive mutations to the sender's surface.
  assert(IOSurfaceLock(surface,0,nullptr)==KERN_SUCCESS);
  static_cast<uint8_t*>(IOSurfaceGetBaseAddress(surface))[0]=0;
  assert(IOSurfaceUnlock(surface,0,nullptr)==KERN_SUCCESS);
  assert(frame->bgra[0]==91);
  for(int variant=0;variant<8;++variant) {
    malformed(receiver.port(),surface,route,variant);
    assert(!receiver.receive(100));
  }
  // Invalid packets, including one larger than the receive buffer, must not
  // wedge the channel or consume the valid sequence number.
  assert(sendSurface(receiver.port(),route,2,surface));
  assert(receiver.receive(100)->sequence==2);
  assert(sendSurface(receiver.port(),route,2,surface));
  assert(!receiver.receive(100)); // replayed sequence
  auto wrong=route;wrong.configRevision=8;
  assert(sendSurface(receiver.port(),wrong,3,surface));
  assert(!receiver.receive(100));
  wrong=route;wrong.token[0]=9;
  assert(sendSurface(receiver.port(),wrong,3,surface));
  assert(!receiver.receive(100));
  wrong=route;wrong.width=15;
  assert(sendSurface(receiver.port(),wrong,3,surface));
  assert(!receiver.receive(100));
  auto unknown=expected;unknown.val[5]++;
  SurfaceReceiver unknownSender(unknown);
  assert(unknownSender.attach(route));
  assert(sendSurface(unknownSender.port(),route,2,surface));
  assert(!unknownSender.receive(100));
  auto small=makeSurface(8,8);
  assert(sendSurface(receiver.port(),route,3,small));
  assert(!receiver.receive(100)); // actual IOSurface disagrees with envelope
  CFRelease(small);
  assert(sendSurface(receiver.port(),route,3,surface));
  assert(receiver.receive(100)->sequence==3); // failed ownership/size checks consumed no sequence
  assert(!receiver.resize(route.token,7,1,32,8)); // stale viewport epoch
  assert(receiver.resize(route.token,7,2,32,8));
  assert(sendSurface(receiver.port(),route,4,surface));
  assert(!receiver.receive(100)); // previous size/epoch after resize
  assert(!receiver.resize(route.token,7,3,4097,8));
  assert(!receiver.resize(route.token,8,3,32,8)); // different config
  auto resized=makeSurface(32,8);auto newRoute=route;
  newRoute.width=32;newRoute.viewportRevision=2;
  assert(sendSurface(receiver.port(),newRoute,4,resized));
  assert(receiver.receive(100)->route==newRoute);
  CFRelease(resized);
  receiver.detach(route.token);
  assert(!receiver.attach(route)); // retired slot cannot be recycled
  assert(sendSurface(receiver.port(),newRoute,5,surface));
  assert(!receiver.receive(100));
  assert(!receiver.receive(1)); // bounded wait, no frame
  CFRelease(surface);
  // Destroying the receiver revokes queued and future sends. A valid local
  // send right can remain, but it must become a dead destination.
  mach_port_t dead;
  {
    SurfaceReceiver dying(expected);dead=dying.port();
    assert(mach_port_mod_refs(mach_task_self(),dead,MACH_PORT_RIGHT_SEND,1)==KERN_SUCCESS);
  }
  auto finalSurface=makeSurface(16,8);
  assert(!sendSurface(dead,route,1,finalSurface));
  mach_port_deallocate(mach_task_self(),dead);
  CFRelease(finalSurface);

  // A fresh native process uses a random, per-launch Mach rendezvous.
  // Only its kernel-audited launch PID may obtain the frame send capability.
  SurfaceLaunch launch;
  char* childArgs[]={argv[0],const_cast<char*>("--child"),const_cast<char*>(launch.name().c_str()),nullptr};
  pid_t child;assert(posix_spawn(&child,argv[0],nullptr,nullptr,childArgs,environ)==0);
  auto hello=launch.accept(child,5000);assert(hello);
  assert(!launch.accept(child,1));
  assert(hello->audit().val[5]==static_cast<unsigned>(child));
  assert(std::memcmp(&hello->audit(),&expected,sizeof(expected))!=0);
  {
    SurfaceReceiver peer(hello->audit());assert(peer.attach(route));
    auto parentSurface=makeSurface(16,8);
    assert(sendSurface(peer.port(),route,1,parentSurface));
    assert(!peer.receive(100)); // genuine wrong process, valid route and real surface
    CFRelease(parentSurface);
    assert(hello->reply(peer.port()));
    assert(!hello->reply(peer.port())); // launch reply is a one-shot right
    const auto childFrame=peer.receive(5000);
    int status;assert(waitpid(child,&status,0)==child);
    if(!childFrame)fprintf(stderr,"Child raw exit status: %d\n",status);
    assert(childFrame && childFrame->bgra[0]==91);
    assert(WIFEXITED(status) && WEXITSTATUS(status)==0);
  }
  SurfaceLaunch rejected;
  char* deniedArgs[]={argv[0],const_cast<char*>("--denied-child"),const_cast<char*>(rejected.name().c_str()),nullptr};
  pid_t deniedChild;assert(posix_spawn(&deniedChild,argv[0],nullptr,nullptr,deniedArgs,environ)==0);
  // A valid hello from a different child cannot acquire any frame capability.
  assert(!rejected.accept(getpid(),5000));
  int deniedStatus;assert(waitpid(deniedChild,&deniedStatus,0)==deniedChild);
  assert(WIFEXITED(deniedStatus) && WEXITSTATUS(deniedStatus)==0);

}
