"""Exercise the actual ES modules with a local HTTP fixture and isolated Chromium."""
import os
import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
from threading import Thread

import pytest


CHECKS = """<output id="test-result"></output>
<script type="module">
const result = document.querySelector('#test-result');
try {
  await import('/static/app.js');
  const field = document.querySelector('#message');
  let submits = 0;
  document.querySelector('#chat-form').addEventListener('submit', () => submits++);
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  const until = async (fn, message) => {
    for (let i = 0; i < 60; i++) { if (fn()) return; await pause(25); }
    throw Error(message);
  };
  function type(value) {
    field.value = value;
    field.dispatchEvent(new Event('input', {bubbles: true}));
  }
  function key(key) {
    field.dispatchEvent(new KeyboardEvent('keydown', {key, bubbles: true, cancelable: true}));
  }
  function check(value, message) { if (!value) throw Error(message); }
  await until(() => field._slashAcWired, 'composer did not initialize');
  type('/har');
  const popup = document.querySelector('#slash-autocomplete');
  check(popup?.offsetWidth > 0 && popup.textContent.includes('/harness'), 'missing suggestion');
  key('Enter');
  const history = document.querySelector('#chat-history');
  await until(() => history.textContent.includes('admin access required'), 'Enter did not run /harness');
  check(submits === 1 && field.value === '', 'command submission count or composer reset');
  check(history.textContent.includes('2 available'), 'lost catalog on partial failure');
  type('/chats');
  key('ArrowDown');
  const selected = popup.querySelector('[aria-selected="true"]').dataset.token;
  key('Tab');
  check(selected.startsWith('/chats ') && field.value === selected + ' ' && submits === 1, 'group selection');
  type('/har');
  key('Escape');
  check(popup.style.display === 'none', 'escape did not dismiss');
  type('/fixture');
  check(popup.textContent.includes('/fixture-skill'), 'missing skill suggestion');
  type('/skill use har');
  check(popup.textContent.includes('/skill use harness'), 'missing colliding skill');
  await pause(320);
  type('/ski');
  key('Enter');
  await until(() => history.querySelector('.skill-picker'), 'missing skill picker');
  const picker = history.querySelector('.skill-picker');
  picker.style.maxWidth = '260px';
  check(picker.querySelectorAll('button').length === 2 && !picker.closest('pre'), 'catalog layout');
  check(picker.scrollWidth <= picker.clientWidth + 1, 'skill picker overflows horizontally');
  check(getComputedStyle(picker).backgroundColor === 'rgb(0, 0, 0)', 'skill picker surface');
  check([...picker.querySelectorAll('button')].every(row => row.offsetHeight >= 44 && row.scrollHeight <= row.clientHeight + 1),
        'skill row clips its contents');
  const search = picker.querySelector('input');
  search.value = 'fixture';
  search.dispatchEvent(new Event('input'));
  check(picker.querySelectorAll('button').length === 1, 'skill search');
  search.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', bubbles:true}));
  check(field.value === '/fixture-skill ' && document.activeElement === field, 'skill selection');
  await pause(320);
  type('/skills list');
  key('Enter');
  await until(() => history.querySelectorAll('.skill-picker').length === 2, 'legacy list alias');
  check(submits === 3, 'duplicate or missing command submission');
  result.textContent = 'passed';
} catch (error) { result.textContent = String(error.stack || error); }
</script>"""


class ComposerFixture(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            page = (Path(self.directory) / "index.html").read_text(encoding="utf-8")
            page = re.sub(r"<script\b[^>]*>.*?</script>", "", page, flags=re.S)
            page = re.sub(r'<link[^>]*href="https?://[^>]+>', "", page)
            body = page.replace("</body>", CHECKS + "</body>").encode()
            kind = "text/html"
        elif self.path == "/api/skills/slash-catalog":
            body = b'{"skills":[{"name":"fixture-skill","help":"Review the layout and keyboard interactions of the current page.","uses":2},{"name":"harness"}]}'
            kind = "application/json"
        elif self.path == "/api/harness/runtime":
            return self.send_error(403)
        elif self.path.startswith("/api/"):
            body = b'{}'
            kind = "application/json"
        elif self.path.startswith("/static/"):
            self.path = self.path[len("/static"):]
            return super().do_GET()
        else:
            return super().do_GET()
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.end_headers()
        self.wfile.write(body)


def test_slash_composer_keyboard_and_catalog(tmp_path):
    browser = os.getenv("CHROMIUM_BINARY") or shutil.which("chromium") or shutil.which("google-chrome")
    if not browser and os.name == "nt":
        edge = Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application/msedge.exe"
        if edge.is_file():
            browser = str(edge)
    if not browser:
        pytest.skip("Set CHROMIUM_BINARY to run the browser regression")
    static = Path(__file__).resolve().parents[1] / "static"
    with ThreadingHTTPServer(("127.0.0.1", 0), partial(ComposerFixture, directory=static)) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            run = subprocess.run([
                browser, "--headless", "--disable-gpu", "--disable-background-networking",
                "--no-first-run", f"--user-data-dir={tmp_path / 'profile'}",
                "--dump-dom", "--virtual-time-budget=5000", f"http://127.0.0.1:{server.server_port}/",
            ], capture_output=True, encoding="utf-8", errors="replace", timeout=45)
            marker = '<output id="test-result">'
            assert marker + "passed</output>" in run.stdout, run.stdout.partition(marker)[2][:900] or run.stderr[-900:]
        finally:
            server.shutdown()
            worker.join()
