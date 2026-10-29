"""Compile the actual viewport-boundary and fractional composition helpers."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]


def compile_run(code):
    with tempfile.TemporaryDirectory(prefix='canonical-scroll-coordinates-') as temp:
        source = Path(temp)/'check.cpp';binary=Path(temp)/'check'
        source.write_text(code)
        subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror',str(source),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)


class CanonicalScrollbarCoordinates(unittest.TestCase):
    def test_actual_zoom_boundary(self):
        source=(ROOT/'firefox-src/layout/base/ViewportUtils.cpp').read_text()
        start=source.index('const nsIFrame* ViewportUtils::IsZoomedContentRoot(')
        end=source.index('\n}\n',start)+3
        code=r'''
#include <cassert>
namespace mozilla {enum class StylePositionProperty{Static,Fixed};}
using namespace mozilla;
enum class LayoutFrameType{Canvas,PageSequence,Viewport,Scrollbar,Generic};
struct Context{bool canonical=true,root=true;bool CloakfoxCanonicalLayout()const{return canonical;}bool IsRootContentDocumentCrossProcess()const{return root;}};
struct Style{StylePositionProperty mPosition=StylePositionProperty::Static;};
struct nsIFrame{virtual~nsIFrame()=default;nsIFrame*parent=nullptr;Context*pc=nullptr;LayoutFrameType type=LayoutFrameType::Generic;Style style;
 nsIFrame*GetParent()const{return parent;}Context*PresContext()const{return pc;}LayoutFrameType Type()const{return type;}const Style*StyleDisplay()const{return &style;}};
struct ScrollContainerFrame:nsIFrame{bool root=true;bool IsRootScrollFrameOfDocument()const{return root;}};
struct Shell{ScrollContainerFrame*root;ScrollContainerFrame*GetRootScrollContainerFrame(){return root;}};
struct ViewportFrame:nsIFrame{Shell*shell;Shell*PresShell(){return shell;}};
struct Query{nsIFrame*value;template<class T>operator T*()const{return dynamic_cast<T*>(value);}};
Query do_QueryFrame(nsIFrame*p){return {p};}
namespace ViewportUtils{const nsIFrame*IsZoomedContentRoot(const nsIFrame*);}
''' +source[start:end]+r'''
int main(){Context pc;ScrollContainerFrame root;root.pc=&pc;ViewportFrame viewport;viewport.pc=&pc;root.parent=&viewport;Shell shell{&root};viewport.shell=&shell;
 nsIFrame canvas;canvas.type=LayoutFrameType::Canvas;canvas.pc=&pc;canvas.parent=&root;
 nsIFrame bar;bar.type=LayoutFrameType::Scrollbar;bar.pc=&pc;bar.parent=&root;
 nsIFrame thumb;thumb.pc=&pc;thumb.parent=&bar;
 assert(ViewportUtils::IsZoomedContentRoot(&bar)==&root);
 assert(ViewportUtils::IsZoomedContentRoot(&canvas)==&root);
 int boundaries=0;for(auto*f=&thumb;f;f=f->GetParent())if(ViewportUtils::IsZoomedContentRoot(f))++boundaries;
 assert(boundaries==1); // Physical output conversion occurs once on the bar.
 pc.canonical=false;assert(!ViewportUtils::IsZoomedContentRoot(&bar));assert(ViewportUtils::IsZoomedContentRoot(&canvas)==&root);
 pc.canonical=true;pc.root=false;assert(!ViewportUtils::IsZoomedContentRoot(&bar));pc.root=true;
 root.root=false;assert(!ViewportUtils::IsZoomedContentRoot(&bar));root.root=true;
 nsIFrame fixed;fixed.pc=&pc;fixed.parent=&viewport;fixed.style.mPosition=StylePositionProperty::Fixed;
 assert(ViewportUtils::IsZoomedContentRoot(&fixed)==&root);
 assert(!ViewportUtils::IsZoomedContentRoot(nullptr));
}
'''
        compile_run(code)

    def test_actual_canonical_scrollbar_dispatch(self):
        source=(ROOT/'firefox-src/layout/generic/ScrollContainerFrame.cpp').read_text()
        start=source.index('  const bool canonicalRoot =',source.index('void ScrollContainerFrame::AppendScrollPartsTo('))
        end=source.index('\n  scrollParts.Sort(',start)
        target=source[start:end]
        start=source.index('    const bool createLayer =',end)
        end=source.index(';',start)+1
        layer=source[start:end]
        slider=(ROOT/'firefox-src/layout/xul/nsSliderFrame.cpp').read_text()
        start=slider.index('  if (auto* sf = GetScrollContainerFrame();',slider.index('void nsSliderFrame::StartAPZDrag('))
        opening=slider.index('{',start);depth=1;end=opening+1
        while depth:
            depth += (slider[end]=='{')-(slider[end]=='}');end+=1
        eligibility=slider[start:end]
        code=r"""
