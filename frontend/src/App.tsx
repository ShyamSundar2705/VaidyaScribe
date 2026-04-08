import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import { Layout } from "./components/Layout";
import { ConsultationRoom } from "./pages/ConsultationRoom";
import { NoteEditor } from "./pages/NoteEditor";
import { BurnoutDashboard } from "./pages/BurnoutDashboard";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<ConsultationRoom />} />
            <Route path="/review/:sessionId" element={<NoteEditor />} />
            <Route path="/wellness" element={<BurnoutDashboard />} />
          </Routes>
        </Layout>
      </BrowserRouter>
      <Toaster position="top-right" />
    </QueryClientProvider>
  );
}
