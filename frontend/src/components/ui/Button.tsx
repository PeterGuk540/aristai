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
          'inline-flex items-center justify-center font-medium rounded-lg',
          'transition-colors duration-200',
          'focus:outline-none focus:ring-2 focus:ring-offset-2',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'cursor-pointer select-none',
          {
            'bg-neutral-900 text-white hover:bg-neutral-800 active:bg-black focus:ring-neutral-500 dark:bg-white dark:text-neutral-900 dark:hover:bg-neutral-200':
              variant === 'primary',
            'bg-neutral-100 text-neutral-700 hover:bg-neutral-200 focus:ring-neutral-400 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700':
              variant === 'secondary',
            'border border-neutral-300 bg-white text-neutral-700 hover:bg-neutral-50 focus:ring-neutral-400 dark:border-neutral-600 dark:bg-transparent dark:text-neutral-200 dark:hover:bg-neutral-800':
              variant === 'outline',
            'text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100 focus:ring-neutral-400 dark:text-neutral-400 dark:hover:text-white dark:hover:bg-neutral-800':
              variant === 'ghost',
            'bg-danger-600 text-white hover:bg-danger-700 focus:ring-danger-500 shadow-sm':
              variant === 'danger',
            'bg-[#f5c842] text-neutral-900 hover:bg-[#e6ba3a] focus:ring-[#f5c842]':
              variant === 'accent',
          },
          {
            'px-3 py-1.5 text-xs gap-1.5': size === 'sm',
            'px-4 py-2 text-sm gap-2': size === 'md',
            'px-5 py-2.5 text-base gap-2.5': size === 'lg',
            'px-6 py-3 text-base gap-3': size === 'xl',
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
