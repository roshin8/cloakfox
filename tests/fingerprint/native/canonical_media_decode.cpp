#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <vector>
extern "C" {
#include "libavcodec/avcodec.h"
#include "libavutil/cpu.h"
#include "libavutil/mem.h"
#include "libavutil/pixdesc.h"
}
std::vector<uint8_t> Read(const char *file) {
  std::ifstream in(file, std::ios::binary);
  return {std::istreambuf_iterator<char>(in), {}};
}
int main(int argc, char **argv) {
  assert(argc == 5);
  av_force_cpu_flags(atoi(argv[4]));
  auto *codec = avcodec_find_decoder_by_name(argv[1]);
  assert(codec);
  auto *ctx = avcodec_alloc_context3(codec);
  assert(ctx);
  ctx->thread_count = 1;
  ctx->flags |= AV_CODEC_FLAG_BITEXACT;
  auto extra = Read(argv[2]);
  ctx->extradata =
      (uint8_t *)av_mallocz(extra.size() + AV_INPUT_BUFFER_PADDING_SIZE);
  ctx->extradata_size = extra.size();
  memcpy(ctx->extradata, extra.data(), extra.size());
  assert(avcodec_open2(ctx, codec, nullptr) >= 0);
  auto raw = Read(argv[3]);
  auto *packet = av_packet_alloc();
  packet->data =
      (uint8_t *)av_mallocz(raw.size() + AV_INPUT_BUFFER_PADDING_SIZE);
  packet->size = raw.size();
  memcpy(packet->data, raw.data(), raw.size());
  assert(avcodec_send_packet(ctx, packet) >= 0);
  assert(avcodec_send_packet(ctx, nullptr) >= 0);
  auto *frame = av_frame_alloc();
  int err = avcodec_receive_frame(ctx, frame);
  if (err < 0) {
    char message[128];
    av_strerror(err, message, sizeof(message));
    fprintf(stderr, "%s\n", message);
    return 2;
  }
  const auto *descriptor = av_pix_fmt_desc_get(AVPixelFormat(frame->format));
  assert(descriptor);
  const unsigned depth = descriptor->comp[0].depth;
  assert(depth == 8 || depth == 10 || depth == 12 || depth == 16);
  const bool rgb = descriptor->flags & AV_PIX_FMT_FLAG_RGB;
  unsigned low = 65535, high = 0;
  uint64_t hash = 14695981039346656037ULL;
  for (int plane = 0; plane < 3; plane++) {
    int w = (!plane || rgb)
                ? frame->width
                : (frame->width + (1 << descriptor->log2_chroma_w) - 1) >>
                      descriptor->log2_chroma_w;
    int h = (!plane || rgb)
                ? frame->height
                : (frame->height + (1 << descriptor->log2_chroma_h) - 1) >>
                      descriptor->log2_chroma_h;
    for (int y = 0; y < h; y++)
      for (int x = 0; x < w; x++) {
        unsigned value = frame->data[plane][y * frame->linesize[plane] +
                                            x * (depth == 8 ? 1 : 2)];
        if (depth != 8)
          value |=
              unsigned(
                  frame->data[plane][y * frame->linesize[plane] + x * 2 + 1])
              << 8;
        hash = (hash ^ (value & 255)) * 1099511628211ULL;
        if (depth != 8)
          hash = (hash ^ (value >> 8)) * 1099511628211ULL;
        if (!plane) {
          low = std::min(low, value);
          high = std::max(high, value);
        }
      }
  }
  printf("{\"codec\":\"%s\",\"width\":%d,\"height\":%d,\"format\":\"%s\","
         "\"depth\":%u,\"range\":%d,\"primaries\":%d,\"transfer\":%d,"
         "\"lumaMin\":%u,\"lumaMax\":%u,\"hash\":\"%016llx\"}\n",
         argv[1], frame->width, frame->height, descriptor->name, depth,
         frame->color_range, frame->color_primaries, frame->color_trc, low,
         high, (unsigned long long)hash);
  av_free(packet->data);
  packet->data = nullptr;
  packet->size = 0;
  av_packet_free(&packet);
  av_frame_free(&frame);
  avcodec_free_context(&ctx);
}
