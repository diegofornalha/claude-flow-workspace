#!/usr/bin/env python3
"""
🔗 Sistema de Clusters - Módulo Principal
Organização e gerenciamento de 27+ agentes em clusters especializados
"""

__version__ = "1.0.0"
__author__ = "Claude Code"
__description__ = "Sistema completo de clusters para organização de agentes"

# Imports principais
from .cluster_definition import (
    AgentCluster,
    ClusterStatus,
    AgentStatus,
    AgentInfo,
    CoreCluster,
    CoordinationCluster,
    MemoryCluster,
    MCPCluster,
    AnalyticsCluster,
    DiscoveryCluster,
    ClusterFactory,
    populate_clusters_with_known_agents
)

from .cluster_orchestrator import (
    ClusterOrchestrator,
    get_orchestrator,
    setup_default_routing_rules
)

from .inter_cluster_comm import (
    MessageBroker,
    EventBus,
    Message,
    MessageType,
    MessagePriority,
    get_message_broker,
    send_cluster_message
)

from .cluster_registry import (
    ClusterRegistry,
    ServiceEndpoint,
    ServiceType,
    get_cluster_registry
)

from .cluster_manager import (
    ClusterManager,
    AutoScaler,
    FailoverManager,
    get_cluster_manager
)

from .cluster_dashboard import (
    ClusterDashboard,
    InteractiveDashboard,
    create_simple_dashboard,
    show_cluster_overview
)

# Funcionalidades de alto nível
async def initialize_cluster_system(config=None):
    """
    Inicializa sistema completo de clusters
    
    Returns:
        dict: Componentes inicializados
    """
    from config.unified_config import get_unified_config
    
    # Carregar configuração
    if config is None:
        config = get_unified_config()
    
    # Verificar se clusters estão habilitados
    if not config.clusters.enabled:
        raise RuntimeError("Sistema de clusters está desabilitado na configuração")
    
    # Inicializar componentes
    orchestrator = get_orchestrator()
    registry = get_cluster_registry()
    manager = get_cluster_manager()
    
    # Iniciar componentes
    await orchestrator.start()
    await registry.start()
    await manager.start(orchestrator)
    
    # Configurar regras de roteamento
    await setup_default_routing_rules(orchestrator)
    
    return {
        'orchestrator': orchestrator,
        'registry': registry,
        'manager': manager,
        'config': config
    }


async def shutdown_cluster_system(components):
    """
    Para sistema de clusters de forma limpa
    
    Args:
        components: Dicionário retornado por initialize_cluster_system
    """
    try:
        if 'manager' in components:
            await components['manager'].stop()
        
        if 'registry' in components:
            await components['registry'].stop()
        
        if 'orchestrator' in components:
            await components['orchestrator'].stop()
    
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erro no shutdown do sistema de clusters: {e}")


def get_cluster_status():
    """
    Retorna status rápido de todos os clusters
    
    Returns:
        dict: Status consolidado
    """
    try:
        orchestrator = get_orchestrator()
        registry = get_cluster_registry()
        manager = get_cluster_manager()
        
        return {
            'orchestrator_running': orchestrator.is_running if orchestrator else False,
            'registry_running': registry.running if registry else False,
            'manager_running': manager.running if manager else False,
            'total_clusters': len(orchestrator.clusters) if orchestrator and orchestrator.is_running else 0,
            'system_healthy': all([
                orchestrator.is_running if orchestrator else False,
                registry.running if registry else False,
                manager.running if manager else False
            ])
        }
    except Exception:
        return {
            'orchestrator_running': False,
            'registry_running': False,
            'manager_running': False,
            'total_clusters': 0,
            'system_healthy': False,
            'error': 'Sistema não inicializado'
        }


# Configurações padrão
DEFAULT_CLUSTER_CONFIGS = {
    'core_cluster': {
        'min_agents': 3,
        'max_agents': 8,
        'priority': 1,
        'capabilities': ['strategic_planning', 'research', 'implementation', 'testing', 'review']
    },
    'coordination_cluster': {
        'min_agents': 2,
        'max_agents': 5,
        'priority': 1,
        'capabilities': ['coordination', 'consensus', 'load_balancing']
    },
    'memory_cluster': {
        'min_agents': 2,
        'max_agents': 6,
        'priority': 2,
        'capabilities': ['memory_management', 'data_analysis', 'visualization']
    },
    'mcp_cluster': {
        'min_agents': 2,
        'max_agents': 8,
        'priority': 2,
        'capabilities': ['protocol_management', 'communication', 'template_creation']
    },
    'analytics_cluster': {
        'min_agents': 1,
        'max_agents': 5,
        'priority': 3,
        'capabilities': ['performance_analysis', 'metrics', 'time_estimation']
    },
    'discovery_cluster': {
        'min_agents': 1,
        'max_agents': 15,
        'priority': 3,
        'capabilities': ['service_discovery', 'network_scanning', 'agent_detection']
    }
}

# Metadados do módulo
__all__ = [
    # Classes principais
    'AgentCluster',
    'ClusterOrchestrator',
    'MessageBroker',
    'ClusterRegistry',
    'ClusterManager',
    'ClusterDashboard',
    
    # Enums e tipos
    'ClusterStatus',
    'AgentStatus',
    'MessageType',
    'MessagePriority',
    'ServiceType',
    
    # Factory e utilitários
    'ClusterFactory',
    'get_orchestrator',
    'get_cluster_registry',
    'get_cluster_manager',
    'get_message_broker',
    
    # Funções de alto nível
    'initialize_cluster_system',
    'shutdown_cluster_system',
    'get_cluster_status',
    'show_cluster_overview',
    
    # Constantes
    'DEFAULT_CLUSTER_CONFIGS',
]


if __name__ == "__main__":
    # Demonstração rápida do módulo
    import asyncio
    
    async def demo():
        print(f"🔗 Sistema de Clusters v{__version__}")
        print(f"📝 {__description__}")
        print("\n📊 Status inicial:")
        
        status = get_cluster_status()
        for key, value in status.items():
            emoji = "✅" if value else "❌" if isinstance(value, bool) else "ℹ️"
            print(f"  {emoji} {key}: {value}")
        
        print(f"\n🏭 Clusters configurados: {len(DEFAULT_CLUSTER_CONFIGS)}")
        for cluster_id, config in DEFAULT_CLUSTER_CONFIGS.items():
            print(f"  - {cluster_id}: {config['min_agents']}-{config['max_agents']} agentes")
        
        print("\n✅ Módulo carregado com sucesso!")
        print("\nPara inicializar o sistema completo:")
        print("  components = await initialize_cluster_system()")
        print("\nPara ver dashboard:")
        print("  await show_cluster_overview()")
    
    asyncio.run(demo())