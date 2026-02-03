'use client';

import { useState, useEffect } from 'react';
import { RefreshCw, Clock, CheckCircle, XCircle, ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatTimestamp } from '@/lib/utils';
import { VoiceAuditEntry } from '@/types';
import { api } from '@/lib/api';
import { useUser } from '@/lib/context';

interface VoiceHistoryProps {
  className?: string;
  limit?: number;
}

export function VoiceHistory({ className, limit = 20 }: VoiceHistoryProps) {
  const { currentUser } = useUser();
  const [audits, setAudits] = useState<VoiceAuditEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const fetchAudits = async () => {
    if (!currentUser?.id) return;
    
    setLoading(true);
    setError('');
    
    try {
      const result = await api.voiceAudit(currentUser.id, 0, limit);
      setAudits(result.audits);
    } catch (err: any) {
      setError(err.message || 'Failed to load history');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAudits();
  }, [currentUser?.id, limit]);

  const toggleExpand = (id: number) => {
    setExpandedId(expandedId === id ? null : id);
  };

  if (loading && audits.length === 0) {
    return (
      <div className={cn('p-4 text-center text-gray-500', className)}>
        <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2" />
        Loading history...
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn('p-4 text-center text-red-500', className)}>
        <XCircle className="h-5 w-5 mx-auto mb-2" />
        {error}
        <button
          onClick={fetchAudits}
          className="block mx-auto mt-2 text-sm text-primary-600 hover:underline"
        >
          Try again
        </button>
      </div>
    );
  }

  if (audits.length === 0) {
    return (
      <div className={cn('p-4 text-center text-gray-500', className)}>
        <Clock className="h-8 w-8 mx-auto mb-2 text-gray-300" />
        <p>No voice history yet</p>
        <p className="text-xs mt-1">Your voice commands will appear here</p>
      </div>
    );
  }

  return (
    <div className={cn('', className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 dark:border-gray-700">
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Recent Commands ({audits.length})
        </span>
        <button
          onClick={fetchAudits}
          disabled={loading}
          className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
        >
          <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
        </button>
      </div>

      {/* List */}
      <div className="divide-y divide-gray-200 dark:divide-gray-700 max-h-96 overflow-auto">
        {audits.map((audit) => {
          const isExpanded = expandedId === audit.id;
          const successCount = audit.tool_calls?.filter(t => t.success).length || 0;
          const totalCount = audit.tool_calls?.length || 0;
          const allSuccess = successCount === totalCount && totalCount > 0;

          return (
            <div key={audit.id} className="bg-white dark:bg-gray-800">
              {/* Summary row */}
              <button
                onClick={() => toggleExpand(audit.id)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors text-left"
              >
                <div className="flex-shrink-0">
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4 text-gray-400" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-gray-400" />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                    {audit.plan_json?.intent || 'Unknown command'}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-gray-500">
                      {formatTimestamp(audit.created_at)}
                    </span>
                    <span className="text-xs text-gray-400">•</span>
                    <span className={cn(
                      'text-xs',
                      allSuccess ? 'text-green-600' : 'text-orange-600'
                    )}>
                      {successCount}/{totalCount} actions
                    </span>
                  </div>
                </div>

                <div className="flex-shrink-0">
                  {allSuccess ? (
                    <CheckCircle className="h-5 w-5 text-green-500" />
                  ) : totalCount > 0 ? (
                    <div className="h-5 w-5 rounded-full bg-orange-100 dark:bg-orange-900/30 flex items-center justify-center">
                      <span className="text-xs text-orange-600 font-medium">!</span>
                    </div>
                  ) : (
                    <div className="h-5 w-5 rounded-full bg-gray-100 dark:bg-gray-700" />
                  )}
                </div>
              </button>

              {/* Expanded details */}
              {isExpanded && (
                <div className="px-4 pb-4 pt-1 bg-gray-50 dark:bg-gray-900/50">
                  {/* Rationale */}
                  {audit.plan_json?.rationale && (
                    <div className="mb-3">
                      <p className="text-xs text-gray-500 mb-1">Reasoning:</p>
                      <p className="text-sm text-gray-700 dark:text-gray-300">
                        {audit.plan_json.rationale}
                      </p>
                    </div>
                  )}

                  {/* Tool calls */}
                  {audit.tool_calls && audit.tool_calls.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-500 mb-2">Actions performed:</p>
                      <div className="space-y-2">
                        {audit.tool_calls.map((call, idx) => (
                          <div
                            key={idx}
                            className={cn(
                              'p-2 rounded text-sm',
                              call.success
                                ? 'bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200'
                                : call.skipped
                                ? 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-200'
                                : 'bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200'
                            )}
                          >
                            <div className="flex items-center gap-2">
                              <span className="font-medium">{formatToolName(call.tool_name)}</span>
                              {call.success && <CheckCircle className="h-3 w-3" />}
                              {call.skipped && <span className="text-xs">(skipped)</span>}
                              {!call.success && !call.skipped && <XCircle className="h-3 w-3" />}
                            </div>
                            {call.error && (
                              <p className="text-xs mt-1 opacity-75">{call.error}</p>
                            )}
                            {call.skipped_reason && (
                              <p className="text-xs mt-1 opacity-75">{call.skipped_reason}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function formatToolName(name: string): string {
  return name
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}
