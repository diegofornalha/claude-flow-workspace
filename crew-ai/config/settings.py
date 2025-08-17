"""
Configuração Unificada do Sistema
Centraliza todas as configurações do projeto
"""

import os
from typing import Dict, Any
from pathlib import Path
import yaml
import json

class ProjectSettings:
    """Configurações centralizadas do projeto"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.config_dir = self.base_dir / "config"
        
        # Neo4j Settings
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_username = os.getenv("NEO4J_USERNAME", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
        
        # MCP Settings
        self.mcp_server_path = "/Users/2a/.claude/mcp-neo4j-agent-memory/build/index.js"
        self.mcp_enabled = os.getenv("MCP_ENABLED", "true").lower() == "true"
        
        # Project Settings
        self.project_name = "Conductor-Baku"
        self.project_version = "claude-20x"
        
        # Load dynamic inputs
        self._inputs = self._load_inputs()
        
        # Load agents and tasks configs
        self._agents_config = self._load_yaml("agents.yaml")
        self._tasks_config = self._load_yaml("tasks.yaml")
    
    def _load_yaml(self, filename: str) -> Dict:
        """Carrega arquivo YAML de configuração"""
        filepath = self.config_dir / filename
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        return {}
    
    def _load_inputs(self) -> Dict[str, Any]:
        """Carrega inputs dinâmicos do sistema"""
        inputs_file = self.base_dir / "config" / "inputs.json"
        
        if inputs_file.exists():
            with open(inputs_file, 'r') as f:
                return json.load(f)
        
        # Inputs padrão se arquivo não existir
        return {
            'project_scope': f'{self.project_name} AI Agent Orchestration with Neo4j Integration',
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
    
    def get_agent_config(self, agent_name: str) -> Dict:
        """Retorna configuração de um agente específico"""
        config = self._agents_config.get(agent_name, {})
        
        # Substitui placeholders pelos valores reais
        for key, value in config.items():
            if isinstance(value, str):
                for input_key, input_value in self._inputs.items():
                    placeholder = f"{{{input_key}}}"
                    if placeholder in value:
                        config[key] = value.replace(placeholder, str(input_value))
        
        return config
    
    def get_task_config(self, task_name: str) -> Dict:
        """Retorna configuração de uma tarefa específica"""
        config = self._tasks_config.get(task_name, {})
        
        # Substitui placeholders
        for key, value in config.items():
            if isinstance(value, str):
                for input_key, input_value in self._inputs.items():
                    placeholder = f"{{{input_key}}}"
                    if placeholder in value:
                        config[key] = value.replace(placeholder, str(input_value))
        
        return config
    
    def get_all_inputs(self) -> Dict[str, Any]:
        """Retorna todos os inputs configurados"""
        return self._inputs.copy()
    
    def update_input(self, key: str, value: Any):
        """Atualiza um input específico"""
        self._inputs[key] = value
        
        # Salva no arquivo
        inputs_file = self.base_dir / "config" / "inputs.json"
        with open(inputs_file, 'w') as f:
            json.dump(self._inputs, f, indent=2)
    
    def get_neo4j_config(self) -> Dict[str, str]:
        """Retorna configuração do Neo4j"""
        return {
            "uri": self.neo4j_uri,
            "username": self.neo4j_username,
            "password": self.neo4j_password
        }
    
    def get_telemetry_config(self) -> Dict[str, Any]:
        """Retorna configuração de telemetria"""
        return {
            "enabled": True,
            "verbose": os.getenv("TELEMETRY_VERBOSE", "false").lower() == "true",
            "batch_size": int(os.getenv("TELEMETRY_BATCH_SIZE", "10")),
            "flush_interval": int(os.getenv("TELEMETRY_FLUSH_INTERVAL", "60"))
        }
    
    def get_optimization_config(self) -> Dict[str, Any]:
        """Retorna configuração de otimização"""
        return {
            "parallel_workers": int(os.getenv("PARALLEL_WORKERS", "4")),
            "cache_ttl": int(os.getenv("CACHE_TTL", "3600")),
            "retry_max_attempts": int(os.getenv("RETRY_MAX_ATTEMPTS", "3")),
            "retry_backoff_factor": float(os.getenv("RETRY_BACKOFF_FACTOR", "2.0"))
        }
    
    def validate_environment(self) -> Dict[str, bool]:
        """Valida se o ambiente está configurado corretamente"""
        checks = {}
        
        # Check Neo4j connection
        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_username, self.neo4j_password)
            )
            with driver.session() as session:
                session.run("RETURN 1")
            driver.close()
            checks["neo4j"] = True
        except:
            checks["neo4j"] = False
        
        # Check MCP server
        checks["mcp_server"] = Path(self.mcp_server_path).exists()
        
        # Check config files
        checks["agents_config"] = (self.config_dir / "agents.yaml").exists()
        checks["tasks_config"] = (self.config_dir / "tasks.yaml").exists()
        
        # Check Python modules
        try:
            import crewai
            checks["crewai"] = True
        except:
            checks["crewai"] = False
        
        try:
            import pydantic
            checks["pydantic"] = True
        except:
            checks["pydantic"] = False
        
        return checks


# Singleton instance
settings = ProjectSettings()