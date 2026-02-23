'use client';

import { useEffect, useState, useMemo, useRef, useCallback } from 'react';
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
  ChevronRight,
  Plug,
} from 'lucide-react';
import { useAuth } from '@/lib/auth-context';
import { useUser } from '@/lib/context';
import { api } from '@/lib/api';
import { User } from '@/types';
import { UserMenu } from './UserMenu';
import { Onboarding, useOnboarding } from './Onboarding';
import { VoiceOnboarding } from './voice/VoiceOnboarding';
import { ConversationalVoice, ConversationalVoiceV2, USE_VOICE_V2 } from './voice';
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
  { key: 'integrations', href: '/integrations', icon: Plug, instructorOnly: true, requiresEnrollment: false },
  { key: 'reports', href: '/reports', icon: FileText, instructorOnly: false, requiresEnrollment: true },
];

const learningOpsKeys = new Set(['courses', 'sessions', 'forum']);
const managementKeys = new Set(['reports', 'console', 'integrations']);

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShellHandsFree({ children }: AppShellProps) {
  const router = useRouter();
  const pathname = usePathname();
  const t = useTranslations('nav');
  const { isAuthenticated, isLoading, user } = useAuth();
  const { currentUser, isInstructor, isAdmin, hasEnrollments } = useUser();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);
  const [adminPendingRequests, setAdminPendingRequests] = useState<User[]>([]);
  const [loadingAdminRequests, setLoadingAdminRequests] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const notificationsRef = useRef<HTMLDivElement>(null);
  
  // Voice state
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [onboardingComplete, setOnboardingComplete] = useState(false);
  const [voiceActive, setVoiceActive] = useState(false);
  const [voiceConnected, setVoiceConnected] = useState(false);

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

  const introNav = useMemo(() => navigation.filter((item) => item.key === 'introduction'), [navigation]);
  const learningNav = useMemo(() => navigation.filter((item) => learningOpsKeys.has(item.key)), [navigation]);
  const managementNav = useMemo(() => navigation.filter((item) => managementKeys.has(item.key)), [navigation]);

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

  const filteredNavigation = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return navigation;
    return navigation.filter((item) => t(item.key).toLowerCase().includes(q));
  }, [navigation, searchQuery, t]);

  const shellNotifications = useMemo(() => {
    const items: Array<{
      id: string;
      title: string;
      detail: string;
      tone: 'default' | 'warning';
      action?: () => void;
      actionVoiceId?: string;
    }> = [];

    // System status
    if (isInstructor || isAdmin) {
      items.push({
        id: 'voice-status',
        title: voiceConnected ? 'Voice controller connected' : 'Voice controller disconnected',
        detail: voiceConnected
          ? 'Natural-language commands are available.'
          : 'Reconnect voice services to restore command execution.',
        tone: voiceConnected ? 'default' : 'warning',
      });
    }

    // Admin requests workflow
    if (isAdmin) {
      if (adminPendingRequests.length > 0 || loadingAdminRequests) {
        items.push({
          id: 'admin-requests',
          title: `Pending instructor requests: ${loadingAdminRequests ? '...' : adminPendingRequests.length}`,
          detail: 'Open Console Requests to approve or reject.',
          tone: adminPendingRequests.length > 0 ? 'warning' : 'default',
          action: () => {
            setNotificationsOpen(false);
            router.push('/console');
            window.dispatchEvent(new CustomEvent('ui.switchTab', { detail: { tabName: 'requests' } }));
          },
          actionVoiceId: 'open-instructor-requests',
        });
      }
    }

    // Student account/request status
    if (!isAdmin && !isInstructor && currentUser?.instructor_request_status === 'pending') {
      items.push({
        id: 'instructor-request-pending',
        title: 'Instructor request pending',
        detail: 'Your request is awaiting administrator approval.',
        tone: 'default',
      });
    }
    if (!isAdmin && !isInstructor && currentUser?.instructor_request_status === 'rejected') {
      items.push({
        id: 'instructor-request-rejected',
        title: 'Instructor request rejected',
        detail: 'Your request was rejected. You can submit a new one later.',
        tone: 'warning',
      });
    }

    // Enrollment guidance
    if (!isAdmin && !isInstructor && !hasEnrollments) {
      items.push({
        id: 'no-enrollments',
        title: 'No enrolled courses',
        detail: 'Join a course to unlock sessions, forum, and reports.',
        tone: 'warning',
        action: () => {
          setNotificationsOpen(false);
          router.push('/courses');
        },
        actionVoiceId: 'open-courses-from-notifications',
      });
    }

    return items;
  }, [
    isInstructor,
    isAdmin,
    voiceConnected,
    adminPendingRequests.length,
    loadingAdminRequests,
    currentUser?.instructor_request_status,
    hasEnrollments,
    router,
  ]);

  const currentNavLabel = useMemo(() => {
    const matched = navigation.find((item) => pathname === item.href || pathname.startsWith(item.href + '/'));
    return matched ? t(matched.key) : 'Dashboard';
  }, [navigation, pathname, t]);

  const fetchAdminRequests = useCallback(async () => {
    if (!isAdmin || !currentUser?.id) {
      setAdminPendingRequests([]);
      return;
    }
    setLoadingAdminRequests(true);
    try {
      const requests = await api.getInstructorRequests(currentUser.id);
      setAdminPendingRequests(requests);
    } catch (error) {
      console.error('Failed to fetch admin notifications:', error);
    } finally {
      setLoadingAdminRequests(false);
    }
  }, [currentUser?.id, isAdmin]);

  useEffect(() => {
    const handleOutsideClick = (event: MouseEvent) => {
      const target = event.target as Node;
      if (searchRef.current && !searchRef.current.contains(target)) {
        setSearchFocused(false);
      }
      if (notificationsRef.current && !notificationsRef.current.contains(target)) {
        setNotificationsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  useEffect(() => {
    fetchAdminRequests();
  }, [fetchAdminRequests]);

  useEffect(() => {
    if (!isAdmin || !currentUser?.id) return;
    const interval = window.setInterval(fetchAdminRequests, 30000);
    return () => window.clearInterval(interval);
  }, [fetchAdminRequests, currentUser?.id, isAdmin]);

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
        <nav className="flex-1 space-y-4 px-3 py-4">
          {introNav.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
            const voiceId = `tab-${item.key}`;

            return (
              <Link
                key={item.key}
                href={item.href}
                data-voice-id={voiceId}
                onClick={() => setSidebarOpen(false)}
                className={cn(
                  'group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary-50 text-primary-800 dark:bg-primary-950/40 dark:text-primary-300'
                    : 'text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-[#231d12] dark:hover:text-neutral-100'
                )}
              >
                {isActive && <span className="absolute left-0 h-6 w-[3px] rounded-r bg-primary-500" />}
                <item.icon className="h-5 w-5" />
                {t(item.key)}
              </Link>
            );
          })}

          {learningNav.length > 0 && (
            <div className="pt-2">
              <p className="mb-1 px-3 text-[11px] font-bold uppercase tracking-wider text-neutral-400 dark:text-neutral-500">
                Learning Ops
              </p>
              <div className="space-y-1">
                {learningNav.map((item) => {
                  const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
                  const voiceId = `tab-${item.key}`;

                  return (
                    <Link
                      key={item.key}
                      href={item.href}
                      data-voice-id={voiceId}
                      onClick={() => setSidebarOpen(false)}
                      className={cn(
                        'group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                        isActive
                          ? 'bg-primary-50 text-primary-800 dark:bg-primary-950/40 dark:text-primary-300'
                          : 'text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-[#231d12] dark:hover:text-neutral-100'
                      )}
                    >
                      {isActive && <span className="absolute left-0 h-6 w-[3px] rounded-r bg-primary-500" />}
                      <item.icon className="h-5 w-5" />
                      {t(item.key)}
                    </Link>
                  );
                })}
              </div>
            </div>
          )}

          {managementNav.length > 0 && (
            <div className="border-t border-stone-200 pt-3 dark:border-primary-900/20">
              <p className="mb-1 px-3 text-[11px] font-bold uppercase tracking-wider text-neutral-400 dark:text-neutral-500">
                Management
              </p>
              <div className="space-y-1">
                {managementNav.map((item) => {
                  const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
                  const voiceId = `tab-${item.key}`;

                  return (
                    <Link
                      key={item.key}
                      href={item.href}
                      data-voice-id={voiceId}
                      onClick={() => setSidebarOpen(false)}
                      className={cn(
                        'group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                        isActive
                          ? 'bg-primary-50 text-primary-800 dark:bg-primary-950/40 dark:text-primary-300'
                          : 'text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-[#231d12] dark:hover:text-neutral-100'
                      )}
                    >
                      {isActive && <span className="absolute left-0 h-6 w-[3px] rounded-r bg-primary-500" />}
                      <item.icon className="h-5 w-5" />
                      {t(item.key)}
                    </Link>
                  );
                })}
              </div>
            </div>
          )}
        </nav>

        {/* Sidebar identity block */}
        <div className="px-4 pb-3">
          <div className="flex items-center gap-3 rounded-xl border border-stone-200 bg-stone-50 p-3 dark:border-primary-900/20 dark:bg-stone-900/25">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white dark:bg-white dark:text-slate-900">
              {currentUser?.name?.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase() || 'U'}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-semibold text-neutral-900 dark:text-white">
                {currentUser?.name || user?.name || 'User'}
              </p>
              <p className="truncate text-[11px] text-neutral-500 dark:text-neutral-400">
                {currentUser?.role || 'member'}
              </p>
            </div>
          </div>
        </div>

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
        <header className="relative sticky top-0 z-30 flex h-[72px] items-center border-b border-stone-200/80 bg-white/80 px-4 backdrop-blur-md dark:border-primary-900/20 dark:bg-[#221c10]/80 sm:px-6">
          <div className="flex flex-1 items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="rounded-lg p-2 text-neutral-500 hover:bg-stone-100 dark:text-neutral-400 dark:hover:bg-[#2a2215] lg:hidden"
              aria-label="Open navigation"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="hidden items-center gap-2 text-sm lg:flex">
              <span className="font-medium text-neutral-400 dark:text-neutral-500">Workspace</span>
              <ChevronRight className="h-4 w-4 text-neutral-300 dark:text-neutral-600" />
              <span className="font-semibold text-neutral-900 dark:text-white">{currentNavLabel}</span>
            </div>
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
            <div className="relative hidden lg:block" ref={searchRef}>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-400" />
                <input
                  value={searchQuery}
                  onFocus={() => setSearchFocused(true)}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && filteredNavigation.length > 0) {
                      router.push(filteredNavigation[0].href);
                      setSearchFocused(false);
                      setSearchQuery('');
                    }
                  }}
                  placeholder="Search pages..."
                  data-voice-id="workspace-search"
                  className="w-64 rounded-lg border border-stone-200 bg-stone-50 py-2 pl-9 pr-3 text-sm text-neutral-700 outline-none transition-all focus:border-primary-400 focus:bg-white dark:border-primary-900/20 dark:bg-[#221c10] dark:text-neutral-300"
                />
              </div>
              {searchFocused && searchQuery.trim() && (
                <div className="absolute right-0 top-12 z-50 w-72 rounded-xl border border-stone-200 bg-white p-2 shadow-md dark:border-primary-900/20 dark:bg-[#1a150c]">
                  <div className="max-h-56 overflow-auto">
                    {filteredNavigation.map((item) => (
                      <Link
                        key={item.key}
                        href={item.href}
                        onClick={() => {
                          setSearchFocused(false);
                          setSearchQuery('');
                        }}
                        className="block rounded-lg px-3 py-2 text-sm text-neutral-700 hover:bg-stone-100 dark:text-neutral-300 dark:hover:bg-stone-900/40"
                      >
                        {t(item.key)}
                      </Link>
                    ))}
                    {filteredNavigation.length === 0 && (
                      <p className="px-3 py-2 text-sm text-neutral-500 dark:text-neutral-400">No matches</p>
                    )}
                  </div>
                </div>
              )}
            </div>
            <button
              onClick={showGuide}
              className="hidden rounded-lg p-2.5 text-neutral-500 transition-all hover:bg-stone-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-[#2a2215] dark:hover:text-white lg:inline-flex"
              aria-label="Help and documentation"
              data-voice-id="open-help"
            >
              <HelpCircle className="h-5 w-5" />
            </button>
            <div className="relative hidden lg:block" ref={notificationsRef}>
              <button
                onClick={() => {
                  setNotificationsOpen((prev) => !prev);
                  setSearchFocused(false);
                  if (!notificationsOpen) {
                    fetchAdminRequests();
                  }
                }}
                className="relative rounded-lg p-2.5 text-neutral-500 transition-all hover:bg-stone-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-[#2a2215] dark:hover:text-white"
                aria-label="Notifications"
                data-voice-id="notifications-button"
              >
                <Bell className="h-5 w-5" />
                {isAdmin && adminPendingRequests.length > 0 && (
                  <span className="absolute right-1 top-1 h-2.5 w-2.5 rounded-full bg-primary-500" />
                )}
              </button>
              {notificationsOpen && (
                <div className="absolute right-0 top-12 z-50 w-80 rounded-xl border border-stone-200 bg-white p-3 shadow-md dark:border-primary-900/20 dark:bg-[#1a150c]">
                  <p className="px-2 pb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
                    Notifications
                  </p>
                  <div className="space-y-1">
                    {shellNotifications.map((item) => {
                      const body = (
                        <>
                          <p className="text-sm font-medium text-neutral-800 dark:text-neutral-200">{item.title}</p>
                          <p className="text-xs text-neutral-500 dark:text-neutral-400">{item.detail}</p>
                        </>
                      );

                      if (item.action) {
                        return (
                          <button
                            key={item.id}
                            onClick={item.action}
                            data-voice-id={item.actionVoiceId}
                            className={cn(
                              'w-full rounded-lg px-3 py-2 text-left transition-colors hover:bg-stone-50 dark:hover:bg-stone-900/25',
                              item.tone === 'warning' && 'bg-warning-50/60 dark:bg-warning-900/20'
                            )}
                          >
                            {body}
                          </button>
                        );
                      }

                      return (
                        <div
                          key={item.id}
                          className={cn(
                            'rounded-lg px-3 py-2',
                            item.tone === 'warning' && 'bg-warning-50/60 dark:bg-warning-900/20'
                          )}
                        >
                          {body}
                        </div>
                      );
                    })}
                    {shellNotifications.length === 0 && (
                      <div className="rounded-lg px-3 py-2">
                        <p className="text-sm font-medium text-neutral-800 dark:text-neutral-200">No unread alerts</p>
                        <p className="text-xs text-neutral-500 dark:text-neutral-400">You are all caught up.</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

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
            <UserMenu />
          </div>
          <div className="pointer-events-none absolute bottom-0 left-0 h-px w-full bg-gradient-to-r from-transparent via-primary-400/40 to-transparent" />
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

      {/* Conversational Voice Assistant - always on for instructors after onboarding */}
      {(isInstructor || isAdmin) && onboardingComplete && (
        <>
          {/* V1 uses VoiceUiActionBridge, V2 uses Client Tools directly */}
          {!USE_VOICE_V2 && (
            <>
              <VoiceUiActionBridge userId={currentUser?.id} onStatusChange={setVoiceConnected} />
              <UiActionHandler />
              <VoiceUIController />
            </>
          )}
          {USE_VOICE_V2 ? (
            <ConversationalVoiceV2
              onNavigate={handleVoiceNavigate}
              onActiveChange={setVoiceActive}
              autoStart={false}
              greeting={`Welcome back, ${currentUser?.name.split(' ')[0]}! How can I help you today?`}
            />
          ) : (
            <ConversationalVoice
              onNavigate={handleVoiceNavigate}
              onActiveChange={setVoiceActive}
              autoStart={false}
              greeting={`Welcome back, ${currentUser?.name.split(' ')[0]}! How can I help you today?`}
            />
          )}
        </>
      )}
    </div>
    </ToastProvider>
  );
}

export default AppShellHandsFree;
