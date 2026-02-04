'use client';

import { X, CheckCircle, Zap, Mic } from 'lucide-react';
import { cn } from '@/lib/utils';

interface VoiceOnboardingProps {
  role: 'instructor' | 'admin' | 'student';
  userName: string;
  onComplete: () => void;
}

export function VoiceOnboarding({ role, userName, onComplete }: VoiceOnboardingProps) {
  const isStudent = role === 'student';

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-md w-full p-6">
        <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                Welcome to AristAI!
              </h2>
          <button
            onClick={onComplete}
            className="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        <div className="space-y-4">
          <div className="text-center py-4">
            <div className="w-20 h-20 bg-primary-100 dark:bg-primary-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
              <Mic className="h-10 w-10 text-primary-600 dark:text-primary-400" />
            </div>
          </div>
          
          <div className="bg-green-50 dark:bg-green-900/30 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400 mt-0.5" />
              <div>
                <h3 className="font-medium text-green-900 dark:text-green-100">
                  AristAI Voice Assistant Enabled
                </h3>
                <p className="text-sm text-green-700 dark:text-green-300 mt-1">
                  Your voice assistant is now ready! You can interact with it using natural voice commands.
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <h4 className="font-medium text-gray-900 dark:text-white">What you can do:</h4>
            <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-400">
              {isStudent ? (
                <>
                  <li>• Ask questions about your courses and materials</li>
                  <li>• Get help with assignments and learning</li>
                  <li>• Navigate to different sections</li>
                  <li>• Access course schedules and sessions</li>
                </>
              ) : (
                <>
                  <li>• Navigate to any section using voice commands</li>
                  <li>• Create courses, polls, and reports by voice</li>
                  <li>• Enroll students and manage classes</li>
                  <li>• Control the entire application hands-free</li>
                </>
              )}
            </ul>
          </div>

          <div className="text-center py-2">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              💡 Tip: Click the Help icon in the top-right menu anytime to review these instructions
            </p>
          </div>
        </div>

        <div className="mt-6 flex justify-end">
          <button
            onClick={onComplete}
            className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors"
          >
            Get Started
          </button>
        </div>
      </div>
    </div>
  );
}