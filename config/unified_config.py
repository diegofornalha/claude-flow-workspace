#!/usr/bin/env python3
"""
⚙️ Configuração Unificada - Sistema Consolidado
Combina as melhores partes de config.py e crew-ai/config/settings.py
Sistema de gerenciamento de configurações unificado com fallbacks e validação
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from dotenv import load_dotenv
import logging

# Carregar variáveis de ambiente
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class ServiceDiscoveryConfig:
    """Configurações do Service Discovery"""
    host: str = field(default_factory=lambda: os.getenv('DISCOVERY_HOST', '0.0.0.0'))
    port: int = field(default_factory=lambda: int(os.getenv('DISCOVERY_PORT', '8002')))
    scan_interval: int = field(default_factory=lambda: int(os.getenv('DISCOVERY_SCAN_INTERVAL', '30')))
    cache_ttl: int = field(default_factory=lambda: int(os.getenv('DISCOVERY_CACHE_TTL', '30')))
    scan_ranges: List[tuple] = field(default_factory=list)
    max_concurrent: int = field(default_factory=lambda: int(os.getenv('MAX_CONCURRENT_CONNECTIONS', '20')))
    
    def __post_init__(self):
        """Parse scan ranges from environment"""
        ranges_str = os.getenv('DISCOVERY_SCAN_RANGES', 'localhost:3000-4000')
        self.scan_ranges = self._parse_scan_ranges(ranges_str)
    
    def _parse_scan_ranges(self, ranges_str: str) -> List[tuple]:
        """Parse scan ranges string into list of tuples"""
        ranges = []
        try:
            for range_spec in ranges_str.split(','):
                range_spec = range_spec.strip()
                if ':' in range_spec:
                    host, ports = range_spec.split(':')
                    if '-' in ports:
                        start, end = ports.split('-')
                        ranges.append((host, range(int(start), int(end) + 1)))
                    else:
                        ranges.append((host, [int(ports)]))
        except Exception as e:
            logger.warning(f"Erro ao parsear scan_ranges, usando padrão: {e}")
            ranges = [("localhost", range(3000, 4000))]
        return ranges


@dataclass
class LoggerConfig:
    """Configurações do Central Logger"""
    host: str = field(default_factory=lambda: os.getenv('LOGGER_HOST', '0.0.0.0'))
    port: int = field(default_factory=lambda: int(os.getenv('LOGGER_PORT', '8003')))
    max_file_size: str = field(default_factory=lambda: os.getenv('LOGGER_MAX_FILE_SIZE', '100MB'))
    retention_days: int = field(default_factory=lambda: int(os.getenv('LOGGER_RETENTION_DAYS', '30')))
    alert_level: str = field(default_factory=lambda: os.getenv('LOGGER_ALERT_LEVEL', 'ERROR'))
    log_level: str = field(default_factory=lambda: os.getenv('LOG_LEVEL', 'INFO'))


@dataclass
class PathsConfig:
    """Configurações de paths do sistema"""
    project_root: Path
    logs_dir: Path
    memory_dir: Path
    sessions_dir: Path
    config_dir: Path
    
    def __init__(self):
        # Usar variável de ambiente ou detectar automaticamente
        root_str = os.getenv('PROJECT_ROOT')
        if root_str:
            self.project_root = Path(root_str)
        else:
            # Tentar detectar o diretório do projeto
            current_file = Path(__file__).resolve()
            self.project_root = current_file.parent.parent  # Subir um nível de /config
        
        # Configurar subdiretórios
        self.logs_dir = Path(os.getenv('LOGS_DIR', str(self.project_root / 'logging' / 'logs')))
        self.memory_dir = Path(os.getenv('MEMORY_DIR', str(self.project_root / 'memory')))
        self.sessions_dir = Path(os.getenv('SESSIONS_DIR', str(self.memory_dir / 'sessions')))
        self.config_dir = self.project_root / "config"
        
        # Criar diretórios se não existirem
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Garante que todos os diretórios necessários existam"""
        for dir_path in [self.logs_dir, self.memory_dir, self.sessions_dir, self.config_dir]:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.warning(f"Não foi possível criar diretório {dir_path}: {e}")


@dataclass
class AgentsConfig:
    """Configurações dos agentes conhecidos"""
    known_agents: Dict[str, Dict[str, Any]]
    
    def __init__(self):
        self.known_agents = {
            "helloworld": {
                "ports": [int(os.getenv('AGENT_HELLOWORLD_PORT', '9999'))],
                "type": "a2a"
            },
            "marvin": {
                "ports": [int(os.getenv('AGENT_MARVIN_PORT', '3002'))],
                "type": "a2a"
            },
            "gemini": {
                "ports": [int(os.getenv('AGENT_GEMINI_PORT', '3003'))],
                "type": "a2a"
            },
            "ui": {
                "ports": [int(os.getenv('UI_PORT', '12000'))],
                "type": "web"
            },
            "analytics": {
                "ports": [int(os.getenv('ANALYTICS_PORT', '5000'))],
                "type": "analytics"
            },
            "a2a-inspector": {
                "ports": [int(os.getenv('INSPECTOR_PORT', '5001'))],
                "type": "debug"
            },
            "rag-coordinator": {
                "ports": [int(os.getenv('RAG_COORDINATOR_PORT', '3004'))],
                "type": "a2a"
            }
        }


