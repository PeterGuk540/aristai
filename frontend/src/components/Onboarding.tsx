'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';
import { useTranslations } from 'next-intl';
import { useLanguage } from '@/lib/i18n-provider';

interface OnboardingProps {
  role: 'admin' | 'instructor' | 'student';
  userName: string;
  onComplete: () => void;
}

interface TabContent {
  id: string;
  labelKey: string;
  icon: string;
  sections: {
    titleKey: string;
    stepsKey: string;
  }[];
}

// Tab structure (keys only, content comes from translations)
const adminTabs: TabContent[] = [
  {
    id: 'courses',
    labelKey: 'onboarding.tabs.courses',
    icon: '📚',
    sections: [
      { titleKey: 'onboarding.admin.courses.creating.title', stepsKey: 'onboarding.admin.courses.creating.steps' },
      { titleKey: 'onboarding.admin.courses.enrolling.title', stepsKey: 'onboarding.admin.courses.enrolling.steps' },
      { titleKey: 'onboarding.admin.courses.generating.title', stepsKey: 'onboarding.admin.courses.generating.steps' },
    ],
  },
  {
    id: 'sessions',
    labelKey: 'onboarding.tabs.sessions',
    icon: '🎯',
    sections: [
      { titleKey: 'onboarding.admin.sessions.creating.title', stepsKey: 'onboarding.admin.sessions.creating.steps' },
      { titleKey: 'onboarding.admin.sessions.lifecycle.title', stepsKey: 'onboarding.admin.sessions.lifecycle.steps' },
      { titleKey: 'onboarding.admin.sessions.running.title', stepsKey: 'onboarding.admin.sessions.running.steps' },
    ],
  },
  {
    id: 'forum',
    labelKey: 'onboarding.tabs.forum',
    icon: '💬',
    sections: [
      { titleKey: 'onboarding.admin.forum.managing.title', stepsKey: 'onboarding.admin.forum.managing.steps' },
      { titleKey: 'onboarding.admin.forum.moderation.title', stepsKey: 'onboarding.admin.forum.moderation.steps' },
    ],
  },
  {
    id: 'console',
    labelKey: 'onboarding.tabs.console',
    icon: '⚙️',
    sections: [
      { titleKey: 'onboarding.admin.console.requests.title', stepsKey: 'onboarding.admin.console.requests.steps' },
      { titleKey: 'onboarding.admin.console.roster.title', stepsKey: 'onboarding.admin.console.roster.steps' },
      { titleKey: 'onboarding.admin.console.copilot.title', stepsKey: 'onboarding.admin.console.copilot.steps' },
      { titleKey: 'onboarding.admin.console.polls.title', stepsKey: 'onboarding.admin.console.polls.steps' },
    ],
  },
  {
    id: 'reports',
    labelKey: 'onboarding.tabs.reports',
    icon: '📊',
    sections: [
      { titleKey: 'onboarding.admin.reports.generating.title', stepsKey: 'onboarding.admin.reports.generating.steps' },
    ],
  },
];

