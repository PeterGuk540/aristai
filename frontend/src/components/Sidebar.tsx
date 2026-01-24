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
          <button
            onClick={login}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors"
          >
            <LogIn className="h-4 w-4" />
            Sign In with Cognito
          </button>
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
