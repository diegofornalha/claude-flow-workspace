#!/usr/bin/env python3
"""
⚡ Gerenciador de Clusters - Auto-scaling e Failover
Implementação avançada de gerenciamento com escalabilidade automática e recuperação de falhas
"""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Set, Tuple
import statistics
import numpy as np

from .cluster_definition import AgentCluster, ClusterStatus, AgentStatus, AgentInfo, ClusterFactory
from .cluster_orchestrator import ClusterOrchestrator, get_orchestrator
from .cluster_registry import ClusterRegistry, get_cluster_registry

# Configurar logging
logger = logging.getLogger(__name__)


class ScalingDirection(Enum):
    """Direções de escalamento"""
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class FailoverTrigger(Enum):
    """Gatilhos para failover"""
    HEALTH_THRESHOLD = "health_threshold"
    RESPONSE_TIME = "response_time"
    ERROR_RATE = "error_rate"
    MANUAL = "manual"
    CLUSTER_FAILURE = "cluster_failure"


@dataclass
class ScalingMetrics:
    """Métricas para decisões de escalamento"""
    cluster_id: str
    timestamp: datetime
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    request_rate: float = 0.0
    response_time_avg: float = 0.0
    error_rate: float = 0.0
    queue_length: int = 0
    active_agents: int = 0
    available_agents: int = 0
    load_percentage: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'cluster_id': self.cluster_id,
            'timestamp': self.timestamp.isoformat(),
            'cpu_usage': self.cpu_usage,
            'memory_usage': self.memory_usage,
            'request_rate': self.request_rate,
            'response_time_avg': self.response_time_avg,
            'error_rate': self.error_rate,
            'queue_length': self.queue_length,
            'active_agents': self.active_agents,
            'available_agents': self.available_agents,
            'load_percentage': self.load_percentage
        }


@dataclass
class ScalingPolicy:
    """Política de escalamento para um cluster"""
    cluster_id: str
    min_agents: int = 1
    max_agents: int = 10
    target_cpu_utilization: float = 70.0
    target_response_time_ms: float = 500.0
    scale_up_threshold: float = 80.0
    scale_down_threshold: float = 30.0
    scale_up_cooldown: int = 300  # segundos
    scale_down_cooldown: int = 600  # segundos
    metrics_window: int = 300  # segundos para análise
    enabled: bool = True
    
    # Configurações avançadas
    aggressive_scaling: bool = False
    predictive_scaling: bool = False
    custom_rules: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class FailoverPolicy:
    """Política de failover para um cluster"""
    cluster_id: str
    health_threshold: float = 50.0
    max_response_time_ms: float = 5000.0
    max_error_rate: float = 20.0
    recovery_attempts: int = 3
    recovery_timeout: int = 120  # segundos
    backup_clusters: List[str] = field(default_factory=list)
    auto_failback: bool = True
    failback_health_threshold: float = 80.0
    enabled: bool = True


@dataclass
class ScalingEvent:
    """Evento de escalamento"""
    id: str
    cluster_id: str
    direction: ScalingDirection
    timestamp: datetime
    reason: str
    previous_count: int
    new_count: int
    metrics: ScalingMetrics
    success: bool = False
    error_message: Optional[str] = None


@dataclass
class FailoverEvent:
    """Evento de failover"""
    id: str
    cluster_id: str
    trigger: FailoverTrigger
    timestamp: datetime
    reason: str
    backup_cluster: Optional[str] = None
    success: bool = False
    recovery_time: float = 0.0
    error_message: Optional[str] = None


