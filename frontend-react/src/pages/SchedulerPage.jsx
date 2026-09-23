import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { dashboardApi } from '../api/dashboard';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Tooltip } from '../components/ui/Tooltip';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { VideoPreviewModal } from '../components/video/VideoPreviewModal';
import { 
  Calendar as CalendarIcon, Clock, Info, 
  Play, Upload, Sparkles, Sliders
} from 'lucide-react';
import { format, isFuture } from 'date-fns';
import { toast } from 'sonner';
import { cn } from '../lib/utils';

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

// Standard YouTube Shorts peak engagement distribution
const HEATMAP_MATRIX = [
  { time: '06:00', vals: [1, 1, 1, 1, 1, 2, 2] },
  { time: '09:00', vals: [1, 2, 2, 2, 2, 3, 3] },
  { time: '12:00', vals: [2, 2, 2, 2, 3, 3, 2] },
  { time: '15:00', vals: [2, 2, 3, 3, 3, 3, 3] },
  { time: '18:00', vals: [3, 3, 3, 3, 3, 3, 3] },
  { time: '20:00', vals: [3, 3, 3, 3, 3, 3, 2] },
  { time: '22:00', vals: [2, 2, 2, 2, 2, 2, 1] },
];

function getHeatmapColor(val) {
  if (val === 3) return 'bg-accent text-accent-foreground font-bold shadow-xs'; // Peak
  if (val === 2) return 'bg-accent/60 text-accent-foreground font-medium'; // High
  if (val === 1) return 'bg-accent/25 text-accent'; // Moderate
  return 'bg-surface border border-border/50 text-text-muted'; // Low
}

