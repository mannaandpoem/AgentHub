import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'react-toastify';
import { PlusIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import { agentService } from '../services/api';
import AgentCard from '../components/AgentCard';

function Dashboard() {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        setLoading(true);
        const response = await agentService.getAgents();
        setAgents(response.agents || []);
      } catch (error) {
        console.error('Error fetching agents:', error);
        toast.error('Failed to load agents');
      } finally {
        setLoading(false);
      }
    };

    fetchAgents();
  }, [refreshKey]);

  const handleRefresh = () => {
    setRefreshKey(prevKey => prevKey + 1);
  };

  const handleTerminate = async (agentId) => {
    try {
      await agentService.terminateAgent(agentId);
      toast.success('Agent terminated successfully');
      handleRefresh();
    } catch (error) {
      console.error('Error terminating agent:', error);
      toast.error('Failed to terminate agent');
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-semibold text-white">Agents Dashboard</h1>
        <div className="flex gap-2">
          <button
            className="btn btn-secondary flex items-center"
            onClick={handleRefresh}
            disabled={loading}
          >
            <ArrowPathIcon className={`h-5 w-5 mr-1 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <Link to="/agents/create" className="btn btn-primary flex items-center">
            <PlusIcon className="h-5 w-5 mr-1" />
            New Agent
          </Link>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      ) : agents.length === 0 ? (
        <div className="text-center py-12 bg-slate-800 rounded-lg">
          <h3 className="text-xl font-medium text-gray-300">No agents created yet</h3>
          <p className="text-gray-400 mt-2">Create your first agent to get started</p>
          <Link
            to="/agents/create"
            className="btn btn-primary mt-4 inline-flex items-center"
          >
            <PlusIcon className="h-5 w-5 mr-1" />
            Create Agent
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {agents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              onTerminate={() => handleTerminate(agent.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default Dashboard;