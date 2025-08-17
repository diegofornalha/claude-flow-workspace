#!/usr/bin/env python3
"""
💾 Cache Manager - Sistema de Caching Centralizado
Gerencia cache unificado para todo o sistema com suporte a TTL, LRU e persistência
"""

import os
import json
import time
import pickle
import hashlib
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import logging
from functools import wraps

# Setup logging
logger = logging.getLogger(__name__)

T = TypeVar('T')


class CachePolicy(Enum):
    """Políticas de cache disponíveis"""
    LRU = "lru"  # Least Recently Used
    TTL = "ttl"  # Time To Live
    LRU_TTL = "lru_ttl"  # Combinação de LRU e TTL
    FIFO = "fifo"  # First In First Out
    PERMANENT = "permanent"  # Cache permanente


@dataclass
class CacheConfig:
    """Configuração do cache"""
    max_size: int = 1000
    default_ttl: int = 3600  # 1 hora em segundos
    policy: CachePolicy = CachePolicy.LRU_TTL
    enable_persistence: bool = True
    persistence_file: Optional[Path] = None
    compression: bool = False
    stats_enabled: bool = True
    
    def __post_init__(self):
        """Configuração pós-inicialização"""
        if self.persistence_file is None:
            cache_dir = Path.cwd() / "cache"
            cache_dir.mkdir(exist_ok=True)
            self.persistence_file = cache_dir / "cache_data.pkl"


@dataclass
class CacheEntry:
    """Entrada individual do cache"""
    key: str
    value: Any
    created_at: float
    accessed_at: float
    expires_at: Optional[float] = None
    access_count: int = 0
    size_bytes: int = 0
    
    def __post_init__(self):
        """Calcula tamanho da entrada"""
        try:
            self.size_bytes = len(pickle.dumps(self.value))
        except Exception:
            self.size_bytes = 0
    
    def is_expired(self) -> bool:
        """Verifica se entrada expirou"""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def touch(self) -> None:
        """Atualiza timestamp de acesso"""
        self.accessed_at = time.time()
        self.access_count += 1


@dataclass
class CacheStats:
    """Estatísticas do cache"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    total_size_bytes: int = 0
    oldest_entry: Optional[float] = None
    newest_entry: Optional[float] = None
    
    @property
    def hit_rate(self) -> float:
        """Taxa de acerto do cache"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def miss_rate(self) -> float:
        """Taxa de erro do cache"""
        return 1.0 - self.hit_rate


