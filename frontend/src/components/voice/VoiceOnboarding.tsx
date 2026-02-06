'use client';

import { useState } from 'react';
import { X, Mic, Volume2, Navigation, Settings, MessageSquare, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';

interface VoiceOnboardingProps {
  role: 'instructor' | 'admin' | 'student';
  userName: string;
  onComplete: () => void;
}

const voiceCommandCategories = [
  {
    id: 'navigation',
    label: 'Navigation',
    icon: Navigation,
    commands: [
      { phrase: '"Go to courses"', description: 'Navigate to the Courses page' },
      { phrase: '"Go to sessions"', description: 'Navigate to the Sessions page' },
      { phrase: '"Go to forum"', description: 'Navigate to the Forum page' },
      { phrase: '"Go to console"', description: 'Navigate to the Console page' },
      { phrase: '"Go to reports"', description: 'Navigate to the Reports page' },
    ],
  },
  {
    id: 'tabs',
    label: 'Tab Switching',
    icon: Settings,
    commands: [
      { phrase: '"Go to AI Copilot"', description: 'Switch to the AI Copilot tab' },
      { phrase: '"Switch to polls"', description: 'Switch to the Polls tab' },
      { phrase: '"Open discussion tab"', description: 'Switch to the Discussion tab' },
      { phrase: '"Go to case studies"', description: 'Switch to the Case Studies tab' },
      { phrase: '"View roster"', description: 'Switch to the Roster tab' },
    ],
  },
  {
    id: 'actions',
    label: 'Actions',
    icon: MessageSquare,
    commands: [
      { phrase: '"Create a course"', description: 'Start creating a new course' },
      { phrase: '"Create a poll"', description: 'Start creating a new poll' },
      { phrase: '"Start copilot"', description: 'Activate the AI Copilot' },
      { phrase: '"Stop copilot"', description: 'Deactivate the AI Copilot' },
      { phrase: '"Post to discussion"', description: 'Start dictating a forum post' },
    ],
  },
  {
    id: 'forms',
    label: 'Form Filling',
    icon: FileText,
    commands: [
      { phrase: '"Select first course"', description: 'Select the first item in a dropdown' },
      { phrase: '"Choose [course name]"', description: 'Select a specific course by name' },
      { phrase: '"Yes" / "No"', description: 'Respond to yes/no questions (add options, confirm, etc.)' },
      { phrase: '"That\'s enough"', description: 'Finish adding options (polls, etc.)' },
      { phrase: '"Cancel"', description: 'Cancel the current operation' },
      { phrase: '"Submit"', description: 'Submit the current form' },
    ],
  },
];

export function VoiceOnboarding({ role, userName, onComplete }: VoiceOnboardingProps) {
  const [activeCategory, setActiveCategory] = useState('navigation');
  const activeCommands = voiceCommandCategories.find(c => c.id === activeCategory);

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-primary-100 dark:bg-primary-900/30 rounded-full flex items-center justify-center">
              <Mic className="h-6 w-6 text-primary-600 dark:text-primary-400" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                Voice Controller Guide
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Control AristAI hands-free with voice commands
              </p>
            </div>
          </div>
          <button
            onClick={onComplete}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        {/* Voice Controller Info */}
        <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border-b border-blue-100 dark:border-blue-800">
          <div className="flex items-start gap-3">
            <Volume2 className="h-5 w-5 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
            <div className="text-sm">
              <p className="font-medium text-blue-900 dark:text-blue-100">
                The voice controller is located at the bottom-right corner
              </p>
              <p className="text-blue-700 dark:text-blue-300 mt-1">
                Click the AristAI icon to expand it. The controller listens continuously and responds to your commands instantly.
              </p>
            </div>
          </div>
        </div>

        {/* Category Tabs */}
        <div className="flex border-b border-gray-200 dark:border-gray-700 px-4 overflow-x-auto">
          {voiceCommandCategories.map((category) => {
            const Icon = category.icon;
            return (
              <button
                key={category.id}
                onClick={() => setActiveCategory(category.id)}
                className={cn(
                  'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
                  activeCategory === category.id
                    ? 'border-primary-600 text-primary-600 dark:border-primary-400 dark:text-primary-400'
                    : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                )}
              >
                <Icon className="h-4 w-4" />
                <span>{category.label}</span>
              </button>
            );
          })}
        </div>

        {/* Commands List */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeCommands && (
            <div className="space-y-3">
              {activeCommands.commands.map((cmd, index) => (
                <div
                  key={index}
                  className="flex items-start gap-4 p-3 rounded-lg bg-gray-50 dark:bg-gray-700/50"
                >
                  <code className="flex-shrink-0 px-3 py-1 bg-primary-100 dark:bg-primary-900/50 text-primary-700 dark:text-primary-300 rounded-md text-sm font-mono">
                    {cmd.phrase}
                  </code>
                  <span className="text-sm text-gray-600 dark:text-gray-400 pt-1">
                    {cmd.description}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Tips Section */}
        <div className="p-4 bg-gray-50 dark:bg-gray-700/50 border-t border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            <p className="font-medium text-gray-900 dark:text-white mb-2">Tips:</p>
            <ul className="space-y-1">
              <li>• Speak naturally - the assistant understands conversational language</li>
              <li>• Wait for the assistant to finish speaking before giving the next command</li>
              <li>• Say "cancel" or "stop" to abort any ongoing operation</li>
              <li>• Access this guide anytime from the user menu → "View Voice Guide"</li>
            </ul>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
          <button
            onClick={onComplete}
            className="px-6 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors"
          >
            Got It!
          </button>
        </div>
      </div>
    </div>
  );
}
