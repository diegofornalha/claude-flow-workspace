#!/usr/bin/env python3
"""
🎼 Orquestrador de Clusters - Gerenciamento Central de Agentes
Implementação do singleton para coordenar todos os clusters e roteamento de mensagens
"""

import asyncio
import json
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Union
from pathlib import Path
import uuid
import weakref

from .cluster_definition import (
    AgentCluster, ClusterStatus, AgentStatus, AgentInfo,
    ClusterFactory, populate_clusters_with_known_agents
)

# Configurar logging
logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Estados do Circuit Breaker"""
    CLOSED = "closed"      # Funcionando normalmente
    OPEN = "open"          # Falha detectada, bloqueando requests
    HALF_OPEN = "half_open"  # Testando recuperação


@dataclass
class CircuitBreaker:
    """Circuit Breaker para cada cluster"""
    failure_threshold: int = 5
    timeout: int = 60  # segundos
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    half_open_max_calls: int = 3
    half_open_calls: int = 0
    
    def call(self, func: Callable, *args, **kwargs):
        """Executa função com circuit breaker"""
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_calls = 0
            else:
                raise Exception("Circuit breaker is OPEN")
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                raise Exception("Circuit breaker HALF_OPEN call limit exceeded")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Verifica se deve tentar resetar o circuit breaker"""
        if self.last_failure_time:
            return (datetime.now() - self.last_failure_time).seconds >= self.timeout
        return False
    
    def _on_success(self):
        """Handler para sucesso"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = 0
    
    def _on_failure(self):
        """Handler para falha"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN


@dataclass
class LoadBalancingStats:
    """Estatísticas para balanceamento de carga"""
    cluster_id: str
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_response_time: float = 0.0
    last_request_time: Optional[datetime] = None
    weight: float = 1.0  # Peso para balanceamento


@dataclass
class RoutingRule:
    """Regra de roteamento de mensagens"""
    rule_id: str
    pattern: str  # regex pattern
    target_cluster: str
    priority: int = 1
    conditions: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


