'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';

interface OnboardingProps {
  role: 'admin' | 'instructor' | 'student';
  userName: string;
  onComplete: () => void;
}

interface TabContent {
  id: string;
  label: string;
  icon: string;
  sections: {
    title: string;
    steps: string[];
  }[];
}

// Admin-specific tabs
const adminTabs: TabContent[] = [
  {
    id: 'courses',
    label: 'Courses',
    icon: '📚',
    sections: [
      {
        title: 'Creating a Course',
        steps: [
          'Click the "Create Course" button on the Courses page',
          'Enter course name, description, syllabus, and learning objectives',
          'Click "Save" - your course is created with a unique Join Code',
          'Find the Join Code displayed on the course card',
          'Share this code with students so they can self-enroll',
        ],
      },
      {
        title: 'Enrolling Students',
        steps: [
          'Option A: Share the Join Code - students enter it on their Courses page',
          'Option B: Go to Console → Roster Upload → Upload a CSV file (columns: email, name)',
          'Option C: Click "Manage Enrollment" on any course to add students individually',
        ],
      },
      {
        title: 'Generating AI Session Plans',
        steps: [
          'Open your course details page',
          'Click "Generate Plans" button',
          'AI will analyze your syllabus and create structured session plans',
          'Review and edit the generated plans as needed',
          'Sessions will appear on the Sessions page',
        ],
      },
    ],
  },
  {
    id: 'sessions',
    label: 'Sessions',
    icon: '🎯',
    sections: [
      {
        title: 'Understanding Session Lifecycle',
        steps: [
          'Draft: Initial state, still being prepared',
          'Scheduled: Ready to go, waiting for start time',
          'Live: Currently active - students can participate',
          'Completed: Session has ended, ready for reports',
        ],
      },
      {
        title: 'Running a Live Session',
        steps: [
          'Go to Sessions page and select your session',
          'Click "Start Session" to change status to Live',
          'Students can now post in the Forum for this session',
          'Use AI Copilot in Console for real-time teaching suggestions',
          'When finished, click "End Session" to mark as Completed',
        ],
      },
    ],
  },
  {
    id: 'forum',
    label: 'Forum',
    icon: '💬',
    sections: [
      {
        title: 'Managing Discussions',
        steps: [
          'Select a course from the dropdown at the top',
          'Select a session (must be Live for active discussion)',
          'Post case studies or discussion prompts for students',
          'View all student posts and replies in real-time',
        ],
      },
      {
        title: 'Moderation Tools',
        steps: [
          'Pin posts: Click the pin icon to keep important posts at the top',
          'Add labels: Categorize posts as Question, Answer, Insight, etc.',
          'Monitor participation: See which students are engaging',
        ],
      },
    ],
  },
  {
    id: 'console',
    label: 'Console',
    icon: '⚙️',
    sections: [
      {
        title: 'Managing Instructor Requests (Admin Only)',
        steps: [
          'Go to Console → Instructor Requests tab',
          'View all pending requests from students who want instructor access',
          'Review each request - see the user\'s name and email',
          'Click "Approve" to grant instructor privileges',
          'Click "Reject" to deny the request',
          'Approved users can immediately create their own courses',
        ],
      },
      {
        title: 'Bulk Roster Upload (Admin Only)',
        steps: [
          'Go to Console → Roster Upload tab',
          'Select the course you want to enroll students in',
          'Prepare a CSV file with columns: email, name',
          'Upload the CSV file',
          'Students will be enrolled automatically (accounts created if needed)',
        ],
      },
      {
        title: 'Using AI Copilot',
        steps: [
          'Go to Console → Copilot tab',
          'Select a Live session from the dropdown',
          'Click "Start Copilot" to begin AI monitoring',
          'Every 90 seconds, receive: discussion summary, confusion points, suggested prompts, poll ideas',
          'Use suggestions to guide your teaching in real-time',
          'Click "Stop Copilot" when the session ends',
        ],
      },
      {
        title: 'Creating Polls',
        steps: [
          'Go to Console → Polls tab',
          'Click "Create Poll" button',
          'Enter your question and answer options',
          'Publish the poll - students can vote immediately',
          'View results in real-time as votes come in',
        ],
      },
    ],
  },
  {
    id: 'reports',
    label: 'Reports',
    icon: '📊',
    sections: [
      {
        title: 'Generating Session Reports',
        steps: [
          'Go to Reports page',
          'Select a completed session',
          'Click "Generate Report" - AI analyzes all discussion posts',
          'Report includes: themes, participation metrics, AI-scored answers, misconceptions',
          'Use insights to improve future sessions',
        ],
      },
    ],
  },
];

