import { useState, useEffect } from 'react';
import { PDFViewer } from './PDFViewer';
import mammoth from 'mammoth';

interface FileViewerProps {
  fileId: number;
  filename: string;
  apiUrl: string;
}

export function FileViewer({ fileId, filename, apiUrl }: FileViewerProps) {
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const extension = filename.split('.').pop()?.toLowerCase();

  // Use PDFViewer for PDF and DOCX (via preview)
  if (extension === 'pdf' || extension === 'docx') {
    return <PDFViewer fileId={fileId} apiUrl={apiUrl} isPreview={extension === 'docx'} />;
  }

  useEffect(() => {
    if (extension === 'pdf' || extension === 'docx') return; // PDFViewer handles fetching

    const fetchContent = async () => {
      setLoading(true);
      setError(null);
      setContent(null);
      try {
        const response = await fetch(`${apiUrl}/files/${fileId}/content`);
        if (!response.ok) throw new Error('Failed to load file');
        
        const blob = await response.blob();

        if (extension === 'docx') {
          const arrayBuffer = await blob.arrayBuffer();
          const result = await mammoth.convertToHtml({ arrayBuffer });
          setContent(result.value);
        } else {
          // Assume text for other formats (txt, md, json, etc.)
          const text = await blob.text();
          setContent(text);
        }
      } catch (err) {
        console.error(err);
        setError('Error loading file content');
      } finally {
        setLoading(false);
      }
    };

    fetchContent();
  }, [fileId, filename, apiUrl, extension]);

  if (extension === 'pdf' || extension === 'docx') {
    return <PDFViewer fileId={fileId} apiUrl={apiUrl} isPreview={extension === 'docx'} />;
  }

  return (
    <div className="h-full flex flex-col bg-white overflow-hidden">
      <div className="bg-gray-100 p-1 sm:p-2 border-b flex justify-between items-center shadow-sm z-10">
        <span className="font-medium text-[10px] sm:text-sm text-gray-700 truncate" title={filename}>{filename}</span>
        <span className="text-[8px] sm:text-xs text-gray-500 uppercase px-1 sm:px-2 py-0.5 bg-gray-200 rounded">{extension}</span>
      </div>
      <div className="flex-1 overflow-auto p-2 sm:p-6">
        {loading && (
            <div className="flex justify-center items-center h-full text-gray-500 text-[10px] sm:text-base">
                <svg className="animate-spin h-4 w-4 sm:h-5 sm:w-5 mr-2 sm:mr-3" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Loading content...
            </div>
        )}
        {error && <div className="text-center text-red-500 mt-2 sm:mt-4 text-[10px] sm:text-base">{error}</div>}
        {!loading && !error && content && (
          extension === 'docx' ? (
            <div className="prose max-w-none text-[10px] sm:text-base" dangerouslySetInnerHTML={{ __html: content }} />
          ) : (
            <pre className="whitespace-pre-wrap font-mono text-[10px] sm:text-sm text-gray-800 bg-gray-50 p-2 sm:p-4 rounded border">{content}</pre>
          )
        )}
      </div>
    </div>
  );
}
