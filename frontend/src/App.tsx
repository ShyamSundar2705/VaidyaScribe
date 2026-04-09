import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { LoginPage }        from "./pages/LoginPage";
import { Dashboard }        from "./pages/Dashboard";
import { ConsultationRoom } from "./pages/ConsultationRoom";
import { NoteEditor }       from "./pages/NoteEditor";
import { PatientHistory }   from "./pages/PatientHistory";
import { BurnoutDashboard } from "./pages/BurnoutDashboard";
import { PrescriptionPad }  from "./pages/PrescriptionPad";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

const Protected = ({ children }: { children: React.ReactNode }) => (
  <ProtectedRoute><Layout>{children}</Layout></ProtectedRoute>
);

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login"              element={<LoginPage />} />
          <Route path="/"                   element={<Protected><Dashboard /></Protected>} />
          <Route path="/consult"            element={<Protected><ConsultationRoom /></Protected>} />
          <Route path="/review/:sessionId"  element={<Protected><NoteEditor /></Protected>} />
          <Route path="/patients"           element={<Protected><PatientHistory /></Protected>} />
          <Route path="/wellness"           element={<Protected><BurnoutDashboard /></Protected>} />
          <Route path="/prescription"       element={<Protected><PrescriptionPad /></Protected>} />
          <Route path="*"                   element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" />
    </QueryClientProvider>
  );
}
