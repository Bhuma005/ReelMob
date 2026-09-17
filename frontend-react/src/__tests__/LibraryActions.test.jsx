import React, { useState } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from '../components/ui/Button';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { Trash2, RotateCcw } from 'lucide-react';

// Isolated table row actions harness matching LibraryPage pattern
function VideoRowActions({ video, onDeleteConfirm, onRetryPublish }) {
  const [deletingVideo, setDeletingVideo] = useState(null);

  return (
    <div>
      <div data-testid={`row-${video.id}`} className="flex items-center gap-2">
        <span>{video.title}</span>
        <span data-testid="status-badge">{video.status}</span>

        {video.status === 'failed' ? (
          <Button
            type="button"
            size="sm"
            onClick={() => onRetryPublish(video)}
            className="retry-btn"
          >
            <RotateCcw className="w-3 h-3" /> Retry
          </Button>
        ) : video.status !== 'uploaded' && video.status !== 'published' ? (
          <Button
            type="button"
            size="sm"
            onClick={() => onRetryPublish(video)}
          >
            Publish
          </Button>
        ) : null}

        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setDeletingVideo(video)}
          aria-label="Delete video"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </div>

      <ConfirmDialog
        isOpen={Boolean(deletingVideo)}
        title="Delete this video?"
        description={`This will permanently delete "${deletingVideo?.title || 'this video'}" from Supabase Cloud Storage and database.`}
        confirmText="Delete Video"
        confirmVariant="danger"
        onClose={() => setDeletingVideo(null)}
        onConfirm={() => {
          onDeleteConfirm(deletingVideo.id);
          setDeletingVideo(null);
        }}
      />
    </div>
  );
}

describe('Library Row Actions: Retry and Delete Confirmation Flow', () => {
  const failedVideo = {
    id: 'vid-failed-123',
    title: 'Instagram Viral Cooking Reel',
    status: 'failed',
    youtube_url: null,
  };

  const completedVideo = {
    id: 'vid-ok-456',
    title: 'Completed Shorts Video',
    status: 'published',
    youtube_url: 'https://youtube.com/shorts/xyz',
  };

  it('renders Retry button when video status is "failed"', () => {
    const onRetryMock = vi.fn();
    render(
      <VideoRowActions
        video={failedVideo}
        onDeleteConfirm={() => {}}
        onRetryPublish={onRetryMock}
      />
    );

    const retryBtn = screen.getByRole('button', { name: /retry/i });
    expect(retryBtn).toBeInTheDocument();

    fireEvent.click(retryBtn);
    expect(onRetryMock).toHaveBeenCalledTimes(1);
    expect(onRetryMock).toHaveBeenCalledWith(failedVideo);
  });

  it('does NOT render Retry button when video is already published', () => {
    render(
      <VideoRowActions
        video={completedVideo}
        onDeleteConfirm={() => {}}
        onRetryPublish={() => {}}
      />
    );

    expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
  });

  it('blocks deletion until confirmed via the ConfirmDialog modal', () => {
    const onDeleteMock = vi.fn();
    render(
      <VideoRowActions
        video={failedVideo}
        onDeleteConfirm={onDeleteMock}
        onRetryPublish={() => {}}
      />
    );

    // Initial state: dialog closed, delete not triggered
    expect(screen.queryByText('Delete this video?')).not.toBeInTheDocument();
    expect(onDeleteMock).not.toHaveBeenCalled();

    // Click trash button to trigger modal
    const trashBtn = screen.getByRole('button', { name: /delete video/i });
    fireEvent.click(trashBtn);

    // Dialog is now visible, but delete NOT yet executed
    expect(screen.getByText('Delete this video?')).toBeInTheDocument();
    expect(
      screen.getByText(/permanently delete "Instagram Viral Cooking Reel"/i)
    ).toBeInTheDocument();
    expect(onDeleteMock).not.toHaveBeenCalled();

    // Click Cancel
    const cancelBtn = screen.getByRole('button', { name: 'Cancel' });
    fireEvent.click(cancelBtn);

    // Modal closes without executing deletion
    expect(screen.queryByText('Delete this video?')).not.toBeInTheDocument();
    expect(onDeleteMock).not.toHaveBeenCalled();

    // Click trash again and Confirm this time
    fireEvent.click(trashBtn);
    const confirmBtn = screen.getByRole('button', { name: 'Delete Video' });
    fireEvent.click(confirmBtn);

    // Deletion executed with correct video ID
    expect(onDeleteMock).toHaveBeenCalledTimes(1);
    expect(onDeleteMock).toHaveBeenCalledWith('vid-failed-123');
  });
});
