'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  BookOpen,
  Mic,
  MessageSquare,
  Calendar,
  FileText,
  Settings,
  BarChart3,
  Users,
  Sparkles,
  ChevronRight,
  Check,
  Play,
  Zap,
  Target,
  Clock,
  ArrowRight,
  Plus,
  Volume2,
  Navigation,
  PenTool,
  LayoutDashboard,
} from 'lucide-react';
import { useUser } from '@/lib/context';

/* ==============================================
   AristAI Platform Introduction
   Design: Matching ebook.aristai.io
   ============================================== */

// Feature data for the platform overview
const platformFeatures = [
  {
    icon: BookOpen,
    title: 'Course Creation',
    description: 'Upload your syllabus and let AI automatically extract learning objectives. Create structured courses with sessions, topics, and discussion prompts.',
    forRole: 'instructor',
  },
  {
    icon: Calendar,
    title: 'Session Management',
    description: 'Plan and schedule live discussion sessions. Generate AI-powered lesson plans with topics, case studies, and facilitation notes.',
    forRole: 'instructor',
  },
  {
    icon: MessageSquare,
    title: 'Live Discussion Forum',
    description: 'Engage in real-time case-based discussions. Post responses, reply to peers, and receive immediate feedback from instructors.',
    forRole: 'all',
  },
  {
    icon: Sparkles,
    title: 'AI Teaching Copilot',
    description: 'Real-time assistance during live sessions. Detect student confusion, get suggested prompts, and receive facilitation recommendations.',
    forRole: 'instructor',
  },
  {
    icon: BarChart3,
    title: 'Comprehensive Reports',
    description: 'Generate detailed session reports with participation metrics, answer scoring, learning objective alignment, and AI-powered summaries.',
    forRole: 'all',
  },
  {
    icon: Mic,
    title: 'Voice Control',
    description: 'Control the entire platform hands-free using natural language. Navigate, create content, manage sessions, and generate reports by speaking.',
    forRole: 'all',
  },
];

// Voice commands organized by context
const voiceCommandGroups = [
  {
    category: 'Navigation',
    icon: Navigation,
    description: 'Move between pages instantly',
    commands: [
      { phrase: 'Go to courses', action: 'Navigate to the Courses page' },
      { phrase: 'Go to sessions', action: 'Navigate to the Sessions page' },
      { phrase: 'Go to forum', action: 'Navigate to the Discussion Forum' },
      { phrase: 'Go to console', action: 'Open the Instructor Console' },
      { phrase: 'Go to reports', action: 'Navigate to the Reports page' },
      { phrase: 'Switch to dark mode', action: 'Toggle the theme' },
    ],
  },
  {
    category: 'Course Management',
    icon: BookOpen,
    description: 'Create and manage courses',
    commands: [
      { phrase: 'Create a new course', action: 'Open the course creation form' },
      { phrase: 'Show my courses', action: 'Display your enrolled or created courses' },
      { phrase: 'Generate lesson plans for [course name]', action: 'Generate AI session plans' },
      { phrase: 'What courses do I have?', action: 'List all available courses' },
    ],
  },
  {
    category: 'Session Control',
    icon: Calendar,
    description: 'Manage live sessions',
    commands: [
      { phrase: 'Create a new session', action: 'Open the session creation form' },
      { phrase: 'Go live', action: 'Set the current session to live status' },
      { phrase: 'Complete session', action: 'Mark the session as completed' },
      { phrase: 'Start a [X] minute timer', action: 'Start a countdown timer' },
    ],
  },
  {
    category: 'Discussion Forum',
    icon: MessageSquare,
    description: 'Participate in discussions',
    commands: [
      { phrase: 'Show cases', action: 'Switch to the Cases tab' },
      { phrase: 'Show discussion', action: 'Switch to the Discussion tab' },
      { phrase: 'Post my response', action: 'Submit your written response' },
      { phrase: 'Refresh the discussion', action: 'Reload the latest posts' },
    ],
  },
  {
    category: 'Instructor Console',
    icon: Settings,
    description: 'Real-time teaching tools',
    commands: [
      { phrase: 'Start copilot', action: 'Activate the AI teaching assistant' },
      { phrase: 'Stop copilot', action: 'Deactivate the AI copilot' },
      { phrase: 'Create a poll', action: 'Open the poll creation form' },
      { phrase: 'Post a case study', action: 'Create a new case for discussion' },
      { phrase: 'Show engagement heatmap', action: 'View student participation levels' },
      { phrase: 'Split into [X] groups', action: 'Create breakout groups' },
      { phrase: 'Who should I call on?', action: 'Get facilitation suggestions' },
    ],
  },
  {
    category: 'Reports & Analytics',
    icon: FileText,
    description: 'Generate insights',
    commands: [
      { phrase: 'Generate report', action: 'Create a session report' },
      { phrase: 'Show analytics', action: 'View course analytics' },
      { phrase: 'Compare sessions', action: 'Compare multiple sessions' },
      { phrase: 'How has [student name] been doing?', action: 'Get individual student progress' },
    ],
  },
];

