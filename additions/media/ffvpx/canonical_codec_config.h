/* MPL-2.0: generic C decoder compilation; imported source remains unchanged. */
#ifndef CLOAKFOX_CANONICAL_CODEC_CONFIG_H
#define CLOAKFOX_CANONICAL_CODEC_CONFIG_H
#include "config.h"
#undef ARCH_AARCH64
#define ARCH_AARCH64 0
#undef ARCH_ARM
#define ARCH_ARM 0
#undef ARCH_X86
#define ARCH_X86 0
#undef ARCH_X86_32
#define ARCH_X86_32 0
#undef ARCH_X86_64
#define ARCH_X86_64 0
#undef ARCH_PPC
#define ARCH_PPC 0
#undef ARCH_MIPS
#define ARCH_MIPS 0
#undef ARCH_LOONGARCH
#define ARCH_LOONGARCH 0
#undef ARCH_RISCV
#define ARCH_RISCV 0
#undef ARCH_SPARC
#define ARCH_SPARC 0
#undef ARCH_WASM
#define ARCH_WASM 0
#ifndef CONFIG_H264_D3D12VA_HWACCEL
#define CONFIG_H264_D3D12VA_HWACCEL 0
#endif
#ifndef CONFIG_HEVC_D3D12VA_HWACCEL
#define CONFIG_HEVC_D3D12VA_HWACCEL 0
#endif
#ifndef CONFIG_VVC_SEI
#define CONFIG_VVC_SEI 0
#endif
#endif
