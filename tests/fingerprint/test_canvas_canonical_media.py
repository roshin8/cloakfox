"""Run scalar native media color math against independently computed references."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class CanonicalMedia(unittest.TestCase):
 def test_scalar_range_matrix_transfer_and_high_depth(self):
  header=ROOT/'firefox-src/gfx/ycbcr/CanonicalYUV.h'
  self.assertTrue(header.exists(),'canonical media scalar transform absent')
  code=r'''
#include <cassert>
#include <array>
#include "CanonicalYUV.h"
using namespace mozilla::gfx::canonical;
int main(){
 const uint8_t interleaved[]={16,99,32,99,240,99,235,99};
 assert(Sample(interleaved,4,1,0,8,1)==32 && Sample(interleaved,4,0,1,8,1)==240);
 assert(Sample(interleaved+4,-4,1,1,8,1)==32);
 uint8_t unaligned[]={99,0,2,99};
 assert(Sample(unaligned+1,2,0,0,10,0)==512);
 ColorPolicy p{Matrix::BT601,Primaries::SRGB,Transfer::SRGB,false};
 assert((Convert(16,128,128,8,p)==std::array<uint8_t,3>{0,0,0}));
 assert((Convert(235,128,128,8,p)==std::array<uint8_t,3>{255,255,255}));
 auto red=Convert(81,90,240,8,p);assert(red[0]>=253 && red[1]<=1 && red[2]<=1);
 auto mid=Convert(128,128,128,8,p);
 assert((mid==std::array<uint8_t,3>{130,130,130}));
 p.fullRange=true;
 assert((Convert(0,128,128,8,p)==std::array<uint8_t,3>{0,0,0}));
 assert((Convert(255,128,128,8,p)==std::array<uint8_t,3>{255,255,255}));
 p.fullRange=false;
 for(unsigned y=16;y<=235;y++){
  auto a=Convert(y,128,128,8,p),b=Convert(y*4,512,512,10,p),c=Convert(y*256,32768,32768,16,p);
  assert(a==b && a==c);
 }
 p.matrix=Matrix::BT709; p.transfer=Transfer::BT709;
 auto gamma=Convert(126,128,128,8,p); // encoded .50228, gamma2.4 -> sRGB .4749086758
 assert(gamma[0]==121 && gamma[1]==121 && gamma[2]==121);
 p.transfer=Transfer::PQ;p.primaries=Primaries::BT2020;
 auto black=Convert(16,128,128,8,p);assert(black[0]==0 && black[1]==0 && black[2]==0);
 auto white=Convert(235,128,128,8,p);assert(white[0]==255 && white[1]==255 && white[2]==255);
 for(auto transfer:{Transfer::SRGB,Transfer::BT709,Transfer::PQ,Transfer::HLG,Transfer::Linear}){
  p.transfer=transfer;unsigned previous=0;
  for(unsigned y=16;y<=235;y++){auto pixel=Convert(y,128,128,8,p);assert(pixel[0]>=previous);previous=pixel[0];}
 }
}
'''
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'color.cpp';src.write_text(code);exe=Path(d)/'color'
   objects=[ROOT/'firefox-src/obj-aarch64-apple-darwin/modules/fdlibm/src'/name for name in ('e_pow.o','e_exp.o')]
   self.assertTrue(all(p.exists() for p in objects),'built bundled fdlibm objects required')
   subprocess.run(['c++','-std=c++17','-ffp-contract=off','-I',str(header.parent),'-I',str(ROOT/'firefox-src/modules/fdlibm/src'),str(src),*map(str,objects),'-o',str(exe)],check=True)
   subprocess.run([str(exe)],check=True)

class CanonicalNativePlanes(unittest.TestCase):
 def test_native_stride_crop_alpha_color_and_failure(self):
  native=(ROOT/'firefox-src/gfx/ycbcr/YCbCrUtils.cpp').read_text()
  start=native.index('static canonical::ColorPolicy CanonicalColorPolicy(')
  end=native.index('nsresult ConvertYCbCrToRGB(const layers::PlanarYCbCrData& aData,\n                           const SurfaceFormat& aDestFormat,',start)
  implementation=native[start:end]
  route_start=end
  route_end=native.index('// ConvertYCbCrToRGB et al.',route_start)
  routing=native[route_start:route_end]+'StaticPrefs::mode=true;return NS_OK;\n}\n'
  types=r"""