class MetricsCollector:
    """Coletor de métricas para análise de escalamento"""
    
    def __init__(self, window_size: int = 100):
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self.collection_interval = 30  # segundos
        self.running = False
    
    async def start_collection(self, orchestrator: ClusterOrchestrator):
        """Inicia coleta de métricas"""
        self.running = True
        
        while self.running:
            try:
                await self._collect_metrics(orchestrator)
                await asyncio.sleep(self.collection_interval)
            except Exception as e:
                logger.error(f"❌ Erro na coleta de métricas: {e}")
                await asyncio.sleep(10)
    
    def stop_collection(self):
        """Para coleta de métricas"""
        self.running = False
    
    async def _collect_metrics(self, orchestrator: ClusterOrchestrator):
        """Coleta métricas de todos os clusters"""
        for cluster_id, cluster in orchestrator.clusters.items():
            metrics = await self._collect_cluster_metrics(cluster_id, cluster, orchestrator)
            self.metrics_history[cluster_id].append(metrics)
    
    async def _collect_cluster_metrics(self, 
                                      cluster_id: str, 
                                      cluster: AgentCluster,
                                      orchestrator: ClusterOrchestrator) -> ScalingMetrics:
        """Coleta métricas de um cluster específico"""
        
        # Obter estatísticas de load balancing
        lb_stats = orchestrator.load_balancing_stats.get(cluster_id)
        
        # Calcular métricas
        active_agents = len([agent for agent in cluster.agents.values() 
                           if agent.status == AgentStatus.ONLINE])
        available_agents = len(cluster.get_available_agents())
        total_agents = len(cluster.agents)
        
        # Simular algumas métricas (em implementação real, viria de monitoring)
        current_load = sum(agent.current_tasks for agent in cluster.agents.values())
        max_capacity = sum(agent.max_concurrent_tasks for agent in cluster.agents.values())
        load_percentage = (current_load / max(max_capacity, 1)) * 100
        
        # CPU e memória simulados baseados na carga
        cpu_usage = min(95, load_percentage * 1.2)
        memory_usage = min(90, load_percentage * 0.8 + 20)
        
        # Métricas de request/response do load balancer
        request_rate = 0.0
        response_time_avg = 0.0
        error_rate = 0.0
        
        if lb_stats:
            if lb_stats.request_count > 0:
                success_rate = (lb_stats.success_count / lb_stats.request_count) * 100
                error_rate = 100 - success_rate
            response_time_avg = lb_stats.avg_response_time
            
            # Calcular taxa de request (aproximada)
            if len(self.metrics_history[cluster_id]) > 0:
                last_metrics = self.metrics_history[cluster_id][-1]
                time_diff = (datetime.now() - last_metrics.timestamp).total_seconds()
                if time_diff > 0:
                    request_diff = lb_stats.request_count - getattr(last_metrics, 'total_requests', 0)
                    request_rate = request_diff / time_diff
        
        return ScalingMetrics(
            cluster_id=cluster_id,
            timestamp=datetime.now(),
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            request_rate=request_rate,
            response_time_avg=response_time_avg,
            error_rate=error_rate,
            queue_length=current_load,
            active_agents=active_agents,
            available_agents=available_agents,
            load_percentage=load_percentage
        )
    
    def get_metrics_summary(self, cluster_id: str, window_minutes: int = 5) -> Dict[str, Any]:
        """Retorna resumo das métricas em uma janela de tempo"""
        if cluster_id not in self.metrics_history:
            return {}
        
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        recent_metrics = [
            m for m in self.metrics_history[cluster_id]
            if m.timestamp >= cutoff_time
        ]
        
        if not recent_metrics:
            return {}
        
        return {
            'count': len(recent_metrics),
            'avg_cpu': statistics.mean(m.cpu_usage for m in recent_metrics),
            'avg_memory': statistics.mean(m.memory_usage for m in recent_metrics),
            'avg_response_time': statistics.mean(m.response_time_avg for m in recent_metrics),
            'avg_error_rate': statistics.mean(m.error_rate for m in recent_metrics),
            'avg_load_percentage': statistics.mean(m.load_percentage for m in recent_metrics),
            'max_cpu': max(m.cpu_usage for m in recent_metrics),
            'max_memory': max(m.memory_usage for m in recent_metrics),
            'max_response_time': max(m.response_time_avg for m in recent_metrics),
            'current_agents': recent_metrics[-1].active_agents,
            'available_agents': recent_metrics[-1].available_agents
        }


