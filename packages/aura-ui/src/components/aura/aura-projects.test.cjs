const assert = require('node:assert/strict');
const fs = require('node:fs');
const Module = require('node:module');
const path = require('node:path');
const test = require('node:test');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const ts = require('typescript');

function loadProductionComponent() {
  const filename = path.join(__dirname, 'aura-projects.tsx');
  const source = fs.readFileSync(filename, 'utf8');
  const output = ts.transpileModule(source, {
    compilerOptions: {
      jsx: ts.JsxEmit.ReactJSX,
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      esModuleInterop: true,
    },
    fileName: filename,
  }).outputText;
  const loaded = new Module(filename, module);
  loaded.filename = filename;
  loaded.paths = Module._nodeModulePaths(path.dirname(filename));
  loaded._compile(output, filename);
  return loaded.exports;
}

function renderProject(project) {
  const { AuraProjects } = loadProductionComponent();
  return renderToStaticMarkup(
    React.createElement(AuraProjects, { projects: [project] }),
  );
}

test('verified project renders an accessible external GitHub link', () => {
  const html = renderProject({
    name: 'open-aura',
    summary: 'Local AI session scoring.',
    session_count: 2,
    aura_score: 8.2,
    github_url: 'https://github.com/vibelevel-ai/open-aura',
  });

  assert.match(
    html,
    /href="https:\/\/github\.com\/vibelevel-ai\/open-aura"/,
  );
  assert.match(html, /target="_blank"/);
  assert.match(html, /rel="noopener noreferrer"/);
  assert.match(html, /aria-label="Open open-aura on GitHub"/);
  assert.doesNotMatch(html, /GitHub repository unavailable/);
});

test('project without a verified URL renders a disabled gray GitHub control', () => {
  const html = renderProject({
    name: 'legacy-project',
    session_count: 1,
    aura_score: 7.4,
  });

  assert.match(html, /<button[^>]*disabled=""/);
  assert.match(html, /aria-disabled="true"/);
  assert.match(
    html,
    /aria-label="GitHub repository unavailable for legacy-project"/,
  );
  assert.match(html, /title="GitHub repository unavailable"/);
  assert.doesNotMatch(html, /<a[^>]*legacy-project/);
});