#include <cassert>
#include <cstdint>
namespace mozilla::layers{struct ScrollableLayerGuid{using ViewID=uint64_t;static constexpr ViewID NULL_SCROLL_ID=0;};}
struct Context{bool canonical=true,root=true;bool CloakfoxCanonicalLayout(){return canonical;}bool IsRootContentDocumentCrossProcess(){return root;}};
struct Content{};struct Child{Content value;Content*GetContent(){return &value;}};
namespace nsLayoutUtils{uint64_t FindOrCreateIDFor(Content*){return 7;}}
namespace StaticPrefs{bool layout_scrollbars_always_layerize_track(){return true;}}
struct Builder{bool BuildCompositorHitTestInfo(){return true;}};
struct Frame{bool mIsRoot=true;Context context;Child child;Child*mScrolledFrame=&child;uint64_t target=99;bool layer=true;
 Context*PresContext(){return &context;}bool IsScrollingActive(){return true;}bool IsRootScrollFrameOfDocument(){return mIsRoot;}
 void Dispatch(Builder*aBuilder,bool aCreateLayer,bool isOverlayScrollbar){
"""+target+layer+r"""
 target=scrollTargetId;layer=createLayer;
 }};
struct Slider{Frame*frame;bool mScrollingWithAPZ=false;int started=0,synchronous=0;
 Frame*GetScrollContainerFrame(){return frame;}Context*PresContext(){return frame->PresContext();}
 void StartAPZDrag(){
"""+eligibility+r"""
 ++started;mScrollingWithAPZ=true;
 }
 void SetupDrag(){mScrollingWithAPZ=false;StartAPZDrag();if(!mScrollingWithAPZ)++synchronous;}
};
int main(){Builder b;Frame frame;Slider slider{&frame};frame.Dispatch(&b,true,false);slider.SetupDrag();
 assert(frame.target==0&&!frame.layer&&slider.synchronous==1&&slider.started==0&&!slider.mScrollingWithAPZ);
 frame.context.canonical=false;frame.Dispatch(&b,true,false);slider.SetupDrag();assert(frame.target==7&&frame.layer&&slider.started==1&&slider.synchronous==1);
 frame.context.canonical=true;frame.mIsRoot=false;frame.Dispatch(&b,true,false);slider.SetupDrag();assert(frame.target==7&&frame.layer&&slider.started==2&&slider.synchronous==1);
 frame.mIsRoot=true;frame.context.root=false;frame.Dispatch(&b,true,false);slider.SetupDrag();assert(frame.target==7&&frame.layer&&slider.started==3&&slider.synchronous==1);
}
"""
        compile_run(code)

    def test_actual_output_scale_reflow_dispatch(self):
        source=(ROOT/'firefox-src/layout/base/nsPresContext.cpp').read_text()
        start=source.index('    if (mCloakfoxCanonicalOutput) {',source.index('void nsPresContext::UIResolutionChangedInternal()'))
        opening=source.index('{',start);depth=1;end=opening+1
        while depth:
            depth += (source[end]=='{')-(source[end]=='}');end+=1
        dispatch=source[start:end]
        code=r"""
#include "CloakfoxCanonicalGeometry.hpp"
#include <cassert>
struct LayoutDeviceIntSize{int width=2000,height=1125;};
struct nsSize{int width,height;bool operator!=(nsSize other)const{return width!=other.width||height!=other.height;}};
enum class ResolutionChangeOrigin{MainThreadAdjustment};enum class IntrinsicDirty{None};constexpr int NS_FRAME_IS_DIRTY=1;
struct Frame{};
struct Shell{float resolution=1.25f;int invalidations=0,reflows=0;nsSize target{0,0};Frame frame;
 float GetResolution(){return resolution;}void SetResolutionAndScaleTo(float v,ResolutionChangeOrigin){resolution=v;}
 void SetLayoutViewportSize(nsSize v,bool){target=v;}Frame*GetRootFrame(){return &frame;}
 void FrameNeedsReflow(Frame*,IntrinsicDirty,int){++reflows;}};
