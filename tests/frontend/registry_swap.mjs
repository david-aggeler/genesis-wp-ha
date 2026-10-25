// ac-37: the card must end up in the registry Home Assistant uses after its frontend replaces
// window.customElements (scoped-registry polyfill), and render with it. Usage: node registry_swap.mjs <card.js>
import { copyFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

class Registry {
  constructor(name) {
    this.name = name;
    this.defined = new Map();
  }
  define(tag, cls) {
    if (this.defined.has(tag)) throw new Error(`${this.name}: ${tag} already defined`);
    this.defined.set(tag, cls);
  }
  get(tag) {
    return this.defined.get(tag);
  }
}

const TAG = "genesis-wp-heating-curve-card";
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

globalThis.window = globalThis;
globalThis.HTMLElement = class { attachShadow() { this.shadowRoot = { innerHTML: "" }; return this.shadowRoot; } };
const native = new Registry("native");
globalThis.customElements = native;

await import(pathToFileURL(process.argv[2]).href);
await sleep(300);
const beforeSwap = Boolean(native.get(TAG));

const replacement = new Registry("replacement"); // HA's app swaps in its polyfill registry, then defines hui-view
globalThis.customElements = replacement;
replacement.define("hui-view", class {});
await sleep(1000);

const Card = replacement.get(TAG);
const result = {
  defined_before_hui_view: beforeSwap,
  defined_in_native: Boolean(native.get(TAG)),
  defined_in_replacement: Boolean(Card),
  custom_cards: (window.customCards || []).filter((c) => c.type === TAG).length,
};
if (Card) {
  const card = new Card();
  card.setConfig({ entity: "sensor.hc1" });
  const curve = [[17, 23], [10, 28], [5, 30], [0, 33], [-5, 35], [-15, 40], [-25, 44]];
  card.hass = { states: { "sensor.hc1": { state: "29.0", attributes: { curve, outdoor_temperature: 7.5 } } } };
  const html = card.shadowRoot.innerHTML;
  result.dots = (html.match(/class="dot"/g) || []).length;
  result.markers = (html.match(/class="now"/g) || []).length;
  result.x_label = html.includes("outdoor temperature [°C]");
  result.y_label = html.includes("supply temperature [°C]");
}
// A module that runs after the swap defines immediately, into the current registry, once.
const late = new Registry("late");
late.define("hui-view", class {});
globalThis.customElements = late;
const copy = join(mkdtempSync(join(tmpdir(), "card-")), "late.js"); // a second, uncached module instance
copyFileSync(process.argv[2], copy);
await import(pathToFileURL(copy).href);
result.late_defined_immediately = Boolean(late.get(TAG));
console.log(JSON.stringify(result));
process.exit(0);
