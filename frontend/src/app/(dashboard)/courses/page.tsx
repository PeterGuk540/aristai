'use client';

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import { BookOpen, Plus, Users, RefreshCw, Copy, Key, Check, CheckCircle, Search, UserPlus, GraduationCap, Clock, Upload, FileText, X, Edit2, Trash2 } from 'lucide-react';
import { api } from '@/lib/api';
import { useUser } from '@/lib/context';
import { useSharedCourseSessionSelection } from '@/lib/shared-selection';
import { createVoiceTabHandler, setupVoiceTabListeners, mergeTabMappings } from '@/lib/voice-tab-handler';
import { Course, EnrolledStudent, User } from '@/types';
import { formatTimestamp, truncate } from '@/lib/utils';
import { useTranslations } from 'next-intl';
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  Input,
  Textarea,
  Select,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
  Badge,
} from '@/components/ui';

// Enhanced AI Features
import { ParticipationInsightsComponent } from '@/components/enhanced/ParticipationInsights';
import { ObjectiveCoverageComponent } from '@/components/enhanced/ObjectiveCoverage';

export default function CoursesPage() {
  const { isInstructor, currentUser, refreshUser } = useUser();
  const searchParams = useSearchParams();
  const t = useTranslations();
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const normalizeTab = (tab: string | null | undefined) => {
    if (tab === 'enrollment' || tab === 'instructor') return 'advanced';
    return tab || 'courses';
  };

  // Tab state - default from URL query param
  const [activeTab, setActiveTab] = useState(normalizeTab(searchParams?.get('tab')));

  // Create course form
  const [title, setTitle] = useState('');
  const [syllabus, setSyllabus] = useState('');
  const [objectives, setObjectives] = useState('');

  // Syllabus upload state
  const [syllabusInputMode, setSyllabusInputMode] = useState<'paste' | 'upload'>('paste');
  const [syllabusFile, setSyllabusFile] = useState<File | null>(null);
  const [uploadingSyllabus, setUploadingSyllabus] = useState(false);
  const [syllabusUploadError, setSyllabusUploadError] = useState<string | null>(null);
  const syllabusFileInputRef = useRef<HTMLInputElement>(null);

  // Auto-extract objectives state
  const [extractingObjectives, setExtractingObjectives] = useState(false);
  const [objectivesExtracted, setObjectivesExtracted] = useState(false);

  // Courses page tab mappings
  const coursesTabMap = mergeTabMappings({
    // Courses tab
    'courses': 'courses',
    'course': 'courses',
    'mycourses': 'courses',
    'viewcourses': 'courses',
    'listcourses': 'courses',
    // Create tab
    'create': 'create',
    'createcourse': 'create',
    'newcourse': 'create',
    'addcourse': 'create',
    // Join tab
    'join': 'join',
    'joincourse': 'join',
    'joinwithcode': 'join',
    'entercode': 'join',
    // Advanced/Enrollment tab
    'advanced': 'advanced',
    'enrollment': 'advanced',
    'enroll': 'advanced',
    'enrollstudents': 'advanced',
    'instructor': 'advanced',
    'instructoraccess': 'advanced',
    'manageenrollment': 'advanced',
    'managestudents': 'advanced',
    // AI Insights tab
    'aiinsights': 'ai-insights',
    'aiinsight': 'ai-insights',
    'objectivecoverage': 'ai-insights',
    'courseinsights': 'ai-insights',
  });

  // Voice tab handler
  const handleVoiceSelectTab = useCallback(
    createVoiceTabHandler(coursesTabMap, setActiveTab, 'Courses'),
    []
  );

  // Set up voice tab listeners
  useEffect(() => {
    return setupVoiceTabListeners(handleVoiceSelectTab);
  }, [handleVoiceSelectTab]);

  // Update tab when URL changes
  useEffect(() => {
    const tabFromUrl = searchParams?.get('tab');
    if (tabFromUrl) {
      setActiveTab(normalizeTab(tabFromUrl));
    }
  }, [searchParams]);

  // Enrollment
  const { selectedCourseId, setSelectedCourseId } = useSharedCourseSessionSelection();
  const [enrolledStudents, setEnrolledStudents] = useState<EnrolledStudent[]>([]);
  const [allStudents, setAllStudents] = useState<User[]>([]);
  const [enrolling, setEnrolling] = useState(false);

  // Bulk enrollment
  const [selectedStudentIds, setSelectedStudentIds] = useState<Set<number>>(new Set());
  const [studentSearchQuery, setStudentSearchQuery] = useState('');

  // Join code management
  const [copiedCourseId, setCopiedCourseId] = useState<number | null>(null);
  const [regeneratingCode, setRegeneratingCode] = useState<number | null>(null);

  // Student join course
  const [joinCode, setJoinCode] = useState('');
  const [joining, setJoining] = useState(false);

  // Instructor request
  const [requestingInstructor, setRequestingInstructor] = useState(false);

  // Edit/Delete course state
  const [editingCourse, setEditingCourse] = useState<Course | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editSyllabus, setEditSyllabus] = useState('');
  const [editObjectives, setEditObjectives] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);

  // Check if user can edit/delete a course
  const canEditCourse = (course: Course) => {
    if (!currentUser) return false;
    if (currentUser.is_admin) return true;
    if (isInstructor && course.created_by === currentUser.id) return true;
    return false;
  };

  const fetchCourses = async () => {
    try {
      setLoading(true);

      if (currentUser?.is_admin) {
        const data = await api.getCourses(currentUser.id);
        setCourses(data);
        if (data.length > 0 && (!selectedCourseId || !data.some((course) => course.id === selectedCourseId))) {
          setSelectedCourseId(data[0].id);
        } else if (data.length === 0) {
          setSelectedCourseId(null);
        }
      } else if (isInstructor && currentUser) {
        const data = await api.getCourses(currentUser.id);
        setCourses(data);
        if (data.length > 0 && (!selectedCourseId || !data.some((course) => course.id === selectedCourseId))) {
          setSelectedCourseId(data[0].id);
        } else if (data.length === 0) {
          setSelectedCourseId(null);
        }
      } else if (currentUser) {
        const enrolledCourses = await api.getUserEnrolledCourses(currentUser.id);
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
    } finally {
      setLoading(false);
    }
  };

  const fetchEnrollment = async (courseId: number) => {
    try {
      const [enrolled, users] = await Promise.all([
        api.getEnrolledStudents(courseId),
        api.getUsers(),
      ]);
      setEnrolledStudents(enrolled);
      setAllStudents(users.filter((u: User) => u.role === 'student'));
    } catch (error) {
      console.error('Failed to fetch enrollment:', error);
    }
  };

  useEffect(() => {
    if (currentUser) {
      fetchCourses();
    }
  }, [currentUser, isInstructor]);

  useEffect(() => {
    if (selectedCourseId) {
      fetchEnrollment(selectedCourseId);
    }
  }, [selectedCourseId]);

  const extractObjectivesFromSyllabus = useCallback(async (syllabusText: string) => {
    if (!syllabusText || syllabusText.length < 50) return;

    setExtractingObjectives(true);
    try {
      const result = await api.extractLearningObjectives(syllabusText);
      if (result.success && result.objectives.length > 0) {
        setObjectives(result.objectives.join('\n'));
        setObjectivesExtracted(true);
      }
    } catch (error) {
      console.error('Failed to extract objectives:', error);
    } finally {
      setExtractingObjectives(false);
    }
  }, []);

  const handleSyllabusFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    setSyllabusFile(file);
    setSyllabusUploadError(null);
    setUploadingSyllabus(true);
    setObjectivesExtracted(false);

    try {
      const result = await api.uploadSyllabus(file);
      setSyllabus(result.extracted_text);
      setSyllabusUploadError(null);

      if (result.extracted_text && result.extracted_text.length >= 50) {
        extractObjectivesFromSyllabus(result.extracted_text);
      }
    } catch (error: any) {
      console.error('Failed to extract syllabus:', error);
      setSyllabusUploadError(error.message || 'Failed to extract text from file');
      setSyllabusFile(null);
    } finally {
      setUploadingSyllabus(false);
    }
  };

  const handleRemoveSyllabusFile = () => {
    setSyllabusFile(null);
    setSyllabus('');
    setObjectives('');
    setSyllabusUploadError(null);
    setObjectivesExtracted(false);
    if (syllabusFileInputRef.current) {
      syllabusFileInputRef.current.value = '';
    }
  };

  const handleSyllabusTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setSyllabus(e.target.value);
    setObjectivesExtracted(false);
  };

  const handleSyllabusBlur = () => {
    if (syllabus && syllabus.length >= 100 && !objectivesExtracted && !objectives.trim()) {
      extractObjectivesFromSyllabus(syllabus);
    }
  };

  const handleCreateCourse = async (generatePlans: boolean) => {
    if (!title.trim()) return;

    setCreating(true);
    try {
      const objectivesList = objectives
        .split('\n')
        .map((o) => o.trim())
        .filter((o) => o);

      const course = await api.createCourse({
        title,
        syllabus_text: syllabus,
        objectives_json: objectivesList,
        created_by: currentUser?.id,
      });

      if (syllabusFile && course.id) {
        try {
          await api.uploadSyllabus(syllabusFile, {
            courseId: course.id,
            userId: currentUser?.id,
          });
        } catch (err) {
          console.error('Failed to save syllabus to materials:', err);
        }
      }

      if (generatePlans) {
        await api.generatePlans(course.id);
        alert(`Course created! Plan generation started.`);
      } else {
        alert(`Course created with ID: ${course.id}`);
      }

      setTitle('');
      setSyllabus('');
      setObjectives('');
      setSyllabusFile(null);
      setSyllabusInputMode('paste');
      setObjectivesExtracted(false);
      if (syllabusFileInputRef.current) {
        syllabusFileInputRef.current.value = '';
      }
      fetchCourses();
    } catch (error) {
      console.error('Failed to create course:', error);
      alert('Failed to create course');
    } finally {
      setCreating(false);
    }
  };

  const handleEnrollStudent = async (userId: number) => {
    if (!selectedCourseId) return;

    setEnrolling(true);
    try {
      await api.enrollUser(userId, selectedCourseId);
      fetchEnrollment(selectedCourseId);
    } catch (error) {
      console.error('Failed to enroll student:', error);
      alert('Failed to enroll student');
    } finally {
      setEnrolling(false);
    }
  };

  const handleEnrollAll = async () => {
    if (!selectedCourseId) return;

    setEnrolling(true);
    try {
      const result = await api.enrollAllStudents(selectedCourseId);
      alert(result.message || 'Students enrolled!');
      fetchEnrollment(selectedCourseId);
    } catch (error) {
      console.error('Failed to enroll all students:', error);
      alert('Failed to enroll students');
    } finally {
      setEnrolling(false);
    }
  };

  const handleBulkEnroll = async () => {
    if (!selectedCourseId || selectedStudentIds.size === 0) return;

    setEnrolling(true);
    try {
      const result = await api.bulkEnrollStudents(Array.from(selectedStudentIds), selectedCourseId);
      alert(result.message || 'Students enrolled!');
      setSelectedStudentIds(new Set());
      fetchEnrollment(selectedCourseId);
    } catch (error) {
      console.error('Failed to bulk enroll students:', error);
      alert('Failed to enroll students');
    } finally {
      setEnrolling(false);
    }
  };

  const handleCopyJoinCode = async (courseId: number, joinCode: string) => {
    try {
      await navigator.clipboard.writeText(joinCode);
      setCopiedCourseId(courseId);
      setTimeout(() => setCopiedCourseId(null), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };

  const handleRegenerateJoinCode = async (courseId: number) => {
    setRegeneratingCode(courseId);
    try {
      const updatedCourse = await api.regenerateJoinCode(courseId);
      setCourses(courses.map(c => c.id === courseId ? updatedCourse : c));
    } catch (error) {
      console.error('Failed to regenerate join code:', error);
      alert('Failed to regenerate join code');
    } finally {
      setRegeneratingCode(null);
    }
  };

  const handleJoinCourse = async () => {
    if (!joinCode.trim() || !currentUser) return;

    setJoining(true);
    try {
      const result = await api.joinCourseByCode(joinCode.trim(), currentUser.id);
      alert(`Successfully enrolled in "${result.course_title}"!`);
      setJoinCode('');
      fetchCourses();
    } catch (error: any) {
      console.error('Failed to join course:', error);
      alert(error.message || 'Failed to join course. Please check the code and try again.');
    } finally {
      setJoining(false);
    }
  };

  const handleRequestInstructor = async () => {
    if (!currentUser) return;

    setRequestingInstructor(true);
    try {
      await api.requestInstructorStatus(currentUser.id);
      await refreshUser();
      alert('Instructor access request submitted! An instructor will review your request.');
    } catch (error: any) {
      console.error('Failed to request instructor status:', error);
      alert(error.message || 'Failed to submit request. Please try again.');
    } finally {
      setRequestingInstructor(false);
    }
  };

  const handleStartEdit = (course: Course) => {
    setEditingCourse(course);
    setEditTitle(course.title);
    setEditSyllabus(course.syllabus_text || '');
    setEditObjectives(course.objectives_json?.join('\n') || '');
  };

  const handleCancelEdit = () => {
    setEditingCourse(null);
    setEditTitle('');
    setEditSyllabus('');
    setEditObjectives('');
  };

  const handleSaveEdit = async () => {
    if (!editingCourse || !currentUser) return;

    setSaving(true);
    try {
      const objectivesList = editObjectives
        .split('\n')
        .map((o) => o.trim())
        .filter((o) => o);

      await api.updateCourse(editingCourse.id, currentUser.id, {
        title: editTitle,
        syllabus_text: editSyllabus,
        objectives_json: objectivesList,
      });

      alert('Course updated successfully!');
      handleCancelEdit();
      fetchCourses();
    } catch (error: any) {
      console.error('Failed to update course:', error);
      alert(error.message || 'Failed to update course. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteCourse = async (courseId: number) => {
    if (!currentUser) return;

    const confirmed = window.confirm(
      'Are you sure you want to delete this course? This will also delete all sessions, enrollments, and materials associated with this course. This action cannot be undone.'
    );

    if (!confirmed) return;

    setDeleting(courseId);
    try {
      await api.deleteCourse(courseId, currentUser.id);
      alert('Course deleted successfully!');
      fetchCourses();
    } catch (error: any) {
      console.error('Failed to delete course:', error);
      alert(error.message || 'Failed to delete course. Please try again.');
    } finally {
      setDeleting(null);
    }
  };

  const toggleStudentSelection = (studentId: number) => {
    const newSelection = new Set(selectedStudentIds);
    if (newSelection.has(studentId)) {
      newSelection.delete(studentId);
    } else {
      newSelection.add(studentId);
    }
    setSelectedStudentIds(newSelection);
  };

  const toggleSelectAll = () => {
    if (selectedStudentIds.size === filteredAvailableStudents.length) {
      setSelectedStudentIds(new Set());
    } else {
      setSelectedStudentIds(new Set(filteredAvailableStudents.map(s => s.id)));
    }
  };

  const enrolledIds = new Set(enrolledStudents.map((s) => s.user_id));
  const availableStudents = allStudents.filter((s) => !enrolledIds.has(s.id));

  const filteredAvailableStudents = useMemo(() => {
    if (!studentSearchQuery.trim()) return availableStudents;
    const query = studentSearchQuery.toLowerCase();
    return availableStudents.filter(
      s => s.name.toLowerCase().includes(query) || s.email.toLowerCase().includes(query)
    );
  }, [availableStudents, studentSearchQuery]);

  const lastUpdatedLabel = useMemo(() => {
    if (!courses.length) return 'No courses yet';
    const newest = [...courses].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    )[0];
    return `Last updated ${formatTimestamp(newest.created_at)}`;
  }, [courses]);

  const pendingActionCount = useMemo(() => {
    if (loading) return 0;
    let count = 0;
    if (isInstructor && courses.length === 0) count += 1;
    if (isInstructor && selectedCourseId && enrolledStudents.length === 0) count += 1;
    if (!isInstructor && courses.length === 0) count += 1;
    if (!isInstructor && currentUser?.instructor_request_status === 'rejected') count += 1;
    return count;
  }, [loading, isInstructor, courses.length, selectedCourseId, enrolledStudents.length, currentUser?.instructor_request_status]);

  return (
    <div className="space-y-8 max-w-6xl pb-4">
      {/* Page Header */}
      <div className="flex items-center justify-between rounded-2xl border border-amber-200/80 dark:border-primary-900/20 bg-white dark:bg-[#1a150c] px-6 py-5 shadow-sm">
        <div>
          <h1 className="text-3xl font-bold text-neutral-900 dark:text-white tracking-tight">{t('courses.title')}</h1>
          <p className="text-neutral-600 dark:text-neutral-400 mt-1">{t('courses.subtitle')}</p>
        </div>
        <Button onClick={fetchCourses} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          {t('common.refresh')}
        </Button>
      </div>

      {/* Workspace Overview */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card variant="default" padding="sm">
          <CardContent className="py-4">
            <p className="text-xs uppercase tracking-wide text-neutral-500 dark:text-neutral-400">Workspace</p>
            <p className="mt-1 text-2xl font-semibold text-neutral-900 dark:text-white">{courses.length}</p>
            <p className="text-sm text-neutral-600 dark:text-neutral-400">
              {isInstructor ? 'Courses you manage' : 'Courses you joined'}
            </p>
          </CardContent>
        </Card>
        <Card variant="default" padding="sm">
          <CardContent className="py-4">
            <p className="text-xs uppercase tracking-wide text-neutral-500 dark:text-neutral-400">Pending Actions</p>
            <p className="mt-1 text-2xl font-semibold text-neutral-900 dark:text-white">{pendingActionCount}</p>
            <p className="text-sm text-neutral-600 dark:text-neutral-400">
              {pendingActionCount > 0 ? 'Tasks need attention' : 'No urgent tasks'}
            </p>
          </CardContent>
        </Card>
        <Card variant="default" padding="sm">
          <CardContent className="py-4">
            <p className="text-xs uppercase tracking-wide text-neutral-500 dark:text-neutral-400">Recent Activity</p>
            <p className="mt-1 text-sm font-medium text-neutral-900 dark:text-white">{lastUpdatedLabel}</p>
            <p className="text-sm text-neutral-600 dark:text-neutral-400">Operational snapshot for this workspace</p>
          </CardContent>
        </Card>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="border border-neutral-200 dark:border-primary-900/20 bg-white dark:bg-[#1a150c] rounded-xl">
          <TabsTrigger value="courses" data-voice-id="tab-courses">Overview</TabsTrigger>
          {isInstructor && <TabsTrigger value="create" data-voice-id="tab-create">{t('courses.createCourse')}</TabsTrigger>}
          {!isInstructor && <TabsTrigger value="join" data-voice-id="tab-join">{t('courses.joinCourse')}</TabsTrigger>}
          <TabsTrigger value="advanced" data-voice-id="tab-advanced">Advanced</TabsTrigger>
          {isInstructor && <TabsTrigger value="ai-insights" data-voice-id="tab-ai-insights">AI Insights</TabsTrigger>}
        </TabsList>

        <TabsContent value="courses">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="flex flex-col items-center gap-3">
                <div className="relative">
                  <div className="w-10 h-10 rounded-full border-4 border-primary-100 dark:border-primary-900"></div>
                  <div className="absolute top-0 left-0 w-10 h-10 rounded-full border-4 border-primary-600 border-t-transparent animate-spin"></div>
                </div>
                <p className="text-sm text-neutral-500 dark:text-neutral-400">{t('common.loading')}</p>
              </div>
            </div>
          ) : courses.length === 0 ? (
            <Card variant="default" padding="lg">
              <div className="text-center py-8">
                <div className="p-4 rounded-2xl bg-primary-50 dark:bg-primary-900/30 w-fit mx-auto mb-4">
                  <BookOpen className="h-10 w-10 text-primary-600 dark:text-primary-400" />
                </div>
                {isInstructor ? (
                  <p className="text-neutral-600 dark:text-neutral-400">{t('courses.noCourses')}</p>
                ) : (
                  <div>
                    <p className="text-neutral-700 dark:text-neutral-300 font-medium mb-1">{t('courses.noEnrolledCourses')}</p>
                    <p className="text-sm text-neutral-500 dark:text-neutral-400">{t('courses.useJoinCode')}</p>
                  </div>
                )}
              </div>
            </Card>
          ) : (
            <div className="grid gap-5">
              {courses.map((course) => (
                <Card key={course.id} variant="default" hover className="overflow-hidden">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-xl bg-primary-100 dark:bg-primary-900/50">
                          <BookOpen className="h-5 w-5 text-primary-600 dark:text-primary-400" />
                        </div>
                        <div>
                          <CardTitle>{course.title}</CardTitle>
                          <CardDescription>Course ID: {course.id}</CardDescription>
                        </div>
                      </div>
                      {canEditCourse(course) && (
                        <div className="flex items-center gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleStartEdit(course)}
                            title={t('common.edit')}
                            data-voice-id={`edit-course-${course.id}`}
                            data-voice-label={`Edit ${course.title}`}
                          >
                            <Edit2 className="h-4 w-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleDeleteCourse(course.id)}
                            disabled={deleting === course.id}
                            title={t('common.delete')}
                            data-voice-id={`delete-course-${course.id}`}
                            data-voice-label={`Delete ${course.title}`}
                            className="text-danger-600 hover:text-danger-700 hover:bg-danger-50 dark:text-danger-400 dark:hover:bg-danger-900/20"
                          >
                            {deleting === course.id ? (
                              <RefreshCw className="h-4 w-4 animate-spin" />
                            ) : (
                              <Trash2 className="h-4 w-4" />
                            )}
                          </Button>
                        </div>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid md:grid-cols-2 gap-6">
                      <div>
                        <h4 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-2">{t('courses.syllabus')}</h4>
                        <p className="text-sm text-neutral-600 dark:text-neutral-400 whitespace-pre-wrap leading-relaxed">
                          {truncate(course.syllabus_text || t('courses.syllabus'), 300)}
                        </p>
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-2">{t('courses.learningObjectives')}</h4>
                        {course.objectives_json && course.objectives_json.length > 0 ? (
                          <ul className="text-sm text-neutral-600 dark:text-neutral-400 space-y-1.5">
                            {course.objectives_json.slice(0, 5).map((obj, i) => (
                              <li key={i} className="flex items-start gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-primary-500 mt-2 flex-shrink-0"></span>
                                <span>{obj}</span>
                              </li>
                            ))}
                            {course.objectives_json.length > 5 && (
                              <li className="text-neutral-400 dark:text-neutral-500 text-xs">
                                ...and {course.objectives_json.length - 5} more
                              </li>
                            )}
                          </ul>
                        ) : (
                          <p className="text-sm text-neutral-400 dark:text-neutral-500 italic">No objectives defined</p>
                        )}
                      </div>
                    </div>
                    {isInstructor && course.join_code && (
                      <div className="mt-5 pt-5 border-t border-neutral-200 dark:border-neutral-700">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="p-1.5 rounded-lg bg-primary-100 dark:bg-primary-900/50">
                              <Key className="h-4 w-4 text-primary-600 dark:text-primary-400" />
                            </div>
                            <span className="text-sm text-neutral-600 dark:text-neutral-400">{t('courses.joinCode')}:</span>
                            <code className="bg-neutral-100 dark:bg-neutral-700 px-3 py-1 rounded-lg text-sm font-mono font-bold text-primary-600 dark:text-primary-400">
                              {course.join_code}
                            </code>
                          </div>
                          <div className="flex items-center gap-1">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleCopyJoinCode(course.id, course.join_code!)}
                              title="Copy join code"
                            >
                              {copiedCourseId === course.id ? (
                                <Check className="h-4 w-4 text-success-600" />
                              ) : (
                                <Copy className="h-4 w-4" />
                              )}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleRegenerateJoinCode(course.id)}
                              disabled={regeneratingCode === course.id}
                              title="Regenerate join code"
                            >
                              <RefreshCw className={`h-4 w-4 ${regeneratingCode === course.id ? 'animate-spin' : ''}`} />
                            </Button>
                          </div>
                        </div>
                      </div>
                    )}
                  </CardContent>
                  <CardFooter className="flex items-center justify-between">
                    <span className="text-xs text-neutral-500 dark:text-neutral-400">
                      Created: {formatTimestamp(course.created_at)}
                    </span>
                    {isInstructor && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={async () => {
                          try {
                            await api.generatePlans(course.id);
                            alert('Plan generation started!');
                          } catch (error) {
                            alert('Failed to start plan generation');
                          }
                        }}
                        data-voice-id="generate-plans"
                        data-voice-label={`Generate plans for ${course.title}`}
                      >
                        <FileText className="h-4 w-4 mr-2" />
                        {t('courses.generatePlans')}
                      </Button>
                    )}
                  </CardFooter>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {isInstructor && (
          <TabsContent value="create">
            <Card variant="default">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-primary-100 dark:bg-primary-900/50">
                    <Plus className="h-4 w-4 text-primary-600 dark:text-primary-400" />
                  </div>
                  {t('courses.createNew')}
                </CardTitle>
                <CardDescription>Create course details and prepare your session structure.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <Input
                  label={t('courses.courseTitle')}
                  placeholder={t('courses.courseTitlePlaceholder')}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  data-voice-id="course-title"
                />

                {/* Syllabus Input - Toggle between Upload and Paste */}
                <div className="space-y-3">
                  <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300">{t('courses.syllabus')}</label>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setSyllabusInputMode('paste')}
                      className={`flex items-center gap-2 px-4 py-2 text-sm rounded-lg transition-all ${
                        syllabusInputMode === 'paste'
                          ? 'bg-primary-100 dark:bg-primary-900/50 text-primary-700 dark:text-primary-300 font-medium'
                          : 'bg-neutral-100 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-200 dark:hover:bg-neutral-600'
                      }`}
                    >
                      <FileText className="h-4 w-4" />
                      {t('courses.pasteText')}
                    </button>
                    <button
                      type="button"
                      onClick={() => setSyllabusInputMode('upload')}
                      className={`flex items-center gap-2 px-4 py-2 text-sm rounded-lg transition-all ${
                        syllabusInputMode === 'upload'
                          ? 'bg-primary-100 dark:bg-primary-900/50 text-primary-700 dark:text-primary-300 font-medium'
                          : 'bg-neutral-100 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-200 dark:hover:bg-neutral-600'
                      }`}
                    >
                      <Upload className="h-4 w-4" />
                      {t('courses.uploadFile')}
                    </button>
                  </div>

                  {syllabusInputMode === 'paste' ? (
                    <Textarea
                      placeholder={t('courses.syllabusPlaceholder')}
                      rows={8}
                      value={syllabus}
                      onChange={handleSyllabusTextChange}
                      onBlur={handleSyllabusBlur}
                      data-voice-id="syllabus"
                    />
                  ) : (
                    <div className="space-y-3">
                      <input
                        ref={syllabusFileInputRef}
                        type="file"
                        accept=".pdf,.doc,.docx,.txt"
                        onChange={handleSyllabusFileSelect}
                        className="hidden"
                        disabled={uploadingSyllabus}
                      />

                      {!syllabusFile ? (
                        <div
                          onClick={() => syllabusFileInputRef.current?.click()}
                          className="border border-neutral-300 dark:border-neutral-600 rounded-xl p-8 text-center cursor-pointer hover:border-neutral-400 dark:hover:border-neutral-500 hover:bg-neutral-50 dark:hover:bg-neutral-800/60 transition-colors"
                        >
                          <div className="p-3 rounded-xl bg-neutral-100 dark:bg-neutral-700 w-fit mx-auto mb-3">
                            <Upload className="h-8 w-8 text-neutral-400 dark:text-neutral-500" />
                          </div>
                          <p className="text-sm text-neutral-600 dark:text-neutral-400 font-medium mb-1">
                            {t('courses.uploadSyllabus')}
                          </p>
                          <p className="text-xs text-neutral-400 dark:text-neutral-500">
                            {t('courses.supportedFormats')}
                          </p>
                        </div>
                      ) : (
                        <Card variant="outlined" padding="md">
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-3">
                              <div className="p-2 rounded-lg bg-primary-100 dark:bg-primary-900/50">
                                <FileText className="h-5 w-5 text-primary-600 dark:text-primary-400" />
                              </div>
                              <div>
                                <span className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
                                  {syllabusFile.name}
                                </span>
                                <span className="text-xs text-neutral-400 dark:text-neutral-500 ml-2">
                                  ({(syllabusFile.size / 1024).toFixed(1)} KB)
                                </span>
                              </div>
                            </div>
                            <button
                              type="button"
                              onClick={handleRemoveSyllabusFile}
                              className="p-1.5 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors"
                              title="Remove file"
                            >
                              <X className="h-4 w-4 text-neutral-500" />
                            </button>
                          </div>

                          {uploadingSyllabus && (
                            <div className="flex items-center gap-2 text-sm text-primary-600 dark:text-primary-400">
                              <RefreshCw className="h-4 w-4 animate-spin" />
                              Extracting text from file...
                            </div>
                          )}

                          {syllabusUploadError && (
                            <div className="text-sm text-danger-600 dark:text-danger-400 bg-danger-50 dark:bg-danger-900/20 p-3 rounded-lg">
                              {syllabusUploadError}
                            </div>
                          )}

                          {syllabus && !uploadingSyllabus && (
                            <div className="mt-3">
                              <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-2 font-medium">{t('courses.extractedTextPreview')}</p>
                              <div className="bg-neutral-50 dark:bg-neutral-800 rounded-lg p-3 max-h-32 overflow-y-auto">
                                <p className="text-xs text-neutral-600 dark:text-neutral-400 whitespace-pre-wrap">
                                  {syllabus.length > 500 ? syllabus.substring(0, 500) + '...' : syllabus}
                                </p>
                              </div>
                              <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-2">
                                {t('courses.charactersExtracted', { count: syllabus.length.toLocaleString() })}
                              </p>
                            </div>
                          )}
                        </Card>
                      )}
                    </div>
                  )}
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300">
                      {t('courses.learningObjectives')} {t('courses.onePerLine')}
                    </label>
                    {extractingObjectives && (
                      <Badge variant="primary" size="sm">
                        <RefreshCw className="h-3 w-3 animate-spin mr-1" />
                        Extracting...
                      </Badge>
                    )}
                    {objectivesExtracted && !extractingObjectives && (
                      <Badge variant="success" size="sm">
                        <CheckCircle className="h-3 w-3 mr-1" />
                        Auto-extracted
                      </Badge>
                    )}
                  </div>
                  <Textarea
                    placeholder={t('courses.learningObjectivesPlaceholder')}
                    rows={5}
                    value={objectives}
                    onChange={(e) => {
                      setObjectives(e.target.value);
                      setObjectivesExtracted(false);
                    }}
                    data-voice-id="learning-objectives"
                  />
                  {syllabus && syllabus.length >= 100 && !objectives.trim() && !extractingObjectives && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => extractObjectivesFromSyllabus(syllabus)}
                    >
                      <FileText className="h-4 w-4 mr-2" />
                      Extract objectives from syllabus
                    </Button>
                  )}
                </div>

                <div className="flex gap-3 pt-2">
                  <Button
                    onClick={() => handleCreateCourse(false)}
                    disabled={creating || !title.trim()}
                    variant="outline"
                    data-voice-id="create-course"
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    {t('courses.createCourse')}
                  </Button>
                  <Button
                    onClick={() => handleCreateCourse(true)}
                    disabled={creating || !title.trim()}
                    variant="accent"
                    data-voice-id="create-course-with-plans"
                  >
                    <FileText className="h-4 w-4 mr-2" />
                    {t('courses.createAndGeneratePlans')}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {isInstructor && (
          <TabsContent value="advanced">
            <Card variant="default">
              <CardHeader>
                <CardTitle>{t('courses.enrollmentManagement')}</CardTitle>
                <CardDescription>Review enrollment and assign students in one place.</CardDescription>
              </CardHeader>
              <CardContent>
                <Select
                  label={t('courses.selectCourse')}
                  value={selectedCourseId?.toString() || ''}
                  onChange={(e) => {
                    setSelectedCourseId(e.target.value ? Number(e.target.value) : null);
                    setSelectedStudentIds(new Set());
                    setStudentSearchQuery('');
                  }}
                  data-voice-id="select-course"
                >
                  <option value="">Select a course...</option>
                  {courses.map((course) => (
                    <option key={course.id} value={course.id}>
                      {course.title} (ID: {course.id})
                    </option>
                  ))}
                </Select>

                {selectedCourseId && (
                  <div className="mt-6 grid md:grid-cols-2 gap-6">
                    <div>
                      <h4 className="font-semibold text-neutral-700 dark:text-neutral-300 mb-3 flex items-center gap-2">
                        <Badge variant="success" size="sm">{enrolledStudents.length}</Badge>
                        {t('courses.enrolledStudents')}
                      </h4>
                      {enrolledStudents.length > 0 ? (
                        <ul className="space-y-2 max-h-96 overflow-y-auto">
                          {enrolledStudents.map((student) => (
                            <li
                              key={student.user_id}
                              className="flex items-center gap-3 text-sm bg-success-50 dark:bg-success-900/20 px-4 py-3 rounded-xl border border-success-200 dark:border-success-800"
                            >
                              <div className="w-8 h-8 rounded-full bg-success-200 dark:bg-success-800 flex items-center justify-center">
                                <Users className="h-4 w-4 text-success-700 dark:text-success-300" />
                              </div>
                              <div>
                                <div className="font-medium text-neutral-900 dark:text-white">{student.name}</div>
                                <div className="text-xs text-neutral-500 dark:text-neutral-400">{student.email}</div>
                              </div>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-sm text-neutral-500 dark:text-neutral-400 italic">{t('courses.noStudentsEnrolled')}</p>
                      )}
                    </div>

                    <div>
                      <h4 className="font-semibold text-neutral-700 dark:text-neutral-300 mb-3 flex items-center gap-2">
                        <Badge variant="default" size="sm">{availableStudents.length}</Badge>
                        {t('courses.availableStudents')}
                      </h4>
                      {availableStudents.length > 0 ? (
                        <div className="space-y-3">
                          <div className="relative">
                            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-neutral-400" />
                            <Input
                              placeholder={t('courses.searchStudents')}
                              value={studentSearchQuery}
                              onChange={(e) => setStudentSearchQuery(e.target.value)}
                              className="pl-10"
                            />
                          </div>

                          <Card variant="outlined" padding="none" className="max-h-64 overflow-y-auto">
                            <div className="sticky top-0 bg-neutral-50 dark:bg-neutral-800 px-4 py-3 border-b border-neutral-200 dark:border-neutral-700 flex items-center justify-between">
                              <label className="flex items-center gap-2 text-sm cursor-pointer">
                                <input
                                  type="checkbox"
                                  checked={selectedStudentIds.size === filteredAvailableStudents.length && filteredAvailableStudents.length > 0}
                                  onChange={toggleSelectAll}
                                  className="rounded border-neutral-300 dark:border-neutral-600 text-primary-600 focus:ring-primary-500"
                                />
                                <span className="text-neutral-700 dark:text-neutral-300">Select All ({filteredAvailableStudents.length})</span>
                              </label>
                              {selectedStudentIds.size > 0 && (
                                <Badge variant="primary" size="sm">
                                  {selectedStudentIds.size} selected
                                </Badge>
                              )}
                            </div>
                            {filteredAvailableStudents.length > 0 ? (
                              <ul className="divide-y divide-neutral-200 dark:divide-neutral-700" data-voice-id="student-pool">
                                {filteredAvailableStudents.map((student) => (
                                  <li
                                    key={student.id}
                                    className="px-4 py-3 hover:bg-neutral-50 dark:hover:bg-neutral-700/50 cursor-pointer transition-colors"
                                    data-voice-item={student.name}
                                    onClick={() => toggleStudentSelection(student.id)}
                                  >
                                    <label className="flex items-center gap-3 cursor-pointer">
                                      <input
                                        type="checkbox"
                                        checked={selectedStudentIds.has(student.id)}
                                        onChange={() => toggleStudentSelection(student.id)}
                                        className="rounded border-neutral-300 dark:border-neutral-600 text-primary-600 focus:ring-primary-500"
                                      />
                                      <div>
                                        <div className="text-sm font-medium text-neutral-900 dark:text-white">{student.name}</div>
                                        <div className="text-xs text-neutral-500 dark:text-neutral-400">{student.email}</div>
                                      </div>
                                    </label>
                                  </li>
                                ))}
                              </ul>
                            ) : (
                              <p className="text-sm text-neutral-500 dark:text-neutral-400 p-4">No students match your search.</p>
                            )}
                          </Card>

                          <div className="flex gap-2">
                            <Button
                              onClick={handleBulkEnroll}
                              disabled={enrolling || selectedStudentIds.size === 0}
                              className="flex-1"
                              data-voice-id="enroll-selected"
                            >
                              <UserPlus className="h-4 w-4 mr-2" />
                              {t('courses.enrollSelected')} ({selectedStudentIds.size})
                            </Button>
                            <Button
                              onClick={handleEnrollAll}
                              disabled={enrolling}
                              variant="outline"
                              data-voice-id="enroll-all"
                            >
                              {t('courses.enrollAll')}
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <p className="text-sm text-neutral-500 dark:text-neutral-400 italic">
                          {allStudents.length === 0
                            ? 'No students in the system yet. Students can sign up and will appear here.'
                            : 'All students are already enrolled in this course.'}
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {!isInstructor && (
          <TabsContent value="join">
            <Card variant="default">
              <CardHeader>
                <CardTitle>{t('courses.joinCourse')}</CardTitle>
                <CardDescription>Enter the course code shared by your instructor.</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-neutral-600 dark:text-neutral-400 mb-4">
                  {t('courses.useJoinCode')}
                </p>
                <div className="flex gap-3 max-w-md">
                  <Input
                    placeholder={t('courses.joinCodePlaceholder')}
                    value={joinCode}
                    onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                    className="font-mono text-lg tracking-wider"
                    maxLength={8}
                  />
                  <Button
                    onClick={handleJoinCourse}
                    disabled={joining || !joinCode.trim()}
                  >
                    {joining ? (
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <UserPlus className="h-4 w-4 mr-2" />
                    )}
                    {t('courses.join')}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {!isInstructor && (
          <TabsContent value="advanced">
            <Card variant="default">
              <CardHeader>
                <CardTitle>{t('courses.requestInstructorAccess')}</CardTitle>
                <CardDescription>Submit a request if you need course-authoring access.</CardDescription>
              </CardHeader>
              <CardContent>
                {currentUser?.instructor_request_status === 'pending' ? (
                  <Card variant="ghost" padding="md" className="bg-warning-50 dark:bg-warning-900/20 border border-warning-200 dark:border-warning-800">
                    <div className="flex items-center gap-3 text-warning-800 dark:text-warning-200">
                      <Clock className="h-5 w-5" />
                      <span className="font-medium">{t('courses.instructorRequestPending')}</span>
                    </div>
                  </Card>
                ) : currentUser?.instructor_request_status === 'rejected' ? (
                  <div className="space-y-4">
                    <Card variant="ghost" padding="md" className="bg-danger-50 dark:bg-danger-900/20 border border-danger-200 dark:border-danger-800">
                      <span className="font-medium text-danger-800 dark:text-danger-200">{t('courses.instructorRequestRejected')}</span>
                    </Card>
                    <Button
                      onClick={handleRequestInstructor}
                      disabled={requestingInstructor}
                      variant="outline"
                    >
                      <GraduationCap className="h-4 w-4 mr-2" />
                      {t('courses.requestInstructorAccess')}
                    </Button>
                  </div>
                ) : (
                  <Button
                    onClick={handleRequestInstructor}
                    disabled={requestingInstructor}
                  >
                    {requestingInstructor ? (
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <GraduationCap className="h-4 w-4 mr-2" />
                    )}
                    {t('courses.requestInstructorAccess')}
                  </Button>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {isInstructor && (
          <TabsContent value="ai-insights">
            <div className="space-y-6">
              {/* Course Selector for AI Insights */}
              <Card variant="default" padding="md">
                <Select
                  label="Select Course for AI Insights"
                  value={selectedCourseId?.toString() || ''}
                  onChange={(e) => setSelectedCourseId(e.target.value ? Number(e.target.value) : null)}
                  data-voice-id="select-course-ai"
                >
                  <option value="">Select a course...</option>
                  {courses.map((course) => (
                    <option key={course.id} value={course.id}>
                      {course.title} (ID: {course.id})
                    </option>
                  ))}
                </Select>
              </Card>

              {selectedCourseId ? (
                <>
                  {/* Participation Insights */}
                  <ParticipationInsightsComponent courseId={selectedCourseId} />

                  {/* Learning Objective Coverage */}
                  <ObjectiveCoverageComponent courseId={selectedCourseId} />

                  {/* Voice Command Hints */}
                  <Card variant="ghost" padding="md">
                    <h3 className="font-semibold text-neutral-900 dark:text-white mb-3">AI Insights Voice Commands</h3>
                    <div className="flex flex-wrap gap-2">
                      {[
                        'Show participation insights',
                        'Who are the at-risk students?',
                        'Analyze participation trends',
                        'Check objective coverage',
                        'What topics need more attention?',
                        'Generate student follow-ups'
                      ].map((cmd) => (
                        <span key={cmd} className="px-3 py-1.5 text-sm bg-white dark:bg-neutral-700 rounded-full text-neutral-600 dark:text-neutral-300 border border-neutral-200 dark:border-neutral-600">
                          "{cmd}"
                        </span>
                      ))}
                    </div>
                  </Card>
                </>
              ) : (
                <Card variant="default" padding="lg">
                  <div className="text-center py-8">
                    <div className="p-4 rounded-2xl bg-primary-50 dark:bg-primary-900/30 w-fit mx-auto mb-4">
                      <BookOpen className="h-10 w-10 text-primary-600 dark:text-primary-400" />
                    </div>
                    <p className="text-neutral-600 dark:text-neutral-400">Select a course to view AI insights</p>
                  </div>
                </Card>
              )}
            </div>
          </TabsContent>
        )}
      </Tabs>

      {/* Edit Course Modal */}
      {editingCourse && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-900/60 backdrop-blur-sm">
          <Card variant="elevated" className="w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-primary-100 dark:bg-primary-900/50">
                    <Edit2 className="h-4 w-4 text-primary-600 dark:text-primary-400" />
                  </div>
                  {t('courses.editCourse')}
                </CardTitle>
                <button
                  onClick={handleCancelEdit}
                  className="p-2 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors"
                >
                  <X className="h-5 w-5 text-neutral-500" />
                </button>
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              <Input
                label={t('courses.courseTitle')}
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
              />

              <Textarea
                label={t('courses.syllabus')}
                rows={6}
                value={editSyllabus}
                onChange={(e) => setEditSyllabus(e.target.value)}
              />

              <Textarea
                label={`${t('courses.learningObjectives')} ${t('courses.onePerLine')}`}
                rows={4}
                value={editObjectives}
                onChange={(e) => setEditObjectives(e.target.value)}
              />
            </CardContent>
            <CardFooter className="flex justify-end gap-3">
              <Button
                variant="outline"
                onClick={handleCancelEdit}
                disabled={saving}
              >
                {t('common.cancel')}
              </Button>
              <Button
                onClick={handleSaveEdit}
                disabled={saving || !editTitle.trim()}
              >
                {saving ? (
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Check className="h-4 w-4 mr-2" />
                )}
                {t('common.save')}
              </Button>
            </CardFooter>
          </Card>
        </div>
      )}
    </div>
  );
}
