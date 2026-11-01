// Shared "active detection" state so the persistent overlay and the pages that mutate
// it (claim / close) stay in sync. Only meaningful for analysts.
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";
import { isAnalyst, useAuth } from "./auth";

const ActiveContext = createContext(null);

export function ActiveProvider({ children }) {
  const { user } = useAuth();
  const [active, setActive] = useState(null);

  const refresh = useCallback(async () => {
    if (!isAnalyst(user)) {
      setActive(null);
      return;
    }
    try {
      setActive(await api.activeDetection());
    } catch {
      setActive(null);
    }
  }, [user]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <ActiveContext.Provider value={{ active, refresh }}>
      {children}
    </ActiveContext.Provider>
  );
}

export function useActive() {
  return useContext(ActiveContext);
}
