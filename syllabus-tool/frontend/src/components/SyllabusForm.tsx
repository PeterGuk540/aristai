import React, { useState, useRef, useEffect } from 'react';
import { FloatingMenu } from './FloatingMenu';
import SyllabusPreview from './SyllabusPreview';
import { fetchWithAuth } from '../lib/fetchWithAuth.ts';

// Helper component for auto-resizing textarea
const AutoResizeTextarea = ({ value, onChange, className, style, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [value]);

  return (
    <textarea
      ref={textareaRef}
      value={value}
      onChange={onChange}
      className={className}
      style={style}
      {...props}
    />
  );
};

// Refresh Button Component
const RefreshButton = ({ onClick, isLoading, title }: { onClick: (e: any) => void, isLoading: boolean, title?: string }) => (
    <button
        onClick={onClick}
        disabled={isLoading}
        className={`p-1 rounded-full hover:bg-gray-100 transition-colors ${isLoading ? 'cursor-not-allowed opacity-50' : 'text-gray-400 hover:text-blue-600'}`}
        title={title || "Regenerate with AI"}
    >
        <svg 
            xmlns="http://www.w3.org/2000/svg" 
            className={`h-4 w-4 ${isLoading ? 'animate-spin text-blue-600' : ''}`} 
            fill="none" 
            viewBox="0 0 24 24" 
            stroke="currentColor"
        >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
    </button>
);

// Helper component for truncated editable cell
const TruncatedEditableCell = ({ value, onChange, onRegenerate, isRegenerating }: { value: string, onChange: (e: any) => void, onRegenerate?: () => void, isRegenerating?: boolean }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  const handleMouseMove = (e: React.MouseEvent) => {
    setMousePos({ x: e.clientX, y: e.clientY });
  };

  if (isEditing) {
    return (
      <AutoResizeTextarea
        value={value}
        onChange={onChange}
        className={`block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-1 px-2 resize-none overflow-hidden ${isRegenerating ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : ''}`}
        style={{ minHeight: '38px' }}
        autoFocus
        onBlur={() => setIsEditing(false)}
        disabled={isRegenerating}
      />
    );
  }

  return (
    <div className="relative group/cell">
      <div
        className={`line-clamp-3 cursor-text min-h-[38px] py-1 px-2 text-sm text-gray-900 rounded border border-transparent pr-6 ${isRegenerating ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : 'hover:bg-gray-50 hover:border-gray-200'}`}
        onClick={() => !isRegenerating && setIsEditing(true)}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        onMouseMove={handleMouseMove}
      >
        {value || <span className="text-gray-400 italic">Empty</span>}
      </div>
      {onRegenerate && (
        <div className="absolute right-1 top-1 opacity-0 group-hover/cell:opacity-100 transition-opacity">
            <RefreshButton onClick={(e) => { e.stopPropagation(); onRegenerate(); }} isLoading={!!isRegenerating} />
        </div>
      )}
      {showTooltip && value && (
        <div 
            className="fixed z-50 bg-gray-800 text-white text-xs rounded p-2 max-w-sm shadow-lg pointer-events-none whitespace-pre-wrap"
            style={{ top: mousePos.y + 10, left: mousePos.x + 10 }}
        >
            {value}
        </div>
      )}
    </div>
  );
};

interface SyllabusData {
  course_info: {
    title: string;
    code: string;
    instructor: string;
    semester: string;
    description?: string;
    prerequisites?: string;
    office_hours?: string;
    email?: string;
    format?: string;
    materials?: string;
  };
  learning_goals: { id: number; text: string }[];
  schedule: { week: string; date?: string; topic: string; assignment: string }[];
  policies: {
    academic_integrity: string;
    accessibility: string;
    attendance: string;
    grading?: string;
    late_work?: string;
    communication?: string;
    technology?: string;
    learning_resources?: string;
  };
  startDate?: string;
  suggestions?: {
    functional: string[];
    ui_ux: string[];
  };
  validation?: {
    conforms_to_guidance: boolean;
    issues: (string | ValidationIssue)[];
  };
  custom_sections?: Record<string, any>;
}

interface ValidationIssue {
    type: string;
    section: string;
    field: string;
    issue: string;
    current: string;
    suggestion: string;
    category?: string;
    status?: string;
}

interface SyllabusFormProps {
  data: SyllabusData;
  onUpdate: (data: SyllabusData) => void;
  onAIRequest?: (prompt: string) => void;
  onAnalyze?: () => void;
  isAnalyzing?: boolean;
  hasGuidance?: boolean;
  fileIds?: number[];
  onSave?: () => Promise<void>;
  onNextStep?: () => void;
}

// const ALL_TABS = ['info', 'goals', 'schedule', 'policies', 'custom', 'preview', 'review'] as const;

