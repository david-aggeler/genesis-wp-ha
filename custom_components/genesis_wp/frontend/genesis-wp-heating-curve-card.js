// Heating curve card for genesis_wp (requirement-11): the heating curves of one or more heating
// circuits in one chart as supply temperature over outdoor temperature, each with its current
// operating point. Read-only, no dependencies.
// Config: { type: custom:genesis-wp-heating-curve-card, entities: [<set temperature sensor>, ...] | entity: <one>, title?: str }

const W = 400;
const H = 260;
const PAD = { left: 48, right: 14, top: 14, bottom: 42 };
// Circuit 1 keeps the theme color; further circuits get distinct theme colors with fallbacks.
const COLORS = ["var(--primary-color)", "var(--info-color, #039be5)", "var(--success-color, #43a047)", "var(--warning-color, #ffa600)"];

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
    const entities = config && (config.entities || (config.entity ? [config.entity] : []));
    if (!Array.isArray(entities) || entities.length === 0 || !entities.every((e) => typeof e === "string" && e)) {
      throw new Error("entity or entities is required: the heating circuits' set temperature sensors");
    }
    this._config = config;
    this._entities = entities;
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
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 12px 12px 4px; }
        .title { font-size: 1.1em; margin: 0 0 6px 4px; color: var(--primary-text-color); }
        .legend { display: flex; flex-wrap: wrap; gap: 4px 16px; margin: 0 0 4px 4px; color: var(--secondary-text-color); font-size: 0.9em; }
        .legend-item { display: inline-flex; align-items: center; gap: 6px; }
        .swatch { width: 14px; height: 3px; border-radius: 2px; }
        svg { width: 100%; height: auto; display: block; }
        .grid { stroke: var(--divider-color, currentColor); stroke-opacity: 0.6; }
        .label { fill: var(--secondary-text-color); font-size: 11px; }
        .curve { fill: none; stroke-width: 2.5; }
        .now { stroke: var(--card-background-color, #fff); stroke-width: 2; }
        .single .now { fill: var(--accent-color, #ff9800); }
        .empty { color: var(--secondary-text-color); padding: 16px 4px; }
      </style>
      <ha-card>
        <div class="title">${escapeText(title)}</div>
        ${legend}
        ${body}
      </ha-card>`;
  }

  _svg(series, single) {
    const xs = series.flatMap((s) => s.curve.map((p) => p[0]).concat(s.now ? [s.now[0]] : []));
    const ys = series.flatMap((s) => s.curve.map((p) => p[1]).concat(s.now ? [s.now[1]] : []));
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

    return `<svg class="${single ? "single" : "overlay"}" viewBox="0 0 ${W} ${H}" role="img" aria-label="heating curves">
      ${xGrid}${yGrid}
      ${curves}${markers}
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
  description: "Heating curves of one or more heating circuits in one chart, each with its current operating point.",
});
