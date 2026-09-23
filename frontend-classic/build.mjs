// Builds one self-contained IIFE bundle per entry into the Plone static
// resource directory.
//
// Plone's resource registry renders bundles as plain `<script src>` (there is
// no way to ask it for `type="module"`), so the entries must not be ES modules
// and must not depend on separately loaded chunks. Each entry is therefore
// built on its own in library mode with all of its dependencies inlined.

import { build } from 'vite';
import { readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const outDir = resolve(
  here,
  '../backend/src/collective/bpmproxy/browser/static'
);

// The control panel loads the BPMN modeler, the DMN modeler and the form
// playground together, so they share a single bundle instead of shipping the
// same vendor code three times.
const entries = [
  { name: 'form', entry: 'src/form.ts', global: 'collectiveBpmproxyForm' },
  { name: 'diagram', entry: 'src/diagram.ts', global: 'collectiveBpmproxyDiagram' },
  { name: 'modeler', entry: 'src/controlpanel.ts', global: 'collectiveBpmproxyModeler' },
];

const watch = process.argv.includes('--watch');

// Keep the resource directory free of output from earlier builds (renamed
// entries, hashed chunks, ...); .gitkeep is what keeps the directory in git.
const clean = async () => {
  for (const name of await readdir(outDir)) {
    if (name === '.gitkeep') continue;
    await rm(resolve(outDir, name), { recursive: true, force: true });
  }
};

const configFor = ({ name, entry, global }) => ({
  root: here,
  // Library mode does not substitute these the way an app build does, and
  // several bpmn-io dependencies read them at runtime -- without this the
  // bundle throws "process is not defined" in the browser.
  define: {
    'process.env.NODE_ENV': '"production"',
    'process.env': '{}',
  },
  // Relative URLs, so font references in the emitted CSS resolve against the
  // ++plone++collective.bpmproxy resource directory.
  base: './',
  build: {
    outDir,
    emptyOutDir: false,
    cssCodeSplit: false,
    watch: watch ? {} : null,
    lib: {
      entry: resolve(here, entry),
      formats: ['iife'],
      name: global,
      fileName: () => `${name}.js`,
    },
    rollupOptions: {
      output: {
        inlineDynamicImports: true,
        assetFileNames: (asset) =>
          asset.names?.some((n) => n.endsWith('.css'))
            ? `${name}.css`
            : '[name].[ext]',
      },
    },
  },
});

// bpmn-font and dmn-font declare EOT and SVG faces, for browsers that have not
// existed in years. Library mode inlines every asset, so those ship as data:
// URIs no engine can parse -- Chromium logs "Failed to decode downloaded font"
// for each one on every page load -- and add tens of kilobytes of base64 to the
// stylesheet. Drop the format-less EOT source browsers try to sniff, and any
// face left with nothing modern to load.
const dropLegacyFontFaces = (css) =>
  css.replace(/@font-face\s*\{[^}]*\}/g, (face) => {
    const trimmed = face.replace(
      /src:url\(data:application\/vnd\.ms-fontobject;base64,[^)]*\);/g,
      ''
    );
    return /url\((?:"|')?data:(?:font\/|application\/octet-stream)/.test(trimmed)
      ? trimmed
      : '';
  });

await clean();
for (const target of entries) {
  await build(configFor(target));
}

for (const name of await readdir(outDir)) {
  if (!name.endsWith('.css')) continue;
  const file = resolve(outDir, name);
  await writeFile(file, dropLegacyFontFaces(await readFile(file, 'utf8')));
}
