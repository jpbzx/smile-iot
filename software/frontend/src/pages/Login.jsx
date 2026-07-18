import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';

export default function Login() {
  const { login } = useAuth();
  const [params] = useSearchParams();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  // Password-reset flows (request + confirm). A ?token= in the URL (from the
  // emailed link) opens the confirm form directly.
  const [showReset, setShowReset] = useState(Boolean(params.get('token')));
  const [email, setEmail] = useState('');
  const [resetMsg, setResetMsg] = useState(null);
  const [token, setToken] = useState(params.get('token') || '');
  const [newPw, setNewPw] = useState('');
  const [newPw2, setNewPw2] = useState('');

  async function onLogin(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(username, password);
    } catch (err) {
      setError(
        err.code === 'account_locked'
          ? `Account locked until ${new Date(err.data.locked_until).toLocaleTimeString()}.`
          : err.message,
      );
    } finally {
      setBusy(false);
    }
  }

  async function onRequestReset(e) {
    e.preventDefault();
    setResetMsg(null);
    try {
      const r = await api('/auth/password-reset/request', { method: 'POST', body: { email } });
      setResetMsg({ ok: true, text: r.message });
    } catch (err) {
      setResetMsg({ ok: false, text: err.message });
    }
  }

  async function onConfirmReset(e) {
    e.preventDefault();
    if (newPw !== newPw2) {
      setResetMsg({ ok: false, text: 'Passwords do not match.' });
      return;
    }
    try {
      await api('/auth/password-reset/confirm', {
        method: 'POST', body: { token, new_password: newPw },
      });
      setResetMsg({ ok: true, text: 'Password updated — log in with the new one.' });
      setToken(''); setNewPw(''); setNewPw2('');
    } catch (err) {
      setResetMsg({ ok: false, text: err.message });
    }
  }

  return (
    <div className="login-wrap">
      <div className="card login-card">
        <div className="brand">⚡ SMILE-<span>IoT</span></div>
        <form onSubmit={onLogin}>
          <label htmlFor="u">Username</label>
          <input id="u" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
          <label htmlFor="p">Password</label>
          <input id="p" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          {error && <div className="msg error">{error}</div>}
          <div style={{ marginTop: '0.9rem' }}>
            <button className="primary" style={{ width: '100%' }} disabled={busy}>
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </div>
        </form>

        <div className="hairline-top">
          <button
            style={{ border: 'none', background: 'none', padding: 0 }}
            onClick={() => setShowReset(!showReset)}
          >
            <span className="subtle">Forgot password?</span>
          </button>

          {showReset && (
            <>
              <form onSubmit={onRequestReset}>
                <label htmlFor="e">Email</label>
                <div className="row">
                  <input id="e" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
                  <button>Send link</button>
                </div>
              </form>
              <form onSubmit={onConfirmReset}>
                <label htmlFor="t">Reset token (from the email)</label>
                <input id="t" value={token} onChange={(e) => setToken(e.target.value)} />
                <label htmlFor="n1">New password</label>
                <input id="n1" type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} />
                <label htmlFor="n2">Confirm new password</label>
                <input id="n2" type="password" value={newPw2} onChange={(e) => setNewPw2(e.target.value)} />
                <div style={{ marginTop: '0.6rem' }}>
                  <button disabled={!token || !newPw}>Reset password</button>
                </div>
              </form>
            </>
          )}
          {resetMsg && <div className={`msg ${resetMsg.ok ? 'ok' : 'error'}`}>{resetMsg.text}</div>}
        </div>
      </div>
    </div>
  );
}
