import React from 'react';

function AgentLogs({ logs = [] }) {
  if (!logs || logs.length === 0) {
    return (
      <div className="bg-slate-800 rounded-lg p-6 text-center">
        <p className="text-gray-400">No logs available</p>
      </div>
    );
  }

  const getLogTypeClass = (type) => {
    switch (type?.toLowerCase()) {
      case 'info':
        return 'agent-log-info';
      case 'error':
        return 'agent-log-error';
      case 'success':
        return 'agent-log-success';
      case 'warning':
        return 'agent-log-warning';
      default:
        return 'agent-log-info';
    }
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  };

  return (
    <div className="bg-slate-800 rounded-lg p-6">
      <h2 className="text-lg font-semibold text-white mb-4">Agent Logs</h2>
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {logs.map((log, index) => (
          <div
            key={index}
            className={`agent-log ${getLogTypeClass(log.level)}`}
          >
            <div className="flex justify-between">
              <span className="text-sm font-medium">{log.level}</span>
              <span className="text-xs text-gray-400">{formatTimestamp(log.timestamp)}</span>
            </div>
            <div className="mt-1 text-sm whitespace-pre-wrap">{log.message}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default AgentLogs;