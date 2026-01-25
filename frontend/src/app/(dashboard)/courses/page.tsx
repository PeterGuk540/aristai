'use client';

import { useState, useEffect } from 'react';
import { BookOpen, Plus, Users, Sparkles, RefreshCw } from 'lucide-react';
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
  const { isInstructor } = useUser();
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  // Create course form
  const [title, setTitle] = useState('');
  const [syllabus, setSyllabus] = useState('');
  const [objectives, setObjectives] = useState('');

  // Enrollment
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  const [enrolledStudents, setEnrolledStudents] = useState<EnrolledStudent[]>([]);
  const [allStudents, setAllStudents] = useState<User[]>([]);
  const [enrolling, setEnrolling] = useState(false);

  const fetchCourses = async () => {
    try {
      setLoading(true);
      const data = await api.getCourses();
      setCourses(data);
      if (data.length > 0 && !selectedCourseId) {
        setSelectedCourseId(data[0].id);
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
    fetchCourses();
  }, []);

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

  const enrolledIds = new Set(enrolledStudents.map((s) => s.user_id));
  const availableStudents = allStudents.filter((s) => !enrolledIds.has(s.id));

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

      <Tabs defaultValue="courses">
        <TabsList>
          <TabsTrigger value="courses">Courses</TabsTrigger>
          {isInstructor && <TabsTrigger value="create">Create Course</TabsTrigger>}
          {isInstructor && <TabsTrigger value="enrollment">Enrollment</TabsTrigger>}
        </TabsList>

        <TabsContent value="courses">
          {loading ? (
            <div className="text-center py-8 text-gray-500">Loading courses...</div>
          ) : courses.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-gray-500">
                <BookOpen className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                <p>No courses found. Create one to get started!</p>
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
                />

                <Textarea
                  label="Syllabus"
                  placeholder="Paste your full syllabus here..."
                  rows={8}
                  value={syllabus}
                  onChange={(e) => setSyllabus(e.target.value)}
                />

                <Textarea
                  label="Learning Objectives (one per line)"
                  placeholder="Understand ML fundamentals&#10;Apply supervised learning&#10;Evaluate model performance"
                  rows={5}
                  value={objectives}
                  onChange={(e) => setObjectives(e.target.value)}
                />

                <div className="flex gap-3">
                  <Button
                    onClick={() => handleCreateCourse(false)}
                    disabled={creating || !title.trim()}
                    variant="outline"
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Create Course
                  </Button>
                  <Button
                    onClick={() => handleCreateCourse(true)}
                    disabled={creating || !title.trim()}
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
                  onChange={(e) => setSelectedCourseId(Number(e.target.value))}
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
                        <ul className="space-y-2">
                          {enrolledStudents.map((student) => (
                            <li
                              key={student.user_id}
                              className="flex items-center gap-2 text-sm text-gray-700 bg-green-50 px-3 py-2 rounded"
                            >
                              <Users className="h-4 w-4 text-green-600" />
                              {student.name}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-sm text-gray-500">No students enrolled yet.</p>
                      )}
                    </div>

                    <div>
                      <h4 className="font-medium text-gray-900 mb-3">Enroll Students</h4>
                      {availableStudents.length > 0 ? (
                        <div className="space-y-3">
                          <Select
                            onChange={(e) => {
                              if (e.target.value) {
                                handleEnrollStudent(Number(e.target.value));
                                e.target.value = '';
                              }
                            }}
                            disabled={enrolling}
                          >
                            <option value="">Select student to enroll...</option>
                            {availableStudents.map((student) => (
                              <option key={student.id} value={student.id}>
                                {student.name}
                              </option>
                            ))}
                          </Select>

                          <div className="pt-2 border-t">
                            <Button
                              onClick={handleEnrollAll}
                              disabled={enrolling}
                              className="w-full"
                            >
                              <Users className="h-4 w-4 mr-2" />
                              Enroll All Students
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <p className="text-sm text-gray-500">
                          {allStudents.length === 0
                            ? 'No students in the system.'
                            : 'All students are already enrolled.'}
                        </p>
                      )}
                    </div>
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
