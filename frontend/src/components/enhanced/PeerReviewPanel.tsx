'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Textarea } from '@/components/ui/Textarea';
import {
  Loader2, Plus, Users, FileText, Star, Send, CheckCircle
} from 'lucide-react';

interface PeerReviewPanelProps {
  sessionId: number;
  userId: number;
  isInstructor?: boolean;
}

interface PeerReviewAssignment {
  id: number;
  session_id: number;
  submission_post_id: number;
  author_name: string;
  reviewer_name: string;
  status: string;
  due_at?: string;
  submitted_at?: string;
  feedback?: {
    overall_rating?: number;
    strengths?: string[];
    areas_for_improvement?: string[];
    specific_comments?: string;
  };
}

interface AssignedReview {
  id: number;
  author_name: string;
  submission_content?: string;
  due_at?: string;
  status: string;
}

export function PeerReviewPanelComponent({ sessionId, userId, isInstructor = false }: PeerReviewPanelProps) {
  const [assignments, setAssignments] = useState<PeerReviewAssignment[]>([]);
  const [myReviews, setMyReviews] = useState<AssignedReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedReview, setSelectedReview] = useState<AssignedReview | null>(null);
  const [feedback, setFeedback] = useState({
    overall_rating: 3,
    strengths: [''],
    areas_for_improvement: [''],
    specific_comments: '',
  });

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      if (isInstructor) {
        const allAssignments = await api.getSessionPeerReviews(sessionId);
        setAssignments(allAssignments);
      }

      const userReviews = await api.getUserAssignedReviews(userId);
      setMyReviews(userReviews);
    } catch (err: any) {
      setError(err.message || 'Failed to load peer reviews');
    } finally {
      setLoading(false);
    }
  };

  const createAssignments = async () => {
    try {
      setCreating(true);
      await api.createPeerReviews(sessionId, { reviews_per_submission: 2 });
      setTimeout(fetchData, 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to create assignments');
    } finally {
      setCreating(false);
    }
  };

  const submitReview = async () => {
    if (!selectedReview) return;
    try {
      await api.submitPeerReview(selectedReview.id, {
        overall_rating: feedback.overall_rating,
        strengths: feedback.strengths.filter(s => s.trim()),
        areas_for_improvement: feedback.areas_for_improvement.filter(s => s.trim()),
        specific_comments: feedback.specific_comments,
      });
      setSelectedReview(null);
      setFeedback({
        overall_rating: 3,
        strengths: [''],
        areas_for_improvement: [''],
        specific_comments: '',
      });
      fetchData();
    } catch (err: any) {
      setError(err.message || 'Failed to submit review');
    }
  };

  useEffect(() => {
    fetchData();
  }, [sessionId, userId]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'submitted': return 'bg-green-100 text-green-800';
      case 'in_progress': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  // Review submission form
  if (selectedReview) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Submit Peer Review</CardTitle>
          <CardDescription>
            Reviewing submission by {selectedReview.author_name}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Submission Content */}
          <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <h4 className="text-sm font-medium mb-2">Submission</h4>
            <p className="text-sm text-gray-700 dark:text-gray-300">
              {selectedReview.submission_content || 'Content not available'}
            </p>
          </div>

          {/* Overall Rating */}
          <div>
            <label className="block text-sm font-medium mb-2">Overall Rating</label>
            <div className="flex gap-2">
              {[1, 2, 3, 4, 5].map((rating) => (
                <button
                  key={rating}
                  onClick={() => setFeedback({ ...feedback, overall_rating: rating })}
                  className="p-2"
                >
                  <Star
                    className={`w-6 h-6 ${rating <= feedback.overall_rating ? 'fill-yellow-400 text-yellow-400' : 'text-gray-300'}`}
                  />
                </button>
              ))}
            </div>
          </div>

          {/* Strengths */}
          <div>
            <label className="block text-sm font-medium mb-2">Strengths</label>
            {feedback.strengths.map((strength, idx) => (
              <input
                key={idx}
                type="text"
                value={strength}
                onChange={(e) => {
                  const newStrengths = [...feedback.strengths];
                  newStrengths[idx] = e.target.value;
                  setFeedback({ ...feedback, strengths: newStrengths });
                }}
                className="w-full px-3 py-2 border rounded-lg mb-2"
                placeholder="What did they do well?"
              />
            ))}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setFeedback({ ...feedback, strengths: [...feedback.strengths, ''] })}
            >
              + Add Strength
            </Button>
          </div>

          {/* Areas for Improvement */}
          <div>
            <label className="block text-sm font-medium mb-2">Areas for Improvement</label>
            {feedback.areas_for_improvement.map((area, idx) => (
              <input
                key={idx}
                type="text"
                value={area}
                onChange={(e) => {
                  const newAreas = [...feedback.areas_for_improvement];
                  newAreas[idx] = e.target.value;
                  setFeedback({ ...feedback, areas_for_improvement: newAreas });
                }}
                className="w-full px-3 py-2 border rounded-lg mb-2"
                placeholder="What could be improved?"
              />
            ))}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setFeedback({ ...feedback, areas_for_improvement: [...feedback.areas_for_improvement, ''] })}
            >
              + Add Area
            </Button>
          </div>

          {/* Specific Comments */}
          <div>
            <label className="block text-sm font-medium mb-2">Additional Comments</label>
            <Textarea
              value={feedback.specific_comments}
              onChange={(e) => setFeedback({ ...feedback, specific_comments: e.target.value })}
              placeholder="Any other feedback..."
              rows={4}
            />
          </div>

          <div className="flex gap-2">
            <Button onClick={submitReview}>
              <Send className="w-4 h-4 mr-2" />
              Submit Review
            </Button>
            <Button variant="secondary" onClick={() => setSelectedReview(null)}>
              Cancel
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* My Assigned Reviews */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5" />
            My Peer Reviews
          </CardTitle>
          <CardDescription>
            Reviews assigned to you
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="p-3 bg-red-50 text-red-700 rounded-lg mb-4">
              {error}
            </div>
          )}

          {myReviews.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No peer reviews assigned to you
            </div>
          ) : (
            <div className="space-y-3">
              {myReviews.map((review) => (
                <div
                  key={review.id}
                  className="p-4 border rounded-lg flex items-center justify-between hover:border-primary-300"
                >
                  <div>
                    <p className="font-medium">Review for {review.author_name}</p>
                    <Badge className={getStatusColor(review.status)}>
                      {review.status}
                    </Badge>
                    {review.due_at && (
                      <p className="text-xs text-gray-500 mt-1">
                        Due: {new Date(review.due_at).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                  {review.status !== 'submitted' && (
                    <Button size="sm" onClick={() => setSelectedReview(review)}>
                      Start Review
                    </Button>
                  )}
                  {review.status === 'submitted' && (
                    <CheckCircle className="w-5 h-5 text-green-500" />
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Instructor View: All Assignments */}
      {isInstructor && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Users className="w-5 h-5" />
                  All Peer Review Assignments
                </CardTitle>
                <CardDescription>
                  Manage peer review workflow
                </CardDescription>
              </div>
              <Button onClick={createAssignments} disabled={creating} data-voice-id="match-peer-reviews">
                {creating ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <Users className="w-4 h-4 mr-2" />
                )}
                Match Students for Review
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {assignments.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No peer review assignments yet
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 px-3">Author</th>
                      <th className="text-left py-2 px-3">Reviewer</th>
                      <th className="text-center py-2 px-3">Status</th>
                      <th className="text-center py-2 px-3">Rating</th>
                    </tr>
                  </thead>
                  <tbody>
                    {assignments.map((assignment) => (
                      <tr key={assignment.id} className="border-b">
                        <td className="py-2 px-3">{assignment.author_name}</td>
                        <td className="py-2 px-3">{assignment.reviewer_name}</td>
                        <td className="text-center py-2 px-3">
                          <Badge className={getStatusColor(assignment.status)}>
                            {assignment.status}
                          </Badge>
                        </td>
                        <td className="text-center py-2 px-3">
                          {assignment.feedback?.overall_rating ? (
                            <div className="flex items-center justify-center gap-1">
                              <Star className="w-4 h-4 fill-yellow-400 text-yellow-400" />
                              {assignment.feedback.overall_rating}/5
                            </div>
                          ) : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default PeerReviewPanelComponent;
