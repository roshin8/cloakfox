"""Compile the real native timing transform and 157 container-timing getters."""
from test_upstream_hardening import ROOT, SRC, block, cpp


def test_transform_is_bounded_monotonic_and_preserves_disabled_values():
    cpp('''
#include <cassert>
#include <cmath>
#include "''' + str(ROOT / 'additions/cloakcfg/CloakfoxTiming.cpp') + '''"
int main() {
  using namespace CloakfoxTiming;
  const Key key{12345,98765};
  double previous=-1;
  for (unsigned i=0;i<100000;i++) {
    double raw=i/1000.0;
    double value=TransformTimestamp(raw,key);
    assert(value>=raw && value<raw+1);
    assert(value>=previous);previous=value;
    assert(TransformTimestamp(raw,key)==value);
    assert(TransformTimestamp(raw,Key{})==raw);
  }
  assert(TransformTimestamp(-1,key)==-1);
  auto interval=TransformInterval(10,20,key);
  assert(interval.Duration()==TransformTimestamp(20,key)-TransformTimestamp(10,key));
  assert(TransformInterval(20,10,key).Duration()==0);
  assert(TransformTimestamp(20,key)!=TransformTimestamp(20,Key{12345,98766}));
}
''')


def test_container_timing_getters_share_the_performance_presentation():
    source=(SRC/'dom/performance/PerformanceContainerTiming.cpp').read_text()
    methods='\n'.join(block(source,'DOMHighResTimeStamp PerformanceContainerTiming::'+name) for name in ('FirstRenderTime','RawStartTime','StartTime'))
    cpp('''
#include <cassert>
#include <optional>
using DOMHighResTimeStamp=double;
struct Performance {
  bool enabled=true;
  double GetReducedTimePrecisionDOMHighRes(double raw) const { return raw; }
  double PresentTimestamp(double reduced) const { return reduced+(enabled?.25:0); }
};
struct PerformanceContainerTiming {
  Performance* mPerformance;
  double mFirstRenderTime=1,mPaintTime=2;
  mutable std::optional<double> mCachedFirstRenderTime,mCachedStartTime;
  double FirstRenderTime() const;
  double StartTime() const;
  double RawStartTime() const;
};
'''+methods+'''
int main() {
  Performance p;PerformanceContainerTiming timing{&p};
  assert(timing.FirstRenderTime()==1.25);
  assert(timing.StartTime()==2.25);
  p.enabled=false;
  assert(timing.FirstRenderTime()==1.25);
  assert(timing.StartTime()==2.25);
  PerformanceContainerTiming native{&p};
  assert(native.FirstRenderTime()==1);
  assert(native.StartTime()==2);
}
''')
