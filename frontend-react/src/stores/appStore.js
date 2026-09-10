import { create } from 'zustand';

export const useAppStore = create((set) => ({
  isSidebarOpen: false,
  setSidebarOpen: (isOpen) => set({ isSidebarOpen: isOpen }),
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),

  ollamaStatus: 'Checking...',
  setOllamaStatus: (status) => set({ ollamaStatus: status }),

  isYtAuthenticated: false,
  ytChannelName: '',
  setYtAuth: (isAuthenticated, channelName) => set({ isYtAuthenticated: isAuthenticated, ytChannelName: channelName }),
}));
