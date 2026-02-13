'use client';

import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Timer, Play, Pause, Square } from 'lucide-react';
import { Button, Card, CardContent, CardHeader, CardTitle, Input } from '@/components/ui';
import type { SessionTimer } from '@/types';

interface SessionTimerProps {
  sessionId: number;
  onTimerExpired?: () => void;
}

export function SessionTimerComponent({ sessionId, onTimerExpired }: SessionTimerProps) {
  const [timer, setTimer] = useState<SessionTimer | null>(null);
  const [localRemaining, setLocalRemaining] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newDuration, setNewDuration] = useState(5);
  const [newLabel, setNewLabel] = useState('Discussion');

  const fetchTimerStatus = useCallback(async () => {
    try {
      const data = await api.getTimerStatus(sessionId);
      if (data.active_timer) {
        setTimer(data.active_timer);
        setLocalRemaining(data.active_timer.remaining_seconds);
      } else {
        setTimer(null);
      }
    } catch (err) {
      console.error('Error fetching timer:', err);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    fetchTimerStatus();
    const pollInterval = setInterval(fetchTimerStatus, 10000); // Poll every 10s
    return () => clearInterval(pollInterval);
  }, [fetchTimerStatus]);

  // Local countdown
  useEffect(() => {
    if (!timer || timer.is_paused || timer.is_expired) return;

    const countdown = setInterval(() => {
      setLocalRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(countdown);
          onTimerExpired?.();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(countdown);
  }, [timer, onTimerExpired]);

  const handleStartTimer = async () => {
    try {
      await api.startTimer(sessionId, newDuration * 60, newLabel);
      setShowCreateForm(false);
      fetchTimerStatus();
    } catch (err) {
      console.error('Error starting timer:', err);
    }
  };

  const handlePause = async () => {
    if (!timer) return;
    try {
      await api.pauseTimer(timer.id);
      fetchTimerStatus();
    } catch (err) {
      console.error('Error pausing timer:', err);
    }
  };

  const handleResume = async () => {
    if (!timer) return;
    try {
      await api.resumeTimer(timer.id);
      fetchTimerStatus();
    } catch (err) {
      console.error('Error resuming timer:', err);
    }
  };

  const handleStop = async () => {
    if (!timer) return;
    try {
      await api.stopTimer(timer.id);
      setTimer(null);
    } catch (err) {
      console.error('Error stopping timer:', err);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (loading) {
    return (
      <div className="animate-pulse p-4 bg-stone-100 dark:bg-stone-900/40 rounded-xl border border-stone-200 dark:border-stone-700">
        <div className="h-6 bg-stone-200 dark:bg-stone-700 rounded w-24"></div>
      </div>
    );
  }

  // No active timer - show create button
  if (!timer) {
    if (showCreateForm) {
      return (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Timer className="w-5 h-5 text-primary-600" />
              Start Timer
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-[0.08em] text-neutral-600 dark:text-neutral-400 mb-2">Duration (minutes)</label>
              <Input
                type="number"
                min={1}
                max={60}
                value={newDuration}
                onChange={(e) => setNewDuration(Number(e.target.value))}
                data-voice-id="timer-duration-minutes"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-[0.08em] text-neutral-600 dark:text-neutral-400 mb-2">Label</label>
              <Input
                type="text"
                value={newLabel}
                onChange={(e) => setNewLabel(e.target.value)}
                placeholder="e.g., Group Discussion"
                data-voice-id="timer-label"
              />
            </div>
            <div className="flex gap-2">
              <Button
                onClick={handleStartTimer}
                data-voice-id="start-session-timer"
                className="flex-1"
              >
                Start
              </Button>
              <Button
                onClick={() => setShowCreateForm(false)}
                variant="outline"
                data-voice-id="cancel-session-timer"
              >
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      );
    }

    return (
      <Button
        onClick={() => setShowCreateForm(true)}
        data-voice-id="open-timer-form"
        variant="outline"
        className="w-full md:w-auto"
      >
        <Timer className="w-5 h-5" />
        Start Timer
      </Button>
    );
  }

  // Active timer display
  const progress = ((timer.duration_seconds - localRemaining) / timer.duration_seconds) * 100;
  const isLow = localRemaining <= 60;
  const isExpired = localRemaining <= 0;

  return (
    <div className={cn(
      'bg-white dark:bg-[#1a150c] rounded-xl border border-stone-200 dark:border-primary-900/20 shadow-sm p-4',
      isExpired && 'ring-2 ring-danger-500',
      isLow && !isExpired && 'ring-2 ring-warning-500'
    )}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-semibold text-stone-700 dark:text-stone-300">{timer.label}</span>
        <div className="flex gap-1">
          {timer.is_paused ? (
            <button
              onClick={handleResume}
              data-voice-id="resume-timer"
              className="p-1.5 hover:bg-stone-100 dark:hover:bg-stone-800 rounded-lg transition-colors"
              title="Resume"
            >
              <Play className="w-4 h-4 text-success-600" />
            </button>
          ) : (
            <button
              onClick={handlePause}
              data-voice-id="pause-timer"
              className="p-1.5 hover:bg-stone-100 dark:hover:bg-stone-800 rounded-lg transition-colors"
              title="Pause"
            >
              <Pause className="w-4 h-4 text-warning-600" />
            </button>
          )}
          <button
            onClick={handleStop}
            data-voice-id="stop-timer"
            className="p-1.5 hover:bg-stone-100 dark:hover:bg-stone-800 rounded-lg transition-colors"
            title="Stop"
          >
            <Square className="w-4 h-4 text-danger-600" />
          </button>
        </div>
      </div>

      <div className={cn(
        'text-4xl font-mono font-bold text-center',
        isExpired ? 'text-danger-600' : isLow ? 'text-warning-600' : 'text-stone-900 dark:text-white'
      )}>
        {isExpired ? "Time's up!" : formatTime(localRemaining)}
      </div>

      {/* Progress bar */}
      <div className="mt-3 h-2 bg-stone-200 dark:bg-stone-800 rounded-full overflow-hidden">
        <div
          className={cn(
            'h-full transition-all duration-1000',
            isExpired ? 'bg-danger-500' : isLow ? 'bg-warning-500' : 'bg-primary-500'
          )}
          style={{ width: `${Math.min(100, progress)}%` }}
        />
      </div>

      {timer.is_paused && (
        <div className="mt-2 text-center text-sm text-warning-600 font-semibold">
          PAUSED
        </div>
      )}
    </div>
  );
}

export default SessionTimerComponent;