const instructorTabs: TabContent[] = [
  {
    id: 'courses',
    labelKey: 'onboarding.tabs.courses',
    icon: '📚',
    sections: [
      { titleKey: 'onboarding.instructor.courses.creating.title', stepsKey: 'onboarding.instructor.courses.creating.steps' },
      { titleKey: 'onboarding.instructor.courses.joinCodes.title', stepsKey: 'onboarding.instructor.courses.joinCodes.steps' },
      { titleKey: 'onboarding.instructor.courses.generating.title', stepsKey: 'onboarding.instructor.courses.generating.steps' },
    ],
  },
  {
    id: 'sessions',
    labelKey: 'onboarding.tabs.sessions',
    icon: '🎯',
    sections: [
      { titleKey: 'onboarding.instructor.sessions.creating.title', stepsKey: 'onboarding.instructor.sessions.creating.steps' },
      { titleKey: 'onboarding.instructor.sessions.lifecycle.title', stepsKey: 'onboarding.instructor.sessions.lifecycle.steps' },
      { titleKey: 'onboarding.instructor.sessions.running.title', stepsKey: 'onboarding.instructor.sessions.running.steps' },
    ],
  },
  {
    id: 'forum',
    labelKey: 'onboarding.tabs.forum',
    icon: '💬',
    sections: [
      { titleKey: 'onboarding.instructor.forum.running.title', stepsKey: 'onboarding.instructor.forum.running.steps' },
      { titleKey: 'onboarding.instructor.forum.moderation.title', stepsKey: 'onboarding.instructor.forum.moderation.steps' },
    ],
  },
  {
    id: 'console',
    labelKey: 'onboarding.tabs.console',
    icon: '⚙️',
    sections: [
      { titleKey: 'onboarding.instructor.console.copilot.title', stepsKey: 'onboarding.instructor.console.copilot.steps' },
      { titleKey: 'onboarding.instructor.console.polls.title', stepsKey: 'onboarding.instructor.console.polls.steps' },
      { titleKey: 'onboarding.instructor.console.roster.title', stepsKey: 'onboarding.instructor.console.roster.steps' },
    ],
  },
  {
    id: 'reports',
    labelKey: 'onboarding.tabs.reports',
    icon: '📊',
    sections: [
      { titleKey: 'onboarding.instructor.reports.generating.title', stepsKey: 'onboarding.instructor.reports.generating.steps' },
      { titleKey: 'onboarding.instructor.reports.includes.title', stepsKey: 'onboarding.instructor.reports.includes.steps' },
    ],
  },
];

const studentTabs: TabContent[] = [
  {
    id: 'courses',
    labelKey: 'onboarding.tabs.courses',
    icon: '📚',
    sections: [
      { titleKey: 'onboarding.student.courses.joining.title', stepsKey: 'onboarding.student.courses.joining.steps' },
      { titleKey: 'onboarding.student.courses.viewing.title', stepsKey: 'onboarding.student.courses.viewing.steps' },
    ],
  },
  {
    id: 'sessions',
    labelKey: 'onboarding.tabs.sessions',
    icon: '🎯',
    sections: [
      { titleKey: 'onboarding.student.sessions.understanding.title', stepsKey: 'onboarding.student.sessions.understanding.steps' },
      { titleKey: 'onboarding.student.sessions.participating.title', stepsKey: 'onboarding.student.sessions.participating.steps' },
    ],
  },
  {
    id: 'forum',
    labelKey: 'onboarding.tabs.forum',
    icon: '💬',
    sections: [
      { titleKey: 'onboarding.student.forum.participating.title', stepsKey: 'onboarding.student.forum.participating.steps' },
      { titleKey: 'onboarding.student.forum.engaging.title', stepsKey: 'onboarding.student.forum.engaging.steps' },
      { titleKey: 'onboarding.student.forum.polls.title', stepsKey: 'onboarding.student.forum.polls.steps' },
    ],
  },
  {
    id: 'reports',
    labelKey: 'onboarding.tabs.reports',
    icon: '📊',
    sections: [
      { titleKey: 'onboarding.student.reports.viewing.title', stepsKey: 'onboarding.student.reports.viewing.steps' },
    ],
  },
  {
    id: 'instructor',
    labelKey: 'onboarding.tabs.becomeInstructor',
    icon: '🎓',
    sections: [
      { titleKey: 'onboarding.student.instructor.requesting.title', stepsKey: 'onboarding.student.instructor.requesting.steps' },
    ],
  },
];

const roleConfig = {
  admin: {
    titleKey: 'onboarding.admin.title',
    subtitleKey: 'onboarding.admin.subtitle',
    tabs: adminTabs,
  },
  instructor: {
    titleKey: 'onboarding.instructor.title',
    subtitleKey: 'onboarding.instructor.subtitle',
    tabs: instructorTabs,
  },
  student: {
    titleKey: 'onboarding.student.title',
    subtitleKey: 'onboarding.student.subtitle',
    tabs: studentTabs,
  },
};