struct nsPresContext;namespace nsLayoutUtils{bool GetDocumentViewerSize(nsPresContext*,LayoutDeviceIntSize&);}
struct nsPresContext{bool mCloakfoxCanonicalOutput=true,available=true;Shell*mPresShell;CloakfoxCanonicalGeometry::Lifecycle*mCloakfoxGeometry;
 nsSize visible{2000,1125};float output=1.25f;
 struct Area{nsSize size;nsSize Size(){return size;}};
 Area GetVisibleArea(){return {visible};}float CloakfoxOutputResolution(){return output;}
 nsSize CloakfoxViewportSize(LayoutDeviceIntSize physical){return {int(physical.width/output),int(physical.height/output)};}
 void InvalidatePaintedLayers(){++mPresShell->invalidations;}
 void Apply(){
"""+dispatch+r"""
 }};
 bool nsLayoutUtils::GetDocumentViewerSize(nsPresContext*pc,LayoutDeviceIntSize&){return pc->available;}
 int main(){Shell shell;CloakfoxCanonicalGeometry::Lifecycle generation;generation.Capture(true);generation.Complete(true);
 nsPresContext pc;pc.mPresShell=&shell;pc.mCloakfoxGeometry=&generation;
 // APD remains fixed and even resolution is already new, but old visible
 // dimensions still reflect physical pixels: a reflow is nevertheless needed.
 pc.Apply();assert(shell.target.width==1600&&shell.target.height==900&&shell.reflows==1&&!generation.Ready()&&generation.Valid());
 generation.Complete(true);assert(generation.Ready());pc.visible={1600,900};pc.Apply();assert(shell.reflows==1&&generation.Ready());
 shell.resolution=1.0f;pc.Apply();assert(shell.resolution==1.25f&&shell.reflows==2&&!generation.Ready());
 generation.Complete(true);pc.mCloakfoxCanonicalOutput=false;pc.visible={2000,1125};pc.Apply();assert(shell.reflows==2&&generation.Ready());
 }
"""
        with tempfile.TemporaryDirectory(prefix='canonical-scale-dispatch-') as temp:
            cpp=Path(temp)/'check.cpp';binary=Path(temp)/'check';cpp.write_text(code)
            subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-I',str(ROOT/'additions/cloakcfg'),str(cpp),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)

    def test_actual_fractional_composition(self):
        source=(ROOT/'firefox-src/layout/base/MobileViewportManager.cpp').read_text()
        marker=' MobileViewportManager::GetCompositionSize('
        middle=source.index(marker);start=source.rfind('\n',0,middle)+1;end=source.index('\n}\n',middle)+3
        function=source[start:end];declaration=function[:function.index('{')].strip().replace('MobileViewportManager::','')+';'
        code=r'''
#include <cassert>
#include <algorithm>
struct ScreenIntSize{int width=0,height=0;ScreenIntSize()=default;ScreenIntSize(int w,int h):width(w),height(h){}};
struct ScreenSize{float width=0,height=0;ScreenSize()=default;ScreenSize(ScreenIntSize v):width(v.width),height(v.height){}};
struct ScreenMargin{float left,right,top,bottom;float LeftRight()const{return left+right;}float TopBottom()const{return top+bottom;}};
struct LayoutDeviceToScreenScale{explicit LayoutDeviceToScreenScale(float){}};
ScreenMargin operator*(ScreenMargin m,LayoutDeviceToScreenScale){return m;}
struct Context{ScreenMargin margin;bool canonical=true;bool IsCloakfoxCanonicalLayout(){return canonical;}ScreenMargin ScrollbarAreaToExcludeFromCompositionBounds(){return margin;}};
struct MobileViewportManager{Context*mContext;''' +declaration+r'''};
''' +function+r'''
int main(){
 Context context{{0,21.25f,0,0}};MobileViewportManager manager{&context};auto size=manager.GetCompositionSize({2000,1125});
 assert(size.width==1978.75f && size.height==1125 && size.width/1.25f==1583);
 context.canonical=false;size=manager.GetCompositionSize({2000,1125});assert(size.width==1978 && size.height==1125);
 context.canonical=true;
 context.margin={17,0,0,0};size=manager.GetCompositionSize({1600,900});assert(size.width==1583 && size.height==900);
 context.margin={34,0,0,0};size=manager.GetCompositionSize({3200,1800});assert(size.width/2==1583);
 manager.mContext=nullptr;size=manager.GetCompositionSize({2000,1125});assert(size.width==0&&size.height==0);
}
'''
        compile_run(code)


    def test_actual_fixed_culling_scrollport_origin(self):
        source=(ROOT/'firefox-src/layout/painting/nsDisplayList.cpp').read_text()
        start=source.index('nsRect nsDisplayListBuilder::OutOfFlowDisplayData::ComputeVisibleRectForFrame(')
        end=source.index('\n}\n',start)+3
        function=source[start:end]
        code=r"""