class AutoScaler:
    """Sistema de auto-scaling baseado em métricas"""
    
    def __init__(self):
        self.scaling_policies: Dict[str, ScalingPolicy] = {}
        self.scaling_history: List[ScalingEvent] = []
        self.last_scaling_action: Dict[str, datetime] = {}
        self.metrics_collector = MetricsCollector()
        self.running = False
        
        # Machine Learning para previsões (simulado)
        self.prediction_model = None
        
    def set_scaling_policy(self, policy: ScalingPolicy):
        """Define política de escalamento para um cluster"""
        self.scaling_policies[policy.cluster_id] = policy
        logger.info(f"📏 Política de escalamento definida para cluster '{policy.cluster_id}'")
    
    async def start_auto_scaling(self, orchestrator: ClusterOrchestrator):
        """Inicia o sistema de auto-scaling"""
        if self.running:
            return
        
        self.running = True
        logger.info("🚀 Iniciando Auto-Scaler...")
        
        # Iniciar coleta de métricas
        asyncio.create_task(self.metrics_collector.start_collection(orchestrator))
        
        # Iniciar loop de análise
        asyncio.create_task(self._scaling_analysis_loop(orchestrator))
        
        # Configurar políticas padrão se não existirem
        await self._setup_default_policies(orchestrator)
        
        logger.info("✅ Auto-Scaler iniciado")
    
    def stop_auto_scaling(self):
        """Para o sistema de auto-scaling"""
        self.running = False
        self.metrics_collector.stop_collection()
        logger.info("⏸️ Auto-Scaler parado")
    
    async def _setup_default_policies(self, orchestrator: ClusterOrchestrator):
        """Configura políticas padrão para clusters"""
        for cluster_id, cluster in orchestrator.clusters.items():
            if cluster_id not in self.scaling_policies:
                
                # Políticas personalizadas por tipo de cluster
                if "core" in cluster_id:
                    policy = ScalingPolicy(
                        cluster_id=cluster_id,
                        min_agents=3,
                        max_agents=8,
                        target_cpu_utilization=60.0,
                        scale_up_threshold=75.0,
                        scale_down_threshold=25.0
                    )
                elif "memory" in cluster_id:
                    policy = ScalingPolicy(
                        cluster_id=cluster_id,
                        min_agents=2,
                        max_agents=6,
                        target_cpu_utilization=70.0,
                        scale_up_threshold=80.0,
                        scale_down_threshold=30.0
                    )
                elif "discovery" in cluster_id:
                    policy = ScalingPolicy(
                        cluster_id=cluster_id,
                        min_agents=1,
                        max_agents=15,
                        target_cpu_utilization=65.0,
                        scale_up_threshold=70.0,
                        scale_down_threshold=20.0,
                        aggressive_scaling=True
                    )
                else:
                    # Política padrão
                    policy = ScalingPolicy(
                        cluster_id=cluster_id,
                        min_agents=1,
                        max_agents=10
                    )
                
                self.set_scaling_policy(policy)
    
    async def _scaling_analysis_loop(self, orchestrator: ClusterOrchestrator):
        """Loop principal de análise para escalamento"""
        while self.running:
            try:
                await self._analyze_scaling_needs(orchestrator)
                await asyncio.sleep(60)  # Análise a cada minuto
            except Exception as e:
                logger.error(f"❌ Erro na análise de escalamento: {e}")
                await asyncio.sleep(30)
    
    async def _analyze_scaling_needs(self, orchestrator: ClusterOrchestrator):
        """Analisa necessidades de escalamento"""
        for cluster_id, policy in self.scaling_policies.items():
            if not policy.enabled:
                continue
            
            if cluster_id not in orchestrator.clusters:
                continue
            
            cluster = orchestrator.clusters[cluster_id]
            
            # Obter métricas recentes
            metrics_summary = self.metrics_collector.get_metrics_summary(
                cluster_id, 
                policy.metrics_window // 60
            )
            
            if not metrics_summary:
                continue
            
            # Determinar ação de escalamento
            scaling_decision = await self._make_scaling_decision(
                cluster, policy, metrics_summary
            )
            
            if scaling_decision != ScalingDirection.STABLE:
                await self._execute_scaling(
                    cluster, policy, scaling_decision, metrics_summary, orchestrator
                )
    
    async def _make_scaling_decision(self, 
                                   cluster: AgentCluster, 
                                   policy: ScalingPolicy,
                                   metrics: Dict[str, Any]) -> ScalingDirection:
        """Toma decisão de escalamento baseada nas métricas"""
        
        cluster_id = cluster.cluster_id
        current_agents = len(cluster.agents)
        
        # Verificar cooldown
        if self._is_in_cooldown(cluster_id, policy):
            return ScalingDirection.STABLE
        
        # Fatores para decisão
        cpu_factor = metrics.get('avg_cpu', 0)
        memory_factor = metrics.get('avg_memory', 0)
        response_time_factor = metrics.get('avg_response_time', 0)
        load_factor = metrics.get('avg_load_percentage', 0)
        error_rate = metrics.get('avg_error_rate', 0)
        
        # Pontuação de stress
        stress_score = self._calculate_stress_score(
            cpu_factor, memory_factor, response_time_factor, load_factor, error_rate, policy
        )
        
        logger.debug(f"📊 Cluster {cluster_id} - Stress Score: {stress_score:.2f}")
        
        # Decisão de escalamento
        if stress_score >= policy.scale_up_threshold and current_agents < policy.max_agents:
            return ScalingDirection.UP
        elif stress_score <= policy.scale_down_threshold and current_agents > policy.min_agents:
            return ScalingDirection.DOWN
        else:
            return ScalingDirection.STABLE
    
    def _calculate_stress_score(self, 
                               cpu: float, 
                               memory: float, 
                               response_time: float,
                               load: float,
                               error_rate: float,
                               policy: ScalingPolicy) -> float:
        """Calcula score de stress do cluster"""
        
        # Pesos para diferentes métricas
        weights = {
            'cpu': 0.25,
            'memory': 0.20,
            'response_time': 0.25,
            'load': 0.25,
            'error_rate': 0.05
        }
        
        # Normalizar response time
        response_time_score = min(100, (response_time / policy.target_response_time_ms) * 100)
        
        # Calcular score ponderado
        stress_score = (
            cpu * weights['cpu'] +
            memory * weights['memory'] +
            response_time_score * weights['response_time'] +
            load * weights['load'] +
            error_rate * weights['error_rate']
        )
        
        return stress_score
    
    def _is_in_cooldown(self, cluster_id: str, policy: ScalingPolicy) -> bool:
        """Verifica se cluster está em período de cooldown"""
        if cluster_id not in self.last_scaling_action:
            return False
        
        last_action = self.last_scaling_action[cluster_id]
        time_since_action = (datetime.now() - last_action).total_seconds()
        
        # Usar o maior cooldown (up ou down)
        cooldown_period = max(policy.scale_up_cooldown, policy.scale_down_cooldown)
        
        return time_since_action < cooldown_period
    
    async def _execute_scaling(self,
                              cluster: AgentCluster,
                              policy: ScalingPolicy,
                              direction: ScalingDirection,
                              metrics: Dict[str, Any],
                              orchestrator: ClusterOrchestrator):
        """Executa ação de escalamento"""
        
        cluster_id = cluster.cluster_id
        current_count = len(cluster.agents)
        
        # Determinar novo número de agentes
        if direction == ScalingDirection.UP:
            if policy.aggressive_scaling:
                new_count = min(policy.max_agents, current_count + 2)
            else:
                new_count = min(policy.max_agents, current_count + 1)
        else:  # DOWN
            new_count = max(policy.min_agents, current_count - 1)
        
        # Criar evento de escalamento
        event = ScalingEvent(
            id=str(time.time()),
            cluster_id=cluster_id,
            direction=direction,
            timestamp=datetime.now(),
            reason=f"Stress score triggered {direction.value} scaling",
            previous_count=current_count,
            new_count=new_count,
            metrics=ScalingMetrics(
                cluster_id=cluster_id,
                timestamp=datetime.now(),
                cpu_usage=metrics.get('avg_cpu', 0),
                memory_usage=metrics.get('avg_memory', 0),
                response_time_avg=metrics.get('avg_response_time', 0),
                load_percentage=metrics.get('avg_load_percentage', 0),
                active_agents=current_count
            )
        )
        
        try:
            # Executar escalamento
            if direction == ScalingDirection.UP:
                success = await self._scale_up(cluster, new_count - current_count)
            else:
                success = await self._scale_down(cluster, current_count - new_count)
            
            event.success = success
            
            if success:
                self.last_scaling_action[cluster_id] = datetime.now()
                logger.info(f"✅ Escalamento {direction.value} executado para cluster '{cluster_id}': {current_count} -> {new_count}")
            else:
                logger.error(f"❌ Falha no escalamento {direction.value} para cluster '{cluster_id}'")
                
        except Exception as e:
            event.success = False
            event.error_message = str(e)
            logger.error(f"❌ Erro no escalamento: {e}")
        
        self.scaling_history.append(event)
    
    async def _scale_up(self, cluster: AgentCluster, count: int) -> bool:
        """Escala cluster para cima adicionando agentes"""
        try:
            for i in range(count):
                # Criar novo agente baseado no tipo do cluster
                agent_info = self._create_agent_for_cluster(cluster)
                success = cluster.register_agent(agent_info)
                
                if not success:
                    logger.warning(f"⚠️ Falha ao adicionar agente {i+1} ao cluster '{cluster.cluster_id}'")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro no scale up: {e}")
            return False
    
    async def _scale_down(self, cluster: AgentCluster, count: int) -> bool:
        """Escala cluster para baixo removendo agentes"""
        try:
            # Remover agentes menos utilizados primeiro
            agents_by_load = sorted(
                cluster.agents.values(),
                key=lambda a: a.current_tasks
            )
            
            removed = 0
            for agent in agents_by_load:
                if removed >= count:
                    break
                
                # Só remover agentes que não estão processando tarefas
                if agent.current_tasks == 0:
                    success = cluster.unregister_agent(agent.id)
                    if success:
                        removed += 1
            
            return removed > 0
            
        except Exception as e:
            logger.error(f"❌ Erro no scale down: {e}")
            return False
    
    def _create_agent_for_cluster(self, cluster: AgentCluster) -> AgentInfo:
        """Cria novo agente apropriado para o tipo de cluster"""
        
        agent_id = f"scaled_agent_{int(time.time())}"
        
        # Definir capacidades baseadas no tipo de cluster
        if "core" in cluster.cluster_id:
            capabilities = ["general_processing", "task_execution"]
            role = "core_worker"
        elif "memory" in cluster.cluster_id:
            capabilities = ["memory_management", "data_processing"]
            role = "memory_worker"
        elif "coordination" in cluster.cluster_id:
            capabilities = ["coordination", "consensus"]
            role = "coordination_worker"
        elif "analytics" in cluster.cluster_id:
            capabilities = ["analytics", "metrics_processing"]
            role = "analytics_worker"
        elif "mcp" in cluster.cluster_id:
            capabilities = ["protocol_handling", "communication"]
            role = "mcp_worker"
        else:
            capabilities = ["general_processing"]
            role = "worker"
        
        return AgentInfo(
            id=agent_id,
            name=f"Scaled {role.title()}",
            role=role,
            capabilities=capabilities,
            status=AgentStatus.ONLINE,
            max_concurrent_tasks=5
        )


