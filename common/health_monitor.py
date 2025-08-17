#!/usr/bin/env python3
"""
🏥 Health Monitor - Sistema de Monitoramento de Saúde
Monitor abrangente para Neo4j, serviços de descoberta, agentes ativos e sistema de arquivos
"""

import os
import time
import psutil
import threading
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Protocol
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import logging
import json
import socket
from contextlib import asynccontextmanager

# Local imports
from .cache_manager import get_cache, CacheConfig, CachePolicy
from .logging_config import get_logger
from .telemetry import get_telemetry, timer, counter, gauge
from .neo4j_connection_pool import get_neo4j_pool

logger = get_logger(__name__)
telemetry = get_telemetry()


class HealthStatus(Enum):
    """Status de saúde"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentType(Enum):
    """Tipos de componentes monitorados"""
    DATABASE = "database"
    SERVICE = "service"
    FILESYSTEM = "filesystem"
    NETWORK = "network"
    AGENT = "agent"
    SYSTEM = "system"


@dataclass
class HealthCheck:
    """Definição de um health check"""
    name: str
    component_type: ComponentType
    check_function: Callable
    interval_seconds: int = 30
    timeout_seconds: int = 10
    retries: int = 3
    critical: bool = False
    enabled: bool = True
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthResult:
    """Resultado de um health check"""
    name: str
    status: HealthStatus
    message: str
    timestamp: datetime
    execution_time: float
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário"""
        return {
            'name': self.name,
            'status': self.status.value,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'execution_time': self.execution_time,
            'details': self.details,
            'error': self.error
        }


