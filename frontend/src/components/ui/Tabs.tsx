'use client';

import { cn } from '@/lib/utils';
import { createContext, useContext, useState, ReactNode, useEffect } from 'react';

interface TabsContextType {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

const TabsContext = createContext<TabsContextType | undefined>(undefined);

interface TabsProps {
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
  children: ReactNode;
  className?: string;
}

export function Tabs({ defaultValue, value, onValueChange, children, className }: TabsProps) {
  // Support both controlled and uncontrolled modes
  const [internalTab, setInternalTab] = useState(value || defaultValue || '');

  // Sync internal state with controlled value
  useEffect(() => {
    if (value !== undefined) {
      setInternalTab(value);
    }
  }, [value]);

  const activeTab = value !== undefined ? value : internalTab;

  const setActiveTab = (tab: string) => {
    if (value === undefined) {
      setInternalTab(tab);
    }
    onValueChange?.(tab);
  };

  return (
    <TabsContext.Provider value={{ activeTab, setActiveTab }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  );
}

interface TabsListProps {
  children: ReactNode;
  className?: string;
  variant?: 'default' | 'pills' | 'underline';
}

export function TabsList({ children, className, variant = 'default' }: TabsListProps) {
  return (
    <div
      className={cn(
        'inline-flex items-center',
        {
          // Default - contained pills
          'gap-1 rounded-xl bg-neutral-100 dark:bg-neutral-800 p-1':
            variant === 'default',
          // Pills - separate buttons
          'gap-2':
            variant === 'pills',
          // Underline - bottom border style
          'gap-6 border-b border-neutral-200 dark:border-neutral-700':
            variant === 'underline',
        },
        className
      )}
      data-variant={variant}
    >
      {children}
    </div>
  );
}

export interface TabsTriggerProps {
  value: string;
  children: ReactNode;
  className?: string;
  disabled?: boolean;
  'data-voice-id'?: string;
}

export function TabsTrigger({ value, children, className, disabled, 'data-voice-id': voiceId }: TabsTriggerProps) {
  const context = useContext(TabsContext);
  if (!context) throw new Error('TabsTrigger must be used within Tabs');

  const { activeTab, setActiveTab } = context;
  const isActive = activeTab === value;

  return (
    <button
      onClick={() => !disabled && setActiveTab(value)}
      disabled={disabled}
      data-voice-id={voiceId || `tab-${value}`}
      data-state={isActive ? 'active' : 'inactive'}
      className={cn(
        // Base styles
        'px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200',
        'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
        // Active state
        isActive
          ? 'bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white shadow-soft'
          : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white hover:bg-white/50 dark:hover:bg-neutral-700/50',
        // Disabled state
        disabled && 'opacity-50 cursor-not-allowed pointer-events-none',
        // Underline variant specific styles (handled via parent data attribute)
        'group-data-[variant=underline]:rounded-none group-data-[variant=underline]:shadow-none',
        className
      )}
    >
      {children}
    </button>
  );
}

interface TabsContentProps {
  value: string;
  children: ReactNode;
  className?: string;
}

export function TabsContent({ value, children, className }: TabsContentProps) {
  const context = useContext(TabsContext);
  if (!context) throw new Error('TabsContent must be used within Tabs');

  const { activeTab } = context;

  if (activeTab !== value) return null;

  return (
    <div
      className={cn(
        'mt-4 animate-fade-in',
        className
      )}
    >
      {children}
    </div>
  );
}
