"""AVIF row padding is carried by stride, never per-pixel skip."""
from pathlib import Path
import re,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class AVIFSkips(unittest.TestCase):
 def test_actual_dav1d_aom_assignments(self):
  s=(ROOT/'firefox-src/image/decoders/nsAVIFDecoder.cpp').read_text()
  blocks=re.findall(r'data->m(?:Y|Cb|Cr)Skip\s*=.*?;',s,re.S)
  self.assertEqual(len(blocks),6)
  cpp=r'''#include <cassert>
struct Data{int mYSkip=1,mCbSkip=1,mCrSkip=1;}d,*data=&d;
struct Picture{int stride[2]={48,32};struct{int w=17;}p;}pic,*aPicture=&pic;
struct Color{int stride[3]={48,32,32};int d_w=17;}img,*colorImage=&img;
constexpr int AOM_PLANE_Y=0,AOM_PLANE_U=1,AOM_PLANE_V=2;
int aom_img_plane_width(Color*c,int plane){return plane==0?c->d_w:(c->d_w+1)/2;}
int main(){
'''+''.join(blocks[:3])+r'''assert(data->mYSkip==0&&data->mCbSkip==0&&data->mCrSkip==0);
'''+''.join(blocks[3:])+r'''assert(data->mYSkip==0&&data->mCbSkip==0&&data->mCrSkip==0);}
'''
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'avif.cpp';p.write_text(cpp);exe=Path(d)/'avif';subprocess.run(['c++','-std=c++17',str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
