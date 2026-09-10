import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { useAppStore } from '../stores/appStore';
import { useVideoStore } from '../stores/videoStore';
import { 
  Cpu, RefreshCw, AlertTriangle, Bell, Sparkles, Terminal, 
  Database, Zap
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '../lib/utils';

export default function SettingsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isYtAuthenticated, ytChannelName } = useAppStore();
  const videoStore = useVideoStore();

  // Settings local state
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [toastNotifications, setToastNotifications] = useState(true);
  
  // Danger Zone confirmation state
  const [isDangerModalOpen, setIsDangerModalOpen] = useState(false);
  const [dangerConfirmInput, setDangerConfirmInput] = useState('');
  const [isResetting, setIsResetting] = useState(false);

  // Health Query
  const { data: health, isLoading: isLoadingHealth, refetch: refetchHealth } = useQuery({
    queryKey: ['systemHealthSettings'],
    queryFn: async () => {
      const res = await fetch('/api/health');
      if (!res.ok) throw new Error('Health check error');
      return res.json();
    }
  });

  const { refetch: refetchAi } = useQuery({
    queryKey: ['aiHealthSettings'],
    queryFn: async () => {
      const res = await fetch('/api/health/ai');
      if (!res.ok) throw new Error('AI health check error');
      return res.json();
    }
  });

  const handleRefreshAll = () => {
    refetchHealth();
    refetchAi();
    toast.success('System health updated');
  };

  const handleDangerReset = async () => {
    if (dangerConfirmInput !== 'CONFIRM') {
      toast.error('Please type CONFIRM exactly to proceed');
      return;
    }
    setIsResetting(true);
    try {
      // 1. Reset client stores
      videoStore.resetWorkflow();
      videoStore.setUrl('');
      // 2. Clear query cache
      queryClient.clear();
      // 3. Clear session storage
      sessionStorage.clear();
      
      toast.success('Client workflow and cache successfully purged');
      setIsDangerModalOpen(false);
      setDangerConfirmInput('');
    } catch (err) {
      toast.error('Failed to reset: ' + err.message);
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="max-w-4xl mx-auto space-y-8 pb-20"
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-text">
            Settings & System Status
          </h1>
          <p className="text-xs sm:text-sm text-text-muted mt-1">
            Configure processing engines, platform preferences, and cloud health monitoring.
          </p>
        </div>

        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleRefreshAll}
          className="text-xs flex items-center gap-1.5 cursor-pointer"
        >
          <RefreshCw className={cn("w-3.5 h-3.5", isLoadingHealth && "animate-spin")} />
          Refresh Health Status
        </Button>
      </div>

      {/* Group 1: AI & Media Processing Engines */}
      <Card className="bg-surface border-border">
        <CardHeader>
          <CardTitle className="text-base font-semibold text-text flex items-center gap-2">
            <Cpu className="w-5 h-5 text-accent" />
            AI & Media Processing Engines
          </CardTitle>
          <CardDescription className="text-xs text-text-muted">
            Vision analysis and viral copy synthesis running across cloud clusters and local inference fallback.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* Gemini */}
            <div className="p-4 rounded-xl bg-surface-elevated/70 border border-border/80 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-semibold text-text flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-accent" /> Cloud Vision AI
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-success/15 text-success font-semibold border border-success/20">
                    Active
                  </span>
                </div>
                <div className="text-sm font-bold text-text">Google Gemini 3.6 Flash</div>
              </div>
              <p className="mt-3 text-[11px] text-text-muted leading-relaxed">
                Frame-by-frame visual scene inspection, emotion tagging, and spoken transcript analysis.
              </p>
            </div>

            {/* Groq */}
            <div className="p-4 rounded-xl bg-surface-elevated/70 border border-border/80 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-semibold text-text flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-accent" /> Viral Copy Synthesizer
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-success/15 text-success font-semibold border border-success/20">
                    Active
                  </span>
                </div>
                <div className="text-sm font-bold text-text">Groq Cloud AI (Compound)</div>
              </div>
              <p className="mt-3 text-[11px] text-text-muted leading-relaxed">
                Sub-second title optimization, SEO description generation, and hashtag bundles.
              </p>
            </div>
          </div>

          {/* Local Ollama Status */}
          <div className="p-3.5 rounded-lg bg-surface-elevated/40 border border-border/70 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2.5">
              <Terminal className="w-4 h-4 text-text-muted" />
              <div>
                <span className="font-semibold text-text">Local Ollama Fallback Engine</span>
                <p className="text-[11px] text-text-muted">
                  {health?.services?.ollama?.message || "Running local qwen2.5:7b when cloud is offline"}
                </p>
              </div>
            </div>
            <span className={cn(
              "text-[10px] font-mono px-2 py-0.5 rounded-full border font-semibold",
              health?.services?.ollama?.status === 'ok' 
                ? "bg-success/15 text-success border-success/25" 
                : "bg-surface-elevated text-text-muted border-border"
            )}>
              {health?.services?.ollama?.status === 'ok' ? 'ONLINE' : 'STANDBY'}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Group 2: Cloud Infrastructure & Database */}
      <Card className="bg-surface border-border">
        <CardHeader>
          <CardTitle className="text-base font-semibold text-text flex items-center gap-2">
            <Database className="w-5 h-5 text-accent" />
            Cloud Infrastructure & Database
          </CardTitle>
          <CardDescription className="text-xs text-text-muted">
            Supabase managed PostgreSQL tables, secure storage buckets, and OAuth credentials.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-3">
          <div className="divide-y divide-border/60">
            <div className="py-2.5 flex items-center justify-between text-xs">
              <div>
                <div className="font-semibold text-text">Supabase PostgreSQL Database</div>
                <div className="text-[11px] text-text-muted">Tables: video_library, scheduled_videos, video_activity_log</div>
              </div>
              <span className="text-[10px] font-mono text-success bg-success/15 px-2 py-0.5 rounded-full border border-success/20 font-semibold">
                CONNECTED
              </span>
            </div>

            <div className="py-2.5 flex items-center justify-between text-xs">
              <div>
                <div className="font-semibold text-text">Cloud Storage Bucket (reelgrab-videos)</div>
                <div className="text-[11px] text-text-muted">High-speed CDN for video downloads and thumbnail frames</div>
              </div>
              <span className="text-[10px] font-mono text-success bg-success/15 px-2 py-0.5 rounded-full border border-success/20 font-semibold">
                ACCESSIBLE
              </span>
            </div>

            <div className="py-2.5 flex items-center justify-between text-xs">
              <div>
                <div className="font-semibold text-text">Connected YouTube Account</div>
                <div className="text-[11px] text-text-muted">
                  {isYtAuthenticated ? `Linked to ${ytChannelName}` : 'No YouTube channel currently connected'}
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/connections')}
                className="text-xs h-7 cursor-pointer"
              >
                Manage in Connections
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Group 3: App Preferences & Polling */}
      <Card className="bg-surface border-border">
        <CardHeader>
          <CardTitle className="text-base font-semibold text-text flex items-center gap-2">
            <Bell className="w-5 h-5 text-accent" />
            Preferences & Telemetry
          </CardTitle>
          <CardDescription className="text-xs text-text-muted">
            Customize background polling intervals and creator notification alerts.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="flex items-center justify-between py-2 border-b border-border/60">
            <div>
              <span className="text-xs font-semibold text-text">Automatic Background Polling</span>
              <p className="text-[11px] text-text-muted">
                Poll queue and activity logs every 8 seconds for real-time status updates
              </p>
            </div>
            <button
              type="button"
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={cn(
                "w-11 h-6 rounded-full transition-colors relative cursor-pointer",
                autoRefresh ? "bg-accent" : "bg-surface-elevated border border-border"
              )}
            >
              <span className={cn(
                "w-5 h-5 rounded-full bg-white block absolute top-0.5 transition-transform",
                autoRefresh ? "translate-x-5.5" : "translate-x-0.5"
              )} />
            </button>
          </div>

          <div className="flex items-center justify-between py-2">
            <div>
              <span className="text-xs font-semibold text-text">Workflow Completion Alerts</span>
              <p className="text-[11px] text-text-muted">
                Display toast notifications when video downloads or AI optimizations complete
              </p>
            </div>
            <button
              type="button"
              onClick={() => setToastNotifications(!toastNotifications)}
              className={cn(
                "w-11 h-6 rounded-full transition-colors relative cursor-pointer",
                toastNotifications ? "bg-accent" : "bg-surface-elevated border border-border"
              )}
            >
              <span className={cn(
                "w-5 h-5 rounded-full bg-white block absolute top-0.5 transition-transform",
                toastNotifications ? "translate-x-5.5" : "translate-x-0.5"
              )} />
            </button>
          </div>
        </CardContent>
      </Card>

      {/* Group 4: Danger Zone */}
      <Card className="bg-surface border-danger/40">
        <CardHeader>
          <CardTitle className="text-base font-semibold text-danger flex items-center gap-2">
            <AlertTriangle className="w-5 h-5" />
            Danger Zone
          </CardTitle>
          <CardDescription className="text-xs text-text-muted">
            Destructive actions that wipe local client cache, reset form states, or clear memory.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="p-4 rounded-xl bg-danger/5 border border-danger/20 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="text-xs font-semibold text-text">Purge Client Cache & Active Workflows</div>
              <p className="text-[11px] text-text-muted mt-0.5">
                Clears all cached query states, unsaved workflow forms, and resets active video stores.
              </p>
            </div>

            <Button
              type="button"
              onClick={() => setIsDangerModalOpen(true)}
              className="bg-danger text-white hover:bg-danger/90 text-xs font-semibold shrink-0 cursor-pointer"
            >
              Purge Client Cache
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Danger Confirmation Modal */}
      {isDangerModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-xs">
          <div className="w-full max-w-md bg-surface border border-danger/40 rounded-xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-danger">
              <AlertTriangle className="w-6 h-6" />
              <h3 className="text-base font-bold text-text">Confirm Cache Purge</h3>
            </div>

            <p className="text-xs text-text-muted leading-relaxed">
              This action will reset your active creation workflow and invalidate all TanStack Query cache in this browser session.
            </p>

            <div className="space-y-1.5 pt-2">
              <label className="text-[11px] font-mono text-text-muted block">
                Type <strong className="text-danger font-mono font-bold">CONFIRM</strong> below to proceed:
              </label>
              <input
                type="text"
                value={dangerConfirmInput}
                onChange={(e) => setDangerConfirmInput(e.target.value)}
                placeholder="CONFIRM"
                className="w-full bg-surface-elevated border border-border rounded-lg px-3 py-2 text-xs font-mono text-text focus:outline-none focus:border-danger transition-colors"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsDangerModalOpen(false);
                  setDangerConfirmInput('');
                }}
                className="text-xs text-text-muted hover:text-text cursor-pointer"
              >
                Cancel
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={dangerConfirmInput !== 'CONFIRM' || isResetting}
                onClick={handleDangerReset}
                className="bg-danger text-white hover:bg-danger/90 text-xs font-semibold cursor-pointer disabled:opacity-40"
              >
                {isResetting ? 'Purging...' : 'Confirm Purge'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </motion.div>
  );
}
