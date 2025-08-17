#!/usr/bin/env python3
"""
🚀 Common - Módulo de Sistemas Otimizados Unificados
Exporta todos os sistemas de otimização implementados
"""

# Cache Manager
from .cache_manager import (
    get_cache, 
    CacheManager, 
    CacheConfig, 
    CachePolicy,
    cached,
    setup_system_caches
)

# Neo4j Connection Pool
from .neo4j_connection_pool import (
    get_neo4j_pool,
    Neo4jConnectionPool,
    Neo4jConfig,
    execute_query,
    execute_transaction,
    get_session
)

# Telemetry System
from .telemetry import (
    get_telemetry,
    TelemetryManager,
    counter,
    gauge,
    histogram,
    timer,
    timed,
    setup_default_alerts
)

# Agent Factory
from .agent_factory import (
    get_agent_factory,
    AgentFactory,
    AgentConfig,
    AgentType,
    create_agent,
    create_researcher,
    create_coder,
    create_tester
)

# Health Monitor
from .health_monitor import (
    get_health_monitor,
    HealthMonitor,
    HealthStatus,
    check_system_health,
    check_component_health
)

# Config Manager
from .config_manager import (
    get_config_manager,
    ConfigManager,
    ConfigFormat,
    ConfigSource,
    optimized_config
)

# Logging
from .logging_config import (
    get_logging_manager,
    get_logger,
    setup_logging_for_module
)

# Validators
from .validators import InputValidator

__version__ = "1.0.0"
__author__ = "Claude Code"

__all__ = [
    # Cache
    'get_cache', 'CacheManager', 'CacheConfig', 'CachePolicy', 'cached', 'setup_system_caches',
    
    # Neo4j
    'get_neo4j_pool', 'Neo4jConnectionPool', 'Neo4jConfig', 'execute_query', 'execute_transaction', 'get_session',
    
    # Telemetry
    'get_telemetry', 'TelemetryManager', 'counter', 'gauge', 'histogram', 'timer', 'timed', 'setup_default_alerts',
    
    # Agent Factory
    'get_agent_factory', 'AgentFactory', 'AgentConfig', 'AgentType', 'create_agent', 'create_researcher', 'create_coder', 'create_tester',
    
    # Health Monitor
    'get_health_monitor', 'HealthMonitor', 'HealthStatus', 'check_system_health', 'check_component_health',
    
    # Config Manager
    'get_config_manager', 'ConfigManager', 'ConfigFormat', 'ConfigSource', 'optimized_config',
    
    # Logging
    'get_logging_manager', 'get_logger', 'setup_logging_for_module',
    
    # Validators
    'InputValidator'
]

def initialize_optimized_systems():
    """
    Inicializa todos os sistemas otimizados de forma coordenada
    
    Returns:
        Dict com instâncias de todos os sistemas
    """
    systems = {}
    
    # Inicializar sistemas na ordem correta de dependências
    
    # 1. Logging (base para todos)
    systems['logging'] = get_logging_manager()
    
    # 2. Cache (usado por outros sistemas)
    setup_system_caches()
    systems['cache'] = get_cache('system')
    
    # 3. Telemetria (monitora outros sistemas)
    systems['telemetry'] = get_telemetry()
    setup_default_alerts()
    
    # 4. Config Manager (configurações otimizadas)
    systems['config'] = get_config_manager()
    
    # 5. Neo4j Pool (database)
    systems['neo4j'] = get_neo4j_pool()
    
    # 6. Agent Factory (criação de agentes)
    systems['agents'] = get_agent_factory()
    
    # 7. Health Monitor (monitora tudo)
    systems['health'] = get_health_monitor()
    
    return systems

def get_system_status():
    """
    Retorna status de todos os sistemas
    
    Returns:
        Dict com status de cada sistema
    """
    status = {}
    
    try:
        # Cache status
        cache = get_cache('system')
        status['cache'] = {
            'status': 'healthy',
            'size': cache.size(),
            'hit_rate': cache.get_stats().hit_rate
        }
    except Exception as e:
        status['cache'] = {'status': 'error', 'error': str(e)}
    
    try:
        # Neo4j status
        pool = get_neo4j_pool()
        pool_stats = pool.get_stats()
        status['neo4j'] = {
            'status': 'healthy' if pool_stats.success_rate > 0.8 else 'degraded',
            'connections': pool_stats.total_connections,
            'success_rate': pool_stats.success_rate
        }
    except Exception as e:
        status['neo4j'] = {'status': 'error', 'error': str(e)}
    
    try:
        # Telemetria status
        telemetry = get_telemetry()
        dashboard = telemetry.get_dashboard_data()
        status['telemetry'] = {
            'status': 'healthy',
            'metrics_count': dashboard['metrics_count']
        }
    except Exception as e:
        status['telemetry'] = {'status': 'error', 'error': str(e)}
    
    try:
        # Agent Factory status
        factory = get_agent_factory()
        factory_stats = factory.get_factory_stats()
        status['agents'] = {
            'status': 'healthy',
            'total_agents': factory_stats['registry_stats']['total_agents'],
            'active_agents': factory_stats['registry_stats']['active_agents']
        }
    except Exception as e:
        status['agents'] = {'status': 'error', 'error': str(e)}
    
    try:
        # Config Manager status
        config_mgr = get_config_manager()
        config_stats = config_mgr.get_stats()
        status['config'] = {
            'status': 'healthy',
            'sources': config_stats['sources_count'],
            'cache_hit_rate': config_stats['cache_stats'].hit_rate
        }
    except Exception as e:
        status['config'] = {'status': 'error', 'error': str(e)}
    
    try:
        # Health Monitor status
        health_mgr = get_health_monitor()
        system_health = health_mgr.get_system_health()
        status['health'] = {
            'status': system_health.overall_status.value,
            'components': len(system_health.components),
            'uptime': system_health.uptime
        }
    except Exception as e:
        status['health'] = {'status': 'error', 'error': str(e)}
    
    return status