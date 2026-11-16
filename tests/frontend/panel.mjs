import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
const hass=JSON.parse(readFileSync(0,'utf8'));
globalThis.HTMLElement=class {attachShadow(){this.shadowRoot={innerHTML:'',addEventListener(){},querySelectorAll(){return [];}};}};
globalThis.customElements={items:new Map(),get(k){return this.items.get(k);},define(k,v){this.items.set(k,v);}};
await import(pathToFileURL(process.argv[2]));
const Panel=customElements.get('genesis-wp-panel');
assert.ok(Panel);
const p=new Panel(); p.hass=hass;
const html=()=>p.shadowRoot.innerHTML;
const order=['internal_heat_pump','heating_system','additional_heating_circuits','buffer_tank','hot_water','cooling','pool','ksm','electric_meter_and_energy','controller'];
const device=c=>Object.entries(hass.devices).find(([,d])=>d.identifiers.some(([dom,id])=>dom==='genesis_wp'&&id===`${hass.entry}_${c}`));
const entity=r=>Object.keys(hass.states).find(id=>hass.states[id].attributes.register===r);
// DHF-TEST: genesis-wp-ha/requirement-21 genesis-wp-ha/ac-82
assert.deepEqual([...html().matchAll(/data-section="([^"]+)"/g)].map(m=>m[1]),order.filter(device));
for(const [c,keys] of Object.entries({internal_heat_pump:[54,9,10,11],heating_system:[12,18],additional_heating_circuits:[40,147],buffer_tank:[41,68],hot_water:[15,17],cooling:[106],pool:[119,120],controller:[13,157,158]})) {
 const tile=html().split(`data-tile="${c}"`)[1]?.split('</article>')[0]; assert.ok(tile,c);
 for(const k of keys){const id=entity('input_'+k); if(id) assert.ok(tile.includes(`data-entity="${id}"`),c+': '+k);}
}
assert.match(html(),/No key readings/);
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
  else if(!/curve at|heat curve x coordinate/i.test(s.attributes.friendly_name||'')) assert.equal(count,1,id);
 }
 if(['heating_system','additional_heating_circuits'].includes(c)) assert.match(body,/<genesis-wp-heating-curve-card/);
}
p.route={path:'/genesis-wp'}; assert.match(html(),/data-tile=/);
// DHF-TEST: genesis-wp-ha/requirement-22 genesis-wp-ha/ac-86
{
  const rows=[...html().matchAll(/<div class="reading"[^>]*>/g)].map(m=>m[0]);
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
