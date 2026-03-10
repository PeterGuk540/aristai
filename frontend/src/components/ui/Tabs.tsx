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
  const [internalTab, setInternalTab] = useState(value || defaultValue || '');

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
          'gap-4 border-b border-neutral-200 dark:border-neutral-700':
            variant === 'default' || variant === 'underline',
          'gap-2':
            variant === 'pills',
        },
        className
      )}
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
        'px-1 pb-2 text-sm font-medium transition-colors duration-200 border-b-2 -mb-px',
        'focus:outline-none',
        isActive
          ? 'border-primary-600 text-neutral-900 dark:text-white dark:border-primary-400'
          : 'border-transparent text-neutral-500 hover:text-neutral-700 dark:text-neutral-400 dark:hover:text-neutral-200',
        disabled && 'opacity-50 cursor-not-allowed pointer-events-none',
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
    <div className={cn('mt-4', className)}>
      {children}
    </div>
  );
}
