import { cn } from '@/lib/utils';
import { ButtonHTMLAttributes, forwardRef } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger' | 'accent';
  size?: 'sm' | 'md' | 'lg' | 'xl';
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', loading = false, children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(
          // Base styles
          'inline-flex items-center justify-center font-semibold rounded-xl',
          'transition-all duration-200 ease-out',
          'focus:outline-none focus:ring-2 focus:ring-offset-2',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'cursor-pointer select-none',
          // Variant styles
          {
            // Primary - stitched dark action
            'bg-slate-900 text-white hover:bg-slate-800 active:bg-black focus:ring-slate-500 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-100':
              variant === 'primary',
            // Secondary - subtle neutral surface
            'bg-stone-100 text-stone-800 hover:bg-stone-200 active:bg-stone-300 focus:ring-stone-400 dark:bg-stone-900 dark:text-stone-200 dark:hover:bg-stone-800':
              variant === 'secondary',
            // Outline - stitched border tone
            'border border-stone-300 bg-white text-stone-700 hover:border-stone-400 hover:text-stone-900 hover:bg-stone-50 focus:ring-stone-400 dark:border-stone-700 dark:bg-transparent dark:text-stone-200 dark:hover:border-stone-500 dark:hover:text-stone-100':
              variant === 'outline',
            // Ghost - Minimal
            'text-stone-600 hover:text-stone-900 hover:bg-stone-100 focus:ring-stone-400 dark:text-stone-400 dark:hover:text-white dark:hover:bg-stone-800':
              variant === 'ghost',
            // Danger - Red
            'bg-danger-600 text-white hover:bg-danger-700 active:bg-danger-800 focus:ring-danger-500 shadow-sm':
              variant === 'danger',
            // Accent - stitched amber CTA
            'bg-amber-500 text-white hover:bg-amber-600 active:bg-amber-700 focus:ring-amber-400':
              variant === 'accent',
          },
          // Size styles
          {
            'px-3 py-1.5 text-xs gap-1.5': size === 'sm',
            'px-4 py-2.5 text-sm gap-2': size === 'md',
            'px-5 py-3 text-base gap-2.5': size === 'lg',
            'px-6 py-3.5 text-base gap-3': size === 'xl',
          },
          className
        )}
        {...props}
      >
        {loading && (
          <svg
            className="animate-spin -ml-1 h-4 w-4"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
