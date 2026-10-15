#!/usr/bin/env python3
"""Exercise the real separately built CPU Vulkan EGL producer, outside Gecko.

This proves dependency operation only. Installed browser/sandbox/transfer probes
are independently required; this report does not qualify canvas provenance.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path


def probe(directory):
    C.CDLL(str(directory / 'libGLESv2_cloakfox_canonical.dylib'), mode=C.RTLD_LOCAL)
    egl = C.CDLL(str(directory / 'libEGL_cloakfox_canonical.dylib'), mode=C.RTLD_LOCAL)

    def bind(name, result, *args):
        fn = getattr(egl, name)
        fn.restype, fn.argtypes = result, args
        return fn

    get_proc = bind('eglGetProcAddress', C.c_void_p, C.c_char_p)

    def gl(name, result, *args):
        addr = get_proc(name.encode())
        assert addr, name
        return C.CFUNCTYPE(result, *args)(addr)

    get_display = bind('eglGetPlatformDisplay', C.c_void_p, C.c_uint, C.c_void_p, C.POINTER(C.c_ssize_t))
    attrs = (C.c_ssize_t * 5)(0x3203, 0x3450, 0x3209, 0x3487, 0x3038)
    display = get_display(0x3202, None, attrs)
    assert display, 'explicit Vulkan/SwiftShader display unavailable'
    initialize = bind('eglInitialize', C.c_uint, C.c_void_p, C.POINTER(C.c_int), C.POINTER(C.c_int))
    major, minor = C.c_int(), C.c_int()
    assert initialize(display, C.byref(major), C.byref(minor)), 'CPU Vulkan initialization failed'
    choose = bind('eglChooseConfig', C.c_uint, C.c_void_p, C.POINTER(C.c_int), C.POINTER(C.c_void_p), C.c_int, C.POINTER(C.c_int))
    config_attrs = (C.c_int * 13)(0x3033, 1, 0x3040, 4, 0x3024, 8, 0x3023, 8, 0x3022, 8, 0x3021, 8, 0x3038)
    config, count = C.c_void_p(), C.c_int()
    assert choose(display, config_attrs, C.byref(config), 1, C.byref(count)) and count.value
    bind_api = bind('eglBindAPI', C.c_uint, C.c_uint)
    assert bind_api(0x30A0)
    create_context = bind('eglCreateContext', C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p, C.POINTER(C.c_int))
    context = create_context(display, config, None, (C.c_int * 3)(0x3098, 2, 0x3038))
    assert context, 'ES2 context creation failed'
    create_surface = bind('eglCreatePbufferSurface', C.c_void_p, C.c_void_p, C.c_void_p, C.POINTER(C.c_int))
    surface = create_surface(display, config, (C.c_int * 5)(0x3057, 32, 0x3056, 32, 0x3038))
    assert surface, 'pbuffer creation failed'
    make_current = bind('eglMakeCurrent', C.c_uint, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p)
    assert make_current(display, surface, surface, context)
    get_string = gl('glGetString', C.c_char_p, C.c_uint)
    renderer = get_string(0x1F01).decode()
    assert 'SwiftShader' in renderer and 'Vulkan' in renderer, renderer
    clear_color = gl('glClearColor', None, C.c_float, C.c_float, C.c_float, C.c_float)
    clear = gl('glClear', None, C.c_uint)
    read = gl('glReadPixels', None, C.c_int, C.c_int, C.c_int, C.c_int, C.c_uint, C.c_uint, C.c_void_p)
    clear_color(0.2, 0.4, 0.6, 1)
    clear(0x4000)
    pixels = (C.c_ubyte * (32 * 32 * 4))()
    read(0, 0, 32, 32, 0x1908, 0x1401, pixels)
    raw = bytes(pixels)
    assert raw == bytes([51, 102, 153, 255]) * 1024, 'opaque authored clear changed'
    # This exercises shader compilation/JIT and actual rasterization, not only
    # a driver's optimized clear command.
    create_shader = gl('glCreateShader', C.c_uint, C.c_uint)
    shader_source = gl('glShaderSource', None, C.c_uint, C.c_int, C.POINTER(C.c_char_p), C.POINTER(C.c_int))
    compile_shader = gl('glCompileShader', None, C.c_uint)
    shader_status = gl('glGetShaderiv', None, C.c_uint, C.c_uint, C.POINTER(C.c_int))
    shader_log = gl('glGetShaderInfoLog', None, C.c_uint, C.c_int, C.POINTER(C.c_int), C.c_char_p)

    def shader(kind, code):
        handle = create_shader(kind)
        text = C.c_char_p(code.encode())
        shader_source(handle, 1, C.byref(text), None)
        compile_shader(handle)
        status = C.c_int()
        shader_status(handle, 0x8B81, C.byref(status))
        log = C.create_string_buffer(4096)
        shader_log(handle, len(log), None, log)
        assert status.value, log.value.decode()
        return handle

    vertex = shader(0x8B31, 'attribute vec2 p; void main(){ gl_Position=vec4(p,0.0,1.0); }')
    fragment = shader(0x8B30, 'precision highp float; void main(){ gl_FragColor=vec4(gl_FragCoord.x/32.0,gl_FragCoord.y/32.0,0.25,1.0); }')
    program = gl('glCreateProgram', C.c_uint)()
    attach = gl('glAttachShader', None, C.c_uint, C.c_uint)
    attach(program, vertex)
    attach(program, fragment)
    gl('glBindAttribLocation', None, C.c_uint, C.c_uint, C.c_char_p)(program, 0, b'p')
    gl('glLinkProgram', None, C.c_uint)(program)
    status = C.c_int()
    gl('glGetProgramiv', None, C.c_uint, C.c_uint, C.POINTER(C.c_int))(program, 0x8B82, C.byref(status))
    assert status.value, 'shader program link failed'
    gl('glUseProgram', None, C.c_uint)(program)
    gl('glViewport', None, C.c_int, C.c_int, C.c_int, C.c_int)(0, 0, 32, 32)
    gl('glDisable', None, C.c_uint)(0x0BD0)  # GL_DITHER
    vertices = (C.c_float * 6)(-1, -1, 3, -1, -1, 3)
    gl('glEnableVertexAttribArray', None, C.c_uint)(0)
    gl('glVertexAttribPointer', None, C.c_uint, C.c_int, C.c_uint, C.c_ubyte, C.c_int, C.c_void_p)(0, 2, 0x1406, 0, 0, vertices)
    gl('glDrawArrays', None, C.c_uint, C.c_int, C.c_int)(4, 0, 3)
    gl('glFinish', None)()
    read(0, 0, 32, 32, 0x1908, 0x1401, pixels)
    shader_pixels = bytes(pixels)
    expected = bytes(channel for y in range(32) for x in range(32)
                     for channel in (int((x + 0.5) * 255 / 32 + 0.5), int((y + 0.5) * 255 / 32 + 0.5), 64, 255))
    assert shader_pixels == expected, 'shader raster pixels diverged from the canonical corpus'
    get_error = gl('glGetError', C.c_uint)
    assert get_error() == 0
    make_current(display, None, None, None)
    bind('eglDestroySurface', C.c_uint, C.c_void_p, C.c_void_p)(display, surface)
    bind('eglDestroyContext', C.c_uint, C.c_void_p, C.c_void_p)(display, context)
    bind('eglTerminate', C.c_uint, C.c_void_p)(display)
    return {'renderer': renderer, 'egl': [major.value, minor.value], 'opaqueClearSHA256': hashlib.sha256(raw).hexdigest(), 'shaderSHA256': hashlib.sha256(shader_pixels).hexdigest(), 'scope': 'standalone CPU Vulkan dependency, not installed browser acceptance'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=lambda p: Path(p).resolve())
    args = parser.parse_args()
    print(json.dumps(probe(args.directory), indent=2))