#include <cassert>
#include <algorithm>
#define MOZ_LIKELY(x) (x)
struct nsPoint{int x=0,y=0;nsPoint()=default;nsPoint(int x_,int y_):x(x_),y(y_){};};
struct nsSize{int width,height;};
struct nsRect{int x=0,y=0,width=0,height=0;nsRect()=default;nsRect(nsPoint p,nsSize s):x(p.x),y(p.y),width(s.width),height(s.height){}
 nsRect(int x_,int y_,int w,int h):x(x_),y(y_),width(w),height(h){}
 nsRect&operator+=(nsPoint p){x+=p.x;y+=p.y;return *this;}nsRect&operator-=(nsPoint p){x-=p.x;y-=p.y;return *this;}
 nsPoint TopLeft()const{return {x,y};}void Inflate(int v){x-=v;y-=v;width+=2*v;height+=2*v;}
 void IntersectRect(nsRect a,nsRect b){int right=std::min(a.x+a.width,b.x+b.width),bottom=std::min(a.y+a.height,b.y+b.height);x=std::max(a.x,b.x);y=std::max(a.y,b.y);width=std::max(0,right-x);height=std::max(0,bottom-y);}
};
nsRect operator-(nsRect r,nsPoint p){r-=p;return r;}
struct Content{};struct Context{bool canonical=true,root=true;bool CloakfoxCanonicalLayout(){return canonical;}bool IsRootContentDocumentCrossProcess(){return root;}static int CSSPixelsToAppUnits(int v){return v;}};using nsPresContext=Context;
struct nsIFrame;struct ScrollContainerFrame;struct PresShell{Context context;ScrollContainerFrame*root=nullptr;bool visual=true;nsPoint offset;nsSize size{1583,900};
 bool IsVisualViewportSizeSet(){return visual;}nsPoint GetVisualViewportOffsetRelativeToLayoutViewport(){return offset;}nsSize GetVisualViewportSize(){return size;}ScrollContainerFrame*GetRootScrollContainerFrame(){return root;}
 struct Doc{bool IsContentDocument(){return true;}}doc;Doc*GetDocument(){return &doc;}
};
struct nsIFrame{nsIFrame*parent=nullptr;::PresShell*shell=nullptr;nsPoint position;nsSize size{1600,900};nsRect overflow{0,0,5,10};Content content;
 nsIFrame*GetParent(){return parent;}nsSize GetSize(){return size;}::PresShell*PresShell(){return shell;}Context*PresContext(){return &shell->context;}Content*GetContent(){return &content;}
 nsPoint GetPosition(){return position;}nsRect InkOverflowRect(){return overflow;}bool IsTransformed(){return false;}
};
struct ScrollContainerFrame:nsIFrame{nsRect port{17,0,1583,900};nsRect GetScrollPortRect(){return port;}};
struct nsDisplayListBuilder{bool retaining=false,partial=false,painting=true;bool IsRetainingDisplayList(){return retaining;}bool IsPartialUpdate(){return partial;}bool IsPaintingToWindow(){return painting;}
 struct OutOfFlowDisplayData{static nsRect ComputeVisibleRectForFrame(nsDisplayListBuilder*,nsIFrame*,const nsRect&,const nsRect&,nsRect*);};};
namespace StaticPrefs{bool apz_allow_zooming(){return true;}bool apz_test_logging_enabled(){return false;}}
enum class ContentGeometryType{Fixed};struct DisplayPortOptions{DisplayPortOptions With(ContentGeometryType){return *this;}};
namespace DisplayPortUtils{bool fixed=true,hasPort=false;nsRect port;
 bool IsFixedPosFrameInDisplayPort(nsIFrame*){return fixed;}bool GetDisplayPort(Content*,nsRect*out,DisplayPortOptions){*out=port;return hasPort;}}
