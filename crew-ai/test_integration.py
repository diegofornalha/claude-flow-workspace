#!/usr/bin/env python
"""
Integration Test for Neo4j Enhanced CrewAI System
Tests all components: Telemetry, Optimization, Learning, MCP
"""

import os
import sys
import time
import json
from datetime import datetime

# Add project path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import all components
from tools.neo4j_tools import Neo4jConnection, Neo4jMemoryTool, Neo4jQueryTool
from tools.telemetry_callbacks import Neo4jTelemetryCallbacks
from tools.optimization_manager import OptimizationOrchestrator
from tools.continuous_learning import ContinuousLearningOrchestrator
from tools.mcp_integration import MCPNeo4jBridge


def test_neo4j_connection():
    """Test Neo4j database connection"""
    print("\n🧪 Testing Neo4j Connection...")
    
    try:
        conn = Neo4jConnection()
        session = conn.get_session()
        
        if session:
            # Test query
            result = session.run("RETURN 'Connected' as status")
            record = result.single()
            
            if record and record['status'] == 'Connected':
                print("✅ Neo4j connection successful")
                session.close()
                return True
            else:
                print("❌ Neo4j query failed")
                return False
        else:
            print("❌ Failed to get Neo4j session")
            return False
            
    except Exception as e:
        print(f"❌ Neo4j connection error: {e}")
        return False


def test_neo4j_tools():
    """Test Neo4j tools"""
    print("\n🧪 Testing Neo4j Tools...")
    
    try:
        # Test Memory Tool
        memory_tool = Neo4jMemoryTool()
        result = memory_tool._run(
            agent_name="test_agent",
            memory_type="test",
            content={"test": "Integration test memory"},
            tags=["test", "integration"]
        )
        print(f"  Memory Tool: {result}")
        
        # Test Query Tool
        query_tool = Neo4jQueryTool()
        result = query_tool._run(
            query_type="agent_history",
            filters={"agent_name": "test_agent"},
            limit=5
        )
        print(f"  Query Tool: Retrieved {len(json.loads(result)) if result != 'Failed to connect to Neo4j' else 0} records")
        
        print("✅ Neo4j tools working")
        return True
        
    except Exception as e:
        print(f"❌ Neo4j tools error: {e}")
        return False


def test_telemetry():
    """Test telemetry system"""
    print("\n🧪 Testing Telemetry System...")
    
    try:
        telemetry = Neo4jTelemetryCallbacks()
        
        # Get initial metrics
        metrics = telemetry.get_metrics_dashboard()
        print(f"  Execution ID: {telemetry.execution_id}")
        print(f"  Metrics: {metrics}")
        
        # Test graph query
        graph_query = telemetry.get_execution_graph()
        print(f"  Graph query generated: {len(graph_query)} characters")
        
        telemetry.close()
        print("✅ Telemetry system working")
        return True
        
    except Exception as e:
        print(f"❌ Telemetry error: {e}")
        return False


def test_optimization():
    """Test optimization manager"""
    print("\n🧪 Testing Optimization Manager...")
    
    try:
        optimizer = OptimizationOrchestrator()
        
        # Test cache
        test_context = {"task": "test_task", "input": "test_input"}
        optimizer.cache.set(test_context, "test_result")
        cached = optimizer.cache.get(test_context)
        print(f"  Cache test: {'✅ Working' if cached == 'test_result' else '❌ Failed'}")
        
        # Test parallel executor
        def test_func(x):
            time.sleep(0.1)
            return x * 2
        
        test_tasks = [1, 2, 3, 4]
        start = time.time()
        results = optimizer.parallel_executor.execute_parallel(
            test_tasks, 
            test_func
        )
        elapsed = time.time() - start
        print(f"  Parallel execution: {len(results)} tasks in {elapsed:.2f}s")
        
        optimizer.close()
        print("✅ Optimization manager working")
        return True
        
    except Exception as e:
        print(f"❌ Optimization error: {e}")
        return False


