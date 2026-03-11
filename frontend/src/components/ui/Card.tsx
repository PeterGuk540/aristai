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
        'rounded-[14px] transition-shadow duration-200',
        {
          'bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 shadow-sm':
            variant === 'default',
          'bg-white dark:bg-neutral-800 shadow-md':
            variant === 'elevated',
          'bg-transparent border border-neutral-200 dark:border-neutral-700':
            variant === 'outlined',
          'bg-neutral-50 dark:bg-neutral-800/30':
            variant === 'ghost',
        },
        hover && 'cursor-pointer hover:shadow-[0_8px_24px_rgba(0,0,0,0.05)] dark:hover:shadow-[0_8px_24px_rgba(0,0,0,0.3)]',
        {
          'p-0': padding === 'none',
          'p-4': padding === 'sm',
          'p-5': padding === 'md',
          'p-6': padding === 'lg',
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
        'px-5 py-4',
        border && 'border-b border-neutral-200 dark:border-neutral-700',
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
        'text-base font-semibold text-neutral-900 dark:text-white',
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
        'text-sm text-neutral-500 dark:text-neutral-400 mt-1',
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
      className={cn('px-5 py-4', className)}
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
        'px-5 py-4',
        border && 'border-t border-neutral-200 dark:border-neutral-700',
        background && 'bg-neutral-50 dark:bg-neutral-800/50',
        className
      )}
      {...props}
    />
  )
);
CardFooter.displayName = 'CardFooter';