namespace CSSSize{nsRect FromAppUnits(nsRect r){return r;}}const char*ToString(nsRect){return "";}
namespace nsLayoutUtils{void LogAdditionalTestData(nsDisplayListBuilder*,const char*,const char*){}}
enum class DisplayItemType{TYPE_TRANSFORM};namespace EffectCompositor{bool HasAnimationsForCompositor(nsIFrame*,DisplayItemType){return false;}}
"""+function+r"""
int main(){PresShell shell;ScrollContainerFrame scroll;scroll.shell=&shell;shell.root=&scroll;nsIFrame viewport;viewport.shell=&shell;nsIFrame fixed;fixed.parent=&viewport;fixed.shell=&shell;fixed.position={1595,5};nsDisplayListBuilder builder;nsRect dirty;nsRect full{0,0,1600,900};
 auto compute=[&](){return nsDisplayListBuilder::OutOfFlowDisplayData::ComputeVisibleRectForFrame(&builder,&fixed,full,full,&dirty);};
 auto r=compute();assert(r.width==5&&r.height==10&&dirty.width==5); // Right edge is inside left-gutter scrollport.
 fixed.position={12,5};r=compute();assert(r.width==0); // Gutter itself stays excluded.
 fixed.position={1595,5};shell.context.canonical=false;r=compute();assert(r.width==0); // Preserve native/off semantics.
 shell.context.canonical=true;shell.context.root=false;r=compute();assert(r.width==0);shell.context.root=true;
 scroll.port.x=0;r=compute();assert(r.width==0);scroll.port.x=17;
 DisplayPortUtils::hasPort=true;DisplayPortUtils::port={0,0,1583,900};r=compute();assert(r.width==5&&dirty.width==5); // Fixed displayport also relative to scrollport.
 DisplayPortUtils::port={-100,0,1783,900};r=compute();assert(r.width==5); // Preserve pre-render margins.
 DisplayPortUtils::hasPort=false;builder.partial=true;r=compute();assert(r.width==5);builder.partial=false;
 shell.visual=false;r=compute();assert(r.width==5); // Whole-parent fallback must not acquire a gutter offset.
}
"""
        compile_run(code)


    def test_actual_root_event_visibility_boundary(self):
        source=(ROOT/'firefox-src/layout/generic/nsIFrame.cpp').read_text()
        start=source.index('static bool DescendIntoChild(')
        end=source.index('\n  if (aChild->ForceDescendIntoIfVisible()',start)
        function=source[start:end]+'\nreturn false;\n}\n'
        code=r"""
#include <cassert>
#include <cmath>
constexpr int NS_FRAME_FORCE_DISPLAY_LIST_DESCEND_INTO=1;
struct nsSize{int width,height;};
struct nsRect{int x=0,y=0,width=0,height=0;bool Intersects(nsRect r)const{return x<r.x+r.width&&r.x<x+width&&y<r.y+r.height&&r.y<y+height;}
 nsSize Size()const{return {width,height};}void SizeTo(nsSize s){width=s.width;height=s.height;}
 void ScaleRoundOut(double scale){const int right=int(std::ceil((x+width)*scale)),bottom=int(std::ceil((y+height)*scale));x=int(std::floor(x*scale));y=int(std::floor(y*scale));width=right-x;height=bottom-y;}};
struct Context{bool canonical=true,root=true,toolbar=false;float output=1.25;bool CloakfoxCanonicalLayout(){return canonical;}bool IsRootContentDocumentCrossProcess(){return root;}bool HasDynamicToolbar(){return toolbar;}float CloakfoxOutputResolution(){return output;}};
struct nsIFrame;struct Shell{nsIFrame*root;nsIFrame*GetRootScrollContainerFrame(){return root;}};
struct nsIFrame{Context*pc;Shell*shell;nsRect overflow{0,0,1600,900};bool HasAnyStateBits(int)const{return false;}nsRect InkOverflowRect()const{return overflow;}Context*PresContext()const{return pc;}Shell*PresShell()const{return shell;}};
struct nsDisplayListBuilder{bool event=true,layout=false;nsIFrame*GetIgnoreScrollFrame(){return nullptr;}nsIFrame*GetPresShellIgnoreScrollFrame(){return nullptr;}bool IsForEventDelivery(){return event;}bool IsRelativeToLayoutViewport(){return layout;}};
namespace nsLayoutUtils{nsSize ExpandHeightForDynamicToolbar(Context*,nsSize s){return s;}}
"""+function+r"""
int main(){Context context;Shell shell;nsIFrame root{&context,&shell};shell.root=&root;nsDisplayListBuilder builder;
 nsRect visible{1990,125,1,1},dirty=visible;
 assert(DescendIntoChild(&builder,&root,visible,dirty)); // Physical 1.25x right gutter reaches its zoom container.
 context.output=2;dirty={3182,200,1,1};assert(DescendIntoChild(&builder,&root,visible,dirty));
 dirty={3201,200,1,1};assert(!DescendIntoChild(&builder,&root,visible,dirty)); // No unbounded root expansion.
 context.canonical=false;dirty={3182,200,1,1};assert(!DescendIntoChild(&builder,&root,visible,dirty));context.canonical=true;
 builder.event=false;assert(!DescendIntoChild(&builder,&root,visible,dirty));builder.event=true;
 builder.layout=true;assert(!DescendIntoChild(&builder,&root,visible,dirty));builder.layout=false;
 context.root=false;assert(!DescendIntoChild(&builder,&root,visible,dirty));context.root=true;
 nsIFrame child{&context,&shell};assert(!DescendIntoChild(&builder,&child,visible,dirty));
 dirty={1591,100,1,1};context.output=1;assert(DescendIntoChild(&builder,&root,visible,dirty));
}
"""
        # aVisible participates only in the continuation excluded above.
        code = code.replace('const nsRect& aVisible,','const nsRect& /*aVisible*/,')
        compile_run(code)


    def test_actual_positioned_root_scrollparts_inside_output(self):
        source=(ROOT/'firefox-src/layout/generic/ScrollContainerFrame.cpp').read_text()
        start=source.index('  MaybeCreateTopLayerAndWrapRootItems(\n      aBuilder, set, willBuildAsyncZoomContainer')
        marker=source.rfind('  // Root positioned scrollparts include classic scrollbars:',0,start)
        before=source[marker:start] if marker>=0 else ''
        callend=source.index(';',start)+1
        wrapper=source[start:callend]
        afterstart=source.index('  // Now display overlay scrollbars and the resizer, if we have one.',callend)
        afterend=source.index('\n\n  set.MoveTo(aLists);',afterstart)
        after=source[afterstart:afterend]
        code=r"""
