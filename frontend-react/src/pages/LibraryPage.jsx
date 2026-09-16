import React, { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { dashboardApi } from '../api/dashboard';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { SkeletonCard, SkeletonTableRow } from '../components/ui/Skeleton';
import { Tooltip } from '../components/ui/Tooltip';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { VideoPreviewModal } from '../components/video/VideoPreviewModal';
import { ConvertRatioModal } from '../components/video/ConvertRatioModal';
import { VideoEditorModal } from '../components/video/VideoEditorModal';
import { 
  Trash2, Film, RefreshCw, CheckCircle2, AlertTriangle, CloudOff, 
  Search, ChevronLeft, ChevronRight, ExternalLink, Play, 
  Clock, LayoutGrid, List, CheckSquare, Square, RotateCcw, Scissors, Tag, Download, FileText
} from 'lucide-react';
import { format, formatDistanceToNow } from 'date-fns';
import { toast } from 'sonner';
import { cn } from '../lib/utils';

function InlineTagEditor({ videoId, tags = [], onUpdateTags }) {
  const [isEditing, setIsEditing] = useState(false);
  const [tagInput, setTagInput] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const handleAddTag = async () => {
    const trimmed = tagInput.trim().toLowerCase();
    if (!trimmed) {
      setIsEditing(false);
      return;
    }
    if (!/^[a-zA-Z0-9_\-]+$/.test(trimmed)) {
      toast.error('Tags can only contain alphanumeric characters, underscores, and dashes');
      return;
    }
    if (trimmed.length > 30) {
      toast.error('Tag must be 30 characters or fewer');
      return;
    }
    if (tags.includes(trimmed)) {
      setTagInput('');
      setIsEditing(false);
      return;
    }
    if (tags.length >= 15) {
      toast.error('Maximum 15 tags per video');
      return;
    }

    const nextTags = [...tags, trimmed];
    setIsSaving(true);
    try {
      await onUpdateTags(videoId, nextTags);
      setTagInput('');
      setIsEditing(false);
    } catch (err) {
      toast.error('Failed to add tag: ' + (err.message || 'Network error'));
    } finally {
      setIsSaving(false);
    }
  };

  const handleRemoveTag = async (tagToRemove, e) => {
    e.stopPropagation();
    const nextTags = tags.filter(t => t !== tagToRemove);
    try {
      await onUpdateTags(videoId, nextTags);
    } catch (err) {
      toast.error('Failed to remove tag: ' + (err.message || 'Network error'));
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-1 mt-1.5" onClick={(e) => e.stopPropagation()}>
      {tags.map((t) => (
        <span
          key={t}
          className="inline-flex items-center gap-0.5 text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface-elevated text-text-muted border border-border group/tag hover:border-accent/50"
        >
          #{t}
          <button
            type="button"
            onClick={(e) => handleRemoveTag(t, e)}
            className="hover:text-danger opacity-60 group-hover/tag:opacity-100 transition-opacity ml-0.5 cursor-pointer leading-none"
            title={`Remove #${t}`}
          >
            ×
          </button>
        </span>
      ))}

      {isEditing ? (
        <input
          type="text"
          autoFocus
          disabled={isSaving}
          value={tagInput}
          onChange={(e) => setTagInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              handleAddTag();
            } else if (e.key === 'Escape') {
              setIsEditing(false);
              setTagInput('');
            }
          }}
          onBlur={handleAddTag}
          placeholder="tag..."
          className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface border border-accent text-text w-16 focus:outline-none"
        />
      ) : (
        tags.length < 15 && (
          <button
            type="button"
            onClick={() => setIsEditing(true)}
            className="text-[10px] font-mono px-1.5 py-0.5 rounded text-text-muted hover:text-accent hover:bg-surface-elevated border border-dashed border-border transition-colors cursor-pointer"
          >
            + tag
          </button>
        )
      )}
    </div>
  );
}

