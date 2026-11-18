// requirement-25: the heating curve card's optional supply limits, heating-season stop and
// measured-supply tick. Usage: node curve_extras.mjs <genesis-wp-heating-curve-card.js>
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

class Registry {
  constructor() { this.items = new Map([["hui-view", class {}]]); }
  get(tag) { return this.items.get(tag); }
  define(tag, cls) { assert.ok(!this.items.has(tag), tag); this.items.set(tag, cls); }
}
globalThis.window = globalThis;
globalThis.HTMLElement = class { attachShadow() { this.shadowRoot = { innerHTML: "" }; return this.shadowRoot; } };
globalThis.customElements = new Registry();
await import(pathToFileURL(process.argv[2]).href);
const Card = customElements.get("genesis-wp-heating-curve-card");
assert.ok(Card);

const curve = [[17, 23], [10, 28], [5, 30], [0, 33], [-5, 35], [-15, 40], [-25, 44]];
const states = (over = {}) => ({
  "sensor.hc1": { state: "29.0", attributes: { curve, outdoor_temperature: 7.5 } },
  "number.min": { state: "15.0", attributes: {} },
  "number.max": { state: "45.0", attributes: {} },
  "number.stop": { state: "17.0", attributes: {} },
  "sensor.t33": { state: "30.5", attributes: {} },
  ...over,
});
const config = { entity: "sensor.hc1", min: "number.min", max: "number.max", stop: "number.stop", measured: "sensor.t33" };
const render = (cfg, st) => { const card = new Card(); card.setConfig(cfg); card.hass = { states: st }; return card.shadowRoot.innerHTML; };
const num = (s, attr) => Number(s.match(new RegExp(`${attr}="([-\\d.]+)"`))[1]);
const close = (a, b, label) => assert.ok(Math.abs(a - b) < 1e-6, `${label}: ${a} != ${b}`);

// DHF-TEST: genesis-wp-ha/requirement-25 genesis-wp-ha/ac-98 genesis-wp-ha/ac-99
// Independent oracle, hand-calculated: 400 x 260 chart, plot x 48..386, y 14..218.
// x axis -30..20 (step 10, the stop at 17 is inside); y axis 15..45 (step 5, from the limits).
{
  const html = render(config, states());
  const limit = (key) => html.match(new RegExp(`<line class="limit" data-limit="${key}"[^>]*>`))?.[0];
  assert.ok(limit("min") && limit("max"));
  close(num(limit("min"), "y1"), 218, "min line at 15 C");
  close(num(limit("max"), "y1"), 14, "max line at 45 C");
  const stop = html.match(/<line class="stop"[^>]*>/)?.[0];
  assert.ok(stop);
  close(num(stop, "x1"), 365.72, "stop line at 17 C outdoor");
  const tick = html.match(/<line class="measured"[^>]*>/)?.[0];
  assert.ok(tick);
  close((num(tick, "x1") + num(tick, "x2")) / 2, 301.5, "tick at the outdoor temperature 7.5 C");
  close(num(tick, "y1"), 112.6, "tick at the measured 30.5 C");
  // Operating point (7.5, 29.0) on the widened y axis.
  const now = html.match(/<circle class="now"[^>]*>/)[0];
  close(num(now, "cx"), 301.5, "operating point x"); close(num(now, "cy"), 122.8, "operating point y");
  // Limits and stop under the curve; the tick before the operating point, so the marker stays on top.
  assert.ok(html.indexOf('class="limit"') < html.indexOf('class="curve"'));
  assert.ok(html.indexOf('class="stop"') < html.indexOf('class="curve"'));
  assert.ok(html.indexOf('class="measured"') < html.indexOf('class="now"'));
  assert.match(html, /max 45 °C/); assert.match(html, /stop 17 °C/);
}

// DHF-TEST: genesis-wp-ha/requirement-25 genesis-wp-ha/ac-100
{
  // Unavailable max and measured: no max line, no tick, no substitute value.
  const html = render(config, states({ "number.max": { state: "unavailable", attributes: {} }, "sensor.t33": { state: "unknown", attributes: {} } }));
  assert.doesNotMatch(html, /data-limit="max"/);
  assert.doesNotMatch(html, /class="measured"/);
  assert.match(html, /data-limit="min"/);
  assert.match(html, /<polyline class="curve"/);
  assert.equal((html.match(/<circle class="now"/g) || []).length, 1);
  // An empty or missing entity draws nothing either.
  const gone = states(); delete gone["number.stop"]; gone["number.min"] = { state: "", attributes: {} };
  const html2 = render(config, gone);
  assert.doesNotMatch(html2, /class="stop"|data-limit="min"/);
  // No outdoor temperature: no operating point and no tick, the curve stays.
  const html3 = render(config, states({ "sensor.hc1": { state: "29.0", attributes: { curve } } }));
  assert.doesNotMatch(html3, /class="measured"|class="now"/);
  assert.match(html3, /<polyline class="curve"/);
  // A config without the optional keys renders as before: no extra elements.
  const plain = render({ entity: "sensor.hc1" }, states());
  assert.doesNotMatch(plain, /class="limit"|class="stop"|class="measured"/);
  // A malformed optional key is rejected.
  assert.throws(() => new Card().setConfig({ entity: "sensor.hc1", max: 45 }), /max must be an entity id/);
}

// The 320 px card floor still renders every element inside the plot.
{
  const card = new Card(); card.setConfig(config); card._width = 296; card.hass = { states: states() };
  const html = card.shadowRoot.innerHTML;
  const [, w, h] = html.match(/viewBox="0 0 (\d+) (\d+)"/).map(Number);
  for (const m of html.matchAll(/<line class="(limit|stop|measured)"[^>]*x1="([-\d.]+)" x2="([-\d.]+)" y1="([-\d.]+)" y2="([-\d.]+)"/g))
    for (const v of [m[2], m[3]]) assert.ok(Number(v) >= 0 && Number(v) <= w, m[0]);
  assert.ok(h >= 180);
}
console.log("ok");
process.exit(0);