// Instructor-specific tabs (similar to admin but without instructor request management)
const instructorTabs: TabContent[] = [
  {
    id: 'courses',
    label: 'Courses',
    icon: '📚',
    sections: [
      {
        title: 'Creating a Course',
        steps: [
          'Click the "Create Course" button on the Courses page',
          'Enter course name, description, syllabus, and learning objectives',
          'Click "Save" - your course is created with a unique Join Code',
          'Find the Join Code displayed on the course card',
          'Share this code with students so they can self-enroll',
        ],
      },
      {
        title: 'Understanding Join Codes',
        steps: [
          'Every course has a unique Join Code (e.g., "ABC123")',
          'Find it on your course card or course detail page',
          'Share this code via email, LMS, or in class',
          'Students enter the code on their Courses page to enroll',
          'This is the easiest way to get students into your course',
        ],
      },
      {
        title: 'Other Enrollment Options',
        steps: [
          'Console → Roster Upload: Upload a CSV file with student emails and names',
          'Manage Enrollment: Add students one-by-one by email',
        ],
      },
      {
        title: 'Generating AI Session Plans',
        steps: [
          'Open your course details page',
          'Click "Generate Plans" button',
          'AI analyzes your syllabus and creates structured session plans',
          'Each plan includes: topics, objectives, discussion prompts, case studies',
          'Review and edit plans before using them',
        ],
      },
    ],
  },
  {
    id: 'sessions',
    label: 'Sessions',
    icon: '🎯',
    sections: [
      {
        title: 'Understanding Session Lifecycle',
        steps: [
          'Draft: Initial state, still being prepared',
          'Scheduled: Ready to go, waiting for start time',
          'Live: Currently active - students can participate in Forum',
          'Completed: Session has ended, ready for report generation',
        ],
      },
      {
        title: 'Running a Live Session',
        steps: [
          'Go to Sessions page and select your session',
          'Click "Start Session" to change status to Live',
          'Students can now see and post in the Forum for this session',
          'Open Console → Copilot for AI-powered teaching assistance',
          'Monitor the Forum for student posts and questions',
          'When finished, click "End Session" to mark as Completed',
        ],
      },
    ],
  },
  {
    id: 'forum',
    label: 'Forum',
    icon: '💬',
    sections: [
      {
        title: 'Running Discussions',
        steps: [
          'Select your course from the dropdown at the top',
          'Select a Live session (discussions only work in Live sessions)',
          'Post case studies or discussion prompts to start the conversation',
          'Students will respond to your prompts and reply to each other',
        ],
      },
      {
        title: 'Moderation Tools',
        steps: [
          'Pin posts: Click the pin icon on important posts to keep them at top',
          'Add labels: Categorize posts (Question, Answer, Insight, Key Point)',
          'Labels help students find important content quickly',
          'All posts are saved for report generation later',
        ],
      },
    ],
  },
  {
    id: 'console',
    label: 'Console',
    icon: '⚙️',
    sections: [
      {
        title: 'Using AI Copilot',
        steps: [
          'Go to Console → Copilot tab',
          'Select a Live session from the dropdown',
          'Click "Start Copilot" to begin AI monitoring',
          'AI analyzes student posts every 90 seconds and provides:',
          '• Rolling summary of the discussion',
          '• Top confusion points or misconceptions detected',
          '• Suggested prompts to re-engage students',
          '• Poll recommendations based on discussion themes',
          'Click "Stop Copilot" when session ends',
        ],
      },
      {
        title: 'Creating Polls',
        steps: [
          'Go to Console → Polls tab',
          'Click "Create Poll" button',
          'Enter your question and 2-4 answer options',
          'Publish the poll - it becomes visible to students immediately',
          'Watch results update in real-time as students vote',
          'Use poll results to guide discussion direction',
        ],
      },
      {
        title: 'Bulk Roster Upload',
        steps: [
          'Go to Console → Roster Upload tab',
          'Select the course you want to enroll students in',
          'Prepare a CSV file with two columns: email, name',
          'Upload the file - students are enrolled automatically',
          'New accounts are created for students not yet registered',
        ],
      },
    ],
  },
  {
    id: 'reports',
    label: 'Reports',
    icon: '📊',
    sections: [
      {
        title: 'Generating Session Reports',
        steps: [
          'Go to Reports page after a session is Completed',
          'Select the session you want to analyze',
          'Click "Generate Report" button',
          'AI processes all posts and produces comprehensive analysis',
        ],
      },
      {
        title: 'What Reports Include',
        steps: [
          'Summary: Key themes, learning objective alignment, misconceptions',
          'Participation: Who posted, who didn\'t, participation rate',
          'Scoring: AI-graded student answers (0-100) with feedback',
          'Use these insights to identify struggling students and improve teaching',
        ],
      },
    ],
  },
];

