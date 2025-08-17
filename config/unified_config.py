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


@dataclass
class ClustersConfig:
    """Configurações do sistema de clusters"""
    enabled: bool = field(default_factory=lambda: os.getenv("CLUSTERS_ENABLED", "true").lower() == "true")
    
    # Configurações do Orquestrador
    orchestrator_enabled: bool = field(default_factory=lambda: os.getenv("ORCHESTRATOR_ENABLED", "true").lower() == "true")
    health_check_interval: int = field(default_factory=lambda: int(os.getenv("CLUSTER_HEALTH_CHECK_INTERVAL", "30")))
    auto_recovery: bool = field(default_factory=lambda: os.getenv("CLUSTER_AUTO_RECOVERY", "true").lower() == "true")
    max_retry_attempts: int = field(default_factory=lambda: int(os.getenv("CLUSTER_MAX_RETRY_ATTEMPTS", "3")))
    default_timeout: float = field(default_factory=lambda: float(os.getenv("CLUSTER_DEFAULT_TIMEOUT", "5.0")))
    
    # Configurações de Comunicação Inter-Cluster
    message_broker_enabled: bool = field(default_factory=lambda: os.getenv("MESSAGE_BROKER_ENABLED", "true").lower() == "true")
    rest_port: int = field(default_factory=lambda: int(os.getenv("CLUSTER_REST_PORT", "8080")))
    websocket_port: int = field(default_factory=lambda: int(os.getenv("CLUSTER_WEBSOCKET_PORT", "8081")))
    grpc_port: int = field(default_factory=lambda: int(os.getenv("CLUSTER_GRPC_PORT", "9090")))
    message_batch_size: int = field(default_factory=lambda: int(os.getenv("MESSAGE_BATCH_SIZE", "100")))
    
    # Configurações do Registry
    registry_enabled: bool = field(default_factory=lambda: os.getenv("CLUSTER_REGISTRY_ENABLED", "true").lower() == "true")
    auto_discovery_interval: int = field(default_factory=lambda: int(os.getenv("AUTO_DISCOVERY_INTERVAL", "300")))
    registry_persistence: bool = field(default_factory=lambda: os.getenv("REGISTRY_PERSISTENCE", "true").lower() == "true")
    registry_storage_path: str = field(default_factory=lambda: os.getenv("REGISTRY_STORAGE_PATH", "clusters_registry.json"))
    
    # Configurações de Auto-Scaling
    auto_scaling_enabled: bool = field(default_factory=lambda: os.getenv("AUTO_SCALING_ENABLED", "true").lower() == "true")
    scaling_analysis_interval: int = field(default_factory=lambda: int(os.getenv("SCALING_ANALYSIS_INTERVAL", "60")))
    metrics_collection_interval: int = field(default_factory=lambda: int(os.getenv("METRICS_COLLECTION_INTERVAL", "30")))
    default_min_agents: int = field(default_factory=lambda: int(os.getenv("DEFAULT_MIN_AGENTS", "1")))
    default_max_agents: int = field(default_factory=lambda: int(os.getenv("DEFAULT_MAX_AGENTS", "10")))
    
    # Configurações de Failover
    failover_enabled: bool = field(default_factory=lambda: os.getenv("FAILOVER_ENABLED", "true").lower() == "true")
    failover_monitoring_interval: int = field(default_factory=lambda: int(os.getenv("FAILOVER_MONITORING_INTERVAL", "30")))
    default_health_threshold: float = field(default_factory=lambda: float(os.getenv("DEFAULT_HEALTH_THRESHOLD", "50.0")))
    auto_failback: bool = field(default_factory=lambda: os.getenv("AUTO_FAILBACK", "true").lower() == "true")
    
    # Topologias suportadas
    supported_topologies: List[str] = field(default_factory=lambda: [
        "star",         # Hub central com clusters conectados
        "mesh",         # Todos clusters conectados entre si
        "hierarchical", # Estrutura hierárquica de clusters
        "ring",         # Clusters em anel
        "tree"          # Estrutura de árvore
    ])
    
    # Política de comunicação padrão
    default_topology: str = field(default_factory=lambda: os.getenv("DEFAULT_CLUSTER_TOPOLOGY", "star"))
    
    # Limites de recursos por cluster
    max_clusters: int = field(default_factory=lambda: int(os.getenv("MAX_CLUSTERS", "20")))
    max_agents_per_cluster: int = field(default_factory=lambda: int(os.getenv("MAX_AGENTS_PER_CLUSTER", "50")))
    max_connections_per_cluster: int = field(default_factory=lambda: int(os.getenv("MAX_CONNECTIONS_PER_CLUSTER", "100")))
    
    # Configurações específicas por tipo de cluster
    cluster_configs: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "core_cluster": {
            "min_agents": 3,
            "max_agents": 8,
            "priority": 1,
            "auto_scaling": True,
            "failover_enabled": True,
            "backup_clusters": ["coordination_cluster"]
        },
        "coordination_cluster": {
            "min_agents": 2,
            "max_agents": 5,
            "priority": 1,
            "auto_scaling": True,
            "failover_enabled": True,
            "backup_clusters": ["core_cluster"]
        },
        "memory_cluster": {
            "min_agents": 2,
            "max_agents": 6,
            "priority": 2,
            "auto_scaling": True,
            "failover_enabled": True,
            "backup_clusters": ["analytics_cluster"]
        },
        "mcp_cluster": {
            "min_agents": 2,
            "max_agents": 8,
            "priority": 2,
            "auto_scaling": True,
            "failover_enabled": True,
            "backup_clusters": ["discovery_cluster"]
        },
        "analytics_cluster": {
            "min_agents": 1,
            "max_agents": 5,
            "priority": 3,
            "auto_scaling": True,
            "failover_enabled": True,
            "backup_clusters": ["memory_cluster"]
        },
        "discovery_cluster": {
            "min_agents": 1,
            "max_agents": 15,
            "priority": 3,
            "auto_scaling": True,
            "failover_enabled": True,
            "backup_clusters": ["mcp_cluster"]
        }
    })
    
    def get_cluster_config(self, cluster_id: str) -> Dict[str, Any]:
        """Retorna configuração específica de um cluster"""
        return self.cluster_configs.get(cluster_id, {
            "min_agents": self.default_min_agents,
            "max_agents": self.default_max_agents,
            "priority": 5,
            "auto_scaling": self.auto_scaling_enabled,
            "failover_enabled": self.failover_enabled,
            "backup_clusters": []
        })
    
    def validate_topology(self, topology: str) -> bool:
        """Valida se topologia é suportada"""
        return topology in self.supported_topologies
    
    def get_communication_ports(self) -> Dict[str, int]:
        """Retorna portas para comunicação inter-cluster"""
        return {
            "rest": self.rest_port,
            "websocket": self.websocket_port,
            "grpc": self.grpc_port
        }


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
        self.clusters = ClustersConfig()
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
    
    def get_clusters_config(self) -> Dict[str, Any]:
        """Retorna configuração completa de clusters"""
        return {
            "enabled": self.clusters.enabled,
            "orchestrator": {
                "enabled": self.clusters.orchestrator_enabled,
                "health_check_interval": self.clusters.health_check_interval,
                "auto_recovery": self.clusters.auto_recovery,
                "max_retry_attempts": self.clusters.max_retry_attempts,
                "default_timeout": self.clusters.default_timeout
            },
            "communication": {
                "message_broker_enabled": self.clusters.message_broker_enabled,
                "ports": self.clusters.get_communication_ports(),
                "message_batch_size": self.clusters.message_batch_size
            },
            "registry": {
                "enabled": self.clusters.registry_enabled,
                "auto_discovery_interval": self.clusters.auto_discovery_interval,
                "persistence": self.clusters.registry_persistence,
                "storage_path": self.clusters.registry_storage_path
            },
            "auto_scaling": {
                "enabled": self.clusters.auto_scaling_enabled,
                "analysis_interval": self.clusters.scaling_analysis_interval,
                "metrics_collection_interval": self.clusters.metrics_collection_interval,
                "default_limits": {
                    "min_agents": self.clusters.default_min_agents,
                    "max_agents": self.clusters.default_max_agents
                }
            },
            "failover": {
                "enabled": self.clusters.failover_enabled,
                "monitoring_interval": self.clusters.failover_monitoring_interval,
                "health_threshold": self.clusters.default_health_threshold,
                "auto_failback": self.clusters.auto_failback
            },
            "topology": {
                "default": self.clusters.default_topology,
                "supported": self.clusters.supported_topologies
            },
            "limits": {
                "max_clusters": self.clusters.max_clusters,
                "max_agents_per_cluster": self.clusters.max_agents_per_cluster,
                "max_connections_per_cluster": self.clusters.max_connections_per_cluster
            },
            "cluster_configs": self.clusters.cluster_configs
        }
    
    def get_cluster_specific_config(self, cluster_id: str) -> Dict[str, Any]:
        """Retorna configuração específica de um cluster"""
        base_config = self.clusters.get_cluster_config(cluster_id)
        
        # Mesclar com configurações globais
        return {
            **base_config,
            "health_check_interval": self.clusters.health_check_interval,
            "communication_ports": self.clusters.get_communication_ports(),
            "auto_discovery_interval": self.clusters.auto_discovery_interval,
            "failover_health_threshold": self.clusters.default_health_threshold
        }
    
    def validate_cluster_config(self, cluster_id: str) -> Dict[str, bool]:
        """Valida configuração de um cluster específico"""
        checks = {}
        
        try:
            config = self.get_cluster_specific_config(cluster_id)
            
            # Validar limites
            checks["min_agents_valid"] = 1 <= config.get("min_agents", 1) <= self.clusters.max_agents_per_cluster
            checks["max_agents_valid"] = config.get("min_agents", 1) <= config.get("max_agents", 10) <= self.clusters.max_agents_per_cluster
            checks["priority_valid"] = 1 <= config.get("priority", 1) <= 10
            
            # Validar portas
            ports = config.get("communication_ports", {})
            checks["ports_available"] = all(1024 <= port <= 65535 for port in ports.values())
            
            # Validar backup clusters
            backup_clusters = config.get("backup_clusters", [])
            checks["backup_clusters_exist"] = all(
                backup_id in self.clusters.cluster_configs 
                for backup_id in backup_clusters
            )
            
            # Validar topologia
            checks["topology_supported"] = self.clusters.validate_topology(self.clusters.default_topology)
            
        except Exception as e:
            logger.error(f"Erro na validação do cluster {cluster_id}: {e}")
            checks["validation_error"] = False
        
        return checks
    
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
            "clusters": {
                "enabled": self.clusters.enabled,
                "orchestrator_enabled": self.clusters.orchestrator_enabled,
                "message_broker_enabled": self.clusters.message_broker_enabled,
                "registry_enabled": self.clusters.registry_enabled,
                "auto_scaling_enabled": self.clusters.auto_scaling_enabled,
                "failover_enabled": self.clusters.failover_enabled,
                "default_topology": self.clusters.default_topology,
                "max_clusters": self.clusters.max_clusters,
                "communication_ports": self.clusters.get_communication_ports(),
                "cluster_count": len(self.clusters.cluster_configs)
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
    
    # Testar configuração de clusters
    print("\n🔗 Testando configuração de clusters...")
    clusters_config = cfg.get_clusters_config()
    print(f"Sistema de clusters: {'✅ HABILITADO' if clusters_config['enabled'] else '❌ DESABILITADO'}")
    print(f"Orquestrador: {'✅' if clusters_config['orchestrator']['enabled'] else '❌'}")
    print(f"Message Broker: {'✅' if clusters_config['communication']['message_broker_enabled'] else '❌'}")
    print(f"Auto-scaling: {'✅' if clusters_config['auto_scaling']['enabled'] else '❌'}")
    print(f"Failover: {'✅' if clusters_config['failover']['enabled'] else '❌'}")
    
    # Testar configurações específicas de clusters
    print("\n📋 Validando clusters individuais...")
    for cluster_id in cfg.clusters.cluster_configs.keys():
        validation = cfg.validate_cluster_config(cluster_id)
        all_valid = all(validation.values())
        emoji = "✅" if all_valid else "⚠️"
        print(f"{emoji} {cluster_id}: {sum(validation.values())}/{len(validation)} checks OK")
        
        if not all_valid:
            failed_checks = [check for check, result in validation.items() if not result]
            print(f"   Falhas: {', '.join(failed_checks)}")
    
    # Testar validação do ambiente
    print("\n🔍 Validando ambiente...")
    env_status = cfg.validate_environment()
    for component, status in env_status.items():
        emoji = "✅" if status else "❌"
        print(f"{emoji} {component}: {'OK' if status else 'FALHA'}")
    
    # Mostrar configurações de comunicação
    print("\n📡 Portas de comunicação:")
    comm_ports = cfg.clusters.get_communication_ports()
    for protocol, port in comm_ports.items():
        print(f"  {protocol.upper()}: {port}")
    
    print("\n✅ Configurações unificadas testadas com sucesso!")