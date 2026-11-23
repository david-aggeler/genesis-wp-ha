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
    const card = this;
    let markup = '';
    this.shadowRoot = {
      set innerHTML(value) {
        markup = value;
        this.activeElement = null;
        this.output = {textContent: ''};
      },
      get innerHTML() { return markup; },
      addEventListener: (name, fn) => { card[name] = fn; },
      querySelector: () => card.shadowRoot.output,
      querySelectorAll: selector => renderedLinks(markup, card.shadowRoot)
        .filter(node => node.hasAttribute(selector.slice(1, -1))),
    };
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
setState('derived_buffer_judgement', 'keep');
for (const [stat, unit, band] of [
  ['minimum', 'min', 'very_short'], ['mean', 'min', 'warning'], ['maximum', 'min', 'good'],
]) fixture.states[byRegister[`derived_heating_run_${stat}`]].attributes = {
  register: `derived_heating_run_${stat}`, unit_of_measurement: unit, band,
};

const requests = [];
let historyScenario = 'normal';
let now = Date.parse('2026-01-15T12:00:00Z');
Date.now = () => now;
const timers = new Map();
let timerId = 0;
globalThis.setInterval = (callback, delay) => {
  assert.equal(delay, 60_000);
  timers.set(++timerId, callback);
  return timerId;
};
globalThis.clearInterval = id => { timers.delete(id); };
const hass = {
  ...fixture,
  locale: {language: 'en-GB'},
  config: {time_zone: 'UTC'},
  localize: key => ({'state.default.unavailable': 'Unavailable locally', 'state.default.unknown': 'Unknown locally'})[key],
  callService() { assert.fail('Unexpected service call'); },
  async callWS(message) {
    requests.push(message);
    if (historyScenario === 'empty') return {};
    const start = Date.parse(message.start_time) / 1000;
    const rows = pairs => pairs.map(([minute, s, unit]) => ({
      s: String(s), lu: start + minute * 60,
      ...(unit ? {a: {unit_of_measurement: unit}} : {}),
    }));
    const entity = (key, pairs) => [byRegister[key], rows(pairs)];
    const openRun = Date.parse(message.end_time) > Date.parse('2026-01-15T12:00:00Z')
      ? [[(Date.parse('2026-01-15T11:58:00Z') / 1000 - start) / 60, 'on']] : [];
    return Object.fromEntries([
      entity('dinput_199', [[0, 'off'], [10, 'on'], [15, 'off'], [20, 'on'], [40, 'off'],
        [50, 'on'], [140, 'off'], [150, 'on'], [190, 'off'], ...openRun]),
      entity('input_1', [[0, 'heating'], [150 + 0.2 / 60, 'Hot water']]),
      entity('dinput_209', [[0, 'off'], [5, 'on'], [80, 'off']]),
      entity('input_41', [[0, 30, '°C'], [15, 84.2, '°F']]),
      entity('input_12', [[0, 33], [15, 34]]),
      entity('input_147', [[0, 32], [15, 31]]),
      entity('input_68', [[0, 35], [15, 36]]),
      entity('derived_heat_to_rooms', [
        ...Array.from({length: 1440}, (_, i) => i % 2 ? [i, 3000, 'W'] : [i, 2, 'kW']),
        [1439.5, 3000, 'mW'],
      ]),
    ].filter(([id]) => message.entity_ids.includes(id)).flatMap(([id, samples]) => {
      if (id !== byRegister.dinput_199 || historyScenario === 'normal') return [[id, samples]];
      if (historyScenario === 'off') return [entity('dinput_199', [[0, 'off']])];
      return [];
    }));
  },
};
card.isConnected = true;
card.connectedCallback?.();
card.hass = hass;
await new Promise(resolve => setImmediate(resolve));
const html = () => card.shadowRoot.innerHTML;
assert.match(html(), /Daily overview/);
assert.doesNotMatch(html(), /<(input|button|ha-slider)\b/);
function tile(title) {
  const section = [...html().matchAll(/<section class="tile"[^>]*><h3>([^<]+)<\/h3>(.*?)<\/section>/gs)]
    .find(([, heading]) => heading === title);
  assert.ok(section, title);
  return section[2];
}

