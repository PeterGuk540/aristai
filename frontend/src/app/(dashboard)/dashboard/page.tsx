'use client';

import { useAuth } from '@/lib/auth-context';
import { BookOpen, Calendar, MessageSquare, TrendingUp, Users, Activity } from 'lucide-react';

export default function DashboardPage() {
  const { user } = useAuth();

  const stats = [
    { name: 'Active Courses', value: '4', icon: BookOpen, color: 'bg-blue-500' },
    { name: 'Upcoming Sessions', value: '12', icon: Calendar, color: 'bg-green-500' },
    { name: 'Forum Posts', value: '89', icon: MessageSquare, color: 'bg-purple-500' },
    { name: 'Students Engaged', value: '156', icon: Users, color: 'bg-orange-500' },
  ];

  const recentActivity = [
    { title: 'New discussion started in CS101', time: '5 minutes ago', type: 'discussion' },
    { title: 'Session "Intro to AI" completed', time: '1 hour ago', type: 'session' },
    { title: 'Report generated for Week 3', time: '2 hours ago', type: 'report' },
    { title: 'New student enrolled in Data Science', time: '3 hours ago', type: 'enrollment' },
  ];

  return (
    <div className="space-y-8">
      {/* Welcome section */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Welcome back, {user?.name || user?.email?.split('@')[0] || 'User'}!
        </h1>
        <p className="mt-1 text-gray-600 dark:text-gray-400">
          Here&apos;s what&apos;s happening with your courses today.
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.name}
            className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700"
          >
            <div className="flex items-center gap-4">
              <div className={`${stat.color} p-3 rounded-lg`}>
                <stat.icon className="h-6 w-6 text-white" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">{stat.value}</p>
                <p className="text-sm text-gray-600 dark:text-gray-400">{stat.name}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Content grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Recent Activity */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
          <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              <Activity className="h-5 w-5 text-primary-600 dark:text-primary-400" />
              Recent Activity
            </h2>
          </div>
          <div className="divide-y divide-gray-200 dark:divide-gray-700">
            {recentActivity.map((activity, index) => (
              <div key={index} className="px-6 py-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                <p className="text-sm font-medium text-gray-900 dark:text-white">{activity.title}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{activity.time}</p>
              </div>
            ))}
          </div>
          <div className="px-6 py-3 border-t border-gray-200 dark:border-gray-700">
            <button className="text-sm text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 font-medium">
              View all activity
            </button>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
          <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-primary-600 dark:text-primary-400" />
              Quick Actions
            </h2>
          </div>
          <div className="p-6 grid grid-cols-2 gap-4">
            <button className="flex flex-col items-center justify-center p-4 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 hover:border-primary-500 dark:hover:border-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/20 transition-colors">
              <BookOpen className="h-8 w-8 text-gray-400 dark:text-gray-500 mb-2" />
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Create Course</span>
            </button>
            <button className="flex flex-col items-center justify-center p-4 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 hover:border-primary-500 dark:hover:border-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/20 transition-colors">
              <Calendar className="h-8 w-8 text-gray-400 dark:text-gray-500 mb-2" />
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Start Session</span>
            </button>
            <button className="flex flex-col items-center justify-center p-4 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 hover:border-primary-500 dark:hover:border-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/20 transition-colors">
              <MessageSquare className="h-8 w-8 text-gray-400 dark:text-gray-500 mb-2" />
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">New Discussion</span>
            </button>
            <button className="flex flex-col items-center justify-center p-4 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 hover:border-primary-500 dark:hover:border-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/20 transition-colors">
              <Users className="h-8 w-8 text-gray-400 dark:text-gray-500 mb-2" />
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Invite Students</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
