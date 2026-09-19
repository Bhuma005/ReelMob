import React, { useState, useRef } from 'react';
import { 
  X, Play, Pause, Volume2, VolumeX, Maximize, RefreshCw, Upload, Trash2, 
  ExternalLink, CheckCircle2, AlertTriangle, Clock, Download, Copy, Check, Film
} from 'lucide-react';
import { Button } from '../ui/Button';
import { formatDistanceToNow, format } from 'date-fns';
import { toast } from 'sonner';

export function VideoPreviewModal({
  video,
  onClose,
  onConvert,
  onPublish,
  onDelete,
}) {
  const [videoError, setVideoError] = useState(false);
  const [copied, setCopied] = useState(false);
  const videoRef = useRef(null);

  if (!video) return null;

  const videoSrc = 
    video.storage_url || 
    video.public_url || 
    video.video_url || 
    video.url || 
    video.signed_url || 
    (video.id ? `/api/dashboard/videos/${video.id}/stream` : '') || 
    '';

  const copyVideoLink = () => {
    if (!videoSrc) return;
    const fullUrl = videoSrc.startsWith('http') ? videoSrc : `${window.location.origin}${videoSrc}`;
    navigator.clipboard.writeText(fullUrl);
    setCopied(true);
    toast.success('Video stream link copied to clipboard');
    setTimeout(() => setCopied(false), 2000);
  };

  const filename = video.storage_path 
    ? video.storage_path.split('/').pop() 
    : (video.title ? `${video.title.replace(/[^a-zA-Z0-9_\-]/g, '_')}.mp4` : 'video.mp4');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-md animate-in fade-in duration-150">
      <div 
        className="w-full max-w-5xl max-h-[92vh] bg-surface border border-border rounded-2xl shadow-2xl overflow-hidden flex flex-col"
        role="dialog"
        aria-modal="true"
      >
        {/* YouTube Studio Modal Header */}
        <div className="px-6 py-4 border-b border-border bg-surface-elevated/40 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent/15 border border-accent/20 flex items-center justify-center text-accent">
              <Film className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-text leading-none">Video Details</h2>
                <span className={`text-[10px] uppercase font-mono px-2 py-0.5 rounded-full font-bold inline-flex items-center ${
                  video.status === 'uploaded' || video.status === 'published' ? 'bg-success/10 text-success border border-success/20' :
                  video.status === 'failed' ? 'bg-danger/10 text-danger border border-danger/20' :
                  video.status === 'uploading' ? 'bg-info/10 text-info border border-info/20 animate-pulse' :
                  'bg-warning/10 text-warning border border-warning/20'
                }`}>
                  {(video.status === 'uploaded' || video.status === 'published') && <CheckCircle2 className="w-3 h-3 mr-1" />}
                  {video.status === 'failed' && <AlertTriangle className="w-3 h-3 mr-1" />}
                  {video.status || 'Ready'}
                </span>
              </div>
              <p className="text-xs text-text-muted mt-0.5">
                {video.created_at ? `Uploaded ${formatDistanceToNow(new Date(video.created_at), { addSuffix: true })}` : 'ReelsMob Video Library'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {videoSrc && (
              <a
                href={videoSrc}
                target="_blank"
                rel="noopener noreferrer"
                download={filename}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-border bg-surface hover:bg-surface-elevated text-text transition-colors"
                title="Download or open raw video file"
              >
                <Download className="w-3.5 h-3.5 text-accent" />
                <span className="hidden sm:inline">Download</span>
              </a>
            )}
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 text-text-muted hover:text-text hover:bg-surface-elevated rounded-lg transition-colors cursor-pointer"
              aria-label="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* YouTube Studio 2-Column Grid */}
        <div className="flex-1 overflow-y-auto p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Metadata & Settings (7 of 12 columns) */}
          <div className="lg:col-span-7 space-y-5">
            {/* Title Block */}
            <div className="rounded-xl border border-border bg-surface-elevated/40 p-4 space-y-1.5 focus-within:border-accent/60 transition-colors">
              <label className="text-[11px] font-mono font-bold uppercase tracking-wider text-text-muted flex justify-between">
                <span>Title (required)</span>
                <span className="text-[10px] text-text-muted/70">{video.title?.length || 0} characters</span>
              </label>
              <p className="text-sm font-semibold text-text leading-relaxed select-text">
                {video.title || 'Untitled Video'}
              </p>
            </div>

            {/* Description Block */}
            <div className="rounded-xl border border-border bg-surface-elevated/40 p-4 space-y-1.5 focus-within:border-accent/60 transition-colors">
              <label className="text-[11px] font-mono font-bold uppercase tracking-wider text-text-muted flex justify-between">
                <span>Description</span>
                <span className="text-[10px] text-text-muted/70">{video.description?.length || 0} characters</span>
              </label>
              <div className="text-xs text-text-muted leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto p-2.5 rounded-lg bg-surface/60 border border-border/40 select-text">
                {video.description || 'No description provided.'}
              </div>
            </div>

            {/* Schedule & Visibility Block */}
            <div className="rounded-xl border border-border bg-surface-elevated/40 p-4 space-y-3">
              <label className="text-[11px] font-mono font-bold uppercase tracking-wider text-text-muted block">
                Visibility & Schedule
              </label>
              {video.schedule_time ? (
                <div className="flex items-center gap-3 p-3 rounded-lg bg-warning/5 border border-warning/20 text-xs">
                  <Clock className="w-4 h-4 text-warning shrink-0" />
                  <div>
                    <span className="font-semibold text-text block">Scheduled to publish</span>
                    <span className="text-text-muted">{format(new Date(video.schedule_time), 'PPPp')}</span>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-3 p-3 rounded-lg bg-surface/60 border border-border/40 text-xs text-text-muted">
                  <Clock className="w-4 h-4 text-text-muted shrink-0" />
                  <span>Not scheduled — ready for immediate publishing or conversion.</span>
                </div>
              )}

              {video.youtube_video_id && (
                <a
                  href={`https://youtube.com/shorts/${video.youtube_video_id}`}
                  target="_blank"
                  rel="noreferrer"
                  className="p-3 rounded-lg bg-danger/10 border border-danger/20 flex items-center justify-between text-xs text-danger hover:bg-danger/15 transition-colors font-medium"
                >
                  <span>View on YouTube Shorts</span>
                  <ExternalLink className="w-4 h-4" />
                </a>
              )}
            </div>

            {/* Tags / Hashtags */}
            {video.hashtags && video.hashtags.length > 0 && (
              <div className="rounded-xl border border-border bg-surface-elevated/40 p-4 space-y-2">
                <label className="text-[11px] font-mono font-bold uppercase tracking-wider text-text-muted block">
                  Hashtags ({video.hashtags.length})
                </label>
                <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
                  {video.hashtags.map((tag, idx) => (
                    <span 
                      key={idx}
                      className="text-xs font-mono px-2.5 py-1 rounded-md bg-surface border border-border text-zinc-300 select-text"
                    >
                      {tag.startsWith('#') ? tag : `#${tag}`}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right Column: YouTube Studio Video Preview Card (5 of 12 columns) */}
          <div className="lg:col-span-5 space-y-4">
            <div className="rounded-2xl border border-border bg-surface-elevated/60 p-4 space-y-4 shadow-xl">
              {/* Video Player Display Container */}
              <div className="relative w-full aspect-[9/16] max-h-[380px] mx-auto bg-black rounded-xl overflow-hidden border border-border shadow-2xl flex items-center justify-center">
                {videoSrc && !videoError ? (
                  <video
                    ref={videoRef}
                    src={videoSrc}
                    poster={video.thumbnail_url}
                    controls
                    playsInline
                    className="w-full h-full object-contain"
                    onError={() => setVideoError(true)}
                  />
                ) : (
                  <div className="flex flex-col items-center justify-center p-6 text-center">
                    {video.thumbnail_url ? (
                      <img 
                        src={video.thumbnail_url} 
                        alt={video.title} 
                        className="max-h-56 rounded-lg object-contain mb-3" 
                      />
                    ) : (
                      <div className="w-16 h-16 rounded-full bg-surface flex items-center justify-center text-text-muted mb-3">
                        <Film className="w-8 h-8 opacity-40" />
                      </div>
                    )}
                    <p className="text-xs text-text-muted max-w-[200px] mb-3">
                      {videoError 
                        ? 'Inline stream could not decode. Use the direct link below.' 
                        : 'Preview stream stored in cloud bucket.'}
                    </p>
                    {videoSrc && (
                      <a
                        href={videoSrc}
                        target="_blank"
                        rel="noopener noreferrer"
                        download={filename}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent text-accent-foreground text-xs font-medium hover:bg-accent/90"
                      >
                        <Download className="w-3.5 h-3.5" /> Open / Download
                      </a>
                    )}
                  </div>
                )}
              </div>

              {/* YouTube Studio Link & File Details Card */}
              <div className="p-3 rounded-xl bg-surface/80 border border-border/60 space-y-2.5 text-xs">
                {/* Video Link */}
                <div className="space-y-1">
                  <span className="text-[10px] font-mono uppercase text-text-muted block">
                    Video link
                  </span>
                  <div className="flex items-center justify-between gap-2 p-2 rounded-lg bg-surface-elevated border border-border/50">
                    <a
                      href={videoSrc || '#'}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent hover:underline font-mono text-[11px] truncate flex-1"
                      title={videoSrc}
                    >
                      {videoSrc ? (videoSrc.length > 32 ? `${videoSrc.slice(0, 32)}...` : videoSrc) : 'Direct stream link'}
                    </a>
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        type="button"
                        onClick={copyVideoLink}
                        disabled={!videoSrc}
                        className="p-1 rounded text-text-muted hover:text-text hover:bg-surface transition-colors cursor-pointer"
                        title="Copy video link"
                      >
                        {copied ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                      {videoSrc && (
                        <a
                          href={videoSrc}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1 rounded text-text-muted hover:text-text hover:bg-surface transition-colors"
                          title="Open video in new tab"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      )}
                    </div>
                  </div>
                </div>

                {/* Filename & Quality Badges */}
                <div className="grid grid-cols-2 gap-2 pt-1 border-t border-border/40 text-[11px]">
                  <div>
                    <span className="text-[10px] font-mono uppercase text-text-muted block">Filename</span>
                    <span className="font-mono text-zinc-300 truncate block" title={filename}>
                      {filename.length > 18 ? `${filename.slice(0, 18)}...` : filename}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] font-mono uppercase text-text-muted block">Video Quality</span>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="px-1.5 py-0.5 rounded bg-accent/15 border border-accent/25 text-accent text-[10px] font-mono font-bold">
                        1080p HD
                      </span>
                      <span className="px-1.5 py-0.5 rounded bg-surface border border-border text-zinc-400 text-[10px] font-mono">
                        9:16
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Direct Open / Download Button in Preview Card */}
              {videoSrc && (
                <a
                  href={videoSrc}
                  target="_blank"
                  rel="noopener noreferrer"
                  download={filename}
                  className="w-full py-2 px-3 rounded-lg border border-border bg-surface hover:bg-surface-elevated text-text text-xs font-medium flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                >
                  <Download className="w-3.5 h-3.5 text-accent" />
                  Download / Open Video in New Tab
                </a>
              )}
            </div>
          </div>
        </div>

        {/* Modal Bottom Action Footer */}
        <div className="px-6 py-4 border-t border-border bg-surface-elevated/60 flex items-center justify-between shrink-0 gap-3">
          <div>
            {onDelete && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => onDelete(video)}
                className="text-xs text-danger hover:bg-danger/10 hover:text-danger flex items-center gap-1.5 cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Delete Video
              </Button>
            )}
          </div>

          <div className="flex items-center gap-2">
            {onConvert && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onConvert(video)}
                className="text-xs flex items-center gap-1.5 cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Convert Ratio
              </Button>
            )}
            {onPublish && video.status !== 'uploaded' && video.status !== 'published' && (
              <Button
                type="button"
                size="sm"
                onClick={() => onPublish(video)}
                className="text-xs bg-accent text-accent-foreground hover:bg-accent/90 flex items-center gap-1.5 font-semibold cursor-pointer"
              >
                <Upload className="w-3.5 h-3.5" />
                Publish Now
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
