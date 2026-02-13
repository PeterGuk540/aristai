'use client';

import { useState, useRef, useEffect } from 'react';
import { LogOut, Settings, ChevronDown } from 'lucide-react';
import { useAuth } from '@/lib/auth-context';
import { cn } from '@/lib/utils';
import { useTranslations } from 'next-intl';

export function UserMenu() {
  const { user, signOut } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const t = useTranslations();

  // Close menu on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Close menu on Escape key
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, []);

  // Listen for voice commands to trigger menu actions directly
  useEffect(() => {
    const handleVoiceMenuAction = (event: CustomEvent) => {
      const { action } = event.detail || {};
      console.log('UserMenu: Voice action received:', action);

      if (action === 'open-profile') {
        setIsOpen(false);
        alert('Profile page coming soon');
      } else if (action === 'sign-out') {
        setIsOpen(false);
        signOut();
      }
    };

    window.addEventListener('voice-menu-action', handleVoiceMenuAction as EventListener);
    return () => window.removeEventListener('voice-menu-action', handleVoiceMenuAction as EventListener);
  }, [signOut]);

  const displayName = user?.name || user?.email?.split('@')[0] || 'User';
  const initials = displayName.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'flex items-center gap-3 px-3 py-2 rounded-xl',
          'bg-stone-50 dark:bg-stone-900/40 border border-stone-200 dark:border-primary-900/20',
          'text-neutral-700 dark:text-neutral-200',
          'hover:bg-stone-100 dark:hover:bg-stone-900/60',
          'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 dark:focus:ring-offset-neutral-800',
          'transition-all duration-200'
        )}
        aria-expanded={isOpen}
        aria-haspopup="true"
        data-voice-id="user-menu"
      >
        <div className="h-8 w-8 rounded-full bg-slate-900 dark:bg-white flex items-center justify-center shadow-sm">
          <span className="text-xs font-semibold text-white dark:text-slate-900">{initials}</span>
        </div>
        <span className="hidden sm:block text-sm font-medium max-w-[150px] truncate">
          {displayName}
        </span>
        <ChevronDown
          className={cn(
            'h-4 w-4 text-neutral-400 transition-transform duration-200',
            isOpen && 'transform rotate-180'
          )}
        />
      </button>

      {/* Dropdown menu */}
      {isOpen && (
        <div
          className={cn(
            'absolute right-0 mt-2 w-72 rounded-xl',
            'bg-white dark:bg-[#1a150c]',
            'border border-stone-200 dark:border-primary-900/20',
            'shadow-soft-md',
            'overflow-hidden',
            'z-50',
            'animate-fade-in'
          )}
          role="menu"
        >
          {/* User info header */}
          <div className="px-4 py-4 bg-stone-50 dark:bg-stone-900/40 border-b border-stone-200 dark:border-primary-900/20">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-full bg-slate-900 dark:bg-white flex items-center justify-center shadow-sm">
                <span className="text-sm font-semibold text-white dark:text-slate-900">{initials}</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-neutral-900 dark:text-white truncate">
                  {user?.name || 'User'}
                </p>
                <p className="text-xs text-neutral-500 dark:text-neutral-400 truncate">
                  {user?.email}
                </p>
              </div>
            </div>
          </div>

          {/* Menu items */}
          <div className="py-2">
            <button
              onClick={() => {
                setIsOpen(false);
                // TODO: Open profile modal or navigate to profile page
                alert('Profile page coming soon');
              }}
              className={cn(
                'w-full flex items-center gap-3 px-4 py-2.5 text-sm',
                'text-neutral-700 dark:text-neutral-200',
                'hover:bg-stone-100 dark:hover:bg-stone-900/50',
                'transition-colors duration-200'
              )}
              role="menuitem"
              data-voice-id="open-profile"
            >
              <div className="p-1.5 rounded-lg bg-neutral-100 dark:bg-neutral-700">
                <Settings className="h-4 w-4 text-neutral-600 dark:text-neutral-400" />
              </div>
              <span className="flex-1 text-left">{t('user.profile')}</span>
            </button>

            {/* Divider */}
            <div className="my-2 mx-4 border-t border-stone-200 dark:border-primary-900/20" />

            <button
              onClick={() => {
                setIsOpen(false);
                signOut();
              }}
              className={cn(
                'w-full flex items-center gap-3 px-4 py-2.5 text-sm',
                'text-danger-600 dark:text-danger-400',
                'hover:bg-danger-50 dark:hover:bg-danger-900/20',
                'transition-colors duration-200'
              )}
              role="menuitem"
              data-voice-id="sign-out"
            >
              <div className="p-1.5 rounded-lg bg-danger-100 dark:bg-danger-900/50">
                <LogOut className="h-4 w-4" />
              </div>
              <span className="flex-1 text-left">{t('user.signOut')}</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
