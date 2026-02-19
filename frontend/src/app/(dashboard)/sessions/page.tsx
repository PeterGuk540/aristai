'use client';

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import { Calendar, Play, CheckCircle, Clock, FileEdit, RefreshCw, ChevronRight, FileText, BookOpen, Copy, LayoutTemplate, Send, Megaphone, ClipboardList, Pencil, Trash2, X } from 'lucide-react';
import { api } from '@/lib/api';
import { useUser } from '@/lib/context';
import { useSharedCourseSessionSelection } from '@/lib/shared-selection';
import { createVoiceTabHandler, setupVoiceTabListeners, mergeTabMappings } from '@/lib/voice-tab-handler';
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
  Textarea,
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

// Enhanced AI Features
import { LiveSummaryComponent } from '@/components/enhanced/LiveSummary';
import { QuestionBankComponent } from '@/components/enhanced/QuestionBank';
import { PeerReviewPanelComponent } from '@/components/enhanced/PeerReviewPanel';

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
  const {
    selectedCourseId,
    setSelectedCourseId,
    selectedSessionId,
    setSelectedSessionId,
  } = useSharedCourseSessionSelection();
  const [selectedSession, setSelectedSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  // Tab state - default from URL query param
  const [activeTab, setActiveTab] = useState(searchParams?.get('tab') || 'sessions');

  // Create session form
  const [newSessionTitle, setNewSessionTitle] = useState('');
  const [creating, setCreating] = useState(false);

  // Edit/Delete session state
  const [editingSession, setEditingSession] = useState<Session | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editDiscussionPrompts, setEditDiscussionPrompts] = useState('');
  const [editCaseScenario, setEditCaseScenario] = useState('');
  const [editGoals, setEditGoals] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Canvas push state
  const [canvasMappings, setCanvasMappings] = useState<Array<{
    connection_id: number;
    connection_label: string;
    api_base_url: string;
    has_mapping: boolean;
    external_course_id?: string;
    external_course_name?: string;
  }>>([]);
  const [selectedCanvasConnection, setSelectedCanvasConnection] = useState<number | null>(null);
  const [pushType, setPushType] = useState<'announcement' | 'assignment'>('announcement');
  const [pushing, setPushing] = useState(false);
  const [pushMessage, setPushMessage] = useState<string | null>(null);
  const [pushHistory, setPushHistory] = useState<Array<{
    id: number;
    push_type: string;
    title: string;
    status: string;
    external_id?: string;
    created_at: string;
  }>>([]);

  // Sessions page tab mappings
  const sessionsTabMap = mergeTabMappings({
    'sessions': 'sessions',
    'session': 'sessions',
    'viewsessions': 'sessions',
    'list': 'sessions',
    'create': 'create',
    'creation': 'create',
    'createsession': 'create',
    'newsession': 'create',
    'manage': 'manage',
    'management': 'manage',
    'managestatus': 'manage',
    'status': 'manage',
    'sessionstatus': 'manage',
    'statuscontrol': 'manage',
  });

  // Voice tab handler
  const handleVoiceSelectTab = useCallback(
    createVoiceTabHandler(sessionsTabMap, setActiveTab, 'Sessions'),
    []
  );

  // Set up voice tab listeners
  useEffect(() => {
    return setupVoiceTabListeners(handleVoiceSelectTab);
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
        if (data.length > 0 && (!selectedCourseId || !data.some((course) => course.id === selectedCourseId))) {
          setSelectedCourseId(data[0].id);
        } else if (data.length === 0) {
          setSelectedCourseId(null);
        }
      } else if (isInstructor) {
        const data = await api.getCourses(currentUser.id);
        setCourses(data);
        if (data.length > 0 && (!selectedCourseId || !data.some((course) => course.id === selectedCourseId))) {
          setSelectedCourseId(data[0].id);
        } else if (data.length === 0) {
          setSelectedCourseId(null);
        }
      } else {
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
      setLoading(true);
      const data = await api.getCourseSessions(courseId);
      setSessions(data);
      if (data.length > 0) {
        const nextSession =
          (selectedSessionId && data.find((session) => session.id === selectedSessionId)) || data[0];
        setSelectedSession(nextSession);
        setSelectedSessionId(nextSession.id);
      } else {
        setSelectedSession(null);
        setSelectedSessionId(null);
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

  useEffect(() => {
    if (!selectedSessionId) {
      setSelectedSession(null);
      return;
    }
    const matched = sessions.find((session) => session.id === selectedSessionId);
    if (matched) {
      setSelectedSession(matched);
    }
  }, [selectedSessionId, sessions]);

  // Fetch Canvas mappings and push history when session is selected
  useEffect(() => {
    if (selectedSession && hasInstructorPrivileges) {
      // Fetch canvas mappings
      api.getCanvasMappingsForSession(selectedSession.id)
        .then(mappings => {
          setCanvasMappings(mappings);
          // Auto-select first connection with a mapping
          const withMapping = mappings.find(m => m.has_mapping);
          if (withMapping) {
            setSelectedCanvasConnection(withMapping.connection_id);
          }
        })
        .catch(err => console.error('Failed to fetch canvas mappings:', err));

      // Fetch push history
      api.getCanvasPushHistory(selectedSession.id)
        .then(history => setPushHistory(history))
        .catch(err => console.error('Failed to fetch push history:', err));
    }
  }, [selectedSession, hasInstructorPrivileges]);

  const handlePushToCanvas = async () => {
    if (!selectedSession || !selectedCanvasConnection) return;

    const mapping = canvasMappings.find(m => m.connection_id === selectedCanvasConnection);
    if (!mapping || !mapping.external_course_id) {
      setPushMessage('No Canvas course mapping found. Please set up the mapping in Integrations first.');
      return;
    }

    setPushing(true);
    setPushMessage(null);

    try {
      const result = await api.pushSessionToCanvas(selectedSession.id, {
        connection_id: selectedCanvasConnection,
        external_course_id: mapping.external_course_id,
        push_type: pushType,
      });

      setPushMessage(`Push started! Job #${result.push_id} is processing...`);

      // Poll for completion
      const pollForCompletion = async () => {
        try {
          const status = await api.getCanvasPushStatus(result.push_id);
          if (status.status === 'completed') {
            setPushMessage(`Success! ${pushType === 'announcement' ? 'Announcement' : 'Assignment'} "${status.title}" created in Canvas.`);
            setPushing(false);
            // Refresh history
            const history = await api.getCanvasPushHistory(selectedSession.id);
            setPushHistory(history);
          } else if (status.status === 'failed') {
            setPushMessage(`Failed: ${status.error_message || 'Unknown error'}`);
            setPushing(false);
          } else {
            // Still running, poll again
            setTimeout(pollForCompletion, 2000);
          }
        } catch (err) {
          setPushMessage('Error checking push status');
          setPushing(false);
        }
      };

      setTimeout(pollForCompletion, 2000);
    } catch (error: any) {
      setPushMessage(`Error: ${error.message || 'Failed to push to Canvas'}`);
      setPushing(false);
    }
  };

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

  const handleEditSession = (session: Session) => {
    setEditingSession(session);
    setEditTitle(session.title);
    // Initialize plan content fields
    const plan = session.plan_json;
    setEditDiscussionPrompts(plan?.discussion_prompts?.join('\n') || '');
    setEditCaseScenario(
      typeof plan?.case === 'string'
        ? plan.case
        : plan?.case?.scenario || plan?.case?.description || ''
    );
    setEditGoals(
      Array.isArray(plan?.goals)
        ? plan.goals.join('\n')
        : plan?.goals || ''
    );
  };

  const handleSaveEdit = async () => {
    if (!editingSession || !currentUser || !editTitle.trim()) return;

    setSaving(true);
    try {
      // Build updated plan_json by merging with existing plan
      const existingPlan = editingSession.plan_json || {};
      const updatedPlan = {
        ...existingPlan,
        discussion_prompts: editDiscussionPrompts.trim()
          ? editDiscussionPrompts.split('\n').map(p => p.trim()).filter(Boolean)
          : existingPlan.discussion_prompts,
        case: editCaseScenario.trim()
          ? typeof existingPlan.case === 'object'
            ? { ...existingPlan.case, scenario: editCaseScenario.trim() }
            : editCaseScenario.trim()
          : existingPlan.case,
        goals: editGoals.trim()
          ? editGoals.split('\n').map(g => g.trim()).filter(Boolean)
          : existingPlan.goals,
      };

      await api.updateSession(editingSession.id, currentUser.id, {
        title: editTitle.trim(),
        plan_json: updatedPlan,
      });
      setEditingSession(null);
      setEditTitle('');
      setEditDiscussionPrompts('');
      setEditCaseScenario('');
      setEditGoals('');
      if (selectedCourseId) {
        fetchSessions(selectedCourseId);
      }
    } catch (error: any) {
      console.error('Failed to update session:', error);
      alert(error.message || 'Failed to update session');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteSession = async () => {
    if (!selectedSession || !currentUser) return;

    setDeleting(true);
    try {
      await api.deleteSession(selectedSession.id, currentUser.id);
      setShowDeleteConfirm(false);
      setSelectedSession(null);
      setSelectedSessionId(null);
      if (selectedCourseId) {
        fetchSessions(selectedCourseId);
      }
    } catch (error: any) {
      console.error('Failed to delete session:', error);
      alert(error.message || 'Failed to delete session');
    } finally {
      setDeleting(false);
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
          onChange={(e) => setSelectedCourseId(e.target.value ? Number(e.target.value) : null)}
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
            <TabsTrigger value="sessions" data-voice-id="tab-sessions">{t('sessions.viewSessions')}</TabsTrigger>
            <TabsTrigger value="materials" data-voice-id="tab-materials">
              <FileText className="w-4 h-4 mr-1.5" />
              {t('sessions.materials')}
            </TabsTrigger>
            {hasInstructorPrivileges && <TabsTrigger value="create" data-voice-id="tab-create">{t('sessions.createSession')}</TabsTrigger>}
            {hasInstructorPrivileges && <TabsTrigger value="manage" data-voice-id="tab-manage">{t('sessions.manageStatus')}</TabsTrigger>}
            {hasInstructorPrivileges && (
              <TabsTrigger value="insights" data-voice-id="tab-insights">
                Insights
              </TabsTrigger>
            )}
            {hasInstructorPrivileges && (
              <TabsTrigger value="ai-features" data-voice-id="tab-ai-features">
                AI Features
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
                              onClick={() => {
                                setSelectedSession(session);
                                setSelectedSessionId(session.id);
                              }}
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
              <div className="space-y-6">
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

                        {/* Edit and Delete buttons */}
                        <div className="flex gap-2 mt-4 pt-4 border-t border-neutral-200 dark:border-neutral-700">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleEditSession(selectedSession)}
                            data-voice-id="edit-session"
                          >
                            <Pencil className="h-4 w-4 mr-2" />
                            Edit Session
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setShowDeleteConfirm(true)}
                            className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20"
                            data-voice-id="delete-session"
                          >
                            <Trash2 className="h-4 w-4 mr-2" />
                            Delete Session
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <p className="text-neutral-500 dark:text-neutral-400">{t('sessions.selectSession')}</p>
                    )}
                  </CardContent>
                </Card>

                {/* Edit Session Modal */}
                {editingSession && (
                  <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-y-auto py-8">
                    <Card variant="default" className="w-full max-w-2xl mx-4 my-auto">
                      <CardHeader>
                        <div className="flex items-center justify-between">
                          <CardTitle>Edit Session</CardTitle>
                          <button
                            onClick={() => setEditingSession(null)}
                            className="p-1 hover:bg-neutral-100 dark:hover:bg-neutral-800 rounded"
                          >
                            <X className="h-5 w-5" />
                          </button>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-4 max-h-[70vh] overflow-y-auto">
                        <Input
                          label="Session Title"
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          placeholder="Enter session title"
                        />
                        <Textarea
                          label="Goals / Learning Objectives"
                          value={editGoals}
                          onChange={(e) => setEditGoals(e.target.value)}
                          placeholder="Enter learning goals (one per line)"
                          rows={3}
                        />
                        <Textarea
                          label="Discussion Prompts"
                          value={editDiscussionPrompts}
                          onChange={(e) => setEditDiscussionPrompts(e.target.value)}
                          placeholder="Enter discussion prompts (one per line)"
                          rows={4}
                        />
                        <Textarea
                          label="Case Study Scenario"
                          value={editCaseScenario}
                          onChange={(e) => setEditCaseScenario(e.target.value)}
                          placeholder="Enter the case study scenario"
                          rows={5}
                        />
                        <div className="flex justify-end gap-2 pt-2 border-t border-neutral-200 dark:border-neutral-700">
                          <Button
                            variant="outline"
                            onClick={() => setEditingSession(null)}
                          >
                            Cancel
                          </Button>
                          <Button
                            onClick={handleSaveEdit}
                            disabled={saving || !editTitle.trim()}
                          >
                            {saving ? 'Saving...' : 'Save Changes'}
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                )}

                {/* Delete Confirmation Modal */}
                {showDeleteConfirm && selectedSession && (
                  <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <Card variant="default" className="w-full max-w-md mx-4">
                      <CardHeader>
                        <CardTitle className="text-red-600 dark:text-red-400">Delete Session</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <p className="text-neutral-600 dark:text-neutral-400">
                          Are you sure you want to delete <strong>"{selectedSession.title}"</strong>? This action cannot be undone.
                        </p>
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="outline"
                            onClick={() => setShowDeleteConfirm(false)}
                          >
                            Cancel
                          </Button>
                          <Button
                            variant="danger"
                            onClick={handleDeleteSession}
                            disabled={deleting}
                          >
                            {deleting ? 'Deleting...' : 'Delete Session'}
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                )}

                {/* Push to Canvas Section */}
                {selectedSession && (
                  <Card variant="default">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Send className="h-5 w-5 text-primary-600" />
                        Push to Canvas
                      </CardTitle>
                      <CardDescription>
                        Generate an AI summary of this session and push it to Canvas as an announcement or assignment.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {canvasMappings.length === 0 ? (
                        <div className="text-center py-4">
                          <p className="text-neutral-500 dark:text-neutral-400 mb-2">
                            No Canvas connections found. Set up a Canvas integration first.
                          </p>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => window.location.href = '/integrations'}
                          >
                            Go to Integrations
                          </Button>
                        </div>
                      ) : (
                        <>
                          {/* Canvas Connection Select */}
                          <Select
                            label="Canvas Connection"
                            value={selectedCanvasConnection?.toString() || ''}
                            onChange={(e) => setSelectedCanvasConnection(e.target.value ? Number(e.target.value) : null)}
                            data-voice-id="select-canvas-connection"
                          >
                            <option value="">Select a Canvas connection...</option>
                            {canvasMappings.map((mapping) => (
                              <option key={mapping.connection_id} value={mapping.connection_id}>
                                {mapping.connection_label}
                                {mapping.has_mapping ? ` → ${mapping.external_course_name || mapping.external_course_id}` : ' (no course mapped)'}
                              </option>
                            ))}
                          </Select>

                          {/* Push Type Selection */}
                          <div className="space-y-2">
                            <label className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
                              Push as
                            </label>
                            <div className="flex gap-4">
                              <label className="flex items-center gap-2 cursor-pointer" data-voice-id="push-type-announcement">
                                <input
                                  type="radio"
                                  name="pushType"
                                  value="announcement"
                                  checked={pushType === 'announcement'}
                                  onChange={() => setPushType('announcement')}
                                  className="text-primary-600"
                                />
                                <Megaphone className="h-4 w-4 text-blue-600" />
                                <span className="text-sm">Announcement</span>
                              </label>
                              <label className="flex items-center gap-2 cursor-pointer" data-voice-id="push-type-assignment">
                                <input
                                  type="radio"
                                  name="pushType"
                                  value="assignment"
                                  checked={pushType === 'assignment'}
                                  onChange={() => setPushType('assignment')}
                                  className="text-primary-600"
                                />
                                <ClipboardList className="h-4 w-4 text-green-600" />
                                <span className="text-sm">Reflection Assignment</span>
                              </label>
                            </div>
                          </div>

                          {/* Push Button */}
                          <Button
                            onClick={handlePushToCanvas}
                            disabled={pushing || !selectedCanvasConnection || !canvasMappings.find(m => m.connection_id === selectedCanvasConnection)?.has_mapping}
                            className="w-full"
                            data-voice-id="push-to-canvas"
                          >
                            {pushing ? (
                              <>
                                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                                Pushing...
                              </>
                            ) : (
                              <>
                                <Send className="h-4 w-4 mr-2" />
                                Push to Canvas
                              </>
                            )}
                          </Button>

                          {/* Status Message */}
                          {pushMessage && (
                            <div className={`p-3 rounded-lg text-sm ${
                              pushMessage.startsWith('Success')
                                ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300'
                                : pushMessage.startsWith('Error') || pushMessage.startsWith('Failed')
                                ? 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'
                                : 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'
                            }`}>
                              {pushMessage}
                            </div>
                          )}

                          {/* Push History */}
                          {pushHistory.length > 0 && (
                            <div className="mt-4">
                              <h4 className="text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                                Recent Pushes
                              </h4>
                              <div className="space-y-2 max-h-48 overflow-y-auto">
                                {pushHistory.slice(0, 5).map((push) => (
                                  <div
                                    key={push.id}
                                    className="flex items-center justify-between p-2 bg-neutral-50 dark:bg-neutral-800/50 rounded-lg text-sm"
                                  >
                                    <div className="flex items-center gap-2">
                                      {push.push_type === 'announcement' ? (
                                        <Megaphone className="h-4 w-4 text-blue-600" />
                                      ) : (
                                        <ClipboardList className="h-4 w-4 text-green-600" />
                                      )}
                                      <span className="font-medium truncate max-w-[200px]">{push.title}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                      <Badge
                                        variant={
                                          push.status === 'completed' ? 'success' :
                                          push.status === 'failed' ? 'danger' :
                                          push.status === 'running' ? 'warning' : 'default'
                                        }
                                        size="sm"
                                      >
                                        {push.status}
                                      </Badge>
                                      <span className="text-xs text-neutral-500">
                                        {new Date(push.created_at).toLocaleDateString()}
                                      </span>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </>
                      )}
                    </CardContent>
                  </Card>
                )}
              </div>
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

          {hasInstructorPrivileges && (
            <TabsContent value="ai-features">
              <div className="space-y-6">
                {selectedSession ? (
                  <>
                    {/* Live Discussion Summary */}
                    {(selectedSession.status === 'live' || selectedSession.status === 'completed') && (
                      <LiveSummaryComponent sessionId={selectedSession.id} />
                    )}

                    {/* Question Bank */}
                    {selectedCourseId && (
                      <QuestionBankComponent
                        courseId={selectedCourseId}
                        sessionId={selectedSession.id}
                      />
                    )}

                    {/* Peer Review Panel */}
                    {currentUser && (
                      <PeerReviewPanelComponent
                        sessionId={selectedSession.id}
                        userId={currentUser.id}
                        isInstructor={hasInstructorPrivileges}
                      />
                    )}

                    {/* Voice Command Hints for AI Features */}
                    <Card variant="ghost" padding="md">
                      <h3 className="font-semibold text-neutral-900 dark:text-white mb-3">AI Feature Voice Commands</h3>
                      <div className="flex flex-wrap gap-2">
                        {[
                          'Generate live summary',
                          'Create quiz questions',
                          'Show participation insights',
                          'Create peer review assignments',
                          'Analyze objective coverage',
                          'Generate follow-ups for struggling students'
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
                      <p className="text-neutral-600 dark:text-neutral-400">Select a session to access AI features</p>
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
