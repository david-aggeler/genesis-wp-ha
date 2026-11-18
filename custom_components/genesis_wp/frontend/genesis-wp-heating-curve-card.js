import { registerCard } from './register-card.js';
import { patch } from './patch.js';
// Heating curve card for genesis_wp (requirement-11): the heating curves of one or more heating
// circuits in one chart as supply temperature over outdoor temperature, each with its current
// operating point. Read-only, no dependencies.
// Config: { type: custom:genesis-wp-heating-curve-card, entities: [<set temperature sensor>, ...] | entity: <one>, title?: str,
//           min?: <entity>, max?: <entity>, stop?: <entity>, measured?: <entity> }
// The optional keys (requirement-25) add the supply limit lines, the heating-season stop line and
// a measured-supply tick at the current outdoor temperature. Each is drawn only from an entity
// with a numeric state; a missing or unavailable one draws nothing, never a substitute value.
const EXTRAS = ["min", "max", "stop", "measured"];

// The chart is drawn at its rendered pixel width, so text keeps its theme size at any card
// width. The height follows the width up to MAX_H.
const DEFAULT_W = 400;
const MAX_H = 320;
const PAD = { left: 48, right: 14, top: 14, bottom: 42 };
// Circuit 1 keeps the theme color; further circuits get distinct theme colors with fallbacks.
const COLORS = ["var(--primary-color)", "var(--info-color, #039be5)", "var(--success-color, #43a047)", "var(--warning-color, #ffa600)"];

function escapeText(value) {
  return String(value).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}

// Estimated label extent for placement: the theme's small font is about 12 px, so a character
// is at most about 7 px wide and a line about 14 px high. Generous on purpose: an estimate that
// is too wide only moves a label, one that is too narrow lets labels collide.
const CHAR_W = 7;
const LINE_H = 14;

function textWidth(text) {
  return text.length * CHAR_W;
}

// The box of a label { text, x, y (baseline), anchor } as [x0, y0, x1, y1].
function labelBox({ text, x, y, anchor }) {
  const w = textWidth(text);
  const x0 = anchor === "end" ? x - w : anchor === "middle" ? x - w / 2 : x;
  return [x0, y - LINE_H + 3, x0 + w, y + 3];
}

function overlaps(a, b) {
  return a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
}

function niceStep(span) {
  for (const step of [1, 2, 5, 10, 20]) {
    if (span / step <= 6) return step;
  }
  return 50;
}

function axis(values) {
  const step = niceStep(Math.max(...values) - Math.min(...values) || 1);
  const low = Math.floor(Math.min(...values) / step) * step;
  const high = Math.ceil(Math.max(...values) / step) * step;
  return { low, high: high > low ? high : low + step, step };
}

function ticks({ low, high, step }) {
  const out = [];
  for (let v = low; v <= high + 1e-9; v += step) out.push(Math.round(v * 100) / 100);
  return out;
}

