import { Navigate, NavLink, Outlet, Route, Routes } from 'react-router-dom';
import { useAuth } from './auth/AuthContext.jsx';
import Admin from './pages/Admin.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Login from './pages/Login.jsx';
import Profile from './pages/Profile.jsx';

function Layout() {
  const { user, logout } = useAuth();
  return (
    <>
      <header className="topbar">
        <div className="brand">⚡ SMILE-<span>IoT</span></div>
        <nav>
          <NavLink to="/" end>Dashboard</NavLink>
          <NavLink to="/profile">Profile</NavLink>
          {user.role === 'admin' && <NavLink to="/admin">Admin</NavLink>}
        </nav>
        <span className="who">{user.username} · {user.role}</span>
        <button onClick={logout}>Logout</button>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </>
  );
}

export default function App() {
  const { user, checking } = useAuth();
  if (checking) return null; // token being validated on first paint

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route element={user ? <Layout /> : <Navigate to="/login" replace />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/profile" element={<Profile />} />
        <Route
          path="/admin"
          element={user?.role === 'admin' ? <Admin /> : <Navigate to="/" replace />}
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