@dataclass
class SystemHealth:
    """Saúde geral do sistema"""
    overall_status: HealthStatus
    timestamp: datetime
    components: Dict[str, HealthResult] = field(default_factory=dict)
    critical_failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    uptime: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário"""
        return {
            'overall_status': self.overall_status.value,
            'timestamp': self.timestamp.isoformat(),
            'components': {name: result.to_dict() for name, result in self.components.items()},
            'critical_failures': self.critical_failures,
            'warnings': self.warnings,
            'uptime': self.uptime,
            'summary': {
                'total_checks': len(self.components),
                'healthy': len([r for r in self.components.values() if r.status == HealthStatus.HEALTHY]),
                'degraded': len([r for r in self.components.values() if r.status == HealthStatus.DEGRADED]),
                'unhealthy': len([r for r in self.components.values() if r.status == HealthStatus.UNHEALTHY]),
                'unknown': len([r for r in self.components.values() if r.status == HealthStatus.UNKNOWN])
            }
        }


class DatabaseHealthChecker:
    """Health checker para bancos de dados"""
    
    @staticmethod
    async def check_neo4j() -> HealthResult:
        """Verifica saúde do Neo4j"""
        start_time = time.time()
        
        try:
            pool = get_neo4j_pool()
            
            # Teste básico de conectividade
            result = pool.execute_query("RETURN 1 as test", use_cache=False)
            
            if result and len(result) > 0 and result[0].get('test') == 1:
                # Obter estatísticas do pool
                stats = pool.get_stats()
                
                execution_time = time.time() - start_time
                
                # Verificar métricas de saúde
                status = HealthStatus.HEALTHY
                message = "Neo4j funcionando normalmente"
                
                if stats.circuit_breaker_state != "closed":
                    status = HealthStatus.DEGRADED
                    message = f"Circuit breaker: {stats.circuit_breaker_state}"
                elif stats.success_rate < 0.8:
                    status = HealthStatus.DEGRADED
                    message = f"Taxa de sucesso baixa: {stats.success_rate:.2%}"
                elif execution_time > 5.0:
                    status = HealthStatus.DEGRADED
                    message = f"Tempo de resposta alto: {execution_time:.2f}s"
                
                return HealthResult(
                    name="neo4j",
                    status=status,
                    message=message,
                    timestamp=datetime.now(),
                    execution_time=execution_time,
                    details={
                        'total_connections': stats.total_connections,
                        'active_connections': stats.active_connections,
                        'success_rate': stats.success_rate,
                        'avg_query_time': stats.avg_query_time,
                        'circuit_breaker_state': stats.circuit_breaker_state
                    }
                )
            else:
                raise Exception("Resposta inválida do Neo4j")
        
        except Exception as e:
            execution_time = time.time() - start_time
            
            return HealthResult(
                name="neo4j",
                status=HealthStatus.UNHEALTHY,
                message=f"Falha na conexão com Neo4j: {str(e)}",
                timestamp=datetime.now(),
                execution_time=execution_time,
                error=str(e)
            )


class ServiceHealthChecker:
    """Health checker para serviços"""
    
    @staticmethod
    async def check_service_discovery() -> HealthResult:
        """Verifica serviço de descoberta"""
        start_time = time.time()
        
        try:
            # Verificar se serviço está respondendo
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                url = "http://localhost:8002/health"  # Porta padrão do service discovery
                
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        execution_time = time.time() - start_time
                        
                        return HealthResult(
                            name="service_discovery",
                            status=HealthStatus.HEALTHY,
                            message="Serviço de descoberta funcionando",
                            timestamp=datetime.now(),
                            execution_time=execution_time,
                            details=data
                        )
                    else:
                        raise Exception(f"Status HTTP: {response.status}")
        
        except Exception as e:
            execution_time = time.time() - start_time
            
            return HealthResult(
                name="service_discovery",
                status=HealthStatus.UNHEALTHY,
                message=f"Serviço de descoberta indisponível: {str(e)}",
                timestamp=datetime.now(),
                execution_time=execution_time,
                error=str(e)
            )
    
    @staticmethod
    async def check_port_availability(host: str, port: int, name: str) -> HealthResult:
        """Verifica disponibilidade de porta"""
        start_time = time.time()
        
        try:
            # Tentar conectar à porta
            future = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(future, timeout=3.0)
            writer.close()
            await writer.wait_closed()
            
            execution_time = time.time() - start_time
            
            return HealthResult(
                name=name,
                status=HealthStatus.HEALTHY,
                message=f"Porta {host}:{port} acessível",
                timestamp=datetime.now(),
                execution_time=execution_time,
                details={'host': host, 'port': port}
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            
            return HealthResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Porta {host}:{port} inacessível: {str(e)}",
                timestamp=datetime.now(),
                execution_time=execution_time,
                error=str(e)
            )


class FilesystemHealthChecker:
    """Health checker para sistema de arquivos"""
    
    @staticmethod
    def check_disk_space(path: Path, warning_threshold: float = 0.8, 
                        critical_threshold: float = 0.9) -> HealthResult:
        """Verifica espaço em disco"""
        start_time = time.time()
        
        try:
            # Obter estatísticas do disco
            usage = psutil.disk_usage(str(path))
            used_percentage = usage.used / usage.total
            
            execution_time = time.time() - start_time
            
            # Determinar status
            if used_percentage >= critical_threshold:
                status = HealthStatus.UNHEALTHY
                message = f"Espaço em disco crítico: {used_percentage:.1%} usado"
            elif used_percentage >= warning_threshold:
                status = HealthStatus.DEGRADED
                message = f"Espaço em disco baixo: {used_percentage:.1%} usado"
            else:
                status = HealthStatus.HEALTHY
                message = f"Espaço em disco OK: {used_percentage:.1%} usado"
            
            return HealthResult(
                name=f"disk_space_{path.name}",
                status=status,
                message=message,
                timestamp=datetime.now(),
                execution_time=execution_time,
                details={
                    'path': str(path),
                    'total_gb': usage.total / (1024**3),
                    'used_gb': usage.used / (1024**3),
                    'free_gb': usage.free / (1024**3),
                    'used_percentage': used_percentage
                }
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            
            return HealthResult(
                name=f"disk_space_{path.name}",
                status=HealthStatus.UNKNOWN,
                message=f"Erro ao verificar disco: {str(e)}",
                timestamp=datetime.now(),
                execution_time=execution_time,
                error=str(e)
            )
    
    @staticmethod
    def check_directory_writeable(path: Path) -> HealthResult:
        """Verifica se diretório é gravável"""
        start_time = time.time()
        
        try:
            # Tentar criar arquivo temporário
            test_file = path / f"health_test_{int(time.time())}.tmp"
            
            with open(test_file, 'w') as f:
                f.write("health check test")
            
            # Remover arquivo de teste
            test_file.unlink()
            
            execution_time = time.time() - start_time
            
            return HealthResult(
                name=f"writeable_{path.name}",
                status=HealthStatus.HEALTHY,
                message=f"Diretório {path} é gravável",
                timestamp=datetime.now(),
                execution_time=execution_time,
                details={'path': str(path)}
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            
            return HealthResult(
                name=f"writeable_{path.name}",
                status=HealthStatus.UNHEALTHY,
                message=f"Diretório {path} não é gravável: {str(e)}",
                timestamp=datetime.now(),
                execution_time=execution_time,
                error=str(e)
            )


class SystemHealthChecker:
    """Health checker para sistema"""
    
    @staticmethod
    def check_memory() -> HealthResult:
        """Verifica uso de memória"""
        start_time = time.time()
        
        try:
            memory = psutil.virtual_memory()
            used_percentage = memory.percent / 100
            
            execution_time = time.time() - start_time
            
            # Determinar status
            if used_percentage >= 0.9:
                status = HealthStatus.UNHEALTHY
                message = f"Memória crítica: {memory.percent:.1f}% usada"
            elif used_percentage >= 0.8:
                status = HealthStatus.DEGRADED
                message = f"Memória alta: {memory.percent:.1f}% usada"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memória OK: {memory.percent:.1f}% usada"
            
            return HealthResult(
                name="memory",
                status=status,
                message=message,
                timestamp=datetime.now(),
                execution_time=execution_time,
                details={
                    'total_gb': memory.total / (1024**3),
                    'used_gb': memory.used / (1024**3),
                    'available_gb': memory.available / (1024**3),
                    'percentage': memory.percent
                }
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            
            return HealthResult(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message=f"Erro ao verificar memória: {str(e)}",
                timestamp=datetime.now(),
                execution_time=execution_time,
                error=str(e)
            )
    
    @staticmethod
    def check_cpu() -> HealthResult:
        """Verifica uso de CPU"""
        start_time = time.time()
        
        try:
            # Medir CPU por 1 segundo
            cpu_percent = psutil.cpu_percent(interval=1)
            
            execution_time = time.time() - start_time
            
            # Determinar status
            if cpu_percent >= 90:
                status = HealthStatus.UNHEALTHY
                message = f"CPU crítica: {cpu_percent:.1f}%"
            elif cpu_percent >= 70:
                status = HealthStatus.DEGRADED
                message = f"CPU alta: {cpu_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU OK: {cpu_percent:.1f}%"
            
            return HealthResult(
                name="cpu",
                status=status,
                message=message,
                timestamp=datetime.now(),
                execution_time=execution_time,
                details={
                    'percentage': cpu_percent,
                    'cores': psutil.cpu_count(),
                    'logical_cores': psutil.cpu_count(logical=True)
                }
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            
            return HealthResult(
                name="cpu",
                status=HealthStatus.UNKNOWN,
                message=f"Erro ao verificar CPU: {str(e)}",
                timestamp=datetime.now(),
                execution_time=execution_time,
                error=str(e)
            )


class HealthMonitor:
    """
    Monitor principal de saúde do sistema
    
    Features:
    - Verificações automáticas e sob demanda
    - Métricas de saúde em tempo real
    - Alertas baseados em thresholds
    - Cache de resultados
    - API HTTP para status
    - Dependências entre componentes
    """
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.start_time = datetime.now()
        self.health_checks: Dict[str, HealthCheck] = {}
        self.latest_results: Dict[str, HealthResult] = {}
        self._lock = threading.RLock()
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # Cache para resultados
        cache_config = CacheConfig(
            max_size=100,
            default_ttl=30,  # 30 segundos
            policy=CachePolicy.TTL
        )
        self._cache = get_cache('health_monitor', cache_config)
        
        # Configurar checks padrão
        self._setup_default_checks()
        
        logger.info(f"🏥 Health Monitor inicializado para: {project_root}")
    
    def _setup_default_checks(self) -> None:
        """Configura health checks padrão"""
        
        # Database checks
        self.register_check(HealthCheck(
            name="neo4j",
            component_type=ComponentType.DATABASE,
            check_function=DatabaseHealthChecker.check_neo4j,
            interval_seconds=60,
            critical=True
        ))
        
        # Service checks
        self.register_check(HealthCheck(
            name="service_discovery",
            component_type=ComponentType.SERVICE,
            check_function=ServiceHealthChecker.check_service_discovery,
            interval_seconds=30
        ))
        
        # Filesystem checks
        self.register_check(HealthCheck(
            name="disk_space_root",
            component_type=ComponentType.FILESYSTEM,
            check_function=lambda: FilesystemHealthChecker.check_disk_space(Path("/")),
            interval_seconds=300,  # 5 minutos
            critical=True
        ))
        
        self.register_check(HealthCheck(
            name="logs_writeable",
            component_type=ComponentType.FILESYSTEM,
            check_function=lambda: FilesystemHealthChecker.check_directory_writeable(
                self.project_root / "logging" / "logs"
            ),
            interval_seconds=300
        ))
        
        # System checks
        self.register_check(HealthCheck(
            name="memory",
            component_type=ComponentType.SYSTEM,
            check_function=SystemHealthChecker.check_memory,
            interval_seconds=30,
            critical=True
        ))
        
        self.register_check(HealthCheck(
            name="cpu",
            component_type=ComponentType.SYSTEM,
            check_function=SystemHealthChecker.check_cpu,
            interval_seconds=30
        ))
        
        logger.debug(f"Configurados {len(self.health_checks)} health checks padrão")
    
    def register_check(self, health_check: HealthCheck) -> None:
        """Registra novo health check"""
        with self._lock:
            self.health_checks[health_check.name] = health_check
            logger.debug(f"Health check registrado: {health_check.name}")
    
    def unregister_check(self, name: str) -> bool:
        """Remove health check"""
        with self._lock:
            if name in self.health_checks:
                del self.health_checks[name]
                if name in self.latest_results:
                    del self.latest_results[name]
                logger.debug(f"Health check removido: {name}")
                return True
        return False
    
    async def run_check(self, name: str) -> HealthResult:
        """
        Executa health check específico
        
        Args:
            name: Nome do health check
            
        Returns:
            Resultado do health check
        """
        if name not in self.health_checks:
            raise ValueError(f"Health check não encontrado: {name}")
        
        health_check = self.health_checks[name]
        
        # Verificar cache
        cache_key = f"health_{name}"
        cached_result = self._cache.get(cache_key)
        if cached_result:
            return HealthResult(**cached_result)
        
        logger.debug(f"Executando health check: {name}")
        
        with timer(f'health.check_time', tags={'check_name': name}):
            try:
                # Executar verificação com retry
                for attempt in range(health_check.retries + 1):
                    try:
                        if asyncio.iscoroutinefunction(health_check.check_function):
                            result = await asyncio.wait_for(
                                health_check.check_function(), 
                                timeout=health_check.timeout_seconds
                            )
                        else:
                            result = health_check.check_function()
                        
                        break
                    except Exception as e:
                        if attempt == health_check.retries:
                            # Última tentativa falhou
                            result = HealthResult(
                                name=name,
                                status=HealthStatus.UNHEALTHY,
                                message=f"Falha após {health_check.retries + 1} tentativas: {str(e)}",
                                timestamp=datetime.now(),
                                execution_time=0.0,
                                error=str(e)
                            )
                        else:
                            # Aguardar antes da próxima tentativa
                            await asyncio.sleep(1)
                
                # Registrar métricas
                self._record_check_metrics(name, result)
                
                # Armazenar resultado
                with self._lock:
                    self.latest_results[name] = result
                
                # Cachear resultado
                self._cache.set(cache_key, asdict(result), ttl=30)
                
                return result
                
            except Exception as e:
                logger.error(f"Erro fatal no health check {name}: {e}")
                
                result = HealthResult(
                    name=name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Erro fatal: {str(e)}",
                    timestamp=datetime.now(),
                    execution_time=0.0,
                    error=str(e)
                )
                
                with self._lock:
                    self.latest_results[name] = result
                
                return result
    
    async def run_all_checks(self) -> Dict[str, HealthResult]:
        """
        Executa todos os health checks
        
        Returns:
            Dicionário com resultados de todos os checks
        """
        logger.debug("Executando todos os health checks")
        
        # Executar checks em paralelo
        tasks = []
        for name, health_check in self.health_checks.items():
            if health_check.enabled:
                tasks.append(self.run_check(name))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            result_dict = {}
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    check_name = list(self.health_checks.keys())[i]
                    result_dict[check_name] = HealthResult(
                        name=check_name,
                        status=HealthStatus.UNKNOWN,
                        message=f"Erro na execução: {str(result)}",
                        timestamp=datetime.now(),
                        execution_time=0.0,
                        error=str(result)
                    )
                else:
                    result_dict[result.name] = result
            
            return result_dict
        
        return {}
    
    def get_system_health(self) -> SystemHealth:
        """
        Obtém saúde geral do sistema
        
        Returns:
            SystemHealth com status consolidado
        """
        with self._lock:
            results = self.latest_results.copy()
        
        if not results:
            return SystemHealth(
                overall_status=HealthStatus.UNKNOWN,
                timestamp=datetime.now(),
                uptime=(datetime.now() - self.start_time).total_seconds()
            )
        
        # Determinar status geral
        critical_failures = []
        warnings = []
        
        status_counts = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.DEGRADED: 0,
            HealthStatus.UNHEALTHY: 0,
            HealthStatus.UNKNOWN: 0
        }
        
        for name, result in results.items():
            status_counts[result.status] += 1
            
            health_check = self.health_checks.get(name)
            if health_check and health_check.critical and result.status == HealthStatus.UNHEALTHY:
                critical_failures.append(f"{name}: {result.message}")
            elif result.status in [HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]:
                warnings.append(f"{name}: {result.message}")
        
        # Determinar status geral
        if critical_failures:
            overall_status = HealthStatus.UNHEALTHY
        elif status_counts[HealthStatus.UNHEALTHY] > 0:
            overall_status = HealthStatus.DEGRADED
        elif status_counts[HealthStatus.DEGRADED] > 0:
            overall_status = HealthStatus.DEGRADED
        elif status_counts[HealthStatus.UNKNOWN] > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        return SystemHealth(
            overall_status=overall_status,
            timestamp=datetime.now(),
            components=results,
            critical_failures=critical_failures,
            warnings=warnings,
            uptime=(datetime.now() - self.start_time).total_seconds()
        )
    
    def _record_check_metrics(self, name: str, result: HealthResult) -> None:
        """Registra métricas do health check"""
        tags = {
            'check_name': name,
            'status': result.status.value
        }
        
        # Contador por status
        counter(f'health.checks.{result.status.value}', tags=tags)
        
        # Tempo de execução
        gauge('health.check_execution_time', result.execution_time, tags=tags)
        
        # Status numérico para agregação
        status_value = {
            HealthStatus.HEALTHY: 1,
            HealthStatus.DEGRADED: 0.5,
            HealthStatus.UNHEALTHY: 0,
            HealthStatus.UNKNOWN: -1
        }[result.status]
        
        gauge('health.check_status', status_value, tags=tags)
    
    def start_monitoring(self, interval: float = 60.0) -> None:
        """Inicia monitoramento automático"""
        if self._monitoring:
            logger.warning("Monitoramento já está ativo")
            return
        
        self._monitoring = True
        
        def monitor_worker():
            logger.info(f"🔍 Iniciando monitoramento de saúde (intervalo: {interval}s)")
            
            while self._monitoring:
                try:
                    # Executar checks que precisam ser executados
                    current_time = time.time()
                    
                    for name, health_check in self.health_checks.items():
                        if not health_check.enabled:
                            continue
                        
                        # Verificar se é hora de executar
                        last_result = self.latest_results.get(name)
                        if (not last_result or 
                            (current_time - last_result.timestamp.timestamp()) >= health_check.interval_seconds):
                            
                            # Executar check assíncronamente
                            try:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                loop.run_until_complete(self.run_check(name))
                                loop.close()
                            except Exception as e:
                                logger.error(f"Erro no health check {name}: {e}")
                    
                    # Atualizar métricas gerais
                    system_health = self.get_system_health()
                    gauge('health.overall_status', {
                        HealthStatus.HEALTHY: 1,
                        HealthStatus.DEGRADED: 0.5,
                        HealthStatus.UNHEALTHY: 0,
                        HealthStatus.UNKNOWN: -1
                    }[system_health.overall_status])
                    
                    gauge('health.uptime_seconds', system_health.uptime)
                    
                    time.sleep(min(interval, 30))  # Máximo 30s entre verificações
                    
                except Exception as e:
                    logger.error(f"Erro no worker de monitoramento: {e}")
                    time.sleep(10)
        
        self._monitor_thread = threading.Thread(target=monitor_worker, daemon=True)
        self._monitor_thread.start()
        
        logger.info("✅ Monitoramento de saúde iniciado")
    
    def stop_monitoring(self) -> None:
        """Para monitoramento automático"""
        if not self._monitoring:
            return
        
        logger.info("🛑 Parando monitoramento de saúde...")
        self._monitoring = False
        
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
        
        logger.info("✅ Monitoramento de saúde parado")
    
    def get_check_history(self, name: str, hours: int = 24) -> List[HealthResult]:
        """Obtém histórico de um health check"""
        # TODO: Implementar armazenamento de histórico
        return []
    
    def export_health_report(self, format: str = 'json') -> str:
        """Exporta relatório de saúde"""
        system_health = self.get_system_health()
        
        if format == 'json':
            return json.dumps(system_health.to_dict(), indent=2)
        elif format == 'prometheus':
            lines = []
            for name, result in system_health.components.items():
                status_value = {
                    HealthStatus.HEALTHY: 1,
                    HealthStatus.DEGRADED: 0.5,
                    HealthStatus.UNHEALTHY: 0,
                    HealthStatus.UNKNOWN: -1
                }[result.status]
                
                lines.append(f'health_check_status{{check="{name}"}} {status_value}')
                lines.append(f'health_check_execution_time{{check="{name}"}} {result.execution_time}')
            
            return '\n'.join(lines)
        else:
            raise ValueError(f"Formato não suportado: {format}")


# Instância global do monitor
_health_monitor: Optional[HealthMonitor] = None
_monitor_lock = threading.Lock()


def get_health_monitor(project_root: Optional[Path] = None) -> HealthMonitor:
    """
    Obtém instância singleton do health monitor
    
    Args:
        project_root: Diretório raiz do projeto
        
    Returns:
        Instância do monitor
    """
    global _health_monitor
    
    if _health_monitor is None:
        with _monitor_lock:
            if _health_monitor is None:
                if project_root is None:
                    project_root = Path.cwd()
                _health_monitor = HealthMonitor(project_root)
    
    return _health_monitor


# Funções de conveniência
async def check_system_health() -> SystemHealth:
    """Função de conveniência para verificar saúde do sistema"""
    monitor = get_health_monitor()
    await monitor.run_all_checks()
    return monitor.get_system_health()


async def check_component_health(component_name: str) -> HealthResult:
    """Função de conveniência para verificar componente específico"""
    monitor = get_health_monitor()
    return await monitor.run_check(component_name)


if __name__ == "__main__":
    # Teste do health monitor
    print("🏥 Testando Health Monitor...")
    
    async def test_health_monitor():
        # Obter monitor
        monitor = get_health_monitor(Path.cwd())
        
        # Executar todos os checks
        print("Executando health checks...")
        results = await monitor.run_all_checks()
        
        print(f"\nResultados dos checks:")
        for name, result in results.items():
            status_emoji = {
                HealthStatus.HEALTHY: "✅",
                HealthStatus.DEGRADED: "⚠️",
                HealthStatus.UNHEALTHY: "❌",
                HealthStatus.UNKNOWN: "❓"
            }[result.status]
            
            print(f"{status_emoji} {name}: {result.message} ({result.execution_time:.3f}s)")
        
        # Obter saúde geral
        system_health = monitor.get_system_health()
        print(f"\nSaúde geral do sistema: {system_health.overall_status.value}")
        print(f"Uptime: {system_health.uptime:.1f}s")
        print(f"Componentes: {len(system_health.components)}")
        
        if system_health.critical_failures:
            print(f"Falhas críticas: {len(system_health.critical_failures)}")
            for failure in system_health.critical_failures:
                print(f"  ❌ {failure}")
        
        if system_health.warnings:
            print(f"Avisos: {len(system_health.warnings)}")
            for warning in system_health.warnings[:3]:  # Mostrar apenas os primeiros 3
                print(f"  ⚠️ {warning}")
        
        # Iniciar monitoramento por alguns segundos
        monitor.start_monitoring(interval=10)
        print("\nMonitoramento iniciado por 15 segundos...")
        
        await asyncio.sleep(15)
        
        monitor.stop_monitoring()
        
        # Exportar relatório
        report = monitor.export_health_report('json')
        print(f"\nRelatório JSON: {len(report)} caracteres")
        
        print("\n✅ Health Monitor testado com sucesso!")
    
    # Executar teste
    try:
        asyncio.run(test_health_monitor())
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        logger.error(f"Erro no teste do health monitor: {e}")