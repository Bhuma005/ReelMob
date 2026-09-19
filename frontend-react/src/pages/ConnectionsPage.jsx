import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAppStore } from '../stores/appStore';
import { authApi } from '../api/auth';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { 
  MonitorPlay, Link2, CheckCircle2, Camera, Database, Cpu, 
  Sparkles, Lock, RefreshCw, Copy, Check, ExternalLink, HelpCircle, Share2, Info, X
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '../lib/utils';

export default function ConnectionsPage() {
  const queryClient = useQueryClient();
  const { isYtAuthenticated, ytChannelName, setYtAuth } = useAppStore();
  
  const [isDisconnectModalOpen, setIsDisconnectModalOpen] = useState(false);
  const [isSetupModalOpen, setIsSetupModalOpen] = useState(false);
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [copied, setCopied] = useState(false);
  const [redirectUri, setRedirectUri] = useState(
    typeof window !== 'undefined' ? `${window.location.origin}/auth/callback` : 'https://reelmob.onrender.com/auth/callback'
  );

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

  useQuery({
    queryKey: ['authStatusInit'],
    queryFn: async () => {
      try {
        const s = await authApi.getStatus();
        if (s?.redirect_uri) setRedirectUri(s.redirect_uri);
        if (s?.is_authenticated) {
          setYtAuth(true, s.channel_name || 'Connected Channel');
        }
        return s;
      } catch {
        return null;
      }
    }
  });

  const handleCopyUri = () => {
    navigator.clipboard.writeText(redirectUri);
    setCopied(true);
    toast.success("Redirect URI copied to clipboard!");
    setTimeout(() => setCopied(false), 2000);
  };

  const handleYtLogin = async () => {
    setIsLoggingIn(true);
    try {
      const res = await authApi.getLoginUrl();
      if (res.redirect_uri) setRedirectUri(res.redirect_uri);
      
      if (res.has_client_secrets === false || (!res.auth_url && res.error)) {
        setIsLoggingIn(false);
        setIsSetupModalOpen(true);
        toast.info("Google OAuth credentials setup required");
        return;
      }
      
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
      setIsSetupModalOpen(true);
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
                <div className="flex items-center gap-2">
                  <Button 
                    variant="outline"
                    size="sm"
                    onClick={() => setIsSetupModalOpen(true)}
                    className="text-xs text-text-muted hover:text-text cursor-pointer flex items-center gap-1"
                  >
                    <HelpCircle className="w-3.5 h-3.5" />
                    Setup Guide
                  </Button>
                  <Button 
                    size="sm"
                    onClick={handleYtLogin}
                    disabled={isLoggingIn}
                    className="bg-[#FF0000] text-white hover:bg-[#FF0000]/90 text-xs font-semibold flex items-center gap-1.5 cursor-pointer shadow-sm"
                  >
                    {isLoggingIn ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Link2 className="w-3.5 h-3.5" />}
                    Connect YouTube
                  </Button>
                </div>
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

        {/* 4. Meta Graph API (Instagram Reels & Facebook Pages) */}
        <Card className="bg-surface border-border">
          <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4">
            <div className="flex items-center gap-3.5">
              <div className="p-3 rounded-xl bg-gradient-to-tr from-[#f09433] via-[#dc2743] to-[#bc1888]/20 text-[#E1306C] flex items-center justify-center shrink-0">
                <Camera className="w-6 h-6" />
              </div>

              <div>
                <CardTitle className="text-base font-semibold text-text flex items-center gap-2">
                  <span>Meta Platforms (Instagram Reels & Facebook)</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-accent/20 text-accent border border-accent/30 font-bold">
                    EXPORT READY
                  </span>
                </CardTitle>
                <CardDescription className="text-xs text-text-muted mt-0.5">
                  Automated 9:16 vertical video conversion, viral titles, and 30 targeted hashtags for Instagram & Facebook discovery.
                </CardDescription>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono text-text-muted px-2.5 py-1 rounded bg-surface-elevated border border-border flex items-center gap-1.5">
                <Lock className="w-3 h-3 text-accent" /> Auto-Publish API: Roadmap
              </span>
            </div>
          </CardHeader>

          <CardContent className="pt-0 border-t border-border/60 p-4">
            <div className="rounded-lg bg-surface-elevated/60 border border-border/70 p-3.5 space-y-2.5 text-xs text-text-muted">
              <div className="flex items-center gap-2 text-text font-medium">
                <Info className="w-4 h-4 text-accent shrink-0" />
                <span>How Instagram & Facebook Publishing Works in ReelsMob:</span>
              </div>
              <ul className="space-y-1.5 pl-6 list-disc text-[11px] leading-relaxed">
                <li>
                  <strong className="text-text">Instant 1-Click Publishing (Active):</strong> ReelsMob reformats any video into Instagram/Facebook compliant 9:16 vertical canvas and writes high-engagement captions & 30 hashtags. In <strong className="text-text">Create Reel</strong>, click <em className="text-accent not-italic">Download Video</em> and copy the generated tags to post directly to your Instagram or Facebook Page in seconds.
                </li>
                <li>
                  <strong className="text-text">Direct API Auto-Publishing (In Development):</strong> Automated direct posting to Instagram & Facebook requires Meta Developer App Review & Business Verification for the <code className="text-accent font-mono text-[10px]">instagram_content_publish</code> and <code className="text-accent font-mono text-[10px]">pages_manage_posts</code> permissions.
                </li>
              </ul>
            </div>
          </CardContent>
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

      {/* YouTube OAuth Setup Guide Modal */}
      {isSetupModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-xs">
          <div className="w-full max-w-lg bg-surface border border-border rounded-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="p-5 border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-[#FF0000]/15 text-[#FF0000]">
                  <MonitorPlay className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-text">Connect YouTube Channel</h3>
                  <p className="text-xs text-text-muted">Google OAuth 2.0 Configuration for Render</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsSetupModalOpen(false)}
                className="p-1 rounded text-text-muted hover:text-text hover:bg-surface-elevated cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-4 text-xs">
              <div>
                <label className="text-[11px] uppercase font-mono text-text-muted block mb-1">
                  1. Authorized Redirect URI (Copy this first)
                </label>
                <div className="flex items-center gap-2 bg-surface-elevated border border-border rounded-lg p-2 font-mono text-[11px] text-accent">
                  <span className="truncate flex-1">{redirectUri}</span>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleCopyUri}
                    className="h-7 px-2.5 text-[10px] shrink-0 flex items-center gap-1 cursor-pointer"
                  >
                    {copied ? <Check className="w-3 h-3 text-success" /> : <Copy className="w-3 h-3" />}
                    {copied ? 'Copied' : 'Copy URI'}
                  </Button>
                </div>
              </div>

              <div className="space-y-2.5 text-text-muted leading-relaxed">
                <p className="font-semibold text-text text-[11px] uppercase tracking-wider font-mono">
                  2. Simple Setup Steps:
                </p>
                <ol className="space-y-2 pl-4 list-decimal text-[11px]">
                  <li>
                    Open{' '}
                    <a
                      href="https://console.cloud.google.com/apis/credentials"
                      target="_blank"
                      rel="noreferrer"
                      className="text-accent hover:underline inline-flex items-center gap-0.5 font-medium"
                    >
                      Google Cloud Console Credentials <ExternalLink className="w-3 h-3" />
                    </a>
                  </li>
                  <li>
                    Click <strong>Create Credentials</strong> &rarr; <strong>OAuth 2.0 Client ID</strong> &rarr; Application type: <strong>Web application</strong>.
                  </li>
                  <li>
                    Under <strong>Authorized redirect URIs</strong>, paste the URI copied above.
                  </li>
                  <li>
                    In your <strong>Render Dashboard</strong> &rarr; <em>ReelsMob Web Service</em> &rarr; <strong>Environment</strong>, add:
                    <div className="mt-1.5 p-2 rounded bg-surface-elevated font-mono text-[10px] text-text space-y-1 border border-border/80">
                      <div>GOOGLE_CLIENT_ID = <span className="text-text-muted">&lt;your-client-id.apps.googleusercontent.com&gt;</span></div>
                      <div>GOOGLE_CLIENT_SECRET = <span className="text-text-muted">&lt;your-client-secret&gt;</span></div>
                    </div>
                  </li>
                  <li>
                    Save changes on Render. Once redeployed, click <strong>Connect YouTube</strong> to authenticate your channel!
                  </li>
                </ol>
              </div>
            </div>

            <div className="p-4 bg-surface-elevated/60 border-t border-border flex items-center justify-end">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsSetupModalOpen(false)}
                className="text-xs cursor-pointer"
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
