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
  Mic,
  MicOff,
  Volume2,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useUser } from '@/lib/context';
import { Course, Session, Intervention, PollResults, User, VoicePlan, VoiceStepResult, VoiceAuditEntry } from '@/types';
import { formatTimestamp } from '@/lib/utils';
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

export default function ConsolePage() {
  const { isInstructor, isAdmin, currentUser } = useUser();
  const [courses, setCourses] = useState<Course[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
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

  // Voice assistant
  const [isRecording, setIsRecording] = useState(false);
  const [mediaRecorderRef, setMediaRecorderRef] = useState<MediaRecorder | null>(null);
  const [voiceTranscript, setVoiceTranscript] = useState('');
  const [voiceTextInput, setVoiceTextInput] = useState('');
  const [voicePlan, setVoicePlan] = useState<VoicePlan | null>(null);
  const [voiceResults, setVoiceResults] = useState<VoiceStepResult[]>([]);
  const [voiceSummary, setVoiceSummary] = useState('');
  const [voiceLoading, setVoiceLoading] = useState(false);
  const [voiceAudits, setVoiceAudits] = useState<VoiceAuditEntry[]>([]);
  const [voiceError, setVoiceError] = useState('');

  const fetchCourses = async () => {
    try {
      const data = await api.getCourses();
      setCourses(data);
      if (data.length > 0 && !selectedCourseId) {
        setSelectedCourseId(data[0].id);
      }
    } catch (error) {
      console.error('Failed to fetch courses:', error);
    }
  };

  const fetchSessions = async (courseId: number) => {
    try {
      const data = await api.getCourseSessions(courseId);
      const liveSessions = data.filter((s: Session) => s.status === 'live');
      setSessions(liveSessions);
      if (liveSessions.length > 0) {
        setSelectedSessionId(liveSessions[0].id);
      } else {
        setSelectedSessionId(null);
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

  // Voice assistant handlers
  const startRecording = async () => {
    setVoiceError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      const chunks: Blob[] = [];
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: 'audio/webm' });
        await processAudio(blob);
      };
      recorder.start();
      setMediaRecorderRef(recorder);
      setIsRecording(true);
    } catch (err: any) {
      setVoiceError('Microphone access denied or unavailable.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef && mediaRecorderRef.state !== 'inactive') {
      mediaRecorderRef.stop();
    }
    setIsRecording(false);
  };

  const processAudio = async (blob: Blob) => {
    setVoiceLoading(true);
    setVoiceError('');
    setVoicePlan(null);
    setVoiceResults([]);
    setVoiceSummary('');
    try {
      const transcribeResult = await api.transcribeAudio(blob);
      setVoiceTranscript(transcribeResult.transcript);
      const planResult = await api.voicePlan(transcribeResult.transcript);
      setVoicePlan(planResult.plan);
    } catch (err: any) {
      setVoiceError('Voice processing failed: ' + (err.message || 'Unknown error'));
    } finally {
      setVoiceLoading(false);
    }
  };

  const handleTextPlan = async () => {
    if (!voiceTextInput.trim()) return;
    setVoiceLoading(true);
    setVoiceError('');
    setVoicePlan(null);
    setVoiceResults([]);
    setVoiceSummary('');
    try {
      setVoiceTranscript(voiceTextInput);
      const planResult = await api.voicePlan(voiceTextInput);
      setVoicePlan(planResult.plan);
      setVoiceTextInput('');
    } catch (err: any) {
      setVoiceError('Planning failed: ' + (err.message || 'Unknown error'));
    } finally {
      setVoiceLoading(false);
    }
  };

  const handleConfirmExecute = async () => {
    if (!voicePlan) return;
    setVoiceLoading(true);
    setVoiceError('');
    try {
      const result = await api.voiceExecute(voicePlan, true, currentUser?.id);
      setVoiceResults(result.results);
      setVoiceSummary(result.summary);
      // TTS via browser SpeechSynthesis
      if (result.summary && 'speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(result.summary);
        speechSynthesis.speak(utterance);
      }
    } catch (err: any) {
      setVoiceError('Execution failed: ' + (err.message || 'Unknown error'));
    } finally {
      setVoiceLoading(false);
    }
  };

  const handleExecuteReadOnly = async () => {
    if (!voicePlan) return;
    setVoiceLoading(true);
    setVoiceError('');
    try {
      const result = await api.voiceExecute(voicePlan, false, currentUser?.id);
      setVoiceResults(result.results);
      setVoiceSummary(result.summary);
      if (result.summary && 'speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(result.summary);
        speechSynthesis.speak(utterance);
      }
    } catch (err: any) {
      setVoiceError('Execution failed: ' + (err.message || 'Unknown error'));
    } finally {
      setVoiceLoading(false);
    }
  };

  const fetchVoiceAudits = async () => {
    try {
      const result = await api.voiceAudit(currentUser?.id);
      setVoiceAudits(result.audits);
    } catch (err) {
      console.error('Failed to fetch voice audits:', err);
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
                          ? 'error'
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

  if (!isInstructor) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="py-8 text-center text-gray-500">
            <Bot className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p>The Instructor Console is only available to instructors.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Instructor Console</h1>
          <p className="text-gray-600">AI copilot and live session tools</p>
        </div>
      </div>

      {/* Course & Session Selector */}
      <div className="grid md:grid-cols-2 gap-4 mb-6">
        <Select
          label="Select Course"
          value={selectedCourseId?.toString() || ''}
          onChange={(e) => setSelectedCourseId(Number(e.target.value))}
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
          onChange={(e) => setSelectedSessionId(Number(e.target.value))}
          disabled={!selectedCourseId}
        >
          <option value="">Select a session...</option>
          {sessions.map((session) => (
            <option key={session.id} value={session.id}>
              {session.title} (ID: {session.id})
            </option>
          ))}
        </Select>
      </div>

      <Tabs defaultValue={selectedSessionId ? "copilot" : (isAdmin ? "requests" : "copilot")}>
        <TabsList>
          <TabsTrigger value="copilot" disabled={!selectedSessionId}>
            AI Copilot
          </TabsTrigger>
          <TabsTrigger value="polls" disabled={!selectedSessionId}>
            Polls
          </TabsTrigger>
          <TabsTrigger value="cases" disabled={!selectedSessionId}>
            Post Case
          </TabsTrigger>
          <TabsTrigger value="voice">
            <Mic className="h-4 w-4 mr-1" />
            Voice Assistant
          </TabsTrigger>
          {isAdmin && (
            <TabsTrigger value="requests">
              Instructor Requests
              {instructorRequests.length > 0 && (
                <Badge variant="error" className="ml-2">{instructorRequests.length}</Badge>
              )}
            </TabsTrigger>
          )}
          {isAdmin && (
            <TabsTrigger value="roster">
              <FileSpreadsheet className="h-4 w-4 mr-1" />
              Roster Upload
            </TabsTrigger>
          )}
        </TabsList>

        {!selectedSessionId && (
          <div className="mt-4 mb-4 p-4 bg-gray-50 rounded-lg text-center text-gray-600">
            <Bot className="h-8 w-8 mx-auto mb-2 text-gray-400" />
            <p className="text-sm">Select a live session above to use AI Copilot, Polls, and Post Case features.</p>
          </div>
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
                        <Button onClick={handleStartCopilot} className="w-full">
                          <Play className="h-4 w-4 mr-2" />
                          Start Copilot
                        </Button>
                      ) : (
                        <Button
                          onClick={handleStopCopilot}
                          variant="secondary"
                          className="w-full"
                        >
                          <Square className="h-4 w-4 mr-2" />
                          Stop Copilot
                        </Button>
                      )}

                      <Button
                        onClick={fetchInterventions}
                        variant="outline"
                        className="w-full"
                      >
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Refresh Interventions
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
                      <Button variant="outline" size="sm" onClick={addPollOption}>
                        Add Option
                      </Button>
                    )}
                  </div>

                  <Button
                    onClick={handleCreatePoll}
                    disabled={creatingPoll || !pollQuestion.trim()}
                    className="w-full"
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
                />

                <Button
                  onClick={handlePostCase}
                  disabled={postingCase || !casePrompt.trim()}
                >
                  <MessageSquare className="h-4 w-4 mr-2" />
                  Post Case
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="voice">
            <div className="grid lg:grid-cols-2 gap-6">
              {/* Left column: Input + Plan */}
              <div className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Mic className="h-5 w-5" />
                      Voice Input
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* Push-to-talk */}
                    <div>
                      <Button
                        onMouseDown={startRecording}
                        onMouseUp={stopRecording}
                        onMouseLeave={() => { if (isRecording) stopRecording(); }}
                        variant={isRecording ? 'danger' : 'primary'}
                        disabled={voiceLoading}
                        className="w-full"
                      >
                        {isRecording ? (
                          <><MicOff className="h-4 w-4 mr-2" />Recording... Release to stop</>
                        ) : (
                          <><Mic className="h-4 w-4 mr-2" />Hold to Talk</>
                        )}
                      </Button>
                    </div>

                    {/* Text fallback */}
                    <div className="flex gap-2">
                      <Input
                        placeholder="Or type a command..."
                        value={voiceTextInput}
                        onChange={(e) => setVoiceTextInput(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleTextPlan(); }}
                      />
                      <Button
                        onClick={handleTextPlan}
                        disabled={voiceLoading || !voiceTextInput.trim()}
                        variant="outline"
                      >
                        Send
                      </Button>
                    </div>

                    {voiceLoading && (
                      <p className="text-sm text-gray-500 animate-pulse">Processing...</p>
                    )}

                    {voiceError && (
                      <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                        {voiceError}
                      </div>
                    )}

                    {voiceTranscript && (
                      <div className="p-3 bg-gray-50 rounded">
                        <h4 className="text-sm font-medium text-gray-700 mb-1">Transcript</h4>
                        <p className="text-sm text-gray-600">{voiceTranscript}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Action Plan */}
                {voicePlan && (
                  <Card>
                    <CardHeader>
                      <CardTitle>Action Plan</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="p-3 bg-blue-50 rounded">
                        <p className="text-sm font-medium text-blue-900">{voicePlan.intent}</p>
                        <p className="text-xs text-blue-700 mt-1">{voicePlan.rationale}</p>
                      </div>

                      <div className="space-y-2">
                        {voicePlan.steps.map((step, i) => (
                          <div
                            key={i}
                            className={`p-2 rounded border-l-4 ${
                              step.mode === 'write'
                                ? 'bg-orange-50 border-orange-500'
                                : 'bg-blue-50 border-blue-500'
                            }`}
                          >
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium">{step.tool_name}</span>
                              <Badge variant={step.mode === 'write' ? 'warning' : 'info'}>
                                {step.mode}
                              </Badge>
                            </div>
                            <pre className="text-xs text-gray-500 mt-1 whitespace-pre-wrap">
                              {JSON.stringify(step.args, null, 2)}
                            </pre>
                          </div>
                        ))}
                      </div>

                      <div className="flex gap-2 pt-2">
                        {voicePlan.required_confirmations.length > 0 ? (
                          <Button onClick={handleConfirmExecute} disabled={voiceLoading}>
                            <CheckCircle className="h-4 w-4 mr-2" />
                            Confirm & Execute
                          </Button>
                        ) : voicePlan.steps.length > 0 ? (
                          <Button onClick={handleExecuteReadOnly} disabled={voiceLoading}>
                            <Play className="h-4 w-4 mr-2" />
                            Execute (Read Only)
                          </Button>
                        ) : null}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>

              {/* Right column: Results + Audit */}
              <div className="space-y-4">
                {/* Results */}
                {voiceResults.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle>Results</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {voiceSummary && (
                        <div className="p-3 bg-green-50 rounded flex items-start gap-2">
                          <Volume2 className="h-4 w-4 text-green-600 mt-0.5 flex-shrink-0" />
                          <p className="text-sm text-green-800">{voiceSummary}</p>
                        </div>
                      )}
                      <div className="space-y-2">
                        {voiceResults.map((r, i) => (
                          <div
                            key={i}
                            className={`p-2 rounded ${
                              r.success
                                ? 'bg-green-50'
                                : r.skipped
                                ? 'bg-yellow-50'
                                : 'bg-red-50'
                            }`}
                          >
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium">{r.tool_name}</span>
                              {r.success && <Badge variant="success">OK</Badge>}
                              {r.skipped && <Badge variant="warning">Skipped</Badge>}
                              {!r.success && !r.skipped && <Badge variant="error">Error</Badge>}
                            </div>
                            {r.error && (
                              <p className="text-xs text-red-600 mt-1">{r.error}</p>
                            )}
                            {r.skipped_reason && (
                              <p className="text-xs text-yellow-700 mt-1">{r.skipped_reason}</p>
                            )}
                            {r.success && r.result && (
                              <pre className="text-xs text-gray-500 mt-1 whitespace-pre-wrap max-h-32 overflow-auto">
                                {JSON.stringify(r.result, null, 2)}
                              </pre>
                            )}
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Audit Trail */}
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle>Audit Trail</CardTitle>
                      <Button onClick={fetchVoiceAudits} variant="outline" size="sm">
                        <RefreshCw className="h-4 w-4 mr-1" />
                        Refresh
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {voiceAudits.length === 0 ? (
                      <p className="text-sm text-gray-500 text-center py-4">
                        No voice audit entries yet. Use the voice assistant to see history here.
                      </p>
                    ) : (
                      <div className="space-y-2 max-h-[400px] overflow-auto">
                        {voiceAudits.map((a) => (
                          <div key={a.id} className="p-3 bg-gray-50 rounded">
                            <p className="text-sm font-medium text-gray-900">
                              {a.plan_json?.intent || 'Unknown intent'}
                            </p>
                            <div className="flex items-center gap-3 mt-1">
                              <span className="text-xs text-gray-500">
                                {formatTimestamp(a.created_at)}
                              </span>
                              <span className="text-xs text-gray-400">
                                {a.tool_calls?.length || 0} tool calls
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
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
