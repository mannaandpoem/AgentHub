import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import AgentHub components
from app.agent import ToolCallAgent, CodeActAgent, SWEAgent, MidwitAgent
from app.config import config
from app.logger import logger
from app.schema import AgentState

# Create FastAPI app
app = FastAPI(
    title="AgentHub API",
    description="API for managing and running AI agents with various tools and capabilities",
    version="0.1.0"
)

# Configure CORS
origins = config.security.allowed_origins if config.security else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active agent sessions
active_agents = {}
agent_logs = {}

# WebSocket connections for real-time updates
websocket_connections = {}


# Models for request/response validation
class AgentRequest(BaseModel):
    agent_type: str
    task: str
    config: Optional[Dict[str, Any]] = None


class ToolRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any] = {}


class AgentResponse(BaseModel):
    agent_id: str
    status: str
    message: str
    state: Optional[str] = None


class AgentListResponse(BaseModel):
    agents: List[Dict[str, Any]]


class AgentTypes(BaseModel):
    types: List[Dict[str, str]]


class AgentLogs(BaseModel):
    logs: List[Dict[str, Any]]


class TaskResult(BaseModel):
    result: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    metrics: Optional[Dict[str, Any]] = None


# Helper functions
def get_agent_class(agent_type: str):
    """Get agent class based on type string"""
    agent_map = {
        "toolcall": ToolCallAgent,
        "codeact": CodeActAgent,
        "swe": SWEAgent,
        "midwit": MidwitAgent,
    }

    if agent_type not in agent_map:
        raise HTTPException(status_code=400, detail=f"Unknown agent type: {agent_type}")

    return agent_map[agent_type]


async def run_agent_task(agent_id: str, agent, task: str):
    """Run agent task in background and update status"""
    try:
        # Initialize the agent with the task
        await agent.run(request=task)
        active_agents[agent_id]["state"] = str(agent.state)

        # Run the agent
        result = await agent.run()

        # Update agent status
        active_agents[agent_id]["status"] = "completed"
        active_agents[agent_id]["result"] = result
        active_agents[agent_id]["state"] = str(agent.state)

        # Notify connected clients
        await broadcast_update(agent_id)

        return result
    except Exception as e:
        logger.error(f"Agent {agent_id} failed: {str(e)}")
        active_agents[agent_id]["status"] = "failed"
        active_agents[agent_id]["error"] = str(e)
        active_agents[agent_id]["state"] = "ERROR"

        # Notify connected clients
        await broadcast_update(agent_id)

        raise


async def broadcast_update(agent_id: str):
    """Broadcast agent updates to all connected WebSocket clients"""
    if agent_id in websocket_connections:
        for websocket in websocket_connections[agent_id]:
            try:
                await websocket.send_json(active_agents[agent_id])
            except Exception as e:
                logger.error(f"Failed to send update to WebSocket: {str(e)}")


# API routes
@app.get("/")
async def root():
    return {"message": "Welcome to AgentHub API", "version": "0.1.0"}


@app.get("/api/agent/types", response_model=AgentTypes)
async def get_agent_types():
    """Get available agent types"""
    return {
        "types": [
            {"id": "toolcall", "name": "Tool Call Agent", "description": "An agent that can execute tool calls"},
            {"id": "codeact", "name": "Code Act Agent", "description": "An agent specialized in coding tasks"},
            {"id": "swe", "name": "Software Engineer Agent",
             "description": "A software engineering agent with planning capabilities"},
            {"id": "midwit", "name": "Midwit Agent", "description": "A simpler agent with basic reasoning capabilities"}
        ]
    }


@app.post("/api/agent/create", response_model=AgentResponse)
async def create_agent(request: AgentRequest, background_tasks: BackgroundTasks):
    """Create a new agent instance"""
    agent_id = f"{request.agent_type}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    try:
        # Get agent class based on type
        agent_class = get_agent_class(request.agent_type)

        # Create agent instance with custom config if provided
        agent_config = request.config or {}

        # Get the LLM config from the global config
        llm_config = config.get_llm_config()
        if "llm" not in agent_config:
            agent_config["llm"] = {
                "model": llm_config.model,
                "base_url": llm_config.base_url,
                "api_key": llm_config.api_key,
                "max_tokens": llm_config.max_tokens,
                "temperature": llm_config.temperature
            }

        agent = agent_class()

        # Store agent in active agents
        active_agents[agent_id] = {
            "id": agent_id,
            "type": request.agent_type,
            "task": request.task,
            "status": "initializing",
            "created_at": datetime.now().isoformat(),
            "state": str(AgentState.INITIALIZING),
            "config": agent_config
        }

        # Initialize log storage
        agent_logs[agent_id] = []

        # Initialize WebSocket connections list
        websocket_connections[agent_id] = []

        # Run agent in background
        background_tasks.add_task(run_agent_task, agent_id, agent, request.task)

        return {
            "agent_id": agent_id,
            "status": "created",
            "message": f"Agent {agent_id} created and initialized",
            "state": str(AgentState.INITIALIZING)
        }
    except Exception as e:
        logger.error(f"Failed to create agent: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create agent: {str(e)}")


