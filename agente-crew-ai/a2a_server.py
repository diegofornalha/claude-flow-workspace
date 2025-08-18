#!/usr/bin/env python3
"""
CrewAI A2A Agent Server
Expõe equipes de agentes CrewAI como serviço A2A
"""

from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import asyncio
import json
import uuid
from datetime import datetime
import logging
from crewai import Agent, Task, Crew, Process
from langchain.tools import tool
import os
from dotenv import load_dotenv

load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Modelos Pydantic para requisições
class TaskRequest(BaseModel):
    task: str
    context: Optional[Dict[str, Any]] = {}
    streaming: Optional[bool] = False
    crew_config: Optional[Dict[str, Any]] = {}

class DecisionRequest(BaseModel):
    context: Dict[str, Any]
    options: List[str]

class LearningRequest(BaseModel):
    data: Dict[str, Any]
    type: Optional[str] = "general"

class ConsensusRequest(BaseModel):
    proposal: Dict[str, Any]
    peers: Optional[List[str]] = []

# Ferramentas customizadas para os agentes
@tool
def search_knowledge(query: str) -> str:
    """Busca na base de conhecimento local"""
    # Implementar busca real aqui
    return f"Knowledge about: {query}"

@tool  
def analyze_data(data: dict) -> dict:
    """Analisa dados estruturados"""
    return {
        "analysis": "Data analyzed",
        "insights": ["insight1", "insight2"],
        "recommendations": ["rec1", "rec2"]
    }

