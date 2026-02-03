'use client';

import { useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';
import { VoiceState } from './VoiceAssistant';
import { Mic, Loader2, Volume2, HelpCircle, AlertCircle } from 'lucide-react';

interface VoiceWaveformProps {
  isActive: boolean;
  audioLevel: number;
  state: VoiceState;
  className?: string;
}

export function VoiceWaveform({ isActive, audioLevel, state, className }: VoiceWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | null>(null);
  const barsRef = useRef<number[]>([]);

  // Initialize bars
  useEffect(() => {
    barsRef.current = Array(32).fill(0);
  }, []);

  // Animate waveform
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const animate = () => {
      const width = canvas.width;
      const height = canvas.height;
      const barCount = barsRef.current.length;
      const barWidth = width / barCount - 2;
      const maxBarHeight = height * 0.8;

      // Clear canvas
      ctx.clearRect(0, 0, width, height);

      // Update and draw bars
      barsRef.current = barsRef.current.map((bar, i) => {
        let targetHeight: number;

        if (isActive) {
          // Active listening - animate based on audio level with some randomness
          const centerDistance = Math.abs(i - barCount / 2) / (barCount / 2);
          const baseHeight = audioLevel * maxBarHeight * (1 - centerDistance * 0.5);
          targetHeight = baseHeight + Math.random() * maxBarHeight * 0.3 * audioLevel;
        } else if (state === 'processing') {
          // Processing - wave animation
          const time = Date.now() / 200;
          targetHeight = (Math.sin(time + i * 0.3) + 1) * 0.3 * maxBarHeight;
        } else if (state === 'speaking') {
          // Speaking - pulsing animation
          const time = Date.now() / 150;
          targetHeight = (Math.sin(time + i * 0.2) + 1) * 0.25 * maxBarHeight;
        } else {
          // Idle - minimal bars
          targetHeight = maxBarHeight * 0.05;
        }

        // Smooth transition
        const smoothedHeight = bar + (targetHeight - bar) * 0.3;
        
        // Get color based on state
        let color: string;
        if (isActive) {
          color = '#ef4444'; // red-500
        } else if (state === 'processing') {
          color = '#eab308'; // yellow-500
        } else if (state === 'speaking') {
          color = '#22c55e'; // green-500
        } else if (state === 'confirming') {
          color = '#3b82f6'; // blue-500
        } else if (state === 'error') {
          color = '#ef4444'; // red-500
        } else {
          color = '#6366f1'; // primary-500
        }

        // Draw bar
        const x = i * (barWidth + 2) + 1;
        const barHeight = Math.max(smoothedHeight, 2);
        const y = (height - barHeight) / 2;

        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.roundRect(x, y, barWidth, barHeight, 2);
        ctx.fill();

        return smoothedHeight;
      });

      animationRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isActive, audioLevel, state]);

  // Get center icon based on state
  const getCenterIcon = () => {
    switch (state) {
      case 'listening':
        return <Mic className="h-8 w-8 text-red-500 animate-pulse" />;
      case 'processing':
        return <Loader2 className="h-8 w-8 text-yellow-500 animate-spin" />;
      case 'speaking':
        return <Volume2 className="h-8 w-8 text-green-500" />;
      case 'confirming':
        return <HelpCircle className="h-8 w-8 text-blue-500" />;
      case 'error':
        return <AlertCircle className="h-8 w-8 text-red-500" />;
      default:
        return <Mic className="h-8 w-8 text-gray-400" />;
    }
  };

  // Get state message
  const getStateMessage = () => {
    switch (state) {
      case 'listening':
        return 'Listening...';
      case 'processing':
        return 'Processing your request...';
      case 'speaking':
        return 'Speaking...';
      case 'confirming':
        return 'Please confirm the action';
      case 'error':
        return 'An error occurred';
      default:
        return 'Ready to listen';
    }
  };

  return (
    <div className={cn('relative', className)}>
      {/* Waveform canvas */}
      <canvas
        ref={canvasRef}
        width={320}
        height={80}
        className="w-full h-20"
      />

      {/* Center overlay with icon */}
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <div className={cn(
          'p-3 rounded-full bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm shadow-lg',
          state === 'listening' && 'ring-4 ring-red-200 dark:ring-red-800',
          state === 'speaking' && 'ring-4 ring-green-200 dark:ring-green-800',
        )}>
          {getCenterIcon()}
        </div>
        <p className={cn(
          'mt-2 text-xs font-medium',
          state === 'listening' ? 'text-red-600' :
          state === 'processing' ? 'text-yellow-600' :
          state === 'speaking' ? 'text-green-600' :
          state === 'confirming' ? 'text-blue-600' :
          state === 'error' ? 'text-red-600' :
          'text-gray-500'
        )}>
          {getStateMessage()}
        </p>
      </div>
    </div>
  );
}
