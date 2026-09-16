import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Search, LayoutDashboard, Library, Calendar, 
  Activity, Link2, Terminal, Settings, ArrowRight, X, Plus, Film, Tag
} from 'lucide-react';
import { dashboardApi } from '../../api/dashboard';

export function CommandPalette({ isOpen, onClose }) {
  const [search, setSearch] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [videoResults, setVideoResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const navigate = useNavigate();
  const inputRef = useRef(null);

  const actions = [
    { id: 'create', label: 'Create New Reel', icon: Plus, path: '/create', group: 'Actions' },
    { id: 'dashboard', label: 'Go to Dashboard', icon: LayoutDashboard, path: '/', group: 'Navigation' },
    { id: 'library', label: 'Go to Library', icon: Library, path: '/library', group: 'Navigation' },
    { id: 'scheduler', label: 'Go to Scheduler', icon: Calendar, path: '/scheduler', group: 'Navigation' },
    { id: 'analytics', label: 'Go to Analytics', icon: Activity, path: '/analytics', group: 'Navigation' },
    { id: 'connections', label: 'Go to Connections', icon: Link2, path: '/connections', group: 'Navigation' },
    { id: 'logs', label: 'Go to Audit Logs', icon: Terminal, path: '/logs', group: 'Navigation' },
    { id: 'settings', label: 'Go to Settings', icon: Settings, path: '/settings', group: 'Navigation' },
  ];

  const filteredActions = actions.filter((a) =>
    a.label.toLowerCase().includes(search.toLowerCase())
  );

  useEffect(() => {
    if (!search.trim()) {
      setVideoResults([]);
      setIsSearching(false);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const data = await dashboardApi.searchVideos(search.trim());
        const items = (data?.results || []).map((v) => ({
          id: `video-${v.id}`,
          label: v.title || 'Untitled Video',
          subtitle: v.tags?.length ? `#${v.tags.join(' #')}` : (v.status || 'video'),
          icon: Film,
          path: '/library',
          group: 'Videos'
        }));
        setVideoResults(items);
      } catch (err) {
        console.debug('Search query error:', err);
      } finally {
        setIsSearching(false);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [search]);

  const allItems = [...filteredActions, ...videoResults];

  useEffect(() => {
    if (isOpen) {
      setSearch('');
      setSelectedIndex(0);
      setVideoResults([]);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [search, videoResults.length]);

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % (allItems.length || 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + allItems.length) % (allItems.length || 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (allItems[selectedIndex]) {
        navigate(allItems[selectedIndex].path);
        onClose();
      }
    } else if (e.key === 'Escape') {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-start justify-center pt-24 p-4 bg-black/75 backdrop-blur-xs animate-in fade-in duration-100"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg bg-surface border border-border rounded-xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-border">
          <Search className="w-4 h-4 text-text-muted shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command or search pages... (Esc to exit)"
            className="flex-1 bg-transparent text-sm text-text placeholder:text-text-muted focus:outline-none"
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              className="text-text-muted hover:text-text p-0.5 rounded cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-2">
          {isSearching && (
            <div className="px-3 py-1.5 text-[11px] text-accent font-mono">
              Searching videos...
            </div>
          )}
          {allItems.length === 0 ? (
            <div className="p-6 text-center text-xs text-text-muted">
              No results found for &ldquo;{search}&rdquo;
            </div>
          ) : (
            allItems.map((item, idx) => {
              const Icon = item.icon;
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={item.id}
                  onClick={() => {
                    navigate(item.path);
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`flex items-center justify-between px-3 py-2 rounded-lg text-sm cursor-pointer transition-colors ${
                    isSelected
                      ? 'bg-accent text-accent-foreground font-medium'
                      : 'text-text hover:bg-surface-elevated'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0 pr-2">
                    <Icon className={`w-4 h-4 shrink-0 ${isSelected ? 'text-accent-foreground' : 'text-text-muted'}`} />
                    <div className="min-w-0">
                      <p className="truncate text-xs font-medium">{item.label}</p>
                      {item.subtitle && (
                        <p className={`text-[10px] font-mono truncate ${isSelected ? 'text-accent-foreground/80' : 'text-text-muted'}`}>
                          {item.subtitle}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={`text-[10px] font-mono uppercase px-1.5 py-0.5 rounded ${
                      isSelected ? 'bg-black/20 text-accent-foreground' : 'bg-surface-elevated text-text-muted'
                    }`}>
                      {item.group}
                    </span>
                    <ArrowRight className={`w-3.5 h-3.5 opacity-0 ${isSelected ? 'opacity-100' : ''}`} />
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer info */}
        <div className="px-4 py-2 bg-surface-elevated/50 border-t border-border flex items-center justify-between text-[11px] text-text-muted font-mono">
          <div className="flex items-center gap-2">
            <span>↑↓ Navigate</span>
            <span>↵ Select</span>
            <span>Esc Close</span>
          </div>
          <span className="text-[10px]">ReelsMob Navigation</span>
        </div>
      </div>
    </div>
  );
}