@app.get("/api/agent/{agent_id}", response_model=Dict[str, Any])
async def get_agent(agent_id: str):
    """Get agent details and status"""
    if agent_id not in active_agents:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    return active_agents[agent_id]


@app.get("/api/agent", response_model=AgentListResponse)
async def list_agents():
    """List all active agents"""
    return {"agents": list(active_agents.values())}


@app.post("/api/agent/{agent_id}/execute", response_model=TaskResult)
async def execute_tool(agent_id: str, request: ToolRequest):
    """Execute a specific tool for an agent"""
    if agent_id not in active_agents:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    agent_info = active_agents[agent_id]
    if agent_info["status"] != "running":
        raise HTTPException(status_code=400, detail=f"Agent {agent_id} is not in running state")

    try:
        # Get agent class based on type
        agent_class = get_agent_class(agent_info["type"])
        agent = agent_class(**agent_info.get("config", {}))

        # Execute tool
        result = await agent.execute_tool({
            "function": {
                "name": request.tool_name,
                "arguments": json.dumps(request.parameters)
            },
            "id": f"manual-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        })

        return {"result": result}
    except Exception as e:
        logger.error(f"Failed to execute tool: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to execute tool: {str(e)}")


@app.delete("/api/agent/{agent_id}", response_model=AgentResponse)
async def terminate_agent(agent_id: str):
    """Terminate an agent"""
    if agent_id not in active_agents:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    # Add termination logic here
    active_agents[agent_id]["status"] = "terminated"
    active_agents[agent_id]["state"] = str(AgentState.FINISHED)

    # Notify connected clients
    await broadcast_update(agent_id)

    return {
        "agent_id": agent_id,
        "status": "terminated",
        "message": f"Agent {agent_id} terminated",
        "state": str(AgentState.FINISHED)
    }


@app.get("/api/agent/{agent_id}/logs", response_model=AgentLogs)
async def get_agent_logs(agent_id: str):
    """Get logs for a specific agent"""
    if agent_id not in agent_logs:
        raise HTTPException(status_code=404, detail=f"Logs for agent {agent_id} not found")

    return {"logs": agent_logs[agent_id]}


@app.websocket("/ws/agent/{agent_id}")
async def websocket_endpoint(websocket: WebSocket, agent_id: str):
    """WebSocket endpoint for real-time agent updates"""
    await websocket.accept()

    if agent_id not in active_agents:
        await websocket.close(code=1008, reason=f"Agent {agent_id} not found")
        return

    # Add connection to list
    if agent_id not in websocket_connections:
        websocket_connections[agent_id] = []

    websocket_connections[agent_id].append(websocket)

    try:
        # Send initial state
        await websocket.send_json(active_agents[agent_id])

        # Keep connection open and handle messages
        while True:
            data = await websocket.receive_text()
            # Handle client messages if needed
    except WebSocketDisconnect:
        # Remove connection from list
        if agent_id in websocket_connections:
            websocket_connections[agent_id].remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        if agent_id in websocket_connections and websocket in websocket_connections[agent_id]:
            websocket_connections[agent_id].remove(websocket)


# Mount React frontend static files in production
if os.path.exists("./frontend/dist"):
    app.mount("/", StaticFiles(directory="./frontend/dist", html=True), name="frontend")


# Initialize with configuration
def start_server():
    """Start the FastAPI server with configuration"""
    import uvicorn

    host = config.api.host if config.api else "0.0.0.0"
    port = config.api.port if config.api else 8000
    debug = config.api.debug if config.api else False

    # Configure logging
    log_level = config.logging.level.upper() if config.logging else "INFO"
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(config.logging.file if config.logging and config.logging.file else "agenthub.log")
        ]
    )

    logger.info(f"Starting AgentHub API on {host}:{port}")
    uvicorn.run("api:app", host=host, port=port, reload=debug)


if __name__ == "__main__":
    start_server()