// Quick start steps
const instructorSteps = [
  {
    title: 'Create a Course',
    description: 'Go to Courses and click "Create Course". Paste your syllabus or course description. AristAI will automatically extract learning objectives using AI.',
  },
  {
    title: 'Generate Session Plans',
    description: 'Once your course is created, click "Generate Plans" to create AI-powered session plans complete with topics, case studies, and discussion prompts.',
  },
  {
    title: 'Go Live',
    description: 'When ready for class, set a session to "Live" status. This opens the discussion forum for students and activates your Instructor Console.',
  },
  {
    title: 'Facilitate with AI',
    description: 'Use the Console to monitor discussions, start the AI Copilot for real-time assistance, create polls, and manage engagement.',
  },
  {
    title: 'Generate Reports',
    description: 'After each session, generate comprehensive reports with participation metrics, answer scoring, and AI-generated summaries.',
  },
];

const studentSteps = [
  {
    title: 'Join a Course',
    description: 'Get a join code from your instructor and enter it on the Courses page to enroll in a course.',
  },
  {
    title: 'View Sessions',
    description: 'Check the Sessions page to see upcoming discussion sessions and any materials your instructor has shared.',
  },
  {
    title: 'Join the Discussion',
    description: 'When a session is live, go to the Forum to read the case study and post your responses. Engage with peer discussions.',
  },
  {
    title: 'Review Your Progress',
    description: 'Check the Reports page to see your participation, scores, and feedback from instructors.',
  },
];

// FAQ data
const faqItems = [
  {
    question: 'How do I use voice commands?',
    answer: 'Click the microphone icon in the bottom-right corner to activate voice mode. Wait for the "Listening" indicator, then speak naturally. The AI assistant understands context and can execute complex multi-step commands.',
  },
  {
    question: 'What makes AristAI different from other LMS platforms?',
    answer: 'AristAI is purpose-built for synchronous case-based discussions. It combines real-time AI assistance, voice control, automatic learning objective alignment, and comprehensive analytics in one platform designed for interactive classroom experiences.',
  },
  {
    question: 'Can I use AristAI for asynchronous classes?',
    answer: 'While AristAI is optimized for live discussions, you can use it for asynchronous learning by setting sessions to "Scheduled" and allowing students to post at their own pace before you mark it complete.',
  },
  {
    question: 'How does the AI Copilot help during class?',
    answer: 'The AI Copilot monitors the discussion in real-time, detects when students seem confused, suggests probing questions, recommends which students to call on for balanced participation, and can generate discussion summaries on demand.',
  },
  {
    question: 'Is my course content private?',
    answer: 'Yes. Your courses, sessions, and student data are private to your institution. The AI features process content securely and do not share information between organizations.',
  },
];

