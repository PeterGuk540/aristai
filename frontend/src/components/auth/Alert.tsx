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
      bg: 'bg-emerald-50 dark:bg-emerald-950/30',
      border: 'border-emerald-200 dark:border-emerald-900',
      text: 'text-emerald-800 dark:text-emerald-200',
      icon: CheckCircle,
    },
    info: {
      bg: 'bg-sky-50 dark:bg-sky-950/30',
      border: 'border-sky-200 dark:border-sky-900',
      text: 'text-sky-800 dark:text-sky-200',
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
