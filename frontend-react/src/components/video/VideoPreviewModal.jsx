import React, { useState, useRef } from 'react';
import { X, Play, Pause, Volume2, VolumeX, Maximize, RefreshCw, Upload, Trash2, ExternalLink, CheckCircle2, AlertTriangle, Clock } from 'lucide-react';
import { Button } from '../ui/Button';
import { formatDistanceToNow, format } from 'date-fns';

export function VideoPreviewModal({
  video,
  onClose,
  onConvert,
  onPublish,
  onDelete,
}) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const videoRef = useRef(null);

  if (!video) return null;

  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const toggleMute = () => {
    if (videoRef.current) {
      videoRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  const handleSeek = (e) => {
    const time = parseFloat(e.target.value);
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  const toggleFullscreen = () => {
    if (videoRef.current) {
      if (videoRef.current.requestFullscreen) {
        videoRef.current.requestFullscreen();
      }
    }
  };

  const formatTime = (secs) => {
    if (isNaN(secs)) return '0:00';
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  const videoSrc = video.storage_url || video.video_url || video.url || '';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div 
        className="w-full max-w-4xl max-h-[90vh] bg-surface border border-border rounded-xl shadow-2xl overflow-hidden flex flex-col md:flex-row"
        role="dialog"
        aria-modal="true"
      >
        {/* Left Side: Video Preview Player */}
        <div className="flex-1 bg-black flex flex-col items-center justify-center relative min-h-[320px] md:min-h-[500px]">
          {videoSrc ? (
            <div className="relative w-full h-full flex items-center justify-center group">
              <video
                ref={videoRef}
                src={videoSrc}
                poster={video.thumbnail_url}
                className="max-h-[500px] w-auto max-w-full object-contain rounded-lg"
                onTimeUpdate={handleTimeUpdate}
                onLoadedMetadata={handleLoadedMetadata}
                onEnded={() => setIsPlaying(false)}
                onClick={togglePlay}
                playsInline
              />

              {/* Center Play overlay */}
              {!isPlaying && (
                <button
                  type="button"
                  onClick={togglePlay}
                  className="absolute p-4 rounded-full bg-black/60 text-white hover:bg-black/80 hover:scale-110 transition-all cursor-pointer"
                  aria-label="Play Video"
                >
                  <Play className="w-8 h-8 fill-white translate-x-0.5" />
                </button>
              )}

              {/* Player Controls Bar */}
              <div className="absolute bottom-0 inset-x-0 p-3 bg-gradient-to-t from-black/90 via-black/50 to-transparent flex items-center gap-3 opacity-0 group-hover:opacity-100 transition-opacity">
                <button 
                  type="button" 
                  onClick={togglePlay} 
                  className="text-white hover:text-accent transition-colors"
                >
                  {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </button>

                <span className="text-[11px] font-mono text-zinc-300">
                  {formatTime(currentTime)} / {formatTime(duration)}
                </span>

                <input
                  type="range"
                  min="0"
                  max={duration || 100}
                  step="0.1"
                  value={currentTime}
                  onChange={handleSeek}
                  className="flex-1 h-1 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-accent"
                />

                <button 
                  type="button" 
                  onClick={toggleMute} 
                  className="text-white hover:text-accent transition-colors"
                >
                  {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                </button>

                <button 
                  type="button" 
                  onClick={toggleFullscreen} 
                  className="text-white hover:text-accent transition-colors"
                >
                  <Maximize className="w-4 h-4" />
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center p-8 text-center">
              {video.thumbnail_url ? (
                <img 
                  src={video.thumbnail_url} 
                  alt={video.title} 
                  className="max-h-72 rounded-lg border border-border object-contain mb-3" 
                />
              ) : (
                <div className="w-20 h-20 rounded-xl bg-surface-elevated flex items-center justify-center text-text-muted mb-3">
                  <Play className="w-8 h-8 opacity-40" />
                </div>
              )}
              <p className="text-xs text-text-muted">Direct stream preview not available. File stored in cloud bucket.</p>
            </div>
          )}
        </div>

        {/* Right Side: Metadata & Actions */}
        <div className="w-full md:w-88 flex flex-col bg-surface border-t md:border-t-0 md:border-l border-border max-h-[500px]">
          {/* Header */}
          <div className="p-4 border-b border-border flex items-center justify-between">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-text-muted">
              Video Inspector
            </span>
            <button
              type="button"
              onClick={onClose}
              className="p-1 text-text-muted hover:text-text rounded-md transition-colors"
              aria-label="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Details Scrollable Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <div>
              <h3 className="text-base font-semibold text-text leading-snug">
                {video.title || 'Untitled Video'}
              </h3>
              <div className="flex items-center gap-2 mt-2">
                <span className={`text-[10px] uppercase font-mono px-2 py-0.5 rounded-full font-bold inline-flex items-center ${
                  video.status === 'uploaded' ? 'bg-success/10 text-success border border-success/20' :
                  video.status === 'failed' ? 'bg-danger/10 text-danger border border-danger/20' :
                  video.status === 'uploading' ? 'bg-info/10 text-info border border-info/20 animate-pulse' :
                  'bg-warning/10 text-warning border border-warning/20'
                }`}>
                  {video.status === 'uploaded' && <CheckCircle2 className="w-3 h-3 mr-1" />}
                  {video.status === 'failed' && <AlertTriangle className="w-3 h-3 mr-1" />}
                  {video.status || 'Pending'}
                </span>
                {video.created_at && (
                  <span className="text-[11px] text-text-muted">
                    {formatDistanceToNow(new Date(video.created_at), { addSuffix: true })}
                  </span>
                )}
              </div>
            </div>

            {video.description && (
              <div>
                <label className="text-[11px] font-mono uppercase text-text-muted block mb-1">
                  Description
                </label>
                <p className="text-xs text-text-muted bg-surface-elevated/60 p-3 rounded-lg border border-border/50 max-h-28 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                  {video.description}
                </p>
              </div>
            )}

            {video.schedule_time && (
              <div className="p-2.5 rounded-lg bg-surface-elevated/60 border border-border/50 flex items-center gap-2.5 text-xs text-text-muted">
                <Clock className="w-4 h-4 text-warning shrink-0" />
                <div>
                  <span className="text-text font-medium block">Scheduled Posting</span>
                  <span>{format(new Date(video.schedule_time), 'PPp')}</span>
                </div>
              </div>
            )}

            {video.youtube_video_id && (
              <a
                href={`https://youtube.com/shorts/${video.youtube_video_id}`}
                target="_blank"
                rel="noreferrer"
                className="p-2.5 rounded-lg bg-danger/10 border border-danger/20 flex items-center justify-between text-xs text-danger hover:bg-danger/15 transition-colors"
              >
                <span>View on YouTube Shorts</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            )}

            {video.hashtags && video.hashtags.length > 0 && (
              <div>
                <label className="text-[11px] font-mono uppercase text-text-muted block mb-1.5">
                  Hashtags ({video.hashtags.length})
                </label>
                <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
                  {video.hashtags.map((tag, idx) => (
                    <span 
                      key={idx}
                      className="text-[11px] font-mono px-2 py-0.5 rounded-md bg-surface-elevated border border-border text-zinc-300"
                    >
                      {tag.startsWith('#') ? tag : `#${tag}`}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Action Bar */}
          <div className="p-4 border-t border-border bg-surface-elevated/40 flex flex-col gap-2">
            <div className="grid grid-cols-2 gap-2">
              {onConvert && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => onConvert(video)}
                  className="text-xs flex items-center justify-center gap-1.5"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Convert Ratio
                </Button>
              )}
              {onPublish && video.status !== 'uploaded' && (
                <Button
                  type="button"
                  size="sm"
                  onClick={() => onPublish(video)}
                  className="text-xs bg-accent text-accent-foreground flex items-center justify-center gap-1.5"
                >
                  <Upload className="w-3.5 h-3.5" />
                  Publish Now
                </Button>
              )}
            </div>

            {onDelete && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => onDelete(video)}
                className="text-xs text-danger hover:bg-danger/10 hover:text-danger flex items-center justify-center gap-1.5 w-full mt-1"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Delete Video
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