export default function IntroductionPage() {
  const { isInstructor, isAdmin, currentUser } = useUser();
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const showInstructorContent = isInstructor || isAdmin;
  const steps = showInstructorContent ? instructorSteps : studentSteps;

  return (
    <div className="animate-fade-in">
      {/* Hero Section */}
      <section className="bg-hero-gradient -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8 pt-12 pb-16 mb-12">
        <div className="container-ebook">
          <p className="section-label mb-4">Platform Guide</p>
          <h1 className="text-balance mb-6">
            Welcome to Arist<span className="text-yellow">AI</span>
          </h1>
          <p className="text-lg max-w-2xl mb-8" style={{ color: 'var(--text-secondary)', lineHeight: 1.7 }}>
            An AI-powered platform for synchronous classroom discussions. Create engaging case-based learning experiences with real-time AI assistance, voice control, and comprehensive analytics.
          </p>
          <div className="flex flex-wrap gap-4">
            <Link href="/courses" className="btn-primary-ebook gap-2">
              <Play className="w-4 h-4" />
              Get Started
            </Link>
            <a href="#voice-commands" className="btn-secondary-ebook gap-2">
              <Mic className="w-4 h-4" />
              Voice Commands
            </a>
          </div>
        </div>
      </section>

      {/* Platform Overview */}
      <section className="container-ebook mb-16">
        <p className="section-label mb-3">Overview</p>
        <h2 className="mb-4">What You Can Do</h2>
        <p className="mb-8 max-w-2xl" style={{ color: 'var(--text-secondary)' }}>
          AristAI provides everything you need to run engaging, discussion-based classes with AI-powered support.
        </p>

        <div className="grid-3-col">
          {platformFeatures
            .filter(f => f.forRole === 'all' || (showInstructorContent && f.forRole === 'instructor'))
            .map((feature, idx) => (
              <div key={idx} className="card-ebook card-hover">
                <div className="icon-box mb-4">
                  <feature.icon className="text-yellow" />
                </div>
                <h4 className="mb-2">{feature.title}</h4>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                  {feature.description}
                </p>
              </div>
            ))}
        </div>
      </section>

      {/* Quick Start Guide */}
      <section className="bg-section-alt -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8 py-16 mb-16">
        <div className="container-ebook">
          <p className="section-label mb-3">Quick Start</p>
          <h2 className="mb-4">
            {showInstructorContent ? 'Instructor Workflow' : 'Student Workflow'}
          </h2>
          <p className="mb-10 max-w-2xl" style={{ color: 'var(--text-secondary)' }}>
            {showInstructorContent
              ? 'Follow these steps to create your first course and run a live discussion session.'
              : 'Follow these steps to join a course and participate in discussions.'}
          </p>

          <div className="step-counter space-y-6">
            {steps.map((step, idx) => (
              <div key={idx} className="step-item flex gap-5">
                <div className="flex-1 accent-bar">
                  <h4 className="mb-1">{step.title}</h4>
                  <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    {step.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Voice Commands Section */}
      <section id="voice-commands" className="container-ebook mb-16 scroll-mt-8">
        <div className="grid-2-col items-start mb-10">
          <div>
            <p className="section-label mb-3">Voice Control</p>
            <h2 className="mb-4">Hands-Free Operation</h2>
            <p style={{ color: 'var(--text-secondary)' }}>
              Control the entire platform using natural language. Click the microphone button to activate voice mode, then speak your commands naturally.
            </p>
          </div>
          <div className="card-ebook" style={{ background: 'var(--yellow-bg)' }}>
            <div className="flex items-start gap-4">
              <div className="icon-box">
                <Volume2 className="text-yellow" />
              </div>
              <div>
                <h4 className="mb-2">How to Activate</h4>
                <ol className="text-sm space-y-2" style={{ color: 'var(--text-secondary)' }}>
                  <li className="flex gap-2">
                    <span className="check-dot"><Check /></span>
                    <span>Click the microphone icon in the bottom-right corner</span>
                  </li>
                  <li className="flex gap-2">
                    <span className="check-dot"><Check /></span>
                    <span>Wait for the "Listening" indicator</span>
                  </li>
                  <li className="flex gap-2">
                    <span className="check-dot"><Check /></span>
                    <span>Speak naturally - the AI understands context</span>
                  </li>
                </ol>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          {voiceCommandGroups
            .filter(group => {
              if (group.category === 'Instructor Console') return showInstructorContent;
              if (group.category === 'Course Management' && !showInstructorContent) {
                // Show limited commands for students
                return true;
              }
              return true;
            })
            .map((group, idx) => (
              <div key={idx} className="card-ebook">
                <div className="flex items-center gap-3 mb-4">
                  <div className="icon-box">
                    <group.icon className="text-yellow" />
                  </div>
                  <div>
                    <h4 className="mb-0">{group.category}</h4>
                    <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                      {group.description}
                    </p>
                  </div>
                </div>
                <div className="grid sm:grid-cols-2 gap-3">
                  {group.commands
                    .filter(cmd => {
                      // Filter instructor-only commands for students
                      if (!showInstructorContent) {
                        const instructorPhrases = ['Create a new course', 'Generate lesson', 'Go live', 'Complete session', 'Start copilot', 'Stop copilot', 'Create a poll', 'Post a case', 'Split into', 'Who should'];
                        return !instructorPhrases.some(p => cmd.phrase.includes(p));
                      }
                      return true;
                    })
                    .map((cmd, cmdIdx) => (
                      <div
                        key={cmdIdx}
                        className="flex items-start gap-3 p-3 rounded-lg"
                        style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)' }}
                      >
                        <Mic className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: 'var(--yellow)' }} />
                        <div>
                          <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                            "{cmd.phrase}"
                          </p>
                          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                            {cmd.action}
                          </p>
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            ))}
        </div>
      </section>

      {/* Tips Section */}
      {showInstructorContent && (
        <section className="bg-section-warm -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8 py-16 mb-16">
          <div className="container-ebook">
            <p className="section-label mb-3">Best Practices</p>
            <h2 className="mb-4">Teaching Tips</h2>
            <p className="mb-10 max-w-2xl" style={{ color: 'var(--text-secondary)' }}>
              Make the most of AristAI with these facilitation strategies.
            </p>

            <div className="grid-3-col">
              {[
                {
                  icon: Target,
                  title: 'Start with a Hook',
                  description: 'Post an intriguing case study that challenges assumptions and sparks immediate debate.',
                },
                {
                  icon: BarChart3,
                  title: 'Use Polls Strategically',
                  description: 'Check understanding before diving deeper. Polls reveal misconceptions you can address.',
                },
                {
                  icon: Users,
                  title: 'Balance Participation',
                  description: 'Use "Who should I call on?" to ensure quieter students have opportunities to contribute.',
                },
                {
                  icon: PenTool,
                  title: 'Highlight Excellence',
                  description: 'Pin and label outstanding posts. It encourages quality and shows what good looks like.',
                },
                {
                  icon: Sparkles,
                  title: 'Let AI Detect Confusion',
                  description: 'The Copilot monitors discussions and alerts you when students seem confused.',
                },
                {
                  icon: Clock,
                  title: 'Use Timers Effectively',
                  description: 'Set clear time limits for responses. It creates urgency and keeps discussions focused.',
                },
              ].map((tip, idx) => (
                <div key={idx} className="flex gap-4">
                  <div className="check-dot flex-shrink-0">
                    <tip.icon />
                  </div>
                  <div>
                    <h4 className="text-base mb-1">{tip.title}</h4>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                      {tip.description}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* FAQ Section */}
      <section className="container-ebook mb-16">
        <p className="section-label mb-3">FAQ</p>
        <h2 className="mb-8">Common Questions</h2>

        <div className="max-w-3xl">
          {faqItems.map((item, idx) => (
            <div
              key={idx}
              className={`faq-item ${openFaq === idx ? 'open' : ''}`}
            >
              <button
                className="faq-question"
                onClick={() => setOpenFaq(openFaq === idx ? null : idx)}
              >
                <span>{item.question}</span>
                <span className="faq-toggle">+</span>
              </button>
              <div className="faq-answer">
                <div className="faq-answer-inner">
                  {item.answer}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA Section */}
      <section className="container-ebook mb-8">
        <div
          className="card-ebook text-center py-12"
          style={{ background: 'var(--yellow-bg)' }}
        >
          <h2 className="mb-4">Ready to Get Started?</h2>
          <p className="mb-6 max-w-xl mx-auto" style={{ color: 'var(--text-secondary)' }}>
            {showInstructorContent
              ? 'Create your first course and experience AI-powered classroom discussions.'
              : 'Join a course and start participating in engaging discussions.'}
          </p>
          <Link href="/courses" className="btn-primary-ebook gap-2">
            {showInstructorContent ? 'Create Your First Course' : 'View Available Courses'}
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>
    </div>
  );
}
