import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
const hass=JSON.parse(readFileSync(0,'utf8'));
globalThis.window=globalThis;
globalThis.HTMLElement=class {attachShadow(){let html='';this.shadowRoot={replaced:0,addEventListener(){},querySelector(){return null;},querySelectorAll(){return [];},
 get innerHTML(){return html;},set innerHTML(v){html=v;this.replaced++;}};return this.shadowRoot;}};
globalThis.customElements={items:new Map([['hui-view',class {}]]),get(k){return this.items.get(k);},define(k,v){assert.ok(!this.items.has(k),k);this.items.set(k,v);}};
const source=process.argv[2];
await import(pathToFileURL(source));
const Panel=customElements.get('genesis-wp-panel');
assert.ok(Panel);
const p=new Panel(); p.hass=hass;
const html=()=>p.shadowRoot.innerHTML;
const order=['internal_heat_pump','heating_system','additional_heating_circuits','buffer_tank','hot_water','cooling','pool','ksm','electric_meter_and_energy','controller'];
const device=c=>Object.entries(hass.devices).find(([,d])=>d.identifiers.some(([dom,id])=>dom==='genesis_wp'&&id===`${hass.entry}_${c}`));
const keyRegs={internal_heat_pump:['input_54','input_9','input_10','input_11'],heating_system:['input_12','input_18'],additional_heating_circuits:['input_40','input_147'],buffer_tank:['input_41'],hot_water:['input_15','input_17'],cooling:['input_106'],pool:['input_119','input_120'],controller:['input_13','input_157','input_158']};
const entity=r=>Object.keys(hass.states).find(id=>hass.states[id].attributes.register===r);
// DHF-TEST: genesis-wp-ha/requirement-21 genesis-wp-ha/ac-82
assert.deepEqual([...html().matchAll(/data-section="([^"]+)"/g)].map(m=>m[1]),order.filter(device));
// Tiles carry only key readings the energy flow does not already show.
for(const [c,keys] of Object.entries({internal_heat_pump:[9],heating_system:[18],additional_heating_circuits:[147],hot_water:[15,17],cooling:[106],pool:[119,120]})) {
 const tile=html().split(`data-tile="${c}"`)[1]?.split('</ha-card>')[0]; assert.ok(tile,c);
 for(const k of keys){const id=entity('input_'+k); if(id) assert.ok(tile.includes(`data-entity="${id}"`),c+': '+k);}
}
// DHF-TEST: genesis-wp-ha/requirement-21 genesis-wp-ha/ac-91
for(const c of order.filter(device)) {
 const tile=html().split(`data-tile="${c}"`)[1].split('</ha-card>')[0];
 const [did]=device(c);
 const hasAlarms=Object.entries(hass.entities).some(([id,e])=>e.device_id===did&&!e.disabled_by&&id.startsWith('binary_sensor.')&&hass.states[id]?.attributes.device_class==='problem');
 if(hasAlarms||c==='internal_heat_pump') assert.match(tile,/<div class="state">/,c);
 assert.doesNotMatch(tile,/\d+ values/,c);
 // A tile repeats flow readings only as the fallback for an otherwise empty tile.
 if(tile.includes('<div class="state">')||!(keyRegs[c]||[]).every(r=>['input_10','input_11','input_54','input_157','input_158','input_41','input_12','input_40','input_13'].includes(r))) for(const r of ['input_10','input_11','input_54','input_157','input_158','input_41','input_12','input_40','input_13']) { const id=entity(r); if(id) assert.ok(!tile.includes(`data-entity="${id}"`),c+': '+r); }
}
assert.doesNotMatch(html(),/No key readings/);
const speed=entity('input_54'); hass.states[speed].state='unavailable'; p.hass=hass;
assert.match(html().split(`data-entity="${speed}"`)[1],/unavailable/);
// DHF-TEST: genesis-wp-ha/requirement-21 genesis-wp-ha/ac-83
const alarms=Object.keys(hass.states).filter(id=>id.startsWith('binary_sensor.')&&hass.states[id].attributes.device_class==='problem');
for(const id of alarms) hass.states[id].state='off'; p.hass=hass; assert.doesNotMatch(html(),/\d+ active/);
hass.states[alarms[0]].state='on'; p.hass=hass; assert.match(html(),/1 active/);
// DHF-TEST: genesis-wp-ha/requirement-21 genesis-wp-ha/ac-84
for(const c of order.filter(device)) {
 p.route={path:'/genesis-wp/'+c};
 const body=html();
 let previous=-1;
 for(const group of ['Measurements','Status','Alarms','Limits and settings']) {const i=body.indexOf('>'+group+'<');assert.ok(i>previous,group);previous=i;}
 assert.match(body,/<details><summary>Limits and settings/);
 const [did]=device(c);
 for(const [id,e] of Object.entries(hass.entities).filter(([,e])=>e.device_id===did&&!e.disabled_by)) {
  const s=hass.states[id]; if(!s) continue;
  const count=body.split(`data-entity="${id}"`).length-1;
  if(id.startsWith('binary_sensor.')&&s.attributes.device_class==='problem'&&s.state==='off') assert.equal(count,0);
  else if(!/curve at|heat curve x coordinate/i.test(s.attributes.friendly_name||'')) assert.equal(count,1+(keyRegs[c]||[]).includes(s.attributes.register),id);
 }
 if(['heating_system','additional_heating_circuits'].includes(c)) assert.match(body,/<genesis-wp-heating-curve-card/);
}
p.route={path:'/genesis-wp'}; assert.match(html(),/data-tile=/);
// DHF-TEST: genesis-wp-ha/requirement-22 genesis-wp-ha/ac-86
{
  const rows=[...html().matchAll(/<div class="reading(?: [^"]*)?"[^>]*>/g)].map(m=>m[0]);
  assert.ok(rows.length);
  for (const r of rows) { assert.match(r,/role="button"/); assert.match(r,/tabindex="0"/); }
  const events=[]; p.dispatchEvent=e=>events.push(e);
  const id=html().match(/data-entity="([^"]+)"/)[1];
  const stop=()=>{};
  p._activate({target:{closest:()=>({dataset:{entity:id}})},stopPropagation:stop});
  assert.equal(events.length,1); assert.equal(events[0].type,'hass-more-info');
  assert.deepEqual(events[0].detail,{entityId:id}); assert.ok(events[0].bubbles&&events[0].composed);
  p._activate({target:{closest:()=>({dataset:{section:'internal_heat_pump'}})},stopPropagation:stop});
  assert.equal(events.length,1);
  assert.match(html(),/>Measurements</);
}
// DHF-TEST: genesis-wp-ha/requirement-21 genesis-wp-ha/ac-84 (tab strip)
{
  p.route={path:'/genesis-wp'};
  const tabs=[...html().matchAll(/<button role="tab" data-tab="([^"]*)"/g)].map(m=>m[1]);
  assert.deepEqual(tabs,['',...order.filter(device)]);
  const stop=()=>{};
  p._activate({target:{closest:()=>({dataset:{tab:'heating_system'}})},stopPropagation:stop});
  assert.match(html(),/data-tab="heating_system" aria-selected="true"/);
  assert.match(html(),/>Measurements</);
  p._activate({target:{closest:()=>({dataset:{tab:''}})},stopPropagation:stop});
  assert.match(html(),/data-tab="" aria-selected="true"/);
  assert.match(html(),/data-tile=/);
}
// DHF-TEST: genesis-wp-ha/requirement-22 genesis-wp-ha/ac-87
{
  p.route={path:'/genesis-wp'};
  const before=p.shadowRoot.replaced;
  p.hass=hass; p.hass={...hass};
  assert.equal(p.shadowRoot.replaced,before,'unchanged markup must not replace the DOM');
  const {morph}=await import(pathToFileURL(source.replace('genesis-wp-panel.js','patch.js')));
  const el=(name,attrs={},kids=[])=>({nodeType:1,nodeName:name,childNodes:kids,attrs:{...attrs},
   get attributes(){return Object.entries(this.attrs).map(([name,value])=>({name,value}));},
   hasAttribute(n){return n in this.attrs;},getAttribute(n){return this.attrs[n]??null;},setAttribute(n,v){this.attrs[n]=v;},removeAttribute(n){delete this.attrs[n];}});
  const text=v=>({nodeType:3,nodeName:'#text',nodeValue:v,childNodes:[]});
  const live={childNodes:[el('DIV',{'data-entity':'sensor.a'},[text('1 C')]),el('DETAILS',{open:''},[])]};
  const target=live.childNodes[0];
  const parent=kids=>({childNodes:kids,appendChild(n){this.childNodes.push(n);},
   replaceChild(n,o){this.childNodes[this.childNodes.indexOf(o)]=n;},removeChild(o){this.childNodes.splice(this.childNodes.indexOf(o),1);}});
  Object.assign(live,parent(live.childNodes));
  assert.equal(morph(live,{childNodes:[el('DIV',{'data-entity':'sensor.a',class:'x'},[text('2 C')]),el('DETAILS',{},[])]}),0);
  assert.equal(live.childNodes[0],target); assert.equal(target.childNodes[0].nodeValue,'2 C'); assert.equal(target.attrs.class,'x');
  assert.ok('open' in live.childNodes[1].attrs,'user-opened details stay open');
  // A structural change elsewhere replaces only that node: the clicked value stays the same node.
  const details=live.childNodes[1];
  assert.equal(morph(live,{childNodes:[el('DIV',{'data-entity':'sensor.a',class:'x'},[text('2 C')]),el('SPAN'),el('P')]}),2);
  assert.equal(live.childNodes[0],target,'unchanged sibling kept'); assert.notEqual(live.childNodes[1],details);
  assert.equal(live.childNodes[1].nodeName,'SPAN'); assert.equal(live.childNodes[2].nodeName,'P');
  assert.equal(morph(live,{childNodes:[el('DIV',{'data-entity':'sensor.a',class:'x'},[text('2 C')])]}),2,'surplus nodes removed');
  assert.equal(live.childNodes.length,1); assert.equal(live.childNodes[0],target);
}
// DHF-TEST: genesis-wp-ha/requirement-21 genesis-wp-ha/ac-88
{
  p.route={path:'/genesis-wp'};
  assert.doesNotMatch(html(),/<select data-entry/);
  const other={...hass,devices:{...hass.devices,other_dev:{identifiers:[['genesis_wp','other_controller']],name:'Controller'}}};
  p.hass=other;
  assert.match(html(),/<select data-entry/);
  assert.match(html(),new RegExp(`<option value="${hass.entry}" selected>`));
  p._selectEntry('other_controller'.replace('_controller',''));
  assert.match(html(),/<option value="other" selected>/);
  assert.deepEqual([...html().matchAll(/data-tab="([^"]*)"/g)].map(m=>m[1]),['','controller']);
  p._selectEntry(hass.entry); p.hass=hass;
}
// DHF-TEST: genesis-wp-ha/requirement-21 genesis-wp-ha/ac-89
{
  p.route={path:'/genesis-wp'};
  for(const [r,label] of [['input_54','Compressor'],['input_9','Condenser out'],['input_10','From ground'],['input_12','Circuit 1 supply'],['input_13','Outdoor']]) {
    const id=entity(r); if(!id) continue;
    assert.match(html(),new RegExp(`data-entity="${id.replaceAll('.','\\.')}"[^>]*><span class="label"[^>]*>${label}</span>`),r);
  }
  p.hass={...hass,language:'de'};
  if(entity('input_54')) assert.match(html(),/>Verdichter</);
  p.hass=hass;
}
// DHF-TEST: genesis-wp-ha/requirement-21 genesis-wp-ha/ac-90
{
  const css=readFileSync(source,'utf8').split('const CSS=`')[1].split('`;')[0];
  assert.ok(css.length>500);
  assert.doesNotMatch(css,/font-size\s*:\s*[\d.]+(px|em|rem|pt)/,'font sizes come from theme tokens');
  assert.doesNotMatch(css,/#[0-9a-f]{3,6}\b|rgba?\(/i,'colors come from theme variables');
  p._activate({target:{closest:()=>({dataset:{tab:'internal_heat_pump'}})}});
  const body=html();
  assert.ok(body.indexOf('<genesis-wp-device-card data-diagram="internal_heat_pump"')<body.indexOf('>Measurements<'),'diagram heads the tab');
  p._activate({target:{closest:()=>({dataset:{tab:'heating_system'}})}});
  assert.ok(html().indexOf('<genesis-wp-heating-curve-card')<html().indexOf('>Measurements<'),'curve above the lists');
  assert.match(html(),/\.curves\{max-width:720px/);
}
// DHF-TEST: genesis-wp-ha/requirement-21 genesis-wp-ha/ac-91 (energy flow)
{
  p.route={path:'/genesis-wp'}; p._activate({target:{closest:()=>({dataset:{tab:''}})}});
  const flow=html().split('<ha-card data-flow>')[1].split('</ha-card>')[0];
  const nodes=[...flow.matchAll(/data-node="([^"]+)"/g)].map(m=>m[1]);
  assert.ok(nodes.length>=2,nodes.join());
  assert.equal((flow.match(/class="pipe"/g)||[]).length,nodes.length-1);
  if(nodes.includes('buffer_tank')) assert.match(flow,/<\/ha-icon>Buffer tank<\/h3>/);
  if(entity('input_12')&&entity('input_40')) { assert.match(flow,/>Circuit 1 supply</); assert.match(flow,/>Circuit 2 supply</); }
  for(const m of flow.matchAll(/--pipe:([^"]+)"/g)) assert.match(m[1],/^(#[0-9a-f]{6}|var\(--divider-color\))$/);
  // Heating sections head with the curve, titled as such.
  p._activate({target:{closest:()=>({dataset:{tab:'heating_system'}})}});
  const head=html().split('<div class="head')[1].split('<div class="groups">')[0];
  if(device('heating_system')&&Object.values(hass.states).some(s=>Array.isArray(s.attributes.curve))) assert.match(head,/<genesis-wp-heating-curve-card/);
  assert.doesNotMatch(head,/<genesis-wp-device-card/);
}
// DHF-TEST: genesis-wp-ha/requirement-21 genesis-wp-ha/ac-91 (tiles are never empty)
{
  p.route={path:'/genesis-wp'}; p._activate({target:{closest:()=>({dataset:{tab:''}})}});
  for(const c of order.filter(device)) {
    const tile=html().split(`data-tile="${c}"`)[1].split('</ha-card>')[0];
    assert.match(tile,/<div class="reading|<div class="state">/,c);
  }
  assert.doesNotMatch(html(),/\d+ alarms ok/);
  p._activate({target:{closest:()=>({dataset:{tab:'internal_heat_pump'}})}});
  for(const [r,label] of [['input_4','Gears available'],['input_60','Blocked'],['dinput_218','Brine pump on'],['dinput_225','OK to start']]) {
    const id=entity(r); if(!id) continue;
    assert.match(html(),new RegExp(`data-entity="${id.replaceAll('.','\\.')}"[^>]*><span class="label"[^>]*>${label}</span>`),r);
  }
  assert.match(html(),/<div class="hint">/);
  assert.match(html(),/<main class="wide">/,'a diagram tab uses the full panel width');
  // A tab click navigates, so a later route set from HA keeps the tab (round 6 regression).
  {const saved={location:globalThis.location,history:globalThis.history,dispatchEvent:globalThis.dispatchEvent};
   const pushed=[],fired=[];globalThis.location={href:'http://ha.local/genesis-wp?entry=x'};
   globalThis.history={pushState:(s,t,url)=>{pushed.push(String(url));globalThis.location={href:String(url)};}};
   globalThis.dispatchEvent=e=>fired.push(e.type);
   p._activate({target:{closest:()=>({dataset:{tab:'internal_heat_pump'}})}});
   assert.deepEqual(pushed,['http://ha.local/genesis-wp/internal_heat_pump?entry=x']);assert.deepEqual(fired,['location-changed']);
   p.route={prefix:'/genesis-wp',path:'/internal_heat_pump'};assert.match(html(),/data-diagram="internal_heat_pump"/);
   p._activate({target:{closest:()=>({dataset:{tab:'internal_heat_pump'}})}});assert.equal(pushed.length,1,'no push for the current tab');
   Object.assign(globalThis,saved);}
  assert.match(readFileSync(source,'utf8').split('const CSS=`')[1].split('`;')[0],/\.diagram\.overflow \.hint\{display:block\}/,'hint follows the diagram overflow, not the viewport');
  assert.doesNotMatch(readFileSync(source,'utf8').split('const CSS=`')[1].split('`;')[0],/max-width:870px\)\{\.diagram \.hint/);
  {const classes=new Set();const box={scrollWidth:976,clientWidth:710,classList:{toggle:(c,on)=>on?classes.add(c):classes.delete(c)}};
   p._overflow(box);assert.ok(classes.has('overflow'));box.clientWidth=1200;p._overflow(box);assert.ok(!classes.has('overflow'));}
}
// DHF-TEST: genesis-wp-ha/requirement-25 genesis-wp-ha/ac-97
{
  for(const c of order.filter(device)) {
    p._activate({target:{closest:()=>({dataset:{tab:c}})}});
    const drawings=(html().match(/<genesis-wp-device-card/g)||[]).length;
    assert.equal(drawings,c==='internal_heat_pump'?1:0,c);
    if(c!=='internal_heat_pump') assert.doesNotMatch(html(),/<main class="wide">/,c);
  }
}
// DHF-TEST: genesis-wp-ha/requirement-25 genesis-wp-ha/ac-98 genesis-wp-ha/ac-99 genesis-wp-ha/ac-100 genesis-wp-ha/ac-101
{
  const extras={heating_system:{min:'holding_4',max:'holding_3',stop:'holding_16',measured:'input_12'},
   additional_heating_circuits:{min:'holding_107',max:'holding_108',stop:'holding_16',measured:'input_40'}};
  for(const [c,want] of Object.entries(extras)) {
    if(!device(c)) continue;
    p._activate({target:{closest:()=>({dataset:{tab:c}})}});
    const card=html().match(/<genesis-wp-heating-curve-card[^>]*>/)?.[0];
    assert.ok(card,c);
    for(const [k,r] of Object.entries(want)) {
      const id=entity(r);
      if(id) assert.match(card,new RegExp(`data-${k}="${id.replaceAll('.','\\.')}"`),c+': '+k);
      else assert.doesNotMatch(card,new RegExp(`data-${k}=`),c+': '+k+' absent');
    }
    // The config handed to the curve card carries exactly the extras that exist (ac-100).
    const data=Object.fromEntries([...card.matchAll(/data-(\w+)="([^"]+)"/g)].map(m=>[m[1],m[2]]));
    const config=p._curveConfig(data);
    assert.equal(config.entity,data.curve);
    for(const k of Object.keys(want)) assert.equal(config[k],entity(want[k]),c+': config '+k);
    // ac-101: parameters after the curve, no curve-point rows.
    const body=html();
    assert.ok(body.indexOf('<genesis-wp-heating-curve-card')<body.indexOf('>Measurements<'),c);
    assert.doesNotMatch(body.split('<div class="groups">')[1],/curve at [^<]* outdoor/i,c);
  }
  // A missing extra entity: no attribute, so the card config has no key for it.
  const without={...hass,states:{...hass.states}};
  const max=entity('holding_3'); if(max){delete without.states[max]; p.hass=without;
   p._activate({target:{closest:()=>({dataset:{tab:'heating_system'}})}});
   assert.doesNotMatch(html().match(/<genesis-wp-heating-curve-card[^>]*>/)[0],/data-max=/);
   assert.equal(p._curveConfig({curve:'sensor.x'}).max,undefined);
   p.hass=hass;}
}
