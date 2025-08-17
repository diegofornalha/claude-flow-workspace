"""
Telemetry Callbacks for CrewAI with Neo4j Integration
Tracks execution, performance, and decision-making in real-time
"""

import time
import json
import traceback
from datetime import datetime
from typing import Any, Dict, Optional
from crewai.agent import Agent
from crewai.task import Task
from crewai.crew import Crew
from neo4j import GraphDatabase
import os


class Neo4jTelemetryCallbacks:
    """Callbacks for tracking CrewAI execution in Neo4j"""
    
    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        username = os.getenv("NEO4J_USERNAME", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        
        try:
            self.driver = GraphDatabase.driver(uri, auth=(username, password))
            self.execution_id = f"exec_{int(time.time())}"
            self._initialize_execution()
            print(f"✅ Telemetry initialized with execution ID: {self.execution_id}")
        except Exception as e:
            print(f"❌ Failed to initialize telemetry: {e}")
            self.driver = None
    
    def _initialize_execution(self):
        """Create execution node in Neo4j"""
        with self.driver.session() as session:
            session.run(
                """
                CREATE (e:Execution {
                    id: $exec_id,
                    started_at: datetime(),
                    status: 'running',
                    project: 'Conductor-Baku'
                })
                """,
                exec_id=self.execution_id
            )
    
    def on_crew_start(self, crew: Crew, inputs: Dict[str, Any]) -> None:
        """Called when crew execution starts"""
        if not self.driver:
            return
            
        with self.driver.session() as session:
            session.run(
                """
                MATCH (e:Execution {id: $exec_id})
                SET e.crew_config = $config,
                    e.inputs = $inputs,
                    e.process_type = $process_type,
                    e.agent_count = $agent_count
                """,
                exec_id=self.execution_id,
                config=json.dumps({
                    "verbose": crew.verbose,
                    "max_rpm": crew.max_rpm if hasattr(crew, 'max_rpm') else None,
                    "share_crew": crew.share_crew if hasattr(crew, 'share_crew') else False
                }),
                inputs=json.dumps(inputs),
                process_type=str(crew.process),
                agent_count=len(crew.agents)
            )
            
            # Create nodes for each agent
            for agent in crew.agents:
                session.run(
                    """
                    CREATE (a:ExecutionAgent {
                        id: $agent_id,
                        name: $name,
                        role: $role,
                        goal: $goal,
                        backstory: $backstory,
                        execution_id: $exec_id
                    })
                    WITH a
                    MATCH (e:Execution {id: $exec_id})
                    CREATE (e)-[:HAS_AGENT]->(a)
                    """,
                    agent_id=f"{self.execution_id}_{agent.role}",
                    name=agent.role,
                    role=agent.role,
                    goal=agent.goal,
                    backstory=agent.backstory[:500] if agent.backstory else "",
                    exec_id=self.execution_id
                )
    
    def on_task_start(self, task: Task, agent: Agent) -> None:
        """Called when a task starts"""
        if not self.driver:
            return
            
        task_id = f"{self.execution_id}_{task.description[:30]}_{int(time.time())}"
        task.telemetry_id = task_id  # Store ID for later use
        task.start_time = time.time()
        
        with self.driver.session() as session:
            # Create task node
            session.run(
                """
                CREATE (t:ExecutionTask {
                    id: $task_id,
                    description: $description,
                    expected_output: $expected_output,
                    agent: $agent,
                    started_at: datetime(),
                    status: 'running',
                    execution_id: $exec_id
                })
                WITH t
                MATCH (e:Execution {id: $exec_id})
                CREATE (e)-[:HAS_TASK]->(t)
                WITH t
                MATCH (a:ExecutionAgent {id: $agent_id})
                CREATE (a)-[:EXECUTES]->(t)
                """,
                task_id=task_id,
                description=task.description,
                expected_output=task.expected_output,
                agent=agent.role,
                exec_id=self.execution_id,
                agent_id=f"{self.execution_id}_{agent.role}"
            )
            
            # Track dependencies if any
            if hasattr(task, 'dependencies') and task.dependencies:
                for dep in task.dependencies:
                    if hasattr(dep, 'telemetry_id'):
                        session.run(
                            """
                            MATCH (t1:ExecutionTask {id: $task_id})
                            MATCH (t2:ExecutionTask {id: $dep_id})
                            CREATE (t1)-[:DEPENDS_ON]->(t2)
                            """,
                            task_id=task_id,
                            dep_id=dep.telemetry_id
                        )
    
    def on_task_complete(self, task: Task, output: Any) -> None:
        """Called when a task completes"""
        if not self.driver:
            return
            
        if not hasattr(task, 'telemetry_id'):
            return
            
        execution_time = time.time() - task.start_time if hasattr(task, 'start_time') else 0
        
        with self.driver.session() as session:
            # Update task with results
            session.run(
                """
                MATCH (t:ExecutionTask {id: $task_id})
                SET t.status = 'completed',
                    t.completed_at = datetime(),
                    t.execution_time = $exec_time,
                    t.output = $output,
                    t.success = true
                """,
                task_id=task.telemetry_id,
                exec_time=execution_time,
                output=str(output)[:1000]  # Limit output size
            )
            
            # Store as successful pattern for learning
            session.run(
                """
                CREATE (p:Pattern {
                    id: $pattern_id,
                    type: 'success',
                    task_description: $description,
                    execution_time: $exec_time,
                    output_summary: $output,
                    created_at: datetime(),
                    score: $score
                })
                WITH p
                MATCH (t:ExecutionTask {id: $task_id})
                CREATE (t)-[:PRODUCED_PATTERN]->(p)
                """,
                pattern_id=f"pattern_{task.telemetry_id}",
                description=task.description,
                exec_time=execution_time,
                output=str(output)[:500],
                score=1.0 if execution_time < 30 else 0.7,  # Score based on speed
                task_id=task.telemetry_id
            )
            
            # Create metric node
            session.run(
                """
                CREATE (m:Metric {
                    id: $metric_id,
                    type: 'execution_time',
                    entity_type: 'task',
                    entity_id: $task_id,
                    value: $exec_time,
                    timestamp: datetime()
                })
                """,
                metric_id=f"metric_{task.telemetry_id}",
                task_id=task.telemetry_id,
                exec_time=execution_time
            )
    
    def on_task_error(self, task: Task, error: Exception) -> None:
        """Called when a task fails"""
        if not self.driver:
            return
            
        if not hasattr(task, 'telemetry_id'):
            return
            
        with self.driver.session() as session:
            # Update task with error
            session.run(
                """
                MATCH (t:ExecutionTask {id: $task_id})
                SET t.status = 'failed',
                    t.error = $error,
                    t.error_trace = $trace,
                    t.completed_at = datetime(),
                    t.success = false
                """,
                task_id=task.telemetry_id,
                error=str(error),
                trace=traceback.format_exc()
            )
            
            # Store as failure pattern for learning
            session.run(
                """
                CREATE (p:Pattern {
                    id: $pattern_id,
                    type: 'failure',
                    task_description: $description,
                    error: $error,
                    created_at: datetime(),
                    score: -1.0
                })
                WITH p
                MATCH (t:ExecutionTask {id: $task_id})
                CREATE (t)-[:PRODUCED_PATTERN]->(p)
                """,
                pattern_id=f"failure_{task.telemetry_id}",
                description=task.description,
                error=str(error),
                task_id=task.telemetry_id
            )
    
    def on_agent_action(self, agent: Agent, action: str, thought: str, **kwargs) -> None:
        """Called when an agent takes an action"""
        if not self.driver:
            return
            
        with self.driver.session() as session:
            # Create decision node
            session.run(
                """
                CREATE (d:Decision {
                    id: $decision_id,
                    agent: $agent,
                    action: $action,
                    thought: $thought,
                    context: $context,
                    timestamp: datetime(),
                    execution_id: $exec_id
                })
                WITH d
                MATCH (a:ExecutionAgent {id: $agent_id})
                CREATE (a)-[:MADE_DECISION]->(d)
                """,
                decision_id=f"decision_{self.execution_id}_{int(time.time()*1000)}",
                agent=agent.role,
                action=action,
                thought=thought,
                context=json.dumps(kwargs),
                exec_id=self.execution_id,
                agent_id=f"{self.execution_id}_{agent.role}"
            )
    
    def on_crew_complete(self, crew: Crew, output: Any) -> None:
        """Called when crew execution completes"""
        if not self.driver:
            return
            
        with self.driver.session() as session:
            # Update execution status
            session.run(
                """
                MATCH (e:Execution {id: $exec_id})
                SET e.status = 'completed',
                    e.completed_at = datetime(),
                    e.output = $output
                WITH e
                MATCH (e)-[:HAS_TASK]->(t:ExecutionTask)
                WITH e, 
                     count(CASE WHEN t.status = 'completed' THEN 1 END) as completed,
                     count(CASE WHEN t.status = 'failed' THEN 1 END) as failed,
                     count(t) as total,
                     avg(t.execution_time) as avg_time
                SET e.task_stats = {
                    completed: completed,
                    failed: failed,
                    total: total,
                    avg_execution_time: avg_time,
                    success_rate: toFloat(completed) / toFloat(total)
                }
                """,
                exec_id=self.execution_id,
                output=str(output)[:2000]
            )
            
            # Analyze bottlenecks
            bottlenecks = session.run(
                """
                MATCH (e:Execution {id: $exec_id})-[:HAS_TASK]->(t:ExecutionTask)
                WHERE t.execution_time > 30
                RETURN t.description as task, 
                       t.agent as agent,
                       t.execution_time as time
                ORDER BY t.execution_time DESC
                LIMIT 5
                """,
                exec_id=self.execution_id
            )
            
            print("\n📊 Execution Complete - Bottleneck Analysis:")
            for record in bottlenecks:
                print(f"  ⚠️ {record['task'][:50]} - {record['time']:.2f}s ({record['agent']})")
    
    def get_execution_graph(self) -> str:
        """Get Cypher query to visualize execution in Neo4j Browser"""
        return f"""
        // Visualize execution graph for {self.execution_id}
        MATCH path = (e:Execution {{id: '{self.execution_id}'}})-[*]-(connected)
        RETURN path
        """
    
    def get_metrics_dashboard(self) -> Dict[str, Any]:
        """Get metrics for the current execution"""
        if not self.driver:
            return {}
            
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e:Execution {id: $exec_id})
                OPTIONAL MATCH (e)-[:HAS_TASK]->(t:ExecutionTask)
                OPTIONAL MATCH (e)-[:HAS_AGENT]->(a:ExecutionAgent)
                OPTIONAL MATCH (a)-[:MADE_DECISION]->(d:Decision)
                RETURN e.status as status,
                       e.started_at as started,
                       e.completed_at as completed,
                       count(DISTINCT t) as total_tasks,
                       count(DISTINCT a) as total_agents,
                       count(DISTINCT d) as total_decisions,
                       avg(t.execution_time) as avg_task_time,
                       max(t.execution_time) as max_task_time,
                       min(t.execution_time) as min_task_time
                """,
                exec_id=self.execution_id
            )
            
            record = result.single()
            if record:
                return dict(record)
            return {}
    
    def close(self):
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()


class TelemetryMiddleware:
    """Middleware to automatically inject telemetry into CrewAI"""
    
    def __init__(self, callbacks: Neo4jTelemetryCallbacks):
        self.callbacks = callbacks
    
    def wrap_crew(self, crew: Crew) -> Crew:
        """Wrap crew with telemetry callbacks"""
        original_kickoff = crew.kickoff
        
        def wrapped_kickoff(inputs: Dict[str, Any] = {}) -> Any:
            self.callbacks.on_crew_start(crew, inputs)
            try:
                result = original_kickoff(inputs)
                self.callbacks.on_crew_complete(crew, result)
                return result
            except Exception as e:
                self.callbacks.on_crew_complete(crew, f"Error: {e}")
                raise
        
        crew.kickoff = wrapped_kickoff
        
        # Wrap each agent
        for agent in crew.agents:
            self._wrap_agent(agent)
        
        # Wrap each task
        for task in crew.tasks:
            self._wrap_task(task)
        
        return crew
    
    def _wrap_agent(self, agent: Agent):
        """Wrap agent with telemetry"""
        if hasattr(agent, 'execute'):
            original_execute = agent.execute
            
            def wrapped_execute(task: Task) -> Any:
                self.callbacks.on_task_start(task, agent)
                try:
                    result = original_execute(task)
                    self.callbacks.on_task_complete(task, result)
                    return result
                except Exception as e:
                    self.callbacks.on_task_error(task, e)
                    raise
            
            agent.execute = wrapped_execute
    
    def _wrap_task(self, task: Task):
        """Wrap task with telemetry"""
        # Tasks are executed by agents, so we track them there
        pass


# Convenience function
def setup_telemetry(crew: Crew) -> Neo4jTelemetryCallbacks:
    """Setup telemetry for a crew"""
    callbacks = Neo4jTelemetryCallbacks()
    middleware = TelemetryMiddleware(callbacks)
    middleware.wrap_crew(crew)
    return callbacks