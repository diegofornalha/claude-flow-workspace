#!/usr/bin/env python3
"""
📋 Registry de Clusters - Service Discovery Automático
Implementação do registro centralizado com discovery, health monitoring e metadata management
"""

import asyncio
import json
import logging
import socket
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
import aiohttp
import aiofiles
import hashlib
import uuid

from .cluster_definition import AgentCluster, ClusterStatus, AgentStatus, AgentInfo

# Configurar logging
logger = logging.getLogger(__name__)


class ServiceType(Enum):
    """Tipos de serviços descobertos"""
    CLUSTER = "cluster"
    AGENT = "agent"
    API = "api"
    WEBSOCKET = "websocket"
    GRPC = "grpc"
    DATABASE = "database"
    MCP_SERVER = "mcp_server"
    WEB_UI = "web_ui"
    UNKNOWN = "unknown"


class ServiceStatus(Enum):
    """Status de um serviço"""
    DISCOVERED = "discovered"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"
    OFFLINE = "offline"


@dataclass
class ServiceEndpoint:
    """Informações de um endpoint de serviço"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    host: str = "localhost"
    port: int = 0
    protocol: str = "http"
    path: str = "/"
    service_type: ServiceType = ServiceType.UNKNOWN
    status: ServiceStatus = ServiceStatus.DISCOVERED
    last_seen: datetime = field(default_factory=datetime.now)
    last_health_check: Optional[datetime] = None
    response_time_ms: float = 0.0
    health_score: float = 100.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)
    version: str = "unknown"
    
    @property
    def url(self) -> str:
        """URL completa do endpoint"""
        return f"{self.protocol}://{self.host}:{self.port}{self.path}"
    
    @property
    def address(self) -> str:
        """Endereço host:port"""
        return f"{self.host}:{self.port}"
    
    def is_healthy(self) -> bool:
        """Verifica se endpoint está saudável"""
        return self.status in [ServiceStatus.HEALTHY, ServiceStatus.DEGRADED]
    
    def update_health(self, 
                     response_time: float = None,
                     is_responding: bool = True,
                     error_message: str = None):
        """Atualiza status de saúde do endpoint"""
        self.last_health_check = datetime.now()
        
        if response_time is not None:
            self.response_time_ms = response_time
        
        if is_responding:
            if response_time and response_time < 100:  # ms
                self.status = ServiceStatus.HEALTHY
                self.health_score = min(100, self.health_score + 5)
            elif response_time and response_time < 1000:  # ms
                self.status = ServiceStatus.HEALTHY
                self.health_score = max(70, min(95, self.health_score))
            else:
                self.status = ServiceStatus.DEGRADED
                self.health_score = max(50, self.health_score - 10)
        else:
            if self.status != ServiceStatus.OFFLINE:
                self.status = ServiceStatus.UNREACHABLE
                self.health_score = max(0, self.health_score - 20)
            
            if error_message:
                self.metadata['last_error'] = error_message
        
        self.last_seen = datetime.now()


@dataclass
class ClusterRegistration:
    """Registro de um cluster no registry"""
    cluster_id: str
    name: str
    description: str
    status: ClusterStatus
    endpoints: List[ServiceEndpoint] = field(default_factory=list)
    agents: List[Dict[str, Any]] = field(default_factory=list)
    capabilities: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    heartbeat_interval: int = 30  # segundos
    last_heartbeat: Optional[datetime] = None
    
    def is_active(self) -> bool:
        """Verifica se cluster está ativo"""
        if not self.last_heartbeat:
            return False
        
        time_since_heartbeat = (datetime.now() - self.last_heartbeat).total_seconds()
        return time_since_heartbeat < (self.heartbeat_interval * 2)
    
    def add_endpoint(self, endpoint: ServiceEndpoint):
        """Adiciona endpoint ao cluster"""
        # Evitar duplicatas
        existing = next(
            (ep for ep in self.endpoints if ep.address == endpoint.address),
            None
        )
        
        if existing:
            # Atualizar endpoint existente
            existing.metadata.update(endpoint.metadata)
            existing.tags.update(endpoint.tags)
            existing.last_seen = datetime.now()
        else:
            self.endpoints.append(endpoint)
        
        self.last_updated = datetime.now()


class ServiceDiscovery:
    """Motor de descoberta de serviços"""
    
    def __init__(self):
        self.known_ports = [
            3000, 3001, 3002, 3003, 3004,  # Aplicações web
            5000, 5001, 5002,              # APIs
            8000, 8080, 8081, 8082,        # Servidores HTTP
            9999,                          # Agente helloworld
            12000,                         # UI
            7474, 7687,                    # Neo4j
            6379,                          # Redis
            5432,                          # PostgreSQL
        ]
        
        self.scan_ranges = [
            ("localhost", range(3000, 4000)),
            ("127.0.0.1", range(5000, 6000)),
            ("0.0.0.0", range(8000, 9000))
        ]
        
        self.discovery_patterns = {
            ServiceType.WEB_UI: [12000],
            ServiceType.API: [5000, 5001, 8080],
            ServiceType.WEBSOCKET: [8081],
            ServiceType.DATABASE: [7474, 7687, 6379, 5432],
            ServiceType.MCP_SERVER: [3000, 3001, 3002, 3003],
            ServiceType.AGENT: [9999]
        }
        
        self.session = None
        self.discovery_cache = {}
        self.cache_ttl = 300  # 5 minutos
    
    async def start(self):
        """Inicia o service discovery"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=5)
        )
        logger.info("🔍 Service Discovery iniciado")
    
    async def stop(self):
        """Para o service discovery"""
        if self.session:
            await self.session.close()
        logger.info("🛑 Service Discovery parado")
    
    async def discover_services(self, 
                               hosts: List[str] = None,
                               port_ranges: List[range] = None) -> List[ServiceEndpoint]:
        """Descobre serviços na rede"""
        discovered = []
        
        hosts = hosts or ["localhost", "127.0.0.1"]
        
        if port_ranges:
            scan_targets = [(host, port_range) for host in hosts for port_range in port_ranges]
        else:
            scan_targets = self.scan_ranges
        
        # Limitar concorrência para não sobrecarregar a rede
        semaphore = asyncio.Semaphore(20)
        
        tasks = []
        for host, ports in scan_targets:
            for port in (ports if hasattr(ports, '__iter__') else [ports]):
                if isinstance(port, range):
                    for p in port:
                        tasks.append(self._scan_port(semaphore, host, p))
                else:
                    tasks.append(self._scan_port(semaphore, host, port))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, ServiceEndpoint):
                    discovered.append(result)
                elif isinstance(result, Exception):
                    logger.debug(f"Erro no scan: {result}")
        
        logger.info(f"🔍 Descobertos {len(discovered)} serviços")
        return discovered
    
    async def _scan_port(self, 
                        semaphore: asyncio.Semaphore, 
                        host: str, 
                        port: int) -> Optional[ServiceEndpoint]:
        """Escaneia uma porta específica"""
        async with semaphore:
            cache_key = f"{host}:{port}"
            
            # Verificar cache
            if cache_key in self.discovery_cache:
                cached_time, cached_result = self.discovery_cache[cache_key]
                if (time.time() - cached_time) < self.cache_ttl:
                    return cached_result
            
            try:
                # Verificar se porta está aberta
                if not await self._is_port_open(host, port):
                    return None
                
                # Tentar identificar o serviço
                endpoint = await self._identify_service(host, port)
                
                # Cache resultado
                self.discovery_cache[cache_key] = (time.time(), endpoint)
                
                return endpoint
                
            except Exception as e:
                logger.debug(f"Erro ao escanear {host}:{port}: {e}")
                return None
    
    async def _is_port_open(self, host: str, port: int) -> bool:
        """Verifica se porta está aberta"""
        try:
            # Usar socket para verificação rápida
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False
    
    async def _identify_service(self, host: str, port: int) -> ServiceEndpoint:
        """Identifica tipo de serviço em uma porta"""
        endpoint = ServiceEndpoint(host=host, port=port)
        
        # Tentar identificar via HTTP
        for protocol in ["http", "https"]:
            try:
                url = f"{protocol}://{host}:{port}"
                
                async with self.session.get(url, timeout=2) as response:
                    endpoint.protocol = protocol
                    endpoint.status = ServiceStatus.HEALTHY
                    endpoint.response_time_ms = response.headers.get('X-Response-Time', 0)
                    
                    # Identificar tipo baseado no conteúdo
                    content_type = response.headers.get('content-type', '').lower()
                    server = response.headers.get('server', '').lower()
                    
                    # Tentar obter informações adicionais
                    if response.status == 200:
                        try:
                            text = await response.text()
                            endpoint.service_type = self._classify_service(port, content_type, server, text)
                            
                            # Extrair metadados
                            endpoint.metadata = self._extract_metadata(response, text)
                            
                        except:
                            pass
                    
                    break
                    
            except:
                continue
        
        # Classificar por porta se não identificado via HTTP
        if endpoint.service_type == ServiceType.UNKNOWN:
            endpoint.service_type = self._classify_by_port(port)
        
        return endpoint
    
    def _classify_service(self, 
                         port: int, 
                         content_type: str, 
                         server: str, 
                         content: str) -> ServiceType:
        """Classifica tipo de serviço baseado em evidências"""
        
        # Verificar por palavras-chave no conteúdo
        content_lower = content.lower()
        
        if any(keyword in content_lower for keyword in ['neo4j', 'cypher', 'graph']):
            return ServiceType.DATABASE
        
        if any(keyword in content_lower for keyword in ['dashboard', 'admin', 'ui']):
            return ServiceType.WEB_UI
        
        if any(keyword in content_lower for keyword in ['api', 'rest', 'graphql']):
            return ServiceType.API
        
        if any(keyword in content_lower for keyword in ['websocket', 'ws://', 'socket.io']):
            return ServiceType.WEBSOCKET
        
        if any(keyword in content_lower for keyword in ['agent', 'claude', 'ai']):
            return ServiceType.AGENT
        
        if any(keyword in content_lower for keyword in ['mcp', 'model context protocol']):
            return ServiceType.MCP_SERVER
        
        # Verificar por content-type
        if 'application/json' in content_type:
            return ServiceType.API
        
        if 'text/html' in content_type:
            return ServiceType.WEB_UI
        
        # Classificar por porta
        return self._classify_by_port(port)
    
    def _classify_by_port(self, port: int) -> ServiceType:
        """Classifica serviço pela porta"""
        for service_type, ports in self.discovery_patterns.items():
            if port in ports:
                return service_type
        
        # Classificação genérica por faixas de porta
        if 3000 <= port < 4000:
            return ServiceType.WEB_UI
        elif 5000 <= port < 6000:
            return ServiceType.API
        elif 7000 <= port < 8000:
            return ServiceType.DATABASE
        elif 8000 <= port < 9000:
            return ServiceType.API
        else:
            return ServiceType.UNKNOWN
    
    def _extract_metadata(self, response, content: str) -> Dict[str, Any]:
        """Extrai metadados do serviço"""
        metadata = {}
        
        # Headers úteis
        useful_headers = [
            'server', 'x-powered-by', 'x-version', 'x-api-version',
            'x-frame-options', 'x-content-type-options'
        ]
        
        for header in useful_headers:
            if header in response.headers:
                metadata[header] = response.headers[header]
        
        # Tentar extrair versão do conteúdo
        import re
        
        version_patterns = [
            r'version["\s:]+([0-9]+\.[0-9]+\.[0-9]+)',
            r'v([0-9]+\.[0-9]+)',
            r'"version"\s*:\s*"([^"]+)"'
        ]
        
        for pattern in version_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                metadata['version'] = match.group(1)
                break
        
        return metadata


