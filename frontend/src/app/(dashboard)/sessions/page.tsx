'use client';

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import { Calendar, Play, CheckCircle, Clock, FileEdit, RefreshCw, ChevronRight, FileText, BookOpen, Copy, LayoutTemplate } from 'lucide-react';
import { api } from '@/lib/api';
import { useUser } from '@/lib/context';
import { Course, Session, SessionStatus } from '@/types';
import { formatTimestamp } from '@/lib/utils';
import { useTranslations } from 'next-intl';
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  Select,
  Input,
  Badge,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from '@/components/ui';
import MaterialsManager from '@/components/materials/MaterialsManager';

// Instructor enhancement components
import { PreClassInsightsComponent } from '@/components/instructor/PreClassInsights';
import { PostClassSummaryComponent } from '@/components/instructor/PostClassSummary';
import { StudentProgressComponent } from '@/components/instructor/StudentProgress';

const statusIcons: Record<SessionStatus, any> = {
  draft: FileEdit,
  scheduled: Clock,
  live: Play,
  completed: CheckCircle,
};

const statusColors: Record<SessionStatus, 'default' | 'primary' | 'success' | 'warning' | 'danger'> = {
  draft: 'default',
  scheduled: 'primary',
  live: 'success',
  completed: 'warning',
};

export default function SessionsPage() {
  const { isInstructor, isAdmin, currentUser } = useUser();
  // Admins have same privileges as instructors
  const hasInstructorPrivileges = isInstructor || isAdmin;
  const searchParams = useSearchParams();
  const t = useTranslations();
  const [courses, setCourses] = useState<Course[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  const [selectedSession, setSelectedSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  // Tab state - default from URL query param
  const [activeTab, setActiveTab] = useState(searchParams?.get('tab') || 'sessions');

  // Create session form
  const [newSessionTitle, setNewSessionTitle] = useState('');
  const [creating, setCreating] = useState(false);

  // Handle voice-triggered tab selection
  const handleVoiceSelectTab = useCallback((event: CustomEvent) => {
    const { tab } = event.detail || {};
    if (tab) {
      setActiveTab(tab);
    }
  }, []);

  // Listen for voice tab selection events
  useEffect(() => {
    window.addEventListener('voice-select-tab', handleVoiceSelectTab as EventListener);
    return () => {
      window.removeEventListener('voice-select-tab', handleVoiceSelectTab as EventListener);
    };
  }, [handleVoiceSelectTab]);

  // Update tab when URL changes
  useEffect(() => {
    const tabFromUrl = searchParams?.get('tab');
    if (tabFromUrl) {
      setActiveTab(tabFromUrl);
    }
  }, [searchParams]);

  const fetchCourses = async () => {
    try {
      if (!currentUser) return;

      if (isAdmin) {
        const data = await api.getCourses(currentUser.id);
        setCourses(data);
        if (data.length > 0 && !selectedCourseId) {
          setSelectedCourseId(data[0].id);
        }
      } else if (isInstructor) {
        const data = await api.getCourses(currentUser.id);
        setCourses(data);
        if (data.length > 0 && !selectedCourseId) {
          setSelectedCourseId(data[0].id);
        }
      } else {
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
      setLoading(true);
      const data = await api.getCourseSessions(courseId);
      setSessions(data);
      if (data.length > 0) {
        setSelectedSession(data[0]);
      } else {
        setSelectedSession(null);
      }
    } catch (error) {
      console.error('Failed to fetch sessions:', error);
    } finally {
      setLoading(false);
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

  const handleCreateSession = async () => {
    if (!selectedCourseId || !newSessionTitle.trim()) return;

    setCreating(true);
    try {
      await api.createSession({
        course_id: selectedCourseId,
        title: newSessionTitle,
      });
      setNewSessionTitle('');
      fetchSessions(selectedCourseId);
    } catch (error) {
      console.error('Failed to create session:', error);
      alert('Failed to create session');
    } finally {
      setCreating(false);
    }
  };

  const handleStatusChange = async (sessionId: number, newStatus: SessionStatus) => {
    try {
      await api.updateSessionStatus(sessionId, newStatus);
      if (selectedCourseId) {
        fetchSessions(selectedCourseId);
      }
    } catch (error) {
      console.error('Failed to update status:', error);
      alert('Failed to update session status');
    }
  };

  const renderPlan = (session: Session) => {
    const plan = session.plan_json;
    if (!plan) {
      return (
        <p className="text-neutral-500 dark:text-neutral-400 italic">
          {t('sessions.noPlanAvailable')}
        </p>
      );
    }

    return (
      <div className="space-y-5">
        {plan.topics && plan.topics.length > 0 && (
          <div>
            <h4 className="font-semibold text-neutral-900 dark:text-white mb-2">{t('sessions.topics')}</h4>
            <ul className="text-sm text-neutral-600 dark:text-neutral-400 space-y-1.5">
              {plan.topics.map((topic, i) => (
                <li key={i} className="flex items-start gap-2">
                  <ChevronRight className="h-4 w-4 text-primary-500 mt-0.5 flex-shrink-0" />
                  {topic}
                </li>
              ))}
            </ul>
          </div>
        )}

        {plan.goals && (
          <div>
            <h4 className="font-semibold text-neutral-900 dark:text-white mb-2">{t('sessions.goals')}</h4>
            <ul className="text-sm text-neutral-600 dark:text-neutral-400 space-y-1.5">
              {(Array.isArray(plan.goals) ? plan.goals : [plan.goals]).map((goal, i) => (
                <li key={i} className="flex items-start gap-2">
                  <ChevronRight className="h-4 w-4 text-primary-500 mt-0.5 flex-shrink-0" />
                  {goal}
                </li>
              ))}
            </ul>
          </div>
        )}

        {plan.key_concepts && plan.key_concepts.length > 0 && (
          <div>
            <h4 className="font-semibold text-neutral-900 dark:text-white mb-2">{t('sessions.keyConcepts')}</h4>
            <div className="flex flex-wrap gap-2">
              {plan.key_concepts.map((concept, i) => (
                <Badge key={i} variant="info">
                  {concept}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {plan.case && (
          <div>
            <h4 className="font-semibold text-neutral-900 dark:text-white mb-2">{t('sessions.caseStudy')}</h4>
            <div className="bg-primary-50 dark:bg-primary-900/30 p-4 rounded-xl text-sm border border-primary-100 dark:border-primary-800">
              {typeof plan.case === 'string' ? (
                <p className="text-primary-800 dark:text-primary-200">{plan.case}</p>
              ) : (
                <>
                  {plan.case.title && (
                    <p className="font-medium text-primary-900 dark:text-primary-100">{plan.case.title}</p>
                  )}
                  <p className="text-primary-700 dark:text-primary-300 mt-1">
                    {plan.case.scenario || plan.case.description}
                  </p>
                </>
              )}
            </div>
          </div>
        )}

        {plan.discussion_prompts && plan.discussion_prompts.length > 0 && (
          <div>
            <h4 className="font-semibold text-neutral-900 dark:text-white mb-2">{t('sessions.discussionPrompts')}</h4>
            <ol className="text-sm text-neutral-600 dark:text-neutral-400 space-y-2 list-decimal list-inside">
              {plan.discussion_prompts.map((prompt, i) => (
                <li key={i}>{prompt}</li>
              ))}
            </ol>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-8 max-w-6xl pb-4">
      {/* Page Header */}
      <div className="flex items-center justify-between rounded-2xl border border-emerald-200/80 dark:border-primary-900/20 bg-white dark:bg-[#1a150c] px-6 py-5 shadow-sm">
        <div>
          <h1 className="text-3xl font-bold text-neutral-900 dark:text-white tracking-tight">{t('sessions.title')}</h1>
          <p className="text-neutral-600 dark:text-neutral-400 mt-1">{t('sessions.subtitle')}</p>
        </div>
      </div>

      {/* Course Selector */}
      <Card variant="default" padding="md" className="border-neutral-200 dark:border-primary-900/20 bg-white dark:bg-[#1a150c]">
        <Select
          label={t('courses.selectCourse')}
          value={selectedCourseId?.toString() || ''}
          onChange={(e) => setSelectedCourseId(Number(e.target.value))}
          data-voice-id="select-course"
        >
          <option value="">Select a course...</option>
          {courses.map((course) => (
            <option key={course.id} value={course.id}>
              {course.title} (ID: {course.id})
            </option>
          ))}
        </Select>
      </Card>

      {selectedCourseId && (
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="border border-neutral-200 dark:border-primary-900/20 bg-white dark:bg-[#1a150c] rounded-xl">
            <TabsTrigger value="sessions">{t('sessions.viewSessions')}</TabsTrigger>
            <TabsTrigger value="materials">
              <FileText className="w-4 h-4 mr-1.5" />
              {t('sessions.materials')}
            </TabsTrigger>
            {hasInstructorPrivileges && <TabsTrigger value="create">{t('sessions.createSession')}</TabsTrigger>}
            {hasInstructorPrivileges && <TabsTrigger value="manage">{t('sessions.manageStatus')}</TabsTrigger>}
            {hasInstructorPrivileges && (
              <TabsTrigger value="insights">
                Insights
              </TabsTrigger>
            )}
          </TabsList>

          <TabsContent value="sessions">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="flex flex-col items-center gap-3">
                  <div className="relative">
                    <div className="w-10 h-10 rounded-full border-4 border-primary-100 dark:border-primary-900"></div>
                    <div className="absolute top-0 left-0 w-10 h-10 rounded-full border-4 border-primary-600 border-t-transparent animate-spin"></div>
                  </div>
                  <p className="text-sm text-neutral-500 dark:text-neutral-400">{t('common.loading')}</p>
                </div>
              </div>
            ) : sessions.length === 0 ? (
              <Card variant="default" padding="lg">
                <div className="text-center py-8">
                  <div className="p-4 rounded-2xl bg-primary-50 dark:bg-primary-900/30 w-fit mx-auto mb-4">
                    <Calendar className="h-10 w-10 text-primary-600 dark:text-primary-400" />
                  </div>
                  <p className="text-neutral-600 dark:text-neutral-400">{t('sessions.noSessions')}</p>
                  <p className="text-sm text-neutral-500 dark:text-neutral-500 mt-2">
                    {t('sessions.createOrGenerate')}
                  </p>
                </div>
              </Card>
            ) : (
              <div className="grid lg:grid-cols-3 gap-6">
                {/* Session List */}
                <div className="lg:col-span-1">
                  <Card variant="default">
                    <CardHeader>
                      <CardTitle className="text-base">Sessions in this course</CardTitle>
                      <CardDescription>{sessions.length} total sessions</CardDescription>
                    </CardHeader>
                    <CardContent className="p-0">
                      <div className="divide-y divide-neutral-200 dark:divide-neutral-700 max-h-[500px] overflow-auto">
                        {sessions.map((session) => {
                          const StatusIcon = statusIcons[session.status];
                          const isSelected = selectedSession?.id === session.id;

                          return (
                            <button
                              key={session.id}
                              onClick={() => setSelectedSession(session)}
                              className={`w-full px-4 py-3.5 text-left hover:bg-neutral-50 dark:hover:bg-neutral-700/50 transition-colors ${
                                isSelected ? 'bg-primary-50 dark:bg-primary-900/30 border-l-3 border-primary-600' : ''
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-medium text-sm text-neutral-900 dark:text-white truncate">
                                  {session.title}
                                </span>
                                <Badge
                                  variant={statusColors[session.status]}
                                  size="sm"
                                  className="ml-2 flex-shrink-0"
                                >
                                  <StatusIcon className="h-3 w-3 mr-1" />
                                  {session.status}
                                </Badge>
                              </div>
                              <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">ID: {session.id}</p>
                            </button>
                          );
                        })}
                      </div>
                    </CardContent>
                  </Card>
                </div>

                {/* Session Details */}
                <div className="lg:col-span-2">
                  {selectedSession ? (
                    <Card variant="default">
                      <CardHeader>
                        <div className="flex items-center justify-between">
                          <CardTitle>{selectedSession.title}</CardTitle>
                          <Badge variant={statusColors[selectedSession.status]}>
                            {selectedSession.status.toUpperCase()}
                          </Badge>
                        </div>
                        <CardDescription>
                          Created: {formatTimestamp(selectedSession.created_at)}
                        </CardDescription>
                      </CardHeader>
                      <CardContent>{renderPlan(selectedSession)}</CardContent>
                    </Card>
                  ) : (
                    <Card variant="default" padding="lg">
                      <div className="text-center py-8 text-neutral-500 dark:text-neutral-400">
                        {t('sessions.selectSession')}
                      </div>
                    </Card>
                  )}
                </div>
              </div>
            )}
          </TabsContent>

          <TabsContent value="materials">
            <div className="space-y-6">
              {/* Course-wide materials */}
              <MaterialsManager
                courseId={selectedCourseId}
                isInstructor={hasInstructorPrivileges}
                userId={currentUser?.id}
              />

              {/* Session-specific materials */}
              {selectedSession && selectedSession.plan_json?.is_materials_session !== true && (
                <div className="mt-6">
                  <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4">
                    Session materials: {selectedSession.title}
                  </h3>
                  <MaterialsManager
                    courseId={selectedCourseId}
                    sessionId={selectedSession.id}
                    isInstructor={hasInstructorPrivileges}
                    userId={currentUser?.id}
                  />
                </div>
              )}
            </div>
          </TabsContent>

          {hasInstructorPrivileges && (
            <TabsContent value="create">
              <Card variant="default">
                <CardHeader>
                  <CardTitle>{t('sessions.createNew')}</CardTitle>
                  <CardDescription>Add a new session title to your course plan.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <Input
                    label={t('sessions.sessionTitle')}
                    placeholder={t('sessions.sessionTitlePlaceholder')}
                    value={newSessionTitle}
                    onChange={(e) => setNewSessionTitle(e.target.value)}
                  />
                  <Button
                    onClick={handleCreateSession}
                    disabled={creating || !newSessionTitle.trim()}
                    data-voice-id="create-session"
                  >
                    {t('sessions.createSession')}
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>
          )}

          {hasInstructorPrivileges && (
            <TabsContent value="manage">
              <Card variant="default">
                <CardHeader>
                  <CardTitle>{t('sessions.statusControl')}</CardTitle>
                  <CardDescription>Update lifecycle state for the selected session.</CardDescription>
                </CardHeader>
                <CardContent>
                  {selectedSession ? (
                    <div className="space-y-4">
                      <div className="flex items-center gap-4 p-4 bg-neutral-50 dark:bg-neutral-800/50 rounded-xl">
                        <span className="font-medium text-neutral-900 dark:text-white">{selectedSession.title}</span>
                        <Badge variant={statusColors[selectedSession.status]}>
                          {t(`sessions.status.${selectedSession.status}`)}
                        </Badge>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        {selectedSession.status !== 'draft' && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleStatusChange(selectedSession.id, 'draft')}
                            data-voice-id="set-to-draft"
                          >
                            {t('sessions.setToDraft')}
                          </Button>
                        )}
                        {selectedSession.status === 'draft' && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleStatusChange(selectedSession.id, 'scheduled')}
                            data-voice-id="schedule-session"
                          >
                            {t('sessions.schedule')}
                          </Button>
                        )}
                        {(selectedSession.status === 'draft' ||
                          selectedSession.status === 'scheduled') && (
                          <Button
                            size="sm"
                            onClick={() => handleStatusChange(selectedSession.id, 'live')}
                            data-voice-id="go-live"
                          >
                            <Play className="h-4 w-4 mr-2" />
                            {t('sessions.goLive')}
                          </Button>
                        )}
                        {selectedSession.status === 'live' && (
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleStatusChange(selectedSession.id, 'completed')}
                            data-voice-id="complete-session"
                          >
                            <CheckCircle className="h-4 w-4 mr-2" />
                            {t('sessions.complete')}
                          </Button>
                        )}
                      </div>
                    </div>
                  ) : (
                    <p className="text-neutral-500 dark:text-neutral-400">{t('sessions.selectSession')}</p>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          )}

          {hasInstructorPrivileges && (
            <TabsContent value="insights">
              <div className="space-y-6">
                {selectedSession ? (
                  <>
                    {/* Pre-Class / Post-Class based on session status */}
                    {(selectedSession.status === 'draft' || selectedSession.status === 'scheduled') && (
                      <Card variant="default">
                        <CardHeader>
                          <CardTitle>Pre-Class Insights</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <PreClassInsightsComponent sessionId={selectedSession.id} />
                        </CardContent>
                      </Card>
                    )}

                    {selectedSession.status === 'completed' && (
                      <Card variant="default">
                        <CardHeader>
                          <CardTitle className="flex items-center gap-2">
                            <div className="p-1.5 rounded-lg bg-success-100 dark:bg-success-900/50">
                              <FileText className="h-4 w-4 text-success-600 dark:text-success-400" />
                            </div>
                            Session Summary
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <PostClassSummaryComponent sessionId={selectedSession.id} />
                        </CardContent>
                      </Card>
                    )}

                    {selectedSession.status === 'live' && (
                      <Card variant="ghost" padding="md" className="bg-warning-50 dark:bg-warning-900/20 border border-warning-200 dark:border-warning-800">
                        <div className="text-center py-4">
                          <div className="p-3 rounded-xl bg-warning-100 dark:bg-warning-800/50 w-fit mx-auto mb-3">
                            <Play className="h-8 w-8 text-warning-600 dark:text-warning-400" />
                          </div>
                          <p className="text-warning-800 dark:text-warning-200">
                            Session is currently live. Use the <strong>Console</strong> page for real-time instructor tools.
                          </p>
                          <Button
                            variant="outline"
                            size="sm"
                            className="mt-4"
                            onClick={() => window.location.href = '/console'}
                          >
                            Go to Console
                          </Button>
                        </div>
                      </Card>
                    )}

                    {/* Student Progress - always visible */}
                    {selectedCourseId && (
                      <Card variant="default">
                        <CardHeader>
                          <CardTitle className="flex items-center gap-2">
                            <div className="p-1.5 rounded-lg bg-info-100 dark:bg-info-900/50">
                              <Calendar className="h-4 w-4 text-info-600 dark:text-info-400" />
                            </div>
                            Student Progress
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <StudentProgressComponent courseId={selectedCourseId} />
                        </CardContent>
                      </Card>
                    )}

                    {/* Voice Command Hints */}
                    <Card variant="ghost" padding="md">
                      <h3 className="font-semibold text-neutral-900 dark:text-white mb-3">Quick Voice Commands</h3>
                      <div className="flex flex-wrap gap-2">
                        {[
                          'Pre-class completion status',
                          'Who didn\'t do the homework?',
                          'Generate session summary',
                          'Send summary to students',
                          'How has Maria been doing?',
                          'Save this as a template',
                          'Clone this session'
                        ].map((cmd) => (
                          <span key={cmd} className="px-3 py-1.5 text-sm bg-white dark:bg-neutral-700 rounded-full text-neutral-600 dark:text-neutral-300 border border-neutral-200 dark:border-neutral-600">
                            "{cmd}"
                          </span>
                        ))}
                      </div>
                    </Card>
                  </>
                ) : (
                  <Card variant="default" padding="lg">
                    <div className="text-center py-8">
                      <div className="p-4 rounded-2xl bg-primary-50 dark:bg-primary-900/30 w-fit mx-auto mb-4">
                        <BookOpen className="h-10 w-10 text-primary-600 dark:text-primary-400" />
                      </div>
                      <p className="text-neutral-600 dark:text-neutral-400">Select a session to view insights</p>
                    </div>
                  </Card>
                )}
              </div>
            </TabsContent>
          )}
        </Tabs>
      )}
    </div>
  );
}
