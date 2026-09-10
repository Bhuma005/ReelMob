import React, { useState, useRef, useEffect } from 'react';
import { Bell, CheckCircle2, AlertTriangle, Info, XCircle, Trash2, Check, ExternalLink } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { useNavigate } from 'react-router-dom';
import { useNotificationStore } from '../../stores/notificationStore';

export function NotificationCenter() {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);
  const navigate = useNavigate();

  const { 
    notifications, 
    markAsRead, 
    markAllAsRead, 
    clearAll 
  } = useNotificationStore();

  const unreadCount = notifications.filter((n) => !n.read).length;

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const handleItemClick = (notif) => {
    markAsRead(notif.id);
    if (notif.link) {
      setIsOpen(false);
      navigate(notif.link);
    }
  };

  const getTypeIcon = (type) => {
    switch (type) {
      case 'success':
        return <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />;
      case 'warning':
        return <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />;
      case 'error':
        return <XCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />;
      case 'info':
      default:
        return <Info className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />;
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Notifications"
        className="relative p-2 text-text-muted hover:text-text rounded-lg hover:bg-surface-elevated transition-colors cursor-pointer"
      >
        <Bell className="w-4 h-4" />
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 flex items-center justify-center min-w-[16px] h-4 px-1 text-[10px] font-bold text-black bg-accent rounded-full animate-in zoom-in-50">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Popover Dropdown */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-surface border border-border rounded-xl shadow-2xl overflow-hidden z-50 animate-in fade-in-50 zoom-in-95 duration-150">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-text uppercase tracking-wider">Notifications</span>
              {unreadCount > 0 && (
                <span className="px-1.5 py-0.5 text-[10px] font-medium bg-accent/20 text-accent rounded-full">
                  {unreadCount} new
                </span>
              )}
            </div>

            <div className="flex items-center gap-1">
              {unreadCount > 0 && (
                <button
                  type="button"
                  onClick={markAllAsRead}
                  className="p-1 rounded text-text-muted hover:text-text hover:bg-surface-2 transition-colors text-xs flex items-center gap-1"
                  title="Mark all as read"
                >
                  <Check className="w-3.5 h-3.5" />
                </button>
              )}
              {notifications.length > 0 && (
                <button
                  type="button"
                  onClick={clearAll}
                  className="p-1 rounded text-text-muted hover:text-rose-400 hover:bg-surface-2 transition-colors text-xs flex items-center gap-1"
                  title="Clear all"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* List */}
          <div className="max-h-[380px] overflow-y-auto divide-y divide-border/50">
            {notifications.length === 0 ? (
              <div className="py-8 text-center text-xs text-text-muted">
                No notifications right now.
              </div>
            ) : (
              notifications.map((notif) => {
                let timeStr = '';
                try {
                  timeStr = formatDistanceToNow(new Date(notif.timestamp), { addSuffix: true });
                } catch {
                  timeStr = 'recently';
                }

                return (
                  <div
                    key={notif.id}
                    onClick={() => handleItemClick(notif)}
                    className={`p-3 text-left transition-colors flex items-start gap-2.5 cursor-pointer ${
                      notif.read ? 'bg-surface/50 hover:bg-surface-elevated/40' : 'bg-surface-1 hover:bg-surface-2'
                    }`}
                  >
                    {getTypeIcon(notif.type)}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1 mb-0.5">
                        <p className={`text-xs truncate ${notif.read ? 'text-text-muted font-normal' : 'text-text font-semibold'}`}>
                          {notif.title}
                        </p>
                        <span className="text-[10px] text-text-muted shrink-0 font-mono">
                          {timeStr}
                        </span>
                      </div>
                      <p className="text-[11px] text-text-muted line-clamp-2 leading-relaxed">
                        {notif.message}
                      </p>
                      {notif.link && (
                        <div className="mt-1 flex items-center gap-1 text-[10px] text-accent hover:underline">
                          <span>View Details</span>
                          <ExternalLink className="w-2.5 h-2.5" />
                        </div>
                      )}
                    </div>
                    {!notif.read && (
                      <span className="w-1.5 h-1.5 rounded-full bg-accent shrink-0 mt-1.5" />
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
