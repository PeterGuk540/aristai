import { cn } from '@/lib/utils';
import { HTMLAttributes, forwardRef } from 'react';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'accent';
  size?: 'sm' | 'md' | 'lg';
  dot?: boolean;
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = 'default', size = 'md', dot = false, children, ...props }, ref) => (
    <span
      ref={ref}
      className={cn(
        // Base styles
        'inline-flex items-center font-semibold rounded-full transition-colors',
        // Variant styles
        {
          // Default - neutral
          'bg-stone-100 text-stone-700 dark:bg-stone-900/50 dark:text-stone-300':
            variant === 'default',
          // Primary - blue
          'bg-primary-100 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300':
            variant === 'primary',
          // Success - green
          'bg-success-100 text-success-700 dark:bg-success-900/40 dark:text-success-300':
            variant === 'success',
          // Warning - orange/amber
          'bg-warning-100 text-warning-700 dark:bg-warning-900/40 dark:text-warning-300':
            variant === 'warning',
          // Danger - red
          'bg-danger-100 text-danger-700 dark:bg-danger-900/40 dark:text-danger-300':
            variant === 'danger',
          // Info - blue (lighter than primary)
          'bg-info-100 text-info-700 dark:bg-info-900/40 dark:text-info-300':
            variant === 'info',
          // Accent - gold
          'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300':
            variant === 'accent',
        },
        // Size styles
        {
          'px-2 py-0.5 text-xs': size === 'sm',
          'px-2.5 py-0.5 text-xs': size === 'md',
          'px-3 py-1 text-sm': size === 'lg',
        },
        className
      )}
      {...props}
    >
      {dot && (
        <span
          className={cn(
            'rounded-full mr-1.5',
            {
              'w-1.5 h-1.5': size === 'sm',
              'w-2 h-2': size === 'md',
              'w-2.5 h-2.5': size === 'lg',
            },
            {
              'bg-neutral-500': variant === 'default',
              'bg-primary-500': variant === 'primary',
              'bg-success-500': variant === 'success',
              'bg-warning-500': variant === 'warning',
              'bg-danger-500': variant === 'danger',
              'bg-info-500': variant === 'info',
              'bg-accent-500': variant === 'accent',
            }
          )}
        />
      )}
      {children}
    </span>
  )
);
Badge.displayName = 'Badge';
