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
} from 'lucide-react';
import { api } from '@/lib/api';
import { useUser } from '@/lib/context';
import { Course, Session, Intervention, PollResults, User } from '@/types';
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
  const { isInstructor } = useUser();
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
    setLoadingRequests(true);
    try {
      const requests = await api.getInstructorRequests();
      setInstructorRequests(requests);
    } catch (error) {
      console.error('Failed to fetch instructor requests:', error);
    } finally {
      setLoadingRequests(false);
    }
  };

  const handleApproveRequest = async (userId: number) => {
    try {
      await api.approveInstructorRequest(userId);
      fetchInstructorRequests();
    } catch (error) {
      console.error('Failed to approve request:', error);
      alert('Failed to approve request');
    }
  };

  const handleRejectRequest = async (userId: number) => {
    try {
      await api.rejectInstructorRequest(userId);
      fetchInstructorRequests();
    } catch (error) {
      console.error('Failed to reject request:', error);
      alert('Failed to reject request');
    }
  };

  useEffect(() => {
    fetchCourses();
    fetchInstructorRequests();
  }, []);

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

      {!selectedSessionId ? (
        <Card>
          <CardContent className="py-8 text-center text-gray-500">
            <Bot className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p>Select a live session to use the instructor console.</p>
          </CardContent>
        </Card>
      ) : (
        <Tabs defaultValue="copilot">
          <TabsList>
            <TabsTrigger value="copilot">AI Copilot</TabsTrigger>
            <TabsTrigger value="polls">Polls</TabsTrigger>
            <TabsTrigger value="cases">Post Case</TabsTrigger>
            <TabsTrigger value="requests">
              Instructor Requests
              {instructorRequests.length > 0 && (
                <Badge variant="error" className="ml-2">{instructorRequests.length}</Badge>
              )}
            </TabsTrigger>
          </TabsList>

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
        </Tabs>
      )}
    </div>
  );
}