#include <optional>
#include <cassert>
#include <cstring>
#include "CanonicalYUV.h"
using nsresult=int;constexpr int NS_OK=0,NS_ERROR_INVALID_ARG=1;
bool NS_SUCCEEDED(nsresult r){return r==NS_OK;}
namespace mozilla::gfx {
struct StaticPrefs{inline static bool mode=false;static bool cloakfox_enabled(){return true;}static bool cloakfox_experimental_canvas_pipeline(){return mode;}};
struct Matrix {}; // Real gfx also defines this name; the codec must qualify its matrix enum.
struct IntSize{int width,height;};
struct IntRect{int x=0,y=0,width=0,height=0;int XMost()const{return x+width;}int YMost()const{return y+height;}bool IsEmpty()const{return width<=0||height<=0;}IntSize Size()const{return {width,height};}};
enum class SurfaceFormat {B8G8R8A8,B8G8R8X8,R8G8B8A8,R8G8B8X8,R5G6B5_UINT16};
enum class ColorDepth{COLOR_8=8,COLOR_10=10,COLOR_12=12,COLOR_16=16};
unsigned BitDepthForColorDepth(ColorDepth d){return unsigned(d);}
enum class ChromaSubsampling {FULL,HALF_WIDTH,HALF_WIDTH_AND_HEIGHT};
enum class YUVColorSpace{BT601,BT709,BT2020,Identity};
enum class ColorSpace2{UNKNOWN,SRGB,BT709,BT601_525,BT2020,DISPLAY_P3};
enum class ColorRange{FULL,LIMITED};
enum class TransferFunction{SRGB,BT709,PQ,HLG,LINEAR};
}
namespace mozilla::layers {
struct PlanarYCbCrImage{static constexpr int MAX_DIMENSION=16384;};
struct Alpha{uint8_t*mChannel=nullptr;gfx::IntSize mSize;gfx::ColorDepth mDepth=gfx::ColorDepth::COLOR_8;bool mPremultiplied=false;};
struct PlanarYCbCrData {
 uint8_t*mYChannel=nullptr,*mCbChannel=nullptr,*mCrChannel=nullptr;
 int mYStride=0,mCbCrStride=0,mYSkip=0,mCbSkip=0,mCrSkip=0;
 gfx::IntRect mPictureRect;
 gfx::ColorDepth mColorDepth=gfx::ColorDepth::COLOR_8;
 gfx::ColorRange mColorRange=gfx::ColorRange::FULL;
 gfx::ChromaSubsampling mChromaSubsampling=gfx::ChromaSubsampling::FULL;
 gfx::YUVColorSpace mYUVColorSpace=gfx::YUVColorSpace::BT709;
 gfx::ColorSpace2 mColorPrimaries=gfx::ColorSpace2::SRGB;
 gfx::TransferFunction mTransferFunction=gfx::TransferFunction::SRGB;
 std::optional<Alpha>mAlpha;
 gfx::IntSize CbCrDataSize()const{return {mPictureRect.XMost(),mPictureRect.YMost()};}
};
}
namespace mozilla::gfx {
"""+implementation+routing+r"""
}
using namespace mozilla::gfx;
int main(){
 uint8_t y[]={11,99,22,99,33,99,44,99,64,99,128,99,55,99,192,99,255,99};
 uint8_t a[]={255,99,255,99,255,99,255,99,0,99,64,99,255,99,128,99,255,99};
 uint8_t out[24];memset(out,77,sizeof(out));
 mozilla::layers::PlanarYCbCrData data;
 data.mYChannel=y;data.mYStride=6;data.mYSkip=1;data.mPictureRect={1,1,2,2};
 assert(ConvertCanonicalYCbCr(data,SurfaceFormat::B8G8R8A8,{2,2},out,12,canonical::AlphaOperation::None)==NS_OK);
 bool proof=true;
 StaticPrefs::mode=false;
 assert(ConvertYCbCrToRGB(data,SurfaceFormat::B8G8R8A8,{2,2},out,12,&proof)==NS_OK && StaticPrefs::mode && !proof);
 proof=false;
 assert(ConvertYCbCrToRGB(data,SurfaceFormat::B8G8R8A8,{2,2},out,12,&proof)==NS_OK && proof);
 assert(out[0]==64 && out[4]==128 && out[12]==192 && out[16]==255 && out[3]==255 && out[8]==77);
 // Native alpha plane stride follows Y, but each alpha sample is packed.
 uint8_t alpha[]={255,255,255,99,99,99,255,0,64,99,99,99,255,128,255,99,99,99};
 data.mAlpha=mozilla::layers::Alpha{alpha,{3,3}};
 assert(ConvertCanonicalYCbCr(data,SurfaceFormat::R8G8B8A8,{2,2},out,12,canonical::AlphaOperation::Premultiply)==NS_OK);
 assert(out[0]==0 && out[3]==0 && out[4]==32 && out[7]==64 && out[12]==96 && out[15]==128 && out[16]==255);
 assert(ConvertCanonicalYCbCr(data,SurfaceFormat::R8G8B8A8,{2,2},out,7,canonical::AlphaOperation::None)==NS_ERROR_INVALID_ARG);
 data.mPictureRect.x=-1;
 proof=true;
 assert(ConvertYCbCrToRGB(data,SurfaceFormat::B8G8R8A8,{2,2},out,12,&proof)==NS_ERROR_INVALID_ARG && !proof);
 assert(ConvertCanonicalYCbCr(data,SurfaceFormat::R8G8B8A8,{2,2},out,12,canonical::AlphaOperation::None)==NS_ERROR_INVALID_ARG);
 // Premultiplied source must become straight before the color transform.
 uint8_t premulY[]={64}, premulAlpha[]={128};
 data.mYChannel=premulY;data.mYStride=1;data.mYSkip=0;data.mPictureRect={0,0,1,1};
 data.mAlpha=mozilla::layers::Alpha{premulAlpha,{1,1},ColorDepth::COLOR_8,true};
 assert(ConvertCanonicalYCbCr(data,SurfaceFormat::R8G8B8A8,{1,1},out,4,canonical::AlphaOperation::Unpremultiply)==NS_OK);
 assert(out[0]==128 && out[1]==128 && out[2]==128 && out[3]==128);
 assert(ConvertCanonicalYCbCr(data,SurfaceFormat::R8G8B8A8,{1,1},out,4,canonical::AlphaOperation::None)==NS_OK);
 assert(out[0]==64 && out[3]==128);
 uint8_t colors[256*4];for(unsigned v=0;v<256;v++){colors[v*4]=v;colors[v*4+1]=255-v;colors[v*4+2]=v/2;colors[v*4+3]=v;}
 uint8_t original[sizeof(colors)];memcpy(original,colors,sizeof(colors));
 assert(CanonicalizeRGBSurface(colors,sizeof(colors),{256,1},SurfaceFormat::B8G8R8A8,ColorSpace2::SRGB,TransferFunction::SRGB,true)==NS_OK);
 assert(!memcmp(original,colors,sizeof(colors)));
 uint8_t wide[]={0,128,255,255};
 assert(CanonicalizeRGBSurface(wide,4,{1,1},SurfaceFormat::B8G8R8A8,ColorSpace2::DISPLAY_P3,TransferFunction::SRGB,true)==NS_OK);
 assert(wide[2]==255 && wide[1]<128 && wide[0]==0 && wide[3]==255);
}
"""
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'planes.cpp';src.write_text(types);exe=Path(d)/'planes'
   objects=[ROOT/'firefox-src/obj-aarch64-apple-darwin/modules/fdlibm/src'/name for name in ('e_pow.o','e_exp.o')]
   subprocess.run(['c++','-std=c++17','-ffp-contract=off','-I',str(ROOT/'firefox-src/gfx/ycbcr'),'-I',str(ROOT/'firefox-src/modules/fdlibm/src'),str(src),*map(str,objects),'-o',str(exe)],check=True)
   subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()

class CanonicalP010Transport(unittest.TestCase):
 def test_native_unpack_preserves_full_range_logical_samples(self):
  native=(ROOT/'firefox-src/gfx/layers/MacIOSurfaceHelpers.cpp').read_text()
  start=native.index('static void CopyP010PlaneToPlanar10(')
  end=native.index('static nsresult CopyFromLockedMacIOSurface(',start)
  code=r'''#include <cassert>
#include <cstdint>
#include <cstddef>
#include <cstring>
#include "CanonicalYUV.h"
'''+native[start:end]+r'''
int main(){
 using namespace mozilla::gfx::canonical;
 ColorPolicy p{Matrix::BT709,Primaries::SRGB,Transfer::SRGB,true};
 uint8_t padded[12]={};uint16_t packed[]={uint16_t(259<<6),uint16_t(512<<6),uint16_t(1023<<6),uint16_t(64<<6)};
 memcpy(padded+1,packed,sizeof(packed));uint16_t y[2],cb[2];
 CopyP010PlaneToPlanar10(padded+1,12,y,2,1,2,0);
 CopyP010PlaneToPlanar10(padded+1,12,cb,2,1,2,1);
 assert(y[0]==259 && y[1]==1023 && cb[0]==512 && cb[1]==64);
 assert(Convert(y[0],512,512,10,p)[0]==65);
 for(unsigned v=0;v<1024;v++){
  uint16_t high=v<<6,logical=0;
  CopyP010PlaneToPlanar10(reinterpret_cast<uint8_t*>(&high),2,&logical,1,1,1,0);
  assert(Convert(logical,512,512,10,p)==Convert(v,512,512,10,p));
 }
}
'''
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'p010.cpp';src.write_text(code);exe=Path(d)/'p010'
   objects=[ROOT/'firefox-src/obj-aarch64-apple-darwin/modules/fdlibm/src'/name for name in ('e_pow.o','e_exp.o')]
   subprocess.run(['c++','-std=c++17','-ffp-contract=off','-I',str(ROOT/'firefox-src/gfx/ycbcr'),'-I',str(ROOT/'firefox-src/modules/fdlibm/src'),str(src),*map(str,objects),'-o',str(exe)],check=True)
   subprocess.run([str(exe)],check=True)


class CanonicalDecoderCreation(unittest.TestCase):
 def test_native_request_is_frozen_across_cpu_setup_and_creation(self):
  native=(ROOT/'firefox-src/dom/media/platforms/ffmpeg/FFmpegDecoderModule.h').read_text()
  start=native.index('    const bool canonicalDecoder =')
  end=native.index('    auto decoder =',start)
  setup=native[start:end]
  # Execute real module setup. Simulate a simultaneous pref change in CPU setup;
  # the constructor's last argument must retain the earlier requested policy.
  call_end=native.index(';',end)+1
  call=native[end:call_end]
  self.assertIn('aParams.mCDM, canonicalDecoder)',call)
  ctor=(ROOT/'firefox-src/dom/media/platforms/ffmpeg/FFmpegVideoDecoder.cpp').read_text()
  self.assertIn('mCanonicalDecoder(aCanonicalDecoder)',ctor)
  code=r"""
