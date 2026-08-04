import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';

export default function Admin() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState([]);
  const [logs, setLogs] = useState([]);
  const [msg, setMsg] = useState(null);
  const [form, setForm] = useState({ username: '', email: '', password: '', role: 'user' });
  const [voltage, setVoltage] = useState('');
  const [voltageMsg, setVoltageMsg] = useState(null);

  const reload = useCallback(async () => {
    const [u, l, v] = await Promise.allSettled([
      api('/users'),
      api('/admin/login-logs?limit=50'),
      api('/settings/grid-voltage'),
    ]);
    if (u.status === 'fulfilled') setUsers(u.value);
    if (l.status === 'fulfilled') setLogs(l.value.logs);
    if (v.status === 'fulfilled') setVoltage(String(v.value.voltage_V));
  }, []);

  useEffect(() => { reload(); }, [reload]);

  async function onCreate(e) {
    e.preventDefault();
    setMsg(null);
    try {
      await api('/users', { method: 'POST', body: form });
      setMsg({ ok: true, text: `User ${form.username} created.` });
      setForm({ username: '', email: '', password: '', role: 'user' });
      reload();
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    }
  }

  async function onRole(u, role) {
    try {
      await api(`/users/${u.id}`, { method: 'PATCH', body: { role } });
      reload();
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    }
  }

  async function onDelete(u) {
    if (!window.confirm(`Delete user ${u.username}?`)) return;
    try {
      await api(`/users/${u.id}`, { method: 'DELETE' });
      reload();
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    }
  }

  async function onSaveVoltage(e) {
    e.preventDefault();
    setVoltageMsg(null);
    try {
      const { voltage_V } = await api('/settings/grid-voltage', {
        method: 'PUT',
        body: { voltage_V: Number(voltage) },
      });
      setVoltage(String(voltage_V));
      setVoltageMsg({ ok: true, text: `Grid voltage set to ${voltage_V} V.` });
    } catch (err) {
      setVoltageMsg({ ok: false, text: err.message });
    }
  }

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <>
      <h1>Administration</h1>

      <div className="card">
        <h2>Device settings</h2>
        <form onSubmit={onSaveVoltage}>
          <label htmlFor="gv">Grid voltage (V)</label>
          <input
            id="gv" type="number" step="1" min="80" max="300"
            value={voltage} onChange={(e) => setVoltage(e.target.value)}
          />
          <p className="subtle">
            Used to compute power from measured current (the device has no voltage
            sensor). Applies to new readings going forward; historical data keeps the
            voltage in effect when it was recorded.
          </p>
          {voltageMsg && <div className={`msg ${voltageMsg.ok ? 'ok' : 'error'}`}>{voltageMsg.text}</div>}
          <div style={{ marginTop: '0.8rem' }}>
            <button className="primary">Save</button>
          </div>
        </form>
      </div>

      <div className="card">
        <h2>Create user</h2>
        <form onSubmit={onCreate}>
          <div className="grid-2">
            <div>
              <label htmlFor="nu">Username</label>
              <input id="nu" value={form.username} onChange={set('username')} />
              <label htmlFor="ne">Email</label>
              <input id="ne" type="email" value={form.email} onChange={set('email')} />
            </div>
            <div>
              <label htmlFor="np">Password</label>
              <input id="np" type="password" value={form.password} onChange={set('password')} />
              <label htmlFor="nr">Role</label>
              <select id="nr" value={form.role} onChange={set('role')}>
                <option value="user">user</option>
                <option value="admin">admin</option>
              </select>
            </div>
          </div>
          {msg && <div className={`msg ${msg.ok ? 'ok' : 'error'}`}>{msg.text}</div>}
          <div style={{ marginTop: '0.8rem' }}>
            <button className="primary">Create</button>
          </div>
        </form>
      </div>

      <div className="card">
        <h2>Users</h2>
        <table>
          <thead>
            <tr><th>ID</th><th>Username</th><th>Email</th><th>Role</th><th>Locked</th><th /></tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td className="num">{u.id}</td>
                <td>{u.username}{u.id === me.id && <span className="subtle"> (you)</span>}</td>
                <td>{u.email}</td>
                <td>
                  <select
                    style={{ width: 'auto' }} value={u.role}
                    disabled={u.id === me.id}
                    onChange={(e) => onRole(u, e.target.value)}
                  >
                    <option value="user">user</option>
                    <option value="admin">admin</option>
                  </select>
                </td>
                <td>{u.locked_until ? new Date(u.locked_until).toLocaleTimeString() : '—'}</td>
                <td>
                  <button className="danger" disabled={u.id === me.id} onClick={() => onDelete(u)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Recent login attempts</h2>
        <table>
          <thead>
            <tr><th>When</th><th>Username</th><th>Result</th><th>Reason</th></tr>
          </thead>
          <tbody>
            {logs.map((l, i) => (
              <tr key={i}>
                <td>{new Date(l.timestamp).toLocaleString()}</td>
                <td>{l.username}</td>
                <td>{l.success ? '✅ success' : '❌ failed'}</td>
                <td className="subtle">{l.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
