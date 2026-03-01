import { useState, useEffect, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Configure worker (essential for react-pdf)
pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs';

interface PDFViewerProps {
  fileId: number;
  apiUrl: string;
  isPreview?: boolean;
}

export function PDFViewer({ fileId, apiUrl, isPreview = false }: PDFViewerProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [containerWidth, setContainerWidth] = useState<number>(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect) {
          // Subtract padding (adjust for mobile: 16px for p-2 = 8px * 2)
          setContainerWidth(entry.contentRect.width - 20);
        }
      }
    });

    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
    setError(null);
  }

  function onDocumentLoadError(err: Error) {
    console.error('Error loading PDF:', err);
    setError(err.message);
  }

  const fileUrl = `${apiUrl}/files/${fileId}/content${isPreview ? '?preview=true' : ''}`;

  return (
    <div className="h-full flex flex-col bg-gray-500 overflow-hidden">
      <div className="bg-gray-700 text-white p-1 sm:p-2 flex justify-between items-center shadow-md z-10">
        <span className="text-[10px] sm:text-sm">{numPages} Pages</span>
      </div>
      <div className="flex-1 overflow-auto flex justify-center p-2 sm:p-4" ref={containerRef}>
        {error ? (
            <div className="text-red-500 bg-white p-2 sm:p-4 rounded shadow">
                <p className="font-bold text-[10px] sm:text-base">Failed to load PDF file.</p>
                <p className="text-[10px] sm:text-sm">{error}</p>
            </div>
        ) : (
            <Document
            file={fileUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            className="shadow-lg flex flex-col gap-2 sm:gap-4"
            >
            {Array.from(new Array(numPages), (_, index) => (
                <Page 
                    key={`page_${index + 1}`} 
                    pageNumber={index + 1} 
                    renderTextLayer={false} 
                    renderAnnotationLayer={false} 
                    width={containerWidth > 0 ? containerWidth : 300} 
                    className="mb-2 sm:mb-4 shadow-md"
                />
            ))}
            </Document>
        )}
      </div>
    </div>
  );
}
