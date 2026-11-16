// DHF-REQ: genesis-wp-ha/requirement-21
// Presentation only: register attributes identify entities; no transport or decoding.
const SECTIONS=['internal_heat_pump','heating_system','additional_heating_circuits','buffer_tank','hot_water','cooling','pool','ksm','electric_meter_and_energy','controller'];
const KEYS={internal_heat_pump:[54,9,10,11],heating_system:[12,18],additional_heating_circuits:[40,147],buffer_tank:[41,68],hot_water:[15,17],cooling:[106],pool:[119,120],controller:[13,157,158]};
const ICONS=['heat-pump','radiator','radiator','storage-tank','water-boiler','snowflake','pool','shield-check','meter-electric','chip'];
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const alarm=e=>e.id.startsWith('binary_sensor.')&&(e.register.includes('alarm')||e.state.attributes.device_class==='problem');
const curvePoint=e=>/curve at .* outdoor|heat curve x coordinate/i.test(e.state.attributes.friendly_name||'');
class GenesisWpPanel extends HTMLElement {
 constructor(){super();this.attachShadow({mode:'open'});this.shadowRoot.addEventListener('click',e=>this._activate(e));this.shadowRoot.addEventListener('keydown',e=>{if(['Enter',' '].includes(e.key)&&e.target.closest('[data-entity],[data-section],[data-tab],[data-back]')){e.preventDefault();this._activate(e);}});}
 set hass(v){this._hass=v;this._render();}
 set route(v){this._section=v?.path?.split('/').filter(Boolean).filter(p=>p!=='genesis-wp')[0];this._render();}
 set panel(v){this._panel=v;}
 set narrow(v){this.toggleAttribute?.('narrow',Boolean(v));}
 _activate(event){const target=event.target.closest('[data-entity],[data-section],[data-tab],[data-back]');if(!target)return;
  if(target.dataset.entity){event.stopPropagation();this.dispatchEvent(new CustomEvent('hass-more-info',{detail:{entityId:target.dataset.entity},bubbles:true,composed:true}));}
  else {this._section=target.dataset.section??target.dataset.tab??undefined;if(this._section==='')this._section=undefined;this._render();}
 }
 _data(){const devices=Object.entries(this._hass.devices||{});let entry;
  for(const [,d] of devices){for(const [dom,id] of d.identifiers||[]){if(dom!=='genesis_wp')continue;const c=SECTIONS.find(c=>id.endsWith('_'+c));if(c){entry=id.slice(0,-c.length-1);break;}}if(entry)break;}
  const sections=SECTIONS.flatMap((category,i)=>{const found=devices.find(([,d])=>(d.identifiers||[]).some(([dom,id])=>dom==='genesis_wp'&&id===`${entry}_${category}`));return found?[{category,id:found[0],device:found[1],icon:ICONS[i]}]:[];});
  const entities=Object.entries(this._hass.entities||{}).flatMap(([id,e])=>{const state=this._hass.states[id];return !e.disabled_by&&state?.attributes.register&&sections.some(s=>s.id===e.device_id)?[{id,state,register:state.attributes.register,deviceId:e.device_id}]:[];});return {sections,entities};
 }
 _name(e){const d=this._hass.devices[e.deviceId];let name=e.state.attributes.friendly_name||e.id;for(const prefix of [d?.name_by_user,d?.name])if(prefix&&name.startsWith(prefix+' ')){name=name.slice(prefix.length+1);break;}return name;}
 _value(e){const s=e.state;return ['unavailable','unknown'].includes(s.state)?s.state:[s.state,s.attributes.unit_of_measurement].filter(Boolean).join(' ');}
 _row(e){const name=this._name(e);return `<div class="reading" data-entity="${esc(e.id)}" role="button" tabindex="0"><span class="label" title="${esc(name)}">${esc(name)}</span><strong>${esc(this._value(e))}</strong></div>`;}
 _render(){if(!this._hass)return;const {sections,entities}=this._data();const selected=sections.find(s=>s.category===this._section);let body;
  if(!selected){body=`<h1>Heat pump</h1><div class="grid">${sections.map(s=>{const own=entities.filter(e=>e.deviceId===s.id),count=own.filter(e=>alarm(e)&&e.state.state==='on').length;
   const keys=(KEYS[s.category]||[]).flatMap(k=>{const e=entities.find(e=>e.register==='input_'+k);return e?[e]:[];});const mode=s.category==='internal_heat_pump'?entities.find(e=>e.register==='input_1'):null;
   return `<article data-tile="${s.category}"><button class="header" data-section="${s.category}"><ha-icon icon="mdi:${s.icon}"></ha-icon> ${esc(s.device.name_by_user||s.device.name||s.category.replaceAll('_',' '))}</button>${mode?this._row(mode):''}${count?`<span class="badge">${count} active</span>`:''}${keys.length?keys.map(e=>this._row(e)).join(''):'<p>No key readings</p>'}</article>`;}).join('')}</div>`;}
  else {const own=entities.filter(e=>e.deviceId===selected.id),curves=['heating_system','additional_heating_circuits'].includes(selected.category)?own.filter(e=>Array.isArray(e.state.attributes.curve)):[];
   const rows=own.filter(e=>!curves.length||!curvePoint(e));const alarms=rows.filter(alarm);const groups=[['Measurements',rows.filter(e=>!alarm(e)&&e.register.startsWith('input_'))],['Status',rows.filter(e=>!alarm(e)&&e.register.startsWith('dinput_'))],['Alarms',alarms.filter(e=>e.state.state!=='off')],['Limits and settings',rows.filter(e=>!alarm(e)&&/^(holding|coil)_/.test(e.register))]];
   body=`<h1>${esc(selected.device.name_by_user||selected.device.name||selected.category)}</h1>${groups.map(([name,items],i)=>{const content=items.map(e=>this._row(e)).join('')+(i===2?`<p>${alarms.filter(e=>e.state.state==='off').length} ok</p>`:'');return i===3?`<details><summary>${name}</summary>${content}</details>`:`<section><h2>${name}</h2>${content}</section>`;}).join('')}${curves.map(e=>`<genesis-wp-heating-curve-card data-curve="${esc(e.id)}"></genesis-wp-heating-curve-card>`).join('')}`;
  }
  const badge=s=>entities.filter(e=>e.deviceId===s.id&&alarm(e)&&e.state.state==='on').length;
  const tabs=`<nav class="tabs" role="tablist"><button role="tab" data-tab="" aria-selected="${!selected}">Overview</button>${sections.map(s=>{const n=badge(s);return `<button role="tab" data-tab="${s.category}" aria-selected="${selected?.category===s.category}">${esc(s.device.name_by_user||s.device.name||s.category.replaceAll('_',' '))}${n?` <span class="badge">${n}</span>`:''}</button>`;}).join('')}</nav>`;
  body=tabs+body;
  this.shadowRoot.innerHTML=`<style>.tabs{display:flex;gap:4px;overflow-x:auto;border-bottom:1px solid var(--divider-color);margin:-16px -16px 16px;padding:0 8px;position:sticky;top:0;background:var(--app-header-background-color,var(--primary-background-color));z-index:1}.tabs button{white-space:nowrap;padding:12px 16px;font-size:14px;border-bottom:2px solid transparent}.tabs [aria-selected=true]{color:var(--primary-color);border-bottom-color:var(--primary-color)}:host{display:block;color:var(--primary-text-color);font-size:14px;padding:16px;box-sizing:border-box}*{box-sizing:border-box}h1{font-size:24px}h2{font-size:18px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:16px}article,section,details{min-width:0;padding:16px;border-radius:12px;background:var(--card-background-color);margin-bottom:12px}.header{font-size:18px;width:100%;text-align:left}button{color:inherit;background:transparent;border:0;padding:8px;cursor:pointer;font:inherit}.reading{display:flex;flex-direction:column;min-width:0;padding:8px;cursor:pointer}.label{font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}strong{font-size:22px;overflow-wrap:anywhere}.badge{color:var(--error-color);font-size:14px}summary{cursor:pointer;font-size:16px}[role=button]:focus-visible,button:focus-visible{outline:2px solid var(--primary-color)}</style>${body}`;
  for(const card of this.shadowRoot.querySelectorAll('[data-curve]')){card.setConfig?.({entity:card.dataset.curve});card.hass=this._hass;}
 }
}
if(!customElements.get('genesis-wp-panel'))customElements.define('genesis-wp-panel',GenesisWpPanel);
