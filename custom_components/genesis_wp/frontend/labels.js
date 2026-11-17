// DHF-REQ: genesis-wp-ha/requirement-21
// Short labels by register, shared by the sidebar panel and the device card's diagram layout.
// The section or drawing gives the context, so a label names only the quantity.
// English is the fallback for every language.
const LABELS = {
  en: {
    input_1: 'Mode', input_5: 'Compressor rpm', input_7: 'Discharge', input_8: 'Condenser in',
    input_9: 'Condenser out', input_10: 'Brine in', input_11: 'Brine out', input_12: 'Supply',
    input_13: 'Outdoor', input_15: 'Top', input_16: 'Lower', input_17: 'Weighted', input_18: 'Target',
    input_39: 'Condenser pump', input_40: 'Supply', input_41: 'Tank', input_43: 'Mix valve',
    input_44: 'Brine pump', input_45: 'Hot gas', input_47: 'Valve', input_48: 'Run hours',
    input_54: 'Compressor', input_61: 'Gear', input_67: 'Heater step', input_68: 'Charge target',
    input_92: 'Mix valve', input_94: 'Mix valve', input_103: 'Return', input_104: 'Tank',
    input_105: 'Tank return', input_106: 'Supply', input_117: 'Return', input_118: 'Supply',
    input_119: 'Supply', input_120: 'Return', input_122: 'Bubble point', input_124: 'Dew point',
    input_125: 'Superheat', input_126: 'Subcooling', input_127: 'Low pressure', input_128: 'High pressure',
    input_129: 'Liquid line', input_130: 'Suction gas', input_147: 'Target', input_157: 'Heat output',
    input_158: 'Power in', input_315: 'Expansion valve', input_319: 'Inverter', input_413: 'KSM fan test',
  },
  de: {
    input_1: 'Betriebsart', input_5: 'Verdichter U/min', input_7: 'Heissgas', input_8: 'Kondensator ein',
    input_9: 'Kondensator aus', input_10: 'Sole ein', input_11: 'Sole aus', input_12: 'Vorlauf',
    input_13: 'Aussen', input_15: 'Oben', input_16: 'Unten', input_17: 'Gewichtet', input_18: 'Soll',
    input_39: 'Kondensatorpumpe', input_40: 'Vorlauf', input_41: 'Speicher', input_43: 'Mischventil',
    input_44: 'Solepumpe', input_45: 'Heissgas-Vorlauf', input_47: 'Umschaltventil', input_48: 'Betriebsstunden',
    input_54: 'Verdichter', input_61: 'Stufe', input_67: 'Heizstab-Stufe', input_68: 'Ladesoll',
    input_92: 'Mischventil', input_94: 'Mischventil', input_103: 'R\u00fccklauf', input_104: 'Speicher',
    input_105: 'Speicher-R\u00fccklauf', input_106: 'Vorlauf', input_117: 'R\u00fccklauf', input_118: 'Vorlauf',
    input_119: 'Vorlauf', input_120: 'R\u00fccklauf', input_122: 'Siedepunkt', input_124: 'Taupunkt',
    input_125: '\u00dcberhitzung', input_126: 'Unterk\u00fchlung', input_127: 'Niederdruck', input_128: 'Hochdruck',
    input_129: 'Fl\u00fcssigkeitsleitung', input_130: 'Sauggas', input_147: 'Soll', input_157: 'Heizleistung',
    input_158: 'Leistungsaufnahme', input_315: 'Expansionsventil', input_319: 'Inverter', input_413: 'KSM-L\u00fcftertest',
  },
};

export function language(hass) {
  const lang = hass?.locale?.language || hass?.language || 'en';
  return LABELS[lang] ? lang : (LABELS[lang.split('-')[0]] ? lang.split('-')[0] : 'en');
}

// The short label of a register, or the entity name without its device prefix and without a
// trailing "Temperature" when the register has none.
export function shortLabel(hass, register, friendlyName, deviceName) {
  const short = LABELS[language(hass)][register] ?? LABELS.en[register];
  if (short) return short;
  let name = friendlyName || '';
  if (deviceName && name.startsWith(deviceName + ' ')) name = name.slice(deviceName.length + 1);
  return name.replace(/ Temperature$/, '');
}
