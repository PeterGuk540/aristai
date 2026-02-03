'use client';

import { cn } from '@/lib/utils';

interface VoiceWaveformMiniProps {
  level: number;
  className?: string;
}

export function VoiceWaveformMini({ level, className }: VoiceWaveformMiniProps) {
  const bars = 5;
  
  return (
    <div className={cn('flex items-center gap-0.5 h-4', className)}>
      {Array.from({ length: bars }).map((_, i) => {
        // Create a wave pattern based on position and level
        const centerDistance = Math.abs(i - (bars - 1) / 2) / ((bars - 1) / 2);
        const baseHeight = 0.3 + (1 - centerDistance) * 0.7;
        const height = Math.max(0.2, baseHeight * (0.3 + level * 0.7));
        
        return (
          <div
            key={i}
            className="w-0.5 bg-white rounded-full transition-all duration-75"
            style={{
              height: `${height * 100}%`,
              opacity: 0.6 + level * 0.4,
            }}
          />
        );
      })}
    </div>
  );
}
