// Dashboard Queries for Neo4j Browser Visualization
// Execute these queries in Neo4j Browser to visualize CrewAI execution

// 1. Full Execution Graph - Shows complete workflow
MATCH path = (e:Execution)-[*]-(connected)
WHERE e.project = 'Conductor-Baku'
RETURN path
LIMIT 500;

// 2. Agent Performance Metrics
MATCH (e:Execution)-[:HAS_AGENT]->(a:ExecutionAgent)
MATCH (a)-[:EXECUTES]->(t:ExecutionTask)
RETURN a.name as Agent, 
       count(t) as TasksExecuted,
       avg(t.execution_time) as AvgExecutionTime,
       sum(CASE WHEN t.success THEN 1 ELSE 0 END) as SuccessfulTasks,
       sum(CASE WHEN NOT t.success THEN 1 ELSE 0 END) as FailedTasks,
       (toFloat(sum(CASE WHEN t.success THEN 1 ELSE 0 END)) / toFloat(count(t))) * 100 as SuccessRate
ORDER BY TasksExecuted DESC;

// 3. Task Dependency Graph - Shows task dependencies and execution flow
MATCH (t1:ExecutionTask)-[:DEPENDS_ON]->(t2:ExecutionTask)
RETURN t1, t2;

// 4. Bottleneck Analysis - Identify slow tasks
MATCH (t:ExecutionTask)
WHERE t.execution_time > 30
RETURN t.description as Task,
       t.agent as Agent,
       t.execution_time as ExecutionTime,
       t.status as Status,
       t.started_at as StartTime
ORDER BY t.execution_time DESC
LIMIT 10;

// 5. Decision Tree - Visualize agent decisions
MATCH (a:ExecutionAgent)-[:MADE_DECISION]->(d:Decision)
RETURN a.name as Agent,
       d.action as Action,
       d.thought as Thought,
       d.timestamp as Time
ORDER BY d.timestamp;

// 6. Pattern Learning Graph - Success and failure patterns
MATCH (p:Pattern)
RETURN p.type as PatternType,
       p.score as Score,
       p.occurrences as Occurrences,
       p.outcome as Outcome,
       p.created_at as FirstSeen,
       p.last_seen as LastSeen
ORDER BY p.occurrences DESC, p.score DESC;

// 7. Memory Network - Agent memories and relationships
MATCH (m:Memory)
OPTIONAL MATCH (m)-[r]-(connected)
RETURN m, r, connected
LIMIT 100;

// 8. Metrics Timeline - Performance over time
MATCH (m:Metric)
WHERE m.type = 'execution_time'
RETURN m.entity_id as Task,
       m.value as ExecutionTime,
       m.timestamp as Time
ORDER BY m.timestamp;

// 9. Agent Collaboration Network - How agents work together
MATCH (a1:ExecutionAgent)-[:EXECUTES]->(t:ExecutionTask)
WITH a1, collect(DISTINCT t) as tasks
MATCH (a2:ExecutionAgent)-[:EXECUTES]->(t2:ExecutionTask)
WHERE a1 <> a2 AND t2 IN tasks
RETURN a1.name as Agent1, a2.name as Agent2, count(t2) as SharedTasks
ORDER BY SharedTasks DESC;

// 10. Execution Summary Dashboard
MATCH (e:Execution)
WHERE e.project = 'Conductor-Baku'
OPTIONAL MATCH (e)-[:HAS_TASK]->(t:ExecutionTask)
OPTIONAL MATCH (e)-[:HAS_AGENT]->(a:ExecutionAgent)
OPTIONAL MATCH (a)-[:MADE_DECISION]->(d:Decision)
RETURN e.id as ExecutionID,
       e.status as Status,
       e.started_at as StartTime,
       e.completed_at as EndTime,
       e.process_type as ProcessType,
       count(DISTINCT t) as TotalTasks,
       count(DISTINCT a) as TotalAgents,
       count(DISTINCT d) as TotalDecisions,
       e.task_stats.success_rate as SuccessRate,
       e.task_stats.avg_execution_time as AvgTaskTime
ORDER BY e.started_at DESC
LIMIT 10;

// 11. Real-time Task Status Monitor
MATCH (t:ExecutionTask)
WHERE t.status = 'running'
RETURN t.description as Task,
       t.agent as Agent,
       t.started_at as StartTime,
       duration.between(t.started_at, datetime()).seconds as RunningForSeconds
ORDER BY RunningForSeconds DESC;

// 12. Knowledge Graph Overview - Project structure
MATCH (p:Project {name: 'Conductor-Baku'})
OPTIONAL MATCH (p)-[:HAS_COMPONENT]->(c:AgentEntity)
OPTIONAL MATCH (p)-[:USES_CLUSTER]->(cl:Cluster)
OPTIONAL MATCH (cl)-[:CONTAINS]->(a:Agent)
RETURN p, c, cl, a;

// 13. Learning Effectiveness - Track improvement over time
MATCH (p:Pattern)
WHERE p.type = 'success'
WITH date(p.created_at) as day, avg(p.score) as avg_score, count(p) as pattern_count
RETURN day, avg_score, pattern_count
ORDER BY day;

// 14. Agent Specialization Analysis
MATCH (a:Agent)
OPTIONAL MATCH (a)-[:HAS_CAPABILITY]->(cap:Capability)
OPTIONAL MATCH (a)-[:INTEGRATES_WITH]->(other:Agent)
RETURN a.name as Agent,
       a.type as Type,
       collect(DISTINCT cap.name) as Capabilities,
       collect(DISTINCT other.name) as Integrations,
       a.cluster as Cluster
ORDER BY size(Capabilities) DESC;

// 15. Critical Path Analysis - Longest execution chains
MATCH path = (start:ExecutionTask)-[:DEPENDS_ON*]->(end:ExecutionTask)
WHERE NOT (end)-[:DEPENDS_ON]->()
WITH path, reduce(total = 0, t IN nodes(path) | total + t.execution_time) as totalTime
RETURN path, totalTime
ORDER BY totalTime DESC
LIMIT 5;