'use client';

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import { Calendar, Play, CheckCircle, Clock, FileEdit, RefreshCw, ChevronRight } from 'lucide-react';
import { api } from '@/lib/api';
import { useUser } from '@/lib/context';
import { Course, Session, SessionStatus } from '@/types';
import { formatTimestamp, getStatusColor } from '@/lib/utils';
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

const statusIcons: Record<SessionStatus, any> = {
  draft: FileEdit,
  scheduled: Clock,
  live: Play,
  completed: CheckCircle,
};

export default function SessionsPage() {
  const { isInstructor, currentUser } = useUser();
  const searchParams = useSearchParams();
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
  }, [currentUser, isInstructor]);

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
          No session plan available. This session may have been created manually.
        </p>
      );
    }

    return (
      <div className="space-y-4">
        {plan.topics && plan.topics.length > 0 && (
          <div>
            <h4 className="font-medium text-gray-900 mb-2">Topics</h4>
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
            <h4 className="font-medium text-gray-900 mb-2">Goals</h4>
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
            <h4 className="font-medium text-gray-900 mb-2">Key Concepts</h4>
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
            <h4 className="font-medium text-gray-900 mb-2">Case Study</h4>
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
            <h4 className="font-medium text-gray-900 mb-2">Discussion Prompts</h4>
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
          <h1 className="text-2xl font-bold text-gray-900">Session Management</h1>
          <p className="text-gray-600">View and manage session plans</p>
        </div>
      </div>

      {/* Course Selector */}
      <div className="mb-6">
        <Select
          label="Select Course"
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
            <TabsTrigger value="sessions">View Sessions</TabsTrigger>
            {isInstructor && <TabsTrigger value="create">Create Session</TabsTrigger>}
            {isInstructor && <TabsTrigger value="manage">Manage Status</TabsTrigger>}
          </TabsList>

          <TabsContent value="sessions">
            {loading ? (
              <div className="text-center py-8 text-gray-500">Loading sessions...</div>
            ) : sessions.length === 0 ? (
              <Card>
                <CardContent className="py-8 text-center text-gray-500">
                  <Calendar className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                  <p>No sessions found for this course.</p>
                  <p className="text-sm mt-2">
                    Create a session or generate plans from the Courses page.
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
                        Select a session to view its details
                      </CardContent>
                    </Card>
                  )}
                </div>
              </div>
            )}
          </TabsContent>

          {isInstructor && (
            <TabsContent value="create">
              <Card>
                <CardHeader>
                  <CardTitle>Create New Session</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <Input
                    label="Session Title"
                    placeholder="e.g., Week 1: Introduction to ML"
                    value={newSessionTitle}
                    onChange={(e) => setNewSessionTitle(e.target.value)}
                  />
                  <Button
                    onClick={handleCreateSession}
                    disabled={creating || !newSessionTitle.trim()}
                    data-voice-id="create-session"
                  >
                    Create Session
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>
          )}

          {isInstructor && (
            <TabsContent value="manage">
              <Card>
                <CardHeader>
                  <CardTitle>Session Status Control</CardTitle>
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
                          {selectedSession.status.toUpperCase()}
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
                            Set to Draft
                          </Button>
                        )}
                        {selectedSession.status === 'draft' && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleStatusChange(selectedSession.id, 'scheduled')}
                            data-voice-id="schedule-session"
                          >
                            Schedule
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
                            Go Live
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
                            Complete
                          </Button>
                        )}
                      </div>
                    </div>
                  ) : (
                    <p className="text-gray-500">Select a session from the list to manage its status.</p>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          )}
        </Tabs>
      )}
    </div>
  );
}
