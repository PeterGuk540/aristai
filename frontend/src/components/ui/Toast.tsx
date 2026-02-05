'use client';

import { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';
import { cn } from '@/lib/utils';

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
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
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
  const typeStyles: Record<ToastType, string> = {
    info: 'bg-blue-600 text-white',
    success: 'bg-green-600 text-white',
    error: 'bg-red-600 text-white',
    warning: 'bg-yellow-500 text-black',
  };

  const typeIcons: Record<ToastType, string> = {
    info: 'ℹ️',
    success: '✓',
    error: '✕',
    warning: '⚠',
  };

  return (
    <div
      className={cn(
        'pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg',
        'animate-in slide-in-from-right-full duration-300',
        'min-w-[280px] max-w-[400px]',
        typeStyles[toast.type]
      )}
    >
      <span className="text-lg flex-shrink-0">{typeIcons[toast.type]}</span>
      <span className="flex-1 text-sm font-medium">{toast.message}</span>
      <button
        onClick={() => onRemove(toast.id)}
        className="flex-shrink-0 opacity-70 hover:opacity-100 transition-opacity"
        aria-label="Dismiss"
      >
        ✕
      </button>
    </div>
  );
}
