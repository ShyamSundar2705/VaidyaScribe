import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  token:         string | null;
  doctorId:      string | null;
  fullName:      string | null;
  email:         string | null;
  specialisation: string | null;
  setAuth: (token: string, doctorId: string, fullName: string, email: string, specialisation?: string | null) => void;
  clearAuth: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token:          null,
      doctorId:       null,
      fullName:       null,
      email:          null,
      specialisation: null,
      setAuth: (token, doctorId, fullName, email, specialisation = null) =>
        set({ token, doctorId, fullName, email, specialisation }),
      clearAuth: () =>
        set({ token: null, doctorId: null, fullName: null, email: null, specialisation: null }),
      isAuthenticated: () => !!get().token,
    }),
    { name: "vaidyascribe-auth" }   // persisted to localStorage
  )
);