#include <cassert>
#include <vector>
struct List{int bars=0;};
struct Frame{bool canonicalOutput;int inside=-1,outside=-1;std::vector<int> calls;explicit Frame(bool c):canonicalOutput(c){}
 void AppendScrollPartsTo(void*,List&set,bool,bool positioned){calls.push_back(positioned);if(positioned)++set.bars;}
 void MaybeCreateTopLayerAndWrapRootItems(void*,List&set,bool,bool,void*,int,void*){inside=set.bars;set.bars=0;}
 void Build(){void*aBuilder=nullptr;List set;bool createLayersForScrollbars=true,willBuildAsyncZoomContainer=true,capturedByViewTransition=false,haveRadii=false;int blendCapture=0,clipRect=0,radii=0;
"""+before+wrapper+after+r"""
 outside=set.bars;
 }};
int main(){Frame canonical{true};canonical.Build();assert(canonical.inside==1&&canonical.outside==0&&canonical.calls.size()==1);
 Frame native{false};native.Build();assert(native.inside==0&&native.outside==1&&native.calls.size()==1);
}
"""
        compile_run(code)


    def test_actual_widget_resize_physical_boundary(self):
        source=(ROOT/'firefox-src/layout/base/PresShellWidgetListener.cpp').read_text()
        start=source.index('void PresShellWidgetListener::WindowResized(')
        end=source.index('\n}\n',start)+3
        function=source[start:end]
        code=r"""