class ClusterRegistry:
    """Registry centralizado de clusters com service discovery"""
    
    def __init__(self, storage_path: str = None):
        self.registrations: Dict[str, ClusterRegistration] = {}
        self.service_discovery = ServiceDiscovery()
        self.storage_path = Path(storage_path or "clusters_registry.json")
        self.running = False
        
        self.metrics = {
            'clusters_registered': 0,
            'services_discovered': 0,
            'health_checks_performed': 0,
            'discovery_scans': 0
        }
        
        self.config = {
            'auto_discovery_interval': 300,  # 5 minutos
            'health_check_interval': 60,    # 1 minuto
            'cleanup_interval': 3600,       # 1 hora
            'max_missed_heartbeats': 3,
            'enable_persistence': True
        }
    
    async def start(self):
        """Inicia o registry"""
        if self.running:
            logger.warning("⚠️ Registry já está rodando")
            return
        
        self.running = True
        logger.info("🚀 Iniciando Cluster Registry...")
        
        # Carregar dados persistidos
        await self._load_state()
        
        # Iniciar service discovery
        await self.service_discovery.start()
        
        # Iniciar tarefas assíncronas
        asyncio.create_task(self._auto_discovery_loop())
        asyncio.create_task(self._health_monitoring_loop())
        asyncio.create_task(self._cleanup_loop())
        
        logger.info("✅ Cluster Registry iniciado")
    
    async def stop(self):
        """Para o registry"""
        if not self.running:
            return
        
        self.running = False
        logger.info("🛑 Parando Cluster Registry...")
        
        # Salvar estado
        await self._save_state()
        
        # Parar service discovery
        await self.service_discovery.stop()
        
        logger.info("⏸️ Cluster Registry parado")
    
    async def register_cluster(self, cluster: AgentCluster) -> bool:
        """Registra um cluster no registry"""
        try:
            cluster_id = cluster.cluster_id
            
            if cluster_id in self.registrations:
                # Atualizar registro existente
                registration = self.registrations[cluster_id]
                registration.status = cluster.status
                registration.last_updated = datetime.now()
                registration.last_heartbeat = datetime.now()
            else:
                # Criar novo registro
                registration = ClusterRegistration(
                    cluster_id=cluster_id,
                    name=cluster.name,
                    description=cluster.description,
                    status=cluster.status,
                    last_heartbeat=datetime.now()
                )
                
                # Extrair capacidades dos agentes
                for agent in cluster.agents.values():
                    registration.capabilities.update(agent.capabilities)
                    registration.agents.append({
                        'id': agent.id,
                        'name': agent.name,
                        'role': agent.role,
                        'status': agent.status.value,
                        'capabilities': agent.capabilities
                    })
                
                self.registrations[cluster_id] = registration
                self.metrics['clusters_registered'] += 1
            
            logger.info(f"✅ Cluster '{cluster.name}' registrado")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao registrar cluster: {e}")
            return False
    
    async def unregister_cluster(self, cluster_id: str) -> bool:
        """Remove cluster do registry"""
        if cluster_id in self.registrations:
            del self.registrations[cluster_id]
            logger.info(f"🗑️ Cluster '{cluster_id}' removido do registry")
            return True
        return False
    
    async def update_heartbeat(self, cluster_id: str) -> bool:
        """Atualiza heartbeat de um cluster"""
        if cluster_id in self.registrations:
            self.registrations[cluster_id].last_heartbeat = datetime.now()
            return True
        return False
    
    async def discover_services(self) -> List[ServiceEndpoint]:
        """Executa descoberta de serviços"""
        logger.info("🔍 Iniciando descoberta de serviços...")
        
        discovered = await self.service_discovery.discover_services()
        self.metrics['services_discovered'] += len(discovered)
        self.metrics['discovery_scans'] += 1
        
        # Associar serviços descobertos aos clusters
        await self._associate_services_to_clusters(discovered)
        
        logger.info(f"✅ Descoberta concluída: {len(discovered)} serviços")
        return discovered
    
    async def _associate_services_to_clusters(self, services: List[ServiceEndpoint]):
        """Associa serviços descobertos aos clusters"""
        for service in services:
            # Tentar associar por padrões conhecidos
            cluster_id = self._infer_cluster_from_service(service)
            
            if cluster_id and cluster_id in self.registrations:
                registration = self.registrations[cluster_id]
                registration.add_endpoint(service)
    
    def _infer_cluster_from_service(self, service: ServiceEndpoint) -> Optional[str]:
        """Infere cluster baseado no tipo de serviço"""
        
        service_to_cluster = {
            ServiceType.DATABASE: "memory_cluster",
            ServiceType.WEB_UI: "discovery_cluster",
            ServiceType.MCP_SERVER: "mcp_cluster",
            ServiceType.AGENT: "discovery_cluster"
        }
        
        return service_to_cluster.get(service.service_type)
    
    def find_clusters_by_capability(self, capability: str) -> List[ClusterRegistration]:
        """Encontra clusters por capacidade"""
        return [
            reg for reg in self.registrations.values()
            if capability in reg.capabilities and reg.is_active()
        ]
    
    def find_services_by_type(self, service_type: ServiceType) -> List[ServiceEndpoint]:
        """Encontra serviços por tipo"""
        services = []
        for registration in self.registrations.values():
            services.extend([
                ep for ep in registration.endpoints
                if ep.service_type == service_type and ep.is_healthy()
            ])
        return services
    
    def get_cluster_info(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        """Retorna informações detalhadas de um cluster"""
        if cluster_id not in self.registrations:
            return None
        
        registration = self.registrations[cluster_id]
        
        return {
            'cluster_id': registration.cluster_id,
            'name': registration.name,
            'description': registration.description,
            'status': registration.status.value,
            'is_active': registration.is_active(),
            'registered_at': registration.registered_at.isoformat(),
            'last_updated': registration.last_updated.isoformat(),
            'last_heartbeat': registration.last_heartbeat.isoformat() if registration.last_heartbeat else None,
            'agents_count': len(registration.agents),
            'endpoints_count': len(registration.endpoints),
            'capabilities': list(registration.capabilities),
            'agents': registration.agents,
            'endpoints': [
                {
                    'id': ep.id,
                    'url': ep.url,
                    'service_type': ep.service_type.value,
                    'status': ep.status.value,
                    'health_score': ep.health_score,
                    'response_time_ms': ep.response_time_ms,
                    'last_seen': ep.last_seen.isoformat()
                }
                for ep in registration.endpoints
            ],
            'metadata': registration.metadata
        }
    
    async def _auto_discovery_loop(self):
        """Loop de descoberta automática"""
        while self.running:
            try:
                await self.discover_services()
                await asyncio.sleep(self.config['auto_discovery_interval'])
            except Exception as e:
                logger.error(f"❌ Erro no auto discovery: {e}")
                await asyncio.sleep(60)
    
    async def _health_monitoring_loop(self):
        """Loop de monitoramento de saúde"""
        while self.running:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.config['health_check_interval'])
            except Exception as e:
                logger.error(f"❌ Erro no health monitoring: {e}")
                await asyncio.sleep(30)
    
    async def _perform_health_checks(self):
        """Executa health checks de todos os endpoints"""
        tasks = []
        
        for registration in self.registrations.values():
            for endpoint in registration.endpoints:
                task = asyncio.create_task(self._health_check_endpoint(endpoint))
                tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            self.metrics['health_checks_performed'] += len(tasks)
    
    async def _health_check_endpoint(self, endpoint: ServiceEndpoint):
        """Health check de um endpoint específico"""
        try:
            start_time = time.time()
            
            if endpoint.protocol in ["http", "https"]:
                async with self.service_discovery.session.get(
                    endpoint.url, 
                    timeout=5
                ) as response:
                    response_time = (time.time() - start_time) * 1000
                    endpoint.update_health(response_time, True)
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            endpoint.update_health(response_time, False, str(e))
    
    async def _cleanup_loop(self):
        """Loop de limpeza de registros antigos"""
        while self.running:
            try:
                await self._cleanup_stale_registrations()
                await asyncio.sleep(self.config['cleanup_interval'])
            except Exception as e:
                logger.error(f"❌ Erro no cleanup: {e}")
                await asyncio.sleep(300)
    
    async def _cleanup_stale_registrations(self):
        """Remove registros de clusters inativos"""
        cutoff_time = datetime.now() - timedelta(
            seconds=self.config['max_missed_heartbeats'] * 60
        )
        
        stale_clusters = [
            cluster_id for cluster_id, registration in self.registrations.items()
            if registration.last_heartbeat and registration.last_heartbeat < cutoff_time
        ]
        
        for cluster_id in stale_clusters:
            logger.info(f"🧹 Removendo cluster inativo: {cluster_id}")
            await self.unregister_cluster(cluster_id)
    
    async def _save_state(self):
        """Salva estado do registry"""
        if not self.config['enable_persistence']:
            return
        
        try:
            state = {
                'registrations': {
                    cluster_id: {
                        'cluster_id': reg.cluster_id,
                        'name': reg.name,
                        'description': reg.description,
                        'status': reg.status.value,
                        'registered_at': reg.registered_at.isoformat(),
                        'last_updated': reg.last_updated.isoformat(),
                        'capabilities': list(reg.capabilities),
                        'agents': reg.agents,
                        'metadata': reg.metadata
                    }
                    for cluster_id, reg in self.registrations.items()
                },
                'metrics': self.metrics.copy(),
                'saved_at': datetime.now().isoformat()
            }
            
            async with aiofiles.open(self.storage_path, 'w') as f:
                await f.write(json.dumps(state, indent=2))
                
            logger.info(f"💾 Estado salvo em {self.storage_path}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar estado: {e}")
    
    async def _load_state(self):
        """Carrega estado do registry"""
        if not self.config['enable_persistence'] or not self.storage_path.exists():
            return
        
        try:
            async with aiofiles.open(self.storage_path, 'r') as f:
                state = json.loads(await f.read())
            
            # Restaurar registrations (sem endpoints, pois podem estar desatualizados)
            for cluster_id, reg_data in state.get('registrations', {}).items():
                registration = ClusterRegistration(
                    cluster_id=reg_data['cluster_id'],
                    name=reg_data['name'],
                    description=reg_data['description'],
                    status=ClusterStatus(reg_data['status']),
                    capabilities=set(reg_data.get('capabilities', [])),
                    agents=reg_data.get('agents', []),
                    metadata=reg_data.get('metadata', {}),
                    registered_at=datetime.fromisoformat(reg_data['registered_at']),
                    last_updated=datetime.fromisoformat(reg_data['last_updated'])
                )
                
                self.registrations[cluster_id] = registration
            
            logger.info(f"📥 Estado carregado de {self.storage_path}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar estado: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status completo do registry"""
        active_clusters = sum(1 for reg in self.registrations.values() if reg.is_active())
        total_endpoints = sum(len(reg.endpoints) for reg in self.registrations.values())
        healthy_endpoints = sum(
            1 for reg in self.registrations.values()
            for ep in reg.endpoints if ep.is_healthy()
        )
        
        return {
            'registry': {
                'running': self.running,
                'clusters_registered': len(self.registrations),
                'active_clusters': active_clusters,
                'total_endpoints': total_endpoints,
                'healthy_endpoints': healthy_endpoints,
                'config': self.config.copy()
            },
            'metrics': self.metrics.copy(),
            'clusters': {
                cluster_id: self.get_cluster_info(cluster_id)
                for cluster_id in self.registrations.keys()
            }
        }


# ==================== SINGLETON E UTILITÁRIOS ====================

_registry_instance = None

def get_cluster_registry(storage_path: str = None) -> ClusterRegistry:
    """Retorna instância singleton do registry"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ClusterRegistry(storage_path)
    return _registry_instance


if __name__ == "__main__":
    async def test_registry():
        """Teste do cluster registry"""
        logger.info("🧪 Testando Cluster Registry...")
        
        # Criar registry
        registry = get_cluster_registry("/tmp/test_registry.json")
        await registry.start()
        
        # Executar descoberta manual
        services = await registry.discover_services()
        print(f"\n🔍 Serviços descobertos: {len(services)}")
        
        for service in services[:10]:  # Mostrar apenas os primeiros 10
            print(f"  - {service.service_type.value}: {service.url} (saúde: {service.health_score}%)")
        
        # Mostrar status
        status = registry.get_status()
        print(f"\n📊 STATUS DO REGISTRY:")
        print(f"Clusters registrados: {status['registry']['clusters_registered']}")
        print(f"Clusters ativos: {status['registry']['active_clusters']}")
        print(f"Endpoints totais: {status['registry']['total_endpoints']}")
        print(f"Endpoints saudáveis: {status['registry']['healthy_endpoints']}")
        print(f"Serviços descobertos: {status['metrics']['services_discovered']}")
        
        # Parar
        await registry.stop()
        print("\n✅ Teste concluído!")
    
    # Executar teste
    asyncio.run(test_registry())