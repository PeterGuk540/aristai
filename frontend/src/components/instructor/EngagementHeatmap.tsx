'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Users, Activity, AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import type { EngagementHeatmap, StudentEngagement, EngagementLevel } from '@/types';

interface EngagementHeatmapProps {
  sessionId: number;
  autoRefresh?: boolean;
  refreshInterval?: number; // in milliseconds
}

const engagementColors: Record<EngagementLevel, string> = {
  highly_active: 'bg-green-500',
  active: 'bg-green-300',
  idle: 'bg-yellow-400',
  disengaged: 'bg-red-400',
  not_joined: 'bg-gray-300',
};

const engagementLabels: Record<EngagementLevel, string> = {
  highly_active: 'Highly Active',
  active: 'Active',
  idle: 'Idle',
  disengaged: 'Disengaged',
  not_joined: 'Not Joined',
};

export function EngagementHeatmapComponent({ sessionId, autoRefresh = true, refreshInterval = 30000 }: EngagementHeatmapProps) {
  const [heatmap, setHeatmap] = useState<EngagementHeatmap | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHeatmap = async () => {
    try {
      const data = await api.getEngagementHeatmap(sessionId);
      setHeatmap(data);
      setError(null);
    } catch (err) {
      setError('Failed to load engagement data');
      console.error('Error fetching heatmap:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHeatmap();

    if (autoRefresh) {
      const interval = setInterval(fetchHeatmap, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [sessionId, autoRefresh, refreshInterval]);

  if (loading) {
    return (
      <div className="animate-pulse p-4">
        <div className="h-8 bg-gray-200 rounded w-1/3 mb-4"></div>
        <div className="grid grid-cols-5 gap-2">
          {Array.from({ length: 20 }).map((_, i) => (
            <div key={i} className="h-12 bg-gray-200 rounded"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 text-red-600 rounded-lg">
        <AlertTriangle className="w-5 h-5 inline mr-2" />
        {error}
      </div>
    );
  }

  if (!heatmap) return null;

  const summary = heatmap.engagement_summary;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Activity className="w-5 h-5 text-primary-600" />
          Student Engagement
        </h3>
        <span className="text-sm text-gray-500">
          {heatmap.total_students} students
        </span>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-5 gap-2 mb-4">
        {(Object.keys(engagementLabels) as EngagementLevel[]).map((level) => (
          <div key={level} className="text-center p-2 rounded bg-gray-50 dark:bg-gray-700">
            <div className={cn('w-4 h-4 rounded-full mx-auto mb-1', engagementColors[level])} />
            <div className="text-xs text-gray-500">{engagementLabels[level]}</div>
            <div className="font-bold">{summary[level] || 0}</div>
          </div>
        ))}
      </div>

      {/* Student Grid */}
      <div className="grid grid-cols-8 gap-1">
        {heatmap.students.map((student) => (
          <div
            key={student.user_id}
            className={cn(
              'p-2 rounded cursor-pointer hover:ring-2 hover:ring-primary-500 transition-all',
              engagementColors[student.engagement_level as EngagementLevel]
            )}
            title={`${student.name} - ${engagementLabels[student.engagement_level as EngagementLevel]} (${student.post_count} posts)`}
          >
            <div className="text-xs font-medium truncate text-white drop-shadow">
              {student.name.split(' ')[0]}
            </div>
            <div className="text-xs text-white/80">
              {student.post_count} posts
            </div>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="mt-4 flex items-center justify-center gap-4 text-xs text-gray-500">
        <Clock className="w-4 h-4" />
        Last updated: {new Date(heatmap.timestamp).toLocaleTimeString()}
      </div>
    </div>
  );
}

export default EngagementHeatmapComponent;
