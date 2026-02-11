import { cn } from '@/lib/utils';
import { InputHTMLAttributes, forwardRef } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  variant?: 'default' | 'filled';
  inputSize?: 'sm' | 'md' | 'lg';
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, hint, variant = 'default', inputSize = 'md', ...props }, ref) => (
    <div className="w-full">
      {label && (
        <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1.5">
          {label}
        </label>
      )}
      <input
        ref={ref}
        className={cn(
          // Base styles
          'w-full rounded-lg transition-all duration-200',
          'text-neutral-900 dark:text-neutral-100',
          'placeholder:text-neutral-400 dark:placeholder:text-neutral-500',
          'focus:outline-none focus:ring-2 focus:ring-offset-0',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          // Variant styles
          {
            // Default - bordered
            'bg-white dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-600 focus:border-primary-500 focus:ring-primary-500/20':
              variant === 'default' && !error,
            // Filled - subtle background
            'bg-neutral-100 dark:bg-neutral-800 border border-transparent focus:border-primary-500 focus:ring-primary-500/20 focus:bg-white dark:focus:bg-neutral-900':
              variant === 'filled' && !error,
          },
          // Error state
          error && 'border-danger-500 focus:border-danger-500 focus:ring-danger-500/20 bg-danger-50/50 dark:bg-danger-900/10',
          // Size styles
          {
            'px-3 py-1.5 text-sm': inputSize === 'sm',
            'px-4 py-2.5 text-sm': inputSize === 'md',
            'px-4 py-3 text-base': inputSize === 'lg',
          },
          className
        )}
        {...props}
      />
      {hint && !error && (
        <p className="mt-1.5 text-xs text-neutral-500 dark:text-neutral-400">{hint}</p>
      )}
      {error && (
        <p className="mt-1.5 text-sm text-danger-600 dark:text-danger-400 flex items-center gap-1">
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
          {error}
        </p>
      )}
    </div>
  )
);
Input.displayName = 'Input';
