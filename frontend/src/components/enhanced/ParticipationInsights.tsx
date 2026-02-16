'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Loader2, RefreshCw, AlertTriangle, CheckCircle, Users,
  TrendingUp, TrendingDown, Activity, Bell
} from 'lucide-react';

interface ParticipationInsightsProps {
  courseId: number;
  sessionId?: number;
}

interface ParticipationSummary {
  course_id: number;
  total_students: number;
  active_students: number;
  at_risk_students: number;
  avg_posts_per_student: number;
  participation_rate: number;
  alerts: Array<{
    id: number;
    alert_type: string;
    severity: string;
    message: string;
    user_name?: string;
    acknowledged: boolean;
    created_at: string;
  }>;
}

interface SessionParticipation {
  user_id: number;
  user_name: string;
  post_count: number;
  reply_count: number;
  quality_score?: number;
  engagement_level?: string;
  at_risk: boolean;
  risk_factors?: string[];
}

export function ParticipationInsightsComponent({ courseId, sessionId }: ParticipationInsightsProps) {
  const [summary, setSummary] = useState<ParticipationSummary | null>(null);
  const [sessionData, setSessionData] = useState<SessionParticipation[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const summaryData = await api.getCourseParticipation(courseId);
      setSummary(summaryData);

      if (sessionId) {
        const sessionParticipation = await api.getSessionParticipation(sessionId);
        setSessionData(sessionParticipation);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load participation data');
    } finally {
      setLoading(false);
    }
  };

  const analyzeParticipation = async () => {
    try {
      setAnalyzing(true);
      await api.analyzeParticipation(courseId);
      setTimeout(fetchData, 5000);
    } catch (err: any) {
      setError(err.message || 'Failed to analyze participation');
    } finally {
      setAnalyzing(false);
    }
  };

  const acknowledgeAlert = async (alertId: number) => {
    try {
      await api.acknowledgeAlert(alertId);
      fetchData();
    } catch (err: any) {
      setError(err.message || 'Failed to acknowledge alert');
    }
  };

  useEffect(() => {
    fetchData();
  }, [courseId, sessionId]);

  const getEngagementColor = (level?: string) => {
    switch (level) {
      case 'highly_active': return 'bg-green-100 text-green-800';
      case 'active': return 'bg-blue-100 text-blue-800';
      case 'idle': return 'bg-yellow-100 text-yellow-800';
      case 'disengaged': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-100 text-red-800 border-red-200';
      case 'warning': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      default: return 'bg-blue-100 text-blue-800 border-blue-200';
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Course Overview */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Activity className="w-5 h-5" />
                Participation Overview
              </CardTitle>
              <CardDescription>
                Course-wide participation metrics and alerts
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={analyzeParticipation}
              disabled={analyzing}
            >
              {analyzing ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <RefreshCw className="w-4 h-4 mr-2" />
              )}
              Analyze
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="p-3 bg-red-50 text-red-700 rounded-lg mb-4">
              {error}
            </div>
          )}

          {summary && (
            <>
              {/* Stats Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg text-center">
                  <Users className="w-6 h-6 mx-auto mb-2 text-blue-500" />
                  <div className="text-2xl font-bold">{summary.total_students}</div>
                  <div className="text-xs text-gray-500">Total Students</div>
                </div>
                <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg text-center">
                  <TrendingUp className="w-6 h-6 mx-auto mb-2 text-green-500" />
                  <div className="text-2xl font-bold">{summary.active_students}</div>
                  <div className="text-xs text-gray-500">Active Students</div>
                </div>
                <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg text-center">
                  <AlertTriangle className="w-6 h-6 mx-auto mb-2 text-red-500" />
                  <div className="text-2xl font-bold">{summary.at_risk_students}</div>
                  <div className="text-xs text-gray-500">At-Risk Students</div>
                </div>
                <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg text-center">
                  <Activity className="w-6 h-6 mx-auto mb-2 text-purple-500" />
                  <div className="text-2xl font-bold">{summary.participation_rate.toFixed(0)}%</div>
                  <div className="text-xs text-gray-500">Participation Rate</div>
                </div>
              </div>

              {/* Alerts */}
              {summary.alerts.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                    <Bell className="w-4 h-4" />
                    Active Alerts ({summary.alerts.filter(a => !a.acknowledged).length})
                  </h4>
                  <div className="space-y-2">
                    {summary.alerts.filter(a => !a.acknowledged).map((alert) => (
                      <div
                        key={alert.id}
                        className={`p-3 rounded-lg border flex items-start justify-between ${getSeverityColor(alert.severity)}`}
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <AlertTriangle className="w-4 h-4" />
                            <span className="font-medium">{alert.user_name || 'Unknown Student'}</span>
                            <Badge variant="outline" className="text-xs">
                              {alert.alert_type.replace('_', ' ')}
                            </Badge>
                          </div>
                          <p className="text-sm mt-1">{alert.message}</p>
                        </div>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => acknowledgeAlert(alert.id)}
                        >
                          <CheckCircle className="w-4 h-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Session Participation Details */}
      {sessionId && sessionData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Session Participation</CardTitle>
            <CardDescription>
              Individual student participation for this session
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 px-3">Student</th>
                    <th className="text-center py-2 px-3">Posts</th>
                    <th className="text-center py-2 px-3">Replies</th>
                    <th className="text-center py-2 px-3">Quality</th>
                    <th className="text-center py-2 px-3">Engagement</th>
                    <th className="text-center py-2 px-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sessionData.map((student) => (
                    <tr key={student.user_id} className="border-b hover:bg-gray-50 dark:hover:bg-gray-800">
                      <td className="py-2 px-3 font-medium">{student.user_name}</td>
                      <td className="text-center py-2 px-3">{student.post_count}</td>
                      <td className="text-center py-2 px-3">{student.reply_count}</td>
                      <td className="text-center py-2 px-3">
                        {student.quality_score !== undefined ? (
                          <span className={student.quality_score >= 0.7 ? 'text-green-600' : student.quality_score >= 0.4 ? 'text-yellow-600' : 'text-red-600'}>
                            {(student.quality_score * 100).toFixed(0)}%
                          </span>
                        ) : '-'}
                      </td>
                      <td className="text-center py-2 px-3">
                        {student.engagement_level && (
                          <Badge className={getEngagementColor(student.engagement_level)}>
                            {student.engagement_level.replace('_', ' ')}
                          </Badge>
                        )}
                      </td>
                      <td className="text-center py-2 px-3">
                        {student.at_risk ? (
                          <Badge className="bg-red-100 text-red-800">At Risk</Badge>
                        ) : (
                          <Badge className="bg-green-100 text-green-800">OK</Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default ParticipationInsightsComponent;
