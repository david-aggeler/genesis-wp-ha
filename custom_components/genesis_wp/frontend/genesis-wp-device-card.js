import { registerCard } from './register-card.js';
import { patch } from './patch.js';
import { shortLabel } from './labels.js';
// DHF-REQ: genesis-wp-ha/requirement-18
// Read-only entity presentation. Register keys are anchors, never wire reads or decoding.
// Geometry redrawn from genesis-wp interface_spec-6, process control room editions.
const CATEGORIES = ['internal_heat_pump',
  'hot_water', 'cooling', 'pool', 'ksm', 'electric_meter_and_energy', 'controller'];
// These child devices still supply entities to the full-plant drawing.
const PLANT_CATEGORIES = [...CATEGORIES, 'buffer_tank', 'heating_system', 'additional_heating_circuits'];
const LABELS = {
  internal_heat_pump: 'Internal heat pump',
  hot_water: 'Hot water', cooling: 'Cooling', pool: 'Pool', ksm: 'KSM',
  electric_meter_and_energy: 'Electric meter and energy', controller: 'Controller',
};
const CATEGORY_COLORS = {
  internal_heat_pump: '#8e6cc0', hot_water: '#8e6cc0', cooling: '#d4a14d', pool: '#5fb88a',
  ksm: '#50a0cb', electric_meter_and_energy: '#8e6cc0', controller: '#d4a14d',
};
const escapeText = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const key = address => `input_${address}`;
// DHF-REQ: genesis-wp-ha/requirement-27
const calculated = new Set([17,18,68,122,124,125,126,147].map(key));
const estimated = new Set(['derived_condenser_flow', 'derived_brine_flow']);
const valueSource = register => estimated.has(register) ? ' estimated' : calculated.has(register) ? ' calculated' : '';
const styleLegend = 'solid: measured; faded chip: other section; dashed: calculated by the controller; \u2248: estimated; faded: idle; gray: no sensor';
// The standalone SVG legend cannot wrap text, so the style legend is split at '; ' into lines of at
// most STYLE_LEGEND_LINE_CHARS characters (8px text, about 4.2 units per character, inside 460 units).
const STYLE_LEGEND_LINE_CHARS = 90;
const styleLegendLines = styleLegend.split('; ').reduce((lines, part, i, parts) => {
  const piece = i < parts.length - 1 ? `${part};` : part;
  const last = lines[lines.length - 1];
  if (last !== undefined && last.length + 1 + piece.length <= STYLE_LEGEND_LINE_CHARS) lines[lines.length - 1] = `${last} ${piece}`;
  else lines.push(piece);
  return lines;
}, []);
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
// Diagram rows are 46 units apart: a 44-unit chip plus a 2-unit gap (requirement-24, ac-102).
const POSITIONS = {
  internal_heat_pump: [[10,30,420],[44,245,188],
    // Estimated flows beside their circulation pumps (ac-108): brine above the brine pump speed,
    // condenser below the condenser pump speed.
    ['derived_brine_flow',245,142],['derived_condenser_flow',940,504],[11,262,540],['coil_33',30,140],['holding_302',30,186],[130,425,218],[127,425,264],[124,425,310],[125,425,356],
    [5,250,0],[61,410,0],[319,250,46],[48,410,46],[413,250,92],[7,640,218],[128,640,264],
    [122,640,340],[129,640,386],[126,640,432],
    // Expansion valve opening centered right below the valve symbol at (630, 510) (ac-109).
    [315,555,530],[9,940,230],[67,965,306],[8,940,412],[39,940,458],
    // Heating circuit 1: settings at the top of the circuit, T33 and its set point by the T-piece.
    // Side-by-side columns keep a 4-unit gap, rows a 2-unit gap (issue-21).
    ['holding_5',940,60],['coil_9',1094,60],['holding_4',940,106],['holding_3',1094,106],[18,1095,186],[12,1095,232],
    // Buffer tank: T31 reads the tank-bottom water, so its chip sits on the tank (issue-21).
    // Input 68 (charge target) has no chip: the owner dropped it from the drawing (ac-93).
    [41,1165,500],
    // Heating circuit 2: right of TR12/13, above FR2 and the rooms (ac-105).
    ['holding_107',1565,56],['holding_108',1735,56],['coil_11',1565,102],[43,1565,216],[147,1735,170],[40,1735,216]],
  hot_water: [[9,10,20],[47,180,20],[15,410,130],[16,410,330],[17,410,380],[45,10,200],[117,10,430],[118,220,430]],
  cooling: [[11,10,20],[106,410,20],[103,410,380],[104,220,160],[105,220,290],[92,410,220]],
  pool: [[9,10,20],[119,410,20],[120,410,330],[94,220,150]],
  ksm: [[413,10,50]],
  electric_meter_and_energy: [[157,10,50],[158,290,50],
    [69,10,130],[70,195,130],[71,380,130],[72,10,180],[73,195,180],[74,380,180],
    [78,10,230],[79,195,230],[80,380,230]],
  controller: [],
};
const VIEWS = {hot_water:'0 0 590 500',cooling:'0 0 590 450',pool:'0 0 590 400',ksm:'0 0 550 100',electric_meter_and_energy:'0 0 550 290',controller:'0 0 550 40',internal_heat_pump:'0 -40 1900 670'};
const rect = (x,y,w,h,label) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" fill="currentColor" fill-opacity="0.04" stroke="currentColor"/><text x="${x+6}" y="${y+22}">${label}</text>`;
// The triangle points along the pipe in the flow direction; the label sits right, left or above the symbol.
const FLOW_ANGLE = {down:0, left:90, up:180, right:-90};
// Pumps are drawn in front of the pipes (see _render), on a card-colored disc that hides the line.
const pump = (x,y,label,flow='down',place='right') => `<circle class="pump" cx="${x}" cy="${y}" r="13" style="fill:var(--card-background-color)" stroke="currentColor"/><path data-flow-direction="${flow}" d="M${x-8},${y-6} l8,14 l8,-14 z" transform="rotate(${FLOW_ANGLE[flow]} ${x} ${y})" fill="currentColor"/>${
  !label ? ''
  : place==='above' ? `<text x="${x}" y="${y-20}" text-anchor="middle">${label}</text>`
  : place==='below' ? `<text x="${x}" y="${y+30}" text-anchor="middle">${label}</text>`
  : place==='left' ? `<text x="${x-18}" y="${y+5}" text-anchor="end">${label}</text>`
  : `<text x="${x+18}" y="${y+5}">${label}</text>`}`;
