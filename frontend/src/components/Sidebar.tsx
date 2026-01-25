'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  BookOpen,
  Calendar,
  MessageSquare,
  Settings,
  FileText,
  GraduationCap,
  User,
  ChevronDown,
  LogIn,
  LogOut,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useUser } from '@/lib/context';
import { useAuth } from '@/lib/auth';

const navigation = [
  { name: 'Courses', href: '/courses', icon: BookOpen },
  { name: 'Sessions', href: '/sessions', icon: Calendar },
  { name: 'Forum', href: '/forum', icon: MessageSquare },
  { name: 'Instructor Console', href: '/console', icon: Settings, instructorOnly: true },
  { name: 'Reports', href: '/reports', icon: FileText },
];

export function Sidebar() {
  const pathname = usePathname();
  const { currentUser, setCurrentUser, users, isInstructor, loading } = useUser();
  const { isAuthenticated, isLoading: authLoading, user: authUser, login, logout } = useAuth();

  return (
    <div className="flex h-full w-64 flex-col bg-white border-r border-gray-200">
      {/* Logo */}
      <div className="flex h-16 items-center gap-2 px-6 border-b border-gray-200">
        <GraduationCap className="h-8 w-8 text-primary-600" />
        <span className="text-xl font-bold text-gray-900">AristAI</span>
      </div>

      {/* Auth Status */}
      <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
        {authLoading ? (
          <div className="text-sm text-gray-400">Loading...</div>
        ) : isAuthenticated ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-full bg-primary-100 flex items-center justify-center">
                <User className="h-4 w-4 text-primary-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {authUser?.name || authUser?.email}
                </p>
                <p className="text-xs text-gray-500 truncate">{authUser?.email}</p>
              </div>
            </div>
            <button
              onClick={logout}
              className="w-full flex items-center justify-center gap-2 px-3 py-1.5 text-sm text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <LogOut className="h-4 w-4" />
              Sign Out
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <button
              onClick={() => login('cognito')}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors"
            >
              <LogIn className="h-4 w-4" />
              Sign In
            </button>
            <button
              onClick={() => login('google')}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              Sign In with Google
            </button>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navigation.map((item) => {
          // Hide instructor-only items from students
          if (item.instructorOnly && !isInstructor) {
            return null;
          }

          const isActive = pathname === item.href || pathname.startsWith(item.href + '/');

          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.name}
            </Link>
          );
        })}
      </nav>

      {/* User Selector */}
      <div className="border-t border-gray-200 p-4">
        <label className="block text-xs font-medium text-gray-500 mb-2">
          Acting as:
        </label>
        {loading ? (
          <div className="text-sm text-gray-400">Loading...</div>
        ) : users.length > 0 ? (
          <div className="relative">
            <select
              value={currentUser?.id || ''}
              onChange={(e) => {
                const user = users.find((u) => u.id === Number(e.target.value));
                setCurrentUser(user || null);
              }}
              className="w-full appearance-none rounded-lg border border-gray-300 bg-white px-3 py-2 pr-8 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            >
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.name} ({user.role})
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400 pointer-events-none" />
          </div>
        ) : (
          <div className="text-sm text-gray-400">No users found</div>
        )}

        {currentUser && (
          <div className="mt-2 flex items-center gap-2 text-xs text-gray-500">
            <User className="h-3 w-3" />
            <span className={cn(
              'px-1.5 py-0.5 rounded',
              isInstructor ? 'bg-purple-100 text-purple-700' : 'bg-green-100 text-green-700'
            )}>
              {currentUser.role}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
