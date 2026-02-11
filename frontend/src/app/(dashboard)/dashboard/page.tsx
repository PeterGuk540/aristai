'use client';

import { useAuth } from '@/lib/auth-context';
import { BookOpen, Calendar, MessageSquare, TrendingUp, Users, Activity, ArrowRight } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui';
import Link from 'next/link';

export default function DashboardPage() {
  const { user } = useAuth();
  const t = useTranslations();

  const stats = [
    {
      name: t('dashboard.activeCourses'),
      value: '4',
      icon: BookOpen,
      gradient: 'from-primary-500 to-primary-700',
      bgLight: 'bg-primary-50 dark:bg-primary-900/30',
      textColor: 'text-primary-600 dark:text-primary-400'
    },
    {
      name: t('dashboard.upcomingSessions'),
      value: '12',
      icon: Calendar,
      gradient: 'from-success-500 to-success-700',
      bgLight: 'bg-success-50 dark:bg-success-900/30',
      textColor: 'text-success-600 dark:text-success-400'
    },
    {
      name: t('dashboard.forumPosts'),
      value: '89',
      icon: MessageSquare,
      gradient: 'from-accent-400 to-accent-600',
      bgLight: 'bg-accent-50 dark:bg-accent-900/30',
      textColor: 'text-accent-600 dark:text-accent-400'
    },
    {
      name: t('dashboard.studentsEngaged'),
      value: '156',
      icon: Users,
      gradient: 'from-info-500 to-info-700',
      bgLight: 'bg-info-50 dark:bg-info-900/30',
      textColor: 'text-info-600 dark:text-info-400'
    },
  ];

  const recentActivity = [
    { title: t('dashboard.activity.newDiscussion'), time: t('dashboard.activity.fiveMinutesAgo'), type: 'discussion' },
    { title: t('dashboard.activity.sessionCompleted'), time: t('dashboard.activity.oneHourAgo'), type: 'session' },
    { title: t('dashboard.activity.reportGenerated'), time: t('dashboard.activity.twoHoursAgo'), type: 'report' },
    { title: t('dashboard.activity.newEnrollment'), time: t('dashboard.activity.threeHoursAgo'), type: 'enrollment' },
  ];

  const quickActions = [
    {
      icon: BookOpen,
      label: t('dashboard.createCourse'),
      href: '/courses',
      description: 'Set up a new course'
    },
    {
      icon: Calendar,
      label: t('dashboard.startSession'),
      href: '/sessions',
      description: 'Begin live discussion'
    },
    {
      icon: MessageSquare,
      label: t('dashboard.newDiscussion'),
      href: '/forum',
      description: 'Start a conversation'
    },
    {
      icon: Users,
      label: t('dashboard.inviteStudents'),
      href: '/courses',
      description: 'Add participants'
    },
  ];

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'discussion': return MessageSquare;
      case 'session': return Calendar;
      case 'report': return Activity;
      case 'enrollment': return Users;
      default: return Activity;
    }
  };

  const getActivityColor = (type: string) => {
    switch (type) {
      case 'discussion': return 'bg-accent-100 dark:bg-accent-900/50 text-accent-600 dark:text-accent-400';
      case 'session': return 'bg-success-100 dark:bg-success-900/50 text-success-600 dark:text-success-400';
      case 'report': return 'bg-info-100 dark:bg-info-900/50 text-info-600 dark:text-info-400';
      case 'enrollment': return 'bg-primary-100 dark:bg-primary-900/50 text-primary-600 dark:text-primary-400';
      default: return 'bg-neutral-100 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-400';
    }
  };

  return (
    <div className="space-y-8">
      {/* Welcome section */}
      <div className="relative">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-neutral-900 dark:text-white">
              {t('dashboard.welcomeBack', { name: user?.name || user?.email?.split('@')[0] || 'User' })}
            </h1>
            <p className="mt-2 text-neutral-600 dark:text-neutral-400 max-w-2xl">
              {t('dashboard.subtitle')}
            </p>
          </div>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card
            key={stat.name}
            variant="default"
            hover
            className="overflow-hidden"
          >
            <div className="p-6">
              <div className="flex items-center gap-4">
                <div className={`p-3 rounded-xl ${stat.bgLight}`}>
                  <stat.icon className={`h-6 w-6 ${stat.textColor}`} />
                </div>
                <div>
                  <p className="text-3xl font-bold text-neutral-900 dark:text-white">{stat.value}</p>
                  <p className="text-sm text-neutral-500 dark:text-neutral-400">{stat.name}</p>
                </div>
              </div>
            </div>
            <div className="px-6 pb-4">
              <div className="h-px bg-neutral-200 dark:bg-neutral-700" />
            </div>
          </Card>
        ))}
      </div>

      {/* Content grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Recent Activity */}
        <Card variant="default">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-primary-100 dark:bg-primary-900/50">
                <Activity className="h-4 w-4 text-primary-600 dark:text-primary-400" />
              </div>
              {t('dashboard.recentActivity')}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-neutral-200 dark:divide-neutral-700">
              {recentActivity.map((activity, index) => {
                const Icon = getActivityIcon(activity.type);
                return (
                  <div
                    key={index}
                    className="px-6 py-4 hover:bg-neutral-50 dark:hover:bg-neutral-700/50 transition-colors cursor-pointer group"
                  >
                    <div className="flex items-center gap-4">
                      <div className={`p-2 rounded-lg ${getActivityColor(activity.type)}`}>
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-neutral-900 dark:text-white truncate">
                          {activity.title}
                        </p>
                        <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
                          {activity.time}
                        </p>
                      </div>
                      <ArrowRight className="h-4 w-4 text-neutral-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
          <div className="px-6 py-4 border-t border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800/50 rounded-b-xl">
            <button className="text-sm text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 font-medium flex items-center gap-1">
              {t('dashboard.viewAllActivity')}
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </Card>

        {/* Quick Actions */}
        <Card variant="default">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-accent-100 dark:bg-accent-900/50">
                <TrendingUp className="h-4 w-4 text-accent-600 dark:text-accent-400" />
              </div>
              {t('dashboard.quickActions')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              {quickActions.map((action, index) => (
                <Link
                  key={index}
                  href={action.href}
                  className="group flex flex-col items-center justify-center p-5 rounded-xl border-2 border-dashed border-neutral-200 dark:border-neutral-700 hover:border-primary-400 dark:hover:border-primary-500 hover:bg-primary-50 dark:hover:bg-primary-900/20 transition-all duration-200"
                >
                  <div className="p-3 rounded-xl bg-neutral-100 dark:bg-neutral-700/50 group-hover:bg-primary-100 dark:group-hover:bg-primary-800/50 transition-colors mb-3">
                    <action.icon className="h-6 w-6 text-neutral-500 dark:text-neutral-400 group-hover:text-primary-600 dark:group-hover:text-primary-400 transition-colors" />
                  </div>
                  <span className="text-sm font-medium text-neutral-700 dark:text-neutral-300 group-hover:text-primary-700 dark:group-hover:text-primary-300 text-center transition-colors">
                    {action.label}
                  </span>
                  <span className="text-xs text-neutral-400 dark:text-neutral-500 mt-1 text-center hidden sm:block">
                    {action.description}
                  </span>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