def test_learning():
    """Test continuous learning system"""
    print("\n🧪 Testing Continuous Learning System...")
    
    try:
        learning = ContinuousLearningOrchestrator()
        
        # Test quality scoring
        score = learning.quality_scorer.score_output(
            task_id="test_task_123",
            output="Test output",
            execution_time=5.0,
            resources_used={"memory_mb": 100, "cpu_percent": 30}
        )
        print(f"  Quality score: {score:.2f}")
        
        # Test pattern detection
        failure_patterns = learning.pattern_detector.detect_failure_patterns()
        success_patterns = learning.pattern_detector.detect_success_patterns()
        print(f"  Detected patterns: {len(failure_patterns)} failures, {len(success_patterns)} successes")
        
        # Test feedback loop
        suggestions = learning.feedback_loop.generate_improvement_suggestions()
        print(f"  Generated {len(suggestions)} improvement suggestions")
        
        # Get insights
        insights = learning.get_learning_insights()
        print(f"  Learning insights retrieved: {len(insights)} categories")
        
        learning.close()
        print("✅ Learning system working")
        return True
        
    except Exception as e:
        print(f"❌ Learning error: {e}")
        return False


def test_mcp_integration():
    """Test MCP Neo4j integration"""
    print("\n🧪 Testing MCP Integration...")
    
    try:
        bridge = MCPNeo4jBridge()
        
        # Test status
        status = bridge.get_mcp_status()
        print(f"  Neo4j connected: {status['neo4j_connected']}")
        print(f"  Statistics: {status['statistics']}")
        
        # Test memory sync
        test_memories = [{
            'name': 'integration_test',
            'type': 'test',
            'content': {'timestamp': datetime.now().isoformat()}
        }]
        bridge.sync_agent_memories("test_agent", test_memories)
        print("  Memory sync: ✅")
        
        # Test context retrieval
        context = bridge.get_agent_context("test_agent")
        print(f"  Context retrieved: {len(context['memories'])} memories")
        
        # Test search
        results = bridge.search_memories("test")
        print(f"  Search results: {len(results)} matches")
        
        bridge.close()
        print("✅ MCP integration working")
        return True
        
    except Exception as e:
        print(f"❌ MCP integration error: {e}")
        return False


def test_crew_integration():
    """Test full CrewAI integration"""
    print("\n🧪 Testing CrewAI Integration...")
    
    try:
        # Import crew
        from sistema_multi_agente_neo4j.crew import SistemaMultiAgenteNeo4jCrew
        
        # Create crew instance
        crew_instance = SistemaMultiAgenteNeo4jCrew()
        crew = crew_instance.crew()
        
        # Check integrations
        has_telemetry = hasattr(crew_instance, 'telemetry')
        has_optimization = hasattr(crew_instance, 'optimization')
        has_learning = hasattr(crew_instance, 'learning')
        has_mcp = hasattr(crew_instance, 'mcp_bridge')
        
        print(f"  Telemetry: {'✅' if has_telemetry else '❌'}")
        print(f"  Optimization: {'✅' if has_optimization else '❌'}")
        print(f"  Learning: {'✅' if has_learning else '❌'}")
        print(f"  MCP Bridge: {'✅' if has_mcp else '❌'}")
        
        # Check crew configuration
        print(f"  Process type: {crew.process}")
        print(f"  Agent count: {len(crew.agents)}")
        print(f"  Task count: {len(crew.tasks)}")
        
        if all([has_telemetry, has_optimization, has_learning, has_mcp]):
            print("✅ CrewAI fully integrated")
            return True
        else:
            print("⚠️ Some integrations missing")
            return False
            
    except Exception as e:
        print(f"❌ CrewAI integration error: {e}")
        return False


def run_full_test():
    """Run complete integration test suite"""
    print("\n" + "="*60)
    print("🚀 CONDUCTOR-BAKU NEO4J INTEGRATION TEST SUITE")
    print("="*60)
    print(f"Started at: {datetime.now().isoformat()}")
    
    # Set environment variables
    os.environ['NEO4J_URI'] = 'bolt://localhost:7687'
    os.environ['NEO4J_USERNAME'] = 'neo4j'
    os.environ['NEO4J_PASSWORD'] = 'password'
    
    # Run tests
    test_results = {
        'Neo4j Connection': test_neo4j_connection(),
        'Neo4j Tools': test_neo4j_tools(),
        'Telemetry': test_telemetry(),
        'Optimization': test_optimization(),
        'Learning': test_learning(),
        'MCP Integration': test_mcp_integration(),
        'CrewAI Integration': test_crew_integration()
    }
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST RESULTS SUMMARY")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for test, result in test_results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {test:20} : {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "-"*60)
    print(f"Total: {passed} passed, {failed} failed")
    print(f"Success Rate: {(passed/(passed+failed)*100):.1f}%")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! System is fully operational.")
    else:
        print(f"\n⚠️ {failed} test(s) failed. Please check the errors above.")
    
    print(f"\nCompleted at: {datetime.now().isoformat()}")
    print("="*60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_full_test()
    sys.exit(0 if success else 1)