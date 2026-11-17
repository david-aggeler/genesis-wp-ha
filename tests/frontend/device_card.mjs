import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const fixture = JSON.parse(readFileSync(0, 'utf8'));
class Registry { constructor() { this.items = new Map(); } get(k) { return this.items.get(k); } define(k, v) { assert.ok(!this.get(k)); this.items.set(k,v); } }
globalThis.window = globalThis;
globalThis.HTMLElement = class { attachShadow() { this.shadowRoot = {innerHTML:''}; } };
globalThis.customElements = new Registry();
await import(pathToFileURL(process.argv[2]));
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-65
assert.equal(customElements.get('genesis-wp-device-card'), undefined);
globalThis.customElements = new Registry();
customElements.define('hui-view', class {});
await new Promise(r=>setTimeout(r,600));
const Card = customElements.get('genesis-wp-device-card');
assert.ok(Card);
const categories = ['internal_heat_pump','buffer_tank','heating_system','additional_heating_circuits','hot_water','cooling','pool','ksm','electric_meter_and_energy','controller'];
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-66
for (const config of [{}, {device:'invalid'}]) {
  assert.throws(()=>new Card().setConfig(config), e=>categories.every(c=>e.message.includes(c)));
}
let services = 0, ws = 0;
const hass = {...fixture, callService(){services++;}, callWS(){ws++;}, localize(key){return key.endsWith('.unavailable')?'Unavailable':key.endsWith('.unknown')?'Unknown':undefined;}};
const render = (device, entry=fixture.entry) => { const card = new Card(); card.setConfig({device,entry}); card.hass=hass; return card; };
const html = card => card.shadowRoot.innerHTML;
const byRegister = key => Object.entries(hass.states).find(([,s])=>s.attributes.register===key)?.[0];
const tag = (card, key) => html(card).match(new RegExp(`<g[^>]*data-register="${key}"[^>]*>[\\s\\S]*?<\\/g>`))?.[0];
const pipe = (card, id) => html(card).match(new RegExp(`<path[^>]*data-path="${id}"[^>]*>`))?.[0];
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-67
for (const category of categories.slice(0,4)) {
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
// Independent register anchors from the requirement's per-card table.
for (const [category, keys] of Object.entries({internal_heat_pump:[10,11,130,127,124,125,5,61,48,7,128,122,129,126,9,8,39,44],buffer_tank:[41,68],heating_system:[12,18],additional_heating_circuits:[43,40,147]})) {
  const card=render(category);
  for (const address of keys) { const key=`input_${address}`; if(byRegister(key)) {
    const state=hass.states[byRegister(key)];
    const rendered=tag(card,key);
    assert.ok(rendered,key);
    const expected=['unknown','unavailable'].includes(state.state)
      ? hass.localize('state.default.'+state.state)
      : [state.state,state.attributes.unit_of_measurement].filter(Boolean).join(' ');
    assert.equal(rendered.match(/class="value"[^>]*>(.*?)<\/text>/)?.[1],expected,category+': '+key);
    // A second, distinct live value catches cross-entity binding and stale values.
    const previous=state.state;
    state.state='37.125'; card.hass=hass;
    assert.equal(tag(card,key).match(/class="value"[^>]*>(.*?)<\/text>/)?.[1],
      ['37.125',state.attributes.unit_of_measurement].filter(Boolean).join(' '));
    state.state=previous; card.hass=hass;
  } }
}
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-73
let card=render('buffer_tank');
assert.match(tag(card,'input_12'), /class="[^"]*context/);
assert.match(tag(card,'input_41'), /class="[^"]*own/);
assert.match(tag(card,'input_68'), /calculated/);
hass.states[byRegister('input_12')].state='26.26'; card.hass=hass;
assert.match(tag(card,'input_12'), />26.26 °C<\/text>/);
assert.match(html(card), /\.context rect\{[^}]*stroke-dasharray:2 3/);
assert.doesNotMatch(tag(card,'input_41'), /context|calculated/);
hass.states[byRegister('input_12')].state='40.0'; card.hass=hass;
assert.match(tag(card,'input_12'), />40.0 °C<\/text>/);
const supply=byRegister('input_12'), mode=byRegister('input_1');
hass.states[mode].state='Heat';
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-69
hass.states[supply].state='26.26'; card.hass=hass;
assert.match(pipe(card,'supply'), /stroke="#eca143"/);
hass.states[supply].state='40.0'; card.hass=hass;
assert.match(pipe(card,'supply'), /stroke="#df4e29"/);
// HA display-unit conversion: equivalent °F and K readings color the same as °C; the tag keeps the display unit.
const supplyUnit=hass.states[supply].attributes.unit_of_measurement;
for (const [value, unit] of [['104.0','°F'],['313.15','K']]) {
  hass.states[supply].state=value; hass.states[supply].attributes.unit_of_measurement=unit; card.hass=hass;
  assert.match(pipe(card,'supply'), /stroke="#df4e29"/);
  assert.match(tag(card,'input_12'), new RegExp(`>${value} ${unit}</text>`));
}
hass.states[supply].attributes.unit_of_measurement='kW'; card.hass=hass;
assert.match(pipe(card,'supply'), /stroke="currentColor"/);
hass.states[supply].attributes.unit_of_measurement=supplyUnit;
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-68
for (const value of ['unavailable','unknown']) {
  hass.states[supply].state=value; card.hass=hass;
  assert.match(tag(card,'input_12'), new RegExp(value, 'i'));
  assert.doesNotMatch(pipe(card,'supply'), /stroke="#[a-f0-9]+"/);
  assert.doesNotMatch(tag(card,'input_12').match(/class="value"[^>]*>(.*?)<\/text>/)[1], /[0-9]/);
}
hass.states[supply].state='26.26';
// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-70
hass.states[byRegister('input_41')].state='40.0';
hass.states[byRegister('input_40')].state='26.26';
card=render('additional_heating_circuits');
assert.match(pipe(card,'buffer-to-mixer'), /data-flow="active"/);
assert.match(pipe(card,'passive-cooling'), /data-flow="idle"/);
assert.match(pipe(card,'passive-cooling'), /stroke="currentColor" stroke-opacity="0.22"/);
assert.match(pipe(card,'buffer-to-mixer'), /stroke="#df4e29" stroke-opacity="1"/);
hass.states[mode].state='Passive cooling';
const coil=byRegister('coil_33'); hass.states[coil].state='on'; card.hass=hass;
assert.match(pipe(card,'buffer-to-mixer'), /data-flow="idle"/);
assert.match(pipe(card,'passive-cooling'), /data-flow="active"/);
assert.match(pipe(card,'buffer-to-mixer'), /stroke="currentColor" stroke-opacity="0.22"/);
assert.match(pipe(card,'passive-cooling'), /stroke="#eca143" stroke-opacity="1"/);
for(const state of ['Heat','Defrost','Hot water','Anti legionella','Pool','Cool','Standby','No demand','OFF','Manual Operation']) {
  hass.states[mode].state=state; card.hass=hass;
  assert.match(pipe(card,'buffer-to-mixer'), /data-flow="active"/);
  assert.match(pipe(card,'passive-cooling'), /data-flow="idle"/);
  assert.match(pipe(card,'passive-cooling'), /stroke="currentColor" stroke-opacity="0.22"/);
  assert.match(pipe(card,'buffer-to-mixer'), /stroke="#df4e29" stroke-opacity="1"/);
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
assert.match(html(render('buffer_tank','absent')), /not found/i);
hass.states[supply].attributes.friendly_name='<img src=x onerror=alert(1)>';
assert.doesNotMatch(html(render('buffer_tank')), /<img/);

// DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-72
// DHF-TEST: genesis-wp-ha/ac-66 genesis-wp-ha/ac-68 genesis-wp-ha/ac-71
// DHF-TEST: genesis-wp-ha/ac-74 genesis-wp-ha/ac-75
for (const category of categories.slice(4)) {
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
// DHF-TEST: genesis-wp-ha/requirement-20 genesis-wp-ha/ac-77
const form = Card.getConfigForm();
assert.deepEqual(form.schema.map(s=>s.name), ['device','title','entry']);
const [deviceField,titleField,entryField] = form.schema;
assert.equal(deviceField.required,true);
assert.equal(deviceField.selector.select.mode,'dropdown');
assert.deepEqual(deviceField.selector.select.options.map(o=>o.value),categories);
assert.deepEqual(deviceField.selector.select.options.map(o=>o.label),[
  'Internal heat pump','Buffer tank','Heating system','Additional heating circuits',
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
}}),{device:'buffer_tank'});
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
  const near = {input_12:'t33', input_18:'t33', input_67:'t33', input_41:'buffer', input_68:'buffer', input_43:'mixer', input_40:'fr2', input_147:'fr2'};
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
  for (const r of ['holding_107','holding_108','coil_11']) between(r, xs.tr9, xs.rooms - 60);
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
}
process.exit(0);
