'use client';

import { X, CheckCircle, Zap } from 'lucide-react';
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
            {isStudent ? 'Welcome to AristAI!' : 'Voice Assistant Ready'}
          </h2>
          <button
            onClick={onComplete}
            className="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        <div className="space-y-4">
          {isStudent ? (
            <div className="text-center py-4">
              <div className="w-16 h-16 bg-primary-100 dark:bg-primary-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
                <Zap className="h-8 w-8 text-primary-600 dark:text-primary-400" />
              </div>
              <p className="text-gray-600 dark:text-gray-400">
                Welcome to AristAI! Your learning experience starts here.
              </p>
            </div>
          ) : (
            <>
              <div className="bg-green-50 dark:bg-green-900/30 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400 mt-0.5" />
                  <div>
                    <h3 className="font-medium text-green-900 dark:text-green-100">
                      ElevenLabs Voice Agent Enabled
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
                  <li>• Navigate to different sections using voice commands</li>
                  <li>• Get help with course management</li>
                  <li>• Ask questions about your sessions and reports</li>
                  <li>• Control the application hands-free</li>
                </ul>
              </div>
            </>
          )}
        </div>

        <div className="mt-6 flex justify-end">
          <button
            onClick={onComplete}
            className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors"
          >
            {isStudent ? 'Get Started' : 'Got it!'}
          </button>
        </div>
      </div>
    </div>
  );
}