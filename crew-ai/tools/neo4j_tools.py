"""
Neo4j Integration Tools for CrewAI
Provides persistence, querying, and learning capabilities
"""

import os
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field
from crewai_tools import BaseTool
from neo4j import GraphDatabase
import hashlib


class Neo4jConnection:
    """Singleton connection to Neo4j database"""
    _instance = None
    _driver = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._driver is None:
            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            username = os.getenv("NEO4J_USERNAME", "neo4j")
            password = os.getenv("NEO4J_PASSWORD", "password")
            
            try:
                self._driver = GraphDatabase.driver(uri, auth=(username, password))
                # Test connection
                with self._driver.session() as session:
                    session.run("RETURN 1")
                print(f"✅ Connected to Neo4j at {uri}")
            except Exception as e:
                print(f"❌ Failed to connect to Neo4j: {e}")
                self._driver = None
    
    def get_session(self):
        if self._driver:
            return self._driver.session()
        return None
    
    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None


class Neo4jMemoryToolInput(BaseModel):
    """Input schema for Neo4jMemoryTool"""
    agent_name: str = Field(description="Name of the agent storing memory")
    memory_type: str = Field(description="Type of memory (decision, knowledge, context)")
    content: Dict[str, Any] = Field(description="Content to store")
    tags: Optional[List[str]] = Field(default=[], description="Tags for categorization")


class Neo4jMemoryTool(BaseTool):
    """Tool for persisting agent decisions and knowledge to Neo4j"""
    
    name: str = "neo4j_memory"
    description: str = "Store agent decisions, knowledge, and context in Neo4j graph database"
    args_schema: Type[BaseModel] = Neo4jMemoryToolInput
    
    def _run(self, agent_name: str, memory_type: str, content: Dict[str, Any], tags: List[str] = []) -> str:
        """Store memory in Neo4j"""
        db = Neo4jConnection()
        session = db.get_session()
        
        if not session:
            return "Failed to connect to Neo4j"
        
        try:
            # Generate unique ID for memory
            memory_id = hashlib.md5(
                f"{agent_name}{memory_type}{str(content)}{time.time()}".encode()
            ).hexdigest()[:12]
            
            # Create memory node
            result = session.run(
                """
                CREATE (m:Memory:AgentMemory {
                    id: $id,
                    agent_name: $agent_name,
                    type: $memory_type,
                    content: $content,
                    tags: $tags,
                    created_at: datetime(),
                    timestamp: $timestamp
                })
                RETURN m
                """,
                id=memory_id,
                agent_name=agent_name,
                memory_type=memory_type,
                content=json.dumps(content),
                tags=tags,
                timestamp=time.time()
            )
            
            # Link to agent if exists
            session.run(
                """
                MATCH (a:Agent {name: $agent_name})
                MATCH (m:Memory {id: $memory_id})
                CREATE (a)-[:CREATED_MEMORY]->(m)
                """,
                agent_name=agent_name,
                memory_id=memory_id
            )
            
            return f"Memory stored with ID: {memory_id}"
            
        except Exception as e:
            return f"Error storing memory: {str(e)}"
        finally:
            session.close()


class Neo4jQueryToolInput(BaseModel):
    """Input schema for Neo4jQueryTool"""
    query_type: str = Field(description="Type of query (agent_history, task_patterns, decisions)")
    filters: Optional[Dict[str, Any]] = Field(default={}, description="Filters for the query")
    limit: Optional[int] = Field(default=10, description="Maximum results to return")


