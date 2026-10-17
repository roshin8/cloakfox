// Owned-fixture native host acceptance: actual CEF paint -> authenticated Mach
// snapshot -> immutable parent pixels. No page-facing handles or network control.
#include "surface_launch_mac.h"
#include "surface_transport_mac.h"
#include "json.hpp"
#include <spawn.h>
#include <algorithm>
#include <poll.h>
#include <sys/wait.h>
#include <unistd.h>
#include <cassert>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <chrono>
#include <thread>
extern char** environ;
using nlohmann::json;
namespace {
std::string line(int fd,int timeoutMs=10000) {
  std::string result;
  while(result.size()<1024*1024) {
    pollfd check{fd,POLLIN,0};
    if(poll(&check,1,timeoutMs)!=1)throw std::runtime_error("Native child response timed out");
    char c;if(read(fd,&c,1)!=1)throw std::runtime_error("Native child closed response pipe");
    if(c=='\n')return result;result+=c;
  }
  throw std::runtime_error("Oversized native child response");
}
json request(int input,int output,int id,const json& data) {
  auto wire=data;wire["version"]=1;wire["id"]=id;
  const auto text=wire.dump()+"\n";
  size_t sent=0;while(sent<text.size()) {
    const auto size=write(input,text.data()+sent,text.size()-sent);
    if(size<=0)throw std::runtime_error("Native child request pipe failed");sent+=size;
  }
  for(int count=0;count<100;++count) {
    const auto response=json::parse(line(output));
    if(response.value("event","")=="crashed")throw std::runtime_error("Native renderer crashed");
    if(response.value("id",0)==id)return response;
  }
  throw std::runtime_error("Native child did not acknowledge request");
}
void okay(const json& result) {
  if(!result.value("ok",false))throw std::runtime_error(result.value("error","Rejected native request"));
}
}
int main(int argc,char** argv) {
  if(argc!=5 && !(argc==6 && std::string(argv[5])=="--popup"))return 2;
  const bool testPopup=argc==6;
  // Only an owned loopback fixture is accepted by this development probe.
  const std::string url=argv[4];
  if(url.rfind("http://127.0.0.1:",0)!=0)return 2;
  pid_t child=-1;int input[2]{-1,-1},output[2]{-1,-1};
  try {
    alarm(60);
    std::ifstream file(argv[3]);const auto config=json::parse(file);
    assert(pipe(input)==0 && pipe(output)==0);
    cloakfox::SurfaceLaunch launch;
    posix_spawn_file_actions_t actions;assert(posix_spawn_file_actions_init(&actions)==0);
    assert(posix_spawn_file_actions_adddup2(&actions,input[0],STDIN_FILENO)==0);
    assert(posix_spawn_file_actions_adddup2(&actions,output[1],STDOUT_FILENO)==0);
    for(int fd:{input[0],input[1],output[0],output[1]})assert(posix_spawn_file_actions_addclose(&actions,fd)==0);
    const std::string profile="--profile-root="+std::string(argv[2]);
    const std::string rendezvous="--host-rendezvous="+launch.name();
    std::vector<std::string> args{argv[1],profile,"--enable-probe","--test-keychain","--windowless","--shared-texture",rendezvous};
    std::vector<char*> native;for(auto& arg:args)native.push_back(arg.data());native.push_back(nullptr);
    assert(posix_spawn(&child,argv[1],&actions,nullptr,native.data(),environ)==0);
    posix_spawn_file_actions_destroy(&actions);close(input[0]);input[0]=-1;close(output[1]);output[1]=-1;
    auto hello=launch.accept(child,5000);
    if(!hello)throw std::runtime_error("Native CEF host handshake failed");
    cloakfox::SurfaceReceiver receiver(hello->audit());
    cloakfox::SurfaceRoute route{{1,2,3,4},config.at("revision").get<uint64_t>(),1,640,480};
    assert(receiver.attach(route));
    mach_port_limits_t limits{1};
    assert(mach_port_set_attributes(mach_task_self(),receiver.port(),MACH_PORT_LIMITS_INFO,reinterpret_cast<mach_port_info_t>(&limits),MACH_PORT_LIMITS_INFO_COUNT)==KERN_SUCCESS);
    assert(hello->reply(receiver.port()));
    const auto ready=json::parse(line(output[0],30000));
    assert(ready.at("windowless").get<bool>());
    okay(request(input[1],output[0],1,{{"command","applyConfig"},{"config",config},{"fixtureURL",url}}));
    const auto opened=request(input[1],output[0],2,{{"command","open"},{"container",config.at("containerId")},{"private",false},{"url",url},{"configRevision",route.configRevision}});
    okay(opened);const int browser=opened.at("browser");
    const std::string token="01020304000000000000000000000000";
    okay(request(input[1],output[0],3,{{"command","surface"},{"browser",browser},{"configRevision",route.configRevision},
        {"viewportRevision",route.viewportRevision},{"token",token},{"width",640},{"height",480}}));
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(10);
    std::optional<cloakfox::SurfaceSnapshot> frame;
    while(std::chrono::steady_clock::now()<deadline) {
      auto candidate=receiver.receive(100);
      if(candidate && candidate->bgra.size()>=4) {
        const auto end=candidate->bgra.end();
        if(std::vector<uint8_t>(end-4,end)==std::vector<uint8_t>{91,37,13,255}) {frame=std::move(candidate);break;}
      }
    }
    if(!frame)throw std::runtime_error("Owned CEF fixture pixels did not reach native host");
    const auto metadata=request(input[1],output[0],4,{{"command","frame"},{"browser",browser}});okay(metadata);
    assert(!metadata.at("topLevelWindow").get<bool>());
    assert(metadata.at("paintSource")=="iosurface");
    // Binding a native surface adds a viewport token/epoch to the input gate.
    const auto stale=request(input[1],output[0],5,{{"command","input"},{"browser",browser},{"configRevision",route.configRevision},
        {"viewportRevision",2},{"token",token},{"kind","char"},{"character",88}});
    assert(!stale.at("ok").get<bool>());
    for(int i=0;i<2;++i)okay(request(input[1],output[0],6+i,{{"command","input"},{"browser",browser},{"configRevision",route.configRevision},
        {"viewportRevision",1},{"token",token},{"kind",i==0?"mouseDown":"mouseUp"},{"x",8},{"y",8}}));
    okay(request(input[1],output[0],8,{{"command","input"},{"browser",browser},{"configRevision",route.configRevision},
        {"viewportRevision",1},{"token",token},{"kind","char"},{"character",65}}));
    const auto field=request(input[1],output[0],9,{{"command","cdp"},{"browser",browser},{"method","Runtime.evaluate"},
        {"params",{{"expression","(async()=>{const field=document.getElementById('field');for(let i=0;i<150&&field.value!=='A';i++)await new Promise(r=>setTimeout(r,20));return field.value})()"},{"awaitPromise",true},{"returnByValue",true}}}});
    okay(field);assert(field.at("result").at("result").at("value")=="A");
    const auto fixtureChecks=request(input[1],output[0],10,{{"command","cdp"},{"browser",browser},{"method","Runtime.evaluate"},
        {"params",{{"expression","window.fixtureCompletion || Promise.resolve(true)"},{"awaitPromise",true},{"returnByValue",true}}}});
    okay(fixtureChecks);assert(fixtureChecks.at("result").at("result").at("value")==true);
    // The receiver deliberately stops draining during >queue-limit paints.
    // The last static frame must arrive after draining resumes, without another
    // page mutation or paint request from the test.
    const auto burst=request(input[1],output[0],11,{{"command","cdp"},{"browser",browser},{"method","Runtime.evaluate"},
        {"params",{{"expression","(async()=>{document.activeElement.blur();for(let i=0;i<30;i++){document.body.style.background=`rgb(${i+40},37,91)`;await new Promise(requestAnimationFrame)}document.body.style.background='rgb(17,93,61)';await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame);return true})()"},{"awaitPromise",true},{"returnByValue",true}}}});
    okay(burst);
    bool publishedFinal=false;
    for(int i=0;i<100;++i){
      const auto state=request(input[1],output[0],12+i,{{"command","frame"},{"browser",browser}});okay(state);
      if(state.at("cornerBGRA")==json({61,93,17,255})){publishedFinal=true;break;}
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    assert(publishedFinal);
    bool recovered=false;
    const auto pressureDeadline=std::chrono::steady_clock::now()+std::chrono::seconds(5);
    while(std::chrono::steady_clock::now()<pressureDeadline){
      const auto snapshot=receiver.receive(100);
      if(snapshot && std::vector<uint8_t>(snapshot->bgra.end()-4,snapshot->bgra.end())==std::vector<uint8_t>{61,93,17,255}){recovered=true;break;}
    }
    if(!recovered)throw std::runtime_error("Final static frame lost after native queue saturation");
    if(testPopup) {
      okay(request(input[1],output[0],200,{{"command","cdp"},{"browser",browser},{"method","Runtime.evaluate"},
          {"params",{{"expression","const pick=document.createElement('select');pick.style='position:absolute;left:40px;top:40px;width:200px';pick.innerHTML='<option>First</option><option>Second</option><option>Third</option>';document.body.append(pick);true"},{"returnByValue",true}}}}));
      for(int i=0;i<2;++i)okay(request(input[1],output[0],201+i,{{"command","input"},{"browser",browser},{"configRevision",route.configRevision},
          {"viewportRevision",1},{"token",token},{"kind",i==0?"mouseDown":"mouseUp"},{"x",80},{"y",50}}));
      json popup;
      for(int i=0;i<100;++i) {
        popup=request(input[1],output[0],203+i,{{"command","frame"},{"browser",browser}});okay(popup);
        if(popup.value("popupPainted",false))break;
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
      }
      if(!popup.value("popupPainted",false))throw std::runtime_error("Native popup did not paint");
      const auto rect=popup.at("popupRect");
      const int x=rect.at(0).get<int>()+rect.at(2).get<int>()/2;
      const int y=rect.at(1).get<int>()+rect.at(3).get<int>()-4;
      if(x<0||y<0||x>=int(route.width)||y>=int(route.height))throw std::runtime_error("Fixture popup is outside viewport");
      const size_t offset=(size_t(y)*route.width+x)*4;
      const std::array<uint8_t,4> background{61,93,17,255};
      uint64_t popupSequence=0;
      const auto popupDeadline=std::chrono::steady_clock::now()+std::chrono::seconds(5);
      while(std::chrono::steady_clock::now()<popupDeadline) {
        const auto snapshot=receiver.receive(100);
        if(snapshot && !std::equal(background.begin(),background.end(),snapshot->bgra.begin()+offset)) {
          popupSequence=snapshot->sequence;break;
        }
      }
      if(!popupSequence)throw std::runtime_error("Popup metadata has no matching native pixels");
      okay(request(input[1],output[0],400,{{"command","input"},{"browser",browser},{"configRevision",route.configRevision},
          {"viewportRevision",1},{"token",token},{"kind","editKey"},{"keyCode",27},{"shift",false}}));
      bool removed=false;
      const auto removedDeadline=std::chrono::steady_clock::now()+std::chrono::seconds(5);
      while(std::chrono::steady_clock::now()<removedDeadline) {
        const auto snapshot=receiver.receive(100);
        if(snapshot && snapshot->sequence>popupSequence && std::equal(background.begin(),background.end(),snapshot->bgra.begin()+offset)) {
          removed=true;break;
        }
      }
      if(!removed)throw std::runtime_error("Retired popup pixels remain on native surface");
    }
    okay(request(input[1],output[0],1000,{{"command","quit"}}));
    int status;assert(waitpid(child,&status,0)==child);child=-1;assert(WIFEXITED(status)&&WEXITSTATUS(status)==0);
    std::cout<<json({{"status","passed"},{"width",frame->route.width},{"height",frame->route.height},
        {"configRevision",frame->route.configRevision},{"sequence",frame->sequence},{"cornerBGRA",{91,37,13,255}},
        {"topLevelWindow",false},{"paintSource","iosurface"},{"inputOwnerVerified",true},{"queuePressureRecovered",true},{"popupPixelsVerified",testPopup}}).dump()<<"\n";
  } catch(const std::exception& e) {
    std::cerr<<e.what()<<"\n";
    if(child>0){kill(child,SIGKILL);int status;waitpid(child,&status,0);}
    return 1;
  }
  for(int fd:{input[0],input[1],output[0],output[1]})if(fd>=0)close(fd);
}
