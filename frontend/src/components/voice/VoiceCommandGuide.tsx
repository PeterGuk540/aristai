'use client';

import { useState } from 'react';
import { X, Mic, Navigation, Settings, FileText, MessageSquare, BarChart, Users, Play, CheckCircle, Moon, LogOut } from 'lucide-react';
import { cn } from '@/lib/utils';

interface VoiceCommandGuideProps {
  onClose: () => void;
}

interface CommandCategory {
  id: string;
  label: string;
  icon: React.ElementType;
  description: string;
  commands: {
    phrase: string;
    alternatives?: string[];
    description: string;
  }[];
}

const commandCategories: CommandCategory[] = [
  {
    id: 'navigation',
    label: 'Navigation',
    icon: Navigation,
    description: 'Navigate between pages',
    commands: [
      { phrase: '"Go to courses"', alternatives: ['"Open courses"', '"Courses page"'], description: 'Navigate to the Courses page' },
      { phrase: '"Go to sessions"', alternatives: ['"Open sessions"', '"Sessions page"'], description: 'Navigate to the Sessions page' },
      { phrase: '"Go to forum"', alternatives: ['"Open forum"', '"Forum page"'], description: 'Navigate to the Forum page' },
      { phrase: '"Go to console"', alternatives: ['"Open console"', '"Console page"'], description: 'Navigate to the Console page (instructors only)' },
      { phrase: '"Go to reports"', alternatives: ['"Open reports"', '"Reports page"'], description: 'Navigate to the Reports page' },
    ],
  },
  {
    id: 'courses',
    label: 'Courses Page',
    icon: FileText,
    description: 'Course management commands',
    commands: [
      { phrase: '"Create a course"', alternatives: ['"New course"', '"Make a course"'], description: 'Start the course creation form (voice will guide you through fields)' },
      { phrase: '"Select first course"', alternatives: ['"Choose first course"', '"Open first course"'], description: 'Select the first course in the list' },
      { phrase: '"Select [course name]"', alternatives: ['"Open [course name]"', '"Choose [course name]"'], description: 'Select a specific course by name' },
      { phrase: '"Yes" / "No"', description: 'When asked to generate plans after course creation, say Yes or No' },
    ],
  },
  {
    id: 'sessions',
    label: 'Sessions Page',
    icon: Play,
    description: 'Session management commands',
    commands: [
      { phrase: '"Go to manage status tab"', alternatives: ['"Manage status"', '"Status tab"'], description: 'Switch to the manage status tab' },
      { phrase: '"Go to create tab"', alternatives: ['"Create session tab"', '"New session"'], description: 'Switch to the create session tab' },
      { phrase: '"Select course"', alternatives: ['"Choose course"', '"Pick a course"'], description: 'Open the course dropdown' },
      { phrase: '"Select first"', alternatives: ['"Choose first"', '"First option"'], description: 'Select the first item in a dropdown' },
      { phrase: '"Select [name]"', alternatives: ['"Choose [name]"'], description: 'Select a specific item by name' },
      { phrase: '"Go live"', alternatives: ['"Start session"', '"Make it live"', '"Launch session"'], description: 'Set the session status to Live' },
      { phrase: '"Set to draft"', alternatives: ['"Make it draft"', '"Revert to draft"'], description: 'Set the session status to Draft' },
      { phrase: '"Complete"', alternatives: ['"End session"', '"Finish session"', '"Mark complete"'], description: 'Set the session status to Completed' },
      { phrase: '"Schedule"', alternatives: ['"Schedule session"', '"Set to scheduled"'], description: 'Set the session status to Scheduled' },
    ],
  },
  {
    id: 'forum',
    label: 'Forum Page',
    icon: MessageSquare,
    description: 'Forum and discussion commands',
    commands: [
      { phrase: '"Go to cases tab"', alternatives: ['"Cases"', '"Case studies"'], description: 'Switch to the Cases tab' },
      { phrase: '"Go to discussion tab"', alternatives: ['"Discussion"', '"Discussions"'], description: 'Switch to the Discussion tab' },
      { phrase: '"Select course"', alternatives: ['"Choose course"'], description: 'Open the course dropdown' },
      { phrase: '"Select session"', alternatives: ['"Choose session"'], description: 'Open the session dropdown' },
      { phrase: '"Select live session"', alternatives: ['"Choose live session"', '"Active session"'], description: 'Select only live sessions from dropdown' },
      { phrase: '"Post to discussion"', alternatives: ['"New post"', '"Create post"'], description: 'Start creating a new discussion post' },
      { phrase: '"Post a case"', alternatives: ['"Create case study"', '"New case"'], description: 'Start creating a new case study' },
    ],
  },
  {
    id: 'console',
    label: 'Console Page',
    icon: Settings,
    description: 'Console and copilot commands',
    commands: [
      { phrase: '"Go to copilot tab"', alternatives: ['"AI copilot"', '"Copilot"'], description: 'Switch to the AI Copilot tab' },
      { phrase: '"Go to polls tab"', alternatives: ['"Polls"', '"Poll tab"'], description: 'Switch to the Polls tab' },
      { phrase: '"Go to cases tab"', alternatives: ['"Post case"', '"Cases"'], description: 'Switch to the Post Case tab' },
      { phrase: '"Go to requests tab"', alternatives: ['"Instructor requests"', '"Requests"'], description: 'Switch to the Instructor Requests tab' },
      { phrase: '"Go to roster tab"', alternatives: ['"Roster"', '"Student roster"'], description: 'Switch to the Roster tab' },
      { phrase: '"Start copilot"', alternatives: ['"Activate copilot"', '"Turn on copilot"'], description: 'Start the AI Copilot monitoring' },
      { phrase: '"Stop copilot"', alternatives: ['"Deactivate copilot"', '"Turn off copilot"'], description: 'Stop the AI Copilot monitoring' },
      { phrase: '"Refresh interventions"', alternatives: ['"Update interventions"', '"Get interventions"'], description: 'Refresh the copilot suggestions' },
      { phrase: '"Create a poll"', alternatives: ['"New poll"', '"Make a poll"'], description: 'Start creating a new poll' },
    ],
  },
  {
    id: 'reports',
    label: 'Reports Page',
    icon: BarChart,
    description: 'Report commands',
    commands: [
      { phrase: '"Select course"', alternatives: ['"Choose course"'], description: 'Open the course dropdown' },
      { phrase: '"Select session"', alternatives: ['"Choose session"'], description: 'Open the session dropdown' },
      { phrase: '"Refresh report"', alternatives: ['"Reload report"', '"Update report"'], description: 'Refresh the current report' },
      { phrase: '"Regenerate report"', alternatives: ['"Generate new report"', '"Rebuild report"'], description: 'Regenerate the AI report' },
    ],
  },
  {
    id: 'dropdowns',
    label: 'Dropdown Selection',
    icon: Users,
    description: 'Select items from dropdowns',
    commands: [
      { phrase: '"Select first"', alternatives: ['"First option"', '"Choose first"'], description: 'Select the first item' },
      { phrase: '"Select second"', alternatives: ['"Second option"', '"Choose second"'], description: 'Select the second item' },
      { phrase: '"Select [name]"', alternatives: ['"Choose [name]"'], description: 'Select item by name' },
      { phrase: '"Cancel"', alternatives: ['"Never mind"', '"Go back"', '"Stop"'], description: 'Cancel the current selection' },
      { phrase: '"Skip"', alternatives: ['"Next"', '"Pass"'], description: 'Skip the current field' },
    ],
  },
  {
    id: 'forms',
    label: 'Form Filling',
    icon: CheckCircle,
    description: 'Fill out forms by voice',
    commands: [
      { phrase: '[Speak your answer]', description: 'Dictate text for the current form field' },
      { phrase: '"Yes"', alternatives: ['"Yeah"', '"Sure"', '"Okay"'], description: 'Confirm or agree to a prompt' },
      { phrase: '"No"', alternatives: ['"Nope"', '"No thanks"'], description: 'Decline or disagree' },
      { phrase: '"That\'s enough"', alternatives: ['"Done"', '"Finish"', '"No more"'], description: 'Stop adding more items (e.g., poll options)' },
      { phrase: '"Cancel"', alternatives: ['"Stop"', '"Abort"', '"Never mind"'], description: 'Cancel the current form' },
      { phrase: '"Submit"', alternatives: ['"Confirm"', '"Send"'], description: 'Submit the current form' },
    ],
  },
  {
    id: 'theme',
    label: 'Theme & Account',
    icon: Moon,
    description: 'Theme and account commands',
    commands: [
      { phrase: '"Dark mode"', alternatives: ['"Switch to dark"', '"Enable dark mode"'], description: 'Switch to dark theme' },
      { phrase: '"Light mode"', alternatives: ['"Switch to light"', '"Enable light mode"'], description: 'Switch to light theme' },
      { phrase: '"Toggle theme"', alternatives: ['"Change theme"', '"Switch theme"'], description: 'Toggle between light and dark' },
      { phrase: '"Open menu"', alternatives: ['"Account menu"', '"My account"'], description: 'Open the user dropdown menu' },
      { phrase: '"View voice guide"', alternatives: ['"Voice commands"', '"Show commands"'], description: 'Open this voice command guide' },
      { phrase: '"Forum instructions"', alternatives: ['"Platform guide"', '"How to use"'], description: 'Open the platform instructions' },
      { phrase: '"Sign out"', alternatives: ['"Log out"', '"Logout"'], description: 'Sign out of the application' },
    ],
  },
];

