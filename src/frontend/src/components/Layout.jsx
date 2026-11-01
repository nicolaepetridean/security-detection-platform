import { NavLink } from "react-router-dom";
import { useAuth } from "../auth";
import ActiveDetectionOverlay from "./ActiveDetectionOverlay";

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">🛡️ Detection Platform</div>
        <nav>
          <NavLink to="/" end>
            Queue
          </NavLink>
          <NavLink to="/detections">Detections</NavLink>
          <NavLink to="/customers">Customers</NavLink>
          <NavLink to="/signatures">Signatures</NavLink>
        </nav>
        <div className="user">
          <span className="role-badge">{user.role}</span>
          <span>{user.username}</span>
          <button className="link" onClick={logout}>
            Logout
          </button>
        </div>
      </header>
      <main className="content">{children}</main>
      <ActiveDetectionOverlay />
    </div>
  );
}
