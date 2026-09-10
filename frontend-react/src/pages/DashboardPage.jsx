import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { dashboardApi } from '../api/dashboard';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { SkeletonMetric, SkeletonTableRow } from '../components/ui/Skeleton';
import { 
  Plus, Clock, Upload, AlertCircle, CheckCircle2, Film, RefreshCw, 
  Trash2, Play, ChevronRight, Calendar, Activity, ArrowUpRight
} from 'lucide-react';
import { formatDistanceToNow, format } from 'date-fns';
import { toast } from 'sonner';
import { VideoPreviewModal } from '../components/video/VideoPreviewModal';
import { ConvertRatioModal } from '../components/video/ConvertRatioModal';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';

export default function DashboardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Modals state
  const [inspectVideo, setInspectVideo] = useState(null);
  const [convertingVideo, setConvertingVideo] = useState(null);
  const [publishingVideo, setPublishingVideo] = useState(null);
  const [deletingVideo, setDeletingVideo] = useState(null);

  // Queries
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboardStats'],
    queryFn: dashboardApi.getStats,
    refetchInterval: 6000,
  });

  const { data: videosData, isLoading: videosLoading } = useQuery({
    queryKey: ['dashboardVideosRecent'],
    queryFn: () => dashboardApi.getVideos({ page: 1, limit: 6 }),
    refetchInterval: 6000,
  });

  const { data: logsData, isLoading: logsLoading } = useQuery({
    queryKey: ['dashboardRecentLogs'],
    queryFn: () => dashboardApi.getLogs(),
    refetchInterval: 8000,
  });

  // Mutations
  const deleteMutation = useMutation({
    mutationFn: (id) => dashboardApi.deleteVideo(id),
    onSuccess: () => {
      toast.success('Video removed from storage and database');
      setDeletingVideo(null);
      if (inspectVideo) setInspectVideo(null);
      queryClient.invalidateQueries(['dashboardStats']);
      queryClient.invalidateQueries(['dashboardVideosRecent']);
      queryClient.invalidateQueries(['dashboardVideos']);
    },
    onError: (err) => toast.error(err.message || 'Failed to delete video'),
  });

  const convertMutation = useMutation({
    mutationFn: ({ id, ratio }) => dashboardApi.convertVideo(id, ratio),
    onSuccess: () => {
      toast.success('Aspect ratio conversion initiated');
      setConvertingVideo(null);
      queryClient.invalidateQueries(['dashboardVideosRecent']);
    },
    onError: (err) => toast.error(err.message || 'Failed to convert video'),
  });

  const publishMutation = useMutation({
    mutationFn: (id) => dashboardApi.publishVideo(id),
    onSuccess: () => {
      toast.success('Video successfully published to YouTube!');
      setPublishingVideo(null);
      if (inspectVideo) setInspectVideo(null);
      queryClient.invalidateQueries(['dashboardStats']);
      queryClient.invalidateQueries(['dashboardVideosRecent']);
      queryClient.invalidateQueries(['dashboardRecentLogs']);
    },
    onError: (err) => toast.error(err.message || 'Failed to publish video'),
  });

  // Time-aware greeting
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 18) return 'Good afternoon';
    return 'Good evening';
  };

  const videos = videosData?.videos || [];
  const activityEvents = logsData?.activity_events?.slice(0, 6) || [];
  const pendingCount = stats?.pending ?? stats?.scheduled ?? 0;
  const uploadedCount = stats?.uploaded ?? stats?.published ?? 0;
  const failedCount = stats?.failed ?? 0;
  const totalProcessed = stats?.total ?? (pendingCount + uploadedCount + failedCount);

  // Overview distribution percentages
  const pendingPct = totalProcessed > 0 ? (pendingCount / totalProcessed) * 100 : 0;
  const uploadedPct = totalProcessed > 0 ? (uploadedCount / totalProcessed) * 100 : 0;
  const failedPct = totalProcessed > 0 ? (failedCount / totalProcessed) * 100 : 0;

  const getEventBadge = (type) => {
    if (type?.includes('SUCCESS') || type?.includes('PUBLISHED')) {
      return <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-success/15 text-success border border-success/30 font-semibold">SUCCESS</span>;
    }
    if (type?.includes('FAILED') || type?.includes('ERROR')) {
      return <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-danger/15 text-danger border border-danger/30 font-semibold">FAILED</span>;
    }
    if (type?.includes('STARTED') || type?.includes('SCHEDULED')) {
      return <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-warning/15 text-warning border border-warning/30 font-semibold">QUEUED</span>;
    }
    return <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-surface-elevated text-text-muted border border-border font-semibold">INFO</span>;
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="space-y-8 pb-16"
    >
      {/* Creator Header Section */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-text">
              {getGreeting()}
            </h1>
            <span className="text-xl">✨</span>
          </div>
          <p className="text-sm text-text-muted mt-1">
            Turn your videos into publish-ready YouTube Shorts & Instagram Reels with AI optimization.
          </p>
        </div>

        {/* Quick-action buttons */}
        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => navigate('/library')}
            className="text-xs flex items-center gap-1.5 cursor-pointer"
          >
            <Film className="w-3.5 h-3.5 text-text-muted" />
            Library
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => navigate('/scheduler')}
            className="text-xs flex items-center gap-1.5 cursor-pointer"
          >
            <Calendar className="w-3.5 h-3.5 text-text-muted" />
            Scheduler
          </Button>
          <Button
            type="button"
            onClick={() => navigate('/create')}
            className="bg-accent text-accent-foreground hover:bg-accent/90 px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm shadow-accent/20 cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            Create Reel
          </Button>
        </div>
      </div>

      {/* Real Statistics Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {statsLoading ? (
          <>
            <SkeletonMetric />
            <SkeletonMetric />
            <SkeletonMetric />
            <SkeletonMetric />
          </>
        ) : (
          <>
            {/* Pending Card */}
            <Card className="bg-surface border-border/80 hover:border-border transition-colors">
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-xs font-mono font-medium text-text-muted uppercase tracking-wider">
                  Pending Queue
                </CardTitle>
                <Clock className="w-4 h-4 text-warning" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-text font-mono">
                  {pendingCount}
                </div>
                <p className="text-[11px] text-text-muted mt-1">Ready for scheduled slot</p>
              </CardContent>
            </Card>

            {/* Ready/Uploaded Card */}
            <Card className="bg-surface border-border/80 hover:border-border transition-colors">
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-xs font-mono font-medium text-text-muted uppercase tracking-wider">
                  Published
                </CardTitle>
                <Upload className="w-4 h-4 text-success" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-text font-mono">
                  {uploadedCount}
                </div>
                <p className="text-[11px] text-text-muted mt-1">Live on YouTube Shorts</p>
              </CardContent>
            </Card>

            {/* Failed Card */}
            <Card className="bg-surface border-border/80 hover:border-border transition-colors">
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-xs font-mono font-medium text-text-muted uppercase tracking-wider">
                  Failed Jobs
                </CardTitle>
                <AlertCircle className="w-4 h-4 text-danger" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-text font-mono">
                  {failedCount}
                </div>
                <p className="text-[11px] text-text-muted mt-1">Errors requiring retry</p>
              </CardContent>
            </Card>

            {/* Total Processed Card */}
            <Card className="bg-surface border-border/80 hover:border-border transition-colors">
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-xs font-mono font-medium text-text-muted uppercase tracking-wider">
                  Total Managed
                </CardTitle>
                <Film className="w-4 h-4 text-info" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-text font-mono">
                  {totalProcessed}
                </div>
                <p className="text-[11px] text-text-muted mt-1">Cloud pipeline throughput</p>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {/* Processing Overview Breakdown Bar */}
      {totalProcessed > 0 && (
        <Card className="bg-surface border-border/80 p-4">
          <div className="flex flex-wrap items-center justify-between text-xs mb-2 gap-2">
            <span className="font-mono font-medium text-text-muted uppercase tracking-wider">
              Pipeline Distribution
            </span>
            <div className="flex items-center gap-4 text-[11px] font-mono">
              <span className="inline-flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-success" />
                Published ({Math.round(uploadedPct)}%)
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-warning" />
                Pending ({Math.round(pendingPct)}%)
              </span>
              {failedCount > 0 && (
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-danger" />
                  Failed ({Math.round(failedPct)}%)
                </span>
              )}
            </div>
          </div>
          <div className="h-2 w-full bg-surface-elevated rounded-full overflow-hidden flex gap-0.5">
            <div style={{ width: `${uploadedPct}%` }} className="bg-success h-full transition-all" />
            <div style={{ width: `${pendingPct}%` }} className="bg-warning h-full transition-all" />
            <div style={{ width: `${failedPct}%` }} className="bg-danger h-full transition-all" />
          </div>
        </Card>
      )}

      {/* 2-Column Grid: Recent Videos + Recent Activity Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Videos Section (2 columns wide on desktop) */}
        <Card className="bg-surface border-border/80 lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between py-4 px-6 border-b border-border">
            <div>
              <CardTitle className="text-base font-semibold text-text">Recent Videos</CardTitle>
              <p className="text-xs text-text-muted mt-0.5">Manage and preview recently queued items</p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => navigate('/library')}
              className="text-xs text-text-muted hover:text-text flex items-center gap-1 cursor-pointer"
            >
              View library
              <ChevronRight className="w-4 h-4" />
            </Button>
          </CardHeader>

          <CardContent className="p-0">
            {videosLoading ? (
              <div className="p-6 space-y-3">
                <SkeletonTableRow />
                <SkeletonTableRow />
                <SkeletonTableRow />
              </div>
            ) : videos.length === 0 ? (
              <div className="p-12 text-center flex flex-col items-center">
                <div className="w-12 h-12 rounded-xl bg-surface-elevated flex items-center justify-center text-text-muted mb-3">
                  <Film className="w-6 h-6 opacity-40" />
                </div>
                <h4 className="text-sm font-semibold text-text">No videos in library yet</h4>
                <p className="text-xs text-text-muted mt-1 max-w-sm">
                  Paste an Instagram Reel or YouTube URL to begin downloading and automating.
                </p>
                <Button
                  type="button"
                  size="sm"
                  onClick={() => navigate('/create')}
                  className="mt-4 bg-accent text-accent-foreground text-xs font-semibold cursor-pointer"
                >
                  Create First Reel
                </Button>
              </div>
            ) : (
              <div className="divide-y divide-border/60">
                {videos.map((v) => (
                  <div 
                    key={v.id} 
                    className="p-4 sm:px-6 flex items-center gap-4 hover:bg-surface-elevated/40 transition-colors group"
                  >
                    {/* Thumbnail / Play Button */}
                    <div 
                      onClick={() => setInspectVideo(v)}
                      className="relative w-20 h-14 bg-surface-elevated rounded-lg border border-border/80 overflow-hidden shrink-0 cursor-pointer flex items-center justify-center group/thumb"
                    >
                      {v.thumbnail_url ? (
                        <img 
                          src={v.thumbnail_url} 
                          alt={v.title} 
                          className="w-full h-full object-cover group-hover/thumb:scale-105 transition-transform" 
                        />
                      ) : (
                        <Film className="w-5 h-5 text-zinc-500" />
                      )}
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/thumb:opacity-100 transition-opacity flex items-center justify-center">
                        <Play className="w-5 h-5 text-white fill-white" />
                      </div>
                    </div>

                    {/* Title & Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p 
                          onClick={() => setInspectVideo(v)}
                          className="text-sm font-medium text-text truncate hover:text-accent cursor-pointer transition-colors"
                        >
                          {v.title || 'Untitled Video'}
                        </p>
                      </div>

                      <div className="flex flex-wrap items-center gap-2 mt-1">
                        <span className={`text-[10px] uppercase font-mono px-2 py-0.5 rounded-full font-bold inline-flex items-center ${
                          v.status === 'uploaded' || v.status === 'published' ? 'bg-success/10 text-success border border-success/20' :
                          v.status === 'failed' ? 'bg-danger/10 text-danger border border-danger/20' :
                          v.status === 'uploading' ? 'bg-info/10 text-info border border-info/20' :
                          'bg-warning/10 text-warning border border-warning/20'
                        }`}>
                          {(v.status === 'uploaded' || v.status === 'published') && <CheckCircle2 className="w-3 h-3 mr-1" />}
                          {v.status === 'failed' && <AlertCircle className="w-3 h-3 mr-1" />}
                          {v.status || 'Pending'}
                        </span>

                        {(v.schedule_time || v.scheduled_time) && (
                          <span className="text-[11px] text-text-muted flex items-center gap-1 font-mono">
                            <Calendar className="w-3 h-3" />
                            {format(new Date(v.schedule_time || v.scheduled_time), 'MMM d, h:mm a')}
                          </span>
                        )}

                        {v.created_at && (
                          <span className="text-[11px] text-text-muted hidden sm:inline">
                            • {formatDistanceToNow(new Date(v.created_at), { addSuffix: true })}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Contextual Action Buttons */}
                    <div className="flex items-center gap-1.5 shrink-0">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setInspectVideo(v)}
                        className="text-xs text-text-muted hover:text-text hidden md:inline-flex cursor-pointer"
                      >
                        Preview
                      </Button>

                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setConvertingVideo(v)}
                        className="text-xs text-text-muted hover:text-accent cursor-pointer"
                        title="Convert Aspect Ratio"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                      </Button>

                      {v.status !== 'uploaded' && v.status !== 'published' && (
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => setPublishingVideo(v)}
                          className="text-xs bg-accent/15 text-accent hover:bg-accent hover:text-accent-foreground border border-accent/20 cursor-pointer hidden sm:inline-flex"
                        >
                          Publish
                        </Button>
                      )}

                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setDeletingVideo(v)}
                        className="text-xs text-zinc-500 hover:text-danger hover:bg-danger/10 cursor-pointer"
                        title="Delete Video"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Activity Feed (1 column on desktop) */}
        <Card className="bg-surface border-border/80 flex flex-col">
          <CardHeader className="flex flex-row items-center justify-between py-4 px-6 border-b border-border">
            <div>
              <CardTitle className="text-base font-semibold text-text flex items-center gap-2">
                <Activity className="w-4 h-4 text-accent" />
                Live Activity
              </CardTitle>
              <p className="text-xs text-text-muted mt-0.5">Real-time pipeline events</p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => navigate('/logs')}
              className="text-xs text-text-muted hover:text-text flex items-center gap-1 cursor-pointer"
            >
              All logs
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Button>
          </CardHeader>

          <CardContent className="p-4 flex-1">
            {logsLoading ? (
              <div className="space-y-3 py-2">
                <div className="h-10 bg-surface-elevated animate-pulse rounded-lg" />
                <div className="h-10 bg-surface-elevated animate-pulse rounded-lg" />
                <div className="h-10 bg-surface-elevated animate-pulse rounded-lg" />
              </div>
            ) : activityEvents.length === 0 ? (
              <div className="py-12 text-center text-xs text-text-muted">
                <Activity className="w-6 h-6 opacity-30 mx-auto mb-2" />
                <p>No activity recorded yet</p>
                <p className="text-[11px] opacity-70 mt-1">Events will appear as videos process</p>
              </div>
            ) : (
              <div className="space-y-3">
                {activityEvents.map((evt, idx) => (
                  <div 
                    key={evt.id || idx}
                    className="p-3 rounded-lg bg-surface-elevated/60 border border-border/60 hover:border-border transition-colors text-xs"
                  >
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      {getEventBadge(evt.event_type)}
                      <span className="text-[10px] font-mono text-text-muted">
                        {evt.created_at ? formatDistanceToNow(new Date(evt.created_at), { addSuffix: true }) : ''}
                      </span>
                    </div>
                    <p className="text-text font-medium line-clamp-2">
                      {evt.message || evt.event_type}
                    </p>
                    {evt.video_library?.title && (
                      <p className="text-[11px] text-text-muted mt-1 truncate">
                        Video: {evt.video_library.title}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Modals & Dialogs */}
      {inspectVideo && (
        <VideoPreviewModal
          video={inspectVideo}
          onClose={() => setInspectVideo(null)}
          onConvert={(v) => {
            setInspectVideo(null);
            setConvertingVideo(v);
          }}
          onPublish={(v) => {
            setInspectVideo(null);
            setPublishingVideo(v);
          }}
          onDelete={(v) => {
            setInspectVideo(null);
            setDeletingVideo(v);
          }}
        />
      )}

      {convertingVideo && (
        <ConvertRatioModal
          video={convertingVideo}
          isOpen={Boolean(convertingVideo)}
          onClose={() => setConvertingVideo(null)}
          isConverting={convertMutation.isPending}
          onConvert={(id, ratio) => convertMutation.mutate({ id, ratio })}
        />
      )}

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={Boolean(deletingVideo)}
        title="Delete this video?"
        description={`This will permanently remove "${deletingVideo?.title || 'this video'}" from Supabase Cloud Storage and database records.`}
        confirmText="Delete Video"
        confirmVariant="danger"
        isLoading={deleteMutation.isPending}
        onClose={() => setDeletingVideo(null)}
        onConfirm={() => deletingVideo && deleteMutation.mutate(deletingVideo.id)}
      />

      {/* Publish Confirmation Dialog */}
      <ConfirmDialog
        isOpen={Boolean(publishingVideo)}
        title="Publish to YouTube Shorts now?"
        description={`This will publish "${publishingVideo?.title || 'this video'}" immediately to your connected YouTube channel.`}
        confirmText="Publish to YouTube"
        confirmVariant="primary"
        icon="info"
        isLoading={publishMutation.isPending}
        onClose={() => setPublishingVideo(null)}
        onConfirm={() => publishingVideo && publishMutation.mutate(publishingVideo.id)}
      />
    </motion.div>
  );
}
