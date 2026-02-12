import { cn } from '@/lib/utils';
import { HTMLAttributes, forwardRef } from 'react';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'elevated' | 'outlined' | 'ghost';
  hover?: boolean;
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant = 'default', hover = false, padding = 'none', ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        // Base styles
        'rounded-xl transition-all duration-200',
        // Variant styles
        {
          // Default - stitched surface
          'bg-white dark:bg-[#1a150c] border border-stone-200 dark:border-primary-900/20 shadow-sm':
            variant === 'default',
          // Elevated - more prominent shadow
          'bg-white dark:bg-[#1a150c] border border-stone-200 dark:border-primary-900/20 shadow-md':
            variant === 'elevated',
          // Outlined - border only
          'bg-transparent border border-stone-300 dark:border-stone-700':
            variant === 'outlined',
          // Ghost - minimal
          'bg-stone-50 dark:bg-stone-900/30':
            variant === 'ghost',
        },
        // Hover effect
        hover && 'cursor-pointer hover:shadow-md hover:-translate-y-[1px]',
        // Padding
        {
          'p-0': padding === 'none',
          'p-4': padding === 'sm',
          'p-6': padding === 'md',
          'p-8': padding === 'lg',
        },
        className
      )}
      {...props}
    />
  )
);
Card.displayName = 'Card';

interface CardHeaderProps extends HTMLAttributes<HTMLDivElement> {
  border?: boolean;
}

export const CardHeader = forwardRef<HTMLDivElement, CardHeaderProps>(
  ({ className, border = true, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'px-6 py-4',
        border && 'border-b border-stone-200 dark:border-primary-900/20',
        className
      )}
      {...props}
    />
  )
);
CardHeader.displayName = 'CardHeader';

export const CardTitle = forwardRef<HTMLHeadingElement, HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3
      ref={ref}
      className={cn(
        'text-lg font-semibold text-neutral-900 dark:text-white',
        'tracking-tight',
        className
      )}
      {...props}
    />
  )
);
CardTitle.displayName = 'CardTitle';

export const CardDescription = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p
      ref={ref}
      className={cn(
        'text-sm text-neutral-600 dark:text-neutral-400 mt-1',
        className
      )}
      {...props}
    />
  )
);
CardDescription.displayName = 'CardDescription';

export const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('px-6 py-4', className)}
      {...props}
    />
  )
);
CardContent.displayName = 'CardContent';

interface CardFooterProps extends HTMLAttributes<HTMLDivElement> {
  border?: boolean;
  background?: boolean;
}

export const CardFooter = forwardRef<HTMLDivElement, CardFooterProps>(
  ({ className, border = true, background = true, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'px-6 py-4',
        border && 'border-t border-stone-200 dark:border-primary-900/20',
        background && 'bg-stone-50 dark:bg-stone-900/25',
        className
      )}
      {...props}
    />
  )
);
CardFooter.displayName = 'CardFooter';
