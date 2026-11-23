import {registerCard} from './register-card.js';
import {patch} from './patch.js';
import {BAND_COLORS, MEAN_BANDS, RUN_BANDS, bandFor} from './overview-bands.js';

const NAME = 'Compressor and buffer overview';
const DAY = 86_400;
const HISTORY_REFRESH = 60;
// Entities from one 30-second poll can be recorded a fraction of a second apart.
const DEMAND_SKEW = 1;
const WIDTH = 840;
const COMPRESSOR = 'dinput_199';
const DEMAND = 'input_1';
const FR2 = 'dinput_209';
const ROOM_HEAT = 'derived_heat_to_rooms';
const BUFFER = [
  ['input_41', 'T31 buffer', '#50a0cb', ''],
  ['input_12', 'T33 supply', '#8e6cc0', ''],
  ['input_147', 'Circuit 2 set point', '#5fb88a', '6 4'],
  ['input_68', 'Charge set point', '#d4a14d', '6 4'],
];
const MODE_HISTORY_KEYS = [COMPRESSOR, DEMAND, FR2];
const NUMERIC_HISTORY_KEYS = [...BUFFER.map(([key]) => key), ROOM_HEAT];
const HISTORY_KEYS = [...MODE_HISTORY_KEYS, ...NUMERIC_HISTORY_KEYS];
const MINUTES = new Map([
  ['μs', 1 / 60e6], ['ms', 1 / 60e3], ['s', 1 / 60], ['min', 1],
  ['h', 60], ['d', 1440], ['w', 10080],
]);
const KWH = new Map([
  ['mWh', 1e-6], ['Wh', 1e-3], ['kWh', 1], ['MWh', 1e3], ['GWh', 1e6], ['TWh', 1e9],
  ['J', 1 / 3.6e6], ['kJ', 1 / 3600], ['MJ', 1 / 3.6], ['GJ', 1e3 / 3.6],
  ['cal', 4.184 / 3.6e6], ['kcal', 4.184 / 3600], ['Mcal', 4.184 / 3.6], ['Gcal', 4184 / 3.6],
  ['thm', 1.054804e8 / 3.6e6],
]);
const KW = new Map([
  ['mW', 1e-6], ['W', 1e-3], ['kW', 1], ['MW', 1e3], ['GW', 1e6], ['TW', 1e9],
  ['BTU/h', 0.29307107 / 1000],
]);

const escape = value => String(value).replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[char]));

