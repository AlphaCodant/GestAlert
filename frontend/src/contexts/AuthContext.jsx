import React, { createContext, useContext, useEffect, useState } from "react";
import { api, setAuthToken, formatApiErrorDetail } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null = checking, false = guest, object = authed
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const { data } = await api.get("/auth/me");
        if (mounted) setUser(data);
      } catch (e) {
        if (mounted) setUser(false);
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  async function login(email, password) {
    try {
      const { data } = await api.post("/auth/login", { email, password });
      if (data.access_token) setAuthToken(data.access_token);
      setUser(data.user);
      return { success: true };
    } catch (e) {
      return { success: false, error: formatApiErrorDetail(e.response?.data?.detail) || e.message };
    }
  }

  async function logout() {
    try { await api.post("/auth/logout"); } catch (_) {}
    setAuthToken(null);
    setUser(false);
  }

  return (
    <AuthContext.Provider value={{ user, setUser, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
