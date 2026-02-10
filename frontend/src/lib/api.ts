import { getIdToken } from './cognito-auth';
import { getGoogleIdToken } from './google-auth';
import { getMicrosoftIdToken } from './ms-auth';

// Always use the proxy route so browser requests stay same-origin.
const API_PROXY_BASE = '/api/proxy';
export const API_BASE = API_PROXY_BASE;

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

const formatApiErrorMessage = (detail: unknown): string => {
  if (!detail) {
    return 'Unknown error';
  }
  if (typeof detail === 'string') {
    return detail;
  }
  if (detail instanceof Error) {
    return detail.message || 'Unknown error';
  }
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
};

export const getAuthHeaders = async (): Promise<HeadersInit> => {
  // Get ID token for API calls (check Google first, then Microsoft, then Cognito SDK)
  // Note: API Gateway JWT authorizer requires ID token (has 'aud' claim), not access token
  const googleToken = getGoogleIdToken();
  const msToken = getMicrosoftIdToken();
  const idToken = googleToken || msToken || await getIdToken();

  return idToken ? { Authorization: `Bearer ${idToken}` } : {};
};

async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const authHeaders = await getAuthHeaders();

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const contentType = response.headers.get('content-type') || '';
    let errorDetail: unknown = 'Unknown error';

    if (contentType.includes('application/json')) {
      errorDetail = await response.json().catch(() => ({ detail: 'Unknown error' }));
    } else {
      errorDetail = await response.text().catch(() => 'Unknown error');
    }

    const message = formatApiErrorMessage(
      typeof errorDetail === 'object' && errorDetail !== null && 'detail' in errorDetail
        ? (errorDetail as { detail?: unknown }).detail
        : errorDetail
    );
    throw new ApiError(response.status, message || `HTTP ${response.status}`);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

// Health check lives outside /api, so use the proxy escape hatch.
const HEALTH_URL = `${API_PROXY_BASE}/../health`;

