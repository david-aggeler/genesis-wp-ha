import { registerCard } from './register-card.js';
import { patch } from './patch.js';
import { shortLabel } from './labels.js';
// DHF-REQ: genesis-wp-ha/requirement-18
// Read-only entity presentation. Register keys are anchors, never wire reads or decoding.
// Geometry redrawn from genesis-wp interface_spec-6, process control room editions.
const CATEGORIES = ['internal_heat_pump', 'buffer_tank', 'heating_system', 'additional_heating_circuits',
  'hot_water', 'cooling', 'pool', 'ksm', 'electric_meter_and_energy', 'controller'];
const LABELS = {
  internal_heat_pump: 'Internal heat pump', buffer_tank: 'Buffer tank',
  heating_system: 'Heating system', additional_heating_circuits: 'Additional heating circuits',
  hot_water: 'Hot water', cooling: 'Cooling', pool: 'Pool', ksm: 'KSM',
  electric_meter_and_energy: 'Electric meter and energy', controller: 'Controller',
};
const CATEGORY_COLORS = ['#8e6cc0', '#d4a14d', '#5fb88a', '#50a0cb'];
const escapeText = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const key = address => `input_${address}`;
const calculated = new Set([17,18,68,122,124,125,126,147].map(key));
// Temperature legend, 0..45 C. Intermediate colors are linear RGB interpolations.
// The source legend samples these stops at each half degree (0.5..44.5).
const SCALE = [[0,'#2c7bb6'],[10,'#64b5d6'],[20,'#e6c84f'],[30,'#f08a3c'],[45,'#d7301f']];
export function temperatureColor(value) {
  const t = Math.max(0, Math.min(45, value));
  const i = Math.max(1, SCALE.findIndex(([v]) => v >= t));
  const [a, ca] = SCALE[i-1], [b, cb] = SCALE[i];
  const rgb = hex => [1,3,5].map(j => parseInt(hex.slice(j,j+2),16));
  return '#' + rgb(ca).map((c,j) => Math.round(c+(rgb(cb)[j]-c)*(t-a)/(b-a)).toString(16).padStart(2,'0')).join('');
}
// HA may convert a temperature entity to the user's display unit; the scale is in Celsius.
// Returns null for a non-numeric state or a non-temperature unit, so the pipe stays neutral.
const TO_CELSIUS = {'\u00b0C': v => v, '\u00b0F': v => (v-32)*5/9, 'K': v => v-273.15};
export function toCelsius(raw, unit) {
  const convert = TO_CELSIUS[unit], value = Number(raw);
  if (!convert || String(raw ?? '').trim()==='' || !Number.isFinite(value)) return null;
  return convert(value);
}
// [register, x, y] tag anchors in the source drawing's coordinate system.
const POSITIONS = {
  internal_heat_pump: [[44,210,150],[10,210,300],[11,200,602],[130,420,250],[127,420,296],[124,420,342],[125,420,388],
    [5,470,40],[61,630,40],[319,470,88],[48,630,88],[413,470,136],[7,640,250],[128,640,296],
    [122,640,470],[129,640,516],[126,640,562],[315,430,730],[9,960,120],[8,850,645],[39,1010,645],[67,960,214]],
  buffer_tank: [[12,1130,150],[18,1130,104],[41,1130,500],[68,1130,546]],
  heating_system: [[12,1130,150],[18,1130,104],[13,830,-120],[9,960,120]],
  hot_water: [[9,10,20],[47,180,20],[15,410,130],[16,410,330],[17,410,380],[45,10,200],[117,10,430],[118,220,430]],
  cooling: [[11,10,20],[106,410,20],[103,410,380],[104,220,160],[105,220,290],[92,410,220]],
  pool: [[9,10,20],[119,410,20],[120,410,330],[94,220,150]],
  ksm: [[413,10,50]],
  electric_meter_and_energy: [[157,10,50],[158,290,50],
    [69,10,130],[70,195,130],[71,380,130],[72,10,180],[73,195,180],[74,380,180],
    [78,10,230],[79,195,230],[80,380,230]],
  controller: [],
  additional_heating_circuits: [[43,1305,262],[40,1305,380],[147,1305,426],[41,1305,540],['holding_302',1305,0],['coil_33',1305,46]],
};
const VIEWS = {hot_water:'0 0 590 500',cooling:'0 0 590 450',pool:'0 0 590 400',ksm:'0 0 550 100',electric_meter_and_energy:'0 0 550 290',controller:'0 0 550 40',internal_heat_pump:'0 -165 1190 955', buffer_tank:'1080 70 240 620', heating_system:'810 -165 520 865', additional_heating_circuits:'1260 -165 370 865'};
const rect = (x,y,w,h,label) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" fill="currentColor" fill-opacity="0.04" stroke="currentColor"/><text x="${x+6}" y="${y+22}">${label}</text>`;
const pump = (x,y,label) => `<circle cx="${x}" cy="${y}" r="13" fill="none" stroke="currentColor"/><path d="M${x-8},${y-6} l8,14 l8,-14 z" fill="currentColor"/><text x="${x+18}" y="${y+5}">${label}</text>`;
const valve = (x,y,label) => `<path d="M${x-12},${y-8} l24,16 v-16 l-24,16 z" fill="none" stroke="currentColor"/><text x="${x+18}" y="${y-12}">${label}</text>`;
// A part is omitted if none of its sensor entities exists. Disabled entities do not count.
const PARTS = {
  hot_water: [[[15,16,17],rect(390,90,180,330,'Hot water tank')],
    [[47],valve(280,80,'Charging valve')],[[45],rect(20,150,160,40,'Hot gas loop')],
    [[117,118],rect(20,380,350,35,'Surplus heat loop')]],
  cooling: [[[104,105],rect(210,120,180,250,'Cooling tank')],
    [[92],valve(490,290,'Mix valve')],[[106,103],valve(100,80,'Supply valve')+valve(100,350,'Return valve')]],
  pool: [[[119,120],rect(400,120,160,180,'Pool exchanger')],[[94],valve(300,210,'Mix valve')]],
  ksm: [[[413,'dinput_251'],rect(0,0,550,100,'Refrigerant safety module')]],
  electric_meter_and_energy: [[[157,158,69,70,71,72,73,74,78,79,80],rect(0,0,550,290,'Three-phase grid')+['L1','L2','L3'].map((phase,i)=>`<text x="${10+i*185}" y="120">${phase}</text>`).join('')]],
  controller: [[[1],'<text x="6" y="22">Controller</text>']],

  internal_heat_pump: [
    [[10,11],rect(20,300,120,300,'Ground loop')+'<path d="M45,320 L115,346 L45,372 L115,398 L45,424 L115,450 L45,476 L115,502 L45,528 L115,554 L45,580" fill="none" stroke="currentColor"/>'],
    [[10,130],rect(290,340,100,220,'Evaporator')+'<path d="M300,352 L330,385 L300,417 L330,450 L300,483 L330,515 L300,548 M352,548 L382,515 L352,483 L382,450 L352,417 L382,385 L352,352" fill="none" stroke="currentColor"/><line x1="341" y1="345" x2="341" y2="555" stroke="currentColor" stroke-dasharray="3 3"/>'], [[7,9],rect(830,340,100,220,'Condenser')+'<path d="M840,352 L870,385 L840,417 L870,450 L840,483 L870,515 L840,548 M892,548 L922,515 L892,483 L922,450 L892,417 L922,385 L892,352" fill="none" stroke="currentColor"/><line x1="881" y1="345" x2="881" y2="555" stroke="currentColor" stroke-dasharray="3 3"/>'],
    [[5,61],'<circle cx="630" cy="220" r="38" fill="none" stroke="currentColor"/><text x="595" y="225">Compressor</text>'],
    [[44],pump(195,200,'Brine pump')], [[39],pump(1040,620,'Condenser pump')], [[129,124],valve(630,700,'Expansion valve')]],
  buffer_tank: [[[41,68],rect(1120,240,150,400,'Buffer tank')]],
  heating_system: [[[12,18],'<circle cx="1160" cy="200" r="7" fill="currentColor"/><text x="960" y="250">Supply T-piece</text>']],
  additional_heating_circuits: [[[40,43],valve(1420,200,'TR9 A/B')+valve(1470,280,'TR12/13')+pump(1470,340,'FR2')+rect(1425,440,125,120,'Rooms / HC2')],
    [['coil_33','holding_302'],rect(1280,-126,100,98,'HX 24')]],
};
// [path id, temperature register, flow group, path geometry, phase dash]
const PIPES = {
  hot_water: [['charging',9,'hot_water','M10,80 L390,80 L390,160'],
    ['tank-top',15,'hot_water','M390,160 L570,160'],
    ['tank-lower',16,'hot_water','M390,360 L570,360'],
    ['hot-gas',45,'hot_water','M20,240 L370,240 L370,260 L390,260'],
    ['surplus-return',117,'hot_water','M20,470 L20,415'],
    ['surplus-supply',118,'hot_water','M370,415 L370,470']],
  cooling: [['cooling-source',11,'cooling','M10,80 L210,80 L210,140'],
    ['cooling-supply',106,'cooling','M390,140 L570,140 L570,80'],
    ['cooling-return',103,'cooling','M570,350 L390,350'],
    ['tank',104,'cooling','M220,210 L380,210'],
    ['tank-return',105,'cooling','M220,340 L380,340']],
  pool: [['pool-source',9,'pool','M10,80 L400,80 L400,140'],
    ['pool-supply',119,'pool','M560,140 L580,140 L580,80'],
    ['pool-return',120,'pool','M580,380 L580,280 L560,280 L560,310 L300,310 L300,210 L400,210']],
  ksm: [], electric_meter_and_energy: [], controller: [],

  internal_heat_pump: [
    ['brine-in',10,'brine','M60,300 L60,-145 L195,-145 L195,360 L300,360'],
    ['brine-out',11,'brine','M300,545 L140,545'],
    ['suction',130,'compressor','M375,352 L375,220 L592,220','12 6'],
    ['discharge',7,'compressor','M668,220 L845,220 L845,352','12 6'],
    ['liquid',129,'compressor','M845,548 L845,700 L652,700'],
    ['expansion',124,'compressor','M608,700 L375,700 L375,548','3 5'],
    ['condenser-out',9,'compressor','M915,352 L915,200 L1060,200'],
    ['condenser-in',8,'compressor','M1060,620 L915,620 L915,548']],
  buffer_tank: [['supply',12,'buffer','M1080,200 L1270,200 M1160,200 L1160,240'],['return',41,'buffer','M1270,600 L1270,620 L1120,620']],
  heating_system: [['condenser-out',9,'heating','M915,352 L915,200'],['supply',12,'heating','M915,200 L1270,200 M1160,200 L1160,240']],
  additional_heating_circuits: [['buffer-to-mixer',41,'hc2','M1260,200 L1408,200'],
    ['passive-cooling',40,'passive','M1347,-124 L1420,-140 L1420,186'],
    ['passive-return',41,'passive','M1535,600 L1290,600 L1290,-10 L1347,-10 L1347,-28'],
    ['hc2-supply',40,'rooms','M1432,200 L1470,200 L1470,440'],
    ['hc2-return',41,'rooms','M1535,560 L1535,600 L1270,600 M1535,600 L1575,600 L1575,280 L1484,280']],
};
function active(group, mode, passiveEnabled) {
  const passive = mode === 'Passive cooling' && passiveEnabled;
  const compressor = ['Heat','Defrost','Hot water','Anti legionella','Pool'].includes(mode);
  return ({brine:compressor||passive, compressor, heating:['Heat','Defrost'].includes(mode),
    hot_water:['Hot water','Anti legionella'].includes(mode), cooling:mode==='Cool', pool:mode==='Pool',
    buffer:['Heat','Defrost'].includes(mode), hc2:!passive, passive, rooms:true})[group];
}
export class GenesisWpDeviceCard extends HTMLElement {
  setConfig(config) {
    if (!config || !CATEGORIES.includes(config.device)) throw new Error(`device must be one of: ${CATEGORIES.join(', ')}`);
    this._config = {...config};
    for (const field of ['title','entry']) if (this._config[field] === '') delete this._config[field];
    if (!this.shadowRoot) {
      this.attachShadow({mode:'open'});
      this.shadowRoot.addEventListener?.('click', e=>this._activate(e));
      this.shadowRoot.addEventListener?.('keydown', e=>{ if (e.key==='Enter'||e.key===' ') this._activate(e); });
    }
    this._render();
  }
  // DHF-REQ: genesis-wp-ha/requirement-22
  _activate(event) {
    const target=event.target?.closest?.('[data-entity]');
    if (!target) return;
    event.preventDefault?.();
    this.dispatchEvent(new CustomEvent('hass-more-info', {detail:{entityId:target.dataset.entity}, bubbles:true, composed:true}));
  }
  set hass(value) { this._hass=value; this._render(); }
  getCardSize() { return 8; }
  // DHF-REQ: genesis-wp-ha/requirement-20
  static getConfigForm() {
    return {
      schema: [
        {name:'device', required:true, selector:{select:{mode:'dropdown',
          options:CATEGORIES.map(value=>({value,label:LABELS[value]}))}}},
        {name:'title', selector:{text:{}}},
        {name:'entry', selector:{config_entry:{integration:'genesis_wp'}}},
      ],
      computeLabel: ({name}) => ({device:'Plant section',title:'Title',entry:'Config entry'})[name],
    };
  }
  // DHF-REQ: genesis-wp-ha/requirement-20
  static getStubConfig(hass) {
    const devices=Object.values(hass?.devices || {});
    const device=CATEGORIES.find(category=>devices.some(d=>(d.identifiers || []).some(
      ([domain,value])=>domain==='genesis_wp' && value.endsWith(`_${category}`))));
    return {device:device || 'internal_heat_pump'};
  }
  _resolve() {
    const {device,entry} = this._config;
    const devices=Object.entries(this._hass.devices||{});
    const suffix=`_${device}`;
    for(const [id,d] of devices) {
      const identifier=(d.identifiers||[]).find(([domain,value])=>domain==='genesis_wp' && value.endsWith(suffix) && (!entry||value===`${entry}${suffix}`));
      if(identifier) return {id,device:d,entry:identifier[1].slice(0,-suffix.length)};
    }
    return null;
  }
  _value(state) {
    const value=state?.state || 'unavailable';
    if(['unknown','unavailable'].includes(value)) return this._hass.localize?.(`state.default.${value}`)||value;
    return `${value}${state.attributes.unit_of_measurement ? ' '+state.attributes.unit_of_measurement : ''}`;
  }
  _tag(entity, x, y, context=false, panel=false) {
    const {id,state,register}=entity;
    const cls = `${register==='dinput_251'&&state.state==='on'?'fault ':''}${context?'context':'own'}${calculated.has(register)?' calculated':''}${id.startsWith('binary_sensor.')?' chip':''}`;
    const title=state.attributes.friendly_name||id;
    return `<g class="${cls}" role="button" tabindex="0" data-register="${escapeText(register)}" data-entity="${escapeText(id)}" transform="translate(${x} ${y})"><title>${escapeText(title)}</title><rect width="${panel?260:150}" height="40" rx="4"/><text x="6" y="14">${escapeText(title)}</text><text class="value" x="6" y="32">${escapeText(this._value(state))}</text></g>`;
  }
  // Short tag label: the name without its device's prefix and without a trailing "Temperature".
  _short(entity) {
    const d=this._hass.devices?.[entity.deviceId];
    return shortLabel(this._hass, entity.register, entity.state.attributes.friendly_name||entity.id, d?.name_by_user||d?.name);
  }
  _chip(entity, left, top, width, context) {
    const {id,state,register}=entity;
    const cls=`chip ${context?'context':'own'}${calculated.has(register)?' calculated':''}${register==='dinput_251'&&state.state==='on'?' fault':''}`;
    return `<div class="${cls}" role="button" tabindex="0" data-register="${escapeText(register)}" data-entity="${escapeText(id)}" style="left:${left.toFixed(2)}%;top:${top.toFixed(2)}%;width:${width.toFixed(2)}%" title="${escapeText(state.attributes.friendly_name||id)}"><span class="label">${escapeText(this._short(entity))}</span><span class="value">${escapeText(this._value(state))}</span></div>`;
  }
  _panel(category, entities) {
    const setting=e=>/^(holding|coil)_/.test(e.register)||e.diagnostic;
    const controllerGroups=[
      ['Operation',[1,55,56,62,63,64,65,66,82].map(key).concat(['dinput_201','dinput_204'])],
      ['Plant',[13,121,157,158].map(key)],
      ['Gears',[143,144,145,146].map(key)],
      ['Versions',[57,58,59,311,312,313].map(key)],
    ];
    const groups=category==='controller'?controllerGroups:[];
    let y=0, tags='';
    // Keep measurements before settings, including across named controller groups.
    for(const settings of [false,true]) {
      const candidates=entities.filter(e=>Boolean(setting(e))===settings);
      const sections=[...groups,['Values',[]]].map(([name,registers],i)=>[name,
        candidates.filter(e=>i===groups.length
          ? !groups.some(([,keys])=>keys.includes(e.register))
          : registers.includes(e.register))]);
      for(const [name,items] of sections) {
        if(!items.length) continue;
        if(groups.length) { tags+=`<text x="6" y="${y+16}">${name}${settings?' - Settings':''}</text>`; y+=26; }
        tags+=items.map((e,i)=>this._tag(e,(i%2)*280,y+Math.floor(i/2)*50,false,true)).join('');
        y+=Math.ceil(items.length/2)*50;
      }
    }
    return tags?`<svg class="values" viewBox="0 0 550 ${y}" aria-label="Values">${tags}</svg>`:'';
  }
  _render() {
    if(!this._config || !this._hass || !this.shadowRoot) return;
    const category=this._config.device, resolved=this._resolve();
    let body='', mode='unavailable', title=this._config.title||resolved?.device.name_by_user||resolved?.device.name||category;
    if(!resolved) body='<p>Device not found</p>';
    else {
      const byRegister=new Map(), own=[];
      const devices=this._hass.devices||{};
      for(const [id,e] of Object.entries(this._hass.entities||{})) {
        const state=this._hass.states[id];
        if(e.disabled_by || !state?.attributes.register) continue;
        const sameEntry=(devices[e.device_id]?.identifiers||[]).some(([domain,value])=>domain==='genesis_wp'&&(value===resolved.entry||CATEGORIES.some(c=>value===`${resolved.entry}_${c}`)));
        if(!sameEntry) continue;
        const entity={id,state,register:state.attributes.register,deviceId:e.device_id,diagnostic:e.entity_category==='diagnostic'};
        byRegister.set(entity.register,entity);
        if(e.device_id===resolved.id) own.push(entity);
      }
      mode=byRegister.get('input_1')?.state.state||'unavailable';
      const passiveEnabled=byRegister.get('coil_33')?.state.state==='on';
      const exists = r => byRegister.has(typeof r==='number'?key(r):r);
      const parts=PARTS[category].filter(([sensors])=>sensors.some(exists)).map(([,svg])=>svg).join('');
      const pipes=PIPES[category].filter(([,r])=>exists(r)).map(([id,r,group,d,dash])=>{
        const state=byRegister.get(key(r))?.state;
        const celsius=state ? toCelsius(state.state, state.attributes.unit_of_measurement) : null;
        const flow=active(group,mode,passiveEnabled);
        const color=flow&&celsius!==null?temperatureColor(celsius):'currentColor';
        return `<path data-path="${id}" data-flow="${flow?'active':'idle'}" d="${d}" fill="none" stroke="${color}" stroke-opacity="${flow?1:0.22}" stroke-width="5"${dash?` stroke-dasharray="${dash}"`:''}/>`;
      }).join('');
      const positioned=new Set();
      const diagram=this._config.layout==='diagram';
      const [vx,vy,vw,vh]=VIEWS[category].split(' ').map(Number);
      const tags=POSITIONS[category].map(([r,x,y])=>{
        const register=typeof r==='number'?key(r):r, entity=byRegister.get(register);
        if(!entity) return '';
        positioned.add(register);
        return diagram?this._chip(entity,(x-vx)/vw*100,(y-vy)/vh*100,150/vw*100,!own.includes(entity)):this._tag(entity,x,y,!own.includes(entity));
      }).join('');
      const alarms=category==='ksm'?[]:own.filter(e=>e.id.startsWith('binary_sensor.')&&e.state.attributes.device_class==='problem');
      const panel=own.filter(e=>!positioned.has(e.register)).sort((a,b)=>{
        const setting=e=>/^(holding|coil)_/.test(e.register)||e.diagnostic?1:0;
        return setting(a)-setting(b)||a.id.localeCompare(b.id);
      });
      const activeAlarms=alarms.filter(e=>e.state.state==='on');
      const legend=`<svg viewBox="0 0 460 65" aria-label="Temperature legend"><text x="0" y="12">pipe color = measured temperature [\u00b0C]</text>${Array.from({length:46},(_,i)=>`<rect x="${i*10}" y="18" width="10" height="12" fill="${temperatureColor(i)}"/>`).join('')}<text x="0" y="44">0</text><text x="440" y="44">45</text><text x="0" y="62">gray: idle; solid outline: own; dotted: context; dashed: calculated</text></svg>`;
      // layout 'diagram': tags are HTML chips over the drawing, so their text keeps the theme size.
      body=diagram
        ? `<div class="stage" style="aspect-ratio:${vw}/${vh};min-width:${Math.round(vw*0.75)}px"><svg class="drawing" viewBox="${VIEWS[category]}" role="img" aria-label="${escapeText(title)}">${parts}${pipes}</svg>${tags}</div><div class="legend"><span>pipe color = measured temperature [\u00b0C]</span><span class="scale"><span>0</span><span class="bar" style="background:linear-gradient(90deg,${SCALE.map(([v,c])=>`${c} ${v/45*100}%`).join(',')})"></span><span>45</span></span><span>gray: idle; solid: own; dotted: context; dashed: calculated</span></div>`
        : `<svg viewBox="${VIEWS[category]}" role="img" aria-label="${escapeText(title)}">${parts}${pipes}${tags}</svg>${legend}`;
      // layout 'diagram': the sidebar panel lists the values itself.
      if(this._config.layout!=='diagram') body+=this._panel(category,panel);
      if(activeAlarms.length) body+=`<div class="alarms" role="status">${activeAlarms.map(e=>escapeText(e.state.attributes.friendly_name||e.id)).join('<br>')}</div>`;
    }
    const diagram=this._config.layout==='diagram';
    patch(this.shadowRoot, `<style>[role=button]{cursor:pointer}[role=button]:focus-visible{outline:2px solid var(--primary-color)}:host{display:block;color:var(--primary-text-color)}ha-card{padding:16px}h2{font-size:var(--ha-font-size-xl);font-weight:var(--ha-font-weight-normal)}.mode{color:var(--secondary-text-color)}svg{display:block;width:100%;height:auto}text{fill:currentColor;font-family:inherit;font-size:11px}.own rect,.context rect{fill:var(--card-background-color);stroke:var(--tag-color);stroke-width:1.5}.context{opacity:.65}.context rect{stroke-dasharray:2 3}.own.calculated rect{stroke-dasharray:6 3}.alarms{color:var(--error-color,#d46161);padding:8px}.value{font-size:13px;font-weight:bold}.chip rect{rx:10px}.stage{position:relative}.stage .drawing{position:absolute;inset:0;width:100%;height:100%}.stage .drawing text{font-size:12px}div.chip{position:absolute;box-sizing:border-box;display:flex;flex-direction:column;padding:0 var(--ha-space-1);border:1.5px solid var(--tag-color);border-radius:var(--ha-border-radius-sm,4px);background:var(--card-background-color);overflow:hidden;cursor:pointer;line-height:1.25}div.chip.context{border-style:dotted;opacity:.8}div.chip.calculated{border-style:dashed}div.chip .label{font-size:var(--ha-font-size-xs);color:var(--secondary-text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}div.chip .value{font-size:var(--ha-font-size-s);font-weight:var(--ha-font-weight-medium);white-space:nowrap}.legend{display:flex;flex-wrap:wrap;gap:var(--ha-space-1) var(--ha-space-4);margin-top:var(--ha-space-2);font-size:var(--ha-font-size-s);color:var(--secondary-text-color)}.scale{display:inline-flex;align-items:center;gap:var(--ha-space-1)}.bar{display:inline-block;width:160px;height:8px;border-radius:4px}.fault{color:var(--error-color,#d46161)}.fault rect{stroke:var(--error-color,#d46161)}</style>${diagram?'<div class="diagram"':'<ha-card'} style="--tag-color:${CATEGORY_COLORS[CATEGORIES.indexOf(category)%4]}">${diagram?'':`<h2>${escapeText(title)}</h2><div class="mode">${escapeText(mode)}</div>`}${body}${diagram?'</div>':'</ha-card>'}`);
  }
}
registerCard('genesis-wp-device-card', GenesisWpDeviceCard, {
  preview: true,
  name: 'Genesis WP device',
  description: 'Read-only process diagram for one plant sub-device.',
});
