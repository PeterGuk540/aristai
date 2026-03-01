import { useState } from 'react';
import { Console } from './Console';

interface LogDrawerProps {
  apiUrl: string;
}

export function LogDrawer({ apiUrl }: LogDrawerProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className={`fixed bottom-0 left-0 right-0 z-40 bg-white shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)] transition-transform duration-300 ease-in-out border-t border-gray-200 ${isOpen ? 'translate-y-0' : 'translate-y-[calc(100%-40px)]'}`}>
      {/* Handle/Header */}
      <div 
        className="h-10 bg-gray-50 hover:bg-gray-100 flex items-center justify-between px-4 cursor-pointer border-b border-gray-200"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center space-x-2 text-xs font-medium text-gray-600">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          {isOpen ? 'System Logs (Click to Collapse)' : 'System Logs & Console (Click to Expand)'}
        </div>
        <div className="flex items-center">
            <svg 
                className={`w-4 h-4 text-gray-400 transform transition-transform ${isOpen ? 'rotate-180' : ''}`} 
                fill="none" 
                viewBox="0 0 24 24" 
                stroke="currentColor"
            >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
            </svg>
        </div>
      </div>

      {/* Content */}
      <div className="h-64 sm:h-80 overflow-hidden">
        <Console apiUrl={apiUrl} />
      </div>
    </div>
  );
}
