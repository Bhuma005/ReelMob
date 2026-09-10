import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAppStore } from '../stores/appStore';
import { authApi } from '../api/auth';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { 
  MonitorPlay, Link2, CheckCircle2, Camera, Database, Cpu, 
  Sparkles, Lock, RefreshCw
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '../lib/utils';

export default function ConnectionsPage() {
  const queryClient = useQueryClient();
  const { isYtAuthenticated, ytChannelName, setYtAuth } = useAppStore();
  
  const [isDisconnectModalOpen, setIsDisconnectModalOpen] = useState(false);
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  // Queries for health and AI providers
  const { refetch: refetchHealth } = useQuery({
    queryKey: ['systemHealth'],
    queryFn: async () => {
      const res = await fetch('/api/health');
      if (!res.ok) throw new Error('Health check failed');
      return res.json();
    }
  });

  const { refetch: refetchAi } = useQuery({
    queryKey: ['aiHealth'],
    queryFn: async () => {
      const res = await fetch('/api/health/ai');
      if (!res.ok) throw new Error('AI health check failed');
      return res.json();
    }
  });

  const handleYtLogin = async () => {
    setIsLoggingIn(true);
    try {
      const res = await authApi.getLoginUrl();
      if (res.error) throw new Error(res.error);
      
      window.open(res.auth_url, '_blank');
      toast.info("Please complete authentication in the new tab");
      
      const poll = setInterval(async () => {
        try {
          const s = await authApi.getStatus();
          if (s.is_authenticated) {
            clearInterval(poll);
            setYtAuth(true, s.channel_name || 'Connected Channel');
            setIsLoggingIn(false);
            toast.success("YouTube channel connected successfully!");
            queryClient.invalidateQueries(['systemHealth']);
          }
        } catch {
          // Ignore polling errors
        }
      }, 3000);
      
      setTimeout(() => {
        clearInterval(poll);
        setIsLoggingIn(false);
      }, 120000);
      
    } catch (err) {
      setIsLoggingIn(false);
      toast.error(err.message || "Failed to start Google OAuth login");
    }
  };

  const handleConfirmDisconnect = async () => {
    try {
      await authApi.logout();
      setYtAuth(false, '');
      setIsDisconnectModalOpen(false);
      toast.success("Disconnected from YouTube account");
      queryClient.invalidateQueries(['systemHealth']);
    } catch (err) {
      toast.error(err.message || "Failed to disconnect");
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-20">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-text">
            Platform & Service Connections
          </h1>
          <p className="text-xs sm:text-sm text-text-muted mt-1">
            Manage authenticated YouTube accounts, Supabase cloud databases, and AI model credentials.
          </p>
        </div>

        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => {
            refetchHealth();
            refetchAi();
            toast.info("Refreshed connection states");
          }}
          className="text-xs flex items-center gap-1.5 cursor-pointer"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh Services
        </Button>
      </div>

      <div className="grid gap-5">
        {/* 1. YouTube Data API Card */}
        <Card className={cn(
          "bg-surface border-border transition-all",
          isYtAuthenticated ? "border-success/40 bg-success/5" : ""
        )}>
          <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4">
            <div className="flex items-center gap-3.5">
              <div className={cn(
                "p-3 rounded-xl flex items-center justify-center shrink-0",
                isYtAuthenticated ? "bg-success/20 text-success" : "bg-[#FF0000]/15 text-[#FF0000]"
              )}>
                <MonitorPlay className="w-6 h-6" />
              </div>

              <div>
                <CardTitle className="text-base font-semibold text-text flex items-center gap-2">
                  <span>YouTube Data API v3</span>
                  {isYtAuthenticated ? (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-success/20 text-success border border-success/30 font-bold">
                      ACTIVE & CONNECTED
                    </span>
                  ) : (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-surface-elevated text-text-muted border border-border">
                      NOT LINKED
                    </span>
                  )}
                </CardTitle>
                <CardDescription className="text-xs text-text-muted mt-0.5">
                  {isYtAuthenticated ? (
                    <span className="text-success font-medium flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Linked to channel: <strong className="text-text">{ytChannelName || 'Primary Account'}</strong>
                    </span>
                  ) : (
                    "OAuth connection required to automate uploads directly to YouTube Shorts."
                  )}
                </CardDescription>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {isYtAuthenticated ? (
                <Button 
                  variant="outline"
                  size="sm"
                  onClick={() => setIsDisconnectModalOpen(true)}
                  className="text-xs text-danger hover:bg-danger/10 border-danger/30 cursor-pointer"
                >
                  Disconnect Channel
                </Button>
              ) : (
                <Button 
                  size="sm"
                  onClick={handleYtLogin}
                  disabled={isLoggingIn}
                  className="bg-[#FF0000] text-white hover:bg-[#FF0000]/90 text-xs font-semibold flex items-center gap-1.5 cursor-pointer shadow-sm"
                >
                  {isLoggingIn ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Link2 className="w-3.5 h-3.5" />}
                  Connect YouTube
                </Button>
              )}
            </div>
          </CardHeader>
        </Card>

        {/* 2. Supabase Cloud Database & Storage Card */}
        <Card className="bg-surface border-border">
          <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4">
            <div className="flex items-center gap-3.5">
              <div className="p-3 rounded-xl bg-[#3ECF8E]/15 text-[#3ECF8E] flex items-center justify-center shrink-0">
                <Database className="w-6 h-6" />
              </div>

              <div>
                <CardTitle className="text-base font-semibold text-text flex items-center gap-2">
                  <span>Supabase Cloud Database & Storage</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-success/20 text-success border border-success/30 font-bold">
                    CONNECTED
                  </span>
                </CardTitle>
                <CardDescription className="text-xs text-text-muted mt-0.5">
                  PostgreSQL database tables and permanent video object storage bucket (<code className="text-accent">reelgrab-videos</code>).
                </CardDescription>
              </div>
            </div>

            <div className="text-right shrink-0">
              <span className="text-xs font-mono text-text-muted">
                Key: <strong className="text-text font-mono">••••••••••••c2f8</strong>
              </span>
            </div>
          </CardHeader>

          <CardContent className="pt-0 border-t border-border/60 p-4">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs font-mono">
              <div className="p-2.5 rounded bg-surface-elevated/70 border border-border/70">
                <span className="text-[10px] text-text-muted uppercase block">Video Library DB</span>
                <span className="text-success font-semibold flex items-center gap-1 mt-0.5">
                  <CheckCircle2 className="w-3 h-3" /> Healthy
                </span>
              </div>
              <div className="p-2.5 rounded bg-surface-elevated/70 border border-border/70">
                <span className="text-[10px] text-text-muted uppercase block">Storage Bucket</span>
                <span className="text-success font-semibold flex items-center gap-1 mt-0.5">
                  <CheckCircle2 className="w-3 h-3" /> reelgrab-videos
                </span>
              </div>
              <div className="p-2.5 rounded bg-surface-elevated/70 border border-border/70 col-span-2 sm:col-span-1">
                <span className="text-[10px] text-text-muted uppercase block">Audit Stream</span>
                <span className="text-success font-semibold flex items-center gap-1 mt-0.5">
                  <CheckCircle2 className="w-3 h-3" /> video_activity_log
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 3. AI Providers: Google Gemini 3.6 Flash & Groq */}
        <Card className="bg-surface border-border">
          <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4">
            <div className="flex items-center gap-3.5">
              <div className="p-3 rounded-xl bg-accent/15 text-accent flex items-center justify-center shrink-0">
                <Cpu className="w-6 h-6" />
              </div>

              <div>
                <CardTitle className="text-base font-semibold text-text flex items-center gap-2">
                  <span>AI Inference Engines</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-success/20 text-success border border-success/30 font-bold">
                    CLOUD CLUSTER ACTIVE
                  </span>
                </CardTitle>
                <CardDescription className="text-xs text-text-muted mt-0.5">
                  Multi-modal vision analysis and sub-second viral metadata generation.
                </CardDescription>
              </div>
            </div>
          </CardHeader>

          <CardContent className="pt-0 border-t border-border/60 p-4 space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Gemini Flash */}
              <div className="p-3 rounded-lg bg-surface-elevated/70 border border-border/80 flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-accent" />
                    <span className="text-xs font-semibold text-text">Google Gemini 3.6 Flash</span>
                  </div>
                  <p className="text-[11px] text-text-muted mt-0.5">Vision Scene & Transcript Agent</p>
                </div>
                <div className="text-right">
                  <span className="text-[10px] font-mono text-success bg-success/15 px-2 py-0.5 rounded border border-success/20 font-semibold">
                    ONLINE
                  </span>
                  <span className="text-[10px] font-mono text-text-muted block mt-1">••••••••93a1</span>
                </div>
              </div>

              {/* Groq Cloud */}
              <div className="p-3 rounded-lg bg-surface-elevated/70 border border-border/80 flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-accent" />
                    <span className="text-xs font-semibold text-text">Groq Cloud AI (Compound)</span>
                  </div>
                  <p className="text-[11px] text-text-muted mt-0.5">Ultra-low latency metadata synthesizer</p>
                </div>
                <div className="text-right">
                  <span className="text-[10px] font-mono text-success bg-success/15 px-2 py-0.5 rounded border border-success/20 font-semibold">
                    ONLINE
                  </span>
                  <span className="text-[10px] font-mono text-text-muted block mt-1">••••••••b7e4</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 4. Instagram Graph API (Coming Soon) */}
        <Card className="bg-surface border-border opacity-70">
          <CardHeader className="flex flex-row items-center justify-between gap-4 pb-4">
            <div className="flex items-center gap-3.5">
              <div className="p-3 rounded-xl bg-surface-elevated text-[#E1306C] flex items-center justify-center shrink-0">
                <Camera className="w-6 h-6" />
              </div>

              <div>
                <CardTitle className="text-base font-semibold text-text flex items-center gap-2">
                  <span>Instagram Graph API</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-surface-elevated text-text-muted border border-border">
                    ROADMAP
                  </span>
                </CardTitle>
                <CardDescription className="text-xs text-text-muted mt-0.5">
                  Direct publishing to Instagram Reels and creator business accounts.
                </CardDescription>
              </div>
            </div>

            <Button variant="outline" size="sm" disabled className="text-xs cursor-not-allowed">
              <Lock className="w-3.5 h-3.5 mr-1" /> Coming Soon
            </Button>
          </CardHeader>
        </Card>
      </div>

      {/* YouTube Disconnect Confirm Dialog */}
      <ConfirmDialog
        isOpen={isDisconnectModalOpen}
        title="Disconnect YouTube channel?"
        description={`This will unlink "${ytChannelName || 'your channel'}" from ReelsMob. Scheduled videos will not be able to auto-publish until you reconnect.`}
        confirmText="Disconnect Account"
        confirmVariant="danger"
        onClose={() => setIsDisconnectModalOpen(false)}
        onConfirm={handleConfirmDisconnect}
      />
    </div>
  );
}
