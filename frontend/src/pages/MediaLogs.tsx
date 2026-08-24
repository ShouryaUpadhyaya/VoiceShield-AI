import React, { useEffect, useState, useRef } from 'react';

export const MediaLogs: React.FC = () => {
  const [logs, setLogs] = useState<string[]>([]);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Connect to the media-tester SSE endpoint
    const eventSource = new EventSource('http://localhost:8005/logs');

    eventSource.onmessage = (event) => {
      setLogs((prev) => [...prev, event.data]);
    };

    eventSource.onerror = (err) => {
      console.error("SSE Error:", err);
      // It will auto-reconnect
    };

    return () => {
      eventSource.close();
    };
  }, []);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="min-h-screen bg-gray-900 text-green-400 p-8 font-mono">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold mb-6 text-white border-b border-gray-700 pb-2">
          Media Pipeline Test Logs
        </h1>
        <div className="bg-black rounded-lg p-4 h-[600px] overflow-y-auto shadow-2xl border border-gray-800">
          {logs.length === 0 ? (
            <div className="text-gray-500 animate-pulse">Waiting for logs... Make sure the media-tester service is running.</div>
          ) : (
            logs.map((log, index) => (
              <div key={index} className="mb-1 hover:bg-gray-800 px-2 py-1 rounded transition-colors">
                {log}
              </div>
            ))
          )}
          <div ref={logsEndRef} />
        </div>
      </div>
    </div>
  );
};
