import { getIdToken } from './cognito-auth';
import { getGoogleIdToken } from './google-auth';
import { getMicrosoftIdToken } from './ms-auth';

// In production (Vercel), use the proxy route to avoid CORS/mixed-content issues.
// In development, call the backend directly.
const isProduction = process.env.NODE_ENV === 'production';
const DIRECT_API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const useProxy = isProduction;
export const API_BASE = useProxy ? '/api/proxy' : `${DIRECT_API_URL}/api`;
export const DIRECT_API_BASE = `${DIRECT_API_URL}/api`;

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
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    const message = formatApiErrorMessage(error?.detail ?? error);
    throw new ApiError(response.status, message || `HTTP ${response.status}`);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

// For health check, we need to handle it differently since it's not under /api
const HEALTH_URL = useProxy
  ? '/api/proxy/../health'
  : (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/health';

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
    return fetchApi('/voice/converse', {
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
  getCourses: () =>
    fetchApi<any[]>('/courses/'),

  getCourse: (id: number) =>
    fetchApi<any>(`/courses/${id}`),

  createCourse: (data: { title: string; syllabus_text?: string; objectives_json?: string[] }) =>
    fetchApi<any>('/courses/', { method: 'POST', body: JSON.stringify(data) }),

  generatePlans: (courseId: number) =>
    fetchApi<any>(`/courses/${courseId}/generate_plans`, { method: 'POST' }),

  regenerateJoinCode: (courseId: number) =>
    fetchApi<any>(`/courses/${courseId}/regenerate-join-code`, { method: 'POST' }),

  joinCourseByCode: (joinCode: string, userId: number) =>
    fetchApi<any>(`/courses/join?user_id=${userId}`, { method: 'POST', body: JSON.stringify({ join_code: joinCode }) }),

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
    const url = `${isProduction ? '/api/proxy' : (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/api'}/enrollments/course/${courseId}/upload-roster`;

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
};

export { ApiError };