export const api = {
  // Health - note: health endpoint might not work through proxy, but that's ok
  health: () => fetch(HEALTH_URL).then(r => r.json()).catch(() => ({ status: 'unknown' })),

  voiceConverse: async (request: {
    transcript: string;
    context?: string[];
    user_id?: number;
    current_page?: string;
  }): Promise<{
    message: string;
    action?: { type: 'navigate' | 'execute' | 'info'; target?: string; executed?: boolean };
    results?: any[];
    suggestions?: string[];
  }> => {
    return fetchApi('/voice-converse/voice/converse', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  // Users
  getUsers: (role?: string) =>
    fetchApi<any[]>(`/users/${role ? `?role=${role}` : ''}`),

  getUser: (id: number) =>
    fetchApi<any>(`/users/${id}`),

  getUserByEmail: (email: string, authProvider?: 'cognito' | 'google' | 'microsoft') =>
    fetchApi<any>(`/users/by-email/${encodeURIComponent(email)}${authProvider ? `?auth_provider=${authProvider}` : ''}`),

  createUser: (data: { name: string; email: string; role: string }) =>
    fetchApi<any>('/users/', { method: 'POST', body: JSON.stringify(data) }),

  registerOrGetUser: (data: { name: string; email: string; auth_provider: 'cognito' | 'google' | 'microsoft'; cognito_sub?: string }) =>
    fetchApi<any>('/users/register-or-get', { method: 'POST', body: JSON.stringify(data) }),

  // Courses
  getCourses: (userId?: number) =>
    fetchApi<any[]>(userId ? `/courses/?user_id=${userId}` : '/courses/'),

  getCourse: (id: number) =>
    fetchApi<any>(`/courses/${id}`),

  createCourse: (data: { title: string; syllabus_text?: string; objectives_json?: string[]; created_by?: number }) =>
    fetchApi<any>('/courses/', { method: 'POST', body: JSON.stringify(data) }),

  updateCourse: (courseId: number, userId: number, data: { title?: string; syllabus_text?: string; objectives_json?: string[] }) =>
    fetchApi<any>(`/courses/${courseId}?user_id=${userId}`, { method: 'PUT', body: JSON.stringify(data) }),

  deleteCourse: (courseId: number, userId: number) =>
    fetchApi<void>(`/courses/${courseId}?user_id=${userId}`, { method: 'DELETE' }),

  generatePlans: (courseId: number) =>
    fetchApi<any>(`/courses/${courseId}/generate_plans`, { method: 'POST' }),

  regenerateJoinCode: (courseId: number) =>
    fetchApi<any>(`/courses/${courseId}/regenerate-join-code`, { method: 'POST' }),

  joinCourseByCode: (joinCode: string, userId: number) =>
    fetchApi<any>(`/courses/join?user_id=${userId}`, { method: 'POST', body: JSON.stringify({ join_code: joinCode }) }),

  uploadSyllabus: async (
    file: File,
    options?: { courseId?: number; userId?: number }
  ): Promise<{
    extracted_text: string;
    filename: string;
    file_size: number;
    material_id: number | null;
    message: string;
  }> => {
    const url = `${API_PROXY_BASE}/courses/upload-syllabus`;

    const googleToken = getGoogleIdToken();
    const msToken = getMicrosoftIdToken();
    const idToken = googleToken || msToken || await getIdToken();

    const formData = new FormData();
    formData.append('file', file);
    if (options?.courseId) formData.append('course_id', String(options.courseId));
    if (options?.userId) formData.append('user_id', String(options.userId));

    const response = await fetch(url, {
      method: 'POST',
      headers: idToken ? { Authorization: `Bearer ${idToken}` } : {},
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      const message = formatApiErrorMessage(error?.detail ?? error);
      throw new ApiError(response.status, message || `HTTP ${response.status}`);
    }

    return response.json();
  },

  getCourseSessions: (courseId: number) =>
    fetchApi<any[]>(`/courses/${courseId}/sessions`),

  // Sessions
  getSession: (id: number) =>
    fetchApi<any>(`/sessions/${id}`),

  createSession: (data: { course_id: number; title: string }) =>
    fetchApi<any>('/sessions/', { method: 'POST', body: JSON.stringify(data) }),

  updateSessionStatus: (id: number, status: string) =>
    fetchApi<any>(`/sessions/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),

  getSessionCases: (sessionId: number) =>
    fetchApi<any[]>(`/sessions/${sessionId}/cases`),

  postCase: (sessionId: number, prompt: string) =>
    fetchApi<any>(`/sessions/${sessionId}/case`, { method: 'POST', body: JSON.stringify({ prompt }) }),

  // Copilot
  startCopilot: (sessionId: number) =>
    fetchApi<any>(`/sessions/${sessionId}/start_live_copilot`, { method: 'POST' }),

  stopCopilot: (sessionId: number) =>
    fetchApi<any>(`/sessions/${sessionId}/stop_live_copilot`, { method: 'POST' }),

  getCopilotStatus: (sessionId: number) =>
    fetchApi<any>(`/sessions/${sessionId}/copilot_status`),

  getInterventions: (sessionId: number) =>
    fetchApi<any[]>(`/sessions/${sessionId}/interventions`),

  // Posts
  getSessionPosts: (sessionId: number) =>
    fetchApi<any[]>(`/posts/session/${sessionId}`),

  createPost: (sessionId: number, data: { user_id: number; content: string; parent_post_id?: number }) =>
    fetchApi<any>(`/posts/session/${sessionId}`, { method: 'POST', body: JSON.stringify(data) }),

  pinPost: (postId: number, pinned: boolean) =>
    fetchApi<any>(`/posts/${postId}/pin`, { method: 'POST', body: JSON.stringify({ pinned }) }),

  labelPost: (postId: number, labels: string[]) =>
    fetchApi<any>(`/posts/${postId}/label`, { method: 'POST', body: JSON.stringify({ labels }) }),

  // Polls
  createPoll: (sessionId: number, data: { question: string; options_json: string[] }) =>
    fetchApi<any>(`/polls/session/${sessionId}`, { method: 'POST', body: JSON.stringify(data) }),

  votePoll: (pollId: number, userId: number, optionIndex: number) =>
    fetchApi<any>(`/polls/${pollId}/vote`, { method: 'POST', body: JSON.stringify({ user_id: userId, option_index: optionIndex }) }),

  getPollResults: (pollId: number) =>
    fetchApi<any>(`/polls/${pollId}/results`),

  // Reports
  generateReport: (sessionId: number) =>
    fetchApi<any>(`/reports/session/${sessionId}/generate`, { method: 'POST' }),

  getReport: (sessionId: number) =>
    fetchApi<any>(`/reports/session/${sessionId}`),

  // Enrollments
  getEnrolledStudents: (courseId: number) =>
    fetchApi<any[]>(`/enrollments/course/${courseId}/students`),

  enrollUser: (userId: number, courseId: number) =>
    fetchApi<any>('/enrollments/', { method: 'POST', body: JSON.stringify({ user_id: userId, course_id: courseId }) }),

  enrollAllStudents: (courseId: number) =>
    fetchApi<any>(`/enrollments/course/${courseId}/enroll-all-students`, { method: 'POST' }),

  bulkEnrollStudents: (userIds: number[], courseId: number) =>
    fetchApi<any>('/enrollments/bulk', { method: 'POST', body: JSON.stringify({ user_ids: userIds, course_id: courseId }) }),

  unenroll: (enrollmentId: number) =>
    fetchApi<void>(`/enrollments/${enrollmentId}`, { method: 'DELETE' }),

  getUserEnrolledCourses: (userId: number) =>
    fetchApi<any[]>(`/enrollments/user/${userId}/courses`),

  // Instructor Request Workflow
  requestInstructorStatus: (userId: number) =>
    fetchApi<any>(`/users/${userId}/request-instructor`, { method: 'POST' }),

  getInstructorRequests: (adminUserId: number) =>
    fetchApi<any[]>(`/users/instructor-requests?admin_user_id=${adminUserId}`),

  approveInstructorRequest: (userId: number, adminUserId: number) =>
    fetchApi<any>(`/users/${userId}/approve-instructor?admin_user_id=${adminUserId}`, { method: 'POST' }),

  rejectInstructorRequest: (userId: number, adminUserId: number) =>
    fetchApi<any>(`/users/${userId}/reject-instructor?admin_user_id=${adminUserId}`, { method: 'POST' }),

  // Voice - ElevenLabs Agent (no legacy TTS API methods needed)

  // CSV Roster Upload
  uploadRosterCsv: async (courseId: number, file: File) => {
    const url = `${API_PROXY_BASE}/enrollments/course/${courseId}/upload-roster`;

    const googleToken = getGoogleIdToken();
    const msToken = getMicrosoftIdToken();
    const idToken = googleToken || msToken || await getIdToken();

    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(url, {
      method: 'POST',
      headers: idToken ? { Authorization: `Bearer ${idToken}` } : {},
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      const message = formatApiErrorMessage(error?.detail ?? error);
      throw new ApiError(response.status, message || `HTTP ${response.status}`);
    }

    return response.json();
  },

  // Course Materials
  getCourseMaterials: (courseId: number, sessionId?: number) =>
    fetchApi<{ materials: any[]; total: number }>(
      `/courses/${courseId}/materials${sessionId ? `?session_id=${sessionId}` : ''}`
    ),

  getSessionMaterials: (sessionId: number) =>
    fetchApi<{ materials: any[]; total: number }>(`/sessions/${sessionId}/materials`),

  getMaterial: (courseId: number, materialId: number) =>
    fetchApi<any>(`/courses/${courseId}/materials/${materialId}`),

  uploadMaterial: async (
    courseId: number,
    file: File,
    options?: { title?: string; description?: string; sessionId?: number; userId?: number }
  ) => {
    const url = `${API_PROXY_BASE}/courses/${courseId}/materials`;

    const googleToken = getGoogleIdToken();
    const msToken = getMicrosoftIdToken();
    const idToken = googleToken || msToken || await getIdToken();

    const formData = new FormData();
    formData.append('file', file);
    if (options?.title) formData.append('title', options.title);
    if (options?.description) formData.append('description', options.description);
    if (options?.sessionId) formData.append('session_id', String(options.sessionId));
    if (options?.userId) formData.append('user_id', String(options.userId));

    const response = await fetch(url, {
      method: 'POST',
      headers: idToken ? { Authorization: `Bearer ${idToken}` } : {},
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      const message = formatApiErrorMessage(error?.detail ?? error);
      throw new ApiError(response.status, message || `HTTP ${response.status}`);
    }

    return response.json();
  },

  updateMaterial: (courseId: number, materialId: number, data: { title?: string; description?: string }) =>
    fetchApi<any>(`/courses/${courseId}/materials/${materialId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  replaceMaterial: async (courseId: number, materialId: number, file: File, userId?: number) => {
    const url = `${API_PROXY_BASE}/courses/${courseId}/materials/${materialId}/replace`;

    const googleToken = getGoogleIdToken();
    const msToken = getMicrosoftIdToken();
    const idToken = googleToken || msToken || await getIdToken();

    const formData = new FormData();
    formData.append('file', file);
    if (userId) formData.append('user_id', String(userId));

    const response = await fetch(url, {
      method: 'POST',
      headers: idToken ? { Authorization: `Bearer ${idToken}` } : {},
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      const message = formatApiErrorMessage(error?.detail ?? error);
      throw new ApiError(response.status, message || `HTTP ${response.status}`);
    }

    return response.json();
  },

  deleteMaterial: (courseId: number, materialId: number) =>
    fetchApi<void>(`/courses/${courseId}/materials/${materialId}`, { method: 'DELETE' }),

  getMaterialDownloadUrl: (courseId: number, materialId: number) =>
    `${API_PROXY_BASE}/courses/${courseId}/materials/${materialId}/download`,

  // =============================================================================
  // INSTRUCTOR ENHANCEMENT FEATURES
  // =============================================================================

  // Engagement Heatmap
  getEngagementHeatmap: (sessionId: number) =>
    fetchApi<any>(`/instructor/engagement/heatmap/${sessionId}`),

  getDisengagedStudents: (sessionId: number) =>
    fetchApi<any>(`/instructor/engagement/needs-attention/${sessionId}`),

  // Smart Facilitation
  getFacilitationSuggestions: (sessionId: number) =>
    fetchApi<any>(`/instructor/facilitation/suggestions/${sessionId}`),

  suggestNextStudent: (sessionId: number) =>
    fetchApi<any>(`/instructor/facilitation/next-student/${sessionId}`),

  // Quick Polls
  getPollSuggestions: (sessionId: number) =>
    fetchApi<any>(`/instructor/polls/suggestions/${sessionId}`),

  createQuickPoll: (sessionId: number, question: string, options: string[]) =>
    fetchApi<any>('/instructor/polls/quick-create', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, question, options }),
    }),

  // Session Templates
  getTemplates: (userId?: number, category?: string) => {
    const params = new URLSearchParams();
    if (userId) params.append('user_id', String(userId));
    if (category) params.append('category', category);
    return fetchApi<any>(`/instructor/templates?${params.toString()}`);
  },

  saveAsTemplate: (sessionId: number, templateName: string, userId: number, description?: string, category?: string) =>
    fetchApi<any>('/instructor/templates/save', {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        template_name: templateName,
        user_id: userId,
        description,
        category,
      }),
    }),

  createFromTemplate: (templateId: number, courseId: number, title: string) =>
    fetchApi<any>('/instructor/templates/create-session', {
      method: 'POST',
      body: JSON.stringify({ template_id: templateId, course_id: courseId, title }),
    }),

  cloneSession: (sessionId: number, newTitle: string, courseId?: number) =>
    fetchApi<any>('/instructor/sessions/clone', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, new_title: newTitle, course_id: courseId }),
    }),

  // Student Progress
  getStudentProgress: (userId: number, courseId?: number) =>
    fetchApi<any>(`/instructor/progress/student/${userId}${courseId ? `?course_id=${courseId}` : ''}`),

  getClassProgress: (courseId: number) =>
    fetchApi<any>(`/instructor/progress/class/${courseId}`),

  // Breakout Groups
  createBreakoutGroups: (sessionId: number, numGroups: number, assignment: string = 'random') =>
    fetchApi<any>('/instructor/breakout/create', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, num_groups: numGroups, assignment }),
    }),

  getBreakoutGroups: (sessionId: number) =>
    fetchApi<any>(`/instructor/breakout/${sessionId}`),

  dissolveBreakoutGroups: (sessionId: number) =>
    fetchApi<any>(`/instructor/breakout/${sessionId}`, { method: 'DELETE' }),

  // Pre-Class Insights
  createPreclassCheckpoint: (sessionId: number, title: string, description?: string, checkpointType: string = 'reading') =>
    fetchApi<any>('/instructor/preclass/checkpoint', {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        title,
        description,
        checkpoint_type: checkpointType,
      }),
    }),

  getPreclassStatus: (sessionId: number) =>
    fetchApi<any>(`/instructor/preclass/status/${sessionId}`),

  getPreClassInsights: (sessionId: number) =>
    fetchApi<any>(`/instructor/preclass/status/${sessionId}`),

  // Post-Class Follow-ups
  getSessionSummary: (sessionId: number) =>
    fetchApi<any>(`/instructor/postclass/summary/${sessionId}`),

  getPostClassSummary: (sessionId: number) =>
    fetchApi<any>(`/instructor/postclass/summary/${sessionId}`),

  generateSessionSummary: (sessionId: number) =>
    fetchApi<any>(`/instructor/postclass/generate-summary/${sessionId}`, { method: 'POST' }),

  sendSummaryToStudents: (sessionId: number) =>
    fetchApi<any>(`/instructor/postclass/send-summary/${sessionId}`, { method: 'POST' }),

  getUnresolvedTopics: (sessionId: number) =>
    fetchApi<any>(`/instructor/postclass/unresolved/${sessionId}`),

  // Comparative Analytics
  compareSessions: (sessionIds: number[]) =>
    fetchApi<any>('/instructor/analytics/compare', {
      method: 'POST',
      body: JSON.stringify({ session_ids: sessionIds }),
    }),

  compareCourseSessions: (courseId: number) =>
    fetchApi<any>(`/instructor/analytics/compare/course/${courseId}`),

  getCourseAnalytics: (courseId: number) =>
    fetchApi<any>(`/instructor/analytics/course/${courseId}`),

  // Timer
  startTimer: (sessionId: number, durationSeconds: number, label: string = 'Discussion') =>
    fetchApi<any>('/instructor/timer/start', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, duration_seconds: durationSeconds, label }),
    }),

  getTimerStatus: (sessionId: number) =>
    fetchApi<any>(`/instructor/timer/status/${sessionId}`),

  pauseTimer: (timerId: number) =>
    fetchApi<any>(`/instructor/timer/${timerId}/pause`, { method: 'POST' }),

  resumeTimer: (timerId: number) =>
    fetchApi<any>(`/instructor/timer/${timerId}/resume`, { method: 'POST' }),

  stopTimer: (timerId: number) =>
    fetchApi<any>(`/instructor/timer/${timerId}/stop`, { method: 'POST' }),

  // Student Lookup
  lookupStudent: (userId: number, sessionId?: number) =>
    fetchApi<any>(`/instructor/student/${userId}${sessionId ? `?session_id=${sessionId}` : ''}`),

  searchStudents: (query: string, courseId?: number) =>
    fetchApi<any>('/instructor/student/search', {
      method: 'POST',
      body: JSON.stringify({ query, course_id: courseId }),
    }),

  // AI Teaching Assistant
  generateAIDraft: (postId: number, sessionId: number) =>
    fetchApi<any>(`/instructor/ai/generate-draft/${postId}?session_id=${sessionId}`, { method: 'POST' }),

  getPendingAIDrafts: (sessionId: number) =>
    fetchApi<any>(`/instructor/ai/pending-drafts/${sessionId}`),

  approveAIDraft: (draftId: number, instructorId: number, editedContent?: string) =>
    fetchApi<any>('/instructor/ai/approve', {
      method: 'POST',
      body: JSON.stringify({ draft_id: draftId, instructor_id: instructorId, edited_content: editedContent }),
    }),

  rejectAIDraft: (draftId: number, instructorId: number) =>
    fetchApi<any>(`/instructor/ai/reject/${draftId}?instructor_id=${instructorId}`, { method: 'POST' }),

  editAIDraft: (draftId: number, editedContent: string) =>
    fetchApi<any>(`/instructor/ai/edit/${draftId}`, {
      method: 'PUT',
      body: JSON.stringify({ edited_content: editedContent }),
    }),
};

export { ApiError };
