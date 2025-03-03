import axios from 'axios';

// Create axios instance with base URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// API services for agents
const agentService = {
  // Get agent types
  getAgentTypes: async () => {
    const response = await api.get('/agent/types');
    return response.data;
  },

  // Create new agent
  createAgent: async (agentType, task, config = {}) => {
    const response = await api.post('/agent/create', {
      agent_type: agentType,
      task,
      config,
    });
    return response.data;
  },

  // Get all agents
  getAgents: async () => {
    const response = await api.get('/agent');
    return response.data;
  },

  // Get agent by ID
  getAgentById: async (agentId) => {
    const response = await api.get(`/agent/${agentId}`);
    return response.data;
  },

  // Execute tool for agent
  executeAgentTool: async (agentId, toolName, parameters = {}) => {
    const response = await api.post(`/agent/${agentId}/execute`, {
      tool_name: toolName,
      parameters,
    });
    return response.data;
  },

  // Terminate agent
  terminateAgent: async (agentId) => {
    const response = await api.delete(`/agent/${agentId}`);
    return response.data;
  },

  // Get agent logs
  getAgentLogs: async (agentId) => {
    const response = await api.get(`/agent/${agentId}/logs`);
    return response.data;
  },
};

// WebSocket connection for real-time updates
const createWebSocketConnection = (agentId, onMessage, onError, onClose) => {
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsHost = import.meta.env.VITE_WS_HOST || window.location.host;
  const wsUrl = `${wsProtocol}//${wsHost}/ws/agent/${agentId}`;

  const socket = new WebSocket(wsUrl);

  socket.onopen = () => {
    console.log(`WebSocket connection established for agent ${agentId}`);
  };

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  };

  socket.onerror = (error) => {
    console.error('WebSocket error:', error);
    if (onError) onError(error);
  };

  socket.onclose = (event) => {
    console.log(`WebSocket connection closed for agent ${agentId}:`, event.code, event.reason);
    if (onClose) onClose(event);
  };

  return {
    socket,
    close: () => {
      socket.close();
    },
  };
};

export { agentService, createWebSocketConnection };