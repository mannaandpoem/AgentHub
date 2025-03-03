import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import { ArrowLeftIcon, StopIcon, PlayIcon } from '@heroicons/react/24/outline';
import { agentService, createWebSocketConnection } from '../services/api';
import StatusBadge from '../components/StatusBadge.jsx';
import AgentLogs from '../components/AgentLogs.jsx';
import AgentToolPanel from '../components/AgentToolPanel.jsx';
import AgentResults from '../components/AgentResults.jsx';

function AgentDetail() {
  const { agentId } = useParams();
  const navigate = useNavigate();

  const [agent, setAgent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [logs, setLogs] = useState([]);
  const [activeTab, setActiveTab] = useState('overview');

  const wsConnectionRef = useRef(null);

  // Initial data fetch
  useEffect(() => {
    const fetchAgentDetails = async () => {
      try {
        setLoading(true);
        const agentData = await agentService.getAgentById(agentId);
        setAgent(agentData);

        // Fetch logs if available
        try {
          const logsData = await agentService.getAgentLogs(agentId);
          setLogs(logsData.logs || []);
        } catch (error) {
          console.error('Error fetching logs:', error);
          // Non-critical error, don't show toast
        }
      } catch (error) {
        console.error('Error fetching agent details:', error);
        toast.error('Failed to load agent details');
        navigate('/dashboard');
      } finally {
        setLoading(false);
      }
    };

    fetchAgentDetails();

    // WebSocket connection for real-time updates
    wsConnectionRef.current = createWebSocketConnection(
      agentId,
      (data) => {
        // Update agent data
        setAgent(prevAgent => ({ ...prevAgent, ...data }));
      },
      (error) => {
        console.error('WebSocket error:', error);
        toast.error('Real-time connection error');
      },
      () => {
        console.log('WebSocket closed');
      }
    );

    // Cleanup on unmount
    return () => {
      if (wsConnectionRef.current) {
        wsConnectionRef.current.close();
      }
    };
  }, [agentId, navigate]);

  // Function to refresh data
  const refreshData = async () => {
    try {
      const agentData = await agentService.getAgentById(agentId);
      setAgent(agentData);

      const logsData = await agentService.getAgentLogs(agentId);
      setLogs(logsData.logs || []);

      toast.success('Data refreshed');
    } catch (error) {
      console.error('Error refreshing data:', error);
      toast.error('Failed to refresh data');
    }
  };

  // Function to terminate agent
  const handleTerminate = async () => {
    try {
      await agentService.terminateAgent(agentId);
      toast.success('Agent terminated successfully');
      refreshData();
    } catch (error) {
      console.error('Error terminating agent:', error);
      toast.error('Failed to terminate agent');
    }
  };

  // Function to execute a tool
  const handleExecuteTool = async (toolName, parameters) => {
    try {
      const result = await agentService.executeAgentTool(agentId, toolName, parameters);
      toast.success(`Tool ${toolName} executed successfully`);
      return result;
    } catch (error) {
      console.error('Error executing tool:', error);
      toast.error(`Failed to execute tool ${toolName}`);
      throw error;
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="text-center py-12 bg-slate-800 rounded-lg">
        <h3 className="text-xl font-medium text-gray-300">Agent not found</h3>
        <button
          onClick={() => navigate('/dashboard')}
          className="btn btn-primary mt-4"
        >
          Back to Dashboard
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Header with navigation and actions */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center">
          <button
            onClick={() => navigate('/dashboard')}
            className="mr-4 text-gray-400 hover:text-white"
          >
            <ArrowLeftIcon className="h-5 w-5" />
          </button>
          <h1 className="text-2xl font-semibold text-white">Agent Details</h1>
          <StatusBadge status={agent.status} className="ml-4" />
        </div>
        <div className="flex items-center space-x-3">
          {agent.status !== 'terminated' && (
            <button
              onClick={handleTerminate}
              className="btn btn-danger flex items-center"
            >
              <StopIcon className="h-5 w-5 mr-1" />
              Terminate
            </button>
          )}
          <button
            onClick={refreshData}
            className="btn btn-secondary flex items-center"
          >
            <PlayIcon className="h-5 w-5 mr-1" />
            Refresh
          </button>
        </div>
      </div>

      {/* Agent information card */}
      <div className="bg-slate-800 rounded-lg p-6 shadow-md mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <h2 className="text-lg font-semibold text-white mb-4">Agent Information</h2>
            <div className="space-y-3">
              <div>
                <span className="text-gray-400 text-sm">ID:</span>
                <div className="text-gray-200 font-mono text-sm">{agent.id}</div>
              </div>
              <div>
                <span className="text-gray-400 text-sm">Type:</span>
                <div className="text-gray-200">{agent.type}</div>
              </div>
              <div>
                <span className="text-gray-400 text-sm">Status:</span>
                <div className="text-gray-200">{agent.status}</div>
              </div>
              <div>
                <span className="text-gray-400 text-sm">State:</span>
                <div className="text-gray-200">{agent.state}</div>
              </div>
              <div>
                <span className="text-gray-400 text-sm">Created:</span>
                <div className="text-gray-200">
                  {new Date(agent.created_at).toLocaleString()}
                </div>
              </div>
            </div>
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white mb-4">Task Description</h2>
            <div className="bg-slate-700 p-4 rounded-md text-gray-200 h-48 overflow-y-auto">
              {agent.task}
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-700 mb-6">
        <nav className="flex -mb-px">
          <button
            className={`mr-8 py-4 text-sm font-medium border-b-2 ${
              activeTab === 'overview'
                ? 'border-blue-500 text-blue-500'
                : 'border-transparent text-gray-400 hover:text-gray-300'
            }`}
            onClick={() => setActiveTab('overview')}
          >
            Overview
          </button>
          <button
            className={`mr-8 py-4 text-sm font-medium border-b-2 ${
              activeTab === 'logs'
                ? 'border-blue-500 text-blue-500'
                : 'border-transparent text-gray-400 hover:text-gray-300'
            }`}
            onClick={() => setActiveTab('logs')}
          >
            Logs
          </button>
          <button
            className={`mr-8 py-4 text-sm font-medium border-b-2 ${
              activeTab === 'tools'
                ? 'border-blue-500 text-blue-500'
                : 'border-transparent text-gray-400 hover:text-gray-300'
            }`}
            onClick={() => setActiveTab('tools')}
          >
            Tools
          </button>
        </nav>
      </div>

      {/* Tab content */}
      <div className="mb-6">
        {activeTab === 'overview' && <AgentResults agent={agent} />}
        {activeTab === 'logs' && <AgentLogs logs={logs} />}
        {activeTab === 'tools' && (
          <AgentToolPanel agentId={agentId} onExecuteTool={handleExecuteTool} />
        )}
      </div>
    </div>
  );
}

export default AgentDetail;