// Student-specific tabs
const studentTabs: TabContent[] = [
  {
    id: 'courses',
    label: 'Courses',
    icon: '📚',
    sections: [
      {
        title: 'Joining a Course',
        steps: [
          'Get the Join Code from your instructor (e.g., via email or in class)',
          'Go to the Courses page',
          'Click the "Join Course" button',
          'Enter the Join Code exactly as provided',
          'Click "Join" - you\'re now enrolled!',
          'The course will appear in your course list immediately',
        ],
      },
      {
        title: 'Viewing Your Courses',
        steps: [
          'All courses you\'re enrolled in appear on the Courses page',
          'Click on any course to see its details',
          'View course description, objectives, and syllabus',
          'Access sessions and forum from the course page',
        ],
      },
    ],
  },
  {
    id: 'sessions',
    label: 'Sessions',
    icon: '🎯',
    sections: [
      {
        title: 'Understanding Sessions',
        steps: [
          'Each course has multiple sessions (like class meetings)',
          'Sessions show: Topic, learning objectives, and discussion prompts',
          'Look for session status to know what\'s happening:',
          '• Scheduled: Upcoming session, not yet active',
          '• Live: Happening now - go to Forum to participate!',
          '• Completed: Session ended, check Reports for summary',
        ],
      },
      {
        title: 'Participating in Live Sessions',
        steps: [
          'When a session is Live, go to the Forum page',
          'Select the course and Live session',
          'Read the case study or discussion prompt',
          'Post your thoughts and respond to classmates',
          'Your participation is tracked and may be graded',
        ],
      },
    ],
  },
  {
    id: 'forum',
    label: 'Forum',
    icon: '💬',
    sections: [
      {
        title: 'Participating in Discussions',
        steps: [
          'Select your course from the dropdown at the top',
          'Select the Live session to see the discussion',
          'Read the case study or prompt posted by your instructor',
          'Click "New Post" to share your response',
          'Be thoughtful - your posts may be AI-scored in reports',
        ],
      },
      {
        title: 'Engaging with Classmates',
        steps: [
          'Read posts from your classmates',
          'Click "Reply" to respond to someone\'s post',
          'Build on others\' ideas or respectfully disagree',
          'Look for pinned posts - they contain important information',
          'Posts with labels (Question, Key Point, etc.) highlight important content',
        ],
      },
      {
        title: 'Voting on Polls',
        steps: [
          'During Live sessions, your instructor may create polls',
          'Polls appear in the Forum or as notifications',
          'Click on a poll to see the question and options',
          'Select your answer and submit',
          'Some polls show results immediately, others after voting closes',
        ],
      },
    ],
  },
  {
    id: 'reports',
    label: 'Reports',
    icon: '📊',
    sections: [
      {
        title: 'Viewing Session Reports',
        steps: [
          'After a session is Completed, go to Reports page',
          'Select the session to view its report',
          'Reports include summaries of key discussion themes',
          'See main takeaways and learning points',
          'Review any misconceptions that were clarified',
        ],
      },
    ],
  },
  {
    id: 'instructor',
    label: 'Become Instructor',
    icon: '🎓',
    sections: [
      {
        title: 'Requesting Instructor Access',
        steps: [
          'Want to create your own courses? You can request instructor access',
          'Go to your Profile (click your name in the top right)',
          'Click "Request Instructor Access" button',
          'Your request is sent to administrators for review',
          'Once approved, you can create and manage your own courses',
          'You\'ll still be able to participate as a student in other courses',
        ],
      },
    ],
  },
];

const roleConfig = {
  admin: {
    title: 'Welcome, Administrator',
    subtitle: 'Complete guide to managing AristAI',
    tabs: adminTabs,
  },
  instructor: {
    title: 'Welcome, Instructor',
    subtitle: 'Your AI-powered teaching assistant guide',
    tabs: instructorTabs,
  },
  student: {
    title: 'Welcome, Student',
    subtitle: 'Guide to participating in your courses',
    tabs: studentTabs,
  },
};

export function Onboarding({ role, userName, onComplete }: OnboardingProps) {
  const config = roleConfig[role];
  const [isVisible, setIsVisible] = useState(true);
  const [activeTab, setActiveTab] = useState(config.tabs[0].id);

  const handleComplete = () => {
    setIsVisible(false);
    setTimeout(onComplete, 300);
  };

  const activeTabContent = config.tabs.find((tab) => tab.id === activeTab);

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
              {config.title}
            </h1>
            <p className="text-gray-600 dark:text-gray-400">{config.subtitle}</p>
            <p className="text-primary-600 dark:text-primary-400 text-sm mt-1">
              Hello, {userName}!
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
                <span>{tab.label}</span>
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-y-auto p-6">
            {activeTabContent && (
              <div className="space-y-6">
                {activeTabContent.sections.map((section, sectionIndex) => (
                  <div key={sectionIndex}>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
                      {section.title}
                    </h3>
                    <ol className="space-y-2">
                      {section.steps.map((step, stepIndex) => (
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
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="border-t border-gray-200 dark:border-gray-700 px-8 py-4 flex-shrink-0">
            <div className="flex items-center justify-between">
              <p className="text-gray-500 dark:text-gray-500 text-sm">
                Access this guide anytime from the user menu → View Voice Guide
              </p>
              <Button
                onClick={handleComplete}
                className="px-6 py-2 bg-primary-600 hover:bg-primary-700"
              >
                I Got It!
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
