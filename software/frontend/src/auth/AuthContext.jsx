import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import {
  api, clearSession, getStoredUser, getToken, setUnauthorizedHandler, storeSession,
} from '../api/client.js';

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(getStoredUser);
  const [checking, setChecking] = useState(Boolean(getToken()));

  // Session expiry (or a deleted user) anywhere in the app → drop to login.
  useEffect(() => { setUnauthorizedHandler(() => setUser(null)); }, []);

  // Validate a stored token once on mount.
  useEffect(() => {
    if (!getToken()) return;
    api('/auth/me')
      .then((me) => setUser(me))
      .catch(() => setUser(null))
      .finally(() => setChecking(false));
  }, []);

  const value = useMemo(() => ({
    user,
    checking,
    async login(username, password) {
      const { access_token, user: u } = await api('/auth/login', {
        method: 'POST', body: { username, password },
      });
      storeSession(access_token, u);
      setUser(u);
    },
    logout() {
      clearSession();
      setUser(null);
    },
  }), [user, checking]);

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