class FailoverManager:
    """Sistema de failover automático"""
    
    def __init__(self):
        self.failover_policies: Dict[str, FailoverPolicy] = {}
        self.failover_history: List[FailoverEvent] = []
        self.active_failovers: Dict[str, str] = {}  # cluster_id -> backup_cluster_id
        self.running = False
    
    def set_failover_policy(self, policy: FailoverPolicy):
        """Define política de failover para um cluster"""
        self.failover_policies[policy.cluster_id] = policy
        logger.info(f"🛡️ Política de failover definida para cluster '{policy.cluster_id}'")
    
    async def start_failover_monitoring(self, orchestrator: ClusterOrchestrator):
        """Inicia monitoramento de failover"""
        if self.running:
            return
        
        self.running = True
        logger.info("🚀 Iniciando Failover Manager...")
        
        # Configurar políticas padrão
        await self._setup_default_failover_policies(orchestrator)
        
        # Iniciar loop de monitoramento
        asyncio.create_task(self._failover_monitoring_loop(orchestrator))
        
        logger.info("✅ Failover Manager iniciado")
    
    def stop_failover_monitoring(self):
        """Para monitoramento de failover"""
        self.running = False
        logger.info("⏸️ Failover Manager parado")
    
    async def _setup_default_failover_policies(self, orchestrator: ClusterOrchestrator):
        """Configura políticas padrão de failover"""
        cluster_backups = {
            "core_cluster": ["coordination_cluster"],
            "memory_cluster": ["analytics_cluster"],
            "coordination_cluster": ["core_cluster"],
            "analytics_cluster": ["memory_cluster"],
            "mcp_cluster": ["discovery_cluster"],
            "discovery_cluster": ["mcp_cluster"]
        }
        
        for cluster_id, backup_clusters in cluster_backups.items():
            if cluster_id not in self.failover_policies:
                policy = FailoverPolicy(
                    cluster_id=cluster_id,
                    backup_clusters=backup_clusters,
                    health_threshold=40.0,
                    max_response_time_ms=10000.0,
                    max_error_rate=30.0
                )
                self.set_failover_policy(policy)
    
    async def _failover_monitoring_loop(self, orchestrator: ClusterOrchestrator):
        """Loop de monitoramento para failover"""
        while self.running:
            try:
                await self._check_failover_conditions(orchestrator)
                await asyncio.sleep(30)  # Verificar a cada 30 segundos
            except Exception as e:
                logger.error(f"❌ Erro no monitoramento de failover: {e}")
                await asyncio.sleep(10)
    
    async def _check_failover_conditions(self, orchestrator: ClusterOrchestrator):
        """Verifica condições que podem triggar failover"""
        for cluster_id, policy in self.failover_policies.items():
            if not policy.enabled:
                continue
            
            if cluster_id not in orchestrator.clusters:
                continue
            
            cluster = orchestrator.clusters[cluster_id]
            
            # Verificar se cluster já está em failover
            if cluster_id in self.active_failovers:
                await self._check_failback_conditions(cluster_id, cluster, orchestrator)
                continue
            
            # Verificar condições de failover
            should_failover, trigger, reason = await self._should_trigger_failover(
                cluster, policy, orchestrator
            )
            
            if should_failover:
                await self._execute_failover(cluster_id, trigger, reason, policy, orchestrator)
    
    async def _should_trigger_failover(self, 
                                     cluster: AgentCluster,
                                     policy: FailoverPolicy,
                                     orchestrator: ClusterOrchestrator) -> Tuple[bool, FailoverTrigger, str]:
        """Determina se deve fazer failover"""
        
        cluster_id = cluster.cluster_id
        
        # Verificar saúde do cluster
        health_report = cluster.health_check()
        health_percentage = health_report.get('health_percentage', 100)
        
        if health_percentage < policy.health_threshold:
            return True, FailoverTrigger.HEALTH_THRESHOLD, f"Health {health_percentage}% < {policy.health_threshold}%"
        
        # Verificar métricas de load balancing
        lb_stats = orchestrator.load_balancing_stats.get(cluster_id)
        if lb_stats:
            
            # Response time
            if lb_stats.avg_response_time > policy.max_response_time_ms:
                return True, FailoverTrigger.RESPONSE_TIME, f"Response time {lb_stats.avg_response_time}ms > {policy.max_response_time_ms}ms"
            
            # Error rate
            if lb_stats.request_count > 0:
                error_rate = ((lb_stats.request_count - lb_stats.success_count) / lb_stats.request_count) * 100
                if error_rate > policy.max_error_rate:
                    return True, FailoverTrigger.ERROR_RATE, f"Error rate {error_rate}% > {policy.max_error_rate}%"
        
        # Verificar se cluster está completamente offline
        if cluster.status == ClusterStatus.FAILED:
            return True, FailoverTrigger.CLUSTER_FAILURE, "Cluster status is FAILED"
        
        return False, None, ""
    
    async def _execute_failover(self,
                               cluster_id: str,
                               trigger: FailoverTrigger,
                               reason: str,
                               policy: FailoverPolicy,
                               orchestrator: ClusterOrchestrator):
        """Executa failover para cluster backup"""
        
        # Encontrar cluster backup disponível
        backup_cluster_id = None
        for backup_id in policy.backup_clusters:
            if backup_id in orchestrator.clusters:
                backup_cluster = orchestrator.clusters[backup_id]
                if backup_cluster.status == ClusterStatus.ACTIVE:
                    backup_cluster_id = backup_id
                    break
        
        if not backup_cluster_id:
            logger.error(f"❌ Nenhum cluster backup disponível para '{cluster_id}'")
            return
        
        # Criar evento de failover
        event = FailoverEvent(
            id=str(time.time()),
            cluster_id=cluster_id,
            trigger=trigger,
            timestamp=datetime.now(),
            reason=reason,
            backup_cluster=backup_cluster_id
        )
        
        start_time = time.time()
        
        try:
            # Marcar failover ativo
            self.active_failovers[cluster_id] = backup_cluster_id
            
            # Redirecionar tráfego (simulated)
            # Em implementação real, atualizaria load balancer
            logger.info(f"🔄 Redirecionando tráfego de '{cluster_id}' para '{backup_cluster_id}'")
            
            # Tentar recuperar cluster original
            original_cluster = orchestrator.clusters[cluster_id]
            if original_cluster.status == ClusterStatus.FAILED:
                original_cluster.start()
            
            event.success = True
            event.recovery_time = time.time() - start_time
            
            logger.warning(f"⚠️ Failover executado: {cluster_id} -> {backup_cluster_id} (Razão: {reason})")
            
        except Exception as e:
            event.success = False
            event.error_message = str(e)
            logger.error(f"❌ Erro no failover: {e}")
        
        self.failover_history.append(event)
    
    async def _check_failback_conditions(self,
                                       cluster_id: str,
                                       cluster: AgentCluster,
                                       orchestrator: ClusterOrchestrator):
        """Verifica se pode fazer failback para cluster original"""
        
        policy = self.failover_policies.get(cluster_id)
        if not policy or not policy.auto_failback:
            return
        
        # Verificar se cluster original está saudável
        health_report = cluster.health_check()
        health_percentage = health_report.get('health_percentage', 0)
        
        if health_percentage >= policy.failback_health_threshold:
            await self._execute_failback(cluster_id, orchestrator)
    
    async def _execute_failback(self, cluster_id: str, orchestrator: ClusterOrchestrator):
        """Executa failback para cluster original"""
        
        if cluster_id not in self.active_failovers:
            return
        
        backup_cluster_id = self.active_failovers[cluster_id]
        
        try:
            # Redirecionar tráfego de volta
            logger.info(f"🔄 Executando failback: {backup_cluster_id} -> {cluster_id}")
            
            # Remover failover ativo
            del self.active_failovers[cluster_id]
            
            logger.info(f"✅ Failback concluído para cluster '{cluster_id}'")
            
        except Exception as e:
            logger.error(f"❌ Erro no failback: {e}")
    
    def get_failover_status(self) -> Dict[str, Any]:
        """Retorna status dos failovers"""
        return {
            'active_failovers': self.active_failovers.copy(),
            'failover_policies': {
                cluster_id: {
                    'enabled': policy.enabled,
                    'health_threshold': policy.health_threshold,
                    'backup_clusters': policy.backup_clusters,
                    'auto_failback': policy.auto_failback
                }
                for cluster_id, policy in self.failover_policies.items()
            },
            'recent_events': [
                {
                    'cluster_id': event.cluster_id,
                    'trigger': event.trigger.value,
                    'timestamp': event.timestamp.isoformat(),
                    'reason': event.reason,
                    'backup_cluster': event.backup_cluster,
                    'success': event.success,
                    'recovery_time': event.recovery_time
                }
                for event in self.failover_history[-10:]  # Últimos 10 eventos
            ]
        }


