import test from 'node:test';
import assert from 'node:assert/strict';
import { create, createIndicator } from '../../static/js/spinner.js';

// Minimal DOM boundary; exercise the actual shared loader and its lifecycle.
class Element {
  children = [];
  attributes = {};
  properties = {};
  style = { setProperty: (key, value) => { this.properties[key] = value; } };
  setAttribute(key, value) { this.attributes[key] = value; }
  appendChild(child) { this.children.push(child); child.parentNode = this; return child; }
  append(...children) { children.forEach(child => this.appendChild(child)); }
  removeChild(child) { this.children.splice(this.children.indexOf(child), 1); child.parentNode = null; }
}

test('legacy wave callers get a reusable loader that stops, restarts and cleans up', () => {
  const previous = globalThis.document;
  globalThis.document = { createElement: () => new Element() };
  try {
    const host = new Element();
    const spinner = create('Processing request', 'right', 'wave');
    const element = host.appendChild(spinner.createElement());
    assert.equal(element.attributes.role, 'status');
    assert.equal(element.properties['--zeph-loader-play-state'], 'paused');
    spinner.start();
    assert.equal(element.properties['--zeph-loader-play-state'], 'running');
    spinner.updateMessage('<img src=x onerror=alert(1)>');
    assert.equal(element.children[0].textContent, '<img src=x onerror=alert(1)>');
    assert.equal(element.children[0].innerHTML, undefined, 'status text must not become HTML');
    spinner.stop();
    assert.equal(element.properties['--zeph-loader-play-state'], 'paused');
    spinner.start();
    assert.equal(element.properties['--zeph-loader-play-state'], 'running');
    spinner.destroy();
    spinner.destroy();
    assert.equal(host.children.length, 0);
    assert.equal(spinner.isRunning, false);
  } finally { globalThis.document = previous; }
});

test('compact indicators preserve nine boxes and expose no decorative content to assistive technology', () => {
  const previous = globalThis.document;
  globalThis.document = { createElement: () => new Element() };
  try {
    const indicator = createIndicator(18);
    assert.equal(indicator.attributes['aria-hidden'], 'true');
    assert.equal(indicator.properties['--zeph-loader-size'], '18px');
    assert.equal(indicator.properties['--zeph-loader-scale'], '0.25');
    assert.equal(indicator.children[0].children.length, 9);
  } finally { globalThis.document = previous; }
});
