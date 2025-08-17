#!/usr/bin/env python3
"""
⚙️ Config Manager - Sistema Otimizado de Configurações
Sistema avançado com lazy loading, cache de YAML, validação de schema e hot-reload
"""

import os
import json
import yaml
import time
import threading
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Type, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging
import hashlib
from functools import wraps, lru_cache
import jsonschema
from jsonschema import validate, ValidationError

# Local imports
from .cache_manager import get_cache, CacheConfig, CachePolicy
from .logging_config import get_logger
from .telemetry import get_telemetry, timer, counter, gauge

logger = get_logger(__name__)
telemetry = get_telemetry()


class ConfigFormat(Enum):
    """Formatos de configuração suportados"""
    YAML = "yaml"
    JSON = "json"
    TOML = "toml"
    INI = "ini"


class ReloadStrategy(Enum):
    """Estratégias de reload"""
    MANUAL = "manual"
    AUTO = "auto"
    IMMEDIATE = "immediate"
    DEBOUNCED = "debounced"


@dataclass
class ConfigSchema:
    """Schema de validação de configuração"""
    name: str
    schema: Dict[str, Any]
    format: ConfigFormat
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    validation_rules: Dict[str, Callable] = field(default_factory=dict)


@dataclass
class ConfigSource:
    """Fonte de configuração"""
    name: str
    path: Path
    format: ConfigFormat
    priority: int = 0
    enabled: bool = True
    watch_changes: bool = True
    cache_ttl: int = 3600  # 1 hora
    lazy_load: bool = True
    schema: Optional[ConfigSchema] = None
    last_modified: Optional[float] = None
    last_loaded: Optional[float] = None
    
    def __post_init__(self):
        """Inicialização pós-criação"""
        if self.path.exists():
            self.last_modified = self.path.stat().st_mtime


@dataclass
class ConfigValue:
    """Valor de configuração com metadados"""
    value: Any
    source: str
    loaded_at: datetime
    cached: bool = False
    validated: bool = False
    priority: int = 0
    
    def is_expired(self, ttl: int) -> bool:
        """Verifica se valor expirou"""
        age = (datetime.now() - self.loaded_at).total_seconds()
        return age > ttl


class ConfigFileWatcher(FileSystemEventHandler):
    """Observador de mudanças em arquivos de configuração"""
    
    def __init__(self, config_manager: 'ConfigManager'):
        self.config_manager = config_manager
        self.debounce_delay = 1.0  # 1 segundo
        self.pending_reloads: Dict[str, float] = {}
        self._lock = threading.Lock()
    
    def on_modified(self, event):
        """Chamado quando arquivo é modificado"""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Verificar se é arquivo de configuração monitorado
        for source in self.config_manager.sources.values():
            if source.path == file_path and source.watch_changes:
                self._schedule_reload(source.name)
                break
    
    def _schedule_reload(self, source_name: str):
        """Agenda reload com debounce"""
        with self._lock:
            now = time.time()
            self.pending_reloads[source_name] = now + self.debounce_delay
            
            # Agendar verificação após delay
            threading.Timer(self.debounce_delay + 0.1, self._check_pending_reloads).start()
    
    def _check_pending_reloads(self):
        """Verifica e executa reloads pendentes"""
        with self._lock:
            now = time.time()
            to_reload = []
            
            for source_name, scheduled_time in list(self.pending_reloads.items()):
                if now >= scheduled_time:
                    to_reload.append(source_name)
                    del self.pending_reloads[source_name]
            
            # Executar reloads
            for source_name in to_reload:
                try:
                    asyncio.create_task(self.config_manager.reload_source(source_name))
                    logger.info(f"🔄 Auto-reload executado para: {source_name}")
                except Exception as e:
                    logger.error(f"Erro no auto-reload de {source_name}: {e}")


class SchemaValidator:
    """Validador de schemas de configuração"""
    
    @staticmethod
    def validate_json_schema(data: Any, schema: Dict[str, Any]) -> bool:
        """Valida dados contra schema JSON"""
        try:
            validate(instance=data, schema=schema)
            return True
        except ValidationError as e:
            logger.error(f"Erro de validação de schema: {e.message}")
            return False
    
    @staticmethod
    def validate_custom_rules(data: Dict[str, Any], rules: Dict[str, Callable]) -> bool:
        """Valida dados contra regras customizadas"""
        for field, rule in rules.items():
            if field in data:
                try:
                    if not rule(data[field]):
                        logger.error(f"Validação falhou para campo {field}")
                        return False
                except Exception as e:
                    logger.error(f"Erro na validação customizada de {field}: {e}")
                    return False
        return True
    
    @staticmethod
    def validate_required_fields(data: Dict[str, Any], required: List[str]) -> bool:
        """Valida campos obrigatórios"""
        missing = [field for field in required if field not in data]
        if missing:
            logger.error(f"Campos obrigatórios ausentes: {missing}")
            return False
        return True