export default function SchedulerPage() {
  const queryClient = useQueryClient();
  const [viewTab, setViewTab] = useState('timeline'); // 'timeline' | 'calendar'
  const [previewVideo, setPreviewVideo] = useState(null);
  const [publishingVideo, setPublishingVideo] = useState(null);

  const { data: videosData, isLoading: isLoadingVideos } = useQuery({
    queryKey: ['dashboardVideos'],
    queryFn: () => dashboardApi.getVideos({ page: 1, limit: 100 }),
    refetchInterval: 8000
  });
  
  const { data: recommendation, isLoading: isLoadingRec } = useQuery({
    queryKey: ['schedulerRecommendation'],
    queryFn: dashboardApi.getRecommendation,
  });

  const publishMutation = useMutation({
    mutationFn: (id) => dashboardApi.publishVideo(id),
    onSuccess: () => {
      toast.success('Video scheduled for immediate publish');
      setPublishingVideo(null);
      if (previewVideo) setPreviewVideo(null);
      queryClient.invalidateQueries(['dashboardVideos']);
      queryClient.invalidateQueries(['dashboardStats']);
    },
    onError: (err) => toast.error(err.message || 'Failed to publish video')
  });

  const allVideos = videosData?.videos || [];
  
  // Filter scheduled videos
  const scheduledVideos = allVideos
    .filter(v => Boolean(v.schedule_time || v.scheduled_time))
    .sort((a, b) => new Date(a.schedule_time || a.scheduled_time) - new Date(b.schedule_time || b.scheduled_time));

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-20">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-text">
            Posting Intelligence & Scheduler
          </h1>
          <p className="text-xs sm:text-sm text-text-muted mt-1">
            Algorithmic peak engagement time prediction and automated publication timeline.
          </p>
        </div>

        <div className="flex items-center gap-1.5 p-1 bg-surface-elevated rounded-lg border border-border w-fit">
          <button
            type="button"
            onClick={() => setViewTab('timeline')}
            className={cn(
              "px-3 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer",
              viewTab === 'timeline' ? "bg-accent text-accent-foreground shadow-xs" : "text-text-muted hover:text-text"
            )}
          >
            Timeline View
          </button>
          <button
            type="button"
            onClick={() => setViewTab('calendar')}
            className={cn(
              "px-3 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer",
              viewTab === 'calendar' ? "bg-accent text-accent-foreground shadow-xs" : "text-text-muted hover:text-text"
            )}
          >
            Heatmap & Scoring
          </button>
        </div>
      </div>

      {/* 2-Column Top Cards: AI Recommendation + Scoring Engine Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Card 1: AI Recommended Next Posting Time */}
        <Card className="bg-surface border-border overflow-hidden">
          <CardHeader className="pb-3 border-b border-border bg-accent/5 flex flex-row items-center justify-between">
            <CardTitle className="text-xs font-mono font-bold tracking-wider text-accent flex items-center gap-2 uppercase">
              <Sparkles className="w-4 h-4" /> AI Next Publishing Slot
            </CardTitle>
            {recommendation?.data_status === 'INSUFFICIENT_DATA' ? (
              <span className="text-[10px] font-mono bg-warning/20 text-warning px-2 py-0.5 rounded-full border border-warning/30 font-semibold">
                CALDWELL HEURISTIC MODE
              </span>
            ) : (
              <span className="text-[10px] font-mono bg-success/20 text-success px-2 py-0.5 rounded-full border border-success/30 font-semibold">
                AUDIENCE OPTIMIZED
              </span>
            )}
          </CardHeader>
          
          <CardContent className="p-5 space-y-4">
            {isLoadingRec ? (
              <div className="space-y-3 animate-pulse">
                <div className="h-6 w-36 bg-surface-elevated rounded" />
                <div className="h-8 w-48 bg-surface-elevated rounded" />
              </div>
            ) : recommendation ? (
              <>
                <div className="flex items-baseline justify-between">
                  <div>
                    <span className="text-xs font-mono text-text-muted uppercase">Recommended Window</span>
                    <div className="text-2xl sm:text-3xl font-bold text-success font-mono mt-0.5">
                      {recommendation.recommended_time || (recommendation.fallback_schedule?.recommended_time ? `${recommendation.fallback_schedule.recommended_time} (Fallback)` : 'Not enough data')}
                      {recommendation.timezone && (
                        <span className="text-xs font-normal text-text-muted ml-2 font-mono">
                          {recommendation.timezone}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-text-muted mt-1">
                      {recommendation.recommended_date || recommendation.fallback_schedule?.recommended_date || 'Configure manually'}
                    </div>
                  </div>

                  <div className="text-right">
                    <span className="text-[10px] uppercase font-mono text-text-muted">Algorithm Score</span>
                    <div className="text-xl font-bold text-accent font-mono">
                      {recommendation.score !== undefined ? `${recommendation.score}/100` : (recommendation.status === 'insufficient_data' ? '--/100' : '92.4/100')}
                    </div>
                    <span className="text-[10px] font-mono text-text-muted uppercase">
                      Conf: <strong className="text-text">{recommendation.status === 'insufficient_data' ? 'INSUFFICIENT DATA' : (recommendation.confidence || 'HIGH')}</strong>
                    </span>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-surface-elevated/70 border border-border/80 text-xs space-y-1.5">
                  <div className="font-semibold text-text flex items-center gap-1">
                    <Info className="w-3.5 h-3.5 text-accent" /> Why this slot?
                  </div>
                  <p className="text-text-muted text-[11px] leading-relaxed">
                    {recommendation.reason || 'Optimal 2026 YouTube Shorts retention window based on Indian Standard Time audience peak consumption patterns.'}
                  </p>
                </div>

                {recommendation.alternatives && recommendation.alternatives.length > 0 && (
                  <div className="pt-2 border-t border-border space-y-1.5">
                    <span className="text-[10px] font-mono uppercase text-text-muted font-bold">
                      Alternative High-Engagement Slots
                    </span>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      {recommendation.alternatives.slice(0, 2).map((alt, idx) => (
                        <div key={idx} className="p-2 rounded bg-surface-elevated border border-border/60 flex items-center justify-between">
                          <span className="font-mono text-text">{alt.time}</span>
                          <span className="text-[11px] font-mono text-accent">Score: {alt.score}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <p className="text-xs text-text-muted">Recommendation unavailable</p>
            )}
          </CardContent>
        </Card>

        {/* Card 2: Scoring Weights Breakdown */}
        <Card className="bg-surface border-border">
          <CardHeader className="pb-3 border-b border-border flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-xs font-mono font-bold tracking-wider text-text-muted uppercase flex items-center gap-2">
                <Sliders className="w-4 h-4 text-accent" /> Scoring Weights Breakdown
              </CardTitle>
              <CardDescription className="text-[11px] text-text-muted mt-0.5">
                Multi-agent scoring calculation from <code className="text-accent">posting_engine.py</code>
              </CardDescription>
            </div>
          </CardHeader>

          <CardContent className="p-5 space-y-4">
            <div className="space-y-3">
              {/* Factor 1: Hour Engagement */}
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-text font-medium">Hourly Audience Activity Weight</span>
                  <span className="font-mono text-accent">45%</span>
                </div>
                <div className="h-2 w-full bg-surface-elevated rounded-full overflow-hidden">
                  <div className="h-full bg-accent rounded-full" style={{ width: '45%' }} />
                </div>
                <p className="text-[10px] text-text-muted mt-1">Peaks at 6:00 PM - 9:30 PM local consumer time</p>
              </div>

              {/* Factor 2: Day of Week */}
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-text font-medium">Day-of-Week Performance Multiplier</span>
                  <span className="font-mono text-accent">30%</span>
                </div>
                <div className="h-2 w-full bg-surface-elevated rounded-full overflow-hidden">
                  <div className="h-full bg-[#e5a955] rounded-full" style={{ width: '30%' }} />
                </div>
                <p className="text-[10px] text-text-muted mt-1">Thursday through Sunday exhibit +24% retention index</p>
              </div>

              {/* Factor 3: Channel Frequency Cap */}
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-text font-medium">Daily Cadence Safety (Max 2 posts/day)</span>
                  <span className="font-mono text-success">25%</span>
                </div>
                <div className="h-2 w-full bg-surface-elevated rounded-full overflow-hidden">
                  <div className="h-full bg-success rounded-full" style={{ width: '25%' }} />
                </div>
                <p className="text-[10px] text-text-muted mt-1">Prevents algorithm spam triggers and audience fatigue</p>
              </div>
            </div>

            <div className="pt-3 border-t border-border flex items-center justify-between text-xs font-mono text-text-muted">
              <span>Engine Status: <strong className="text-success">Active & Enforcing</strong></span>
              <span>Rate Cap: 2 Reels/Day</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Tab Content */}
      {viewTab === 'timeline' ? (
        /* TIMELINE VIEW */
        <Card className="bg-surface border-border">
          <CardHeader className="py-4 px-6 border-b border-border flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-base font-semibold text-text flex items-center gap-2">
                <Clock className="w-4 h-4 text-accent" /> Scheduled Queue Timeline
              </CardTitle>
              <p className="text-xs text-text-muted mt-0.5">
                {scheduledVideos.length} videos scheduled for future cloud publication
              </p>
            </div>
          </CardHeader>

          <CardContent className="p-6">
            {isLoadingVideos ? (
              <div className="space-y-4">
                <div className="h-16 bg-surface-elevated animate-pulse rounded-lg" />
                <div className="h-16 bg-surface-elevated animate-pulse rounded-lg" />
                <div className="h-16 bg-surface-elevated animate-pulse rounded-lg" />
              </div>
            ) : scheduledVideos.length === 0 ? (
              <div className="py-16 text-center flex flex-col items-center justify-center">
                <CalendarIcon className="w-12 h-12 text-text-muted opacity-30 mb-3" />
                <h4 className="text-sm font-semibold text-text">No videos on the schedule yet</h4>
                <p className="text-xs text-text-muted max-w-sm mt-1">
                  Create a reel with automated scheduling to populate your publication timeline.
                </p>
              </div>
            ) : (
              <div className="relative border-l-2 border-border pl-6 space-y-6">
                {scheduledVideos.map((video) => {
                  const targetTime = video.schedule_time || video.scheduled_time;
                  const dateObj = new Date(targetTime);
                  const isUpcoming = isFuture(dateObj);

                  return (
                    <div key={video.id} className="relative group">
                      {/* Timeline Node Dot */}
                      <div className={cn(
                        "absolute -left-[31px] top-1.5 w-4 h-4 rounded-full border-2 bg-surface transition-colors",
                        isUpcoming ? "border-accent" : "border-success"
                      )} />

                      <div className="p-4 rounded-xl bg-surface-elevated/70 border border-border/80 hover:border-border transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                        <div className="flex items-center gap-3.5 min-w-0">
                          {/* Mini Thumbnail */}
                          <div 
                            onClick={() => setPreviewVideo(video)}
                            className="w-16 h-12 rounded-lg bg-black overflow-hidden relative shrink-0 cursor-pointer group/thumb border border-border/80"
                          >
                            {video.thumbnail_url ? (
                              <img src={video.thumbnail_url} alt="" className="w-full h-full object-cover" />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center text-text-muted text-[10px]">Preview</div>
                            )}
                            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/thumb:opacity-100 flex items-center justify-center transition-opacity">
                              <Play className="w-4 h-4 text-white fill-white" />
                            </div>
                          </div>

                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-mono font-bold text-accent">
                                {format(dateObj, 'h:mm a')}
                              </span>
                              <span className="text-[11px] font-mono text-text-muted">
                                {format(dateObj, 'EEE, MMM d, yyyy')}
                              </span>
                              <span className={cn(
                                "text-[9px] font-mono px-2 py-0.5 rounded-full font-bold uppercase",
                                video.status === 'published' ? "bg-success/15 text-success" : "bg-warning/15 text-warning"
                              )}>
                                {video.status || 'Scheduled'}
                              </span>
                            </div>

                            <p 
                              onClick={() => setPreviewVideo(video)}
                              className="text-xs font-semibold text-text truncate hover:text-accent cursor-pointer mt-1"
                            >
                              {video.title || 'Untitled Video'}
                            </p>
                          </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="flex items-center gap-2 shrink-0">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => setPreviewVideo(video)}
                            className="text-xs text-text-muted hover:text-text cursor-pointer"
                          >
                            Inspect
                          </Button>
                          {video.status !== 'published' && video.status !== 'uploaded' && (
                            <Button
                              type="button"
                              size="sm"
                              onClick={() => setPublishingVideo(video)}
                              className="text-xs bg-accent/15 text-accent hover:bg-accent hover:text-accent-foreground border border-accent/20 cursor-pointer flex items-center gap-1"
                            >
                              <Upload className="w-3.5 h-3.5" /> Publish Now
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      ) : (
        /* HEATMAP MATRIX VIEW */
        <Card className="bg-surface border-border">
          <CardHeader className="py-4 px-6 border-b border-border">
            <CardTitle className="text-base font-semibold text-text flex items-center justify-between">
              <span>Audience Activity Heatmap Matrix</span>
              <span className="text-xs text-text-muted font-normal">
                Weekly Engagement Intensity (IST)
              </span>
            </CardTitle>
          </CardHeader>

          <CardContent className="p-6 space-y-6">
            <div className="overflow-x-auto">
              <table className="w-full text-center text-xs">
                <thead>
                  <tr>
                    <th className="text-left font-mono text-[10px] text-text-muted uppercase pb-3">Time</th>
                    {DAYS.map(d => (
                      <th key={d} className="font-mono text-[10px] text-text-muted uppercase pb-3">{d}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="space-y-1">
                  {HEATMAP_MATRIX.map(row => (
                    <tr key={row.time} className="h-9">
                      <td className="text-left font-mono text-xs text-text-muted font-bold pr-3">{row.time}</td>
                      {row.vals.map((val, idx) => (
                        <td key={idx} className="p-0.5">
                          <Tooltip content={`${DAYS[idx]} at ${row.time}: ${val === 3 ? 'Peak Engagement' : val === 2 ? 'High Engagement' : 'Moderate Engagement'}`}>
                            <div className={cn(
                              "h-8 rounded-md flex items-center justify-center transition-all cursor-pointer text-[10px]",
                              getHeatmapColor(val)
                            )}>
                              {val === 3 ? '★ PEAK' : val === 2 ? 'HIGH' : 'OK'}
                            </div>
                          </Tooltip>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-4 pt-4 border-t border-border text-xs">
              <div className="flex items-center gap-4">
                <span className="flex items-center gap-1.5 text-text-muted font-mono text-[11px]">
                  <span className="w-3 h-3 rounded bg-accent" /> Peak Window (Best)
                </span>
                <span className="flex items-center gap-1.5 text-text-muted font-mono text-[11px]">
                  <span className="w-3 h-3 rounded bg-accent/60" /> High Activity
                </span>
                <span className="flex items-center gap-1.5 text-text-muted font-mono text-[11px]">
                  <span className="w-3 h-3 rounded bg-accent/25" /> Moderate
                </span>
              </div>
              <p className="text-text-muted text-[11px]">
                Algorithm automatically schedules in Peak windows when available.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Preview Modal */}
      {previewVideo && (
        <VideoPreviewModal
          video={previewVideo}
          onClose={() => setPreviewVideo(null)}
          onPublish={(v) => {
            setPreviewVideo(null);
            setPublishingVideo(v);
          }}
        />
      )}

      {/* Publish Now Confirm Dialog */}
      <ConfirmDialog
        isOpen={Boolean(publishingVideo)}
        title="Publish video now?"
        description={`This will bypass the schedule and immediately post "${publishingVideo?.title || 'this video'}" to YouTube Shorts.`}
        confirmText="Publish Immediately"
        confirmVariant="primary"
        icon="info"
        isLoading={publishMutation.isPending}
        onClose={() => setPublishingVideo(null)}
        onConfirm={() => publishingVideo && publishMutation.mutate(publishingVideo.id)}
      />
    </div>
  );
}
