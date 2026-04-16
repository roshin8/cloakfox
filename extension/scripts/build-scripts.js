/**
 * Build script for background, content, and inject scripts.
 * Uses esbuild to create self-contained IIFE bundles.
 *
 * Firefox MV2 loads these as classic scripts (not ES modules),
 * so they must not have any `import` statements.
 */

import { build } from 'esbuild';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, '..');

const isProduction = process.argv.includes('--production');

const commonOptions = {
  bundle: true,
  format: 'iife',
  target: 'es2020',
  sourcemap: !isProduction,
  minify: isProduction,
  define: {
    'process.env.NODE_ENV': JSON.stringify(isProduction ? 'production' : 'development'),
  },
};

async function buildScripts() {
  console.log(`Building scripts (${isProduction ? 'production' : 'development'})...`);

  try {
    // Build background script
    await build({
      ...commonOptions,
      entryPoints: [resolve(projectRoot, 'src/background/index.ts')],
      outfile: resolve(projectRoot, 'dist/background/index.js'),
      globalName: '__containerShieldBackground',
    });
    console.log('  ✓ background/index.js');

    // Build content script
    await build({
      ...commonOptions,
      entryPoints: [resolve(projectRoot, 'src/content/index.ts')],
      outfile: resolve(projectRoot, 'dist/content/index.js'),
      globalName: '__containerShieldContent',
    });
    console.log('  ✓ content/index.js');

    // Build inject script
    await build({
      ...commonOptions,
      entryPoints: [resolve(projectRoot, 'src/inject/index.ts')],
      outfile: resolve(projectRoot, 'dist/inject/index.js'),
      globalName: '__containerShieldInject',
    });
    console.log('  ✓ inject/index.js');

    console.log('Scripts build complete!');
  } catch (error) {
    console.error('Build failed:', error);
    process.exit(1);
  }
}

buildScripts();
