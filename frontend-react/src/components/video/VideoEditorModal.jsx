import React, { useState, useRef, useEffect } from 'react';
import { 
  X, Scissors, Sliders, Type, Shield, 
  Play, Pause, RotateCcw, Check, Loader2 
} from 'lucide-react';
import { Button } from '../ui/Button';
import { toast } from 'sonner';

export function VideoEditorModal({
  isOpen,
  onClose,
  videoPath,
  videoUrl,
  onSaveSuccess,
}) {
  const videoRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  // Active Tab: 'trim' | 'color' | 'captions' | 'watermark' | 'framing'
  const [activeTab, setActiveTab] = useState('trim');

  // Edit Parameters
  const [trimStart, setTrimStart] = useState(0);
  const [trimEnd, setTrimEnd] = useState(0);

  const [brightness, setBrightness] = useState(0);
  const [contrast, setContrast] = useState(1);
  const [saturation, setSaturation] = useState(1);

  const [enableCaptions, setEnableCaptions] = useState(false);
  const [captionText, setCaptionText] = useState('');
  const [captionSize, setCaptionSize] = useState(32);
  const [captionPos, setCaptionPos] = useState('bottom');
  const [captionColor, setCaptionColor] = useState('white');

  const [enableWatermark, setEnableWatermark] = useState(false);
  const [watermarkText, setWatermarkText] = useState('');
  const [watermarkPos, setWatermarkPos] = useState('bottom-right');
  const [watermarkOpacity, setWatermarkOpacity] = useState(0.8);

  const [framing, setFraming] = useState('original');
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setIsPlaying(false);
      setCurrentTime(0);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      const dur = videoRef.current.duration || 0;
      setDuration(dur);
      setTrimEnd(dur);
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
      if (trimEnd > 0 && videoRef.current.currentTime >= trimEnd) {
        videoRef.current.pause();
        setIsPlaying(false);
      }
    }
  };

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      if (currentTime >= trimEnd) {
        videoRef.current.currentTime = trimStart;
      }
      videoRef.current.play();
      setIsPlaying(true);
    }
  };

  const setInPoint = () => {
    setTrimStart(currentTime);
    if (trimEnd <= currentTime) {
      setTrimEnd(Math.min(duration, currentTime + 5));
    }
    toast.info(`Trim In point set to ${currentTime.toFixed(1)}s`);
  };

  const setOutPoint = () => {
    if (currentTime > trimStart) {
      setTrimEnd(currentTime);
      toast.info(`Trim Out point set to ${currentTime.toFixed(1)}s`);
    } else {
      toast.warning('Out point must be greater than In point');
    }
  };

  const resetColor = () => {
    setBrightness(0);
    setContrast(1);
    setSaturation(1);
  };

  const handleProcess = async () => {
    setIsProcessing(true);
    try {
      const payload = {
        video_path: videoPath,
        framing,
        trim: {
          start: Number(trimStart.toFixed(2)),
          end: Number(trimEnd.toFixed(2)),
        },
        color: {
          brightness: Number(brightness),
          contrast: Number(contrast),
          saturation: Number(saturation),
        },
      };

      if (enableCaptions && captionText.trim()) {
        payload.captions = {
          text: captionText.trim(),
          font_size: Number(captionSize),
          position: captionPos,
          color: captionColor,
        };
      }

      if (enableWatermark && watermarkText.trim()) {
        payload.watermark = {
          text: watermarkText.trim(),
          position: watermarkPos,
          opacity: Number(watermarkOpacity),
        };
      }

      const res = await fetch('/api/video/edit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.detail || errData?.message || 'Processing failed');
      }

      const data = await res.json();
      toast.success('Video edit applied successfully!');
      if (onSaveSuccess) {
        onSaveSuccess(data);
      }
      onClose();
    } catch (err) {
      toast.error(`Edit failed: ${err.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  // Real-time CSS filter simulation for the preview video
  const cssFilter = `brightness(${1 + brightness}) contrast(${contrast}) saturate(${saturation})`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/85 backdrop-blur-sm animate-in fade-in duration-200">
      <div 
        className="w-full max-w-4xl bg-surface border border-border rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]"
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-surface-1">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-accent/10 text-accent">
              <Scissors className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-text">Reels Studio Editor</h3>
              <p className="text-xs text-text-muted">Trim, color grade, burn captions, and brand your short</p>
            </div>
          </div>
          <button 
            onClick={onClose} 
            disabled={isProcessing}
            className="p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-surface-2 transition-colors disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Video Preview & Playhead */}
          <div className="lg:col-span-7 flex flex-col gap-4">
            <div className="relative aspect-9/16 max-h-[460px] mx-auto bg-black rounded-xl overflow-hidden border border-border flex items-center justify-center group shadow-inner">
              <video
                ref={videoRef}
                src={videoUrl}
                onLoadedMetadata={handleLoadedMetadata}
                onTimeUpdate={handleTimeUpdate}
                onClick={togglePlay}
                style={{ filter: cssFilter }}
                className="w-full h-full object-contain cursor-pointer"
              />

              {/* Real-time Simulated Caption Overlay */}
              {enableCaptions && captionText && (
                <div 
                  className={`absolute inset-x-4 flex justify-center pointer-events-none ${
                    captionPos === 'top' ? 'top-6' : captionPos === 'center' ? 'top-1/2 -translate-y-1/2' : 'bottom-8'
                  }`}
                >
                  <span 
                    className="px-3 py-1.5 rounded bg-black/75 text-center font-bold tracking-wide shadow-md max-w-xs"
                    style={{ color: captionColor, fontSize: `${captionSize * 0.45}px` }}
                  >
                    {captionText}
                  </span>
                </div>
              )}

              {/* Real-time Simulated Watermark Overlay */}
              {enableWatermark && watermarkText && (
                <div 
                  className={`absolute p-2 pointer-events-none ${
                    watermarkPos === 'top-left' ? 'top-2 left-2' :
                    watermarkPos === 'top-right' ? 'top-2 right-2' :
                    watermarkPos === 'bottom-left' ? 'bottom-2 left-2' : 'bottom-2 right-2'
                  }`}
                >
                  <span 
                    className="px-2 py-0.5 rounded bg-black/60 font-semibold tracking-wider text-[11px]"
                    style={{ opacity: watermarkOpacity, color: 'white' }}
                  >
                    {watermarkText}
                  </span>
                </div>
              )}

              {/* Play / Pause Center Overlay */}
              <button
                onClick={togglePlay}
                className="absolute inset-0 m-auto w-12 h-12 rounded-full bg-black/60 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity backdrop-blur-xs hover:scale-110"
              >
                {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 ml-0.5" />}
              </button>
            </div>

            {/* Scrubber & In/Out Setters */}
            <div className="p-3 bg-surface-1 rounded-xl border border-border space-y-3">
              <div className="flex items-center justify-between text-xs text-text-muted font-mono">
                <span>Current: {currentTime.toFixed(1)}s</span>
                <span className="text-accent font-semibold">Trim: {trimStart.toFixed(1)}s – {trimEnd.toFixed(1)}s ({(trimEnd - trimStart).toFixed(1)}s)</span>
                <span>Total: {duration.toFixed(1)}s</span>
              </div>

              {/* Video Timeline Scrubber */}
              <input
                type="range"
                min={0}
                max={duration || 100}
                step={0.1}
                value={currentTime}
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  setCurrentTime(val);
                  if (videoRef.current) videoRef.current.currentTime = val;
                }}
                className="w-full accent-accent h-1.5 bg-surface-3 rounded-lg cursor-pointer"
              />

              {/* In/Out Quick Action Buttons */}
              <div className="flex items-center justify-between gap-2">
                <Button variant="secondary" size="sm" onClick={setInPoint} className="text-xs h-8">
                  [ Set In ({currentTime.toFixed(1)}s)
                </Button>
                <Button variant="ghost" size="sm" onClick={togglePlay} className="text-xs h-8">
                  {isPlaying ? 'Pause' : 'Play'}
                </Button>
                <Button variant="secondary" size="sm" onClick={setOutPoint} className="text-xs h-8">
                  Set Out ({currentTime.toFixed(1)}s) ]
                </Button>
              </div>
            </div>
          </div>

          {/* Right Column: Editing Tools Tabs */}
          <div className="lg:col-span-5 flex flex-col gap-4">
            {/* Tool Category Tabs */}
            <div className="flex items-center gap-1 p-1 bg-surface-1 rounded-xl border border-border overflow-x-auto text-xs">
              <button
                onClick={() => setActiveTab('trim')}
                className={`flex-1 py-1.5 px-2 rounded-lg font-medium transition-colors flex items-center justify-center gap-1 ${
                  activeTab === 'trim' ? 'bg-surface-2 text-text shadow-xs' : 'text-text-muted hover:text-text'
                }`}
              >
                <Scissors className="w-3.5 h-3.5" /> Trim
              </button>
              <button
                onClick={() => setActiveTab('color')}
                className={`flex-1 py-1.5 px-2 rounded-lg font-medium transition-colors flex items-center justify-center gap-1 ${
                  activeTab === 'color' ? 'bg-surface-2 text-text shadow-xs' : 'text-text-muted hover:text-text'
                }`}
              >
                <Sliders className="w-3.5 h-3.5" /> Color
              </button>
              <button
                onClick={() => setActiveTab('captions')}
                className={`flex-1 py-1.5 px-2 rounded-lg font-medium transition-colors flex items-center justify-center gap-1 ${
                  activeTab === 'captions' ? 'bg-surface-2 text-text shadow-xs' : 'text-text-muted hover:text-text'
                }`}
              >
                <Type className="w-3.5 h-3.5" /> Captions
              </button>
              <button
                onClick={() => setActiveTab('watermark')}
                className={`flex-1 py-1.5 px-2 rounded-lg font-medium transition-colors flex items-center justify-center gap-1 ${
                  activeTab === 'watermark' ? 'bg-surface-2 text-text shadow-xs' : 'text-text-muted hover:text-text'
                }`}
              >
                <Shield className="w-3.5 h-3.5" /> Brand
              </button>
            </div>

            {/* Tab 1: Trim Controls */}
            {activeTab === 'trim' && (
              <div className="p-4 bg-surface-1 rounded-xl border border-border space-y-4">
                <h4 className="text-xs font-semibold text-text uppercase tracking-wider">Trim & Cut Dead Air</h4>
                <div className="space-y-3">
                  <div>
                    <label className="text-xs text-text-muted flex justify-between">
                      <span>Start Point</span>
                      <span className="font-mono text-text">{trimStart.toFixed(1)}s</span>
                    </label>
                    <input
                      type="range"
                      min={0}
                      max={Math.max(0, trimEnd - 0.5)}
                      step={0.1}
                      value={trimStart}
                      onChange={(e) => setTrimStart(parseFloat(e.target.value))}
                      className="w-full accent-accent h-1.5 bg-surface-3 rounded-lg mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-text-muted flex justify-between">
                      <span>End Point</span>
                      <span className="font-mono text-text">{trimEnd.toFixed(1)}s</span>
                    </label>
                    <input
                      type="range"
                      min={trimStart + 0.5}
                      max={duration || 100}
                      step={0.1}
                      value={trimEnd}
                      onChange={(e) => setTrimEnd(parseFloat(e.target.value))}
                      className="w-full accent-accent h-1.5 bg-surface-3 rounded-lg mt-1"
                    />
                  </div>
                </div>

                {/* Framing Selection */}
                <div className="pt-3 border-t border-border space-y-2">
                  <label className="text-xs font-medium text-text">Framing & Aspect Ratio</label>
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      type="button"
                      onClick={() => setFraming('original')}
                      className={`p-2 rounded-lg text-[11px] border text-center transition-colors ${
                        framing === 'original' ? 'border-accent bg-accent/10 text-accent font-semibold' : 'border-border text-text-muted hover:bg-surface-2'
                      }`}
                    >
                      Original
                    </button>
                    <button
                      type="button"
                      onClick={() => setFraming('blur_pad')}
                      className={`p-2 rounded-lg text-[11px] border text-center transition-colors ${
                        framing === 'blur_pad' ? 'border-accent bg-accent/10 text-accent font-semibold' : 'border-border text-text-muted hover:bg-surface-2'
                      }`}
                    >
                      9:16 Blur Fill
                    </button>
                    <button
                      type="button"
                      onClick={() => setFraming('crop')}
                      className={`p-2 rounded-lg text-[11px] border text-center transition-colors ${
                        framing === 'crop' ? 'border-accent bg-accent/10 text-accent font-semibold' : 'border-border text-text-muted hover:bg-surface-2'
                      }`}
                    >
                      9:16 Crop
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Tab 2: Color Grading (FFmpeg eq) */}
            {activeTab === 'color' && (
              <div className="p-4 bg-surface-1 rounded-xl border border-border space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-semibold text-text uppercase tracking-wider">Color & Contrast</h4>
                  <button onClick={resetColor} className="text-[11px] text-text-muted hover:text-text flex items-center gap-1">
                    <RotateCcw className="w-3 h-3" /> Reset
                  </button>
                </div>
                <div className="space-y-3">
                  <div>
                    <label className="text-xs text-text-muted flex justify-between">
                      <span>Brightness</span>
                      <span className="font-mono text-text">{brightness.toFixed(2)}</span>
                    </label>
                    <input
                      type="range"
                      min={-0.3}
                      max={0.3}
                      step={0.02}
                      value={brightness}
                      onChange={(e) => setBrightness(parseFloat(e.target.value))}
                      className="w-full accent-accent h-1.5 bg-surface-3 rounded-lg mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-text-muted flex justify-between">
                      <span>Contrast</span>
                      <span className="font-mono text-text">{contrast.toFixed(2)}</span>
                    </label>
                    <input
                      type="range"
                      min={0.7}
                      max={1.5}
                      step={0.05}
                      value={contrast}
                      onChange={(e) => setContrast(parseFloat(e.target.value))}
                      className="w-full accent-accent h-1.5 bg-surface-3 rounded-lg mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-text-muted flex justify-between">
                      <span>Saturation</span>
                      <span className="font-mono text-text">{saturation.toFixed(2)}</span>
                    </label>
                    <input
                      type="range"
                      min={0.5}
                      max={1.6}
                      step={0.05}
                      value={saturation}
                      onChange={(e) => setSaturation(parseFloat(e.target.value))}
                      className="w-full accent-accent h-1.5 bg-surface-3 rounded-lg mt-1"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Tab 3: Subtitle / Caption Burn-In */}
            {activeTab === 'captions' && (
              <div className="p-4 bg-surface-1 rounded-xl border border-border space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-semibold text-text uppercase tracking-wider">Burn-In Captions</h4>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={enableCaptions}
                      onChange={(e) => setEnableCaptions(e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-8 h-4 bg-surface-3 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-accent" />
                  </label>
                </div>

                {enableCaptions ? (
                  <div className="space-y-3 animate-in fade-in duration-150">
                    <div>
                      <label className="text-xs text-text-muted block mb-1">Hook Caption Text</label>
                      <input
                        type="text"
                        placeholder="e.g. Wait for the ending twist... 🔥"
                        value={captionText}
                        onChange={(e) => setCaptionText(e.target.value)}
                        className="w-full px-3 py-2 bg-surface-2 border border-border rounded-lg text-xs text-text focus:outline-none focus:border-accent"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[11px] text-text-muted block mb-1">Position</label>
                        <select
                          value={captionPos}
                          onChange={(e) => setCaptionPos(e.target.value)}
                          className="w-full px-2.5 py-1.5 bg-surface-2 border border-border rounded-lg text-xs text-text"
                        >
                          <option value="bottom">Bottom (Standard)</option>
                          <option value="center">Center (Impact)</option>
                          <option value="top">Top (Headline)</option>
                        </select>
                      </div>
                      <div>
                        <label className="text-[11px] text-text-muted block mb-1">Color</label>
                        <select
                          value={captionColor}
                          onChange={(e) => setCaptionColor(e.target.value)}
                          className="w-full px-2.5 py-1.5 bg-surface-2 border border-border rounded-lg text-xs text-text"
                        >
                          <option value="white">White</option>
                          <option value="yellow">Yellow</option>
                          <option value="cyan">Cyan</option>
                          <option value="lime">Lime Green</option>
                        </select>
                      </div>
                    </div>
                    <div>
                      <label className="text-[11px] text-text-muted block mb-1">Font Size: {captionSize}px</label>
                      <input
                        type="range"
                        min={18}
                        max={64}
                        step={2}
                        value={captionSize}
                        onChange={(e) => setCaptionSize(parseInt(e.target.value, 10))}
                        className="w-full accent-accent h-1.5 bg-surface-3 rounded-lg"
                      />
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-text-muted py-2">
                    Enable to burn a high-visibility headline or hook caption directly into the video output.
                  </p>
                )}
              </div>
            )}

            {/* Tab 4: Branding / Watermark */}
            {activeTab === 'watermark' && (
              <div className="p-4 bg-surface-1 rounded-xl border border-border space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-semibold text-text uppercase tracking-wider">Watermark & Logo</h4>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={enableWatermark}
                      onChange={(e) => setEnableWatermark(e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-8 h-4 bg-surface-3 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-accent" />
                  </label>
                </div>

                {enableWatermark ? (
                  <div className="space-y-3 animate-in fade-in duration-150">
                    <div>
                      <label className="text-xs text-text-muted block mb-1">Handle or Brand Text</label>
                      <input
                        type="text"
                        placeholder="e.g. @ReelsMob"
                        value={watermarkText}
                        onChange={(e) => setWatermarkText(e.target.value)}
                        className="w-full px-3 py-2 bg-surface-2 border border-border rounded-lg text-xs text-text focus:outline-none focus:border-accent"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[11px] text-text-muted block mb-1">Corner</label>
                        <select
                          value={watermarkPos}
                          onChange={(e) => setWatermarkPos(e.target.value)}
                          className="w-full px-2.5 py-1.5 bg-surface-2 border border-border rounded-lg text-xs text-text"
                        >
                          <option value="bottom-right">Bottom-Right</option>
                          <option value="top-right">Top-Right</option>
                          <option value="bottom-left">Bottom-Left</option>
                          <option value="top-left">Top-Left</option>
                        </select>
                      </div>
                      <div>
                        <label className="text-[11px] text-text-muted block mb-1">Opacity: {Math.round(watermarkOpacity * 100)}%</label>
                        <input
                          type="range"
                          min={0.2}
                          max={1.0}
                          step={0.1}
                          value={watermarkOpacity}
                          onChange={(e) => setWatermarkOpacity(parseFloat(e.target.value))}
                          className="w-full accent-accent h-1.5 bg-surface-3 rounded-lg mt-2"
                        />
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-text-muted py-2">
                    Enable to stamp your creator watermark across all exports for copyright protection and brand recall.
                  </p>
                )}
              </div>
            )}

            {/* Footer Buttons */}
            <div className="mt-auto pt-4 border-t border-border flex items-center justify-end gap-3">
              <Button variant="ghost" onClick={onClose} disabled={isProcessing}>
                Cancel
              </Button>
              <Button 
                variant="primary" 
                onClick={handleProcess} 
                disabled={isProcessing}
                className="gap-2"
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Rendering Video...
                  </>
                ) : (
                  <>
                    <Check className="w-4 h-4" />
                    Apply Edits
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
