// Heating curve card for genesis_wp (requirement-11): one heating circuit's curve as supply
// temperature over outdoor temperature, plus the current operating point. Read-only, no
// dependencies. Config: { type: custom:genesis-wp-heating-curve-card, entity: <set temperature sensor>, title?: str }

const W = 400;
const H = 260;
const PAD = { left: 48, right: 14, top: 14, bottom: 42 };

function escapeText(value) {
  return String(value).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
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

class GenesisWpHeatingCurveCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("entity is required: the heating circuit's set temperature sensor");
    }
    this._config = config;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 5;
  }

  static getStubConfig(hass) {
    const entity = Object.keys(hass.states).find((id) => Array.isArray(hass.states[id].attributes.curve));
    return { entity: entity || "" };
  }

  _render() {
    if (!this._config || !this._hass || !this.shadowRoot) return;
    const state = this._hass.states[this._config.entity];
    const title = this._config.title || (state && state.attributes.friendly_name) || this._config.entity;
    const curve = state && Array.isArray(state.attributes.curve) ? state.attributes.curve : [];
    const setPoint = state ? Number.parseFloat(state.state) : Number.NaN;
    const outdoor = state ? state.attributes.outdoor_temperature : null;
    const hasPoint = Number.isFinite(setPoint) && typeof outdoor === "number";

    let body;
    if (curve.length < 2) {
      body = `<div class="empty">No heating curve on ${escapeText(this._config.entity)}</div>`;
    } else {
      body = this._svg(curve, hasPoint ? [outdoor, setPoint] : null);
    }
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 12px 12px 4px; }
        .title { font-size: 1.1em; margin: 0 0 6px 4px; color: var(--primary-text-color); }
        svg { width: 100%; height: auto; display: block; }
        .grid { stroke: var(--divider-color, currentColor); stroke-opacity: 0.6; }
        .label { fill: var(--secondary-text-color); font-size: 11px; }
        .curve { fill: none; stroke: var(--primary-color); stroke-width: 2.5; }
        .dot { fill: var(--primary-color); }
        .now { fill: var(--accent-color, #ff9800); stroke: var(--card-background-color, #fff); stroke-width: 2; }
        .empty { color: var(--secondary-text-color); padding: 16px 4px; }
      </style>
      <ha-card>
        <div class="title">${escapeText(title)}</div>
        ${body}
      </ha-card>`;
  }

  _svg(curve, now) {
    const xs = curve.map((p) => p[0]).concat(now ? [now[0]] : []);
    const ys = curve.map((p) => p[1]).concat(now ? [now[1]] : []);
    const ax = axis(xs);
    const ay = axis(ys);
    const px = (x) => PAD.left + ((x - ax.low) / (ax.high - ax.low)) * (W - PAD.left - PAD.right);
    const py = (y) => H - PAD.bottom - ((y - ay.low) / (ay.high - ay.low)) * (H - PAD.top - PAD.bottom);
    const sorted = [...curve].sort((a, b) => a[0] - b[0]);

    const xGrid = ticks(ax)
      .map((x) => `<line class="grid" x1="${px(x)}" x2="${px(x)}" y1="${PAD.top}" y2="${H - PAD.bottom}"/>
        <text class="label" x="${px(x)}" y="${H - PAD.bottom + 14}" text-anchor="middle">${x}</text>`)
      .join("");
    const yGrid = ticks(ay)
      .map((y) => `<line class="grid" x1="${PAD.left}" x2="${W - PAD.right}" y1="${py(y)}" y2="${py(y)}"/>
        <text class="label" x="${PAD.left - 6}" y="${py(y) + 4}" text-anchor="end">${y}</text>`)
      .join("");
    const line = sorted.map((p) => `${px(p[0])},${py(p[1])}`).join(" ");
    const dots = sorted
      .map((p) => `<circle class="dot" cx="${px(p[0])}" cy="${py(p[1])}" r="3.5"><title>${p[0]} \u00b0C outdoor: ${p[1]} \u00b0C</title></circle>`)
      .join("");
    const marker = now
      ? `<circle class="now" cx="${px(now[0])}" cy="${py(now[1])}" r="6"><title>now: ${now[0]} \u00b0C outdoor, ${now[1]} \u00b0C set</title></circle>`
      : "";

    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="heating curve">
      ${xGrid}${yGrid}
      <polyline class="curve" points="${line}"/>
      ${dots}${marker}
      <text class="label" x="${(PAD.left + W - PAD.right) / 2}" y="${H - 6}" text-anchor="middle">outdoor temperature [\u00b0C]</text>
      <text class="label" transform="translate(12 ${(PAD.top + H - PAD.bottom) / 2}) rotate(-90)" text-anchor="middle">supply temperature [\u00b0C]</text>
    </svg>`;
  }
}

const TAG = "genesis-wp-heating-curve-card";

// Home Assistant's frontend replaces window.customElements with a scoped-registry polyfill and
// looks cards up there; this module can run before that swap (issue-6). Define the card once
// HA's own hui-view is in the current registry, so the definition lands where HA looks.
function register() {
  const registry = window.customElements;
  if (!registry.get("hui-view")) return false;
  if (!registry.get(TAG)) registry.define(TAG, GenesisWpHeatingCurveCard);
  return true;
}

if (!register()) {
  const started = Date.now();
  let warned = false;
  const timer = setInterval(() => {
    if (register()) {
      clearInterval(timer);
    } else if (!warned && Date.now() - started > 30000) {
      warned = true;
      console.warn(`${TAG}: not defined yet, Home Assistant's hui-view is not in window.customElements`);
    }
  }, 250);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: TAG,
  name: "Genesis WP heating curve",
  description: "Heating curve of one heating circuit with the current operating point.",
});