export function VoiceCommandGuide({ onClose }: VoiceCommandGuideProps) {
  const [activeCategory, setActiveCategory] = useState('navigation');
  const activeCommands = commandCategories.find(c => c.id === activeCategory);

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-primary-100 dark:bg-primary-900/30 rounded-full flex items-center justify-center">
              <Mic className="h-6 w-6 text-primary-600 dark:text-primary-400" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                Voice Command Guide
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Complete list of voice commands for AristAI
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
            data-voice-id="close-voice-guide"
          >
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar - Category List */}
          <div className="w-56 border-r border-gray-200 dark:border-gray-700 overflow-y-auto flex-shrink-0">
            <nav className="p-2">
              {commandCategories.map((category) => {
                const Icon = category.icon;
                return (
                  <button
                    key={category.id}
                    onClick={() => setActiveCategory(category.id)}
                    className={cn(
                      'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors text-left',
                      activeCategory === category.id
                        ? 'bg-primary-100 dark:bg-primary-900/50 text-primary-700 dark:text-primary-300'
                        : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                    )}
                  >
                    <Icon className="h-4 w-4 flex-shrink-0" />
                    <span className="truncate">{category.label}</span>
                  </button>
                );
              })}
            </nav>
          </div>

          {/* Main Content - Commands */}
          <div className="flex-1 overflow-y-auto p-6">
            {activeCommands && (
              <div>
                <div className="mb-4">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    {activeCommands.label}
                  </h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {activeCommands.description}
                  </p>
                </div>
                <div className="space-y-4">
                  {activeCommands.commands.map((cmd, index) => (
                    <div
                      key={index}
                      className="p-4 rounded-lg bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600"
                    >
                      <div className="flex flex-wrap items-start gap-2 mb-2">
                        <code className="px-3 py-1 bg-primary-100 dark:bg-primary-900/50 text-primary-700 dark:text-primary-300 rounded-md text-sm font-mono">
                          {cmd.phrase}
                        </code>
                        {cmd.alternatives && cmd.alternatives.map((alt, altIndex) => (
                          <code
                            key={altIndex}
                            className="px-2 py-1 bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300 rounded-md text-xs font-mono"
                          >
                            {alt}
                          </code>
                        ))}
                      </div>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        {cmd.description}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Tips Footer */}
        <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border-t border-gray-200 dark:border-gray-700">
          <div className="text-sm">
            <p className="font-medium text-blue-900 dark:text-blue-100 mb-1">Tips:</p>
            <ul className="text-blue-700 dark:text-blue-300 space-y-1">
              <li>- Speak naturally - the assistant understands conversational language</li>
              <li>- Wait for the assistant to finish speaking before giving the next command</li>
              <li>- Say "cancel" or "stop" to abort any ongoing operation</li>
              <li>- The voice controller is at the bottom-right corner of the screen</li>
            </ul>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
          <button
            onClick={onClose}
            className="px-6 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors"
          >
            Got It!
          </button>
        </div>
      </div>
    </div>
  );
}
