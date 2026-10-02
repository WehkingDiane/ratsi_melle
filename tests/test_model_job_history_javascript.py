"""Execute history refresh against transient failure and pruned records."""
from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.mark.integration
def test_history_refresh_handles_failure_recovery_and_pruning():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    script = Path(__file__).resolve().parents[1] / 'web/core/static/core/js/model_job_history.js'
    harness = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function element() {
  return {children: [], textContent: '', hidden: false,
    appendChild(node) { this.children.push(node); },
    replaceChildren() { this.children = []; }};
}
const last = element(), active = element(), feedback = element();
const card = {getAttribute: () => 'check_embedding_models',
  querySelector: selector => selector.includes('last') ? last : active};
const panel = {getAttribute: () => '/daten/model-jobs/status/',
  querySelector: () => feedback, querySelectorAll: () => [card]};
let refresh, failed = false, history;
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), {
  document: {getElementById: () => panel, createElement: element, addEventListener: () => {}},
  window: {setInterval: callback => {refresh = callback;}},
  fetch: async () => ({ok: !failed, json: async () => ({history})}),
});
(async () => {
  history = {available: true, entries: [{scope: 'check_embedding_models', active: [], last_finished: {
    job_id: 'id/encoded', status_label: 'Fehler', result: 'inkompatibel',
    association_label: 'Historisches Ergebnis', models_dir: '<img src=x>', manifest_sha256: 'old'}}]};
  await refresh();
  assert.equal(last.children[2].textContent, 'Modellverzeichnis: <img src=x>');
  assert.equal(last.children[4].href, '/daten/jobs/id%2Fencoded/');
  assert.equal(feedback.hidden, true);
  failed = true;
  await refresh();
  assert.equal(feedback.hidden, false);
  assert.equal(last.children.length, 5);
  failed = false;
  history = {available: true, entries: [{scope: 'check_embedding_models', last_finished: null,
    active: [{job_id: 'active', status_label: 'Läuft', progress: {message: 'Unbekannter Prozentfortschritt'}}]}]};
  await refresh();
  assert.equal(last.children.length, 1);
  assert.equal(last.children[0].textContent, 'Kein gespeichertes Prüfergebnis.');
  assert.equal(active.children.length, 2);
  assert.equal(feedback.hidden, true);
  history.entries = [];
  await refresh();
  assert.equal(active.children.length, 0);
})().catch(error => { console.error(error); process.exit(1); });
"""
    subprocess.run([node, '-e', harness, str(script)], check=True, capture_output=True, text=True)
