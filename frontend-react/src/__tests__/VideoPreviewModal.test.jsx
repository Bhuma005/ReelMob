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

  it('renders iframe player when video has an Instagram reel source URL', () => {
    const instagramReelVideo = {
      id: 'vid-ig-999',
      title: 'What Happens Next Will Crack You Up',
      source_url: 'https://www.instagram.com/reel/DXP2hVzEm1W/?exln=MTZhZ3Q1ZmF1eDNqdg==',
      storage_path: 'source:https://www.instagram.com/reel/DXP2hVzEm1W/?exln=MTZhZ3Q1ZmF1eDNqdg==',
      status: 'scheduled',
    };

    const { container } = render(
      <VideoPreviewModal
        video={instagramReelVideo}
        onClose={vi.fn()}
      />
    );

    const iframeEl = container.querySelector('iframe');
    expect(iframeEl).toBeDefined();
    expect(iframeEl.getAttribute('src')).toBe('https://www.instagram.com/reel/DXP2hVzEm1W/embed/');
  });

  it('renders iframe player when video has YouTube shorts source URL or youtube_video_id', () => {
    const youtubeVideo = {
      id: 'vid-yt-111',
      title: 'YouTube Shorts Clip',
      source_url: 'https://www.youtube.com/shorts/dQw4w9WgXcQ',
      storage_path: 'source:https://www.youtube.com/shorts/dQw4w9WgXcQ',
      status: 'scheduled',
    };

    const { container } = render(
      <VideoPreviewModal
        video={youtubeVideo}
        onClose={vi.fn()}
      />
    );

    const iframeEl = container.querySelector('iframe');
    expect(iframeEl).toBeDefined();
    expect(iframeEl.getAttribute('src')).toContain('https://www.youtube.com/embed/dQw4w9WgXcQ');
  });
});