class CacheManager(Generic[T]):
    """
    Gerenciador de cache unificado com múltiplas políticas
    
    Features:
    - Múltiplas políticas de cache (LRU, TTL, FIFO)
    - Persistência opcional
    - Thread-safe
    - Estatísticas detalhadas
    - Compressão opcional
    - Callbacks para eventos
    """
    
    def __init__(self, name: str, config: Optional[CacheConfig] = None):
        """
        Inicializa cache manager
        
        Args:
            name: Nome identificador do cache
            config: Configuração do cache
        """
        self.name = name
        self.config = config or CacheConfig()
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: OrderedDict = OrderedDict()
        self._lock = threading.RLock()
        self._stats = CacheStats()
        self._callbacks: Dict[str, List[Callable]] = {
            'hit': [],
            'miss': [],
            'evict': [],
            'set': [],
            'delete': []
        }
        
        # Carregar cache persistido
        if self.config.enable_persistence:
            self._load_from_disk()
        
        logger.info(f"💾 Cache '{name}' inicializado - Policy: {self.config.policy.value}, Max Size: {self.config.max_size}")
    
    def get(self, key: str, default: T = None) -> T:
        """
        Obtém valor do cache
        
        Args:
            key: Chave do cache
            default: Valor padrão se não encontrado
            
        Returns:
            Valor armazenado ou default
        """
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats.misses += 1
                self._trigger_callbacks('miss', key, None)
                logger.debug(f"Cache MISS: {self.name}/{key}")
                return default
            
            if entry.is_expired():
                self._remove_entry(key)
                self._stats.misses += 1
                self._trigger_callbacks('miss', key, None)
                logger.debug(f"Cache EXPIRED: {self.name}/{key}")
                return default
            
            # Atualizar acesso
            entry.touch()
            self._update_access_order(key)
            
            self._stats.hits += 1
            self._trigger_callbacks('hit', key, entry.value)
            logger.debug(f"Cache HIT: {self.name}/{key}")
            
            return entry.value
    
    def set(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        """
        Armazena valor no cache
        
        Args:
            key: Chave do cache
            value: Valor a armazenar
            ttl: Time to live em segundos (opcional)
        """
        with self._lock:
            now = time.time()
            
            # Calcular expiração
            expires_at = None
            if ttl is not None:
                expires_at = now + ttl
            elif self.config.policy in [CachePolicy.TTL, CachePolicy.LRU_TTL]:
                expires_at = now + self.config.default_ttl
            
            # Criar entrada
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                accessed_at=now,
                expires_at=expires_at
            )
            
            # Verificar se precisa fazer eviction
            if key not in self._cache and len(self._cache) >= self.config.max_size:
                self._evict()
            
            # Armazenar entrada
            self._cache[key] = entry
            self._update_access_order(key)
            self._update_stats()
            
            self._trigger_callbacks('set', key, value)
            logger.debug(f"Cache SET: {self.name}/{key} (TTL: {ttl})")
            
            # Persistir se habilitado
            if self.config.enable_persistence:
                self._save_to_disk()
    
    def delete(self, key: str) -> bool:
        """
        Remove entrada do cache
        
        Args:
            key: Chave a remover
            
        Returns:
            True se removido com sucesso
        """
        with self._lock:
            if key in self._cache:
                value = self._cache[key].value
                self._remove_entry(key)
                self._trigger_callbacks('delete', key, value)
                logger.debug(f"Cache DELETE: {self.name}/{key}")
                return True
            return False
    
    def clear(self) -> None:
        """Limpa todo o cache"""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self._stats = CacheStats()
            logger.info(f"Cache CLEAR: {self.name}")
    
    def has(self, key: str) -> bool:
        """Verifica se chave existe no cache"""
        with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired():
                return True
            elif entry and entry.is_expired():
                self._remove_entry(key)
            return False
    
    def keys(self) -> List[str]:
        """Retorna todas as chaves válidas"""
        with self._lock:
            valid_keys = []
            expired_keys = []
            
            for key, entry in self._cache.items():
                if entry.is_expired():
                    expired_keys.append(key)
                else:
                    valid_keys.append(key)
            
            # Limpar chaves expiradas
            for key in expired_keys:
                self._remove_entry(key)
            
            return valid_keys
    
    def values(self) -> List[T]:
        """Retorna todos os valores válidos"""
        with self._lock:
            return [self._cache[key].value for key in self.keys()]
    
    def items(self) -> List[tuple]:
        """Retorna todos os pares (chave, valor) válidos"""
        with self._lock:
            return [(key, self._cache[key].value) for key in self.keys()]
    
    def size(self) -> int:
        """Retorna número de entradas válidas"""
        return len(self.keys())
    
    def get_stats(self) -> CacheStats:
        """Retorna estatísticas do cache"""
        with self._lock:
            self._update_stats()
            return self._stats
    
    def cleanup_expired(self) -> int:
        """
        Remove entradas expiradas
        
        Returns:
            Número de entradas removidas
        """
        with self._lock:
            expired_keys = []
            
            for key, entry in self._cache.items():
                if entry.is_expired():
                    expired_keys.append(key)
            
            for key in expired_keys:
                self._remove_entry(key)
            
            if expired_keys:
                logger.info(f"Cache CLEANUP: {self.name} - Removidas {len(expired_keys)} entradas expiradas")
            
            return len(expired_keys)
    
    def add_callback(self, event: str, callback: Callable) -> None:
        """
        Adiciona callback para eventos do cache
        
        Args:
            event: Tipo de evento (hit, miss, evict, set, delete)
            callback: Função callback
        """
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def _evict(self) -> None:
        """Executa política de eviction"""
        if not self._cache:
            return
        
        key_to_evict = None
        
        if self.config.policy == CachePolicy.LRU or self.config.policy == CachePolicy.LRU_TTL:
            # Remove o menos recentemente usado
            key_to_evict = next(iter(self._access_order))
        
        elif self.config.policy == CachePolicy.FIFO:
            # Remove o mais antigo por criação
            oldest_time = float('inf')
            for k, entry in self._cache.items():
                if entry.created_at < oldest_time:
                    oldest_time = entry.created_at
                    key_to_evict = k
        
        elif self.config.policy == CachePolicy.TTL:
            # Remove o que expira primeiro
            earliest_expiry = float('inf')
            for k, entry in self._cache.items():
                if entry.expires_at and entry.expires_at < earliest_expiry:
                    earliest_expiry = entry.expires_at
                    key_to_evict = k
        
        if key_to_evict:
            evicted_value = self._cache[key_to_evict].value
            self._remove_entry(key_to_evict)
            self._stats.evictions += 1
            self._trigger_callbacks('evict', key_to_evict, evicted_value)
            logger.debug(f"Cache EVICT: {self.name}/{key_to_evict}")
    
    def _remove_entry(self, key: str) -> None:
        """Remove entrada do cache"""
        if key in self._cache:
            del self._cache[key]
        if key in self._access_order:
            del self._access_order[key]
    
    def _update_access_order(self, key: str) -> None:
        """Atualiza ordem de acesso para LRU"""
        if key in self._access_order:
            del self._access_order[key]
        self._access_order[key] = time.time()
    
    def _update_stats(self) -> None:
        """Atualiza estatísticas"""
        if not self._cache:
            return
        
        self._stats.size = len(self._cache)
        self._stats.total_size_bytes = sum(entry.size_bytes for entry in self._cache.values())
        
        creation_times = [entry.created_at for entry in self._cache.values()]
        if creation_times:
            self._stats.oldest_entry = min(creation_times)
            self._stats.newest_entry = max(creation_times)
    
    def _trigger_callbacks(self, event: str, key: str, value: Any) -> None:
        """Dispara callbacks para evento"""
        for callback in self._callbacks.get(event, []):
            try:
                callback(key, value)
            except Exception as e:
                logger.warning(f"Erro em callback {event}: {e}")
    
    def _save_to_disk(self) -> None:
        """Salva cache em disco"""
        try:
            if not self.config.persistence_file:
                return
            
            # Preparar dados para serialização
            cache_data = {
                'name': self.name,
                'config': self.config,
                'entries': {},
                'stats': self._stats,
                'saved_at': time.time()
            }
            
            # Serializar entradas válidas
            for key, entry in self._cache.items():
                if not entry.is_expired():
                    cache_data['entries'][key] = entry
            
            # Salvar com compressão opcional
            with open(self.config.persistence_file, 'wb') as f:
                if self.config.compression:
                    import gzip
                    pickle.dump(cache_data, gzip.GzipFile(fileobj=f))
                else:
                    pickle.dump(cache_data, f)
            
            logger.debug(f"Cache {self.name} salvo em disco: {len(cache_data['entries'])} entradas")
            
        except Exception as e:
            logger.error(f"Erro ao salvar cache {self.name}: {e}")
    
    def _load_from_disk(self) -> None:
        """Carrega cache do disco"""
        try:
            if not self.config.persistence_file or not self.config.persistence_file.exists():
                return
            
            with open(self.config.persistence_file, 'rb') as f:
                if self.config.compression:
                    import gzip
                    cache_data = pickle.load(gzip.GzipFile(fileobj=f))
                else:
                    cache_data = pickle.load(f)
            
            # Verificar se é o mesmo cache
            if cache_data.get('name') != self.name:
                return
            
            # Carregar entradas válidas
            now = time.time()
            loaded_count = 0
            
            for key, entry in cache_data.get('entries', {}).items():
                if not entry.is_expired():
                    self._cache[key] = entry
                    self._update_access_order(key)
                    loaded_count += 1
            
            # Carregar estatísticas
            if 'stats' in cache_data:
                self._stats = cache_data['stats']
            
            logger.info(f"Cache {self.name} carregado do disco: {loaded_count} entradas")
            
        except Exception as e:
            logger.warning(f"Erro ao carregar cache {self.name}: {e}")


