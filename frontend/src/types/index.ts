// User types
export type InstructorRequestStatus = 'none' | 'pending' | 'approved' | 'rejected';

export interface User {
  id: number;
  name: string;
  email: string;
  role: 'instructor' | 'student';
  auth_provider?: 'cognito' | 'google' | 'microsoft';
  instructor_request_status?: InstructorRequestStatus;
  instructor_request_date?: string;
  is_admin?: boolean;
  created_at: string;
}

// Course types
export interface Course {
  id: number;
  title: string;
  syllabus_text?: string;
  objectives_json?: string[];
  join_code?: string;
  created_by?: number;
  created_at: string;
  updated_at: string;
}

// Session types
export type SessionStatus = 'draft' | 'scheduled' | 'live' | 'completed';

export interface SessionPlan {
  topics?: string[];
  goals?: string | string[];
  key_concepts?: string[];
  readings?: Array<{ title: string; description: string } | string>;
  case?: { title?: string; scenario?: string; description?: string } | string;
  discussion_prompts?: string[];
  checkpoints?: string[];
  flow?: string[];
  is_materials_session?: boolean;
  description?: string;
}

export interface Session {
  id: number;
  course_id: number;
  title: string;
  date?: string;
  status: SessionStatus;
  plan_json?: SessionPlan;
  plan_version?: string;
  model_name?: string;
  prompt_version?: string;
  copilot_active?: number;
  created_at: string;
  updated_at: string;
}

export interface Case {
  id: number;
  session_id: number;
  prompt: string;
  attachments?: string[];
  created_at: string;
}

// Post types
export interface Post {
  id: number;
  session_id: number;
  user_id: number;
  content: string;
  parent_post_id?: number;
  labels_json?: string[];
  pinned: boolean;
  created_at: string;
}

// Poll types
export interface Poll {
  id: number;
  session_id: number;
  question: string;
  options_json: string[];
  created_at: string;
}

export interface PollResults {
  poll_id: number;
  question: string;
  options: string[];
  vote_counts: number[];
  total_votes: number;
}

// Intervention types
export interface Intervention {
  id: number;
  session_id: number;
  intervention_type: string;
  suggestion_json: {
    rolling_summary?: string;
    confusion_points?: Array<{
      issue: string;
      explanation: string;
      severity: 'high' | 'medium' | 'low';
      evidence_post_ids?: number[];
    }>;
    instructor_prompts?: Array<{
      prompt: string;
      purpose: string;
      target: string;
    }>;
    reengagement_activity?: {
      type: string;
      description: string;
      estimated_time?: string;
    };
    poll_suggestion?: {
      question: string;
      options: string[];
    };
    overall_assessment?: {
      engagement_level: string;
      understanding_level: string;
      discussion_quality: string;
      recommendation?: string;
    };
  };
  evidence_post_ids?: number[];
  model_name?: string;
  created_at: string;
}

// Enrollment types
export interface Enrollment {
  id: number;
  user_id: number;
  course_id: number;
  enrolled_at: string;
}

export interface EnrolledStudent {
  user_id: number;
  name: string;
  email: string;
  enrolled_at: string;
}

// Report types
export interface Report {
  id: number;
  session_id: number;
  version: string;
  report_md?: string;
  report_json?: ReportJSON;
  model_name?: string;
  prompt_version?: string;
  execution_time_seconds?: number;
  total_tokens?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  estimated_cost_usd?: number;
  error_message?: string;
  retry_count?: number;
  used_fallback?: number;
  created_at: string;
}

export interface ReportJSON {
  session_id: number;
  session_title: string;
  generated_at: string;
  summary: {
    total_posts: number;
    student_posts: number;
    instructor_posts: number;
    discussion_quality: string;
  };
  theme_clusters?: Array<{
    theme: string;
    description: string;
    post_ids: number[];
  }>;
  learning_objectives_alignment?: Array<{
    objective: string;
    coverage: string;
    evidence_post_ids: number[];
  }>;
  misconceptions?: Array<{
    post_id: number;
    misconception: string;
    correction: string;
  }>;
  best_practice_answer?: {
    summary: string;
    detailed_explanation: string;
    key_concepts: string[];
  };
  student_summary?: {
    what_you_did_well: string[];
    what_to_improve: string[];
    key_takeaways: string[];
  };
  participation?: {
    total_enrolled_students: number;
    participation_count: number;
    participation_rate: number;
    students_who_participated: Array<{
      user_id: number;
      name: string;
      post_count: number;
    }>;
    students_who_did_not_participate: Array<{
      user_id: number;
      name: string;
    }>;
  };
  answer_scores?: {
    student_scores: Array<{
      user_id: number;
      user_name?: string;
      post_id: number;
      score: number;
      key_points_covered?: string[];
      missing_points?: string[];
      feedback?: string;
    }>;
    class_statistics?: {
      average_score: number;
      highest_score: number;
      lowest_score: number;
    };
    closest_to_correct?: {
      user_id: number;
      user_name?: string;
      post_id: number;
      score: number;
    };
    furthest_from_correct?: {
      user_id: number;
      user_name?: string;
      post_id: number;
      score: number;
    };
  };
  poll_results?: Array<{
    poll_id: number;
    question: string;
    options: string[];
    vote_counts: number[];
    total_votes: number;
    percentages: number[];
    interpretation?: string;
  }>;
  observability?: {
    total_tokens: number;
    execution_time_seconds: number;
    estimated_cost_usd: number;
  };
}

