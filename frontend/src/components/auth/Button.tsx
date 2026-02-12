'use client';

import { ButtonHTMLAttributes, forwardRef } from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean;
  variant?: 'primary' | 'secondary' | 'outline';
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ children, loading, disabled, variant = 'primary', className, ...props }, ref) => {
    const isDisabled = disabled || loading;

    const variants = {
      primary: cn(
        'bg-amber-400 text-neutral-950 dark:bg-amber-300 dark:text-neutral-950',
        'hover:bg-amber-300 dark:hover:bg-amber-200',
        'focus:ring-amber-400',
        'disabled:bg-amber-200 dark:disabled:bg-amber-700'
      ),
      secondary: cn(
        'bg-sky-100 text-sky-900 dark:bg-sky-900/40 dark:text-sky-200',
        'hover:bg-sky-200 dark:hover:bg-sky-900/60',
        'focus:ring-sky-400',
        'disabled:bg-sky-50 dark:disabled:bg-sky-900/20'
      ),
      outline: cn(
        'bg-transparent text-neutral-800 dark:text-neutral-200 border border-neutral-300 dark:border-neutral-700',
        'hover:bg-neutral-50 dark:hover:bg-neutral-800',
        'focus:ring-neutral-500',
        'disabled:border-neutral-200 dark:disabled:border-neutral-800 disabled:text-neutral-400 dark:disabled:text-neutral-600'
      ),
    };

    return (
      <button
        ref={ref}
        disabled={isDisabled}
        className={cn(
          'w-full flex items-center justify-center gap-2 rounded-md px-4 py-3',
          'font-medium text-sm tracking-[0.01em]',
          'focus:outline-none focus:ring-2 focus:ring-offset-2 dark:focus:ring-offset-neutral-900',
          'transition-colors duration-200',
          'disabled:cursor-not-allowed',
          variants[variant],
          className
        )}
        {...props}
      >
        {loading && <Loader2 className="h-4 w-4 animate-spin" />}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
