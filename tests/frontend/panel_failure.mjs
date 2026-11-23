import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';

globalThis.window = globalThis;
globalThis.HTMLElement = class {
  attachShadow() {
    this.shadowRoot = {innerHTML: ''};
    return this.shadowRoot;
  }
};
const elements = new Map([['hui-view', class {}]]);
globalThis.customElements = {
  get: (name) => elements.get(name),
  define: (name, element) => elements.set(name, element),
};

await import(pathToFileURL(process.argv[2]));
const Panel = customElements.get('genesis-wp-panel');
assert.ok(Panel, 'The panel element must be defined after a dependency failure');
const panel = new Panel();
panel.hass = {};
assert.match(
  panel.shadowRoot.innerHTML,
  /Genesis WP panel failed to load\. Reload the page with Ctrl\+Shift\+R \(on a phone, clear the app cache\)/,
);
console.log('HARNESS-COMPLETE');
