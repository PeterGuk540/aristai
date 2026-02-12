'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Bot,
  Play,
  Square,
  RefreshCw,
  AlertTriangle,
  Lightbulb,
  BarChart3,
  MessageSquare,
  Zap,
  CheckCircle,
  XCircle,
  UserPlus,
  Clock,
  Upload,
  FileSpreadsheet,
  Activity,
  Timer,
  Users,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useUser } from '@/lib/context';
import { useSharedCourseSessionSelection } from '@/lib/shared-selection';
import { Course, Session, Intervention, PollResults, User } from '@/types';
import { formatTimestamp } from '@/lib/utils';
import { useTranslations } from 'next-intl';
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
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

// Instructor enhancement components
import { EngagementHeatmapComponent } from '@/components/instructor/EngagementHeatmap';
import { SessionTimerComponent } from '@/components/instructor/SessionTimer';
import { FacilitationPanel } from '@/components/instructor/FacilitationPanel';
import { BreakoutGroupsComponent } from '@/components/instructor/BreakoutGroups';
import { AIResponseDraftsComponent } from '@/components/instructor/AIResponseDrafts';

export default function ConsolePage() {
  const { isInstructor, isAdmin, currentUser } = useUser();
  const t = useTranslations();
  const [courses, setCourses] = useState<Course[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const {
    selectedCourseId,
    setSelectedCourseId,
    selectedSessionId,
    setSelectedSessionId,
  } = useSharedCourseSessionSelection();
  const [copilotActive, setCopilotActive] = useState(false);
  const [interventions, setInterventions] = useState<Intervention[]>([]);
  const [loading, setLoading] = useState(false);

  // Poll creation
  const [pollQuestion, setPollQuestion] = useState('');
  const [pollOptions, setPollOptions] = useState(['', '']);
  const [creatingPoll, setCreatingPoll] = useState(false);
  const [activePollId, setActivePollId] = useState<number | null>(null);
  const [pollResults, setPollResults] = useState<PollResults | null>(null);

  // Case posting
  const [casePrompt, setCasePrompt] = useState('');
  const [postingCase, setPostingCase] = useState(false);

  // Instructor requests
  const [instructorRequests, setInstructorRequests] = useState<User[]>([]);
  const [loadingRequests, setLoadingRequests] = useState(false);

  // Roster upload
  const [rosterCourseId, setRosterCourseId] = useState<number | null>(null);
  const [rosterFile, setRosterFile] = useState<File | null>(null);
  const [uploadingRoster, setUploadingRoster] = useState(false);
  const [rosterResults, setRosterResults] = useState<any>(null);

  // Active tab state for voice control
  const [activeTab, setActiveTab] = useState<string>(isAdmin ? "requests" : "copilot");

  // Listen for voice tab switching events
  useEffect(() => {
    const handleVoiceTabSwitch = (event: CustomEvent) => {
      const { tabName, target } = event.detail || {};
      console.log('🎤 Console: Voice tab switch received:', { tabName, target });

      // Normalize the tab name
      let normalizedTab = (tabName || '').toLowerCase().replace(/\s+/g, '');

      // Map common names to tab values
      const tabMap: Record<string, string> = {
        'copilot': 'copilot',
        'aicopilot': 'copilot',
        'aiassistant': 'copilot',
        'polls': 'polls',
        'poll': 'polls',
        'polling': 'polls',
        'cases': 'cases',
        'case': 'cases',
        'postcase': 'cases',
        'casestudy': 'cases',
        'casestudies': 'cases',
        'requests': 'requests',
        'request': 'requests',
        'instructorrequests': 'requests',
        'roster': 'roster',
        'rosterupload': 'roster',
        // Instructor enhancement tabs
        'tools': 'tools',
        'instructortools': 'tools',
        'engagement': 'tools',
        'heatmap': 'tools',
        'timer': 'tools',
        'facilitation': 'tools',
        'breakout': 'tools',
        'breakoutgroups': 'tools',
        'groups': 'tools',
        'aidrafts': 'tools',
      };

      const targetTab = tabMap[normalizedTab] || normalizedTab;
      console.log('🎤 Console: Switching to tab:', targetTab);

      // Check if the tab requires a session and we don't have one
      const requiresSession = ['copilot', 'polls', 'cases'].includes(targetTab);
      if (requiresSession && !selectedSessionId) {
        console.warn('🎤 Console: Tab requires session but none selected:', targetTab);
        // Still switch the tab - the UI will show the "select session" message
      }

      setActiveTab(targetTab);
    };

    // Listen for both event types
    window.addEventListener('ui.switchTab', handleVoiceTabSwitch as EventListener);
    window.addEventListener('voice-select-tab', handleVoiceTabSwitch as EventListener);

    return () => {
      window.removeEventListener('ui.switchTab', handleVoiceTabSwitch as EventListener);
      window.removeEventListener('voice-select-tab', handleVoiceTabSwitch as EventListener);
    };
  }, [selectedSessionId]);

  // Update active tab when session is selected/deselected
  useEffect(() => {
    if (selectedSessionId && activeTab === 'requests' && !isAdmin) {
      setActiveTab('copilot');
    }
  }, [selectedSessionId, activeTab, isAdmin]);

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
      }
      // Note: Console page is for instructors/admins only, students shouldn't access this page
    } catch (error) {
      console.error('Failed to fetch courses:', error);
    }
  };

  const fetchSessions = async (courseId: number) => {
    try {
      const data = await api.getCourseSessions(courseId);
      const liveSessions = data.filter((s: Session) => s.status === 'live');
      setSessions(liveSessions);
      if (liveSessions.length > 0 && (!selectedSessionId || !liveSessions.some((session) => session.id === selectedSessionId))) {
        setSelectedSessionId(liveSessions[0].id);
      } else {
        if (liveSessions.length === 0) {
          setSelectedSessionId(null);
        }
      }
    } catch (error) {
      console.error('Failed to fetch sessions:', error);
    }
  };

  const fetchCopilotStatus = useCallback(async () => {
    if (!selectedSessionId) return;

    try {
      const status = await api.getCopilotStatus(selectedSessionId);
      setCopilotActive(status.copilot_active);
    } catch (error) {
      console.error('Failed to fetch copilot status:', error);
    }
  }, [selectedSessionId]);

  const fetchInterventions = useCallback(async () => {
    if (!selectedSessionId) return;

    try {
      setLoading(true);
      const data = await api.getInterventions(selectedSessionId);
      setInterventions(data);
    } catch (error) {
      console.error('Failed to fetch interventions:', error);
    } finally {
      setLoading(false);
    }
  }, [selectedSessionId]);

  const fetchInstructorRequests = async () => {
    if (!currentUser?.id || !isAdmin) return;
    setLoadingRequests(true);
    try {
      const requests = await api.getInstructorRequests(currentUser.id);
      setInstructorRequests(requests);
    } catch (error) {
      console.error('Failed to fetch instructor requests:', error);
    } finally {
      setLoadingRequests(false);
    }
  };

  const handleApproveRequest = async (userId: number) => {
    if (!currentUser?.id) return;
    try {
      await api.approveInstructorRequest(userId, currentUser.id);
      fetchInstructorRequests();
    } catch (error) {
      console.error('Failed to approve request:', error);
      alert('Failed to approve request');
    }
  };

  const handleRejectRequest = async (userId: number) => {
    if (!currentUser?.id) return;
    try {
      await api.rejectInstructorRequest(userId, currentUser.id);
      fetchInstructorRequests();
    } catch (error) {
      console.error('Failed to reject request:', error);
      alert('Failed to reject request');
    }
  };

  const handleRosterUpload = async () => {
    if (!rosterCourseId || !rosterFile) return;

    setUploadingRoster(true);
    setRosterResults(null);
    try {
      const results = await api.uploadRosterCsv(rosterCourseId, rosterFile);
      setRosterResults(results);
      setRosterFile(null);
    } catch (error: any) {
      console.error('Failed to upload roster:', error);
      alert(`Failed to upload roster: ${error.message}`);
    } finally {
      setUploadingRoster(false);
    }
  };

  useEffect(() => {
    fetchCourses();
  }, []);

  useEffect(() => {
    if (isAdmin && currentUser?.id) {
      fetchInstructorRequests();
    }
  }, [isAdmin, currentUser?.id]);

  useEffect(() => {
    if (selectedCourseId) {
      fetchSessions(selectedCourseId);
    }
  }, [selectedCourseId]);

  useEffect(() => {
    if (selectedSessionId) {
      fetchCopilotStatus();
      fetchInterventions();
    }
  }, [selectedSessionId, fetchCopilotStatus, fetchInterventions]);

  // Auto-refresh interventions when copilot is active
  useEffect(() => {
    if (copilotActive && selectedSessionId) {
      const interval = setInterval(fetchInterventions, 15000); // Every 15 seconds
      return () => clearInterval(interval);
    }
  }, [copilotActive, selectedSessionId, fetchInterventions]);

  const handleStartCopilot = async () => {
    if (!selectedSessionId) return;

    try {
      await api.startCopilot(selectedSessionId);
      setCopilotActive(true);
    } catch (error) {
      console.error('Failed to start copilot:', error);
      alert('Failed to start copilot');
    }
  };

  const handleStopCopilot = async () => {
    if (!selectedSessionId) return;

    try {
      await api.stopCopilot(selectedSessionId);
      setCopilotActive(false);
    } catch (error) {
      console.error('Failed to stop copilot:', error);
      alert('Failed to stop copilot');
    }
  };

  const handleCreatePoll = async () => {
    if (!selectedSessionId || !pollQuestion.trim()) return;

    const validOptions = pollOptions.filter((o) => o.trim());
    if (validOptions.length < 2) {
      alert('Please provide at least 2 options');
      return;
    }

    setCreatingPoll(true);
    try {
      const poll = await api.createPoll(selectedSessionId, {
        question: pollQuestion,
        options_json: validOptions,
      });
      setActivePollId(poll.id);
      setPollQuestion('');
      setPollOptions(['', '']);
      alert('Poll created!');
    } catch (error) {
      console.error('Failed to create poll:', error);
      alert('Failed to create poll');
    } finally {
      setCreatingPoll(false);
    }
  };

  const handleFetchPollResults = async () => {
    if (!activePollId) return;

    try {
      const results = await api.getPollResults(activePollId);
      setPollResults(results);
    } catch (error) {
      console.error('Failed to fetch poll results:', error);
    }
  };

  const handlePostCase = async () => {
    if (!selectedSessionId || !casePrompt.trim()) return;

    setPostingCase(true);
    try {
      await api.postCase(selectedSessionId, casePrompt);
      setCasePrompt('');
      alert('Case posted!');
    } catch (error) {
      console.error('Failed to post case:', error);
      alert('Failed to post case');
    } finally {
      setPostingCase(false);
    }
  };

  const addPollOption = () => {
    if (pollOptions.length < 6) {
      setPollOptions([...pollOptions, '']);
    }
  };

  const updatePollOption = (index: number, value: string) => {
    const newOptions = [...pollOptions];
    newOptions[index] = value;
    setPollOptions(newOptions);
  };

  const removePollOption = (index: number) => {
    if (pollOptions.length > 2) {
      setPollOptions(pollOptions.filter((_, i) => i !== index));
    }
  };

  const renderIntervention = (intervention: Intervention) => {
    const suggestion = intervention.suggestion_json;

    return (
      <Card key={intervention.id} className="mb-4">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Zap className="h-4 w-4 text-yellow-500" />
              Intervention #{intervention.id}
            </CardTitle>
            <span className="text-xs text-gray-500">
              {formatTimestamp(intervention.created_at)}
            </span>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Rolling Summary */}
          {suggestion.rolling_summary && (
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-1">Summary</h4>
              <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded">
                {suggestion.rolling_summary}
              </p>
            </div>
          )}

          {/* Confusion Points */}
          {suggestion.confusion_points && suggestion.confusion_points.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-orange-500" />
                Confusion Points
              </h4>
              <div className="space-y-2">
                {suggestion.confusion_points.map((point, i) => (
                  <div
                    key={i}
                    className={`p-3 rounded border-l-4 ${
                      point.severity === 'high'
                        ? 'bg-red-50 border-red-500'
                        : point.severity === 'medium'
                        ? 'bg-orange-50 border-orange-500'
                        : 'bg-yellow-50 border-yellow-500'
                    }`}
                  >
                    <p className="text-sm font-medium text-gray-800">{point.issue}</p>
                    <p className="text-sm text-gray-600 mt-1">{point.explanation}</p>
                    <Badge
                      variant={
                        point.severity === 'high'
                          ? 'danger'
                          : point.severity === 'medium'
                          ? 'warning'
                          : 'default'
                      }
                      className="mt-2"
                    >
                      {point.severity} severity
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Instructor Prompts */}
          {suggestion.instructor_prompts && suggestion.instructor_prompts.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                <Lightbulb className="h-4 w-4 text-blue-500" />
                Suggested Prompts
              </h4>
              <div className="space-y-2">
                {suggestion.instructor_prompts.map((prompt, i) => (
                  <div key={i} className="bg-blue-50 p-3 rounded">
                    <p className="text-sm text-blue-900 font-medium">"{prompt.prompt}"</p>
                    <p className="text-xs text-blue-700 mt-1">
                      Purpose: {prompt.purpose} | Target: {prompt.target}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Poll Suggestion */}
          {suggestion.poll_suggestion && (
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-purple-500" />
                Suggested Poll
              </h4>
              <div className="bg-purple-50 p-3 rounded">
                <p className="text-sm font-medium text-purple-900">
                  {suggestion.poll_suggestion.question}
                </p>
                <ul className="mt-2 text-sm text-purple-700">
                  {suggestion.poll_suggestion.options.map((opt, i) => (
                    <li key={i} className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-purple-200 flex items-center justify-center text-xs">
                        {String.fromCharCode(65 + i)}
                      </span>
                      {opt}
                    </li>
                  ))}
                </ul>
                <Button
                  size="sm"
                  className="mt-3"
                  onClick={() => {
                    setPollQuestion(suggestion.poll_suggestion!.question);
                    setPollOptions(suggestion.poll_suggestion!.options);
                  }}
                >
                  Use This Poll
                </Button>
              </div>
            </div>
          )}

          {/* Overall Assessment */}
          {suggestion.overall_assessment && (
            <div className="bg-gray-50 p-3 rounded">
              <h4 className="text-sm font-medium text-gray-700 mb-2">Assessment</h4>
              <div className="grid grid-cols-3 gap-2 text-sm">
                <div>
                  <span className="text-gray-500">Engagement:</span>
                  <span className="ml-1 font-medium">
                    {suggestion.overall_assessment.engagement_level}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500">Understanding:</span>
                  <span className="ml-1 font-medium">
                    {suggestion.overall_assessment.understanding_level}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500">Quality:</span>
                  <span className="ml-1 font-medium">
                    {suggestion.overall_assessment.discussion_quality}
                  </span>
                </div>
              </div>
              {suggestion.overall_assessment.recommendation && (
                <p className="text-sm text-gray-600 mt-2 pt-2 border-t">
                  {suggestion.overall_assessment.recommendation}
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  // Both instructors and admins can access the console
  if (!isInstructor && !isAdmin) {
    return (
      <div className="space-y-6">
        <Card variant="default" padding="lg">
          <div className="text-center py-8">
            <div className="p-4 rounded-2xl bg-danger-50 dark:bg-danger-900/30 w-fit mx-auto mb-4">
              <Bot className="h-10 w-10 text-danger-600 dark:text-danger-400" />
            </div>
            <p className="text-neutral-600 dark:text-neutral-400">{t('errors.forbidden')}</p>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-4">
      {/* Page Header */}
      <div className="flex items-center justify-between rounded-2xl border border-sky-200/80 dark:border-primary-900/20 bg-white dark:bg-[#1a150c] px-6 py-5 shadow-sm">
        <div>
          <h1 className="text-3xl font-bold text-neutral-900 dark:text-white tracking-tight">{t('console.title')}</h1>
          <p className="text-neutral-600 dark:text-neutral-400 mt-1">{t('console.subtitle')}</p>
        </div>
      </div>

      {/* Course & Session Selector */}
      <Card variant="default" padding="md" className="border-neutral-200 dark:border-primary-900/20 bg-white dark:bg-[#1a150c]">
        <div className="grid md:grid-cols-2 gap-4">
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
          label="Select Live Session"
          value={selectedSessionId?.toString() || ''}
          onChange={(e) => setSelectedSessionId(e.target.value ? Number(e.target.value) : null)}
          disabled={!selectedCourseId}
          data-voice-id="select-session"
        >
          <option value="">Select a session...</option>
          {sessions.map((session) => (
            <option key={session.id} value={session.id}>
              {session.title} (ID: {session.id})
            </option>
          ))}
        </Select>
        </div>
      </Card>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="border border-neutral-200 dark:border-primary-900/20 bg-white dark:bg-[#1a150c] rounded-xl">
          <TabsTrigger value="copilot" disabled={!selectedSessionId}>
            {t('console.copilot')}
          </TabsTrigger>
          <TabsTrigger value="polls" disabled={!selectedSessionId}>
            {t('console.polls')}
          </TabsTrigger>
          <TabsTrigger value="cases" disabled={!selectedSessionId}>
            {t('console.postCase')}
          </TabsTrigger>
          <TabsTrigger value="tools" disabled={!selectedSessionId}>
            <Activity className="h-4 w-4 mr-1" />
            Instructor Tools
          </TabsTrigger>
          {isAdmin && (
            <TabsTrigger value="requests">
              {t('console.instructorRequests')}
              {instructorRequests.length > 0 && (
                <Badge variant="danger" className="ml-2">{instructorRequests.length}</Badge>
              )}
            </TabsTrigger>
          )}
          {isAdmin && (
            <TabsTrigger value="roster">
              <FileSpreadsheet className="h-4 w-4 mr-1" />
              {t('console.roster')}
            </TabsTrigger>
          )}
        </TabsList>

        {!selectedSessionId && (
          <Card variant="ghost" padding="md" className="mt-4 mb-4">
            <div className="text-center py-4">
              <div className="p-3 rounded-xl bg-primary-100 dark:bg-primary-900/50 w-fit mx-auto mb-3">
                <Bot className="h-8 w-8 text-primary-600 dark:text-primary-400" />
              </div>
              <p className="text-sm text-neutral-600 dark:text-neutral-400">Select a live session above to use AI Copilot, Polls, and Post Case features.</p>
            </div>
          </Card>
        )}

        <TabsContent value="copilot">
          <div className="grid lg:grid-cols-3 gap-6">
            {/* Copilot Control */}
            <div className="lg:col-span-1">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Bot className="h-5 w-5" />
                    Copilot Control
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-3 mb-4">
                    <span className="text-sm font-medium">Status:</span>
                    {copilotActive ? (
                      <Badge variant="success">
                        <CheckCircle className="h-3 w-3 mr-1" />
                        Active
                      </Badge>
                    ) : (
                      <Badge variant="default">
                        <XCircle className="h-3 w-3 mr-1" />
                        Inactive
                      </Badge>
                    )}
                  </div>

                  <div className="space-y-2">
                    {!copilotActive ? (
                      <Button onClick={handleStartCopilot} className="w-full" data-voice-id="start-copilot">
                        <Play className="h-4 w-4 mr-2" />
                        {t('console.startCopilot')}
                      </Button>
                    ) : (
                      <Button
                        onClick={handleStopCopilot}
                        variant="secondary"
                        className="w-full"
                        data-voice-id="stop-copilot"
                      >
                        <Square className="h-4 w-4 mr-2" />
                        {t('console.stopCopilot')}
                      </Button>
                    )}

                    <Button
                      onClick={fetchInterventions}
                      variant="outline"
                      className="w-full"
                      data-voice-id="refresh-interventions"
                    >
                      <RefreshCw className="h-4 w-4 mr-2" />
                      {t('console.refreshInterventions')}
                    </Button>
                  </div>

                  <p className="text-xs text-gray-500 mt-4">
                    The copilot monitors discussion and provides real-time suggestions.
                    {copilotActive && ' Auto-refreshing every 15 seconds.'}
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* Interventions */}
            <div className="lg:col-span-2">
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                Interventions ({interventions.length})
              </h3>
              {loading ? (
                <div className="text-center py-8 text-gray-500">Loading...</div>
              ) : interventions.length === 0 ? (
                <Card>
                  <CardContent className="py-8 text-center text-gray-500">
                    <Zap className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                    <p>No interventions yet.</p>
                    <p className="text-sm mt-2">
                      {copilotActive
                        ? 'The copilot is analyzing the discussion...'
                        : 'Start the copilot to receive suggestions.'}
                    </p>
                  </CardContent>
                </Card>
              ) : (
                <div className="max-h-[600px] overflow-auto">
                  {interventions.map(renderIntervention)}
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="polls">
          <div className="grid lg:grid-cols-2 gap-6">
            {/* Create Poll */}
            <Card>
              <CardHeader>
                <CardTitle>Create Poll</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Input
                  label="Question"
                  placeholder="What do you think about...?"
                  value={pollQuestion}
                  onChange={(e) => setPollQuestion(e.target.value)}
                  data-voice-id="poll-question"
                />

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Options
                  </label>
                  {pollOptions.map((option, index) => (
                    <div key={index} className="flex gap-2 mb-2">
                      <Input
                        placeholder={`Option ${index + 1}`}
                        value={option}
                        onChange={(e) => updatePollOption(index, e.target.value)}
                        data-voice-id={`poll-option-${index + 1}`}
                      />
                      {pollOptions.length > 2 && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => removePollOption(index)}
                        >
                          Remove
                        </Button>
                      )}
                    </div>
                  ))}
                  {pollOptions.length < 6 && (
                    <Button variant="outline" size="sm" onClick={addPollOption} data-voice-id="add-poll-option">
                      Add Option
                    </Button>
                  )}
                </div>

                <Button
                  onClick={handleCreatePoll}
                  disabled={creatingPoll || !pollQuestion.trim()}
                  className="w-full"
                  data-voice-id="create-poll"
                >
                  <BarChart3 className="h-4 w-4 mr-2" />
                  Create Poll
                </Button>
              </CardContent>
            </Card>

            {/* Poll Results */}
            <Card>
              <CardHeader>
                <CardTitle>Poll Results</CardTitle>
              </CardHeader>
              <CardContent>
                {activePollId ? (
                  <div className="space-y-4">
                    <Button onClick={handleFetchPollResults} variant="outline">
                      <RefreshCw className="h-4 w-4 mr-2" />
                      Refresh Results
                    </Button>

                    {pollResults ? (
                      <div>
                        <h4 className="font-medium text-gray-900 mb-3">
                          {pollResults.question}
                        </h4>
                        <div className="space-y-2">
                          {pollResults.options.map((option, index) => {
                            const percentage =
                              pollResults.total_votes > 0
                                ? (pollResults.vote_counts[index] / pollResults.total_votes) *
                                  100
                                : 0;

                            return (
                              <div key={index}>
                                <div className="flex justify-between text-sm mb-1">
                                  <span>{option}</span>
                                  <span className="text-gray-500">
                                    {pollResults.vote_counts[index]} votes ({percentage.toFixed(0)}
                                    %)
                                  </span>
                                </div>
                                <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                                  <div
                                    className="h-full bg-primary-600 rounded-full transition-all"
                                    style={{ width: `${percentage}%` }}
                                  />
                                </div>
                              </div>
                            );
                          })}
                        </div>
                        <p className="text-sm text-gray-500 mt-4">
                          Total votes: {pollResults.total_votes}
                        </p>
                      </div>
                    ) : (
                      <p className="text-gray-500">Click refresh to load results.</p>
                    )}
                  </div>
                ) : (
                  <p className="text-gray-500">Create a poll to see results here.</p>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="cases">
          <Card>
            <CardHeader>
              <CardTitle>Post Case Study</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Textarea
                label="Case Prompt"
                placeholder="Describe the case study scenario for students to discuss..."
                rows={6}
                value={casePrompt}
                onChange={(e) => setCasePrompt(e.target.value)}
                data-voice-id="case-prompt"
              />

              <Button
                onClick={handlePostCase}
                disabled={postingCase || !casePrompt.trim()}
                data-voice-id="post-case"
              >
                <MessageSquare className="h-4 w-4 mr-2" />
                Post Case
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="tools">
          <div className="space-y-6">
            {/* Real-time Instructor Enhancement Tools */}
            <div className="grid lg:grid-cols-2 gap-6">
              {/* Engagement Heatmap */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Activity className="h-5 w-5 text-green-500" />
                    Engagement Heatmap
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {selectedSessionId ? (
                    <EngagementHeatmapComponent sessionId={selectedSessionId} />
                  ) : (
                    <p className="text-gray-500">Select a session to view engagement.</p>
                  )}
                </CardContent>
              </Card>

              {/* Session Timer */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Timer className="h-5 w-5 text-blue-500" />
                    Session Timer
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {selectedSessionId ? (
                    <SessionTimerComponent sessionId={selectedSessionId} />
                  ) : (
                    <p className="text-gray-500">Select a session to use the timer.</p>
                  )}
                </CardContent>
              </Card>

              {/* Facilitation Suggestions */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Lightbulb className="h-5 w-5 text-yellow-500" />
                    Facilitation Suggestions
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {selectedSessionId ? (
                    <FacilitationPanel sessionId={selectedSessionId} />
                  ) : (
                    <p className="text-gray-500">Select a session to get suggestions.</p>
                  )}
                </CardContent>
              </Card>

              {/* Breakout Groups */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Users className="h-5 w-5 text-purple-500" />
                    Breakout Groups
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {selectedSessionId ? (
                    <BreakoutGroupsComponent sessionId={selectedSessionId} />
                  ) : (
                    <p className="text-gray-500">Select a session to manage groups.</p>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* AI Response Drafts - Full width */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Bot className="h-5 w-5 text-primary-500" />
                  AI Response Drafts
                </CardTitle>
              </CardHeader>
              <CardContent>
                {selectedSessionId && currentUser?.id ? (
                  <AIResponseDraftsComponent
                    sessionId={selectedSessionId}
                    instructorId={currentUser.id}
                  />
                ) : (
                  <p className="text-gray-500">Select a session to view AI drafts.</p>
                )}
              </CardContent>
            </Card>

            {/* Voice Command Hints */}
            <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <h3 className="font-medium mb-3 flex items-center gap-2">
                <MessageSquare className="h-4 w-4" />
                Quick Voice Commands
              </h3>
              <div className="flex flex-wrap gap-2">
                {[
                  'Show engagement heatmap',
                  'Who\'s not participating?',
                  'Start a 5 minute timer',
                  'Split into 4 groups',
                  'Who should I call on next?',
                  'Suggest a poll',
                  'Show AI drafts'
                ].map((cmd) => (
                  <span key={cmd} className="px-3 py-1 text-sm bg-white dark:bg-gray-700 rounded-full text-gray-600 dark:text-gray-300 border">
                    "{cmd}"
                  </span>
                ))}
              </div>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="requests">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <UserPlus className="h-5 w-5" />
                  Pending Instructor Requests
                </CardTitle>
                <Button onClick={fetchInstructorRequests} variant="outline" size="sm">
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Refresh
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {loadingRequests ? (
                <div className="text-center py-8 text-gray-500">Loading...</div>
              ) : instructorRequests.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <UserPlus className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                  <p>No pending instructor requests.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {instructorRequests.map((request) => (
                    <div
                      key={request.id}
                      className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
                    >
                      <div>
                        <p className="font-medium text-gray-900">{request.name}</p>
                        <p className="text-sm text-gray-500">{request.email}</p>
                        <p className="text-xs text-gray-400 flex items-center gap-1 mt-1">
                          <Clock className="h-3 w-3" />
                          Requested: {request.instructor_request_date
                            ? formatTimestamp(request.instructor_request_date)
                            : 'Unknown'}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          onClick={() => handleApproveRequest(request.id)}
                        >
                          <CheckCircle className="h-4 w-4 mr-1" />
                          Approve
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleRejectRequest(request.id)}
                        >
                          <XCircle className="h-4 w-4 mr-1" />
                          Reject
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="roster">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileSpreadsheet className="h-5 w-5" />
                Upload Student Roster
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="bg-blue-50 p-4 rounded-lg">
                <h4 className="font-medium text-blue-900 mb-2">CSV Format</h4>
                <p className="text-sm text-blue-700 mb-2">
                  Upload a CSV file with student emails. The system will:
                </p>
                <ul className="text-sm text-blue-700 list-disc list-inside space-y-1">
                  <li>Find existing users by email and enroll them</li>
                  <li>Create new student accounts for unknown emails</li>
                  <li>Skip students already enrolled in the course</li>
                </ul>
                <div className="mt-3 p-3 bg-white rounded border border-blue-200 font-mono text-xs">
                  email,name<br />
                  student1@university.edu,John Doe<br />
                  student2@university.edu,Jane Smith
                </div>
                <p className="text-xs text-blue-600 mt-2">
                  * &quot;name&quot; column is optional. If omitted, email prefix is used as name.
                </p>
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <Select
                  label="Select Course"
                  value={rosterCourseId?.toString() || ''}
                  onChange={(e) => setRosterCourseId(Number(e.target.value))}
                >
                  <option value="">Select a course...</option>
                  {courses.map((course) => (
                    <option key={course.id} value={course.id}>
                      {course.title}
                    </option>
                  ))}
                </Select>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    CSV File
                  </label>
                  <input
                    type="file"
                    accept=".csv"
                    onChange={(e) => setRosterFile(e.target.files?.[0] || null)}
                    className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-medium file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
                  />
                  {rosterFile && (
                    <p className="text-xs text-gray-500 mt-1">
                      Selected: {rosterFile.name}
                    </p>
                  )}
                </div>
              </div>

              <Button
                onClick={handleRosterUpload}
                disabled={uploadingRoster || !rosterCourseId || !rosterFile}
                className="w-full md:w-auto"
              >
                <Upload className="h-4 w-4 mr-2" />
                {uploadingRoster ? 'Uploading...' : 'Upload Roster'}
              </Button>

              {rosterResults && (
                <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                  <h4 className="font-medium text-gray-900 mb-3">Upload Results</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    <div className="text-center p-3 bg-white rounded">
                      <div className="text-2xl font-bold text-green-600">
                        {rosterResults.created_and_enrolled_count}
                      </div>
                      <div className="text-xs text-gray-500">Created & Enrolled</div>
                    </div>
                    <div className="text-center p-3 bg-white rounded">
                      <div className="text-2xl font-bold text-blue-600">
                        {rosterResults.existing_enrolled_count}
                      </div>
                      <div className="text-xs text-gray-500">Existing Enrolled</div>
                    </div>
                    <div className="text-center p-3 bg-white rounded">
                      <div className="text-2xl font-bold text-gray-600">
                        {rosterResults.already_enrolled_count}
                      </div>
                      <div className="text-xs text-gray-500">Already Enrolled</div>
                    </div>
                    <div className="text-center p-3 bg-white rounded">
                      <div className="text-2xl font-bold text-red-600">
                        {rosterResults.error_count}
                      </div>
                      <div className="text-xs text-gray-500">Errors</div>
                    </div>
                  </div>

                  {rosterResults.details?.errors?.length > 0 && (
                    <div className="mt-4">
                      <h5 className="text-sm font-medium text-red-700 mb-2">Errors:</h5>
                      <ul className="text-sm text-red-600 list-disc list-inside">
                        {rosterResults.details.errors.map((err: string, i: number) => (
                          <li key={i}>{err}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
