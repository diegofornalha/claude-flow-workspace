#!/usr/bin/env python3
"""
📊 Sistema de Telemetria Unificado
Coleta e análise de métricas de performance, uso de memória, tempo de resposta e taxa de erro
"""

import os
import time
import psutil
import threading
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque
from contextlib import contextmanager
import logging
import json
import uuid
from pathlib import Path

# Local imports
from .cache_manager import get_cache, CacheConfig, CachePolicy
from .logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class MetricType(Enum):
    """Tipos de métricas"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    RATE = "rate"


class Severity(Enum):
    """Níveis de severidade"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MetricPoint:
    """Ponto individual de métrica"""
    timestamp: float
    value: Union[int, float]
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário"""
        return {
            'timestamp': self.timestamp,
            'value': self.value,
            'tags': self.tags,
            'metadata': self.metadata,
            'datetime': datetime.fromtimestamp(self.timestamp).isoformat()
        }


@dataclass
class Metric:
    """Métrica com histórico de pontos"""
    name: str
    type: MetricType
    description: str
    unit: str
    points: deque = field(default_factory=lambda: deque(maxlen=1000))
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    
    def add_point(self, value: Union[int, float], tags: Optional[Dict[str, str]] = None, 
                  metadata: Optional[Dict[str, Any]] = None) -> None:
        """Adiciona ponto à métrica"""
        point = MetricPoint(
            timestamp=time.time(),
            value=value,
            tags={**self.tags, **(tags or {})},
            metadata=metadata or {}
        )
        self.points.append(point)
    
    def get_latest(self) -> Optional[MetricPoint]:
        """Obtém último ponto"""
        return self.points[-1] if self.points else None
    
    def get_average(self, window_seconds: Optional[int] = None) -> float:
        """Calcula média dos valores"""
        if not self.points:
            return 0.0
        
        if window_seconds:
            cutoff_time = time.time() - window_seconds
            values = [p.value for p in self.points if p.timestamp >= cutoff_time]
        else:
            values = [p.value for p in self.points]
        
        return sum(values) / len(values) if values else 0.0
    
    def get_max(self, window_seconds: Optional[int] = None) -> float:
        """Obtém valor máximo"""
        if not self.points:
            return 0.0
        
        if window_seconds:
            cutoff_time = time.time() - window_seconds
            values = [p.value for p in self.points if p.timestamp >= cutoff_time]
        else:
            values = [p.value for p in self.points]
        
        return max(values) if values else 0.0
    
    def get_min(self, window_seconds: Optional[int] = None) -> float:
        """Obtém valor mínimo"""
        if not self.points:
            return 0.0
        
        if window_seconds:
            cutoff_time = time.time() - window_seconds
            values = [p.value for p in self.points if p.timestamp >= cutoff_time]
        else:
            values = [p.value for p in self.points]
        
        return min(values) if values else 0.0
    
    def get_rate(self, window_seconds: int = 60) -> float:
        """Calcula taxa por segundo"""
        cutoff_time = time.time() - window_seconds
        recent_points = [p for p in self.points if p.timestamp >= cutoff_time]
        
        if len(recent_points) < 2:
            return 0.0
        
        total_value = sum(p.value for p in recent_points)
        time_span = recent_points[-1].timestamp - recent_points[0].timestamp
        
        return total_value / time_span if time_span > 0 else 0.0


@dataclass
class Alert:
    """Alerta de métrica"""
    id: str
    metric_name: str
    condition: str
    threshold: float
    severity: Severity
    message: str
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_active(self) -> bool:
        """Verifica se alerta está ativo"""
        return self.resolved_at is None
    
    def resolve(self) -> None:
        """Resolve alerta"""
        self.resolved_at = datetime.now()


class SystemMonitor:
    """Monitor de recursos do sistema"""
    
    def __init__(self, telemetry: 'TelemetryManager'):
        self.telemetry = telemetry
        self._process = psutil.Process()
        self._monitoring = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self, interval: float = 5.0) -> None:
        """Inicia monitoramento do sistema"""
        if self._monitoring:
            return
        
        self._monitoring = True
        
        def monitor_worker():
            while self._monitoring:
                try:
                    self._collect_system_metrics()
                    time.sleep(interval)
                except Exception as e:
                    logger.error(f"Erro no monitoramento do sistema: {e}")
                    time.sleep(10)
        
        self._thread = threading.Thread(target=monitor_worker, daemon=True)
        self._thread.start()
        logger.info(f"🔍 Monitor do sistema iniciado (intervalo: {interval}s)")
    
    def stop(self) -> None:
        """Para monitoramento do sistema"""
        self._monitoring = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("🔍 Monitor do sistema parado")
    
    def _collect_system_metrics(self) -> None:
        """Coleta métricas do sistema"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            self.telemetry.gauge('system.cpu.percent', cpu_percent, 
                               tags={'component': 'system'})
            
            # Memória
            memory = psutil.virtual_memory()
            self.telemetry.gauge('system.memory.percent', memory.percent,
                               tags={'component': 'system'})
            self.telemetry.gauge('system.memory.used_gb', memory.used / (1024**3),
                               tags={'component': 'system'})
            self.telemetry.gauge('system.memory.available_gb', memory.available / (1024**3),
                               tags={'component': 'system'})
            
            # Disco
            disk = psutil.disk_usage('/')
            self.telemetry.gauge('system.disk.percent', (disk.used / disk.total) * 100,
                               tags={'component': 'system'})
            self.telemetry.gauge('system.disk.used_gb', disk.used / (1024**3),
                               tags={'component': 'system'})
            self.telemetry.gauge('system.disk.free_gb', disk.free / (1024**3),
                               tags={'component': 'system'})
            
            # Processo atual
            self.telemetry.gauge('process.memory.rss_mb', self._process.memory_info().rss / (1024**2),
                               tags={'component': 'process'})
            self.telemetry.gauge('process.memory.vms_mb', self._process.memory_info().vms / (1024**2),
                               tags={'component': 'process'})
            self.telemetry.gauge('process.cpu.percent', self._process.cpu_percent(),
                               tags={'component': 'process'})
            self.telemetry.gauge('process.threads.count', self._process.num_threads(),
                               tags={'component': 'process'})
            
            # Conexões de rede
            connections = self._process.connections()
            self.telemetry.gauge('process.connections.count', len(connections),
                               tags={'component': 'process'})
            
            # File descriptors (Unix/Linux apenas)
            try:
                self.telemetry.gauge('process.fd.count', self._process.num_fds(),
                                   tags={'component': 'process'})
            except AttributeError:
                pass  # Windows não suporta
            
        except Exception as e:
            logger.debug(f"Erro ao coletar métricas do sistema: {e}")


class AlertManager:
    """Gerenciador de alertas"""
    
    def __init__(self, telemetry: 'TelemetryManager'):
        self.telemetry = telemetry
        self.alerts: Dict[str, Alert] = {}
        self.rules: List[Dict[str, Any]] = []
        self._checking = False
        self._thread: Optional[threading.Thread] = None
    
    def add_rule(self, metric_name: str, condition: str, threshold: float,
                severity: Severity, message: str) -> None:
        """
        Adiciona regra de alerta
        
        Args:
            metric_name: Nome da métrica
            condition: Condição (>, <, >=, <=, ==)
            threshold: Valor limite
            severity: Severidade do alerta
            message: Mensagem do alerta
        """
        rule = {
            'metric_name': metric_name,
            'condition': condition,
            'threshold': threshold,
            'severity': severity,
            'message': message
        }
        self.rules.append(rule)
        logger.info(f"📋 Regra de alerta adicionada: {metric_name} {condition} {threshold}")
    
    def start_checking(self, interval: float = 30.0) -> None:
        """Inicia verificação de alertas"""
        if self._checking:
            return
        
        self._checking = True
        
        def check_worker():
            while self._checking:
                try:
                    self._check_rules()
                    time.sleep(interval)
                except Exception as e:
                    logger.error(f"Erro na verificação de alertas: {e}")
                    time.sleep(10)
        
        self._thread = threading.Thread(target=check_worker, daemon=True)
        self._thread.start()
        logger.info(f"🚨 Verificação de alertas iniciada (intervalo: {interval}s)")
    
    def stop_checking(self) -> None:
        """Para verificação de alertas"""
        self._checking = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("🚨 Verificação de alertas parada")
    
    def _check_rules(self) -> None:
        """Verifica regras de alerta"""
        for rule in self.rules:
            try:
                metric = self.telemetry.get_metric(rule['metric_name'])
                if not metric:
                    continue
                
                latest_point = metric.get_latest()
                if not latest_point:
                    continue
                
                # Verificar condição
                value = latest_point.value
                condition = rule['condition']
                threshold = rule['threshold']
                
                triggered = False
                if condition == '>':
                    triggered = value > threshold
                elif condition == '<':
                    triggered = value < threshold
                elif condition == '>=':
                    triggered = value >= threshold
                elif condition == '<=':
                    triggered = value <= threshold
                elif condition == '==':
                    triggered = value == threshold
                
                alert_id = f"{rule['metric_name']}_{condition}_{threshold}"
                
                if triggered:
                    # Criar ou manter alerta
                    if alert_id not in self.alerts:
                        alert = Alert(
                            id=alert_id,
                            metric_name=rule['metric_name'],
                            condition=f"{condition} {threshold}",
                            threshold=threshold,
                            severity=rule['severity'],
                            message=rule['message'].format(value=value, threshold=threshold),
                            triggered_at=datetime.now(),
                            metadata={'current_value': value}
                        )
                        self.alerts[alert_id] = alert
                        logger.warning(f"🚨 ALERTA: {alert.message}")
                else:
                    # Resolver alerta se existir
                    if alert_id in self.alerts and self.alerts[alert_id].is_active:
                        self.alerts[alert_id].resolve()
                        logger.info(f"✅ Alerta resolvido: {rule['metric_name']}")
                
            except Exception as e:
                logger.error(f"Erro ao verificar regra {rule}: {e}")
    
    def get_active_alerts(self) -> List[Alert]:
        """Retorna alertas ativos"""
        return [alert for alert in self.alerts.values() if alert.is_active]
    
    def get_alert_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de alertas"""
        active_alerts = self.get_active_alerts()
        
        by_severity = defaultdict(int)
        for alert in active_alerts:
            by_severity[alert.severity.value] += 1
        
        return {
            'total_alerts': len(self.alerts),
            'active_alerts': len(active_alerts),
            'resolved_alerts': len(self.alerts) - len(active_alerts),
            'by_severity': dict(by_severity),
            'rules_count': len(self.rules)
        }


class TelemetryManager:
    """
    Gerenciador principal de telemetria
    
    Features:
    - Coleta de métricas customizadas
    - Monitoramento automático do sistema
    - Sistema de alertas
    - Cache para performance
    - Exportação de dados
    - Dashboards em tempo real
    """
    
    def __init__(self, service_name: str = "unified-system"):
        self.service_name = service_name
        self.metrics: Dict[str, Metric] = {}
        self._lock = threading.RLock()
        
        # Cache para métricas agregadas
        cache_config = CacheConfig(
            max_size=500,
            default_ttl=60,  # 1 minuto
            policy=CachePolicy.LRU_TTL
        )
        self._cache = get_cache('telemetry', cache_config)
        
        # Monitor do sistema
        self.system_monitor = SystemMonitor(self)
        
        # Gerenciador de alertas
        self.alert_manager = AlertManager(self)
        
        # Métricas básicas
        self._setup_basic_metrics()
        
        logger.info(f"📊 Telemetria iniciada para serviço: {service_name}")
    
    def _setup_basic_metrics(self) -> None:
        """Configura métricas básicas do sistema"""
        # Métricas de requests
        self._register_metric('requests.total', MetricType.COUNTER, 
                            'Total de requests', 'count')
        self._register_metric('requests.success', MetricType.COUNTER,
                            'Requests bem-sucedidos', 'count')
        self._register_metric('requests.error', MetricType.COUNTER,
                            'Requests com erro', 'count')
        self._register_metric('requests.duration', MetricType.HISTOGRAM,
                            'Duração dos requests', 'seconds')
        
        # Métricas de agentes
        self._register_metric('agents.active', MetricType.GAUGE,
                            'Agentes ativos', 'count')
        self._register_metric('agents.tasks_completed', MetricType.COUNTER,
                            'Tarefas completadas', 'count')
        self._register_metric('agents.tasks_failed', MetricType.COUNTER,
                            'Tarefas falhadas', 'count')
        
        # Métricas de Neo4j
        self._register_metric('neo4j.queries.total', MetricType.COUNTER,
                            'Total de queries Neo4j', 'count')
        self._register_metric('neo4j.queries.duration', MetricType.HISTOGRAM,
                            'Duração das queries Neo4j', 'seconds')
        self._register_metric('neo4j.connections.active', MetricType.GAUGE,
                            'Conexões Neo4j ativas', 'count')
    
    def _register_metric(self, name: str, type: MetricType, description: str, 
                        unit: str, tags: Optional[Dict[str, str]] = None) -> Metric:
        """Registra nova métrica"""
        with self._lock:
            metric = Metric(
                name=name,
                type=type,
                description=description,
                unit=unit,
                tags=tags or {}
            )
            self.metrics[name] = metric
            return metric
    
    def counter(self, name: str, value: Union[int, float] = 1, 
               tags: Optional[Dict[str, str]] = None,
               metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Incrementa contador
        
        Args:
            name: Nome da métrica
            value: Valor a incrementar
            tags: Tags adicionais
            metadata: Metadados adicionais
        """
        with self._lock:
            if name not in self.metrics:
                self._register_metric(name, MetricType.COUNTER, f"Counter {name}", "count")
            
            metric = self.metrics[name]
            
            # Para contadores, somar ao último valor
            latest = metric.get_latest()
            current_value = latest.value if latest else 0
            new_value = current_value + value
            
            metric.add_point(new_value, tags, metadata)
    
    def gauge(self, name: str, value: Union[int, float], 
             tags: Optional[Dict[str, str]] = None,
             metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Define valor de gauge
        
        Args:
            name: Nome da métrica
            value: Valor atual
            tags: Tags adicionais
            metadata: Metadados adicionais
        """
        with self._lock:
            if name not in self.metrics:
                self._register_metric(name, MetricType.GAUGE, f"Gauge {name}", "value")
            
            self.metrics[name].add_point(value, tags, metadata)
    
    def histogram(self, name: str, value: Union[int, float],
                 tags: Optional[Dict[str, str]] = None,
                 metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Adiciona valor ao histograma
        
        Args:
            name: Nome da métrica
            value: Valor a adicionar
            tags: Tags adicionais
            metadata: Metadados adicionais
        """
        with self._lock:
            if name not in self.metrics:
                self._register_metric(name, MetricType.HISTOGRAM, f"Histogram {name}", "value")
            
            self.metrics[name].add_point(value, tags, metadata)
    
    @contextmanager
    def timer(self, name: str, tags: Optional[Dict[str, str]] = None,
             metadata: Optional[Dict[str, Any]] = None):
        """
        Context manager para medir tempo
        
        Args:
            name: Nome da métrica
            tags: Tags adicionais
            metadata: Metadados adicionais
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.histogram(name, duration, tags, metadata)
    
    def timed(self, metric_name: str, tags: Optional[Dict[str, str]] = None):
        """
        Decorator para medir tempo de execução
        
        Args:
            metric_name: Nome da métrica
            tags: Tags adicionais
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                with self.timer(metric_name, tags):
                    return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def get_metric(self, name: str) -> Optional[Metric]:
        """Obtém métrica por nome"""
        return self.metrics.get(name)
    
    def list_metrics(self) -> List[str]:
        """Lista nomes de todas as métricas"""
        return list(self.metrics.keys())
    
    def get_metric_summary(self, name: str, window_seconds: Optional[int] = None) -> Dict[str, Any]:
        """
        Obtém resumo de métrica
        
        Args:
            name: Nome da métrica
            window_seconds: Janela de tempo em segundos
            
        Returns:
            Resumo da métrica
        """
        cache_key = f"summary_{name}_{window_seconds}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached
        
        metric = self.get_metric(name)
        if not metric:
            return {}
        
        latest = metric.get_latest()
        summary = {
            'name': name,
            'type': metric.type.value,
            'description': metric.description,
            'unit': metric.unit,
            'points_count': len(metric.points),
            'latest_value': latest.value if latest else None,
            'latest_timestamp': latest.timestamp if latest else None,
            'average': metric.get_average(window_seconds),
            'max': metric.get_max(window_seconds),
            'min': metric.get_min(window_seconds)
        }
        
        if metric.type in [MetricType.COUNTER, MetricType.RATE]:
            summary['rate'] = metric.get_rate(window_seconds or 60)
        
        # Cache por 30 segundos
        self._cache.set(cache_key, summary, ttl=30)
        
        return summary
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Obtém dados para dashboard"""
        dashboard = {
            'service': self.service_name,
            'timestamp': datetime.now().isoformat(),
            'metrics_count': len(self.metrics),
            'system': {},
            'applications': {},
            'alerts': self.alert_manager.get_alert_stats()
        }
        
        # Métricas do sistema
        system_metrics = [
            'system.cpu.percent', 'system.memory.percent', 'system.disk.percent',
            'process.memory.rss_mb', 'process.cpu.percent', 'process.threads.count'
        ]
        
        for metric_name in system_metrics:
            if metric_name in self.metrics:
                summary = self.get_metric_summary(metric_name, 300)  # Últimos 5 minutos
                dashboard['system'][metric_name.split('.')[-1]] = summary.get('latest_value', 0)
        
        # Métricas de aplicação
        app_metrics = [
            'requests.total', 'requests.success', 'requests.error',
            'agents.active', 'neo4j.connections.active'
        ]
        
        for metric_name in app_metrics:
            if metric_name in self.metrics:
                summary = self.get_metric_summary(metric_name, 300)
                key = metric_name.replace('.', '_')
                dashboard['applications'][key] = summary.get('latest_value', 0)
        
        return dashboard
    
    def export_metrics(self, format: str = 'json', window_seconds: Optional[int] = None) -> str:
        """
        Exporta métricas em formato específico
        
        Args:
            format: Formato de exportação (json, prometheus)
            window_seconds: Janela de tempo
            
        Returns:
            String com métricas exportadas
        """
        if format == 'json':
            return self._export_json(window_seconds)
        elif format == 'prometheus':
            return self._export_prometheus(window_seconds)
        else:
            raise ValueError(f"Formato não suportado: {format}")
    
    def _export_json(self, window_seconds: Optional[int]) -> str:
        """Exporta métricas em formato JSON"""
        export_data = {
            'service': self.service_name,
            'timestamp': datetime.now().isoformat(),
            'window_seconds': window_seconds,
            'metrics': {}
        }
        
        for name in self.metrics:
            export_data['metrics'][name] = self.get_metric_summary(name, window_seconds)
        
        return json.dumps(export_data, indent=2)
    
    def _export_prometheus(self, window_seconds: Optional[int]) -> str:
        """Exporta métricas em formato Prometheus"""
        lines = []
        
        for name, metric in self.metrics.items():
            latest = metric.get_latest()
            if not latest:
                continue
            
            # Converter nome para formato Prometheus
            prom_name = name.replace('.', '_').replace('-', '_')
            
            # Adicionar help e type
            lines.append(f"# HELP {prom_name} {metric.description}")
            lines.append(f"# TYPE {prom_name} {metric.type.value}")
            
            # Adicionar valor
            tags_str = ""
            if latest.tags:
                tag_pairs = [f'{k}="{v}"' for k, v in latest.tags.items()]
                tags_str = "{" + ",".join(tag_pairs) + "}"
            
            lines.append(f"{prom_name}{tags_str} {latest.value} {int(latest.timestamp * 1000)}")
        
        return "\n".join(lines)
    
    def start_monitoring(self, system_interval: float = 5.0, alert_interval: float = 30.0) -> None:
        """Inicia monitoramento automático"""
        self.system_monitor.start(system_interval)
        self.alert_manager.start_checking(alert_interval)
        logger.info("🔍 Monitoramento automático iniciado")
    
    def stop_monitoring(self) -> None:
        """Para monitoramento automático"""
        self.system_monitor.stop()
        self.alert_manager.stop_checking()
        logger.info("🔍 Monitoramento automático parado")
    
    def add_alert_rule(self, metric_name: str, condition: str, threshold: float,
                      severity: Severity, message: str) -> None:
        """Adiciona regra de alerta"""
        self.alert_manager.add_rule(metric_name, condition, threshold, severity, message)


# Instância global de telemetria
_telemetry_manager: Optional[TelemetryManager] = None
_telemetry_lock = threading.Lock()


def get_telemetry(service_name: str = "unified-system") -> TelemetryManager:
    """
    Obtém instância singleton do gerenciador de telemetria
    
    Args:
        service_name: Nome do serviço
        
    Returns:
        Instância do gerenciador
    """
    global _telemetry_manager
    
    if _telemetry_manager is None:
        with _telemetry_lock:
            if _telemetry_manager is None:
                _telemetry_manager = TelemetryManager(service_name)
    
    return _telemetry_manager


# Funções de conveniência
def counter(name: str, value: Union[int, float] = 1, **kwargs) -> None:
    """Função de conveniência para counter"""
    get_telemetry().counter(name, value, **kwargs)


def gauge(name: str, value: Union[int, float], **kwargs) -> None:
    """Função de conveniência para gauge"""
    get_telemetry().gauge(name, value, **kwargs)


def histogram(name: str, value: Union[int, float], **kwargs) -> None:
    """Função de conveniência para histogram"""
    get_telemetry().histogram(name, value, **kwargs)


def timer(name: str, **kwargs):
    """Função de conveniência para timer"""
    return get_telemetry().timer(name, **kwargs)


def timed(metric_name: str, **kwargs):
    """Função de conveniência para decorator timed"""
    return get_telemetry().timed(metric_name, **kwargs)


# Setup de alertas padrão
def setup_default_alerts():
    """Configura alertas padrão do sistema"""
    telemetry = get_telemetry()
    
    # Alertas de sistema
    telemetry.add_alert_rule('system.cpu.percent', '>', 80.0, 
                           Severity.HIGH, 'CPU alto: {value:.1f}%')
    telemetry.add_alert_rule('system.memory.percent', '>', 85.0,
                           Severity.HIGH, 'Memória alta: {value:.1f}%')
    telemetry.add_alert_rule('system.disk.percent', '>', 90.0,
                           Severity.CRITICAL, 'Disco cheio: {value:.1f}%')
    
    # Alertas de processo
    telemetry.add_alert_rule('process.memory.rss_mb', '>', 1000.0,
                           Severity.MEDIUM, 'Processo usando muita memória: {value:.1f}MB')
    telemetry.add_alert_rule('process.cpu.percent', '>', 50.0,
                           Severity.MEDIUM, 'Processo usando muito CPU: {value:.1f}%')
    
    logger.info("📋 Alertas padrão configurados")


if __name__ == "__main__":
    # Teste do sistema de telemetria
    print("📊 Testando sistema de telemetria...")
    
    # Configurar telemetria
    telemetry = get_telemetry("test-service")
    setup_default_alerts()
    
    # Testar métricas básicas
    counter('test.requests', 1, tags={'endpoint': '/api/test'})
    gauge('test.active_users', 42)
    histogram('test.response_time', 0.123)
    
    # Testar timer
    with timer('test.operation_duration'):
        time.sleep(0.1)
    
    # Testar decorator
    @timed('test.function_duration')
    def test_function():
        time.sleep(0.05)
        return "resultado"
    
    result = test_function()
    print(f"Função retornou: {result}")
    
    # Mostrar resumos
    for metric_name in ['test.requests', 'test.active_users', 'test.response_time']:
        summary = telemetry.get_metric_summary(metric_name)
        print(f"\nMétrica: {metric_name}")
        print(f"Último valor: {summary.get('latest_value')}")
        print(f"Tipo: {summary.get('type')}")
    
    # Iniciar monitoramento
    telemetry.start_monitoring(system_interval=2.0, alert_interval=10.0)
    
    print("\nMonitoramento iniciado por 10 segundos...")
    time.sleep(10)
    
    # Mostrar dashboard
    dashboard = telemetry.get_dashboard_data()
    print(f"\nDashboard:")
    print(f"Métricas de sistema: {len(dashboard['system'])}")
    print(f"Métricas de aplicação: {len(dashboard['applications'])}")
    print(f"Alertas ativos: {dashboard['alerts']['active_alerts']}")
    
    # Exportar métricas
    json_export = telemetry.export_metrics('json', 300)
    print(f"\nExportação JSON: {len(json_export)} caracteres")
    
    # Parar monitoramento
    telemetry.stop_monitoring()
    
    print("\n✅ Sistema de telemetria testado com sucesso!")