class CrewA2AAgent:
    def __init__(self):
        self.agent_id = f"crew-{uuid.uuid4().hex[:8]}"
        self.agent_name = "CrewAI A2A Team"
        self.agent_type = "team"
        self.tasks = {}
        self.crews = {}
        self.knowledge_base = []
        self.metrics = {
            "tasks_completed": 0,
            "decisions_made": 0,
            "crews_created": 0,
            "started_at": datetime.utcnow().isoformat()
        }
        
        # Criar FastAPI app
        self.app = FastAPI(title="CrewAI A2A Agent")
        self.setup_middleware()
        self.setup_routes()
        
        # WebSocket connections
        self.websockets = set()

    def setup_middleware(self):
        """Configurar CORS e outros middlewares"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def setup_routes(self):
        """Configurar todas as rotas A2A"""
        
        @self.app.get("/")
        async def agent_card():
            """Agent Card com informações do agente"""
            return {
                "agent": {
                    "id": self.agent_id,
                    "name": self.agent_name,
                    "type": self.agent_type,
                    "version": "1.0.0"
                },
                "protocol": {
                    "version": "2.0",
                    "type": "a2a"
                },
                "capabilities": [
                    "multi_agent_coordination",
                    "task_delegation",
                    "role_based_agents",
                    "sequential_processing",
                    "hierarchical_processing",
                    "consensus_building",
                    "collaborative_problem_solving"
                ],
                "endpoints": {
                    "tasks": "/tasks",
                    "decide": "/decide",
                    "learn": "/learn",
                    "adapt": "/adapt",
                    "consensus": "/consensus",
                    "crew": {
                        "create": "/crew/create",
                        "list": "/crew/list",
                        "execute": "/crew/execute"
                    }
                },
                "crew_roles": [
                    "researcher",
                    "analyst", 
                    "writer",
                    "reviewer",
                    "coordinator"
                ]
            }

        @self.app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "agent_id": self.agent_id,
                "uptime": self._calculate_uptime()
            }

        @self.app.get("/status")
        async def get_status():
            return {
                "agent_id": self.agent_id,
                "tasks_running": len(self.tasks),
                "crews_active": len(self.crews),
                "metrics": self.metrics
            }

        @self.app.post("/tasks")
        async def create_task(request: TaskRequest, background_tasks: BackgroundTasks):
            """Criar nova tarefa A2A"""
            task_id = f"task-{uuid.uuid4().hex}"
            
            task_data = {
                "id": task_id,
                "task": request.task,
                "context": request.context,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "streaming": request.streaming
            }
            
            self.tasks[task_id] = task_data
            
            # Executar tarefa em background
            background_tasks.add_task(self.execute_task, task_id, request.crew_config)
            
            return {
                "task_id": task_id,
                "status": "accepted",
                "streaming": request.streaming,
                "poll_url": f"/tasks/{task_id}",
                "stream_url": f"/tasks/{task_id}/stream" if request.streaming else None
            }

        @self.app.get("/tasks/{task_id}")
        async def get_task(task_id: str):
            """Obter status da tarefa"""
            if task_id not in self.tasks:
                raise HTTPException(status_code=404, detail="Task not found")
            
            return self.tasks[task_id]

        @self.app.get("/tasks/{task_id}/stream")
        async def stream_task(task_id: str):
            """Stream de eventos da tarefa"""
            if task_id not in self.tasks:
                raise HTTPException(status_code=404, detail="Task not found")
            
            async def event_generator():
                while True:
                    task = self.tasks.get(task_id)
                    if not task:
                        break
                    
                    if task["status"] == "completed":
                        yield f"data: {json.dumps({'type': 'complete', 'result': task.get('result')})}\n\n"
                        break
                    elif task["status"] == "failed":
                        yield f"data: {json.dumps({'type': 'error', 'error': task.get('error')})}\n\n"
                        break
                    elif task["status"] == "running":
                        if "progress" in task:
                            yield f"data: {json.dumps({'type': 'progress', 'progress': task['progress']})}\n\n"
                    
                    await asyncio.sleep(1)
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream"
            )

        @self.app.post("/decide")
        async def make_decision(request: DecisionRequest):
            """Tomada de decisão usando crew de agentes"""
            # Criar crew de decisão
            researcher = Agent(
                role="Decision Researcher",
                goal="Research context and options",
                backstory="Expert at analyzing decision contexts",
                verbose=True
            )
            
            analyst = Agent(
                role="Decision Analyst",
                goal="Analyze options and provide recommendations",
                backstory="Expert at weighing pros and cons",
                verbose=True
            )
            
            # Criar tarefas
            research_task = Task(
                description=f"Research context: {request.context}",
                agent=researcher,
                expected_output="Context analysis"
            )
            
            analysis_task = Task(
                description=f"Analyze options: {request.options}",
                agent=analyst,
                expected_output="Best option recommendation"
            )
            
            # Criar e executar crew
            crew = Crew(
                agents=[researcher, analyst],
                tasks=[research_task, analysis_task],
                process=Process.sequential
            )
            
            try:
                result = crew.kickoff()
                
                self.metrics["decisions_made"] += 1
                
                return {
                    "decision": request.options[0],  # Simplificado
                    "confidence": 0.85,
                    "reasoning": str(result),
                    "agent_id": self.agent_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"Decision error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/learn")
        async def learn(request: LearningRequest):
            """Aprendizagem contínua"""
            knowledge_item = {
                "id": str(uuid.uuid4()),
                "type": request.type,
                "data": request.data,
                "learned_at": datetime.utcnow().isoformat()
            }
            
            self.knowledge_base.append(knowledge_item)
            
            return {
                "success": True,
                "knowledge_id": knowledge_item["id"],
                "total_knowledge": len(self.knowledge_base)
            }

        @self.app.post("/adapt")
        async def adapt(request: Dict[str, Any]):
            """Auto-adaptação baseada em feedback"""
            return {
                "adapted": True,
                "adaptation": {
                    "type": "performance",
                    "adjustments": {
                        "crew_size": 0,
                        "process_type": "sequential"
                    }
                },
                "agent_id": self.agent_id
            }

        @self.app.post("/consensus")
        async def participate_consensus(request: ConsensusRequest):
            """Participar em consenso distribuído"""
            # Criar crew para avaliar proposta
            evaluator = Agent(
                role="Proposal Evaluator",
                goal="Evaluate proposals for consensus",
                backstory="Expert at proposal analysis"
            )
            
            eval_task = Task(
                description=f"Evaluate proposal: {request.proposal}",
                agent=evaluator,
                expected_output="Approve or reject with reasoning"
            )
            
            crew = Crew(
                agents=[evaluator],
                tasks=[eval_task],
                process=Process.sequential
            )
            
            try:
                result = crew.kickoff()
                
                vote = "approve" if "approve" in str(result).lower() else "reject"
                
                return {
                    "proposal_id": request.proposal.get("id"),
                    "agent_id": self.agent_id,
                    "vote": vote,
                    "confidence": 0.8,
                    "reasoning": str(result),
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"Consensus error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/crew/create")
        async def create_crew(request: Dict[str, Any]):
            """Criar nova crew customizada"""
            crew_id = f"crew-{uuid.uuid4().hex[:8]}"
            
            # Configurar agentes baseado na requisição
            agents = []
            for agent_config in request.get("agents", []):
                agent = Agent(
                    role=agent_config.get("role", "Generic Agent"),
                    goal=agent_config.get("goal", "Complete tasks"),
                    backstory=agent_config.get("backstory", "Experienced agent"),
                    verbose=True,
                    tools=[search_knowledge, analyze_data]
                )
                agents.append(agent)
            
            # Configurar tarefas
            tasks = []
            for task_config in request.get("tasks", []):
                # Encontrar agente responsável
                agent_index = task_config.get("agent_index", 0)
                if agent_index < len(agents):
                    task = Task(
                        description=task_config.get("description", ""),
                        agent=agents[agent_index],
                        expected_output=task_config.get("expected_output", "Result")
                    )
                    tasks.append(task)
            
            # Criar crew
            process_type = Process.sequential if request.get("process") == "sequential" else Process.hierarchical
            
            crew = Crew(
                agents=agents,
                tasks=tasks,
                process=process_type
            )
            
            self.crews[crew_id] = crew
            self.metrics["crews_created"] += 1
            
            return {
                "crew_id": crew_id,
                "agents": len(agents),
                "tasks": len(tasks),
                "process": str(process_type)
            }

        @self.app.get("/crew/list")
        async def list_crews():
            """Listar crews ativas"""
            return {
                "crews": list(self.crews.keys()),
                "count": len(self.crews)
            }

        @self.app.post("/crew/execute/{crew_id}")
        async def execute_crew(crew_id: str, request: Dict[str, Any]):
            """Executar crew específica"""
            if crew_id not in self.crews:
                raise HTTPException(status_code=404, detail="Crew not found")
            
            crew = self.crews[crew_id]
            
            try:
                inputs = request.get("inputs", {})
                result = crew.kickoff(inputs=inputs)
                
                return {
                    "crew_id": crew_id,
                    "result": str(result),
                    "status": "completed"
                }
            except Exception as e:
                logger.error(f"Crew execution error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket para comunicação P2P"""
            await websocket.accept()
            self.websockets.add(websocket)
            
            try:
                # Handshake
                await websocket.send_json({
                    "type": "connected",
                    "agent_id": self.agent_id,
                    "agent_type": self.agent_type
                })
                
                while True:
                    data = await websocket.receive_json()
                    await self.handle_ws_message(websocket, data)
                    
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                self.websockets.discard(websocket)

    async def execute_task(self, task_id: str, crew_config: Dict[str, Any]):
        """Executar tarefa usando CrewAI"""
        task = self.tasks[task_id]
        task["status"] = "running"
        task["started_at"] = datetime.utcnow().isoformat()
        
        try:
            # Criar crew padrão se não houver configuração
            if not crew_config:
                crew_config = {
                    "agents": [
                        {"role": "Researcher", "goal": "Research the topic"},
                        {"role": "Writer", "goal": "Write comprehensive response"}
                    ],
                    "process": "sequential"
                }
            
            # Criar agentes
            agents = []
            for agent_config in crew_config.get("agents", []):
                agent = Agent(
                    role=agent_config.get("role"),
                    goal=agent_config.get("goal"),
                    backstory=agent_config.get("backstory", "Expert agent"),
                    verbose=True
                )
                agents.append(agent)
            
            # Criar tarefa para crew
            crew_task = Task(
                description=task["task"],
                agent=agents[0] if agents else None,
                expected_output="Complete response"
            )
            
            # Criar e executar crew
            crew = Crew(
                agents=agents,
                tasks=[crew_task],
                process=Process.sequential
            )
            
            result = crew.kickoff(inputs=task.get("context", {}))
            
            task["result"] = str(result)
            task["status"] = "completed"
            task["completed_at"] = datetime.utcnow().isoformat()
            
            self.metrics["tasks_completed"] += 1
            
            # Notificar via WebSocket
            await self.broadcast_to_websockets({
                "type": "task_complete",
                "task_id": task_id,
                "result": task["result"]
            })
            
        except Exception as e:
            logger.error(f"Task execution error: {e}")
            task["status"] = "failed"
            task["error"] = str(e)
            task["failed_at"] = datetime.utcnow().isoformat()

    async def handle_ws_message(self, websocket: WebSocket, message: Dict[str, Any]):
        """Processar mensagem WebSocket"""
        msg_type = message.get("type")
        
        if msg_type == "subscribe_task":
            # Subscrever a atualizações de tarefa
            task_id = message.get("task_id")
            if task_id in self.tasks:
                await websocket.send_json({
                    "type": "task_status",
                    "task": self.tasks[task_id]
                })
        
        elif msg_type == "knowledge_share":
            # Receber conhecimento compartilhado
            self.knowledge_base.append({
                **message.get("data", {}),
                "from": "peer",
                "received_at": datetime.utcnow().isoformat()
            })

    async def broadcast_to_websockets(self, message: Dict[str, Any]):
        """Broadcast mensagem para todos os WebSockets conectados"""
        disconnected = set()
        
        for ws in self.websockets:
            try:
                await ws.send_json(message)
            except:
                disconnected.add(ws)
        
        # Remover conexões desconectadas
        self.websockets -= disconnected

    def _calculate_uptime(self) -> float:
        """Calcular uptime em segundos"""
        started = datetime.fromisoformat(self.metrics["started_at"])
        return (datetime.utcnow() - started).total_seconds()

# Criar instância global
agent = CrewA2AAgent()
app = agent.app

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8002))
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )