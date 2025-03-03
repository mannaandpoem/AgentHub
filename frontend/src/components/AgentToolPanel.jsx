import React, { useState } from 'react';
import { toast } from 'react-toastify';

// Available tools with their parameters
const AVAILABLE_TOOLS = [
  {
    name: 'create_chat_completion',
    description: 'Generate content using LLM',
    parameters: [
      {
        name: 'prompt',
        type: 'text',
        required: true,
        description: 'The prompt to send to the LLM',
      },
      {
        name: 'max_tokens',
        type: 'number',
        required: false,
        default: 1000,
        description: 'Maximum number of tokens to generate',
      }
    ]
  },
  {
    name: 'view',
    description: 'View file content',
    parameters: [
      {
        name: 'path',
        type: 'text',
        required: true,
        description: 'Path to the file to view',
      }
    ]
  },
  {
    name: 'write_code',
    description: 'Write code to a file',
    parameters: [
      {
        name: 'path',
        type: 'text',
        required: true,
        description: 'Path to write the file',
      },
      {
        name: 'content',
        type: 'textarea',
        required: true,
        description: 'Content to write to the file',
      }
    ]
  },
  {
    name: 'terminal',
    description: 'Execute terminal command',
    parameters: [
      {
        name: 'command',
        type: 'text',
        required: true,
        description: 'Command to execute',
      }
    ]
  },
  {
    name: 'search_file',
    description: 'Search for content in files',
    parameters: [
      {
        name: 'query',
        type: 'text',
        required: true,
        description: 'Search query',
      },
      {
        name: 'path',
        type: 'text',
        required: false,
        description: 'Directory path to search in (optional)',
      }
    ]
  }
];

function AgentToolPanel({ onExecuteTool }) {
  const [selectedTool, setSelectedTool] = useState(AVAILABLE_TOOLS[0].name);
  const [parameters, setParameters] = useState({});
  const [result, setResult] = useState(null);
  const [executing, setExecuting] = useState(false);

  // Find the current tool configuration
  const currentTool = AVAILABLE_TOOLS.find(tool => tool.name === selectedTool);

  const handleToolChange = (e) => {
    setSelectedTool(e.target.value);
    setParameters({});
    setResult(null);
  };

  const handleParameterChange = (e) => {
    const { name, value } = e.target;
    setParameters(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleExecute = async () => {
    // Validate required parameters
    const missingParams = currentTool.parameters
      .filter(param => param.required && !parameters[param.name])
      .map(param => param.name);

    if (missingParams.length > 0) {
      toast.error(`Missing required parameters: ${missingParams.join(', ')}`);
      return;
    }

    try {
      setExecuting(true);
      setResult(null);

      // Prepare parameters
      const toolParams = {};
      currentTool.parameters.forEach(param => {
        if (parameters[param.name] !== undefined) {
          toolParams[param.name] = parameters[param.name];
        } else if (param.default !== undefined) {
          toolParams[param.name] = param.default;
        }
      });

      // Execute tool
      const response = await onExecuteTool(selectedTool, toolParams);
      setResult(response.result);
    } catch (error) {
      console.error('Error executing tool:', error);
      setResult(`Error: ${error.message || 'Failed to execute tool'}`);
    } finally {
      setExecuting(false);
    }
  };

  return (
    <div className="bg-slate-800 rounded-lg overflow-hidden">
      <div className="p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Tool Execution</h2>

        <div className="mb-4">
          <label className="block text-gray-300 text-sm font-medium mb-2">
            Select Tool
          </label>
          <select
            value={selectedTool}
            onChange={handleToolChange}
            className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {AVAILABLE_TOOLS.map(tool => (
              <option key={tool.name} value={tool.name}>
                {tool.name} - {tool.description}
              </option>
            ))}
          </select>
        </div>

        <div className="mb-6">
          <h3 className="text-md font-medium text-white mb-2">Parameters</h3>

          {currentTool.parameters.map(param => (
            <div key={param.name} className="mb-4">
              <label className="block text-gray-300 text-sm font-medium mb-1">
                {param.name}
                {param.required && <span className="text-red-500 ml-1">*</span>}
              </label>

              {param.type === 'textarea' ? (
                <textarea
                  name={param.name}
                  value={parameters[param.name] || ''}
                  onChange={handleParameterChange}
                  placeholder={param.description}
                  rows={6}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              ) : param.type === 'number' ? (
                <input
                  type="number"
                  name={param.name}
                  value={parameters[param.name] || ''}
                  onChange={handleParameterChange}
                  placeholder={param.description}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              ) : (
                <input
                  type="text"
                  name={param.name}
                  value={parameters[param.name] || ''}
                  onChange={handleParameterChange}
                  placeholder={param.description}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              )}

              <p className="mt-1 text-xs text-gray-400">
                {param.description}
                {!param.required && ' (Optional)'}
                {param.default !== undefined && ` (Default: ${param.default})`}
              </p>
            </div>
          ))}

          <div className="mt-6">
            <button
              onClick={handleExecute}
              disabled={executing}
              className="btn btn-primary w-full"
            >
              {executing ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Executing...
                </span>
              ) : (
                'Execute Tool'
              )}
            </button>
          </div>
        </div>

        {result && (
          <div className="mt-6">
            <h3 className="text-md font-medium text-white mb-2">Result</h3>
            <div className="bg-slate-900 p-4 rounded-md text-gray-200 whitespace-pre-wrap font-mono text-sm overflow-auto max-h-96">
              {result}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default AgentToolPanel;