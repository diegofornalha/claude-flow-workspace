#!/usr/bin/env python3
"""
🔍 Service Discovery System - Claude-20x REFATORADO
Sistema de descoberta automática de agentes A2A com:
- Configurações centralizadas
- Tratamento robusto de exceções
- Logging detalhado
- Retry logic com backoff exponencial
- Fallbacks para serviços indisponíveis
- Validações de entrada robustas
- Type hints completos
- Circuit breaker pattern
"""

import os
import json
import asyncio
import aiohttp
import socket
import time
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import psutil
import requests
from urllib.parse import urljoin
import logging
from functools import wraps

# Importar configurações centralizadas
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_config, Config

# Configurar logging com base nas configurações
config = get_config()
logging.basicConfig(
    level=getattr(logging, config.logger.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.paths.logs_dir / 'service-discovery.log')
    ]
)
logger = logging.getLogger(__name__)


# ========== EXCEÇÕES PERSONALIZADAS ==========

class ServiceDiscoveryError(Exception):
    """Exceção base para erros do Service Discovery"""
    pass


class AgentProbeError(ServiceDiscoveryError):
    """Erro ao fazer probe de um agente"""
    pass


class ConfigurationError(ServiceDiscoveryError):
    """Erro de configuração"""
    pass


class NetworkTimeoutError(ServiceDiscoveryError):
    """Erro de timeout de rede"""
    pass


class AgentUnreachableError(ServiceDiscoveryError):
    """Agente não alcançável"""
    pass


# ========== VALIDADORES ==========

class InputValidator:
    """Classe para validação de entradas"""
    
    @staticmethod
    def validate_host(host: str) -> str:
        """Valida host de entrada"""
        if not host or not isinstance(host, str):
            raise ValueError("Host deve ser uma string não vazia")
        
        host = host.strip()
        if not host:
            raise ValueError("Host não pode estar vazio")
        
        # Permitir apenas hosts seguros
        allowed_hosts = ['localhost', '127.0.0.1', '0.0.0.0']
        if host not in allowed_hosts and not host.startswith('192.168.') and not host.startswith('10.'):
            logger.warning(f"Host potencialmente inseguro: {host}")
        
        return host
    
    @staticmethod
    def validate_port(port: Union[int, str]) -> int:
        """Valida porta de entrada"""
        try:
            port_num = int(port)
        except (ValueError, TypeError):
            raise ValueError(f"Porta deve ser um número inteiro, recebido: {port}")
        
        if not (1 <= port_num <= 65535):
            raise ValueError(f"Porta deve estar entre 1 e 65535, recebido: {port_num}")
        
        return port_num
    
    @staticmethod
    def validate_url(url: str) -> str:
        """Valida URL de entrada"""
        if not url or not isinstance(url, str):
            raise ValueError("URL deve ser uma string não vazia")
        
        url = url.strip()
        if not url:
            raise ValueError("URL não pode estar vazia")
        
        if not (url.startswith('http://') or url.startswith('https://')):
            raise ValueError(f"URL deve começar com http:// ou https://, recebido: {url}")
        
        return url


# ========== CIRCUIT BREAKER ==========

class CircuitBreakerState(Enum):
    """Estados do Circuit Breaker"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Configuração do Circuit Breaker"""
    failure_threshold: int = 5
    recovery_timeout: int = 60
    expected_exception: tuple = (Exception,)


class CircuitBreaker:
    """Implementação do padrão Circuit Breaker para agentes problemáticos"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitBreakerState.CLOSED
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator para aplicar circuit breaker"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    logger.info("Circuit breaker mudou para HALF_OPEN")
                else:
                    raise AgentUnreachableError("Circuit breaker OPEN - agente indisponível")
            
            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except self.config.expected_exception as e:
                self._on_failure()
                raise
        
        return wrapper
    
    def _should_attempt_reset(self) -> bool:
        """Verifica se deve tentar resetar o circuit breaker"""
        if self.last_failure_time is None:
            return True
        
        return (datetime.now() - self.last_failure_time).total_seconds() >= self.config.recovery_timeout
    
    def _on_success(self) -> None:
        """Chamado quando operação é bem-sucedida"""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
    
    def _on_failure(self) -> None:
        """Chamado quando operação falha"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.warning(f"Circuit breaker ABERTO - {self.failure_count} falhas consecutivas")


# ========== RETRY LOGIC ==========

