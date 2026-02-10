'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { BookOpen, CheckCircle, XCircle, Clock, Users, RefreshCw } from 'lucide-react';
import type { PreClassInsights } from '@/types';

interface PreClassInsightsProps {
  sessionId: number;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

export function PreClassInsightsComponent({
  sessionId,
  autoRefresh = false,
  refreshInterval = 60000
}: PreClassInsightsProps) {
  const [insights, setInsights] = useState<PreClassInsights | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchInsights = async () => {
    try {
      const data = await api.getPreClassInsights(sessionId);
      setInsights(data);
      setError(null);
    } catch (err) {
      setError('Failed to load pre-class insights');
      console.error('Error fetching pre-class insights:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInsights();

    if (autoRefresh) {
      const interval = setInterval(fetchInsights, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [sessionId, autoRefresh, refreshInterval]);

  if (loading) {
    return (
      <div className="animate-pulse p-4">
        <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 bg-gray-200 rounded"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-red-600 bg-red-50 rounded-lg">
        {error}
        <button onClick={fetchInsights} className="ml-2 underline">
          Retry
        </button>
      </div>
    );
  }

  if (!insights) return null;

  const completionRate = insights.total_students > 0
    ? (insights.completed_count / insights.total_students * 100).toFixed(0)
    : 0;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-primary-600" />
          Pre-Class Preparation
        </h3>
        <button
          onClick={fetchInsights}
          className="p-1 hover:bg-gray-100 rounded"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4 text-gray-500" />
        </button>
      </div>

      {/* Completion overview */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-gray-600">Completion Rate</span>
          <span className="font-bold text-lg">{completionRate}%</span>
        </div>
        <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
          <div
            className={cn(
              'h-full transition-all',
              Number(completionRate) >= 80 ? 'bg-green-500' :
              Number(completionRate) >= 50 ? 'bg-yellow-500' : 'bg-red-500'
            )}
            style={{ width: `${completionRate}%` }}
          />
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="text-center p-2 bg-green-50 dark:bg-green-900/20 rounded">
          <CheckCircle className="w-5 h-5 text-green-500 mx-auto mb-1" />
          <div className="text-lg font-bold text-green-600">{insights.completed_count}</div>
          <div className="text-xs text-gray-500">Completed</div>
        </div>
        <div className="text-center p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded">
          <Clock className="w-5 h-5 text-yellow-500 mx-auto mb-1" />
          <div className="text-lg font-bold text-yellow-600">{insights.partial_count}</div>
          <div className="text-xs text-gray-500">Partial</div>
        </div>
        <div className="text-center p-2 bg-red-50 dark:bg-red-900/20 rounded">
          <XCircle className="w-5 h-5 text-red-500 mx-auto mb-1" />
          <div className="text-lg font-bold text-red-600">{insights.not_started_count}</div>
          <div className="text-xs text-gray-500">Not Started</div>
        </div>
      </div>

      {/* Checkpoints breakdown */}
      {insights.checkpoints && insights.checkpoints.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-600 mb-2">Checkpoints</h4>
          <div className="space-y-2">
            {insights.checkpoints.map((checkpoint) => (
              <div
                key={checkpoint.id}
                className="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-700 rounded"
              >
                <span className="text-sm">{checkpoint.title}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">
                    {checkpoint.completed_count}/{checkpoint.total_count}
                  </span>
                  <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary-500"
                      style={{
                        width: `${checkpoint.total_count > 0
                          ? (checkpoint.completed_count / checkpoint.total_count * 100)
                          : 0}%`
                      }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Students who haven't started */}
      {insights.students_not_started && insights.students_not_started.length > 0 && (
        <div className="mt-4 pt-4 border-t">
          <h4 className="text-sm font-medium text-gray-600 mb-2 flex items-center gap-1">
            <Users className="w-4 h-4" />
            Haven't Started ({insights.students_not_started.length})
          </h4>
          <div className="flex flex-wrap gap-1">
            {insights.students_not_started.slice(0, 10).map((student) => (
              <span
                key={student.user_id}
                className="px-2 py-1 text-xs bg-red-100 text-red-800 rounded-full"
              >
                {student.name}
              </span>
            ))}
            {insights.students_not_started.length > 10 && (
              <span className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded-full">
                +{insights.students_not_started.length - 10} more
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default PreClassInsightsComponent;