#include <cassert>
#include <cstdint>
template<class T>using RefPtr=T*;
struct nsSize{int width=0,height=0;bool operator!=(nsSize v)const{return width!=v.width||height!=v.height;}};
struct LayoutDeviceIntSize{int width,height;static nsSize ToAppUnits(LayoutDeviceIntSize s,int p2a){return {s.width*p2a,s.height*p2a};}};
struct Device{bool changed=true;int checks=0;bool CheckDPIChange(){++checks;return changed;}};
struct Frame{int invalidations=0;void InvalidateFrame(){++invalidations;}};
struct nsPresContext{bool canonical=true,suspendedAtSync=false;int apd=60,changes=0,begins=0;Device device;nsSize visible{96000,54000};
 Device*DeviceContext(){return &device;}int AppUnitsPerDevPixel(){return apd;}bool CloakfoxCanonicalLayout(){return canonical;}
 void UIResolutionChangedSync(){++changes;suspendedAtSync=begins>0;}void BeginCloakfoxCanonicalLayout(){++begins;}
 nsSize CloakfoxViewportSize(LayoutDeviceIntSize s){return {s.width*30,s.height*30};}
 struct Area{nsSize value;nsSize Size(){return value;}};Area GetVisibleArea(){return {visible};}
};
struct PresShell{nsPresContext pc;Frame frame;nsSize size;nsPresContext*GetPresContext(){return &pc;}Frame*GetRootFrame(){return &frame;}void SetLayoutViewportSize(nsSize s,bool){size=s;}};
struct nsIWidget{};struct nsXULPopupManager{static nsXULPopupManager*GetInstance(){return nullptr;}void AdjustPopupsOnWindowChange(PresShell*){}};
struct PresShellWidgetListener{PresShell*shell;PresShell*GetPresShell(){return shell;}void WindowResized(nsIWidget*,const LayoutDeviceIntSize&);};
"""+function+r"""
int main(){PresShell shell;PresShellWidgetListener listener{&shell};listener.WindowResized(nullptr,{3200,1800});
 assert(shell.size.width==96000&&shell.size.height==54000&&shell.pc.changes==1&&shell.frame.invalidations==1&&shell.pc.suspendedAtSync);
 shell.pc.device.changed=false;shell.pc.visible={192000,108000};listener.WindowResized(nullptr,{3200,1800});assert(shell.pc.begins>0);
 shell.pc.canonical=false;shell.pc.apd=30;listener.WindowResized(nullptr,{3200,1800});assert(shell.size.width==96000&&shell.size.height==54000&&shell.pc.changes==1);
 shell.pc.apd=60;listener.WindowResized(nullptr,{3200,1800});assert(shell.size.width==192000&&shell.size.height==108000);
 listener.shell=nullptr;listener.WindowResized(nullptr,{3200,1800});
}
"""
        compile_run(code)


    def test_actual_ready_requires_viewer_normalized_viewport(self):
        source=(ROOT/'firefox-src/layout/base/nsPresContext.cpp').read_text()
        start=source.index('bool nsPresContext::CloakfoxCanonicalGeometryReady()')
        end=source.index('\nvoid nsPresContext::CompleteCloakfoxCanonicalLayout()',start)
        ready=source[start:end];marker=ready.find('  if (mCloakfoxCanonicalOutput) {')
        dispatch=''
        if marker>=0:
            opening=ready.index('{',marker);depth=1;stop=opening+1
            while depth:
                depth+=(ready[stop]=='{')-(ready[stop]=='}');stop+=1
            dispatch=ready[marker:stop]
        code=r"""
#include <cassert>
struct LayoutDeviceIntSize{int width=3200,height=1800;};struct nsSize{int width,height;bool operator!=(nsSize v)const{return width!=v.width||height!=v.height;}};
struct Shell{nsSize pending{1600,900};nsSize MaybePendingLayoutViewportSize(){return pending;}};
struct nsPresContext;namespace nsLayoutUtils{bool GetDocumentViewerSize(nsPresContext*,LayoutDeviceIntSize&);}
struct nsPresContext{bool mCloakfoxCanonicalOutput=true,viewer=true;Shell*mPresShell;nsSize visible{3200,1800};int revocations=0;
 struct Area{nsSize value;nsSize Size(){return value;}};Area GetVisibleArea(){return {visible};}
 nsSize CloakfoxViewportSize(LayoutDeviceIntSize s){return {s.width/2,s.height/2};}
 bool Ready(){
"""+dispatch+r"""
 return true;
 }};
bool nsLayoutUtils::GetDocumentViewerSize(nsPresContext*pc,LayoutDeviceIntSize&){return pc->viewer;}
int main(){Shell shell;nsPresContext pc;pc.mPresShell=&shell;assert(!pc.Ready()); // Completed stale3200 layout must stay protected.
 pc.visible={1600,900};assert(pc.Ready());shell.pending={3200,1800};assert(!pc.Ready()); // Wrong queued reflow cannot reopen admission.
 shell.pending={1600,900};assert(pc.Ready());pc.viewer=false;assert(!pc.Ready());
 pc.mCloakfoxCanonicalOutput=false;assert(pc.Ready());assert(pc.revocations==0); // Transient resize mismatch does not permanently revoke an owner.
}
"""
        compile_run(code)


    def test_actual_canonical_root_excludes_embedder_insets(self):
        source=(ROOT/'firefox-src/layout/generic/ScrollContainerFrame.cpp').read_text()
        start=source.index('nsMargin ScrollContainerFrame::ScrollbarInsets() const')
        end=source.index('\n}\n',start)+3
        function=source[start:end]
        code=r"""
#include <cassert>
struct nsMargin{int top=0,right=0,bottom=0,left=0;};struct WritingMode{};struct ComputedStyle{};
struct Context{bool canonical=true;nsMargin embedder{0,0,15,0};bool CloakfoxCanonicalLayout(){return canonical;}nsMargin EmbedderScrollbarInset(){return embedder;}};
nsMargin StyleScrollbarInsets(const ComputedStyle&,WritingMode){return {1,2,3,4};}
struct ScrollContainerFrame{bool mIsRoot=true;mutable Context pc;ComputedStyle style;Context*PresContext()const{return &pc;}const ComputedStyle*Style()const{return &style;}WritingMode GetWritingMode()const{return {};}
 nsMargin ScrollbarInsets()const;};
