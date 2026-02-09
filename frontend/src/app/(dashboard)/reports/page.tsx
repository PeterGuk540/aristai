'use client';

import { useState, useEffect } from 'react';
import {
  FileText,
  RefreshCw,
  Sparkles,
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
import { Course, Session, Report, ReportJSON } from '@/types';
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
} from '@/components/ui';

export default function ReportsPage() {
  const { isInstructor, currentUser } = useUser();
  const t = useTranslations();
  const [courses, setCourses] = useState<Course[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);

  const fetchCourses = async () => {
    try {
      if (isInstructor) {
        const data = await api.getCourses();
        setCourses(data);
        if (data.length > 0 && !selectedCourseId) {
          setSelectedCourseId(data[0].id);
        }
      } else if (currentUser) {
        // Students only see courses they're enrolled in
        const enrolledCourses = await api.getUserEnrolledCourses(currentUser.id);
        const coursePromises = enrolledCourses.map((ec: any) => api.getCourse(ec.course_id));
        const fullCourses = await Promise.all(coursePromises);
        setCourses(fullCourses);
        if (fullCourses.length > 0 && !selectedCourseId) {
          setSelectedCourseId(fullCourses[0].id);
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
      if (completedSessions.length > 0) {
        setSelectedSessionId(completedSessions[0].id);
      } else {
        setSelectedSessionId(null);
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

  useEffect(() => {
    if (currentUser) {
      fetchCourses();
    }
  }, [currentUser, isInstructor]);

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
        <Card>
          <CardContent className="py-8 text-center text-gray-500">
            <Users className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p>Participation data not available.</p>
          </CardContent>
        </Card>
      );
    }

    const { participation } = reportJson;
    const rate = participation.participation_rate || 0;

    return (
      <div className="space-y-4">
        {/* Summary Stats */}
        <div className="grid grid-cols-3 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-center">
                <Users className="h-8 w-8 mx-auto text-blue-500 mb-2" />
                <p className="text-2xl font-bold">{participation.total_enrolled_students}</p>
                <p className="text-sm text-gray-500">Enrolled Students</p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="text-center">
                <CheckCircle className="h-8 w-8 mx-auto text-green-500 mb-2" />
                <p className="text-2xl font-bold">{participation.participation_count}</p>
                <p className="text-sm text-gray-500">Participated</p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="text-center">
                <BarChart3 className="h-8 w-8 mx-auto text-purple-500 mb-2" />
                <p className="text-2xl font-bold">{rate.toFixed(1)}%</p>
                <p className="text-sm text-gray-500">Participation Rate</p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Participated */}
        {participation.students_who_participated &&
          participation.students_who_participated.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <CheckCircle className="h-5 w-5 text-green-500" />
                  Students Who Participated ({participation.students_who_participated.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-2">
                  {participation.students_who_participated.map((student) => (
                    <div
                      key={student.user_id}
                      className="flex items-center justify-between bg-green-50 px-3 py-2 rounded"
                    >
                      <span className="text-sm text-gray-700">{student.name}</span>
                      <Badge variant="success">{student.post_count} posts</Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

        {/* Did Not Participate */}
        {participation.students_who_did_not_participate &&
          participation.students_who_did_not_participate.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <XCircle className="h-5 w-5 text-red-500" />
                  Students Who Did Not Participate (
                  {participation.students_who_did_not_participate.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-2">
                  {participation.students_who_did_not_participate.map((student) => (
                    <div
                      key={student.user_id}
                      className="flex items-center bg-red-50 px-3 py-2 rounded"
                    >
                      <span className="text-sm text-gray-700">{student.name}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
      </div>
    );
  };

  const renderScoring = () => {
    if (!reportJson?.answer_scores) {
      return (
        <Card>
          <CardContent className="py-8 text-center text-gray-500">
            <Award className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p>Scoring data not available.</p>
          </CardContent>
        </Card>
      );
    }

    const { answer_scores } = reportJson;

    return (
      <div className="space-y-4">
        {/* Statistics */}
        {answer_scores.class_statistics && (
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <BarChart3 className="h-8 w-8 mx-auto text-blue-500 mb-2" />
                  <p className="text-2xl font-bold">
                    {answer_scores.class_statistics.average_score.toFixed(1)}
                  </p>
                  <p className="text-sm text-gray-500">Average Score</p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <TrendingUp className="h-8 w-8 mx-auto text-green-500 mb-2" />
                  <p className="text-2xl font-bold">
                    {answer_scores.class_statistics.highest_score.toFixed(1)}
                  </p>
                  <p className="text-sm text-gray-500">Highest Score</p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <TrendingDown className="h-8 w-8 mx-auto text-red-500 mb-2" />
                  <p className="text-2xl font-bold">
                    {answer_scores.class_statistics.lowest_score.toFixed(1)}
                  </p>
                  <p className="text-sm text-gray-500">Lowest Score</p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Top Performers */}
        <div className="grid md:grid-cols-2 gap-4">
          {answer_scores.closest_to_correct && (
            <Card className="border-green-200 bg-green-50">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <Award className="h-5 w-5 text-green-600" />
                  Closest to Correct
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="font-medium text-green-900">
                  {answer_scores.closest_to_correct.user_name ||
                    `User #${answer_scores.closest_to_correct.user_id}`}
                </p>
                <p className="text-sm text-green-700">
                  Score: {answer_scores.closest_to_correct.score.toFixed(1)} / 100
                </p>
              </CardContent>
            </Card>
          )}

          {answer_scores.furthest_from_correct && (
            <Card className="border-red-200 bg-red-50">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-red-600" />
                  Needs Attention
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="font-medium text-red-900">
                  {answer_scores.furthest_from_correct.user_name ||
                    `User #${answer_scores.furthest_from_correct.user_id}`}
                </p>
                <p className="text-sm text-red-700">
                  Score: {answer_scores.furthest_from_correct.score.toFixed(1)} / 100
                </p>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Individual Scores */}
        {answer_scores.student_scores && answer_scores.student_scores.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">All Student Scores</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {answer_scores.student_scores
                  .sort((a, b) => b.score - a.score)
                  .map((score, index) => (
                    <div
                      key={`${score.user_id}-${score.post_id}`}
                      className="border rounded-lg p-3"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium">
                          #{index + 1} {score.user_name || `User #${score.user_id}`}
                        </span>
                        <Badge
                          variant={
                            score.score >= 80
                              ? 'success'
                              : score.score >= 60
                              ? 'warning'
                              : 'error'
                          }
                        >
                          {score.score.toFixed(1)} / 100
                        </Badge>
                      </div>

                      {/* Score bar */}
                      <div className="h-2 bg-gray-200 rounded-full overflow-hidden mb-2">
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

                      {score.key_points_covered && score.key_points_covered.length > 0 && (
                        <div className="text-sm mb-1">
                          <span className="text-green-600 font-medium">Covered: </span>
                          <span className="text-gray-600">
                            {score.key_points_covered.join(', ')}
                          </span>
                        </div>
                      )}

                      {score.missing_points && score.missing_points.length > 0 && (
                        <div className="text-sm mb-1">
                          <span className="text-red-600 font-medium">Missing: </span>
                          <span className="text-gray-600">
                            {score.missing_points.join(', ')}
                          </span>
                        </div>
                      )}

                      {score.feedback && (
                        <p className="text-sm text-gray-500 mt-2 italic">{score.feedback}</p>
                      )}
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>
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
                  <p className="text-sm text-gray-500">Total Posts</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-blue-600">
                    {reportJson.summary.student_posts}
                  </p>
                  <p className="text-sm text-gray-500">Student Posts</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-green-600">
                    {reportJson.summary.instructor_posts}
                  </p>
                  <p className="text-sm text-gray-500">Instructor Posts</p>
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
                  <p className="text-sm text-gray-500 mt-1">Quality</p>
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
                  <div key={i} className="bg-gray-50 p-3 rounded-lg">
                    <h4 className="font-medium text-gray-900">{cluster.theme}</h4>
                    <p className="text-sm text-gray-600 mt-1">{cluster.description}</p>
                    <p className="text-xs text-gray-400 mt-2">
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
                      <p className="font-medium text-gray-900">{obj.objective}</p>
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
              <p className="text-gray-800">{reportJson.best_practice_answer.summary}</p>
              {reportJson.best_practice_answer.detailed_explanation && (
                <p className="text-sm text-gray-600">
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
      return (
        <Card>
          <CardContent className="py-8 text-center text-gray-500">
            <Award className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p>Your performance data is not available yet.</p>
          </CardContent>
        </Card>
      );
    }

    const { answer_scores } = reportJson;
    // For now, show all scores - in a real app, you'd filter by current user ID
    const studentScores = answer_scores.student_scores || [];

    if (studentScores.length === 0) {
      return (
        <Card>
          <CardContent className="py-8 text-center text-gray-500">
            <Award className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p>No performance data found for this session.</p>
          </CardContent>
        </Card>
      );
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
                      : 'error'
                  }
                  className="text-lg px-4 py-1"
                >
                  {score.score.toFixed(1)} / 100
                </Badge>
              </div>

              {/* Score bar */}
              <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
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
                <div className="bg-blue-50 p-4 rounded-lg">
                  <h4 className="font-medium text-blue-800 mb-2">Feedback</h4>
                  <p className="text-blue-700">{score.feedback}</p>
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
      return (
        <Card>
          <CardContent className="py-8 text-center text-gray-500">
            <BookOpen className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p>Best practice answer is not available yet.</p>
          </CardContent>
        </Card>
      );
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
              <p className="text-gray-800 font-medium">{best_practice_answer.summary}</p>
            </div>

            {best_practice_answer.detailed_explanation && (
              <div>
                <h4 className="font-medium text-gray-700 mb-2">Detailed Explanation</h4>
                <p className="text-gray-600">{best_practice_answer.detailed_explanation}</p>
              </div>
            )}

            {best_practice_answer.key_concepts && best_practice_answer.key_concepts.length > 0 && (
              <div>
                <h4 className="font-medium text-gray-700 mb-2">Key Concepts</h4>
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
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('reports.title')}</h1>
          <p className="text-gray-600">{t('reports.subtitle')}</p>
        </div>
      </div>

      {/* Course & Session Selector */}
      <div className="grid md:grid-cols-2 gap-4 mb-6">
        <Select
          label={t('courses.selectCourse')}
          value={selectedCourseId?.toString() || ''}
          onChange={(e) => setSelectedCourseId(Number(e.target.value))}
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
          onChange={(e) => setSelectedSessionId(Number(e.target.value))}
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

      {!selectedSessionId ? (
        <Card>
          <CardContent className="py-8 text-center text-gray-500">
            <FileText className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p>{t('reports.generateFirst')}</p>
          </CardContent>
        </Card>
      ) : loading ? (
        <div className="text-center py-8 text-gray-500">{t('common.loading')}</div>
      ) : !report ? (
        <Card>
          <CardContent className="py-8 text-center">
            <FileText className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p className="text-gray-500 mb-4">{t('reports.noReport')}</p>
            {isInstructor && (
              <Button onClick={handleGenerateReport} disabled={generating} data-voice-id="generate-report">
                <Sparkles className="h-4 w-4 mr-2" />
                {generating ? t('common.loading') : t('reports.generateReport')}
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div>
          {/* Report Header */}
          <Card className="mb-6">
            <CardContent className="py-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">
                    Report for: {reportJson?.session_title || `Session #${report.session_id}`}
                  </h2>
                  <p className="text-sm text-gray-500">
                    Generated: {formatTimestamp(report.created_at)} | Version: {report.version}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button onClick={fetchReport} variant="outline" size="sm" data-voice-id="refresh-report">
                    <RefreshCw className="h-4 w-4 mr-2" />
                    {t('reports.refreshReport')}
                  </Button>
                  {isInstructor && (
                    <Button onClick={handleGenerateReport} size="sm" disabled={generating} data-voice-id="regenerate-report">
                      <Sparkles className="h-4 w-4 mr-2" />
                      {t('reports.regenerateReport')}
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Report Tabs - Different views for instructors vs students */}
          {isInstructor ? (
            <Tabs defaultValue="summary">
              <TabsList>
                <TabsTrigger value="summary">{t('reports.summary')}</TabsTrigger>
                <TabsTrigger value="participation">{t('reports.participation')}</TabsTrigger>
                <TabsTrigger value="scoring">{t('reports.answerScores')}</TabsTrigger>
              </TabsList>

              <TabsContent value="summary">{renderSummary()}</TabsContent>
              <TabsContent value="participation">{renderParticipation()}</TabsContent>
              <TabsContent value="scoring">{renderScoring()}</TabsContent>
            </Tabs>
          ) : (
            /* Student view: Only scoring, best practice, what they did well, gaps */
            <Tabs defaultValue="my-performance">
              <TabsList>
                <TabsTrigger value="my-performance">My Performance</TabsTrigger>
                <TabsTrigger value="best-practice">Best Practice Answer</TabsTrigger>
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
