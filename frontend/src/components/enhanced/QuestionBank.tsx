'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import {
  Loader2, Plus, Trash2, Edit, CheckCircle, XCircle,
  HelpCircle, ListChecks, FileText, ToggleLeft
} from 'lucide-react';

interface QuestionBankProps {
  courseId: number;
  sessionId?: number;
}

interface Question {
  id: number;
  course_id: number;
  session_id?: number;
  question_type: string;
  question_text: string;
  options?: string[];
  correct_answer?: string;
  explanation?: string;
  difficulty?: string;
  learning_objective?: string;
  tags?: string[];
  times_used: number;
  status: string;
  created_at: string;
}

export function QuestionBankComponent({ courseId, sessionId }: QuestionBankProps) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<{
    question_type?: string;
    difficulty?: string;
    status?: string;
  }>({ status: 'approved' });

  const fetchQuestions = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getQuestionBank(courseId, {
        session_id: sessionId,
        ...filter,
      });
      setQuestions(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load questions');
    } finally {
      setLoading(false);
    }
  };

  const generateQuestions = async () => {
    if (!sessionId) {
      setError('Session ID required to generate questions');
      return;
    }
    try {
      setGenerating(true);
      setError(null);
      await api.generateQuestions(sessionId, {
        question_types: ['mcq', 'short_answer'],
        num_questions: 5,
      });
      setTimeout(fetchQuestions, 5000);
    } catch (err: any) {
      setError(err.message || 'Failed to generate questions');
    } finally {
      setGenerating(false);
    }
  };

  const updateQuestionStatus = async (questionId: number, newStatus: string) => {
    try {
      await api.updateQuestion(questionId, { status: newStatus });
      fetchQuestions();
    } catch (err: any) {
      setError(err.message || 'Failed to update question');
    }
  };

  const deleteQuestion = async (questionId: number) => {
    if (!confirm('Are you sure you want to delete this question?')) return;
    try {
      await api.deleteQuestion(questionId);
      setQuestions(questions.filter(q => q.id !== questionId));
    } catch (err: any) {
      setError(err.message || 'Failed to delete question');
    }
  };

  useEffect(() => {
    fetchQuestions();
  }, [courseId, sessionId, filter]);

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'mcq': return <ListChecks className="w-4 h-4" />;
      case 'short_answer': return <FileText className="w-4 h-4" />;
      case 'true_false': return <ToggleLeft className="w-4 h-4" />;
      default: return <HelpCircle className="w-4 h-4" />;
    }
  };

  const getDifficultyColor = (difficulty?: string) => {
    switch (difficulty) {
      case 'easy': return 'bg-green-100 text-green-800';
      case 'hard': return 'bg-red-100 text-red-800';
      default: return 'bg-yellow-100 text-yellow-800';
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Question Bank</CardTitle>
            <CardDescription>
              AI-generated quiz questions from discussions
            </CardDescription>
          </div>
          {sessionId && (
            <Button
              onClick={generateQuestions}
              disabled={generating}
              size="sm"
              data-voice-id="generate-questions"
            >
              {generating ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <Plus className="w-4 h-4 mr-2" />
              )}
              {generating ? 'Generating...' : 'Generate Questions'}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {/* Filters */}
        <div className="flex gap-2 mb-4 flex-wrap">
          <select
            className="px-3 py-1.5 text-sm border rounded-lg"
            value={filter.status || ''}
            onChange={(e) => setFilter({ ...filter, status: e.target.value || undefined })}
            data-voice-id="question-status-filter"
          >
            <option value="">All Status</option>
            <option value="draft">Draft</option>
            <option value="approved">Approved</option>
            <option value="archived">Archived</option>
          </select>
          <select
            className="px-3 py-1.5 text-sm border rounded-lg"
            value={filter.question_type || ''}
            onChange={(e) => setFilter({ ...filter, question_type: e.target.value || undefined })}
            data-voice-id="question-type-filter"
          >
            <option value="">All Types</option>
            <option value="mcq">Multiple Choice</option>
            <option value="short_answer">Short Answer</option>
            <option value="essay">Essay</option>
            <option value="true_false">True/False</option>
          </select>
          <select
            className="px-3 py-1.5 text-sm border rounded-lg"
            value={filter.difficulty || ''}
            onChange={(e) => setFilter({ ...filter, difficulty: e.target.value || undefined })}
            data-voice-id="question-difficulty-filter"
          >
            <option value="">All Difficulty</option>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </div>

        {error && (
          <div className="p-3 bg-red-50 text-red-700 rounded-lg mb-4">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin" />
          </div>
        ) : questions.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <HelpCircle className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p>No questions found</p>
            {sessionId && (
              <Button className="mt-4" onClick={generateQuestions} disabled={generating} data-voice-id="generate-questions-alt">
                Generate Questions from Discussion
              </Button>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {questions.map((question) => (
              <div
                key={question.id}
                className="p-4 border rounded-lg hover:border-primary-300 transition-colors"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      {getTypeIcon(question.question_type)}
                      <span className="text-xs font-medium uppercase text-gray-500">
                        {question.question_type.replace('_', ' ')}
                      </span>
                      {question.difficulty && (
                        <Badge className={getDifficultyColor(question.difficulty)}>
                          {question.difficulty}
                        </Badge>
                      )}
                      <Badge variant={question.status === 'approved' ? 'success' : 'default'}>
                        {question.status}
                      </Badge>
                    </div>
                    <p className="font-medium text-gray-900 dark:text-white mb-2">
                      {question.question_text}
                    </p>
                    {question.options && question.options.length > 0 && (
                      <div className="ml-4 space-y-1">
                        {question.options.map((opt, idx) => (
                          <div
                            key={idx}
                            className={`text-sm ${opt === question.correct_answer ? 'text-green-600 font-medium' : 'text-gray-600'}`}
                          >
                            {String.fromCharCode(65 + idx)}. {opt}
                            {opt === question.correct_answer && ' ✓'}
                          </div>
                        ))}
                      </div>
                    )}
                    {question.explanation && (
                      <p className="text-sm text-gray-500 mt-2 italic">
                        Explanation: {question.explanation}
                      </p>
                    )}
                    {question.tags && question.tags.length > 0 && (
                      <div className="flex gap-1 mt-2">
                        {question.tags.map((tag, idx) => (
                          <Badge key={idx} variant="default" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex flex-col gap-1">
                    {question.status === 'draft' && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => updateQuestionStatus(question.id, 'approved')}
                        title="Approve"
                        data-voice-id={`approve-question-${question.id}`}
                      >
                        <CheckCircle className="w-4 h-4 text-green-600" />
                      </Button>
                    )}
                    {question.status === 'approved' && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => updateQuestionStatus(question.id, 'archived')}
                        title="Archive"
                        data-voice-id={`archive-question-${question.id}`}
                      >
                        <XCircle className="w-4 h-4 text-gray-400" />
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => deleteQuestion(question.id)}
                      title="Delete"
                      data-voice-id={`delete-question-${question.id}`}
                    >
                      <Trash2 className="w-4 h-4 text-red-500" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default QuestionBankComponent;
