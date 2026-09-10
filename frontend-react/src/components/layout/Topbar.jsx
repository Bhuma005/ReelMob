import React from 'react';
import { Menu, Plus, Search } from 'lucide-react';
import { useAppStore } from '../../stores/appStore';
import { useNavigate } from 'react-router-dom';

export default function Topbar({ onOpenCommandPalette }) {
  const { setSidebarOpen } = useAppStore();
  const navigate = useNavigate();

  return (
    <header className="h-16 flex items-center justify-between px-4 md:px-8 border-b border-border bg-surface/75 backdrop-blur-md sticky top-0 z-30">
      <div className="flex items-center gap-4">
        <button 
          onClick={() => setSidebarOpen(true)}
          className="lg:hidden text-text-muted hover:text-text p-1.5 rounded-md hover:bg-surface-elevated cursor-pointer"
          aria-label="Open Navigation Menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Command Palette Trigger Button */}
        <button
          onClick={onOpenCommandPalette}
          type="button"
          className="hidden sm:flex items-center gap-3 px-3 py-1.5 rounded-lg bg-surface-elevated border border-border text-xs text-text-muted hover:text-text hover:border-zinc-600 transition-colors cursor-pointer w-56 md:w-72"
        >
          <Search className="w-3.5 h-3.5 shrink-0" />
          <span className="flex-1 text-left truncate">Search or jump to...</span>
          <kbd className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] font-mono font-semibold text-text-muted bg-zinc-800 border border-zinc-700 rounded">
            Ctrl K
          </kbd>
        </button>
      </div>
      
      <div className="flex items-center gap-3">
        {/* Mobile Search Icon */}
        <button
          onClick={onOpenCommandPalette}
          className="sm:hidden p-2 text-text-muted hover:text-text rounded-md hover:bg-surface-elevated cursor-pointer"
          aria-label="Search"
        >
          <Search className="w-4 h-4" />
        </button>

        <button 
          onClick={() => navigate('/create')}
          className="flex items-center gap-2 bg-accent text-accent-foreground hover:bg-accent/90 px-3.5 py-1.5 sm:px-4 sm:py-2 rounded-lg text-xs sm:text-sm font-semibold transition-all shadow-sm shadow-accent/20 cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>Create Reel</span>
        </button>
      </div>
    </header>
  );
}
