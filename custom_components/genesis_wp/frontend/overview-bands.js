// Keep the thresholds and labels in sync with cycles.py.
export const RUN_BANDS = [[60, 'good'], [30, 'acceptable'], [10, 'short'], [6, 'very_short'], [0, 'short_cycle']];
export const MEAN_BANDS = [[120, 'good'], [60, 'acceptable'], [30, 'warning'], [0, 'bad']];

export const BAND_COLORS = {
  good: '#5fb88a',
  acceptable: '#a8b86a',
  warning: '#d4a14d',
  short: '#d4a14d',
  very_short: '#e07f52',
  short_cycle: '#d46161',
  bad: '#d46161',
};

export function bandFor(minutes, bands) {
  return bands.find(([minimum]) => minutes >= minimum)?.[1];
}