function row(section, label) {
  const metric = [...tile(section).matchAll(/(<div class="metric"[^>]*>)<span>([^<]+)<\/span>(.*?)<\/div>/gs)]
    .find(([, , heading]) => heading === label);
  assert.ok(metric, `${section}: ${label}`);
  const [, attributes, , content] = metric;
  const [, style, value] = content.match(/<strong([^>]*)>([^<]*)<\/strong>/);
  return {
    value,
    color: style.match(/style="color:([^"]+)"/)?.[1],
    neutral: style.includes('class="unavailable"'),
    caption: content.match(/class="caption">([^<]+)/)?.[1],
    attributes,
  };
}

function display(section, label, value, color, caption, neutral = false) {
  const {attributes, ...reading} = row(section, label);
  assert.deepEqual(reading, {value, color, caption, neutral}, `${section}: ${label}`);
}

// DHF-TEST: genesis-wp-ha/requirement-31 genesis-wp-ha/ac-148
display('Starts today', 'Total', '6');
display('Starts today', 'Hot water', '2');
display('Short heating runs', 'Today', '1', '#d46161');
display('Heating run length', 'Minimum', '8 min', '#e07f52', 'very short');
display('Heating run length', 'Heating run mean', '45 min', '#d4a14d', 'warning');
display('Heating run length', 'Maximum', '140 min', '#5fb88a', 'good');
display('Running hours', 'Today', '7.5 h');
setState('derived_heating_run_minimum', 60, {band: 'acceptable'});
card.hass = hass;
display('Heating run length', 'Minimum', '60 min', '#a8b86a', 'acceptable');
setState('derived_heating_run_minimum', 300, {unit_of_measurement: 's', band: 'short_cycle'});
setState('derived_running_hours_today', 450, {unit_of_measurement: 'min'});
card.hass = hass;
display('Heating run length', 'Minimum', '5 min', '#d46161', 'short cycle');
display('Running hours', 'Today', '7.5 h');

// DHF-TEST: genesis-wp-ha/requirement-31 genesis-wp-ha/ac-149
setState('derived_heat_produced_today', 24_000, {unit_of_measurement: 'Wh'});
card.hass = hass;
display('Heat today', 'Produced', '24.0 kWh');
display('Heat today', 'To the rooms', '18.5 kWh');
display('Heat today', 'Coverage', '80 %');
display('Buffer', 'Median restart margin', '1.2 K');
display('Buffer', 'Reference', '2.0 K');
display('Buffer', 'Judgement', '• keep', '#5fb88a');
display('Buffer', 'Curve gap', '2.0 K');
for (const [judgement, marker, color] of [['lower', '↓', '#d4a14d'], ['raise', '↑', '#d46161']]) {
  setState('derived_buffer_judgement', judgement);
  card.hass = hass;
  display('Buffer', 'Judgement', `${marker} ${judgement}`, color);
}
// DHF-TEST: genesis-wp-ha/requirement-31 genesis-wp-ha/ac-150
setState('derived_heating_run_mean', 'unavailable');
setState('derived_buffer_judgement', 'unknown');
card.hass = hass;
display('Heating run length', 'Heating run mean', 'Unavailable locally', undefined, undefined, true);
display('Buffer', 'Judgement', 'Unknown locally', undefined, undefined, true);
// DHF-TEST: genesis-wp-ha/requirement-31 genesis-wp-ha/ac-151
const segments = [...html().matchAll(/<rect[^>]*class="run"[^>]*x="([^"]+)"[^>]*width="([^"]+)"[^>]*fill="([^"]+)"/g)];
assert.equal(segments.length, 4);
assert.deepEqual(segments.map(match => match[3]), ['#d46161', '#d4a14d', '#5fb88a', 'currentColor']);
assert.match(html(), /<title>Hot water · 40\.0 min<\/title>/);
const timeAxis = html().match(/viewBox="0 0 (\d+) \d+"/);
assert.ok(timeAxis);
const width = Number(timeAxis[1]);
for (const [i, [start, duration]] of [[10, 5], [20, 20], [50, 90], [150, 40]].entries()) {
  assert.ok(Math.abs(Number(segments[i][1]) / width - start / 1440) < 0.00001);
  assert.ok(Math.abs(Number(segments[i][2]) / width - duration / 1440) < 0.00001);
}
const lanes = new Map([...html().matchAll(/<svg data-lane viewBox="0 0 (\d+) (\d+)"[^>]*aria-label="([^"]+)"[^>]*>(.*?)<\/svg>/gs)]
  .map(([, w, height, name, traces]) => [name, {width: Number(w), height: Number(height), traces}]));
