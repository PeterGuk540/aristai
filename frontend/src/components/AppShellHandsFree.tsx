'use client';

import { useEffect, useState, useMemo } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import { useTranslations } from 'next-intl';
import {
  HelpCircle,
  BookOpen,
  Calendar,
  MessageSquare,
  Settings,
  FileText,
  Menu,
  X,
  Sun,
  Moon,
  Search,
  Bell,
  LayoutGrid,
} from 'lucide-react';
import { useAuth } from '@/lib/auth-context';
import { useUser } from '@/lib/context';
import { UserMenu } from './UserMenu';
import { Onboarding, useOnboarding } from './Onboarding';
import { VoiceOnboarding } from './voice/VoiceOnboarding';
import { VoiceCommandGuide } from './voice/VoiceCommandGuide';
import { ConversationalVoice } from './voice/ConversationalVoice';
import { VoiceUiActionBridge } from './voice/VoiceUiActionBridge';
import { UiActionHandler } from './voice/UiActionHandler';
import { VoiceUIController } from './voice/VoiceUIController';
import { ToastProvider } from './ui/Toast';
import { LanguageToggleCompact } from './LanguageToggle';
import { cn } from '@/lib/utils';

// Navigation items with optional instructor-only flag and enrollment requirement
// Using translation keys instead of hardcoded names
const allNavigation = [
  { key: 'introduction', href: '/platform-guide', icon: HelpCircle, instructorOnly: false, requiresEnrollment: false },
  { key: 'courses', href: '/courses', icon: BookOpen, instructorOnly: false, requiresEnrollment: false },
  { key: 'sessions', href: '/sessions', icon: Calendar, instructorOnly: false, requiresEnrollment: true },
  { key: 'forum', href: '/forum', icon: MessageSquare, instructorOnly: false, requiresEnrollment: true },
  { key: 'console', href: '/console', icon: Settings, instructorOnly: true, requiresEnrollment: false },
  { key: 'reports', href: '/reports', icon: FileText, instructorOnly: false, requiresEnrollment: true },
];

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShellHandsFree({ children }: AppShellProps) {
  const router = useRouter();
  const pathname = usePathname();
  const t = useTranslations('nav');
  const { isAuthenticated, isLoading } = useAuth();
  const { currentUser, isInstructor, isAdmin, hasEnrollments } = useUser();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  
  // Voice state
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [onboardingComplete, setOnboardingComplete] = useState(false);
  const [voiceActive, setVoiceActive] = useState(false);
  const [voiceConnected, setVoiceConnected] = useState(false);
  const [showVoiceCommandGuide, setShowVoiceCommandGuide] = useState(false);

  // Determine the effective role for onboarding
  const effectiveRole = isAdmin ? 'admin' : isInstructor ? 'instructor' : 'student';

  // Regular onboarding (welcome guide)
  const { showOnboarding: showWelcomeGuide, completeOnboarding: completeWelcomeGuide, showGuide, isReady } = useOnboarding(currentUser?.id, currentUser?.role);

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

  // Show loading state while checking auth or onboarding
  if (isLoading || !isReady) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-neutral-100 dark:bg-neutral-950">
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
    <div className="min-h-screen bg-stone-50 dark:bg-[#221c10]">
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
          'fixed inset-y-0 left-0 z-50 w-72 bg-white dark:bg-[#1a150c] border-r border-primary-200/40 dark:border-primary-900/20',
          'transform transition-transform duration-300 ease-in-out lg:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Logo */}
        <div className="flex h-16 items-center justify-between px-6 border-b border-primary-200/40 dark:border-primary-900/20">
          <Link href="/courses" className="flex items-center gap-2">
            <img
              src="/AristAI_logo.png"
              alt="AristAI"
              className="h-8 w-8 object-contain"
            />
            <div>
              <span className="block text-lg font-semibold text-neutral-900 dark:text-white tracking-tight">AristAI</span>
              <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-primary-600 dark:text-primary-400">Internal Console</span>
            </div>
          </Link>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden p-1 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-700"
          >
            <X className="h-5 w-5 text-neutral-500 dark:text-neutral-400" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 px-3 py-4">
          {navigation.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
            const voiceId = item.key === 'introduction' ? undefined : `tab-${item.key}`;

            return (
              <Link
                key={item.key}
                href={item.href}
                data-voice-id={voiceId}
                onClick={() => setSidebarOpen(false)}
                className={cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary-50 text-primary-800 dark:bg-primary-950/40 dark:text-primary-300 border border-primary-200/80 dark:border-primary-900/30'
                    : 'text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-[#231d12] dark:hover:text-neutral-100'
                )}
              >
                <item.icon className="h-5 w-5" />
                {t(item.key)}
              </Link>
            );
          })}
        </nav>

        {/* Voice status indicator in sidebar */}
        {(isInstructor || isAdmin) && onboardingComplete && voiceConnected && (
          <div className="px-4 py-3 border-t border-primary-200/40 dark:border-primary-900/20">
            <div className="flex items-center gap-2 text-sm text-neutral-600 dark:text-neutral-400">
              <div className={cn(
                'w-2 h-2 rounded-full',
                'bg-green-500'
              )} />
              <span>Voice Connected</span>
            </div>
          </div>
        )}
      </aside>

      {/* Main content */}
      <div className="lg:pl-72">
        {/* Top navigation */}
        <header className="sticky top-0 z-30 flex h-[72px] items-center border-b border-stone-200/80 bg-white/80 px-4 backdrop-blur-md dark:border-primary-900/20 dark:bg-[#221c10]/80 sm:px-6">
          <div className="flex flex-1 items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="rounded-lg p-2 text-neutral-500 hover:bg-stone-100 dark:text-neutral-400 dark:hover:bg-[#2a2215] lg:hidden"
              aria-label="Open navigation"
            >
              <Menu className="h-5 w-5" />
            </button>
            <button
              className="hidden items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-bold uppercase tracking-wide text-neutral-500 transition-colors hover:bg-stone-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-[#2a2215] dark:hover:text-white lg:flex"
              aria-label="Workspace"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300">
                <LayoutGrid className="h-4 w-4" />
              </span>
              Workspace
            </button>
          </div>

          <div className="flex flex-1 items-center justify-center py-1">
            {/* Light mode logo (black on white) */}
            <img
              src="/EPGUPP_logo_light.png"
              alt="Postgrado Universidad Politécnica"
              className="h-10 object-contain dark:hidden"
            />
            {/* Dark mode logo (white on dark) */}
            <img
              src="/EPGUPP_logo_white.png"
              alt="Postgrado Universidad Politécnica"
              className="h-10 object-contain hidden dark:block"
            />
          </div>

          <div className="flex flex-1 items-center justify-end gap-2">
            <button
              className="hidden rounded-lg p-2.5 text-neutral-500 transition-all hover:bg-stone-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-[#2a2215] dark:hover:text-white lg:inline-flex"
              aria-label="Search workspace"
            >
              <Search className="h-5 w-5" />
            </button>
            <button
              onClick={showGuide}
              className="hidden rounded-lg p-2.5 text-neutral-500 transition-all hover:bg-stone-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-[#2a2215] dark:hover:text-white lg:inline-flex"
              aria-label="Help and documentation"
            >
              <HelpCircle className="h-5 w-5" />
            </button>
            <button
              className="hidden rounded-lg p-2.5 text-neutral-500 transition-all hover:bg-stone-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-[#2a2215] dark:hover:text-white lg:inline-flex"
              aria-label="Notifications"
            >
              <Bell className="h-5 w-5" />
            </button>

            {/* Language toggle */}
            <LanguageToggleCompact />

            {/* Dark mode toggle */}
            <button
              onClick={toggleDarkMode}
              className={cn(
                'p-2.5 rounded-lg',
                'text-neutral-500 dark:text-neutral-400',
                'hover:bg-neutral-100 dark:hover:bg-[#2a2215] hover:text-primary-600 dark:hover:text-primary-400',
                'focus:outline-none focus:ring-2 focus:ring-primary-500'
              )}
              aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
              data-voice-id="toggle-theme"
            >
              {darkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </button>

            <div className="mx-1 hidden h-6 w-px bg-stone-200 dark:bg-primary-900/20 sm:block" />

            {/* User menu */}
            <UserMenu onShowGuide={showGuide} onShowVoiceGuide={() => setShowVoiceCommandGuide(true)} />
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

      {/* Welcome Guide - shows on first login or when "View Guide" is clicked */}
      {showWelcomeGuide && currentUser && (
        <Onboarding
          role={effectiveRole}
          userName={currentUser.name}
          onComplete={completeWelcomeGuide}
        />
      )}

      {/* Voice Command Guide - shows when "Voice Commands" is clicked */}
      {showVoiceCommandGuide && (
        <VoiceCommandGuide onClose={() => setShowVoiceCommandGuide(false)} />
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
            autoStart={false}
            greeting={`Welcome back, ${currentUser?.name.split(' ')[0]}! How can I help you today?`}
          />
        </>
      )}
    </div>
    </ToastProvider>
  );
}

export default AppShellHandsFree;
