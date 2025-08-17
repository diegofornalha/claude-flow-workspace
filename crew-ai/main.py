#!/usr/bin/env python
import sys
import os
import time
import json
from datetime import datetime
from sistema_multi_agente_neo4j.crew import SistemaMultiAgenteNeo4jCrew
from tools.telemetry_callbacks import Neo4jTelemetryCallbacks
from config.unified_config import get_unified_config

# Compatibility alias
settings = get_unified_config()

# This main file is intended to be a way for your to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def run():
    """
    Run the crew with Neo4j telemetry and optimizations.
    """
    # Configure environment from settings
    neo4j_config = settings.get_neo4j_config()
    os.environ['NEO4J_URI'] = neo4j_config['uri']
    os.environ['NEO4J_USERNAME'] = neo4j_config['username']
    os.environ['NEO4J_PASSWORD'] = neo4j_config['password']
    
    print(f"🚀 Starting {settings.project_name} Neo4j Enhanced Crew...")
    print(f"⏰ Execution started at: {datetime.now().isoformat()}")
    
    # Validate environment
    checks = settings.validate_environment()
    if not all(checks.values()):
        print("⚠️ Environment validation failed:")
        for check, status in checks.items():
            print(f"  {'✅' if status else '❌'} {check}")
        if not checks.get('neo4j'):
            print("\n❌ Neo4j connection failed. Please ensure Neo4j is running.")
            return
    
    # Get inputs from settings
    inputs = settings.get_all_inputs()
    
    # Create crew with telemetry
    crew_instance = SistemaMultiAgenteNeo4jCrew()
    crew = crew_instance.crew()
    
    # Run with monitoring
    start_time = time.time()
    try:
        result = crew.kickoff(inputs=inputs)
        execution_time = time.time() - start_time
        
        print(f"\n✅ Execution completed in {execution_time:.2f} seconds")
        print("\n📊 Telemetry Dashboard:")
        if hasattr(crew_instance, 'telemetry'):
            metrics = crew_instance.telemetry.get_metrics_dashboard()
            for key, value in metrics.items():
                print(f"  {key}: {value}")
            
            print(f"\n🔍 View execution graph in Neo4j Browser:")
            print(crew_instance.telemetry.get_execution_graph())
            
            # Close telemetry connection
            crew_instance.telemetry.close()
        
        return result
    except Exception as e:
        print(f"\n❌ Execution failed: {e}")
        if hasattr(crew_instance, 'telemetry'):
            crew_instance.telemetry.close()
        raise


