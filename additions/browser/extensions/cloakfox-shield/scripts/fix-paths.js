/**
 * Fix paths in HTML files for browser extension compatibility
 *
 * Vite generates paths relative to the source location, but we move
 * the HTML files to different locations. This script fixes the paths.
 */

import { readFileSync, writeFileSync, readdirSync } from 'fs';
import { join } from 'path';

const distDir = 'dist';

// Fix paths in popup HTML (moved from dist/src/popup to dist/popup)
function fixPopupPaths() {
  const popupHtml = join(distDir, 'popup', 'index.html');

  try {
    let content = readFileSync(popupHtml, 'utf-8');

    // Fix paths: ../../popup/index.js -> ./index.js
    content = content.replace(/\.\.\/\.\.\/popup\//g, './');
    // Fix paths: ../../chunks/ -> ../chunks/
    content = content.replace(/\.\.\/\.\.\/chunks\//g, '../chunks/');
    // Fix paths: ../../assets/ -> ../assets/
    content = content.replace(/\.\.\/\.\.\/assets\//g, '../assets/');

    writeFileSync(popupHtml, content);
    console.log('Fixed paths in popup/index.html');
  } catch (e) {
    console.log('No popup HTML to fix or error:', e.message);
  }
}

// Fix paths in pages HTML (moved from dist/src/pages to dist/pages)
function fixPagePaths() {
  const pagesDir = join(distDir, 'pages');

  try {
    const files = readdirSync(pagesDir).filter(f => f.endsWith('.html'));

    for (const file of files) {
      const filePath = join(pagesDir, file);
      let content = readFileSync(filePath, 'utf-8');

      // Fix paths: ../../pages/ -> ./
      content = content.replace(/\.\.\/\.\.\/pages\//g, './');
      // Fix paths: ../../chunks/ -> ../chunks/
      content = content.replace(/\.\.\/\.\.\/chunks\//g, '../chunks/');
      // Fix paths: ../../assets/ -> ../assets/
      content = content.replace(/\.\.\/\.\.\/assets\//g, '../assets/');
      // Fix paths: ../../test-runner.js -> ../test-runner.js (or similar root-level JS)
      content = content.replace(/\.\.\/\.\.\/([\w-]+\.js)/g, '../$1');

      writeFileSync(filePath, content);
      console.log(`Fixed paths in pages/${file}`);
    }
  } catch (e) {
    console.log('No pages to fix or error:', e.message);
  }
}

fixPopupPaths();
fixPagePaths();
console.log('Path fixing complete!');
