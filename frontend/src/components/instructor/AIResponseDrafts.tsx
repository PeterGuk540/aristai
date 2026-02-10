'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Bot, Check, X, Edit, RefreshCw, MessageSquare } from 'lucide-react';
import type { AIResponseDraft } from '@/types';

interface AIResponseDraftsProps {
  sessionId: number;
  instructorId: number;
  autoRefresh?: boolean;
  refreshInterval?: number;
  onDraftActioned?: () => void;
}

export function AIResponseDraftsComponent({
  sessionId,
  instructorId,
  autoRefresh = true,
  refreshInterval = 30000,
  onDraftActioned
}: AIResponseDraftsProps) {
  const [drafts, setDrafts] = useState<AIResponseDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingDraft, setEditingDraft] = useState<number | null>(null);
  const [editedContent, setEditedContent] = useState('');

  const fetchDrafts = async () => {
    try {
      const data = await api.getPendingAIDrafts(sessionId);
      setDrafts(data.drafts || []);
      setError(null);
    } catch (err) {
      setError('Failed to load AI drafts');
      console.error('Error fetching AI drafts:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDrafts();

    if (autoRefresh) {
      const interval = setInterval(fetchDrafts, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [sessionId, autoRefresh, refreshInterval]);

  const handleApprove = async (draftId: number) => {
    try {
      await api.approveAIDraft(draftId, instructorId);
      setDrafts(drafts.filter(d => d.id !== draftId));
      onDraftActioned?.();
    } catch (err) {
      console.error('Error approving draft:', err);
    }
  };

  const handleReject = async (draftId: number) => {
    try {
      await api.rejectAIDraft(draftId, instructorId);
      setDrafts(drafts.filter(d => d.id !== draftId));
      onDraftActioned?.();
    } catch (err) {
      console.error('Error rejecting draft:', err);
    }
  };

  const handleEdit = (draft: AIResponseDraft) => {
    setEditingDraft(draft.id);
    setEditedContent(draft.draft_response);
  };

  const handleSaveEdit = async (draftId: number) => {
    try {
      await api.editAIDraft(draftId, editedContent);
      setDrafts(drafts.map(d =>
        d.id === draftId ? { ...d, draft_response: editedContent } : d
      ));
      setEditingDraft(null);
    } catch (err) {
      console.error('Error editing draft:', err);
    }
  };

  const handleCancelEdit = () => {
    setEditingDraft(null);
    setEditedContent('');
  };

  if (loading) {
    return (
      <div className="animate-pulse p-4">
        <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-24 bg-gray-200 rounded"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-red-600 bg-red-50 rounded-lg">
        {error}
        <button onClick={fetchDrafts} className="ml-2 underline">
          Retry
        </button>
      </div>
    );
  }

  if (drafts.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div className="text-center py-6">
          <Bot className="w-10 h-10 text-gray-300 mx-auto mb-2" />
          <p className="text-sm text-gray-500">No pending AI drafts</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Bot className="w-5 h-5 text-primary-600" />
          AI Response Drafts
          <span className="px-2 py-0.5 text-xs bg-primary-100 text-primary-800 rounded-full">
            {drafts.length}
          </span>
        </h3>
        <button
          onClick={fetchDrafts}
          className="p-1 hover:bg-gray-100 rounded"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4 text-gray-500" />
        </button>
      </div>

      <div className="space-y-4">
        {drafts.map((draft) => (
          <div
            key={draft.id}
            className="border rounded-lg overflow-hidden"
          >
            {/* Original question */}
            <div className="p-3 bg-gray-50 dark:bg-gray-700 border-b">
              <div className="flex items-start gap-2">
                <MessageSquare className="w-4 h-4 text-gray-400 mt-1 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium">{draft.student_name}</p>
                  <p className="text-sm text-gray-600 dark:text-gray-300">
                    {draft.original_question}
                  </p>
                </div>
              </div>
            </div>

            {/* AI draft response */}
            <div className="p-3">
              {editingDraft === draft.id ? (
                <div className="space-y-2">
                  <textarea
                    value={editedContent}
                    onChange={(e) => setEditedContent(e.target.value)}
                    className="w-full p-2 border rounded text-sm min-h-[100px]"
                    placeholder="Edit the AI response..."
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleSaveEdit(draft.id)}
                      className="px-3 py-1 text-sm bg-primary-600 text-white rounded hover:bg-primary-700"
                    >
                      Save
                    </button>
                    <button
                      onClick={handleCancelEdit}
                      className="px-3 py-1 text-sm text-gray-600 hover:bg-gray-100 rounded"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex items-start gap-2 mb-3">
                    <Bot className="w-4 h-4 text-primary-500 mt-1 flex-shrink-0" />
                    <p className="text-sm">{draft.draft_response}</p>
                  </div>

                  {/* Action buttons */}
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleApprove(draft.id)}
                      className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 text-sm bg-green-100 text-green-700 rounded hover:bg-green-200"
                    >
                      <Check className="w-4 h-4" />
                      Approve
                    </button>
                    <button
                      onClick={() => handleEdit(draft)}
                      className="flex items-center justify-center gap-1 px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                    >
                      <Edit className="w-4 h-4" />
                      Edit
                    </button>
                    <button
                      onClick={() => handleReject(draft.id)}
                      className="flex items-center justify-center gap-1 px-3 py-1.5 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200"
                    >
                      <X className="w-4 h-4" />
                      Reject
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default AIResponseDraftsComponent;
