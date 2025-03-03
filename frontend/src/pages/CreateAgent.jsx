import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import { ArrowLeftIcon } from '@heroicons/react/24/outline';
import { agentService } from '../services/api';

function CreateAgent() {
  const navigate = useNavigate();

  const [agentTypes, setAgentTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const [formData, setFormData] = useState({
    agentType: '',
    task: '',
    configJson: '{\n  "max_steps": 30\n}',
  });
  const [errors, setErrors] = useState({});

  useEffect(() => {
    const fetchAgentTypes = async () => {
      try {
        setLoading(true);
        const response = await agentService.getAgentTypes();
        setAgentTypes(response.types || []);
        if (response.types?.length > 0) {
          setFormData(prev => ({
            ...prev,
            agentType: response.types[0].id
          }));
        }
      } catch (error) {
        console.error('Error fetching agent types:', error);
        toast.error('Failed to load agent types');
      } finally {
        setLoading(false);
      }
    };

    fetchAgentTypes();
  }, []);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));

    // Clear error for this field
    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: null
      }));
    }
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.agentType) {
      newErrors.agentType = 'Please select an agent type';
    }

    if (!formData.task || formData.task.trim() === '') {
      newErrors.task = 'Please enter a task description';
    }

    try {
      if (formData.configJson && formData.configJson.trim() !== '') {
        JSON.parse(formData.configJson);
      }
    } catch (error) {
      newErrors.configJson = 'Invalid JSON configuration';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    try {
      setCreating(true);

      // Parse the config JSON
      let config = {};
      try {
        if (formData.configJson && formData.configJson.trim() !== '') {
          config = JSON.parse(formData.configJson);
        }
      } catch (error) {
        // Already validated in validateForm
      }

      const response = await agentService.createAgent(
        formData.agentType,
        formData.task,
        config
      );

      toast.success('Agent created successfully');
      navigate(`/agents/${response.agent_id}`);
    } catch (error) {
      console.error('Error creating agent:', error);
      toast.error('Failed to create agent: ' + (error.response?.data?.detail || error.message));
    } finally {
      setCreating(false);
    }
  };

  const handleCancel = () => {
    navigate('/dashboard');
  };

  return (
    <div>
      <div className="flex items-center mb-6">
        <button
          onClick={() => navigate('/dashboard')}
          className="mr-4 text-gray-400 hover:text-white"
        >
          <ArrowLeftIcon className="h-5 w-5" />
        </button>
        <h1 className="text-2xl font-semibold text-white">Create New Agent</h1>
      </div>

      {loading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      ) : (
        <div className="bg-slate-800 rounded-lg p-6 shadow-md">
          <form onSubmit={handleSubmit}>
            <div className="mb-6">
              <label className="block text-gray-300 text-sm font-medium mb-2" htmlFor="agentType">
                Agent Type
              </label>
              <select
                id="agentType"
                name="agentType"
                value={formData.agentType}
                onChange={handleInputChange}
                className={`w-full px-3 py-2 bg-slate-700 border ${
                  errors.agentType ? 'border-red-500' : 'border-slate-600'
                } rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500`}
              >
                {agentTypes.map((type) => (
                  <option key={type.id} value={type.id}>
                    {type.name} - {type.description}
                  </option>
                ))}
              </select>
              {errors.agentType && (
                <p className="mt-1 text-sm text-red-500">{errors.agentType}</p>
              )}
            </div>

            <div className="mb-6">
              <label className="block text-gray-300 text-sm font-medium mb-2" htmlFor="task">
                Task Description
              </label>
              <textarea
                id="task"
                name="task"
                value={formData.task}
                onChange={handleInputChange}
                rows={4}
                placeholder="Describe the task for the agent to perform..."
                className={`w-full px-3 py-2 bg-slate-700 border ${
                  errors.task ? 'border-red-500' : 'border-slate-600'
                } rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500`}
              />
              {errors.task && (
                <p className="mt-1 text-sm text-red-500">{errors.task}</p>
              )}
            </div>

            <div className="mb-6">
              <label className="block text-gray-300 text-sm font-medium mb-2" htmlFor="configJson">
                Configuration (JSON)
              </label>
              <textarea
                id="configJson"
                name="configJson"
                value={formData.configJson}
                onChange={handleInputChange}
                rows={6}
                placeholder="Enter configuration in JSON format..."
                className={`w-full px-3 py-2 bg-slate-700 border ${
                  errors.configJson ? 'border-red-500' : 'border-slate-600'
                } rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm`}
              />
              {errors.configJson && (
                <p className="mt-1 text-sm text-red-500">{errors.configJson}</p>
              )}
              <p className="mt-1 text-xs text-gray-400">
                Optional: Customize agent behavior with JSON configuration
              </p>
            </div>

            <div className="flex justify-end gap-3 mt-8">
              <button
                type="button"
                onClick={handleCancel}
                className="btn btn-secondary"
                disabled={creating}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={creating}
              >
                {creating ? (
                  <span className="flex items-center">
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Creating...
                  </span>
                ) : (
                  'Create Agent'
                )}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

export default CreateAgent;