async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True
) -> Any:
    """
    Executa função com retry e backoff exponencial
    
    Args:
        func: Função assíncrona para executar
        max_retries: Número máximo de tentativas
        base_delay: Delay inicial em segundos
        max_delay: Delay máximo em segundos
        backoff_factor: Fator de multiplicação do delay
        jitter: Se deve adicionar variação aleatória
    
    Returns:
        Resultado da função
    
    Raises:
        Exception: Última exceção capturada após todas as tentativas
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            logger.debug(f"Tentativa {attempt + 1}/{max_retries + 1}")
            result = await func()
            if attempt > 0:
                logger.info(f"Sucesso na tentativa {attempt + 1}")
            return result
        
        except Exception as e:
            last_exception = e
            
            if attempt == max_retries:
                logger.error(f"Todas as {max_retries + 1} tentativas falharam. Última exceção: {e}")
                break
            
            # Calcular delay com backoff exponencial
            delay = min(base_delay * (backoff_factor ** attempt), max_delay)
            
            # Adicionar jitter para evitar thundering herd
            if jitter:
                delay *= (0.5 + random.random() * 0.5)
            
            logger.warning(f"Tentativa {attempt + 1} falhou: {e}. Aguardando {delay:.2f}s...")
            await asyncio.sleep(delay)
    
    raise last_exception


class AgentStatus(Enum):
    """Status possíveis dos agentes"""
    ONLINE = "online"
    OFFLINE = "offline"
    STARTING = "starting"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class AgentInfo:
    """
    Informações completas do agente descoberto
    
    Attributes:
        id: Identificador único do agente (formato: host:port)
        name: Nome amigável do agente
        type: Tipo do agente (a2a, web, analytics, debug, etc.)
        host: Endereço IP ou hostname do agente
        port: Porta de rede do agente
        url: URL base do agente
        status: Status atual do agente
        last_seen: Timestamp da última vez que o agente foi visto online
        capabilities: Lista de capacidades do agente
        metadata: Metadados adicionais do agente
        health_endpoint: URL do endpoint de health check
        card_endpoint: URL do endpoint de agent card
        version: Versão do agente (opcional)
        uptime: Tempo de atividade em segundos (opcional)
        circuit_breaker: Circuit breaker para este agente (opcional)
    """
    id: str
    name: str
    type: str
    host: str
    port: int
    url: str
    status: AgentStatus
    last_seen: datetime
    capabilities: List[str]
    metadata: Dict[str, Any]
    health_endpoint: str
    card_endpoint: str
    version: Optional[str] = None
    uptime: Optional[float] = None
    circuit_breaker: Optional[CircuitBreaker] = None
    
    def __post_init__(self) -> None:
        """Validação e inicialização pós-criação"""
        # Validar campos obrigatórios
        self.host = InputValidator.validate_host(self.host)
        self.port = InputValidator.validate_port(self.port)
        self.url = InputValidator.validate_url(self.url)
        
        # Inicializar circuit breaker se não foi fornecido
        if self.circuit_breaker is None:
            cb_config = CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=30,
                expected_exception=(AgentProbeError, NetworkTimeoutError, AgentUnreachableError)
            )
            self.circuit_breaker = CircuitBreaker(cb_config)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Converte AgentInfo para dicionário
        
        Returns:
            Dicionário com todas as informações do agente
        """
        try:
            return {
                **asdict(self),
                'status': self.status.value,
                'last_seen': self.last_seen.isoformat(),
                'uptime': self.uptime,
                'circuit_breaker_state': self.circuit_breaker.state.value if self.circuit_breaker else None
            }
        except Exception as e:
            logger.error(f"Erro ao converter AgentInfo para dict: {e}")
            # Fallback com dados mínimos
            return {
                'id': self.id,
                'name': self.name,
                'status': self.status.value,
                'error': str(e)
            }
    
    def is_healthy(self) -> bool:
        """
        Verifica se o agente está saudável
        
        Returns:
            True se o agente está online e o circuit breaker está fechado
        """
        return (
            self.status == AgentStatus.ONLINE and
            (self.circuit_breaker is None or self.circuit_breaker.state == CircuitBreakerState.CLOSED)
        )


