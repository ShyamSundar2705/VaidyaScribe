import { create } from "zustand";
import type { PipelineResult } from "../hooks/useAudioCapture";

interface AppStore {
  doctorId: string;
  setDoctorId: (id: string) => void;
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
  consentGiven: boolean;
  setConsentGiven: (v: boolean) => void;
  lastResult: PipelineResult | null;
  setLastResult: (r: PipelineResult | null) => void;
  history: PipelineResult[];
  addToHistory: (r: PipelineResult) => void;
}

export const useAppStore = create<AppStore>((set) => ({
  doctorId: "DR-DEMO-001",
  setDoctorId: (id) => set({ doctorId: id }),
  sessionId: null,
  setSessionId: (id) => set({ sessionId: id }),
  consentGiven: false,
  setConsentGiven: (v) => set({ consentGiven: v }),
  lastResult: null,
  setLastResult: (r) => set({ lastResult: r }),
  history: [],
  addToHistory: (r) => set((s) => ({ history: [r, ...s.history].slice(0, 20) })),
}));
