import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const useNotificationStore = create(
  persist(
    (set, get) => ({
      notifications: [
        {
          id: 'welcome-notification',
          title: 'Welcome to Reels Studio',
          message: 'Video trimmer, color grading, and subtitle burn-in tools are ready to use.',
          type: 'info',
          timestamp: new Date().toISOString(),
          read: false,
        }
      ],

      unreadCount: () => {
        return get().notifications.filter((n) => !n.read).length;
      },

      addNotification: ({ title, message, type = 'info', link = null }) => {
        const newNotif = {
          id: `notif-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
          title,
          message,
          type,
          link,
          timestamp: new Date().toISOString(),
          read: false,
        };
        set((state) => ({
          notifications: [newNotif, ...state.notifications].slice(0, 50), // keep latest 50
        }));
      },

      markAsRead: (id) => {
        set((state) => ({
          notifications: state.notifications.map((n) =>
            n.id === id ? { ...n, read: true } : n
          ),
        }));
      },

      markAllAsRead: () => {
        set((state) => ({
          notifications: state.notifications.map((n) => ({ ...n, read: true })),
        }));
      },

      clearNotification: (id) => {
        set((state) => ({
          notifications: state.notifications.filter((n) => n.id !== id),
        }));
      },

      clearAll: () => {
        set({ notifications: [] });
      },
    }),
    {
      name: 'reelsmob-notifications-storage',
    }
  )
);