class ClusterOrchestrator:
    """
    Orquestrador singleton para gerenciamento de todos os clusters
    Responsável por:
    - Gerenciamento de ciclo de vida dos clusters
    - Roteamento de mensagens entre clusters
    - Balanceamento de carga automático
    - Circuit breaker por cluster
    - Métricas de performance
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Implementação singleton thread-safe"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Inicializa o orquestrador (apenas uma vez)"""
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.clusters: Dict[str, AgentCluster] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.load_balancing_stats: Dict[str, LoadBalancingStats] = {}
        self.routing_rules: List[RoutingRule] = []
        self.message_queue = asyncio.Queue()
        self.is_running = False
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="orchestrator")
        
        # Métricas globais
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'avg_response_time': 0.0,
            'clusters_active': 0,
            'agents_total': 0,
            'agents_available': 0,
            'uptime': 0.0
        }
        
        self.started_at = datetime.now()
        
        # Configurações
        self.config = {
            'health_check_interval': 30,  # segundos
            'auto_recovery': True,
            'max_retry_attempts': 3,
            'default_timeout': 5.0,  # segundos
            'message_batch_size': 100,
            'enable_metrics': True,
            'debug_mode': False
        }
        
        logger.info("🎼 ClusterOrchestrator inicializado (Singleton)")
    
    async def start(self):
        """Inicia o orquestrador"""
        if self.is_running:
            logger.warning("⚠️ Orquestrador já está em execução")
            return
        
        self.is_running = True
        logger.info("🚀 Iniciando ClusterOrchestrator...")
        
        # Criar clusters padrão
        await self._initialize_default_clusters()
        
        # Iniciar tarefas assíncronas
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._message_processor())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("✅ ClusterOrchestrator iniciado com sucesso")
    
    async def stop(self):
        """Para o orquestrador"""
        if not self.is_running:
            return
        
        self.is_running = False
        logger.info("🛑 Parando ClusterOrchestrator...")
        
        # Parar todos os clusters
        for cluster in self.clusters.values():
            cluster.stop()
        
        # Limpar recursos
        self.executor.shutdown(wait=True)
        
        logger.info("⏸️ ClusterOrchestrator parado")
    
    async def _initialize_default_clusters(self):
        """Inicializa clusters padrão"""
        logger.info("🏭 Inicializando clusters padrão...")
        
        # Criar todos os clusters
        default_clusters = ClusterFactory.create_all_clusters()
        
        for cluster_name, cluster in default_clusters.items():
            await self.register_cluster(cluster)
        
        # Popular com agentes conhecidos
        populate_clusters_with_known_agents(self.clusters)
        
        logger.info(f"✅ {len(self.clusters)} clusters inicializados")
    
    async def register_cluster(self, cluster: AgentCluster) -> bool:
        """Registra um cluster no orquestrador"""
        try:
            cluster_id = cluster.cluster_id
            
            if cluster_id in self.clusters:
                logger.warning(f"⚠️ Cluster '{cluster_id}' já está registrado")
                return False
            
            # Registrar cluster
            self.clusters[cluster_id] = cluster
            
            # Inicializar circuit breaker
            self.circuit_breakers[cluster_id] = CircuitBreaker()
            
            # Inicializar estatísticas
            self.load_balancing_stats[cluster_id] = LoadBalancingStats(cluster_id)
            
            # Iniciar cluster
            cluster.start()
            
            logger.info(f"✅ Cluster '{cluster.name}' registrado e iniciado")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao registrar cluster: {e}")
            return False
    
    async def unregister_cluster(self, cluster_id: str) -> bool:
        """Remove um cluster do orquestrador"""
        try:
            if cluster_id not in self.clusters:
                logger.warning(f"⚠️ Cluster '{cluster_id}' não encontrado")
                return False
            
            cluster = self.clusters[cluster_id]
            cluster.stop()
            
            # Remover referências
            del self.clusters[cluster_id]
            del self.circuit_breakers[cluster_id]
            del self.load_balancing_stats[cluster_id]
            
            logger.info(f"🗑️ Cluster '{cluster.name}' removido")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao remover cluster: {e}")
            return False
    
    def route_message(self, 
                     message: Dict[str, Any], 
                     target_cluster: str = None,
                     target_capability: str = None) -> Optional[str]:
        """
        Roteia mensagem para cluster/agente apropriado
        Retorna o ID do cluster que processará a mensagem
        """
        try:
            # Tentar roteamento direto por cluster
            if target_cluster and target_cluster in self.clusters:
                cluster = self.clusters[target_cluster]
                if cluster.status == ClusterStatus.ACTIVE:
                    return target_cluster
            
            # Roteamento por capacidade
            if target_capability:
                for cluster_id, cluster in self.clusters.items():
                    agents = cluster.get_agent_by_capability(target_capability)
                    if agents and cluster.status == ClusterStatus.ACTIVE:
                        return cluster_id
            
            # Roteamento por regras
            for rule in sorted(self.routing_rules, key=lambda x: x.priority):
                if rule.enabled and self._matches_rule(message, rule):
                    if rule.target_cluster in self.clusters:
                        return rule.target_cluster
            
            # Fallback: encontrar qualquer cluster ativo
            for cluster_id, cluster in self.clusters.items():
                if cluster.status == ClusterStatus.ACTIVE:
                    available_agents = cluster.get_available_agents()
                    if available_agents:
                        return cluster_id
            
            logger.warning("⚠️ Nenhum cluster disponível para rotear mensagem")
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro no roteamento: {e}")
            return None
    
    def _matches_rule(self, message: Dict[str, Any], rule: RoutingRule) -> bool:
        """Verifica se mensagem match com regra de roteamento"""
        import re
        
        # Match por padrão no conteúdo da mensagem
        message_str = json.dumps(message, default=str)
        if re.search(rule.pattern, message_str, re.IGNORECASE):
            return True
        
        # Match por condições específicas
        for key, expected_value in rule.conditions.items():
            if key in message and message[key] == expected_value:
                return True
        
        return False
    
    async def send_message(self, 
                          message: Dict[str, Any],
                          target_cluster: str = None,
                          target_capability: str = None,
                          timeout: float = None) -> Dict[str, Any]:
        """Envia mensagem para cluster apropriado"""
        start_time = time.time()
        timeout = timeout or self.config['default_timeout']
        
        try:
            # Rotear mensagem
            cluster_id = self.route_message(message, target_cluster, target_capability)
            
            if not cluster_id:
                raise Exception("Nenhum cluster disponível")
            
            # Verificar circuit breaker
            circuit_breaker = self.circuit_breakers[cluster_id]
            
            # Executar com circuit breaker
            result = circuit_breaker.call(
                self._execute_message_on_cluster,
                cluster_id, message, timeout
            )
            
            # Atualizar métricas
            response_time = (time.time() - start_time) * 1000  # ms
            await self._update_metrics(cluster_id, True, response_time)
            
            return {
                'success': True,
                'result': result,
                'cluster_id': cluster_id,
                'response_time_ms': response_time
            }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            await self._update_metrics(cluster_id if 'cluster_id' in locals() else None, False, response_time)
            
            logger.error(f"❌ Erro ao enviar mensagem: {e}")
            return {
                'success': False,
                'error': str(e),
                'response_time_ms': response_time
            }
    
    def _execute_message_on_cluster(self, 
                                   cluster_id: str, 
                                   message: Dict[str, Any], 
                                   timeout: float) -> Any:
        """Executa mensagem em cluster específico"""
        cluster = self.clusters[cluster_id]
        
        # Selecionar melhor agente
        agent = cluster.select_best_agent()
        
        if not agent:
            raise Exception(f"Nenhum agente disponível no cluster '{cluster_id}'")
        
        # Incrementar contador de tarefas do agente
        agent.current_tasks += 1
        
        try:
            # Simular processamento (em implementação real, seria chamada para o agente)
            # Aqui você integraria com o sistema real de agentes
            result = {
                'processed_by': agent.name,
                'cluster': cluster.name,
                'message': message,
                'timestamp': datetime.now().isoformat()
            }
            
            return result
            
        finally:
            # Decrementar contador de tarefas
            agent.current_tasks = max(0, agent.current_tasks - 1)
    
    async def _update_metrics(self, cluster_id: str, success: bool, response_time: float):
        """Atualiza métricas de performance"""
        self.metrics['total_requests'] += 1
        
        if success:
            self.metrics['successful_requests'] += 1
        else:
            self.metrics['failed_requests'] += 1
        
        # Atualizar média de response time
        total_requests = self.metrics['total_requests']
        current_avg = self.metrics['avg_response_time']
        self.metrics['avg_response_time'] = (current_avg * (total_requests - 1) + response_time) / total_requests
        
        # Atualizar estatísticas do cluster
        if cluster_id and cluster_id in self.load_balancing_stats:
            stats = self.load_balancing_stats[cluster_id]
            stats.request_count += 1
            stats.last_request_time = datetime.now()
            
            if success:
                stats.success_count += 1
            else:
                stats.failure_count += 1
            
            # Atualizar média de response time do cluster
            stats.avg_response_time = (
                stats.avg_response_time * (stats.request_count - 1) + response_time
            ) / stats.request_count
    
    def add_routing_rule(self, rule: RoutingRule) -> bool:
        """Adiciona regra de roteamento"""
        try:
            # Verificar se regra já existe
            existing = next((r for r in self.routing_rules if r.rule_id == rule.rule_id), None)
            if existing:
                logger.warning(f"⚠️ Regra '{rule.rule_id}' já existe")
                return False
            
            self.routing_rules.append(rule)
            logger.info(f"✅ Regra de roteamento '{rule.rule_id}' adicionada")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao adicionar regra: {e}")
            return False
    
    def remove_routing_rule(self, rule_id: str) -> bool:
        """Remove regra de roteamento"""
        try:
            original_count = len(self.routing_rules)
            self.routing_rules = [r for r in self.routing_rules if r.rule_id != rule_id]
            
            if len(self.routing_rules) < original_count:
                logger.info(f"🗑️ Regra '{rule_id}' removida")
                return True
            else:
                logger.warning(f"⚠️ Regra '{rule_id}' não encontrada")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao remover regra: {e}")
            return False
    
    async def _health_check_loop(self):
        """Loop de health check de todos os clusters"""
        while self.is_running:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.config['health_check_interval'])
            except Exception as e:
                logger.error(f"❌ Erro no health check loop: {e}")
                await asyncio.sleep(5)
    
    async def _perform_health_checks(self):
        """Executa health check em todos os clusters"""
        tasks = []
        
        for cluster_id, cluster in self.clusters.items():
            task = asyncio.create_task(self._health_check_cluster(cluster))
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _health_check_cluster(self, cluster: AgentCluster):
        """Health check de um cluster específico"""
        try:
            health_report = cluster.health_check()
            
            # Auto-recovery se necessário
            if self.config['auto_recovery']:
                if cluster.status == ClusterStatus.FAILED:
                    logger.warning(f"🔄 Tentando recuperar cluster '{cluster.name}'")
                    cluster.start()
                    
        except Exception as e:
            logger.error(f"❌ Health check falhou para '{cluster.name}': {e}")
    
    async def _message_processor(self):
        """Processa mensagens da queue"""
        while self.is_running:
            try:
                # Processar batch de mensagens
                messages = []
                for _ in range(self.config['message_batch_size']):
                    try:
                        message = await asyncio.wait_for(
                            self.message_queue.get(), 
                            timeout=1.0
                        )
                        messages.append(message)
                    except asyncio.TimeoutError:
                        break
                
                if messages:
                    await self._process_message_batch(messages)
                    
            except Exception as e:
                logger.error(f"❌ Erro no processador de mensagens: {e}")
                await asyncio.sleep(1)
    
    async def _process_message_batch(self, messages: List[Dict[str, Any]]):
        """Processa batch de mensagens"""
        tasks = [
            self.send_message(msg) 
            for msg in messages
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ Erro ao processar mensagem {i}: {result}")
    
    async def _metrics_collector(self):
        """Coleta métricas do sistema"""
        while self.is_running:
            try:
                await self._collect_system_metrics()
                await asyncio.sleep(60)  # Coletar a cada minuto
            except Exception as e:
                logger.error(f"❌ Erro na coleta de métricas: {e}")
                await asyncio.sleep(10)
    
    async def _collect_system_metrics(self):
        """Coleta métricas do sistema"""
        # Contar clusters ativos
        active_clusters = sum(
            1 for cluster in self.clusters.values()
            if cluster.status == ClusterStatus.ACTIVE
        )
        
        # Contar agentes
        total_agents = sum(len(cluster.agents) for cluster in self.clusters.values())
        available_agents = sum(
            len(cluster.get_available_agents()) 
            for cluster in self.clusters.values()
        )
        
        # Calcular uptime
        uptime = (datetime.now() - self.started_at).total_seconds()
        
        # Atualizar métricas
        self.metrics.update({
            'clusters_active': active_clusters,
            'agents_total': total_agents,
            'agents_available': available_agents,
            'uptime': uptime
        })
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status completo do orquestrador"""
        return {
            'orchestrator': {
                'is_running': self.is_running,
                'started_at': self.started_at.isoformat(),
                'uptime_seconds': (datetime.now() - self.started_at).total_seconds(),
                'config': self.config.copy()
            },
            'clusters': {
                cluster_id: cluster.to_dict()
                for cluster_id, cluster in self.clusters.items()
            },
            'circuit_breakers': {
                cluster_id: {
                    'state': breaker.state.value,
                    'failure_count': breaker.failure_count,
                    'last_failure': breaker.last_failure_time.isoformat() 
                                  if breaker.last_failure_time else None
                }
                for cluster_id, breaker in self.circuit_breakers.items()
            },
            'load_balancing': {
                cluster_id: {
                    'request_count': stats.request_count,
                    'success_rate': (stats.success_count / max(stats.request_count, 1)) * 100,
                    'avg_response_time': stats.avg_response_time,
                    'weight': stats.weight
                }
                for cluster_id, stats in self.load_balancing_stats.items()
            },
            'routing_rules': [
                {
                    'rule_id': rule.rule_id,
                    'pattern': rule.pattern,
                    'target_cluster': rule.target_cluster,
                    'priority': rule.priority,
                    'enabled': rule.enabled
                }
                for rule in self.routing_rules
            ],
            'metrics': self.metrics.copy()
        }


# ==================== FUNÇÕES UTILITÁRIAS ====================

def get_orchestrator() -> ClusterOrchestrator:
    """Retorna instância singleton do orquestrador"""
    return ClusterOrchestrator()


async def setup_default_routing_rules(orchestrator: ClusterOrchestrator):
    """Configura regras de roteamento padrão"""
    
    default_rules = [
        RoutingRule(
            rule_id="core_tasks",
            pattern=r"(plan|research|code|test|review)",
            target_cluster="core_cluster",
            priority=1
        ),
        RoutingRule(
            rule_id="memory_operations",
            pattern=r"(memory|neo4j|graph|remember)",
            target_cluster="memory_cluster",
            priority=1
        ),
        RoutingRule(
            rule_id="coordination_tasks",
            pattern=r"(coordinate|consensus|sync)",
            target_cluster="coordination_cluster",
            priority=1
        ),
        RoutingRule(
            rule_id="analytics_requests",
            pattern=r"(analyze|metrics|performance|dashboard)",
            target_cluster="analytics_cluster",
            priority=1
        ),
        RoutingRule(
            rule_id="mcp_protocols",
            pattern=r"(mcp|a2a|protocol|communication)",
            target_cluster="mcp_cluster",
            priority=1
        ),
        RoutingRule(
            rule_id="service_discovery",
            pattern=r"(discover|find|lookup|port)",
            target_cluster="discovery_cluster",
            priority=1
        )
    ]
    
    for rule in default_rules:
        orchestrator.add_routing_rule(rule)
    
    logger.info(f"✅ {len(default_rules)} regras de roteamento configuradas")


if __name__ == "__main__":
    async def test_orchestrator():
        """Teste do orquestrador"""
        logger.info("🧪 Testando ClusterOrchestrator...")
        
        # Criar orquestrador
        orchestrator = get_orchestrator()
        
        # Iniciar
        await orchestrator.start()
        
        # Configurar regras de roteamento
        await setup_default_routing_rules(orchestrator)
        
        # Teste de roteamento
        test_messages = [
            {"action": "plan", "content": "Criar novo feature"},
            {"action": "remember", "content": "Salvar informação importante"},
            {"action": "analyze", "content": "Verificar performance"},
            {"action": "discover", "content": "Encontrar serviços"}
        ]
        
        print("\n🧪 TESTANDO ROTEAMENTO DE MENSAGENS:")
        for msg in test_messages:
            result = await orchestrator.send_message(msg)
            print(f"Mensagem: {msg['action']} -> Resultado: {result['success']}")
        
        # Mostrar status
        status = orchestrator.get_status()
        print(f"\n📊 STATUS FINAL:")
        print(f"Clusters ativos: {status['metrics']['clusters_active']}")
        print(f"Agentes totais: {status['metrics']['agents_total']}")
        print(f"Requisições: {status['metrics']['total_requests']}")
        print(f"Taxa de sucesso: {status['metrics']['successful_requests']}/{status['metrics']['total_requests']}")
        
        # Parar
        await orchestrator.stop()
        print("\n✅ Teste concluído!")
    
    # Executar teste
    asyncio.run(test_orchestrator())