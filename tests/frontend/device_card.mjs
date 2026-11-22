import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const fixture = JSON.parse(readFileSync(0, 'utf8'));
class Registry { constructor() { this.items = new Map(); } get(k) { return this.items.get(k); } define(k, v) { assert.ok(!this.get(k)); this.items.set(k,v); } }
globalThis.window = globalThis;
globalThis.HTMLElement = class { attachShadow() { this.shadowRoot = {innerHTML:''}; } };
globalThis.customElements = new Registry();
const { temperatureColor } = await import(pathToFileURL(process.argv[2]));
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-65
assert.equal(customElements.get('genesis-wp-device-card'), undefined);
globalThis.customElements = new Registry();
customElements.define('hui-view', class {});
await new Promise(r=>setTimeout(r,600));
const Card = customElements.get('genesis-wp-device-card');
assert.ok(Card);
const categories = ['internal_heat_pump','hot_water','cooling','pool','ksm','electric_meter_and_energy','controller'];
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-66
const retired = ['buffer_tank','heating_system','additional_heating_circuits'];
for (const device of [undefined, 'invalid', ...retired]) {
  assert.throws(()=>new Card().setConfig(device === undefined ? {} : {device}),
    {message:`device must be one of: ${categories.join(', ')}`}, String(device));
}
let services = 0, ws = 0;
const hass = {...fixture, callService(){services++;}, callWS(){ws++;}, localize(key){return key.endsWith('.unavailable')?'Unavailable':key.endsWith('.unknown')?'Unknown':undefined;}};
const render = (device, entry=fixture.entry) => { const card = new Card(); card.setConfig({device,entry}); card.hass=hass; return card; };
const html = card => card.shadowRoot.innerHTML;
const byRegister = key => Object.entries(hass.states).find(([,s])=>s.attributes.register===key)?.[0];
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-129
const heatPumpId = Object.keys(hass.devices).find(id => hass.devices[id].identifiers.some(
  ([domain, identifier]) => domain === 'genesis_wp' && identifier === `${fixture.entry}_internal_heat_pump`,
));
assert.ok(heatPumpId);
const siblingEntities = Object.fromEntries(Object.entries(hass.entities)
  .filter(([, entity]) => entity.device_id !== heatPumpId));
