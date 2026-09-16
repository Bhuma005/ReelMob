import { create } from 'zustand';

const getInitialTheme = () => {
  try {
    const stored = localStorage.getItem('reelsmob_theme');
    if (stored === 'light' || stored === 'dark') return stored;
  } catch (_) {}
  return 'dark';
};

const initialTheme = getInitialTheme();
if (typeof document !== 'undefined') {
  document.documentElement.setAttribute('data-theme', initialTheme);
}

export const useAppStore = create((set) => ({
  isSidebarOpen: false,
  setSidebarOpen: (isOpen) => set({ isSidebarOpen: isOpen }),
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),

  theme: initialTheme,
  setTheme: (theme) => {
    try {
      localStorage.setItem('reelsmob_theme', theme);
      if (typeof document !== 'undefined') {
        document.documentElement.setAttribute('data-theme', theme);
      }
    } catch (_) {}
    set({ theme });
  },
  toggleTheme: () => {
    set((state) => {
      const nextTheme = state.theme === 'light' ? 'dark' : 'light';
      try {
        localStorage.setItem('reelsmob_theme', nextTheme);
        if (typeof document !== 'undefined') {
          document.documentElement.setAttribute('data-theme', nextTheme);
        }
      } catch (_) {}
      return { theme: nextTheme };
    });
  },

  ollamaStatus: 'Checking...',
  setOllamaStatus: (status) => set({ ollamaStatus: status }),

  isYtAuthenticated: false,
  ytChannelName: '',
  setYtAuth: (isAuthenticated, channelName) => set({ isYtAuthenticated: isAuthenticated, ytChannelName: channelName }),
}));

