'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import { BookOpen, Plus, Users, Sparkles, RefreshCw, Copy, Key, Check, Search, UserPlus, GraduationCap, Clock } from 'lucide-react';
import { api } from '@/lib/api';
import { useUser } from '@/lib/context';
import { Course, EnrolledStudent, User } from '@/types';
import { formatTimestamp, truncate } from '@/lib/utils';
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
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  // Tab state - default from URL query param
  const [activeTab, setActiveTab] = useState(searchParams?.get('tab') || 'courses');

  // Create course form
  const [title, setTitle] = useState('');
  const [syllabus, setSyllabus] = useState('');
  const [objectives, setObjectives] = useState('');

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

  const fetchCourses = async () => {
    try {
      setLoading(true);

      if (isInstructor) {
        // Instructors see all courses
        const data = await api.getCourses();
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
      });

      if (generatePlans) {
        await api.generatePlans(course.id);
        alert(`Course created! Plan generation started.`);
      } else {
        alert(`Course created with ID: ${course.id}`);
      }

      setTitle('');
      setSyllabus('');
      setObjectives('');
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
          <h1 className="text-2xl font-bold text-gray-900">Course Management</h1>
          <p className="text-gray-600">Create and manage courses</p>
        </div>
        <Button onClick={fetchCourses} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="courses">Courses</TabsTrigger>
          {isInstructor && <TabsTrigger value="create">Create Course</TabsTrigger>}
          {isInstructor && <TabsTrigger value="enrollment">Enrollment</TabsTrigger>}
          {!isInstructor && <TabsTrigger value="join">Join Course</TabsTrigger>}
          {!isInstructor && <TabsTrigger value="instructor">Become Instructor</TabsTrigger>}
        </TabsList>

        <TabsContent value="courses">
          {loading ? (
            <div className="text-center py-8 text-gray-500">Loading courses...</div>
          ) : courses.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-gray-500">
                <BookOpen className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                {isInstructor ? (
                  <p>No courses found. Create one to get started!</p>
                ) : (
                  <div>
                    <p className="mb-2">You are not enrolled in any courses yet.</p>
                    <p className="text-sm">Use the "Join Course" tab to enter a course code from your instructor.</p>
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
                        <h4 className="font-medium text-gray-900 mb-2">Syllabus Preview</h4>
                        <p className="text-sm text-gray-600 whitespace-pre-wrap">
                          {truncate(course.syllabus_text || 'No syllabus', 300)}
                        </p>
                      </div>
                      <div>
                        <h4 className="font-medium text-gray-900 mb-2">Learning Objectives</h4>
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
                            <span className="text-sm text-gray-600">Join Code:</span>
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
                          Generate Plans
                        </Button>
                      )}
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
                <CardTitle>Create New Course</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Input
                  label="Course Title"
                  placeholder="e.g., Introduction to Machine Learning"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  data-voice-id="course-title"
                />

                <Textarea
                  label="Syllabus"
                  placeholder="Paste your full syllabus here..."
                  rows={8}
                  value={syllabus}
                  onChange={(e) => setSyllabus(e.target.value)}
                  data-voice-id="syllabus"
                />

                <Textarea
                  label="Learning Objectives (one per line)"
                  placeholder="Understand ML fundamentals&#10;Apply supervised learning&#10;Evaluate model performance"
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
                    Create Course
                  </Button>
                  <Button
                    onClick={() => handleCreateCourse(true)}
                    disabled={creating || !title.trim()}
                    data-voice-id="create-course-with-plans"
                  >
                    <Sparkles className="h-4 w-4 mr-2" />
                    Create & Generate Plans
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
                  Enrollment Management
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Select
                  label="Select Course"
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
                        Enrolled Students ({enrolledStudents.length})
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
                        <p className="text-sm text-gray-500">No students enrolled yet.</p>
                      )}
                    </div>

                    <div>
                      <h4 className="font-medium text-gray-900 mb-3">
                        Student Pool ({availableStudents.length} available)
                      </h4>
                      {availableStudents.length > 0 ? (
                        <div className="space-y-3">
                          <div className="relative">
                            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                            <Input
                              placeholder="Search by name or email..."
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
                              <ul className="divide-y">
                                {filteredAvailableStudents.map((student) => (
                                  <li
                                    key={student.id}
                                    className="px-3 py-2 hover:bg-gray-50 cursor-pointer"
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
                            >
                              <UserPlus className="h-4 w-4 mr-2" />
                              Enroll Selected ({selectedStudentIds.size})
                            </Button>
                            <Button
                              onClick={handleEnrollAll}
                              disabled={enrolling}
                              variant="outline"
                            >
                              Enroll All
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
                  Join a Course
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-gray-600 mb-4">
                  Enter the join code provided by your instructor to enroll in a course.
                </p>
                <div className="flex gap-3 max-w-md">
                  <Input
                    placeholder="Enter join code (e.g., ABC12345)"
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
                    Join
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
                  Request Instructor Access
                </CardTitle>
              </CardHeader>
              <CardContent>
                {currentUser?.instructor_request_status === 'pending' ? (
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                    <div className="flex items-center gap-2 text-yellow-800 mb-2">
                      <Clock className="h-5 w-5" />
                      <span className="font-medium">Request Pending</span>
                    </div>
                    <p className="text-sm text-yellow-700">
                      Your instructor access request is being reviewed. An existing instructor will approve or reject your request.
                    </p>
                  </div>
                ) : currentUser?.instructor_request_status === 'rejected' ? (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <div className="flex items-center gap-2 text-red-800 mb-2">
                      <span className="font-medium">Request Rejected</span>
                    </div>
                    <p className="text-sm text-red-700 mb-4">
                      Your previous request was not approved. If you believe this was a mistake, please contact an administrator.
                    </p>
                    <Button
                      onClick={handleRequestInstructor}
                      disabled={requestingInstructor}
                      variant="outline"
                    >
                      <GraduationCap className="h-4 w-4 mr-2" />
                      Request Again
                    </Button>
                  </div>
                ) : (
                  <div>
                    <p className="text-sm text-gray-600 mb-4">
                      If you are an instructor and need to create and manage courses, you can request instructor access.
                      An existing instructor will review and approve your request.
                    </p>
                    <Button
                      onClick={handleRequestInstructor}
                      disabled={requestingInstructor}
                    >
                      {requestingInstructor ? (
                        <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <GraduationCap className="h-4 w-4 mr-2" />
                      )}
                      Request Instructor Access
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}
