import React, { useCallback, useState } from 'react';

interface UploadZoneProps {
  category: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  onUpload: (files: FileList, category: string) => void;
  accept?: string;
  className?: string;
  uploadedCount?: number;
}

export function UploadZone({ category, title, description, icon, onUpload, accept, className, uploadedCount = 0 }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        onUpload(e.dataTransfer.files, category);
      }
    },
    [onUpload, category]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        onUpload(e.target.files, category);
      }
    },
    [onUpload, category]
  );

  const borderColor = isDragging ? 'border-gray-400 bg-gray-50' : 'border-gray-200 bg-white hover:border-gray-300';
  const ringColor = uploadedCount > 0 ? 'ring-1 ring-gray-200 ring-offset-0' : '';

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`relative rounded-lg border border-dashed p-6 transition-all duration-200 cursor-pointer flex flex-col items-center justify-center text-center h-56 ${borderColor} ${ringColor} ${className || ''}`}
    >
      <input
        type="file"
        multiple
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        onChange={handleFileInput}
        accept={accept}
      />
      
      <div className={`p-3 rounded-full mb-3 transition-colors ${uploadedCount > 0 ? 'bg-gray-100 text-gray-700' : 'bg-gray-50 text-gray-400'}`}>
        {uploadedCount > 0 ? (
           <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
             <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 13l4 4L19 7" />
           </svg>
        ) : (
          icon
        )}
      </div>

      <h3 className="text-sm font-medium text-gray-900 mb-0.5">{title}</h3>
      <p className="text-xs text-gray-500 mb-4 px-2 leading-relaxed">{description}</p>
      
      <span className="inline-flex items-center px-2.5 py-1 rounded text-[10px] font-medium bg-gray-50 text-gray-500 border border-gray-100">
        {uploadedCount > 0 ? `${uploadedCount} file(s) ready` : 'Drag files here'}
      </span>
    </div>
  );
}
