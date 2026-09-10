import React, { useState, useEffect, Suspense } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import { Toaster } from 'sonner';
import { CommandPalette } from '../ui/CommandPalette';
import { LayoutDashboard, PlusCircle, Library, Calendar, Settings } from 'lucide-react';

export default function AppLayout() {
  const [isCommandOpen, setIsCommandOpen] = useState(false);

  // Global keyboard shortcut for Command Palette
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setIsCommandOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const mobileNavLinks = [
    { to: '/', icon: LayoutDashboard, label: 'Home' },
    { to: '/create', icon: PlusCircle, label: 'Create' },
    { to: '/library', icon: Library, label: 'Library' },
    { to: '/scheduler', icon: Calendar, label: 'Schedule' },
    { to: '/settings', icon: Settings, label: 'Settings' },
  ];

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />

      <div className="flex flex-col flex-1 w-full overflow-hidden">
        <Topbar onOpenCommandPalette={() => setIsCommandOpen(true)} />
        
        <main className="flex-1 overflow-y-auto p-4 md:p-8 pb-20 sm:pb-8">
          <div className="max-w-6xl mx-auto">
            <Suspense fallback={
              <div className="space-y-6 animate-pulse p-2">
                <div className="h-8 w-64 bg-surface-2 rounded-lg" />
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="h-24 bg-surface-2 rounded-xl" />
                  <div className="h-24 bg-surface-2 rounded-xl" />
                  <div className="h-24 bg-surface-2 rounded-xl" />
                  <div className="h-24 bg-surface-2 rounded-xl" />
                </div>
                <div className="h-96 bg-surface-2 rounded-2xl" />
              </div>
            }>
              <Outlet />
            </Suspense>
          </div>
        </main>

        {/* Mobile Bottom Navigation (Visible under 640px) */}
        <nav 
          aria-label="Mobile Bottom Navigation"
          className="sm:hidden fixed bottom-0 inset-x-0 h-14 bg-surface/90 backdrop-blur-md border-t border-border flex items-center justify-around px-2 z-40"
        >
          {mobileNavLinks.map((link) => {
            const Icon = link.icon;
            return (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  `flex flex-col items-center justify-center gap-0.5 px-3 py-1 rounded-lg text-[10px] font-medium transition-colors ${
                    isActive
                      ? 'text-accent font-semibold'
                      : 'text-text-muted hover:text-text'
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                <span>{link.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>

      <CommandPalette 
        isOpen={isCommandOpen} 
        onClose={() => setIsCommandOpen(false)} 
      />

      <Toaster 
        theme="dark" 
        position="bottom-right" 
        richColors 
        closeButton 
      />
    </div>
  );
}