class CacheRegistry:
    """Registry global para gerenciar múltiplos caches"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._caches: Dict[str, CacheManager] = {}
            self._default_config = CacheConfig()
            self._cleanup_thread = None
            self._running = False
            self._initialized = True
            
            # Iniciar thread de limpeza
            self._start_cleanup_thread()
    
    def get_cache(self, name: str, config: Optional[CacheConfig] = None) -> CacheManager:
        """
        Obtém ou cria cache com nome específico
        
        Args:
            name: Nome do cache
            config: Configuração do cache (opcional)
            
        Returns:
            Instância do cache
        """
        if name not in self._caches:
            cache_config = config or self._default_config
            cache_config.persistence_file = Path.cwd() / "cache" / f"{name}.pkl"
            self._caches[name] = CacheManager(name, cache_config)
            logger.info(f"Cache criado: {name}")
        
        return self._caches[name]
    
    def list_caches(self) -> List[str]:
        """Lista nomes de todos os caches"""
        return list(self._caches.keys())
    
    def clear_all(self) -> None:
        """Limpa todos os caches"""
        for cache in self._caches.values():
            cache.clear()
        logger.info("Todos os caches foram limpos")
    
    def get_global_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas globais de todos os caches"""
        stats = {
            'total_caches': len(self._caches),
            'caches': {}
        }
        
        total_hits = 0
        total_misses = 0
        total_size = 0
        
        for name, cache in self._caches.items():
            cache_stats = cache.get_stats()
            stats['caches'][name] = {
                'hits': cache_stats.hits,
                'misses': cache_stats.misses,
                'hit_rate': cache_stats.hit_rate,
                'size': cache_stats.size,
                'size_bytes': cache_stats.total_size_bytes
            }
            
            total_hits += cache_stats.hits
            total_misses += cache_stats.misses
            total_size += cache_stats.size
        
        stats['totals'] = {
            'hits': total_hits,
            'misses': total_misses,
            'hit_rate': total_hits / (total_hits + total_misses) if (total_hits + total_misses) > 0 else 0.0,
            'total_entries': total_size
        }
        
        return stats
    
    def cleanup_all_expired(self) -> Dict[str, int]:
        """Remove entradas expiradas de todos os caches"""
        results = {}
        for name, cache in self._caches.items():
            results[name] = cache.cleanup_expired()
        return results
    
    def _start_cleanup_thread(self) -> None:
        """Inicia thread de limpeza automática"""
        import threading
        
        def cleanup_worker():
            while self._running:
                try:
                    self.cleanup_all_expired()
                    time.sleep(300)  # Limpar a cada 5 minutos
                except Exception as e:
                    logger.error(f"Erro na limpeza automática: {e}")
                    time.sleep(60)
        
        self._running = True
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        logger.info("Thread de limpeza automática iniciada")
    
    def stop(self) -> None:
        """Para todos os caches e threads"""
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        
        # Salvar todos os caches
        for cache in self._caches.values():
            if cache.config.enable_persistence:
                cache._save_to_disk()
        
        logger.info("Cache registry parado")


