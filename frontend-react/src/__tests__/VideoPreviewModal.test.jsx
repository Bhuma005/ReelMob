import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { VideoPreviewModal } from '../components/video/VideoPreviewModal';

describe('VideoPreviewModal Component', () => {
  const mockVideo = {
    id: 'vid-test-123',
    title: 'Test Viral Reel',
    description: 'A great test description for previewing',
    status: 'uploaded',
    storage_url: 'https://storage.supabase.co/reelgrab-videos/sample.mp4',
    storage_path: 'videos/sample.mp4',
    thumbnail_url: 'https://cdn.example.com/thumb.jpg',
    hashtags: ['viral', 'trending'],
    created_at: new Date().toISOString(),
  };

  it('renders modal dialog without crashing or throwing ReferenceError', () => {
    render(
      <VideoPreviewModal
        video={mockVideo}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText('Video Details')).toBeDefined();
    expect(screen.getByText('Test Viral Reel')).toBeDefined();
    expect(screen.getByText('A great test description for previewing')).toBeDefined();
    expect(screen.getByText('#viral')).toBeDefined();
    expect(screen.getByText('#trending')).toBeDefined();
  });

  it('renders video element with source tag pointing to stream url', () => {
    const { container } = render(
      <VideoPreviewModal
        video={mockVideo}
        onClose={vi.fn()}
      />
    );

    const videoEl = container.querySelector('video');
    expect(videoEl).toBeDefined();

    const sourceEl = container.querySelector('video source');
    expect(sourceEl).toBeDefined();
    expect(sourceEl.getAttribute('src')).toBe('https://storage.supabase.co/reelgrab-videos/sample.mp4');
    expect(sourceEl.getAttribute('type')).toBe('video/mp4');
  });

  it('falls back to stream endpoint when storage_url is not set', () => {
    const videoWithoutStorageUrl = {
      id: 'vid-fallback-789',
      title: 'Fallback Video',
      status: 'scheduled',
    };

    const { container } = render(
      <VideoPreviewModal
        video={videoWithoutStorageUrl}
        onClose={vi.fn()}
      />
    );

    const sourceEl = container.querySelector('video source');
    expect(sourceEl).toBeDefined();
    expect(sourceEl.getAttribute('src')).toBe('/api/dashboard/videos/vid-fallback-789/stream');
  });
});