assert.equal(siblingEntities[byRegister('input_12')]?.disabled_by, null, 'sibling T33 is enabled');
for (const [scenario, entities] of [['empty registry', {}], ['enabled siblings', siblingEntities]]) {
  for (const layout of [undefined, 'diagram']) {
    const card = new Card();
    card.setConfig({device:'internal_heat_pump', entry:fixture.entry, layout});
    card.hass = {...hass, entities};
    const output = html(card);
    const context = `${layout ?? 'card'}, ${scenario}`;
    assert.match(output, /<p>No enabled entities for this device<\/p>/, context);
    assert.doesNotMatch(output, /<svg\b|Temperature legend|pipe color = measured temperature/, context);
  }
}
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-73 genesis-wp-ha/ac-129
// An enabled own registry entity without a current state is not an empty device: T33 stays as context.
{
  const waitingId = Object.keys(hass.entities).find(id => hass.entities[id].device_id === heatPumpId && !hass.entities[id].disabled_by);
  assert.ok(waitingId, 'an enabled heat-pump registry entity exists');
  const t33 = byRegister('input_12');
  const entities = {...siblingEntities, [waitingId]: hass.entities[waitingId]};
  const states = Object.fromEntries(Object.entries(hass.states).filter(([id]) => id !== waitingId));
  for (const layout of [undefined, 'diagram']) {
    const card = new Card();
    card.setConfig({device:'internal_heat_pump', entry:fixture.entry, layout});
    card.hass = {...hass, entities, states};
    const output = html(card);
    const context = `${layout ?? 'card'}, waiting own entity`;
    assert.doesNotMatch(output, /No enabled entities for this device/, context);
    assert.match(output, new RegExp(`class="[^"]*\\bcontext\\b[^"]*"[^>]*data-register="input_12"[^>]*data-entity="${t33.replace(/\./g, '\\.')}"`), context);
  }
}
const tag = (card, key) => html(card).match(new RegExp(`<g[^>]*data-register="${key}"[^>]*>[\\s\\S]*?<\\/g>`))?.[0];
const pipe = (card, id) => html(card).match(new RegExp(`<path[^>]*data-path="${id}"[^>]*>`))?.[0];
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-126 genesis-wp-ha/ac-127 genesis-wp-ha/ac-128
for (const [device, register, width] of [['hot_water', 'input_15', 150], ['controller', 'input_55', 260]]) {
  const id = byRegister(register);
  const deviceName = hass.devices[hass.entities[id].device_id].name;
  const wideLabel = `${'W'.repeat(19)}é👩‍🔧${'W'.repeat(20)} & status`;
  const fullName = `${deviceName} ${wideLabel}`;
  const states = structuredClone(hass.states);
  states[id].attributes.friendly_name = fullName;
  const card = new Card();
  card.setConfig({device, entry:fixture.entry});
  card.hass = {...hass, states, locale:{language:'en'}};
  const rendered = tag(card, register);
  assert.ok(rendered, register);
  const label = rendered.match(/<div class="tag-label">([^<]+)<\/div>/)?.[1];
  assert.equal(label, device === 'controller' ? wideLabel.replace('&', '&amp;') : 'Top', register);
  assert.ok(rendered.includes(`<title>${fullName.replace('&', '&amp;')}</title>`), register);
  assert.ok(rendered.includes(`<foreignObject x="6" y="2" width="${width - 12}" height="18">`), register);
  const rule = html(card).match(/\.tag-label\{([^}]+)}/)?.[1];
  for (const declaration of ['overflow:hidden', 'white-space:nowrap', 'text-overflow:ellipsis']) {
    assert.ok(rule?.includes(declaration), declaration);
  }
}
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-126
// formal_review-50 B1: prefix plus trailing "Temperature" must not render a blank label.
{
  const id = byRegister('input_55');
  const deviceName = hass.devices[hass.entities[id].device_id].name;
  const states = structuredClone(hass.states);
  states[id].attributes.friendly_name = `${deviceName}  Temperature`;
  const card = new Card();
  card.setConfig({device:'controller', entry:fixture.entry});
  card.hass = {...hass, states, locale:{language:'en'}};
  const label = tag(card, 'input_55')?.match(/<div class="tag-label">([^<]*)<\/div>/)?.[1];
  assert.equal(label, 'Temperature');
  assert.ok(!label.startsWith(deviceName));
}
{
  const states = structuredClone(hass.states);
  states[byRegister('input_1')].state = 'Heat';
  states[byRegister('input_12')].state = '26.26';
  const estimates = ['derived_condenser_flow', 'derived_brine_flow', 'derived_hc2_return'];
  const calculated = [18, 122, 124, 125, 126, 147].map(address => `input_${address}`);
  for (const register of [...estimates, ...calculated, 'input_17', 'input_68']) {
    states[byRegister(register)].state = '13.7';
  }
  const renderWithStates = (device, layout, entities = hass.entities) => {
    const card = new Card();
    card.setConfig({device, entry:fixture.entry, layout});
    card.hass = {...hass, states, entities};
    return card;
  };
  const positionedChip = (card, register) => html(card).match(new RegExp(
    `<div class="chip [^"]*"[^>]*data-register="${register}"[^>]*>[\\s\\S]*?</div>`
  ))?.[0];
  const checkDashedValue = (card, register, source, layout) => {
    const positioned = layout === 'diagram';
    const chip = positioned ? positionedChip(card, register) : tag(card, register);
    const label = `${register} (${layout ?? 'card'})`;
    assert.ok(chip, label);
    const classes = chip.match(/^<\w+ class="([^"]+)"/)[1].split(/\s+/);
    assert.ok(classes.includes(source), label);
    assert.match(chip, positioned
      ? /<svg class="chip-border"[^>]*>\s*<rect\b[^>]*\/?>\s*<\/svg>/
      : /<rect\b[^>]*>/, label);

    const style = html(card).match(/<style>([\s\S]*?)<\/style>/)[1];
    const dashRules = [...style.matchAll(/([^{}]+)\{[^{}]*\bstroke-dasharray:\s*6\s+3\s*(?:;|\})/g)];
    const selectors = dashRules.flatMap(rule => rule[1].trim().split(/\s*,\s*/));
    assert.ok(selectors.includes(`.${source} rect`), label);

    const value = chip.match(/class="value"[^>]*>([^<]+)<\/(?:span|text)>/)?.[1];
    assert.ok(value?.includes('13.7'), label);
    if (source === 'estimated') assert.match(value, /^≈ 13\.7/, label);
    else assert.doesNotMatch(value, /≈/, label);
  };
  for (const layout of [undefined, 'diagram']) {
    const card = renderWithStates('internal_heat_pump', layout);
    const out = html(card);
    const contextChip = layout === 'diagram' ? positionedChip(card, 'input_12') : tag(card, 'input_12');
    // DHF-TEST: genesis-wp-ha/requirement-27 genesis-wp-ha/ac-112
    assert.match(contextChip, /class="[^"]*context/);
    assert.match(out, /\.context\{opacity:0?\.75\}/);
    assert.doesNotMatch(out, /\.context[^{}]*\{[^{}]*(?:dotted|stroke-dasharray)/);
    // DHF-TEST: genesis-wp-ha/requirement-27 genesis-wp-ha/ac-113
    for (const register of estimates) checkDashedValue(card, register, 'estimated', layout);
    // DHF-TEST: genesis-wp-ha/requirement-27 genesis-wp-ha/ac-114
    for (const register of calculated) checkDashedValue(card, register, 'calculated', layout);
    checkDashedValue(renderWithStates('hot_water', layout), 'input_17', 'calculated', layout);
    // DHF-TEST: genesis-wp-ha/requirement-27 genesis-wp-ha/ac-115
    assert.match(pipe(card,'bypass'), /data-flow="active"[^>]*stroke="currentColor" stroke-opacity="0.75"/);
    assert.match(pipe(card,'cooling-return'), /data-flow="idle"[^>]*stroke-opacity="0.22"/);
    assert.match(pipe(card,'either-way'), /data-flow="active"[^>]*stroke="#[0-9a-f]+" stroke-opacity="1"/);
    // DHF-TEST: genesis-wp-ha/requirement-27 genesis-wp-ha/ac-116
    const fullLegend = 'solid: measured; faded chip: other section; dashed: calculated by the controller; ≈: estimated; faded: idle; gray: no sensor';
    if (layout === 'diagram') assert.ok(out.includes(fullLegend));
    else {
      // The standalone SVG cannot wrap: every style-legend line must fit the legend viewport.
      // Budget: 8px text at 4.2 units per character (DejaVu Sans measured 498 units for the
      // 120-character single line), so a line fits when chars * 4.2 <= the viewBox width.
      const legendSvg = out.match(/<svg viewBox="0 0 (\d+) (\d+)" aria-label="Temperature legend">.*?<\/svg>/s);
      assert.ok(legendSvg, 'standalone legend svg');
      const [svg, width, height] = [legendSvg[0], Number(legendSvg[1]), Number(legendSvg[2])];
      const lines = [...svg.matchAll(/<text x="0" y="(\d+)" class="style-legend">([^<]+)<\/text>/g)];
      assert.ok(lines.length >= 2, 'style legend wraps into lines');
      assert.equal(lines.map(m => m[2]).join(' '), fullLegend);
      for (const [, y, text] of lines) {
        assert.ok(text.length * 4.2 <= width, `legend line fits ${width} units: ${text}`);
        assert.ok(Number(y) <= height, `legend line y ${y} inside viewBox height ${height}`);
      }
    }
    assert.doesNotMatch(out, /dashed: calculated</);
  }
  // DHF-TEST: genesis-wp-ha/requirement-27 genesis-wp-ha/ac-114
  // Input 68 has no drawing position. Exercise its value tag through a supported
  // card category while keeping the emulator's register identity and state.
  const chargeTarget = byRegister('input_68');
  const [deviceId] = Object.entries(hass.devices).find(([, device]) =>
    device.identifiers.some(([domain, id]) =>
      domain === 'genesis_wp' && id === `${fixture.entry}_internal_heat_pump`));
  const entities = {...hass.entities, [chargeTarget]: {...hass.entities[chargeTarget], device_id: deviceId}};
  checkDashedValue(renderWithStates('internal_heat_pump', undefined, entities), 'input_68', 'calculated');
}
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-67
{
  const category = 'internal_heat_pump';
  const card = render(category);
  assert.match(html(card), /<svg/);
  const device = Object.entries(hass.devices).find(([,d])=>d.identifiers.some(([domain,id])=>domain==='genesis_wp'&&id===`${fixture.entry}_${category}`))?.[0];
  const own = Object.entries(hass.entities).filter(([,e])=>e.device_id===device&&!e.disabled_by);
  assert.ok(own.length);
  for (const [id] of own) {
    const state=hass.states[id];
    assert.ok(html(card).includes(`data-entity="${id}"`), `${category}: ${id} omitted`);
    if (!['unknown','unavailable'].includes(state.state)) {
      assert.ok(html(card).includes(state.state));
    }
  }
}
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-67
// Expected full-plant tag inventory, independent of the card's position table.
const plantAnchors = [
  // Heat pump and passive cooling
  ...[10,11,130,127,124,125,5,61,48,7,128,122,129,126,9,8,39,44].map(address => `input_${address}`),
  'derived_brine_flow', 'derived_condenser_flow', 'coil_33', 'holding_302',
  // Controller and KSM
  'input_315', 'input_319', 'input_67', 'input_413',
  // HC1, buffer tank and HC2
  'holding_5', 'coil_9', 'holding_4', 'holding_3', 'input_18', 'input_12', 'input_41',
  'holding_107', 'holding_108', 'coil_11', 'input_43', 'input_147', 'input_40', 'derived_hc2_return',
];
let card=render('internal_heat_pump');
for (const key of plantAnchors) {
  const id=byRegister(key);
  assert.ok(id,key);
  const state=hass.states[id];
  const rendered=tag(card,key);
  assert.ok(rendered,key);
  assert.ok(rendered.includes(`data-entity="${id}"`), key);
  const diagram = html(card).match(/<svg[\s\S]*?<\/svg>/)?.[0];
  assert.ok(diagram?.includes(rendered), `${key}: tag outside the drawing`);
  const prefix = key.startsWith('derived_') ? '≈ ' : '';
  const expected=['unknown','unavailable'].includes(state.state)
    ? hass.localize('state.default.'+state.state)
    : prefix + [state.state,state.attributes.unit_of_measurement].filter(Boolean).join(' ');
  assert.equal(rendered.match(/class="value"[^>]*>(.*?)<\/text>/)?.[1],expected,key);
  assert.equal(html(card).split(`data-register="${key}"`).length,2,key);
  const previous=state.state;
  state.state='37.125'; card.hass=hass;
  assert.equal(tag(card,key).match(/class="value"[^>]*>(.*?)<\/text>/)?.[1],
    [prefix + '37.125',state.attributes.unit_of_measurement].filter(Boolean).join(' '));
  state.state=previous; card.hass=hass;
}
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-73
assert.match(tag(card,'input_12'), /class="[^"]*\bcontext\b/);
assert.doesNotMatch(tag(card,'input_12'), /class="[^"]*\bown\b/);
assert.match(tag(card,'input_18'), /calculated/);
const supply=byRegister('input_12'), mode=byRegister('input_1');
hass.states[mode].state='Heat';
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-69
hass.states[supply].state='26.26'; card.hass=hass;
assert.match(pipe(card,'either-way'), /stroke="#eca143"/);
hass.states[supply].state='40.0'; card.hass=hass;
assert.match(pipe(card,'either-way'), /stroke="#df4e29"/);
// HA display-unit conversion: equivalent °F and K readings color the same as °C; the tag keeps the display unit.
const supplyUnit=hass.states[supply].attributes.unit_of_measurement;
for (const [value, unit] of [['104.0','°F'],['313.15','K']]) {
  hass.states[supply].state=value; hass.states[supply].attributes.unit_of_measurement=unit; card.hass=hass;
  assert.match(pipe(card,'either-way'), /stroke="#df4e29"/);
  assert.match(tag(card,'input_12'), new RegExp(`>${value} ${unit}</text>`));
}
hass.states[supply].attributes.unit_of_measurement='kW'; card.hass=hass;
assert.match(pipe(card,'either-way'), /stroke="currentColor"/);
hass.states[supply].attributes.unit_of_measurement=supplyUnit;
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-68
const localizedStates = {unavailable:'Measurement missing', unknown:'State undetermined'};
const localize = hass.localize;
hass.localize = key => ({
  'state.default.unavailable': localizedStates.unavailable,
  'state.default.unknown': localizedStates.unknown,
})[key] ?? localize(key);
for (const [state, expected] of Object.entries(localizedStates)) {
  hass.states[supply].state = state;
  card.hass = hass;
  const value = tag(card,'input_12')?.match(/class="value"[^>]*>(.*?)<\/text>/)?.[1];
  assert.equal(value, expected, state);
  assert.doesNotMatch(value, /[0-9]/);
  assert.match(pipe(card,'either-way'), /data-flow="active"/);
  assert.match(pipe(card,'either-way'), /stroke="currentColor" stroke-opacity="1"/);
}
hass.localize = localize;
hass.states[supply].state='26.26';
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-70
hass.states[byRegister('input_40')].state='26.26';
card=render('internal_heat_pump');
assert.match(pipe(card,'hc2-port-b'), /data-flow="active"/);
assert.match(pipe(card,'passive-port-a'), /data-flow="idle"/);
assert.match(pipe(card,'passive-port-a'), /stroke="currentColor" stroke-opacity="0.22"/);
assert.match(pipe(card,'hc2-port-b'), /stroke="#eca143" stroke-opacity="1"/);
hass.states[mode].state='Passive cooling';
const coil=byRegister('coil_33'); hass.states[coil].state='on'; card.hass=hass;
assert.match(pipe(card,'hc2-port-b'), /data-flow="idle"/);
assert.match(pipe(card,'passive-port-a'), /data-flow="active"/);
assert.match(pipe(card,'hc2-port-b'), /stroke="currentColor" stroke-opacity="0.22"/);
assert.match(pipe(card,'passive-port-a'), /stroke="#eca143" stroke-opacity="1"/);
for(const state of ['Heat','Defrost','Hot water','Anti legionella','Pool','Cool','Standby','No demand','OFF','Manual Operation']) {
  hass.states[mode].state=state; card.hass=hass;
  assert.match(pipe(card,'hc2-port-b'), /data-flow="active"/);
  assert.match(pipe(card,'passive-port-a'), /data-flow="idle"/);
  assert.match(pipe(card,'passive-port-a'), /stroke="currentColor" stroke-opacity="0.22"/);
  assert.match(pipe(card,'hc2-port-b'), /stroke="#eca143" stroke-opacity="1"/);
}
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-74
const hpDevice=hass.entities[byRegister('input_54')].device_id;
hass.entities['sensor.test_setting']={device_id:hpDevice};
hass.states['sensor.test_setting']={state:'12',attributes:{register:'holding_999',friendly_name:'Test setting',unit_of_measurement:'K'}};
hass.states[byRegister('input_54')].state='63.5';
card=render('internal_heat_pump');
const panel=html(card).slice(html(card).indexOf('class="values"'));
assert.match(panel, /data-register="input_54"/);
assert.match(panel, /data-register="holding_999"/);
assert.match(tag(card,'input_54'), />63.5 %<\/text>/);
assert.match(tag(card,'holding_999'), />12 K<\/text>/);
const measurementIndex=panel.indexOf(`data-entity="${byRegister('input_54')}"`);
const settingIndex=panel.indexOf('data-entity="sensor.test_setting"');
assert.ok(measurementIndex>=0 && settingIndex>=0 && measurementIndex<settingIndex);
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-75
const alarms=Object.entries(hass.states).filter(([id,s])=>hass.entities[id].device_id===hpDevice && s.attributes.device_class==='problem');
assert.ok(alarms.length>1);
for(const [,s] of alarms) s.state='off';
alarms[0][1].state='on'; card.hass=hass;
assert.match(html(card), /class="alarms"/);
const strip=html(card).match(/<div class="alarms"[^>]*>(.*?)<\/div>/)?.[1];
assert.equal(strip,alarms[0][1].attributes.friendly_name);
for(const [,state] of alarms.slice(1)) assert.ok(!strip.includes(state.attributes.friendly_name));
alarms[0][1].state='off'; card.hass=hass;
assert.doesNotMatch(html(card), /class="alarms"/);
// Missing child, another entry, disabled entities and untrusted text are safe.
assert.match(html(render('internal_heat_pump','absent')), /not found/i);
hass.states[supply].attributes.friendly_name='<img src=x onerror=alert(1)>';
assert.doesNotMatch(html(render('internal_heat_pump')), /<img/);

// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-72
// DHF-TEST: genesis-wp-ha/ac-66 genesis-wp-ha/ac-68 genesis-wp-ha/ac-71
// DHF-TEST: genesis-wp-ha/ac-74 genesis-wp-ha/ac-75
for (const category of categories.slice(1)) {
  const device=Object.entries(hass.devices).find(([,d])=>d.identifiers.some(([domain,id])=>domain==='genesis_wp'&&id===`${fixture.entry}_${category}`))?.[0];
  assert.ok(device,category);
  const own=Object.entries(hass.entities).filter(([,e])=>e.device_id===device&&!e.disabled_by);
  assert.ok(own.length,category);
  const card=render(category);
  assert.match(html(card),/<svg/);
  assert.doesNotMatch(html(card),/not drawn yet/i);
  for (const [id] of own) {
    const state=hass.states[id], register=state.attributes.register;
    const value=()=>tag(card,register)?.match(/class="value"[^>]*>(.*?)<\/text>/)?.[1];
    assert.equal(value(), ['unknown','unavailable'].includes(state.state)
      ? hass.localize('state.default.'+state.state)
      : [state.state,state.attributes.unit_of_measurement].filter(Boolean).join(' '),id);
    const original=state.state;
    for(const next of ['37.125','unknown','unavailable']) {
      state.state=next; card.hass=hass;
      assert.equal(value(),next==='37.125'
        ? [next,state.attributes.unit_of_measurement].filter(Boolean).join(' ')
        : hass.localize('state.default.'+next),id);
    }
    state.state=original; card.hass=hass;
  }
  // Unpositioned settings follow measurements in the shared values panel.
  hass.entities['sensor.new_setting']={device_id:device};
  hass.states['sensor.new_setting']={state:'12',attributes:{register:'holding_998',unit_of_measurement:'K'}};
  hass.entities['sensor.new_measurement']={device_id:device};
  hass.states['sensor.new_measurement']={state:'23',attributes:{register:'input_998',unit_of_measurement:'K'}};
  card.hass=hass;
  const panel=html(card).slice(html(card).indexOf('class="values"'));
  assert.ok(panel.indexOf('data-register="input_998"')<panel.indexOf('data-register="holding_998"'));
  assert.match(tag(card,'holding_998'),/>12 K<\/text>/);
  const alarms=own.filter(([id])=>id.startsWith('binary_sensor.')&&hass.states[id].attributes.device_class==='problem');
  for(const [id] of alarms) hass.states[id].state='off';
  card.hass=hass;
  assert.doesNotMatch(html(card),/class="alarms"/);
  if(alarms.length && category!=='ksm') {
    hass.states[alarms[0][0]].state='on'; card.hass=hass;
    assert.match(html(card),/class="alarms"/);
    hass.states[alarms[0][0]].state='off';
  }
  delete hass.entities['sensor.new_setting']; delete hass.states['sensor.new_setting'];
  delete hass.entities['sensor.new_measurement']; delete hass.states['sensor.new_measurement'];
}
for(const [category,keys] of Object.entries({
  hot_water:[15,16,17,45,47,117,118],cooling:[106,103,104,105,92],pool:[119,120,94]
})) {
  const card=render(category);
  for(const address of keys) {
    const id=byRegister('input_'+address);
    if(id) assert.ok(html(card).split('class="values"')[0].includes(`data-register="input_${address}"`));
  }
}