export const SyllabusForm: React.FC<SyllabusFormProps> = ({ data, onUpdate: parentOnUpdate, onAIRequest, onAnalyze, isAnalyzing, hasGuidance, fileIds, onSave, onNextStep }) => {
  const [activeTab, setActiveTab] = useState<string>('info');
  const [dateInputType, setDateInputType] = useState('text');
  const [regeneratingFields, setRegeneratingFields] = useState<Set<string>>(new Set());
  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Dynamic Tabs Calculation
  const visibleTabs = React.useMemo(() => {
    const tabs: string[] = ['info']; // Always present

    // Standard sections generally available, but could be conditional if data is explicit
    tabs.push('goals');
    tabs.push('schedule');
    tabs.push('policies');

    // Custom sections only if they exist
    if (data.custom_sections && Object.keys(data.custom_sections).length > 0) {
      tabs.push('custom');
    }

    // Always present
    tabs.push('preview');

    // Review only if validation data exists
    if (data.validation) {
      tabs.push('review');
    }

    return tabs;
  }, [data]);

  // Ensure active tab is valid
  useEffect(() => {
     if (!visibleTabs.includes(activeTab)) {
         setActiveTab('info');
     }
  }, [visibleTabs, activeTab]);

  const onUpdate = (newData: SyllabusData) => {
    parentOnUpdate(newData);
    setIsDirty(true);
  };

  const handleTabChange = async (tab: string) => {
    if (tab === activeTab) return;

    if (isDirty) {
      if (onSave) {
        try {
          setIsSaving(true);
          await onSave();
          setIsDirty(false);
          setActiveTab(tab);
        } catch (error) {
          console.error("Auto-save failed", error);
          alert("Failed to save changes. Please try again.");
        } finally {
          setIsSaving(false);
        }
      } else {
        alert("Please save your changes before moving to the next step.");
      }
    } else {
      setActiveTab(tab);
    }
  };

  const handleManualSave = async () => {
    if (onSave) {
      try {
        setIsSaving(true);
        await onSave();
        setIsDirty(false);
      } catch (error) {
        console.error("Save failed", error);
        alert("Failed to save changes.");
      } finally {
        setIsSaving(false);
      }
    }
  };

  const regenerateField = async (section: string, field: string, itemContext?: any, instruction?: string) => {
    if (!fileIds || fileIds.length === 0) {
        throw new Error("No files selected");
    }
    
    const apiUrl = import.meta.env.VITE_API_URL || '/api/v1';
    const response = await fetchWithAuth(`${apiUrl}/regenerate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            file_ids: fileIds,
            section,
            field,
            item_context: itemContext,
            instruction
        })
    });
    
    if (!response.ok) {
        throw new Error(response.statusText);
    }
    
    const result = await response.json();
    return result.value;
  };

  const applyRegeneratedValue = (currentData: SyllabusData, section: string, field: string, value: any, itemContext?: any) => {
      let newData = { ...currentData };
      if (section === 'course_info') {
        newData.course_info = { ...newData.course_info, [field]: value };
      } else if (section === 'policies') {
        newData.policies = { ...newData.policies, [field]: value };
      } else if (section === 'schedule') {
        if (typeof itemContext?.index === 'number') {
             const newSchedule = [...newData.schedule];
             if (newSchedule[itemContext.index]) {
                newSchedule[itemContext.index] = { ...newSchedule[itemContext.index], [field]: value };
                newData.schedule = newSchedule;
             }
        }
      } else if (section === 'learning_goals') {
        if (typeof itemContext?.index === 'number') {
            const newGoals = [...newData.learning_goals];
            if (newGoals[itemContext.index]) {
                newGoals[itemContext.index] = { ...newGoals[itemContext.index], text: value };
                newData.learning_goals = newGoals;
            }
        } else {
            // Handle bulk update (e.g. from "Fix All" or missing field)
            // Assume value is a string, possibly newline separated
            const lines = (value as string).split('\n').map(l => l.trim()).filter(l => l);
            if (lines.length > 0) {
                newData.learning_goals = lines.map((text, i) => ({ 
                    id: Date.now() + i, 
                    text: text.replace(/^[\d\.\-\*]+\s*/, '') // Remove leading bullets/numbers
                }));
            }
        }
      }
      return newData;
  };

  const handleRegenerate = async (section: string, field: string, itemContext?: any, stateKey?: string, instruction?: string) => {
    if (!fileIds || fileIds.length === 0) {
        alert("No files selected for context. Please select files in the Upload tab.");
        return;
    }
    
    const key = stateKey || `${section}.${field}`;
    setRegeneratingFields(prev => new Set(prev).add(key));
    
    try {
        const value = await regenerateField(section, field, itemContext, instruction);
        if (value) {
            const newData = applyRegeneratedValue(data, section, field, value, itemContext);
            onUpdate(newData);
        }
    } catch (e) {
        console.error("Regeneration failed", e);
    } finally {
        setRegeneratingFields(prev => {
            const next = new Set(prev);
            next.delete(key);
            return next;
        });
    }
  };

  const handleFixIssue = async (issue: ValidationIssue, index: number) => {
    const fixKey = `fix_issue_${index}`;
    setRegeneratingFields(prev => new Set(prev).add(fixKey));
    
    try {
        let section = issue.section;
        let field = issue.field;
        let itemContext = undefined;
        
        // Parse field for lists
        if (section === 'schedule' || section === 'learning_goals') {
            const parts = field.split('.');
            if (parts.length >= 3) {
                const idx = parseInt(parts[1]);
                field = parts[2];
                if (!isNaN(idx)) {
                    itemContext = { index: idx };
                    if (section === 'schedule' && data.schedule[idx]) {
                        itemContext = { ...itemContext, week: data.schedule[idx].week, date: data.schedule[idx].date };
                    } else if (section === 'learning_goals' && data.learning_goals[idx]) {
                        itemContext = { ...itemContext, id: data.learning_goals[idx].id };
                    }
                }
            }
        }
        
        const value = await regenerateField(section, field, itemContext, issue.suggestion);
        
        let newData = applyRegeneratedValue(data, section, field, value, itemContext);
        
        // Remove the issue from the list
        const newIssues = [...(newData.validation?.issues || [])];
        newIssues.splice(index, 1);
        newData.validation = { ...newData.validation!, issues: newIssues };
        
        onUpdate(newData);
        
    } catch (e) {
        console.error("Fix failed", e);
        alert("Failed to apply fix.");
    } finally {
        setRegeneratingFields(prev => {
            const next = new Set(prev);
            next.delete(fixKey);
            return next;
        });
    }
  };

  const handleFixAll = async () => {
    if (!data.validation?.issues) return;
    
    const fixableIssues = data.validation.issues
        .map((issue, index) => ({ issue, index }))
        .filter(item => typeof item.issue !== 'string' && item.issue.status !== 'passed' && item.issue.type !== 'passed') as { issue: ValidationIssue, index: number }[];
        
    if (fixableIssues.length === 0) return;
    
    if (!confirm(`Are you sure you want to attempt to fix ${fixableIssues.length} issues automatically? This may take a moment.`)) return;

    setIsSaving(true); 
    
    let currentData = { ...data };
    let remainingIssues = [...(currentData.validation?.issues || [])];

    try {
        for (const { issue } of fixableIssues) {
            let section = issue.section;
            let field = issue.field;
            let itemContext = undefined;
            
            if (section === 'schedule' || section === 'learning_goals') {
                const parts = field.split('.');
                if (parts.length >= 3) {
                    const idx = parseInt(parts[1]);
                    field = parts[2];
                    if (!isNaN(idx)) {
                        itemContext = { index: idx };
                        if (section === 'schedule' && currentData.schedule[idx]) {
                            itemContext = { ...itemContext, week: currentData.schedule[idx].week, date: currentData.schedule[idx].date };
                        } else if (section === 'learning_goals' && currentData.learning_goals[idx]) {
                            itemContext = { ...itemContext, id: currentData.learning_goals[idx].id };
                        }
                    }
                }
            }

            try {
                const newValue = await regenerateField(section, field, itemContext, issue.suggestion);
                currentData = applyRegeneratedValue(currentData, section, field, newValue, itemContext);
                
                remainingIssues = remainingIssues.filter(i => i !== issue);
                currentData.validation = { ...currentData.validation!, issues: remainingIssues };
                
                onUpdate(currentData);
                
            } catch (e) {
                console.error(`Failed to fix issue for ${section}.${field}`, e);
            }
        }
    } finally {
        setIsSaving(false);
    }
  };

  const handleInfoChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    onUpdate({
      ...data,
      course_info: { ...data.course_info, [e.target.name]: e.target.value },
    });
  };

  const handleStartDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onUpdate({ ...data, startDate: e.target.value });
  };

  const calculateDate = (weekNum: string | number) => {
    if (!data.startDate) return '';
    const num = typeof weekNum === 'number' ? weekNum : parseInt(weekNum);
    if (isNaN(num)) return '';

    const start = new Date(data.startDate);
    const date = new Date(start);
    date.setDate(start.getDate() + (num - 1) * 7);
    return date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  };

  const formatDateForDisplay = (isoDate: string) => {
    if (!isoDate) return '';
    const [y, m, d] = isoDate.split('-');
    return `${m}/${d}/${y}`;
  };

  const handlePolicyChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onUpdate({
      ...data,
      policies: { ...data.policies, [e.target.name]: e.target.value },
    });
  };

  const updateGoal = (index: number, text: string) => {
    const newGoals = [...data.learning_goals];
    newGoals[index].text = text;
    onUpdate({ ...data, learning_goals: newGoals });
  };

  const addGoal = () => {
    onUpdate({
      ...data,
      learning_goals: [...data.learning_goals, { id: Date.now(), text: '' }],
    });
  };

  const removeGoal = (index: number) => {
    const newGoals = data.learning_goals.filter((_, i) => i !== index);
    onUpdate({ ...data, learning_goals: newGoals });
  };

  // Calculate spans for Week and Date columns
  const scheduleSpans = React.useMemo(() => {
    const weekSpans = new Array(data.schedule.length).fill(0);
    const dateSpans = new Array(data.schedule.length).fill(0);

    if (data.schedule.length === 0) return { week: [], date: [] };

    let currentWeekStart = 0;
    for (let i = 1; i <= data.schedule.length; i++) {
      const prevWeek = data.schedule[i - 1]?.week;
      const currWeek = data.schedule[i]?.week;

      if (i === data.schedule.length || currWeek !== prevWeek) {
        weekSpans[currentWeekStart] = i - currentWeekStart;
        currentWeekStart = i;
      }
    }

    let currentDateStart = 0;
    for (let i = 1; i <= data.schedule.length; i++) {
      const prevDate = data.schedule[i - 1]?.date || calculateDate(data.schedule[i - 1]?.week);
      const currDate = data.schedule[i]?.date || calculateDate(data.schedule[i]?.week);

      if (i === data.schedule.length || currDate !== prevDate) {
        dateSpans[currentDateStart] = i - currentDateStart;
        currentDateStart = i;
      }
    }

    return { week: weekSpans, date: dateSpans };
  }, [data.schedule, data.startDate]);

  const updateSchedule = (index: number, field: string, value: string | number) => {
    const newSchedule = [...data.schedule];
    
    // Handle bulk update for merged cells
    if (field === 'week' && scheduleSpans.week[index] > 1) {
        const span = scheduleSpans.week[index];
        for (let i = 0; i < span; i++) {
            // @ts-ignore
            newSchedule[index + i][field] = value;
        }
    } else if (field === 'date' && scheduleSpans.date[index] > 1) {
        const span = scheduleSpans.date[index];
        for (let i = 0; i < span; i++) {
            // @ts-ignore
            newSchedule[index + i][field] = value;
        }
    } else {
        // @ts-ignore
        newSchedule[index][field] = value;
    }

    onUpdate({ ...data, schedule: newSchedule });
  };

  const addScheduleItem = () => {
    onUpdate({
      ...data,
      schedule: [
        ...data.schedule,
        { week: (data.schedule.length + 1).toString(), date: '', topic: '', assignment: '' },
      ],
    });
  };

  const removeScheduleItem = (index: number) => {
    const newSchedule = data.schedule.filter((_, i) => i !== index);
    onUpdate({ ...data, schedule: newSchedule });
  };

  const handlePolicyFileUpload = async (event: React.ChangeEvent<HTMLInputElement>, field: keyof SyllabusData['policies']) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const apiUrl = import.meta.env.VITE_API_URL || '/api/v1';
      const response = await fetchWithAuth(`${apiUrl}/upload/`, {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const responseData = await response.json();
        if (responseData.extracted_text) {
           onUpdate({
            ...data,
            policies: { ...data.policies, [field]: responseData.extracted_text },
          });
        }
      } else {
        alert('Failed to upload file');
      }
    } catch (error) {
      console.error('Error uploading file:', error);
      alert('Error uploading file');
    }
  };

  const currentTabIndex = visibleTabs.indexOf(activeTab);
  const nextTab = currentTabIndex < visibleTabs.length - 1 ? visibleTabs[currentTabIndex + 1] : null;

  const handleNextClick = async () => {
    if (nextTab) {
      await handleTabChange(nextTab);
    } else if (onNextStep) {
       if (isDirty && onSave) {
        try {
          setIsSaving(true);
          await onSave();
          setIsDirty(false);
          onNextStep();
        } catch (error) {
          console.error("Auto-save failed", error);
          alert("Failed to save changes. Please try again.");
        } finally {
          setIsSaving(false);
        }
      } else {
        onNextStep();
      }
    }
  };

  return (
    <div ref={containerRef} className="bg-white shadow rounded-lg p-2 sm:p-6 h-full flex flex-col relative overflow-hidden">
      {isAnalyzing && (
        <div className="absolute inset-0 bg-white/90 z-50 flex flex-col items-center justify-center rounded-lg backdrop-blur-sm">
          <div className="flex items-center space-x-3 text-blue-600 mb-4">
            <svg className="animate-spin h-8 w-8" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span className="text-lg font-medium">Analyzing...</span>
          </div>
        </div>
      )}
      {onAIRequest && <FloatingMenu onAction={onAIRequest} containerRef={containerRef as React.RefObject<HTMLElement>} />}
      <div className="flex flex-row justify-between items-center border-b mb-1 sm:mb-4 gap-1 flex-shrink-0">
        <div className="flex space-x-1 sm:space-x-4 overflow-x-auto w-full pb-1 no-scrollbar">
          {visibleTabs.map((tab) => (
            <button
              key={tab}
              onClick={() => handleTabChange(tab)}
              className={`pb-1 sm:pb-2 px-1 sm:px-4 capitalize whitespace-nowrap text-[10px] sm:text-base ${
                activeTab === tab
                  ? 'border-b-2 border-blue-500 text-blue-600 font-medium'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1 sm:gap-2 flex-shrink-0">
            {onAnalyze && (
            <button
                onClick={onAnalyze}
                disabled={isAnalyzing}
                className={`text-[10px] sm:text-sm font-medium flex items-center gap-1 px-1 sm:px-3 py-0.5 sm:py-1 rounded transition-colors ${
                    isAnalyzing 
                    ? 'text-gray-400 cursor-not-allowed' 
                    : 'text-blue-600 hover:text-blue-800 hover:bg-blue-50'
                }`}
                title="Re-analyze"
            >
                {isAnalyzing ? (
                    <>
                        <svg className="animate-spin h-3 w-3 sm:h-4 sm:w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <span className="hidden sm:inline">Analyzing...</span>
                    </>
                ) : (
                    <>
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 sm:h-4 sm:w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        <span className="hidden sm:inline">Analyze</span>
                    </>
                )}
            </button>
        )}
      </div>
    </div>

      <div className="flex-1 overflow-y-auto min-h-0">
        {activeTab === 'info' && (
          <div className="space-y-2 sm:space-y-4">
            <h3 className="text-xs sm:text-lg font-medium hidden sm:block">Course Information</h3>
            <div className="grid grid-cols-2 gap-2 sm:gap-4">
              {['title', 'code', 'instructor', 'semester', 'email', 'office_hours', 'format'].map((field) => {
                const isRegenerating = regeneratingFields.has(`course_info.${field}`);
                return (
                <div key={field} className="relative">
                  <label className="block text-[10px] sm:text-sm font-medium text-gray-700 capitalize truncate">{field.replace('_', ' ')}</label>
                  <div className="flex gap-1 sm:gap-2 items-center">
                    <input
                      type="text"
                      name={field}
                      // @ts-ignore
                      value={data.course_info[field] || ''}
                      // @ts-ignore
                      title={data.course_info[field] || ''}
                      onChange={handleInfoChange}
                      disabled={isRegenerating}
                      className={`mt-0.5 sm:mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-[10px] sm:text-sm border p-1 sm:p-2 min-w-0 h-6 sm:h-auto ${isRegenerating ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : ''}`}
                    />
                    <div className="flex-shrink-0 transform scale-75 sm:scale-100 origin-left">
                        <RefreshButton 
                            onClick={() => handleRegenerate('course_info', field)} 
                            isLoading={isRegenerating} 
                        />
                    </div>
                  </div>
                </div>
              )})}
            </div>
            
            {/* Long Text Fields */}
            {['description', 'prerequisites', 'materials'].map((field) => {
                const isRegenerating = regeneratingFields.has(`course_info.${field}`);
                return (
                <div key={field} className="relative">
                  <label className="block text-[10px] sm:text-sm font-medium text-gray-700 capitalize truncate">{field.replace('_', ' ')}</label>
                  <div className="flex gap-1 sm:gap-2 items-start">
                    <AutoResizeTextarea
                      name={field}
                      // @ts-ignore
                      value={data.course_info[field] || ''}
                      onChange={handleInfoChange}
                      disabled={isRegenerating}
                      className={`mt-0.5 sm:mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-[10px] sm:text-sm border p-1 sm:p-2 min-h-[40px] ${isRegenerating ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : ''}`}
                    />
                    <div className="mt-1 transform scale-75 sm:scale-100 origin-top-left">
                        <RefreshButton 
                            onClick={() => handleRegenerate('course_info', field)} 
                            isLoading={isRegenerating} 
                        />
                    </div>
                  </div>
                </div>
              )})}
          </div>
        )}

        {activeTab === 'goals' && (
          <div className="space-y-2 sm:space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-xs sm:text-lg font-medium hidden sm:block">Learning Goals</h3>
              <button onClick={addGoal} className="text-[10px] sm:text-sm text-blue-600 hover:text-blue-800">+ Add Goal</button>
            </div>
            {data.learning_goals.map((goal, index) => {
              const isRegenerating = regeneratingFields.has(`learning_goals.${index}`);
              return (
              <div key={goal.id} className="flex gap-1 sm:gap-2 items-start">
                <span className="pt-1 sm:pt-2 text-[10px] sm:text-base text-gray-500">{index + 1}.</span>
                <textarea
                  value={goal.text}
                  onChange={(e) => updateGoal(index, e.target.value)}
                  disabled={isRegenerating}
                  className={`flex-1 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-[10px] sm:text-sm border p-1 sm:p-2 min-h-[30px] ${isRegenerating ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : ''}`}
                  rows={2}
                />
                <div className="pt-1 sm:pt-2 flex flex-col gap-1">
                    <div className="transform scale-75 sm:scale-100 origin-top-right">
                        <RefreshButton 
                            onClick={() => handleRegenerate('learning_goals', 'text', { index, id: goal.id }, `learning_goals.${index}`)} 
                            isLoading={isRegenerating} 
                        />
                    </div>
                    <button onClick={() => removeGoal(index)} className="text-red-500 hover:text-red-700 text-xs sm:text-base">
                    ×
                    </button>
                </div>
              </div>
            )})}
          </div>
        )}

        {activeTab === 'schedule' && (
          <div className="flex flex-col h-full">
            <div className="flex justify-between items-center mb-2 sm:mb-4">
              <h3 className="text-xs sm:text-lg font-medium text-gray-900 hidden sm:block">Course Schedule</h3>
              <div className="flex items-center gap-1 sm:gap-3 bg-gray-50 p-1 sm:p-2 rounded-lg border border-gray-200 w-full sm:w-auto justify-between sm:justify-start">
                <div className="flex items-center gap-1 sm:gap-2 flex-1 sm:flex-none">
                  <label className="text-[10px] sm:text-sm font-medium text-gray-700 whitespace-nowrap">Start:</label>
                  <input
                    type={dateInputType}
                    placeholder="mm/dd/yyyy"
                    onFocus={() => setDateInputType('date')}
                    onBlur={(e) => {
                      if (!e.target.value) setDateInputType('text');
                      else setDateInputType('text'); // Force text display on blur even if value exists
                    }}
                    value={dateInputType === 'date' ? (data.startDate || '') : formatDateForDisplay(data.startDate || '')}
                    onChange={handleStartDateChange}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-[10px] sm:text-sm py-0.5 sm:py-1 px-1 sm:px-2 min-w-0"
                  />
                </div>
                <div className="h-3 sm:h-4 w-px bg-gray-300 mx-1"></div>
                <button 
                  onClick={addScheduleItem} 
                  className="inline-flex items-center px-2 sm:px-3 py-0.5 sm:py-1 border border-transparent text-[10px] sm:text-sm font-medium rounded-md text-blue-700 bg-blue-100 hover:bg-blue-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 whitespace-nowrap"
                >
                  + Week
                </button>
              </div>
            </div>
            
            <div className="flex-1 overflow-hidden border rounded-lg shadow-sm bg-white flex flex-col">
              <div className="overflow-x-auto flex-1">
                <table className="min-w-full divide-y divide-gray-200 relative">
                  <thead className="bg-gray-50 sticky top-0 z-10">
                    <tr>
                      <th scope="col" className="px-1 sm:px-4 py-1 sm:py-3 text-left text-[10px] sm:text-xs font-semibold text-gray-600 uppercase tracking-wider w-10 sm:w-20 whitespace-nowrap">
                        Wk
                      </th>
                      <th scope="col" className="px-1 sm:px-4 py-1 sm:py-3 text-left text-[10px] sm:text-xs font-semibold text-gray-600 uppercase tracking-wider w-16 sm:w-32 whitespace-nowrap">
                        Date
                      </th>
                      <th scope="col" className="px-1 sm:px-4 py-1 sm:py-3 text-left text-[10px] sm:text-xs font-semibold text-gray-600 uppercase tracking-wider whitespace-nowrap">
                        Topic
                      </th>
                      <th scope="col" className="px-1 sm:px-4 py-1 sm:py-3 text-left text-[10px] sm:text-xs font-semibold text-gray-600 uppercase tracking-wider whitespace-nowrap">
                        Assign
                      </th>
                      <th scope="col" className="relative px-1 sm:px-4 py-1 sm:py-3 w-6 sm:w-10">
                        <span className="sr-only">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white">
                    {data.schedule.map((item, index) => {
                      const weekSpan = scheduleSpans.week[index];
                      const dateSpan = scheduleSpans.date[index];
                      const isNewWeek = weekSpan > 0;
                      
                      return (
                      <tr key={index} className={`hover:bg-gray-50 transition-colors ${isNewWeek && index !== 0 ? 'border-t-2 border-gray-200' : 'border-t border-gray-100'}`}>
                        {weekSpan > 0 && (
                            <td rowSpan={weekSpan} className="px-1 sm:px-4 py-1 sm:py-2 whitespace-nowrap align-top bg-white border-r border-gray-100">
                              <input
                                type="text"
                                value={item.week}
                                onChange={(e) => updateSchedule(index, 'week', e.target.value)}
                                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-[10px] sm:text-sm py-0.5 sm:py-1 px-1 text-center"
                              />
                            </td>
                        )}
                        {dateSpan > 0 && (
                            <td rowSpan={dateSpan} className="px-1 sm:px-4 py-1 sm:py-2 whitespace-nowrap text-[10px] sm:text-sm text-gray-500 align-top bg-white border-r border-gray-100">
                              <TruncatedEditableCell
                                value={item.date || calculateDate(item.week)}
                                onChange={(e) => updateSchedule(index, 'date', e.target.value)}
                              />
                            </td>
                        )}
                        <td className="px-1 sm:px-4 py-1 sm:py-2 align-top">
                          <TruncatedEditableCell
                            value={item.topic}
                            onChange={(e) => updateSchedule(index, 'topic', e.target.value)}
                            onRegenerate={() => handleRegenerate('schedule', 'topic', { index, week: item.week, date: item.date }, `schedule.${index}.topic`)}
                            isRegenerating={regeneratingFields.has(`schedule.${index}.topic`)}
                          />
                        </td>
                        <td className="px-1 sm:px-4 py-1 sm:py-2 align-top">
                          <TruncatedEditableCell
                            value={item.assignment}
                            onChange={(e) => updateSchedule(index, 'assignment', e.target.value)}
                            onRegenerate={() => handleRegenerate('schedule', 'assignment', { index, week: item.week, date: item.date }, `schedule.${index}.assignment`)}
                            isRegenerating={regeneratingFields.has(`schedule.${index}.assignment`)}
                          />
                        </td>
                        <td className="px-1 sm:px-4 py-1 sm:py-2 whitespace-nowrap text-right text-[10px] sm:text-sm font-medium align-middle">
                          <button 
                            onClick={() => removeScheduleItem(index)} 
                            className="text-gray-400 hover:text-red-600 transition-colors p-0.5 sm:p-1 rounded-full hover:bg-red-50"
                            title="Remove item"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 sm:h-5 sm:w-5" viewBox="0 0 20 20" fill="currentColor">
                              <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                            </svg>
                          </button>
                        </td>
                      </tr>
                    );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'policies' && (
          <div className="space-y-2 sm:space-y-6">
            <h3 className="text-xs sm:text-lg font-medium hidden sm:block">Policies</h3>
            
            <div>
              <div className="flex justify-between items-center mb-0.5 sm:mb-1">
                <label className="block text-[10px] sm:text-sm font-medium text-gray-700">Academic Integrity</label>
                <div className="transform scale-75 sm:scale-100 origin-right">
                    <RefreshButton 
                        onClick={() => handleRegenerate('policies', 'academic_integrity')} 
                        isLoading={regeneratingFields.has('policies.academic_integrity')} 
                    />
                </div>
              </div>
              <textarea
                name="academic_integrity"
                value={data.policies.academic_integrity}
                onChange={handlePolicyChange}
                disabled={regeneratingFields.has('policies.academic_integrity')}
                rows={4}
                className={`block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-[10px] sm:text-sm border p-1 sm:p-2 ${regeneratingFields.has('policies.academic_integrity') ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : ''}`}
              />
            </div>

            <div>
              <div className="flex justify-between items-center mb-0.5 sm:mb-1">
                <label className="block text-[10px] sm:text-sm font-medium text-gray-700">
                  Accessibility Statement 
                  <span className="ml-1 sm:ml-2 inline-flex items-center px-1 sm:px-2 py-0.5 rounded text-[8px] sm:text-xs font-medium bg-green-100 text-green-800">
                    Required
                  </span>
                </label>
                <div className="flex items-center gap-1 sm:gap-2">
                    <div className="transform scale-75 sm:scale-100 origin-right">
                        <RefreshButton 
                            onClick={() => handleRegenerate('policies', 'accessibility')} 
                            isLoading={regeneratingFields.has('policies.accessibility')} 
                        />
                    </div>
                    <label className="cursor-pointer text-[10px] sm:text-sm text-blue-600 hover:text-blue-800 flex items-center gap-0.5 sm:gap-1">
                    <svg className="w-3 h-3 sm:w-4 sm:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                    </svg>
                    <span className="hidden sm:inline">Import from file</span>
                    <span className="sm:hidden">Import</span>
                    <input 
                        type="file" 
                        className="hidden" 
                        accept=".docx,.pdf,.txt,.md" 
                        onChange={(e) => handlePolicyFileUpload(e, 'accessibility')}
                    />
                    </label>
                </div>
              </div>
              <textarea
                name="accessibility"
                value={data.policies.accessibility}
                onChange={handlePolicyChange}
                disabled={regeneratingFields.has('policies.accessibility')}
                rows={4}
                className={`block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-[10px] sm:text-sm border p-1 sm:p-2 ${regeneratingFields.has('policies.accessibility') ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : ''}`}
                placeholder="Paste the official university accessibility statement here or import from a file..."
              />
            </div>

            <div>
              <div className="flex justify-between items-center mb-0.5 sm:mb-1">
                <label className="block text-[10px] sm:text-sm font-medium text-gray-700">Attendance Policy</label>
                <div className="transform scale-75 sm:scale-100 origin-right">
                    <RefreshButton 
                        onClick={() => handleRegenerate('policies', 'attendance')} 
                        isLoading={regeneratingFields.has('policies.attendance')} 
                    />
                </div>
              </div>
              <textarea
                name="attendance"
                value={data.policies.attendance}
                onChange={handlePolicyChange}
                disabled={regeneratingFields.has('policies.attendance')}
                rows={4}
                className={`block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-[10px] sm:text-sm border p-1 sm:p-2 ${regeneratingFields.has('policies.attendance') ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : ''}`}
              />
            </div>

            <div>
              <div className="flex justify-between items-center mb-0.5 sm:mb-1">
                <label className="block text-[10px] sm:text-sm font-medium text-gray-700">Grading Policy</label>
                <div className="transform scale-75 sm:scale-100 origin-right">
                    <RefreshButton 
                        onClick={() => handleRegenerate('policies', 'grading')} 
                        isLoading={regeneratingFields.has('policies.grading')} 
                    />
                </div>
              </div>
              <textarea
                name="grading"
                value={data.policies.grading || ''}
                onChange={handlePolicyChange}
                disabled={regeneratingFields.has('policies.grading')}
                rows={4}
                className={`block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-[10px] sm:text-sm border p-1 sm:p-2 ${regeneratingFields.has('policies.grading') ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : ''}`}
                placeholder="Enter grading policy..."
              />
            </div>

            {['late_work', 'communication', 'technology', 'learning_resources'].map((field) => (
                <div key={field}>
                  <div className="flex justify-between items-center mb-0.5 sm:mb-1">
                    <label className="block text-[10px] sm:text-sm font-medium text-gray-700 capitalize">{field.replace('_', ' ')} Policy</label>
                    <div className="transform scale-75 sm:scale-100 origin-right">
                        <RefreshButton 
                            onClick={() => handleRegenerate('policies', field)} 
                            isLoading={regeneratingFields.has(`policies.${field}`)} 
                        />
                    </div>
                  </div>
                  <textarea
                    name={field}
                    // @ts-ignore
                    value={data.policies[field] || ''}
                    onChange={handlePolicyChange}
                    disabled={regeneratingFields.has(`policies.${field}`)}
                    rows={4}
                    className={`block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-[10px] sm:text-sm border p-1 sm:p-2 ${regeneratingFields.has(`policies.${field}`) ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : ''}`}
                  />
                </div>
            ))}
          </div>
        )}

        {activeTab === 'custom' && (
            <div className="space-y-4 p-4">
                <h3 className="text-lg font-medium">Custom Sections</h3>
                <p className="text-sm text-gray-500 mb-4">University-specific fields (e.g., Sumilla, Competencies).</p>
                {data.custom_sections && Object.keys(data.custom_sections).length > 0 ? (
                    Object.entries(data.custom_sections).map(([key, value]) => (
                        <div key={key} className="mb-4">
                            <label className="block text-sm font-medium text-gray-700 capitalize mb-1">
                                {key.replace(/_/g, ' ')}
                            </label>
                            <AutoResizeTextarea
                                value={typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
                                onChange={(e) => onUpdate({
                                    ...data,
                                    custom_sections: {
                                        ...(data.custom_sections || {}),
                                        [key]: e.target.value
                                    }
                                })}
                                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm border p-2 min-h-[100px]"
                            />
                        </div>
                    ))
                ) : (
                     <div className="text-gray-500 italic bg-gray-50 p-4 rounded border">No custom sections found.</div>
                )}
            </div>
        )}

        {activeTab === 'preview' && (
          <div className="h-full flex flex-col">
            <h3 className="text-xs sm:text-lg font-medium mb-2 sm:mb-4 hidden sm:block">Preview</h3>
            <div className="flex-1 border rounded-lg overflow-y-auto bg-gray-100">
                <SyllabusPreview data={data} format="docx" />
            </div>
          </div>
        )}

        {activeTab === 'review' && (
          <div className="space-y-2 sm:space-y-6">
            <div className="flex justify-between items-center">
                <h3 className="text-xs sm:text-lg font-medium hidden sm:block">Review & Suggestions</h3>
                {onAnalyze && (
                    <div className="transform scale-75 sm:scale-100 origin-right">
                        <RefreshButton 
                            onClick={(e) => { e.stopPropagation(); onAnalyze(); }} 
                            isLoading={!!isAnalyzing} 
                            title="Re-analyze to update review"
                        />
                    </div>
                )}
            </div>
            
            {data.validation && (
                <div className={`p-2 sm:p-4 rounded-md border ${data.validation.conforms_to_guidance ? 'bg-green-50 border-green-200' : 'bg-yellow-50 border-yellow-200'}`}>
                    <div className="flex justify-between items-center mb-1 sm:mb-2">
                        <h4 className={`text-[10px] sm:text-base font-medium ${data.validation.conforms_to_guidance ? 'text-green-800' : 'text-yellow-800'}`}>
                            Guidance Check: {data.validation.conforms_to_guidance ? 'Passed' : 'Attention Needed'}
                        </h4>
                        {data.validation.issues.some(i => typeof i !== 'string' && i.status !== 'passed' && i.type !== 'passed') && (
                            <button
                                onClick={handleFixAll}
                                className="text-[10px] sm:text-xs bg-white border border-gray-300 px-1 sm:px-2 py-0.5 sm:py-1 rounded hover:bg-gray-50 text-gray-700"
                                title="Attempt to fix all issues"
                            >
                                Fix All Issues
                            </button>
                        )}
                    </div>
                    
                    {data.validation.issues.length > 0 && (
                        <div className="mt-1 sm:mt-2 space-y-1 sm:space-y-3">
                            {data.validation.issues.map((issue, i) => {
                                if (typeof issue === 'string') {
                                    return <div key={i} className="text-[10px] sm:text-sm text-gray-700 pl-2 border-l-2 border-gray-300">{issue}</div>;
                                }
                                
                                if (issue.status === 'passed' || issue.type === 'passed') {
                                     return (
                                        <div key={i} className="bg-white border border-green-200 rounded-lg p-2 sm:p-3 shadow-sm flex justify-between items-center">
                                            <div>
                                                <div className="flex items-center gap-1 sm:gap-2 mb-0.5 sm:mb-1">
                                                    <span className="px-1 sm:px-2 py-0.5 text-[8px] sm:text-[10px] font-bold uppercase tracking-wider rounded bg-green-100 text-green-800">
                                                        PASSED
                                                    </span>
                                                    <span className="text-[10px] sm:text-xs text-gray-400">
                                                        {issue.section} • {issue.field}
                                                    </span>
                                                </div>
                                                <h5 className="text-[10px] sm:text-sm font-medium text-gray-900">{issue.issue}</h5>
                                            </div>
                                            <svg className="w-4 h-4 sm:w-5 sm:h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                            </svg>
                                        </div>
                                     );
                                }

                                const isFixing = regeneratingFields.has(`fix_issue_${i}`);
                                
                                return (
                                    <div key={i} className="bg-white border rounded-lg p-2 sm:p-3 shadow-sm">
                                        <div className="flex justify-between items-start mb-1 sm:mb-2">
                                            <div className="flex items-center gap-1 sm:gap-2">
                                                <span className={`px-1 sm:px-2 py-0.5 text-[8px] sm:text-[10px] font-bold uppercase tracking-wider rounded ${
                                                    issue.type === 'missing' ? 'bg-red-100 text-red-800' :
                                                    issue.type === 'incorrect' ? 'bg-yellow-100 text-yellow-800' :
                                                    'bg-blue-100 text-blue-800'
                                                }`}>
                                                    {issue.type}
                                                </span>
                                                <span className="text-[10px] sm:text-xs text-gray-400">
                                                    {issue.section} • {issue.field}
                                                </span>
                                            </div>
                                        </div>
                                        
                                        <h5 className="text-[10px] sm:text-sm font-medium text-gray-900 mb-1 sm:mb-2">{issue.issue}</h5>
                                        
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-1 sm:gap-3 mb-1 sm:mb-3">
                                            <div className="bg-red-50 p-1 sm:p-2 rounded border border-red-100">
                                                <div className="text-[8px] sm:text-[10px] font-bold text-red-700 uppercase mb-0.5 sm:mb-1">Current</div>
                                                <div className="text-[10px] sm:text-xs text-gray-600 italic break-words">{issue.current || "Missing"}</div>
                                            </div>
                                            <div className="bg-green-50 p-1 sm:p-2 rounded border border-green-100">
                                                <div className="text-[8px] sm:text-[10px] font-bold text-green-700 uppercase mb-0.5 sm:mb-1">Suggestion</div>
                                                <div className="text-[10px] sm:text-xs text-gray-600 break-words">{issue.suggestion}</div>
                                            </div>
                                        </div>
                                        
                                        <div className="flex justify-end">
                                            <button
                                                onClick={() => handleFixIssue(issue, i)}
                                                disabled={isFixing}
                                                className="inline-flex items-center px-2 sm:px-3 py-1 sm:py-1.5 border border-transparent text-[10px] sm:text-xs font-medium rounded text-white bg-blue-600 hover:bg-blue-700 focus:outline-none disabled:opacity-50 transition-colors"
                                            >
                                                {isFixing ? 'Fixing...' : 'Apply Fix'}
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            )}


            
            {!data.validation && (
                <p className="text-gray-500 italic text-[10px] sm:text-base">
                    {hasGuidance 
                        ? "Review data pending. Click Analyze to generate." 
                        : "No review data available. Try analyzing with a guidance file."}
                </p>
            )}
          </div>
        )}
      </div>

      <div className="border-t p-1 sm:p-4 flex flex-row justify-end bg-gray-50 rounded-b-lg gap-1 sm:gap-3">
        <button
            type="button"
            onClick={handleManualSave}
            disabled={isSaving || !isDirty}
            className={`inline-flex items-center justify-center px-2 sm:px-4 py-1 sm:py-2 border shadow-sm text-[10px] sm:text-sm font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 transition-colors ${
                isDirty 
                ? 'border-transparent text-white bg-green-600 hover:bg-green-700' 
                : 'border-gray-300 text-gray-500 bg-gray-100 cursor-not-allowed'
            }`}
        >
            {isSaving ? 'Saving...' : (isDirty ? 'Save' : 'Saved')}
        </button>
        <button
            onClick={handleNextClick}
            disabled={isSaving}
            className="inline-flex items-center justify-center px-2 sm:px-4 py-1 sm:py-2 border border-transparent text-[10px] sm:text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
        >
            {isSaving ? 'Saving...' : (nextTab ? `Next: ${nextTab.charAt(0).toUpperCase() + nextTab.slice(1)}` : 'Proceed to Export')}
            <svg className="ml-1 sm:ml-2 -mr-1 h-3 w-3 sm:h-4 sm:w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
        </button>
      </div>
    </div>
  );
};
