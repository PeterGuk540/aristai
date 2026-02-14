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

  extractLearningObjectives: async (syllabusText: string): Promise<{
    objectives: string[];
    confidence: string;
    notes: string | null;
    success: boolean;
    error: string | null;
  }> => {
    return fetchApi('/courses/extract-objectives', {
      method: 'POST',
      body: JSON.stringify({ syllabus_text: syllabusText }),
    });
  },

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

  // LMS Integrations (Canvas-first, provider-based)
  getIntegrationProviders: () =>
    fetchApi<Array<{ name: string; configured: boolean; enabled: boolean }>>('/integrations/providers'),

  listProviderConnections: (provider: string) =>
    fetchApi<Array<{
      id: number;
      provider: string;
      label: string;
      api_base_url: string;
      token_masked: string;
      is_active: boolean;
      is_default: boolean;
      created_by?: number;
      last_tested_at?: string;
      last_test_status?: string;
      last_test_error?: string;
      created_at?: string;
      updated_at?: string;
    }>>(`/integrations/${provider}/config-connections`),

  createProviderConnection: (
    provider: string,
    data: {
      label: string;
      api_base_url: string;
      api_token: string;
      is_default?: boolean;
      created_by?: number;
    }
  ) =>
    fetchApi<{
      id: number;
      provider: string;
      label: string;
      api_base_url: string;
      token_masked: string;
      is_active: boolean;
      is_default: boolean;
      last_test_status?: string;
      last_test_error?: string;
    }>(`/integrations/${provider}/config-connections`, { method: 'POST', body: JSON.stringify(data) }),

  startCanvasOAuth: (data: { label: string; api_base_url: string; created_by?: number; redirect_uri: string }) =>
    fetchApi<{ authorization_url: string; state: string }>(
      '/integrations/canvas/oauth/start',
      { method: 'POST', body: JSON.stringify(data) }
    ),

  exchangeCanvasOAuth: (data: { code: string; state: string; redirect_uri: string }) =>
    fetchApi<{
      id: number;
      provider: string;
      label: string;
      api_base_url: string;
      token_masked: string;
      is_active: boolean;
      is_default: boolean;
    }>('/integrations/canvas/oauth/exchange', { method: 'POST', body: JSON.stringify(data) }),

  activateProviderConnection: (provider: string, connectionId: number) =>
    fetchApi<any>(`/integrations/${provider}/config-connections/${connectionId}/activate`, { method: 'POST' }),

  testProviderConnection: (provider: string, connectionId: number) =>
    fetchApi<any>(`/integrations/${provider}/config-connections/${connectionId}/test`, { method: 'POST' }),

  checkIntegrationConnection: (provider: string, userId: number, connectionId?: number) =>
    fetchApi<{
      id: number;
      provider: string;
      user_id: number;
      status: string;
      provider_user_id?: string;
      provider_user_name?: string;
      last_checked_at?: string;
    }>(
      `/integrations/${provider}/connections/check?user_id=${userId}${connectionId ? `&connection_id=${connectionId}` : ''}`,
      { method: 'POST' }
    ),

  listIntegrationConnections: (provider: string, userId?: number) =>
    fetchApi<Array<{
      id: number;
      provider: string;
      user_id: number;
      status: string;
      provider_user_id?: string;
      provider_user_name?: string;
      last_checked_at?: string;
    }>>(
      `/integrations/${provider}/connections${userId ? `?user_id=${userId}` : ''}`
    ),

  getExternalCourses: (provider: string, connectionId?: number) =>
    fetchApi<Array<{
      provider: string;
      external_id: string;
      title: string;
      code?: string;
      term?: string;
    }>>(`/integrations/${provider}/courses${connectionId ? `?connection_id=${connectionId}` : ''}`),

  getExternalMaterials: (provider: string, courseExternalId: string, connectionId?: number) =>
    fetchApi<Array<{
      provider: string;
      external_id: string;
      course_external_id: string;
      title: string;
      filename: string;
      content_type: string;
      size_bytes: number;
      updated_at?: string;
      source_url?: string;
    }>>(
      `/integrations/${provider}/courses/${encodeURIComponent(courseExternalId)}/materials${connectionId ? `?connection_id=${connectionId}` : ''}`
    ),

  importExternalCourse: (
    provider: string,
    courseExternalId: string,
    data: {
      source_connection_id?: number;
      created_by?: number;
      source_course_name?: string;
    }
  ) =>
    fetchApi<{
      provider: string;
      source_connection_id?: number;
      source_course_external_id: string;
      target_course_id: number;
      target_course_title: string;
      mapping_id: number;
      created: boolean;
    }>(
      `/integrations/${provider}/courses/${encodeURIComponent(courseExternalId)}/import-course`,
      { method: 'POST', body: JSON.stringify(data) }
    ),

  listIntegrationMappings: (provider: string, targetCourseId?: number, sourceConnectionId?: number) =>
    fetchApi<Array<{
      id: number;
      provider: string;
      external_course_id: string;
      external_course_name?: string;
      source_connection_id?: number;
      target_course_id: number;
      created_by?: number;
      is_active: boolean;
      created_at?: string;
      updated_at?: string;
    }>>(
      `/integrations/${provider}/mappings?${
        [
          targetCourseId ? `target_course_id=${targetCourseId}` : '',
          sourceConnectionId ? `source_connection_id=${sourceConnectionId}` : '',
        ].filter(Boolean).join('&')
      }`
    ),

  createIntegrationMapping: (
    provider: string,
    data: {
      target_course_id: number;
      source_course_external_id: string;
      source_course_name?: string;
      source_connection_id?: number;
      created_by?: number;
    }
  ) =>
    fetchApi<{
      id: number;
      provider: string;
      external_course_id: string;
      external_course_name?: string;
      source_connection_id?: number;
      target_course_id: number;
      created_by?: number;
      is_active: boolean;
      created_at?: string;
      updated_at?: string;
    }>(`/integrations/${provider}/mappings`, { method: 'POST', body: JSON.stringify(data) }),

  importExternalMaterials: (
    provider: string,
    data: {
      target_course_id: number;
      source_course_external_id: string;
      material_external_ids: string[];
      source_connection_id?: number;
      target_session_id?: number;
      uploaded_by?: number;
      overwrite_title_prefix?: string;
    }
  ) =>
    fetchApi<{
      provider: string;
      job_id: number;
      imported_count: number;
      skipped_count: number;
      failed_count: number;
      results: Array<{
        material_external_id: string;
        status: string;
        message: string;
        created_material_id?: number;
      }>;
    }>(`/integrations/${provider}/import`, { method: 'POST', body: JSON.stringify(data) }),

  syncExternalMaterials: (
    provider: string,
    data: {
      target_course_id: number;
      source_course_external_id: string;
      source_connection_id?: number;
      target_session_id?: number;
      uploaded_by?: number;
      overwrite_title_prefix?: string;
      mapping_id?: number;
      material_external_ids?: string[];
    }
  ) =>
    fetchApi<{
      provider: string;
      job_id: number;
      imported_count: number;
      skipped_count: number;
      failed_count: number;
      results: Array<{
        material_external_id: string;
        status: string;
        message: string;
        created_material_id?: number;
      }>;
    }>(`/integrations/${provider}/sync`, { method: 'POST', body: JSON.stringify(data) }),

  listIntegrationSyncJobs: (provider?: string, targetCourseId?: number, limit: number = 20, sourceConnectionId?: number) => {
    const params = new URLSearchParams();
    if (provider) params.append('provider', provider);
    if (targetCourseId) params.append('target_course_id', String(targetCourseId));
    if (sourceConnectionId) params.append('source_connection_id', String(sourceConnectionId));
    params.append('limit', String(limit));
    return fetchApi<Array<{
      id: number;
      provider: string;
      source_course_external_id: string;
      source_connection_id?: number;
      target_course_id: number;
      target_session_id?: number;
      triggered_by?: number;
      status: string;
      requested_count: number;
      imported_count: number;
      skipped_count: number;
      failed_count: number;
      error_message?: string;
      started_at?: string;
      completed_at?: string;
      created_at?: string;
    }>>(`/integrations/sync-jobs?${params.toString()}`);
  },

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
