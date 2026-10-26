"""Compile and exercise the shared native camera selection policy."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]

class CameraExposurePolicyTest(unittest.TestCase):
    def test_selection_limit_and_missing_camera(self):
        header=ROOT/'additions/cloakcfg/CloakfoxCameraExposure.hpp'
        self.assertTrue(header.exists(), 'Missing native camera exposure policy')
        code=r'''
#include "CloakfoxCameraExposure.hpp"
#include <cassert>
int main() {
  using J=nlohmann::json;
  J cfg={{"mediaDevices:enabled",true},{"mediaDevices:webcams",1u}};
  CloakfoxCameraExposure first(cfg);
  assert(first.AllowCamera("a")); assert(!first.AllowCamera("b"));
  cfg["mediaDevices:cameraDevice"]="b";
  CloakfoxCameraExposure chosen(cfg);
  assert(!chosen.AllowCamera("a")); assert(chosen.AllowCamera("b"));
  cfg["mediaDevices:cameraDevice"]="disconnected";
  CloakfoxCameraExposure missing(cfg);
  assert(!missing.AllowCamera("a"));assert(!missing.AllowCamera("b"));
  cfg["mediaDevices:webcams"]=0u;cfg["mediaDevices:cameraDevice"]="a";
  CloakfoxCameraExposure zero(cfg);assert(!zero.AllowCamera("a"));
  cfg["mediaDevices:webcams"]=2u;
  cfg["mediaDevices:cameraDevices"]="[\"b\",\"c\"]";
  CloakfoxCameraExposure multi(cfg);
  assert(!multi.AllowCamera("a"));assert(multi.AllowCamera("b"));assert(multi.AllowCamera("c"));
  cfg["mediaDevices:webcams"]=1u;
  CloakfoxCameraExposure reduced(cfg);
  assert(!reduced.AllowCamera("a"));assert(reduced.AllowCamera("b"));assert(!reduced.AllowCamera("c"));
  cfg["mediaDevices:cameraDevices"]="[]";
  CloakfoxCameraExposure none(cfg);assert(!none.AllowCamera("a"));
  CloakfoxCameraExposure off(J::object());
  assert(off.AllowCamera("a"));assert(off.AllowCamera("b"));
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp,'camera.cpp');src.write_text(code);binary=Path(tmp,'camera')
            subprocess.run([shutil.which('clang++') or 'c++','-std=c++17','-I',str(header.parent),str(src),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)

if __name__=='__main__':unittest.main()
