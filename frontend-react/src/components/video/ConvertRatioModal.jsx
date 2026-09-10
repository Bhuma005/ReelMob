import React, { useState } from 'react';
import { X, RefreshCw, Film, Smartphone, Square, Monitor, Sparkles } from 'lucide-react';
import { Button } from '../ui/Button';

export function ConvertRatioModal({
  video,
  isOpen,
  onClose,
  onConvert,
  isConverting = false,
}) {
  const [selectedRatio, setSelectedRatio] = useState('9:16');

  if (!isOpen || !video) return null;

  const ratios = [
    {
      id: '9:16',
      name: '9:16 Vertical',
      subtitle: 'YouTube Shorts & IG Reels',
      icon: Smartphone,
      badge: 'Recommended',
    },
    {
      id: '1:1',
      name: '1:1 Square',
      subtitle: 'Feed Post & Carousel',
      icon: Square,
    },
    {
      id: '4:5',
      name: '4:5 Portrait',
      subtitle: 'Instagram Optimal Feed',
      icon: Film,
    },
    {
      id: '16:9',
      name: '16:9 Landscape',
      subtitle: 'YouTube Standard Video',
      icon: Monitor,
    },
  ];

  const handleConvert = () => {
    if (onConvert) {
      onConvert(video.id, selectedRatio);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-xs animate-in fade-in duration-150">
      <div 
        className="w-full max-w-lg bg-surface border border-border rounded-xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-150"
        role="dialog"
        aria-modal="true"
      >
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-semibold text-text">Convert Aspect Ratio</h3>
              <p className="text-xs text-text-muted mt-0.5">
                Re-render and adapt layout with smart padding and FFmpeg canvas reframing.
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              disabled={isConverting}
              className="p-1 text-text-muted hover:text-text rounded-md transition-colors"
              aria-label="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-2 gap-3 my-4">
            {ratios.map((r) => {
              const Icon = r.icon;
              const isSelected = selectedRatio === r.id;
              return (
                <button
                  key={r.id}
                  type="button"
                  disabled={isConverting}
                  onClick={() => setSelectedRatio(r.id)}
                  className={`p-3.5 rounded-xl border text-left transition-all relative flex flex-col justify-between ${
                    isSelected
                      ? 'border-accent bg-accent/10 shadow-sm'
                      : 'border-border bg-surface-elevated/50 hover:bg-surface-elevated hover:border-zinc-700'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <Icon className={`w-5 h-5 ${isSelected ? 'text-accent' : 'text-zinc-400'}`} />
                    {r.badge && (
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-accent/20 text-accent font-semibold">
                        {r.badge}
                      </span>
                    )}
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-text">{r.name}</div>
                    <div className="text-[11px] text-text-muted mt-0.5">{r.subtitle}</div>
                  </div>
                </button>
              );
            })}
          </div>

          {isConverting && (
            <div className="p-3.5 rounded-lg bg-surface-elevated border border-border/80 text-xs text-zinc-300 flex items-center gap-3">
              <RefreshCw className="w-4 h-4 text-accent animate-spin shrink-0" />
              <div>
                <div className="font-semibold text-text">Re-rendering Video Stream...</div>
                <div className="text-[11px] text-text-muted mt-0.5">FFmpeg canvas reframing in progress on server.</div>
              </div>
            </div>
          )}
        </div>

        <div className="px-6 py-4 bg-surface-elevated/50 border-t border-border flex items-center justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={isConverting}
            size="sm"
          >
            Cancel
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={handleConvert}
            disabled={isConverting}
            isLoading={isConverting}
            className="bg-accent text-accent-foreground flex items-center gap-2"
          >
            <Sparkles className="w-3.5 h-3.5" />
            Start Conversion
          </Button>
        </div>
      </div>
    </div>
  );
}