// Circuit activity and unavailable measurements use the same rendering contract.
for(const [category,path,register,activeMode] of [
  ['hot_water','tank-top','input_15','Hot water'],
  ['cooling','cooling-supply','input_106','Cool'],
  ['pool','pool-supply','input_119','Pool']
]) {
  const state=hass.states[byRegister(register)], original=state.state;
  hass.states[mode].state=activeMode; state.state='40.0';
  const card=render(category);
  assert.match(pipe(card,path),/data-flow="active".*stroke="#df4e29"/);
  state.state='unavailable'; card.hass=hass;
  assert.match(pipe(card,path),/stroke="currentColor"/);
  state.state='40.0'; hass.states[mode].state='Standby'; card.hass=hass;
  assert.match(pipe(card,path),/data-flow="idle".*stroke="currentColor"/);
  state.state=original;
}
// A three-phase table and controller sections keep the large panels readable.
card=render('electric_meter_and_energy');
for(const phase of ['L1','L2','L3']) assert.match(html(card),new RegExp('>'+phase+'</text>'));
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-72
// Each phase measurement can be the only enabled entity; absent/disabled peers
// must not remove the headings that identify its column.
const meterRegisters=[157,158,69,70,71,72,73,74,78,79,80].map(n=>'input_'+n);
const meterIds=meterRegisters.map(byRegister);
assert.ok(meterIds.every(Boolean));
for(const disposition of ['missing','disabled']) {
  for(const address of [69,70,71,72,73,74,78,79,80]) {
    const retained=byRegister('input_'+address);
    const entities={...hass.entities};
    for(const id of meterIds) if(id!==retained) {
      if(disposition==='missing') delete entities[id];
      else entities[id]={...entities[id],disabled_by:'user'};
    }
    const partial=new Card(); partial.setConfig({device:'electric_meter_and_energy',entry:fixture.entry});
    partial.hass={...hass,entities};
    assert.ok(tag(partial,'input_'+address),`${disposition}: input_${address}`);
    for(const phase of ['L1','L2','L3']) {
      assert.ok(html(partial).includes('>'+phase+'</text>'),`${disposition}: input_${address} lost ${phase}`);
    }
  }
}
card=render('controller');
for(const group of ['Operation','Plant','Gears','Versions']) assert.ok(html(card).includes('>'+group+'</text>'));
const leak=byRegister('dinput_251');
hass.states[leak].state='on'; card=render('ksm');
assert.match(tag(card,'dinput_251'),/class="fault own chip"/);
assert.doesNotMatch(html(card),/class="alarms"/);
hass.states[leak].state='off'; card.hass=hass;
assert.doesNotMatch(tag(card,'dinput_251'),/class="fault/);
for(const category of ['ksm','electric_meter_and_energy','controller']) {
  assert.doesNotMatch(html(render(category)),/data-path=/);
}

// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-71
assert.equal(services,0); assert.equal(ws,0);
// DHF-TEST: genesis-wp-ha/requirement-27 genesis-wp-ha/ac-119 genesis-wp-ha/ac-120 genesis-wp-ha/ac-121 genesis-wp-ha/ac-122 genesis-wp-ha/ac-123 genesis-wp-ha/ac-124
{
  const states = structuredClone(hass.states);
  const entities = structuredClone(hass.entities);
  const set = (register, value) => {
    const id = byRegister(register);
    assert.ok(id, register);
    entities[id].disabled_by = null;
    states[id].state = value;
    return states[id].attributes;
  };
  set('input_1', 'Heat');
  set('derived_condenser_flow', '20');
  set('derived_brine_flow', '2');
  const returnState = states[byRegister('derived_hc2_return')];
  assert.equal(returnState.state, 'unavailable');
  set('dinput_209', 'on');
  const renderFlow = (flow_speed, darkMode = false) => {
    const card = new Card();
    card.setConfig({device:'internal_heat_pump', entry:fixture.entry, flow_speed});
    card.hass = {...hass, states, entities, themes:{darkMode}};
    return card;
  };
  const markers = (card, leg) => html(card).match(new RegExp(
    `<g data-chevrons="${leg}"[^>]*>([\\s\\S]*?)</g>`,
  ))?.[1] || '';
  const duration = (card, leg) => Number(markers(card, leg).match(/dur="([0-9.]+)s"/)?.[1]);
  const card = renderFlow(0.5);
  assert.equal(duration(card, 'condenser-out'), 10);
  assert.ok(Math.abs(duration(card, 'brine-hx') - 67.7777777778) < 0.0001);
  assert.ok(Math.abs(duration(card, 'hc2-supply') - 7.20130932897) < 0.0001);
  assert.ok(Math.abs(duration(card, 'room-return') - 13.2751391169) < 0.0001);
  assert.equal(duration(renderFlow(), 'condenser-out'), 31.25);
  card.setConfig({device:'internal_heat_pump', entry:fixture.entry, flow_speed:1});
  assert.equal(duration(card, 'condenser-out'), 5);
  card.setConfig({device:'internal_heat_pump', entry:fixture.entry, flow_speed:0.5});
  const pumpSymbols = html(card).match(/<(?:circle class="pump"|path data-flow-direction)[^>]*>/g);
  assert.ok(pumpSymbols.length);
  for (const symbol of pumpSymbols) assert.ok(symbol.endsWith('/>'), symbol);
  assert.match(html(card), /data-chevrons="condenser-out"[^>]*stroke="white" stroke-opacity="0.8"/);
  assert.match(html(renderFlow(0.5, true)), /data-chevrons="condenser-out"[^>]*stroke="black" stroke-opacity="0.55"/);
  assert.match(html(card), /data-chevrons="condenser-out"[^>]*stroke-width="1.1"/);
  assert.match(markers(card, 'condenser-out'), /M-3,-1.7 L0.5,0 L-3,1.7/);
  assert.match(markers(card, 'room-return'), /path="M1815,470 L1815,560 L1540,560"/);
  const converted = set('derived_condenser_flow', '1.2');
  converted.unit_of_measurement = 'm³/h';
  assert.equal(duration(renderFlow(0.5), 'hc2-supply'), duration(card, 'hc2-supply'));
  converted.unit_of_measurement = 'L/min';
  set('derived_condenser_flow', 'unavailable');
  const unknown = renderFlow(0.5);
  assert.equal(markers(unknown, 'condenser-out'), '');
  assert.equal(markers(unknown, 'hc2-supply'), '');
  assert.match(pipe(unknown, 'condenser-out'), /data-flow="active"/);
  set('derived_condenser_flow', '20');
  set('dinput_209', 'unavailable');
  assert.equal(markers(renderFlow(), 'hc2-supply'), '');
  set('dinput_209', 'on');
  assert.match(markers(card, 'condenser-out'), /path="M920,290 L1220,290" rotate="auto"/);
  for (const leg of ['either-way', 'hc2-port-b', 'tr9-mixer', 'bypass', 'room-return-buffer', 'suction']) {
    assert.equal(markers(card, leg), '', leg);
  }
  assert.match(pipe(card, 'bypass'), /data-flow="active"[^>]*stroke="currentColor" stroke-opacity="0.75"/);
  let listener;
  const preference = {
    matches: true,
    addEventListener(type, callback) { assert.equal(type, 'change'); listener = callback; },
    removeEventListener(type, callback) { assert.equal(type, 'change'); assert.equal(listener, callback); listener = undefined; },
  };
  globalThis.matchMedia = query => {
    assert.equal(query, '(prefers-reduced-motion: reduce)');
    return preference;
  };
  const reduced = renderFlow(0.5);
  reduced.connectedCallback();
  const pipeTags = () => html(reduced).match(/<path data-path[^>]*>/g);
  assert.doesNotMatch(html(reduced), /<animateMotion/);
  assert.deepEqual(pipeTags(), html(card).match(/<path data-path[^>]*>/g));
  for (const matches of [false, true]) {
    preference.matches = matches;
    listener({matches});
    assert.equal(duration(reduced, 'condenser-out'), matches ? NaN : 10);
    assert.deepEqual(pipeTags(), html(card).match(/<path data-path[^>]*>/g));
  }
  reduced.disconnectedCallback();
  assert.equal(listener, undefined);
  delete globalThis.matchMedia;
  returnState.attributes.circuit_flow = 0;
  const zeroHc2 = renderFlow();
  for (const leg of ['hc2-supply', 'room-return']) {
    assert.match(pipe(zeroHc2, leg), /data-flow="idle"[^>]*stroke="currentColor" stroke-opacity="0.22"/);
    assert.equal(markers(zeroHc2, leg), '');
  }
  returnState.attributes.circuit_flow = 18.33;
  // Reconcile the rendered SVG with the production patcher, then check node identity.
  const {morph} = await import(new URL('./patch.js', pathToFileURL(process.argv[2])));
  const drawingTree = () => {
    const svg = html(card).match(/<svg\b[^>]*>[\s\S]*?<\/svg>/)[0];
    const root = {childNodes:[]};
    const stack = [root];
    for (const [tag, closing, name, attributes] of svg.matchAll(/<(\/?)([\w-]+)([^>]*)>/g)) {
      if (closing) {
        stack.pop();
        continue;
      }
      const attrs = new Map([...attributes.matchAll(/([\w-]+)="([^"]*)"/g)]
        .map(([, key, value]) => [key, value]));
      const node = {
        nodeType:1, nodeName:name, childNodes:[],
        get attributes() { return Array.from(attrs, ([name, value]) => ({name, value})); },
        hasAttribute(key) { return attrs.has(key); },
        getAttribute(key) { return attrs.get(key); },
        setAttribute(key, value) { attrs.set(key, value); },
        removeAttribute(key) { attrs.delete(key); },
        appendChild(child) { this.childNodes.push(child); },
        replaceChild(child, previous) { this.childNodes[this.childNodes.indexOf(previous)] = child; },
        removeChild(child) { this.childNodes.splice(this.childNodes.indexOf(child), 1); },
      };
      stack.at(-1).childNodes.push(node);
      if (!tag.endsWith('/>')) stack.push(node);
    }
    return root.childNodes[0];
  };
  const animation = drawing => drawing.childNodes.find(node => node.getAttribute('class') === 'flow-motion')
    .childNodes.flatMap(slot => slot.childNodes)
    .find(node => node.getAttribute('data-chevrons') === 'condenser-out').childNodes[0].childNodes[0];
  const liveDrawing = drawingTree();
  const liveAnimation = animation(liveDrawing);
  const mixerId = byRegister('input_43');
  const beforeGeometry = html(card);
  entities[mixerId].disabled_by = 'user';
  card.hass = {...hass, states, entities};
  assert.match(beforeGeometry, /TR12\/13/);
  assert.doesNotMatch(html(card), /TR12\/13/);
  morph(liveDrawing, drawingTree());
  assert.equal(animation(liveDrawing), liveAnimation);
  entities[mixerId].disabled_by = null;
  card.hass = {...hass, states, entities};
  morph(liveDrawing, drawingTree());
  assert.equal(animation(liveDrawing), liveAnimation);
  set('derived_brine_flow', '0');
  assert.match(pipe(renderFlow(), 'brine-hx'), /data-flow="idle"[^>]*stroke="currentColor" stroke-opacity="0.22"/);
  assert.equal(markers(renderFlow(), 'brine-hx'), '');
  set('dinput_209', 'off');
  assert.equal(markers(renderFlow(), 'hc2-supply'), '');
  set('derived_condenser_flow', '0');
  const stopped = renderFlow();
  assert.match(pipe(stopped, 'condenser-out'), /data-flow="idle"[^>]*stroke="currentColor" stroke-opacity="0.22"/);
  assert.equal(markers(stopped, 'condenser-out'), '');
  const field = Card.getConfigForm().schema.find(item => item.name === 'flow_speed');
  assert.equal(field.default, 0.16);
  assert.deepEqual(field.selector, {number:{min:0.02,max:1,step:0.01,mode:'slider'}});
  assert.equal(services, 0);
}
// DHF-TEST: genesis-wp-ha/requirement-20 genesis-wp-ha/ac-77
const form = Card.getConfigForm();
assert.deepEqual(form.schema.map(s=>s.name), ['device','title','entry','flow_speed']);
const [deviceField,titleField,entryField] = form.schema;
assert.equal(deviceField.required,true);
assert.equal(deviceField.selector.select.mode,'dropdown');
assert.deepEqual(deviceField.selector.select.options.map(o=>o.value),categories);
assert.deepEqual(deviceField.selector.select.options.map(o=>o.label),[
  'Internal heat pump',
  'Hot water','Cooling','Pool','KSM','Electric meter and energy','Controller']);
assert.deepEqual(titleField.selector,{text:{}});
assert.deepEqual(entryField.selector,{config_entry:{integration:'genesis_wp'}});
for(const field of [titleField,entryField]) assert.ok(!field.required);
for(const field of form.schema) assert.ok(form.computeLabel(field).trim());
const metadata=window.customCards.find(c=>c.type==='genesis-wp-device-card');
assert.ok(metadata.name && metadata.description);
assert.equal(metadata.preview,true);
// DHF-TEST: genesis-wp-ha/requirement-20 genesis-wp-ha/ac-78
for(const {value:device} of deviceField.selector.select.options) {
  for(const optional of [{}, {title:'',entry:''}, {title:'Custom section'}, {entry:fixture.entry,title:'Custom section'}]) {
    const generated=new Card();
    assert.doesNotThrow(()=>generated.setConfig({type:'custom:genesis-wp-device-card',device,...optional}));
    generated.hass=hass;
    const manual=new Card();
    manual.setConfig({device,...(optional.title?{title:optional.title}:{}),...(optional.entry?{entry:optional.entry}:{})});
    manual.hass=hass;
    assert.equal(html(generated),html(manual),device);
    assert.doesNotMatch(html(generated),/Device not found/);
  }
}
// DHF-TEST: genesis-wp-ha/requirement-20 genesis-wp-ha/ac-79
const child=(domain,value)=>({identifiers:[[domain,value]]});
assert.deepEqual(Card.getStubConfig({devices:{
  pool:child('genesis_wp','entry_pool'),
  buffer:child('genesis_wp','entry_buffer_tank'),
  foreign:child('other','entry_internal_heat_pump'),
}}),{device:'pool'});
for (const category of retired) {
  assert.deepEqual(Card.getStubConfig({devices:{only:child('genesis_wp',`entry_${category}`)}}),
    {device:'internal_heat_pump'});
}
for(const category of categories) {
  assert.deepEqual(Card.getStubConfig({devices:{only:child('genesis_wp',`entry_${category}`)}}),{device:category});
}
for(const empty of [undefined,{}, {devices:{}}, {devices:{root:child('genesis_wp','entry'),foreign:child('other','entry_pool')}}]) {
  assert.deepEqual(Card.getStubConfig(empty),{device:'internal_heat_pump'});
}

// DHF-TEST: genesis-wp-ha/requirement-22 genesis-wp-ha/ac-86
{
  const card = render('internal_heat_pump');
  const ids = [...html(card).matchAll(/<g[^>]*data-entity="([^"]+)"[^>]*>/g)];
  assert.ok(ids.length);
  for (const [g] of ids) { assert.match(g, /role="button"/); assert.match(g, /tabindex="0"/); }
  const events = [];
  card.dispatchEvent = e => events.push(e);
  const id = ids[0][1];
  const target = {closest: sel => sel==='[data-entity]' ? {dataset:{entity:id}} : null};
  card._activate({target});
  card._activate({target:{closest:()=>null}});
  assert.equal(events.length, 1);
  assert.equal(events[0].type, 'hass-more-info');
  assert.deepEqual(events[0].detail, {entityId:id});
  assert.ok(events[0].bubbles && events[0].composed);
}
// DHF-TEST: genesis-wp-ha/requirement-21 genesis-wp-ha/ac-90 (diagram layout for the panel)
{
  const card = new Card(); card.setConfig({device:'internal_heat_pump',entry:fixture.entry,layout:'diagram'}); card.hass=hass;
  const out = html(card);
  assert.match(out, /<div class="stage" style="aspect-ratio:1900\/670/);
  assert.doesNotMatch(out, /<ha-card/, 'the panel wraps the diagram in its own card');
  assert.doesNotMatch(out, /<svg class="values"/, 'the panel lists the values itself');
  assert.doesNotMatch(out, /<g class="[^"]*" role="button"/, 'tags are HTML chips, not scaled SVG text');
  const chips = [...out.matchAll(/<div class="chip [^"]*"[^>]*data-entity="([^"]+)" style="left:([\d.]+)%;top:([\d.]+)%;width:([\d.]+)%"[^>]*><span class="label">([^<]*)<\/span>/g)];
  assert.ok(chips.length > 5, String(chips.length));
  for (const [, id, left, top, width, label] of chips) {
    for (const v of [left, top]) assert.ok(Number(v) >= -1 && Number(v) <= 100, `${id}: ${v}`);
    assert.ok(Math.abs(Number(width) - 150/1900*100) < 0.01);
    assert.doesNotMatch(label, / Temperature$/, label);
    const device = hass.devices[hass.entities[id].device_id];
    assert.ok(!label.startsWith(device.name + ' '), label);
  }
  assert.match(out, /<div class="legend">/);
}
// DHF-TEST: genesis-wp-ha/requirement-21 genesis-wp-ha/ac-90 (round 5: diagram geometry)
{
  const card = new Card(); card.setConfig({device:'internal_heat_pump',entry:fixture.entry,layout:'diagram'}); card.hass=hass;
  const out = html(card);
  const path = id => out.match(new RegExp(`data-path="${id}"[^>]* d="([^"]+)"`))[1];
  const points = d => [...d.matchAll(/(-?\d+),(-?\d+)/g)].map(([,x,y])=>[Number(x),Number(y)]);
  // The ground loop sits at the bottom: brine leaves and re-enters it below the exchangers
  // (requirement-24 routes the up-leg through the passive-cooling exchanger at the top).
  assert.ok(points(path('brine-in'))[0][1] >= 480); assert.ok(points(path('brine-out')).at(-1)[1] >= 480);
  // Condenser supply out and return in are single straight horizontal runs.
  for (const id of ['condenser-out','condenser-in']) {
    const p = points(path(id));
    assert.equal(p.length, 2, id); assert.equal(p[0][1], p[1][1], id);
  }
  // Pumps point along their pipe in the flow direction.
  assert.deepEqual([...out.matchAll(/data-flow-direction="(\w+)"/g)].map(m=>m[1]), ['down','left','right'], 'brine pump down from the passive-cooling HX, condenser pump left, FR2 right');
  assert.doesNotMatch(out, /min-width:892px/);
  // Part labels are HTML at the theme's small size, not SVG text that shrinks with the stage.
  assert.doesNotMatch(out.match(/<svg class="drawing"[\s\S]*?<\/svg>/)[0], /<text/);
  for (const label of ['Evaporator','Condenser','Compressor','Heating circuit 1','Heating circuit 2','Buffer tank','TR9','TR12/13','FR2','Rooms (HC2)','either way'])
    assert.match(out, new RegExp(`<span class="part-label" style="left:[\\d.]+%;top:[\\d.]+%;transform:translate\\((0|-50|-100)%,-80%\\)">${label.replace(/[()]/g,'\\$&')}</span>`), label);
  assert.match(out, /\.part-label\{[^}]*font-size:var\(--ha-font-size-s\)/);
  assert.match(out, /min-width:1273px/, 'the full plant fits from 0.67 px per unit');
  // Pumps sit in front of their pipe on a card-colored disc.
  const drawing = out.match(/<svg class="drawing"[\s\S]*?<\/svg>/)[0];
  assert.ok(drawing.lastIndexOf('data-path=') < drawing.indexOf('class="pump"'), 'pumps after pipes');
  assert.match(drawing, /class="pump"[^>]*style="fill:var\(--card-background-color\)"/);
}
// DHF-TEST: genesis-wp-ha/requirement-24 genesis-wp-ha/ac-92 genesis-wp-ha/ac-93 genesis-wp-ha/ac-94 genesis-wp-ha/ac-95 genesis-wp-ha/ac-96
// DHF-TEST: genesis-wp-ha/ac-102 genesis-wp-ha/ac-103 genesis-wp-ha/ac-104 genesis-wp-ha/ac-105 genesis-wp-ha/ac-109
// DHF-TEST: genesis-wp-ha/requirement-26 genesis-wp-ha/ac-108
{
  const reg = r => typeof r === 'number' ? `input_${r}` : r;
  const idOf = r => Object.keys(hass.states).find(id => hass.states[id].attributes.register === reg(r));
  // Heating with passive cooling off (ac-95).
  const heat = {...hass, states:structuredClone(hass.states)};
  heat.states[idOf(1)].state = 'Heat';
  if (idOf('coil_33')) heat.states[idOf('coil_33')].state = 'off';
  const card = new Card(); card.setConfig({device:'internal_heat_pump',entry:fixture.entry,layout:'diagram'}); card.hass=heat;
  const out = html(card);
  const [vx, vy, vw, vh] = out.match(/<svg class="drawing" viewBox="([^"]+)"/)[1].split(' ').map(Number);
  // ac-92: plant order right of the condenser.
  const xs = Object.fromEntries([...out.matchAll(/data-part="(\w+)" data-x="(\d+)"/g)].map(([, n, x]) => [n, Number(x)]));
  const order = ['t33','buffer','tr9','mixer','fr2','rooms'];
  for (const n of order) assert.ok(n in xs, n);
  order.reduce((prev, n) => { assert.ok(xs[n] > prev, `${n} ${xs[n]} after ${prev}`); return xs[n]; }, 930);
  // Chip boxes in drawing units; a chip is at most 44 units tall at the stage min-width.
  const chips = [...out.matchAll(/<div class="chip [^"]*" role="button" tabindex="0" data-register="([^"]+)" data-entity="([^"]+)" style="left:([\d.]+)%;top:([\d.]+)%;width:([\d.]+)%"/g)]
    .map(([, register, id, l, t, w]) => { const x = vx + l/100*vw, y = vy + t/100*vh; return {register, id, box:[x, y, x + w/100*vw, y + 44]}; });
  const segments = [...out.matchAll(/data-path="([^"]+)"[^>]* d="([^"]+)"/g)].flatMap(([, name, d]) => {
    const pts = [...d.matchAll(/(-?\d+),(-?\d+)/g)].map(([, x, y]) => [Number(x), Number(y)]);
    return pts.slice(1).map((b, i) => ({name, box:[Math.min(pts[i][0], b[0]) - 2.5, Math.min(pts[i][1], b[1]) - 2.5, Math.max(pts[i][0], b[0]) + 2.5, Math.max(pts[i][1], b[1]) + 2.5]}));
  });
  // Half a unit of tolerance: positions round-trip through 2-decimal percentages.
  const hit = (a, b) => a[0] < b[2] - 0.5 && b[0] < a[2] - 0.5 && a[1] < b[3] - 0.5 && b[1] < a[3] - 0.5;
  // ac-93: one chip per value, beside its part, never on a pipe or another chip.
  const near = {input_12:'t33', input_18:'t33', input_67:'t33', input_41:'buffer', input_43:'mixer', input_40:'fr2', input_147:'fr2'};
  // The charge target (input 68) is no longer drawn; its entity stays listed by the panel.
  assert.equal(chips.filter(c => c.register === 'input_68').length, 0, 'no input_68 chip');
  for (const [register, partName] of Object.entries(near)) {
    const mine = chips.filter(c => c.register === register);
    assert.equal(mine.length, 1, register);
    const cx = (mine[0].box[0] + mine[0].box[2]) / 2;
    assert.ok(Math.abs(cx - xs[partName]) <= 250, `${register} at ${cx}, ${partName} at ${xs[partName]}`);
  }
  chips.forEach((a, i) => {
    for (const b of chips.slice(i + 1)) assert.ok(!hit(a.box, b.box), `${a.register} overlaps ${b.register}`);
    for (const s of segments) assert.ok(!hit(a.box, s.box), `${a.register} on pipe ${s.name}`);
    assert.ok(a.box[0] >= vx && a.box[2] <= vx + vw && a.box[1] >= vy && a.box[3] <= vy + vh, `${a.register} inside the view`);
  });
  // ac-94: settings chips sit in their circuit's region.
  const between = (register, lo, hi) => { const c = chips.find(c => c.register === register); assert.ok(c, register); assert.ok(c.box[0] >= lo && c.box[2] <= hi, `${register} ${c.box}`); };
  for (const r of ['holding_5','holding_4','holding_3','coil_9']) between(r, 930, xs.t33 + 30);
  // HC2 settings run from TR9 to the end of the circuit, the rooms, at the right edge (ac-105).
  for (const r of ['holding_107','holding_108','coil_11']) between(r, xs.tr9, vx + vw);
  // ac-95: passive cooling and TR9 port A idle while heating; HC2 from the buffer through port B active.
  const flow = name => out.match(new RegExp(`data-path="${name}" data-flow="(\\w+)"`))[1];
  assert.equal(flow('passive-port-a'), 'idle');
  assert.equal(flow('hc2-port-b'), 'active');
  assert.equal(flow('either-way'), 'active');
  // ac-96: the T32 chip opens more-info for its entity.
  const events = []; card.dispatchEvent = e => events.push(e);
  const t32 = idOf(40);
  card._activate({target:{closest:() => ({dataset:{entity:t32}})}, preventDefault(){}});
  assert.equal(events.length, 1); assert.equal(events[0].type, 'hass-more-info'); assert.deepEqual(events[0].detail, {entityId:t32});
  // ac-102: chips stacked in one column keep at least 2 units between them.
  chips.forEach((a, i) => { for (const b of chips.slice(i + 1)) {
    if (!(a.box[0] < b.box[2] - 0.5 && b.box[0] < a.box[2] - 0.5)) continue;
    const gap = Math.max(a.box[1], b.box[1]) - Math.min(a.box[3], b.box[3]);
    assert.ok(gap >= 1.9, `${a.register} and ${b.register}: ${gap.toFixed(2)} units apart`);
  } });
  // issue-21 finding 2: chips side by side keep at least 2 units between them too.
  chips.forEach((a, i) => { for (const b of chips.slice(i + 1)) {
    if (!(a.box[1] < b.box[3] - 0.5 && b.box[1] < a.box[3] - 0.5)) continue;
    const gap = Math.max(a.box[0], b.box[0]) - Math.min(a.box[2], b.box[2]);
    assert.ok(gap >= 1.9, `${a.register} and ${b.register}: ${gap.toFixed(2)} units apart side by side`);
  } });
  // issue-21: T31 reads the tank-bottom water, so its chip sits on the buffer tank (1160..1320, 330..580).
  {
    const t31 = chips.find(c => c.register === 'input_41');
    assert.ok(t31 && t31.box[0] >= 1160 && t31.box[2] <= 1320 && t31.box[1] >= 330 && t31.box[3] <= 580, `T31 chip on the tank: ${t31?.box}`);
  }
  // issue-21: a pipe without a sensor draws neutral even while active, never a guessed color; the
  // return into the condenser is colored by condenser in (input 8).
  {
    const tag = out.match(/<path data-path="bypass"[^>]*>/)?.[0];
    assert.ok(tag, 'bypass');
    assert.match(tag, /data-flow="active"/);
    assert.match(tag, /stroke="currentColor" stroke-opacity="0.75"/);
    assert.doesNotMatch(tag, /data-estimated/);
  }
  {
    const returnId = idOf('derived_hc2_return');
    const renderReturn = (estimate, buffer, disableT31 = false, disableT32 = false) => {
      const states = structuredClone(heat.states);
      states[returnId].state = estimate;
      states[returnId].attributes.unit_of_measurement = '°C';
      states[idOf(41)].state = buffer;
      const diagram = new Card();
      diagram.setConfig({device:'internal_heat_pump',entry:fixture.entry,layout:'diagram'});
      const entities = structuredClone(heat.entities);
      if (disableT31) entities[idOf(41)].disabled_by = 'user';
      if (disableT32) entities[idOf(40)].disabled_by = 'user';
      diagram.hass = {...heat, entities, states};
      return pipe(diagram, 'room-return');
    };
    // DHF-TEST: genesis-wp-ha/requirement-27 genesis-wp-ha/ac-117
    const active = renderReturn('20', '30');
    assert.match(active, /data-flow="active"[^>]*stroke="#e6c84f" stroke-opacity="1"/);
    assert.equal(renderReturn('20', '45'), active);
    assert.equal(renderReturn('20', '45', true), active);
    assert.match(renderReturn('30', '45'), /stroke="#f08a3c" stroke-opacity="1"/);
    // formal_review-60 B1: with T32 disabled and the HC2 set point (input 147) enabled the Rooms
    // block stays, and so does its return pipe, colored by the estimate.
    assert.ok(idOf(147), 'HC2 supply set point in the fixture');
    assert.equal(renderReturn('20', '30', false, true), active);
    // DHF-TEST: genesis-wp-ha/requirement-27 genesis-wp-ha/ac-118
    for (const disabled of [false, true]) {
      assert.match(renderReturn('unavailable', '45', disabled), /data-flow="active"[^>]*stroke="currentColor" stroke-opacity="0.75"/);
      assert.match(renderReturn('unavailable', '45', disabled, true), /data-flow="active"[^>]*stroke="currentColor" stroke-opacity="0.75"/);
    }
  }
  // change_request-50 (owner): the buffer tank's two cold ports are level on opposite walls, the
  // heat-pump return on the left wall (x 1160), the room return on the right wall (x 1320).
  {
    const pts = name => [...out.match(new RegExp(`data-path="${name}"[^>]* d="([^"]+)"`))[1].matchAll(/(-?\d+),(-?\d+)/g)].map(([, x, y]) => [Number(x), Number(y)]);
    const hp = pts('buffer-return')[0], room = pts('room-return-buffer').at(-1);
    assert.deepEqual(hp, [1160, 560], `heat-pump return port ${hp}`);
    assert.deepEqual(room, [1320, 560], `room return port ${room}`);
    // No pipe reaches the tank bottom (y 580) any more.
    for (const s of segments) assert.ok(!(s.box[1] <= 580 && s.box[3] >= 580 && s.box[0] < 1320 && s.box[2] > 1160), `${s.name} on the tank bottom`);
  }
  // issue-22: the T33 junction dot takes the style of the first active pipe it joins.
  {
    const style = (o, id) => { const t = o.match(new RegExp(`<path data-path="${id}" data-flow="(\\w+)"[^>]* stroke="([^"]+)" stroke-opacity="([\\d.]+)"`)); return t && {flow:t[1], color:t[2], opacity:t[3]}; };
    const dot = o => { const t = o.match(/<circle class="junction" data-junction="either-way" data-flow="(\w+)"[^>]* fill="([^"]+)" fill-opacity="([\d.]+)"/); return t && {flow:t[1], color:t[2], opacity:t[3]}; };
    assert.equal((out.match(/class="junction"/g) || []).length, 1, 'one junction dot');
    const first = ['either-way','hc2-port-b','condenser-out'].map(id => style(out, id)).find(s => s && s.flow === 'active');
    assert.ok(first, 'a joined pipe is active while heating');
    assert.deepEqual(dot(out), first);
    assert.equal(first.opacity, '1');
    // Passive cooling: compressor, buffer and HC2 port B all idle, so the dot is idle-styled.
    assert.ok(idOf('coil_33'), 'passive cooling switch in the fixture');
    const off = {...heat, states:structuredClone(heat.states)};
    off.states[idOf(1)].state = 'Passive cooling'; off.states[idOf('coil_33')].state = 'on';
    const o = new Card(); o.setConfig({device:'internal_heat_pump',entry:fixture.entry,layout:'diagram'}); o.hass = off;
    const oh = html(o);
    const joined = ['either-way','hc2-port-b','condenser-out'].map(id => style(oh, id)).filter(Boolean);
    assert.ok(joined.length && joined.every(s => s.flow === 'idle'), JSON.stringify(joined));
    assert.deepEqual(dot(oh), {flow:'idle', color:'currentColor', opacity:'0.22'});
    // DHF-TEST: genesis-wp-ha/requirement-27 genesis-wp-ha/ac-170
    const cover = (svg, x, y) => {
      for (const [tag] of svg.matchAll(/<rect\b[^>]*>/g)) {
        const attr = name => tag.match(new RegExp(`(?:^| )${name}="([^"]+)"`))?.[1];
        if (+attr('x') === x - 2.5 && +attr('y') === y - 2.5 &&
            +attr('width') === 5 && +attr('height') === 5) {
          return {color: attr('fill'), opacity: attr('fill-opacity')};
        }
      }
    };
    const checkCorners = svg => {
      const corners = new Map();
      for (const [tag, id, d] of svg.matchAll(/<path data-path="([^"]+)"[^>]* d="([^"]+)"/g)) {
        assert.doesNotMatch(tag, /stroke-linecap="(?:round|square)"/);
        const points = [...d.matchAll(/(-?\d+),(-?\d+)/g)].map(([, x, y]) => [+x, +y]);
        for (const [point, neighbor] of [[points[0], points[1]], [points.at(-1), points.at(-2)]]) {
          const ends = corners.get(String(point)) || [];
          ends.push({id, dx: neighbor[0] - point[0], dy: neighbor[1] - point[1]});
          corners.set(String(point), ends);
        }
      }
      for (const [point, ends] of corners) {
        if (ends.length !== 2) continue;
        const [a, b] = ends;
        if (a.id === b.id || a.dx * b.dx + a.dy * b.dy !== 0) continue;
        const [x, y] = point.split(',').map(Number);
        if (svg.match(new RegExp(`<circle class="junction"[^>]* cx="${x}" cy="${y}"`))) continue;
        assert.ok(cover(svg, x, y), `missing pipe corner at ${point} (${a.id}, ${b.id})`);
      }
    };
    checkCorners(out);
    for (const category of categories.filter(name => name !== 'internal_heat_pump')) {
      checkCorners(html(render(category)));
    }
    const condenserReturn = style(out, 'condenser-in');
    assert.equal(condenserReturn.flow, 'active');
    assert.deepEqual(cover(out, 1100, 390), {
      color: condenserReturn.color, opacity: condenserReturn.opacity,
    });
    assert.equal(style(oh, 'condenser-in').flow, 'idle');
    assert.deepEqual(cover(oh, 1100, 390), {color: 'currentColor', opacity: '0.22'});
    // No static text-colored dot remains in the drawing.
    assert.doesNotMatch(out, /<circle cx="1220" cy="290"[^>]*fill="currentColor"/);
  }
  {
    const t8 = heat.states[idOf(8)], c8 = Number(t8?.state);
    const tag = out.match(/<path data-path="buffer-return"[^>]*>/)[0];
    if (Number.isFinite(c8)) assert.match(tag, new RegExp(`stroke="${temperatureColor(c8)}"`));
  }
  // ac-103 (gate proxy; the browser check at 1600 px is the system rung): the two labels that
  // were cut off are now no longer than 11 characters in every language.
  for (const register of ['input_5','input_39']) {
    const label = out.match(new RegExp(`data-register="${register}"[^>]*><span class="label">([^<]*)<`))?.[1];
    assert.ok(label && label.length <= 11, `${register}: ${label}`);
    const de = html((() => { const c = new Card(); c.setConfig({device:'internal_heat_pump',entry:fixture.entry,layout:'diagram'}); c.hass = {...heat, language:'de'}; return c; })())
      .match(new RegExp(`data-register="${register}"[^>]*><span class="label">([^<]*)<`))?.[1];
    assert.ok(de && de.length <= 11, `${register} (de): ${de}`);
  }
  // ac-104: the room return to the passive-cooling exchanger, idle while heating.
  const ret = out.match(/data-path="cooling-return"[^>]* d="([^"]+)"/)?.[1];
  assert.ok(ret, 'cooling-return drawn');
  const rp = [...ret.matchAll(/(-?\d+),(-?\d+)/g)].map(([, x, y]) => [Number(x), Number(y)]);
  assert.ok(rp[0][0] >= 1320 && rp[0][0] <= 1360 && rp[0][1] === 560, `starts at the T31 port: ${rp[0]}`);
  assert.ok(rp.at(-1)[0] >= 130 && rp.at(-1)[0] <= 240 && rp.at(-1)[1] === 10, `enters the cooling HX from the top: ${rp.at(-1)}`);
  assert.ok(Math.min(...rp.map(([, y]) => y)) < 10, 'runs over the top of the plant');
  assert.equal(flow('cooling-return'), 'idle');
  assert.match(out.match(/<path data-path="cooling-return"[^>]*>/)[0], /stroke="currentColor" stroke-opacity="0.22"/);
  if (idOf('coil_33')) {
    const cool = {...hass, states:structuredClone(hass.states)};
    cool.states[idOf(1)].state = 'Passive cooling'; cool.states[idOf('coil_33')].state = 'on';
    const c = new Card(); c.setConfig({device:'internal_heat_pump',entry:fixture.entry,layout:'diagram'}); c.hass = cool;
    const tag = html(c).match(/<path data-path="cooling-return"[^>]*>/)[0];
    assert.match(tag, /data-flow="active"/);
    // No sensor on the room return (issue-21): active, but neutral rather than T31's color.
    assert.match(tag, /stroke="currentColor" stroke-opacity="0.75"/);
  }
  // ac-108: one estimated-flow chip beside each circulation pump; unknown shows the placeholder, not 0.
  for (const [register, [px, py]] of Object.entries({derived_condenser_flow:[1040, 390], derived_brine_flow:[225, 200]})) {
    const mine = chips.filter(c => c.register === register);
    assert.equal(mine.length, 1, register);
    const [x0, y0, x1, y1] = mine[0].box;
    const dx = Math.max(x0 - px, 0, px - x1), dy = Math.max(y0 - py, 0, py - y1);
    assert.ok(Math.hypot(dx, dy) <= 120, `${register} ${Math.hypot(dx, dy).toFixed(1)} units from its pump`);
    const value = out.match(new RegExp(`data-register="${register}"[^>]*>[^]*?<span class="value">([^<]*)<`))[1];
    if (['unknown','unavailable'].includes(heat.states[mine[0].id].state)) assert.doesNotMatch(value, /^0/, register);
  }
  // ac-109: the expansion valve opening sits directly under the valve symbol at (630, 510).
  {
    const c = chips.find(c => c.register === 'input_315');
    if (c) {
      assert.ok(Math.abs((c.box[0] + c.box[2]) / 2 - 630) <= 10, `input_315 center ${(c.box[0] + c.box[2]) / 2}`);
      assert.ok(c.box[1] > 518 && c.box[1] - 518 <= 30, `input_315 top ${c.box[1]}`);
    }
  }
  // ac-105: HC2 chips right of the TR12/13 mixer, inside the view, clear of the Rooms (HC2) box.
  const rooms = [1750, 270, 1880, 470];
  for (const r of ['holding_107','holding_108','coil_11','input_147','input_43','input_40']) {
    const c = chips.find(c => c.register === r); if (!c) continue;
    assert.ok(c.box[0] > xs.mixer, `${r} left edge ${c.box[0]} right of TR12/13 at ${xs.mixer}`);
    assert.ok(!hit(c.box, rooms), `${r} on the Rooms box`);
  }
  // issue-21 finding 4: chip values go through Home Assistant's formatter, which applies the
  // entity's display precision. Independent oracle: the formatter below rounds to the registry's
  // display_precision; the raw 15-decimal state must not reach the chip.
  {
    const id = idOf('derived_condenser_flow');
    assert.ok(id, 'derived_condenser_flow entity');
    const st = {...hass, states:structuredClone(heat.states), entities:{...hass.entities, [id]:{...hass.entities[id], display_precision:1}}};
    st.states[id].state = '9.829977359887123';
    st.formatEntityState = s => {
      const e = Object.entries(st.states).find(([, v]) => v === s)?.[0];
      const p = st.entities[e]?.display_precision;
      const n = Number(s.state);
      return `${p === undefined || !Number.isFinite(n) ? s.state : n.toFixed(p)} ${s.attributes.unit_of_measurement || ''}`.trim();
    };
    const c = new Card(); c.setConfig({device:'internal_heat_pump',entry:fixture.entry,layout:'diagram'}); c.hass = st;
    const value = html(c).match(new RegExp(`data-register="derived_condenser_flow"[^>]*>[^]*?<span class="value">([^<]*)<`))[1];
    assert.equal(value, '≈ 9.8 L/min');
    // Unknown keeps the localized placeholder; a formatter that throws falls back to the raw state.
    st.states[id].state = 'unknown'; c.hass = st;
    assert.equal(html(c).match(new RegExp(`data-register="derived_condenser_flow"[^>]*>[^]*?<span class="value">([^<]*)<`))[1], 'Unknown');
    st.states[id].state = '9.5'; st.formatEntityState = () => { throw new Error('x'); }; c.hass = st;
    assert.equal(html(c).match(new RegExp(`data-register="derived_condenser_flow"[^>]*>[^]*?<span class="value">([^<]*)<`))[1], '≈ 9.5 L/min');
  }
}
console.log("HARNESS-COMPLETE");
