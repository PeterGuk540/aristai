import { useState, useEffect, useRef } from 'react'
import './App.css'
import logo from './assets/AristAI.jpg'
import { SyllabusForm } from './components/SyllabusForm'
import { ChatInterface } from './components/ChatInterface'
import type { ChatInterfaceRef } from './components/ChatInterface'
import { FileViewer } from './components/FileViewer'
import { LogDrawer } from './components/LogDrawer'
import { AnalysisProgress } from './components/AnalysisProgress'
import { UploadZone } from './components/UploadZone'
import { CommandCenter } from './components/CommandCenter'
import ExportModal from './components/ExportModal'
import PreviewModal from './components/PreviewModal'

// Mock initial data
const initialSyllabusData: any = {
  course_info: {
    title: '',
    code: '',
    instructor: '',
    semester: '',
  },
  learning_goals: [
    { id: 1, text: 'Understand the fundamental concepts of the subject.' },
  ],
  schedule: [
    { week: '1', topic: 'Introduction', assignment: 'Read Chapter 1' },
  ],
  policies: {
    academic_integrity: '',
    accessibility: '',
    attendance: '',
  },
  custom_sections: {},
}

interface FileInfo {
  id: number;
  filename: string;
  version: number;
  category: string;
  school?: string;
  department?: string;
  subject?: string;
  status?: string;
}

interface AnalysisHistoryItem {
  id: number;
  created_at: string;
  file_ids: number[];
  file_names: string[];
  combined_text: string;
  structured_data: any;
}

const HistoryItemCard = ({ item, expandedId, setExpandedId, onDelete, onLoad }: { 
  item: AnalysisHistoryItem, 
  expandedId: number | null, 
  setExpandedId: (id: number | null) => void, 
  onDelete: (id: number, e: React.MouseEvent) => void, 
  onLoad: (item: AnalysisHistoryItem) => void 
}) => (
    <div 
      className="border rounded hover:bg-gray-50 transition-colors text-[9px] sm:text-sm overflow-hidden bg-white"
    >
      <div 
        className="p-1 sm:p-3 cursor-pointer flex justify-between items-center bg-gray-50 relative group"
        onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
      >
        <div>
          <div className="font-medium text-gray-800">
            {new Date(item.created_at).toLocaleString()}
          </div>
          <div className="text-gray-500 mt-0.5 sm:mt-1 text-[8px] sm:text-xs">
            {item.file_ids.length} file(s)
          </div>
        </div>
        
        <div className="flex items-center">
          <button
              onClick={(e) => onDelete(item.id, e)}
              className="mr-1 sm:mr-2 p-0.5 sm:p-1 text-gray-400 hover:text-red-500 rounded-full hover:bg-red-50 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity"
              title="Delete history"
          >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 sm:h-4 sm:w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
          </button>
          <svg 
              className={`w-3 h-3 sm:w-4 sm:h-4 text-gray-400 transform transition-transform ${expandedId === item.id ? 'rotate-180' : ''}`} 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
          >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
      
      {expandedId === item.id && (
        <div className="p-1 sm:p-3 border-t bg-white">
          <div className="mb-1 sm:mb-3">
            <p className="text-[8px] sm:text-xs font-semibold text-gray-500 mb-0.5 sm:mb-1">Source Files:</p>
            <div className="border border-gray-200 rounded bg-white">
              {item.file_names && item.file_names.map((name, idx) => (
                <div 
                  key={idx} 
                  className={`px-2 py-1.5 text-xs text-gray-600 truncate ${idx !== 0 ? 'border-t border-gray-200' : ''}`}
                  title={name}
                >
                  {name}
                </div>
              ))}
            </div>
          </div>
          <button
            onClick={() => onLoad(item)}
            className="w-full px-3 py-1.5 bg-blue-100 text-blue-700 text-xs font-medium rounded hover:bg-blue-200 transition-colors"
          >
            Restore This Version
          </button>
        </div>
      )}
    </div>
);