@dataclass
class SecurityConfig:
    """Configurações de segurança"""
    enable_auth: bool = field(default_factory=lambda: os.getenv('ENABLE_AUTH', 'false').lower() == 'true')
    jwt_secret: str = field(default_factory=lambda: os.getenv('JWT_SECRET', 'change-this-in-production'))
    api_rate_limit: int = field(default_factory=lambda: int(os.getenv('API_RATE_LIMIT', '100')))


@dataclass
class PerformanceConfig:
    """Configurações de performance"""
    request_timeout: int = field(default_factory=lambda: int(os.getenv('REQUEST_TIMEOUT', '5000')))
    websocket_heartbeat: int = field(default_factory=lambda: int(os.getenv('WEBSOCKET_HEARTBEAT', '30000')))
    max_concurrent: int = field(default_factory=lambda: int(os.getenv('MAX_CONCURRENT_CONNECTIONS', '20')))


@dataclass
class Neo4jConfig:
    """Configurações do Neo4j Database"""
    uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    username: str = field(default_factory=lambda: os.getenv("NEO4J_USERNAME", "neo4j"))
    password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", "password"))
    database: str = field(default_factory=lambda: os.getenv("NEO4J_DATABASE", "neo4j"))


@dataclass
class MCPConfig:
    """Configurações do MCP (Model Context Protocol)"""
    server_path: str = field(default_factory=lambda: os.getenv("MCP_SERVER_PATH", "/Users/2a/.claude/mcp-neo4j-agent-memory/build/index.js"))
    enabled: bool = field(default_factory=lambda: os.getenv("MCP_ENABLED", "true").lower() == "true")


@dataclass
class CrewAIConfig:
    """Configurações específicas do CrewAI"""
    project_name: str = field(default_factory=lambda: os.getenv("PROJECT_NAME", "Conductor-Baku"))
    project_version: str = field(default_factory=lambda: os.getenv("PROJECT_VERSION", "claude-20x"))
    max_rpm: int = field(default_factory=lambda: int(os.getenv("CREW_MAX_RPM", "100")))
    memory_enabled: bool = field(default_factory=lambda: os.getenv("CREW_MEMORY_ENABLED", "true").lower() == "true")
    planning_enabled: bool = field(default_factory=lambda: os.getenv("CREW_PLANNING_ENABLED", "true").lower() == "true")
    verbose: bool = field(default_factory=lambda: os.getenv("CREW_VERBOSE", "true").lower() == "true")


