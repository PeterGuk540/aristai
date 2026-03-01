import React, { useEffect, useState, useRef } from 'react';

interface LogEntry {
  timestamp: string;
  level: string;
  module?: string;
  message: string;
}

interface ConsoleProps {
  apiUrl: string;
}

const getModuleColor = (module?: string) => {
  if (!module) return 'text-gray-500';
  if (module.startsWith('uvicorn')) return 'text-purple-600';
  if (module.startsWith('fastapi')) return 'text-green-600';
  if (module.startsWith('app')) return 'text-blue-600';
  if (module.startsWith('sqlalchemy')) return 'text-orange-600';
  return 'text-gray-600';
};

const maskMessage = (message: string) => {
  // Regex for IPv4 address and optional port
  const ipRegex = /\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b/g;
  return message.replace(ipRegex, (match) => match.replace(/\d/g, '■'));
};

export const Console: React.FC<ConsoleProps> = ({ apiUrl }) => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const fetchLogs = async () => {
    try {
      const response = await fetch(`${apiUrl}/logs`);
      if (response.ok) {
        const data = await response.json();
        setLogs(data);
      }
    } catch (error) {
      console.error('Error fetching logs:', error);
    }
  };

  useEffect(() => {
    // Initial fetch
    fetchLogs();

    // Poll every 1 second
    const intervalId = setInterval(fetchLogs, 1000);

    return () => clearInterval(intervalId);
  }, [apiUrl]);

  useEffect(() => {
    // Auto-scroll to bottom
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="flex flex-col h-full bg-white text-blue-900 rounded-lg shadow-lg overflow-hidden font-mono text-[10px] sm:text-xs border border-gray-200">
      <div className="bg-gray-50 px-2 sm:px-4 py-1 sm:py-2 border-b border-gray-200 flex justify-between items-center">
        <span className="font-semibold text-blue-900 text-[10px] sm:text-sm">Completed Task List</span>
        <div className="flex space-x-1 sm:space-x-2">
            <div className="w-2 h-2 sm:w-3 sm:h-3 rounded-full bg-red-500"></div>
            <div className="w-2 h-2 sm:w-3 sm:h-3 rounded-full bg-yellow-500"></div>
            <div className="w-2 h-2 sm:w-3 sm:h-3 rounded-full bg-green-500"></div>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-1 sm:p-2">
        {logs.length === 0 ? (
          <div className="text-gray-400 italic">Waiting for logs...</div>
        ) : (
          <div className="w-full">
            <div className="grid grid-cols-[auto_1fr] sm:grid-cols-[auto_40px_140px_1fr] gap-x-1 sm:gap-x-3 gap-y-0.5 items-start">
              {logs.map((log, index) => (
                <React.Fragment key={index}>
                  <span className="text-gray-400 whitespace-nowrap hidden sm:block">[{new Date(log.timestamp).toLocaleTimeString([], { hour12: false })}]</span>
                  <span className={`font-bold whitespace-nowrap hidden sm:block ${
                    log.level === 'ERROR' ? 'text-red-600' :
                    log.level === 'WARNING' ? 'text-yellow-600' :
                    'text-blue-600'
                  }`}>
                    {log.level}
                  </span>
                  <span className={`font-medium whitespace-nowrap overflow-hidden text-ellipsis hidden sm:block ${getModuleColor(log.module)}`} title={log.module}>
                      {log.module ? `[${log.module}]` : ''}
                  </span>
                  
                  {/* Mobile View: Combined line */}
                  <div className="sm:hidden col-span-2 flex gap-1">
                    <span className={`font-bold ${
                        log.level === 'ERROR' ? 'text-red-600' :
                        log.level === 'WARNING' ? 'text-yellow-600' :
                        'text-blue-600'
                    }`}>
                        {log.level.charAt(0)}
                    </span>
                    <span className="text-gray-800 break-all leading-tight">
                        {maskMessage(log.message)}
                    </span>
                  </div>

                  {/* Desktop View: Message only */}
                  <span className="text-gray-800 whitespace-nowrap overflow-hidden text-ellipsis hidden sm:block" title={maskMessage(log.message)}>
                    {maskMessage(log.message)}
                  </span>
                </React.Fragment>
              ))}
            </div>
          </div>
        )}
        <div ref={logsEndRef} />
      </div>
    </div>
  );
};
