'use client';

import { X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { VoiceMode } from './VoiceAssistant';

interface VoiceSettingsProps {
  mode: VoiceMode;
  onModeChange: (mode: VoiceMode) => void;
  wakeWord: string;
  onWakeWordChange: (word: string) => void;
  autoConfirm: boolean;
  onAutoConfirmChange: (auto: boolean) => void;
  onClose: () => void;
  className?: string;
}

const modeDescriptions: Record<VoiceMode, string> = {
  'push-to-talk': 'Hold the button while speaking. Best for noisy environments.',
  'wake-word': 'Say the wake word to activate, then speak your command.',
  'continuous': 'Always listening. Good for hands-free operation.',
};

export function VoiceSettings({
  mode,
  onModeChange,
  wakeWord,
  onWakeWordChange,
  autoConfirm,
  onAutoConfirmChange,
  onClose,
  className,
}: VoiceSettingsProps) {
  return (
    <div className={cn(
      'border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900',
      className
    )}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 dark:border-gray-700">
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Settings</span>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="p-4 space-y-4">
        {/* Mode Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Interaction Mode
          </label>
          <div className="space-y-2">
            {(['push-to-talk', 'wake-word', 'continuous'] as VoiceMode[]).map((m) => (
              <label
                key={m}
                className={cn(
                  'flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-colors',
                  mode === m
                    ? 'bg-primary-50 dark:bg-primary-900/30 border border-primary-200 dark:border-primary-800'
                    : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
              >
                <input
                  type="radio"
                  name="voice-mode"
                  value={m}
                  checked={mode === m}
                  onChange={() => onModeChange(m)}
                  className="mt-1"
                />
                <div>
                  <span className="text-sm font-medium text-gray-900 dark:text-white capitalize">
                    {m.replace('-', ' ')}
                  </span>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    {modeDescriptions[m]}
                  </p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Wake Word (only shown for wake-word mode) */}
        {mode === 'wake-word' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Wake Word
            </label>
            <input
              type="text"
              value={wakeWord}
              onChange={(e) => onWakeWordChange(e.target.value)}
              placeholder="e.g., hey assistant"
              className={cn(
                'w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600',
                'bg-white dark:bg-gray-800 text-gray-900 dark:text-white',
                'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
                'text-sm'
              )}
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Say this phrase to activate voice input
            </p>
          </div>
        )}

        {/* Auto Confirm */}
        <div>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={autoConfirm}
              onChange={(e) => onAutoConfirmChange(e.target.checked)}
              className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            <div>
              <span className="text-sm font-medium text-gray-900 dark:text-white">
                Auto-confirm write operations
              </span>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Skip confirmation for actions that modify data
              </p>
            </div>
          </label>
          {autoConfirm && (
            <div className="mt-2 p-2 bg-orange-50 dark:bg-orange-900/20 rounded text-xs text-orange-700 dark:text-orange-300">
              ⚠️ Warning: Enabling this will execute write operations without confirmation
            </div>
          )}
        </div>

        {/* Voice Output */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Voice Output
          </label>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Voice responses use your browser's speech synthesis. Adjust volume using the mute button above.
          </p>
        </div>
      </div>
    </div>
  );
}