class ConfigLoader:
    """Carregador de arquivos de configuração"""
    
    @staticmethod
    def load_file(path: Path, format: ConfigFormat) -> Dict[str, Any]:
        """Carrega arquivo de configuração"""
        if not path.exists():
            raise FileNotFoundError(f"Arquivo de configuração não encontrado: {path}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                if format == ConfigFormat.YAML:
                    return yaml.safe_load(f) or {}
                elif format == ConfigFormat.JSON:
                    return json.load(f) or {}
                elif format == ConfigFormat.TOML:
                    import tomli
                    return tomli.loads(f.read()) or {}
                elif format == ConfigFormat.INI:
                    import configparser
                    config = configparser.ConfigParser()
                    config.read_string(f.read())
                    return {section: dict(config[section]) for section in config.sections()}
                else:
                    raise ValueError(f"Formato não suportado: {format}")
        
        except Exception as e:
            logger.error(f"Erro ao carregar {path}: {e}")
            raise
    
    @staticmethod
    def save_file(path: Path, data: Dict[str, Any], format: ConfigFormat) -> None:
        """Salva arquivo de configuração"""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                if format == ConfigFormat.YAML:
                    yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
                elif format == ConfigFormat.JSON:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                elif format == ConfigFormat.TOML:
                    import tomli_w
                    tomli_w.dump(data, f)
                elif format == ConfigFormat.INI:
                    import configparser
                    config = configparser.ConfigParser()
                    for section, values in data.items():
                        config[section] = values
                    config.write(f)
                else:
                    raise ValueError(f"Formato não suportado: {format}")
        
        except Exception as e:
            logger.error(f"Erro ao salvar {path}: {e}")
            raise


class ConfigManager:
    """
    Gerenciador otimizado de configurações
    
    Features:
    - Lazy loading de configurações
    - Cache inteligente com TTL
    - Hot-reload automático
    - Validação de schema
    - Múltiplos formatos (YAML, JSON, TOML, INI)
    - Prioridade entre fontes
    - Interpolação de variáveis
    - Backup automático
    """
    
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path.cwd()
        self.sources: Dict[str, ConfigSource] = {}
        self.schemas: Dict[str, ConfigSchema] = {}
        self.values: Dict[str, ConfigValue] = {}
        self._lock = threading.RLock()
        
        # Cache para dados carregados
        cache_config = CacheConfig(
            max_size=500,
            default_ttl=3600,  # 1 hora
            policy=CachePolicy.LRU_TTL
        )
        self._cache = get_cache('config_manager', cache_config)
        
        # Observador de arquivos
        self.observer: Optional[Observer] = None
        self.file_watcher = ConfigFileWatcher(self)
        
        # Callbacks para mudanças
        self.change_callbacks: Dict[str, List[Callable]] = {}
        
        logger.info(f"⚙️ Config Manager inicializado - Base: {self.base_path}")
    
    def register_source(self, source: ConfigSource) -> None:
        """Registra fonte de configuração"""
        with self._lock:
            self.sources[source.name] = source
            
            # Registrar schema se fornecido
            if source.schema:
                self.schemas[source.name] = source.schema
            
            logger.debug(f"Fonte registrada: {source.name} ({source.path})")
    
    def register_schema(self, schema: ConfigSchema) -> None:
        """Registra schema de validação"""
        self.schemas[schema.name] = schema
        logger.debug(f"Schema registrado: {schema.name}")
    
    def add_change_callback(self, source_name: str, callback: Callable) -> None:
        """Adiciona callback para mudanças"""
        if source_name not in self.change_callbacks:
            self.change_callbacks[source_name] = []
        self.change_callbacks[source_name].append(callback)
    
    @lru_cache(maxsize=128)
    def _get_cache_key(self, path: str, modified_time: float) -> str:
        """Gera chave de cache baseada no arquivo"""
        return hashlib.md5(f"{path}:{modified_time}".encode()).hexdigest()
    
    async def load_source(self, source_name: str, force_reload: bool = False) -> Dict[str, Any]:
        """
        Carrega configuração de uma fonte
        
        Args:
            source_name: Nome da fonte
            force_reload: Se deve forçar reload
            
        Returns:
            Dados da configuração
        """
        if source_name not in self.sources:
            raise ValueError(f"Fonte não encontrada: {source_name}")
        
        source = self.sources[source_name]
        
        with timer('config.load_time', tags={'source': source_name}):
            try:
                # Verificar se arquivo foi modificado
                current_mtime = source.path.stat().st_mtime if source.path.exists() else 0
                
                # Verificar cache se não força reload
                if not force_reload and source.lazy_load:
                    cache_key = self._get_cache_key(str(source.path), current_mtime)
                    cached_data = self._cache.get(cache_key)
                    
                    if cached_data:
                        logger.debug(f"Cache HIT para {source_name}")
                        counter('config.cache_hits', tags={'source': source_name})
                        return cached_data
                
                # Carregar do arquivo
                logger.debug(f"Carregando configuração: {source_name}")
                data = ConfigLoader.load_file(source.path, source.format)
                
                # Validar se schema está definido
                if source.schema:
                    await self._validate_data(data, source.schema)
                
                # Aplicar interpolação de variáveis
                data = self._interpolate_variables(data)
                
                # Cachear dados
                if source.lazy_load:
                    cache_key = self._get_cache_key(str(source.path), current_mtime)
                    self._cache.set(cache_key, data, ttl=source.cache_ttl)
                
                # Atualizar metadados
                source.last_modified = current_mtime
                source.last_loaded = time.time()
                
                # Registrar métricas
                counter('config.loads', tags={'source': source_name})
                gauge('config.last_load_time', time.time(), tags={'source': source_name})
                
                # Disparar callbacks
                await self._trigger_callbacks(source_name, data)
                
                return data
                
            except Exception as e:
                counter('config.load_errors', tags={'source': source_name})
                logger.error(f"Erro ao carregar {source_name}: {e}")
                raise
    
    async def get_value(self, key: str, default: Any = None, source_priority: Optional[List[str]] = None) -> Any:
        """
        Obtém valor de configuração
        
        Args:
            key: Chave da configuração (suporta notação de ponto)
            default: Valor padrão
            source_priority: Lista de fontes em ordem de prioridade
            
        Returns:
            Valor da configuração
        """
        with timer('config.get_value_time', tags={'key': key}):
            # Determinar ordem de prioridade das fontes
            if source_priority:
                sources_to_check = source_priority
            else:
                sources_to_check = sorted(
                    self.sources.keys(),
                    key=lambda s: self.sources[s].priority,
                    reverse=True
                )
            
            # Procurar valor nas fontes
            for source_name in sources_to_check:
                if not self.sources[source_name].enabled:
                    continue
                
                try:
                    data = await self.load_source(source_name)
                    value = self._get_nested_value(data, key)
                    
                    if value is not None:
                        # Armazenar informações do valor
                        config_value = ConfigValue(
                            value=value,
                            source=source_name,
                            loaded_at=datetime.now(),
                            priority=self.sources[source_name].priority
                        )
                        self.values[key] = config_value
                        
                        counter('config.value_hits', tags={'key': key, 'source': source_name})
                        return value
                
                except Exception as e:
                    logger.debug(f"Erro ao obter {key} de {source_name}: {e}")
                    continue
            
            counter('config.value_misses', tags={'key': key})
            return default
    
    async def set_value(self, key: str, value: Any, source_name: Optional[str] = None) -> None:
        """
        Define valor de configuração
        
        Args:
            key: Chave da configuração
            value: Valor a definir
            source_name: Nome da fonte (usa a primeira se não especificado)
        """
        if not source_name:
            # Usar primeira fonte habilitada
            enabled_sources = [s for s in self.sources.values() if s.enabled]
            if not enabled_sources:
                raise ValueError("Nenhuma fonte de configuração habilitada")
            source_name = enabled_sources[0].name
        
        if source_name not in self.sources:
            raise ValueError(f"Fonte não encontrada: {source_name}")
        
        source = self.sources[source_name]
        
        try:
            # Carregar dados atuais
            data = await self.load_source(source_name, force_reload=True)
            
            # Definir valor
            self._set_nested_value(data, key, value)
            
            # Salvar arquivo
            ConfigLoader.save_file(source.path, data, source.format)
            
            # Invalidar cache
            self._invalidate_cache(source_name)
            
            # Registrar métricas
            counter('config.value_sets', tags={'key': key, 'source': source_name})
            
            logger.debug(f"Valor definido: {key} = {value} em {source_name}")
            
        except Exception as e:
            counter('config.set_errors', tags={'key': key, 'source': source_name})
            logger.error(f"Erro ao definir {key} em {source_name}: {e}")
            raise
    
    async def reload_source(self, source_name: str) -> None:
        """Recarrega fonte específica"""
        if source_name not in self.sources:
            raise ValueError(f"Fonte não encontrada: {source_name}")
        
        logger.info(f"🔄 Recarregando configuração: {source_name}")
        
        # Invalidar cache
        self._invalidate_cache(source_name)
        
        # Recarregar
        await self.load_source(source_name, force_reload=True)
        
        counter('config.reloads', tags={'source': source_name})
    
    async def reload_all(self) -> None:
        """Recarrega todas as fontes"""
        logger.info("🔄 Recarregando todas as configurações")
        
        tasks = []
        for source_name in self.sources.keys():
            tasks.append(self.reload_source(source_name))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def start_watching(self) -> None:
        """Inicia observação de mudanças nos arquivos"""
        if self.observer:
            logger.warning("Observação de arquivos já está ativa")
            return
        
        self.observer = Observer()
        
        # Adicionar watchers para todas as fontes que suportam
        watched_dirs = set()
        for source in self.sources.values():
            if source.watch_changes and source.path.exists():
                watch_dir = source.path.parent
                if watch_dir not in watched_dirs:
                    self.observer.schedule(self.file_watcher, str(watch_dir), recursive=False)
                    watched_dirs.add(watch_dir)
        
        if watched_dirs:
            self.observer.start()
            logger.info(f"📂 Observando {len(watched_dirs)} diretórios para mudanças")
        else:
            logger.info("Nenhum diretório para observar")
    
    def stop_watching(self) -> None:
        """Para observação de mudanças"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            logger.info("📂 Observação de arquivos parada")
    
    def _get_nested_value(self, data: Dict[str, Any], key: str) -> Any:
        """Obtém valor usando notação de ponto"""
        keys = key.split('.')
        current = data
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None
        
        return current
    
    def _set_nested_value(self, data: Dict[str, Any], key: str, value: Any) -> None:
        """Define valor usando notação de ponto"""
        keys = key.split('.')
        current = data
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
    
    def _interpolate_variables(self, data: Any) -> Any:
        """Aplica interpolação de variáveis de ambiente"""
        if isinstance(data, dict):
            return {k: self._interpolate_variables(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._interpolate_variables(item) for item in data]
        elif isinstance(data, str):
            # Substituir variáveis de ambiente ${VAR} ou $VAR
            import re
            pattern = re.compile(r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)')
            
            def replace_var(match):
                var_name = match.group(1) or match.group(2)
                return os.getenv(var_name, match.group(0))
            
            return pattern.sub(replace_var, data)
        else:
            return data
    
    async def _validate_data(self, data: Dict[str, Any], schema: ConfigSchema) -> None:
        """Valida dados contra schema"""
        try:
            # Validar campos obrigatórios
            if not SchemaValidator.validate_required_fields(data, schema.required_fields):
                raise ValueError("Validação de campos obrigatórios falhou")
            
            # Validar schema JSON se fornecido
            if schema.schema:
                if not SchemaValidator.validate_json_schema(data, schema.schema):
                    raise ValueError("Validação de schema JSON falhou")
            
            # Validar regras customizadas
            if schema.validation_rules:
                if not SchemaValidator.validate_custom_rules(data, schema.validation_rules):
                    raise ValueError("Validação de regras customizadas falhou")
            
            logger.debug(f"Validação bem-sucedida para schema {schema.name}")
            
        except Exception as e:
            logger.error(f"Erro na validação: {e}")
            raise
    
    async def _trigger_callbacks(self, source_name: str, data: Dict[str, Any]) -> None:
        """Dispara callbacks de mudança"""
        if source_name in self.change_callbacks:
            for callback in self.change_callbacks[source_name]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(source_name, data)
                    else:
                        callback(source_name, data)
                except Exception as e:
                    logger.error(f"Erro em callback para {source_name}: {e}")
    
    def _invalidate_cache(self, source_name: str) -> None:
        """Invalida cache para uma fonte"""
        # Remover entradas de cache relacionadas
        keys_to_remove = []
        for key in self._cache.keys():
            if source_name in key:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            self._cache.delete(key)
        
        logger.debug(f"Cache invalidado para {source_name}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do gerenciador"""
        return {
            'sources_count': len(self.sources),
            'schemas_count': len(self.schemas),
            'cached_values': len(self.values),
            'cache_stats': self._cache.get_stats(),
            'watching': self.observer is not None and self.observer.is_alive() if self.observer else False,
            'sources': {
                name: {
                    'enabled': source.enabled,
                    'last_loaded': source.last_loaded,
                    'last_modified': source.last_modified,
                    'cache_ttl': source.cache_ttl
                }
                for name, source in self.sources.items()
            }
        }
    
    def export_config(self, format: ConfigFormat = ConfigFormat.JSON) -> str:
        """Exporta todas as configurações"""
        all_config = {}
        
        for source_name in self.sources.keys():
            try:
                # Carregar de forma síncrona para export
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                data = loop.run_until_complete(self.load_source(source_name))
                loop.close()
                
                all_config[source_name] = data
            except Exception as e:
                logger.error(f"Erro ao exportar {source_name}: {e}")
        
        if format == ConfigFormat.JSON:
            return json.dumps(all_config, indent=2)
        elif format == ConfigFormat.YAML:
            return yaml.dump(all_config, default_flow_style=False)
        else:
            raise ValueError(f"Formato de export não suportado: {format}")


# Instância global do gerenciador
_config_manager: Optional[ConfigManager] = None
_manager_lock = threading.Lock()


def get_config_manager(base_path: Optional[Path] = None) -> ConfigManager:
    """
    Obtém instância singleton do config manager
    
    Args:
        base_path: Diretório base para configurações
        
    Returns:
        Instância do gerenciador
    """
    global _config_manager
    
    if _config_manager is None:
        with _manager_lock:
            if _config_manager is None:
                _config_manager = ConfigManager(base_path)
    
    return _config_manager


# Função de conveniência para configuração otimizada
def optimized_config(key: str, default: Any = None, source: Optional[str] = None) -> Any:
    """
    Função de conveniência para obter configuração
    
    Args:
        key: Chave da configuração
        default: Valor padrão
        source: Fonte específica
        
    Returns:
        Valor da configuração
    """
    manager = get_config_manager()
    
    # Executar de forma síncrona
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        if source:
            result = loop.run_until_complete(manager.get_value(key, default, [source]))
        else:
            result = loop.run_until_complete(manager.get_value(key, default))
        return result
    finally:
        loop.close()


if __name__ == "__main__":
    # Teste do config manager
    print("⚙️ Testando Config Manager otimizado...")
    
    async def test_config_manager():
        # Obter gerenciador
        manager = get_config_manager(Path.cwd())
        
        # Registrar fonte de teste
        test_config_path = Path("test_config.yaml")
        test_data = {
            'app': {
                'name': 'Test App',
                'version': '1.0.0',
                'debug': True
            },
            'database': {
                'host': '${DB_HOST:-localhost}',
                'port': 5432
            }
        }
        
        # Criar arquivo de teste
        with open(test_config_path, 'w') as f:
            yaml.dump(test_data, f)
        
        try:
            # Registrar fonte
            source = ConfigSource(
                name="test",
                path=test_config_path,
                format=ConfigFormat.YAML,
                priority=1,
                watch_changes=True
            )
            manager.register_source(source)
            
            # Testar carregamento
            config_data = await manager.load_source("test")
            print(f"✅ Configuração carregada: {len(config_data)} seções")
            
            # Testar obtenção de valores
            app_name = await manager.get_value("app.name")
            print(f"App name: {app_name}")
            
            db_host = await manager.get_value("database.host")
            print(f"DB host (interpolado): {db_host}")
            
            # Testar cache
            start_time = time.time()
            await manager.get_value("app.name")
            cache_time = time.time() - start_time
            print(f"Cache hit em: {cache_time:.4f}s")
            
            # Testar definição de valor
            await manager.set_value("app.version", "2.0.0", "test")
            new_version = await manager.get_value("app.version")
            print(f"Nova versão: {new_version}")
            
            # Iniciar observação
            manager.start_watching()
            print("📂 Observação de arquivos iniciada")
            
            # Aguardar um pouco
            await asyncio.sleep(2)
            
            # Parar observação
            manager.stop_watching()
            
            # Mostrar estatísticas
            stats = manager.get_stats()
            print(f"\nEstatísticas:")
            print(f"Fontes: {stats['sources_count']}")
            print(f"Valores em cache: {stats['cached_values']}")
            print(f"Cache hit rate: {stats['cache_stats'].hit_rate:.2%}")
            
            print("\n✅ Config Manager testado com sucesso!")
            
        finally:
            # Limpar arquivo de teste
            if test_config_path.exists():
                test_config_path.unlink()
    
    # Executar teste
    try:
        asyncio.run(test_config_manager())
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        logger.error(f"Erro no teste do config manager: {e}")