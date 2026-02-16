'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Loader2, RefreshCw, AlertCircle, CheckCircle, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface LiveSummaryProps {
  sessionId: number;
}

interface Summary {
  id: number;
  summary_text: string;
  key_themes?: string[];
  unanswered_questions?: string[];
  misconceptions?: Array<{ concept: string; misconception: string; correction: string }>;
  engagement_pulse?: string;
  posts_analyzed?: number;
  created_at: string;
}

export function LiveSummaryComponent({ sessionId }: LiveSummaryProps) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getLiveSummary(sessionId);
      setSummary(data);
    } catch (err: any) {
      if (err.status === 404) {
        setSummary(null);
      } else {
        setError(err.message || 'Failed to load summary');
      }
    } finally {
      setLoading(false);
    }
  };

  const generateSummary = async () => {
    try {
      setGenerating(true);
      setError(null);
      await api.generateLiveSummary(sessionId);
      // Poll for completion
      setTimeout(fetchSummary, 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to generate summary');
    } finally {
      setGenerating(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, [sessionId]);

  const getEngagementIcon = (pulse?: string) => {
    switch (pulse) {
      case 'high': return <TrendingUp className="w-4 h-4 text-green-500" />;
      case 'low': return <TrendingDown className="w-4 h-4 text-red-500" />;
      default: return <Minus className="w-4 h-4 text-yellow-500" />;
    }
  };

  const getEngagementColor = (pulse?: string) => {
    switch (pulse) {
      case 'high': return 'bg-green-100 text-green-800';
      case 'low': return 'bg-red-100 text-red-800';
      default: return 'bg-yellow-100 text-yellow-800';
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-primary-600" />
          <span className="ml-2">Loading summary...</span>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              Live Discussion Summary
              {summary?.engagement_pulse && (
                <Badge className={getEngagementColor(summary.engagement_pulse)}>
                  {getEngagementIcon(summary.engagement_pulse)}
                  <span className="ml-1 capitalize">{summary.engagement_pulse} Engagement</span>
                </Badge>
              )}
            </CardTitle>
            <CardDescription>
              AI-generated summary of the ongoing discussion
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={generateSummary}
            disabled={generating}
          >
            {generating ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : (
              <RefreshCw className="w-4 h-4 mr-2" />
            )}
            {generating ? 'Generating...' : 'Refresh'}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <div className="flex items-center gap-2 p-3 bg-red-50 text-red-700 rounded-lg">
            <AlertCircle className="w-5 h-5" />
            {error}
          </div>
        )}

        {!summary && !error && (
          <div className="text-center py-8 text-gray-500">
            <p className="mb-4">No summary available yet</p>
            <Button onClick={generateSummary} disabled={generating}>
              {generating ? 'Generating...' : 'Generate Summary'}
            </Button>
          </div>
        )}

        {summary && (
          <>
            <div className="prose prose-sm max-w-none">
              <p className="text-gray-700 dark:text-gray-300">{summary.summary_text}</p>
            </div>

            {summary.key_themes && summary.key_themes.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2">Key Themes</h4>
                <div className="flex flex-wrap gap-2">
                  {summary.key_themes.map((theme, idx) => (
                    <Badge key={idx} variant="secondary">{theme}</Badge>
                  ))}
                </div>
              </div>
            )}

            {summary.unanswered_questions && summary.unanswered_questions.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2">Unanswered Questions</h4>
                <ul className="list-disc list-inside space-y-1 text-sm text-gray-600 dark:text-gray-400">
                  {summary.unanswered_questions.map((q, idx) => (
                    <li key={idx}>{q}</li>
                  ))}
                </ul>
              </div>
            )}

            {summary.misconceptions && summary.misconceptions.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2">Detected Misconceptions</h4>
                <div className="space-y-2">
                  {summary.misconceptions.map((m, idx) => (
                    <div key={idx} className="p-3 bg-orange-50 dark:bg-orange-900/20 rounded-lg text-sm">
                      <p className="font-medium text-orange-800 dark:text-orange-200">{m.concept}</p>
                      <p className="text-orange-700 dark:text-orange-300 mt-1">
                        <strong>Misconception:</strong> {m.misconception}
                      </p>
                      <p className="text-green-700 dark:text-green-300 mt-1">
                        <strong>Correction:</strong> {m.correction}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="text-xs text-gray-400 flex items-center justify-between">
              <span>{summary.posts_analyzed} posts analyzed</span>
              <span>Last updated: {new Date(summary.created_at).toLocaleTimeString()}</span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

export default LiveSummaryComponent;