class Neo4jQueryTool(BaseTool):
    """Tool for querying historical data and patterns from Neo4j"""
    
    name: str = "neo4j_query"
    description: str = "Query historical execution patterns, decisions, and knowledge from Neo4j"
    args_schema: Type[BaseModel] = Neo4jQueryToolInput
    
    def _run(self, query_type: str, filters: Dict[str, Any] = {}, limit: int = 10) -> str:
        """Query data from Neo4j"""
        db = Neo4jConnection()
        session = db.get_session()
        
        if not session:
            return "Failed to connect to Neo4j"
        
        try:
            if query_type == "agent_history":
                agent_name = filters.get("agent_name", "")
                result = session.run(
                    """
                    MATCH (m:Memory)
                    WHERE m.agent_name = $agent_name OR $agent_name = ''
                    RETURN m
                    ORDER BY m.created_at DESC
                    LIMIT $limit
                    """,
                    agent_name=agent_name,
                    limit=limit
                )
                
            elif query_type == "task_patterns":
                result = session.run(
                    """
                    MATCH (t:Task)-[:EXECUTED_BY]->(a:Agent)
                    OPTIONAL MATCH (t)-[:PRODUCED]->(o:Output)
                    RETURN t.name as task, a.name as agent, 
                           avg(t.execution_time) as avg_time,
                           count(o) as outputs
                    ORDER BY avg_time DESC
                    LIMIT $limit
                    """,
                    limit=limit
                )
                
            elif query_type == "decisions":
                memory_type = filters.get("memory_type", "decision")
                result = session.run(
                    """
                    MATCH (m:Memory {type: $memory_type})
                    RETURN m
                    ORDER BY m.created_at DESC
                    LIMIT $limit
                    """,
                    memory_type=memory_type,
                    limit=limit
                )
            else:
                return f"Unknown query type: {query_type}"
            
            # Format results
            records = []
            for record in result:
                records.append({k: v for k, v in record.items()})
            
            return json.dumps(records, default=str, indent=2)
            
        except Exception as e:
            return f"Error querying Neo4j: {str(e)}"
        finally:
            session.close()


class Neo4jRelationshipToolInput(BaseModel):
    """Input schema for Neo4jRelationshipTool"""
    source_type: str = Field(description="Type of source node (agent, task, memory)")
    source_id: str = Field(description="ID of source node")
    target_type: str = Field(description="Type of target node")
    target_id: str = Field(description="ID of target node")
    relationship: str = Field(description="Type of relationship")
    properties: Optional[Dict[str, Any]] = Field(default={}, description="Relationship properties")


class Neo4jRelationshipTool(BaseTool):
    """Tool for creating relationships between tasks, agents, and memories"""
    
    name: str = "neo4j_relationship"
    description: str = "Create and manage relationships between tasks, agents, and memories in Neo4j"
    args_schema: Type[BaseModel] = Neo4jRelationshipToolInput
    
    def _run(self, source_type: str, source_id: str, target_type: str, 
             target_id: str, relationship: str, properties: Dict[str, Any] = {}) -> str:
        """Create relationship in Neo4j"""
        db = Neo4jConnection()
        session = db.get_session()
        
        if not session:
            return "Failed to connect to Neo4j"
        
        try:
            # Build dynamic query based on node types
            query = f"""
            MATCH (source:{source_type.capitalize()} {{id: $source_id}})
            MATCH (target:{target_type.capitalize()} {{id: $target_id}})
            CREATE (source)-[r:{relationship.upper()} $properties]->(target)
            RETURN r
            """
            
            result = session.run(
                query,
                source_id=source_id,
                target_id=target_id,
                properties=properties
            )
            
            if result.single():
                return f"Relationship {relationship} created between {source_id} and {target_id}"
            else:
                return "Failed to create relationship"
                
        except Exception as e:
            return f"Error creating relationship: {str(e)}"
        finally:
            session.close()


class Neo4jMetricsToolInput(BaseModel):
    """Input schema for Neo4jMetricsTool"""
    metric_type: str = Field(description="Type of metric (execution_time, success_rate, resource_usage)")
    entity_type: str = Field(description="Entity type (agent, task, crew)")
    entity_id: str = Field(description="Entity identifier")
    value: float = Field(description="Metric value")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")


