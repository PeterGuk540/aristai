'use client';

import { VoicePlan } from '@/types';
import { cn } from '@/lib/utils';
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  BookOpen,
  Calendar,
  MessageSquare,
  BarChart3,
  Users,
  FileText,
  Settings,
  Eye,
  Edit,
} from 'lucide-react';

interface VoicePlanPreviewProps {
  plan: VoicePlan;
  onConfirm: () => void;
  onCancel: () => void;
  className?: string;
}

// Map tool names to icons
const toolIcons: Record<string, any> = {
  // Course tools
  list_courses: BookOpen,
  get_course: BookOpen,
  create_course: BookOpen,
  update_course: Edit,
  generate_session_plans: BookOpen,
  
  // Session tools
  list_sessions: Calendar,
  get_session: Calendar,
  create_session: Calendar,
  update_session_status: Calendar,
  
  // Forum tools
  list_posts: MessageSquare,
  create_post: MessageSquare,
  pin_post: MessageSquare,
  label_post: MessageSquare,
  
  // Poll tools
  create_poll: BarChart3,
  get_poll_results: BarChart3,
  
  // Copilot tools
  start_copilot: Settings,
  stop_copilot: Settings,
  get_copilot_status: Settings,
  get_interventions: Settings,
  
  // Report tools
  generate_report: FileText,
  get_report: FileText,
  
  // Enrollment tools
  list_enrollments: Users,
  enroll_student: Users,
  bulk_enroll: Users,
};

export function VoicePlanPreview({ plan, onConfirm, onCancel, className }: VoicePlanPreviewProps) {
  const hasWriteOps = plan.steps.some(step => step.mode === 'write');
  const needsConfirmation = plan.required_confirmations.length > 0;

  return (
    <div className={cn(
      'bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800 overflow-hidden',
      className
    )}>
      {/* Header */}
      <div className="px-4 py-3 bg-blue-100 dark:bg-blue-900/40 border-b border-blue-200 dark:border-blue-800">
        <h4 className="font-medium text-blue-900 dark:text-blue-100 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4" />
          Review Action Plan
        </h4>
        <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
          {plan.intent}
        </p>
      </div>

      {/* Steps */}
      <div className="p-4 space-y-2">
        <p className="text-xs text-blue-600 dark:text-blue-400 font-medium uppercase tracking-wide">
          Actions to perform:
        </p>
        
        <div className="space-y-2">
          {plan.steps.map((step, index) => {
            const IconComponent = toolIcons[step.tool_name] || Settings;
            const isWrite = step.mode === 'write';
            
            return (
              <div
                key={index}
                className={cn(
                  'flex items-start gap-3 p-2 rounded-lg',
                  isWrite 
                    ? 'bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800'
                    : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700'
                )}
              >
                <div className={cn(
                  'p-1.5 rounded',
                  isWrite ? 'bg-orange-100 dark:bg-orange-800' : 'bg-blue-100 dark:bg-blue-800'
                )}>
                  <IconComponent className={cn(
                    'h-4 w-4',
                    isWrite ? 'text-orange-600 dark:text-orange-300' : 'text-blue-600 dark:text-blue-300'
                  )} />
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-900 dark:text-white">
                      {formatToolName(step.tool_name)}
                    </span>
                    <span className={cn(
                      'px-1.5 py-0.5 text-xs rounded',
                      isWrite 
                        ? 'bg-orange-200 text-orange-800 dark:bg-orange-800 dark:text-orange-200'
                        : 'bg-blue-200 text-blue-800 dark:bg-blue-800 dark:text-blue-200'
                    )}>
                      {isWrite ? (
                        <span className="flex items-center gap-1">
                          <Edit className="h-3 w-3" /> write
                        </span>
                      ) : (
                        <span className="flex items-center gap-1">
                          <Eye className="h-3 w-3" /> read
                        </span>
                      )}
                    </span>
                  </div>
                  
                  {Object.keys(step.args).length > 0 && (
                    <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      {formatArgs(step.args)}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Rationale */}
        {plan.rationale && (
          <div className="mt-3 pt-3 border-t border-blue-200 dark:border-blue-800">
            <p className="text-xs text-blue-600 dark:text-blue-400 font-medium uppercase tracking-wide mb-1">
              Reasoning:
            </p>
            <p className="text-sm text-gray-700 dark:text-gray-300">
              {plan.rationale}
            </p>
          </div>
        )}

        {/* Confirmations needed */}
        {needsConfirmation && (
          <div className="mt-3 pt-3 border-t border-blue-200 dark:border-blue-800">
            <p className="text-xs text-orange-600 dark:text-orange-400 font-medium uppercase tracking-wide mb-1">
              Requires confirmation:
            </p>
            <ul className="text-sm text-orange-700 dark:text-orange-300 space-y-1">
              {plan.required_confirmations.map((conf, i) => (
                <li key={i} className="flex items-center gap-2">
                  <AlertTriangle className="h-3 w-3" />
                  {conf}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="px-4 py-3 bg-blue-100 dark:bg-blue-900/40 border-t border-blue-200 dark:border-blue-800 flex items-center justify-end gap-2">
        <button
          onClick={onCancel}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
        >
          <XCircle className="h-4 w-4" />
          Cancel
        </button>
        <button
          onClick={onConfirm}
          className={cn(
            'flex items-center gap-1.5 px-4 py-2 rounded-lg text-white transition-colors',
            hasWriteOps 
              ? 'bg-orange-500 hover:bg-orange-600'
              : 'bg-blue-500 hover:bg-blue-600'
          )}
        >
          <CheckCircle className="h-4 w-4" />
          {hasWriteOps ? 'Confirm & Execute' : 'Execute'}
        </button>
      </div>
    </div>
  );
}

// Helper to format tool names
function formatToolName(name: string): string {
  return name
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

// Helper to format args for display
function formatArgs(args: Record<string, any>): string {
  const parts: string[] = [];
  
  for (const [key, value] of Object.entries(args)) {
    if (value === undefined || value === null) continue;
    
    const displayKey = key.replace(/_/g, ' ');
    let displayValue: string;
    
    if (typeof value === 'string') {
      displayValue = value.length > 30 ? value.slice(0, 30) + '...' : value;
    } else if (Array.isArray(value)) {
      displayValue = `[${value.length} items]`;
    } else if (typeof value === 'object') {
      displayValue = '{...}';
    } else {
      displayValue = String(value);
    }
    
    parts.push(`${displayKey}: ${displayValue}`);
  }
  
  return parts.join(' • ');
}
