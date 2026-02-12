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
        <label className="block text-xs font-semibold uppercase tracking-[0.08em] text-neutral-600 dark:text-neutral-400 mb-2">
          {label}
        </label>
      )}
      <input
        ref={ref}
        className={cn(
          // Base styles
          'w-full rounded-xl transition-all duration-200',
          'text-neutral-900 dark:text-neutral-100',
          'placeholder:text-neutral-400 dark:placeholder:text-neutral-500',
          'focus:outline-none focus:ring-2 focus:ring-offset-0',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          // Variant styles
          {
            // Default - bordered
            'bg-white dark:bg-[#1a150c] border border-stone-300 dark:border-stone-700 focus:border-amber-500 focus:ring-amber-500/20':
              variant === 'default' && !error,
            // Filled - subtle background
            'bg-stone-50 dark:bg-stone-900/40 border border-transparent focus:border-amber-500 focus:ring-amber-500/20 focus:bg-white dark:focus:bg-[#1a150c]':
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
