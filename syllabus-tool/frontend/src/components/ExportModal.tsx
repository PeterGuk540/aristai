import React, { useState } from 'react';

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onExport: (format: string) => void;
  onPreview?: (format: string) => void;
}

const ExportModal: React.FC<ExportModalProps> = ({ isOpen, onClose, onExport, onPreview }) => {
  const [selectedFormat, setSelectedFormat] = useState<string>('docx');

  if (!isOpen) return null;

  const formats = [
    { id: 'docx', label: 'Word Document', ext: '.docx' },
    { id: 'pdf', label: 'PDF Document', ext: '.pdf' },
    { id: 'json', label: 'JSON Data', ext: '.json' },
    { id: 'md', label: 'Markdown', ext: '.md' },
  ];

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 backdrop-blur-sm flex items-center justify-center z-50 transition-opacity p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-[480px] transform transition-all overflow-hidden">
        {/* Header */}
        <div className="bg-gray-50 px-6 py-4 border-b border-gray-100 flex justify-between items-center">
          <h2 className="text-xl font-semibold text-gray-800">Export Syllabus</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        
        {/* Body */}
        <div className="p-6">
          <label className="block text-sm font-medium text-gray-700 mb-3">Select Format</label>
          <div className="grid grid-cols-1 gap-3">
            {formats.map((format) => (
              <label 
                key={format.id}
                className={`flex items-center p-3 border rounded-lg cursor-pointer transition-all ${
                  selectedFormat === format.id 
                    ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500' 
                    : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'
                }`}
              >
                <input
                  type="radio"
                  value={format.id}
                  checked={selectedFormat === format.id}
                  onChange={(e) => setSelectedFormat(e.target.value)}
                  className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                />
                <span className="ml-3 flex-1 font-medium text-gray-700">{format.label}</span>
                <span className="text-xs text-gray-400 font-mono bg-gray-100 px-2 py-1 rounded">{format.ext}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="bg-gray-50 px-6 py-4 border-t border-gray-100">
          <div className="flex space-x-3">
            <button
              onClick={onClose}
              className="flex-1 px-4 py-2.5 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 transition-colors"
            >
              Cancel
            </button>
            {onPreview && (
              <button
                onClick={() => onPreview(selectedFormat)}
                className="flex-1 px-4 py-2.5 border border-blue-600 text-blue-600 font-medium rounded-lg hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
              >
                Preview
              </button>
            )}
            <button
              onClick={() => onExport(selectedFormat)}
              className="flex-1 px-4 py-2.5 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 shadow-sm transition-colors"
            >
              Export
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ExportModal;
