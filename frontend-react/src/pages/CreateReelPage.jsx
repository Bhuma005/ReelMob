import React, { useState, useEffect, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { motion } from 'framer-motion';
import { useVideoStore } from '../stores/videoStore';
import { useAppStore } from '../stores/appStore';
import { metadataApi } from '../api/metadata';
import { videosApi } from '../api/videos';
import { automationApi } from '../api/automation';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { toast } from 'sonner';
import { 
  Loader2, Download, Wand2, MonitorPlay, Check, Sparkles, 
  CheckCircle2, RotateCcw, XCircle, RefreshCw,
  Film, Copy, ShieldCheck
} from 'lucide-react';
import { cn } from '../lib/utils';

// Zod Schema for Video URL Validation
const urlSchema = z.object({
  url: z.string()
    .min(1, 'Please enter a video URL')
    .url('Please enter a valid URL (https://...)')
    .refine(
      (val) => /(instagram\.com|youtube\.com|youtu\.be)/i.test(val),
      'Must be a valid Instagram Reel or YouTube Shorts / Video link'
    ),
});

export default function CreateReelPage() {
  const store = useVideoStore();
  const appStore = useAppStore();
  
  const [isLoading, setIsLoading] = useState(false);
  const [isAutomating, setIsAutomating] = useState(false);
  const [automationResult, setAutomationResult] = useState(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [isAccepted, setIsAccepted] = useState(false);
  const [activeFormatId, setActiveFormatId] = useState(null);

  const pollTimerRef = useRef(null);
  const stopwatchRef = useRef(null);

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors }
  } = useForm({
    resolver: zodResolver(urlSchema),
    defaultValues: {
      url: store.url || ''
    }
  });

  const watchedUrl = watch('url');

  const stopPolling = () => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    if (stopwatchRef.current) {
      clearInterval(stopwatchRef.current);
      stopwatchRef.current = null;
    }
  };

  useEffect(() => {
    return () => stopPolling();
  }, []);

  // Sync store URL with form
  useEffect(() => {
    if (store.url && !watchedUrl) {
      setValue('url', store.url);
    }
  }, [store.url, setValue, watchedUrl]);

  const startAiAnalysis = async (title, description, videoUrl) => {
    stopPolling();
    setElapsedSeconds(0);
    setIsAccepted(false);
    stopwatchRef.current = setInterval(() => setElapsedSeconds(s => s + 1), 1000);

    store.setAiAnalysisStatus('loading');
    store.setAiJobProgress(null, 15, 'Queued for background analysis...');

    try {
      const initRes = await metadataApi.analyze(title, description, videoUrl);
      if (!initRes) {
        store.setAiAnalysisStatus('error', 'Failed to initialize AI analysis');
        return;
      }

      if (initRes.status === 'COMPLETED' && initRes.result) {
        store.setAiAnalysisResult(initRes.result);
        stopPolling();
        if (initRes.cached) {
          toast.success("⚡ Instant AI optimization loaded from cache!");
        }
        return;
      }

      const jobId = initRes.job_id;
      if (!jobId) {
        store.setAiAnalysisStatus('error', 'No job ID received from server');
        return;
      }

      store.setAiJobProgress(jobId, initRes.progress || 15, initRes.current_step || 'Processing video...');

      // Polling every 1.5 seconds
      let pollCount = 0;
      const MAX_POLLS = 200;

      pollTimerRef.current = setInterval(async () => {
        pollCount++;
        if (pollCount > MAX_POLLS) {
          stopPolling();
          store.setAiAnalysisStatus('timeout', 'AI analysis timed out after 5 minutes.');
          return;
        }

        try {
          const statusRes = await metadataApi.getAnalysisStatus(jobId);
          if (!statusRes) return;

          if (statusRes.status === 'COMPLETED' && statusRes.result) {
            stopPolling();
            store.setAiAnalysisResult(statusRes.result);
            toast.success("✨ AI Content Optimization complete!");
          } else if (statusRes.status === 'FAILED') {
            stopPolling();
            store.setAiAnalysisStatus('error', statusRes.error || 'AI analysis failed');
          } else if (statusRes.status === 'CANCELLED') {
            stopPolling();
            store.setAiAnalysisStatus('cancelled', 'AI analysis was cancelled');
          } else {
            store.setAiJobProgress(jobId, statusRes.progress || 20, statusRes.current_step || 'Working...');
          }
        } catch (pollErr) {
          console.warn("Polling error:", pollErr);
        }
      }, 1500);

    } catch (err) {
      console.error(err);
      store.setAiAnalysisStatus('error', err.message || 'Failed to start AI optimization');
    }
  };

  const handleCancelAi = async () => {
    stopPolling();
    if (store.aiJobId) {
      try {
        await metadataApi.cancelAnalysis(store.aiJobId);
      } catch (e) {
        console.warn("Cancel request failed", e);
      }
    }
    store.setAiAnalysisStatus('cancelled', 'AI analysis was cancelled.');
    toast.info("AI Analysis cancelled");
  };

  const handleRetryAi = () => {
    if (store.metadata?.title || store.metadata?.description || store.url) {
      startAiAnalysis(store.metadata?.title, store.metadata?.description, store.url);
    } else {
      onFormSubmit({ url: store.url });
    }
  };

  const handleContinueWithoutAi = () => {
    stopPolling();
    const fallbackTitle = store.metadata?.title || 'Trending Reel';
    const fallbackDesc = store.metadata?.description || '';
    const fallbackTags = store.allHashtags && store.allHashtags.length > 0 ? store.allHashtags : ['#Shorts', '#Viral', '#Trending'];
    
    store.setAiAnalysisResult({
      viral_title: fallbackTitle,
      optimized_description: fallbackDesc,
      youtube: fallbackTags,
      instagram: fallbackTags,
      analysis: "Using original video metadata (bypassed AI model).",
      confidence_notes: "MANUAL",
      scheduled_time: "07:30 PM",
      raw_result: {
        title: fallbackTitle,
        description: fallbackDesc,
        youtube_hashtags: fallbackTags,
        instagram_hashtags: fallbackTags,
        title_candidates: [{ strategy: 'Original Source', title: fallbackTitle }],
        viewer_appeal_score: 75,
        title_reason: ['Original Source Metadata'],
        posting_recommendation: {
          human_readable_time: "07:30 PM",
          reason: "Standard evening posting slot."
        }
      }
    });
    setIsAccepted(true);
    toast.info("Proceeding with standard metadata");
  };

  const onFormSubmit = async (data) => {
    const targetUrl = data.url.trim();
    if (!targetUrl) return;
    
    setIsLoading(true);
    stopPolling();
    store.resetWorkflow();
    store.setUrl(targetUrl);
    setIsAccepted(false);
    
    try {
      const formatsPromise = metadataApi.getFormats(targetUrl);
      const metadataPromise = metadataApi.getMetadata(targetUrl);
      const commentsPromise = metadataApi.getComments(targetUrl);

      metadataPromise.then(meta => {
        if (!meta) return;
        store.setMetadata(meta);
        const tags = meta.hashtags || [];
        if (tags.length > 0) store.setAllHashtags(tags);

        if (meta.title || meta.description || targetUrl) {
          startAiAnalysis(meta.title, meta.description, targetUrl);
        }
      });

      commentsPromise.then(comm => {
        if (comm?.available && comm.hashtags?.length > 0) {
          store.setAllHashtags([...new Set([...useVideoStore.getState().allHashtags, ...comm.hashtags])]);
        }
      });

      const formats = await formatsPromise;
      store.setFormats(formats);
      if (formats && formats.length > 0) {
        setActiveFormatId(formats[0].format_id);
      }

    } catch (err) {
      toast.error(err.message || "Failed to fetch video details");
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownload = async (formatId) => {
    const idToUse = formatId || activeFormatId || store.formats[0]?.format_id;
    if (!idToUse) return;
    toast.promise(
      videosApi.downloadVideo(store.url, idToUse).then(r => videosApi.handleFileDownload(r)),
      {
        loading: 'Starting download...',
        success: 'Download started!',
        error: 'Download failed'
      }
    );
  };

  const triggerAutomation = async () => {
    if (!appStore.isYtAuthenticated) {
      toast.error("Please connect YouTube first in Settings/Connections");
      return;
    }
    
    setIsAutomating(true);
    try {
      const payload = {
        title: store.aiAnalysisResult?.viral_title || store.metadata.title || 'Untitled',
        description: store.aiAnalysisResult?.optimized_description || store.metadata.description || '',
        hashtags: store.allHashtags || [],
        thumbnail_url: store.metadata.thumbnail_url || '',
        url: store.url,
        opus_mode: store.isOpusMode,
        iso_schedule: store.aiAnalysisResult?.raw_result?.posting_recommendation?.iso_time || store.aiAnalysisResult?.iso_schedule || null,
        scheduled_time_human: store.aiAnalysisResult?.scheduled_time || null
      };
      
      const res = await automationApi.triggerAutomation(payload);
      setAutomationResult(res.automation_details);
      toast.success("Scheduled successfully to Cloud!");
    } catch (err) {
      toast.error(err.message || "Automation failed");
    } finally {
      setIsAutomating(false);
    }
  };

  const hasResults = store.metadata || store.formats.length > 0;

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-20">
      {/* Header */}
      <div className="text-center space-y-2 mb-6">
        <h1 className="text-3xl font-black uppercase tracking-tight text-text">
          Create & Optimize Reel
        </h1>
        <p className="text-sm text-text-muted max-w-lg mx-auto">
          Paste an Instagram Reel or YouTube Shorts URL for frame inspection, viral copy generation, and automated cloud scheduling.
        </p>
      </div>

      {/* URL Input Form with React Hook Form & Zod Validation */}
      <Card className="bg-surface border-border p-4 shadow-sm">
        <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-2">
          <div className="flex flex-col sm:flex-row gap-2.5">
            <div className="relative flex-1">
              <input 
                type="text" 
                {...register('url')}
                placeholder="Paste an Instagram Reel or YouTube Shorts link (e.g. https://www.instagram.com/reel/...)"
                className={cn(
                  "w-full bg-surface-elevated/70 border rounded-lg px-4 py-3 pr-24 font-mono text-sm focus:outline-none transition-colors",
                  errors.url ? "border-danger focus:border-danger text-danger" : "border-border focus:border-accent text-text"
                )}
                disabled={isLoading || isAutomating}
              />
              
              <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1.5">
                {watchedUrl ? (
                  <button
                    type="button"
                    onClick={() => {
                      setValue('url', '');
                      store.setUrl('');
                    }}
                    className="text-xs text-text-muted hover:text-text px-2 py-1 rounded cursor-pointer transition-colors"
                  >
                    Clear
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        const text = await navigator.clipboard.readText();
                        if (text) {
                          setValue('url', text.trim());
                          store.setUrl(text.trim());
                          toast.success("URL pasted from clipboard");
                        }
                      } catch {
                        toast.error("Clipboard permission denied");
                      }
                    }}
                    className="text-[11px] font-mono font-medium text-accent bg-accent/10 border border-accent/20 px-2.5 py-1 rounded cursor-pointer hover:bg-accent/20 transition-colors"
                  >
                    Paste
                  </button>
                )}
              </div>
            </div>

            <Button 
              type="submit"
              disabled={isLoading || isAutomating} 
              className="h-auto px-6 py-3 bg-accent text-accent-foreground font-semibold flex items-center justify-center gap-2 cursor-pointer shadow-sm shadow-accent/20 shrink-0"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
              Analyze Video
            </Button>
          </div>

          {errors.url && (
            <p className="text-xs text-danger font-medium pl-1 flex items-center gap-1">
              <XCircle className="w-3.5 h-3.5" />
              {errors.url.message}
            </p>
          )}
        </form>
      </Card>

      {/* Loading State with Stopwatch */}
      {isLoading && (
        <Card className="bg-surface border-border p-12 text-center flex flex-col items-center justify-center space-y-3">
          <Loader2 className="w-8 h-8 animate-spin text-accent" />
          <p className="text-sm font-semibold tracking-wider uppercase text-text">
            Extracting Video Metadata & Formats...
          </p>
          <p className="text-xs text-text-muted">Analyzing source streams via yt-dlp</p>
        </Card>
      )}

      {/* Results Workspace */}
      {hasResults && !isLoading && (
        <motion.div 
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="grid gap-6"
        >
          {/* Top Section: Media Preview & AI Assistant Side-by-Side */}
          <div className="grid md:grid-cols-[300px_1fr] gap-6 items-start">
            {/* Left Card: Thumbnail & Quick Actions */}
            <Card className="overflow-hidden border-border bg-surface">
              <div className="aspect-[9/16] bg-black relative flex items-center justify-center overflow-hidden">
                {store.metadata?.thumbnail_url ? (
                  <img 
                    src={store.metadata.thumbnail_url} 
                    alt="Thumbnail" 
                    className="w-full h-full object-cover" 
                  />
                ) : (
                  <div className="flex flex-col items-center justify-center text-text-muted text-xs gap-2">
                    <Film className="w-8 h-8 opacity-40" />
                    <span>No Preview Available</span>
                  </div>
                )}
                <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-transparent to-transparent pointer-events-none" />
                <div className="absolute bottom-4 left-4 right-4">
                  <p className="text-xs font-bold text-white line-clamp-2 leading-snug">
                    {store.metadata?.title || 'Video Title'}
                  </p>
                  {store.metadata?.duration && (
                    <span className="text-[10px] font-mono text-zinc-300 mt-1 inline-block">
                      Duration: {Math.round(store.metadata.duration)}s
                    </span>
                  )}
                </div>
              </div>
              
              <div className="p-3 grid gap-2">
                <Button 
                  variant="secondary" 
                  className="w-full text-xs font-semibold cursor-pointer" 
                  onClick={() => handleDownload(activeFormatId)}
                >
                  <Download className="w-4 h-4 mr-2 text-accent" /> Download Selected MP4
                </Button>
                <Button 
                  variant="ghost" 
                  className="w-full text-xs text-text-muted hover:text-text cursor-pointer" 
                  onClick={() => videosApi.downloadThumbnail(store.url)}
                >
                  Download Cover Image
                </Button>
              </div>
            </Card>

            {/* Right Column: AI Optimization Panel & Staged Progress */}
            <div className="space-y-6">
              {/* AI Content Optimization Card */}
              <Card className="bg-surface border-border overflow-hidden">
                <CardHeader className="py-3 px-5 border-b border-border bg-surface-elevated/40 flex flex-row items-center justify-between">
                  <CardTitle className="text-xs font-mono font-bold tracking-wider text-accent flex items-center gap-2 uppercase">
                    <Sparkles className="w-4 h-4" /> AI Content Optimization
                  </CardTitle>
                  
                  {store.aiAnalysisResult && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleRetryAi}
                      className="text-xs text-text-muted hover:text-accent flex items-center gap-1 h-7 cursor-pointer"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      Regenerate
                    </Button>
                  )}
                </CardHeader>

                <CardContent className="p-5 space-y-5">
                  {store.aiAnalysisResult ? (
                    <>
                      {/* Proposed Viral Title */}
                      <div className="space-y-1.5 bg-accent/5 p-4 rounded-lg border border-accent/20">
                        <div className="flex justify-between items-center pb-1">
                          <span className="text-[10px] uppercase text-text-muted font-mono font-bold tracking-wider">
                            VIRAL SHORT TITLE
                          </span>
                          {store.aiAnalysisResult.raw_result?.viewer_appeal_score && (
                            <span className="text-xs font-mono font-bold text-accent">
                              Appeal Score: {store.aiAnalysisResult.raw_result.viewer_appeal_score}/100
                            </span>
                          )}
                        </div>
                        <div className="text-base font-bold text-text">
                          "{store.aiAnalysisResult.viral_title}"
                        </div>
                        
                        {store.aiAnalysisResult.raw_result?.title_reason && (
                          <div className="pt-2 mt-2 border-t border-accent/10 flex flex-wrap gap-x-3 gap-y-1">
                            {store.aiAnalysisResult.raw_result.title_reason.map((reason, i) => (
                              <div key={i} className="text-[11px] text-text-muted flex items-center gap-1.5">
                                <Check className="w-3 h-3 text-success" /> {reason}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Description */}
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] uppercase text-text-muted font-mono font-bold tracking-wider">
                            SEARCH-OPTIMIZED DESCRIPTION
                          </span>
                          <button 
                            type="button"
                            className="text-[10px] text-text-muted hover:text-accent flex items-center gap-1 cursor-pointer font-mono"
                            onClick={() => {
                              navigator.clipboard.writeText(store.aiAnalysisResult.optimized_description || "");
                              toast.success("Description copied to clipboard!");
                            }}
                          >
                            <Copy className="w-3 h-3" /> Copy
                          </button>
                        </div>
                        <div className="text-xs text-text bg-surface-elevated p-3 rounded-lg border border-border/70 leading-relaxed whitespace-pre-line font-sans">
                          {store.aiAnalysisResult.optimized_description}
                        </div>
                      </div>

                      {/* Hashtag Chips */}
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] uppercase text-text-muted font-mono font-bold tracking-wider">
                              VIRAL HASHTAGS
                            </span>
                            <span className="text-[10px] bg-surface-elevated px-2 py-0.5 rounded-full border border-border font-mono text-text-muted">
                              {(store.aiAnalysisResult.youtube || []).length} tags
                            </span>
                          </div>
                          <button 
                            type="button"
                            className="text-[10px] text-text-muted hover:text-accent flex items-center gap-1 cursor-pointer font-mono"
                            onClick={() => {
                              const tags = (store.aiAnalysisResult.youtube || []).join(' ');
                              navigator.clipboard.writeText(tags);
                              toast.success(`Copied ${(store.aiAnalysisResult.youtube || []).length} hashtags!`);
                            }}
                          >
                            <Copy className="w-3 h-3" /> Copy All
                          </button>
                        </div>

                        <div className="flex flex-wrap gap-1.5 p-3 bg-surface-elevated/50 rounded-lg border border-border min-h-[48px]">
                          {(store.aiAnalysisResult.youtube || []).map((tag, idx) => (
                            <span 
                              key={idx} 
                              className="text-xs px-2.5 py-1 bg-surface-elevated text-accent border border-accent/20 rounded-full flex items-center gap-1"
                            >
                              <span>{tag}</span>
                              <button 
                                type="button"
                                className="w-3.5 h-3.5 rounded-full hover:bg-danger/20 hover:text-danger text-text-muted inline-flex items-center justify-center text-[10px] transition-colors ml-0.5 cursor-pointer"
                                title="Remove tag"
                                onClick={() => {
                                  const updated = (store.aiAnalysisResult.youtube || []).filter((_, i) => i !== idx);
                                  store.setAiAnalysisResult({
                                    ...store.aiAnalysisResult,
                                    youtube: updated,
                                    instagram: updated
                                  });
                                }}
                              >
                                ×
                              </button>
                            </span>
                          ))}
                        </div>
                      </div>

                      {/* Recommended Publish Slot */}
                      <div className="p-3 bg-surface-elevated/40 border border-border rounded-lg space-y-1.5">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-mono text-[10px] uppercase text-text-muted font-bold tracking-wider">
                            RECOMMENDED TIME
                          </span>
                          <span className="font-bold text-success font-mono">
                            {store.aiAnalysisResult.scheduled_time}
                          </span>
                        </div>
                        <p className="text-[11px] text-text-muted italic">
                          {store.aiAnalysisResult.analysis || "Optimal engagement slot calculated based on channel history."}
                        </p>
                      </div>

                      {/* Accept / Apply Suggestions Confirmation Step */}
                      <div className="pt-2 border-t border-border flex flex-col sm:flex-row items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                          {isAccepted ? (
                            <span className="text-xs font-semibold text-success flex items-center gap-1.5 bg-success/10 px-2.5 py-1 rounded-md border border-success/20">
                              <ShieldCheck className="w-4 h-4" /> Suggestions Accepted
                            </span>
                          ) : (
                            <span className="text-xs text-text-muted">
                              Review metadata above, then accept to proceed.
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-2 w-full sm:w-auto">
                          {!isAccepted ? (
                            <Button
                              type="button"
                              onClick={() => {
                                setIsAccepted(true);
                                toast.success("AI Suggestions applied!");
                              }}
                              className="w-full sm:w-auto bg-accent text-accent-foreground hover:bg-accent/90 text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
                            >
                              <CheckCircle2 className="w-4 h-4" />
                              Accept Suggestions
                            </Button>
                          ) : (
                            <Button
                              type="button"
                              variant="outline"
                              onClick={() => setIsAccepted(false)}
                              className="text-xs text-text-muted cursor-pointer"
                            >
                              Edit / Unaccept
                            </Button>
                          )}
                        </div>
                      </div>
                    </>
                  ) : store.aiAnalysisStatus === 'loading' ? (
                    /* Live Indeterminate Progress & Stopwatch Indicator */
                    <div className="space-y-4 p-4 bg-surface-elevated/40 rounded-lg border border-border">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-accent font-semibold text-xs tracking-wider uppercase">
                          <Sparkles className="w-4 h-4 animate-spin text-accent" />
                          <span>AI Generation In Progress</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] font-mono text-text-muted bg-surface px-2 py-0.5 rounded border border-border">
                            ⏱ {String(Math.floor(elapsedSeconds / 60)).padStart(2, '0')}:{String(elapsedSeconds % 60).padStart(2, '0')}
                          </span>
                          <span className="text-xs font-mono font-bold bg-accent/15 text-accent px-2 py-0.5 rounded border border-accent/30">
                            {store.aiProgress}%
                          </span>
                        </div>
                      </div>

                      {/* Progress Bar */}
                      <div className="w-full bg-surface h-2 rounded-full overflow-hidden border border-border">
                        <div 
                          className="bg-accent h-full transition-all duration-500 rounded-full"
                          style={{ width: `${Math.max(store.aiProgress, 12)}%` }}
                        />
                      </div>

                      {/* 5-Step Staged Pipeline */}
                      <div className="space-y-2 text-xs font-mono">
                        <div className="flex items-center gap-2.5">
                          {store.aiProgress >= 20 ? (
                            <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                          ) : (
                            <RefreshCw className="w-3.5 h-3.5 text-accent animate-spin shrink-0" />
                          )}
                          <span className={store.aiProgress >= 20 ? "text-text font-medium" : "text-text-muted"}>
                            Inspecting video footage & key frames
                          </span>
                        </div>

                        <div className="flex items-center gap-2.5">
                          {store.aiProgress >= 40 ? (
                            <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                          ) : store.aiProgress >= 20 ? (
                            <RefreshCw className="w-3.5 h-3.5 text-accent animate-spin shrink-0" />
                          ) : (
                            <div className="w-3.5 h-3.5 rounded-full border border-border flex items-center justify-center text-[9px] text-text-muted">○</div>
                          )}
                          <span className={store.aiProgress >= 40 ? "text-text font-medium" : "text-text-muted"}>
                            Extracting visual frames & spoken dialogue
                          </span>
                        </div>

                        <div className="flex items-center gap-2.5">
                          {store.aiProgress >= 60 ? (
                            <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                          ) : store.aiProgress >= 40 ? (
                            <RefreshCw className="w-3.5 h-3.5 text-accent animate-spin shrink-0" />
                          ) : (
                            <div className="w-3.5 h-3.5 rounded-full border border-border flex items-center justify-center text-[9px] text-text-muted">○</div>
                          )}
                          <span className={store.aiProgress >= 60 ? "text-text font-medium" : "text-text-muted"}>
                            Analyzing retention hooks & audience sentiment
                          </span>
                        </div>

                        <div className="flex items-center gap-2.5">
                          {store.aiProgress >= 80 ? (
                            <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                          ) : store.aiProgress >= 60 ? (
                            <RefreshCw className="w-3.5 h-3.5 text-accent animate-spin shrink-0" />
                          ) : (
                            <div className="w-3.5 h-3.5 rounded-full border border-border flex items-center justify-center text-[9px] text-text-muted">○</div>
                          )}
                          <span className={store.aiProgress >= 80 ? "text-text font-medium" : "text-text-muted"}>
                            Generating viral title & SEO description
                          </span>
                        </div>

                        <div className="flex items-center gap-2.5">
                          {store.aiProgress >= 100 ? (
                            <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                          ) : store.aiProgress >= 80 ? (
                            <RefreshCw className="w-3.5 h-3.5 text-accent animate-spin shrink-0" />
                          ) : (
                            <div className="w-3.5 h-3.5 rounded-full border border-border flex items-center justify-center text-[9px] text-text-muted">○</div>
                          )}
                          <span className={store.aiProgress >= 100 ? "text-text font-medium" : "text-text-muted"}>
                            Finalizing hashtags & optimal posting slot
                          </span>
                        </div>
                      </div>

                      <div className="pt-3 border-t border-border flex items-center justify-between gap-2">
                        <p className="text-[11px] text-text-muted truncate font-mono">
                          {store.aiStepMessage || "Processing through model pipeline..."}
                        </p>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            className="h-7 text-xs text-danger hover:bg-danger/10 flex items-center gap-1 cursor-pointer"
                            onClick={handleCancelAi}
                          >
                            <XCircle className="w-3.5 h-3.5" /> Cancel
                          </Button>
                          <Button 
                            variant="secondary" 
                            size="sm" 
                            className="h-7 text-xs bg-surface-elevated hover:bg-surface-elevated/80 text-text cursor-pointer"
                            onClick={handleContinueWithoutAi}
                          >
                            Skip AI
                          </Button>
                        </div>
                      </div>
                    </div>
                  ) : store.aiAnalysisStatus === 'cancelled' ? (
                    <div className="py-6 flex flex-col items-center justify-center text-center space-y-3">
                      <XCircle className="w-8 h-8 text-text-muted" />
                      <h3 className="font-bold text-sm text-text">AI Analysis Cancelled</h3>
                      <p className="text-xs text-text-muted max-w-xs">
                        You stopped the background worker. You can retry or proceed using original metadata.
                      </p>
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={handleRetryAi} className="text-xs cursor-pointer">
                          <RotateCcw className="w-3.5 h-3.5 mr-1" /> Retry AI
                        </Button>
                        <Button variant="secondary" size="sm" onClick={handleContinueWithoutAi} className="text-xs bg-accent text-accent-foreground cursor-pointer">
                          Continue Without AI
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="py-6 flex flex-col items-center justify-center text-center space-y-3">
                      <Button 
                        onClick={handleRetryAi} 
                        className="bg-accent text-accent-foreground text-xs font-semibold flex items-center gap-2 cursor-pointer"
                      >
                        <Sparkles className="w-4 h-4" /> Start AI Analysis
                      </Button>
                      <button 
                        type="button" 
                        onClick={handleContinueWithoutAi}
                        className="text-xs text-text-muted hover:text-text cursor-pointer underline underline-offset-4"
                      >
                        or skip and use original video title
                      </button>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Cloud Publisher Scheduling Card */}
              <Card className="bg-surface border-border p-5 space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-border">
                  <div className="flex items-center gap-2">
                    <MonitorPlay className="w-4 h-4 text-accent" />
                    <span className="text-xs font-mono font-bold tracking-wider text-text uppercase">
                      Cloud Publisher
                    </span>
                  </div>
                  {appStore.isYtAuthenticated ? (
                    <span className="text-[10px] font-mono bg-success/15 text-success px-2 py-0.5 rounded-full border border-success/25 font-semibold">
                      Connected to YouTube
                    </span>
                  ) : (
                    <span className="text-[10px] font-mono bg-warning/15 text-warning px-2 py-0.5 rounded-full border border-warning/25 font-semibold">
                      YouTube Not Linked
                    </span>
                  )}
                </div>

                {automationResult ? (
                  <div className="bg-success/10 border border-success/30 p-4 rounded-lg space-y-2">
                    <div className="flex items-center gap-2 text-success font-bold text-sm">
                      <Check className="w-4 h-4" /> Pipeline Scheduled Successfully!
                    </div>
                    <p className="text-xs text-text-muted">
                      Scheduled for: <strong className="text-text">{automationResult.scheduled_time}</strong>
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <Button 
                      className="w-full h-11 bg-accent text-accent-foreground hover:bg-accent/90 text-sm font-semibold flex items-center justify-center gap-2 cursor-pointer shadow-sm"
                      onClick={triggerAutomation}
                      disabled={isAutomating || !appStore.isYtAuthenticated || (!isAccepted && Boolean(store.aiAnalysisResult))}
                    >
                      {isAutomating ? <Loader2 className="w-4 h-4 animate-spin" /> : <MonitorPlay className="w-4 h-4" />}
                      Deploy & Schedule to YouTube Shorts
                    </Button>

                    {!appStore.isYtAuthenticated && (
                      <p className="text-[11px] text-danger text-center">
                        Link your YouTube channel in Settings or Connections before publishing.
                      </p>
                    )}
                    {Boolean(store.aiAnalysisResult) && !isAccepted && (
                      <p className="text-[11px] text-text-muted text-center">
                        Click "Accept Suggestions" in the panel above to unlock deployment.
                      </p>
                    )}
                  </div>
                )}
              </Card>
            </div>
          </div>

          {/* Visual Format & Quality Picker Cards */}
          <Card className="bg-surface border-border">
            <CardHeader className="py-4 px-6 border-b border-border">
              <CardTitle className="text-sm font-semibold text-text flex items-center justify-between">
                <span>Available Video Formats & Quality</span>
                <span className="text-xs font-normal text-text-muted font-mono">
                  {store.formats.length} formats extracted
                </span>
              </CardTitle>
            </CardHeader>

            <CardContent className="p-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {store.formats.map((fmt) => {
                  const isSelected = activeFormatId === fmt.format_id;
                  const sizeMb = fmt.filesize ? (fmt.filesize / 1024 / 1024).toFixed(1) : null;

                  return (
                    <div
                      key={fmt.format_id}
                      onClick={() => setActiveFormatId(fmt.format_id)}
                      className={cn(
                        "p-4 rounded-xl border transition-all cursor-pointer flex flex-col justify-between group",
                        isSelected 
                          ? "bg-accent/10 border-accent shadow-sm" 
                          : "bg-surface-elevated/60 border-border/70 hover:border-border hover:bg-surface-elevated"
                      )}
                    >
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <span className={cn(
                            "text-[10px] font-mono font-bold px-2 py-0.5 rounded uppercase tracking-wider",
                            fmt.is_original 
                              ? "bg-accent text-accent-foreground" 
                              : "bg-surface text-text-muted border border-border"
                          )}>
                            {fmt.is_original ? 'ORIGINAL SOURCE' : fmt.ext}
                          </span>

                          {fmt.is_original && (
                            <span className="text-[10px] text-success font-semibold flex items-center gap-0.5">
                              <CheckCircle2 className="w-3 h-3" /> Best
                            </span>
                          )}
                        </div>

                        <div className="text-sm font-bold text-text mb-1">
                          {fmt.resolution || 'Standard'}
                        </div>

                        <div className="text-xs text-text-muted font-mono space-y-0.5">
                          <div>Ratio: {fmt.aspect_ratio || '9:16'}</div>
                          <div>FPS: {fmt.fps || '30'} • Codec: {fmt.vcodec?.split('.')[0] || 'h264'}</div>
                          {sizeMb && <div>Est. Size: {sizeMb} MB</div>}
                        </div>
                      </div>

                      <div className="mt-4 pt-3 border-t border-border/60 flex items-center justify-between">
                        <span className="text-[11px] text-text-muted font-mono">
                          {isSelected ? 'Selected' : 'Click to select'}
                        </span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDownload(fmt.format_id);
                          }}
                          className="h-7 text-xs text-accent hover:bg-accent/20 cursor-pointer flex items-center gap-1"
                        >
                          <Download className="w-3 h-3" /> Download
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
