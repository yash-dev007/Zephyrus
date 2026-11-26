"""Regression: stripToolBlocks must not delete ordinary prose or code.

The old QWEN_BARE_MARKER_RE made the pipes optional, so it matched the plain
English words "end" and "assistant" anywhere in a sentence. TOOL_NARRATION_RE
also stripped ``stdout:`` / ``stderr:`` / ``exit_code:`` lines inside fenced
code. Both silently corrupted the live view, the reloaded history, and the
Copy button.

chatRenderer.js pulls in browser globals and can't be imported under node, so
the relevant source ranges are sliced out and evaluated in isolation (same
approach as test_copy_message_strips_thinking_js.py).
"""

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_HAS_NODE = shutil.which("node") is not None

pytestmark = pytest.mark.skipif(not _HAS_NODE, reason="node binary not on PATH")


def _strip(text: str) -> str:
    script = textwrap.dedent(
        r"""
        import fs from 'node:fs';

        const src = fs.readFileSync('./static/js/chatRenderer.js', 'utf8');
        const slice = (a, b) => {
          const i = src.indexOf(a);
          const j = src.indexOf(b);
          if (i < 0 || j < 0 || j <= i) throw new Error('marker not found: ' + a);
          return src.slice(i, j);
        };
        const code =
          slice('const TOOL_CALL_RE', 'async function loadExecFenceRegex') +
          slice('const XML_TOOL_CALL_RE', '// Model pricing table') +
          slice('function _mapOutsideFences', 'export function copyMessageText');

        const moduleUrl = 'data:text/javascript;base64,' + Buffer.from(code).toString('base64');
        const mod = await import(moduleUrl);
        const input = JSON.parse(process.argv[1]);
        console.log(JSON.stringify({ out: mod.stripToolBlocks(input) }));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, json.dumps(text)],
        cwd=_REPO,
        capture_output=True,
        timeout=15,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(f"node failed:\nSTDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}")
    return json.loads(result.stdout.splitlines()[-1])["out"]


def test_ordinary_words_are_preserved():
    assert _strip("Scroll to the end of the file") == "Scroll to the end of the file"
    assert _strip("I am your assistant today.") == "I am your assistant today."


def test_code_fence_content_is_preserved():
    text = "```yaml\n  stderr: true\n  exit_code: 0\n```"
    assert _strip(text) == text


def test_tool_narration_outside_a_fence_is_still_stripped():
    assert _strip("stderr: boom") == ""


def test_leaked_role_markers_on_their_own_line_are_stripped():
    assert _strip("hello\nassistant\nworld") == "hello\n\nworld"
    assert _strip("hello\n|end|\nworld") == "hello\n\nworld"


def test_unclosed_fence_is_treated_as_code():
    text = "```yaml\n  stderr: true"
    assert _strip(text) == text
