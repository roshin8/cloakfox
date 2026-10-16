// Owned fixture: exercise ANGLE shader compilation and rendered pixel readback.
(() => {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 8;
  const gl = canvas.getContext('webgl2', {antialias: false});
  if (!gl) throw new Error('WebGL2 unavailable');
  const shader = (type, source) => {
    const result = gl.createShader(type);
    gl.shaderSource(result, source);
    gl.compileShader(result);
    if (!gl.getShaderParameter(result, gl.COMPILE_STATUS))
      throw new Error(gl.getShaderInfoLog(result));
    return result;
  };
  const program = gl.createProgram();
  gl.attachShader(program, shader(gl.VERTEX_SHADER, `#version 300 es
    void main() {
      vec2 vertices[3] = vec2[3](vec2(-1., -1.), vec2(3., -1.), vec2(-1., 3.));
      gl_Position = vec4(vertices[gl_VertexID], 0., 1.);
    }`));
  gl.attachShader(program, shader(gl.FRAGMENT_SHADER, `#version 300 es
    precision highp float;
    out vec4 color;
    void main() { color = vec4(1., 0., 0., 1.); }`));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS))
    throw new Error(gl.getProgramInfoLog(program));
  gl.useProgram(program);
  gl.drawArrays(gl.TRIANGLES, 0, 3);
  const pixel = new Uint8Array(4);
  gl.readPixels(4, 4, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
  const debug = gl.getExtension('WEBGL_debug_renderer_info');
  const result = {pixel: Array.from(pixel), error: gl.getError(),
    renderer: debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)};
  gl.getExtension('WEBGL_lose_context')?.loseContext();
  return result;
})()