class UnifiedConfig:
    """Configuração principal unificada do sistema"""
    
    def __init__(self):
        # Inicializar todas as configurações
        self.paths = PathsConfig()
        self.discovery = ServiceDiscoveryConfig()
        self.logger = LoggerConfig()
        self.agents = AgentsConfig()
        self.security = SecurityConfig()
        self.performance = PerformanceConfig()
        self.neo4j = Neo4jConfig()
        self.mcp = MCPConfig()
        self.crewai = CrewAIConfig()
        self.debug_mode = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
        
        # Carregar configurações dinâmicas
        self._inputs = self._load_inputs()
        self._agents_config = self._load_yaml("agents.yaml")
        self._tasks_config = self._load_yaml("tasks.yaml")
        
        # Validar configurações
        self._validate()
        
        # Log configurações carregadas (sem dados sensíveis)
        if self.debug_mode:
            logger.info("✅ Configurações unificadas carregadas com sucesso")
            logger.debug(f"Project root: {self.paths.project_root}")
            logger.debug(f"Discovery port: {self.discovery.port}")
            logger.debug(f"Logger port: {self.logger.port}")
    
    def _load_yaml(self, filename: str) -> Dict:
        """Carrega arquivo YAML de configuração"""
        # Tentar primeiro na pasta crew-ai/config
        crew_config_path = self.paths.project_root / "crew-ai" / "config" / filename
        if crew_config_path.exists():
            with open(crew_config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        
        # Tentar na pasta config principal
        main_config_path = self.paths.config_dir / filename
        if main_config_path.exists():
            with open(main_config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        
        logger.warning(f"Arquivo YAML não encontrado: {filename}")
        return {}
    
    def _load_inputs(self) -> Dict[str, Any]:
        """Carrega inputs dinâmicos do sistema"""
        # Tentar primeiro na pasta crew-ai/config
        crew_inputs_file = self.paths.project_root / "crew-ai" / "config" / "inputs.json"
        if crew_inputs_file.exists():
            with open(crew_inputs_file, 'r') as f:
                return json.load(f)
        
        # Tentar na pasta config principal
        main_inputs_file = self.paths.config_dir / "inputs.json"
        if main_inputs_file.exists():
            with open(main_inputs_file, 'r') as f:
                return json.load(f)
        
        # Inputs padrão se arquivo não existir
        return {
            'project_scope': f'{self.crewai.project_name} AI Agent Orchestration with Neo4j Integration',
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
    
    def _validate(self):
        """Valida as configurações"""
        # Validar portas
        if not (1 <= self.discovery.port <= 65535):
            raise ValueError(f"Porta do Discovery inválida: {self.discovery.port}")
        
        if not (1 <= self.logger.port <= 65535):
            raise ValueError(f"Porta do Logger inválida: {self.logger.port}")
        
        # Validar paths
        if not self.paths.project_root.exists():
            logger.warning(f"Project root não existe: {self.paths.project_root}")
        
        # Avisar sobre segurança apenas se não for ambiente local
        is_local = os.getenv('ENVIRONMENT', 'local').lower() in ['local', 'dev', 'development']
        
        if not is_local:
            if not self.security.enable_auth:
                logger.warning("⚠️ Autenticação desabilitada - não usar em produção!")
            
            if self.security.jwt_secret == 'change-this-in-production':
                logger.warning("⚠️ JWT secret padrão - alterar em produção!")
    
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
        
        # Salva no arquivo (priorizar crew-ai/config se existir)
        crew_inputs_file = self.paths.project_root / "crew-ai" / "config" / "inputs.json"
        if crew_inputs_file.parent.exists():
            with open(crew_inputs_file, 'w') as f:
                json.dump(self._inputs, f, indent=2)
        else:
            inputs_file = self.paths.config_dir / "inputs.json"
            with open(inputs_file, 'w') as f:
                json.dump(self._inputs, f, indent=2)
    
    def get_neo4j_config(self) -> Dict[str, str]:
        """Retorna configuração do Neo4j"""
        return {
            "uri": self.neo4j.uri,
            "username": self.neo4j.username,
            "password": self.neo4j.password,
            "database": self.neo4j.database
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
                self.neo4j.uri,
                auth=(self.neo4j.username, self.neo4j.password)
            )
            with driver.session() as session:
                session.run("RETURN 1")
            driver.close()
            checks["neo4j"] = True
        except:
            checks["neo4j"] = False
        
        # Check MCP server
        checks["mcp_server"] = Path(self.mcp.server_path).exists()
        
        # Check config files
        checks["agents_config"] = bool(self._agents_config)
        checks["tasks_config"] = bool(self._tasks_config)
        
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
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte configurações para dicionário (sem dados sensíveis)"""
        return {
            "paths": {
                "project_root": str(self.paths.project_root),
                "logs_dir": str(self.paths.logs_dir),
                "config_dir": str(self.paths.config_dir)
            },
            "discovery": {
                "host": self.discovery.host,
                "port": self.discovery.port,
                "scan_interval": self.discovery.scan_interval
            },
            "logger": {
                "host": self.logger.host,
                "port": self.logger.port,
                "retention_days": self.logger.retention_days
            },
            "crewai": {
                "project_name": self.crewai.project_name,
                "project_version": self.crewai.project_version,
                "max_rpm": self.crewai.max_rpm
            },
            "neo4j": {
                "uri": self.neo4j.uri,
                "database": self.neo4j.database
                # Não incluir credenciais
            },
            "mcp": {
                "enabled": self.mcp.enabled
                # Não incluir path completo
            },
            "security": {
                "auth_enabled": self.security.enable_auth,
                "rate_limit": self.security.api_rate_limit
            },
            "debug_mode": self.debug_mode
        }


# Singleton da configuração unificada
_unified_config = None


def get_unified_config() -> UnifiedConfig:
    """Retorna instância singleton da configuração unificada"""
    global _unified_config
    if _unified_config is None:
        _unified_config = UnifiedConfig()
    return _unified_config


# Manter compatibilidade com sistemas antigos
def get_config() -> UnifiedConfig:
    """Alias para get_unified_config() para compatibilidade"""
    return get_unified_config()


# Exportar para uso direto
config = get_unified_config()


if __name__ == "__main__":
    # Teste das configurações unificadas
    print("🔧 Testando configurações unificadas...")
    cfg = get_unified_config()
    print(json.dumps(cfg.to_dict(), indent=2))
    
    # Testar validação do ambiente
    print("\n🔍 Validando ambiente...")
    env_status = cfg.validate_environment()
    for component, status in env_status.items():
        emoji = "✅" if status else "❌"
        print(f"{emoji} {component}: {'OK' if status else 'FALHA'}")
    
    print("\n✅ Configurações unificadas testadas com sucesso!")