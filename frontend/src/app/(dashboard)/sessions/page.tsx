'use client';

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import { Calendar, Play, CheckCircle, Clock, FileEdit, RefreshCw, ChevronRight, FileText, BookOpen, Copy, LayoutTemplate } from 'lucide-react';
import { api } from '@/lib/api';
import { useUser } from '@/lib/context';
import { Course, Session, SessionStatus } from '@/types';
import { formatTimestamp, getStatusColor } from '@/lib/utils';
import { useTranslations } from 'next-intl';
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
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
        // Admin sees all courses
        const data = await api.getCourses(currentUser.id);
        setCourses(data);
        if (data.length > 0 && !selectedCourseId) {
          setSelectedCourseId(data[0].id);
        }
      } else if (isInstructor) {
        // Instructors see only their own courses
        const data = await api.getCourses(currentUser.id);
        setCourses(data);
        if (data.length > 0 && !selectedCourseId) {
          setSelectedCourseId(data[0].id);
        }
      } else {
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
        <p className="text-gray-500 italic">
          {t('sessions.noPlanAvailable')}
        </p>
      );
    }

    return (
      <div className="space-y-4">
        {plan.topics && plan.topics.length > 0 && (
          <div>
            <h4 className="font-medium text-gray-900 mb-2">{t('sessions.topics')}</h4>
            <ul className="text-sm text-gray-600 space-y-1">
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
            <h4 className="font-medium text-gray-900 mb-2">{t('sessions.goals')}</h4>
            <ul className="text-sm text-gray-600 space-y-1">
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
            <h4 className="font-medium text-gray-900 mb-2">{t('sessions.keyConcepts')}</h4>
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
            <h4 className="font-medium text-gray-900 mb-2">{t('sessions.caseStudy')}</h4>
            <div className="bg-blue-50 p-3 rounded-lg text-sm">
              {typeof plan.case === 'string' ? (
                <p>{plan.case}</p>
              ) : (
                <>
                  {plan.case.title && (
                    <p className="font-medium text-blue-900">{plan.case.title}</p>
                  )}
                  <p className="text-blue-800 mt-1">
                    {plan.case.scenario || plan.case.description}
                  </p>
                </>
              )}
            </div>
          </div>
        )}

        {plan.discussion_prompts && plan.discussion_prompts.length > 0 && (
          <div>
            <h4 className="font-medium text-gray-900 mb-2">{t('sessions.discussionPrompts')}</h4>
            <ol className="text-sm text-gray-600 space-y-2 list-decimal list-inside">
              {plan.discussion_prompts.map((prompt, i) => (
                <li key={i}>{prompt}</li>
              ))}
            </ol>
          </div>
        )}

        {/* Developer info hidden from users */}
      </div>
    );
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('sessions.title')}</h1>
          <p className="text-gray-600">{t('sessions.subtitle')}</p>
        </div>
      </div>

      {/* Course Selector */}
      <div className="mb-6">
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
      </div>

      {selectedCourseId && (
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="sessions">{t('sessions.viewSessions')}</TabsTrigger>
            <TabsTrigger value="materials">
              <FileText className="w-4 h-4 mr-1" />
              {t('sessions.materials')}
            </TabsTrigger>
            {hasInstructorPrivileges && <TabsTrigger value="create">{t('sessions.createSession')}</TabsTrigger>}
            {hasInstructorPrivileges && <TabsTrigger value="manage">{t('sessions.manageStatus')}</TabsTrigger>}
            {hasInstructorPrivileges && (
              <TabsTrigger value="insights">
                <BookOpen className="w-4 h-4 mr-1" />
                Insights
              </TabsTrigger>
            )}
          </TabsList>

          <TabsContent value="sessions">
            {loading ? (
              <div className="text-center py-8 text-gray-500">{t('common.loading')}</div>
            ) : sessions.length === 0 ? (
              <Card>
                <CardContent className="py-8 text-center text-gray-500">
                  <Calendar className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                  <p>{t('sessions.noSessions')}</p>
                  <p className="text-sm mt-2">
                    {t('sessions.createOrGenerate')}
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid lg:grid-cols-3 gap-6">
                {/* Session List */}
                <div className="lg:col-span-1">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base">Sessions ({sessions.length})</CardTitle>
                    </CardHeader>
                    <CardContent className="p-0">
                      <div className="divide-y max-h-[500px] overflow-auto">
                        {sessions.map((session) => {
                          const StatusIcon = statusIcons[session.status];
                          const isSelected = selectedSession?.id === session.id;

                          return (
                            <button
                              key={session.id}
                              onClick={() => setSelectedSession(session)}
                              className={`w-full px-4 py-3 text-left hover:bg-gray-50 transition-colors ${
                                isSelected ? 'bg-primary-50 border-l-2 border-primary-600' : ''
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-medium text-sm text-gray-900 truncate">
                                  {session.title}
                                </span>
                                <Badge
                                  variant={
                                    session.status === 'live'
                                      ? 'success'
                                      : session.status === 'completed'
                                      ? 'warning'
                                      : 'default'
                                  }
                                  className="ml-2 flex-shrink-0"
                                >
                                  <StatusIcon className="h-3 w-3 mr-1" />
                                  {session.status}
                                </Badge>
                              </div>
                              <p className="text-xs text-gray-500 mt-1">ID: {session.id}</p>
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
                    <Card>
                      <CardHeader>
                        <div className="flex items-center justify-between">
                          <CardTitle>{selectedSession.title}</CardTitle>
                          <Badge
                            variant={
                              selectedSession.status === 'live'
                                ? 'success'
                                : selectedSession.status === 'completed'
                                ? 'warning'
                                : 'default'
                            }
                          >
                            {selectedSession.status.toUpperCase()}
                          </Badge>
                        </div>
                        <p className="text-sm text-gray-500">
                          Created: {formatTimestamp(selectedSession.created_at)}
                        </p>
                      </CardHeader>
                      <CardContent>{renderPlan(selectedSession)}</CardContent>
                    </Card>
                  ) : (
                    <Card>
                      <CardContent className="py-8 text-center text-gray-500">
                        {t('sessions.selectSession')}
                      </CardContent>
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
                  <h3 className="text-lg font-medium mb-4">
                    Materials for: {selectedSession.title}
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
              <Card>
                <CardHeader>
                  <CardTitle>{t('sessions.createNew')}</CardTitle>
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
              <Card>
                <CardHeader>
                  <CardTitle>{t('sessions.statusControl')}</CardTitle>
                </CardHeader>
                <CardContent>
                  {selectedSession ? (
                    <div className="space-y-4">
                      <div className="flex items-center gap-4">
                        <span className="font-medium">{selectedSession.title}</span>
                        <Badge
                          variant={
                            selectedSession.status === 'live'
                              ? 'success'
                              : selectedSession.status === 'completed'
                              ? 'warning'
                              : 'default'
                          }
                        >
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
                    <p className="text-gray-500">{t('sessions.selectSession')}</p>
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
                      <Card>
                        <CardHeader>
                          <CardTitle className="flex items-center gap-2">
                            <BookOpen className="h-5 w-5 text-blue-500" />
                            Pre-Class Insights
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <PreClassInsightsComponent sessionId={selectedSession.id} />
                        </CardContent>
                      </Card>
                    )}

                    {selectedSession.status === 'completed' && (
                      <Card>
                        <CardHeader>
                          <CardTitle className="flex items-center gap-2">
                            <FileText className="h-5 w-5 text-green-500" />
                            Session Summary
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <PostClassSummaryComponent sessionId={selectedSession.id} />
                        </CardContent>
                      </Card>
                    )}

                    {selectedSession.status === 'live' && (
                      <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg text-center">
                        <Play className="h-8 w-8 mx-auto mb-2 text-yellow-600" />
                        <p className="text-yellow-800 dark:text-yellow-200">
                          Session is currently live. Use the <strong>Console</strong> page for real-time instructor tools.
                        </p>
                        <Button
                          variant="outline"
                          size="sm"
                          className="mt-3"
                          onClick={() => window.location.href = '/console'}
                        >
                          Go to Console
                        </Button>
                      </div>
                    )}

                    {/* Student Progress - always visible */}
                    {selectedCourseId && (
                      <Card>
                        <CardHeader>
                          <CardTitle className="flex items-center gap-2">
                            <Calendar className="h-5 w-5 text-purple-500" />
                            Student Progress
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <StudentProgressComponent courseId={selectedCourseId} />
                        </CardContent>
                      </Card>
                    )}

                    {/* Voice Command Hints */}
                    <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                      <h3 className="font-medium mb-3">Quick Voice Commands</h3>
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
                          <span key={cmd} className="px-3 py-1 text-sm bg-white dark:bg-gray-700 rounded-full text-gray-600 dark:text-gray-300 border">
                            "{cmd}"
                          </span>
                        ))}
                      </div>
                    </div>
                  </>
                ) : (
                  <Card>
                    <CardContent className="py-8 text-center text-gray-500">
                      <BookOpen className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                      <p>Select a session to view insights</p>
                    </CardContent>
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
