'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Lightbulb, UserCheck, HelpCircle, TrendingUp, TrendingDown, RefreshCw } from 'lucide-react';
import type { FacilitationSuggestions, FacilitationSuggestion } from '@/types';

interface FacilitationPanelProps {
  sessionId: number;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

const priorityColors = {
  high: 'border-red-500 bg-red-50',
  medium: 'border-yellow-500 bg-yellow-50',
  low: 'border-blue-500 bg-blue-50',
};

const typeIcons = {
  reengagement: TrendingDown,
  call_on_student: UserCheck,
  address_questions: HelpCircle,
};

export function FacilitationPanel({ sessionId, autoRefresh = true, refreshInterval = 60000 }: FacilitationPanelProps) {
  const [suggestions, setSuggestions] = useState<FacilitationSuggestions | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSuggestions = async () => {
    try {
      const data = await api.getFacilitationSuggestions(sessionId);
      setSuggestions(data);
      setError(null);
    } catch (err) {
      setError('Failed to load suggestions');
      console.error('Error fetching facilitation suggestions:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSuggestions();

    if (autoRefresh) {
      const interval = setInterval(fetchSuggestions, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [sessionId, autoRefresh, refreshInterval]);

  if (loading) {
    return (
      <div className="animate-pulse p-4">
        <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 bg-gray-200 rounded"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-red-600 bg-red-50 rounded-lg">
        {error}
        <button onClick={fetchSuggestions} className="ml-2 underline">
          Retry
        </button>
      </div>
    );
  }

  if (!suggestions) return null;

  const MomentumIcon = suggestions.discussion_momentum === 'active' ? TrendingUp : TrendingDown;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Lightbulb className="w-5 h-5 text-yellow-500" />
          Facilitation Suggestions
        </h3>
        <button
          onClick={fetchSuggestions}
          className="p-1 hover:bg-gray-100 rounded"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4 text-gray-500" />
        </button>
      </div>

      {/* Momentum indicator */}
      <div className={cn(
        'flex items-center gap-2 p-2 rounded-lg mb-4',
        suggestions.discussion_momentum === 'active' ? 'bg-green-50' : 'bg-yellow-50'
      )}>
        <MomentumIcon className={cn(
          'w-5 h-5',
          suggestions.discussion_momentum === 'active' ? 'text-green-600' : 'text-yellow-600'
        )} />
        <span className="text-sm font-medium">
          Discussion is {suggestions.discussion_momentum}
        </span>
        <span className="text-xs text-gray-500 ml-auto">
          {suggestions.posts_per_minute} posts/min
        </span>
      </div>

      {/* Suggestions list */}
      {suggestions.suggestions.length === 0 ? (
        <div className="text-center py-4 text-gray-500">
          No specific suggestions right now. Discussion is flowing well!
        </div>
      ) : (
        <div className="space-y-3">
          {suggestions.suggestions.map((suggestion, index) => {
            const Icon = typeIcons[suggestion.type as keyof typeof typeIcons] || Lightbulb;
            return (
              <div
                key={index}
                className={cn(
                  'p-3 rounded-lg border-l-4',
                  priorityColors[suggestion.priority as keyof typeof priorityColors]
                )}
              >
                <div className="flex items-start gap-2">
                  <Icon className="w-5 h-5 mt-0.5 text-gray-600" />
                  <div className="flex-1">
                    <p className="text-sm">{suggestion.message}</p>
                    {suggestion.students && suggestion.students.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {suggestion.students.map((student) => (
                          <span
                            key={student.user_id}
                            className="px-2 py-1 text-xs bg-white rounded-full border"
                          >
                            {student.name} ({student.post_count} posts)
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <span className={cn(
                    'text-xs px-2 py-0.5 rounded-full',
                    suggestion.priority === 'high' ? 'bg-red-200 text-red-800' :
                    suggestion.priority === 'medium' ? 'bg-yellow-200 text-yellow-800' :
                    'bg-blue-200 text-blue-800'
                  )}>
                    {suggestion.priority}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Low participation count */}
      {suggestions.low_participation_count > 0 && (
        <div className="mt-4 pt-4 border-t text-sm text-gray-600">
          {suggestions.low_participation_count} students have low participation
        </div>
      )}
    </div>
  );
}

export default FacilitationPanel;
