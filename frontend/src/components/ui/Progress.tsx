import { cn } from '@/lib/utils';
import { HTMLAttributes, forwardRef } from 'react';

interface ProgressProps extends HTMLAttributes<HTMLDivElement> {
  value?: number;
  max?: number;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
}

export const Progress = forwardRef<HTMLDivElement, ProgressProps>(
  ({ className, value = 0, max = 100, variant = 'default', ...props }, ref) => {
    const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

    return (
      <div
        ref={ref}
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={max}
        className={cn(
          'w-full bg-stone-200 dark:bg-stone-700 rounded-full overflow-hidden',
          className
        )}
        {...props}
      >
        <div
          className={cn(
            'h-full transition-all duration-300 ease-out rounded-full',
            {
              'bg-primary-600 dark:bg-primary-500': variant === 'default',
              'bg-success-600 dark:bg-success-500': variant === 'success',
              'bg-warning-600 dark:bg-warning-500': variant === 'warning',
              'bg-danger-600 dark:bg-danger-500': variant === 'danger',
              'bg-info-600 dark:bg-info-500': variant === 'info',
            }
          )}
          style={{ width: `${percentage}%` }}
        />
      </div>
    );
  }
);

Progress.displayName = 'Progress';
