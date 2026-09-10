import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect, lazy, Suspense } from 'react';
import { useAppStore } from './stores/appStore';
import { authApi } from './api/auth';

import AppLayout from './components/layout/AppLayout';

import DashboardPage from './pages/DashboardPage';
import CreateReelPage from './pages/CreateReelPage';
import LibraryPage from './pages/LibraryPage';
import SchedulerPage from './pages/SchedulerPage';
import ConnectionsPage from './pages/ConnectionsPage';
import LogsPage from './pages/LogsPage';
import SettingsPage from './pages/SettingsPage';
import AnalyticsPage from './pages/AnalyticsPage';
import { ErrorBoundary } from './components/ErrorBoundary';

const ComponentGallery = lazy(() => import('./pages/dev/ComponentGallery'));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: false,
    },
  },
});

function AppBootstrapper({ children }) {
  const { setOllamaStatus, setYtAuth } = useAppStore();

  useEffect(() => {
    // Check Auth Status
    authApi.getStatus()
      .then(status => {
        if (status.is_authenticated) {
          setYtAuth(true, status.channel_name || "Ready to Post");
        } else {
          setYtAuth(false, "");
        }
      })
      .catch(() => setYtAuth(false, ""));

    // Check Ollama
    fetch('http://127.0.0.1:11434/api/tags')
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(data => {
        if (data.models && data.models.length > 0) {
          setOllamaStatus(`✅ ${data.models[0].name}`);
        } else {
          setOllamaStatus('⚠️ No Models');
        }
      })
      .catch(() => setOllamaStatus('🔴 Offline'));
  }, [setOllamaStatus, setYtAuth]);

  return children;
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AppBootstrapper>
            <Routes>
              <Route path="/" element={<AppLayout />}>
                <Route index element={<DashboardPage />} />
                <Route path="create" element={<CreateReelPage />} />
                <Route path="library" element={<LibraryPage />} />
                <Route path="scheduler" element={<SchedulerPage />} />
                <Route path="analytics" element={<AnalyticsPage />} />
                <Route path="connections" element={<ConnectionsPage />} />
                <Route path="logs" element={<LogsPage />} />
                <Route path="settings" element={<SettingsPage />} />
                
                {/* Dev component gallery route */}
                <Route 
                  path="dev/components" 
                  element={
                    <Suspense fallback={<div className="p-8 text-center text-xs text-text-muted">Loading Dev Gallery...</div>}>
                      <ComponentGallery />
                    </Suspense>
                  } 
                />

                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </AppBootstrapper>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