class ClusterManager:
    """Gerenciador principal que coordena auto-scaling e failover"""
    
    def __init__(self):
        self.auto_scaler = AutoScaler()
        self.failover_manager = FailoverManager()
        self.running = False
        
        self.metrics = {
            'scaling_events': 0,
            'failover_events': 0,
            'clusters_managed': 0,
            'uptime': 0.0
        }
        
        self.started_at = None
    
    async def start(self, orchestrator: ClusterOrchestrator = None):
        """Inicia o gerenciador de clusters"""
        if self.running:
            logger.warning("⚠️ Cluster Manager já está rodando")
            return
        
        self.running = True
        self.started_at = datetime.now()
        
        # Usar orchestrador padrão se não fornecido
        if orchestrator is None:
            orchestrator = get_orchestrator()
        
        logger.info("🚀 Iniciando Cluster Manager...")
        
        # Iniciar componentes
        await self.auto_scaler.start_auto_scaling(orchestrator)
        await self.failover_manager.start_failover_monitoring(orchestrator)
        
        # Iniciar loop de métricas
        asyncio.create_task(self._metrics_loop())
        
        self.metrics['clusters_managed'] = len(orchestrator.clusters)
        
        logger.info("✅ Cluster Manager iniciado com sucesso")
    
    async def stop(self):
        """Para o gerenciador de clusters"""
        if not self.running:
            return
        
        self.running = False
        logger.info("🛑 Parando Cluster Manager...")
        
        # Parar componentes
        self.auto_scaler.stop_auto_scaling()
        self.failover_manager.stop_failover_monitoring()
        
        logger.info("⏸️ Cluster Manager parado")
    
    async def _metrics_loop(self):
        """Loop de atualização de métricas"""
        while self.running:
            try:
                if self.started_at:
                    self.metrics['uptime'] = (datetime.now() - self.started_at).total_seconds()
                
                self.metrics['scaling_events'] = len(self.auto_scaler.scaling_history)
                self.metrics['failover_events'] = len(self.failover_manager.failover_history)
                
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"❌ Erro no loop de métricas: {e}")
                await asyncio.sleep(30)
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status completo do gerenciador"""
        return {
            'manager': {
                'running': self.running,
                'started_at': self.started_at.isoformat() if self.started_at else None,
                'metrics': self.metrics.copy()
            },
            'auto_scaler': {
                'running': self.auto_scaler.running,
                'policies_count': len(self.auto_scaler.scaling_policies),
                'recent_events': [
                    {
                        'cluster_id': event.cluster_id,
                        'direction': event.direction.value,
                        'timestamp': event.timestamp.isoformat(),
                        'reason': event.reason,
                        'previous_count': event.previous_count,
                        'new_count': event.new_count,
                        'success': event.success
                    }
                    for event in self.auto_scaler.scaling_history[-5:]
                ]
            },
            'failover_manager': self.failover_manager.get_failover_status()
        }


# ==================== SINGLETON E UTILITÁRIOS ====================

_cluster_manager_instance = None

def get_cluster_manager() -> ClusterManager:
    """Retorna instância singleton do cluster manager"""
    global _cluster_manager_instance
    if _cluster_manager_instance is None:
        _cluster_manager_instance = ClusterManager()
    return _cluster_manager_instance


if __name__ == "__main__":
    async def test_cluster_manager():
        """Teste do cluster manager"""
        logger.info("🧪 Testando Cluster Manager...")
        
        # Inicializar componentes
        orchestrator = get_orchestrator()
        await orchestrator.start()
        
        manager = get_cluster_manager()
        await manager.start(orchestrator)
        
        # Simular load para triggerar auto-scaling
        logger.info("⏳ Aguardando alguns ciclos de análise...")
        await asyncio.sleep(90)
        
        # Mostrar status
        status = manager.get_status()
        print(f"\n📊 STATUS DO CLUSTER MANAGER:")
        print(f"Clusters gerenciados: {status['manager']['metrics']['clusters_managed']}")
        print(f"Eventos de scaling: {status['manager']['metrics']['scaling_events']}")
        print(f"Eventos de failover: {status['manager']['metrics']['failover_events']}")
        print(f"Uptime: {status['manager']['metrics']['uptime']:.1f}s")
        
        print(f"\n📈 AUTO-SCALER:")
        print(f"Políticas ativas: {status['auto_scaler']['policies_count']}")
        print(f"Eventos recentes: {len(status['auto_scaler']['recent_events'])}")
        
        print(f"\n🛡️ FAILOVER:")
        print(f"Failovers ativos: {len(status['failover_manager']['active_failovers'])}")
        print(f"Eventos recentes: {len(status['failover_manager']['recent_events'])}")
        
        # Cleanup
        await manager.stop()
        await orchestrator.stop()
        
        print("\n✅ Teste concluído!")
    
    # Executar teste
    asyncio.run(test_cluster_manager())