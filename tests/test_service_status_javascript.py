"""Run the status refresh script against an isolated DOM and fake HTTP results."""

from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.integration
def test_model_refresh_clears_stale_values_and_uses_text_content():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for JavaScript execution")
    script = Path(__file__).resolve().parents[1] / "web/core/static/core/js/service_status.js"
    harness = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function element(attrs = {}) {
  const classes = new Set();
  return { textContent: '', hidden: false, disabled: false,
    getAttribute: key => attrs[key] || null,
    classList: { toggle: (key, enabled) => enabled ? classes.add(key) : classes.delete(key),
                 contains: key => classes.has(key) } };
}
const fields = [
  element({'data-model-field': 'status', 'data-model-format': 'status'}),
  element({'data-model-field': 'message'}),
  element({'data-model-field': 'components.dense_model.prepared_revision', 'data-model-empty': 'Nicht verifiziert'}),
  element({'data-model-field': 'components.dense_model.status', 'data-model-format': 'status', 'data-model-empty': 'Nicht einzeln verifiziert'}),
  element({'data-model-field': 'size_bytes', 'data-model-format': 'bytes', 'data-model-empty': 'Nicht verifiziert'}),
];
let click;
const button = element(); button.textContent = 'Modellstatus aktualisieren';
button.addEventListener = (name, handler) => { click = handler; };
const feedback = element();
const panel = { getAttribute: () => '/daten/status/',
  querySelector: selector => selector.includes('feedback') ? feedback : button,
  querySelectorAll: selector => selector === '[data-model-field]' ? fields : [] };
let models;
let failed = false;
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), {
  document: { getElementById: () => null, querySelectorAll: () => [panel], addEventListener: () => {} },
  fetch: async () => ({ok: !failed, json: async () => ({status: {embedding_models: models}})}),
});
async function refresh() { click(); await new Promise(resolve => setImmediate(resolve)); }
(async () => {
  models = {status: 'bereit', message: '<img src=x onerror=alert(1)>', size_bytes: 1024,
            components: {dense_model: {status: 'bereit', prepared_revision: 'verified-sha'}}};
  await refresh();
  assert.equal(fields[1].textContent, models.message);
  assert.equal(fields[2].textContent, 'verified-sha');
  assert(fields[3].classList.contains('status-ok'));
  assert.equal(fields[4].textContent, '1 KB');
  models = {status: 'unvollstaendig', size_bytes: null, components: {dense_model: {status: null, prepared_revision: null}}};
  await refresh();
  assert.equal(fields[0].textContent, 'unvollständig');
  assert(fields[0].classList.contains('status-warning'));
  assert.equal(fields[2].textContent, 'Nicht verifiziert');
  assert.equal(fields[3].textContent, 'Nicht einzeln verifiziert');
  assert(!fields[3].classList.contains('status-ok'));
  assert.equal(fields[4].textContent, 'Nicht verifiziert');
  models = {status: 'bereit', size_bytes: 0};
  await refresh();
  assert.equal(fields[4].textContent, '0 Bytes');
  failed = true;
  await refresh();
  assert.equal(feedback.textContent, 'Status konnte nicht aktualisiert werden.');
  assert.equal(button.disabled, false);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    result = subprocess.run([node, "-e", harness, str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