export function Onboarding({ role, userName, onComplete }: OnboardingProps) {
  const config = roleConfig[role];
  const [isVisible, setIsVisible] = useState(true);
  const [activeTab, setActiveTab] = useState(config.tabs[0].id);
  const t = useTranslations();

  const handleComplete = () => {
    setIsVisible(false);
    setTimeout(onComplete, 300);
  };

  const activeTabContent = config.tabs.find((tab) => tab.id === activeTab);

  // Helper to get steps array from translation
  const getSteps = (stepsKey: string): string[] => {
    try {
      const raw = t.raw(stepsKey);
      if (Array.isArray(raw)) {
        return raw;
      }
      return [];
    } catch {
      return [];
    }
  };

  return (
    <div
      className={cn(
        'fixed inset-0 z-50 flex items-center justify-center bg-black/50 dark:bg-black/70 transition-opacity duration-300',
        isVisible ? 'opacity-100' : 'opacity-0'
      )}
    >
      <div className="max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden flex flex-col">
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 flex flex-col max-h-[90vh]">
          {/* Header */}
          <div className="text-center py-6 px-8 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-1">
              {t(config.titleKey)}
            </h1>
            <p className="text-gray-600 dark:text-gray-400">{t(config.subtitleKey)}</p>
            <p className="text-primary-600 dark:text-primary-400 text-sm mt-1">
              {t('onboarding.hello', { name: userName })}
            </p>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-gray-200 dark:border-gray-700 px-4 overflow-x-auto flex-shrink-0">
            {config.tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
                  activeTab === tab.id
                    ? 'border-primary-600 text-primary-600 dark:border-primary-400 dark:text-primary-400'
                    : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                )}
              >
                <span>{tab.icon}</span>
                <span>{t(tab.labelKey)}</span>
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-y-auto p-6">
            {activeTabContent && (
              <div className="space-y-6">
                {activeTabContent.sections.map((section, sectionIndex) => {
                  const steps = getSteps(section.stepsKey);
                  return (
                    <div key={sectionIndex}>
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
                        {t(section.titleKey)}
                      </h3>
                      <ol className="space-y-2">
                        {steps.map((step, stepIndex) => (
                          <li
                            key={stepIndex}
                            className="flex gap-3 text-gray-700 dark:text-gray-300"
                          >
                            <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary-100 dark:bg-primary-900/50 text-primary-600 dark:text-primary-400 text-sm flex items-center justify-center font-medium">
                              {stepIndex + 1}
                            </span>
                            <span className="pt-0.5">{step}</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="border-t border-gray-200 dark:border-gray-700 px-8 py-4 flex-shrink-0">
            <div className="flex items-center justify-between">
              <p className="text-gray-500 dark:text-gray-500 text-sm">
                {t('onboarding.accessAnytime')}
              </p>
              <Button
                onClick={handleComplete}
                className="px-6 py-2 bg-primary-600 hover:bg-primary-700"
                data-voice-id="got-it-platform-guide"
              >
                {t('onboarding.gotIt')}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Hook to manage onboarding state
export function useOnboarding(userId: number | undefined, role: string | undefined) {
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    if (!userId || !role) {
      setIsReady(true);
      return;
    }

    const storageKey = `aristai_onboarding_${userId}`;
    const hasSeenOnboarding = localStorage.getItem(storageKey);

    if (!hasSeenOnboarding) {
      setShowOnboarding(true);
    }
    setIsReady(true);
  }, [userId, role]);

  const completeOnboarding = () => {
    if (userId) {
      const storageKey = `aristai_onboarding_${userId}`;
      localStorage.setItem(storageKey, 'true');
    }
    setShowOnboarding(false);
  };

  // Allow manually showing the guide again
  const showGuide = () => {
    setShowOnboarding(true);
  };

  return { showOnboarding, completeOnboarding, showGuide, isReady };
}