function number(value) {
  if (typeof value !== 'number' && (typeof value !== 'string' || !value.trim())) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function scaled(value, factors, unit, target) {
  const reading = number(value);
  const factor = factors.get(unit ?? target);
  if (reading === null || factor === undefined) return null;
  return number(reading * factor / factors.get(target));
}

function temperature(value, unit) {
  const reading = number(value);
  if (reading === null) return null;
  switch (unit ?? '°C') {
    case '°C': return reading;
    case '°F': return (reading - 32) * 5 / 9;
    case 'K': return reading - 273.15;
    default: return null;
  }
}

function historyPoints(rows, start, end, convert) {
  if (!Array.isArray(rows)) return [];
  return rows.flatMap(row => {
    const time = number(row?.lu ?? row?.lc);
    return time === null || time > end || typeof row.s !== 'string'
      ? [] : [{time: Math.max(start, time), state: convert(row.s, row.a?.unit_of_measurement)}];
  }).sort((a, b) => a.time - b.time);
}

function atTime(points, time) {
  let low = 0;
  let high = points.length;
  while (low < high) {
    const mid = (low + high) >>> 1;
    if (points[mid].time <= time) low = mid + 1;
    else high = mid;
  }
  return points[low - 1]?.state;
}

function runs(points, demand, start, end) {
  const result = [];
  let previous;
  let open;
  for (const {state, time} of points) {
    if (state === 'on' && previous !== 'on') {
      const completeStart = previous === 'off' && time > start;
      const modeTime = time === start ? time : time + DEMAND_SKEW;
      open = {time, completeStart, mode: atTime(demand, modeTime)};
    } else if (state !== 'on' && open) {
      result.push(segment(open, time, state === 'off'));
      open = undefined;
    }
    previous = state;
  }
  if (open) result.push(segment(open, end, false));
  return result;
}

function segment(open, end, completeEnd) {
  const minutes = (end - open.time) / 60;
  const mode = open.mode?.toLowerCase().replaceAll(' ', '_');
  let label = 'Unscored';
  let color = 'currentColor';
  if (mode === 'hot_water') label = 'Hot water';
  if ((mode === 'heat' || mode === 'heating') && open.completeStart && completeEnd) {
    const band = bandFor(minutes, RUN_BANDS);
    label = band.replaceAll('_', ' ');
    color = BAND_COLORS[band];
  }
  return {start: open.time, end, label, color};
}

function linePath(points, x, y, end) {
  let path = '';
  let previous = null;
  for (const {time, state: value} of points) {
    if (previous !== null) path += `H${x(time)}`;
    if (value !== null) path += previous === null ? `M${x(time)},${y(value)}` : `V${y(value)}`;
    previous = value;
  }
  if (previous !== null) path += `H${x(end)}`;
  return path;
}

function binaryValue(state) {
  if (state === 'on') return 1;
  if (state === 'off') return 0;
  return null;
}
const STYLES = `
  :host {display:block;color:var(--primary-text-color);}
  .body {padding:16px;display:grid;gap:20px;}
  .tiles {display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,140px),1fr));gap:8px;}
  .tile {border:1px solid var(--divider-color);border-radius:10px;padding:10px 12px;display:grid;gap:4px;}
  .tile h3 {font-size:.88rem;font-weight:500;margin:0 0 4px;color:var(--secondary-text-color);}
  .metric {display:flex;justify-content:space-between;align-items:baseline;gap:6px;font-variant-numeric:tabular-nums;}
  .metric:first-of-type strong {font-size:1.2rem;}
  .caption {font-size:.8rem;color:var(--secondary-text-color);}
  .unavailable {color:var(--secondary-text-color);}
  [data-entity] {cursor:pointer;}
  [data-entity]:focus-visible {outline:2px solid var(--primary-color);outline-offset:1px;}
  .lanes {display:grid;gap:5px;position:relative;}
  .lanes h2 {margin:0 0 4px;font-size:1rem;font-weight:600;}
  .lanes h3 {margin:0;font-size:.9rem;font-weight:500;}
  svg {display:block;width:100%;background:var(--secondary-background-color);border-radius:4px;}
  svg path {fill:none;stroke-width:2;vector-effect:non-scaling-stroke;}
  .axis,.legend {color:var(--secondary-text-color);font-size:.75rem;}
  .lanes {container-type:inline-size;}
  .axis {position:relative;height:1.6em;}
  .axis span {position:absolute;left:var(--tick);transform:translateX(-50%);white-space:nowrap;}
  .axis span:first-child {transform:none;}
  .axis span:last-child {transform:translateX(-100%);}
  @container (max-width: 340px) {
    .axis span:nth-child(2n) {display:none;}
  }
  @container (max-width: 200px) {
    .axis span:nth-child(3) {display:none;}
  }
  .legend {display:flex;flex-wrap:wrap;gap:8px;}
  .legend span {white-space:nowrap;}
  output {display:block;min-height:2.5em;color:var(--secondary-text-color);font-size:.85rem;}
`;

// DHF-REQ: genesis-wp-ha/requirement-31
class OverviewCard extends HTMLElement {
  setConfig(config) {
    // Lovelace adds the dispatch key before calling setConfig.
    if (!config || Object.keys(config).some(key => !['type', 'entry', 'title'].includes(key))
      || (config.type !== undefined && config.type !== 'custom:genesis-wp-overview-card')
      || ['entry', 'title'].some(key => config[key] !== undefined && typeof config[key] !== 'string')) {
      throw new Error('Overview card accepts entry and title');
    }
    if (this.config?.entry !== config.entry) this.hoverFraction = undefined;
    this.config = config;
    if (!this.shadowRoot) {
      this.attachShadow({mode: 'open'});
      this.shadowRoot.addEventListener('click', event => this.openEntity(event));
      this.shadowRoot.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') this.openEntity(event);
      });
      this.shadowRoot.addEventListener('pointermove', event => this.readHistory(event));
    }
    this.update();
  }

  connectedCallback() {
    this.refreshTimer = setInterval(() => this.update(), HISTORY_REFRESH * 1000);
    this.update();
  }

  disconnectedCallback() {
    clearInterval(this.refreshTimer);
  }

  static getStubConfig() { return {}; }

  static getConfigForm() {
    return {schema: [
      {name: 'entry', selector: {config_entry: {integration: 'genesis_wp'}}},
      {name: 'title', selector: {text: {}}},
    ]};
  }

  getCardSize() { return 8; }

  set hass(value) {
    this._hass = value;
    this.update();
  }

  update() {
    if (!this.config || !this._hass) return;
    this.entities = this.resolveEntities();
    const ids = HISTORY_KEYS.map(key => this.entities.get(key)?.id);
    const signature = JSON.stringify(ids);
    const now = Date.now() / 1000;
    if (signature !== this.historySignature) {
      this.historySignature = signature;
      this.history = undefined;
      this.pending = undefined;
      this.requestedAt = undefined;
      this.historyFailed = false;
      this.hoverFraction = undefined;
    }
    if (this.isConnected && ids.some(Boolean) && !this.pending && (this.requestedAt === undefined
      || now - this.requestedAt >= HISTORY_REFRESH || now < this.requestedAt)) {
      this.requestedAt = now;
      this.loadHistory(now);
    }
    this.render();
  }

  resolveEntities() {
    const {devices = {}, entities = {}, states = {}} = this._hass;
    const entry = this.config.entry || Object.values(devices).flatMap(device => device.identifiers ?? [])
      .find(([domain, identifier]) => domain === 'genesis_wp' && !identifier.includes('_'))?.[1];
    const matches = new Map();
    if (!entry) return matches;
    for (const [id, entity] of Object.entries(entities)) {
      const state = states[id];
      const key = state?.attributes?.register;
      if (!key || entity.disabled_by) continue;
      if (devices[entity.device_id]?.identifiers?.some(([domain, identifier]) =>
        domain === 'genesis_wp' && (identifier === entry || identifier.startsWith(`${entry}_`)))) {
        matches.set(key, {id, state});
      }
    }
    return matches;
  }

  async loadHistory(end) {
    const request = {};
    this.pending = request;
    const start = end - DAY;
    const read = (keys, compact) => {
      const entityIds = keys.flatMap(key => {
        const id = this.entities.get(key)?.id;
        return id ? [id] : [];
      });
      if (!entityIds.length) return {};
      return this._hass.callWS({
        type: 'history/history_during_period',
        start_time: new Date(start * 1000).toISOString(),
        end_time: new Date(end * 1000).toISOString(),
        entity_ids: entityIds,
        minimal_response: compact,
        no_attributes: compact,
        significant_changes_only: false,
      });
    };
    try {
      // Full numeric rows retain the unit per sample and Recorder's attribute-only changes.
      const [modes, measurements] = await Promise.all([
        read(MODE_HISTORY_KEYS, true), read(NUMERIC_HISTORY_KEYS, false),
      ]);
      if (this.pending !== request) return;
      const data = {...modes, ...measurements};
      const series = new Map(HISTORY_KEYS.map(key => {
        const convert = key === ROOM_HEAT ? (value, unit) => scaled(value, KW, unit, 'kW')
          : key === FR2 ? binaryValue
          : MODE_HISTORY_KEYS.includes(key) ? value => value : temperature;
        return [key, historyPoints(data[this.entities.get(key)?.id], start, end, convert)];
      }));
      this.history = {start, end, series};
      this.historyFailed = false;
    } catch {
      if (this.pending !== request) return;
      this.historyFailed = true;
    }
    this.pending = undefined;
    this.render();
  }

  openEntity(event) {
    const target = event.target?.closest?.('[data-entity]');
    if (!target?.dataset?.entity) return;
    event.preventDefault?.();
    this.dispatchEvent(new CustomEvent('hass-more-info', {
      detail: {entityId: target.dataset.entity}, bubbles: true, composed: true,
    }));
  }

  entityAttributes(key, link = key) {
    const entity = this.entities.get(key);
    return entity ? ` data-entity="${escape(entity.id)}" data-link="${escape(link)}" tabindex="0" role="link"` : '';
  }

  stateWord(state) {
    const key = state === 'unknown' ? 'unknown' : 'unavailable';
    return this._hass.localize?.(`state.default.${key}`) || (key === 'unknown' ? 'Unknown' : 'Unavailable');
  }

  metric(key, label, unit = '', options = {}) {
    const register = `derived_${key}`;
    const state = this.entities.get(register)?.state;
    const raw = state?.state;
    const value = options.factors
      ? scaled(raw, options.factors, state?.attributes.unit_of_measurement, unit)
      : number(raw);
    const canonical = state?.attributes.band;
    const band = value !== null && options.bands?.some(([, label]) => label === canonical)
      ? canonical : undefined;
    const display = value === null ? this.stateWord(raw)
      : `${options.decimals === undefined ? value : value.toFixed(options.decimals)}${unit ? ` ${unit}` : ''}`;
    const color = band ? BAND_COLORS[band] : value > 0 && options.alert ? BAND_COLORS.bad : undefined;
    return this.valueRow(register, label, display, color, band?.replaceAll('_', ' '), value === null);
  }

  valueRow(register, label, display, color, caption, unavailable = false) {
    return `<div class="metric"${this.entityAttributes(register, `tile:${register}:${label}`)}><span>${escape(label)}</span>
      <strong${unavailable ? ' class="unavailable"' : ''}${color ? ` style="color:${color}"` : ''}>${escape(display)}</strong>
      ${caption ? `<span class="caption">${escape(caption)}</span>` : ''}</div>`;
  }

  tiles() {
    const tile = (title, rows) => `<section class="tile"><h3>${title}</h3>${rows}</section>`;
    const metric = (...args) => this.metric(...args);
    const rooms = this.entities.get('derived_heat_to_rooms_today')?.state;
    const coverage = number(rooms?.state) === null ? null : number(rooms?.attributes.coverage);
    const judgement = this.entities.get('derived_buffer_judgement')?.state;
    const reference = number(judgement?.attributes.reference_offset);
    const markers = new Map([
      ['keep', ['• keep', BAND_COLORS.good]],
      ['lower', ['↓ lower', BAND_COLORS.warning]],
      ['raise', ['↑ raise', BAND_COLORS.bad]],
    ]);
    const [marker, color] = markers.get(judgement?.state) ?? [this.stateWord(judgement?.state)];
    return [
      tile('Starts today', metric('starts_today', 'Total') + metric('hot_water_starts_today', 'Hot water')),
      tile('Short heating runs', metric('short_heating_runs_today', 'Today', '', {alert: true})),
      tile('Heating run length',
        metric('heating_run_minimum', 'Minimum', 'min', {bands: RUN_BANDS, factors: MINUTES}) +
        metric('heating_run_mean', 'Heating run mean', 'min', {bands: MEAN_BANDS, factors: MINUTES}) +
        metric('heating_run_maximum', 'Maximum', 'min', {bands: RUN_BANDS, factors: MINUTES})),
      tile('Running hours', metric('running_hours_today', 'Today', 'h', {factors: MINUTES})),
      tile('Heat today',
        metric('heat_produced_today', 'Produced', 'kWh', {decimals: 1, factors: KWH}) +
        metric('heat_to_rooms_today', 'To the rooms', 'kWh', {decimals: 1, factors: KWH}) +
        this.valueRow('derived_heat_to_rooms_today', 'Coverage', coverage === null
          ? this.stateWord(rooms?.state) : `${coverage} %`)),
      tile('Buffer',
        metric('median_restart_margin_today', 'Median restart margin', 'K', {decimals: 1}) +
        this.valueRow('derived_buffer_judgement', 'Reference', reference === null
          ? this.stateWord(judgement?.state) : `${reference.toFixed(1)} K`) +
        this.valueRow('derived_buffer_judgement', 'Judgement', marker, color, undefined, !color) +
        metric('curve_gap', 'Curve gap', 'K', {decimals: 1})),
    ].join('');
  }

  timeLabel(time) {
    const timeZone = this._hass.config?.time_zone;
    return new Date(time * 1000).toLocaleTimeString(this._hass.locale?.language, {
      hour: '2-digit', minute: '2-digit', timeZone,
    });
  }

  strip() {
    if (!this.history) {
      return `<p>${this.historyFailed ? 'Recorder history unavailable'
        : this.pending ? 'Loading recorder history…' : 'No history entities available'}</p>`;
    }
    const {start, end, series} = this.history;
    const x = time => (WIDTH * (time - start) / DAY).toFixed(3);
    const lane = (title, height, contents) => `<h3>${title}</h3>
      <svg data-lane viewBox="0 0 ${WIDTH} ${height}" preserveAspectRatio="none"
        style="height:${height}px" aria-label="${title}">${contents}</svg>`;
    const trace = (key, y, color, dash = '') =>
      `<path${this.entityAttributes(key)} d="${linePath(series.get(key), x, y, end)}"
        stroke="${color}" stroke-dasharray="${dash}"/>`;
    const range = (values, height) => {
      const {low, high} = values.reduce((bounds, value) => value === null ? bounds : ({
        low: Math.min(bounds.low, value), high: Math.max(bounds.high, value),
      }), {low: Infinity, high: -Infinity});
      return value => Number.isFinite(low) && high !== low
        ? (height - 4 - (height - 8) * (value - low) / (high - low)).toFixed(2) : height / 2;
    };
    const compressor = runs(series.get(COMPRESSOR), series.get(DEMAND), start, end).map(run =>
      `<rect class="run" x="${x(run.start)}" width="${x(start + run.end - run.start)}"
        fill="${run.color}" fill-opacity="${run.color === 'currentColor' ? 0.35 : 1}"
        y="3" height="18"${this.entityAttributes(COMPRESSOR, `run:${run.start}`)}>
        <title>${run.label} · ${((run.end - run.start) / 60).toFixed(1)} min</title></rect>`).join('');
    const bufferScale = range(BUFFER.flatMap(([key]) =>
      series.get(key).map(({state}) => state)), 72);
    const heatScale = range([0, ...series.get(ROOM_HEAT).map(({state}) => state)], 56);
    const ticks = Array.from({length: 5}, (_, i) =>
      `<span style="--tick:${i * 25}%">${escape(this.timeLabel(start + i * DAY / 4))}</span>`);
    const swatch = (color, label) => `<span><span style="color:${color}" aria-hidden="true">●</span> ${label}</span>`;
    const bandLegend = [...RUN_BANDS].reverse().map(([, label]) => swatch(BAND_COLORS[label], label.replaceAll('_', ' ')));
    return `<section class="lanes" aria-label="Last 24 hours">
      <h2>Last 24 hours</h2>
      ${lane('Compressor', 24, compressor)}
      ${lane('FR2', 24, trace(FR2, value => value ? 4 : 20, '#50a0cb'))}
      ${lane('Buffer [°C]', 72, BUFFER.map(([key, , color, dash]) =>
        trace(key, bufferScale, color, dash)).join(''))}
      ${lane('Heat to the rooms [kW]', 56, trace(ROOM_HEAT, heatScale, '#5fb88a'))}
      <div class="axis">${ticks.join('')}</div>
      <div class="legend">${bandLegend.join('')} ${swatch('currentColor', 'Hot water / unscored')}</div>
      <div class="legend">${BUFFER.map(([key, label, color]) =>
        `<span${this.entityAttributes(key, `legend:${key}`)}>${swatch(color, label)}</span>`).join('')}</div>
      <output></output>
      ${this.historyFailed ? '<p>Recorder history refresh failed</p>' : ''}
      </section>`;
  }

  readHistory(event) {
    const lane = event.target?.closest?.('[data-lane]');
    if (!lane || !this.history) return;
    const bounds = lane.getBoundingClientRect();
    if (bounds.width <= 0) return;
    this.hoverFraction = Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width));
    this.renderHover();
  }

  renderHover() {
    if (!this.history || this.hoverFraction === undefined) return;
    const output = this.shadowRoot.querySelector('output');
    const {start, series} = this.history;
    const time = start + DAY * this.hoverFraction;
    const get = key => atTime(series.get(key), time);
    const reading = (value, unit) => value === null || value === undefined ? this.stateWord() : `${value.toFixed(1)} ${unit}`;
    output.textContent = [
      this.timeLabel(time),
      `Compressor ${get(COMPRESSOR) ?? this.stateWord()}`,
      `FR2 ${['off', 'on'][get(FR2)] ?? this.stateWord()}`,
      ...BUFFER.map(([key, label]) => `${label} ${reading(get(key), '°C')}`),
      `Heat to the rooms ${reading(get(ROOM_HEAT), 'kW')}`,
    ].join(' · ');
  }

  render() {
    const markup = `<style>${STYLES}</style><ha-card header="${escape(this.config.title || NAME)}">
      <div class="body"><div class="tiles">${this.tiles()}</div>${this.strip()}</div></ha-card>`;
    const root = this.shadowRoot;
    const focused = root.activeElement;
    const link = focused?.getAttribute('data-link');
    const entityId = focused?.getAttribute('data-entity');
    if (patch(root, markup) === 'unchanged') return;
    if (link && (root.activeElement?.getAttribute('data-link') !== link
      || root.activeElement?.getAttribute('data-entity') !== entityId)) {
      const replacement = [...root.querySelectorAll('[data-link]')].find(node =>
        node.getAttribute('data-link') === link && node.getAttribute('data-entity') === entityId);
      replacement?.focus({preventScroll: true});
    }
    this.renderHover();
  }
}

registerCard('genesis-wp-overview-card', OverviewCard, {name: NAME});
