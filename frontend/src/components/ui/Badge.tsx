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
        'inline-flex items-center font-medium rounded-full transition-colors',
        {
          'bg-neutral-100 text-neutral-700 dark:bg-neutral-700 dark:text-neutral-300':
            variant === 'default' || variant === 'primary',
          'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300':
            variant === 'success',
          'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300':
            variant === 'warning',
          'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300':
            variant === 'danger',
          'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300':
            variant === 'info',
          'bg-[#f5c842]/10 text-[#a16207] dark:bg-[#f5c842]/20 dark:text-[#f5c842]':
            variant === 'accent',
        },
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
              'bg-neutral-500': variant === 'default' || variant === 'primary',
              'bg-green-500': variant === 'success',
              'bg-amber-500': variant === 'warning',
              'bg-red-500': variant === 'danger',
              'bg-blue-500': variant === 'info',
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
