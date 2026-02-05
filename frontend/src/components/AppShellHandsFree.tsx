'use client';

import { useEffect, useState, useMemo } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  GraduationCap,
  BookOpen,
  Calendar,
  MessageSquare,
  Settings,
  FileText,
  Menu,
  X,
  Sun,
  Moon,
} from 'lucide-react';
import { useAuth } from '@/lib/auth-context';
import { useUser } from '@/lib/context';
import { UserMenu } from './UserMenu';
import { VoiceOnboarding } from './voice/VoiceOnboarding';
import { ConversationalVoice } from './voice/ConversationalVoice';
import { VoiceUiActionBridge } from './voice/VoiceUiActionBridge';
import { UiActionHandler } from './voice/UiActionHandler';
import { VoiceUIController } from './voice/VoiceUIController';
import { ToastProvider } from './ui/Toast';
import { cn } from '@/lib/utils';

// Navigation items with optional instructor-only flag and enrollment requirement
const allNavigation = [
  { name: 'Courses', href: '/courses', icon: BookOpen, instructorOnly: false, requiresEnrollment: false },
  { name: 'Sessions', href: '/sessions', icon: Calendar, instructorOnly: false, requiresEnrollment: true },
  { name: 'Forum', href: '/forum', icon: MessageSquare, instructorOnly: false, requiresEnrollment: true },
  { name: 'Console', href: '/console', icon: Settings, instructorOnly: true, requiresEnrollment: false },
  { name: 'Reports', href: '/reports', icon: FileText, instructorOnly: false, requiresEnrollment: true },
];

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShellHandsFree({ children }: AppShellProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, isLoading } = useAuth();
  const { currentUser, isInstructor, isAdmin, hasEnrollments } = useUser();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  
  // Voice state
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [onboardingComplete, setOnboardingComplete] = useState(false);
  const [voiceActive, setVoiceActive] = useState(false);
  const [voiceConnected, setVoiceConnected] = useState(false);

  // Determine the effective role for onboarding
  const effectiveRole = isAdmin ? 'admin' : isInstructor ? 'instructor' : 'student';

  // Filter navigation based on user role and enrollment status
  const navigation = useMemo(() => {
    return allNavigation.filter(item => {
      // Hide instructor-only items for non-instructors
      if (item.instructorOnly && !isInstructor) return false;
      // Hide enrollment-required items for students without enrollments
      if (item.requiresEnrollment && !isInstructor && !hasEnrollments) return false;
      return true;
    });
  }, [isInstructor, hasEnrollments]);

  // Check authentication and redirect if not authenticated
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  // Check if onboarding should be shown (only for instructors/admins)
  useEffect(() => {
    if (currentUser && (isInstructor || isAdmin)) {
      const storageKey = `aristai_voice_onboarding_${currentUser.id}`;
      const hasSeenOnboarding = localStorage.getItem(storageKey);
      
      if (!hasSeenOnboarding) {
        setShowOnboarding(true);
      } else {
        setOnboardingComplete(true);
      }
    } else if (currentUser) {
      // Non-instructors don't need voice onboarding
      setOnboardingComplete(true);
    }
  }, [currentUser, isInstructor, isAdmin]);

  // Handle onboarding completion
  const handleOnboardingComplete = () => {
    if (currentUser) {
      const storageKey = `aristai_voice_onboarding_${currentUser.id}`;
      localStorage.setItem(storageKey, 'true');
    }
    setShowOnboarding(false);
    setOnboardingComplete(true);
  };

  // Initialize dark mode from system preference
  useEffect(() => {
    const isDark =
      localStorage.getItem('darkMode') === 'true' ||
      (!localStorage.getItem('darkMode') &&
        window.matchMedia('(prefers-color-scheme: dark)').matches);
    setDarkMode(isDark);
    if (isDark) {
      document.documentElement.classList.add('dark');
    }
  }, []);

  // Toggle dark mode
  const toggleDarkMode = () => {
    const newDarkMode = !darkMode;
    setDarkMode(newDarkMode);
    localStorage.setItem('darkMode', String(newDarkMode));
    if (newDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  };

  // Handle voice navigation
  const handleVoiceNavigate = (path: string) => {
    router.push(path);
  };

  // Show loading state while checking auth
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  // Don't render if not authenticated (will redirect)
  if (!isAuthenticated) {
    return null;
  }

  return (
    <ToastProvider>
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700',
          'transform transition-transform duration-300 ease-in-out lg:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Logo */}
        <div className="flex h-16 items-center justify-between px-6 border-b border-gray-200 dark:border-gray-700">
          <Link href="/courses" className="flex items-center gap-2">
            <GraduationCap className="h-8 w-8 text-primary-600 dark:text-primary-400" />
            <span className="text-xl font-bold text-gray-900 dark:text-white">AristAI</span>
          </Link>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <X className="h-5 w-5 text-gray-500 dark:text-gray-400" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 px-3 py-4">
          {navigation.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + '/');

            return (
              <Link
                key={item.name}
                href={item.href}
                onClick={() => setSidebarOpen(false)}
                className={cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/50 dark:text-primary-300'
                    : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-300 dark:hover:bg-gray-700 dark:hover:text-white'
                )}
              >
                <item.icon className="h-5 w-5" />
                {item.name}
              </Link>
            );
          })}
        </nav>

        {/* Voice status indicator in sidebar */}
        {(isInstructor || isAdmin) && onboardingComplete && (
          <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
              <div className={cn(
                'w-2 h-2 rounded-full',
                voiceConnected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'
              )} />
              <span>Voice {voiceConnected ? 'Connected' : 'Ready'}</span>
            </div>
          </div>
        )}
      </aside>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Top navigation */}
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 sm:px-6">
          {/* Mobile menu button */}
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <Menu className="h-5 w-5 text-gray-500 dark:text-gray-400" />
          </button>

          {/* Page title placeholder */}
          <div className="hidden lg:block" />

          {/* Right side actions */}
          <div className="flex items-center gap-2">
            {/* Dark mode toggle */}
            <button
              onClick={toggleDarkMode}
              className={cn(
                'p-2 rounded-lg',
                'text-gray-500 dark:text-gray-400',
                'hover:bg-gray-100 dark:hover:bg-gray-700',
                'focus:outline-none focus:ring-2 focus:ring-primary-500'
              )}
              aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {darkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </button>

            {/* User menu */}
            <UserMenu />
          </div>
        </header>

        {/* Page content */}
        <main className="p-4 sm:p-6 lg:p-8">{children}</main>
      </div>

      {/* Voice Onboarding - shows first time for instructors/admins */}
      {showOnboarding && currentUser && (
        <VoiceOnboarding
          role={effectiveRole}
          userName={currentUser.name}
          onComplete={handleOnboardingComplete}
        />
      )}

      {/* Conversational Voice Assistant - always on for instructors after onboarding */}
      {(isInstructor || isAdmin) && onboardingComplete && (
        <>
          <VoiceUiActionBridge userId={currentUser?.id} onStatusChange={setVoiceConnected} />
          <UiActionHandler />
          <VoiceUIController />
          <ConversationalVoice
            onNavigate={handleVoiceNavigate}
            onActiveChange={setVoiceActive}
            autoStart={true}
            greeting={`Welcome back, ${currentUser?.name.split(' ')[0]}! How can I help you today?`}
          />
        </>
      )}
    </div>
    </ToastProvider>
  );
}

export default AppShellHandsFree;
