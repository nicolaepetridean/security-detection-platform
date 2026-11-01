// Auth context: holds the current user, exposes login/logout.
// NOTE: role-based UI here is UX only. The backend enforces authorization on every
// endpoint, so hiding a button is a convenience, not a security boundary.
import { createContext, useContext, useEffect, useState } from "react";
import { api, setToken } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  async function login(username, password) {
    const { access_token } = await api.login(username, password);
    setToken(access_token);
    const me = await api.me();
    setUser(me);
  }

  function logout() {
    setToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

export const isAnalyst = (user) => user?.role === "analyst" || user?.role === "admin";
export const isAdmin = (user) => user?.role === "admin";
