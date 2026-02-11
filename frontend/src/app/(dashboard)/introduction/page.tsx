'use client';

import { useState } from 'react';
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
  Play,
  ChevronRight,
  GraduationCap,
  Lightbulb,
  Volume2,
  Check,
} from 'lucide-react';
import { useTranslations } from 'next-intl';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  Badge,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from '@/components/ui';
import { useUser } from '@/lib/context';

interface VoiceCommand {
  command: string;
  description: string;
  category: 'navigation' | 'forum' | 'session' | 'console' | 'reports';
}

const voiceCommands: VoiceCommand[] = [
  // Navigation
  { command: "Go to courses", description: "Navigate to the Courses page", category: 'navigation' },
  { command: "Go to sessions", description: "Navigate to the Sessions page", category: 'navigation' },
  { command: "Go to forum", description: "Navigate to the Discussion Forum", category: 'navigation' },
  { command: "Go to console", description: "Navigate to the Instructor Console", category: 'navigation' },
  { command: "Go to reports", description: "Navigate to the Reports page", category: 'navigation' },
  { command: "Switch to dark mode", description: "Toggle dark mode theme", category: 'navigation' },

  // Forum
  { command: "Show cases", description: "Switch to the Cases tab in Forum", category: 'forum' },
  { command: "Show discussion", description: "Switch to the Discussion tab", category: 'forum' },
  { command: "Post my response", description: "Submit your written response", category: 'forum' },
  { command: "Refresh the discussion", description: "Reload the latest posts", category: 'forum' },

  // Session Management
  { command: "Create new session", description: "Open the create session form", category: 'session' },
  { command: "Go live", description: "Set session status to live", category: 'session' },
  { command: "Complete session", description: "Mark session as completed", category: 'session' },
  { command: "Generate plans", description: "Generate AI lesson plans for a course", category: 'session' },

  // Console (Instructor)
  { command: "Start copilot", description: "Activate the AI teaching assistant", category: 'console' },
  { command: "Stop copilot", description: "Deactivate the AI copilot", category: 'console' },
  { command: "Create a poll", description: "Open poll creation form", category: 'console' },
  { command: "Post a case study", description: "Post a new case for discussion", category: 'console' },
  { command: "Show engagement heatmap", description: "View student engagement visualization", category: 'console' },
  { command: "Start a 5 minute timer", description: "Start a countdown timer", category: 'console' },
  { command: "Split into 4 groups", description: "Create breakout groups", category: 'console' },
  { command: "Who should I call on?", description: "Get facilitation suggestions", category: 'console' },

  // Reports
  { command: "Generate report", description: "Generate a session report", category: 'reports' },
  { command: "Show analytics", description: "View course analytics", category: 'reports' },
  { command: "Compare sessions", description: "Compare multiple sessions", category: 'reports' },
  { command: "How has Maria been doing?", description: "Get individual student progress", category: 'reports' },
];

const categoryIcons: Record<string, any> = {
  navigation: ChevronRight,
  forum: MessageSquare,
  session: Calendar,
  console: Settings,
  reports: BarChart3,
};

const categoryColors: Record<string, string> = {
  navigation: 'bg-primary-100 dark:bg-primary-900/50 text-primary-600 dark:text-primary-400',
  forum: 'bg-accent-100 dark:bg-accent-900/50 text-accent-600 dark:text-accent-400',
  session: 'bg-success-100 dark:bg-success-900/50 text-success-600 dark:text-success-400',
  console: 'bg-info-100 dark:bg-info-900/50 text-info-600 dark:text-info-400',
  reports: 'bg-warning-100 dark:bg-warning-900/50 text-warning-600 dark:text-warning-400',
};