class Neo4jMetricsTool(BaseTool):
    """Tool for storing and analyzing performance metrics"""
    
    name: str = "neo4j_metrics"
    description: str = "Store and analyze performance metrics for agents, tasks, and crews"
    args_schema: Type[BaseModel] = Neo4jMetricsToolInput
    
    def _run(self, metric_type: str, entity_type: str, entity_id: str, 
             value: float, metadata: Dict[str, Any] = {}) -> str:
        """Store metrics in Neo4j"""
        db = Neo4jConnection()
        session = db.get_session()
        
        if not session:
            return "Failed to connect to Neo4j"
        
        try:
            # Create metric node
            result = session.run(
                """
                CREATE (m:Metric {
                    id: $id,
                    type: $metric_type,
                    entity_type: $entity_type,
                    entity_id: $entity_id,
                    value: $value,
                    metadata: $metadata,
                    timestamp: datetime()
                })
                RETURN m
                """,
                id=f"{entity_id}_{metric_type}_{int(time.time())}",
                metric_type=metric_type,
                entity_type=entity_type,
                entity_id=entity_id,
                value=value,
                metadata=json.dumps(metadata)
            )
            
            # Calculate aggregates
            agg_result = session.run(
                """
                MATCH (m:Metric {entity_id: $entity_id, type: $metric_type})
                RETURN avg(m.value) as avg_value, 
                       min(m.value) as min_value,
                       max(m.value) as max_value,
                       count(m) as count
                """,
                entity_id=entity_id,
                metric_type=metric_type
            )
            
            agg = agg_result.single()
            return f"Metric stored. Stats - Avg: {agg['avg_value']:.2f}, Min: {agg['min_value']:.2f}, Max: {agg['max_value']:.2f}, Count: {agg['count']}"
            
        except Exception as e:
            return f"Error storing metric: {str(e)}"
        finally:
            session.close()


class Neo4jLearningToolInput(BaseModel):
    """Input schema for Neo4jLearningTool"""
    pattern_type: str = Field(description="Type of pattern (success, failure, optimization)")
    context: Dict[str, Any] = Field(description="Context of the pattern")
    outcome: str = Field(description="Outcome or result")
    score: Optional[float] = Field(default=0.0, description="Quality score")


class Neo4jLearningTool(BaseTool):
    """Tool for continuous learning and pattern detection"""
    
    name: str = "neo4j_learning"
    description: str = "Store successful patterns and learn from historical executions"
    args_schema: Type[BaseModel] = Neo4jLearningToolInput
    
    def _run(self, pattern_type: str, context: Dict[str, Any], 
             outcome: str, score: float = 0.0) -> str:
        """Store learning patterns in Neo4j"""
        db = Neo4jConnection()
        session = db.get_session()
        
        if not session:
            return "Failed to connect to Neo4j"
        
        try:
            # Store pattern
            pattern_id = hashlib.md5(
                f"{pattern_type}{str(context)}{outcome}".encode()
            ).hexdigest()[:12]
            
            result = session.run(
                """
                MERGE (p:Pattern {id: $pattern_id})
                ON CREATE SET 
                    p.type = $pattern_type,
                    p.context = $context,
                    p.outcome = $outcome,
                    p.score = $score,
                    p.occurrences = 1,
                    p.created_at = datetime()
                ON MATCH SET
                    p.occurrences = p.occurrences + 1,
                    p.score = (p.score * p.occurrences + $score) / (p.occurrences + 1),
                    p.last_seen = datetime()
                RETURN p
                """,
                pattern_id=pattern_id,
                pattern_type=pattern_type,
                context=json.dumps(context),
                outcome=outcome,
                score=score
            )
            
            # Find similar patterns
            similar = session.run(
                """
                MATCH (p:Pattern {type: $pattern_type})
                WHERE p.score > 0.7 AND p.id <> $pattern_id
                RETURN p.outcome, p.score, p.occurrences
                ORDER BY p.score DESC
                LIMIT 3
                """,
                pattern_type=pattern_type,
                pattern_id=pattern_id
            )
            
            recommendations = []
            for record in similar:
                recommendations.append(f"{record['outcome']} (score: {record['score']:.2f})")
            
            if recommendations:
                return f"Pattern stored. Similar successful patterns: {', '.join(recommendations)}"
            else:
                return f"Pattern stored with ID: {pattern_id}"
                
        except Exception as e:
            return f"Error in learning tool: {str(e)}"
        finally:
            session.close()


# Export all tools
__all__ = [
    'Neo4jMemoryTool',
    'Neo4jQueryTool',
    'Neo4jRelationshipTool',
    'Neo4jMetricsTool',
    'Neo4jLearningTool',
    'Neo4jConnection'
]