function BulkTagModal({ isOpen, count, onClose, onApply }) {
  const [tag, setTag] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    const clean = tag.trim().toLowerCase();
    if (!clean) return;
    if (!/^[a-zA-Z0-9_\-]+$/.test(clean)) {
      toast.error('Tags can only contain alphanumeric characters, underscores, and dashes');
      return;
    }
    if (clean.length > 30) {
      toast.error('Tag must be 30 characters or fewer');
      return;
    }
    setIsSubmitting(true);
    try {
      await onApply(clean);
      setTag('');
      onClose();
    } catch (err) {
      toast.error('Failed to apply tags: ' + (err.message || 'Error'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-xs">
      <div className="w-full max-w-sm bg-surface border border-border rounded-xl p-5 space-y-4 shadow-xl">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <Tag className="w-4 h-4 text-accent" />
          Add Tag to {count} {count === 1 ? 'Video' : 'Videos'}
        </h3>
        <p className="text-xs text-text-muted">
          Enter a tag to append to all selected videos in your library.
        </p>
        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="text"
            autoFocus
            value={tag}
            onChange={(e) => setTag(e.target.value)}
            placeholder="e.g. viral, hook, tutorial"
            className="w-full bg-surface-elevated border border-border rounded-lg px-3 py-2 text-xs text-text font-mono placeholder:text-text-muted focus:outline-none focus:border-accent"
          />
          <div className="flex items-center justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onClose}
              disabled={isSubmitting}
              className="text-xs"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={isSubmitting || !tag.trim()}
              className="text-xs bg-accent text-accent-foreground hover:bg-accent/90"
            >
              {isSubmitting ? 'Applying...' : 'Apply Tag'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function LibraryPage() {
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState('grid'); // 'grid' | 'table'
  const [activeStatus, setActiveStatus] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [page, setPage] = useState(1);
  
  // Selection & modals state
  const [selectedIds, setSelectedIds] = useState([]);
  const [previewVideo, setPreviewVideo] = useState(null);
  const [convertingVideo, setConvertingVideo] = useState(null);
  const [editingVideo, setEditingVideo] = useState(null);
  const [publishingVideo, setPublishingVideo] = useState(null);
  const [deletingVideo, setDeletingVideo] = useState(null);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const [isBulkTagging, setIsBulkTagging] = useState(false);

  const limit = viewMode === 'grid' ? 12 : 20;

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const { data: videosData, isLoading } = useQuery({
    queryKey: ['dashboardVideos', page, limit, activeStatus, debouncedSearch],
    queryFn: () => dashboardApi.getVideos({ page, limit, status: activeStatus, search: debouncedSearch }),
    refetchInterval: 8000
  });

  // Optimistic Deletion Mutation
  const deleteMutation = useMutation({
    mutationFn: (id) => dashboardApi.deleteVideo(id),
    onMutate: async (deletedId) => {
      await queryClient.cancelQueries(['dashboardVideos']);
      const previousData = queryClient.getQueryData(['dashboardVideos', page, limit, activeStatus, debouncedSearch]);
      
      if (previousData) {
        queryClient.setQueryData(['dashboardVideos', page, limit, activeStatus, debouncedSearch], {
          ...previousData,
          videos: previousData.videos.filter((v) => v.id !== deletedId),
          total: Math.max(0, previousData.total - 1)
        });
      }
      return { previousData };
    },
    onError: (err, deletedId, context) => {
      if (context?.previousData) {
        queryClient.setQueryData(['dashboardVideos', page, limit, activeStatus, debouncedSearch], context.previousData);
      }
      toast.error(err.message || 'Failed to delete video');
    },
    onSuccess: () => {
      toast.success('Video removed from library');
      setDeletingVideo(null);
      if (previewVideo) setPreviewVideo(null);
      queryClient.invalidateQueries(['dashboardVideos']);
      queryClient.invalidateQueries(['dashboardStats']);
    }
  });

  // Bulk Delete
  const handleBulkDelete = async () => {
    if (selectedIds.length === 0) return;
    try {
      const results = await Promise.allSettled(
        selectedIds.map(id => dashboardApi.deleteVideo(id))
      );
      const successful = results.filter(r => r.status === 'fulfilled').length;
      toast.success(`Deleted ${successful} of ${selectedIds.length} videos`);
      setSelectedIds([]);
      setIsBulkDeleting(false);
      queryClient.invalidateQueries(['dashboardVideos']);
      queryClient.invalidateQueries(['dashboardStats']);
    } catch (err) {
      toast.error('Bulk deletion failed: ' + err.message);
    }
  };

  const handleBulkTag = async (newTag) => {
    if (selectedIds.length === 0) return;
    try {
      const updates = selectedIds.map(id => {
        const vid = rawVideos.find(v => v.id === id);
        const existingTags = Array.isArray(vid?.tags) ? vid.tags : [];
        if (!existingTags.includes(newTag)) {
          const nextTags = [...existingTags, newTag];
          return dashboardApi.updateVideoTags(id, nextTags);
        }
        return Promise.resolve();
      });
      await Promise.all(updates);
      queryClient.invalidateQueries({ queryKey: ['dashboardVideos'] });
      queryClient.invalidateQueries({ queryKey: ['dashboardAnalyticsTags'] });
      toast.success(`Tagged ${selectedIds.length} videos with #${newTag}`);
      setIsBulkTagging(false);
    } catch (err) {
      toast.error('Bulk tagging failed: ' + (err.message || 'Error'));
    }
  };

  const handleBulkExport = (exportType) => {
    if (selectedIds.length === 0) return;
    const selectedVideos = rawVideos.filter(v => selectedIds.includes(v.id));
    if (selectedVideos.length === 0) return;

    if (exportType === 'json') {
      const dataStr = JSON.stringify(selectedVideos, null, 2);
      const blob = new Blob([dataStr], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `reelsmob_videos_${Date.now()}.json`;
      link.click();
      URL.revokeObjectURL(url);
      toast.success(`Exported ${selectedVideos.length} videos as JSON`);
    } else {
      const headers = ['id', 'title', 'status', 'created_at', 'schedule_time', 'tags', 'youtube_url'];
      const rows = selectedVideos.map(v => [
        `"${(v.id || '').replace(/"/g, '""')}"`,
        `"${(v.title || '').replace(/"/g, '""')}"`,
        `"${(v.status || '').replace(/"/g, '""')}"`,
        `"${(v.created_at || '').replace(/"/g, '""')}"`,
        `"${(v.schedule_time || v.scheduled_time || '').replace(/"/g, '""')}"`,
        `"${(Array.isArray(v.tags) ? v.tags.join(';') : '').replace(/"/g, '""')}"`,
        `"${(v.youtube_url || '').replace(/"/g, '""')}"`
      ].join(','));
      const csvContent = [headers.join(','), ...rows].join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `reelsmob_videos_${Date.now()}.csv`;
      link.click();
      URL.revokeObjectURL(url);
      toast.success(`Exported ${selectedVideos.length} videos as CSV`);
    }
  };

  const publishMutation = useMutation({
    mutationFn: (id) => dashboardApi.publishVideo(id),
    onSuccess: () => {
      toast.success('Video successfully published to YouTube!');
      setPublishingVideo(null);
      if (previewVideo) setPreviewVideo(null);
      queryClient.invalidateQueries(['dashboardVideos']);
      queryClient.invalidateQueries(['dashboardStats']);
    },
    onError: (err) => toast.error(err.message || 'Failed to publish video')
  });

  const convertMutation = useMutation({
    mutationFn: ({ id, ratio }) => dashboardApi.convertVideo(id, ratio),
    onSuccess: () => {
      toast.success('Aspect ratio conversion initiated');
      setConvertingVideo(null);
      queryClient.invalidateQueries(['dashboardVideos']);
    },
    onError: (err) => toast.error(err.message || 'Failed to convert video')
  });

  const [selectedTagFilter, setSelectedTagFilter] = useState(null);

  const tagMutation = useMutation({
    mutationFn: ({ id, tags }) => dashboardApi.updateVideoTags(id, tags),
    onSuccess: (data, variables) => {
      queryClient.setQueryData(['dashboardVideos', page, limit, activeStatus, debouncedSearch], (old) => {
        if (!old?.videos) return old;
        return {
          ...old,
          videos: old.videos.map(v => v.id === variables.id ? { ...v, tags: variables.tags } : v)
        };
      });
      queryClient.invalidateQueries({ queryKey: ['dashboardVideos'] });
      queryClient.invalidateQueries({ queryKey: ['dashboardAnalyticsTags'] });
      toast.success('Tags updated');
    },
    onError: (err) => toast.error(err.message || 'Failed to update tags')
  });

  const handleUpdateTags = async (id, tags) => {
    return tagMutation.mutateAsync({ id, tags });
  };

  const rawVideos = videosData?.videos || [];
  const totalPages = videosData?.total_pages || 1;
  const totalCount = videosData?.total || 0;

  const availableTags = useMemo(() => {
    const set = new Set();
    rawVideos.forEach(v => {
      if (Array.isArray(v.tags)) {
        v.tags.forEach(t => set.add(t));
      }
    });
    return Array.from(set).sort();
  }, [rawVideos]);

  const videos = useMemo(() => {
    if (!selectedTagFilter) return rawVideos;
    return rawVideos.filter(v => Array.isArray(v.tags) && v.tags.includes(selectedTagFilter));
  }, [rawVideos, selectedTagFilter]);

  const statusTabs = [
    { key: 'all', label: 'All Videos' },
    { key: 'scheduled', label: 'Scheduled' },
    { key: 'published', label: 'Published' },
    { key: 'cleaned', label: 'Archived' },
    { key: 'failed', label: 'Failed' },
  ];

  const toggleSelectAll = () => {
    if (selectedIds.length === videos.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(videos.map(v => v.id));
    }
  };

  const toggleSelectVideo = (id) => {
    setSelectedIds(prev => 
      prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]
    );
  };

  const renderStatusBadge = (v) => {
    let badge = {
      label: v.status || 'Pending',
      className: 'bg-warning/10 text-warning border-warning/20',
      icon: <Clock className="w-3 h-3 mr-1 inline" />,
      tooltip: v.schedule_time ? `Scheduled for ${format(new Date(v.schedule_time), 'PPp')}` : 'Queued for processing'
    };

    if (v.status === 'published' || v.status === 'uploaded') {
      badge = {
        label: 'Published',
        className: 'bg-success/10 text-success border-success/20',
        icon: <CheckCircle2 className="w-3 h-3 mr-1 inline" />,
        tooltip: v.youtube_url ? `Live on YouTube: ${v.youtube_url}` : 'Successfully uploaded'
      };
    } else if (v.status === 'failed') {
      badge = {
        label: 'Failed',
        className: 'bg-danger/10 text-danger border-danger/20',
        icon: <AlertTriangle className="w-3 h-3 mr-1 inline" />,
        tooltip: v.last_error || v.error || 'Processing failed. Click Retry to re-run.'
      };
    } else if (v.status === 'uploading' || v.status === 'processing') {
      badge = {
        label: 'Processing',
        className: 'bg-info/10 text-info border-info/20',
        icon: <RefreshCw className="w-3 h-3 mr-1 inline animate-spin" />,
        tooltip: 'Currently being processed by cloud worker'
      };
    } else if (v.status === 'cleaned') {
      badge = {
        label: 'Archived',
        className: 'bg-surface text-text-muted border-border',
        icon: <CloudOff className="w-3 h-3 mr-1 inline" />,
        tooltip: 'File removed from temporary storage after successful upload'
      };
    }

    return (
      <Tooltip content={badge.tooltip}>
        <span className={cn(
          "text-[10px] uppercase font-mono px-2 py-0.5 rounded-full font-bold inline-flex items-center border cursor-help",
          badge.className
        )}>
          {badge.icon}
          {badge.label}
        </span>
      </Tooltip>
    );
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-20">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-text">
            Content Library
          </h1>
          <p className="text-xs sm:text-sm text-text-muted mt-1">
            Browse, inspect, and manage generated reels ({totalCount} total in database).
          </p>
        </div>

        {/* Search & View Mode Switcher */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 sm:w-64">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
            <input 
              type="text" 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search library..."
              className="w-full bg-surface border border-border rounded-lg pl-9 pr-4 py-2 text-xs text-text placeholder:text-text-muted focus:outline-none focus:border-accent font-mono transition-colors"
            />
            {searchTerm && (
              <button 
                onClick={() => setSearchTerm('')} 
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-text-muted hover:text-text cursor-pointer"
              >
                ✕
              </button>
            )}
          </div>

          <div className="flex items-center p-1 bg-surface-elevated rounded-lg border border-border">
            <button
              type="button"
              onClick={() => setViewMode('grid')}
              className={cn(
                "p-1.5 rounded-md transition-all cursor-pointer",
                viewMode === 'grid' ? "bg-accent text-accent-foreground shadow-xs" : "text-text-muted hover:text-text"
              )}
              title="Grid View"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => setViewMode('table')}
              className={cn(
                "p-1.5 rounded-md transition-all cursor-pointer",
                viewMode === 'table' ? "bg-accent text-accent-foreground shadow-xs" : "text-text-muted hover:text-text"
              )}
              title="Table View"
            >
              <List className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Filter Tabs & Bulk Actions Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex flex-wrap gap-1.5 p-1 bg-surface rounded-lg border border-border w-fit">
          {statusTabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => {
                setActiveStatus(tab.key);
                setPage(1);
              }}
              className={cn(
                "px-3 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer",
                activeStatus === tab.key 
                  ? "bg-accent text-accent-foreground shadow-xs" 
                  : "text-text-muted hover:text-text"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Bulk Action Controls */}
        {selectedIds.length > 0 && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex items-center gap-2 bg-surface-elevated p-1.5 px-3 rounded-lg border border-border shadow-sm text-xs"
          >
            <span className="font-mono text-accent font-semibold">
              {selectedIds.length} selected
            </span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setSelectedIds([])}
              className="text-xs h-7 text-text-muted cursor-pointer"
            >
              Deselect
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsBulkTagging(true)}
              className="text-xs h-7 border-border hover:border-accent hover:text-accent cursor-pointer flex items-center gap-1"
            >
              <Tag className="w-3.5 h-3.5" />
              Tag Selected
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => handleBulkExport('csv')}
              className="text-xs h-7 border-border hover:border-accent hover:text-accent cursor-pointer flex items-center gap-1"
              title="Export selected videos as CSV"
            >
              <Download className="w-3.5 h-3.5" />
              CSV
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => handleBulkExport('json')}
              className="text-xs h-7 border-border hover:border-accent hover:text-accent cursor-pointer flex items-center gap-1"
              title="Export selected videos as JSON"
            >
              <FileText className="w-3.5 h-3.5" />
              JSON
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={() => setIsBulkDeleting(true)}
              className="text-xs h-7 bg-danger text-white hover:bg-danger/90 cursor-pointer flex items-center gap-1"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Delete Selected
            </Button>
          </motion.div>
        )}
      </div>

      {/* Tag Filter Chips */}
      {availableTags.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 p-2 bg-surface/60 rounded-lg border border-border/80">
          <span className="text-[11px] font-mono text-text-muted flex items-center gap-1 mr-1">
            <Tag className="w-3 h-3 text-accent" /> Filter by Tag:
          </span>
          {availableTags.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setSelectedTagFilter(prev => prev === t ? null : t)}
              className={cn(
                "text-[10px] font-mono px-2 py-0.5 rounded-full border transition-all cursor-pointer",
                selectedTagFilter === t
                  ? "bg-accent text-accent-foreground border-accent font-semibold"
                  : "bg-surface-elevated text-text-muted border-border hover:border-accent/40"
              )}
            >
              #{t}
            </button>
          ))}
          {selectedTagFilter && (
            <button
              type="button"
              onClick={() => setSelectedTagFilter(null)}
              className="text-[10px] font-mono text-text-muted hover:text-text cursor-pointer underline ml-1"
            >
              Clear filter
            </button>
          )}
        </div>
      )}

      {/* Main Content: Loading, Empty, Grid or Table */}
      {isLoading ? (
        viewMode === 'grid' ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        ) : (
          <div className="bg-surface border border-border rounded-xl p-4 space-y-3">
            <SkeletonTableRow />
            <SkeletonTableRow />
            <SkeletonTableRow />
            <SkeletonTableRow />
          </div>
        )
      ) : videos.length === 0 ? (
        <Card className="bg-surface border-border p-16 text-center flex flex-col items-center justify-center">
          <Film className="w-12 h-12 text-text-muted opacity-30 mb-3" />
          <h3 className="text-base font-semibold text-text">No videos found</h3>
          <p className="text-xs text-text-muted max-w-sm mt-1">
            {searchTerm ? `No videos match "${searchTerm}" in status "${activeStatus}".` : 'No videos have been added to this filter yet.'}
          </p>
          {searchTerm && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSearchTerm('')}
              className="mt-4 text-xs cursor-pointer"
            >
              Clear Search
            </Button>
          )}
        </Card>
      ) : viewMode === 'grid' ? (
        /* GRID VIEW */
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {videos.map((v) => {
            const isSelected = selectedIds.includes(v.id);

            return (
              <Card 
                key={v.id}
                className={cn(
                  "bg-surface border-border/80 overflow-hidden hover:border-border transition-all flex flex-col justify-between group",
                  isSelected && "ring-2 ring-accent"
                )}
              >
                <div>
                  {/* Thumbnail Banner with aspect 16:9 or 9:16 */}
                  <div className="relative aspect-video bg-black overflow-hidden flex items-center justify-center">
                    {v.thumbnail_url ? (
                      <img 
                        src={v.thumbnail_url} 
                        alt={v.title} 
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                    ) : (
                      <Film className="w-8 h-8 text-text-muted opacity-40" />
                    )}

                    {/* Selection Checkbox */}
                    <div className="absolute top-2 left-2 z-10">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleSelectVideo(v.id);
                        }}
                        className={cn(
                          "w-6 h-6 rounded flex items-center justify-center transition-colors cursor-pointer",
                          isSelected ? "bg-accent text-accent-foreground" : "bg-black/60 text-white/80 hover:bg-black/80"
                        )}
                      >
                        {isSelected ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4" />}
                      </button>
                    </div>

                    {/* Play Button Overlay */}
                    <button
                      type="button"
                      onClick={() => setPreviewVideo(v)}
                      className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center cursor-pointer"
                    >
                      <div className="w-10 h-10 rounded-full bg-accent/90 text-accent-foreground flex items-center justify-center shadow-lg">
                        <Play className="w-5 h-5 fill-current ml-0.5" />
                      </div>
                    </button>
                  </div>

                  {/* Card Content */}
                  <div className="p-3.5 space-y-2">
                    <div className="flex items-center justify-between gap-1">
                      {renderStatusBadge(v)}
                      {v.created_at && (
                        <span className="text-[10px] font-mono text-text-muted">
                          {formatDistanceToNow(new Date(v.created_at), { addSuffix: true })}
                        </span>
                      )}
                    </div>

                    <h4 
                      onClick={() => setPreviewVideo(v)}
                      className="text-xs font-semibold text-text line-clamp-2 hover:text-accent cursor-pointer transition-colors"
                      title={v.title}
                    >
                      {v.title || 'Untitled Video'}
                    </h4>

                    {(v.schedule_time || v.scheduled_time) && (
                      <p className="text-[11px] font-mono text-text-muted flex items-center gap-1">
                        <Clock className="w-3 h-3 text-warning" />
                        {format(new Date(v.schedule_time || v.scheduled_time), 'MMM d, h:mm a')}
                      </p>
                    )}

                    <InlineTagEditor
                      videoId={v.id}
                      tags={v.tags || []}
                      onUpdateTags={handleUpdateTags}
                    />
                  </div>
                </div>

                {/* Card Actions Footer */}
                <div className="p-3 pt-0 border-t border-border/50 mt-2 flex items-center justify-between">
                  <div className="flex items-center gap-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setPreviewVideo(v)}
                      className="h-7 px-2 text-xs text-text-muted hover:text-text cursor-pointer"
                    >
                      Preview
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setConvertingVideo(v)}
                      className="h-7 px-2 text-xs text-text-muted hover:text-accent cursor-pointer"
                      title="Convert Aspect Ratio"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setEditingVideo(v)}
                      className="h-7 px-2 text-xs text-text-muted hover:text-accent cursor-pointer"
                      title="Studio Edit (Trim, Color, Captions, Brand)"
                    >
                      <Scissors className="w-3.5 h-3.5" />
                    </Button>
                  </div>

                  <div className="flex items-center gap-1">
                    {v.status === 'failed' ? (
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => setPublishingVideo(v)}
                        className="h-7 px-2 text-xs bg-warning/20 text-warning hover:bg-warning hover:text-black border border-warning/30 cursor-pointer flex items-center gap-1"
                        title="Retry Publish"
                      >
                        <RotateCcw className="w-3 h-3" /> Retry
                      </Button>
                    ) : v.status !== 'uploaded' && v.status !== 'published' ? (
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => setPublishingVideo(v)}
                        className="h-7 px-2 text-xs bg-accent/15 text-accent hover:bg-accent hover:text-accent-foreground border border-accent/20 cursor-pointer"
                      >
                        Publish
                      </Button>
                    ) : null}

                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setDeletingVideo(v)}
                      className="h-7 px-2 text-xs text-zinc-500 hover:text-danger hover:bg-danger/10 cursor-pointer"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      ) : (
        /* TABLE VIEW */
        <div className="bg-surface border border-border rounded-xl overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-elevated/70 border-b border-border text-text-muted font-mono uppercase text-[10px]">
                <tr>
                  <th className="p-3 pl-4 w-10">
                    <button
                      type="button"
                      onClick={toggleSelectAll}
                      className="text-text-muted hover:text-text cursor-pointer"
                    >
                      {selectedIds.length === videos.length && videos.length > 0 ? (
                        <CheckSquare className="w-4 h-4 text-accent" />
                      ) : (
                        <Square className="w-4 h-4" />
                      )}
                    </button>
                  </th>
                  <th className="p-3 w-16">Media</th>
                  <th className="p-3">Title & Information</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Scheduled / Published</th>
                  <th className="p-3 text-right pr-4">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60 font-sans">
                {videos.map((v) => {
                  const isSelected = selectedIds.includes(v.id);

                  return (
                    <tr 
                      key={v.id} 
                      className={cn(
                        "hover:bg-surface-elevated/40 transition-colors group",
                        isSelected && "bg-accent/5"
                      )}
                    >
                      <td className="p-3 pl-4">
                        <button
                          type="button"
                          onClick={() => toggleSelectVideo(v.id)}
                          className="text-text-muted hover:text-text cursor-pointer"
                        >
                          {isSelected ? (
                            <CheckSquare className="w-4 h-4 text-accent" />
                          ) : (
                            <Square className="w-4 h-4" />
                          )}
                        </button>
                      </td>

                      <td className="p-3">
                        <div 
                          onClick={() => setPreviewVideo(v)}
                          className="w-14 h-10 bg-black rounded border border-border/80 overflow-hidden relative cursor-pointer group/thumb"
                        >
                          {v.thumbnail_url ? (
                            <img src={v.thumbnail_url} alt="" className="w-full h-full object-cover" />
                          ) : (
                            <Film className="w-4 h-4 m-auto text-text-muted opacity-50" />
                          )}
                          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/thumb:opacity-100 flex items-center justify-center transition-opacity">
                            <Play className="w-3.5 h-3.5 text-white fill-white" />
                          </div>
                        </div>
                      </td>

                      <td className="p-3 max-w-xs sm:max-w-md">
                        <p 
                          onClick={() => setPreviewVideo(v)}
                          className="font-medium text-text truncate hover:text-accent cursor-pointer transition-colors"
                        >
                          {v.title || 'Untitled Video'}
                        </p>
                        {v.youtube_url && (
                          <a 
                            href={v.youtube_url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-[11px] text-accent hover:underline inline-flex items-center gap-1 mt-0.5"
                          >
                            <span>Open on YouTube</span>
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                        <InlineTagEditor
                          videoId={v.id}
                          tags={v.tags || []}
                          onUpdateTags={handleUpdateTags}
                        />
                      </td>

                      <td className="p-3 whitespace-nowrap">
                        {renderStatusBadge(v)}
                      </td>

                      <td className="p-3 whitespace-nowrap font-mono text-[11px] text-text-muted">
                        {v.schedule_time || v.scheduled_time 
                          ? format(new Date(v.schedule_time || v.scheduled_time), 'MMM d, yyyy h:mm a')
                          : v.created_at ? formatDistanceToNow(new Date(v.created_at), { addSuffix: true }) : '-'}
                      </td>

                      <td className="p-3 text-right pr-4 whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => setPreviewVideo(v)}
                            className="h-7 px-2 text-xs text-text-muted hover:text-text cursor-pointer"
                          >
                            Preview
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => setConvertingVideo(v)}
                            className="h-7 px-2 text-xs text-text-muted hover:text-accent cursor-pointer"
                            title="Convert Aspect Ratio"
                          >
                            <RefreshCw className="w-3.5 h-3.5" />
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => setEditingVideo(v)}
                            className="h-7 px-2 text-xs text-text-muted hover:text-accent cursor-pointer"
                            title="Studio Edit (Trim, Color, Captions, Brand)"
                          >
                            <Scissors className="w-3.5 h-3.5" />
                          </Button>

                          {v.status === 'failed' ? (
                            <Button
                              type="button"
                              size="sm"
                              onClick={() => setPublishingVideo(v)}
                              className="h-7 px-2 text-xs bg-warning/20 text-warning hover:bg-warning hover:text-black border border-warning/30 cursor-pointer flex items-center gap-1"
                            >
                              <RotateCcw className="w-3 h-3" /> Retry
                            </Button>
                          ) : v.status !== 'uploaded' && v.status !== 'published' ? (
                            <Button
                              type="button"
                              size="sm"
                              onClick={() => setPublishingVideo(v)}
                              className="h-7 px-2 text-xs bg-accent/15 text-accent hover:bg-accent hover:text-accent-foreground border border-accent/20 cursor-pointer"
                            >
                              Publish
                            </Button>
                          ) : null}

                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => setDeletingVideo(v)}
                            className="h-7 px-2 text-xs text-zinc-500 hover:text-danger hover:bg-danger/10 cursor-pointer"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-border pt-4">
          <span className="text-xs text-text-muted font-mono">
            Page {page} of {totalPages} ({totalCount} total)
          </span>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage(p => Math.max(1, p - 1))}
              className="text-xs flex items-center gap-1 cursor-pointer"
            >
              <ChevronLeft className="w-3.5 h-3.5" /> Previous
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage(p => p + 1)}
              className="text-xs flex items-center gap-1 cursor-pointer"
            >
              Next <ChevronRight className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      )}

      {/* Modals & Dialogs */}
      {previewVideo && (
        <VideoPreviewModal
          video={previewVideo}
          onClose={() => setPreviewVideo(null)}
          onConvert={(v) => {
            setPreviewVideo(null);
            setConvertingVideo(v);
          }}
          onPublish={(v) => {
            setPreviewVideo(null);
            setPublishingVideo(v);
          }}
          onDelete={(v) => {
            setPreviewVideo(null);
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

      {editingVideo && (
        <VideoEditorModal
          isOpen={Boolean(editingVideo)}
          onClose={() => setEditingVideo(null)}
          videoPath={editingVideo.storage_path || editingVideo.id}
          videoUrl={editingVideo.storage_path ? `/download/${editingVideo.storage_path.replace(/^videos\//, '')}` : ''}
          onSaveSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ['library-videos'] });
            queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
          }}
        />
      )}

      {/* Single Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={Boolean(deletingVideo)}
        title="Delete this video?"
        description={`This will permanently delete "${deletingVideo?.title || 'this video'}" from Supabase Cloud Storage and database.`}
        confirmText="Delete Video"
        confirmVariant="danger"
        isLoading={deleteMutation.isPending}
        onClose={() => setDeletingVideo(null)}
        onConfirm={() => deletingVideo && deleteMutation.mutate(deletingVideo.id)}
      />

      {/* Bulk Tag Dialog */}
      <BulkTagModal
        isOpen={isBulkTagging}
        count={selectedIds.length}
        onClose={() => setIsBulkTagging(false)}
        onApply={handleBulkTag}
      />

      {/* Bulk Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={isBulkDeleting}
        title={`Delete ${selectedIds.length} videos?`}
        description={`This will permanently remove all ${selectedIds.length} selected videos and their cloud storage files. This action cannot be undone.`}
        confirmText={`Delete ${selectedIds.length} Videos`}
        confirmVariant="danger"
        onClose={() => setIsBulkDeleting(false)}
        onConfirm={handleBulkDelete}
      />

      {/* Publish Confirmation Dialog */}
      <ConfirmDialog
        isOpen={Boolean(publishingVideo)}
        title="Publish to YouTube Shorts now?"
        description={`This will immediately upload and publish "${publishingVideo?.title || 'this video'}" to your connected YouTube channel.`}
        confirmText="Publish to YouTube"
        confirmVariant="primary"
        icon="info"
        isLoading={publishMutation.isPending}
        onClose={() => setPublishingVideo(null)}
        onConfirm={() => publishingVideo && publishMutation.mutate(publishingVideo.id)}
      />
    </div>
  );
}
