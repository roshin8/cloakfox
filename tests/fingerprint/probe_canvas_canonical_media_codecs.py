"""Exercise newly bundled codecs on upstream Gecko's known video corpus.

This loads the actual build libraries. No browser installation or system decoder
is involved. CPU C dispatch and available SIMD dispatch must decode identically.
"""
from pathlib import Path
import argparse,hashlib,json,os,struct,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
def boxes(data):
 offset=0
 while offset+8<=len(data):
  length,kind=struct.unpack_from('>I4s',data,offset)
  if length<8 or offset+length>len(data):break
  yield kind,data[offset+8:offset+length]
  offset+=length
def child(data,kind):return next(value for key,value in boxes(data) if key==kind)
def first_video_sample(path):
 data=path.read_bytes()
 for kind,track in boxes(child(data,b'moov')):
  if kind!=b'trak':continue
  media=child(track,b'mdia')
  if child(media,b'hdlr')[8:12]!=b'vide':continue
  table=child(child(media,b'minf'),b'stbl')
  description=child(table,b'stsd');sizes=child(table,b'stsz');offsets=child(table,b'stco')
  size=struct.unpack_from('>I',sizes,4)[0] or struct.unpack_from('>I',sizes,12)[0]
  offset=struct.unpack_from('>I',offsets,8)[0]
  for tag,codec in [(b'avcC','h264'),(b'hvcC','hevc'),(b'av1C','libdav1d'),(b'vpcC','vp9')]:
   at=description.find(tag)
   if at<4:continue
   length=struct.unpack_from('>I',description,at-4)[0]
   extra=description[at+4:at-4+length] if tag!=b'vpcC' else b''
   return codec,extra,data[offset:offset+size]
 raise ValueError(f'No supported clear MP4 video sample: {path}')
def run(output):
 native=ROOT/'firefox-src';libraries=Path(os.environ.get('CANONICAL_CODEC_LIB_DIR',str(native/'obj-aarch64-apple-darwin/dist/bin')))
 fixtures=[native/'dom/media/webvtt/test/reftest/black.mp4',native/'dom/media/test/hevc_white_frame.mp4',native/'dom/media/test/red-48x46.mp4']
 fixtures+=sorted((native/'dom/media/test/reftest/color_quads').glob('*.mp4'))
 result={'scope':'actual bundled Mac FFVPX first-frame corpus; C versus available SIMD, not cross-host acceptance','cases':[],'libraryDirectory':str(libraries),'librarySHA256':{name:hashlib.sha256((libraries/name).read_bytes()).hexdigest() for name in ['libmozavcodec.dylib','libmozavutil.dylib']}}
 with tempfile.TemporaryDirectory() as directory:
  directory=Path(directory);exe=directory/'decode'
  subprocess.run(['c++','-std=c++17','-I',str(native/'media/ffvpx'),str(ROOT/'tests/fingerprint/native/canonical_media_decode.cpp'),'-L',str(libraries),'-lmozavcodec','-lmozavutil','-o',str(exe)],check=True)
  environment=dict(os.environ,DYLD_LIBRARY_PATH=str(libraries))
  for fixture in fixtures:
   codec,extra,packet=first_video_sample(fixture)
   (directory/'extra').write_bytes(extra);(directory/'packet').write_bytes(packet)
   command=[str(exe),codec,str(directory/'extra'),str(directory/'packet')]
   c=json.loads(subprocess.check_output([*command,'0'],env=environment,text=True))
   simd=json.loads(subprocess.check_output([*command,'-1'],env=environment,text=True))
   assert c==simd,(fixture,c,simd)
   if fixture.name=='black.mp4':assert c['lumaMin']==c['lumaMax']==16 and c['hash']=='63dcf40ec9d8b125'
   if fixture.name=='hevc_white_frame.mp4':assert c['lumaMin']==c['lumaMax']==235 and c['hash']=='76fbda93cf8df325'
   result['cases'].append({'fixture':str(fixture.relative_to(native)),**c,'cEqualsSIMD':True})
   print(f'{codec}: {fixture.name}: {c["format"]} {c["hash"]}',flush=True)
 output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
 return result
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'docs/canvas-pipeline-completion/media-codec-corpus.json');args=parser.parse_args();result=run(args.output);print(f'{len(result["cases"])} real codec corpus cases passed')