// Legacy voice types removed - using ElevenLabs Agent now

// =============================================================================
// INSTRUCTOR ENHANCEMENT FEATURE TYPES
// =============================================================================

// Engagement Heatmap
export type EngagementLevel = 'highly_active' | 'active' | 'idle' | 'disengaged' | 'not_joined';

export interface StudentEngagement {
  user_id: number;
  name: string;
  email: string;
  engagement_level: EngagementLevel;
  post_count: number;
  reply_count: number;
  last_activity: string | null;
  joined_at: string | null;
}

export interface EngagementHeatmap {
  session_id: number;
  total_students: number;
  engagement_summary: Record<EngagementLevel, number>;
  students: StudentEngagement[];
  timestamp: string;
}

// Smart Facilitation
export interface FacilitationSuggestion {
  type: 'reengagement' | 'call_on_student' | 'address_questions';
  priority: 'high' | 'medium' | 'low';
  message: string;
  students?: Array<{ user_id: number; name: string; post_count: number }>;
  post_ids?: number[];
}

export interface FacilitationSuggestions {
  session_id: number;
  discussion_momentum: 'stalling' | 'active';
  posts_per_minute: number;
  suggestions: FacilitationSuggestion[];
  low_participation_count: number;
}

// Session Templates
export interface SessionTemplate {
  id: number;
  name: string;
  description?: string;
  category?: string;
  use_count: number;
  created_at: string;
}

// Breakout Groups
export interface BreakoutGroupMember {
  user_id: number;
  name: string;
}

export interface BreakoutGroup {
  id: number;
  name: string;
  topic?: string;
  member_count: number;
  members: BreakoutGroupMember[];
  post_count: number;
}

// Student Progress
export interface StudentProgress {
  user_id: number;
  user_name: string;
  total_sessions: number;
  total_posts: number;
  total_quality_posts: number;
  participation_trend: 'improving' | 'stable' | 'declining' | 'insufficient_data';
  sessions: Array<{
    session_id: number;
    session_title: string;
    session_date: string;
    post_count: number;
    quality_posts: number;
  }>;
}

// Class-level progress summary
export interface ClassProgress {
  course_id: number;
  total_students: number;
  on_track_count: number;
  needs_attention_count: number;
  students_needing_attention: Array<{
    user_id: number;
    name: string;
    sessions_attended: number;
    trend: 'improving' | 'stable' | 'declining';
  }>;
}

// Pre-Class Checkpoints
export interface PreClassCheckpoint {
  checkpoint_id: number;
  title: string;
  type: string;
  completion_rate: number;
  completed_count: number;
  incomplete_count: number;
  completed_students: Array<{ user_id: number; name: string }>;
  incomplete_students: Array<{ user_id: number; name: string }>;
}

// Session Timer
export interface SessionTimer {
  id: number;
  label: string;
  duration_seconds: number;
  remaining_seconds: number;
  is_paused: boolean;
  is_expired: boolean;
}

// AI Response Draft
export interface AIResponseDraft {
  id: number;
  draft_id?: number; // Alias for backwards compatibility
  post_id: number;
  student_name: string;
  original_question: string;
  question?: string; // Alias for backwards compatibility
  draft_response: string;
  confidence: number;
  status: string;
  created_at: string;
}

// Poll Suggestion
export interface PollSuggestion {
  type: 'opinion_poll' | 'comprehension_check' | 'concept_check';
  question: string;
  options: string[];
  context: string;
}

// Session Comparison
export interface SessionComparison {
  session_id: number;
  title: string;
  date: string;
  status: string;
  total_posts: number;
  unique_participants: number;
  participation_rate: number;
  polls_count: number;
  avg_posts_per_student: number;
}

// Post-Class Summary
export interface PostClassSummary {
  session_id: number;
  summary_text: string;
  key_topics: string[];
  follow_up_items: string[];
  participation_stats: {
    total_posts: number;
    unique_participants: number;
    avg_engagement: number;
  };
  generated_at: string;
}

// Pre-Class Insights
export interface PreClassInsights {
  session_id: number;
  total_students: number;
  completed_count: number;
  partial_count: number;
  not_started_count: number;
  checkpoints: {
    id: number;
    title: string;
    completed_count: number;
    total_count: number;
  }[];
  students_not_started: {
    user_id: number;
    name: string;
  }[];
}

// Student Lookup
export interface StudentLookup {
  user_id: number;
  name: string;
  email: string;
  total_posts: number;
  average_engagement: number;
  sessions_attended: number;
}

// API Response types
export interface TaskResponse {
  task_id: string;
  message?: string;
  status?: string;
}
