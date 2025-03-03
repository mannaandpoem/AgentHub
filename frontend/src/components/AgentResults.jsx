import React from 'react';
import { PaperClipIcon, CodeBracketIcon } from '@heroicons/react/24/outline';
import SyntaxHighlighter from 'react-syntax-highlighter';
import { atomOneDark } from 'react-syntax-highlighter/dist/esm/styles/hljs';

function AgentResults({ agent }) {
  if (!agent) {
    return (
      <div className="bg-slate-800 rounded-lg p-6 text-center">
        <p className="text-gray-400">No agent data available</p>
      </div>
    );
  }

  // Function to detect if a string contains code
  const detectLanguage = (content) => {
    if (!content) return null;

    // Simple heuristics to detect common programming languages
    if (content.includes('import') && content.includes('def ')) return 'python';
    if (content.includes('function') && content.includes('{')) return 'javascript';
    if (content.includes('class') && content.includes('{')) return 'java';
    if (content.includes('#include')) return 'cpp';
    if (content.includes('<html>') || content.includes('<!DOCTYPE html>')) return 'html';

    // Default to plaintext if no language detected
    return null;
  };

  // Format the result with code highlighting when appropriate
  const formatResult = (result) => {
    if (!result) return null;

    const language = detectLanguage(result);

    if (language) {
      return (
        <div className="code-block">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center">
              <CodeBracketIcon className="h-4 w-4 text-gray-400 mr-2" />
              <span className="text-xs text-gray-400">Detected {language} code</span>
            </div>
          </div>
          <SyntaxHighlighter
            language={language}
            style={atomOneDark}
            customStyle={{ background: 'transparent' }}
          >
            {result}
          </SyntaxHighlighter>
        </div>
      );
    }

    // Check if it looks like terminal output
    if (result.includes('$') || result.includes('#') || result.includes('>>>')) {
      return <div className="terminal-output">{result}</div>;
    }

    // Regular text
    return <div className="bg-slate-700 p-4 rounded-md text-gray-200 whitespace-pre-wrap">{result}</div>;
  };

  // Display configuration
  const displayConfig = () => {
    if (!agent.config) return null;

    try {
      return (
        <div className="mt-4">
          <h3 className="text-md font-medium text-white mb-2">Configuration</h3>
          <div className="code-block">
            <SyntaxHighlighter
              language="json"
              style={atomOneDark}
              customStyle={{ background: 'transparent' }}
            >
              {JSON.stringify(agent.config, null, 2)}
            </SyntaxHighlighter>
          </div>
        </div>
      );
    } catch (error) {
      return null;
    }
  };

  return (
    <div className="bg-slate-800 rounded-lg p-6">
      <h2 className="text-lg font-semibold text-white mb-4">Agent Results</h2>

      {agent.status === 'running' || agent.status === 'initializing' ? (
        <div className="flex items-center justify-center p-8">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500 mr-3"></div>
          <p className="text-gray-300">Agent is running...</p>
        </div>
      ) : agent.status === 'failed' ? (
        <div className="bg-red-900/20 border border-red-700 rounded-md p-4 text-red-300">
          <h3 className="font-medium mb-2">Execution Failed</h3>
          <p>{agent.error || 'An unknown error occurred'}</p>
        </div>
      ) : (
        <>
          <div>
            <h3 className="text-md font-medium text-white mb-2">Output</h3>
            {agent.result ? (
              formatResult(agent.result)
            ) : (
              <p className="text-gray-400 italic">No results available yet</p>
            )}
          </div>

          {agent.tool_calls && agent.tool_calls.length > 0 && (
            <div className="mt-6">
              <h3 className="text-md font-medium text-white mb-2">Tool Calls</h3>
              <div className="space-y-3">
                {agent.tool_calls.map((tool, index) => (
                  <div key={index} className="bg-slate-700 p-3 rounded-md">
                    <div className="flex items-center">
                      <PaperClipIcon className="h-4 w-4 text-blue-400 mr-2" />
                      <span className="font-medium text-white">{tool.function?.name || 'Unknown Tool'}</span>
                    </div>
                    {tool.function?.arguments && (
                      <div className="mt-2">
                        <div className="text-xs text-gray-400 mb-1">Arguments:</div>
                        <div className="code-block text-xs">
                          <SyntaxHighlighter
                            language="json"
                            style={atomOneDark}
                            customStyle={{ background: 'transparent' }}
                          >
                            {tool.function.arguments}
                          </SyntaxHighlighter>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {displayConfig()}
        </>
      )}
    </div>
  );
}

export default AgentResults;