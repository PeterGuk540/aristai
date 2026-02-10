'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Users, Plus, Trash2, RefreshCw, Shuffle } from 'lucide-react';
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
        <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
        <div className="grid grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
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
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Users className="w-5 h-5 text-primary-600" />
            Create Breakout Groups
          </h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Number of Groups</label>
              <input
                type="number"
                min={2}
                max={10}
                value={numGroups}
                onChange={(e) => setNumGroups(Number(e.target.value))}
                className="w-full p-2 border rounded"
              />
              <p className="text-xs text-gray-500 mt-1">
                Students will be randomly distributed across groups
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleCreateGroups}
                disabled={creating}
                className="flex-1 bg-primary-600 text-white py-2 px-4 rounded hover:bg-primary-700 disabled:opacity-50"
              >
                {creating ? 'Creating...' : 'Create Groups'}
              </button>
              <button
                onClick={() => setShowCreateForm(false)}
                className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      );
    }

    return (
      <button
        onClick={() => setShowCreateForm(true)}
        className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition w-full justify-center"
      >
        <Plus className="w-5 h-5" />
        Create Breakout Groups
      </button>
    );
  }

  // Display existing groups
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Users className="w-5 h-5 text-primary-600" />
          Breakout Groups
        </h3>
        <div className="flex gap-2">
          <button
            onClick={fetchGroups}
            className="p-1 hover:bg-gray-100 rounded"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4 text-gray-500" />
          </button>
          <button
            onClick={handleDissolveGroups}
            className="p-1 hover:bg-red-100 rounded"
            title="Dissolve Groups"
          >
            <Trash2 className="w-4 h-4 text-red-500" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {groups.map((group) => (
          <div
            key={group.id}
            className="border rounded-lg p-3 bg-gray-50 dark:bg-gray-700"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium">{group.name}</span>
              <span className="text-xs text-gray-500">
                {group.members?.length || 0} members
              </span>
            </div>
            <div className="space-y-1">
              {group.members?.map((member) => (
                <div
                  key={member.user_id}
                  className="text-sm px-2 py-1 bg-white dark:bg-gray-600 rounded"
                >
                  {member.name}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default BreakoutGroupsComponent;
