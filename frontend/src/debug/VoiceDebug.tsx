"use client";

import { useState, useEffect } from 'react';

export default function VoiceDebug() {
  const [logs, setLogs] = useState<string[]>([]);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    // Listen for voice events for debugging
    const handleMessage = (event: CustomEvent) => {
      setLogs(prev => [...prev, `[${new Date().toISOString()}] ${event.detail}`]);
    };

    window.addEventListener('voice-message', handleMessage as EventListener);
    window.addEventListener('voice-status', handleMessage as EventListener);
    window.addEventListener('voice-transcription', handleMessage as EventListener);

    return () => {
      window.removeEventListener('voice-message', handleMessage as EventListener);
      window.removeEventListener('voice-status', handleMessage as EventListener);
      window.removeEventListener('voice-transcription', handleMessage as EventListener);
    };
  }, []);

  return (
    <div className="p-4 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Voice Assistant Debug</h1>
      
      <div className="mb-4">
        <button
          onClick={() => {
            // Test connection
            fetch('/api/voice/agent/test')
              .then(res => res.json())
              .then(data => {
                setIsConnected(true);
                setLogs(prev => [...prev, `[TEST] Backend connected: ${JSON.stringify(data)}`]);
              })
              .catch(err => {
                setIsConnected(false);
                setLogs(prev => [...prev, `[ERROR] Backend connection failed: ${err.message}`]);
              });
          }}
          className={`px-4 py-2 rounded ${isConnected ? 'bg-green-500 text-white' : 'bg-red-500 text-white'}`}
        >
          Test Backend Connection
        </button>
      </div>

      <div className="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg">
        <h2 className="text-lg font-semibold mb-2">Event Logs:</h2>
        <div className="space-y-1 max-h-96 overflow-y-auto font-mono text-sm">
          {logs.map((log, index) => (
            <div key={index} className="border-b border-gray-200 dark:border-gray-700 pb-1">
              {log}
            </div>
          ))}
        </div>
      </div>

      <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
        <h3 className="font-semibold mb-2">Debug Info:</h3>
        <ul className="list-disc list-inside space-y-1 text-sm">
          <li>ElevenLabs SDK Version: 0.6.0</li>
          <li>Backend URL: {process.env.NODE_ENV === 'production' ? '/api' : process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}</li>
          <li>Environment: {process.env.NODE_ENV}</li>
          <li>Browser: {typeof window !== 'undefined' ? navigator.userAgent : 'N/A'}</li>
          <li>WebSocket Connection: {isConnected ? '✅ Working' : '❌ Issues detected'}</li>
        </ul>
      </div>
    </div>
  );
}