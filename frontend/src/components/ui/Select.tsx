import { cn } from '@/lib/utils';
import { SelectHTMLAttributes, forwardRef } from 'react';

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  hint?: string;
  variant?: 'default' | 'filled';
  selectSize?: 'sm' | 'md' | 'lg';
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, error, hint, variant = 'default', selectSize = 'md', children, ...props }, ref) => (
    <div className="w-full">
      {label && (
        <label className="block text-xs font-semibold uppercase tracking-[0.08em] text-neutral-600 dark:text-neutral-400 mb-2">
          {label}
        </label>
      )}
      <div className="relative">
        <select
          ref={ref}
          className={cn(
            // Base styles
            'w-full rounded-2xl transition-colors duration-200 appearance-none',
            'text-neutral-900 dark:text-neutral-100',
            'focus:outline-none focus:ring-2 focus:ring-offset-0',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'cursor-pointer',
            // Variant styles
            {
              // Default - bordered, neutral focus
              'bg-white dark:bg-[#1c1c1e] border border-neutral-200 dark:border-neutral-700 focus:border-neutral-400 focus:ring-neutral-400/20':
                variant === 'default' && !error,
              // Filled - subtle background
              'bg-neutral-100/60 dark:bg-neutral-800/40 border border-transparent focus:border-neutral-400 focus:ring-neutral-400/20 focus:bg-white dark:focus:bg-[#1c1c1e]':
                variant === 'filled' && !error,
            },
            // Error state
            error && 'border-danger-500 focus:border-danger-500 focus:ring-danger-500/20 bg-danger-50/50 dark:bg-danger-900/10',
            // Size styles with padding for arrow
            {
              'pl-3 pr-8 py-1.5 text-sm': selectSize === 'sm',
              'pl-4 pr-10 py-2.5 text-sm': selectSize === 'md',
              'pl-4 pr-10 py-3 text-base': selectSize === 'lg',
            },
            className
          )}
          {...props}
        >
          {children}
        </select>
        {/* Custom dropdown arrow */}
        <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
          <svg
            className={cn(
              "text-neutral-400 dark:text-neutral-500",
              selectSize === 'sm' ? 'w-4 h-4' : 'w-5 h-5'
            )}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
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
Select.displayName = 'Select';
