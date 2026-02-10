'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { FileText, Send, CheckCircle, AlertTriangle, ListChecks, RefreshCw } from 'lucide-react';
import type { PostClassSummary } from '@/types';

interface PostClassSummaryProps {
  sessionId: number;
  onSummarySent?: () => void;
}

export function PostClassSummaryComponent({ sessionId, onSummarySent }: PostClassSummaryProps) {
  const [summary, setSummary] = useState<PostClassSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  const fetchSummary = async () => {
    try {
      const data = await api.getPostClassSummary(sessionId);
      setSummary(data);
      setError(null);
    } catch (err: any) {
      if (err.status === 404) {
        // No summary yet
        setSummary(null);
      } else {
        setError('Failed to load summary');
        console.error('Error fetching summary:', err);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, [sessionId]);

  const handleGenerateSummary = async () => {
    setGenerating(true);
    try {
      const data = await api.generateSessionSummary(sessionId);
      setSummary(data);
    } catch (err) {
      setError('Failed to generate summary');
      console.error('Error generating summary:', err);
    } finally {
      setGenerating(false);
    }
  };

  const handleSendToStudents = async () => {
    setSending(true);
    try {
      await api.sendSummaryToStudents(sessionId);
      setSent(true);
      onSummarySent?.();
    } catch (err) {
      setError('Failed to send summary');
      console.error('Error sending summary:', err);
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse p-4">
        <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
        <div className="h-32 bg-gray-200 rounded"></div>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div className="text-center py-8">
          <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-600 mb-2">No Summary Yet</h3>
          <p className="text-sm text-gray-500 mb-4">
            Generate a summary of this session to share with students
          </p>
          <button
            onClick={handleGenerateSummary}
            disabled={generating}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            {generating ? 'Generating...' : 'Generate Summary'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <FileText className="w-5 h-5 text-primary-600" />
          Session Summary
        </h3>
        <div className="flex gap-2">
          <button
            onClick={handleGenerateSummary}
            disabled={generating}
            className="p-1 hover:bg-gray-100 rounded"
            title="Regenerate"
          >
            <RefreshCw className={cn("w-4 h-4 text-gray-500", generating && "animate-spin")} />
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-2 bg-red-50 text-red-600 rounded text-sm">
          {error}
        </div>
      )}

      {/* Summary content */}
      <div className="prose prose-sm dark:prose-invert max-w-none mb-4">
        <div className="p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
          <p className="text-sm">{summary.summary_text}</p>
        </div>
      </div>

      {/* Key topics */}
      {summary.key_topics && summary.key_topics.length > 0 && (
        <div className="mb-4">
          <h4 className="text-sm font-medium text-gray-600 mb-2">Key Topics Covered</h4>
          <div className="flex flex-wrap gap-2">
            {summary.key_topics.map((topic, index) => (
              <span
                key={index}
                className="px-2 py-1 text-xs bg-primary-100 text-primary-800 rounded-full"
              >
                {topic}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Follow-up items */}
      {summary.follow_up_items && summary.follow_up_items.length > 0 && (
        <div className="mb-4">
          <h4 className="text-sm font-medium text-gray-600 mb-2 flex items-center gap-1">
            <ListChecks className="w-4 h-4" />
            Follow-up Items
          </h4>
          <ul className="space-y-1">
            {summary.follow_up_items.map((item, index) => (
              <li
                key={index}
                className="flex items-start gap-2 text-sm p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded"
              >
                <AlertTriangle className="w-4 h-4 text-yellow-500 mt-0.5 flex-shrink-0" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Participation stats */}
      {summary.participation_stats && (
        <div className="mb-4 grid grid-cols-3 gap-3">
          <div className="text-center p-2 bg-gray-50 dark:bg-gray-700 rounded">
            <div className="text-lg font-bold">{summary.participation_stats.total_posts}</div>
            <div className="text-xs text-gray-500">Total Posts</div>
          </div>
          <div className="text-center p-2 bg-gray-50 dark:bg-gray-700 rounded">
            <div className="text-lg font-bold">{summary.participation_stats.unique_participants}</div>
            <div className="text-xs text-gray-500">Participants</div>
          </div>
          <div className="text-center p-2 bg-gray-50 dark:bg-gray-700 rounded">
            <div className="text-lg font-bold">{summary.participation_stats.avg_engagement}%</div>
            <div className="text-xs text-gray-500">Avg Engagement</div>
          </div>
        </div>
      )}

      {/* Send to students */}
      <div className="pt-4 border-t">
        {sent ? (
          <div className="flex items-center justify-center gap-2 text-green-600">
            <CheckCircle className="w-5 h-5" />
            <span>Summary sent to students!</span>
          </div>
        ) : (
          <button
            onClick={handleSendToStudents}
            disabled={sending}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            <Send className="w-4 h-4" />
            {sending ? 'Sending...' : 'Send Summary to Students'}
          </button>
        )}
      </div>
    </div>
  );
}

export default PostClassSummaryComponent;
