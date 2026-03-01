import React, { useState } from 'react';

interface FileInfo {
    id: number;
    filename: string;
}

interface CommandCenterProps {
    onGenerate: (data: { title: string; audience: string; duration: string; referenceFileId?: number }) => void;
    isGenerating: boolean;
    children?: React.ReactNode;
    files?: FileInfo[];
}

export function CommandCenter({ onGenerate, isGenerating, children, files = [] }: CommandCenterProps) {
  const [title, setTitle] = useState('');
  const [audience, setAudience] = useState('');
  const [duration, setDuration] = useState('16 weeks');
  const [selectedFileId, setSelectedFileId] = useState<string>('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (title && audience && duration) {
        onGenerate({ 
            title, 
            audience, 
            duration,
            referenceFileId: selectedFileId ? parseInt(selectedFileId) : undefined
        });
    }
  };

  return (
    <div className="h-full bg-white rounded-lg shadow-sm border border-gray-100 overflow-y-auto flex flex-col p-8">
      
      {/* AI Draft Generator Section */}
      <div className="max-w-xl mx-auto w-full mb-8">
        <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center p-2 bg-black rounded-lg shadow-lg mb-4">
                 <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
            </div>
            <h2 className="text-2xl font-bold text-gray-900">AI Draft Generator</h2>
            <p className="text-sm text-gray-500 mt-1">Start from scratch? Just tell us what you're teaching.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 bg-gray-50 p-6 rounded-xl border border-gray-200">
            <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1 uppercase tracking-wide">Course Title</label>
                <input 
                    type="text" 
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g. Python for Data Analysis" 
                    className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-black focus:border-black outline-none transition-all"
                    required
                />
            </div>
            
            {files && files.length > 0 && (
                <div>
                   <label className="block text-xs font-semibold text-gray-700 mb-1 uppercase tracking-wide">
                        Reference Document (Optional)
                   </label>
                   <select
                        value={selectedFileId}
                        onChange={(e) => setSelectedFileId(e.target.value)}
                        className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-black focus:border-black outline-none transition-all bg-white"
                   >
                       <option value="">Select a file to guide the draft...</option>
                       {files.map(f => (
                           <option key={f.id} value={f.id}>{f.filename}</option>
                       ))}
                   </select>
                   <p className="text-[10px] text-gray-400 mt-1">The AI will use this file to better understand your course content.</p>
                </div>
            )}

            <div className="grid grid-cols-2 gap-4">
                <div>
                    <label className="block text-xs font-semibold text-gray-700 mb-1 uppercase tracking-wide">Target Audience</label>
                    <input 
                        type="text" 
                        value={audience}
                        onChange={(e) => setAudience(e.target.value)}
                        placeholder="e.g. Sophomore Business" 
                        className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-black focus:border-black outline-none transition-all"
                        required
                    />
                </div>
                <div>
                     <label className="block text-xs font-semibold text-gray-700 mb-1 uppercase tracking-wide">Duration</label>
                     <select
                        value={duration}
                        onChange={(e) => setDuration(e.target.value)}
                        className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-black focus:border-black outline-none transition-all bg-white"
                     >
                        <option value="16 weeks">16 Weeks (Semester)</option>
                        <option value="12 weeks">12 Weeks</option>
                        <option value="8 weeks">8 Weeks (Half-term)</option>
                        <option value="4 weeks">4 Weeks (Intensive)</option>
                     </select>
                </div>
            </div>

            <button 
                type="submit" 
                disabled={isGenerating}
                className="w-full py-3 px-4 bg-black hover:bg-gray-800 text-white font-medium rounded-lg shadow-sm hover:shadow-md transition-all flex items-center justify-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
                {isGenerating ? (
                     <>
                        <svg className="animate-spin h-4 w-4 text-white" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <span>Generating Draft...</span>
                    </>
                ) : (
                    <>
                        <span>Generate Syllabus Draft</span>
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
                        </svg>
                    </>
                )}
            </button>
        </form>
      </div>

      {(children) && (
        <>
            <div className="w-full border-t border-gray-100 my-8 relative">
                <span className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-white px-2 text-xs text-gray-400 font-medium">OR UPLOAD FILES</span>
            </div>
            
            <div className="flex-1">
                {children}
            </div>
        </>
      )}
    </div>
  );
}
