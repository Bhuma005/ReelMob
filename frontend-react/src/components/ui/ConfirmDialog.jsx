import React from 'react';
import { AlertTriangle, AlertCircle, HelpCircle } from 'lucide-react';
import { Button } from './Button';

export function ConfirmDialog({
  isOpen,
  title,
  description,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  confirmVariant = 'danger',
  icon = 'warning',
  isLoading = false,
  onConfirm,
  onClose,
}) {
  if (!isOpen) return null;

  const IconComponent = 
    icon === 'danger' ? AlertCircle :
    icon === 'info' ? HelpCircle : AlertTriangle;

  const iconColor = 
    confirmVariant === 'danger' ? 'text-danger bg-danger/10 border-danger/20' :
    'text-accent bg-accent/10 border-accent/20';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-xs">
      <div 
        className="w-full max-w-md bg-surface border border-border rounded-xl shadow-2xl overflow-hidden"
        role="dialog"
        aria-modal="true"
      >
        <div className="p-6">
          <div className="flex items-start gap-4">
            <div className={`p-3 rounded-lg border ${iconColor} shrink-0`}>
              <IconComponent className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-base font-semibold text-text">{title}</h3>
              <p className="mt-1.5 text-sm text-text-muted leading-relaxed">{description}</p>
            </div>
          </div>
        </div>

        <div className="px-6 py-4 bg-surface-elevated/50 border-t border-border flex items-center justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={isLoading}
            className="text-sm"
          >
            {cancelText}
          </Button>
          <Button
            type="button"
            variant={confirmVariant === 'danger' ? 'danger' : 'primary'}
            onClick={onConfirm}
            isLoading={isLoading}
            className={`text-sm ${confirmVariant === 'danger' ? 'bg-danger hover:bg-danger/90 text-white' : 'bg-accent text-accent-foreground'}`}
          >
            {confirmText}
          </Button>
        </div>
      </div>
    </div>
  );
}
