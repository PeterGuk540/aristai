'use client';

import { AlertCircle, CheckCircle, Info, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface AlertProps {
  type: 'error' | 'success' | 'info' | 'warning';
  message: string;
  className?: string;
}

export function Alert({ type, message, className }: AlertProps) {
  const styles = {
    error: {
      bg: 'bg-red-50 dark:bg-red-950/30',
      border: 'border-red-200 dark:border-red-900',
      text: 'text-red-800 dark:text-red-200',
      icon: XCircle,
    },
    success: {
      bg: 'bg-green-50 dark:bg-green-950/30',
      border: 'border-green-200 dark:border-green-900',
      text: 'text-green-800 dark:text-green-200',
      icon: CheckCircle,
    },
    info: {
      bg: 'bg-neutral-50 dark:bg-neutral-900',
      border: 'border-neutral-300 dark:border-neutral-700',
      text: 'text-neutral-700 dark:text-neutral-300',
      icon: Info,
    },
    warning: {
      bg: 'bg-amber-50 dark:bg-amber-950/30',
      border: 'border-amber-200 dark:border-amber-900',
      text: 'text-amber-800 dark:text-amber-200',
      icon: AlertCircle,
    },
  };

  const { bg, border, text, icon: Icon } = styles[type];

  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-md border p-3.5',
        bg,
        border,
        text,
        className
      )}
      role="alert"
      aria-live="polite"
    >
      <Icon className="h-5 w-5 flex-shrink-0 mt-0.5" />
      <p className="text-sm leading-relaxed">{message}</p>
    </div>
  );
}
