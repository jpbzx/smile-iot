import { useEffect, useRef } from 'react';

// Runs fn immediately and then every `ms`. Skips ticks while the tab is
// hidden (no point polling a dashboard nobody is looking at).
export function usePolling(fn, ms, deps = []) {
  const saved = useRef(fn);
  saved.current = fn;

  useEffect(() => {
    let cancelled = false;
    const tick = () => {
      if (!cancelled && !document.hidden) saved.current();
    };
    tick();
    const id = setInterval(tick, ms);
    return () => { cancelled = true; clearInterval(id); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ms, ...deps]);
}