class ServiceDiscovery:
    """
    🕵️ Sistema de Service Discovery robusto e configurável
    
    Funcionalidades implementadas:
    - Descoberta automática de agentes A2A
    - Health checking contínuo com circuit breaker
    - Registry centralizado com validação
    - Retry logic com backoff exponencial
    - Fallbacks para serviços indisponíveis
    - Logging detalhado para debug
    - Configurações centralizadas
    - Tratamento robusto de exceções
    """
    
    def __init__(self, config_override: Optional[Config] = None):
        """
        Inicializa o Service Discovery
        
        Args:
            config_override: Configuração customizada (opcional)
            
        Raises:
            ConfigurationError: Se configurações estão inválidas
        """
        try:
            logger.info("🔍 Inicializando Service Discovery System...")
            
            # Usar configuração fornecida ou carregar a padrão
            self.config = config_override or get_config()
            
            # Validar configurações
            self._validate_config()
            
            # Inicializar componentes
            self.registry: Dict[str, AgentInfo] = {}
            self.discovery_cache: Dict[str, Any] = {}
            self._last_discovery: Optional[float] = None
            
            # Thread de discovery automático
            self.running = True
            self.discovery_thread = threading.Thread(
                target=self._discovery_worker, 
                daemon=True,
                name="ServiceDiscoveryWorker"
            )
            
            logger.info(f"📁 Project root: {self.config.paths.project_root}")
            logger.info(f"🔍 Scan ranges: {self.config.discovery.scan_ranges}")
            logger.info(f"⏱️ Scan interval: {self.config.discovery.scan_interval}s")
            logger.info(f"🤖 Known agents: {list(self.config.agents.known_agents.keys())}")
            
            # Iniciar thread de discovery
            self.discovery_thread.start()
            logger.info("✅ Service Discovery inicializado com sucesso")
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar Service Discovery: {e}")
            raise ConfigurationError(f"Falha na inicialização: {e}") from e
    
    def _validate_config(self) -> None:
        """
        Valida as configurações do sistema
        
        Raises:
            ConfigurationError: Se alguma configuração está inválida
        """
        try:
            # Validar paths
            if not self.config.paths.project_root.exists():
                logger.warning(f"⚠️ Project root não existe: {self.config.paths.project_root}")
            
            # Validar configurações de discovery
            if self.config.discovery.scan_interval <= 0:
                raise ConfigurationError(f"Scan interval deve ser positivo: {self.config.discovery.scan_interval}")
            
            if self.config.discovery.cache_ttl <= 0:
                raise ConfigurationError(f"Cache TTL deve ser positivo: {self.config.discovery.cache_ttl}")
            
            if not self.config.discovery.scan_ranges:
                raise ConfigurationError("Scan ranges não pode estar vazio")
            
            # Validar agentes conhecidos
            for agent_name, agent_config in self.config.agents.known_agents.items():
                if not agent_config.get('ports'):
                    raise ConfigurationError(f"Agent {agent_name} deve ter portas definidas")
                
                for port in agent_config['ports']:
                    InputValidator.validate_port(port)
            
            logger.debug("✅ Configurações validadas com sucesso")
            
        except Exception as e:
            logger.error(f"❌ Erro na validação das configurações: {e}")
            raise ConfigurationError(f"Configurações inválidas: {e}") from e
    
    async def discover_agents(self, force_scan: bool = False) -> List[AgentInfo]:
        """
        Descobre todos os agentes ativos no sistema
        
        Args:
            force_scan: Se True, força nova descoberta ignorando cache
            
        Returns:
            Lista de agentes descobertos
            
        Raises:
            ServiceDiscoveryError: Se descoberta falhar completamente
        """
        try:
            logger.info("🔍 Iniciando descoberta de agentes...")
            start_time = time.time()
            
            # Verificar cache se não é force scan
            if not force_scan and self._is_cache_valid():
                cached_agents = list(self.registry.values())
                logger.debug(f"📋 Usando cache: {len(cached_agents)} agentes")
                return cached_agents
            
            discovered: List[AgentInfo] = []
            
            # 1. Descoberta por agentes conhecidos (alta prioridade)
            try:
                known_agents = await self._discover_known_agents()
                discovered.extend(known_agents)
                logger.info(f"🎯 Descobertos {len(known_agents)} agentes conhecidos")
            except Exception as e:
                logger.warning(f"⚠️ Erro na descoberta de agentes conhecidos: {e}")
            
            # 2. Descoberta por scan de rede (média prioridade)
            try:
                scanned_agents = await self._discover_by_scan()
                discovered.extend(scanned_agents)
                logger.info(f"🔍 Descobertos {len(scanned_agents)} agentes por scan")
            except Exception as e:
                logger.warning(f"⚠️ Erro no scan de rede: {e}")
            
            # 3. Descoberta por arquivos de configuração (baixa prioridade)
            try:
                config_agents = await self._discover_from_configs()
                discovered.extend(config_agents)
                logger.info(f"📋 Descobertos {len(config_agents)} agentes por config")
            except Exception as e:
                logger.warning(f"⚠️ Erro na descoberta por config: {e}")
            
            # Deduplizar agentes
            unique_agents = self._deduplicate_agents(discovered)
            
            # Atualizar registry com validação
            await self._update_registry(unique_agents)
            
            # Limpar agentes offline
            await self._cleanup_offline_agents()
            
            # Atualizar cache
            self._last_discovery = time.time()
            
            discovery_time = time.time() - start_time
            logger.info(f"✅ Descoberta concluída: {len(unique_agents)} agentes únicos em {discovery_time:.2f}s")
            
            return unique_agents
            
        except Exception as e:
            logger.error(f"❌ Erro na descoberta de agentes: {e}")
            # Fallback: retornar agentes conhecidos do registry
            fallback_agents = self._get_fallback_agents()
            logger.warning(f"🆘 Usando fallback: {len(fallback_agents)} agentes")
            return fallback_agents
    
    def _get_fallback_agents(self) -> List[AgentInfo]:
        """
        Retorna agentes conhecidos como fallback
        
        Returns:
            Lista de agentes em fallback
        """
        try:
            # Retornar agentes online do registry
            fallback = [agent for agent in self.registry.values() 
                       if agent.status != AgentStatus.OFFLINE]
            
            if not fallback:
                # Se não há agentes no registry, criar agentes mock dos conhecidos
                for agent_name, agent_config in self.config.agents.known_agents.items():
                    for port in agent_config['ports']:
                        try:
                            fallback_agent = AgentInfo(
                                id=f"localhost:{port}",
                                name=agent_name,
                                type=agent_config['type'],
                                host="localhost",
                                port=port,
                                url=f"http://localhost:{port}",
                                status=AgentStatus.UNKNOWN,
                                last_seen=datetime.now(),
                                capabilities=[],
                                metadata={"fallback": True},
                                health_endpoint=f"http://localhost:{port}/health",
                                card_endpoint=f"http://localhost:{port}/agent/card"
                            )
                            fallback.append(fallback_agent)
                        except Exception as e:
                            logger.debug(f"Erro ao criar fallback para {agent_name}: {e}")
            
            return fallback
            
        except Exception as e:
            logger.error(f"Erro ao gerar fallback agents: {e}")
            return []
    
    def _deduplicate_agents(self, agents: List[AgentInfo]) -> List[AgentInfo]:
        """
        Remove agentes duplicados baseado no ID
        
        Args:
            agents: Lista de agentes para deduplificar
            
        Returns:
            Lista de agentes únicos
        """
        seen_ids = set()
        unique_agents = []
        
        for agent in agents:
            if agent.id not in seen_ids:
                unique_agents.append(agent)
                seen_ids.add(agent.id)
            else:
                logger.debug(f"Agente duplicado removido: {agent.id}")
        
        return unique_agents
    
    async def _update_registry(self, agents: List[AgentInfo]) -> None:
        """
        Atualiza o registry com novos agentes
        
        Args:
            agents: Lista de agentes para atualizar
        """
        try:
            for agent in agents:
                # Validar agente antes de adicionar
                if self._validate_agent(agent):
                    self.registry[agent.id] = agent
                    logger.debug(f"Agente adicionado ao registry: {agent.id}")
                else:
                    logger.warning(f"Agente inválido não adicionado: {agent.id}")
        except Exception as e:
            logger.error(f"Erro ao atualizar registry: {e}")
    
    def _validate_agent(self, agent: AgentInfo) -> bool:
        """
        Valida um agente antes de adicionar ao registry
        
        Args:
            agent: Agente para validar
            
        Returns:
            True se agente é válido
        """
        try:
            # Validações básicas
            if not agent.id or not agent.name or not agent.host:
                return False
            
            if not (1 <= agent.port <= 65535):
                return False
            
            if not agent.url.startswith(('http://', 'https://')):
                return False
            
            return True
            
        except Exception as e:
            logger.debug(f"Erro na validação do agente: {e}")
            return False
    
    def _is_cache_valid(self) -> bool:
        """
        Verifica se cache ainda é válido
        
        Returns:
            True se cache é válido
        """
        if self._last_discovery is None:
            return False
        
        cache_age = time.time() - self._last_discovery
        return cache_age < self.config.discovery.cache_ttl
    
    async def _discover_known_agents(self) -> List[AgentInfo]:
        """
        Descobre agentes conhecidos definidos na configuração
        
        Returns:
            Lista de agentes conhecidos descobertos
        """
        discovered = []
        
        for agent_name, agent_config in self.config.agents.known_agents.items():
            for port in agent_config["ports"]:
                try:
                    # Criar função para retry
                    async def probe_known_agent():
                        return await self._probe_agent("localhost", port, agent_name, agent_config["type"])
                    
                    # Usar retry com backoff
                    agent = await retry_with_backoff(
                        probe_known_agent,
                        max_retries=2,
                        base_delay=0.5
                    )
                    
                    if agent:
                        discovered.append(agent)
                        logger.debug(f"✅ Agente conhecido descoberto: {agent_name}:{port}")
                    
                except Exception as e:
                    logger.debug(f"❌ Falha ao probar agente conhecido {agent_name}:{port}: {e}")
                    # Continuar com próximo agente
                    continue
        
        return discovered
    
    async def _discover_by_scan(self) -> List[AgentInfo]:
        """
        Descobre agentes fazendo scan das faixas de portas configuradas
        
        Returns:
            Lista de agentes descobertos por scan
        """
        scan_tasks = []
        
        # Criar tasks de scan para todas as combinações host:porta
        for host, port_range in self.config.discovery.scan_ranges:
            try:
                validated_host = InputValidator.validate_host(host)
                
                if isinstance(port_range, range):
                    for port in port_range:
                        scan_tasks.append(self._create_scan_task(validated_host, port))
                else:
                    for port in port_range:
                        scan_tasks.append(self._create_scan_task(validated_host, port))
                        
            except ValueError as e:
                logger.warning(f"⚠️ Host inválido no scan: {host} - {e}")
                continue
        
        # Executar scans em paralelo com semáforo para controlar concorrência
        semaphore = asyncio.Semaphore(self.config.discovery.max_concurrent)
        
        async def limited_scan(task):
            async with semaphore:
                return await task
        
        logger.debug(f"🔍 Executando {len(scan_tasks)} scans em paralelo...")
        results = await asyncio.gather(
            *[limited_scan(task) for task in scan_tasks], 
            return_exceptions=True
        )
        
        # Filtrar resultados válidos
        discovered = []
        for result in results:
            if isinstance(result, AgentInfo):
                discovered.append(result)
            elif isinstance(result, Exception):
                logger.debug(f"Scan falhou: {result}")
        
        return discovered
    
    async def _create_scan_task(self, host: str, port: int) -> Optional[AgentInfo]:
        """
        Cria task de scan para um host:porta específico
        
        Args:
            host: Host para scan
            port: Porta para scan
            
        Returns:
            AgentInfo se agente encontrado, None caso contrário
        """
        try:
            # Usar retry apenas para operações críticas
            async def scan_single_port():
                return await self._probe_agent(host, port)
            
            return await retry_with_backoff(
                scan_single_port,
                max_retries=1,  # Scan deve ser rápido
                base_delay=0.1
            )
            
        except Exception:
            # Scan failures são esperados - não logar como erro
            return None
    
    async def _probe_agent(
        self, 
        host: str, 
        port: int, 
        expected_name: Optional[str] = None, 
        expected_type: Optional[str] = None
    ) -> Optional[AgentInfo]:
        """
        Testa se há um agente em host:port específico com validação robusta
        
        Args:
            host: Host para testar
            port: Porta para testar
            expected_name: Nome esperado do agente (opcional)
            expected_type: Tipo esperado do agente (opcional)
            
        Returns:
            AgentInfo se agente encontrado, None caso contrário
            
        Raises:
            AgentProbeError: Se houver erro crítico no probe
        """
        try:
            # Validar entradas
            validated_host = InputValidator.validate_host(host)
            validated_port = InputValidator.validate_port(port)
            
            logger.debug(f"🔎 Probando agente em {validated_host}:{validated_port}")
            
            # Verificar se porta está aberta primeiro (mais rápido)
            if not await self._is_port_open_async(validated_host, validated_port):
                logger.debug(f"❌ Porta {validated_host}:{validated_port} não está aberta")
                return None
            
            base_url = f"http://{validated_host}:{validated_port}"
            
            # Tentar endpoints A2A primeiro (agentes especializados)
            try:
                agent_info = await self._probe_a2a_agent(base_url, expected_name, expected_type)
                if agent_info:
                    logger.debug(f"✅ Agente A2A encontrado: {agent_info.name}")
                    return agent_info
            except NetworkTimeoutError:
                logger.debug(f"⏰ Timeout no probe A2A para {base_url}")
            except AgentProbeError as e:
                logger.debug(f"❌ Erro no probe A2A para {base_url}: {e}")
            
            # Tentar endpoints web como fallback
            try:
                agent_info = await self._probe_web_service(base_url, expected_name, expected_type)
                if agent_info:
                    logger.debug(f"✅ Serviço web encontrado: {agent_info.name}")
                    return agent_info
            except NetworkTimeoutError:
                logger.debug(f"⏰ Timeout no probe web para {base_url}")
            except AgentProbeError as e:
                logger.debug(f"❌ Erro no probe web para {base_url}: {e}")
            
            logger.debug(f"❌ Nenhum agente encontrado em {validated_host}:{validated_port}")
            return None
            
        except (ValueError, ConfigurationError) as e:
            logger.warning(f"⚠️ Erro de validação ao probar {host}:{port}: {e}")
            return None
        except Exception as e:
            logger.debug(f"❌ Erro inesperado ao probar {host}:{port}: {e}")
            # Para scan rápido, não propagar erro
            return None
    
    async def _is_port_open_async(self, host: str, port: int, timeout: float = 1.0) -> bool:
        """
        Verifica se porta está aberta de forma assíncrona
        
        Args:
            host: Host para testar
            port: Porta para testar
            timeout: Timeout em segundos
            
        Returns:
            True se porta está aberta
        """
        try:
            future = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(future, timeout=timeout)
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False
    
    async def _probe_a2a_agent(
        self, 
        base_url: str, 
        expected_name: Optional[str] = None,
        expected_type: Optional[str] = None
    ) -> Optional[AgentInfo]:
        """
        Verifica se é um agente A2A válido testando endpoints específicos
        
        Args:
            base_url: URL base do agente
            expected_name: Nome esperado (opcional)
            expected_type: Tipo esperado (opcional)
            
        Returns:
            AgentInfo se agente A2A válido encontrado
            
        Raises:
            AgentProbeError: Se houver erro crítico
            NetworkTimeoutError: Se timeout ocorrer
        """
        try:
            # Validar URL
            validated_url = InputValidator.validate_url(base_url)
            
            # Timeout configurável baseado nas configurações
            timeout_seconds = self.config.performance.request_timeout / 1000  # ms para s
            timeout = aiohttp.ClientTimeout(total=timeout_seconds)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Endpoints A2A padrão (em ordem de prioridade)
                card_endpoints = [
                    "/agent/card",
                    "/.well-known/agent.json", 
                    "/agent",
                    "/a2a/info",
                    "/api/agent"
                ]
                
                for endpoint in card_endpoints:
                    try:
                        endpoint_url = urljoin(validated_url, endpoint)
                        logger.debug(f"🔍 Testando endpoint A2A: {endpoint_url}")
                        
                        async with session.get(endpoint_url) as response:
                            if response.status == 200:
                                try:
                                    card_data = await response.json()
                                    logger.debug(f"✅ Agent card encontrado em {endpoint}")
                                    return self._create_agent_from_card(
                                        validated_url, card_data, expected_name, expected_type
                                    )
                                except json.JSONDecodeError as e:
                                    logger.debug(f"❌ JSON inválido em {endpoint}: {e}")
                                    continue
                            elif response.status == 404:
                                logger.debug(f"❌ Endpoint {endpoint} não encontrado")
                                continue
                            else:
                                logger.debug(f"❌ Status {response.status} em {endpoint}")
                                continue
                                
                    except asyncio.TimeoutError:
                        logger.debug(f"⏰ Timeout no endpoint {endpoint}")
                        raise NetworkTimeoutError(f"Timeout ao acessar {endpoint}")
                    except aiohttp.ClientError as e:
                        logger.debug(f"❌ Erro de cliente em {endpoint}: {e}")
                        continue
                    except Exception as e:
                        logger.debug(f"❌ Erro inesperado em {endpoint}: {e}")
                        continue
                        
        except NetworkTimeoutError:
            raise  # Re-propagar timeout
        except Exception as e:
            logger.debug(f"❌ Erro geral no probe A2A {base_url}: {e}")
            raise AgentProbeError(f"Falha ao probar agente A2A: {e}") from e
        
        return None
    
    async def _probe_web_service(
        self, 
        base_url: str,
        expected_name: Optional[str] = None,
        expected_type: Optional[str] = None
    ) -> Optional[AgentInfo]:
        """
        Verifica se é um serviço web válido
        
        Args:
            base_url: URL base do serviço
            expected_name: Nome esperado (opcional)
            expected_type: Tipo esperado (opcional)
            
        Returns:
            AgentInfo se serviço web válido encontrado
            
        Raises:
            AgentProbeError: Se houver erro crítico
            NetworkTimeoutError: Se timeout ocorrer
        """
        try:
            validated_url = InputValidator.validate_url(base_url)
            
            timeout_seconds = self.config.performance.request_timeout / 1000
            timeout = aiohttp.ClientTimeout(total=timeout_seconds)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Endpoints web comuns
                health_endpoints = ["/health", "/status", "/ping", "/api/health", "/"]
                
                for endpoint in health_endpoints:
                    try:
                        endpoint_url = urljoin(validated_url, endpoint)
                        logger.debug(f"🌐 Testando endpoint web: {endpoint_url}")
                        
                        async with session.get(endpoint_url) as response:
                            if 200 <= response.status < 400:
                                content = await response.text()
                                logger.debug(f"✅ Serviço web encontrado em {endpoint}")
                                return self._create_web_service_info(
                                    validated_url, content, expected_name, expected_type
                                )
                    except asyncio.TimeoutError:
                        logger.debug(f"⏰ Timeout no endpoint {endpoint}")
                        raise NetworkTimeoutError(f"Timeout ao acessar {endpoint}")
                    except aiohttp.ClientError as e:
                        logger.debug(f"❌ Erro de cliente em {endpoint}: {e}")
                        continue
                    except Exception as e:
                        logger.debug(f"❌ Erro inesperado em {endpoint}: {e}")
                        continue
                        
        except NetworkTimeoutError:
            raise
        except Exception as e:
            logger.debug(f"❌ Erro geral no probe web {base_url}: {e}")
            raise AgentProbeError(f"Falha ao probar serviço web: {e}") from e
        
        return None
    
    def _create_agent_from_card(
        self, 
        base_url: str, 
        card_data: Dict[str, Any],
        expected_name: Optional[str] = None,
        expected_type: Optional[str] = None
    ) -> AgentInfo:
        """
        Cria AgentInfo a partir de agent card A2A
        
        Args:
            base_url: URL base do agente
            card_data: Dados do agent card
            expected_name: Nome esperado (opcional)
            expected_type: Tipo esperado (opcional)
            
        Returns:
            AgentInfo criado a partir do card
        """
        try:
            host, port = self._parse_url(base_url)
            agent_id = f"{host}:{port}"
            
            return AgentInfo(
                id=agent_id,
                name=card_data.get('name', expected_name or f"agent-{port}"),
                type=expected_type or card_data.get('type', 'a2a'),
                host=host,
                port=port,
                url=base_url,
                status=AgentStatus.ONLINE,
                last_seen=datetime.now(),
                capabilities=card_data.get('capabilities', []),
                metadata=card_data,
                health_endpoint=urljoin(base_url, "/health"),
                card_endpoint=urljoin(base_url, "/agent/card"),
                version=card_data.get('version')
            )
        except Exception as e:
            logger.error(f"Erro ao criar agente a partir do card: {e}")
            raise AgentProbeError(f"Falha ao criar agente do card: {e}") from e
    
    def _create_web_service_info(
        self, 
        base_url: str, 
        content: str,
        expected_name: Optional[str] = None,
        expected_type: Optional[str] = None
    ) -> AgentInfo:
        """
        Cria AgentInfo para serviço web
        
        Args:
            base_url: URL base do serviço
            content: Conteúdo da resposta
            expected_name: Nome esperado (opcional)
            expected_type: Tipo esperado (opcional)
            
        Returns:
            AgentInfo para o serviço web
        """
        try:
            host, port = self._parse_url(base_url)
            agent_id = f"{host}:{port}"
            
            # Tentar extrair informações do conteúdo
            service_name = expected_name or self._detect_service_name(content, port)
            service_type = expected_type or self._detect_service_type(content, port)
            
            return AgentInfo(
                id=agent_id,
                name=service_name,
                type=service_type,
                host=host,
                port=port,
                url=base_url,
                status=AgentStatus.ONLINE,
                last_seen=datetime.now(),
                capabilities=self._detect_capabilities(content),
                metadata={"content_preview": content[:200], "web_service": True},
                health_endpoint=urljoin(base_url, "/health"),
                card_endpoint=urljoin(base_url, "/"),
            )
        except Exception as e:
            logger.error(f"Erro ao criar info do serviço web: {e}")
            raise AgentProbeError(f"Falha ao criar info do serviço web: {e}") from e
    
    def _detect_service_name(self, content: str, port: int) -> str:
        """
        Detecta nome do serviço baseado no conteúdo
        
        Args:
            content: Conteúdo da resposta
            port: Porta do serviço
            
        Returns:
            Nome detectado do serviço
        """
        content_lower = content.lower()
        
        # Padrões conhecidos
        name_patterns = {
            "a2a inspector": ["a2a inspector", "inspector"],
            "Analytics Service": ["analytics", "metrics", "monitoring"],
            "Claude Service": ["claude", "anthropic"],
            "Web UI": ["ui", "interface", "dashboard"],
            "API Gateway": ["gateway", "api"],
            "Health Check": ["health", "status"]
        }
        
        for service_name, keywords in name_patterns.items():
            if any(keyword in content_lower for keyword in keywords):
                return service_name
        
        # Fallback baseado na porta
        port_names = {
            12000: "Main UI",
            5000: "Analytics",
            5001: "A2A Inspector",
            9999: "HelloWorld Agent",
            3002: "Marvin Agent",
            3003: "Gemini Agent"
        }
        
        return port_names.get(port, f"Service-{port}")
    
    def _detect_service_type(self, content: str, port: int) -> str:
        """
        Detecta tipo do serviço
        
        Args:
            content: Conteúdo da resposta
            port: Porta do serviço
            
        Returns:
            Tipo detectado do serviço
        """
        content_lower = content.lower()
        
        # Padrões de tipo
        type_patterns = {
            "debug": ["inspector", "debug", "console"],
            "analytics": ["analytics", "metrics", "monitoring"],
            "api": ["api", "rest", "graphql"],
            "web": ["html", "css", "javascript", "react", "vue"],
            "a2a": ["agent", "a2a", "autonomous"]
        }
        
        for service_type, keywords in type_patterns.items():
            if any(keyword in content_lower for keyword in keywords):
                return service_type
        
        # Fallback baseado na porta
        if port == 12000:
            return "web"
        elif port in [5000]:
            return "analytics"
        elif port in [5001]:
            return "debug"
        elif port in [9999, 3002, 3003]:
            return "a2a"
        
        return "service"
    
    def _detect_capabilities(self, content: str) -> List[str]:
        """
        Detecta capacidades do serviço
        
        Args:
            content: Conteúdo da resposta
            
        Returns:
            Lista de capacidades detectadas
        """
        capabilities = []
        content_lower = content.lower()
        
        capability_keywords = {
            "rest": ["api", "rest", "endpoint"],
            "websocket": ["websocket", "ws", "socket"],
            "debug": ["debug", "inspector", "console"],
            "analytics": ["analytics", "metrics", "monitoring"],
            "ui": ["ui", "interface", "dashboard"],
            "chat": ["chat", "conversation", "message"],
            "health": ["health", "status", "ping"],
            "auth": ["auth", "login", "token"],
            "database": ["database", "db", "storage"]
        }
        
        for capability, keywords in capability_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                capabilities.append(capability)
        
        return capabilities if capabilities else ["unknown"]
    
    def _parse_url(self, url: str) -> Tuple[str, int]:
        """
        Extrai host e porta da URL
        
        Args:
            url: URL para parsear
            
        Returns:
            Tuple (host, port)
        """
        try:
            # Remover protocolo
            if "://" in url:
                url = url.split("://")[1]
            
            # Separar host e porta
            if ":" in url:
                host, port_str = url.split(":")
                # Remover path se existir
                if "/" in port_str:
                    port_str = port_str.split("/")[0]
                return host, int(port_str)
            else:
                return url, 80
        except Exception as e:
            logger.error(f"Erro ao parsear URL {url}: {e}")
            return "localhost", 80
    
    async def _discover_from_configs(self) -> List[AgentInfo]:
        """
        Descobre agentes através de arquivos de configuração
        
        Returns:
            Lista de agentes descobertos por config
        """
        agents = []
        
        try:
            # Buscar por arquivos a2a-config.json
            config_files = list(self.config.paths.project_root.rglob("a2a-config.json"))
            
            for config_file in config_files:
                try:
                    with open(config_file, 'r') as f:
                        config_data = json.load(f)
                    
                    # Extrair informações do config
                    agent_info = self._create_agent_from_config(config_data, config_file)
                    if agent_info:
                        agents.append(agent_info)
                        logger.debug(f"Agente descoberto por config: {config_file}")
                        
                except Exception as e:
                    logger.debug(f"Erro ao ler config {config_file}: {e}")
        
        except Exception as e:
            logger.warning(f"Erro na descoberta por configs: {e}")
        
        return agents
    
    def _create_agent_from_config(
        self, 
        config_data: Dict[str, Any], 
        config_file: Path
    ) -> Optional[AgentInfo]:
        """
        Cria AgentInfo a partir de configuração
        
        Args:
            config_data: Dados da configuração
            config_file: Caminho do arquivo de config
            
        Returns:
            AgentInfo se criado com sucesso
        """
        try:
            # Tentar descobrir porta e host do config
            host = config_data.get('host', 'localhost')
            port = config_data.get('port')
            
            if not port:
                # Tentar extrair do diretório
                parent_dir = config_file.parent.name
                # Mapear diretórios conhecidos para portas
                dir_port_map = {
                    "helloworld": 9999,
                    "marvin": 3002,
                    "gemini": 3003
                }
                port = dir_port_map.get(parent_dir)
                
                if not port:
                    logger.debug(f"Porta não encontrada para {parent_dir}")
                    return None
            
            base_url = f"http://{host}:{port}"
            
            return AgentInfo(
                id=f"{host}:{port}",
                name=config_data.get('name', config_file.parent.name),
                type=config_data.get('type', 'a2a'),
                host=host,
                port=port,
                url=base_url,
                status=AgentStatus.UNKNOWN,  # Verificar depois
                last_seen=datetime.now(),
                capabilities=config_data.get('capabilities', []),
                metadata={**config_data, "config_file": str(config_file)},
                health_endpoint=urljoin(base_url, "/health"),
                card_endpoint=urljoin(base_url, "/agent/card"),
                version=config_data.get('version')
            )
            
        except Exception as e:
            logger.debug(f"Erro ao criar agent do config: {e}")
            return None
    
    async def health_check_agent(self, agent_id: str) -> bool:
        """
        Verifica saúde de agente específico com circuit breaker
        
        Args:
            agent_id: ID do agente para verificar
            
        Returns:
            True se agente está saudável
        """
        if agent_id not in self.registry:
            logger.warning(f"Agente {agent_id} não encontrado no registry")
            return False
        
        agent = self.registry[agent_id]
        
        try:
            # Usar circuit breaker se disponível
            if agent.circuit_breaker:
                @agent.circuit_breaker
                async def check_health():
                    return await self._perform_health_check(agent)
                
                try:
                    return await check_health()
                except AgentUnreachableError:
                    logger.warning(f"Circuit breaker aberto para {agent_id}")
                    agent.status = AgentStatus.OFFLINE
                    return False
            else:
                return await self._perform_health_check(agent)
                
        except Exception as e:
            logger.error(f"Erro no health check de {agent_id}: {e}")
            agent.status = AgentStatus.ERROR
            return False
    
    async def _perform_health_check(self, agent: AgentInfo) -> bool:
        """
        Executa health check real no agente
        
        Args:
            agent: Agente para verificar
            
        Returns:
            True se agente está saudável
            
        Raises:
            NetworkTimeoutError: Se timeout ocorrer
            AgentProbeError: Se houver erro no health check
        """
        try:
            timeout_seconds = self.config.performance.request_timeout / 1000
            timeout = aiohttp.ClientTimeout(total=timeout_seconds)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(agent.health_endpoint) as response:
                    if response.status == 200:
                        agent.status = AgentStatus.ONLINE
                        agent.last_seen = datetime.now()
                        logger.debug(f"✅ Health check OK para {agent.id}")
                        return True
                    else:
                        agent.status = AgentStatus.ERROR
                        logger.debug(f"❌ Health check falhou para {agent.id}: status {response.status}")
                        return False
                        
        except asyncio.TimeoutError:
            logger.debug(f"⏰ Timeout no health check de {agent.id}")
            agent.status = AgentStatus.OFFLINE
            raise NetworkTimeoutError(f"Timeout no health check de {agent.id}")
        except aiohttp.ClientError as e:
            logger.debug(f"❌ Erro de rede no health check de {agent.id}: {e}")
            agent.status = AgentStatus.OFFLINE
            raise AgentProbeError(f"Erro de rede: {e}") from e
        except Exception as e:
            logger.error(f"❌ Erro inesperado no health check de {agent.id}: {e}")
            agent.status = AgentStatus.ERROR
            raise AgentProbeError(f"Erro inesperado: {e}") from e
    
    async def _cleanup_offline_agents(self) -> None:
        """
        Remove agentes offline há muito tempo
        """
        try:
            cutoff_time = datetime.now() - timedelta(minutes=5)
            offline_agents = []
            
            for agent_id, agent in self.registry.items():
                if agent.last_seen < cutoff_time and agent.status == AgentStatus.OFFLINE:
                    offline_agents.append(agent_id)
            
            for agent_id in offline_agents:
                del self.registry[agent_id]
                logger.info(f"🗑️ Removido agente offline: {agent_id}")
                
        except Exception as e:
            logger.error(f"Erro na limpeza de agentes offline: {e}")
    
    def _discovery_worker(self) -> None:
        """
        Worker thread para descoberta contínua
        """
        logger.info("🔄 Iniciando worker de descoberta contínua")
        
        while self.running:
            try:
                # Executar descoberta
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.discover_agents())
                loop.close()
                
                # Aguardar próximo ciclo
                time.sleep(self.config.discovery.scan_interval)
                
            except Exception as e:
                logger.error(f"Erro no discovery worker: {e}")
                time.sleep(10)  # Aguardar antes de tentar novamente
    
    def get_agents_by_type(self, agent_type: str) -> List[AgentInfo]:
        """
        Retorna agentes de um tipo específico
        
        Args:
            agent_type: Tipo dos agentes a buscar
            
        Returns:
            Lista de agentes do tipo especificado
        """
        try:
            return [agent for agent in self.registry.values() if agent.type == agent_type]
        except Exception as e:
            logger.error(f"Erro ao buscar agentes por tipo {agent_type}: {e}")
            return []
    
    def get_healthy_agents(self) -> List[AgentInfo]:
        """
        Retorna apenas agentes saudáveis
        
        Returns:
            Lista de agentes saudáveis
        """
        try:
            return [agent for agent in self.registry.values() if agent.is_healthy()]
        except Exception as e:
            logger.error(f"Erro ao buscar agentes saudáveis: {e}")
            return []
    
    def get_agent_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas dos agentes
        
        Returns:
            Dicionário com estatísticas
        """
        try:
            agents = list(self.registry.values())
            stats = {
                "total_agents": len(agents),
                "by_status": {},
                "by_type": {},
                "healthy_count": len(self.get_healthy_agents()),
                "discovery_cache_valid": self._is_cache_valid(),
                "last_discovery": self._last_discovery
            }
            
            for agent in agents:
                # Por status
                status = agent.status.value
                stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
                
                # Por tipo
                agent_type = agent.type
                stats["by_type"][agent_type] = stats["by_type"].get(agent_type, 0) + 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Erro ao gerar estatísticas: {e}")
            return {"error": str(e)}
    
    def stop(self) -> None:
        """
        Para o sistema de descoberta graciosamente
        """
        try:
            logger.info("🛑 Parando Service Discovery...")
            self.running = False
            
            if self.discovery_thread.is_alive():
                self.discovery_thread.join(timeout=5)
                
            logger.info("✅ Service Discovery parado com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao parar Service Discovery: {e}")


# 🌐 API FastAPI para Service Discovery
def create_discovery_api(discovery_service: ServiceDiscovery) -> FastAPI:
    """
    Cria API FastAPI para service discovery com tratamento robusto de erros
    
    Args:
        discovery_service: Instância do ServiceDiscovery
        
    Returns:
        Aplicação FastAPI configurada
    """
    
    app = FastAPI(
        title="Service Discovery API",
        version="2.0.0",
        description="API robusta para descoberta de agentes A2A"
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/agents")
    async def list_agents(
        agent_type: Optional[str] = None, 
        healthy_only: bool = False
    ):
        """Lista todos os agentes descobertos com filtros opcionais"""
        try:
            agents = list(discovery_service.registry.values())
            
            if agent_type:
                agents = [a for a in agents if a.type == agent_type]
            
            if healthy_only:
                agents = [a for a in agents if a.is_healthy()]
            
            return {
                "success": True,
                "agents": [agent.to_dict() for agent in agents],
                "count": len(agents),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Erro ao listar agentes: {e}")
            raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
    
    @app.get("/agents/{agent_id}")
    async def get_agent(agent_id: str):
        """Obtém informações detalhadas de agente específico"""
        try:
            if agent_id not in discovery_service.registry:
                raise HTTPException(status_code=404, detail=f"Agente {agent_id} não encontrado")
            
            agent = discovery_service.registry[agent_id]
            return {
                "success": True,
                "agent": agent.to_dict(),
                "timestamp": datetime.now().isoformat()
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Erro ao obter agente {agent_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
    
    @app.post("/discover")
    async def trigger_discovery(background_tasks: BackgroundTasks, force: bool = False):
        """Dispara descoberta manual em background"""
        try:
            async def discover():
                await discovery_service.discover_agents(force_scan=force)
            
            background_tasks.add_task(discover)
            return {
                "success": True,
                "message": "Descoberta iniciada em background",
                "force_scan": force,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Erro ao disparar descoberta: {e}")
            raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
    
    @app.post("/agents/{agent_id}/health")
    async def check_agent_health(agent_id: str):
        """Verifica saúde de agente específico"""
        try:
            is_healthy = await discovery_service.health_check_agent(agent_id)
            return {
                "success": True,
                "agent_id": agent_id,
                "healthy": is_healthy,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Erro no health check de {agent_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Erro no health check: {str(e)}")
    
    @app.get("/stats")
    async def get_stats():
        """Obtém estatísticas detalhadas do sistema"""
        try:
            stats = discovery_service.get_agent_stats()
            return {
                "success": True,
                "stats": stats,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
    
    @app.get("/health")
    async def api_health():
        """Health check da própria API"""
        return {
            "success": True,
            "status": "healthy",
            "service": "Service Discovery API",
            "version": "2.0.0",
            "timestamp": datetime.now().isoformat()
        }
    
    return app


# 🚀 Script principal
if __name__ == "__main__":
    print("🔍 Iniciando Service Discovery System refatorado...")
    
    try:
        # Inicializar service discovery
        discovery = ServiceDiscovery()
        
        # Criar API
        app = create_discovery_api(discovery)
        
        print(f"🔍 Service Discovery iniciado em: http://{discovery.config.discovery.host}:{discovery.config.discovery.port}")
        print(f"📖 API docs: http://{discovery.config.discovery.host}:{discovery.config.discovery.port}/docs")
        print(f"🤖 Agentes descobertos: http://{discovery.config.discovery.host}:{discovery.config.discovery.port}/agents")
        print(f"📊 Estatísticas: http://{discovery.config.discovery.host}:{discovery.config.discovery.port}/stats")
        
        # Executar servidor
        uvicorn.run(
            app, 
            host=discovery.config.discovery.host, 
            port=discovery.config.discovery.port,
            log_level=discovery.config.logger.log_level.lower()
        )
        
    except KeyboardInterrupt:
        print("\n🛑 Parando Service Discovery...")
    except Exception as e:
        print(f"❌ Erro fatal: {e}")
        logger.error(f"Erro fatal na inicialização: {e}")
    finally:
        try:
            discovery.stop()
        except:
            pass