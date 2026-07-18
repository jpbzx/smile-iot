import { useState } from 'react';
import { api } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';

export default function Profile() {
  const { user } = useAuth();
  const [current, setCurrent] = useState('');
  const [pw1, setPw1] = useState('');
  const [pw2, setPw2] = useState('');
  const [msg, setMsg] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setMsg(null);
    if (pw1 !== pw2) {
      setMsg({ ok: false, text: 'New passwords do not match.' });
      return;
    }
    try {
      await api('/users/me/password', {
        method: 'PUT', body: { current_password: current, new_password: pw1 },
      });
      setMsg({ ok: true, text: 'Password updated.' });
      setCurrent(''); setPw1(''); setPw2('');
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    }
  }

  return (
    <>
      <h1>Profile</h1>
      <div className="card">
        <table>
          <tbody>
            <tr><th style={{ width: 120 }}>Username</th><td>{user.username}</td></tr>
            <tr><th>Email</th><td>{user.email || '—'}</td></tr>
            <tr><th>Role</th><td>{user.role}</td></tr>
          </tbody>
        </table>
      </div>

      <div className="card" style={{ maxWidth: 420 }}>
        <h2>Change password</h2>
        <form onSubmit={onSubmit}>
          <label htmlFor="cur">Current password</label>
          <input id="cur" type="password" value={current} onChange={(e) => setCurrent(e.target.value)} />
          <label htmlFor="n1">New password</label>
          <input id="n1" type="password" value={pw1} onChange={(e) => setPw1(e.target.value)} />
          <label htmlFor="n2">Confirm new password</label>
          <input id="n2" type="password" value={pw2} onChange={(e) => setPw2(e.target.value)} />
          {msg && <div className={`msg ${msg.ok ? 'ok' : 'error'}`}>{msg.text}</div>}
          <div style={{ marginTop: '0.8rem' }}>
            <button className="primary" disabled={!current || pw1.length < 5}>Update password</button>
          </div>
        </form>
      </div>
    </>
  );
}