export class GenesisWpHeatingCurveCard extends HTMLElement {
  setConfig(config) {
    const entities = config && (config.entities || (config.entity ? [config.entity] : []));
    if (!Array.isArray(entities) || entities.length === 0 || !entities.every((e) => typeof e === "string" && e)) {
      throw new Error("entity or entities is required: the heating circuits' set temperature sensors");
    }
    for (const key of EXTRAS) {
      if (config[key] !== undefined && (typeof config[key] !== "string" || !config[key])) {
        throw new Error(`${key} must be an entity id`);
      }
    }
    this._config = config;
    this._entities = entities;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      if (typeof ResizeObserver !== "undefined") {
        new ResizeObserver((entries) => {
          const width = Math.round(entries[0].contentRect.width) - 24;
          if (width > 0 && width !== this._width) {
            this._width = width;
            this._render();
          }
        }).observe(this);
      }
    }
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 5;
  }

  static getStubConfig(hass) {
    const entities = Object.keys(hass.states).filter((id) => Array.isArray(hass.states[id].attributes.curve));
    return entities.length ? { entities } : { entity: "" };
  }

  // The device's name, when Home Assistant's registry tables are present and all entities share it.
  _deviceName() {
    const { entities, devices } = this._hass;
    if (!entities || !devices) return null;
    const names = new Set(this._entities.map((id) => entities[id] && devices[entities[id].device_id] && devices[entities[id].device_id].name));
    const [name] = names;
    return names.size === 1 && name ? name : null;
  }

  _series() {
    const device = this._deviceName();
    return this._entities.map((entity, index) => {
      const state = this._hass.states[entity];
      const fullName = (state && state.attributes.friendly_name) || entity;
      const name = device && fullName.startsWith(`${device} `) ? fullName.slice(device.length + 1) : fullName;
      const curve = state && Array.isArray(state.attributes.curve) ? state.attributes.curve : [];
      const setPoint = state ? Number.parseFloat(state.state) : Number.NaN;
      const outdoor = state ? state.attributes.outdoor_temperature : null;
      const now = Number.isFinite(setPoint) && typeof outdoor === "number" ? [outdoor, setPoint] : null;
      return { entity, fullName, name, curve, setPoint, now, color: COLORS[index % COLORS.length] };
    });
  }

  // The numeric state of an optional config entity, or null when absent, unavailable or not a number.
  _number(key) {
    const id = this._config[key];
    const state = id && this._hass.states[id];
    const raw = state ? String(state.state ?? "").trim() : "";
    const value = raw === "" ? Number.NaN : Number(raw);
    return Number.isFinite(value) ? value : null;
  }

  _extras(series) {
    const out = {};
    for (const key of EXTRAS) out[key] = this._number(key);
    // The measured tick sits at the operating point's outdoor temperature; without one, no tick.
    const outdoor = series.find((s) => s.now);
    out.tick = out.measured !== null && outdoor ? [outdoor.now[0], out.measured] : null;
    return out;
  }

  _render() {
    if (!this._config || !this._hass || !this.shadowRoot) return;
    const series = this._series();
    const single = series.length === 1;
    const title = this._config.title || (single ? series[0].fullName : this._deviceName() || "Heating curves");
    const drawn = series.filter((s) => s.curve.length >= 2);

    let body;
    if (drawn.length === 0) {
      body = `<div class="empty">No heating curve on ${escapeText(this._entities.join(", "))}</div>`;
    } else {
      body = this._svg(drawn, single);
    }
    const legend = single
      ? ""
      : `<div class="legend">${series
          .map((s) => {
            const value = s.curve.length >= 2 && Number.isFinite(s.setPoint) ? `${s.setPoint} \u00b0C` : "unavailable";
            return `<span class="legend-item"><span class="swatch" style="background:${s.color}"></span>${escapeText(s.name)}: ${value}</span>`;
          })
          .join("")}</div>`;
    patch(this.shadowRoot, `
      <style>
        :host { display: block; }
        ha-card { padding: 12px 12px 4px; }
        .title { font-size: var(--ha-font-size-l); margin: 0 0 6px 4px; color: var(--primary-text-color); }
        .legend { display: flex; flex-wrap: wrap; gap: 4px 16px; margin: 0 0 4px 4px; color: var(--secondary-text-color); font-size: var(--ha-font-size-s); }
        .legend-item { display: inline-flex; align-items: center; gap: 6px; }
        .swatch { width: 14px; height: 3px; border-radius: 2px; }
        svg { width: 100%; height: auto; display: block; }
        .grid { stroke: var(--divider-color, currentColor); stroke-opacity: 0.6; }
        .label { fill: var(--secondary-text-color); font-size: var(--ha-font-size-s); }
        .axis { fill: var(--secondary-text-color); font-size: var(--ha-font-size-m); }
        .curve { fill: none; stroke-width: 2.5; }
        .now { stroke: var(--card-background-color, #fff); stroke-width: 2; }
        .single .now { fill: var(--accent-color, #ff9800); }
        .limit { stroke: var(--error-color, #db4437); stroke-width: 1.5; stroke-dasharray: 6 4; }
        .stop { stroke: var(--secondary-text-color); stroke-width: 1.5; stroke-dasharray: 2 4; }
        .measured { stroke: var(--primary-text-color); stroke-width: 3; stroke-linecap: round; }
        .empty { color: var(--secondary-text-color); padding: 16px 4px; }
      </style>
      <ha-card>
        <div class="title">${escapeText(title)}</div>
        ${legend}
        ${body}
      </ha-card>`);
  }

  _svg(series, single) {
    const W = Math.max(240, this._width || DEFAULT_W);
    const H = Math.min(MAX_H, Math.max(180, Math.round(W * 0.65)));
    const extra = this._extras(series);
    const xs = series.flatMap((s) => s.curve.map((p) => p[0]).concat(s.now ? [s.now[0]] : []))
      .concat(extra.stop !== null ? [extra.stop] : []);
    const ys = series.flatMap((s) => s.curve.map((p) => p[1]).concat(s.now ? [s.now[1]] : []))
      .concat([extra.min, extra.max, extra.tick && extra.tick[1]].filter((v) => v !== null && v !== undefined));
    const ax = axis(xs);
    const ay = axis(ys);
    const px = (x) => PAD.left + ((x - ax.low) / (ax.high - ax.low)) * (W - PAD.left - PAD.right);
    const py = (y) => H - PAD.bottom - ((y - ay.low) / (ay.high - ay.low)) * (H - PAD.top - PAD.bottom);

    const xGrid = ticks(ax)
      .map((x) => `<line class="grid" x1="${px(x)}" x2="${px(x)}" y1="${PAD.top}" y2="${H - PAD.bottom}"/>
        <text class="label" x="${px(x)}" y="${H - PAD.bottom + 14}" text-anchor="middle">${x}</text>`)
      .join("");
    const yGrid = ticks(ay)
      .map((y) => `<line class="grid" x1="${PAD.left}" x2="${W - PAD.right}" y1="${py(y)}" y2="${py(y)}"/>
        <text class="label" x="${PAD.left - 6}" y="${py(y) + 4}" text-anchor="end">${y}</text>`)
      .join("");
    // Every curve first, then every marker, so no line covers an operating point.
    const curves = series
      .map((s) => {
        const sorted = [...s.curve].sort((a, b) => a[0] - b[0]);
        const line = sorted.map((p) => `${px(p[0])},${py(p[1])}`).join(" ");
        const dots = sorted
          .map((p) => `<circle class="dot" style="fill:${s.color}" cx="${px(p[0])}" cy="${py(p[1])}" r="3.5"><title>${escapeText(s.name)}: ${p[0]} \u00b0C outdoor, ${p[1]} \u00b0C</title></circle>`)
          .join("");
        return `<polyline class="curve" style="stroke:${s.color}" points="${line}"/>${dots}`;
      })
      .join("");
    const markers = series
      .filter((s) => s.now)
      .map((s) => {
        const fill = single ? "" : ` style="fill:${s.color}"`;
        return `<circle class="now"${fill} cx="${px(s.now[0])}" cy="${py(s.now[1])}" r="6"><title>${escapeText(s.name)} now: ${s.now[0]} \u00b0C outdoor, ${s.now[1]} \u00b0C set</title></circle>`;
      })
      .join("");
    // Limits and the stop line lie under the curves; the measured tick sits with the markers.
    // Label placement (issue-21): limit labels at the left end of their line, the stop label at the
    // bottom of the plot on the side of the stop line with more room. When the stop line runs
    // through the left-anchored limit labels, those move to the right end; a stop label that would
    // overlap a limit label moves up one line at a time.
    const stopX = extra.stop === null ? null : px(extra.stop);
    const limitLabels = ["min", "max"]
      .filter((key) => extra[key] !== null)
      .map((key) => ({ key, text: `${key} ${extra[key]} \u00b0C`, y: py(extra[key]) + (key === "max" ? 14 : -4) }));
    const left = PAD.left + 4;
    const crossed = stopX !== null && limitLabels.some((l) => stopX >= left - 2 && stopX <= left + textWidth(l.text) + 2);
    for (const l of limitLabels) {
      l.anchor = crossed ? "end" : "start";
      l.x = crossed ? W - PAD.right - 4 : left;
    }
    const limits = limitLabels
      .map((l) => `<line class="limit" data-limit="${l.key}" x1="${PAD.left}" x2="${W - PAD.right}" y1="${py(extra[l.key])}" y2="${py(extra[l.key])}"><title>${l.key} supply: ${extra[l.key]} \u00b0C</title></line>
        <text class="label" data-label="${l.key}" x="${l.x}" y="${l.y}" text-anchor="${l.anchor}">${l.text}</text>`)
      .join("");
    let stop = "";
    if (stopX !== null) {
      const text = `stop ${extra.stop} \u00b0C`;
      const onLeft = stopX - PAD.left > W - PAD.right - stopX;
      const label = { text, anchor: onLeft ? "end" : "start", x: onLeft ? stopX - 4 : stopX + 4, y: H - PAD.bottom - 4 };
      for (let i = 0; i < 4 && limitLabels.some((l) => overlaps(labelBox(l), labelBox(label))); i++) label.y -= LINE_H;
      stop = `<line class="stop" x1="${stopX}" x2="${stopX}" y1="${PAD.top}" y2="${H - PAD.bottom}"><title>heating stops above ${extra.stop} \u00b0C outdoor</title></line>
        <text class="label" data-label="stop" x="${label.x}" y="${label.y}" text-anchor="${label.anchor}">${text}</text>`;
    }
    const tick = extra.tick ? `<line class="measured" x1="${px(extra.tick[0]) - 9}" x2="${px(extra.tick[0]) + 9}" y1="${py(extra.tick[1])}" y2="${py(extra.tick[1])}"><title>measured supply: ${extra.tick[1]} \u00b0C</title></line>` : "";

    return `<svg class="${single ? "single" : "overlay"}" viewBox="0 0 ${W} ${H}" role="img" aria-label="heating curves">
      ${xGrid}${yGrid}
      ${limits}${stop}
      ${curves}${tick}${markers}
      <text class="axis" x="${(PAD.left + W - PAD.right) / 2}" y="${H - 6}" text-anchor="middle">outdoor temperature [\u00b0C]</text>
      <text class="axis" transform="translate(12 ${(PAD.top + H - PAD.bottom) / 2}) rotate(-90)" text-anchor="middle">supply temperature [\u00b0C]</text>
    </svg>`;
  }
}

const TAG = "genesis-wp-heating-curve-card";
registerCard(TAG, GenesisWpHeatingCurveCard, {
  name: 'Genesis WP heating curve',
  description: 'Heating curves of one or more heating circuits in one chart, each with its current operating point.',
});
