'use client';

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import { BookOpen, Plus, Users, Sparkles, RefreshCw, Copy, Key, Check, Search, UserPlus, GraduationCap, Clock, Upload, FileText, X, Edit2, Trash2 } from 'lucide-react';
import { api } from '@/lib/api';
import { useUser } from '@/lib/context';
import { Course, EnrolledStudent, User } from '@/types';
import { formatTimestamp, truncate } from '@/lib/utils';
import { useTranslations } from 'next-intl';
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Input,
  Textarea,
  Select,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from '@/components/ui';

export default function CoursesPage() {
  const { isInstructor, currentUser, refreshUser } = useUser();
  const searchParams = useSearchParams();
  const t = useTranslations();
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  // Tab state - default from URL query param
  const [activeTab, setActiveTab] = useState(searchParams?.get('tab') || 'courses');

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

  // Handle voice-triggered tab selection
  const handleVoiceSelectTab = useCallback((event: CustomEvent) => {
    const { tab } = event.detail || {};
    if (tab) {
      setActiveTab(tab);
    }
  }, []);

  // Listen for voice tab selection events
  useEffect(() => {
    window.addEventListener('voice-select-tab', handleVoiceSelectTab as EventListener);
    return () => {
      window.removeEventListener('voice-select-tab', handleVoiceSelectTab as EventListener);
    };
  }, [handleVoiceSelectTab]);

  // Update tab when URL changes
  useEffect(() => {
    const tabFromUrl = searchParams?.get('tab');
    if (tabFromUrl) {
      setActiveTab(tabFromUrl);
    }
  }, [searchParams]);

  // Enrollment
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
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
        // Admin sees all courses
        const data = await api.getCourses(currentUser.id);
        setCourses(data);
        if (data.length > 0 && !selectedCourseId) {
          setSelectedCourseId(data[0].id);
        }
      } else if (isInstructor && currentUser) {
        // Instructors see only their own courses
        const data = await api.getCourses(currentUser.id);
        setCourses(data);
        if (data.length > 0 && !selectedCourseId) {
          setSelectedCourseId(data[0].id);
        }
      } else if (currentUser) {
        // Students only see enrolled courses
        const enrolledCourses = await api.getUserEnrolledCourses(currentUser.id);
        // enrolledCourses returns {course_id, course_title, ...}, we need to fetch full course details
        const coursePromises = enrolledCourses.map((ec: any) => api.getCourse(ec.course_id));
        const fullCourses = await Promise.all(coursePromises);
        setCourses(fullCourses);
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

  const handleSyllabusFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    setSyllabusFile(file);
    setSyllabusUploadError(null);
    setUploadingSyllabus(true);

    try {
      const result = await api.uploadSyllabus(file);
      setSyllabus(result.extracted_text);
      setSyllabusUploadError(null);
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
    setSyllabusUploadError(null);
    if (syllabusFileInputRef.current) {
      syllabusFileInputRef.current.value = '';
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

      // If a syllabus file was uploaded, save it to the course materials
      if (syllabusFile && course.id) {
        try {
          await api.uploadSyllabus(syllabusFile, {
            courseId: course.id,
            userId: currentUser?.id,
          });
        } catch (err) {
          console.error('Failed to save syllabus to materials:', err);
          // Don't fail the whole operation if this fails
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

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('courses.title')}</h1>
          <p className="text-gray-600">{t('courses.subtitle')}</p>
        </div>
        <Button onClick={fetchCourses} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          {t('common.refresh')}
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="courses">{t('nav.courses')}</TabsTrigger>
          {isInstructor && <TabsTrigger value="create">{t('courses.createCourse')}</TabsTrigger>}
          {isInstructor && <TabsTrigger value="enrollment">{t('courses.enrollment')}</TabsTrigger>}
          {!isInstructor && <TabsTrigger value="join">{t('courses.joinCourse')}</TabsTrigger>}
          {!isInstructor && <TabsTrigger value="instructor">{t('courses.becomeInstructor')}</TabsTrigger>}
        </TabsList>

        <TabsContent value="courses">
          {loading ? (
            <div className="text-center py-8 text-gray-500">{t('common.loading')}</div>
          ) : courses.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-gray-500">
                <BookOpen className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                {isInstructor ? (
                  <p>{t('courses.noCourses')}</p>
                ) : (
                  <div>
                    <p className="mb-2">{t('courses.noEnrolledCourses')}</p>
                    <p className="text-sm">{t('courses.useJoinCode')}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4">
              {courses.map((course) => (
                <Card key={course.id}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="flex items-center gap-2">
                        <BookOpen className="h-5 w-5 text-primary-600" />
                        {course.title}
                      </CardTitle>
                      <span className="text-sm text-gray-500">ID: {course.id}</span>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid md:grid-cols-2 gap-4">
                      <div>
                        <h4 className="font-medium text-gray-900 mb-2">{t('courses.syllabus')}</h4>
                        <p className="text-sm text-gray-600 whitespace-pre-wrap">
                          {truncate(course.syllabus_text || t('courses.syllabus'), 300)}
                        </p>
                      </div>
                      <div>
                        <h4 className="font-medium text-gray-900 mb-2">{t('courses.learningObjectives')}</h4>
                        {course.objectives_json && course.objectives_json.length > 0 ? (
                          <ul className="text-sm text-gray-600 space-y-1">
                            {course.objectives_json.slice(0, 5).map((obj, i) => (
                              <li key={i} className="flex items-start gap-2">
                                <span className="text-primary-600">•</span>
                                {obj}
                              </li>
                            ))}
                            {course.objectives_json.length > 5 && (
                              <li className="text-gray-400">
                                ...and {course.objectives_json.length - 5} more
                              </li>
                            )}
                          </ul>
                        ) : (
                          <p className="text-sm text-gray-400">No objectives defined</p>
                        )}
                      </div>
                    </div>
                    {isInstructor && course.join_code && (
                      <div className="mt-4 pt-4 border-t border-gray-100">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Key className="h-4 w-4 text-gray-400" />
                            <span className="text-sm text-gray-600">{t('courses.joinCode')}:</span>
                            <code className="bg-gray-100 px-2 py-1 rounded text-sm font-mono font-bold text-primary-600">
                              {course.join_code}
                            </code>
                          </div>
                          <div className="flex items-center gap-2">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleCopyJoinCode(course.id, course.join_code!)}
                              title="Copy join code"
                            >
                              {copiedCourseId === course.id ? (
                                <Check className="h-4 w-4 text-green-600" />
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
                    <div className="mt-4 pt-4 border-t border-gray-100 flex items-center justify-between">
                      <span className="text-xs text-gray-500">
                        Created: {formatTimestamp(course.created_at)}
                      </span>
                      <div className="flex items-center gap-2">
                        {canEditCourse(course) && (
                          <>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleStartEdit(course)}
                              title={t('common.edit')}
                            >
                              <Edit2 className="h-4 w-4" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleDeleteCourse(course.id)}
                              disabled={deleting === course.id}
                              title={t('common.delete')}
                              className="text-red-600 hover:text-red-700 hover:bg-red-50"
                            >
                              {deleting === course.id ? (
                                <RefreshCw className="h-4 w-4 animate-spin" />
                              ) : (
                                <Trash2 className="h-4 w-4" />
                              )}
                            </Button>
                          </>
                        )}
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
                          >
                            <Sparkles className="h-4 w-4 mr-2" />
                            {t('courses.generatePlans')}
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {isInstructor && (
          <TabsContent value="create">
            <Card>
              <CardHeader>
                <CardTitle>{t('courses.createNew')}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Input
                  label={t('courses.courseTitle')}
                  placeholder={t('courses.courseTitlePlaceholder')}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  data-voice-id="course-title"
                />

                {/* Syllabus Input - Toggle between Upload and Paste */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-gray-700">{t('courses.syllabus')}</label>
                  <div className="flex gap-2 mb-2">
                    <button
                      type="button"
                      onClick={() => setSyllabusInputMode('paste')}
                      className={`flex items-center gap-1 px-3 py-1.5 text-sm rounded-md transition-colors ${
                        syllabusInputMode === 'paste'
                          ? 'bg-primary-100 text-primary-700 border border-primary-300'
                          : 'bg-gray-100 text-gray-600 border border-gray-200 hover:bg-gray-200'
                      }`}
                    >
                      <FileText className="h-4 w-4" />
                      {t('courses.pasteText')}
                    </button>
                    <button
                      type="button"
                      onClick={() => setSyllabusInputMode('upload')}
                      className={`flex items-center gap-1 px-3 py-1.5 text-sm rounded-md transition-colors ${
                        syllabusInputMode === 'upload'
                          ? 'bg-primary-100 text-primary-700 border border-primary-300'
                          : 'bg-gray-100 text-gray-600 border border-gray-200 hover:bg-gray-200'
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
                      onChange={(e) => setSyllabus(e.target.value)}
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
                          className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-primary-400 hover:bg-primary-50 transition-colors"
                        >
                          <Upload className="h-10 w-10 mx-auto text-gray-400 mb-3" />
                          <p className="text-sm text-gray-600 mb-1">
                            {t('courses.uploadSyllabus')}
                          </p>
                          <p className="text-xs text-gray-400">
                            {t('courses.supportedFormats')}
                          </p>
                        </div>
                      ) : (
                        <div className="border border-gray-200 rounded-lg p-4">
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                              <FileText className="h-5 w-5 text-primary-500" />
                              <span className="text-sm font-medium text-gray-700">
                                {syllabusFile.name}
                              </span>
                              <span className="text-xs text-gray-400">
                                ({(syllabusFile.size / 1024).toFixed(1)} KB)
                              </span>
                            </div>
                            <button
                              type="button"
                              onClick={handleRemoveSyllabusFile}
                              className="p-1 rounded hover:bg-gray-100"
                              title="Remove file"
                            >
                              <X className="h-4 w-4 text-gray-500" />
                            </button>
                          </div>

                          {uploadingSyllabus && (
                            <div className="flex items-center gap-2 text-sm text-gray-500">
                              <RefreshCw className="h-4 w-4 animate-spin" />
                              Extracting text from file...
                            </div>
                          )}

                          {syllabusUploadError && (
                            <div className="text-sm text-red-600 bg-red-50 p-2 rounded">
                              {syllabusUploadError}
                            </div>
                          )}

                          {syllabus && !uploadingSyllabus && (
                            <div className="mt-2">
                              <p className="text-xs text-gray-500 mb-1">{t('courses.extractedTextPreview')}</p>
                              <div className="bg-gray-50 rounded p-2 max-h-32 overflow-y-auto">
                                <p className="text-xs text-gray-600 whitespace-pre-wrap">
                                  {syllabus.length > 500 ? syllabus.substring(0, 500) + '...' : syllabus}
                                </p>
                              </div>
                              <p className="text-xs text-gray-400 mt-1">
                                {t('courses.charactersExtracted', { count: syllabus.length.toLocaleString() })}
                              </p>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <Textarea
                  label={`${t('courses.learningObjectives')} ${t('courses.onePerLine')}`}
                  placeholder={t('courses.learningObjectivesPlaceholder')}
                  rows={5}
                  value={objectives}
                  onChange={(e) => setObjectives(e.target.value)}
                  data-voice-id="learning-objectives"
                />

                <div className="flex gap-3">
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
                    data-voice-id="create-course-with-plans"
                  >
                    <Sparkles className="h-4 w-4 mr-2" />
                    {t('courses.createAndGeneratePlans')}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {isInstructor && (
          <TabsContent value="enrollment">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-5 w-5" />
                  {t('courses.enrollmentManagement')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Select
                  label={t('courses.selectCourse')}
                  value={selectedCourseId?.toString() || ''}
                  onChange={(e) => {
                    setSelectedCourseId(Number(e.target.value));
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
                      <h4 className="font-medium text-gray-900 mb-3">
                        {t('courses.enrolledStudents')} ({enrolledStudents.length})
                      </h4>
                      {enrolledStudents.length > 0 ? (
                        <ul className="space-y-2 max-h-96 overflow-y-auto">
                          {enrolledStudents.map((student) => (
                            <li
                              key={student.user_id}
                              className="flex items-center gap-2 text-sm text-gray-700 bg-green-50 px-3 py-2 rounded"
                            >
                              <Users className="h-4 w-4 text-green-600" />
                              <div>
                                <div className="font-medium">{student.name}</div>
                                <div className="text-xs text-gray-500">{student.email}</div>
                              </div>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-sm text-gray-500">{t('courses.noStudentsEnrolled')}</p>
                      )}
                    </div>

                    <div>
                      <h4 className="font-medium text-gray-900 mb-3">
                        {t('courses.availableStudents')} ({availableStudents.length})
                      </h4>
                      {availableStudents.length > 0 ? (
                        <div className="space-y-3">
                          <div className="relative">
                            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                            <Input
                              placeholder={t('courses.searchStudents')}
                              value={studentSearchQuery}
                              onChange={(e) => setStudentSearchQuery(e.target.value)}
                              className="pl-10"
                            />
                          </div>

                          <div className="border rounded-lg max-h-64 overflow-y-auto">
                            <div className="sticky top-0 bg-gray-50 px-3 py-2 border-b flex items-center justify-between">
                              <label className="flex items-center gap-2 text-sm cursor-pointer">
                                <input
                                  type="checkbox"
                                  checked={selectedStudentIds.size === filteredAvailableStudents.length && filteredAvailableStudents.length > 0}
                                  onChange={toggleSelectAll}
                                  className="rounded border-gray-300"
                                />
                                Select All ({filteredAvailableStudents.length})
                              </label>
                              {selectedStudentIds.size > 0 && (
                                <span className="text-xs text-primary-600 font-medium">
                                  {selectedStudentIds.size} selected
                                </span>
                              )}
                            </div>
                            {filteredAvailableStudents.length > 0 ? (
                              <ul className="divide-y" data-voice-id="student-pool">
                                {filteredAvailableStudents.map((student) => (
                                  <li
                                    key={student.id}
                                    className="px-3 py-2 hover:bg-gray-50 cursor-pointer"
                                    data-voice-item={student.name}
                                    onClick={() => toggleStudentSelection(student.id)}
                                  >
                                    <label className="flex items-center gap-3 cursor-pointer">
                                      <input
                                        type="checkbox"
                                        checked={selectedStudentIds.has(student.id)}
                                        onChange={() => toggleStudentSelection(student.id)}
                                        className="rounded border-gray-300"
                                      />
                                      <div>
                                        <div className="text-sm font-medium text-gray-900">{student.name}</div>
                                        <div className="text-xs text-gray-500">{student.email}</div>
                                      </div>
                                    </label>
                                  </li>
                                ))}
                              </ul>
                            ) : (
                              <p className="text-sm text-gray-500 p-3">No students match your search.</p>
                            )}
                          </div>

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
                        <p className="text-sm text-gray-500">
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
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Key className="h-5 w-5" />
                  {t('courses.joinCourse')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-gray-600 mb-4">
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
          <TabsContent value="instructor">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <GraduationCap className="h-5 w-5" />
                  {t('courses.requestInstructorAccess')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {currentUser?.instructor_request_status === 'pending' ? (
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                    <div className="flex items-center gap-2 text-yellow-800 mb-2">
                      <Clock className="h-5 w-5" />
                      <span className="font-medium">{t('courses.instructorRequestPending')}</span>
                    </div>
                  </div>
                ) : currentUser?.instructor_request_status === 'rejected' ? (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <div className="flex items-center gap-2 text-red-800 mb-2">
                      <span className="font-medium">{t('courses.instructorRequestRejected')}</span>
                    </div>
                    <Button
                      onClick={handleRequestInstructor}
                      disabled={requestingInstructor}
                      variant="outline"
                      className="mt-4"
                    >
                      <GraduationCap className="h-4 w-4 mr-2" />
                      {t('courses.requestInstructorAccess')}
                    </Button>
                  </div>
                ) : (
                  <div>
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
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>

      {/* Edit Course Modal */}
      {editingCourse && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                  {t('courses.editCourse')}
                </h2>
                <button
                  onClick={handleCancelEdit}
                  className="p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="space-y-4">
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

                <div className="flex justify-end gap-3 pt-4 border-t">
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
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
