"""
MCP Neo4j Integration for CrewAI
Connects MCP server capabilities with CrewAI agents
"""

import os
import json
import subprocess
import time
from typing import Any, Dict, List, Optional
from datetime import datetime
from neo4j import GraphDatabase


class MCPNeo4jBridge:
    """Bridge between MCP Neo4j server and CrewAI"""
    
    def __init__(self):
        self.mcp_server_path = "/Users/2a/.claude/mcp-neo4j-agent-memory/build/index.js"
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_username = os.getenv("NEO4J_USERNAME", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
        
        # Direct Neo4j connection for verification
        try:
            self.driver = GraphDatabase.driver(
                self.neo4j_uri, 
                auth=(self.neo4j_username, self.neo4j_password)
            )
            print("✅ MCP Bridge connected to Neo4j")
        except Exception as e:
            print(f"❌ Failed to connect to Neo4j: {e}")
            self.driver = None
    
    def sync_agent_memories(self, agent_name: str, memories: List[Dict[str, Any]]):
        """Sync agent memories with MCP Neo4j server"""
        if not self.driver:
            return
        
        with self.driver.session() as session:
            for memory in memories:
                # Create memory node using MCP format
                session.run(
                    """
                    CREATE (m:Memory {
                        name: $name,
                        agent: $agent,
                        type: $type,
                        content: $content,
                        created_at: datetime(),
                        mcp_synced: true
                    })
                    WITH m
                    MATCH (a:Agent {name: $agent})
                    CREATE (a)-[:HAS_MEMORY]->(m)
                    """,
                    name=memory.get('name', f"{agent_name}_memory_{int(time.time())}"),
                    agent=agent_name,
                    type=memory.get('type', 'general'),
                    content=json.dumps(memory.get('content', {}))
                )
    
    def get_agent_context(self, agent_name: str, depth: int = 1) -> Dict[str, Any]:
        """Get agent context from Neo4j including memories and relationships"""
        if not self.driver:
            return {}
        
        context = {
            'agent': agent_name,
            'memories': [],
            'relationships': [],
            'patterns': []
        }
        
        with self.driver.session() as session:
            # Get agent memories
            memories_result = session.run(
                """
                MATCH (a:Agent {name: $agent})-[:HAS_MEMORY]->(m:Memory)
                RETURN m.name as name, m.type as type, m.content as content
                ORDER BY m.created_at DESC
                LIMIT 10
                """,
                agent=agent_name
            )
            
            for record in memories_result:
                context['memories'].append({
                    'name': record['name'],
                    'type': record['type'],
                    'content': json.loads(record['content']) if record['content'] else {}
                })
            
            # Get agent relationships
            rel_result = session.run(
                """
                MATCH (a:Agent {name: $agent})-[r]-(connected)
                WHERE NOT type(r) IN ['HAS_MEMORY', 'BELONGS_TO']
                RETURN type(r) as relationship, 
                       labels(connected)[0] as connected_type,
                       connected.name as connected_name
                LIMIT 20
                """,
                agent=agent_name
            )
            
            for record in rel_result:
                context['relationships'].append({
                    'type': record['relationship'],
                    'with': record['connected_name'],
                    'entity_type': record['connected_type']
                })
            
            # Get relevant patterns
            pattern_result = session.run(
                """
                MATCH (a:Agent {name: $agent})-[:EXECUTES]->(t:ExecutionTask)
                MATCH (t)-[:PRODUCED_PATTERN]->(p:Pattern)
                WHERE p.score > 0.5
                RETURN p.type as type, p.outcome as outcome, p.score as score
                ORDER BY p.score DESC
                LIMIT 5
                """,
                agent=agent_name
            )
            
            for record in pattern_result:
                context['patterns'].append({
                    'type': record['type'],
                    'outcome': record['outcome'],
                    'score': record['score']
                })
        
        return context
    
    def create_memory_connection(self, source_id: str, target_id: str, 
                                relationship_type: str, properties: Dict = {}):
        """Create connection between memories using MCP format"""
        if not self.driver:
            return
        
        with self.driver.session() as session:
            session.run(
                """
                MATCH (source {id: $source_id})
                MATCH (target {id: $target_id})
                CREATE (source)-[r:$rel_type $properties]->(target)
                """,
                source_id=source_id,
                target_id=target_id,
                rel_type=relationship_type.upper(),
                properties=properties
            )
    
    def search_memories(self, query: str, agent_filter: Optional[str] = None, 
                       limit: int = 10) -> List[Dict[str, Any]]:
        """Search memories across agents"""
        if not self.driver:
            return []
        
        results = []
        
        with self.driver.session() as session:
            # Build query based on filters
            cypher_query = """
                MATCH (m:Memory)
                WHERE toLower(m.content) CONTAINS toLower($query)
            """
            
            if agent_filter:
                cypher_query += " AND m.agent = $agent"
            
            cypher_query += """
                RETURN m.name as name, m.agent as agent, 
                       m.type as type, m.content as content,
                       m.created_at as created_at
                ORDER BY m.created_at DESC
                LIMIT $limit
            """
            
            params = {'query': query, 'limit': limit}
            if agent_filter:
                params['agent'] = agent_filter
            
            result = session.run(cypher_query, **params)
            
            for record in result:
                results.append({
                    'name': record['name'],
                    'agent': record['agent'],
                    'type': record['type'],
                    'content': json.loads(record['content']) if record['content'] else {},
                    'created_at': str(record['created_at'])
                })
        
        return results
    
    def sync_execution_to_mcp(self, execution_id: str):
        """Sync CrewAI execution data to MCP format"""
        if not self.driver:
            return
        
        with self.driver.session() as session:
            # Get execution summary
            exec_result = session.run(
                """
                MATCH (e:Execution {id: $exec_id})
                OPTIONAL MATCH (e)-[:HAS_TASK]->(t:ExecutionTask)
                OPTIONAL MATCH (e)-[:HAS_AGENT]->(a:ExecutionAgent)
                RETURN e, collect(DISTINCT t) as tasks, collect(DISTINCT a) as agents
                """,
                exec_id=execution_id
            ).single()
            
            if not exec_result:
                return
            
            execution = exec_result['e']
            
            # Create MCP-compatible memory for execution
            session.run(
                """
                CREATE (m:Memory {
                    name: $name,
                    type: 'execution',
                    execution_id: $exec_id,
                    status: $status,
                    started_at: $started_at,
                    completed_at: $completed_at,
                    task_count: $task_count,
                    agent_count: $agent_count,
                    mcp_synced: true,
                    created_at: datetime()
                })
                """,
                name=f"Execution_{execution_id}",
                exec_id=execution_id,
                status=execution.get('status'),
                started_at=str(execution.get('started_at')),
                completed_at=str(execution.get('completed_at')),
                task_count=len(exec_result['tasks']),
                agent_count=len(exec_result['agents'])
            )
            
            # Create memories for significant decisions
            decision_result = session.run(
                """
                MATCH (e:Execution {id: $exec_id})-[:HAS_AGENT]->(a:ExecutionAgent)
                MATCH (a)-[:MADE_DECISION]->(d:Decision)
                WHERE d.thought IS NOT NULL
                RETURN a.name as agent, d.action as action, 
                       d.thought as thought, d.timestamp as timestamp
                LIMIT 20
                """,
                exec_id=execution_id
            )
            
            for record in decision_result:
                session.run(
                    """
                    CREATE (m:Memory {
                        name: $name,
                        type: 'decision',
                        agent: $agent,
                        action: $action,
                        thought: $thought,
                        execution_id: $exec_id,
                        mcp_synced: true,
                        created_at: $timestamp
                    })
                    """,
                    name=f"Decision_{record['agent']}_{int(time.time())}",
                    agent=record['agent'],
                    action=record['action'],
                    thought=record['thought'],
                    exec_id=execution_id,
                    timestamp=record['timestamp']
                )
    
    def get_mcp_status(self) -> Dict[str, Any]:
        """Get MCP server status and statistics"""
        status = {
            'connected': False,
            'neo4j_connected': self.driver is not None,
            'statistics': {}
        }
        
        if self.driver:
            with self.driver.session() as session:
                # Check MCP-synced memories
                stats = session.run(
                    """
                    MATCH (m:Memory {mcp_synced: true})
                    WITH count(m) as total_memories,
                         count(DISTINCT m.agent) as unique_agents,
                         count(DISTINCT m.type) as memory_types
                    RETURN total_memories, unique_agents, memory_types
                    """
                ).single()
                
                if stats:
                    status['statistics'] = {
                        'total_mcp_memories': stats['total_memories'],
                        'unique_agents': stats['unique_agents'],
                        'memory_types': stats['memory_types']
                    }
                
                # Check server process
                try:
                    result = subprocess.run(
                        ['pgrep', '-f', self.mcp_server_path],
                        capture_output=True,
                        text=True
                    )
                    status['connected'] = result.returncode == 0
                except:
                    pass
        
        return status
    
    def close(self):
        """Close connections"""
        if self.driver:
            self.driver.close()


class MCPToolWrapper:
    """Wrapper to use MCP tools within CrewAI agents"""
    
    def __init__(self, bridge: MCPNeo4jBridge):
        self.bridge = bridge
    
    def create_memory(self, agent_name: str, memory_type: str, content: Dict) -> str:
        """Create a memory using MCP format"""
        memory = {
            'name': f"{agent_name}_{memory_type}_{int(time.time())}",
            'type': memory_type,
            'content': content
        }
        
        self.bridge.sync_agent_memories(agent_name, [memory])
        return f"Memory created: {memory['name']}"
    
    def search_memories(self, query: str, agent: Optional[str] = None) -> List[Dict]:
        """Search memories using MCP bridge"""
        return self.bridge.search_memories(query, agent)
    
    def get_context(self, agent_name: str) -> Dict:
        """Get agent context including memories and relationships"""
        return self.bridge.get_agent_context(agent_name)
    
    def create_connection(self, source: str, target: str, relationship: str) -> str:
        """Create connection between entities"""
        self.bridge.create_memory_connection(source, target, relationship)
        return f"Connection created: {source} -> {relationship} -> {target}"


def integrate_mcp_with_crew(crew):
    """Integrate MCP Neo4j capabilities with CrewAI crew"""
    # Create bridge
    bridge = MCPNeo4jBridge()
    wrapper = MCPToolWrapper(bridge)
    
    # Add MCP capabilities to each agent
    if hasattr(crew, 'agents'):
        for agent in crew.agents:
            # Add context loading before execution
            original_execute = getattr(agent, 'execute', None)
            if original_execute:
                def mcp_enhanced_execute(task, *args, **kwargs):
                    # Load context from MCP
                    context = wrapper.get_context(agent.role)
                    
                    # Add context to task if possible
                    if hasattr(task, 'context'):
                        task.context = context
                    
                    # Execute task
                    result = original_execute(task, *args, **kwargs)
                    
                    # Store result as memory
                    if result:
                        wrapper.create_memory(
                            agent.role,
                            'task_result',
                            {
                                'task': str(task),
                                'result': str(result)[:1000],
                                'timestamp': datetime.now().isoformat()
                            }
                        )
                    
                    return result
                
                agent.execute = mcp_enhanced_execute
            
            # Add MCP tools to agent
            agent.mcp_create_memory = lambda t, c: wrapper.create_memory(agent.role, t, c)
            agent.mcp_search = wrapper.search_memories
            agent.mcp_get_context = lambda: wrapper.get_context(agent.role)
    
    # Sync execution after completion
    original_kickoff = crew.kickoff
    
    def mcp_synced_kickoff(inputs={}):
        result = original_kickoff(inputs)
        
        # Sync execution to MCP
        if hasattr(crew, 'telemetry') and hasattr(crew.telemetry, 'execution_id'):
            bridge.sync_execution_to_mcp(crew.telemetry.execution_id)
        
        return result
    
    crew.kickoff = mcp_synced_kickoff
    
    # Add status check
    crew.mcp_status = bridge.get_mcp_status
    
    return bridge


# Integration test function
def test_mcp_integration():
    """Test MCP Neo4j integration"""
    print("\n🧪 Testing MCP Neo4j Integration...")
    
    # Set environment variables
    os.environ['NEO4J_URI'] = 'bolt://localhost:7687'
    os.environ['NEO4J_USERNAME'] = 'neo4j'
    os.environ['NEO4J_PASSWORD'] = 'password'
    
    # Create bridge
    bridge = MCPNeo4jBridge()
    
    # Test status
    status = bridge.get_mcp_status()
    print(f"\n📊 MCP Status:")
    print(f"  Neo4j Connected: {status['neo4j_connected']}")
    print(f"  MCP Server Running: {status['connected']}")
    print(f"  Statistics: {status['statistics']}")
    
    # Test memory creation
    test_agent = "test_agent"
    test_memories = [
        {
            'name': 'test_memory_1',
            'type': 'knowledge',
            'content': {'fact': 'Integration test successful'}
        }
    ]
    
    bridge.sync_agent_memories(test_agent, test_memories)
    print(f"\n✅ Created test memory for {test_agent}")
    
    # Test search
    results = bridge.search_memories("test")
    print(f"\n🔍 Found {len(results)} memories matching 'test'")
    
    # Test context retrieval
    context = bridge.get_agent_context(test_agent)
    print(f"\n📝 Agent context retrieved:")
    print(f"  Memories: {len(context['memories'])}")
    print(f"  Relationships: {len(context['relationships'])}")
    print(f"  Patterns: {len(context['patterns'])}")
    
    # Cleanup
    bridge.close()
    print("\n✅ MCP Integration test completed")


if __name__ == "__main__":
    test_mcp_integration()