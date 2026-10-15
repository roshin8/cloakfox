#include "CloakfoxGeometry.hpp"
#include <cassert>
#include <vector>

struct Rect {
  double x=0,y=0,w=0,h=0;
  double X() const {return x;} double Y() const {return y;}
  double Width() const {return w;} double Height() const {return h;}
  void SetRect(float a,float b,float c,float d) {x=a;y=b;w=c;h=d;}
  void SetX(double a){x=a;} void SetY(double a){y=a;}
  void SetWidth(double a){w=a;} void SetHeight(double a){h=a;}
  bool operator==(const Rect& other) const {return x==other.x&&y==other.y&&w==other.w&&h==other.h;}
};
struct List {
  std::vector<Rect> rects;
  uint32_t Length() const {return rects.size();}
  Rect* Item(uint32_t i) {return &rects[i];}
};
// The old Mac/Clang call evaluated n() left to right. Spell that sequence
// explicitly: C++ does not prescribe argument evaluation order across compilers.
Rect OriginalMacSequence(Rect rect,uint32_t seed) {
  auto n=[&seed](){seed=seed*1664525u+1013904223u;return (static_cast<float>(seed)/4294967295.0f-0.5f)*0.4f;};
  const float x=n(),y=n(),width=n(),height=n();
  rect.SetRect(static_cast<float>(rect.X())+x,static_cast<float>(rect.Y())+y,
               static_cast<float>(rect.Width())+width,static_cast<float>(rect.Height())+height);
  return rect;
}
int main() {
  for(uint32_t seed: {1u,12345u,54321u,0xffffffffu}) {
    CloakfoxGeometry::Presentation noise(seed);
    Rect zero;noise.Apply(&zero);assert(zero==Rect{});
    Rect positioned{19,27,0,0};noise.Apply(&positioned);assert(positioned.w==0&&positioned.h==0);assert(positioned.x!=19||positioned.y!=27);
    Rect caret{71.65,180.4,0,22};noise.Apply(&caret);assert(caret.w==0&&caret.h>=0);
    Rect horizontal{19,27,12,0};noise.Apply(&horizontal);assert(horizontal.h==0&&horizontal.w>=0);
    Rect tiny{3,7,.00001,.00001};noise.Apply(&tiny);assert(tiny.w>=0&&tiny.h>=0);
    Rect original{40,180.4,126.1,22},copy=original;
    noise.Apply(&copy);assert(copy==OriginalMacSequence(original,seed)); // unchanged nonempty amplitude and seed sequence
    Rect repeat=original;noise.Apply(&repeat);assert(copy==repeat);
    Rect other=original;CloakfoxGeometry::Presentation(seed^0x8123).Apply(&other);assert(!(copy==other));
    List list{{original,{40,203.2,106.06,22},{40,226,89.73,22},{40,248.8,37.45,22}}};
    for(auto& rect:list.rects) noise.Apply(&rect);
    Rect bounding;CloakfoxGeometry::BoundingFromClientRects(&list,&bounding);
    assert(bounding.x==list.rects[0].x&&bounding.y==list.rects[0].y);
    assert(bounding.x+bounding.w==list.rects[0].x+list.rects[0].w);
    assert(bounding.y+bounding.h==list.rects[3].y+list.rects[3].h);
    // List order cannot affect output coordinates or its nonempty union.
    std::reverse(list.rects.begin(),list.rects.end());Rect reverse;
    CloakfoxGeometry::BoundingFromClientRects(&list,&reverse);assert(reverse==bounding);
    List empty{{{9,12,0,5},{23,29,7,0}}};Rect first;
    CloakfoxGeometry::BoundingFromClientRects(&empty,&first);assert(first==empty.rects[0]);
    List mixed{{{300,300,0,100},{40,50,10,20},{-300,-300,20,0}}};Rect middle;
    CloakfoxGeometry::BoundingFromClientRects(&mixed,&middle);assert(middle==mixed.rects[1]);
    List none;Rect noBound;CloakfoxGeometry::BoundingFromClientRects(&none,&noBound);assert(noBound==Rect{});
  }
}
