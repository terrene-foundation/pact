import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export interface AuthUser {
  uid: string;
  email: string | null;
  displayName: string | null;
  photoURL: string | null;
  role?: string;
}

interface AuthState {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoaded: boolean;
  loading: boolean;

  setUser: (user: AuthUser | null) => void;
  setToken: (token: string | null) => void;
  setAuthenticated: (auth: boolean) => void;
  setLoaded: (loaded: boolean) => void;
  setLoading: (loading: boolean) => void;
  login: (user: AuthUser, token: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoaded: false,
      loading: false,

      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setToken: (token) => set({ token }),
      setAuthenticated: (isAuthenticated) => set({ isAuthenticated }),
      setLoaded: (isLoaded) => set({ isLoaded }),
      setLoading: (loading) => set({ loading }),
      login: (user, token) =>
        set({ user, token, isAuthenticated: true, loading: false }),
      logout: () => {
        if (typeof window !== "undefined") {
          localStorage.removeItem("PACT_API_TOKEN");
        }
        set({ user: null, token: null, isAuthenticated: false });
      },
    }),
    {
      name: "pact-auth",
      storage: createJSONStorage(() => {
        if (typeof window === "undefined") {
          return {
            getItem: () => null,
            setItem: () => {},
            removeItem: () => {},
          };
        }
        return localStorage;
      }),
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    },
  ),
);