"""+function+r"""
int main(){ScrollContainerFrame root;auto inset=root.ScrollbarInsets();assert(inset.top==0&&inset.bottom==0&&inset.left==0&&inset.right==0);
 root.pc.embedder={0,0,24,0};assert(root.ScrollbarInsets().bottom==0); // Physical host rounding/UI cannot shorten the canonical track.
 root.pc.canonical=false;assert(root.ScrollbarInsets().bottom==24); // Ordinary embedder policy remains exact.
 root.mIsRoot=false;root.pc.canonical=true;inset=root.ScrollbarInsets();assert(inset.top==1&&inset.right==2&&inset.bottom==3&&inset.left==4); // Authored element inset remains exact.
}
"""
        compile_run(code)


    def test_actual_canonical_theme_avoids_host_arrow_policy(self):
        source=(ROOT/'firefox-src/widget/Theme.cpp').read_text()
        start=source.index('class CloakfoxScrollbarDrawing final :')
        end=source.index('\n};',start)+3
        definition=source[start:end]
        code=r"""
#include <cassert>
class ScrollbarDrawingWin{public:int size=0;virtual~ScrollbarDrawingWin()=default;virtual void RecomputeScrollbarParams(){};virtual bool ShouldDrawScrollbarButtons(){return true;}void ConfigureScrollbarSize(int n){size=n;}};
"""+definition+r"""
int main(){CloakfoxScrollbarDrawing canonical;canonical.RecomputeScrollbarParams();assert(canonical.size==17);assert(!canonical.ShouldDrawScrollbarButtons());
 ScrollbarDrawingWin native;assert(native.ShouldDrawScrollbarButtons()); // Host/native arrow policy remains supported outside this drawing instance.
}
"""
        compile_run(code)


    def test_actual_canonical_async_zoom_event_bounds(self):
        source=(ROOT/'firefox-src/layout/painting/nsDisplayList.cpp').read_text()
        start=source.index('nsRect nsDisplayWrapList::GetBounds(')
        end=source.index('\n}\n',start)+3
        function=source[start:end]
        code=r"""
#include <cassert>
#include <cmath>
struct nsRect{int x=0,y=0,width=0,height=0;void ScaleRoundOut(double scale){const int r=int(std::ceil((x+width)*scale)),b=int(std::ceil((y+height)*scale));x=int(std::floor(x*scale));y=int(std::floor(y*scale));width=r-x;height=b-y;}bool Contains(int px,int py)const{return px>=x&&py>=y&&px<x+width&&py<y+height;}};
enum class DisplayItemType{TYPE_ASYNC_ZOOM,TYPE_OTHER};
struct Context{bool canonical=true;bool CloakfoxCanonicalLayout(){return canonical;}};
struct Shell{float resolution=2;float GetResolution(){return resolution;}};
struct Frame{Context context;Shell shell;Context*PresContext(){return &context;}Shell*PresShell(){return &shell;}};
struct nsDisplayListBuilder{bool event=true,layout=false;bool IsForEventDelivery(){return event;}bool IsRelativeToLayoutViewport(){return layout;}};
struct nsDisplayWrapList{nsRect mBounds{0,0,1600,900};Frame*mFrame;DisplayItemType type=DisplayItemType::TYPE_ASYNC_ZOOM;DisplayItemType GetType()const{return type;}nsRect GetBounds(nsDisplayListBuilder*,bool*)const;};
"""+function+r"""
int main(){Frame frame;nsDisplayWrapList zoom;zoom.mFrame=&frame;nsDisplayListBuilder builder;bool snap=true;
 auto b=zoom.GetBounds(&builder,&snap);assert(!snap&&b.width==3200&&b.height==1800&&b.Contains(3182,200)); // Pre-HitTest visual filter reaches the right thumb.
 frame.shell.resolution=1.25;b=zoom.GetBounds(&builder,&snap);assert(b.width==2000&&b.height==1125&&b.Contains(1990,125));
 builder.layout=true;b=zoom.GetBounds(&builder,&snap);assert(b.width==1600);builder.layout=false;
 builder.event=false;b=zoom.GetBounds(&builder,&snap);assert(b.width==1600);builder.event=true;
 frame.context.canonical=false;b=zoom.GetBounds(&builder,&snap);assert(b.width==1600);frame.context.canonical=true;
 zoom.type=DisplayItemType::TYPE_OTHER;b=zoom.GetBounds(&builder,&snap);assert(b.width==1600);
}
"""
        compile_run(code)
