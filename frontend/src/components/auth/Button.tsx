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
        'bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900',
        'hover:bg-neutral-800 dark:hover:bg-neutral-200',
        'focus:ring-neutral-500',
        'disabled:bg-neutral-400 dark:disabled:bg-neutral-600'
      ),
      secondary: cn(
        'bg-neutral-100 text-neutral-800 dark:bg-neutral-800 dark:text-neutral-200',
        'hover:bg-neutral-200 dark:hover:bg-neutral-700',
        'focus:ring-neutral-500',
        'disabled:bg-neutral-100 dark:disabled:bg-neutral-800'
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
