import { BrowserRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ToastProvider, useToasts } from "./context/ToastContext";
import { ToastStack } from "./components/ToastStack";
import { Layout } from "./components/Layout";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { DeviceDetail } from "./pages/DeviceDetail";
import { Settings } from "./pages/Settings";
import { useLiveUpdates } from "./hooks/useWebSocket";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5_000,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AuthGate />
      </AuthProvider>
    </QueryClientProvider>
  );
}

function AuthGate() {
  const { state } = useAuth();

  if (state.status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-ink-faint">Memuat…</div>
    );
  }

  if (state.status === "needs_setup" || state.status === "logged_out") {
    return <Login />;
  }

  return (
    <ToastProvider>
      <AuthenticatedApp />
    </ToastProvider>
  );
}

function AuthenticatedApp() {
  const { push } = useToasts();
  useLiveUpdates(push);

  return (
    <>
      <ToastStack />
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/devices/:id" element={<DeviceDetail />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Dashboard />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </>
  );
}
