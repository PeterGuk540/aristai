'use client';

import { useState } from 'react';
import { Mic, X, History, Maximize2, Minimize2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { VoiceAssistant } from './VoiceAssistant';
import { VoiceHistory } from './VoiceHistory';

interface VoiceFabProps {
  className?: string;
  position?: 'bottom-right' | 'bottom-left' | 'top-right' | 'top-left';
}

const positionClasses = {
  'bottom-right': 'bottom-4 right-4',
  'bottom-left': 'bottom-4 left-4',
  'top-right': 'top-4 right-4',
  'top-left': 'top-4 left-4',
};

export function VoiceFab({ className, position = 'bottom-right' }: VoiceFabProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className={cn('fixed z-50', positionClasses[position], className)}>
      {/* Expanded panel */}
      {isOpen && (
        <div
          className={cn(
            'absolute mb-4 bg-white dark:bg-gray-800 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden transition-all',
            position.includes('right') ? 'right-0' : 'left-0',
            position.includes('bottom') ? 'bottom-full' : 'top-full mt-4',
            isExpanded ? 'w-[480px]' : 'w-80'
          )}
        >
          {/* Panel header */}
          <div className="flex items-center justify-between px-4 py-2 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Voice Assistant
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setShowHistory(!showHistory)}
                className={cn(
                  'p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors',
                  showHistory && 'bg-gray-200 dark:bg-gray-700'
                )}
                title="History"
              >
                <History className="h-4 w-4" />
              </button>
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                title={isExpanded ? 'Collapse' : 'Expand'}
              >
                {isExpanded ? (
                  <Minimize2 className="h-4 w-4" />
                ) : (
                  <Maximize2 className="h-4 w-4" />
                )}
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                title="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Content */}
          <div className={cn(
            'flex',
            isExpanded ? 'flex-row' : 'flex-col'
          )}>
            {/* Voice Assistant */}
            <div className={cn(
              isExpanded && showHistory ? 'w-1/2 border-r border-gray-200 dark:border-gray-700' : 'w-full'
            )}>
              <VoiceAssistant compact={false} />
            </div>

            {/* History panel */}
            {showHistory && (
              <div className={cn(
                'bg-gray-50 dark:bg-gray-900',
                isExpanded ? 'w-1/2' : 'w-full border-t border-gray-200 dark:border-gray-700'
              )}>
                <VoiceHistory limit={10} />
              </div>
            )}
          </div>
        </div>
      )}

      {/* FAB button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'p-4 rounded-full shadow-lg transition-all',
          'focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500',
          isOpen
            ? 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
            : 'bg-primary-600 hover:bg-primary-700 text-white'
        )}
      >
        {isOpen ? (
          <X className="h-6 w-6" />
        ) : (
          <Mic className="h-6 w-6" />
        )}
      </button>
    </div>
  );
}
