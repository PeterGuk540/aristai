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
        'bg-primary-600 text-white',
        'hover:bg-primary-700',
        'focus:ring-primary-500',
        'disabled:bg-primary-400'
      ),
      secondary: cn(
        'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-200',
        'hover:bg-gray-200 dark:hover:bg-gray-600',
        'focus:ring-gray-500',
        'disabled:bg-gray-100 dark:disabled:bg-gray-700'
      ),
      outline: cn(
        'bg-transparent text-primary-600 dark:text-primary-400 border-2 border-primary-600 dark:border-primary-400',
        'hover:bg-primary-50 dark:hover:bg-primary-900/20',
        'focus:ring-primary-500',
        'disabled:border-primary-300 disabled:text-primary-300'
      ),
    };

    return (
      <button
        ref={ref}
        disabled={isDisabled}
        className={cn(
          'w-full flex items-center justify-center gap-2 rounded-lg px-4 py-3',
          'font-medium text-sm',
          'focus:outline-none focus:ring-2 focus:ring-offset-2 dark:focus:ring-offset-gray-800',
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
