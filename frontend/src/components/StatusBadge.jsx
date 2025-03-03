import React from 'react';
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  ClockIcon,
  StopIcon
} from '@heroicons/react/24/outline';

function StatusBadge({ status, className = '' }) {
  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'running':
      case 'initializing':
        return 'bg-yellow-900 text-yellow-300';
      case 'completed':
        return 'bg-green-900 text-green-300';
      case 'failed':
        return 'bg-red-900 text-red-300';
      case 'terminated':
        return 'bg-gray-800 text-gray-300';
      default:
        return 'bg-gray-800 text-gray-300';
    }
  };

  const getStatusIcon = (status) => {
    switch (status?.toLowerCase()) {
      case 'running':
      case 'initializing':
        return <ClockIcon className="h-4 w-4" />;
      case 'completed':
        return <CheckCircleIcon className="h-4 w-4" />;
      case 'failed':
        return <ExclamationCircleIcon className="h-4 w-4" />;
      case 'terminated':
        return <StopIcon className="h-4 w-4" />;
      default:
        return <ClockIcon className="h-4 w-4" />;
    }
  };

  return (
    <span
      className={`${getStatusColor(
        status
      )} inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${className}`}
    >
      {getStatusIcon(status)}
      <span className="ml-1">{status}</span>
    </span>
  );
}

export default StatusBadge;