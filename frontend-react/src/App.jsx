import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect, lazy, Suspense } from 'react';
import { useAppStore } from './stores/appStore';
import { authApi } from './api/auth';
import { fetchApi } from './api/client';
import AppLayout from './components/layout/AppLayout';

import { ErrorBoundary } from './components/ErrorBoundary';

const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const CreateReelPage = lazy(() => import('./pages/CreateReelPage'));
const LibraryPage = lazy(() => import('./pages/LibraryPage'));
const SchedulerPage = lazy(() => import('./pages/SchedulerPage'));
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'));
const ConnectionsPage = lazy(() => import('./pages/ConnectionsPage'));
const LogsPage = lazy(() => import('./pages/LogsPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
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

    // Check Cloud AI Engine
    fetchApi('/api/health/ai')
      .then(data => {
        if (data && data.available) {
          setOllamaStatus('✅ Cloud AI');
        } else if (data && data.status === 'keys_missing') {
          setOllamaStatus('⚠️ Keys Missing');
        } else {
          setOllamaStatus('⚠️ Fallback Active');
        }
      })
      .catch(() => setOllamaStatus('🔴 AI Offline'));
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
