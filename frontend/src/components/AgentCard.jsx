import React from 'react';
import { Link } from 'react-router-dom';
import {
  BeakerIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ClockIcon,
  ArrowRightIcon,
  StopIcon
} from '@heroicons/react/24/outline';

function AgentCard({ agent, onTerminate }) {
  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'running':
      case 'initializing':
        return 'text-yellow-500';
      case 'completed':
        return 'text-green-500';
      case 'failed':
        return 'text-red-500';
      case 'terminated':
        return 'text-gray-500';
      default:
        return 'text-gray-300';
    }
  };

  const getStatusIcon = (status) => {
    switch (status?.toLowerCase()) {
      case 'running':
      case 'initializing':
        return <ClockIcon className="h-5 w-5" />;
      case 'completed':
        return <CheckCircleIcon className="h-5 w-5" />;
      case 'failed':
        return <ExclamationCircleIcon className="h-5 w-5" />;
      case 'terminated':
        return <StopIcon className="h-5 w-5" />;
      default:
        return <ClockIcon className="h-5 w-5" />;
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  return (
    <div className="card hover:shadow-lg transition-all duration-200">
      <div className="card-header">
        <div className="flex justify-between items-center">
          <div className="flex items-center">
            <BeakerIcon className="h-5 w-5 text-blue-500 mr-2" />
            <h3 className="text-lg font-medium text-white truncate">{agent.type}</h3>
          </div>
          <div className={`flex items-center ${getStatusColor(agent.status)}`}>
            {getStatusIcon(agent.status)}
            <span className="ml-1 text-sm">{agent.status}</span>
          </div>
        </div>
      </div>
      <div className="card-body">
        <div className="mb-4">
          <div className="text-sm text-gray-400 mb-1">Agent ID</div>
          <div className="text-xs text-gray-300 truncate font-mono">{agent.id}</div>
        </div>
        <div className="mb-4">
          <div className="text-sm text-gray-400 mb-1">Task</div>
          <p className="text-sm text-gray-200 line-clamp-2">{agent.task}</p>
        </div>
        <div className="mb-4">
          <div className="text-sm text-gray-400 mb-1">Created</div>
          <div className="text-sm text-gray-300">{formatDate(agent.created_at)}</div>
        </div>
        <div className="flex justify-between mt-4">
          {agent.status !== 'terminated' && (
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onTerminate();
              }}
              className="btn bg-red-600 hover:bg-red-700 text-white text-sm px-3 py-1 rounded"
            >
              Terminate
            </button>
          )}
          <Link
            to={`/agents/${agent.id}`}
            className="btn bg-blue-600 hover:bg-blue-700 text-white text-sm px-3 py-1 rounded ml-auto flex items-center"
          >
            View Details
            <ArrowRightIcon className="ml-1 h-4 w-4" />
          </Link>
        </div>
      </div>
    </div>
  );
}

export default AgentCard;