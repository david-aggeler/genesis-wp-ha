// DHF-REQ: genesis-wp-ha/requirement-21
// Presentation only: register attributes identify entities; no transport or decoding.
// Styling follows the Home Assistant design guidelines: type, spacing and color come from
// theme tokens (--ha-font-size-*, --ha-space-*, theme color variables), never fixed values.
import { patch } from './patch.js';
import { shortLabel } from './labels.js';
import { GenesisWpDeviceCard, temperatureColor, toCelsius } from './genesis-wp-device-card.js';
import { GenesisWpHeatingCurveCard } from './genesis-wp-heating-curve-card.js';

const SECTIONS=['internal_heat_pump','heating_system','additional_heating_circuits','buffer_tank','hot_water','cooling','pool','ksm','electric_meter_and_energy','controller'];
const ICONS={internal_heat_pump:'heat-pump',heating_system:'radiator',additional_heating_circuits:'radiator',buffer_tank:'storage-tank',hot_water:'water-boiler',cooling:'snowflake',pool:'pool',ksm:'shield-check',electric_meter_and_energy:'meter-electric',controller:'chip'};
// Key readings per section, as [register, tone]. Tone picks a theme state color.
const KEYS={internal_heat_pump:[['input_54'],['input_9','heat'],['input_10','cool'],['input_11','cool']],
 heating_system:[['input_12','heat'],['input_18']],additional_heating_circuits:[['input_40','heat'],['input_147']],
 buffer_tank:[['input_41','heat']],hot_water:[['input_15','heat'],['input_17']],cooling:[['input_106','cool']],
 pool:[['input_119','heat'],['input_120']],controller:[['input_13','cool'],['input_157'],['input_158']]};
// Sections whose device card draws a process diagram.
// Heating sections head with their heating curve instead; their drawings are sparse.
const DIAGRAMS=['internal_heat_pump','hot_water','cooling','pool'];
// Energy flow on the overview: ground -> heat pump -> buffer -> house. Each node is
// [name, icon, readings as [register, tone, label key]]; each pipe after a node is colored by
// the measured temperature of its register on the shared 0..45 C scale.
const FLOW=[['ground','earth',[['input_10','cool'],['input_11','cool']],'input_10'],
 ['heat_pump','heat-pump',[['input_54'],['input_157'],['input_158']],'input_9'],
 ['buffer_tank','storage-tank',[['input_41','heat']],'input_12'],
 ['house','home-thermometer',[['input_12','heat','supply_hc1'],['input_40','heat','supply_hc2'],['input_13','cool']]]];
