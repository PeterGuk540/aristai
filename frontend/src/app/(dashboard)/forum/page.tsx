'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  MessageSquare,
  Send,
  Pin,
  Tag,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  FileText,
  User,
  Clock,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useUser } from '@/lib/context';
import { Course, Session, Post, Case } from '@/types';
import { formatTimestamp } from '@/lib/utils';
import { useTranslations } from 'next-intl';
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Select,
  Textarea,
  Badge,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from '@/components/ui';

const LABEL_OPTIONS = [
  'insightful',
  'question',
  'misconception',
  'evidence',
  'synthesis',
  'clarification',
];

interface PostWithReplies extends Post {
  replies?: PostWithReplies[];
  user_name?: string;
}

export default function ForumPage() {
  const { currentUser: user, isInstructor } = useUser();
  const t = useTranslations();
  const [courses, setCourses] = useState<Course[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [cases, setCases] = useState<Case[]>([]);
  const [posts, setPosts] = useState<PostWithReplies[]>([]);
  const [loading, setLoading] = useState(false);

  // New post form
  const [newPostContent, setNewPostContent] = useState('');
  const [replyingTo, setReplyingTo] = useState<number | null>(null);
  const [replyContent, setReplyContent] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Moderation
  const [expandedPosts, setExpandedPosts] = useState<Set<number>>(new Set());

  // Active tab state for voice control
  const [activeTab, setActiveTab] = useState<string>('discussion');

  // Listen for voice tab switching events
  useEffect(() => {
    const handleVoiceTabSwitch = (event: CustomEvent) => {
      const { tabName, target } = event.detail || {};
      console.log('🎤 Forum: Voice tab switch received:', { tabName, target });

      // Normalize the tab name
      let normalizedTab = (tabName || '').toLowerCase().replace(/\s+/g, '');

      // Map common names to tab values
      const tabMap: Record<string, string> = {
        'cases': 'cases',
        'case': 'cases',
        'casestudies': 'cases',
        'casestudy': 'cases',
        'discussion': 'discussion',
        'discussions': 'discussion',
        'posts': 'discussion',
        'forum': 'discussion',
      };

      const targetTab = tabMap[normalizedTab] || normalizedTab;
      console.log('🎤 Forum: Switching to tab:', targetTab);
      setActiveTab(targetTab);
    };

    // Listen for both event types
    window.addEventListener('ui.switchTab', handleVoiceTabSwitch as EventListener);
    window.addEventListener('voice-select-tab', handleVoiceTabSwitch as EventListener);

    return () => {
      window.removeEventListener('ui.switchTab', handleVoiceTabSwitch as EventListener);
      window.removeEventListener('voice-select-tab', handleVoiceTabSwitch as EventListener);
    };
  }, []);

  const fetchCourses = async () => {
    try {
      if (!user) return;

      if (user.is_admin) {
        // Admin sees all courses
        const data = await api.getCourses(user.id);
        setCourses(data);
        if (data.length > 0 && !selectedCourseId) {
          setSelectedCourseId(data[0].id);
        }
      } else if (isInstructor) {
        // Instructors see only their own courses
        const data = await api.getCourses(user.id);
        setCourses(data);
        if (data.length > 0 && !selectedCourseId) {
          setSelectedCourseId(data[0].id);
        }
      } else {
        // Students only see courses they're enrolled in
        const enrolledCourses = await api.getUserEnrolledCourses(user.id);
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
      const data = await api.getCourseSessions(courseId);
      // Filter to only live sessions for forum
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

  const fetchForumData = useCallback(async () => {
    if (!selectedSessionId) return;

    setLoading(true);
    try {
      const [casesData, postsData] = await Promise.all([
        api.getSessionCases(selectedSessionId),
        api.getSessionPosts(selectedSessionId),
      ]);
      setCases(casesData);
      // Organize posts into threads
      const organized = organizePostsIntoThreads(postsData);
      setPosts(organized);
    } catch (error) {
      console.error('Failed to fetch forum data:', error);
    } finally {
      setLoading(false);
    }
  }, [selectedSessionId]);

  useEffect(() => {
    if (user) {
      fetchCourses();
    }
  }, [user, isInstructor]);

  useEffect(() => {
    if (selectedCourseId) {
      fetchSessions(selectedCourseId);
    }
  }, [selectedCourseId]);

  useEffect(() => {
    if (selectedSessionId) {
      fetchForumData();
    }
  }, [selectedSessionId, fetchForumData]);

  // Organize flat posts into threaded structure
  const organizePostsIntoThreads = (flatPosts: Post[]): PostWithReplies[] => {
    const postMap = new Map<number, PostWithReplies>();
    const rootPosts: PostWithReplies[] = [];

    // First pass: create map
    flatPosts.forEach((post) => {
      postMap.set(post.id, { ...post, replies: [] });
    });

    // Second pass: organize into threads
    flatPosts.forEach((post) => {
      const postWithReplies = postMap.get(post.id)!;
      if (post.parent_post_id) {
        const parent = postMap.get(post.parent_post_id);
        if (parent) {
          parent.replies = parent.replies || [];
          parent.replies.push(postWithReplies);
        } else {
          rootPosts.push(postWithReplies);
        }
      } else {
        rootPosts.push(postWithReplies);
      }
    });

    // Sort by created_at descending
    return rootPosts.sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  };

  const handleCreatePost = async () => {
    if (!selectedSessionId || !newPostContent.trim() || !user) return;

    setSubmitting(true);
    try {
      await api.createPost(selectedSessionId, {
        user_id: user.id,
        content: newPostContent,
      });
      setNewPostContent('');
      fetchForumData();
    } catch (error) {
      console.error('Failed to create post:', error);
      alert('Failed to create post');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReply = async (parentId: number) => {
    if (!selectedSessionId || !replyContent.trim() || !user) return;

    setSubmitting(true);
    try {
      await api.createPost(selectedSessionId, {
        user_id: user.id,
        content: replyContent,
        parent_post_id: parentId,
      });
      setReplyContent('');
      setReplyingTo(null);
      fetchForumData();
    } catch (error) {
      console.error('Failed to reply:', error);
      alert('Failed to reply');
    } finally {
      setSubmitting(false);
    }
  };

  const handlePinPost = async (postId: number, currentPinned: boolean) => {
    try {
      await api.pinPost(postId, !currentPinned);
      fetchForumData();
    } catch (error) {
      console.error('Failed to pin/unpin post:', error);
    }
  };

  const handleLabelPost = async (postId: number, label: string) => {
    const post = findPost(posts, postId);
    if (!post) return;

    const currentLabels = post.labels_json || [];
    let newLabels: string[];

    if (currentLabels.includes(label)) {
      newLabels = currentLabels.filter((l) => l !== label);
    } else {
      newLabels = [...currentLabels, label];
    }

    try {
      await api.labelPost(postId, newLabels);
      fetchForumData();
    } catch (error) {
      console.error('Failed to label post:', error);
    }
  };

  const findPost = (
    postList: PostWithReplies[],
    postId: number
  ): PostWithReplies | null => {
    for (const post of postList) {
      if (post.id === postId) return post;
      if (post.replies) {
        const found = findPost(post.replies, postId);
        if (found) return found;
      }
    }
    return null;
  };

  const toggleExpand = (postId: number) => {
    setExpandedPosts((prev) => {
      const next = new Set(prev);
      if (next.has(postId)) {
        next.delete(postId);
      } else {
        next.add(postId);
      }
      return next;
    });
  };

  const renderPost = (post: PostWithReplies, depth = 0) => {
    const hasReplies = post.replies && post.replies.length > 0;
    const isExpanded = expandedPosts.has(post.id);
    const isReplying = replyingTo === post.id;

    return (
      <div
        key={post.id}
        className={`${depth > 0 ? 'ml-6 border-l-2 border-gray-200 pl-4' : ''}`}
      >
        <div
          className={`p-4 rounded-lg ${
            post.pinned ? 'bg-yellow-50 border border-yellow-200' : 'bg-white border'
          } ${depth === 0 ? 'mb-4' : 'mt-3'}`}
        >
          {/* Post Header */}
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <User className="h-4 w-4 text-gray-400" />
              <span className="text-sm font-medium text-gray-700">
                User #{post.user_id}
              </span>
              <Clock className="h-3 w-3 text-gray-400 ml-2" />
              <span className="text-xs text-gray-500">
                {formatTimestamp(post.created_at)}
              </span>
              {post.pinned && (
                <Badge variant="warning" className="ml-2">
                  <Pin className="h-3 w-3 mr-1" />
                  Pinned
                </Badge>
              )}
            </div>
            <span className="text-xs text-gray-400">#{post.id}</span>
          </div>

          {/* Post Content */}
          <p className="text-gray-800 whitespace-pre-wrap mb-3">{post.content}</p>

          {/* Labels */}
          {post.labels_json && post.labels_json.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-3">
              {post.labels_json.map((label) => (
                <Badge key={label} variant="info">
                  {label}
                </Badge>
              ))}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-2 pt-2 border-t">
            {hasReplies && (
              <Button variant="ghost" size="sm" onClick={() => toggleExpand(post.id)}>
                {isExpanded ? (
                  <ChevronDown className="h-4 w-4 mr-1" />
                ) : (
                  <ChevronRight className="h-4 w-4 mr-1" />
                )}
                {post.replies!.length} {post.replies!.length === 1 ? 'reply' : 'replies'}
              </Button>
            )}

            <Button
              variant="ghost"
              size="sm"
              onClick={() => setReplyingTo(isReplying ? null : post.id)}
            >
              <MessageSquare className="h-4 w-4 mr-1" />
              Reply
            </Button>

            {isInstructor && (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handlePinPost(post.id, post.pinned)}
                >
                  <Pin className="h-4 w-4 mr-1" />
                  {post.pinned ? 'Unpin' : 'Pin'}
                </Button>

                <div className="relative group">
                  <Button variant="ghost" size="sm">
                    <Tag className="h-4 w-4 mr-1" />
                    Label
                  </Button>
                  <div className="absolute left-0 top-full mt-1 bg-white border rounded-lg shadow-lg p-2 hidden group-hover:block z-10 min-w-[150px]">
                    {LABEL_OPTIONS.map((label) => (
                      <button
                        key={label}
                        onClick={() => handleLabelPost(post.id, label)}
                        className={`w-full text-left px-3 py-1.5 rounded text-sm hover:bg-gray-100 ${
                          post.labels_json?.includes(label) ? 'bg-blue-50 text-blue-700' : ''
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Reply Form */}
          {isReplying && (
            <div className="mt-3 pt-3 border-t">
              <Textarea
                placeholder="Write your reply..."
                rows={2}
                value={replyContent}
                onChange={(e) => setReplyContent(e.target.value)}
              />
              <div className="flex gap-2 mt-2">
                <Button
                  size="sm"
                  onClick={() => handleReply(post.id)}
                  disabled={submitting || !replyContent.trim()}
                >
                  <Send className="h-4 w-4 mr-1" />
                  Send Reply
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setReplyingTo(null);
                    setReplyContent('');
                  }}
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Nested Replies */}
        {hasReplies && isExpanded && (
          <div className="mt-2">
            {post.replies!.map((reply) => renderPost(reply, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  const pinnedPosts = posts.filter((p) => p.pinned);
  const regularPosts = posts.filter((p) => !p.pinned);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('forum.title')}</h1>
          <p className="text-gray-600">{t('forum.subtitle')}</p>
        </div>
        <Button onClick={fetchForumData} variant="outline" size="sm" disabled={!selectedSessionId} data-voice-id="refresh">
          <RefreshCw className="h-4 w-4 mr-2" />
          {t('common.refresh')}
        </Button>
      </div>

      {/* Course & Session Selector */}
      <div className="grid md:grid-cols-2 gap-4 mb-6">
        <Select
          label={t('courses.selectCourse')}
          value={selectedCourseId?.toString() || ''}
          onChange={(e) => setSelectedCourseId(Number(e.target.value))}
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
          onChange={(e) => setSelectedSessionId(Number(e.target.value))}
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

      {!selectedSessionId ? (
        <Card>
          <CardContent className="py-8 text-center text-gray-500">
            <MessageSquare className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p>Select a live session to view the discussion forum.</p>
            {selectedCourseId && sessions.length === 0 && (
              <p className="text-sm mt-2">No live sessions available for this course.</p>
            )}
          </CardContent>
        </Card>
      ) : (
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="cases">{t('forum.cases')}</TabsTrigger>
            <TabsTrigger value="discussion">{t('forum.discussion')} ({posts.length})</TabsTrigger>
          </TabsList>

          <TabsContent value="cases">
            {cases.length === 0 ? (
              <Card>
                <CardContent className="py-8 text-center text-gray-500">
                  <FileText className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                  <p>No case studies posted for this session yet.</p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                {cases.map((caseItem) => (
                  <Card key={caseItem.id}>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <FileText className="h-5 w-5 text-primary-600" />
                        Case Study #{caseItem.id}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-gray-800 whitespace-pre-wrap">{caseItem.prompt}</p>
                      <p className="text-xs text-gray-500 mt-4">
                        Posted: {formatTimestamp(caseItem.created_at)}
                      </p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="discussion">
            {loading ? (
              <div className="text-center py-8 text-gray-500">Loading discussion...</div>
            ) : (
              <div className="space-y-6">
                {/* New Post Form */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Post to Discussion</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Textarea
                      placeholder="Share your thoughts or respond to the case study..."
                      rows={3}
                      value={newPostContent}
                      onChange={(e) => setNewPostContent(e.target.value)}
                      data-voice-id="textarea-post-content"
                    />
                    <div className="flex justify-end mt-3">
                      <Button
                        onClick={handleCreatePost}
                        disabled={submitting || !newPostContent.trim()}
                        data-voice-id="submit-post"
                      >
                        <Send className="h-4 w-4 mr-2" />
                        Post
                      </Button>
                    </div>
                  </CardContent>
                </Card>

                {/* Pinned Posts */}
                {pinnedPosts.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                      <Pin className="h-4 w-4" />
                      Pinned Posts
                    </h3>
                    {pinnedPosts.map((post) => renderPost(post))}
                  </div>
                )}

                {/* Regular Posts */}
                {regularPosts.length > 0 ? (
                  <div>
                    {pinnedPosts.length > 0 && (
                      <h3 className="text-sm font-medium text-gray-700 mb-3">All Posts</h3>
                    )}
                    {regularPosts.map((post) => renderPost(post))}
                  </div>
                ) : pinnedPosts.length === 0 ? (
                  <Card>
                    <CardContent className="py-8 text-center text-gray-500">
                      <MessageSquare className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                      <p>No posts yet. Be the first to contribute!</p>
                    </CardContent>
                  </Card>
                ) : null}
              </div>
            )}
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
