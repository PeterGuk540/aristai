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
  ChevronRight,
  HelpCircle,
} from 'lucide-react';
import { useAuth } from '@/lib/auth-context';
import { useUser } from '@/lib/context';
import { UserMenu } from './UserMenu';
import { Onboarding, useOnboarding } from './Onboarding';
import { ToastProvider } from './ui/Toast';
import { cn } from '@/lib/utils';

// Navigation items with optional instructor-only flag and enrollment requirement
const allNavigation = [
  { name: 'Introduction', href: '/introduction', icon: HelpCircle, instructorOnly: false, requiresEnrollment: false },
  { name: 'Courses', href: '/courses', icon: BookOpen, instructorOnly: false, requiresEnrollment: false },
  { name: 'Sessions', href: '/sessions', icon: Calendar, instructorOnly: false, requiresEnrollment: true },
  { name: 'Forum', href: '/forum', icon: MessageSquare, instructorOnly: false, requiresEnrollment: true },
  { name: 'Console', href: '/console', icon: Settings, instructorOnly: true, requiresEnrollment: false },
  { name: 'Reports', href: '/reports', icon: FileText, instructorOnly: false, requiresEnrollment: true },
];

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, isLoading } = useAuth();
  const { currentUser, isInstructor, isAdmin, hasEnrollments } = useUser();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(false);

  // Determine the effective role for onboarding
  const effectiveRole = isAdmin ? 'admin' : isInstructor ? 'instructor' : 'student';
  const { showOnboarding, completeOnboarding, showGuide, isReady } = useOnboarding(currentUser?.id, currentUser?.role);

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

  // Show loading state while checking auth or onboarding
  if (isLoading || !isReady) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-neutral-50 dark:bg-neutral-900">
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <div className="w-12 h-12 rounded-full border-4 border-primary-100 dark:border-primary-900"></div>
            <div className="absolute top-0 left-0 w-12 h-12 rounded-full border-4 border-primary-600 border-t-transparent animate-spin"></div>
          </div>
          <p className="text-sm text-neutral-500 dark:text-neutral-400">Loading...</p>
        </div>
      </div>
    );
  }

  // Don't render if not authenticated (will redirect)
  if (!isAuthenticated) {
    return null;
  }

  return (
    <ToastProvider>
    <div className="min-h-screen bg-neutral-50 dark:bg-neutral-900">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-neutral-900/60 backdrop-blur-sm z-40 lg:hidden transition-opacity"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-64 bg-white dark:bg-neutral-800',
          'border-r border-neutral-200 dark:border-neutral-700',
          'transform transition-transform duration-300 ease-out lg:translate-x-0',
          'shadow-xl lg:shadow-none',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Logo */}
        <div className="flex h-16 items-center justify-between px-6 border-b border-neutral-200 dark:border-neutral-700">
          <Link href="/dashboard" className="flex items-center gap-3 group">
            <div className="relative">
              <GraduationCap className="h-8 w-8 text-primary-700 dark:text-primary-400 transition-transform group-hover:scale-110" />
              <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-accent-400 rounded-full opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
            <span className="text-xl font-bold text-neutral-900 dark:text-white tracking-tight">
              Arist<span className="text-primary-700 dark:text-primary-400">AI</span>
            </span>
          </Link>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden p-2 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors"
          >
            <X className="h-5 w-5 text-neutral-500 dark:text-neutral-400" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 px-3 py-6">
          <p className="px-3 mb-3 text-xs font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider">
            Navigation
          </p>
          {navigation.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + '/');

            return (
              <Link
                key={item.name}
                href={item.href}
                onClick={() => setSidebarOpen(false)}
                className={cn(
                  'group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200',
                  isActive
                    ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 shadow-soft'
                    : 'text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-700/50 hover:text-neutral-900 dark:hover:text-white'
                )}
              >
                <div className={cn(
                  'p-1.5 rounded-lg transition-colors',
                  isActive
                    ? 'bg-primary-100 dark:bg-primary-800/50'
                    : 'bg-neutral-100 dark:bg-neutral-700/50 group-hover:bg-neutral-200 dark:group-hover:bg-neutral-600/50'
                )}>
                  <item.icon className="h-4 w-4" />
                </div>
                <span className="flex-1">{item.name}</span>
                {isActive && (
                  <ChevronRight className="h-4 w-4 text-primary-400 dark:text-primary-500" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Bottom section with role indicator */}
        <div className="p-4 border-t border-neutral-200 dark:border-neutral-700">
          <div className="flex items-center gap-3 px-2">
            <div className={cn(
              'w-2 h-2 rounded-full',
              isAdmin ? 'bg-accent-500' : isInstructor ? 'bg-primary-500' : 'bg-success-500'
            )} />
            <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400 capitalize">
              {effectiveRole} Mode
            </span>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Top navigation */}
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-4 border-b border-neutral-200 dark:border-neutral-700 bg-white/80 dark:bg-neutral-800/80 backdrop-blur-md px-4 sm:px-6">
          {/* Mobile menu button */}
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden p-2 rounded-xl hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors"
          >
            <Menu className="h-5 w-5 text-neutral-600 dark:text-neutral-400" />
          </button>

          {/* Page title placeholder / Breadcrumb area */}
          <div className="hidden lg:block" />

          {/* Right side actions */}
          <div className="flex items-center gap-3">
            {/* Dark mode toggle */}
            <button
              onClick={toggleDarkMode}
              className={cn(
                'p-2.5 rounded-xl transition-all duration-200',
                'bg-neutral-100 dark:bg-neutral-700',
                'text-neutral-600 dark:text-neutral-300',
                'hover:bg-neutral-200 dark:hover:bg-neutral-600',
                'hover:text-neutral-900 dark:hover:text-white',
                'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 dark:focus:ring-offset-neutral-800'
              )}
              aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
              data-voice-id="toggle-theme"
            >
              {darkMode ? (
                <Sun className="h-5 w-5" />
              ) : (
                <Moon className="h-5 w-5" />
              )}
            </button>

            {/* Divider */}
            <div className="h-8 w-px bg-neutral-200 dark:bg-neutral-700" />

            {/* User menu */}
            <UserMenu onShowGuide={showGuide} />
          </div>
        </header>

        {/* Page content */}
        <main className="p-4 sm:p-6 lg:p-8">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>

      {/* Onboarding overlay */}
      {showOnboarding && currentUser && (
        <Onboarding
          role={effectiveRole}
          userName={currentUser.name}
          onComplete={completeOnboarding}
        />
      )}
    </div>
    </ToastProvider>
  );
}
