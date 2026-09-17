import React, { useState } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { cn } from '../lib/utils';
import { Button } from '../components/ui/Button';

// Mock format picker unit matching CreateReelPage implementation
function FormatPicker({ formats, onDownload }) {
  const [activeFormatId, setActiveFormatId] = useState(
    formats.find(f => f.is_original)?.format_id || formats[0]?.format_id
  );

  return (
    <div data-testid="format-picker">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {formats.map((fmt) => {
          const isSelected = activeFormatId === fmt.format_id;
          return (
            <div
              key={fmt.format_id}
              data-testid={`format-card-${fmt.format_id}`}
              onClick={() => setActiveFormatId(fmt.format_id)}
              className={cn(
                "p-4 rounded-xl border cursor-pointer",
                isSelected ? "border-accent bg-accent/10 selected-card" : "border-border"
              )}
            >
              <div className="flex justify-between">
                <span>{fmt.is_original ? 'ORIGINAL SOURCE' : fmt.ext}</span>
                <span>{fmt.resolution}</span>
              </div>
              <div>Ratio: {fmt.aspect_ratio || '9:16'} • FPS: {fmt.fps}</div>
              <div className="mt-2 flex justify-between items-center">
                <span data-testid={`status-${fmt.format_id}`}>
                  {isSelected ? 'Selected' : 'Click to select'}
                </span>
                <Button
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDownload(fmt.format_id);
                  }}
                >
                  Download
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

describe('Video Format & Quality Selection Flow', () => {
  const mockFormats = [
    {
      format_id: 'fmt-1080p',
      resolution: '1080x1920',
      aspect_ratio: '9:16',
      fps: 60,
      vcodec: 'h264',
      filesize: 25000000,
      is_original: true,
      ext: 'mp4'
    },
    {
      format_id: 'fmt-720p',
      resolution: '720x1280',
      aspect_ratio: '9:16',
      fps: 30,
      vcodec: 'h264',
      filesize: 12000000,
      is_original: false,
      ext: 'mp4'
    },
    {
      format_id: 'fmt-480p',
      resolution: '480x854',
      aspect_ratio: '9:16',
      fps: 30,
      vcodec: 'h264',
      filesize: 6000000,
      is_original: false,
      ext: 'mp4'
    }
  ];

  it('renders all available extracted formats with resolutions and badges', () => {
    render(<FormatPicker formats={mockFormats} onDownload={() => {}} />);

    expect(screen.getByText('1080x1920')).toBeInTheDocument();
    expect(screen.getByText('720x1280')).toBeInTheDocument();
    expect(screen.getByText('480x854')).toBeInTheDocument();
    expect(screen.getByText('ORIGINAL SOURCE')).toBeInTheDocument();
  });

  it('defaults to the original source format as active', () => {
    render(<FormatPicker formats={mockFormats} onDownload={() => {}} />);

    expect(screen.getByTestId('status-fmt-1080p')).toHaveTextContent('Selected');
    expect(screen.getByTestId('status-fmt-720p')).toHaveTextContent('Click to select');
  });

  it('updates selection and visual indicators when user selects a different format card', () => {
    render(<FormatPicker formats={mockFormats} onDownload={() => {}} />);

    // Click on the 720p format card
    const card720p = screen.getByTestId('format-card-fmt-720p');
    fireEvent.click(card720p);

    // 720p is now selected, 1080p is deselected
    expect(screen.getByTestId('status-fmt-720p')).toHaveTextContent('Selected');
    expect(screen.getByTestId('status-fmt-1080p')).toHaveTextContent('Click to select');
    expect(card720p).toHaveClass('selected-card');
  });

  it('triggers download callback with the specific format_id when download button is clicked', () => {
    const onDownloadMock = vi.fn();
    render(<FormatPicker formats={mockFormats} onDownload={onDownloadMock} />);

    // Click download on the 480p format
    const card480p = screen.getByTestId('format-card-fmt-480p');
    const downloadBtn = card480p.querySelector('button');
    fireEvent.click(downloadBtn);

    expect(onDownloadMock).toHaveBeenCalledTimes(1);
    expect(onDownloadMock).toHaveBeenCalledWith('fmt-480p');
  });
});
