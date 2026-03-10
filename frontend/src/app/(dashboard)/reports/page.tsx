'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  FileText,
  RefreshCw,
  Users,
  BarChart3,
  CheckCircle,
  XCircle,
  Award,
  TrendingUp,
  TrendingDown,
  BookOpen,
  AlertTriangle,
  Clock,
  DollarSign,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useUser } from '@/lib/context';
import { useSharedCourseSessionSelection } from '@/lib/shared-selection';
import { createVoiceTabHandler, setupVoiceTabListeners, mergeTabMappings } from '@/lib/voice-tab-handler';
import { Course, Session, Report, ReportJSON, SessionComparison } from '@/types';
import { formatTimestamp } from '@/lib/utils';
import { useTranslations } from 'next-intl';
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Select,
  Badge,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
  EmptyState,
} from '@/components/ui';

// Instructor enhancement components
import { StudentProgressComponent } from '@/components/instructor/StudentProgress';

export default function ReportsPage() {
  const { isInstructor, isAdmin, currentUser } = useUser();
  // Admins have same privileges as instructors
  const hasInstructorPrivileges = isInstructor || isAdmin;
  const t = useTranslations();
  const [courses, setCourses] = useState<Course[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const {
    selectedCourseId,
    setSelectedCourseId,
    selectedSessionId,
    setSelectedSessionId,
  } = useSharedCourseSessionSelection();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);

  // Analytics state
  const [sessionComparisons, setSessionComparisons] = useState<SessionComparison[]>([]);
  const [courseAnalytics, setCourseAnalytics] = useState<any>(null);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);

  // Tab state for voice control
  const [activeTab, setActiveTab] = useState('summary');

  // Reports page tab mappings
  const reportsTabMap = mergeTabMappings({
    // Instructor tabs
    'summary': 'summary',
    'reportsummary': 'summary',
    'overview': 'summary',
    'participation': 'participation',
    'participationtab': 'participation',
    'scoring': 'scoring',
    'scores': 'scoring',
    'grades': 'scoring',
    'answerscores': 'scoring',
    'analytics': 'analytics',
    'reportanalytics': 'analytics',
    'dataanalytics': 'analytics',
    // Student tabs
    'myperformance': 'my-performance',
    'performance': 'my-performance',
    'bestpractice': 'best-practice',
    'bestpractices': 'best-practice',
    'bestanswer': 'best-practice',
  });

  // Voice tab handler
  const handleVoiceTabSwitch = useCallback(
    createVoiceTabHandler(reportsTabMap, setActiveTab, 'Reports'),
    []
  );

  // Set up voice tab listeners
  useEffect(() => {
    return setupVoiceTabListeners(handleVoiceTabSwitch);
  }, [handleVoiceTabSwitch]);

  const fetchCourses = async () => {
    try {
      if (!currentUser) return;

      if (isAdmin) {
        // Admin sees all courses
        const data = await api.getCourses(currentUser.id);
        setCourses(data);
        if (data.length > 0 && (!selectedCourseId || !data.some((course) => course.id === selectedCourseId))) {
          setSelectedCourseId(data[0].id);
        } else if (data.length === 0) {
          setSelectedCourseId(null);
        }
      } else if (isInstructor) {
        // Instructors see only their own courses
        const data = await api.getCourses(currentUser.id);
        setCourses(data);
        if (data.length > 0 && (!selectedCourseId || !data.some((course) => course.id === selectedCourseId))) {
          setSelectedCourseId(data[0].id);
        } else if (data.length === 0) {
          setSelectedCourseId(null);
        }
      } else {
        // Students only see courses they're enrolled in
        const enrolledCourses = await api.getUserEnrolledCourses(currentUser.id);
        const coursePromises = enrolledCourses.map((ec: any) => api.getCourse(ec.course_id));
        const fullCourses = await Promise.all(coursePromises);
        setCourses(fullCourses);
        if (fullCourses.length > 0 && (!selectedCourseId || !fullCourses.some((course) => course.id === selectedCourseId))) {
          setSelectedCourseId(fullCourses[0].id);
        } else if (fullCourses.length === 0) {
          setSelectedCourseId(null);
        }
      }
    } catch (error) {
      console.error('Failed to fetch courses:', error);
    }
  };

  const fetchSessions = async (courseId: number) => {
    try {
      const data = await api.getCourseSessions(courseId);
      // Only show completed sessions for reports
      const completedSessions = data.filter(
        (s: Session) => s.status === 'completed'
      );
      setSessions(completedSessions);
      if (completedSessions.length > 0 && (!selectedSessionId || !completedSessions.some((session) => session.id === selectedSessionId))) {
        setSelectedSessionId(completedSessions[0].id);
      } else {
        if (completedSessions.length === 0) {
          setSelectedSessionId(null);
        }
      }
    } catch (error) {
      console.error('Failed to fetch sessions:', error);
    }
  };

  const fetchReport = async () => {
    if (!selectedSessionId) return;

    setLoading(true);
    try {
      const data = await api.getReport(selectedSessionId);
      setReport(data);
    } catch (error: any) {
      if (error.status === 404) {
        setReport(null);
      } else {
        console.error('Failed to fetch report:', error);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateReport = async () => {
    if (!selectedSessionId) return;

    setGenerating(true);
    try {
      await api.generateReport(selectedSessionId);
      alert('Report generation started! Refresh in a moment to see results.');
      // Wait a bit then refresh
      setTimeout(fetchReport, 5000);
    } catch (error) {
      console.error('Failed to generate report:', error);
      alert('Failed to generate report');
    } finally {
      setGenerating(false);
    }
  };

  const fetchAnalytics = async () => {
    if (!selectedCourseId) return;

    setLoadingAnalytics(true);
    try {
      // Fetch session comparisons
      const comparisons = await api.compareCourseSessions(selectedCourseId);
      setSessionComparisons(comparisons.sessions || []);

      // Fetch course analytics
      const analytics = await api.getCourseAnalytics(selectedCourseId);
      setCourseAnalytics(analytics);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    } finally {
      setLoadingAnalytics(false);
    }
  };

  useEffect(() => {
    if (currentUser) {
      fetchCourses();
    }
  }, [currentUser, hasInstructorPrivileges]);

  useEffect(() => {
    if (selectedCourseId) {
      fetchSessions(selectedCourseId);
    }
  }, [selectedCourseId]);

  useEffect(() => {
    if (selectedSessionId) {
      fetchReport();
    }
  }, [selectedSessionId]);

  const reportJson: ReportJSON | undefined = report?.report_json;

  const renderParticipation = () => {
    if (!reportJson?.participation) {
      return (
        <EmptyState icon={Users} message="Participation data not available." />
      );
    }

    const { participation } = reportJson;
    const rate = participation.participation_rate || 0;

    return (
      <div className="space-y-4">
        {/* Inline text summary replacing stat cards */}
        <p className="text-sm text-neutral-600 dark:text-neutral-400">
          <strong className="text-neutral-900 dark:text-white">{participation.total_enrolled_students}</strong> enrolled
          {' \u00B7 '}
          <strong className="text-neutral-900 dark:text-white">{participation.participation_count}</strong> participated
          {' \u00B7 '}
          <strong className="text-neutral-900 dark:text-white">{rate.toFixed(1)}%</strong> participation rate
        </p>

        {/* Participated - table layout */}
        {participation.students_who_participated &&
          participation.students_who_participated.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-2 flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-green-500" />
                Students Who Participated ({participation.students_who_participated.length})
              </h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-neutral-200 dark:border-neutral-700">
                    <th className="text-left py-2 font-medium text-neutral-500 dark:text-neutral-400">Student</th>
                    <th className="text-right py-2 font-medium text-neutral-500 dark:text-neutral-400">Posts</th>
                  </tr>
                </thead>
                <tbody>
                  {participation.students_who_participated.map((student) => (
                    <tr key={student.user_id} className="border-b border-neutral-100 dark:border-neutral-800">
                      <td className="py-2 text-neutral-700 dark:text-neutral-300">{student.name}</td>
                      <td className="py-2 text-right text-neutral-600 dark:text-neutral-400">{student.post_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

        {/* Did Not Participate - comma-separated text */}
        {participation.students_who_did_not_participate &&
          participation.students_who_did_not_participate.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-2 flex items-center gap-2">
                <XCircle className="h-4 w-4 text-red-500" />
                Did Not Participate ({participation.students_who_did_not_participate.length})
              </h3>
              <p className="text-sm text-neutral-600 dark:text-neutral-400">
                {participation.students_who_did_not_participate.map((s) => s.name).join(', ')}
              </p>
            </div>
          )}
      </div>
    );
  };

  const renderScoring = () => {
    if (!reportJson?.answer_scores) {
      return (
        <EmptyState icon={Award} message="Scoring data not available." />
      );
    }

    const { answer_scores } = reportJson;

    return (
      <div className="space-y-4">
        {/* Inline statistics replacing stat cards */}
        {answer_scores.class_statistics && (
          <p className="text-sm text-neutral-600 dark:text-neutral-400">
            Avg: <strong className="text-neutral-900 dark:text-white">{answer_scores.class_statistics.average_score.toFixed(1)}</strong>
            {' \u00B7 '}
            High: <strong className="text-green-600 dark:text-green-400">{answer_scores.class_statistics.highest_score.toFixed(1)}</strong>
            {' \u00B7 '}
            Low: <strong className="text-red-600 dark:text-red-400">{answer_scores.class_statistics.lowest_score.toFixed(1)}</strong>
            {answer_scores.closest_to_correct && (
              <>
                {' \u00B7 '}
                Best: {answer_scores.closest_to_correct.user_name || `User #${answer_scores.closest_to_correct.user_id}`} ({answer_scores.closest_to_correct.score.toFixed(1)})
              </>
            )}
          </p>
        )}

        {/* Student scores table */}
        {answer_scores.student_scores && answer_scores.student_scores.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-200 dark:border-neutral-700">
                  <th className="text-left py-2 font-medium text-neutral-500 dark:text-neutral-400 w-8">#</th>
                  <th className="text-left py-2 font-medium text-neutral-500 dark:text-neutral-400">Student</th>
                  <th className="text-right py-2 font-medium text-neutral-500 dark:text-neutral-400 w-20">Score</th>
                  <th className="text-left py-2 font-medium text-neutral-500 dark:text-neutral-400 pl-4">Key Points</th>
                </tr>
              </thead>
              <tbody>
                {answer_scores.student_scores
                  .sort((a, b) => b.score - a.score)
                  .map((score, index) => (
                    <tr
                      key={`${score.user_id}-${score.post_id}`}
                      className="border-b border-neutral-100 dark:border-neutral-800"
                    >
                      <td className="py-2 text-neutral-400">{index + 1}</td>
                      <td className="py-2 text-neutral-700 dark:text-neutral-300">
                        {score.user_name || `User #${score.user_id}`}
                      </td>
                      <td className="py-2 text-right">
                        <Badge
                          variant={
                            score.score >= 80 ? 'success' : score.score >= 60 ? 'warning' : 'danger'
                          }
                          size="sm"
                        >
                          {score.score.toFixed(1)}
                        </Badge>
                      </td>
                      <td className="py-2 pl-4 text-xs text-neutral-500 dark:text-neutral-400">
                        {score.key_points_covered && score.key_points_covered.length > 0
                          ? score.key_points_covered.join(', ')
                          : score.feedback || '\u2014'}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  };

  const renderSummary = () => {
    if (!reportJson) return null;

    return (
      <div className="space-y-4">
        {/* Summary Stats */}
        {reportJson.summary && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Discussion Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center">
                  <p className="text-2xl font-bold text-primary-600">
                    {reportJson.summary.total_posts}
                  </p>
                  <p className="text-sm text-neutral-500">Total Posts</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-primary-600">
                    {reportJson.summary.student_posts}
                  </p>
                  <p className="text-sm text-neutral-500">Student Posts</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-green-600">
                    {reportJson.summary.instructor_posts}
                  </p>
                  <p className="text-sm text-neutral-500">Instructor Posts</p>
                </div>
                <div className="text-center">
                  <Badge
                    variant={
                      reportJson.summary.discussion_quality === 'High'
                        ? 'success'
                        : reportJson.summary.discussion_quality === 'Medium'
                        ? 'warning'
                        : 'default'
                    }
                    className="text-lg px-4 py-1"
                  >
                    {reportJson.summary.discussion_quality}
                  </Badge>
                  <p className="text-sm text-neutral-500 mt-1">Quality</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Theme Clusters */}
        {reportJson.theme_clusters && reportJson.theme_clusters.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Theme Clusters</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {reportJson.theme_clusters.map((cluster, i) => (
                  <div key={i} className="bg-neutral-50 p-3 rounded-lg">
                    <h4 className="font-medium text-neutral-900">{cluster.theme}</h4>
                    <p className="text-sm text-neutral-600 mt-1">{cluster.description}</p>
                    <p className="text-xs text-neutral-400 mt-2">
                      {cluster.post_ids.length} related posts
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Learning Objectives */}
        {reportJson.learning_objectives_alignment &&
          reportJson.learning_objectives_alignment.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <BookOpen className="h-5 w-5" />
                  Learning Objectives Alignment
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {reportJson.learning_objectives_alignment.map((obj, i) => (
                    <div key={i} className="border-l-4 border-primary-500 pl-3 py-1">
                      <p className="font-medium text-neutral-900">{obj.objective}</p>
                      <Badge
                        variant={
                          obj.coverage === 'Strong'
                            ? 'success'
                            : obj.coverage === 'Moderate'
                            ? 'warning'
                            : 'default'
                        }
                        className="mt-1"
                      >
                        {obj.coverage} coverage
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

        {/* Misconceptions */}
        {reportJson.misconceptions && reportJson.misconceptions.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-orange-500" />
                Misconceptions Identified
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {reportJson.misconceptions.map((m, i) => (
                  <div key={i} className="bg-orange-50 p-3 rounded-lg">
                    <p className="text-sm text-orange-800">
                      <span className="font-medium">Issue:</span> {m.misconception}
                    </p>
                    <p className="text-sm text-green-700 mt-2">
                      <span className="font-medium">Correction:</span> {m.correction}
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Best Practice Answer */}
        {reportJson.best_practice_answer && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Award className="h-5 w-5 text-yellow-500" />
                Best Practice Answer
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-neutral-800">{reportJson.best_practice_answer.summary}</p>
              {reportJson.best_practice_answer.detailed_explanation && (
                <p className="text-sm text-neutral-600">
                  {reportJson.best_practice_answer.detailed_explanation}
                </p>
              )}
              {reportJson.best_practice_answer.key_concepts &&
                reportJson.best_practice_answer.key_concepts.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {reportJson.best_practice_answer.key_concepts.map((concept, i) => (
                      <Badge key={i} variant="info">
                        {concept}
                      </Badge>
                    ))}
                  </div>
                )}
            </CardContent>
          </Card>
        )}

        {/* Developer observability stats hidden from users */}
      </div>
    );
  };

  // Student-only view: Show only their own performance
  const renderStudentPerformance = () => {
    if (!reportJson?.answer_scores) {
      return <EmptyState icon={Award} message="Your performance data is not available yet." />;
    }

    const { answer_scores } = reportJson;
    // For now, show all scores - in a real app, you'd filter by current user ID
    const studentScores = answer_scores.student_scores || [];

    if (studentScores.length === 0) {
      return <EmptyState icon={Award} message="No performance data found for this session." />;
    }

    return (
      <div className="space-y-4">
        {studentScores.map((score, index) => (
          <Card key={`${score.user_id}-${score.post_id}`}>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Award className="h-5 w-5 text-yellow-500" />
                Your Score
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Score display */}
              <div className="flex items-center justify-between">
                <span className="text-lg font-medium">Overall Score</span>
                <Badge
                  variant={
                    score.score >= 80
                      ? 'success'
                      : score.score >= 60
                      ? 'warning'
                      : 'danger'
                  }
                  className="text-lg px-4 py-1"
                >
                  {score.score.toFixed(1)} / 100
                </Badge>
              </div>

              {/* Score bar */}
              <div className="h-3 bg-neutral-200 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    score.score >= 80
                      ? 'bg-green-500'
                      : score.score >= 60
                      ? 'bg-yellow-500'
                      : 'bg-red-500'
                  }`}
                  style={{ width: `${score.score}%` }}
                />
              </div>

              {/* What you did well */}
              {score.key_points_covered && score.key_points_covered.length > 0 && (
                <div className="bg-green-50 p-4 rounded-lg">
                  <h4 className="font-medium text-green-800 flex items-center gap-2 mb-2">
                    <CheckCircle className="h-5 w-5" />
                    What You Did Well
                  </h4>
                  <ul className="list-disc list-inside space-y-1">
                    {score.key_points_covered.map((point, i) => (
                      <li key={i} className="text-green-700">{point}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Gaps / Areas for improvement */}
              {score.missing_points && score.missing_points.length > 0 && (
                <div className="bg-orange-50 p-4 rounded-lg">
                  <h4 className="font-medium text-orange-800 flex items-center gap-2 mb-2">
                    <AlertTriangle className="h-5 w-5" />
                    Areas for Improvement
                  </h4>
                  <ul className="list-disc list-inside space-y-1">
                    {score.missing_points.map((point, i) => (
                      <li key={i} className="text-orange-700">{point}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Feedback */}
              {score.feedback && (
                <div className="rounded-lg bg-primary-50 p-4 dark:bg-primary-900/20">
                  <h4 className="mb-2 font-medium text-primary-800 dark:text-primary-200">Feedback</h4>
                  <p className="text-primary-700 dark:text-primary-300">{score.feedback}</p>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    );
  };

  // Student-only view: Best practice answer
  const renderBestPractice = () => {
    if (!reportJson?.best_practice_answer) {
      return <EmptyState icon={BookOpen} message="Best practice answer is not available yet." />;
    }

    const { best_practice_answer } = reportJson;

    return (
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Award className="h-5 w-5 text-yellow-500" />
              Best Practice Answer
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="bg-yellow-50 p-4 rounded-lg">
              <p className="text-neutral-800 font-medium">{best_practice_answer.summary}</p>
            </div>

            {best_practice_answer.detailed_explanation && (
              <div>
                <h4 className="font-medium text-neutral-700 mb-2">Detailed Explanation</h4>
                <p className="text-neutral-600">{best_practice_answer.detailed_explanation}</p>
              </div>
            )}

            {best_practice_answer.key_concepts && best_practice_answer.key_concepts.length > 0 && (
              <div>
                <h4 className="font-medium text-neutral-700 mb-2">Key Concepts</h4>
                <div className="flex flex-wrap gap-2">
                  {best_practice_answer.key_concepts.map((concept, i) => (
                    <Badge key={i} variant="info">
                      {concept}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  };

  return (
    <div className="space-y-6 pb-4">
      {/* Header + selectors merged into one row */}
      <div className="pb-4 border-b border-neutral-200 dark:border-neutral-700">
        <div className="flex flex-col sm:flex-row sm:items-end gap-3">
          <div className="flex-1">
            <h1 className="text-xl font-semibold text-neutral-900 dark:text-white">{t('reports.title')}</h1>
            <p className="text-neutral-600 dark:text-neutral-400 mt-1 text-sm">{t('reports.subtitle')}</p>
          </div>
          <div className="flex flex-col sm:flex-row items-stretch sm:items-end gap-3">
            <Select
              label={t('courses.selectCourse')}
              value={selectedCourseId?.toString() || ''}
              onChange={(e) => setSelectedCourseId(e.target.value ? Number(e.target.value) : null)}
              data-voice-id="select-course"
            >
              <option value="">Select a course...</option>
              {courses.map((course) => (
                <option key={course.id} value={course.id}>
                  {course.title}
                </option>
              ))}
            </Select>

            <Select
              label="Select Session"
              value={selectedSessionId?.toString() || ''}
              onChange={(e) => setSelectedSessionId(e.target.value ? Number(e.target.value) : null)}
              disabled={!selectedCourseId}
              data-voice-id="select-session"
            >
              <option value="">Select a session...</option>
              {sessions.map((session) => (
                <option key={session.id} value={session.id}>
                  {session.title} ({session.status})
                </option>
              ))}
            </Select>
          </div>
        </div>
      </div>

      {!selectedSessionId ? (
        <EmptyState
          icon={FileText}
          message={t('reports.generateFirst')}
        />
      ) : loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="flex flex-col items-center gap-3">
            <div className="relative">
              <div className="w-10 h-10 rounded-full border-4 border-primary-100 dark:border-primary-900"></div>
              <div className="absolute top-0 left-0 w-10 h-10 rounded-full border-4 border-primary-600 border-t-transparent animate-spin"></div>
            </div>
            <p className="text-sm text-neutral-500 dark:text-neutral-400">{t('common.loading')}</p>
          </div>
        </div>
      ) : !report ? (
        <EmptyState
          icon={FileText}
          message={t('reports.noReport')}
          action={hasInstructorPrivileges ? (
            <Button onClick={handleGenerateReport} disabled={generating} data-voice-id="generate-report" size="sm">
              <FileText className="h-4 w-4 mr-2" />
              {generating ? t('common.loading') : t('reports.generateReport')}
            </Button>
          ) : undefined}
        />
      ) : (
        <div>
          {/* Report Header */}
          <Card className="mb-6">
            <CardContent className="py-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">
                    Report for: {reportJson?.session_title || `Session #${report.session_id}`}
                  </h2>
                  <p className="text-sm text-neutral-500 dark:text-neutral-400">
                    Generated: {formatTimestamp(report.created_at)} | Version: {report.version}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button onClick={fetchReport} variant="outline" size="sm" data-voice-id="refresh-report">
                    <RefreshCw className="h-4 w-4 mr-2" />
                    {t('reports.refreshReport')}
                  </Button>
                  {hasInstructorPrivileges && (
                    <Button onClick={handleGenerateReport} size="sm" disabled={generating} data-voice-id="regenerate-report">
                      <FileText className="h-4 w-4 mr-2" />
                      {t('reports.regenerateReport')}
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Report Tabs - Different views for instructors/admins vs students */}
          {hasInstructorPrivileges ? (
            <Tabs value={activeTab} onValueChange={(value) => {
              setActiveTab(value);
              if (value === 'analytics') {
                fetchAnalytics();
              }
            }}>
              <TabsList className="border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-800 rounded-xl">
                <TabsTrigger value="summary" data-voice-id="tab-summary">{t('reports.summary')}</TabsTrigger>
                <TabsTrigger value="participation" data-voice-id="tab-participation">{t('reports.participation')}</TabsTrigger>
                <TabsTrigger value="scoring" data-voice-id="tab-scoring">{t('reports.answerScores')}</TabsTrigger>
                <TabsTrigger value="analytics" data-voice-id="tab-analytics">
                  <TrendingUp className="h-4 w-4 mr-1" />
                  Analytics
                </TabsTrigger>
              </TabsList>

              <TabsContent value="summary">{renderSummary()}</TabsContent>
              <TabsContent value="participation">{renderParticipation()}</TabsContent>
              <TabsContent value="scoring">{renderScoring()}</TabsContent>
              <TabsContent value="analytics">
                {loadingAnalytics ? (
                  <div className="text-center py-8 text-neutral-500">{t('common.loading')}</div>
                ) : (
                  <div className="space-y-6">
                    {/* Course Analytics Overview */}
                    {courseAnalytics && (
                      <Card>
                        <CardHeader>
                          <CardTitle className="flex items-center gap-2">
                            <BarChart3 className="h-5 w-5 text-accent-500" />
                            Course Analytics
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div className="text-center p-3 bg-neutral-50 rounded">
                              <p className="text-2xl font-bold text-primary-600">
                                {courseAnalytics.total_sessions || 0}
                              </p>
                              <p className="text-sm text-neutral-500">Total Sessions</p>
                            </div>
                            <div className="text-center p-3 bg-neutral-50 rounded">
                              <p className="text-2xl font-bold text-green-600">
                                {courseAnalytics.completed_sessions || 0}
                              </p>
                              <p className="text-sm text-neutral-500">Completed</p>
                            </div>
                            <div className="text-center p-3 bg-neutral-50 rounded">
                              <p className="text-2xl font-bold text-primary-600">
                                {courseAnalytics.overall_stats?.average_participation_rate?.toFixed(0) || 0}%
                              </p>
                              <p className="text-sm text-neutral-500">Avg Participation</p>
                            </div>
                            <div className="text-center p-3 bg-neutral-50 rounded">
                              <p className="text-2xl font-bold text-yellow-600">
                                {courseAnalytics.overall_stats?.average_posts_per_session?.toFixed(1) || 0}
                              </p>
                              <p className="text-sm text-neutral-500">Avg Posts/Session</p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {/* Session Comparison */}
                    {sessionComparisons.length > 0 && (
                      <Card>
                        <CardHeader>
                          <CardTitle className="flex items-center gap-2">
                            <TrendingUp className="h-5 w-5 text-green-500" />
                            Session Comparison
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="border-b">
                                  <th className="text-left py-2 px-3">Session</th>
                                  <th className="text-center py-2 px-3">Status</th>
                                  <th className="text-center py-2 px-3">Posts</th>
                                  <th className="text-center py-2 px-3">Participants</th>
                                  <th className="text-center py-2 px-3">Rate</th>
                                  <th className="text-center py-2 px-3">Polls</th>
                                </tr>
                              </thead>
                              <tbody>
                                {sessionComparisons.map((session) => (
                                  <tr key={session.session_id} className="border-b hover:bg-neutral-50">
                                    <td className="py-2 px-3">
                                      <div>
                                        <p className="font-medium">{session.title}</p>
                                        <p className="text-xs text-neutral-500">{session.date}</p>
                                      </div>
                                    </td>
                                    <td className="text-center py-2 px-3">
                                      <Badge
                                        variant={
                                          session.status === 'completed' ? 'success' :
                                          session.status === 'live' ? 'warning' : 'default'
                                        }
                                      >
                                        {session.status}
                                      </Badge>
                                    </td>
                                    <td className="text-center py-2 px-3 font-medium">
                                      {session.total_posts}
                                    </td>
                                    <td className="text-center py-2 px-3">
                                      {session.unique_participants}
                                    </td>
                                    <td className="text-center py-2 px-3">
                                      <span className={
                                        session.participation_rate >= 70 ? 'text-green-600' :
                                        session.participation_rate >= 50 ? 'text-yellow-600' : 'text-red-600'
                                      }>
                                        {session.participation_rate?.toFixed(0)}%
                                      </span>
                                    </td>
                                    <td className="text-center py-2 px-3">
                                      {session.polls_count}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {/* Student Progress */}
                    {selectedCourseId && (
                      <Card>
                        <CardHeader>
                          <CardTitle className="flex items-center gap-2">
                            <Users className="h-5 w-5 text-primary-500" />
                            Student Progress
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <StudentProgressComponent courseId={selectedCourseId} />
                        </CardContent>
                      </Card>
                    )}

                    {/* Voice Command Hints */}
                    <div className="p-4 bg-neutral-50 dark:bg-neutral-800 rounded-lg">
                      <h3 className="font-medium mb-3">Quick Voice Commands</h3>
                      <div className="flex flex-wrap gap-2">
                        {[
                          'Compare the last 5 sessions',
                          'Show course analytics',
                          'How has Maria been doing?',
                          'Who\'s improving?',
                          'Which students need help?'
                        ].map((cmd) => (
                          <span key={cmd} className="px-3 py-1 text-sm bg-white dark:bg-neutral-700 rounded-full text-neutral-600 dark:text-neutral-300 border">
                            "{cmd}"
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </TabsContent>
            </Tabs>
          ) : (
            /* Student view: Only scoring, best practice, what they did well, gaps */
            <Tabs value={activeTab === 'summary' ? 'my-performance' : activeTab} onValueChange={setActiveTab}>
              <TabsList className="border border-neutral-200 dark:border-neutral-800 bg-white/80 dark:bg-neutral-900">
                <TabsTrigger value="my-performance" data-voice-id="tab-my-performance">My Performance</TabsTrigger>
                <TabsTrigger value="best-practice" data-voice-id="tab-best-practice">Best Practice Answer</TabsTrigger>
              </TabsList>

              <TabsContent value="my-performance">{renderStudentPerformance()}</TabsContent>
              <TabsContent value="best-practice">{renderBestPractice()}</TabsContent>
            </Tabs>
          )}
        </div>
      )}
    </div>
  );
}

