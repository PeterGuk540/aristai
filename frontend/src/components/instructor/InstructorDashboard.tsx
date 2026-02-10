'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  Activity,
  Timer,
  Lightbulb,
  Users,
  BarChart3,
  BookOpen,
  FileText,
  Bot,
  ChevronDown,
  ChevronUp,
  Maximize2,
  Minimize2
} from 'lucide-react';

import { EngagementHeatmapComponent } from './EngagementHeatmap';
import { SessionTimerComponent } from './SessionTimer';
import { FacilitationPanel } from './FacilitationPanel';
import { BreakoutGroupsComponent } from './BreakoutGroups';
import { StudentProgressComponent } from './StudentProgress';
import { PreClassInsightsComponent } from './PreClassInsights';
import { PostClassSummaryComponent } from './PostClassSummary';
import { AIResponseDraftsComponent } from './AIResponseDrafts';

interface InstructorDashboardProps {
  sessionId: number;
  courseId: number;
  instructorId: number;
  sessionStatus: 'before' | 'live' | 'ended';
}

type PanelId = 'engagement' | 'timer' | 'facilitation' | 'breakout' | 'progress' | 'preclass' | 'postclass' | 'ai';

interface PanelConfig {
  id: PanelId;
  title: string;
  icon: React.ElementType;
  showWhen: ('before' | 'live' | 'ended')[];
}

const panelConfigs: PanelConfig[] = [
  { id: 'preclass', title: 'Pre-Class Insights', icon: BookOpen, showWhen: ['before', 'live'] },
  { id: 'engagement', title: 'Engagement Heatmap', icon: Activity, showWhen: ['live'] },
  { id: 'timer', title: 'Session Timer', icon: Timer, showWhen: ['live'] },
  { id: 'facilitation', title: 'Facilitation Suggestions', icon: Lightbulb, showWhen: ['live'] },
  { id: 'breakout', title: 'Breakout Groups', icon: Users, showWhen: ['live'] },
  { id: 'ai', title: 'AI Response Drafts', icon: Bot, showWhen: ['live'] },
  { id: 'progress', title: 'Student Progress', icon: BarChart3, showWhen: ['before', 'live', 'ended'] },
  { id: 'postclass', title: 'Session Summary', icon: FileText, showWhen: ['ended'] },
];

export function InstructorDashboard({ sessionId, courseId, instructorId, sessionStatus }: InstructorDashboardProps) {
  const [expandedPanels, setExpandedPanels] = useState<Set<PanelId>>(new Set(['engagement', 'timer']));
  const [focusedPanel, setFocusedPanel] = useState<PanelId | null>(null);

  const togglePanel = (panelId: PanelId) => {
    const newExpanded = new Set(expandedPanels);
    if (newExpanded.has(panelId)) {
      newExpanded.delete(panelId);
    } else {
      newExpanded.add(panelId);
    }
    setExpandedPanels(newExpanded);
  };

  const toggleFocus = (panelId: PanelId) => {
    setFocusedPanel(focusedPanel === panelId ? null : panelId);
  };

  const renderPanelContent = (panelId: PanelId) => {
    switch (panelId) {
      case 'engagement':
        return <EngagementHeatmapComponent sessionId={sessionId} />;
      case 'timer':
        return <SessionTimerComponent sessionId={sessionId} />;
      case 'facilitation':
        return <FacilitationPanel sessionId={sessionId} />;
      case 'breakout':
        return <BreakoutGroupsComponent sessionId={sessionId} />;
      case 'progress':
        return <StudentProgressComponent courseId={courseId} />;
      case 'preclass':
        return <PreClassInsightsComponent sessionId={sessionId} />;
      case 'postclass':
        return <PostClassSummaryComponent sessionId={sessionId} />;
      case 'ai':
        return <AIResponseDraftsComponent sessionId={sessionId} instructorId={instructorId} />;
      default:
        return null;
    }
  };

  const visiblePanels = panelConfigs.filter(p => p.showWhen.includes(sessionStatus));

  // If a panel is focused, show only that panel
  if (focusedPanel) {
    const panel = panelConfigs.find(p => p.id === focusedPanel);
    if (panel) {
      const Icon = panel.icon;
      return (
        <div className="h-full bg-gray-50 dark:bg-gray-900 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg h-full overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <Icon className="w-5 h-5 text-primary-600" />
                {panel.title}
              </h2>
              <button
                onClick={() => toggleFocus(panel.id)}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                title="Exit focus mode"
              >
                <Minimize2 className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 overflow-auto" style={{ height: 'calc(100% - 60px)' }}>
              {renderPanelContent(panel.id)}
            </div>
          </div>
        </div>
      );
    }
  }

  return (
    <div className="bg-gray-50 dark:bg-gray-900 min-h-full p-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Instructor Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">
            Session status: <span className={cn(
              'font-medium',
              sessionStatus === 'live' ? 'text-green-600' :
              sessionStatus === 'ended' ? 'text-gray-600' : 'text-yellow-600'
            )}>{sessionStatus === 'live' ? 'Live' : sessionStatus === 'ended' ? 'Ended' : 'Not Started'}</span>
          </p>
        </div>

        {/* Panels Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {visiblePanels.map((panel) => {
            const Icon = panel.icon;
            const isExpanded = expandedPanels.has(panel.id);

            return (
              <div
                key={panel.id}
                className={cn(
                  'bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden transition-all',
                  isExpanded ? 'row-span-1' : ''
                )}
              >
                {/* Panel Header */}
                <div
                  className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 border-b"
                  onClick={() => togglePanel(panel.id)}
                >
                  <h3 className="font-medium flex items-center gap-2">
                    <Icon className="w-5 h-5 text-primary-600" />
                    {panel.title}
                  </h3>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleFocus(panel.id);
                      }}
                      className="p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded"
                      title="Focus on this panel"
                    >
                      <Maximize2 className="w-4 h-4 text-gray-400" />
                    </button>
                    {isExpanded ? (
                      <ChevronUp className="w-5 h-5 text-gray-400" />
                    ) : (
                      <ChevronDown className="w-5 h-5 text-gray-400" />
                    )}
                  </div>
                </div>

                {/* Panel Content */}
                {isExpanded && (
                  <div className="p-4">
                    {renderPanelContent(panel.id)}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Quick Actions */}
        {sessionStatus === 'live' && (
          <div className="mt-6 p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
            <h3 className="font-medium mb-3">Quick Voice Commands</h3>
            <div className="flex flex-wrap gap-2">
              {[
                'Show engagement heatmap',
                'Who needs attention?',
                'Start a 5 minute timer',
                'Split into 4 groups',
                'Suggest a poll',
                'Show AI drafts'
              ].map((command) => (
                <span
                  key={command}
                  className="px-3 py-1 text-sm bg-gray-100 dark:bg-gray-700 rounded-full text-gray-600 dark:text-gray-300"
                >
                  "{command}"
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default InstructorDashboard;
