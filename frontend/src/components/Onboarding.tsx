'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';

interface OnboardingProps {
  role: 'admin' | 'instructor' | 'student';
  userName: string;
  onComplete: () => void;
}

const roleContent = {
  admin: {
    title: 'Welcome, Administrator',
    subtitle: 'You have full access to manage AristAI',
    features: [
      {
        icon: '📚',
        title: 'Courses',
        description: 'Create and manage courses, upload syllabi, and generate AI session plans.',
      },
      {
        icon: '👥',
        title: 'Instructor Requests',
        description: 'Review and approve requests from students who want to become instructors.',
      },
      {
        icon: '📋',
        title: 'CSV Roster Upload',
        description: 'Bulk-enroll students by uploading a CSV file with email and name columns.',
      },
      {
        icon: '🎯',
        title: 'Sessions & Forum',
        description: 'Manage live sessions, post case studies, and moderate discussions.',
      },
      {
        icon: '🤖',
        title: 'AI Copilot',
        description: 'Use the live copilot to get real-time teaching suggestions during discussions.',
      },
      {
        icon: '📊',
        title: 'Reports',
        description: 'Generate comprehensive reports with participation metrics and answer scoring.',
      },
    ],
    navigation: [
      { name: 'Courses', path: '/courses', description: 'Manage courses and enrollment' },
      { name: 'Sessions', path: '/sessions', description: 'View and manage session plans' },
      { name: 'Forum', path: '/forum', description: 'Moderate student discussions' },
      { name: 'Console', path: '/console', description: 'AI Copilot, Polls, Instructor Requests, Roster Upload' },
      { name: 'Reports', path: '/reports', description: 'View session analytics' },
    ],
  },
  instructor: {
    title: 'Welcome, Instructor',
    subtitle: 'Your AI-powered teaching assistant is ready',
    features: [
      {
        icon: '📚',
        title: 'Courses',
        description: 'Create courses with syllabi and objectives. AI generates session plans automatically.',
      },
      {
        icon: '👥',
        title: 'Enrollment',
        description: 'Enroll students individually or use the bulk enrollment feature.',
      },
      {
        icon: '🎯',
        title: 'Sessions',
        description: 'Manage session lifecycle: draft, scheduled, live, and completed.',
      },
      {
        icon: '💬',
        title: 'Forum',
        description: 'Post case studies, moderate discussions, pin important posts, and add labels.',
      },
      {
        icon: '🤖',
        title: 'AI Copilot',
        description: 'Get real-time suggestions, confusion detection, and poll recommendations.',
      },
      {
        icon: '📊',
        title: 'Reports',
        description: 'Generate reports with themes, participation metrics, and answer scoring.',
      },
    ],
    navigation: [
      { name: 'Courses', path: '/courses', description: 'Manage your courses' },
      { name: 'Sessions', path: '/sessions', description: 'View AI-generated session plans' },
      { name: 'Forum', path: '/forum', description: 'Run discussions with students' },
      { name: 'Console', path: '/console', description: 'AI Copilot and Polls' },
      { name: 'Reports', path: '/reports', description: 'View session analytics' },
    ],
  },
  student: {
    title: 'Welcome, Student',
    subtitle: 'Join discussions and engage with your courses',
    features: [
      {
        icon: '📚',
        title: 'Courses',
        description: 'View courses you are enrolled in. Join new courses using a join code.',
      },
      {
        icon: '🎯',
        title: 'Sessions',
        description: 'See upcoming and past sessions with learning objectives and topics.',
      },
      {
        icon: '💬',
        title: 'Forum',
        description: 'Participate in discussions, respond to case studies, and reply to peers.',
      },
      {
        icon: '📊',
        title: 'Reports',
        description: 'Review session summaries and see key takeaways from discussions.',
      },
      {
        icon: '🗳️',
        title: 'Polls',
        description: 'Vote on polls created by your instructor during live sessions.',
      },
      {
        icon: '🎓',
        title: 'Become Instructor',
        description: 'Request instructor access if you want to create your own courses.',
      },
    ],
    navigation: [
      { name: 'Courses', path: '/courses', description: 'View enrolled courses or join new ones' },
      { name: 'Sessions', path: '/sessions', description: 'See session schedules and plans' },
      { name: 'Forum', path: '/forum', description: 'Participate in discussions' },
      { name: 'Reports', path: '/reports', description: 'Review session summaries' },
    ],
  },
};

export function Onboarding({ role, userName, onComplete }: OnboardingProps) {
  const content = roleContent[role];
  const [isVisible, setIsVisible] = useState(true);

  const handleComplete = () => {
    setIsVisible(false);
    setTimeout(onComplete, 300);
  };

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center bg-gray-900/95 transition-opacity duration-300 ${
        isVisible ? 'opacity-100' : 'opacity-0'
      }`}
    >
      <div className="max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="bg-gray-800 rounded-2xl shadow-2xl border border-gray-700 p-8">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-white mb-2">{content.title}</h1>
            <p className="text-gray-400 text-lg">{content.subtitle}</p>
            <p className="text-purple-400 mt-2">Hello, {userName}!</p>
          </div>

          {/* Features Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
            {content.features.map((feature, index) => (
              <div
                key={index}
                className="bg-gray-700/50 rounded-lg p-4 border border-gray-600 hover:border-purple-500 transition-colors"
              >
                <div className="text-2xl mb-2">{feature.icon}</div>
                <h3 className="text-white font-semibold mb-1">{feature.title}</h3>
                <p className="text-gray-400 text-sm">{feature.description}</p>
              </div>
            ))}
          </div>

          {/* Navigation Guide */}
          <div className="bg-gray-700/30 rounded-lg p-6 mb-8">
            <h2 className="text-white font-semibold mb-4">Your Navigation</h2>
            <div className="flex flex-wrap gap-3">
              {content.navigation.map((nav, index) => (
                <div
                  key={index}
                  className="bg-gray-800 rounded-lg px-4 py-2 border border-gray-600"
                >
                  <span className="text-purple-400 font-medium">{nav.name}</span>
                  <span className="text-gray-500 text-sm ml-2">- {nav.description}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Action Button */}
          <div className="text-center">
            <Button
              onClick={handleComplete}
              className="px-8 py-3 text-lg bg-purple-600 hover:bg-purple-700"
            >
              I Got It!
            </Button>
            <p className="text-gray-500 text-sm mt-3">
              You can always find help in the documentation
            </p>
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

  return { showOnboarding, completeOnboarding, isReady };
}
