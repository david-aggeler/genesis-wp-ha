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
process.exit(0);
