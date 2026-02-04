'use client';

import { cn } from '@/lib/utils';

interface VoiceWaveformMiniProps {
  isActive?: boolean;
  className?: string;
}

export function VoiceWaveformMini({ isActive = false, className }: VoiceWaveformMiniProps) {
  return (
    <div className={cn('flex items-center gap-1', className)}>
      {[1, 2, 3, 4, 5].map((bar) => (
        <div
          key={bar}
          className={cn(
            'w-1 bg-primary-400 rounded-full transition-all duration-300',
            isActive ? 'animate-pulse' : 'opacity-30',
            isActive && bar === 3 && 'h-4',
            isActive && bar !== 3 && 'h-2',
            !isActive && 'h-2'
          )}
          style={{
            height: isActive ? `${Math.random() * 16 + 8}px` : '8px',
            animationDelay: isActive ? `${bar * 100}ms` : '0ms',
          }}
        />
      ))}
    </div>
  );
}