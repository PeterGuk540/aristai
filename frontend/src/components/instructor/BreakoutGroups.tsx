'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Users, Plus, Trash2, RefreshCw } from 'lucide-react';
import { Button, Card, CardContent, CardHeader, CardTitle, Input } from '@/components/ui';
import type { BreakoutGroup } from '@/types';

interface BreakoutGroupsProps {
  sessionId: number;
  onGroupsChanged?: () => void;
}

export function BreakoutGroupsComponent({ sessionId, onGroupsChanged }: BreakoutGroupsProps) {
  const [groups, setGroups] = useState<BreakoutGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [numGroups, setNumGroups] = useState(4);
  const [error, setError] = useState<string | null>(null);

  const fetchGroups = async () => {
    try {
      const data = await api.getBreakoutGroups(sessionId);
      setGroups(data.groups || []);
      setError(null);
    } catch (err) {
      setError('Failed to load groups');
      console.error('Error fetching breakout groups:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGroups();
  }, [sessionId]);

  const handleCreateGroups = async () => {
    setCreating(true);
    try {
      await api.createBreakoutGroups(sessionId, numGroups);
      await fetchGroups();
      setShowCreateForm(false);
      onGroupsChanged?.();
    } catch (err) {
      setError('Failed to create groups');
      console.error('Error creating groups:', err);
    } finally {
      setCreating(false);
    }
  };

  const handleDissolveGroups = async () => {
    if (!confirm('Are you sure you want to dissolve all breakout groups?')) return;

    try {
      await api.dissolveBreakoutGroups(sessionId);
      setGroups([]);
      onGroupsChanged?.();
    } catch (err) {
      setError('Failed to dissolve groups');
      console.error('Error dissolving groups:', err);
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse p-4">
        <div className="h-6 bg-stone-200 dark:bg-stone-700 rounded w-1/3 mb-4"></div>
        <div className="grid grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 bg-stone-200 dark:bg-stone-700 rounded-xl"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-danger-700 bg-danger-50 dark:bg-danger-900/20 rounded-xl border border-danger-200 dark:border-danger-900/50">
        {error}
        <button onClick={fetchGroups} className="ml-2 underline">
          Retry
        </button>
      </div>
    );
  }

  // No groups - show create option
  if (groups.length === 0) {
    if (showCreateForm) {
      return (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="w-5 h-5 text-primary-600" />
              Create Breakout Groups
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-[0.08em] text-neutral-600 dark:text-neutral-400 mb-2">Number of Groups</label>
              <Input
                type="number"
                min={2}
                max={10}
                value={numGroups}
                onChange={(e) => setNumGroups(Number(e.target.value))}
                data-voice-id="num-breakout-groups"
              />
              <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                Students will be randomly distributed across groups
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                onClick={handleCreateGroups}
                disabled={creating}
                data-voice-id="create-breakout-groups"
                className="flex-1"
              >
                {creating ? 'Creating...' : 'Create Groups'}
              </Button>
              <Button
                onClick={() => setShowCreateForm(false)}
                variant="outline"
                data-voice-id="cancel-breakout-groups"
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
        data-voice-id="open-breakout-form"
        variant="outline"
        className="w-full justify-center"
      >
        <Plus className="w-5 h-5" />
        Create Breakout Groups
      </Button>
    );
  }

  // Display existing groups
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <Users className="w-5 h-5 text-primary-600" />
          Breakout Groups
        </CardTitle>
        <div className="flex gap-2">
          <button
            onClick={fetchGroups}
            className="p-1.5 hover:bg-stone-100 dark:hover:bg-stone-800 rounded-lg transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4 text-stone-500" />
          </button>
          <button
            onClick={handleDissolveGroups}
            data-voice-id="dissolve-breakout-groups"
            className="p-1.5 hover:bg-danger-100 dark:hover:bg-danger-900/30 rounded-lg transition-colors"
            title="Dissolve Groups"
          >
            <Trash2 className="w-4 h-4 text-danger-500" />
          </button>
        </div>
      </CardHeader>

      <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {groups.map((group) => (
          <div
            key={group.id}
            className="border border-stone-200 dark:border-stone-700 rounded-xl p-3 bg-stone-50 dark:bg-stone-900/30"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold text-neutral-900 dark:text-neutral-100">{group.name}</span>
              <span className="text-xs text-neutral-500 dark:text-neutral-400">
                {group.members?.length || 0} members
              </span>
            </div>
            <div className="space-y-1">
              {group.members?.map((member) => (
                <div
                  key={member.user_id}
                  className="text-sm px-2 py-1 bg-white dark:bg-stone-800 rounded-lg border border-stone-100 dark:border-stone-700"
                >
                  {member.name}
                </div>
              ))}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export default BreakoutGroupsComponent;
