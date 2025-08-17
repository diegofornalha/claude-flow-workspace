#!/usr/bin/env python3
"""
🔗 Definição de Clusters - Sistema de Agentes Organizados
Implementação da estrutura base para organizar 27+ agentes em clusters especializados
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Any, Callable
from pathlib import Path
import uuid
from datetime import datetime, timedelta

# Configurar logging
logger = logging.getLogger(__name__)


class ClusterStatus(Enum):
    """Estados possíveis de um cluster"""
    INACTIVE = "inactive"
    STARTING = "starting"
    ACTIVE = "active"
    DEGRADED = "degraded"
    FAILED = "failed"
    STOPPING = "stopping"


class AgentStatus(Enum):
    """Estados possíveis de um agente"""
    OFFLINE = "offline"
    STARTING = "starting"
    ONLINE = "online"
    BUSY = "busy"
    ERROR = "error"
    STOPPING = "stopping"


@dataclass
class AgentInfo:
    """Informações de um agente no cluster"""
    id: str
    name: str
    role: str
    status: AgentStatus = AgentStatus.OFFLINE
    health_score: float = 100.0
    last_ping: Optional[datetime] = None
    capabilities: List[str] = field(default_factory=list)
    current_tasks: int = 0
    max_concurrent_tasks: int = 5
    ports: List[int] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.last_ping is None:
            self.last_ping = datetime.now()
    
    def is_available(self) -> bool:
        """Verifica se o agente está disponível para novas tarefas"""
        return (
            self.status == AgentStatus.ONLINE and
            self.current_tasks < self.max_concurrent_tasks and
            self.health_score > 50.0
        )
    
    def update_health(self, response_time: float = None, error_count: int = 0):
        """Atualiza o score de saúde baseado em métricas"""
        base_score = 100.0
        
        # Penalizar por erros
        if error_count > 0:
            base_score -= min(error_count * 10, 50)
        
        # Penalizar por response time alto
        if response_time and response_time > 1000:  # ms
            base_score -= min((response_time - 1000) / 100, 30)
        
        # Penalizar por ping antigo
        if self.last_ping:
            time_since_ping = (datetime.now() - self.last_ping).total_seconds()
            if time_since_ping > 300:  # 5 minutos
                base_score -= min(time_since_ping / 60, 40)
        
        self.health_score = max(0, min(100, base_score))
        self.last_ping = datetime.now()


class AgentCluster(ABC):
    """Classe base para clusters de agentes"""
    
    def __init__(self, 
                 cluster_id: str,
                 name: str,
                 description: str,
                 max_agents: int = 10):
        self.cluster_id = cluster_id
        self.name = name
        self.description = description
        self.max_agents = max_agents
        self.status = ClusterStatus.INACTIVE
        self.agents: Dict[str, AgentInfo] = {}
        self.created_at = datetime.now()
        self.last_health_check = datetime.now()
        self.message_queue: List[Dict] = []
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'avg_response_time': 0.0,
            'uptime_percentage': 100.0
        }
        
        # Configurações do cluster
        self.config = {
            'auto_scaling': True,
            'health_check_interval': 30,  # segundos
            'max_retry_attempts': 3,
            'load_balancing_strategy': 'round_robin',  # round_robin, least_loaded, health_based
            'failover_enabled': True
        }
        
        logger.info(f"🔗 Cluster '{self.name}' iniciado com ID: {self.cluster_id}")
    
    def register_agent(self, agent_info: AgentInfo) -> bool:
        """Registra um agente no cluster"""
        try:
            if len(self.agents) >= self.max_agents:
                logger.warning(f"❌ Cluster '{self.name}' está no limite máximo de agentes")
                return False
            
            if agent_info.id in self.agents:
                logger.warning(f"⚠️ Agente '{agent_info.id}' já está registrado no cluster")
                return False
            
            self.agents[agent_info.id] = agent_info
            logger.info(f"✅ Agente '{agent_info.name}' registrado no cluster '{self.name}'")
            
            # Auto-start cluster se for o primeiro agente
            if len(self.agents) == 1 and self.status == ClusterStatus.INACTIVE:
                self.start()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao registrar agente: {e}")
            return False
    
    def unregister_agent(self, agent_id: str) -> bool:
        """Remove um agente do cluster"""
        try:
            if agent_id not in self.agents:
                logger.warning(f"⚠️ Agente '{agent_id}' não encontrado no cluster")
                return False
            
            agent_info = self.agents.pop(agent_id)
            logger.info(f"🗑️ Agente '{agent_info.name}' removido do cluster '{self.name}'")
            
            # Auto-stop cluster se ficar sem agentes
            if len(self.agents) == 0:
                self.stop()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao remover agente: {e}")
            return False
    
    def get_available_agents(self) -> List[AgentInfo]:
        """Retorna lista de agentes disponíveis"""
        return [agent for agent in self.agents.values() if agent.is_available()]
    
    def get_agent_by_capability(self, capability: str) -> List[AgentInfo]:
        """Busca agentes por capacidade específica"""
        return [
            agent for agent in self.agents.values()
            if capability in agent.capabilities and agent.is_available()
        ]
    
    def select_best_agent(self, 
                         criteria: Dict[str, Any] = None) -> Optional[AgentInfo]:
        """Seleciona o melhor agente baseado nos critérios"""
        available_agents = self.get_available_agents()
        
        if not available_agents:
            return None
        
        strategy = self.config.get('load_balancing_strategy', 'round_robin')
        
        if strategy == 'health_based':
            # Ordenar por health score
            return max(available_agents, key=lambda x: x.health_score)
        
        elif strategy == 'least_loaded':
            # Ordenar por menor carga atual
            return min(available_agents, key=lambda x: x.current_tasks)
        
        else:  # round_robin (padrão)
            # Implementação simples baseada em timestamp
            return min(available_agents, key=lambda x: x.last_ping or datetime.min)
    
    def health_check(self) -> Dict[str, Any]:
        """Executa verificação de saúde do cluster"""
        try:
            healthy_agents = 0
            total_agents = len(self.agents)
            avg_health = 0.0
            
            for agent in self.agents.values():
                if agent.health_score > 70:
                    healthy_agents += 1
                avg_health += agent.health_score
            
            if total_agents > 0:
                avg_health /= total_agents
                health_percentage = (healthy_agents / total_agents) * 100
            else:
                health_percentage = 0
                avg_health = 0
            
            # Determinar status do cluster
            if health_percentage >= 80:
                new_status = ClusterStatus.ACTIVE
            elif health_percentage >= 50:
                new_status = ClusterStatus.DEGRADED
            elif total_agents == 0:
                new_status = ClusterStatus.INACTIVE
            else:
                new_status = ClusterStatus.FAILED
            
            self.status = new_status
            self.last_health_check = datetime.now()
            
            health_report = {
                'cluster_id': self.cluster_id,
                'cluster_name': self.name,
                'status': self.status.value,
                'total_agents': total_agents,
                'healthy_agents': healthy_agents,
                'health_percentage': health_percentage,
                'avg_health_score': avg_health,
                'uptime': (datetime.now() - self.created_at).total_seconds(),
                'last_check': self.last_health_check.isoformat()
            }
            
            logger.debug(f"🏥 Health check do cluster '{self.name}': {health_percentage}%")
            return health_report
            
        except Exception as e:
            logger.error(f"❌ Erro no health check do cluster '{self.name}': {e}")
            return {'error': str(e)}
    
    def start(self):
        """Inicia o cluster"""
        if self.status == ClusterStatus.INACTIVE:
            self.status = ClusterStatus.STARTING
            logger.info(f"🚀 Iniciando cluster '{self.name}'...")
            
            # Lógica de inicialização personalizada
            self._on_start()
            
            self.status = ClusterStatus.ACTIVE
            logger.info(f"✅ Cluster '{self.name}' está ativo")
    
    def stop(self):
        """Para o cluster"""
        if self.status in [ClusterStatus.ACTIVE, ClusterStatus.DEGRADED]:
            self.status = ClusterStatus.STOPPING
            logger.info(f"🛑 Parando cluster '{self.name}'...")
            
            # Lógica de parada personalizada
            self._on_stop()
            
            self.status = ClusterStatus.INACTIVE
            logger.info(f"⏸️ Cluster '{self.name}' parado")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas do cluster"""
        uptime = (datetime.now() - self.created_at).total_seconds()
        
        return {
            'cluster_id': self.cluster_id,
            'name': self.name,
            'status': self.status.value,
            'agent_count': len(self.agents),
            'available_agents': len(self.get_available_agents()),
            'uptime_seconds': uptime,
            'uptime_hours': uptime / 3600,
            'metrics': self.metrics.copy(),
            'config': self.config.copy()
        }
    
    @abstractmethod
    def _on_start(self):
        """Hook para lógica de inicialização específica do cluster"""
        pass
    
    @abstractmethod
    def _on_stop(self):
        """Hook para lógica de parada específica do cluster"""
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte cluster para dicionário"""
        return {
            'cluster_id': self.cluster_id,
            'name': self.name,
            'description': self.description,
            'status': self.status.value,
            'agent_count': len(self.agents),
            'max_agents': self.max_agents,
            'created_at': self.created_at.isoformat(),
            'last_health_check': self.last_health_check.isoformat(),
            'agents': {
                agent_id: {
                    'name': agent.name,
                    'role': agent.role,
                    'status': agent.status.value,
                    'health_score': agent.health_score,
                    'current_tasks': agent.current_tasks,
                    'capabilities': agent.capabilities
                }
                for agent_id, agent in self.agents.items()
            },
            'metrics': self.metrics.copy(),
            'config': self.config.copy()
        }


# ==================== IMPLEMENTAÇÃO DOS 6 CLUSTERS PRINCIPAIS ====================

class CoreCluster(AgentCluster):
    """Cluster principal com agentes fundamentais"""
    
    def __init__(self):
        super().__init__(
            cluster_id="core_cluster",
            name="Core Operations",
            description="Agentes fundamentais para operações principais do sistema",
            max_agents=8
        )
        self.core_agents = ['planner', 'researcher', 'coder', 'tester', 'reviewer']
    
    def _on_start(self):
        """Inicialização específica do cluster core"""
        logger.info("🎯 Inicializando cluster Core - agentes fundamentais")
        # Lógica específica para agentes core
    
    def _on_stop(self):
        """Parada específica do cluster core"""
        logger.info("⏸️ Parando cluster Core")


class CoordinationCluster(AgentCluster):
    """Cluster para coordenação e consenso"""
    
    def __init__(self):
        super().__init__(
            cluster_id="coordination_cluster",
            name="Coordination & Consensus",
            description="Agentes responsáveis por coordenação e consenso bizantino",
            max_agents=5
        )
        self.coordination_agents = ['adaptive_coordinator', 'consensus_builder']
    
    def _on_start(self):
        """Inicialização específica do cluster de coordenação"""
        logger.info("🤝 Inicializando cluster Coordination - consenso e coordenação")
        # Configurar protocolos de consenso
    
    def _on_stop(self):
        """Parada específica do cluster de coordenação"""
        logger.info("⏸️ Parando cluster Coordination")


class MemoryCluster(AgentCluster):
    """Cluster para gerenciamento de memória e conhecimento"""
    
    def __init__(self):
        super().__init__(
            cluster_id="memory_cluster",
            name="Memory & Knowledge",
            description="Agentes para gerenciamento de memória e análise do Knowledge Graph",
            max_agents=6
        )
        self.memory_agents = ['memory_guardian', 'memory_guardian_analyzer', 'neo4j_dashboard']
    
    def _on_start(self):
        """Inicialização específica do cluster de memória"""
        logger.info("🧠 Inicializando cluster Memory - knowledge graph e memória")
        # Configurar conexões Neo4j
    
    def _on_stop(self):
        """Parada específica do cluster de memória"""
        logger.info("⏸️ Parando cluster Memory")


class MCPCluster(AgentCluster):
    """Cluster para protocolos MCP e A2A"""
    
    def __init__(self):
        super().__init__(
            cluster_id="mcp_cluster",
            name="MCP & A2A Protocols",
            description="Agentes para gerenciamento de protocolos MCP e comunicação A2A",
            max_agents=8
        )
        self.mcp_agents = ['mcp_manager', 'a2a_coherence_checker', 'a2a_agent_template', 'a2a_template']
    
    def _on_start(self):
        """Inicialização específica do cluster MCP"""
        logger.info("📡 Inicializando cluster MCP - protocolos e comunicação")
        # Configurar servidores MCP
    
    def _on_stop(self):
        """Parada específica do cluster MCP"""
        logger.info("⏸️ Parando cluster MCP")


class AnalyticsCluster(AgentCluster):
    """Cluster para análise e métricas"""
    
    def __init__(self):
        super().__init__(
            cluster_id="analytics_cluster",
            name="Analytics & Performance",
            description="Agentes para análise de performance e métricas do sistema",
            max_agents=5
        )
        self.analytics_agents = ['performance_analyzer', 'timeline_estimator']
    
    def _on_start(self):
        """Inicialização específica do cluster analytics"""
        logger.info("📊 Inicializando cluster Analytics - métricas e performance")
        # Configurar coleta de métricas
    
    def _on_stop(self):
        """Parada específica do cluster analytics"""
        logger.info("⏸️ Parando cluster Analytics")


class DiscoveryCluster(AgentCluster):
    """Cluster para service discovery"""
    
    def __init__(self):
        super().__init__(
            cluster_id="discovery_cluster",
            name="Service Discovery",
            description="Agentes para descoberta de serviços e comunicação externa",
            max_agents=10
        )
        self.discovery_ports = [9999, 3002, 3003, 5000, 5001, 12000]
        self.discovery_agents = ['helloworld', 'marvin', 'gemini', 'ui', 'analytics', 'a2a-inspector']
    
    def _on_start(self):
        """Inicialização específica do cluster discovery"""
        logger.info("🔍 Inicializando cluster Discovery - service discovery")
        # Configurar escaneamento de portas
    
    def _on_stop(self):
        """Parada específica do cluster discovery"""
        logger.info("⏸️ Parando cluster Discovery")


# ==================== FACTORY PARA CRIAÇÃO DE CLUSTERS ====================

class ClusterFactory:
    """Factory para criar instâncias dos clusters"""
    
    @staticmethod
    def create_all_clusters() -> Dict[str, AgentCluster]:
        """Cria todos os clusters principais"""
        clusters = {
            'core': CoreCluster(),
            'coordination': CoordinationCluster(),
            'memory': MemoryCluster(),
            'mcp': MCPCluster(),
            'analytics': AnalyticsCluster(),
            'discovery': DiscoveryCluster()
        }
        
        logger.info(f"🏭 Factory criou {len(clusters)} clusters")
        return clusters
    
    @staticmethod
    def create_cluster(cluster_type: str) -> Optional[AgentCluster]:
        """Cria um cluster específico por tipo"""
        cluster_map = {
            'core': CoreCluster,
            'coordination': CoordinationCluster,
            'memory': MemoryCluster,
            'mcp': MCPCluster,
            'analytics': AnalyticsCluster,
            'discovery': DiscoveryCluster
        }
        
        if cluster_type in cluster_map:
            return cluster_map[cluster_type]()
        
        logger.error(f"❌ Tipo de cluster desconhecido: {cluster_type}")
        return None


# ==================== UTILITÁRIOS ====================

def populate_clusters_with_known_agents(clusters: Dict[str, AgentCluster]) -> None:
    """Popula clusters com agentes conhecidos do sistema"""
    
    # Agentes Core
    core_agents_data = [
        ('planner', 'planner', ['strategic_planning', 'architecture_design']),
        ('researcher', 'researcher', ['information_gathering', 'analysis']),
        ('coder', 'coder', ['implementation', 'debugging']),
        ('tester', 'tester', ['quality_assurance', 'testing']),
        ('reviewer', 'reviewer', ['code_review', 'quality_control'])
    ]
    
    for agent_id, role, capabilities in core_agents_data:
        agent_info = AgentInfo(
            id=agent_id,
            name=agent_id.title(),
            role=role,
            capabilities=capabilities,
            status=AgentStatus.ONLINE
        )
        clusters['core'].register_agent(agent_info)
    
    # Agentes Coordination
    coordination_agents_data = [
        ('adaptive_coordinator', 'adaptive-coordinator', ['dynamic_coordination', 'load_balancing']),
        ('consensus_builder', 'consensus-builder', ['byzantine_consensus', 'distributed_agreement'])
    ]
    
    for agent_id, role, capabilities in coordination_agents_data:
        agent_info = AgentInfo(
            id=agent_id,
            name=agent_id.replace('_', ' ').title(),
            role=role,
            capabilities=capabilities,
            status=AgentStatus.ONLINE
        )
        clusters['coordination'].register_agent(agent_info)
    
    # Agentes Memory
    memory_agents_data = [
        ('memory_guardian', 'memory_specialist', ['memory_management', 'pattern_detection']),
        ('memory_guardian_analyzer', 'memory_analyst', ['data_analysis', 'cleanup']),
        ('neo4j_dashboard', 'dashboard_agent', ['visualization', 'monitoring'])
    ]
    
    for agent_id, role, capabilities in memory_agents_data:
        agent_info = AgentInfo(
            id=agent_id,
            name=agent_id.replace('_', ' ').title(),
            role=role,
            capabilities=capabilities,
            status=AgentStatus.ONLINE
        )
        clusters['memory'].register_agent(agent_info)
    
    # Agentes MCP
    mcp_agents_data = [
        ('mcp_manager', 'mcp-manager', ['protocol_management', 'server_coordination']),
        ('a2a_coherence_checker', 'a2a-coherence-checker', ['coherence_validation', 'message_integrity']),
        ('a2a_agent_template', 'a2a-agent-template', ['template_creation', 'protocol_standards']),
        ('a2a_template', 'a2a-template', ['base_template', 'communication_patterns'])
    ]
    
    for agent_id, role, capabilities in mcp_agents_data:
        agent_info = AgentInfo(
            id=agent_id,
            name=agent_id.replace('_', ' ').title(),
            role=role,
            capabilities=capabilities,
            status=AgentStatus.ONLINE
        )
        clusters['mcp'].register_agent(agent_info)
    
    # Agentes Analytics
    analytics_agents_data = [
        ('performance_analyzer', 'performance-analyzer', ['metrics_analysis', 'bottleneck_detection']),
        ('timeline_estimator', 'timeline-estimator', ['time_estimation', 'planning_analysis'])
    ]
    
    for agent_id, role, capabilities in analytics_agents_data:
        agent_info = AgentInfo(
            id=agent_id,
            name=agent_id.replace('_', ' ').title(),
            role=role,
            capabilities=capabilities,
            status=AgentStatus.ONLINE
        )
        clusters['analytics'].register_agent(agent_info)
    
    # Agentes Discovery (baseado nos conhecidos do sistema)
    discovery_agents_data = [
        ('helloworld', 'a2a_agent', ['basic_communication'], [9999]),
        ('marvin', 'a2a_agent', ['advanced_ai'], [3002]),
        ('gemini', 'a2a_agent', ['google_integration'], [3003]),
        ('ui', 'web_interface', ['user_interface'], [12000]),
        ('analytics_service', 'analytics_service', ['data_collection'], [5000]),
        ('a2a_inspector', 'debug_agent', ['protocol_inspection'], [5001])
    ]
    
    for agent_id, role, capabilities, ports in discovery_agents_data:
        agent_info = AgentInfo(
            id=agent_id,
            name=agent_id.replace('_', ' ').title(),
            role=role,
            capabilities=capabilities,
            ports=ports,
            status=AgentStatus.ONLINE
        )
        clusters['discovery'].register_agent(agent_info)
    
    logger.info("🎯 Clusters populados com agentes conhecidos")


if __name__ == "__main__":
    # Teste da implementação
    logger.info("🧪 Testando implementação de clusters...")
    
    # Criar todos os clusters
    clusters = ClusterFactory.create_all_clusters()
    
    # Popular com agentes conhecidos
    populate_clusters_with_known_agents(clusters)
    
    # Mostrar status de todos os clusters
    print("\n" + "="*60)
    print("📊 STATUS DOS CLUSTERS")
    print("="*60)
    
    for cluster_name, cluster in clusters.items():
        health = cluster.health_check()
        print(f"\n🔗 {cluster.name}")
        print(f"   Status: {cluster.status.value}")
        print(f"   Agentes: {len(cluster.agents)}/{cluster.max_agents}")
        print(f"   Saúde: {health.get('health_percentage', 0):.1f}%")
        print(f"   Disponíveis: {len(cluster.get_available_agents())}")
    
    print("\n✅ Teste concluído com sucesso!")