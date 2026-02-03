'use client';

import { VoiceAssistant, VoiceHistory } from '@/components/voice';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui';
import { Mic, History, Info } from 'lucide-react';

interface VoiceTabContentProps {
  className?: string;
}

/**
 * Enhanced Voice Tab Content for the Console page
 * Replaces the existing basic voice implementation with the full-featured version
 */
export function VoiceTabContent({ className }: VoiceTabContentProps) {
  return (
    <div className={className}>
      {/* Info banner */}
      <Card className="mb-6 bg-gradient-to-r from-primary-50 to-blue-50 dark:from-primary-900/20 dark:to-blue-900/20 border-primary-200 dark:border-primary-800">
        <CardContent className="py-4">
          <div className="flex items-start gap-3">
            <Info className="h-5 w-5 text-primary-600 dark:text-primary-400 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="font-medium text-primary-900 dark:text-primary-100 mb-1">
                Voice-Enabled Teaching Assistant
              </h3>
              <p className="text-sm text-primary-700 dark:text-primary-300">
                Use voice commands to manage your courses, sessions, polls, and more. Try saying things like:
              </p>
              <ul className="text-sm text-primary-600 dark:text-primary-400 mt-2 space-y-1">
                <li>• "List all my courses"</li>
                <li>• "Start a live session for Introduction to AI"</li>
                <li>• "Create a poll asking students about their understanding"</li>
                <li>• "Show me the copilot suggestions for the current session"</li>
                <li>• "Generate a report for today's session"</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Voice Assistant */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mic className="h-5 w-5" />
                Voice Input
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <VoiceAssistant />
            </CardContent>
          </Card>
        </div>

        {/* History */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <History className="h-5 w-5" />
                Command History
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <VoiceHistory limit={20} />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Command Reference */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-base">Voice Command Reference</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            <CommandCategory
              title="Courses"
              commands={[
                'List all courses',
                'Show course [name]',
                'Create a new course called [name]',
                'Generate session plans for [course]',
              ]}
            />
            <CommandCategory
              title="Sessions"
              commands={[
                'List sessions for [course]',
                'Start session [name]',
                'End the current session',
                'What\'s the session status?',
              ]}
            />
            <CommandCategory
              title="Forum & Polls"
              commands={[
                'Show recent posts',
                'Create a poll: [question]',
                'Pin the last post',
                'Get poll results',
              ]}
            />
            <CommandCategory
              title="AI Copilot"
              commands={[
                'Start the copilot',
                'Stop the copilot',
                'Show copilot suggestions',
                'What are the confusion points?',
              ]}
            />
            <CommandCategory
              title="Reports"
              commands={[
                'Generate a report',
                'Show the session report',
                'Who participated today?',
                'What were the main themes?',
              ]}
            />
            <CommandCategory
              title="Enrollment"
              commands={[
                'List enrolled students',
                'Enroll [email] in [course]',
                'How many students are enrolled?',
                'Show enrollment stats',
              ]}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

interface CommandCategoryProps {
  title: string;
  commands: string[];
}

function CommandCategory({ title, commands }: CommandCategoryProps) {
  return (
    <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-3">
      <h4 className="font-medium text-gray-900 dark:text-white text-sm mb-2">{title}</h4>
      <ul className="text-xs text-gray-600 dark:text-gray-400 space-y-1">
        {commands.map((cmd, i) => (
          <li key={i} className="flex items-start gap-1.5">
            <span className="text-primary-500">›</span>
            <span>"{cmd}"</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
