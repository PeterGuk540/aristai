'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { TrendingUp, TrendingDown, Minus, User, BarChart3, Search } from 'lucide-react';
import type { StudentProgress, StudentLookup } from '@/types';

interface StudentProgressProps {
  courseId: number;
}

export function StudentProgressComponent({ courseId }: StudentProgressProps) {
  const [progress, setProgress] = useState<StudentProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<StudentLookup[]>([]);
  const [selectedStudent, setSelectedStudent] = useState<StudentLookup | null>(null);
  const [searching, setSearching] = useState(false);

  const fetchProgress = async () => {
    try {
      const data = await api.getClassProgress(courseId);
      setProgress(data);
      setError(null);
    } catch (err) {
      setError('Failed to load progress data');
      console.error('Error fetching progress:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProgress();
  }, [courseId]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    setSearching(true);
    try {
      const results = await api.lookupStudent(courseId, searchQuery);
      setSearchResults(results.matches || []);
    } catch (err) {
      console.error('Error searching students:', err);
    } finally {
      setSearching(false);
    }
  };

  const handleSelectStudent = async (student: StudentLookup) => {
    setSelectedStudent(student);
    setSearchResults([]);
    setSearchQuery('');
  };

  const TrendIcon = ({ trend }: { trend: string }) => {
    if (trend === 'improving') return <TrendingUp className="w-4 h-4 text-green-500" />;
    if (trend === 'declining') return <TrendingDown className="w-4 h-4 text-red-500" />;
    return <Minus className="w-4 h-4 text-gray-400" />;
  };

  if (loading) {
    return (
      <div className="animate-pulse p-4">
        <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
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
        <button onClick={fetchProgress} className="ml-2 underline">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-primary-600" />
          Student Progress
        </h3>
      </div>

      {/* Search bar */}
      <div className="mb-4">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search for a student..."
              className="w-full p-2 pl-8 border rounded"
            />
            <Search className="w-4 h-4 text-gray-400 absolute left-2 top-3" />
          </div>
          <button
            onClick={handleSearch}
            disabled={searching}
            className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
          >
            {searching ? '...' : 'Search'}
          </button>
        </div>

        {/* Search results dropdown */}
        {searchResults.length > 0 && (
          <div className="mt-2 border rounded-lg bg-white shadow-lg max-h-48 overflow-y-auto">
            {searchResults.map((student) => (
              <button
                key={student.user_id}
                onClick={() => handleSelectStudent(student)}
                className="w-full text-left px-4 py-2 hover:bg-gray-100 flex items-center gap-2"
              >
                <User className="w-4 h-4 text-gray-400" />
                <span>{student.name}</span>
                <span className="text-xs text-gray-500 ml-auto">{student.email}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Selected student details */}
      {selectedStudent && (
        <div className="mb-4 p-4 bg-primary-50 dark:bg-primary-900/20 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <User className="w-5 h-5 text-primary-600" />
              <span className="font-medium">{selectedStudent.name}</span>
            </div>
            <button
              onClick={() => setSelectedStudent(null)}
              className="text-xs text-gray-500 hover:text-gray-700"
            >
              Clear
            </button>
          </div>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Total Posts:</span>
              <span className="ml-2 font-medium">{selectedStudent.total_posts}</span>
            </div>
            <div>
              <span className="text-gray-500">Avg Engagement:</span>
              <span className="ml-2 font-medium">
                {(selectedStudent.average_engagement * 100).toFixed(0)}%
              </span>
            </div>
            <div>
              <span className="text-gray-500">Sessions Attended:</span>
              <span className="ml-2 font-medium">{selectedStudent.sessions_attended}</span>
            </div>
          </div>
        </div>
      )}

      {/* Class progress overview */}
      {progress && (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div className="text-center p-3 bg-gray-50 dark:bg-gray-700 rounded">
              <div className="text-2xl font-bold text-primary-600">
                {progress.total_students}
              </div>
              <div className="text-xs text-gray-500">Total Students</div>
            </div>
            <div className="text-center p-3 bg-gray-50 dark:bg-gray-700 rounded">
              <div className="text-2xl font-bold text-green-600">
                {progress.on_track_count}
              </div>
              <div className="text-xs text-gray-500">On Track</div>
            </div>
            <div className="text-center p-3 bg-gray-50 dark:bg-gray-700 rounded">
              <div className="text-2xl font-bold text-red-600">
                {progress.needs_attention_count}
              </div>
              <div className="text-xs text-gray-500">Need Attention</div>
            </div>
          </div>

          {/* Students needing attention */}
          {progress.students_needing_attention && progress.students_needing_attention.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-600 mb-2">Students Needing Attention</h4>
              <div className="space-y-2">
                {progress.students_needing_attention.map((student) => (
                  <div
                    key={student.user_id}
                    className="flex items-center justify-between p-2 bg-red-50 dark:bg-red-900/20 rounded"
                  >
                    <div className="flex items-center gap-2">
                      <User className="w-4 h-4 text-gray-400" />
                      <span className="text-sm">{student.name}</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      <TrendIcon trend={student.trend} />
                      <span className="text-gray-500">
                        {student.sessions_attended} sessions
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default StudentProgressComponent;