function App() {
  const [step, setStep] = useState<'upload' | 'edit' | 'export'>('upload')
  const [syllabusData, setSyllabusData] = useState(initialSyllabusData)
  const [syllabusContext, setSyllabusContext] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [files, setFiles] = useState<FileInfo[]>([])
  const [selectedFiles, setSelectedFiles] = useState<number[]>([])
  const [isExportModalOpen, setIsExportModalOpen] = useState(false)
  const [isPreviewOpen, setIsPreviewOpen] = useState(false)
  const [previewFormat, setPreviewFormat] = useState('docx')
  const [selectedExportFormat, setSelectedExportFormat] = useState('docx')
  const [templateId, setTemplateId] = useState('BGSU_Standard')
  const [analysisHistory, setAnalysisHistory] = useState<AnalysisHistoryItem[]>([])
  const [expandedHistoryId, setExpandedHistoryId] = useState<number | null>(null)
  const [isHistoryExpanded, setIsHistoryExpanded] = useState(false);

  const handleDeleteAllOlderHistory = async () => {
    if (analysisHistory.length <= 1) return;
    if (!confirm(`Are you sure you want to delete all ${analysisHistory.length - 1} older history items?`)) return;

    const olderIds = analysisHistory.slice(1).map(h => h.id);
    
    try {
      // Execute deletes in parallel
      await Promise.all(olderIds.map(id => 
          fetch(`${apiUrl}/analysis_history/${id}`, { method: 'DELETE' })
      ));
      fetchAnalysisHistory();
    } catch (error) {
      console.error('Error deleting older history items:', error);
      alert('Failed to delete some history items');
    }
  };
  
  // Guidance File State
  const [guidanceFileId, setGuidanceFileId] = useState<number | null>(null)

  // New state for Split View
  const [viewMode, setViewMode] = useState<'history' | 'pdf'>('history')
  const [viewingFileId, setViewingFileId] = useState<number | null>(null)
  
  const chatRef = useRef<ChatInterfaceRef>(null);

  const apiUrl = import.meta.env.VITE_API_URL || '/api/v1'

  useEffect(() => {
    fetchFiles()
    fetchAnalysisHistory()
  }, [])

  // Sync selectedFiles with files list to remove any IDs that no longer exist
  useEffect(() => {
    if (files.length > 0) {
      setSelectedFiles(prev => {
        const validIds = new Set(files.map(f => f.id));
        const newSelection = prev.filter(id => validIds.has(id));
        // Only update if length changed to avoid unnecessary re-renders
        if (newSelection.length !== prev.length) {
          return newSelection;
        }
        return prev;
      });
    }
  }, [files]);

  const fetchFiles = async () => {
    try {
      const response = await fetch(`${apiUrl}/files/`)
      if (response.ok) {
        const data = await response.json()
        setFiles(data)
      }
    } catch (error) {
      console.error('Error fetching files:', error)
    }
  }

  const fetchAnalysisHistory = async () => {
    try {
      const response = await fetch(`${apiUrl}/analysis_history/`)
      if (response.ok) {
        const data = await response.json()
        setAnalysisHistory(data)
      }
    } catch (error) {
      console.error('Error fetching analysis history:', error)
    }
  }

  const loadAnalysis = (historyItem: AnalysisHistoryItem) => {
    if (historyItem.structured_data) {
      setSyllabusData(historyItem.structured_data)
    }
    if (historyItem.combined_text) {
      setSyllabusContext(historyItem.combined_text)
    }
    // Optionally set selected files to match history, but only if they exist in current files
    const currentIds = new Set(files.map(f => f.id));
    const validHistoryIds = historyItem.file_ids.filter(id => currentIds.has(id));
    setSelectedFiles(validHistoryIds)
  }

  const toggleFileSelection = (id: number) => {
    setSelectedFiles(prev => 
      prev.includes(id) 
        ? prev.filter(f => f !== id)
        : [...prev, id]
    )
  }

  const handleDeleteFile = async (id: number, filename: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent selecting the file when deleting
    if (!confirm(`Are you sure you want to delete ${filename}?`)) return;

    try {
      const response = await fetch(`${apiUrl}/files/${id}`, {
        method: 'DELETE',
      });
      if (response.ok) {
        fetchFiles(); // Refresh list
        // Also remove from selectedFiles if it was selected
        setSelectedFiles(prev => prev.filter(f => f !== id));
      } else {
        alert('Failed to delete file');
      }
    } catch (error) {
      console.error('Error deleting file:', error);
    }
  }

  const handleDeleteHistory = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this history item?')) return;

    try {
      const response = await fetch(`${apiUrl}/analysis_history/${id}`, {
        method: 'DELETE',
      });
      if (response.ok) {
        fetchAnalysisHistory();
      } else {
        alert('Failed to delete history item');
      }
    } catch (error) {
      console.error('Error deleting history item:', error);
    }
  }

  // Filter files for content extraction (exclude guidance)
  const contentFileIds = files
    .filter(f => selectedFiles.includes(f.id) && f.category === 'user_upload')
    .map(f => f.id);

  // Fallback: if no user_upload files selected, but other non-guidance files are, use them.
  const effectiveContentFileIds = contentFileIds.length > 0 
    ? contentFileIds 
    : files.filter(f => selectedFiles.includes(f.id) && f.category !== 'guidance').map(f => f.id);

  // Determine effective guidance ID for UI state
  const selectedGuidanceFiles = files.filter(f => selectedFiles.includes(f.id) && f.category === 'guidance');
  const effectiveGuidanceId = selectedGuidanceFiles.length > 0 ? selectedGuidanceFiles[0].id : guidanceFileId;

  const handleAnalyzeSelected = async () => {
    if (selectedFiles.length === 0) return
    
    setIsUploading(true)
    setIsAnalyzing(true)
    try {
      // Only send guidance_file_id if we don't have validation data yet
      // This prevents re-running validation on subsequent analyzes as requested
      const shouldRunValidation = !syllabusData.validation;
      
      // If we have a guidance file but no validation data, force validation run
      const finalGuidanceId = (shouldRunValidation || effectiveGuidanceId) ? effectiveGuidanceId : null;

      const response = await fetch(`${apiUrl}/analyze_batch/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
            file_ids: effectiveContentFileIds, // Use filtered IDs for content
            guidance_file_id: finalGuidanceId,
            template_id: templateId
        }),
      })

      if (response.ok) {
        const data = await response.json()
        
        if (data.combined_text) {
          setSyllabusContext(data.combined_text)
        }
        
        if (data.structured_data) {
          console.log('Received structured data:', data.structured_data);
          setSyllabusData((prev: any) => {
            try {
                const newData = data.structured_data;
                
                // Smart merge for course_info
                const mergedCourseInfo = { ...prev.course_info };
                if (newData.course_info && typeof newData.course_info === 'object') {
                    Object.keys(newData.course_info).forEach(key => {
                        // @ts-ignore
                        if (newData.course_info[key]) {
                            // @ts-ignore
                            mergedCourseInfo[key] = newData.course_info[key];
                        }
                    });
                }

                return {
                  ...prev,
                  ...newData,
                  course_info: mergedCourseInfo,
                  // Ensure arrays are arrays
                  learning_goals: Array.isArray(newData.learning_goals) ? newData.learning_goals : (prev.learning_goals || []),
                  schedule: Array.isArray(newData.schedule) ? newData.schedule : (prev.schedule || []),
                  // Ensure policies is an object
                  policies: { ...prev.policies, ...(newData.policies || {}) },
                  // Preserve validation/suggestions if not present in new data
                  suggestions: newData.suggestions || prev.suggestions,
                  validation: newData.validation || prev.validation
                };
            } catch (e) {
                console.error("Error updating syllabus data:", e);
                return prev;
            }
          })
        }
        
        console.log('Setting step to edit');
        setStep('edit')
        fetchFiles() // Refresh list to show updated status
        // Note: We do NOT fetch history here anymore, as it's only created on export
      } else {
        console.error('Analysis failed:', response.statusText);
        alert(`Analysis failed: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Error analyzing files:', error)
      alert('Error analyzing files. Please check the console for details.')
    } finally {
      setIsUploading(false)
      setIsAnalyzing(false)
    }
  }

  const handleSave = async () => {
    try {
      const response = await fetch(`${apiUrl}/analysis_history/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_ids: effectiveContentFileIds,
          combined_text: syllabusContext,
          structured_data: syllabusData
        })
      });

      if (response.ok) {
        const newHistory = await response.json();
        setAnalysisHistory(prev => [newHistory, ...prev]);
      } else {
        throw new Error('Failed to save history');
      }
    } catch (error) {
      console.error('Error saving history:', error);
      throw error;
    }
  };



  // Reusable File Upload Handler for Drag & Drop
  const handleBatchUpload = async (files: FileList | null, category: string) => {
    if (!files || files.length === 0) return;
    setIsUploading(true);
    
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
    }
    formData.append('category', category); // Use passed category

    try {
      const response = await fetch(`${apiUrl}/upload/`, {
        method: 'POST',
        body: formData,
      })
      
      if (!response.ok) {
        throw new Error('Upload failed')
      }

      const data = await response.json()
      
      if (category === 'guidance') {
        if (data && data.length > 0) {
            setGuidanceFileId(data[0].id)
        }
      }
      
      fetchFiles() // Refresh list
    } catch (error) {
      console.error('Error uploading file:', error)
      alert('Failed to upload file. Please try again.')
    } finally {
      setIsUploading(false)
    }
  }

  const handleGenerateDraft = async (draftInfo: { title: string; audience: string; duration: string; referenceFileId?: number }) => {
    setIsAnalyzing(true);
    try {
        const response = await fetch(`${apiUrl}/generate/draft`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                course_title: draftInfo.title,
                target_audience: draftInfo.audience,
                duration: draftInfo.duration,
                reference_file_id: draftInfo.referenceFileId
            }),
        });

        if (!response.ok) {
            throw new Error('Failed to generate draft');
        }

        const data = await response.json();
        setSyllabusData(data);
        setStep('edit');
    } catch (error) {
        console.error('Error generating draft:', error);
        alert('Failed to generate draft. Please try again.');
    } finally {
        setIsAnalyzing(false);
    }
  };

  const handleExport = async (format: string) => {
    setIsExporting(true);
    // Try to get file handle immediately to preserve user gesture
    let fileHandle: any = null;
    const useFileSystemAccess = 'showSaveFilePicker' in window;

    if (useFileSystemAccess) {
      try {
        const mimeType = format === 'pdf' ? 'application/pdf' : 
                         format === 'json' ? 'application/json' : 
                         format === 'md' ? 'text/markdown' : 
                         'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
        
        // @ts-ignore
        fileHandle = await window.showSaveFilePicker({
          suggestedName: `syllabus.${format}`,
          types: [{
            description: `${format.toUpperCase()} File`,
            accept: { [mimeType]: [`.${format}`] },
          }],
        });
      } catch (err: any) {
        if (err.name === 'AbortError') {
          setIsExporting(false);
          return; // User cancelled the dialog
        }
        console.warn('File System Access API failed, falling back to default download:', err);
      }
    }

    try {
      const response = await fetch(`${apiUrl}/export/${format}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(syllabusData),
      })

      if (!response.ok) {
        throw new Error('Export failed')
      }

      const blob = await response.blob()

      // Save to history
      try {
        await fetch(`${apiUrl}/analysis_history/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            file_ids: selectedFiles,
            combined_text: syllabusContext,
            structured_data: syllabusData
          }),
        });
        fetchAnalysisHistory(); // Refresh history list
      } catch (historyError) {
        console.error('Error saving history:', historyError);
      }

      if (fileHandle) {
        // Write to the handle we got earlier
        // @ts-ignore
        const writable = await fileHandle.createWritable();
        await writable.write(blob);
        await writable.close();
      } else {
        // Fallback to standard download
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `syllabus.${format}`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
        
        // Notify user if they might have missed the download
        if (!useFileSystemAccess) {
             // Optional: could use a toast here, but alert is safer for now
             // setTimeout(() => alert('File downloaded to your default Downloads folder.'), 100);
        }
      }
      
      setIsExportModalOpen(false)
    } catch (error) {
      console.error('Error exporting file:', error)
      alert('Failed to export file. Please try again.')
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <div className="h-[100dvh] w-screen bg-gray-100 flex flex-col overflow-hidden">
      {/* Header */}
      <header className="bg-white shadow-sm sticky top-0 z-50 flex-shrink-0 h-8 sm:h-16">
        <div className="max-w-7xl mx-auto px-2 sm:px-6 lg:px-8 flex flex-row justify-between items-center h-full gap-1">
          <div className="flex items-center flex-shrink-0">
            <img src={logo} alt="AristAI Logo" className="h-5 sm:h-10 w-auto mr-1 sm:mr-2" />
            <h1 className="text-xs sm:text-2xl font-bold text-gray-900 truncate">Syllabus Tool</h1>
          </div>
          <div className="flex items-center space-x-1 sm:space-x-4 flex-shrink-0">
            <button 
              onClick={() => setStep('upload')}
              className={`px-1 sm:px-0 text-[9px] sm:text-sm font-medium hover:text-blue-800 transition-colors whitespace-nowrap ${step === 'upload' ? 'font-bold text-blue-600' : 'text-gray-500'}`}
            >
              1. Upload
            </button>
            <span className="text-gray-300 text-[9px] sm:text-sm px-0.5">→</span>
            <button 
              onClick={() => setStep('edit')}
              className={`px-1 sm:px-0 text-[9px] sm:text-sm font-medium hover:text-blue-800 transition-colors whitespace-nowrap ${step === 'edit' ? 'font-bold text-blue-600' : 'text-gray-500'}`}
            >
              2. Edit
            </button>
            <span className="text-gray-300 text-[9px] sm:text-sm px-0.5">→</span>
            <button 
              onClick={() => setStep('export')}
              className={`px-1 sm:px-0 text-[9px] sm:text-sm font-medium hover:text-blue-800 transition-colors whitespace-nowrap ${step === 'export' ? 'font-bold text-blue-600' : 'text-gray-500'}`}
            >
              3. Export
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-1 sm:px-6 lg:px-8 py-1 sm:py-6 overflow-hidden flex flex-col relative">
        {step === 'upload' && (
          <div className="flex flex-row gap-4 h-full min-h-0">
            {/* Sidebar (Left 25%) - File List & History */}
            <div className="w-[30%] sm:w-1/4 flex flex-col gap-4 h-full border-r border-gray-200 pr-4">
                 <div className="flex flex-col h-full bg-white rounded-lg shadow-sm overflow-hidden">
                    <div className="px-4 py-3 border-b border-gray-100 bg-gray-50 flex justify-between items-center">
                        <h3 className="font-semibold text-gray-700">Explorer</h3>
                        <span className="text-xs text-gray-400">{files.length} items</span>
                    </div>
                    
                    {/* File List */}
                    <div className="flex-1 overflow-y-auto p-2 space-y-4">
                        {files.length === 0 && (
                            <div className="text-center py-8 text-gray-400 text-xs">
                                No files uploaded yet.
                            </div>
                        )}
                        {['user_upload', 'template', 'guidance', 'example'].map(cat => {
                        const catFiles = files.filter(f => (f.category || 'user_upload').toLowerCase() === cat);
                        if (catFiles.length === 0) return null;
                        
                        const catLabel = cat === 'user_upload' ? 'Draft Content' : 
                                       cat === 'template' ? 'Templates' : 
                                       cat === 'guidance' ? 'Policy / Requirements' : 
                                       'Examples';

                        return (
                            <div key={cat} className="space-y-1">
                                <h4 className="text-[10px] uppercase font-bold text-gray-400 tracking-wider px-2">{catLabel}</h4>
                                <div className="space-y-1">
                                  {catFiles.map((file) => (
                                    <div 
                                      key={file.id} 
                                      className={`flex items-center justify-between p-2 rounded-md text-sm cursor-pointer group ${
                                        selectedFiles.includes(file.id) 
                                          ? 'bg-blue-50 text-blue-700' 
                                          : 'hover:bg-gray-50 text-gray-600'
                                      }`}
                                      onClick={() => toggleFileSelection(file.id)}
                                    >
                                      <div className="flex items-center flex-1 min-w-0">
                                          <div className={`w-1.5 h-1.5 rounded-full mr-2 ${selectedFiles.includes(file.id) ? 'bg-blue-500' : 'bg-gray-300'}`} />
                                          <span className="truncate" title={file.filename}>{file.filename}</span>
                                      </div>
                                      <button
                                        onClick={(e) => handleDeleteFile(file.id, file.filename, e)}
                                        className="hidden group-hover:block ml-2 text-gray-400 hover:text-red-500"
                                      >
                                          ×
                                      </button>
                                    </div>
                                  ))}
                                </div>
                            </div>
                         )
                       })}
                    </div>

                    {/* Quick History Access */}
                     {analysisHistory.length > 0 && (
                        <div className="border-t border-gray-100 p-2 bg-gray-50">
                             <div className="text-[10px] uppercase font-bold text-gray-400 tracking-wider mb-2 px-2">Recent History</div>
                             <button
                                onClick={() => {
                                    if (analysisHistory.length > 0) {
                                        loadAnalysis(analysisHistory[0]);
                                        setStep('edit');
                                    }
                                }}
                                className="w-full text-left px-3 py-2 text-xs font-medium text-blue-600 hover:bg-blue-50 rounded flex items-center justify-between transition-colors"
                            >
                                <span>Restore Last Session</span>
                                <span className="opacity-50">↩</span>
                            </button>
                        </div>
                     )}
                 </div>
            </div>

            {/* Main Workspace (Right 75%) - Upload Zones & Preview */}
            <div className="flex-1 flex flex-col h-full overflow-hidden relative">
                {isAnalyzing ? (
                   <AnalysisProgress isAnalyzing={isAnalyzing} />
                ) : (
                   <CommandCenter 
                        onGenerate={handleGenerateDraft} 
                        isGenerating={isAnalyzing}
                        files={files}
                   >
                    
                    {/* Drop Zones Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 auto-rows-fr mb-8">
                        <UploadZone
                            category="user_upload"
                            title="Course Content"
                            description="Existing syllabus or rough draft materials."
                            uploadedCount={files.filter(f => f.category === 'user_upload').length}
                            onUpload={handleBatchUpload}
                            icon={
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.414.586l5.414 5.414a1 1 0 01.586.414V19a2 2 0 01-2 2z" />
                                </svg>
                            }
                        />
                        <UploadZone
                            category="guidance"
                            title="Policy Requirements"
                            description="Institutional requirements or standards."
                            uploadedCount={files.filter(f => f.category === 'guidance').length}
                            onUpload={handleBatchUpload}
                            className="bg-amber-50/50 border-amber-100"
                            icon={
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                                </svg>
                            }
                        />
                        <UploadZone
                            category="template"
                            title="Formatting Template"
                            description="Desired layout or style guide (DOCX)."
                            uploadedCount={files.filter(f => f.category === 'template').length}
                            onUpload={handleBatchUpload}
                             className="bg-purple-50/50 border-purple-100"
                            icon={
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
                                </svg>
                            }
                        />
                         <UploadZone
                            category="example"
                            title="Reference Material"
                            description="Past syllabi for reference."
                            uploadedCount={files.filter(f => f.category === 'example').length}
                             className="bg-emerald-50/50 border-emerald-100"
                            onUpload={handleBatchUpload}
                            icon={
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 14v3m4-3v3m4-3v3M3 21h18M3 10h18M3 7l9-4 9 4M4 10h16v11H4V10z" />
                                </svg>
                            }
                        />
                    </div>

                    {/* Template Selection */}
                    <div className="flex justify-center mb-6">
                        <label className="mr-3 text-sm font-medium text-gray-700 self-center">Analysis Template:</label>
                        <select 
                            value={templateId} 
                            onChange={(e) => setTemplateId(e.target.value)}
                            className="block w-64 pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-black focus:border-black sm:text-sm rounded-md bg-white border"
                        >
                            <option value="BGSU_Standard">Bowling Green State</option>
                            <option value="Exponential">Exponential Methodology (LATAM)</option>
                        </select>
                    </div>
                    
                    {/* Primary CTA */}
                    <div className="flex justify-center pb-8">
                         <button
                            onClick={handleAnalyzeSelected}
                            disabled={selectedFiles.length === 0 || isUploading}
                            className={`
                                group relative w-full sm:w-auto px-10 py-3.5 rounded-lg shadow-sm border transform transition-all duration-200 
                                ${selectedFiles.length > 0 ? 'bg-black text-white border-transparent hover:bg-gray-800 hover:shadow-md' : 'bg-gray-50 text-gray-400 border-gray-200 cursor-not-allowed'}
                            `}
                        >
                            <span className="flex flex-col items-center">
                                <span className="text-sm font-semibold tracking-wide">Generate Syllabus Draft</span>
                                {selectedFiles.length > 0 && (
                                    <span className="text-[10px] font-medium mt-0.5 opacity-80">{selectedFiles.length} files selected</span>
                                )}
                            </span>
                            
                            {isUploading && (
                                <div className="absolute inset-0 bg-white/10 rounded-lg flex items-center justify-center backdrop-blur-[1px]">
                                     <svg className="animate-spin h-5 w-5 text-white" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                </div>
                            )}
                        </button>
                    </div>

                   </CommandCenter>
                )}
            </div>
            
            <LogDrawer apiUrl={apiUrl} />
          </div>
        )}

        {step === 'edit' && (
          <div className="flex flex-col gap-0.5 sm:gap-6 h-full">
            {/* Top Section: History/PDF (35%) and Form (65%) */}
            <div className="flex flex-row gap-0.5 sm:gap-6 h-[70%] sm:h-[60%] min-h-0">
              {/* Left: History Sidebar or PDF Viewer */}
              <div className="w-[35%] sm:w-[40%] h-full bg-white rounded-lg shadow overflow-hidden flex flex-col">
                {/* Toggle Header */}
                <div className="flex border-b">
                  <button
                    onClick={() => setViewMode('history')}
                    className={`flex-1 py-1 sm:py-2 text-[9px] sm:text-sm font-medium ${viewMode === 'history' ? 'bg-gray-100 text-blue-600 border-b-2 border-blue-600' : 'text-gray-500 hover:bg-gray-50'}`}
                  >
                    History
                  </button>
                  <button
                    onClick={() => setViewMode('pdf')}
                    disabled={!viewingFileId}
                    className={`flex-1 py-1 sm:py-2 text-[9px] sm:text-sm font-medium ${viewMode === 'pdf' ? 'bg-gray-100 text-blue-600 border-b-2 border-blue-600' : 'text-gray-500 hover:bg-gray-50 disabled:opacity-50'}`}
                  >
                    File
                  </button>
                </div>

                {viewMode === 'pdf' && viewingFileId ? (
                  <FileViewer 
                      fileId={viewingFileId} 
                      filename={files.find(f => f.id === viewingFileId)?.filename || 'document'} 
                      apiUrl={apiUrl} 
                  />
                ) : (
                  <div className="flex-1 overflow-y-auto p-1 sm:p-4">
                    <h3 className="font-bold text-gray-700 mb-1 sm:mb-4 text-[10px] sm:text-base hidden sm:block">Analysis History</h3>
                    <div className="space-y-1 sm:space-y-3">
                      {/* Show current files list to allow PDF selection */}
                      {selectedFiles.length > 0 && (
                        <div className="mb-1 sm:mb-6">
                          <h4 className="text-[8px] sm:text-xs font-semibold text-gray-500 uppercase tracking-wider mb-0.5 sm:mb-2">Files</h4>
                          <div className="space-y-0.5 sm:space-y-2">
                            {files.filter(f => selectedFiles.includes(f.id)).map(file => (
                              <div key={file.id} className="flex items-center justify-between p-1 sm:p-2 bg-blue-50 rounded border border-blue-100">
                                <span className="text-[9px] sm:text-xs truncate flex-1 mr-1" title={file.filename}>{file.filename}</span>
                                <button
                                  onClick={() => {
                                    setViewingFileId(file.id);
                                    setViewMode('pdf');
                                  }}
                                  className="text-[8px] sm:text-xs bg-white border border-blue-200 text-blue-600 px-1 py-0.5 rounded hover:bg-blue-100"
                                >
                                  View
                                </button>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {analysisHistory.length > 0 && (
                        <>
                          {/* Latest Item */}
                          <HistoryItemCard 
                            item={analysisHistory[0]}
                            expandedId={expandedHistoryId}
                            setExpandedId={setExpandedHistoryId}
                            onDelete={handleDeleteHistory}
                            onLoad={loadAnalysis}
                          />

                          {/* Older Items */}
                          {analysisHistory.length > 1 && (
                            <div className="mt-1 sm:mt-4 border-t pt-1 sm:pt-4">
                              <div className="flex justify-between items-center mb-1 sm:mb-2">
                                <button 
                                  onClick={() => setIsHistoryExpanded(!isHistoryExpanded)}
                                  className="text-[9px] sm:text-xs font-medium text-gray-500 flex items-center hover:text-gray-700"
                                >
                                  <svg 
                                    className={`w-3 h-3 mr-1 transform transition-transform ${isHistoryExpanded ? 'rotate-90' : ''}`} 
                                    fill="none" 
                                    stroke="currentColor" 
                                    viewBox="0 0 24 24"
                                  >
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                  </svg>
                                  {isHistoryExpanded ? 'Hide' : 'Show'} Older
                                </button>
                                
                                <button
                                  onClick={handleDeleteAllOlderHistory}
                                  className="text-[9px] sm:text-xs text-red-500 hover:text-red-700 flex items-center"
                                  title="Delete all older history items"
                                >
                                  <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 mr-1" viewBox="0 0 20 20" fill="currentColor">
                                    <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                                  </svg>
                                  Clear
                                </button>
                              </div>

                              {isHistoryExpanded && (
                                <div className="space-y-1 sm:space-y-3 pl-1 sm:pl-2 border-l-2 border-gray-100">
                                  {analysisHistory.slice(1).map(item => (
                                    <HistoryItemCard 
                                      key={item.id}
                                      item={item}
                                      expandedId={expandedHistoryId}
                                      setExpandedId={setExpandedHistoryId}
                                      onDelete={handleDeleteHistory}
                                      onLoad={loadAnalysis}
                                    />
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </>
                      )}
                      {analysisHistory.length === 0 && (
                        <p className="text-gray-400 text-[9px] sm:text-sm text-center py-1 sm:py-4">No history</p>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Right: Form */}
              <div className="w-[65%] sm:w-[60%] h-full overflow-hidden">
                  <SyllabusForm 
                    data={syllabusData} 
                    onUpdate={setSyllabusData} 
                    onAIRequest={(prompt) => {
                        if (chatRef.current) {
                            chatRef.current.setInput(prompt);
                            chatRef.current.sendMessage(prompt);
                        }
                    }}
                    onAnalyze={selectedFiles.length > 0 ? handleAnalyzeSelected : undefined}
                    isAnalyzing={isUploading}
                    hasGuidance={!!effectiveGuidanceId}
                    fileIds={effectiveContentFileIds}
                    onSave={handleSave}
                    onNextStep={() => setStep('export')}
                  />
              </div>
            </div>
            
            {/* Bottom Section: Chat */}
            <div className="w-full h-[30%] sm:h-[40%] min-h-0 overflow-hidden">
                <ChatInterface 
                  ref={chatRef}
                  context={`Raw Text Context:\n${syllabusContext}\n\nCurrent Structured Data:\n${JSON.stringify(syllabusData, null, 2)}`}
                  onApplyChanges={(changes) => {
                    setSyllabusData((prev: any) => {
                      const newData = { ...prev };
                      if (changes.course_info) {
                        newData.course_info = { ...newData.course_info, ...changes.course_info };
                      }
                      if (changes.learning_goals) {
                        newData.learning_goals = changes.learning_goals;
                      }
                      if (changes.schedule) {
                        newData.schedule = changes.schedule;
                      }
                      if (changes.policies) {
                        newData.policies = { ...newData.policies, ...changes.policies };
                      }
                      return newData;
                    });
                  }}
                />
            </div>
          </div>
        )}

        {step === 'export' && (
          <div className="max-w-3xl mx-auto mt-8">
            <div className="bg-white rounded-lg shadow-lg overflow-hidden">
              <div className="px-6 py-8 border-b border-gray-200 bg-gray-50">
                <h2 className="text-2xl font-bold text-gray-900">Export Your Syllabus</h2>
                <p className="mt-2 text-gray-600">Select a format to download your finalized syllabus.</p>
              </div>
              
              <div className="p-8">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {[
                    { id: 'docx', label: 'Word Document', ext: '.docx', desc: 'Best for further editing' },
                    { id: 'pdf', label: 'PDF Document', ext: '.pdf', desc: 'Best for distribution' },
                    { id: 'json', label: 'JSON Data', ext: '.json', desc: 'Structured data format' },
                    { id: 'md', label: 'Markdown', ext: '.md', desc: 'Plain text with formatting' },
                  ].map((format) => (
                    <div 
                      key={format.id}
                      onClick={() => setSelectedExportFormat(format.id)}
                      className={`relative rounded-lg border-2 p-6 cursor-pointer transition-all hover:shadow-md ${
                        selectedExportFormat === format.id 
                          ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500' 
                          : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="text-lg font-medium text-gray-900">{format.label}</h3>
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                          {format.ext}
                        </span>
                      </div>
                      <p className="text-sm text-gray-500">{format.desc}</p>
                      
                      {selectedExportFormat === format.id && (
                        <div className="absolute top-4 right-4 text-blue-600">
                          <svg className="h-6 w-6" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                          </svg>
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                <div className="mt-10 flex justify-center space-x-6">
                  <button
                    onClick={() => {
                      setPreviewFormat(selectedExportFormat);
                      setIsPreviewOpen(true);
                    }}
                    className="px-8 py-3 border border-blue-600 text-blue-600 font-medium rounded-lg hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors text-lg"
                  >
                    Preview
                  </button>
                  <button
                    onClick={() => handleExport(selectedExportFormat)}
                    disabled={isExporting}
                    className={`px-8 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 shadow-lg transition-colors text-lg flex items-center ${isExporting ? 'opacity-75 cursor-not-allowed' : ''}`}
                  >
                    {isExporting ? (
                        <>
                            <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            Exporting...
                        </>
                    ) : (
                        <>
                            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                            </svg>
                            Download / Export
                        </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer Actions (Only in Edit mode) - REMOVED as per request
      {step === 'edit' && (
        <div className="bg-white border-t p-4">
          <div className="max-w-7xl mx-auto flex justify-end space-x-4">
            <button 
              onClick={() => setStep('upload')}
              className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button 
              onClick={() => setIsExportModalOpen(true)}
              className="px-4 py-2 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700"
            >
              Export
            </button>
          </div>
        </div>
      )}
      */}

      <ExportModal
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        onExport={handleExport}
        onPreview={(format) => {
          setPreviewFormat(format)
          setIsPreviewOpen(true)
        }}
      />

      <PreviewModal
        isOpen={isPreviewOpen}
        onClose={() => setIsPreviewOpen(false)}
        data={syllabusData}
        format={previewFormat}
      />
      
      <div className="fixed bottom-2 right-2 text-xs text-gray-400 pointer-events-none">
        v1.6 (Output Tab Added)
      </div>
    </div>
  )
}

export default App