// Heat exchanger: label in a header band, zig-zags below it. Pipes attach at the zig-zag ends,
// (x+10 | x+90, y+35 | y+135), through the side walls, so no pipe crosses the label.
const exchanger = (x,y,label) => rect(x,y,100,155,label)+`<path d="M${x+10},${y+35} L${x+40},${y+60} L${x+10},${y+85} L${x+40},${y+110} L${x+10},${y+135} M${x+90},${y+135} L${x+60},${y+110} L${x+90},${y+85} L${x+60},${y+60} L${x+90},${y+35}" fill="none" stroke="currentColor"/><line x1="${x+50}" y1="${y+30}" x2="${x+50}" y2="${y+140}" stroke="currentColor" stroke-dasharray="3 3"/>`;
// Full-plant parts carry data-part and their anchor x, so tests can check the plant order.
const part = (name,x,svg) => `<g data-part="${name}" data-x="${x}">${svg}</g>`;
// Three-way valve: horizontal body plus the third port's triangle pointing up or down.
const valve3 = (x,y,port) => `<path d="M${x-12},${y-8} l24,16 v-16 l-24,16 z" style="fill:var(--card-background-color)" stroke="currentColor"/><path d="M${x},${y} l-8,${port==='up'?-14:14} h16 z" style="fill:var(--card-background-color)" stroke="currentColor"/>`;
const heater = (x,y) => `<g class="heater"><rect x="${x-18}" y="${y-10}" width="36" height="20" rx="3" style="fill:var(--card-background-color)" stroke="currentColor"/>${[-8,0,8].map(d=>`<line x1="${x+d}" y1="${y-6}" x2="${x+d}" y2="${y+6}" stroke="currentColor"/>`).join('')}</g>`;
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
    // The ground loop sits at the bottom; brine runs up to the evaporator and back down.
    [[10,11],rect(30,480,120,110,'Ground loop')+'<path d="M50,512 L130,528 L50,544 L130,560 L50,576" fill="none" stroke="currentColor"/>'],
    [[10,130],exchanger(290,255,'Evaporator')], [[7,9],exchanger(830,255,'Condenser')],
    [[5,61],'<circle cx="630" cy="172" r="38" fill="none" stroke="currentColor"/><text x="630" y="124" text-anchor="middle">Compressor</text>'],
    [[44],pump(225,200,'','down')], [[39],pump(1040,390,'Condenser pump','left','above')], [[129,124],valve(630,510,'Expansion valve')],
    // Passive-cooling exchanger 24 on the brine up-leg; its water side feeds TR9 port A.
    [['coil_33','holding_302'],part('passive_hx',185,rect(130,10,110,100,'Cooling HX')+'<path d="M200,60 C200,38 225,38 225,60" fill="none" stroke="currentColor"/><path d="M145,50 L175,62 L145,74 L175,86 L145,98" fill="none" stroke="currentColor" stroke-opacity="0.4"/>')],
    // Heating circuit 1 -> buffer tank -> heating circuit 2, in plant order.
    [[67],heater(1040,290)],
    [[12,18],part('t33',1220,'<text x="1228" y="318">either way</text>')+'<text x="940" y="48">Heating circuit 1</text>'],
    [[41,68],part('buffer',1240,rect(1160,330,160,250,'Buffer tank'))],
    [[40,43],part('tr9',1420,valve3(1420,290,'up')+'<text x="1412" y="320" text-anchor="end">TR9</text>')+'<text x="1565" y="44">Heating circuit 2</text>'],
    [[43],part('mixer',1540,valve3(1540,290,'down')+'<text x="1528" y="320" text-anchor="end">TR12/13</text>')],
    [[40],part('fr2',1660,pump(1660,290,'FR2','right','below'))],
    [[40,147],part('rooms',1815,rect(1750,270,130,200,'Rooms (HC2)'))]],
};
// [path id, temperature register, flow group, path geometry, phase dash]
// The register may be [shown when, colored by]: a pipe without a sensor on it is drawn while its
// part exists, colored by null, so it stays neutral (issue-21, never a guessed temperature).
// A third element, a label, marks an owner-chosen estimate: the pipe takes that sensor's color,
// carries data-estimated and says "estimated from <label>" on hover (change_request-50).
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
    ['brine-in',10,'brine','M150,500 L200,500 L200,60'],
    ['brine-hx',10,'brine','M225,60 L225,290 L300,290'],
    ['brine-out',11,'brine','M300,390 L250,390 L250,570 L150,570'],
    ['suction',130,'compressor','M380,290 L405,290 L405,172 L592,172','12 6'],
    ['discharge',7,'compressor','M668,172 L805,172 L805,290 L840,290','12 6'],
    ['liquid',129,'compressor','M840,390 L805,390 L805,510 L652,510'],
    ['expansion',124,'compressor','M608,510 L405,510 L405,390 L380,390','3 5'],
    // Water side: supply out and return in run straight and level through the condenser wall.
    ['condenser-out',9,'compressor','M920,290 L1220,290'],
    ['condenser-in',8,'compressor','M1100,390 L920,390'],
    // Buffer: either-way leg at the T33 T-piece. The two cold ports sit at the same height on
    // opposite walls (owner, change_request-50): the return to the condenser pump leaves the left
    // wall level with the room return entering the right wall.
    ['either-way',12,'buffer','M1220,290 L1220,330'],
    ['buffer-return',8,'buffer','M1160,560 L1100,560 L1100,390'],
    // Heating circuit 2 draws from the buffer top through TR9 port B. The room return, its bypass to
    // TR12/13 and its branch to the passive-cooling exchanger carry no sensor: T31 (input 41) sits in
    // a tank wall sleeve and reads the tank-bottom water, not the return (issue-21). The owner chose
    // T31's color as an estimate for the room return only (change_request-50).
    ['hc2-port-b',12,'hc2','M1220,290 L1408,290'],
    ['tr9-mixer',12,'rooms','M1432,290 L1528,290'],
    ['hc2-supply',40,'rooms','M1552,290 L1750,290'],
    ['room-return',[41,41,'T31'],'rooms','M1815,470 L1815,560 L1320,560'],
    ['bypass',[41,null],'rooms','M1540,560 L1540,304'],
    ['passive-port-a',40,'passive','M160,10 L160,-25 L1420,-25 L1420,276'],
    // Passive cooling: the room return leaves at the T31 port, rises over the plant and enters
    // the cooling exchanger from the top (interface_spec-6, "room return to passive-cooling HX").
    ['cooling-return',[41,null],'passive','M1345,560 L1345,-10 L230,-10 L230,10']],
};
// Junction dots [x, y, r, [path ids]]: a dot takes the style of the first active path it joins,
// the idle style when none is active, and is omitted when none of its paths is drawn (issue-22).
const JUNCTIONS = {
  internal_heat_pump: [[1220,290,6,['either-way','hc2-port-b','condenser-out']]],
};
function active(group, mode, passiveEnabled) {
  const passive = mode === 'Passive cooling' && passiveEnabled;
  const compressor = ['Heat','Defrost','Hot water','Anti legionella','Pool'].includes(mode);
  return ({brine:compressor||passive, compressor,
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
  // Home Assistant's formatter applies the entity's display precision and unit (issue-21: a derived
  // flow shows 9.8 L/min, not its raw state); without it, the raw state and unit.
  _value(state, register) {
    const value=state?.state || 'unavailable';
    if(['unknown','unavailable'].includes(value)) return this._hass.localize?.(`state.default.${value}`)||value;
    const prefix = estimated.has(register) && value.trim() && Number.isFinite(Number(value)) ? '\u2248 ' : '';
    if(typeof this._hass.formatEntityState==='function') {
      try { const text=this._hass.formatEntityState(state); if(typeof text==='string' && text) return prefix + text; } catch { /* raw fallback */ }
    }
    return `${prefix}${value}${state.attributes.unit_of_measurement ? ' '+state.attributes.unit_of_measurement : ''}`;
  }
  // DHF-REQ: genesis-wp-ha/requirement-18
  _tag(entity, x, y, context=false, panel=false) {
    const {id,state,register}=entity;
    const cls = `${register==='dinput_251'&&state.state==='on'?'fault ':''}${context?'context':'own'}${valueSource(register)}${id.startsWith('binary_sensor.')?' chip':''}`;
    const title=state.attributes.friendly_name||id;
    const width = panel ? 260 : 150;
    const label = escapeText(this._short(entity));
    return `<g class="${cls}" role="button" tabindex="0" data-register="${escapeText(register)}" data-entity="${escapeText(id)}" transform="translate(${x} ${y})"><title>${escapeText(title)}</title><rect width="${width}" height="40" rx="4"/><foreignObject x="6" y="2" width="${width - 12}" height="18"><div class="tag-label">${label}</div></foreignObject><text class="value" x="6" y="32">${escapeText(this._value(state, register))}</text></g>`;
  }
  // Short tag label: the name without its device's prefix and without a trailing "Temperature".
  _short(entity) {
    const d=this._hass.devices?.[entity.deviceId];
    return shortLabel(this._hass, entity.register, entity.state.attributes.friendly_name||entity.id, d?.name_by_user||d?.name);
  }
  _chip(entity, left, top, width, context) {
    const {id,state,register}=entity;
    const source = valueSource(register);
    const border = source ? '<svg class="chip-border" aria-hidden="true"><rect rx="4"/></svg>' : '';
    const cls=`chip ${context?'context':'own'}${source}${register==='dinput_251'&&state.state==='on'?' fault':''}`;
    return `<div class="${cls}" role="button" tabindex="0" data-register="${escapeText(register)}" data-entity="${escapeText(id)}" style="left:${left.toFixed(2)}%;top:${top.toFixed(2)}%;width:${width.toFixed(2)}%" title="${escapeText(state.attributes.friendly_name||id)}"><span class="label">${escapeText(this._short(entity))}</span><span class="value">${escapeText(this._value(state, register))}</span>${border}</div>`;
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
      const identifiers=new Set([resolved.entry, ...PLANT_CATEGORIES.map(c=>`${resolved.entry}_${c}`)]);
      for(const [id,e] of Object.entries(this._hass.entities||{})) {
        const state=this._hass.states[id];
        if(e.disabled_by || !state?.attributes.register) continue;
        const sameEntry=(devices[e.device_id]?.identifiers||[]).some(([domain,value])=>domain==='genesis_wp'&&identifiers.has(value));
        if(!sameEntry) continue;
        const entity={id,state,register:state.attributes.register,deviceId:e.device_id,diagnostic:e.entity_category==='diagnostic'};
        byRegister.set(entity.register,entity);
        if(e.device_id===resolved.id) own.push(entity);
      }
      mode=byRegister.get('input_1')?.state.state||'unavailable';
      const passiveEnabled=byRegister.get('coil_33')?.state.state==='on';
      const exists = r => byRegister.has(typeof r==='number'?key(r):r);
      const drawn=PARTS[category].filter(([sensors])=>sensors.some(exists)).map(([,svg])=>svg);
      const front=svg=>svg.includes('class="pump"')||svg.includes('class="heater"');
      const parts=drawn.filter(svg=>!front(svg)).join(''), frontParts=drawn.filter(front).join('');
      const styles=new Map();
      const pipesSvg=PIPES[category].filter(([,r])=>exists(Array.isArray(r)?r[0]:r)).map(([id,r,group,d,dash])=>{
        const sensor=Array.isArray(r)?r[1]:r, estimate=Array.isArray(r)?r[2]:undefined;
        const state=sensor===null?null:byRegister.get(key(sensor))?.state;
        const celsius=state ? toCelsius(state.state, state.attributes.unit_of_measurement) : null;
        const flow=active(group,mode,passiveEnabled);
        const color=flow&&celsius!==null?temperatureColor(celsius):'currentColor';
        const opacity = flow ? (sensor === null ? 0.75 : 1) : 0.22;
        styles.set(id,{flow,color,opacity});
        const estimated=estimate&&flow&&celsius!==null;
        return `<path data-path="${id}" data-flow="${flow?'active':'idle'}"${estimated?` data-estimated="${key(sensor)}"`:''} d="${d}" fill="none" stroke="${color}" stroke-opacity="${opacity}" stroke-width="5"${dash?` stroke-dasharray="${dash}"`:''}>${estimated?`<title>estimated from ${estimate}</title>`:''}</path>`;
      }).join('');
      const junctions=(JUNCTIONS[category]||[]).map(([x,y,r,ids])=>{
        const joined=ids.map(id=>styles.get(id)).filter(Boolean);
        if(!joined.length) return '';
        const s=joined.find(j=>j.flow)||{flow:false,color:'currentColor',opacity:0.22};
        return `<circle class="junction" data-junction="${ids[0]}" data-flow="${s.flow?'active':'idle'}" cx="${x}" cy="${y}" r="${r}" fill="${s.color}" fill-opacity="${s.opacity}"/>`;
      }).join('');
      const pipes=pipesSvg+junctions;
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
      const legend=`<svg viewBox="0 0 460 ${52+styleLegendLines.length*11}" aria-label="Temperature legend"><text x="0" y="12">pipe color = measured temperature [\u00b0C]</text>${Array.from({length:46},(_,i)=>`<rect x="${i*10}" y="18" width="10" height="12" fill="${temperatureColor(i)}"/>`).join('')}<text x="0" y="44">0</text><text x="440" y="44">45</text>${styleLegendLines.map((line,i)=>`<text x="0" y="${60+i*11}" class="style-legend">${line}</text>`).join('')}</svg>`;
      // layout 'diagram': tags and part labels are HTML over the drawing, so their text keeps the
      // theme size (--ha-font-size-s) at any stage width. Below 0.67 px per unit the stage stops
      // shrinking and scrolls: a two-line chip (about 29 px) then still fits its 44-unit row.
      const labels=[];
      const svgOnly=svg=>diagram?svg.replace(/<text x="(-?[\d.]+)" y="(-?[\d.]+)"(?: text-anchor="(\w+)")?>([^<]*)<\/text>/g,(m,x,y,anchor,text)=>{
        labels.push(`<span class="part-label" style="left:${((x-vx)/vw*100).toFixed(2)}%;top:${((y-vy)/vh*100).toFixed(2)}%;transform:translate(${anchor==='middle'?-50:anchor==='end'?-100:0}%,-80%)">${text}</span>`);
        return '';
      }):svg;
      const drawingParts=svgOnly(parts), drawingFront=svgOnly(frontParts);
      body=diagram
        ? `<div class="stage" style="aspect-ratio:${vw}/${vh};min-width:${Math.round(vw*0.67)}px"><svg class="drawing" viewBox="${VIEWS[category]}" role="img" aria-label="${escapeText(title)}">${drawingParts}${pipes}${drawingFront}</svg>${labels.join('')}${tags}</div><div class="legend"><span>pipe color = measured temperature [\u00b0C]</span><span class="scale"><span>0</span><span class="bar" style="background:linear-gradient(90deg,${SCALE.map(([v,c])=>`${c} ${v/45*100}%`).join(',')})"></span><span>45</span></span><span>${styleLegend}</span></div>`
        : `<svg viewBox="${VIEWS[category]}" role="img" aria-label="${escapeText(title)}">${parts}${pipes}${frontParts}${tags}</svg>${legend}`;
      // layout 'diagram': the sidebar panel lists the values itself.
      if(this._config.layout!=='diagram') body+=this._panel(category,panel);
      if(activeAlarms.length) body+=`<div class="alarms" role="status">${activeAlarms.map(e=>escapeText(e.state.attributes.friendly_name||e.id)).join('<br>')}</div>`;
    }
    const diagram=this._config.layout==='diagram';
    patch(this.shadowRoot, `<style>[role=button]{cursor:pointer}[role=button]:focus-visible{outline:2px solid var(--primary-color)}:host{display:block;color:var(--primary-text-color)}ha-card{padding:16px}h2{font-size:var(--ha-font-size-xl);font-weight:var(--ha-font-weight-normal)}.mode{color:var(--secondary-text-color)}svg{display:block;width:100%;height:auto}text{fill:currentColor;font-family:inherit;font-size:11px}.tag-label{font-size:11px;line-height:17px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.own rect,.context rect{fill:var(--card-background-color);stroke:var(--tag-color);stroke-width:1.5}.context{opacity:.75}.calculated rect,.estimated rect{stroke-dasharray:6 3}.style-legend{font-size:8px}.alarms{color:var(--error-color,#d46161);padding:8px}.value{font-size:13px;font-weight:bold}.chip rect{rx:10px}.stage{position:relative}.stage .drawing{position:absolute;inset:0;width:100%;height:100%}.stage .drawing text{font-size:12px}div.chip{position:absolute;box-sizing:border-box;display:flex;flex-direction:column;padding:0 var(--ha-space-1);border:1.5px solid var(--tag-color);border-radius:var(--ha-border-radius-sm,4px);background:var(--card-background-color);overflow:hidden;cursor:pointer;line-height:1.1}.part-label{position:absolute;white-space:nowrap;line-height:1;font-size:var(--ha-font-size-s);color:var(--primary-text-color);pointer-events:none}div.chip.calculated,div.chip.estimated{border-color:transparent;overflow:visible}.chip-border{position:absolute;inset:-1.5px;width:calc(100% + 3px);height:calc(100% + 3px);pointer-events:none}.chip-border rect{x:.75px;y:.75px;width:calc(100% - 1.5px);height:calc(100% - 1.5px);fill:none}div.chip .label{font-size:var(--ha-font-size-s);color:var(--secondary-text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}div.chip .value{font-size:var(--ha-font-size-s);font-weight:var(--ha-font-weight-medium);white-space:nowrap;overflow:hidden}.legend{display:flex;flex-wrap:wrap;gap:var(--ha-space-1) var(--ha-space-4);margin-top:var(--ha-space-2);font-size:var(--ha-font-size-s);color:var(--secondary-text-color)}.scale{display:inline-flex;align-items:center;gap:var(--ha-space-1)}.bar{display:inline-block;width:160px;height:8px;border-radius:4px}.fault{color:var(--error-color,#d46161)}.fault rect{stroke:var(--error-color,#d46161)}</style>${diagram?'<div class="diagram"':'<ha-card'} style="--tag-color:${CATEGORY_COLORS[category]}">${diagram?'':`<h2>${escapeText(title)}</h2><div class="mode">${escapeText(mode)}</div>`}${body}${diagram?'</div>':'</ha-card>'}`);
  }
}
registerCard('genesis-wp-device-card', GenesisWpDeviceCard, {
  preview: true,
  name: 'Genesis WP device',
  description: 'Read-only process diagram for one plant sub-device.',
});