assert.deepEqual([...lanes.keys()], ['Compressor', 'FR2', 'Buffer [°C]', 'Heat to the rooms [kW]']);
for (const lane of lanes.values()) assert.equal(lane.width, width);
function paths(name) {
  return [...lanes.get(name).traces.matchAll(/<path[^>]*d="([^"]+)"/g)].map(([, path]) => path);
}
assert.deepEqual(paths('FR2'), ['M0.000,20H2.917V4H46.667V20H840.000']);
assert.deepEqual(paths('Buffer [°C]'), [
  'M0.000,58.86H8.750V68.00H840.000',
  'M0.000,31.43H8.750V22.29H840.000',
  'M0.000,40.57H8.750V49.71H840.000',
  'M0.000,13.14H8.750V4.00H840.000',
]);
const [heat] = paths('Heat to the rooms [kW]');
assert.match(heat, /^M0\.000,20\.00H0\.583V4\.00H1\.167V20\.00/);
assert.match(heat, /H839\.708V51\.95H840\.000$/);
assert.equal((heat.match(/V/g) ?? []).length, 1440);
const axis = html().match(/<div class="axis">(.*?)<\/div>/s)?.[1];
assert.deepEqual([...axis.matchAll(/--tick:(\d+)%">([^<]+)/g)].map(([, x, label]) => [Number(x), label]), [
  [0, '12:00'], [25, '18:00'], [50, '00:00'], [75, '06:00'], [100, '12:00'],
]);
const legend = html().match(/<div class="legend">(.*?)<\/div>/s)?.[1];
assert.deepEqual([...legend.matchAll(/aria-hidden="true">●<\/span> ([^<]+)/g)].map(match => match[1]), [
  'short cycle', 'very short', 'short', 'acceptable', 'good', 'Hot water / unscored',
]);
const bounds = {left: 20, width: 1440};
const lane = {getBoundingClientRect: () => bounds};
card.pointermove({clientX: bounds.left + 15, target: {closest: selector => selector === '[data-lane]' ? lane : null}});
const hover = () => card.shadowRoot.output.textContent;
assert.equal(hover(), '12:15 · Compressor off · FR2 on · T31 buffer 29.0 °C · T33 supply 34.0 °C · Circuit 2 set point 31.0 °C · Charge set point 36.0 °C · Heat to the rooms 3.0 kW');

// DHF-TEST: genesis-wp-ha/requirement-31 genesis-wp-ha/ac-152
function renderedLinks(markup, root) {
  return [...markup.matchAll(/<(?:section|div|path|rect|span)\b([^>]* data-entity="[^"]+"[^>]*)>/g)].map(([tag, attrs]) => {
    const attributes = Object.fromEntries([...attrs.matchAll(/([\w-]+)="([^"]*)"/g)]
      .map(([, name, value]) => [name, value]));
    const node = {
      tag,
      dataset: {entity: attributes['data-entity'], link: attributes['data-link']},
      getAttribute: name => attributes[name] ?? null,
      hasAttribute: name => Object.hasOwn(attributes, name),
      closest: selector => selector === '[data-entity]' ? node : null,
      focus: () => { root.activeElement = node; },
    };
    return node;
  });
}
const links = renderedLinks(html(), card.shadowRoot);
const starts = links.find(node => node.tag === row('Starts today', 'Total').attributes);
const fr2 = links.find(node => node.tag.startsWith('<path') && node.dataset.entity === byRegister.dinput_209);
assert.ok(starts);
assert.ok(fr2);
for (const target of [starts, fr2]) card.click({target});
assert.deepEqual(events.map(({type, detail}) => [type, detail.entityId]),
  [['hass-more-info', byRegister.derived_starts_today], ['hass-more-info', byRegister.dinput_209]]);
fr2.focus();
const originalHover = hover();
setState('derived_starts_today', 7);
card.hass = hass;
assert.equal(card.shadowRoot.activeElement?.dataset.entity, byRegister.dinput_209);
assert.equal(hover(), originalHover);
const beforeRefresh = requests.length;
assert.equal(timers.size, 1);
async function refreshHistory() {
  now += 60_000;
  for (const refresh of timers.values()) refresh();
  await new Promise(resolve => setImmediate(resolve));
}
await refreshHistory();
assert.ok(requests.length > beforeRefresh);
assert.equal(Math.max(...requests.map(request => Date.parse(request.end_time))), now);
assert.ok(hover().startsWith('12:16'));
assert.match(html(), /<title>Hot water · 3\.0 min<\/title>/);
await refreshHistory();
assert.match(html(), /<title>Hot water · 4\.0 min<\/title>/);
assert.equal(card.shadowRoot.activeElement?.dataset.entity, byRegister.dinput_209);
// DHF-TEST: genesis-wp-ha/requirement-31 genesis-wp-ha/ac-151
function compressorLane() {
  return html().match(/<h3>Compressor(?:<[^/][^>]*>[^<]*<\/span>)?<\/h3>\s*<svg\b[^>]*aria-label="Compressor">[\s\S]*?<\/svg>/)[0];
}
for (const scenario of ['omitted', 'empty', 'off']) {
  historyScenario = scenario;
  await refreshHistory();
  assert.doesNotMatch(compressorLane(), /class="run"/, scenario);
  assert.equal(compressorLane().includes('Unavailable locally'), scenario !== 'off', scenario);
  if (scenario === 'omitted') assert.match(html(), /aria-label="FR2">\s*<path[^>]+ d="M/);
}

// DHF-TEST: genesis-wp-ha/requirement-31 genesis-wp-ha/ac-152
const tileLinks = renderedLinks(html(), card.shadowRoot);
const startsTile = tileLinks.find(node => node.tag.startsWith('<section')
  && node.dataset.entity === byRegister.derived_starts_today);
assert.ok(startsTile, 'Starts today tile opens more-info from its padding');
const hotWater = tileLinks.find(node => node.tag === row('Starts today', 'Hot water').attributes);
assert.ok(hotWater);
const firstTileEvent = events.length;
card.click({target: startsTile});
card.click({target: {closest: selector => startsTile.closest(selector)}});
card.click({target: hotWater});
assert.deepEqual(events.slice(firstTileEvent).map(({type, detail}) => [type, detail.entityId]), [
  ['hass-more-info', byRegister.derived_starts_today],
  ['hass-more-info', byRegister.derived_starts_today],
  ['hass-more-info', byRegister.derived_hot_water_starts_today],
]);
card.isConnected = false;
card.disconnectedCallback();
assert.equal(timers.size, 0);
assert.ok(requests.every(request => request.type === 'history/history_during_period'
  && Date.parse(request.end_time) - Date.parse(request.start_time) === 86_400_000));
assert.ok(requests.some(request => request.entity_ids.includes(byRegister.derived_heat_to_rooms)
  && request.no_attributes === false && request.minimal_response === false));
process.stdout.write('HARNESS-COMPLETE\n');
