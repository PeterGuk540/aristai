'use client';

import { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';

export type ToastType = 'info' | 'success' | 'error' | 'warning';

interface Toast {
  id: string;
  message: string;
  type: ToastType;
  duration?: number;
}

interface ToastContextType {
  showToast: (message: string, type?: ToastType, duration?: number) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}

interface ToastProviderProps {
  children: ReactNode;
}

export function ToastProvider({ children }: ToastProviderProps) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, type: ToastType = 'info', duration = 4000) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const newToast: Toast = { id, message, type, duration };

    setToasts(prev => [...prev, newToast]);

    if (duration > 0) {
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
      }, duration);
    }
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // Listen for ui.toast CustomEvents from voice actions
  useEffect(() => {
    const handleToastEvent = (event: CustomEvent) => {
      const { message, type = 'info', duration } = event.detail || {};
      if (message) {
        showToast(message, type, duration);
      }
    };

    window.addEventListener('ui.toast', handleToastEvent as EventListener);
    return () => {
      window.removeEventListener('ui.toast', handleToastEvent as EventListener);
    };
  }, [showToast]);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </ToastContext.Provider>
  );
}

interface ToastContainerProps {
  toasts: Toast[];
  onRemove: (id: string) => void;
}

function ToastContainer({ toasts, onRemove }: ToastContainerProps) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-3 pointer-events-none">
      {toasts.map(toast => (
        <ToastItem key={toast.id} toast={toast} onRemove={onRemove} />
      ))}
    </div>
  );
}

interface ToastItemProps {
  toast: Toast;
  onRemove: (id: string) => void;
}

function ToastItem({ toast, onRemove }: ToastItemProps) {
  const typeConfig: Record<ToastType, { bg: string; border: string; icon: typeof Info; iconColor: string }> = {
    info: {
      bg: 'bg-white dark:bg-neutral-800',
      border: 'border-primary-200 dark:border-primary-800',
      icon: Info,
      iconColor: 'text-primary-500',
    },
    success: {
      bg: 'bg-white dark:bg-neutral-800',
      border: 'border-success-200 dark:border-success-800',
      icon: CheckCircle,
      iconColor: 'text-success-500',
    },
    error: {
      bg: 'bg-white dark:bg-neutral-800',
      border: 'border-danger-200 dark:border-danger-800',
      icon: XCircle,
      iconColor: 'text-danger-500',
    },
    warning: {
      bg: 'bg-white dark:bg-neutral-800',
      border: 'border-warning-200 dark:border-warning-800',
      icon: AlertTriangle,
      iconColor: 'text-warning-500',
    },
  };

  const config = typeConfig[toast.type];
  const Icon = config.icon;

  return (
    <div
      className={cn(
        'pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl',
        'shadow-soft-md border',
        'animate-slide-up',
        'min-w-[320px] max-w-[420px]',
        config.bg,
        config.border
      )}
    >
      <Icon className={cn('h-5 w-5 flex-shrink-0 mt-0.5', config.iconColor)} />
      <span className="flex-1 text-sm font-medium text-neutral-700 dark:text-neutral-200">
        {toast.message}
      </span>
      <button
        onClick={() => onRemove(toast.id)}
        className="flex-shrink-0 p-1 rounded-lg text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
