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
import { useSharedCourseSessionSelection } from '@/lib/shared-selection';
import { createVoiceTabHandler, setupVoiceTabListeners, mergeTabMappings } from '@/lib/voice-tab-handler';
import { Course, Session, Post, Case } from '@/types';
import { formatTimestamp } from '@/lib/utils';
import { useTranslations } from 'next-intl';
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  Select,
  Textarea,
  Badge,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
  EmptyState,
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
  const {
    selectedCourseId,
    setSelectedCourseId,
    selectedSessionId,
    setSelectedSessionId,
  } = useSharedCourseSessionSelection();
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

  // Forum page tab mappings
  const forumTabMap = mergeTabMappings({
    'discussion': 'discussion',
    'discussions': 'discussion',
    'posts': 'discussion',
    'forum': 'discussion',
  });

  // Voice tab handler
  const handleVoiceTabSwitch = useCallback(
    createVoiceTabHandler(forumTabMap, setActiveTab, 'Forum'),
    []
  );

  // Set up voice tab listeners
  useEffect(() => {
    return setupVoiceTabListeners(handleVoiceTabSwitch);
  }, [handleVoiceTabSwitch]);

  const fetchCourses = async () => {
    try {
      if (!user) return;

      if (user.is_admin) {
        const data = await api.getCourses(user.id);
        setCourses(data);
        if (data.length > 0 && (!selectedCourseId || !data.some((course) => course.id === selectedCourseId))) {
          setSelectedCourseId(data[0].id);
        } else if (data.length === 0) {
          setSelectedCourseId(null);
        }
      } else if (isInstructor) {
        const data = await api.getCourses(user.id);
        setCourses(data);
        if (data.length > 0 && (!selectedCourseId || !data.some((course) => course.id === selectedCourseId))) {
          setSelectedCourseId(data[0].id);
        } else if (data.length === 0) {
          setSelectedCourseId(null);
        }
      } else {
        const enrolledCourses = await api.getUserEnrolledCourses(user.id);
        const coursePromises = enrolledCourses.map((ec: any) => api.getCourse(ec.course_id));
        const fullCourses = await Promise.all(coursePromises);
        setCourses(fullCourses);
        if (fullCourses.length > 0 && (!selectedCourseId || !fullCourses.some((course) => course.id === selectedCourseId))) {
          setSelectedCourseId(fullCourses[0].id);
        } else if (fullCourses.length === 0) {
          setSelectedCourseId(null);
        }
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

  const fetchForumData = useCallback(async () => {
    if (!selectedSessionId) return;

    setLoading(true);
    try {
      const [casesData, postsData] = await Promise.all([
        api.getSessionCases(selectedSessionId),
        api.getSessionPosts(selectedSessionId),
      ]);
      setCases(casesData);
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

  const organizePostsIntoThreads = (flatPosts: Post[]): PostWithReplies[] => {
    const postMap = new Map<number, PostWithReplies>();
    const rootPosts: PostWithReplies[] = [];

    flatPosts.forEach((post) => {
      postMap.set(post.id, { ...post, replies: [] });
    });

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
        className={`${depth > 0 ? 'ml-8 border-l border-neutral-200 dark:border-neutral-700 pl-4' : ''}`}
      >
        <div
          className={`p-4 rounded-lg border ${
            post.pinned
              ? 'bg-[#f5c842]/5 border-[#f5c842]/20'
              : 'bg-white dark:bg-neutral-800 border-neutral-200 dark:border-neutral-700 shadow-sm'
          } ${depth === 0 ? 'mb-3' : 'mt-2'}`}
        >
          {/* Post Header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-neutral-100 dark:bg-neutral-700 flex items-center justify-center">
                <User className="h-4 w-4 text-neutral-700 dark:text-neutral-200" />
              </div>
              <span className="text-sm font-medium text-neutral-900 dark:text-white">
                User #{post.user_id}
              </span>
              <span className="flex items-center gap-1 text-xs text-neutral-500 dark:text-neutral-400">
                <Clock className="h-3 w-3" />
                {formatTimestamp(post.created_at)}
              </span>
              {post.pinned && (
                <Badge variant="accent" size="sm">
                  <Pin className="h-3 w-3 mr-1" />
                  Pinned
                </Badge>
              )}
            </div>
            <span className="text-xs text-neutral-400 dark:text-neutral-500">#{post.id}</span>
          </div>

          {/* Post Content */}
          <p className="text-neutral-800 dark:text-neutral-200 whitespace-pre-wrap mb-3 leading-relaxed">{post.content}</p>

          {/* Labels */}
          {post.labels_json && post.labels_json.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-3">
              {post.labels_json.map((label) => (
                <Badge key={label} variant="info" size="sm">
                  {label}
                </Badge>
              ))}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-2 pt-3 border-t border-neutral-100 dark:border-neutral-800">
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
              data-voice-id={`reply-post-${post.id}`}
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
                  data-voice-id={`pin-post-${post.id}`}
                >
                  <Pin className="h-4 w-4 mr-1" />
                  {post.pinned ? 'Unpin' : 'Pin'}
                </Button>

                <div className="relative group">
                  <Button variant="ghost" size="sm">
                    <Tag className="h-4 w-4 mr-1" />
                    Label
                  </Button>
                  <div className="absolute left-0 top-full mt-1 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg shadow-md p-1.5 hidden group-hover:block z-10 min-w-[150px]">
                    {LABEL_OPTIONS.map((label) => (
                      <button
                        key={label}
                        onClick={() => handleLabelPost(post.id, label)}
                        className={`w-full text-left px-3 py-2 rounded-lg text-sm hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors ${
                          post.labels_json?.includes(label) ? 'bg-neutral-100 dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100' : ''
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
            <div className="mt-4 pt-4 border-t border-neutral-100 dark:border-neutral-800">
              <Textarea
                placeholder="Write your reply..."
                rows={2}
                value={replyContent}
                onChange={(e) => setReplyContent(e.target.value)}
              />
              <div className="flex gap-2 mt-3">
                <Button
                  size="sm"
                  onClick={() => handleReply(post.id)}
                  disabled={submitting || !replyContent.trim()}
                  data-voice-id="send-reply"
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
                  data-voice-id="cancel-reply"
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
    <div className="space-y-4 sm:space-y-6 max-w-6xl">
      {/* Header + selectors merged into one row */}
      <div className="pb-4 border-b border-neutral-200 dark:border-neutral-700">
        <div className="flex flex-col sm:flex-row sm:items-end gap-3">
          <div className="flex-1">
            <h1 className="text-xl font-semibold text-neutral-900 dark:text-white">{t('forum.title')}</h1>
            <p className="text-neutral-500 dark:text-neutral-400 mt-0.5 text-sm">{t('forum.subtitle')}</p>
          </div>
          <div className="flex flex-col sm:flex-row items-stretch sm:items-end gap-3">
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

            <Button onClick={fetchForumData} variant="outline" size="sm" disabled={!selectedSessionId} data-voice-id="refresh">
              <RefreshCw className="h-4 w-4 mr-2" />
              {t('common.refresh')}
            </Button>
          </div>
        </div>
      </div>

      {!selectedSessionId ? (
        <EmptyState
          icon={MessageSquare}
          message="Select a live session to open the discussion space."
          submessage={selectedCourseId && sessions.length === 0 ? 'No live sessions available for this course.' : undefined}
        />
      ) : (
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="cases" data-voice-id="tab-cases">{t('forum.cases')}</TabsTrigger>
            <TabsTrigger value="discussion" data-voice-id="tab-discussion">
              {t('forum.discussion')}
              <Badge variant="primary" size="sm" className="ml-2">{posts.length}</Badge>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="cases">
            {cases.length === 0 ? (
              <EmptyState
                icon={FileText}
                message="No case prompts have been posted for this session."
              />
            ) : (
              <div className="space-y-4">
                {cases.map((caseItem) => (
                  <Card key={caseItem.id} variant="default">
                    <CardHeader>
                      <CardTitle>Case Prompt #{caseItem.id}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-neutral-800 dark:text-neutral-200 whitespace-pre-wrap leading-relaxed">{caseItem.prompt}</p>
                      <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-4">
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
              <div className="flex items-center justify-center py-12">
                <div className="flex flex-col items-center gap-3">
                  <div className="relative">
                    <div className="w-10 h-10 rounded-full border-4 border-neutral-100 dark:border-neutral-800"></div>
                    <div className="absolute top-0 left-0 w-10 h-10 rounded-full border-4 border-neutral-900 dark:border-white border-t-transparent animate-spin"></div>
                  </div>
                  <p className="text-sm text-neutral-500 dark:text-neutral-400">Loading discussion...</p>
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                {/* New Post Form - chat-style inline */}
                <div className="flex items-end gap-2">
                  <div className="flex-1">
                    <Textarea
                      placeholder="Share your response, question, or reflection..."
                      rows={2}
                      value={newPostContent}
                      onChange={(e) => setNewPostContent(e.target.value)}
                      data-voice-id="textarea-post-content"
                    />
                  </div>
                  <Button
                    onClick={handleCreatePost}
                    disabled={submitting || !newPostContent.trim()}
                    data-voice-id="submit-post"
                    className="flex-shrink-0"
                  >
                    <Send className="h-4 w-4" />
                  </Button>
                </div>

                {/* Pinned Posts */}
                {pinnedPosts.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-3 flex items-center gap-2">
                      <Pin className="h-4 w-4 text-[#f5c842]" />
                      Pinned Posts
                    </h3>
                    {pinnedPosts.map((post) => renderPost(post))}
                  </div>
                )}

                {/* Regular Posts */}
                {regularPosts.length > 0 ? (
                  <div>
                    {pinnedPosts.length > 0 && (
                      <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-3">All Posts</h3>
                    )}
                    {regularPosts.map((post) => renderPost(post))}
                  </div>
                ) : pinnedPosts.length === 0 ? (
                  <EmptyState
                    icon={MessageSquare}
                    message="No posts yet. Start the conversation."
                  />
                ) : null}
              </div>
            )}
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
