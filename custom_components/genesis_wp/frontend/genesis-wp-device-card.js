import { registerCard } from './register-card.js';
// DHF-REQ: genesis-wp-ha/requirement-18
// Read-only entity presentation. Register keys are anchors, never wire reads or decoding.
// Geometry redrawn from genesis-wp interface_spec-6, process control room editions.
const CATEGORIES = ['internal_heat_pump', 'buffer_tank', 'heating_system', 'additional_heating_circuits',
  'hot_water', 'cooling', 'pool', 'ksm', 'electric_meter_and_energy', 'controller'];
const CATEGORY_COLORS = ['#8e6cc0', '#d4a14d', '#5fb88a', '#50a0cb'];
const escapeText = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const key = address => `input_${address}`;
const calculated = new Set([18,68,122,124,125,126,147].map(key));
// Temperature legend, 0..45 C. Intermediate colors are linear RGB interpolations.
// The source legend samples these stops at each half degree (0.5..44.5).
const SCALE = [[0,'#2c7bb6'],[10,'#64b5d6'],[20,'#e6c84f'],[30,'#f08a3c'],[45,'#d7301f']];
function temperatureColor(value) {
  const t = Math.max(0, Math.min(45, value));
  const i = Math.max(1, SCALE.findIndex(([v]) => v >= t));
  const [a, ca] = SCALE[i-1], [b, cb] = SCALE[i];
  const rgb = hex => [1,3,5].map(j => parseInt(hex.slice(j,j+2),16));
  return '#' + rgb(ca).map((c,j) => Math.round(c+(rgb(cb)[j]-c)*(t-a)/(b-a)).toString(16).padStart(2,'0')).join('');
}
// HA may convert a temperature entity to the user's display unit; the scale is in Celsius.
// Returns null for a non-numeric state or a non-temperature unit, so the pipe stays neutral.
const TO_CELSIUS = {'\u00b0C': v => v, '\u00b0F': v => (v-32)*5/9, 'K': v => v-273.15};
function toCelsius(raw, unit) {
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
  additional_heating_circuits: [[43,1305,262],[40,1305,380],[147,1305,426],[41,1305,540],['holding_302',1305,0],['coil_33',1305,46]],
};
const VIEWS = {internal_heat_pump:'0 -165 1190 955', buffer_tank:'1080 70 240 620', heating_system:'810 -165 520 865', additional_heating_circuits:'1260 -165 370 865'};
const rect = (x,y,w,h,label) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" fill="currentColor" fill-opacity="0.04" stroke="currentColor"/><text x="${x+6}" y="${y+22}">${label}</text>`;
const pump = (x,y,label) => `<circle cx="${x}" cy="${y}" r="13" fill="none" stroke="currentColor"/><path d="M${x-8},${y-6} l8,14 l8,-14 z" fill="currentColor"/><text x="${x+18}" y="${y+5}">${label}</text>`;
const valve = (x,y,label) => `<path d="M${x-12},${y-8} l24,16 v-16 l-24,16 z" fill="none" stroke="currentColor"/><text x="${x+18}" y="${y-12}">${label}</text>`;
// A part is omitted if none of its sensor entities exists. Disabled entities do not count.
const PARTS = {
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
    buffer:['Heat','Defrost'].includes(mode), hc2:!passive, passive, rooms:true})[group];
}
class GenesisWpDeviceCard extends HTMLElement {
  setConfig(config) {
    if (!config || !CATEGORIES.includes(config.device)) throw new Error(`device must be one of: ${CATEGORIES.join(', ')}`);
    this._config = {...config};
    if (!this.shadowRoot) this.attachShadow({mode:'open'});
    this._render();
  }
  set hass(value) { this._hass=value; this._render(); }
  getCardSize() { return 8; }
  static getStubConfig() { return {device:'internal_heat_pump'}; }
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
    const cls = `${context?'context':'own'}${calculated.has(register)?' calculated':''}${id.startsWith('binary_sensor.')?' chip':''}`;
    const title=state.attributes.friendly_name||id;
    return `<g class="${cls}" data-register="${escapeText(register)}" data-entity="${escapeText(id)}" transform="translate(${x} ${y})"><title>${escapeText(title)}</title><rect width="${panel?260:150}" height="40" rx="4"/><text x="6" y="14">${escapeText(title)}</text><text class="value" x="6" y="32">${escapeText(this._value(state))}</text></g>`;
  }
  _render() {
    if(!this._config || !this._hass || !this.shadowRoot) return;
    const category=this._config.device, resolved=this._resolve();
    let body='', mode='unavailable', title=this._config.title||resolved?.device.name_by_user||resolved?.device.name||category;
    if(!POSITIONS[category]) body='<p>Not drawn yet</p>';
    else if(!resolved) body='<p>Device not found</p>';
    else {
      const byRegister=new Map(), own=[];
      const devices=this._hass.devices||{};
      for(const [id,e] of Object.entries(this._hass.entities||{})) {
        const state=this._hass.states[id];
        if(e.disabled_by || !state?.attributes.register) continue;
        const sameEntry=(devices[e.device_id]?.identifiers||[]).some(([domain,value])=>domain==='genesis_wp'&&(value===resolved.entry||CATEGORIES.some(c=>value===`${resolved.entry}_${c}`)));
        if(!sameEntry) continue;
        const entity={id,state,register:state.attributes.register,diagnostic:e.entity_category==='diagnostic'};
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
      const tags=POSITIONS[category].map(([r,x,y])=>{
        const register=typeof r==='number'?key(r):r, entity=byRegister.get(register);
        if(!entity) return '';
        positioned.add(register);
        return this._tag(entity,x,y,!own.includes(entity));
      }).join('');
      const alarms=own.filter(e=>e.id.startsWith('binary_sensor.')&&e.state.attributes.device_class==='problem');
      const panel=own.filter(e=>!positioned.has(e.register)).sort((a,b)=>{
        const setting=e=>/^(holding|coil)_/.test(e.register)||e.diagnostic?1:0;
        return setting(a)-setting(b)||a.id.localeCompare(b.id);
      });
      const activeAlarms=alarms.filter(e=>e.state.state==='on');
      const legend=`<svg viewBox="0 0 460 65" aria-label="Temperature legend"><text x="0" y="12">pipe color = measured temperature [\u00b0C]</text>${Array.from({length:46},(_,i)=>`<rect x="${i*10}" y="18" width="10" height="12" fill="${temperatureColor(i)}"/>`).join('')}<text x="0" y="44">0</text><text x="440" y="44">45</text><text x="0" y="62">gray: idle; solid outline: own; dotted: context; dashed: calculated</text></svg>`;
      body=`<svg viewBox="${VIEWS[category]}" role="img" aria-label="${escapeText(title)}">${parts}${pipes}${tags}</svg>${legend}`;
      if(panel.length) body+=`<svg class="values" viewBox="0 0 550 ${Math.ceil(panel.length/2)*50}" aria-label="Values">${panel.map((e,i)=>this._tag(e,(i%2)*280,Math.floor(i/2)*50,false,true)).join('')}</svg>`;
      if(activeAlarms.length) body+=`<div class="alarms" role="status">${activeAlarms.map(e=>escapeText(e.state.attributes.friendly_name||e.id)).join('<br>')}</div>`;
    }
    this.shadowRoot.innerHTML=`<style>:host{display:block;color:var(--primary-text-color)}ha-card{padding:16px}h2{font-size:20px}.mode{color:var(--secondary-text-color)}svg{display:block;width:100%;height:auto}text{fill:currentColor;font-family:inherit;font-size:11px}.own rect,.context rect{fill:var(--card-background-color);stroke:var(--tag-color);stroke-width:1.5}.context{opacity:.65}.context rect{stroke-dasharray:2 3}.own.calculated rect{stroke-dasharray:6 3}.alarms{color:var(--error-color,#d46161);padding:8px}.value{font-size:13px;font-weight:bold}.chip rect{rx:10px}</style><ha-card style="--tag-color:${CATEGORY_COLORS[CATEGORIES.indexOf(category)%4]}"><h2>${escapeText(title)}</h2><div class="mode">${escapeText(mode)}</div>${body}</ha-card>`;
  }
}
registerCard('genesis-wp-device-card', GenesisWpDeviceCard, {
  name: 'Genesis WP device',
  description: 'Read-only process diagram for one plant sub-device.',
});
