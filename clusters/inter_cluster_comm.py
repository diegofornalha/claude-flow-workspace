#!/usr/bin/env python3
"""
📡 Sistema de Comunicação Inter-Cluster
Implementação de event bus, message broker e protocolos de comunicação assíncrona
"""

import asyncio
import json
import logging
import time
import uuid
import weakref
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Union, Set
from pathlib import Path
import socket
import websockets
import aiohttp
from aiohttp import web
import grpc
from grpc import aio as aiogrpc

# Configurar logging
logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Tipos de mensagens no sistema"""
    COMMAND = "command"
    QUERY = "query"
    EVENT = "event"
    RESPONSE = "response"
    HEARTBEAT = "heartbeat"
    BROADCAST = "broadcast"
    NOTIFICATION = "notification"


class MessagePriority(Enum):
    """Prioridades de mensagens"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class Protocol(Enum):
    """Protocolos de comunicação suportados"""
    REST = "rest"
    WEBSOCKET = "websocket"
    GRPC = "grpc"
    INTERNAL = "internal"


@dataclass
class Message:
    """Estrutura de mensagem padronizada"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType = MessageType.COMMAND
    priority: MessagePriority = MessagePriority.NORMAL
    source_cluster: str = ""
    target_cluster: str = ""
    source_agent: str = ""
    target_agent: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    ttl: int = 300  # Time to live em segundos
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    retries: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte mensagem para dicionário"""
        return {
            'id': self.id,
            'type': self.type.value,
            'priority': self.priority.value,
            'source_cluster': self.source_cluster,
            'target_cluster': self.target_cluster,
            'source_agent': self.source_agent,
            'target_agent': self.target_agent,
            'payload': self.payload,
            'headers': self.headers,
            'timestamp': self.timestamp.isoformat(),
            'ttl': self.ttl,
            'correlation_id': self.correlation_id,
            'reply_to': self.reply_to,
            'retries': self.retries,
            'max_retries': self.max_retries
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Cria mensagem a partir de dicionário"""
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            type=MessageType(data.get('type', 'command')),
            priority=MessagePriority(data.get('priority', 2)),
            source_cluster=data.get('source_cluster', ''),
            target_cluster=data.get('target_cluster', ''),
            source_agent=data.get('source_agent', ''),
            target_agent=data.get('target_agent', ''),
            payload=data.get('payload', {}),
            headers=data.get('headers', {}),
            timestamp=datetime.fromisoformat(data.get('timestamp', datetime.now().isoformat())),
            ttl=data.get('ttl', 300),
            correlation_id=data.get('correlation_id'),
            reply_to=data.get('reply_to'),
            retries=data.get('retries', 0),
            max_retries=data.get('max_retries', 3)
        )
    
    def is_expired(self) -> bool:
        """Verifica se mensagem expirou"""
        return (datetime.now() - self.timestamp).total_seconds() > self.ttl


@dataclass
class Subscription:
    """Inscrição para receber mensagens"""
    id: str
    pattern: str  # Padrão de matching (regex)
    callback: Callable[[Message], Any]
    cluster_id: str
    agent_id: Optional[str] = None
    message_types: Set[MessageType] = field(default_factory=set)
    active: bool = True
    created_at: datetime = field(default_factory=datetime.now)


class EventBus:
    """Event Bus para comunicação assíncrona baseada em eventos"""
    
    def __init__(self):
        self.subscriptions: Dict[str, Subscription] = {}
        self.message_history: deque = deque(maxlen=1000)
        self.metrics = {
            'messages_published': 0,
            'messages_delivered': 0,
            'active_subscriptions': 0,
            'failed_deliveries': 0
        }
        self.executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="eventbus")
    
    def subscribe(self, 
                 pattern: str,
                 callback: Callable[[Message], Any],
                 cluster_id: str,
                 agent_id: str = None,
                 message_types: Set[MessageType] = None) -> str:
        """Inscreve-se para receber mensagens que fazem match com o padrão"""
        subscription_id = str(uuid.uuid4())
        
        subscription = Subscription(
            id=subscription_id,
            pattern=pattern,
            callback=callback,
            cluster_id=cluster_id,
            agent_id=agent_id,
            message_types=message_types or {MessageType.EVENT, MessageType.BROADCAST}
        )
        
        self.subscriptions[subscription_id] = subscription
        self.metrics['active_subscriptions'] = len(self.subscriptions)
        
        logger.info(f"📝 Subscription criada: {subscription_id} para padrão '{pattern}'")
        return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove inscrição"""
        if subscription_id in self.subscriptions:
            del self.subscriptions[subscription_id]
            self.metrics['active_subscriptions'] = len(self.subscriptions)
            logger.info(f"🗑️ Subscription removida: {subscription_id}")
            return True
        return False
    
    async def publish(self, message: Message) -> int:
        """Publica mensagem para todos os assinantes relevantes"""
        import re
        
        self.metrics['messages_published'] += 1
        self.message_history.append(message)
        
        delivered_count = 0
        
        # Encontrar subscriptions que fazem match
        matching_subscriptions = []
        
        for subscription in self.subscriptions.values():
            if not subscription.active:
                continue
            
            # Verificar tipo de mensagem
            if subscription.message_types and message.type not in subscription.message_types:
                continue
            
            # Verificar padrão
            message_str = json.dumps(message.to_dict(), default=str)
            if re.search(subscription.pattern, message_str, re.IGNORECASE):
                matching_subscriptions.append(subscription)
        
        # Entregar mensagens assíncronamente
        if matching_subscriptions:
            tasks = [
                self._deliver_message(message, subscription)
                for subscription in matching_subscriptions
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    self.metrics['failed_deliveries'] += 1
                    logger.error(f"❌ Erro na entrega: {result}")
                else:
                    delivered_count += 1
        
        self.metrics['messages_delivered'] += delivered_count
        
        logger.debug(f"📤 Mensagem {message.id} entregue para {delivered_count} assinantes")
        return delivered_count
    
    async def _deliver_message(self, message: Message, subscription: Subscription):
        """Entrega mensagem para um assinante específico"""
        try:
            # Executar callback em thread separada para não bloquear
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor,
                subscription.callback,
                message
            )
            
        except Exception as e:
            logger.error(f"❌ Erro ao entregar mensagem para {subscription.id}: {e}")
            raise
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas do event bus"""
        return {
            'metrics': self.metrics.copy(),
            'active_subscriptions': len(self.subscriptions),
            'message_history_size': len(self.message_history),
            'subscriptions': [
                {
                    'id': sub.id,
                    'pattern': sub.pattern,
                    'cluster_id': sub.cluster_id,
                    'agent_id': sub.agent_id,
                    'active': sub.active,
                    'created_at': sub.created_at.isoformat()
                }
                for sub in self.subscriptions.values()
            ]
        }


class MessageQueue:
    """Queue de mensagens com prioridades e retry logic"""
    
    def __init__(self, max_size: int = 10000):
        self.queues = {
            MessagePriority.CRITICAL: asyncio.PriorityQueue(),
            MessagePriority.HIGH: asyncio.PriorityQueue(),
            MessagePriority.NORMAL: asyncio.PriorityQueue(),
            MessagePriority.LOW: asyncio.PriorityQueue()
        }
        self.max_size = max_size
        self.size = 0
        self.dead_letter_queue: List[Message] = []
        self.metrics = {
            'enqueued': 0,
            'dequeued': 0,
            'expired': 0,
            'dead_letters': 0
        }
    
    async def enqueue(self, message: Message) -> bool:
        """Adiciona mensagem à queue com prioridade"""
        if self.size >= self.max_size:
            logger.warning("⚠️ Queue cheia, rejeitando mensagem")
            return False
        
        if message.is_expired():
            logger.warning(f"⚠️ Mensagem {message.id} expirada, movendo para dead letter")
            self.dead_letter_queue.append(message)
            self.metrics['dead_letters'] += 1
            return False
        
        # Usar timestamp negativo para ordenação correta (prioridade + FIFO)
        priority_value = (-message.priority.value, -time.time())
        
        await self.queues[message.priority].put((priority_value, message))
        self.size += 1
        self.metrics['enqueued'] += 1
        
        logger.debug(f"📥 Mensagem {message.id} enfileirada com prioridade {message.priority.name}")
        return True
    
    async def dequeue(self, timeout: float = None) -> Optional[Message]:
        """Remove mensagem da queue respeitando prioridades"""
        # Tentar em ordem de prioridade
        for priority in [MessagePriority.CRITICAL, MessagePriority.HIGH, 
                        MessagePriority.NORMAL, MessagePriority.LOW]:
            queue = self.queues[priority]
            
            if not queue.empty():
                try:
                    if timeout:
                        priority_value, message = await asyncio.wait_for(
                            queue.get(), timeout=timeout
                        )
                    else:
                        priority_value, message = await queue.get()
                    
                    self.size -= 1
                    self.metrics['dequeued'] += 1
                    
                    # Verificar se mensagem ainda é válida
                    if message.is_expired():
                        self.metrics['expired'] += 1
                        self.dead_letter_queue.append(message)
                        logger.warning(f"⚠️ Mensagem {message.id} expirou durante processamento")
                        continue
                    
                    logger.debug(f"📤 Mensagem {message.id} removida da queue")
                    return message
                    
                except asyncio.TimeoutError:
                    continue
        
        return None
    
    def get_size(self) -> Dict[str, int]:
        """Retorna tamanho das queues por prioridade"""
        return {
            priority.name: queue.qsize()
            for priority, queue in self.queues.items()
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas da queue"""
        return {
            'metrics': self.metrics.copy(),
            'total_size': self.size,
            'queue_sizes': self.get_size(),
            'dead_letter_count': len(self.dead_letter_queue)
        }


class ProtocolHandler(ABC):
    """Interface para handlers de protocolos de comunicação"""
    
    @abstractmethod
    async def start(self, host: str, port: int):
        """Inicia o servidor do protocolo"""
        pass
    
    @abstractmethod
    async def stop(self):
        """Para o servidor do protocolo"""
        pass
    
    @abstractmethod
    async def send_message(self, message: Message, target_address: str) -> bool:
        """Envia mensagem usando o protocolo"""
        pass


class RESTProtocolHandler(ProtocolHandler):
    """Handler para comunicação via REST API"""
    
    def __init__(self, message_broker):
        self.message_broker = message_broker
        self.app = None
        self.runner = None
        self.site = None
        self.session = None
    
    async def start(self, host: str = "0.0.0.0", port: int = 8080):
        """Inicia servidor REST"""
        self.app = web.Application()
        
        # Configurar rotas
        self.app.router.add_post('/messages', self._handle_message)
        self.app.router.add_get('/health', self._handle_health)
        self.app.router.add_get('/metrics', self._handle_metrics)
        
        # Configurar CORS
        self.app.middlewares.append(self._cors_middleware)
        
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        self.site = web.TCPSite(self.runner, host, port)
        await self.site.start()
        
        # Inicializar sessão HTTP para envios
        self.session = aiohttp.ClientSession()
        
        logger.info(f"🌐 Servidor REST iniciado em http://{host}:{port}")
    
    async def stop(self):
        """Para servidor REST"""
        if self.session:
            await self.session.close()
        
        if self.site:
            await self.site.stop()
        
        if self.runner:
            await self.runner.cleanup()
        
        logger.info("🛑 Servidor REST parado")
    
    async def send_message(self, message: Message, target_address: str) -> bool:
        """Envia mensagem via REST"""
        try:
            url = f"http://{target_address}/messages"
            data = message.to_dict()
            
            async with self.session.post(url, json=data) as response:
                if response.status == 200:
                    logger.debug(f"✅ Mensagem {message.id} enviada via REST para {target_address}")
                    return True
                else:
                    logger.error(f"❌ Erro REST {response.status}: {await response.text()}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem REST: {e}")
            return False
    
    async def _handle_message(self, request):
        """Handler para recebimento de mensagens"""
        try:
            data = await request.json()
            message = Message.from_dict(data)
            
            # Enviar para message broker
            await self.message_broker.receive_message(message, Protocol.REST)
            
            return web.json_response({'status': 'received', 'message_id': message.id})
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar mensagem REST: {e}")
            return web.json_response({'error': str(e)}, status=400)
    
    async def _handle_health(self, request):
        """Handler para health check"""
        return web.json_response({'status': 'healthy', 'protocol': 'REST'})
    
    async def _handle_metrics(self, request):
        """Handler para métricas"""
        metrics = self.message_broker.get_metrics()
        return web.json_response(metrics)
    
    @web.middleware
    async def _cors_middleware(self, request, handler):
        """Middleware para CORS"""
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response


class WebSocketProtocolHandler(ProtocolHandler):
    """Handler para comunicação via WebSocket"""
    
    def __init__(self, message_broker):
        self.message_broker = message_broker
        self.server = None
        self.connections: Set[websockets.WebSocketServerProtocol] = set()
        self.client_connections: Dict[str, websockets.WebSocketServerProtocol] = {}
    
    async def start(self, host: str = "0.0.0.0", port: int = 8081):
        """Inicia servidor WebSocket"""
        self.server = await websockets.serve(
            self._handle_connection,
            host,
            port
        )
        
        logger.info(f"🔌 Servidor WebSocket iniciado em ws://{host}:{port}")
    
    async def stop(self):
        """Para servidor WebSocket"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # Fechar todas as conexões
        if self.connections:
            await asyncio.gather(
                *[conn.close() for conn in self.connections],
                return_exceptions=True
            )
        
        logger.info("🛑 Servidor WebSocket parado")
    
    async def send_message(self, message: Message, target_address: str) -> bool:
        """Envia mensagem via WebSocket"""
        try:
            # Se já temos conexão com o target
            if target_address in self.client_connections:
                websocket = self.client_connections[target_address]
                await websocket.send(json.dumps(message.to_dict()))
                logger.debug(f"✅ Mensagem {message.id} enviada via WebSocket para {target_address}")
                return True
            
            # Tentar conectar
            uri = f"ws://{target_address}/ws"
            async with websockets.connect(uri) as websocket:
                await websocket.send(json.dumps(message.to_dict()))
                logger.debug(f"✅ Mensagem {message.id} enviada via WebSocket para {target_address}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem WebSocket: {e}")
            return False
    
    async def _handle_connection(self, websocket, path):
        """Handler para novas conexões WebSocket"""
        self.connections.add(websocket)
        
        try:
            logger.info(f"🔌 Nova conexão WebSocket: {websocket.remote_address}")
            
            async for message_data in websocket:
                try:
                    data = json.loads(message_data)
                    message = Message.from_dict(data)
                    
                    # Enviar para message broker
                    await self.message_broker.receive_message(message, Protocol.WEBSOCKET)
                    
                except json.JSONDecodeError:
                    logger.error("❌ Erro ao decodificar mensagem WebSocket")
                except Exception as e:
                    logger.error(f"❌ Erro ao processar mensagem WebSocket: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("🔌 Conexão WebSocket fechada")
        finally:
            self.connections.discard(websocket)


class MessageBroker:
    """Message Broker central para gerenciar comunicação inter-cluster"""
    
    def __init__(self):
        self.event_bus = EventBus()
        self.message_queue = MessageQueue()
        self.protocol_handlers: Dict[Protocol, ProtocolHandler] = {}
        self.running = False
        self.metrics = {
            'messages_received': 0,
            'messages_sent': 0,
            'protocol_errors': 0,
            'retry_attempts': 0
        }
        
        # Configurar handlers de protocolo
        self.protocol_handlers[Protocol.REST] = RESTProtocolHandler(self)
        self.protocol_handlers[Protocol.WEBSOCKET] = WebSocketProtocolHandler(self)
    
    async def start(self, 
                   rest_port: int = 8080, 
                   websocket_port: int = 8081):
        """Inicia o message broker"""
        if self.running:
            logger.warning("⚠️ Message Broker já está rodando")
            return
        
        self.running = True
        logger.info("🚀 Iniciando Message Broker...")
        
        # Iniciar handlers de protocolo
        await self.protocol_handlers[Protocol.REST].start(port=rest_port)
        await self.protocol_handlers[Protocol.WEBSOCKET].start(port=websocket_port)
        
        # Iniciar worker de processamento de mensagens
        asyncio.create_task(self._message_processor())
        asyncio.create_task(self._retry_processor())
        
        logger.info("✅ Message Broker iniciado com sucesso")
    
    async def stop(self):
        """Para o message broker"""
        if not self.running:
            return
        
        self.running = False
        logger.info("🛑 Parando Message Broker...")
        
        # Parar handlers de protocolo
        for handler in self.protocol_handlers.values():
            await handler.stop()
        
        logger.info("⏸️ Message Broker parado")
    
    async def send_message(self, 
                          message: Message, 
                          protocol: Protocol = Protocol.INTERNAL,
                          target_address: str = None) -> bool:
        """Envia mensagem usando protocolo especificado"""
        try:
            self.metrics['messages_sent'] += 1
            
            if protocol == Protocol.INTERNAL:
                # Comunicação interna via event bus
                await self.event_bus.publish(message)
                return True
            
            elif protocol in self.protocol_handlers and target_address:
                # Comunicação externa via protocolo específico
                handler = self.protocol_handlers[protocol]
                success = await handler.send_message(message, target_address)
                
                if not success and message.retries < message.max_retries:
                    # Adicionar à queue para retry
                    message.retries += 1
                    await self.message_queue.enqueue(message)
                    self.metrics['retry_attempts'] += 1
                
                return success
            
            else:
                logger.error(f"❌ Protocolo não suportado ou endereço não fornecido: {protocol}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem: {e}")
            self.metrics['protocol_errors'] += 1
            return False
    
    async def receive_message(self, message: Message, protocol: Protocol):
        """Recebe mensagem de protocolo externo"""
        try:
            self.metrics['messages_received'] += 1
            
            # Adicionar à queue de processamento
            await self.message_queue.enqueue(message)
            
            logger.debug(f"📥 Mensagem {message.id} recebida via {protocol.value}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao receber mensagem: {e}")
    
    def subscribe(self, 
                 pattern: str,
                 callback: Callable[[Message], Any],
                 cluster_id: str,
                 agent_id: str = None,
                 message_types: Set[MessageType] = None) -> str:
        """Inscreve-se para receber mensagens"""
        return self.event_bus.subscribe(
            pattern, callback, cluster_id, agent_id, message_types
        )
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove inscrição"""
        return self.event_bus.unsubscribe(subscription_id)
    
    async def _message_processor(self):
        """Processa mensagens da queue"""
        while self.running:
            try:
                message = await self.message_queue.dequeue(timeout=1.0)
                
                if message:
                    # Publicar no event bus para processamento interno
                    await self.event_bus.publish(message)
                    
            except Exception as e:
                logger.error(f"❌ Erro no processador de mensagens: {e}")
                await asyncio.sleep(1)
    
    async def _retry_processor(self):
        """Processa tentativas de retry"""
        while self.running:
            try:
                await asyncio.sleep(5)  # Verificar a cada 5 segundos
                
                # Aqui você poderia implementar lógica mais sofisticada
                # para processar mensagens que falharam
                
            except Exception as e:
                logger.error(f"❌ Erro no processador de retry: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas consolidadas"""
        return {
            'broker': self.metrics.copy(),
            'event_bus': self.event_bus.get_metrics(),
            'message_queue': self.message_queue.get_metrics(),
            'protocols': {
                protocol.value: {
                    'active': True,
                    'handler_type': type(handler).__name__
                }
                for protocol, handler in self.protocol_handlers.items()
            }
        }


# ==================== SINGLETON E UTILITÁRIOS ====================

_message_broker_instance = None

def get_message_broker() -> MessageBroker:
    """Retorna instância singleton do message broker"""
    global _message_broker_instance
    if _message_broker_instance is None:
        _message_broker_instance = MessageBroker()
    return _message_broker_instance


async def send_cluster_message(source_cluster: str,
                              target_cluster: str,
                              payload: Dict[str, Any],
                              message_type: MessageType = MessageType.COMMAND,
                              priority: MessagePriority = MessagePriority.NORMAL) -> bool:
    """Função utilitária para enviar mensagem entre clusters"""
    
    message = Message(
        type=message_type,
        priority=priority,
        source_cluster=source_cluster,
        target_cluster=target_cluster,
        payload=payload
    )
    
    broker = get_message_broker()
    return await broker.send_message(message, Protocol.INTERNAL)


if __name__ == "__main__":
    async def test_communication():
        """Teste do sistema de comunicação"""
        logger.info("🧪 Testando sistema de comunicação inter-cluster...")
        
        # Iniciar message broker
        broker = get_message_broker()
        await broker.start(rest_port=8080, websocket_port=8081)
        
        # Criar callback de teste
        received_messages = []
        
        def test_callback(message: Message):
            received_messages.append(message)
            logger.info(f"📨 Mensagem recebida: {message.payload}")
        
        # Inscrever-se para receber mensagens
        subscription_id = broker.subscribe(
            pattern="test.*",
            callback=test_callback,
            cluster_id="test_cluster"
        )
        
        # Enviar mensagens de teste
        test_messages = [
            {
                'source_cluster': 'core_cluster',
                'target_cluster': 'memory_cluster',
                'payload': {'action': 'test_message_1', 'data': 'hello'}
            },
            {
                'source_cluster': 'coordination_cluster',
                'target_cluster': 'analytics_cluster',
                'payload': {'action': 'test_message_2', 'data': 'world'}
            }
        ]
        
        for msg_data in test_messages:
            success = await send_cluster_message(**msg_data)
            logger.info(f"Mensagem enviada: {success}")
        
        # Aguardar processamento
        await asyncio.sleep(2)
        
        # Mostrar métricas
        metrics = broker.get_metrics()
        print(f"\n📊 MÉTRICAS:")
        print(f"Mensagens enviadas: {metrics['broker']['messages_sent']}")
        print(f"Mensagens recebidas: {metrics['broker']['messages_received']}")
        print(f"Mensagens processadas pelo event bus: {metrics['event_bus']['metrics']['messages_published']}")
        print(f"Mensagens recebidas no callback: {len(received_messages)}")
        
        # Cleanup
        broker.unsubscribe(subscription_id)
        await broker.stop()
        
        print("\n✅ Teste concluído!")
    
    # Executar teste
    asyncio.run(test_communication())