# Instância global do registry
cache_registry = CacheRegistry()

# Funções de conveniência
def get_cache(name: str, config: Optional[CacheConfig] = None) -> CacheManager:
    """Função de conveniência para obter cache"""
    return cache_registry.get_cache(name, config)

def cached(cache_name: str, ttl: Optional[int] = None, key_func: Optional[Callable] = None):
    """
    Decorator para cache automático de funções
    
    Args:
        cache_name: Nome do cache a usar
        ttl: Time to live em segundos
        key_func: Função para gerar chave do cache
    """
    def decorator(func):
        cache = get_cache(cache_name)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Gerar chave do cache
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Usar hash dos argumentos como chave
                key_data = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
                cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Tentar obter do cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Executar função e cachear resultado
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator


# Caches pré-configurados para o sistema
def setup_system_caches():
    """Configura caches do sistema com configurações otimizadas"""
    
    # Cache de configurações - permanente com TTL longo
    config_cache_config = CacheConfig(
        max_size=100,
        default_ttl=3600,  # 1 hora
        policy=CachePolicy.LRU_TTL,
        enable_persistence=True
    )
    
    # Cache de conexões Neo4j - pequeno mas crítico
    neo4j_cache_config = CacheConfig(
        max_size=50,
        default_ttl=1800,  # 30 minutos
        policy=CachePolicy.LRU,
        enable_persistence=False  # Conexões não devem ser persistidas
    )
    
    # Cache de descoberta de serviços - TTL curto, alta rotatividade
    discovery_cache_config = CacheConfig(
        max_size=500,
        default_ttl=300,  # 5 minutos
        policy=CachePolicy.TTL,
        enable_persistence=True
    )
    
    # Cache de métricas - grande volume, TTL médio
    metrics_cache_config = CacheConfig(
        max_size=2000,
        default_ttl=600,  # 10 minutos
        policy=CachePolicy.LRU_TTL,
        enable_persistence=True
    )
    
    # Criar caches
    caches = {
        'config': get_cache('config', config_cache_config),
        'neo4j': get_cache('neo4j', neo4j_cache_config),
        'discovery': get_cache('discovery', discovery_cache_config),
        'metrics': get_cache('metrics', metrics_cache_config)
    }
    
    logger.info("Caches do sistema configurados:")
    for name, cache in caches.items():
        logger.info(f"  - {name}: {cache.config.policy.value}, max_size={cache.config.max_size}")
    
    return caches


