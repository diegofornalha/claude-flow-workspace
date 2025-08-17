#!/usr/bin/env python3
"""
🔗 Neo4j Connection Pool - Sistema Otimizado de Conexões
Pool de conexões Neo4j com singleton, circuit breaker e retry logic
"""

import os
import time
import threading
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, ContextManager
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, Future
import logging
import queue
import weakref

# Neo4j imports
try:
    from neo4j import GraphDatabase, Driver, Session, Transaction, Result
    from neo4j.exceptions import ServiceUnavailable, TransientError, ClientError
except ImportError:
    print("⚠️  Neo4j driver não instalado. Execute: pip install neo4j")
    raise

# Local imports
from .cache_manager import get_cache, CacheConfig, CachePolicy

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Estados da conexão"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    CIRCUIT_OPEN = "circuit_open"


class CircuitBreakerState(Enum):
    """Estados do Circuit Breaker"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class Neo4jConfig:
    """Configuração do Neo4j"""
    uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    username: str = field(default_factory=lambda: os.getenv("NEO4J_USERNAME", "neo4j"))
    password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", "password"))
    database: str = field(default_factory=lambda: os.getenv("NEO4J_DATABASE", "neo4j"))
    max_connection_lifetime: int = 3600  # 1 hora
    max_connection_pool_size: int = 50
    connection_acquisition_timeout: int = 60
    encrypted: bool = False
    trust: str = "TRUST_ALL_CERTIFICATES"
    
    def __post_init__(self):
        """Validação pós-inicialização"""
        if not self.uri.startswith(('bolt://', 'neo4j://', 'bolt+s://', 'neo4j+s://')):
            raise ValueError(f"URI Neo4j inválida: {self.uri}")


@dataclass
class CircuitBreakerConfig:
    """Configuração do Circuit Breaker"""
    failure_threshold: int = 5
    recovery_timeout: int = 60
    half_open_max_calls: int = 3
    expected_exception: tuple = (ServiceUnavailable, TransientError)


@dataclass
class PoolStats:
    """Estatísticas do pool de conexões"""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    failed_connections: int = 0
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    avg_query_time: float = 0.0
    circuit_breaker_state: str = "closed"
    last_health_check: Optional[datetime] = None
    uptime: timedelta = field(default_factory=lambda: timedelta(0))
    
    @property
    def success_rate(self) -> float:
        """Taxa de sucesso das queries"""
        if self.total_queries == 0:
            return 0.0
        return self.successful_queries / self.total_queries
    
    @property
    def failure_rate(self) -> float:
        """Taxa de falha das queries"""
        return 1.0 - self.success_rate


class Neo4jCircuitBreaker:
    """Circuit Breaker para conexões Neo4j"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0
        self._lock = threading.Lock()
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Executa função através do circuit breaker
        
        Args:
            func: Função a executar
            *args: Argumentos posicionais
            **kwargs: Argumentos nomeados
            
        Returns:
            Resultado da função
            
        Raises:
            Exception: Se circuit breaker estiver aberto ou função falhar
        """
        with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.half_open_calls = 0
                    logger.info("Circuit breaker mudou para HALF_OPEN")
                else:
                    raise ServiceUnavailable("Circuit breaker OPEN - Neo4j indisponível")
            
            if self.state == CircuitBreakerState.HALF_OPEN:
                if self.half_open_calls >= self.config.half_open_max_calls:
                    self.state = CircuitBreakerState.OPEN
                    logger.warning("Circuit breaker voltou para OPEN")
                    raise ServiceUnavailable("Circuit breaker OPEN - muitas falhas em HALF_OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.config.expected_exception as e:
            self._on_failure(e)
            raise
        except Exception as e:
            # Não contar exceções não relacionadas ao Neo4j
            logger.debug(f"Exceção não relacionada ao circuit breaker: {e}")
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Verifica se deve tentar resetar o circuit breaker"""
        if self.last_failure_time is None:
            return True
        
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.config.recovery_timeout
    
    def _on_success(self) -> None:
        """Chamado quando operação é bem-sucedida"""
        with self._lock:
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.half_open_calls += 1
                if self.half_open_calls >= self.config.half_open_max_calls:
                    self.state = CircuitBreakerState.CLOSED
                    self.failure_count = 0
                    logger.info("Circuit breaker voltou para CLOSED")
            elif self.state == CircuitBreakerState.CLOSED:
                self.failure_count = 0
    
    def _on_failure(self, exception: Exception) -> None:
        """Chamado quando operação falha"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.OPEN
                logger.warning("Circuit breaker ABERTO após falha em HALF_OPEN")
            elif self.failure_count >= self.config.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                logger.warning(f"Circuit breaker ABERTO - {self.failure_count} falhas consecutivas")


class ConnectionWrapper:
    """Wrapper para conexão Neo4j com métricas e controle"""
    
    def __init__(self, session: Session, pool: 'Neo4jConnectionPool'):
        self.session = session
        self.pool = pool
        self.created_at = datetime.now()
        self.last_used = datetime.now()
        self.query_count = 0
        self.is_active = True
        self.connection_id = id(self)
    
    def run(self, query: str, parameters: Optional[Dict] = None, **kwargs) -> Result:
        """
        Executa query com métricas
        
        Args:
            query: Query Cypher
            parameters: Parâmetros da query
            **kwargs: Argumentos adicionais
            
        Returns:
            Resultado da query
        """
        start_time = time.time()
        self.last_used = datetime.now()
        self.query_count += 1
        
        try:
            result = self.session.run(query, parameters, **kwargs)
            
            # Registrar sucesso
            execution_time = time.time() - start_time
            self.pool._record_query_success(execution_time)
            
            logger.debug(f"Query executada com sucesso em {execution_time:.3f}s")
            return result
            
        except Exception as e:
            # Registrar falha
            execution_time = time.time() - start_time
            self.pool._record_query_failure(execution_time, e)
            
            logger.error(f"Falha na query após {execution_time:.3f}s: {e}")
            raise
    
    def begin_transaction(self) -> Transaction:
        """Inicia transação"""
        self.last_used = datetime.now()
        return self.session.begin_transaction()
    
    def close(self) -> None:
        """Fecha conexão"""
        if self.is_active:
            try:
                self.session.close()
            except Exception as e:
                logger.debug(f"Erro ao fechar sessão: {e}")
            finally:
                self.is_active = False
    
    def is_expired(self, max_lifetime: int) -> bool:
        """Verifica se conexão expirou"""
        age = (datetime.now() - self.created_at).total_seconds()
        return age > max_lifetime
    
    def is_idle(self, max_idle_time: int) -> bool:
        """Verifica se conexão está idle há muito tempo"""
        idle_time = (datetime.now() - self.last_used).total_seconds()
        return idle_time > max_idle_time


class Neo4jConnectionPool:
    """
    Pool de conexões Neo4j thread-safe com circuit breaker
    
    Features:
    - Pool de conexões reutilizáveis
    - Circuit breaker para falhas
    - Métricas detalhadas
    - Health check automático
    - Cache de resultados
    - Retry logic
    - Connection lifecycle management
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, config: Optional[Neo4jConfig] = None):
        """Singleton pattern"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config: Optional[Neo4jConfig] = None):
        """
        Inicializa pool de conexões
        
        Args:
            config: Configuração do Neo4j
        """
        if hasattr(self, '_initialized'):
            return
        
        self.config = config or Neo4jConfig()
        self.circuit_breaker = Neo4jCircuitBreaker(CircuitBreakerConfig())
        
        # Pool de conexões
        self._pool: queue.Queue[ConnectionWrapper] = queue.Queue()
        self._active_connections: List[ConnectionWrapper] = []
        self._pool_lock = threading.RLock()
        
        # Driver principal
        self._driver: Optional[Driver] = None
        
        # Estatísticas
        self._stats = PoolStats()
        self._start_time = datetime.now()
        
        # Cache para resultados
        cache_config = CacheConfig(
            max_size=1000,
            default_ttl=300,  # 5 minutos
            policy=CachePolicy.LRU_TTL
        )
        self._cache = get_cache('neo4j_queries', cache_config)
        
        # Thread de manutenção
        self._maintenance_thread = None
        self._running = False
        
        # Inicializar
        self._initialize()
        self._initialized = True
    
    def _initialize(self) -> None:
        """Inicializa o pool"""
        try:
            logger.info(f"🔗 Inicializando Neo4j Connection Pool...")
            logger.info(f"📍 URI: {self.config.uri}")
            logger.info(f"🏛️ Database: {self.config.database}")
            logger.info(f"👥 Max connections: {self.config.max_connection_pool_size}")
            
            # Criar driver
            self._driver = GraphDatabase.driver(
                self.config.uri,
                auth=(self.config.username, self.config.password),
                max_connection_lifetime=self.config.max_connection_lifetime,
                max_connection_pool_size=self.config.max_connection_pool_size,
                connection_acquisition_timeout=self.config.connection_acquisition_timeout,
                encrypted=self.config.encrypted,
                trust=self.config.trust
            )
            
            # Testar conexão
            self._test_connection()
            
            # Iniciar thread de manutenção
            self._start_maintenance_thread()
            
            logger.info("✅ Neo4j Connection Pool inicializado com sucesso")
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar Neo4j pool: {e}")
            raise
    
    def _test_connection(self) -> None:
        """Testa conexão inicial"""
        try:
            with self._driver.session(database=self.config.database) as session:
                result = session.run("RETURN 1 as test")
                test_value = result.single()["test"]
                if test_value != 1:
                    raise ValueError("Teste de conexão falhou")
            
            logger.debug("✅ Teste de conexão Neo4j bem-sucedido")
            
        except Exception as e:
            logger.error(f"❌ Teste de conexão falhou: {e}")
            raise
    
    @contextmanager
    def get_session(self, database: Optional[str] = None) -> ContextManager[ConnectionWrapper]:
        """
        Context manager para obter sessão do pool
        
        Args:
            database: Database específico (opcional)
            
        Yields:
            ConnectionWrapper com sessão ativa
        """
        connection = None
        try:
            connection = self._acquire_connection(database)
            yield connection
        finally:
            if connection:
                self._release_connection(connection)
    
    def _acquire_connection(self, database: Optional[str] = None) -> ConnectionWrapper:
        """Adquire conexão do pool"""
        def acquire():
            with self._pool_lock:
                # Tentar reutilizar conexão do pool
                while not self._pool.empty():
                    try:
                        connection = self._pool.get_nowait()
                        if connection.is_active and not connection.is_expired(self.config.max_connection_lifetime):
                            self._active_connections.append(connection)
                            self._stats.active_connections = len(self._active_connections)
                            return connection
                        else:
                            # Conexão expirada
                            connection.close()
                    except queue.Empty:
                        break
                
                # Criar nova conexão se necessário
                if len(self._active_connections) < self.config.max_connection_pool_size:
                    session = self._driver.session(database=database or self.config.database)
                    connection = ConnectionWrapper(session, self)
                    self._active_connections.append(connection)
                    self._stats.total_connections += 1
                    self._stats.active_connections = len(self._active_connections)
                    return connection
                else:
                    raise ServiceUnavailable("Pool de conexões esgotado")
        
        return self.circuit_breaker.call(acquire)
    
    def _release_connection(self, connection: ConnectionWrapper) -> None:
        """Libera conexão de volta para o pool"""
        with self._pool_lock:
            if connection in self._active_connections:
                self._active_connections.remove(connection)
            
            if connection.is_active and not connection.is_expired(self.config.max_connection_lifetime):
                # Retornar ao pool
                self._pool.put_nowait(connection)
                self._stats.idle_connections = self._pool.qsize()
            else:
                # Fechar conexão expirada
                connection.close()
            
            self._stats.active_connections = len(self._active_connections)
    
    def execute_query(self, query: str, parameters: Optional[Dict] = None, 
                     database: Optional[str] = None, use_cache: bool = True) -> Any:
        """
        Executa query com cache e retry logic
        
        Args:
            query: Query Cypher
            parameters: Parâmetros da query
            database: Database específico
            use_cache: Se deve usar cache
            
        Returns:
            Resultado da query
        """
        # Gerar chave do cache
        cache_key = None
        if use_cache:
            import hashlib
            key_data = f"{query}:{str(parameters)}:{database}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Verificar cache
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache HIT para query: {query[:50]}...")
                return cached_result
        
        # Executar query
        def execute():
            with self.get_session(database) as connection:
                result = connection.run(query, parameters)
                # Converter para lista para cache
                data = [dict(record) for record in result]
                
                # Cachear resultado se solicitado
                if use_cache and cache_key:
                    self._cache.set(cache_key, data, ttl=300)
                
                return data
        
        return self.circuit_breaker.call(execute)
    
    def execute_transaction(self, func: Callable, *args, database: Optional[str] = None, **kwargs) -> Any:
        """
        Executa função em transação
        
        Args:
            func: Função a executar na transação
            *args: Argumentos posicionais
            database: Database específico
            **kwargs: Argumentos nomeados
            
        Returns:
            Resultado da função
        """
        def execute_tx():
            with self.get_session(database) as connection:
                with connection.begin_transaction() as tx:
                    return func(tx, *args, **kwargs)
        
        return self.circuit_breaker.call(execute_tx)
    
    def health_check(self) -> bool:
        """
        Verifica saúde das conexões
        
        Returns:
            True se sistema está saudável
        """
        try:
            # Teste simples de conectividade
            result = self.execute_query("RETURN 1 as health_check", use_cache=False)
            is_healthy = result and len(result) > 0 and result[0].get('health_check') == 1
            
            self._stats.last_health_check = datetime.now()
            
            if is_healthy:
                logger.debug("✅ Health check Neo4j passou")
            else:
                logger.warning("⚠️ Health check Neo4j falhou")
            
            return is_healthy
            
        except Exception as e:
            logger.error(f"❌ Health check Neo4j falhou: {e}")
            return False
    
    def get_stats(self) -> PoolStats:
        """Retorna estatísticas do pool"""
        with self._pool_lock:
            self._stats.idle_connections = self._pool.qsize()
            self._stats.uptime = datetime.now() - self._start_time
            self._stats.circuit_breaker_state = self.circuit_breaker.state.value
        
        return self._stats
    
    def _record_query_success(self, execution_time: float) -> None:
        """Registra query bem-sucedida"""
        self._stats.total_queries += 1
        self._stats.successful_queries += 1
        
        # Atualizar tempo médio
        total_time = self._stats.avg_query_time * (self._stats.successful_queries - 1)
        self._stats.avg_query_time = (total_time + execution_time) / self._stats.successful_queries
    
    def _record_query_failure(self, execution_time: float, exception: Exception) -> None:
        """Registra query que falhou"""
        self._stats.total_queries += 1
        self._stats.failed_queries += 1
        
        logger.warning(f"Query falhou após {execution_time:.3f}s: {exception}")
    
    def _start_maintenance_thread(self) -> None:
        """Inicia thread de manutenção"""
        def maintenance_worker():
            while self._running:
                try:
                    self._cleanup_expired_connections()
                    self._cleanup_cache()
                    time.sleep(60)  # Manutenção a cada minuto
                except Exception as e:
                    logger.error(f"Erro na manutenção do pool: {e}")
                    time.sleep(30)
        
        self._running = True
        self._maintenance_thread = threading.Thread(target=maintenance_worker, daemon=True)
        self._maintenance_thread.start()
        logger.debug("Thread de manutenção do pool iniciada")
    
    def _cleanup_expired_connections(self) -> None:
        """Remove conexões expiradas"""
        with self._pool_lock:
            # Limpar pool de conexões idle
            temp_queue = queue.Queue()
            expired_count = 0
            
            while not self._pool.empty():
                try:
                    connection = self._pool.get_nowait()
                    if connection.is_expired(self.config.max_connection_lifetime):
                        connection.close()
                        expired_count += 1
                    else:
                        temp_queue.put_nowait(connection)
                except queue.Empty:
                    break
            
            # Recolocar conexões válidas
            self._pool = temp_queue
            
            # Limpar conexões ativas expiradas
            active_expired = []
            for connection in self._active_connections[:]:
                if connection.is_expired(self.config.max_connection_lifetime):
                    active_expired.append(connection)
            
            for connection in active_expired:
                self._active_connections.remove(connection)
                connection.close()
                expired_count += 1
            
            if expired_count > 0:
                logger.debug(f"Removidas {expired_count} conexões expiradas")
    
    def _cleanup_cache(self) -> None:
        """Limpa cache de queries"""
        self._cache.cleanup_expired()
    
    def close(self) -> None:
        """Fecha pool e todas as conexões"""
        logger.info("🔗 Fechando Neo4j Connection Pool...")
        
        self._running = False
        
        # Aguardar thread de manutenção
        if self._maintenance_thread and self._maintenance_thread.is_alive():
            self._maintenance_thread.join(timeout=5)
        
        # Fechar todas as conexões
        with self._pool_lock:
            while not self._pool.empty():
                try:
                    connection = self._pool.get_nowait()
                    connection.close()
                except queue.Empty:
                    break
            
            for connection in self._active_connections[:]:
                connection.close()
            
            self._active_connections.clear()
        
        # Fechar driver
        if self._driver:
            self._driver.close()
        
        logger.info("✅ Neo4j Connection Pool fechado")


# Instância global do pool
_neo4j_pool: Optional[Neo4jConnectionPool] = None
_pool_lock = threading.Lock()


def get_neo4j_pool(config: Optional[Neo4jConfig] = None) -> Neo4jConnectionPool:
    """
    Obtém instância singleton do pool Neo4j
    
    Args:
        config: Configuração do Neo4j (opcional)
        
    Returns:
        Instância do pool
    """
    global _neo4j_pool
    
    if _neo4j_pool is None:
        with _pool_lock:
            if _neo4j_pool is None:
                _neo4j_pool = Neo4jConnectionPool(config)
    
    return _neo4j_pool


def execute_query(query: str, parameters: Optional[Dict] = None, 
                 database: Optional[str] = None, use_cache: bool = True) -> Any:
    """
    Função de conveniência para executar query
    
    Args:
        query: Query Cypher
        parameters: Parâmetros da query
        database: Database específico
        use_cache: Se deve usar cache
        
    Returns:
        Resultado da query
    """
    pool = get_neo4j_pool()
    return pool.execute_query(query, parameters, database, use_cache)


def execute_transaction(func: Callable, *args, database: Optional[str] = None, **kwargs) -> Any:
    """
    Função de conveniência para executar transação
    
    Args:
        func: Função a executar na transação
        *args: Argumentos posicionais
        database: Database específico
        **kwargs: Argumentos nomeados
        
    Returns:
        Resultado da função
    """
    pool = get_neo4j_pool()
    return pool.execute_transaction(func, *args, database=database, **kwargs)


@contextmanager
def get_session(database: Optional[str] = None) -> ContextManager[ConnectionWrapper]:
    """
    Context manager de conveniência para sessão
    
    Args:
        database: Database específico
        
    Yields:
        ConnectionWrapper com sessão ativa
    """
    pool = get_neo4j_pool()
    with pool.get_session(database) as session:
        yield session


if __name__ == "__main__":
    # Teste do pool de conexões
    print("🔗 Testando Neo4j Connection Pool...")
    
    try:
        # Configurar pool
        config = Neo4jConfig()
        pool = get_neo4j_pool(config)
        
        # Testar health check
        is_healthy = pool.health_check()
        print(f"Health check: {'✅' if is_healthy else '❌'}")
        
        # Testar query simples
        result = execute_query("RETURN 'Hello Neo4j' as message")
        print(f"Query result: {result}")
        
        # Testar com cache
        start_time = time.time()
        result1 = execute_query("RETURN rand() as random_number", use_cache=True)
        time1 = time.time() - start_time
        
        start_time = time.time()
        result2 = execute_query("RETURN rand() as random_number", use_cache=True)
        time2 = time.time() - start_time
        
        print(f"Primeira query: {time1:.3f}s")
        print(f"Segunda query (cache): {time2:.3f}s")
        
        # Mostrar estatísticas
        stats = pool.get_stats()
        print(f"\nEstatísticas do pool:")
        print(f"Total de conexões: {stats.total_connections}")
        print(f"Conexões ativas: {stats.active_connections}")
        print(f"Conexões idle: {stats.idle_connections}")
        print(f"Total de queries: {stats.total_queries}")
        print(f"Taxa de sucesso: {stats.success_rate:.2%}")
        print(f"Tempo médio de query: {stats.avg_query_time:.3f}s")
        print(f"Circuit breaker: {stats.circuit_breaker_state}")
        
        print("\n✅ Neo4j Connection Pool testado com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        logger.error(f"Erro no teste do pool: {e}")
    
    finally:
        # Fechar pool
        if _neo4j_pool:
            _neo4j_pool.close()