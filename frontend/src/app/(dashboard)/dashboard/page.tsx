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

      {/* Stats grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { value: '4', label: t('dashboard.activeCourses'), bg: 'var(--ink-light)' },
          { value: '12', label: t('dashboard.upcomingSessions'), bg: 'var(--yellow-light)' },
          { value: '89', label: t('dashboard.forumPosts'), bg: 'var(--warm-100)' },
          { value: '156', label: t('dashboard.studentsEngaged'), bg: 'var(--ink-light)' },
        ].map((stat, i) => (
          <div key={i} className="rounded-[10px] p-4 border border-neutral-200 dark:border-neutral-700" style={{ backgroundColor: stat.bg }}>
            <p className="text-2xl font-semibold text-neutral-900 dark:text-white">{stat.value}</p>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Asymmetric layout */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
        {/* Recent Activity - simple text list */}
        <div>
          <h2 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-3">
            {t('dashboard.recentActivity')}
          </h2>
          <div className="divide-y divide-neutral-100 dark:divide-neutral-800">
            {recentActivity.map((activity, index) => {
              const dotColors: Record<string, string> = {
                discussion: 'bg-blue-500',
                session: 'bg-emerald-500',
                report: 'bg-amber-500',
                enrollment: 'bg-violet-500',
              };
              return (
                <div
                  key={index}
                  className="flex items-center justify-between py-3"
                >
                  <div className="flex items-center gap-3">
                    <span className={`w-2 h-2 rounded-full flex-shrink-0 ${dotColors[activity.type] || 'bg-neutral-400'}`} />
                    <span className="text-sm text-neutral-900 dark:text-white">
                      {activity.title}
                    </span>
                  </div>
                  <span className="text-xs text-neutral-500 dark:text-neutral-400 ml-4 flex-shrink-0">
                    {activity.time}
                  </span>
                </div>
              );
            })}
          </div>
          <button className="text-sm text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 font-medium mt-3">
            {t('dashboard.viewAllActivity')}
          </button>
        </div>

        {/* Quick Actions - pill-style links */}
        <div>
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
                    ? 'bg-[#1e3a5f] text-white border border-[#1e3a5f] hover:bg-[#234876] dark:bg-[#7ba3cc] dark:text-neutral-900 dark:border-[#7ba3cc] dark:hover:bg-[#94b8d9]'
                    : 'border border-neutral-200 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-800'
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