// UI strings and short labels. English is the fallback for every language.
const TEXT={
 en:{title:'Heat pump',overview:'Overview',energy_flow:'Energy flow',ground:'Ground loop',heat_pump:'Heat pump',buffer_tank:'Buffer tank',house:'House',
  supply_hc1:'Circuit 1 supply',supply_hc2:'Circuit 2 supply',heating_curve:'Heating curve',
  measurements:'Measurements',status:'Status',alarms:'Alarms',settings:'Limits and settings',active:'{n} active',
  alarms_ok:'No active alarms',not_active:'Not active',signals_on:'{n} on',scroll:'Scroll sideways for the full diagram',no_alarms:'No alarms',values:'{n} values',entry:'Plant',
  section:{internal_heat_pump:'Heat pump',heating_system:'Heating',additional_heating_circuits:'Circuit 2',buffer_tank:'Buffer tank',
   hot_water:'Hot water',cooling:'Cooling',pool:'Pool',ksm:'Safety module',electric_meter_and_energy:'Energy',controller:'Controller'}},
 de:{title:'W\u00e4rmepumpe',overview:'\u00dcbersicht',energy_flow:'Energiefluss',ground:'Erdsonde',heat_pump:'W\u00e4rmepumpe',buffer_tank:'Pufferspeicher',house:'Haus',
  supply_hc1:'Vorlauf Heizkreis 1',supply_hc2:'Vorlauf Heizkreis 2',heating_curve:'Heizkurve',
  measurements:'Messwerte',status:'Status',alarms:'Alarme',settings:'Grenzen und Einstellungen',active:'{n} aktiv',
  alarms_ok:'Keine aktiven Alarme',not_active:'Nicht aktiv',signals_on:'{n} ein',scroll:'Seitlich scrollen f\u00fcr das ganze Schema',no_alarms:'Keine Alarme',values:'{n} Werte',entry:'Anlage',
  section:{internal_heat_pump:'W\u00e4rmepumpe',heating_system:'Heizung',additional_heating_circuits:'Heizkreis 2',buffer_tank:'Pufferspeicher',
   hot_water:'Warmwasser',cooling:'K\u00fchlung',pool:'Pool',ksm:'Sicherheitsmodul',electric_meter_and_energy:'Energie',controller:'Regler'}},
};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const alarm=e=>e.id.startsWith('binary_sensor.')&&(e.register.includes('alarm')||e.state.attributes.device_class==='problem');
const curvePoint=e=>/curve at .* outdoor|heat curve x coordinate/i.test(e.state.attributes.friendly_name||'');
const CSS=`
:host{display:block;min-height:100vh;background:var(--primary-background-color);color:var(--primary-text-color);font-size:var(--ha-font-size-m);font-family:var(--ha-font-family-body,inherit)}
*{box-sizing:border-box}
.toolbar{display:flex;align-items:center;gap:var(--ha-space-2);min-height:var(--header-height);padding:0 var(--ha-space-3);background:var(--app-header-background-color);color:var(--app-header-text-color,var(--text-primary-color));border-bottom:var(--app-header-border-bottom,none)}
.toolbar .name{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:var(--ha-font-size-xl);font-weight:var(--ha-font-weight-normal)}
.toolbar select{min-width:0;max-width:50%;text-overflow:ellipsis;font:inherit;font-size:var(--ha-font-size-m);color:inherit;background:transparent;border:1px solid currentColor;border-radius:var(--ha-border-radius-sm,4px);padding:var(--ha-space-1) var(--ha-space-2)}
.toolbar option{color:var(--primary-text-color);background:var(--card-background-color)}
.tabs{display:flex;flex-wrap:wrap;gap:0 var(--ha-space-1);padding:0 var(--ha-space-2);background:var(--app-header-background-color);color:var(--app-header-text-color,var(--text-primary-color))}
.tabs button{padding:var(--ha-space-3) var(--ha-space-3);border-bottom:2px solid transparent;font-size:var(--ha-font-size-m);opacity:.8}
.tabs [aria-selected=true]{opacity:1;border-bottom-color:currentColor;font-weight:var(--ha-font-weight-medium)}
main{max-width:1280px;margin:0 auto;padding:var(--ha-space-4)}
main.wide{max-width:none}
button{color:inherit;background:transparent;border:0;padding:0;cursor:pointer;font:inherit}
ha-card{display:block;padding:var(--ha-space-4);margin-bottom:var(--ha-space-4)}
h2{margin:0 0 var(--ha-space-3);font-size:var(--ha-font-size-l);font-weight:var(--ha-font-weight-medium)}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,260px),1fr));gap:var(--ha-space-4);align-items:start}
.tiles ha-card{margin:0}
.tile-head{display:flex;align-items:center;gap:var(--ha-space-2);width:100%;text-align:left;font-size:var(--ha-font-size-l);font-weight:var(--ha-font-weight-medium);margin-bottom:var(--ha-space-2)}
.tile-head ha-icon{color:var(--state-icon-color)}
.readings{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,150px),1fr));gap:var(--ha-space-1) var(--ha-space-3)}
.reading{display:flex;flex-direction:column;min-width:0;padding:var(--ha-space-1) var(--ha-space-2);margin:0 calc(-1 * var(--ha-space-2));border-radius:var(--ha-border-radius-sm,4px);cursor:pointer}
.reading:hover{background:var(--secondary-background-color)}
.label{font-size:var(--ha-font-size-s);color:var(--secondary-text-color);overflow:hidden;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow-wrap:anywhere}
.value{font-size:var(--ha-font-size-l);font-weight:var(--ha-font-weight-medium);overflow-wrap:anywhere}
.key .value{font-size:var(--ha-font-size-xl)}
.heat .value{color:var(--state-climate-heat-color)}
.cool .value{color:var(--state-climate-cool-color)}
.state{font-size:var(--ha-font-size-s);color:var(--secondary-text-color);margin-top:var(--ha-space-2)}
.badge{color:var(--error-color);font-weight:var(--ha-font-weight-medium)}
.flow{display:flex;align-items:stretch}
.node{flex:1;min-width:0;border:1px solid var(--divider-color);border-radius:var(--ha-card-border-radius,12px);padding:var(--ha-space-3)}
.node h3{display:flex;align-items:center;gap:var(--ha-space-2);margin:0 0 var(--ha-space-2);font-size:var(--ha-font-size-m);font-weight:var(--ha-font-weight-medium);color:var(--secondary-text-color)}
.node h3 ha-icon{color:var(--state-icon-color)}
.node .readings{grid-template-columns:1fr}
.pipe{flex:0 0 var(--ha-space-8,32px);align-self:center;height:var(--ha-space-2);border-radius:var(--ha-space-1);background:var(--pipe)}
.head{display:grid;grid-template-columns:minmax(0,2fr) minmax(220px,1fr);gap:var(--ha-space-4);align-items:start}
.head ha-card{margin:0}
.head.single,.head.stacked{grid-template-columns:minmax(0,1fr)}
.head.curve{grid-template-columns:minmax(0,720px) minmax(220px,1fr)}
.head .readings{grid-template-columns:repeat(auto-fill,minmax(min(100%,130px),1fr))}
.diagram{overflow-x:auto}
.diagram .hint{display:none;font-size:var(--ha-font-size-s);color:var(--secondary-text-color);margin-bottom:var(--ha-space-2)}
.diagram genesis-wp-device-card{display:block}
.diagram.overflow .hint{display:block}
.head .curves{margin:0}
.groups{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:0 var(--ha-space-4);margin-top:var(--ha-space-4)}
.curves{max-width:720px;margin-top:var(--ha-space-4)}
details summary{cursor:pointer;font-size:var(--ha-font-size-l);font-weight:var(--ha-font-weight-medium)}
details[open] summary{margin-bottom:var(--ha-space-3)}
[role=button]:focus-visible,button:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}
@media (max-width:870px){.head,.head.curve{grid-template-columns:minmax(0,1fr)}.flow{flex-direction:column}.pipe{flex-basis:var(--ha-space-6,24px);width:var(--ha-space-2);height:auto}}
`;
export class GenesisWpPanel extends HTMLElement {
 constructor(){
  super();this.attachShadow({mode:'open'});
  this.shadowRoot.addEventListener('click',e=>this._activate(e));
  this.shadowRoot.addEventListener('change',e=>{const t=e.target;if(t?.dataset&&'entry' in t.dataset)this._selectEntry(t.value);});
  this.shadowRoot.addEventListener('keydown',e=>{if(['Enter',' '].includes(e.key)&&e.target.closest?.('[data-entity],[data-section],[data-tab]')){e.preventDefault();this._activate(e);}});
  try{this._entry=new URLSearchParams(globalThis.location?.search||'').get('entry')||undefined;}catch{this._entry=undefined;}
 }
 set hass(v){this._hass=v;this._loadTitles();this._render();}
 set route(v){this._section=v?.path?.split('/').filter(Boolean).filter(p=>p!=='genesis-wp')[0];this._render();}
 set panel(v){this._panel=v;}
 set narrow(v){this._narrow=Boolean(v);this.toggleAttribute?.('narrow',this._narrow);this._render();}
 _t(key,n){const lang=this._hass?.locale?.language||this._hass?.language||'en';const pick=t=>key.split('.').reduce((o,k)=>o?.[k],t);
  const s=pick(TEXT[lang]||TEXT[lang?.split('-')[0]]||{})??pick(TEXT.en);return n===undefined?s:String(s).replace('{n}',n);}
 _activate(event){const target=event.target?.closest?.('[data-entity],[data-section],[data-tab]');if(!target)return;
  if(target.dataset.entity){event.preventDefault?.();this.dispatchEvent(new CustomEvent('hass-more-info',{detail:{entityId:target.dataset.entity},bubbles:true,composed:true}));}
  else {this._section=target.dataset.section??target.dataset.tab??undefined;if(this._section==='')this._section=undefined;this._navigate();this._render();}
 }
 // The URL is the source of truth for the selected tab: HA sets route again after load and on
 // location updates, and route would otherwise reset a tab chosen only in memory.
 _navigate(){try{const url=new URL(globalThis.location.href);
  url.pathname='/'+(this._panel?.url_path||'genesis-wp')+(this._section?'/'+this._section:'');
  if(url.href===globalThis.location.href)return;
  globalThis.history.pushState(null,'',url);
  globalThis.dispatchEvent(new CustomEvent('location-changed',{detail:{replace:false}}));}catch{}}
 _selectEntry(entry){this._entry=entry||undefined;
  try{const url=new URL(globalThis.location.href);url.searchParams.set('entry',entry);globalThis.history.replaceState(globalThis.history.state,'',url);}catch{}
  this._render();}
 // Config entry titles for the selector; the device registry alone does not carry them.
 _loadTitles(){if(this._titles||this._titlesPending||!this._hass?.callWS)return;this._titlesPending=true;
  this._hass.callWS({type:'config_entries/get',domain:'genesis_wp'}).then(list=>{this._titles=Object.fromEntries((list||[]).map(e=>[e.entry_id,e.title]));this._render();}).catch(()=>{this._titles={};});}
 _entries(devices){const out=[];for(const [,d] of devices)for(const [dom,id] of d.identifiers||[]){if(dom!=='genesis_wp')continue;const c=SECTIONS.find(c=>id.endsWith('_'+c));if(c){const e=id.slice(0,-c.length-1);if(!out.includes(e))out.push(e);}}return out;}
 _data(){const devices=Object.entries(this._hass.devices||{});const entries=this._entries(devices);
  const entry=entries.includes(this._entry)?this._entry:entries[0];
  const sections=SECTIONS.flatMap(category=>{const found=devices.find(([,d])=>(d.identifiers||[]).some(([dom,id])=>dom==='genesis_wp'&&id===`${entry}_${category}`));return found?[{category,id:found[0],device:found[1],icon:ICONS[category]}]:[];});
  const entities=Object.entries(this._hass.entities||{}).flatMap(([id,e])=>{const state=this._hass.states[id];return !e.disabled_by&&state?.attributes.register&&sections.some(s=>s.id===e.device_id)?[{id,state,register:state.attributes.register,deviceId:e.device_id}]:[];});
  return {entries,entry,sections,entities};
 }
 _name(e){const d=this._hass.devices[e.deviceId];return shortLabel(this._hass,e.register,e.state.attributes.friendly_name||e.id,d?.name_by_user||d?.name);}
 _value(e){const s=e.state;if(['unavailable','unknown'].includes(s.state))return this._hass.localize?.(`state.default.${s.state}`)||s.state;
  return this._hass.formatEntityState?.(s)??[s.state,s.attributes.unit_of_measurement].filter(Boolean).join(' ');}
 _row(e,tone='',key=false,label){return `<div class="reading${key?' key':''}${tone?' '+tone:''}" data-entity="${esc(e.id)}" role="button" tabindex="0"><span class="label" title="${esc(e.state.attributes.friendly_name||e.id)}">${esc(label?this._t(label):this._name(e))}</span><span class="value">${esc(this._value(e))}</span></div>`;}
 _keys(list,entities,key=false){return list.flatMap(([r,tone,label])=>{const e=entities.find(e=>e.register===r);return e?[this._row(e,tone,key,label)]:[];}).join('');}
 _sectionName(s){return s.device.name_by_user||this._t('section.'+s.category)||s.device.name||s.category;}
 // One-line section state: active alarms first, then the alarm count, then the value count.
 // Optional mode entity first, e.g. "Heat - 18 alarms ok". No line when there is nothing to say.
 _state(own,mode){const alarms=own.filter(alarm),on=alarms.filter(e=>e.state.state==='on').length;
  const parts=[];if(mode)parts.push(esc(this._value(mode)));
  if(on)parts.push(`<span class="badge">${esc(this._t('active',on))}</span>`);else if(alarms.length)parts.push(esc(this._t('alarms_ok',alarms.length)));
  return parts.length?`<div class="state">${parts.join(' \u00b7 ')}</div>`:'';}
 _overview(sections,entities){
  const pipe=r=>{const e=entities.find(e=>e.register===r);const c=e?toCelsius(e.state.state,e.state.attributes.unit_of_measurement):null;
   return `<div class="pipe" aria-hidden="true" style="--pipe:${c===null?'var(--divider-color)':temperatureColor(c)}"></div>`;};
  const shown=FLOW.map(([name,icon,keys,next])=>[name,icon,this._keys(keys,entities,true),next]).filter(([,,html])=>html);
  const nodes=shown.map(([name,icon,html,next],i)=>`<div class="node" data-node="${name}"><h3><ha-icon icon="mdi:${icon}"></ha-icon>${esc(this._t(name))}</h3><div class="readings">${html}</div></div>${i<shown.length-1?pipe(next):''}`).join('');
  const mode=entities.find(e=>e.register==='input_1');
  const flow=nodes?`<ha-card data-flow><h2>${esc(this._t('energy_flow'))}</h2>${mode?`<div class="readings">${this._row(mode)}</div>`:''}<div class="flow">${nodes}</div></ha-card>`:'';
  const inFlow=new Set(FLOW.flatMap(([,,k])=>k.map(([r])=>r)));
  const tiles=sections.map(s=>{const own=entities.filter(e=>e.deviceId===s.id);let keys=this._keys((KEYS[s.category]||[]).filter(([r])=>!inFlow.has(r)),entities);
   let state=this._state(own,s.category==='internal_heat_pump'?mode:null);
   // Never an empty tile: fall back to the section's own key readings, then to its binary signals.
   if(!keys&&!state)keys=this._keys(KEYS[s.category]||[],entities);
   if(!keys&&!state){const bits=own.filter(e=>e.id.startsWith('binary_sensor.')),on=bits.filter(e=>e.state.state==='on').length;state=`<div class="state">${esc(on?this._t('signals_on',on):this._t('not_active'))}</div>`;}
   return `<ha-card data-tile="${s.category}"><button class="tile-head" data-section="${s.category}"><ha-icon icon="mdi:${s.icon}"></ha-icon><span>${esc(this._sectionName(s))}</span></button>${keys?`<div class="readings">${keys}</div>`:''}${state}</ha-card>`;}).join('');
  return `${flow}<div class="tiles">${tiles}</div>`;
 }
 _detail(selected,entities,entry){
  const own=entities.filter(e=>e.deviceId===selected.id);
  const curves=['heating_system','additional_heating_circuits'].includes(selected.category)?own.filter(e=>Array.isArray(e.state.attributes.curve)):[];
  const rows=own.filter(e=>!curves.length||!curvePoint(e));const alarms=rows.filter(alarm);
  const measured=e=>e.register.startsWith('input_')&&e.state.attributes.unit_of_measurement;
  const groups=[['measurements',rows.filter(e=>!alarm(e)&&measured(e))],
   ['status',rows.filter(e=>!alarm(e)&&(e.register.startsWith('dinput_')||(e.register.startsWith('input_')&&!measured(e))))],
   ['alarms',alarms.filter(e=>e.state.state!=='off')],
   ['settings',rows.filter(e=>!alarm(e)&&/^(holding|coil)_/.test(e.register))]];
  const keys=this._keys(KEYS[selected.category]||[],entities,true);
  const diagram=DIAGRAMS.includes(selected.category)?`<ha-card class="diagram"><div class="hint">${esc(this._t('scroll'))} \u2192</div><genesis-wp-device-card data-diagram="${selected.category}" data-entry="${esc(entry)}"></genesis-wp-device-card></ha-card>`:'';
  const head=`<ha-card class="keys"><h2>${esc(this._sectionName(selected))}</h2>${keys?`<div class="readings">${keys}</div>`:''}${this._state(own)}</ha-card>`;
  const curveHtml=curves.length?`<div class="curves">${curves.map(e=>`<genesis-wp-heating-curve-card data-curve="${esc(e.id)}"></genesis-wp-heating-curve-card>`).join('')}</div>`:'';
  const graphic=diagram||curveHtml;
  const groupHtml=groups.map(([name,items],i)=>{
   const content=`<div class="readings">${items.map(e=>this._row(e)).join('')}</div>`+(name==='alarms'&&!items.length?`<div class="state">${esc(this._t('alarms_ok',alarms.filter(e=>e.state.state==='off').length))}</div>`:'');
   const title=esc(this._t(name));
   return name==='settings'?`<ha-card><details><summary>${title}</summary>${content}</details></ha-card>`:`<ha-card><h2>${title}</h2>${content}</ha-card>`;}).join('');
  const layout=diagram?' stacked':curveHtml?' curve':' single';
  return `<div class="head${layout}">${diagram?head+diagram:graphic+head}</div><div class="groups">${groupHtml}</div>`;
 }
 _render(){if(!this._hass)return;
  for(const [tag,cls] of [['genesis-wp-device-card',GenesisWpDeviceCard],['genesis-wp-heating-curve-card',GenesisWpHeatingCurveCard]])
   if(!customElements.get(tag))customElements.define(tag,cls);
  const {entries,entry,sections,entities}=this._data();const selected=sections.find(s=>s.category===this._section);
  const badge=s=>entities.filter(e=>e.deviceId===s.id&&alarm(e)&&e.state.state==='on').length;
  const select=entries.length>1?`<select data-entry aria-label="${esc(this._t('entry'))}">${entries.map(e=>`<option value="${esc(e)}"${e===entry?' selected':''}>${esc(this._titles?.[e]||e)}</option>`).join('')}</select>`:'';
  const toolbar=`<div class="toolbar"><ha-menu-button></ha-menu-button><div class="name">${esc(this._t('title'))}</div>${select}</div>`;
  const tabs=`<nav class="tabs" role="tablist"><button role="tab" data-tab="" aria-selected="${!selected}">${esc(this._t('overview'))}</button>${sections.map(s=>{const n=badge(s);return `<button role="tab" data-tab="${s.category}" aria-selected="${selected?.category===s.category}">${esc(this._sectionName(s))}${n?` <span class="badge">${n}</span>`:''}</button>`;}).join('')}</nav>`;
  const body=selected?this._detail(selected,entities,entry):this._overview(sections,entities);
  patch(this.shadowRoot,`<style>${CSS}</style>${toolbar}${tabs}<main${selected&&DIAGRAMS.includes(selected.category)?' class="wide"':''}>${body}</main>`);
  const menu=this.shadowRoot.querySelector?.('ha-menu-button');if(menu){menu.hass=this._hass;menu.narrow=this._narrow;}
  for(const card of this.shadowRoot.querySelectorAll('[data-curve]')){const key=card.dataset.curve;
   if(card.__config!==key){card.__config=key;card.setConfig?.({entity:key,title:this._t('heating_curve')});}card.hass=this._hass;}
  for(const card of this.shadowRoot.querySelectorAll('[data-diagram]')){const key=card.dataset.diagram+'|'+card.dataset.entry;
   if(card.__config!==key){card.__config=key;card.setConfig?.({device:card.dataset.diagram,entry:card.dataset.entry,layout:'diagram'});}card.hass=this._hass;
   const box=card.parentNode;if(box?.classList){this._overflow(box);
    if(!box.__observed&&typeof ResizeObserver!=='undefined'){box.__observed=new ResizeObserver(()=>this._overflow(box));box.__observed.observe(box);}}}
 }
 // The scroll hint shows whenever the diagram is wider than its card, whatever the viewport.
 // patch() resets the class to the template's; _render calls this again right after it.
 _overflow(box){const on=box.scrollWidth>box.clientWidth+1;if(box.classList.contains?.('overflow')!==on)box.classList.toggle('overflow',on);}
}
if(!customElements.get('genesis-wp-panel'))customElements.define('genesis-wp-panel',GenesisWpPanel);
