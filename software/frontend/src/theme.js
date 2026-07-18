// Chart color tokens (validated reference palette, light+dark selected —
// see docs/dataviz guidance). SVG presentation attributes can't resolve CSS
// vars reliably, so chart marks get hex from here while page chrome uses
// the CSS custom properties in index.css.
import { useEffect, useState } from 'react';

const LIGHT = {
  power: '#2a78d6',      // categorical slot 1 (blue)  — power/energy entity
  current: '#1baf7a',    // categorical slot 2 (aqua)  — current entity
  grid: '#e1e0d9',
  axis: '#c3c2b7',
  ink: '#0b0b0b',
  muted: '#898781',
  surface: '#fcfcfb',
  border: 'rgba(11,11,11,0.10)',
};

const DARK = {
  power: '#3987e5',
  current: '#199e70',
  grid: '#2c2c2a',
  axis: '#383835',
  ink: '#ffffff',
  muted: '#898781',
  surface: '#1a1a19',
  border: 'rgba(255,255,255,0.10)',
};

export function useDarkMode() {
  const [dark, setDark] = useState(
    () => window.matchMedia('(prefers-color-scheme: dark)').matches,
  );
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = (e) => setDark(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  return dark;
}

export function useChartTheme() {
  return useDarkMode() ? DARK : LIGHT;
}
