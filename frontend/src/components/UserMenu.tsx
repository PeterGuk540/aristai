'use client';

import { useState, useRef, useEffect } from 'react';
import { User, LogOut, Settings, ChevronDown, HelpCircle, Mic, BookOpen } from 'lucide-react';
import { useAuth } from '@/lib/auth-context';
import { cn } from '@/lib/utils';

interface UserMenuProps {
  onShowGuide?: () => void;
  onShowVoiceGuide?: () => void;
}

export function UserMenu({ onShowGuide, onShowVoiceGuide }: UserMenuProps) {
  const { user, signOut } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

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
      console.log('🎤 UserMenu: Voice action received:', action);

      if (action === 'view-voice-guide') {
        setIsOpen(false);
        onShowVoiceGuide?.();
      } else if (action === 'forum-instructions') {
        setIsOpen(false);
        onShowGuide?.();
      } else if (action === 'open-profile') {
        setIsOpen(false);
        alert('Profile page coming soon');
      } else if (action === 'sign-out') {
        setIsOpen(false);
        signOut();
      }
    };

    window.addEventListener('voice-menu-action', handleVoiceMenuAction as EventListener);
    return () => window.removeEventListener('voice-menu-action', handleVoiceMenuAction as EventListener);
  }, [onShowVoiceGuide, onShowGuide, signOut]);

  const displayName = user?.name || user?.email?.split('@')[0] || 'User';

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'flex items-center gap-2 px-3 py-2 rounded-lg',
          'text-gray-700 dark:text-gray-200',
          'hover:bg-gray-100 dark:hover:bg-gray-700',
          'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800',
          'transition-colors duration-200'
        )}
        aria-expanded={isOpen}
        aria-haspopup="true"
        data-voice-id="user-menu"
      >
        <div className="h-8 w-8 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center">
          <User className="h-4 w-4 text-primary-600 dark:text-primary-400" />
        </div>
        <span className="hidden sm:block text-sm font-medium max-w-[150px] truncate">
          {displayName}
        </span>
        <ChevronDown
          className={cn(
            'h-4 w-4 transition-transform duration-200',
            isOpen && 'transform rotate-180'
          )}
        />
      </button>

      {/* Dropdown menu */}
      {isOpen && (
        <div
          className={cn(
            'absolute right-0 mt-2 w-64 rounded-lg',
            'bg-white dark:bg-gray-800',
            'border border-gray-200 dark:border-gray-700',
            'shadow-lg',
            'py-1',
            'z-50'
          )}
          role="menu"
        >
          {/* User info */}
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
            <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
              {user?.name || 'User'}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400 truncate">
              {user?.email}
            </p>
          </div>

          {/* Menu items */}
          <div className="py-1">
            <button
              onClick={() => {
                setIsOpen(false);
                onShowVoiceGuide?.();
              }}
              className={cn(
                'w-full flex items-center gap-3 px-4 py-2 text-sm',
                'text-gray-700 dark:text-gray-200',
                'hover:bg-gray-100 dark:hover:bg-gray-700',
                'transition-colors duration-200'
              )}
              role="menuitem"
              data-voice-id="view-voice-guide"
            >
              <Mic className="h-4 w-4" />
              Voice Commands
            </button>

            <button
              onClick={() => {
                setIsOpen(false);
                onShowGuide?.();
              }}
              className={cn(
                'w-full flex items-center gap-3 px-4 py-2 text-sm',
                'text-gray-700 dark:text-gray-200',
                'hover:bg-gray-100 dark:hover:bg-gray-700',
                'transition-colors duration-200'
              )}
              role="menuitem"
              data-voice-id="forum-instructions"
            >
              <BookOpen className="h-4 w-4" />
              Platform Instructions
            </button>

            <button
              onClick={() => {
                setIsOpen(false);
                // TODO: Open profile modal or navigate to profile page
                alert('Profile page coming soon');
              }}
              className={cn(
                'w-full flex items-center gap-3 px-4 py-2 text-sm',
                'text-gray-700 dark:text-gray-200',
                'hover:bg-gray-100 dark:hover:bg-gray-700',
                'transition-colors duration-200'
              )}
              role="menuitem"
              data-voice-id="open-profile"
            >
              <Settings className="h-4 w-4" />
              Profile
            </button>

            <button
              onClick={() => {
                setIsOpen(false);
                signOut();
              }}
              className={cn(
                'w-full flex items-center gap-3 px-4 py-2 text-sm',
                'text-red-600 dark:text-red-400',
                'hover:bg-red-50 dark:hover:bg-red-900/20',
                'transition-colors duration-200'
              )}
              role="menuitem"
              data-voice-id="sign-out"
            >
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
