import React from 'react';
import SyllabusPreview from './SyllabusPreview';

interface PreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  data: any;
  format?: string;
}

const PreviewModal: React.FC<PreviewModalProps> = ({ isOpen, onClose, data, format = 'docx' }) => {
  if (!isOpen) return null;

  return (
    <div 
        className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 backdrop-blur-sm p-4"
        onClick={onClose}
    >
      <div 
        className="bg-white rounded-xl w-full h-full md:w-3/4 md:h-3/4 overflow-hidden relative shadow-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="bg-gray-50 px-6 py-4 border-b border-gray-100 flex justify-between items-center flex-shrink-0">
            <h3 className="text-lg font-semibold text-gray-700">
                Preview: {format === 'docx' ? 'Word Document' : format === 'pdf' ? 'PDF Document' : format.toUpperCase()}
            </h3>
            <button 
                onClick={onClose}
                className="text-gray-400 hover:text-gray-600 transition-colors p-1 rounded-full hover:bg-gray-200"
            >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
            </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 bg-gray-100">
            <SyllabusPreview data={data} format={format} />
        </div>
      </div>
    </div>
  );
};

export default PreviewModal;
