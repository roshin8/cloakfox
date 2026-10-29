/* Native execution checks for a disposable observed-profile test context.
 * Runs in windows and workers with the normal readback privacy policy intact.
 * No detector hashes or fixture-specific production behavior are involved.
 */
function observedGpuExecution() {
  const result = {checks: [], contexts: []};
  for (const kind of ['webgl', 'webgl2']) {
    const row = {kind, checks: [], pixels: {}};
    result.contexts.push(row);
    const check = (name, pass, detail) => {
      const entry = {name: `${kind}: ${name}`, pass: Boolean(pass)};
      if (detail !== undefined) entry.detail = detail;
      row.checks.push(entry);
      result.checks.push(entry);
    };
    const canvas = typeof document === 'object'
      ? document.createElement('canvas') : new OffscreenCanvas(16, 16);
    canvas.width = canvas.height = 16;
    const gl = canvas.getContext(kind, {
      stencil: true, depth: false, antialias: false, preserveDrawingBuffer: true,
    });
    check('context created with stencil', gl && gl.getContextAttributes().stencil);
    if (!gl) continue;
    const gl2 = kind === 'webgl2';
    const shaders = [], programs = [], buffers = [], textures = [];
    try {
      const error = () => gl.getError();
      const noError = name => check(name, error() === gl.NO_ERROR);
      const read = () => {
        const pixel = new Uint8Array(4);
        gl.readPixels(8, 8, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
        return Array.from(pixel);
      };
      const near = (a, b) => a.length === 4 && b.length === 4 &&
        a.slice(0, 3).every((value, index) => Math.abs(value - b[index]) <= 8) &&
        a[3] === b[3];
      const shader = (type, source) => {
        const object = gl.createShader(type);
        shaders.push(object);
        gl.shaderSource(object, source);
        gl.compileShader(object);
        if (!gl.getShaderParameter(object, gl.COMPILE_STATUS)) {
          throw Error(`shader failed: ${gl.getShaderInfoLog(object)}`);
        }
        return object;
      };
      const vertex = shader(gl.VERTEX_SHADER, gl2 ? `#version 300 es
in vec2 p; out vec2 uv;
void main(){uv=(p+1.)*.5;gl_Position=vec4(p,0.,1.);}` : `
attribute vec2 p; varying vec2 uv;
void main(){uv=(p+1.)*.5;gl_Position=vec4(p,0.,1.);}`);
      const program = (body, declarations = '', extension = '') => {
        const fragment = shader(gl.FRAGMENT_SHADER, (gl2 ? '#version 300 es\n' : '') +
          extension + '\nprecision highp float;\n' +
          (gl2 ? 'in vec2 uv;out vec4 outputColor;\n' : 'varying vec2 uv;\n') +
          declarations + '\nvoid main(){' +
          (gl2 ? 'outputColor=' : 'gl_FragColor=') + body + ';}');
        const object = gl.createProgram();
        programs.push(object);
        gl.attachShader(object, vertex);
        gl.attachShader(object, fragment);
        gl.bindAttribLocation(object, 0, 'p');
        gl.linkProgram(object);
        if (!gl.getProgramParameter(object, gl.LINK_STATUS)) {
          throw Error(`program failed: ${gl.getProgramInfoLog(object)}`);
        }
        return object;
      };
      const vertices = gl.createBuffer();
      buffers.push(vertices);
      gl.bindBuffer(gl.ARRAY_BUFFER, vertices);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
      gl.enableVertexAttribArray(0);
      gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
      gl.viewport(0, 0, 16, 16);
      gl.disable(gl.DITHER);
      const solid = program('color', 'uniform vec4 color;');
      gl.useProgram(solid);
      const solidColor = gl.getUniformLocation(solid, 'color');
      const paint = color => {
        gl.uniform4fv(solidColor, color);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
      };

      const defaults = [gl.STENCIL_VALUE_MASK, gl.STENCIL_BACK_VALUE_MASK,
        gl.STENCIL_WRITEMASK, gl.STENCIL_BACK_WRITEMASK].map(p => gl.getParameter(p));
      check('observed stencil initial state', defaults.every(mask => mask === 0x7fffffff), defaults);
      gl.stencilFuncSeparate(gl.FRONT, gl.ALWAYS, 0, 0x13579bdf);
      gl.stencilFuncSeparate(gl.BACK, gl.ALWAYS, 0, 0x2468ace0);
      gl.stencilMaskSeparate(gl.FRONT, 0x89abcdef);
      gl.stencilMaskSeparate(gl.BACK, 0x12345678);
      const authored = [gl.STENCIL_VALUE_MASK, gl.STENCIL_BACK_VALUE_MASK,
        gl.STENCIL_WRITEMASK, gl.STENCIL_BACK_WRITEMASK].map(p => gl.getParameter(p));
      check('separate authored stencil masks remain mutable',
        authored.every((value, i) => value === [0x13579bdf, 0x2468ace0, 0x89abcdef, 0x12345678][i]), authored);
      gl.stencilFunc(gl.ALWAYS, 0, 0xffffffff);
      gl.stencilMask(0xffffffff);
      check('authored all-ones stencil masks are retained',
        [gl.STENCIL_VALUE_MASK, gl.STENCIL_BACK_VALUE_MASK,
          gl.STENCIL_WRITEMASK, gl.STENCIL_BACK_WRITEMASK]
          .every(p => gl.getParameter(p) === 0xffffffff));
      gl.clearColor(0, 0, 0, 1);
      gl.clearStencil(0);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.STENCIL_BUFFER_BIT);
      gl.enable(gl.STENCIL_TEST);
      gl.stencilFunc(gl.ALWAYS, 5, 0xff);
      gl.stencilOp(gl.KEEP, gl.KEEP, gl.REPLACE);
      gl.colorMask(false, false, false, false);
      paint([1, 0, 0, 1]);
      gl.colorMask(true, true, true, true);
      gl.stencilOp(gl.KEEP, gl.KEEP, gl.KEEP);
      gl.stencilFunc(gl.EQUAL, 5, 0xff);
      paint([0, 1, 0, 1]);
      row.pixels.stencilAccepted = read();
      gl.stencilFunc(gl.EQUAL, 6, 0xff);
      paint([0, 0, 1, 1]);
      row.pixels.stencilRejected = read();
      check('stencil reference controls native fragments',
        near(row.pixels.stencilAccepted, [0, 255, 0, 255]) &&
        near(row.pixels.stencilRejected, row.pixels.stencilAccepted), row.pixels.stencilAccepted);
      gl.stencilMask(0);
      gl.stencilFunc(gl.ALWAYS, 6, 0xff);
      gl.stencilOp(gl.KEEP, gl.KEEP, gl.REPLACE);
      gl.colorMask(false, false, false, false);
      paint([1, 0, 0, 1]);
      gl.colorMask(true, true, true, true);
      gl.stencilFunc(gl.EQUAL, 5, 0xff);
      gl.stencilOp(gl.KEEP, gl.KEEP, gl.KEEP);
      paint([1, 1, 0, 1]);
      row.pixels.stencilWriteDisabled = read();
      check('zero stencil write mask prevents native update',
        near(row.pixels.stencilWriteDisabled, [255, 255, 0, 255]), row.pixels.stencilWriteDisabled);
      gl.stencilMask(0xff);
      gl.stencilFunc(gl.ALWAYS, 6, 0xff);
      gl.stencilOp(gl.KEEP, gl.KEEP, gl.REPLACE);
      gl.colorMask(false, false, false, false);
      paint([1, 0, 0, 1]);
      gl.colorMask(true, true, true, true);
      gl.stencilFunc(gl.EQUAL, 6, 0xff);
      gl.stencilOp(gl.KEEP, gl.KEEP, gl.KEEP);
      paint([0, 0, 1, 1]);
      row.pixels.stencilWriteEnabled = read();
      check('restored stencil write mask updates native fragments',
        near(row.pixels.stencilWriteEnabled, [0, 0, 255, 255]), row.pixels.stencilWriteEnabled);
      // WebGL requires equal effective front/back masks and references at draw
      // time. Comparison functions may differ: front NEVER and back ALWAYS/
      // EQUAL prove this reversed triangle actually uses the back-face state.
      gl.stencilMask(0xff);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.STENCIL_BUFFER_BIT);
      gl.frontFace(gl.CW);
      gl.stencilMaskSeparate(gl.FRONT, 0xff);
      gl.stencilMaskSeparate(gl.BACK, 0xff);
      gl.stencilFuncSeparate(gl.FRONT, gl.NEVER, 9, 0xff);
      gl.stencilFuncSeparate(gl.BACK, gl.ALWAYS, 9, 0xff);
      gl.stencilOp(gl.KEEP, gl.KEEP, gl.REPLACE);
      gl.colorMask(false, false, false, false);
      paint([1, 0, 0, 1]);
      noError('back-facing stencil replacement is a legal WebGL draw');
      gl.colorMask(true, true, true, true);
      gl.stencilOp(gl.KEEP, gl.KEEP, gl.KEEP);
      gl.stencilFuncSeparate(gl.BACK, gl.EQUAL, 9, 0xff);
      paint([0, 1, 0, 1]);
      noError('back-facing stencil comparison is a legal WebGL draw');
      row.pixels.backStencilAccepted = read();
      check('back-facing fragments use the back stencil comparison and write state',
        near(row.pixels.backStencilAccepted, [0, 255, 0, 255]), row.pixels.backStencilAccepted);
      gl.stencilMaskSeparate(gl.FRONT, 0);
      gl.stencilMaskSeparate(gl.BACK, 0);
      gl.stencilFuncSeparate(gl.FRONT, gl.NEVER, 10, 0xff);
      gl.stencilFuncSeparate(gl.BACK, gl.ALWAYS, 10, 0xff);
      gl.stencilOp(gl.KEEP, gl.KEEP, gl.REPLACE);
      gl.colorMask(false, false, false, false);
      paint([1, 0, 0, 1]);
      noError('zero back stencil write mask is a legal WebGL draw');
      gl.colorMask(true, true, true, true);
      gl.stencilOp(gl.KEEP, gl.KEEP, gl.KEEP);
      gl.stencilFuncSeparate(gl.FRONT, gl.NEVER, 9, 0xff);
      gl.stencilFuncSeparate(gl.BACK, gl.EQUAL, 9, 0xff);
      paint([1, 1, 0, 1]);
      noError('preserved back stencil reference is a legal WebGL draw');
      row.pixels.backStencilWriteDisabled = read();
      check('zero stencil write mask prevents native update on back-facing fragments',
        near(row.pixels.backStencilWriteDisabled, [255, 255, 0, 255]), row.pixels.backStencilWriteDisabled);
      gl.frontFace(gl.CCW);
      gl.disable(gl.STENCIL_TEST);
      noError('native stencil rendering has no GL errors');

      const mipColors = [[240, 32, 32], [32, 224, 32], [32, 32, 224],
        [224, 224, 32], [224, 32, 224], [32, 224, 224], [224, 96, 32],
        [96, 32, 224], [128, 128, 128]];
      const texture = gl.createTexture();
      textures.push(texture);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, texture);
      for (let level = 0; level < 9; ++level) {
        const size = 256 >> level;
        const data = new Uint8Array(size * size * 4);
        for (let i = 0; i < data.length; i += 4) data.set([...mipColors[level], 255], i);
        gl.texImage2D(gl.TEXTURE_2D, level, gl.RGBA, size, size, 0, gl.RGBA, gl.UNSIGNED_BYTE, data);
      }
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST_MIPMAP_NEAREST);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      const sample = gl2 ? 'texture' : 'texture2D';
      const sampleProj = gl2 ? 'textureProj' : 'texture2DProj';
      const textureUniforms = 'uniform sampler2D t;uniform float bias;';
      const dynamic = program(`${sample}(t,uv,bias)`, textureUniforms);
      const render = (object, bias = 0) => {
        gl.useProgram(object);
        gl.uniform1i(gl.getUniformLocation(object, 't'), 0);
        gl.uniform1f(gl.getUniformLocation(object, 'bias'), bias);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
        return read();
      };
      row.pixels.positiveAt = render(dynamic, 2);
      row.pixels.positiveAbove = render(dynamic, 8);
      row.pixels.negativeAt = render(dynamic, -2);
      row.pixels.negativeAbove = render(dynamic, -8);
      check('positive dynamic bias clamps native mip selection at two',
        near(row.pixels.positiveAt, [...mipColors[6], 255]) &&
        near(row.pixels.positiveAbove, row.pixels.positiveAt), row.pixels.positiveAbove);
      check('negative dynamic bias clamps native mip selection at minus two',
        near(row.pixels.negativeAt, [...mipColors[2], 255]) &&
        near(row.pixels.negativeAbove, row.pixels.negativeAt), row.pixels.negativeAbove);
      for (const [name, expression] of [
        ['constant', `${sample}(t,uv,8.)`],
        ['projective', `${sampleProj}(t,vec3(uv,1.),bias)`],
        ...(gl2 ? [
          ['offset', 'textureOffset(t,uv,ivec2(0),bias)'],
          ['projective offset', 'textureProjOffset(t,vec3(uv,1.),ivec2(0),bias)'],
        ] : []),
      ]) {
        const pixel = render(program(expression, textureUniforms), 8);
        row.pixels[name] = pixel;
        check(`${name} bias reaches the same capped mip`, near(pixel, row.pixels.positiveAt), pixel);
      }
      const sideEffect = program('sampleOnce()',
        textureUniforms + `float calls=0.;float takeBias(){calls+=1.;return bias;}
vec4 sampleOnce(){vec4 c=${sample}(t,uv,takeBias());return vec4(c.rgb,calls==1.?1.:0.);}`);
      row.pixels.sideEffect = render(sideEffect, 8);
      check('bias expression executes once during native rendering',
        near(row.pixels.sideEffect, row.pixels.positiveAt), row.pixels.sideEffect);
      const lodExtension = gl2 ? true : gl.getExtension('EXT_shader_texture_lod');
      check('explicit LOD execution is available', Boolean(lodExtension));
      if (lodExtension) {
        const explicit = program(gl2 ? 'textureLod(t,uv,8.)' : 'texture2DLodEXT(t,uv,8.)',
          textureUniforms, gl2 ? '' : '#extension GL_EXT_shader_texture_lod : require\n');
        row.pixels.explicitLod = render(explicit);
        check('explicit LOD remains uncapped and reaches mip eight',
          near(row.pixels.explicitLod, [...mipColors[8], 255]) &&
          !near(row.pixels.explicitLod, row.pixels.positiveAt), row.pixels.explicitLod);
      }
      if (gl2) check('max element index describes the non-restart bound',
        gl.getParameter(gl.MAX_ELEMENT_INDEX) === 0xfffffffe);
      if (gl2) {
        gl.useProgram(solid);
        gl.uniform4fv(solidColor, [0, 1, 0, 1]);
        const indices = gl.createBuffer();
        buffers.push(indices);
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indices);
        gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,
          new Uint32Array([0xffffffff, 0, 1, 2, 0xffffffff]), gl.STATIC_DRAW);
        for (const [name, draw] of [
          ['drawElements', () => gl.drawElements(gl.TRIANGLES, 5, gl.UNSIGNED_INT, 0)],
          ['drawRangeElements', () => gl.drawRangeElements(gl.TRIANGLES, 0, 2, 5, gl.UNSIGNED_INT, 0)],
          ['drawElementsInstanced', () => gl.drawElementsInstanced(gl.TRIANGLES, 5, gl.UNSIGNED_INT, 0, 1)],
        ]) {
          gl.clear(gl.COLOR_BUFFER_BIT);
          draw();
          const pixel = read();
          row.pixels[name] = pixel;
          check(`${name} retains legal uint32 fixed restart`,
            error() === gl.NO_ERROR && near(pixel, [0, 255, 0, 255]), pixel);
        }
        gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint32Array([0xffffffff]), gl.STATIC_DRAW);
        gl.clear(gl.COLOR_BUFFER_BIT);
        gl.drawElements(gl.POINTS, 1, gl.UNSIGNED_INT, 0);
        const pixel = read();
        row.pixels.restartOnly = pixel;
        check('restart-only indices produce no fragments without errors',
          error() === gl.NO_ERROR && near(pixel, [0, 0, 0, 255]), pixel);
      }
      noError('native bias execution has no GL errors');
    } catch (error) {
      row.error = String(error);
      check('native execution completed', false, row.error);
    } finally {
      for (const object of programs) gl.deleteProgram(object);
      for (const object of shaders) gl.deleteShader(object);
      for (const object of buffers) gl.deleteBuffer(object);
      for (const object of textures) gl.deleteTexture(object);
      gl.getExtension('WEBGL_lose_context')?.loseContext();
    }
  }
  return result;
}