#include <cassert>
struct StaticPrefs{inline static bool mode=true;static bool cloakfox_enabled(){return true;}static bool cloakfox_experimental_canvas_pipeline(){return mode;}};
struct Library{bool invoked=false;void av_force_cpu_flags(int value){assert(value==0);invoked=true;StaticPrefs::mode=false;}};
int main(){Library library;auto* mLib=&library;
"""+setup+r"""
assert(canonicalDecoder && library.invoked && !StaticPrefs::mode);
}
"""
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'freeze.cpp';src.write_text(code);exe=Path(d)/'freeze'
   subprocess.run(['c++','-std=c++17',str(src),'-o',str(exe)],check=True)
   subprocess.run([str(exe)],check=True)

class CanonicalDecodedImageProof(unittest.TestCase):
 def test_real_decoder_output_branch_first_assignment_and_unknown_retention(self):
  root=ROOT/'firefox-src'
  image=(root/'gfx/layers/ImageContainer.h').read_text()
  begin=image.index('  gfx::CanvasPrivacyMetadata GetCanvasPrivacyMetadata() const {')
  methods=image[begin:image.index('  ImageFormat GetFormat()',begin)]
  impl='\n'.join(line for line in (root/'gfx/2d/CanvasPrivacy.cpp').read_text().splitlines() if not line.startswith('#include'))
  primitive=r'''
#include <cassert>
#include <optional>
#include <map>
#include <mutex>
#include "CanvasPrivacy.h"
namespace mozilla {using StaticMutex=std::mutex;using StaticMutexAutoLock=std::lock_guard<std::mutex>;}
namespace mozilla::gfx {
struct UserDataKey{};
struct SourceSurface{std::map<UserDataKey*,std::pair<void*,void(*)(void*)>> data;
 ~SourceSurface(){for(auto&x:data)x.second.second(x.second.first);}
 void*GetUserData(UserDataKey*k){auto i=data.find(k);return i==data.end()?nullptr:i->second.first;}
 void AddUserData(UserDataKey*k,void*v,void(*d)(void*)){assert(!data.count(k));data[k]={v,d};}
};
}
'''+impl+r'''
namespace gfx=mozilla::gfx;
template<class T>struct Maybe:std::optional<T>{using std::optional<T>::optional;bool isSome(){return this->has_value();}T&ref(){return this->value();}T valueOr(T fallback){return this->value_or(fallback);}};
template<class T>Maybe<T>Some(T x){return Maybe<T>(x);}
template<class T>struct DataMutex{mutable T data;T*Lock()const{return &data;}};
struct Image{
 mutable DataMutex<Maybe<gfx::CanvasPrivacyMetadata>>mCanvasPrivacyMetadata;
 bool mAuthoredRawCanvasInput=false;
'''+methods+r'''
};
struct Video{Image*mImage;};
'''
  frame=(root/'dom/media/webcodecs/VideoFrame.cpp').read_text()
  guard_start=frame.index('static bool CloakfoxCanCopyVideoFramePixels(')
  primitive+=frame[guard_start:frame.index('// https://w3c.github.io/webcodecs/#dom-videoframe-copyto',guard_start)]
  for path,ending in [('dom/media/platforms/ffmpeg/FFmpegVideoDecoder.cpp','  aResults.AppendElement'),('dom/media/platforms/agnostic/VPXDecoder.cpp','    rec.apply')]:
   source=(root/path).read_text();start=source.index('if (mCanonicalDecoder && v->mImage) {');branch=source[start:source.index(ending,start)]
   code=primitive+r'''
void Produce(bool mCanonicalDecoder,Video*v){
'''+branch+r'''
}
int main(){
 assert(CloakfoxCanCopyVideoFramePixels(false,{},false));
 assert(!CloakfoxCanCopyVideoFramePixels(true,{},false));
 assert(CloakfoxCanCopyVideoFramePixels(true,{},true));
 assert(CloakfoxCanCopyVideoFramePixels(true,{0,0,0,0,32|128},false));
 assert(!CloakfoxCanCopyVideoFramePixels(true,{0,0,0,0,32|256},false));
 assert(!CloakfoxCanCopyVideoFramePixels(true,{999,0,0,0,32|128},false));
 assert(!CloakfoxCanCopyVideoFramePixels(true,{1,7,123,456,3},false));
 assert(CloakfoxCanCopyVideoFramePixels(true,{1,7,123,456,2},false));
 assert(CloakfoxCanCopyVideoFramePixels(true,{0,0,0,0,16|1024},false));
 Image fresh;Video v{&fresh};Produce(true,&v);
 auto p=fresh.GetCanvasPrivacyMetadata();assert(p.version==0 && p.userContextId==0 && p.ownerHi==0 && p.ownerLo==0);
 assert(p.sources==(32|128) && !gfx::CanImportCanonicalCanvasPixels(p));
 Image old;old.SetCanvasPrivacyMetadata({});v.mImage=&old;Produce(true,&v);
 assert(old.GetCanvasPrivacyMetadata().sources==(1|32|128));
 assert(!gfx::CanImportCanonicalCanvasPixels(old.CanvasPrivacyMetadataForConvertedPixels(true)));
 Image inactive;v.mImage=&inactive;Produce(false,&v);assert(inactive.GetCanvasPrivacyMetadata().sources==1);
 Image wrong;wrong.SetCanvasPrivacyMetadata({0,0,0,0,32|256});v.mImage=&wrong;Produce(false,&v);
 assert(wrong.GetCanvasPrivacyMetadata().sources==(32|256));
 assert(!gfx::CanImportCanonicalCanvasPixels(wrong.GetCanvasPrivacyMetadata()));
 Image owned;owned.SetCanvasPrivacyMetadata({1,7,123,456,2});v.mImage=&owned;Produce(true,&v);
 p=owned.GetCanvasPrivacyMetadata();assert(p.version==0 && (p.sources&1));
 Image raw;raw.MarkAuthoredRawCanvasInput();
 assert(raw.GetCanvasPrivacyMetadata().sources==16 && !gfx::CanImportCanonicalCanvasPixels(raw.GetCanvasPrivacyMetadata()));
 assert(raw.CanvasPrivacyMetadataForConvertedPixels(false).sources==16);
 p=raw.CanvasPrivacyMetadataForConvertedPixels(true);
 assert(p.sources==(16|1024|256) && p.version==0 && !p.ownerHi && !p.ownerLo && gfx::CanImportCanonicalCanvasPixels(p));
 assert(raw.GetCanvasPrivacyMetadata().sources==16 && !gfx::CanImportCanonicalCanvasPixels(raw.GetCanvasPrivacyMetadata())); // No mutation of pending storage.
 Image host;host.SetCanvasPrivacyMetadata({});host.MarkAuthoredRawCanvasInput();
 assert(host.GetCanvasPrivacyMetadata().sources==1);
 p=host.CanvasPrivacyMetadataForConvertedPixels(true);
 assert(p.sources==(1|32|256) && !gfx::CanImportCanonicalCanvasPixels(p)); // Old host pixels cannot gain author or decoder proof.
 Image decoded;v.mImage=&decoded;Produce(true,&v);
 p=decoded.CanvasPrivacyMetadataForConvertedPixels(true);
 assert(p.sources==(32|128|256) && gfx::CanImportCanonicalCanvasPixels(p));
}
'''
   with tempfile.TemporaryDirectory() as d:
    src=Path(d)/'proof.cpp';src.write_text(code);exe=Path(d)/'proof'
    subprocess.run(['c++','-std=c++17','-I',str(root/'gfx/2d'),str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

class AuthoredRGBProducer(unittest.TestCase):
 def test_actual_buffer_branch_keeps_original_and_requires_conversion_success(self):
  source=(ROOT/'firefox-src/dom/media/webcodecs/VideoFrame.cpp').read_text()
  start=source.index('  if (aAuthoredColorSpace && StaticPrefs::cloakfox_enabled()')
  end=source.index('\n}\n',start)
  branch=source[start:end]
  # The canonical branch is exercised as written; its scalar math is separately
  # executed above. Surface allocation/mapping is a minimal in-memory primitive.
  code=r'''
#include <cassert>
#include <optional>
#include <vector>
#include <variant>
#include <memory>
#include <cstdint>
#include "CanvasPrivacy.h"
using nsresult=int;constexpr int NS_OK=0,NS_ERROR_DOM_MEDIA_FATAL_ERR=1;
bool NS_FAILED(int r){return r!=0;}
const char*operator""_ns(const char*s,size_t){return s;}
struct MediaResult{int result;MediaResult(int r,const char*):result(r){}};
MediaResult Err(MediaResult x){return x;}
template<class T>using RefPtr=std::shared_ptr<T>;
#define MOZ_TRY(x) (x)
struct StaticPrefs{inline static bool mode=true;static bool cloakfox_enabled(){return true;}static bool cloakfox_experimental_canvas_pipeline(){return mode;}};
namespace gfx=mozilla::gfx;
namespace mozilla::gfx {
struct IntSize{int width,height;};
enum class SurfaceFormat{BGRA};enum class ColorSpace2{SRGB,DISPLAY_P3};enum class TransferFunction{SRGB,BT709};
struct DataSourceSurface{
 enum{WRITE};std::vector<uint8_t>data;CanvasPrivacyMetadata privacy;
 IntSize size;DataSourceSurface(std::vector<uint8_t>d,IntSize s):data(d),size(s){}
 SurfaceFormat GetFormat(){return SurfaceFormat::BGRA;}
 IntSize GetSize(){return size;}
 struct ScopedMap{DataSourceSurface*p;ScopedMap(RefPtr<DataSourceSurface>s,int):p(s.get()){}bool IsMapped(){return true;}uint8_t*GetData(){return p->data.data();}int GetStride(){return p->size.width*4;}};
};
inline bool fail=false;inline ColorSpace2 lastPrimaries;inline TransferFunction lastTransfer;
nsresult CanonicalizeRGBSurface(uint8_t*p,int,IntSize,SurfaceFormat,ColorSpace2 primaries,TransferFunction transfer,bool premul){
 assert(!premul);lastPrimaries=primaries;lastTransfer=transfer;
 if(fail)return 2;p[0]+=10;return NS_OK;
}
void SetCanvasPrivacyMetadata(DataSourceSurface*p,CanvasPrivacyMetadata m){p->privacy=m;}
CanvasPrivacyMetadata GetCanvasPrivacyMetadata(DataSourceSurface*p){return p->privacy;}
inline bool swizzleSuccess=true;
template<class...T>bool SwizzleData(T...){return swizzleSuccess;}
}
namespace layers {
struct Image{virtual~Image()=default;};
struct SourceSurfaceImage:Image{
 std::vector<uint8_t>rendered,original;gfx::CanvasPrivacyMetadata privacy;
 SourceSurfaceImage(gfx::DataSourceSurface*p,gfx::DataSourceSurface*raw=nullptr):rendered(p->data),privacy(p->privacy){if(raw)original=raw->data;}
};
}
struct VideoColorSpaceInternal{std::optional<gfx::ColorSpace2>mPrimaries;std::optional<gfx::TransferFunction>mTransfer;};
auto ToPrimaries(gfx::ColorSpace2 p){return p;}auto ToTransferFunction(gfx::TransferFunction t){return t;}
RefPtr<gfx::DataSourceSurface>AllocateBGRASurface(RefPtr<gfx::DataSourceSurface>s){return std::make_shared<gfx::DataSourceSurface>(s->data,s->size);}
using Result=std::variant<RefPtr<layers::Image>,MediaResult>;
Result Produce(RefPtr<gfx::DataSourceSurface>bgraSurface,const VideoColorSpaceInternal*aAuthoredColorSpace){
 const gfx::IntSize aSize=bgraSurface->size;
 const gfx::CanvasPrivacyMetadata* aConvertedProvenance=nullptr;
'''+branch+r'''
}
int main(){
 auto raw=std::make_shared<gfx::DataSourceSurface>(std::vector<uint8_t>{20,40,60,128},gfx::IntSize{1,1});
 VideoColorSpaceInternal color{gfx::ColorSpace2::DISPLAY_P3,gfx::TransferFunction::BT709};
 auto result=Produce(raw,&color);assert(std::holds_alternative<RefPtr<layers::Image>>(result));
 auto image=std::static_pointer_cast<layers::SourceSurfaceImage>(std::get<RefPtr<layers::Image>>(result));
 assert((image->rendered==std::vector<uint8_t>{15,20,30,128}));
 assert(image->original==raw->data && (raw->data==std::vector<uint8_t>{20,40,60,128}));
 assert(gfx::lastPrimaries==gfx::ColorSpace2::DISPLAY_P3 && gfx::lastTransfer==gfx::TransferFunction::BT709);
 assert(image->privacy.sources==(16|1024|256) && image->privacy.version==0 && image->privacy.ownerHi==0);
 gfx::fail=true;result=Produce(raw,&color);assert(std::holds_alternative<MediaResult>(result));gfx::fail=false;
 result=Produce(raw,nullptr);image=std::static_pointer_cast<layers::SourceSurfaceImage>(std::get<RefPtr<layers::Image>>(result));
 assert(image->privacy.sources==1 && image->original.empty() && image->rendered==raw->data);
 StaticPrefs::mode=false;result=Produce(raw,&color);image=std::static_pointer_cast<layers::SourceSurfaceImage>(std::get<RefPtr<layers::Image>>(result));assert(image->privacy.sources==16 && image->original==raw->data && image->rendered==raw->data);
}
'''
  copy_start=source.index('  RefPtr<gfx::DataSourceSurface> bgraSurface =',source.index('static Result<RefPtr<layers::Image>, MediaResult> CreateImageFromSourceSurface('))
  copy_tail=source[copy_start:source.index('\n}\n',copy_start)]
  swizzle_start=source.index('  if (!gfx::SwizzleData(')
  swizzle_end=source.index('  return bgraSurface;',swizzle_start)
  swizzle_check=source[swizzle_start:swizzle_end]
  code=code.replace('int main(){',r'''Result CopyFromSource(RefPtr<gfx::DataSourceSurface>surface,gfx::DataSourceSurface*aSource){
'''+copy_tail+r'''
}
std::variant<RefPtr<gfx::DataSourceSurface>,MediaResult> CheckSwizzle(RefPtr<gfx::DataSourceSurface>aSurface,RefPtr<gfx::DataSourceSurface>bgraSurface){
 gfx::DataSourceSurface::ScopedMap surfaceMap(aSurface,gfx::DataSourceSurface::WRITE),bgraMap(bgraSurface,gfx::DataSourceSurface::WRITE);
'''+swizzle_check+r'''
 return bgraSurface;
}
int main(){
 auto original=std::make_shared<gfx::DataSourceSurface>(std::vector<uint8_t>{20,40,60,255},gfx::IntSize{1,1});
 original->privacy={1,7,123,456,2};auto copied=CopyFromSource(original,original.get());
 auto retained=std::static_pointer_cast<layers::SourceSurfaceImage>(std::get<RefPtr<layers::Image>>(copied));
 assert(retained->privacy==original->privacy);
 original->privacy={};copied=CopyFromSource(original,original.get());retained=std::static_pointer_cast<layers::SourceSurfaceImage>(std::get<RefPtr<layers::Image>>(copied));assert(retained->privacy.sources==1);
 gfx::swizzleSuccess=false;assert(std::holds_alternative<MediaResult>(CheckSwizzle(original,original)));gfx::swizzleSuccess=true;
 assert(std::holds_alternative<RefPtr<gfx::DataSourceSurface>>(CheckSwizzle(original,original)));
''')
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'rgbproducer.cpp';src.write_text(code);exe=Path(d)/'rgbproducer'
   subprocess.run(['c++','-std=c++17','-I',str(ROOT/'firefox-src/gfx/2d'),str(src),'-o',str(exe)],check=True)
   subprocess.run([str(exe)],check=True)

class AuthoredRGBExplicitConversion(unittest.TestCase):
 def test_actual_rgb_conversion_unpremultiplies_only_verified_rendered_author_copy(self):
  source=(ROOT/'firefox-src/dom/media/ImageConversion.cpp').read_text()
  start=source.index('  const bool canonicalSource = gfx::CanImportCanonicalCanvasPixels(')
  end=source.index('\n}\n',start)
  branch=source[start:end]
  code=r'''
#include <cassert>
#include <memory>
#include <array>
#include <cstdint>
using nsresult=int;constexpr int NS_OK=0,NS_ERROR_FAILURE=1;
template<class T>using RefPtr=std::shared_ptr<T>;
struct SourceSurface{std::array<uint8_t,4>data;bool canonical=false;bool opaque=false;auto GetSize(){return 1;}bool GetFormat(){return opaque;}};
namespace gfx{
inline int unpremul=0,swizzle=0;inline bool succeeds=true;
bool GetCanvasPrivacyMetadata(SourceSurface*p){return p->canonical;}
bool CanImportCanonicalCanvasPixels(bool canonical){return canonical;}
bool UnpremultiplyData(uint8_t*src,int,bool,uint8_t*dest,int,bool opaque,int){
 unpremul++;if(!succeeds)return false;for(unsigned c=0;c<3;c++)dest[c]=src[3]?(unsigned(src[c])*255+src[3]/2)/src[3]:0;dest[3]=opaque?255:src[3];return true;
}
bool SwizzleData(uint8_t*src,int,bool,uint8_t*dest,int,bool opaque,int){swizzle++;if(!succeeds)return false;for(unsigned c=0;c<4;c++)dest[c]=src[c];if(opaque)dest[3]=255;return true;}
}
struct Image{RefPtr<SourceSurface>original;auto GetOriginalAuthoredBufferSurface(){return original;}};
struct Map{SourceSurface*p;uint8_t*GetData(){return p->data.data();}int GetStride(){return 4;}};
nsresult Convert(Image*aImage,RefPtr<SourceSurface>surf,RefPtr<SourceSurface>dest,bool*aOutCanonicalConversion){
 if(aOutCanonicalConversion)*aOutCanonicalConversion=false;
 auto src=surf;Map srcMap{src.get()},destMap{dest.get()};
'''+branch+r'''
}
int main(){
 auto src=std::make_shared<SourceSurface>();src->data={64,32,16,128};src->canonical=true;
 auto dest=std::make_shared<SourceSurface>();Image authored{src};bool proof=false;
 assert(Convert(&authored,src,dest,&proof)==NS_OK&&proof&&gfx::unpremul==1);
 assert((dest->data==std::array<uint8_t,4>{128,64,32,128}));
 dest->opaque=true;assert(Convert(&authored,src,dest,&proof)==NS_OK&&proof);
 assert((dest->data==std::array<uint8_t,4>{128,64,32,255}));
 src->canonical=false;dest->opaque=false;assert(Convert(&authored,src,dest,&proof)==NS_OK&&!proof&&gfx::swizzle==1);
 assert(dest->data==src->data);
 src->canonical=true;Image native;assert(Convert(&native,src,dest,&proof)==NS_OK&&proof&&gfx::swizzle==2);
 assert(dest->data==src->data);
 gfx::succeeds=false;proof=true;assert(Convert(&authored,src,dest,&proof)==NS_ERROR_FAILURE&&!proof);
}
'''
  with tempfile.TemporaryDirectory()as d:
   src=Path(d)/'alpha.cpp';src.write_text(code);exe=Path(d)/'alpha'
   subprocess.run(['c++','-std=c++17',str(src),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
