import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(new URL('../../static/js/chatRenderer.js', import.meta.url), 'utf8');
const addSource = source.match(/export function addMessage\([^\n]+\{[\s\S]*?\n\}/)[0].replace('export ', '');

class Element {
  children = [];
  dataset = {};
  className = '';
  classList = {
    contains: name => this.className.split(' ').includes(name),
    add: name => { this.className += ` ${name}`; },
  };
  appendChild(child) { this.children.push(child); return child; }
}

function render(metadata) {
  const history = new Element(), errors = [];
  const context = vm.createContext({
    console: { error: (...args) => errors.push(args) }, window: {},
    document: { createElement: () => new Element(), getElementById: () => history },
    hideWelcomeScreen() {}, resolveDocumentPlaceholderLinks: text => text,
    markdownModule: {
      createCollapsible: (text, label) => `collapsed:${label}:${text}`,
      processWithThinking: text => text, squashOutsideCode: text => text,
    },
    buildToolNodeInnerHtml: event => `${event.tool}:${event.exit_code}`,
    replyModelPair: () => ({ actualModel: 'model', requestedModel: 'model' }),
    modelRouteLabel: () => 'model', sameModelName: () => true,
    applyModelColor() {}, roleTimestamp: () => new Element(),
    createMsgFooter: () => new Element(), displayMetrics() {},
  });
  vm.runInContext(addSource, context);
  context.addMessage('assistant', 'Final answer', 'model', metadata);
  assert.deepEqual(errors, []);
  return history.children;
}

test('tool-only rounds restore thinking, ordered receipts, failures and a primary final answer', () => {
  const nodes = render({
    thinking: 'Saved thinking', _db_id: 42,
    round_texts: ['', '', 'Final answer'],
    tool_events: [
      { round: 1, tool: 'bash', exit_code: 1 },
      { round: 2, tool: 'write_file', exit_code: 0 },
    ],
  });
  assert.equal(nodes[0].className, 'agent-thinking-summary');
  assert.equal(nodes[0].innerHTML, 'collapsed:thinking:Saved thinking');
  const thread = nodes[1];
  assert.equal(thread.children[0].innerHTML, 'bash:1');
  assert.equal(thread.children[0].classList.contains('open'), true);
  assert.equal(thread.children[1].innerHTML, 'write_file:0');
  assert.equal(thread.children[1].classList.contains('open'), false);
  const reply = nodes[2];
  assert.equal(reply.className, 'msg msg-ai');
  assert.equal(reply.dataset.raw, 'Final answer');
  assert.equal(reply.dataset.dbId, 42);
});

test('legacy tool history without round texts still displays its final answer', () => {
  const nodes = render({ tool_events: [{ round: 1, tool: 'read_file', exit_code: 0 }] });
  assert.equal(nodes.length, 2);
  assert.equal(nodes[1].dataset.raw, 'Final answer');
});
