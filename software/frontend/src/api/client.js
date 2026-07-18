// Single fetch wrapper: same-origin /api (Vite proxies to Flask in dev),
// JWT header injection, uniform error objects, 401 → token wipe.
const TOKEN_KEY = 'smile_token';
const USER_KEY = 'smile_user';

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const getStoredUser = () => {
  try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch { return null; }
};
export function storeSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}
export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export class ApiError extends Error {
  constructor(status, code, message, data) {
    super(message || code || `HTTP ${status}`);
    this.status = status;
    this.code = code;
    this.data = data;
  }
}

let onUnauthorized = () => {};
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn; };

export async function api(path, { method = 'GET', body } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  const res = await fetch(`/api${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);

  if (res.status === 401) {
    clearSession();
    onUnauthorized();
    throw new ApiError(401, data?.error, data?.message, data);
  }
  if (!res.ok) throw new ApiError(res.status, data?.error, data?.message, data);
  return data;
}