export default function IntroductionPage() {
  const { isInstructor, isAdmin } = useUser();
  const t = useTranslations();
  const [activeTab, setActiveTab] = useState('overview');

  const features = [
    {
      icon: BookOpen,
      title: 'Course Management',
      description: 'Create and manage courses with AI-generated lesson plans and learning objectives.',
      forInstructor: true,
    },
    {
      icon: Calendar,
      title: 'Session Planning',
      description: 'Organize live discussion sessions with structured topics and case studies.',
      forInstructor: true,
    },
    {
      icon: MessageSquare,
      title: 'Live Discussion Forum',
      description: 'Engage in real-time discussions with threaded replies and instructor moderation.',
      forInstructor: false,
    },
    {
      icon: Sparkles,
      title: 'AI Copilot',
      description: 'Get real-time teaching assistance with confusion detection and suggested prompts.',
      forInstructor: true,
    },
    {
      icon: BarChart3,
      title: 'Reports & Analytics',
      description: 'View participation metrics, answer scores, and learning objective alignment.',
      forInstructor: false,
    },
    {
      icon: Mic,
      title: 'Voice Commands',
      description: 'Control the platform hands-free using natural language voice commands.',
      forInstructor: false,
    },
  ];

  const quickStart = [
    {
      step: 1,
      title: isInstructor ? 'Create a Course' : 'Join a Course',
      description: isInstructor
        ? 'Go to Courses and create a new course with a syllabus. AI will extract learning objectives automatically.'
        : 'Get a join code from your instructor and enter it in the Courses page to enroll.',
    },
    {
      step: 2,
      title: isInstructor ? 'Generate Session Plans' : 'View Sessions',
      description: isInstructor
        ? 'Click "Generate Plans" to create AI-powered session plans with topics, cases, and discussion prompts.'
        : 'Check the Sessions page to see upcoming and live discussion sessions.',
    },
    {
      step: 3,
      title: isInstructor ? 'Go Live' : 'Join the Discussion',
      description: isInstructor
        ? 'Set a session to "Live" to open the discussion forum. Use the Console for real-time tools.'
        : 'When a session is live, go to Forum to view cases and post your responses.',
    },
    {
      step: 4,
      title: 'Review & Learn',
      description: isInstructor
        ? 'After the session, generate reports to see participation, scores, and themes.'
        : 'Check Reports to see your performance, feedback, and the best practice answer.',
    },
  ];

  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary-700 to-primary-900 p-8 lg:p-12">
        <div className="absolute top-0 right-0 w-64 h-64 bg-accent-400/20 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
        <div className="relative">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 rounded-xl bg-white/10 backdrop-blur">
              <GraduationCap className="h-8 w-8 text-white" />
            </div>
            <Badge variant="accent" size="lg">AI-Powered Education</Badge>
          </div>
          <h1 className="text-3xl lg:text-4xl font-bold text-white mb-4">
            Welcome to AristAI
          </h1>
          <p className="text-lg text-primary-100 max-w-2xl mb-6">
            An AI-powered platform for synchronous classroom discussions. Engage students with
            case-based learning, real-time AI assistance, and comprehensive analytics.
          </p>
          <div className="flex flex-wrap gap-4">
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/10 backdrop-blur">
              <Mic className="h-5 w-5 text-accent-400" />
              <span className="text-white text-sm">Voice Controlled</span>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/10 backdrop-blur">
              <Sparkles className="h-5 w-5 text-accent-400" />
              <span className="text-white text-sm">AI-Assisted Teaching</span>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/10 backdrop-blur">
              <BarChart3 className="h-5 w-5 text-accent-400" />
              <span className="text-white text-sm">Rich Analytics</span>
            </div>
          </div>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview">
            <BookOpen className="h-4 w-4 mr-1.5" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="quickstart">
            <Play className="h-4 w-4 mr-1.5" />
            Quick Start
          </TabsTrigger>
          <TabsTrigger value="voice">
            <Mic className="h-4 w-4 mr-1.5" />
            Voice Commands
          </TabsTrigger>
          <TabsTrigger value="tips">
            <Lightbulb className="h-4 w-4 mr-1.5" />
            Tips
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, index) => (
              <Card key={index} variant="default" hover>
                <CardContent className="p-6">
                  <div className="flex items-start gap-4">
                    <div className="p-3 rounded-xl bg-primary-100 dark:bg-primary-900/50">
                      <feature.icon className="h-6 w-6 text-primary-600 dark:text-primary-400" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="font-semibold text-neutral-900 dark:text-white">
                          {feature.title}
                        </h3>
                        {feature.forInstructor && (
                          <Badge variant="primary" size="sm">Instructor</Badge>
                        )}
                      </div>
                      <p className="text-sm text-neutral-600 dark:text-neutral-400">
                        {feature.description}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="quickstart">
          <Card variant="default">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-success-100 dark:bg-success-900/50">
                  <Play className="h-4 w-4 text-success-600 dark:text-success-400" />
                </div>
                Get Started in 4 Steps
              </CardTitle>
              <CardDescription>
                {isInstructor
                  ? 'Follow these steps to set up your first course and run a live discussion.'
                  : 'Follow these steps to join a course and participate in discussions.'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {quickStart.map((item, index) => (
                  <div key={index} className="flex gap-4">
                    <div className="flex-shrink-0">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center text-white font-bold">
                        {item.step}
                      </div>
                    </div>
                    <div className="flex-1 pb-6 border-l-2 border-neutral-200 dark:border-neutral-700 pl-6 -ml-5">
                      <h4 className="font-semibold text-neutral-900 dark:text-white mb-1">
                        {item.title}
                      </h4>
                      <p className="text-sm text-neutral-600 dark:text-neutral-400">
                        {item.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="voice">
          <div className="space-y-6">
            {/* Voice activation instructions */}
            <Card variant="ghost" padding="md" className="bg-accent-50 dark:bg-accent-900/20 border border-accent-200 dark:border-accent-800">
              <div className="flex items-start gap-4">
                <div className="p-3 rounded-xl bg-accent-100 dark:bg-accent-800/50">
                  <Volume2 className="h-6 w-6 text-accent-600 dark:text-accent-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-accent-900 dark:text-accent-100 mb-2">
                    How to Use Voice Commands
                  </h3>
                  <ol className="text-sm text-accent-800 dark:text-accent-200 space-y-2 list-decimal list-inside">
                    <li>Click the microphone button in the top bar to start voice mode</li>
                    <li>Wait for the "Listening..." indicator</li>
                    <li>Speak your command naturally - the AI understands context</li>
                    <li>Commands work across all pages for seamless navigation</li>
                  </ol>
                </div>
              </div>
            </Card>

            {/* Voice commands by category */}
            {['navigation', 'forum', 'session', 'console', 'reports'].map((category) => {
              const categoryCommands = voiceCommands.filter(cmd => cmd.category === category);
              const Icon = categoryIcons[category];

              // Only show instructor categories to instructors
              if ((category === 'console' || category === 'session') && !isInstructor && !isAdmin) {
                return null;
              }

              return (
                <Card key={category} variant="default">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 capitalize">
                      <div className={`p-1.5 rounded-lg ${categoryColors[category]}`}>
                        <Icon className="h-4 w-4" />
                      </div>
                      {category} Commands
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid sm:grid-cols-2 gap-3">
                      {categoryCommands.map((cmd, index) => (
                        <div
                          key={index}
                          className="flex items-start gap-3 p-3 rounded-xl bg-neutral-50 dark:bg-neutral-800/50 border border-neutral-200 dark:border-neutral-700"
                        >
                          <div className="p-1.5 rounded-lg bg-white dark:bg-neutral-700 shadow-soft">
                            <Mic className="h-4 w-4 text-primary-600 dark:text-primary-400" />
                          </div>
                          <div>
                            <p className="font-medium text-neutral-900 dark:text-white text-sm">
                              "{cmd.command}"
                            </p>
                            <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
                              {cmd.description}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </TabsContent>

        <TabsContent value="tips">
          <div className="grid md:grid-cols-2 gap-6">
            <Card variant="default">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-success-100 dark:bg-success-900/50">
                    <Check className="h-4 w-4 text-success-600 dark:text-success-400" />
                  </div>
                  Best Practices
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-3">
                  {[
                    'Paste your syllabus when creating a course - AI will extract learning objectives',
                    'Use the AI Copilot during live sessions to spot confusion points',
                    'Pin important student posts to highlight key insights',
                    'Label posts to help organize the discussion (insightful, question, etc.)',
                    'Generate reports after each session to track progress',
                    'Use voice commands for hands-free classroom control',
                  ].map((tip, index) => (
                    <li key={index} className="flex items-start gap-2 text-sm">
                      <ChevronRight className="h-4 w-4 text-success-500 mt-0.5 flex-shrink-0" />
                      <span className="text-neutral-600 dark:text-neutral-400">{tip}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>

            <Card variant="default">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-info-100 dark:bg-info-900/50">
                    <Lightbulb className="h-4 w-4 text-info-600 dark:text-info-400" />
                  </div>
                  Pro Tips
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-3">
                  {[
                    'The AI can suggest polls based on discussion confusion - just ask!',
                    'Use breakout groups for small-group discussions, then bring everyone back',
                    'Check the engagement heatmap to see who needs more participation',
                    'The session timer helps keep discussions on track',
                    'Review AI response drafts before posting to maintain your voice',
                    'Dark mode is easier on the eyes for longer sessions',
                  ].map((tip, index) => (
                    <li key={index} className="flex items-start gap-2 text-sm">
                      <Sparkles className="h-4 w-4 text-info-500 mt-0.5 flex-shrink-0" />
                      <span className="text-neutral-600 dark:text-neutral-400">{tip}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>

            {isInstructor && (
              <Card variant="default" className="md:col-span-2">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <div className="p-1.5 rounded-lg bg-accent-100 dark:bg-accent-900/50">
                      <Users className="h-4 w-4 text-accent-600 dark:text-accent-400" />
                    </div>
                    Student Engagement Tips
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid sm:grid-cols-2 gap-4">
                    {[
                      { title: 'Start with a Hook', desc: 'Post an intriguing case study to spark discussion' },
                      { title: 'Use Polls Strategically', desc: 'Check understanding before diving deeper' },
                      { title: 'Call on Quiet Students', desc: 'Use facilitation suggestions to include everyone' },
                      { title: 'Highlight Good Responses', desc: 'Pin and label excellent contributions' },
                      { title: 'Address Misconceptions', desc: 'Let AI help identify and correct confusion' },
                      { title: 'Summarize Key Points', desc: 'Use post-class summaries to reinforce learning' },
                    ].map((item, index) => (
                      <div key={index} className="p-4 rounded-xl bg-neutral-50 dark:bg-neutral-800/50 border border-neutral-200 dark:border-neutral-700">
                        <h4 className="font-medium text-neutral-900 dark:text-white text-sm mb-1">
                          {item.title}
                        </h4>
                        <p className="text-xs text-neutral-500 dark:text-neutral-400">
                          {item.desc}
                        </p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
