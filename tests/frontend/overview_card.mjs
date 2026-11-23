import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';

const fixture = JSON.parse(readFileSync(0, 'utf8'));
const elements = new Map([['hui-view', class {}]]);
globalThis.window = globalThis;
globalThis.customElements = {get: name => elements.get(name), define: (name, value) => elements.set(name, value)};
const events = [];
globalThis.HTMLElement = class {
  attachShadow() {
    this.shadowRoot = {innerHTML: '', addEventListener: (name, fn) => { this[name] = fn; }};
  }
  dispatchEvent(event) { events.push(event); }
};

const url = pathToFileURL(process.argv[2]);
await import(url);
// DHF-TEST: genesis-wp-ha/requirement-31 genesis-wp-ha/ac-147
const Card = elements.get('genesis-wp-overview-card');
assert.ok(Card);
assert.ok(customCards.some(({type}) => type === 'genesis-wp-overview-card'));
const card = new Card();
assert.throws(() => card.setConfig({entry: fixture.entry, speed: 2}));
card.setConfig({entry: fixture.entry, title: 'Daily overview'});
const bands = await import(new URL('overview-bands.js', url));
for (const [name, expected] of Object.entries(fixture.bands)) assert.deepEqual(bands[name], expected);

const byRegister = Object.fromEntries(Object.entries(fixture.states).map(
  ([id, {attributes}]) => [attributes.register, id],
));
const setState = (key, state, attributes = {}) => {
  const id = byRegister[key];
  assert.ok(id, key);
  Object.assign(fixture.states[id].attributes, attributes);
  fixture.states[id].state = String(state);
};
for (const [key, value] of Object.entries({
  starts_today: 6, hot_water_starts_today: 2, short_heating_runs_today: 1,
  heating_run_minimum: 8, heating_run_mean: 45, heating_run_maximum: 140,
  running_hours_today: 7.5, heat_produced_today: 24, heat_to_rooms_today: 18.5,
  median_restart_margin_today: 1.2, buffer_judgement: 'keep', curve_gap: 2,
})) setState(`derived_${key}`, value);
setState('derived_heat_to_rooms_today', 18.5, {coverage: 80});
setState('derived_buffer_judgement', 'keep', {reference_offset: 2});

const requests = [];
const hass = {
  ...fixture,
  callService() { assert.fail('Unexpected service call'); },
  async callWS(message) {
    requests.push(message);
    const start = Date.parse(message.start_time) / 1000;
    const rows = pairs => pairs.map(([minute, s]) => ({s: String(s), lu: start + minute * 60}));
    const entity = (key, pairs) => {
      assert.ok(message.entity_ids.includes(byRegister[key]), key);
      return [byRegister[key], rows(pairs)];
    };
    return Object.fromEntries([
      entity('dinput_199', [[0, 'off'], [10, 'on'], [15, 'off'], [20, 'on'], [40, 'off'],
        [50, 'on'], [140, 'off'], [150, 'on'], [190, 'off']]),
      entity('input_1', [[0, 'heating'], [150, 'hot_water']]),
      entity('dinput_209', [[0, 'off'], [5, 'on'], [80, 'off']]),
      entity('input_41', [[0, 30], [15, 29]]),
      entity('input_12', [[0, 33], [15, 34]]),
      entity('input_147', [[0, 32], [15, 31]]),
      entity('input_68', [[0, 35], [15, 36]]),
      entity('derived_heat_to_rooms', Array.from({length: 1440}, (_, i) => [i, 2 + i % 2])),
    ]);
  },
};
card.hass = hass;
await new Promise(resolve => setImmediate(resolve));
const html = () => card.shadowRoot.innerHTML;
assert.match(html(), /Daily overview/);
assert.doesNotMatch(html(), /<(input|button|ha-slider)\b/);
// DHF-TEST: genesis-wp-ha/requirement-31 genesis-wp-ha/ac-148
for (const token of ['6', '2', '1', '8 min', '45 min', '140 min', '7.5 h', 'very short', 'warning', 'good',
  '#e07f52', '#d4a14d', '#5fb88a', '#d46161']) assert.ok(html().includes(token), token);
// DHF-TEST: genesis-wp-ha/requirement-31 genesis-wp-ha/ac-149
for (const token of ['24.0 kWh', '18.5 kWh', '80 %', '1.2 K', '2.0 K', 'keep', 'Curve gap']) {
  assert.ok(html().includes(token), token);
}
for (const [judgement, arrow] of [['lower', '↓'], ['raise', '↑']]) {
  setState('derived_buffer_judgement', judgement);
  card.hass = hass;
  assert.ok(html().includes(`${arrow} ${judgement}`));
}
// DHF-TEST: genesis-wp-ha/requirement-31 genesis-wp-ha/ac-150
setState('derived_heating_run_mean', 'unavailable');
setState('derived_buffer_judgement', 'unknown');
card.hass = hass;
assert.match(html(), /Heating run mean[^]*?Unavailable/);
assert.match(html(), /Unknown/);
assert.doesNotMatch(html(), /45 min|↑ raise|↓ lower/);
// DHF-TEST: genesis-wp-ha/requirement-31 genesis-wp-ha/ac-151
const segments = [...html().matchAll(/<rect[^>]*class="run"[^>]*x="([^"]+)"[^>]*width="([^"]+)"[^>]*fill="([^"]+)"/g)];
assert.equal(segments.length, 4);
assert.deepEqual(segments.map(match => match[3]), ['#d46161', '#d4a14d', '#5fb88a', 'currentColor']);
const timeAxis = html().match(/viewBox="0 0 (\d+) \d+"/);
assert.ok(timeAxis);
const width = Number(timeAxis[1]);
for (const [i, [start, duration]] of [[10, 5], [20, 20], [50, 90], [150, 40]].entries()) {
  assert.ok(Math.abs(Number(segments[i][1]) / width - start / 1440) < 0.00001);
  assert.ok(Math.abs(Number(segments[i][2]) / width - duration / 1440) < 0.00001);
}
for (const token of ['FR2', 'Buffer [°C]', 'Heat to the rooms [kW]', 'short cycle', 'very short',
  'short', 'acceptable', 'good', 'Hot water']) assert.ok(html().includes(token), token);
// DHF-TEST: genesis-wp-ha/requirement-31 genesis-wp-ha/ac-152
assert.ok(requests.length > 0);
assert.ok(requests.every(request => request.type === 'history/history_during_period'));
assert.equal(Date.parse(requests[0].end_time) - Date.parse(requests[0].start_time), 86_400_000);
const starts = byRegister.derived_starts_today;
assert.ok(html().includes(`data-entity="${starts}"`));
card.click({target: {closest: () => ({dataset: {entity: starts}})}});
assert.deepEqual(events.map(({type, detail}) => [type, detail.entityId]), [['hass-more-info', starts]]);
process.stdout.write('HARNESS-COMPLETE\n');