def train():
    """
    Train the crew for a given number of iterations with learning patterns.
    """
    # Set Neo4j environment variables
    os.environ['NEO4J_URI'] = 'bolt://localhost:7687'
    os.environ['NEO4J_USERNAME'] = 'neo4j'
    os.environ['NEO4J_PASSWORD'] = 'password'
    
    inputs = {
        'project_scope': 'Conductor-Baku AI Agent Orchestration with Neo4j Integration',
        'research_topic': 'Advanced patterns in multi-agent systems and knowledge graphs',
        'development_task': 'Implement and optimize CrewAI with Neo4j telemetry and learning',
        'testing_scope': 'Full coverage testing with performance benchmarks',
        'review_scope': 'Code quality, performance metrics, and pattern compliance',
        'target_platform': 'MacOS with Docker and Neo4j',
        'budget_constraints': 'Optimize for resource efficiency',
        'timeline_requirements': 'Real-time execution with telemetry',
        'research_focus_area': 'Multi-agent coordination and knowledge persistence',
        'target_market': 'AI development teams and researchers',
        'programming_language': 'Python, TypeScript, JavaScript',
        'development_framework': 'CrewAI, Neo4j, MCP',
        'testing_methodology': 'Unit, integration, and performance testing',
        'testing_environment': 'Local development with CI/CD pipeline',
        'code_standards': 'PEP8, ESLint, clean architecture',
        'security_framework': 'Zero-trust, encrypted connections'
    }
    
    try:
        print(f"🎯 Starting training with {sys.argv[1]} iterations...")
        crew_instance = SistemaMultiAgenteNeo4jCrew()
        crew = crew_instance.crew()
        
        # Train with pattern learning
        crew.train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)
        
        print("✅ Training completed successfully")
        if hasattr(crew_instance, 'telemetry'):
            crew_instance.telemetry.close()

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task with telemetry.
    """
    # Set Neo4j environment variables
    os.environ['NEO4J_URI'] = 'bolt://localhost:7687'
    os.environ['NEO4J_USERNAME'] = 'neo4j'
    os.environ['NEO4J_PASSWORD'] = 'password'
    
    try:
        print(f"🔄 Replaying from task: {sys.argv[1]}")
        crew_instance = SistemaMultiAgenteNeo4jCrew()
        crew = crew_instance.crew()
        
        result = crew.replay(task_id=sys.argv[1])
        
        print("✅ Replay completed successfully")
        if hasattr(crew_instance, 'telemetry'):
            crew_instance.telemetry.close()
        
        return result

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution with performance benchmarks.
    """
    # Set Neo4j environment variables
    os.environ['NEO4J_URI'] = 'bolt://localhost:7687'
    os.environ['NEO4J_USERNAME'] = 'neo4j'
    os.environ['NEO4J_PASSWORD'] = 'password'
    
    inputs = {
        'project_scope': 'Test: Conductor-Baku AI Agent Orchestration',
        'research_topic': 'Test: Pattern validation in multi-agent systems',
        'development_task': 'Test: Validate CrewAI with Neo4j integration',
        'testing_scope': 'Test: Coverage and performance benchmarks',
        'review_scope': 'Test: Quality metrics validation',
        'target_platform': 'Test: MacOS environment',
        'budget_constraints': 'Test: Resource limits',
        'timeline_requirements': 'Test: Execution time limits',
        'research_focus_area': 'Test: Agent coordination',
        'target_market': 'Test: Development teams',
        'programming_language': 'Test: Python',
        'development_framework': 'Test: CrewAI',
        'testing_methodology': 'Test: Unit tests',
        'testing_environment': 'Test: Local',
        'code_standards': 'Test: PEP8',
        'security_framework': 'Test: Basic security'
    }
    
    try:
        print(f"🧪 Starting test with {sys.argv[1]} iterations using {sys.argv[2]} model...")
        crew_instance = SistemaMultiAgenteNeo4jCrew()
        crew = crew_instance.crew()
        
        # Run tests with benchmarking
        start_time = time.time()
        crew.test(n_iterations=int(sys.argv[1]), openai_model_name=sys.argv[2], inputs=inputs)
        test_time = time.time() - start_time
        
        print(f"\n✅ Tests completed in {test_time:.2f} seconds")
        print(f"  Average time per iteration: {test_time/int(sys.argv[1]):.2f}s")
        
        if hasattr(crew_instance, 'telemetry'):
            crew_instance.telemetry.close()

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: main.py <command> [<args>]")
        print("Commands:")
        print("  run - Execute the crew with telemetry")
        print("  train <iterations> <filename> - Train the crew")
        print("  replay <task_id> - Replay from a specific task")
        print("  test <iterations> <model> - Test the crew")
        sys.exit(1)

    command = sys.argv[1]
    if command == "run":
        run()
    elif command == "train":
        if len(sys.argv) < 4:
            print("Usage: main.py train <iterations> <filename>")
            sys.exit(1)
        train()
    elif command == "replay":
        if len(sys.argv) < 3:
            print("Usage: main.py replay <task_id>")
            sys.exit(1)
        replay()
    elif command == "test":
        if len(sys.argv) < 4:
            print("Usage: main.py test <iterations> <model>")
            sys.exit(1)
        test()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)