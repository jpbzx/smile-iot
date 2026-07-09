import { useCallback, useState } from 'react';
import { api } from '../api/client.js';
import { CurrentChart, DailyChart, PowerChart } from '../components/EnergyCharts.jsx';
import { usePolling } from '../hooks/usePolling.js';

const POLL_MS = 5000;
const WINDOWS = { '15 min': { minutes: 15, every: '10s' },
                  '60 min': { minutes: 60, every: '10s' },
                  '3 h':    { minutes: 180, every: '1m' } };

function Kpi({ label, value, unit, digits = 2 }) {
  return (
    <div className="kpi">
      <div className="label">{label}</div>
      <div className="value">
        {value == null ? '—' : value.toFixed(digits)}
        <span className="unit">{unit}</span>
      </div>
    </div>
  );
}

function StateChip({ latest }) {
  if (!latest) return <span className="chip offline"><span className="dot" />No data</span>;
  const on = latest.outlet_state === 'ON';
  return (
    <span className={`chip ${on ? 'on' : 'off'}`}>
      <span className="dot" />Outlet {latest.outlet_state}
    </span>
  );
}

export default function Dashboard() {
  const [latest, setLatest] = useState(null);
  const [points, setPoints] = useState([]);
  const [days, setDays] = useState([]);
  const [status, setStatus] = useState(null);
  const [windowKey, setWindowKey] = useState('15 min');
  const [cmdMsg, setCmdMsg] = useState(null);

  const refresh = useCallback(async () => {
    const w = WINDOWS[windowKey];
    const [l, r, d, s] = await Promise.allSettled([
      api('/telemetry/latest'),
      api(`/telemetry/range?minutes=${w.minutes}&every=${w.every}`),
      api('/telemetry/daily?days=14'),
      api('/system/status'),
    ]);
    if (l.status === 'fulfilled') setLatest(l.value);           // null on 204
    if (r.status === 'fulfilled') setPoints(r.value.points);
    if (d.status === 'fulfilled') setDays(d.value.days);
    if (s.status === 'fulfilled') setStatus(s.value);
  }, [windowKey]);

  usePolling(refresh, POLL_MS, [refresh]);

  async function sendCommand(path, body) {
    setCmdMsg(null);
    try {
      await api(path, { method: 'POST', body });
      setCmdMsg({ ok: true, text: 'Command published — the board confirms via telemetry within ~2 s.' });
    } catch (err) {
      setCmdMsg({ ok: false, text: err.message });
    }
  }

  const powerVals = points.map((p) => p.power_W).filter((v) => v != null);
  const avgPower = powerVals.length ? powerVals.reduce((a, b) => a + b, 0) / powerVals.length : null;
  const peakPower = powerVals.length ? Math.max(...powerVals) : null;
  const deviceOnline = status?.last_reading_age_s != null && status.last_reading_age_s <= 10;

  return (
    <>
      {latest?.trip_latched && (
        <div className="banner-critical">
          <span className="icon">⚠️</span>
          <div style={{ flex: 1 }}>
            <strong>Overcurrent trip latched</strong> — the firmware cut the outlet and
            refuses ON commands until the trip is reset.
          </div>
          <button className="danger" onClick={() => sendCommand('/control/reset-trip')}>
            Reset trip
          </button>
        </div>
      )}

      <div className="row" style={{ justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap' }}>
        <h1 style={{ margin: 0 }}>Energy dashboard</h1>
        <div className="row">
          <span className={`chip ${deviceOnline ? 'on' : 'offline'}`}>
            <span className="dot" />
            Device {deviceOnline ? 'online' : status?.last_reading_age_s == null ? 'never seen' : 'offline'}
          </span>
          <StateChip latest={latest} />
          <span className={`chip ${status?.mqtt_connected ? 'on' : 'offline'}`}>
            <span className="dot" />Broker
          </span>
        </div>
      </div>

      <div className="kpis">
        <Kpi label="Current (RMS)" value={latest?.current_A} unit="A" />
        <Kpi label="Instant power" value={latest?.power_W} unit="W" digits={0} />
        <Kpi label={`Avg power (${windowKey})`} value={avgPower} unit="W" digits={0} />
        <Kpi label={`Peak power (${windowKey})`} value={peakPower} unit="W" digits={0} />
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
          <h2 style={{ margin: 0 }}>Outlet control</h2>
          <div className="row">
            <button
              className="primary"
              disabled={latest?.outlet_state === 'ON'}
              onClick={() => sendCommand('/control/outlet', { state: 'ON' })}
            >
              Turn ON
            </button>
            <button
              disabled={latest?.outlet_state === 'OFF'}
              onClick={() => sendCommand('/control/outlet', { state: 'OFF' })}
            >
              Turn OFF
            </button>
          </div>
        </div>
        {cmdMsg && <div className={`msg ${cmdMsg.ok ? 'ok' : 'error'}`}>{cmdMsg.text}</div>}
      </div>

      <div className="row" style={{ justifyContent: 'flex-end', marginBottom: '0.5rem' }}>
        <label htmlFor="win" style={{ margin: 0 }}>Window</label>
        <select
          id="win" style={{ width: 'auto' }}
          value={windowKey} onChange={(e) => setWindowKey(e.target.value)}
        >
          {Object.keys(WINDOWS).map((k) => <option key={k}>{k}</option>)}
        </select>
      </div>

      {points.length === 0 ? (
        <div className="card subtle">
          No telemetry in this window yet — check that the ingest worker is running
          and the board (or the fake publisher) is sending to <code>smile-iot/power</code>.
        </div>
      ) : (
        <div className="grid-2">
          <div className="card">
            <h3>Power (W)</h3>
            <PowerChart points={points} />
          </div>
          <div className="card">
            <h3>Current (A)</h3>
            <CurrentChart points={points} />
          </div>
        </div>
      )}

      <div className="card">
        <h3>Daily energy — last 14 days</h3>
        {days.length === 0
          ? <div className="subtle">No history yet.</div>
          : <DailyChart days={days} />}
      </div>
    </>
  );
}
