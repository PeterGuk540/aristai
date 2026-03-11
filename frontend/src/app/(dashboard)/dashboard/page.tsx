'use client';

import { useAuth } from '@/lib/auth-context';
import { BookOpen, Calendar, MessageSquare, Users, Activity } from 'lucide-react';
import { useTranslations } from 'next-intl';
import Link from 'next/link';

export default function DashboardPage() {
  const { user } = useAuth();
  const t = useTranslations();

  const recentActivity = [
    { title: t('dashboard.activity.newDiscussion'), time: t('dashboard.activity.fiveMinutesAgo'), type: 'discussion' },
    { title: t('dashboard.activity.sessionCompleted'), time: t('dashboard.activity.oneHourAgo'), type: 'session' },
    { title: t('dashboard.activity.reportGenerated'), time: t('dashboard.activity.twoHoursAgo'), type: 'report' },
    { title: t('dashboard.activity.newEnrollment'), time: t('dashboard.activity.threeHoursAgo'), type: 'enrollment' },
  ];

  const quickActions = [
    { icon: BookOpen, label: t('dashboard.createCourse'), href: '/courses' },
    { icon: Calendar, label: t('dashboard.startSession'), href: '/sessions' },
    { icon: MessageSquare, label: t('dashboard.newDiscussion'), href: '/forum' },
    { icon: Users, label: t('dashboard.inviteStudents'), href: '/courses' },
  ];

  return (
    <div className="space-y-6">
      {/* Plain greeting with border-bottom */}
      <div className="pb-4 border-b border-neutral-200 dark:border-neutral-700">
        <h1 className="text-xl font-semibold text-neutral-900 dark:text-white">
          {t('dashboard.welcomeBack', { name: user?.name || user?.email?.split('@')[0] || 'User' })}
        </h1>
        <p className="text-neutral-600 dark:text-neutral-400 mt-1 text-sm">{t('dashboard.subtitle')}</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { value: '4', label: t('dashboard.activeCourses') },
          { value: '12', label: t('dashboard.upcomingSessions') },
          { value: '89', label: t('dashboard.forumPosts') },
          { value: '156', label: t('dashboard.studentsEngaged') },
        ].map((stat, idx) => (
          <div key={idx} className="rounded-[14px] border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 py-7 px-5 text-center">
            <p className="text-2xl font-bold text-neutral-900 dark:text-white">{stat.value}</p>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Asymmetric layout */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
        {/* Recent Activity - contained card with colored dots */}
        <div className="rounded-[14px] border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-5">
          <h2 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-3">
            {t('dashboard.recentActivity')}
          </h2>
          <div className="divide-y divide-neutral-100 dark:divide-neutral-700">
            {recentActivity.map((activity, index) => (
              <div
                key={index}
                className="flex items-center justify-between py-3"
              >
                <span className="flex items-center gap-2.5 text-sm text-neutral-900 dark:text-white">
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    activity.type === 'discussion' ? 'bg-blue-500' :
                    activity.type === 'session' ? 'bg-green-500' :
                    activity.type === 'report' ? 'bg-amber-500' :
                    'bg-purple-500'
                  }`} />
                  {activity.title}
                </span>
                <span className="text-xs text-neutral-500 dark:text-neutral-400 ml-4 flex-shrink-0">
                  {activity.time}
                </span>
              </div>
            ))}
          </div>
          <button className="text-sm text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 font-medium mt-3">
            {t('dashboard.viewAllActivity')}
          </button>
        </div>

        {/* Quick Actions - contained card, first action dark */}
        <div className="rounded-[14px] border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-5">
          <h2 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-3">
            {t('dashboard.quickActions')}
          </h2>
          <div className="flex flex-wrap gap-2">
            {quickActions.map((action, index) => (
              <Link
                key={index}
                href={action.href}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm transition-colors ${
                  index === 0
                    ? 'bg-neutral-900 text-white hover:bg-neutral-800 dark:bg-neutral-100 dark:text-neutral-900 dark:hover:bg-neutral-200'
                    : 'border border-neutral-200 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-700'
                }`}
              >
                <action.icon className="h-3.5 w-3.5" />
                {action.label}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
