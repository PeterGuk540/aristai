import { getAccessToken } from './auth';

// In production (Vercel), use the proxy route to avoid CORS/mixed-content issues
// In development, call the backend directly
const isProduction = process.env.NODE_ENV === 'production';
const API_BASE = isProduction ? '/api/proxy' : (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/api';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  // Get auth token if available
  const accessToken = getAccessToken();
  const authHeaders: HeadersInit = accessToken
    ? { Authorization: `Bearer ${accessToken}` }
    : {};

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
    throw new ApiError(response.status, error.detail || `HTTP ${response.status}`);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

// For health check, we need to handle it differently since it's not under /api
const HEALTH_URL = isProduction ? '/api/proxy/../health' : (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/health';

export const api = {
  // Health - note: health endpoint might not work through proxy, but that's ok
  health: () => fetch(HEALTH_URL).then(r => r.json()).catch(() => ({ status: 'unknown' })),

  // Users
  getUsers: (role?: string) =>
    fetchApi<any[]>(`/users/${role ? `?role=${role}` : ''}`),

  getUser: (id: number) =>
    fetchApi<any>(`/users/${id}`),

  createUser: (data: { name: string; email: string; role: string }) =>
    fetchApi<any>('/users/', { method: 'POST', body: JSON.stringify(data) }),

  // Courses
  getCourses: () =>
    fetchApi<any[]>('/courses/'),

  getCourse: (id: number) =>
    fetchApi<any>(`/courses/${id}`),

  createCourse: (data: { title: string; syllabus_text?: string; objectives_json?: string[] }) =>
    fetchApi<any>('/courses/', { method: 'POST', body: JSON.stringify(data) }),

  generatePlans: (courseId: number) =>
    fetchApi<any>(`/courses/${courseId}/generate_plans`, { method: 'POST' }),

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

  unenroll: (enrollmentId: number) =>
    fetchApi<void>(`/enrollments/${enrollmentId}`, { method: 'DELETE' }),
};

export { ApiError };