if __name__ == "__main__":
    # Teste do sistema de cache
    print("💾 Testando sistema de cache...")
    
    # Configurar caches do sistema
    system_caches = setup_system_caches()
    
    # Testar cache básico
    cache = get_cache("test", CacheConfig(max_size=5, default_ttl=10))
    
    # Testar operações básicas
    cache.set("key1", "value1")
    cache.set("key2", {"data": "complex"})
    cache.set("key3", [1, 2, 3, 4, 5])
    
    print(f"Get key1: {cache.get('key1')}")
    print(f"Get key2: {cache.get('key2')}")
    print(f"Has key3: {cache.has('key3')}")
    
    # Testar decorator
    @cached("test_func", ttl=5)
    def expensive_function(x, y):
        time.sleep(0.1)  # Simular operação cara
        return x * y
    
    # Primeira chamada - deve ser lenta
    start = time.time()
    result1 = expensive_function(10, 20)
    time1 = time.time() - start
    
    # Segunda chamada - deve ser rápida (cache hit)
    start = time.time()
    result2 = expensive_function(10, 20)
    time2 = time.time() - start
    
    print(f"Primeira chamada: {result1} em {time1:.3f}s")
    print(f"Segunda chamada: {result2} em {time2:.3f}s")
    print(f"Speedup: {time1/time2:.1f}x")
    
    # Mostrar estatísticas
    stats = cache_registry.get_global_stats()
    print(f"\nEstatísticas globais:")
    print(f"Total de caches: {stats['total_caches']}")
    print(f"Hit rate global: {stats['totals']['hit_rate']:.2%}")
    print(f"Total de entradas: {stats['totals']['total_entries']}")
    
    print("\n✅ Sistema de cache testado com sucesso!")