'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Progress } from '@/components/ui/Progress';
import {
  Loader2, RefreshCw, Target, CheckCircle, AlertCircle, Circle
} from 'lucide-react';

interface ObjectiveCoverageProps {
  courseId: number;
}

interface CoverageReport {
  course_id: number;
  total_objectives: number;
  fully_covered: number;
  partially_covered: number;
  not_covered: number;
  objectives: Array<{
    objective_text: string;
    objective_index?: number;
    coverage_level?: string;
    coverage_score?: number;
    coverage_summary?: string;
    gaps_identified?: string[];
    sessions_covered: number[];
  }>;
  recommended_topics: string[];
}

export function ObjectiveCoverageComponent({ courseId }: ObjectiveCoverageProps) {
  const [report, setReport] = useState<CoverageReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCoverage = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getObjectiveCoverage(courseId);
      setReport(data);
    } catch (err: any) {
      if (err.status === 404) {
        setReport(null);
      } else {
        setError(err.message || 'Failed to load coverage data');
      }
    } finally {
      setLoading(false);
    }
  };

  const analyzeCoverage = async () => {
    try {
      setAnalyzing(true);
      await api.analyzeObjectiveCoverage(courseId);
      setTimeout(fetchCoverage, 5000);
    } catch (err: any) {
      setError(err.message || 'Failed to analyze coverage');
    } finally {
      setAnalyzing(false);
    }
  };

  useEffect(() => {
    fetchCoverage();
  }, [courseId]);

  const getCoverageIcon = (level?: string) => {
    switch (level) {
      case 'fully': return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'partially': return <Circle className="w-5 h-5 text-yellow-500" />;
      default: return <AlertCircle className="w-5 h-5 text-red-500" />;
    }
  };

  const getCoverageColor = (level?: string) => {
    switch (level) {
      case 'fully': return 'bg-green-100 text-green-800';
      case 'partially': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-red-100 text-red-800';
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
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Target className="w-5 h-5" />
              Learning Objective Coverage
            </CardTitle>
            <CardDescription>
              Track how well discussions cover learning objectives
            </CardDescription>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={analyzeCoverage}
            disabled={analyzing}
          >
            {analyzing ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : (
              <RefreshCw className="w-4 h-4 mr-2" />
            )}
            Analyze Coverage
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {error && (
          <div className="p-3 bg-red-50 text-red-700 rounded-lg">
            {error}
          </div>
        )}

        {!report || report.total_objectives === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Target className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p>No learning objectives analyzed yet</p>
            <p className="text-sm mt-2">
              Make sure your course has learning objectives defined, then run analysis.
            </p>
            <Button className="mt-4" onClick={analyzeCoverage} disabled={analyzing}>
              Analyze Coverage
            </Button>
          </div>
        ) : (
          <>
            {/* Summary Stats */}
            <div className="grid grid-cols-3 gap-4">
              <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg text-center">
                <CheckCircle className="w-6 h-6 mx-auto mb-2 text-green-500" />
                <div className="text-2xl font-bold text-green-700 dark:text-green-300">
                  {report.fully_covered}
                </div>
                <div className="text-xs text-green-600 dark:text-green-400">Fully Covered</div>
              </div>
              <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg text-center">
                <Circle className="w-6 h-6 mx-auto mb-2 text-yellow-500" />
                <div className="text-2xl font-bold text-yellow-700 dark:text-yellow-300">
                  {report.partially_covered}
                </div>
                <div className="text-xs text-yellow-600 dark:text-yellow-400">Partially Covered</div>
              </div>
              <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg text-center">
                <AlertCircle className="w-6 h-6 mx-auto mb-2 text-red-500" />
                <div className="text-2xl font-bold text-red-700 dark:text-red-300">
                  {report.not_covered}
                </div>
                <div className="text-xs text-red-600 dark:text-red-400">Not Covered</div>
              </div>
            </div>

            {/* Overall Progress */}
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span>Overall Coverage</span>
                <span>
                  {((report.fully_covered + report.partially_covered * 0.5) / report.total_objectives * 100).toFixed(0)}%
                </span>
              </div>
              <Progress
                value={(report.fully_covered + report.partially_covered * 0.5) / report.total_objectives * 100}
                className="h-2"
              />
            </div>

            {/* Objectives List */}
            <div className="space-y-3">
              <h4 className="text-sm font-medium">Learning Objectives</h4>
              {report.objectives.map((obj, idx) => (
                <div
                  key={idx}
                  className="p-4 border rounded-lg hover:border-primary-300 transition-colors"
                >
                  <div className="flex items-start gap-3">
                    {getCoverageIcon(obj.coverage_level)}
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-gray-900 dark:text-white">
                          {obj.objective_text}
                        </span>
                        <Badge className={getCoverageColor(obj.coverage_level)}>
                          {obj.coverage_level?.replace('_', ' ') || 'not analyzed'}
                        </Badge>
                      </div>

                      {obj.coverage_score !== undefined && (
                        <div className="mb-2">
                          <Progress value={obj.coverage_score * 100} className="h-1.5" />
                        </div>
                      )}

                      {obj.coverage_summary && (
                        <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                          {obj.coverage_summary}
                        </p>
                      )}

                      {obj.gaps_identified && obj.gaps_identified.length > 0 && (
                        <div className="text-sm">
                          <span className="text-red-600 font-medium">Gaps: </span>
                          {obj.gaps_identified.join(', ')}
                        </div>
                      )}

                      {obj.sessions_covered.length > 0 && (
                        <div className="text-xs text-gray-500 mt-1">
                          Covered in sessions: {obj.sessions_covered.join(', ')}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Recommended Topics */}
            {report.recommended_topics && report.recommended_topics.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2">Recommended Topics for Future Sessions</h4>
                <div className="flex flex-wrap gap-2">
                  {report.recommended_topics.map((topic, idx) => (
                    <Badge key={idx} variant="default">
                      {topic}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

export default ObjectiveCoverageComponent;
