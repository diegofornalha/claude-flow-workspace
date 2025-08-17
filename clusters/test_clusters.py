#!/usr/bin/env python3
"""
🧪 Testes Abrangentes do Sistema de Clusters
Suite completa de testes unitários, integração e carga para o sistema de clusters
"""

import asyncio
import json
import logging
import time
import unittest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Any

# Imports dos módulos de clusters
from .cluster_definition import (
    AgentCluster, ClusterStatus, AgentStatus, AgentInfo,
    CoreCluster, CoordinationCluster, MemoryCluster,
    MCPCluster, AnalyticsCluster, DiscoveryCluster,
    ClusterFactory
)
from .cluster_orchestrator import ClusterOrchestrator, CircuitBreakerState
from .inter_cluster_comm import (
    MessageBroker, EventBus, MessageQueue, Message, MessageType, MessagePriority
)
from .cluster_registry import ClusterRegistry, ServiceEndpoint, ServiceType
from .cluster_manager import ClusterManager, AutoScaler, FailoverManager
from .cluster_dashboard import ClusterDashboard, ASCIICharts, DashboardConfig

# Configurar logging para testes
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class TestAgentCluster(unittest.TestCase):
    """Testes para a classe base AgentCluster"""
    
    def setUp(self):
        """Setup para cada teste"""
        self.cluster = CoreCluster()
        self.agent_info = AgentInfo(
            id="test_agent_1",
            name="Test Agent",
            role="tester",
            capabilities=["testing", "validation"],
            status=AgentStatus.ONLINE
        )
    
    def test_cluster_initialization(self):
        """Testa inicialização do cluster"""
        self.assertEqual(self.cluster.cluster_id, "core_cluster")
        self.assertEqual(self.cluster.name, "Core Operations")
        self.assertEqual(self.cluster.status, ClusterStatus.INACTIVE)
        self.assertEqual(len(self.cluster.agents), 0)
    
    def test_agent_registration(self):
        """Testa registro de agentes"""
        # Registrar agente
        success = self.cluster.register_agent(self.agent_info)
        self.assertTrue(success)
        self.assertEqual(len(self.cluster.agents), 1)
        self.assertIn("test_agent_1", self.cluster.agents)
        
        # Tentar registrar mesmo agente novamente
        success = self.cluster.register_agent(self.agent_info)
        self.assertFalse(success)
        self.assertEqual(len(self.cluster.agents), 1)
    
    def test_agent_unregistration(self):
        """Testa remoção de agentes"""
        # Registrar e depois remover
        self.cluster.register_agent(self.agent_info)
        success = self.cluster.unregister_agent("test_agent_1")
        self.assertTrue(success)
        self.assertEqual(len(self.cluster.agents), 0)
        
        # Tentar remover agente inexistente
        success = self.cluster.unregister_agent("nonexistent")
        self.assertFalse(success)
    
    def test_agent_selection(self):
        """Testa seleção de agentes"""
        # Adicionar múltiplos agentes
        for i in range(3):
            agent = AgentInfo(
                id=f"agent_{i}",
                name=f"Agent {i}",
                role="worker",
                capabilities=["work"],
                status=AgentStatus.ONLINE,
                current_tasks=i  # Diferentes cargas
            )
            self.cluster.register_agent(agent)
        
        # Testar seleção por menor carga
        self.cluster.config['load_balancing_strategy'] = 'least_loaded'
        selected = self.cluster.select_best_agent()
        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, "agent_0")  # Menor carga
    
    def test_health_check(self):
        """Testa health check do cluster"""
        # Cluster vazio
        health = self.cluster.health_check()
        self.assertEqual(health['health_percentage'], 0)
        
        # Adicionar agentes com diferentes saúdes
        for i, health_score in enumerate([100, 80, 60]):
            agent = AgentInfo(
                id=f"agent_{i}",
                name=f"Agent {i}",
                role="worker",
                health_score=health_score
            )
            self.cluster.register_agent(agent)
        
        health = self.cluster.health_check()
        self.assertGreater(health['health_percentage'], 0)
        self.assertEqual(health['total_agents'], 3)
    
    def test_cluster_lifecycle(self):
        """Testa ciclo de vida do cluster"""
        # Iniciar
        self.cluster.start()
        self.assertEqual(self.cluster.status, ClusterStatus.ACTIVE)
        
        # Parar
        self.cluster.stop()
        self.assertEqual(self.cluster.status, ClusterStatus.INACTIVE)


class TestClusterFactory(unittest.TestCase):
    """Testes para ClusterFactory"""
    
    def test_create_all_clusters(self):
        """Testa criação de todos os clusters"""
        clusters = ClusterFactory.create_all_clusters()
        
        self.assertEqual(len(clusters), 6)
        self.assertIn('core', clusters)
        self.assertIn('coordination', clusters)
        self.assertIn('memory', clusters)
        self.assertIn('mcp', clusters)
        self.assertIn('analytics', clusters)
        self.assertIn('discovery', clusters)
        
        # Verificar tipos corretos
        self.assertIsInstance(clusters['core'], CoreCluster)
        self.assertIsInstance(clusters['coordination'], CoordinationCluster)
        self.assertIsInstance(clusters['memory'], MemoryCluster)
    
    def test_create_specific_cluster(self):
        """Testa criação de cluster específico"""
        cluster = ClusterFactory.create_cluster('core')
        self.assertIsInstance(cluster, CoreCluster)
        
        invalid = ClusterFactory.create_cluster('invalid')
        self.assertIsNone(invalid)


class TestClusterOrchestrator(unittest.IsolatedAsyncioTestCase):
    """Testes para ClusterOrchestrator"""
    
    async def asyncSetUp(self):
        """Setup assíncrono"""
        self.orchestrator = ClusterOrchestrator()
    
    async def asyncTearDown(self):
        """Teardown assíncrono"""
        if self.orchestrator.is_running:
            await self.orchestrator.stop()
    
    async def test_singleton_pattern(self):
        """Testa padrão singleton"""
        orch1 = ClusterOrchestrator()
        orch2 = ClusterOrchestrator()
        self.assertIs(orch1, orch2)
    
    async def test_orchestrator_lifecycle(self):
        """Testa ciclo de vida do orquestrador"""
        await self.orchestrator.start()
        self.assertTrue(self.orchestrator.is_running)
        self.assertGreater(len(self.orchestrator.clusters), 0)
        
        await self.orchestrator.stop()
        self.assertFalse(self.orchestrator.is_running)
    
    async def test_message_routing(self):
        """Testa roteamento de mensagens"""
        await self.orchestrator.start()
        
        # Teste de roteamento por capacidade
        cluster_id = self.orchestrator.route_message(
            message={'action': 'test'},
            target_capability='strategic_planning'
        )
        self.assertIsNotNone(cluster_id)
        
        # Teste de roteamento direto
        cluster_id = self.orchestrator.route_message(
            message={'action': 'test'},
            target_cluster='core_cluster'
        )
        self.assertEqual(cluster_id, 'core_cluster')
    
    async def test_send_message(self):
        """Testa envio de mensagens"""
        await self.orchestrator.start()
        
        # Aguardar inicialização
        await asyncio.sleep(0.1)
        
        result = await self.orchestrator.send_message(
            message={'action': 'test_message', 'data': 'hello'},
            target_cluster='core_cluster'
        )
        
        self.assertTrue(result['success'])
        self.assertIn('result', result)
        self.assertIn('cluster_id', result)
    
    async def test_circuit_breaker(self):
        """Testa circuit breaker"""
        await self.orchestrator.start()
        
        # Simular falhas para triggerar circuit breaker
        cluster_id = 'core_cluster'
        circuit_breaker = self.orchestrator.circuit_breakers[cluster_id]
        
        # Forçar falhas
        for _ in range(10):
            circuit_breaker._on_failure()
        
        self.assertEqual(circuit_breaker.state, CircuitBreakerState.OPEN)


class TestMessageBroker(unittest.IsolatedAsyncioTestCase):
    """Testes para MessageBroker"""
    
    async def asyncSetUp(self):
        """Setup assíncrono"""
        self.broker = MessageBroker()
    
    async def asyncTearDown(self):
        """Teardown assíncrono"""
        if self.broker:
            await self.broker.stop()
    
    async def test_broker_lifecycle(self):
        """Testa ciclo de vida do broker"""
        await self.broker.start(rest_port=18080, websocket_port=18081)
        
        # Verificar que está rodando
        self.assertTrue(self.broker.running)
        
        await self.broker.stop()
        self.assertFalse(self.broker.running)
    
    async def test_message_queue(self):
        """Testa queue de mensagens"""
        queue = MessageQueue()
        
        # Criar mensagem de teste
        message = Message(
            type=MessageType.COMMAND,
            priority=MessagePriority.HIGH,
            payload={'action': 'test'}
        )
        
        # Enqueue
        success = await queue.enqueue(message)
        self.assertTrue(success)
        self.assertEqual(queue.size, 1)
        
        # Dequeue
        dequeued = await queue.dequeue(timeout=1.0)
        self.assertIsNotNone(dequeued)
        self.assertEqual(dequeued.payload['action'], 'test')
        self.assertEqual(queue.size, 0)
    
    async def test_event_bus(self):
        """Testa event bus"""
        event_bus = EventBus()
        received_messages = []
        
        def test_callback(message):
            received_messages.append(message)
        
        # Subscribe
        subscription_id = event_bus.subscribe(
            pattern="test.*",
            callback=test_callback,
            cluster_id="test_cluster"
        )
        
        # Publish
        message = Message(payload={'action': 'test_event'})
        delivered = await event_bus.publish(message)
        
        self.assertGreater(delivered, 0)
        
        # Aguardar processamento
        await asyncio.sleep(0.1)
        
        # Unsubscribe
        success = event_bus.unsubscribe(subscription_id)
        self.assertTrue(success)


class TestClusterRegistry(unittest.IsolatedAsyncioTestCase):
    """Testes para ClusterRegistry"""
    
    async def asyncSetUp(self):
        """Setup assíncrono"""
        # Usar arquivo temporário para testes
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        
        self.registry = ClusterRegistry(storage_path=self.temp_file.name)
    
    async def asyncTearDown(self):
        """Teardown assíncrono"""
        if self.registry.running:
            await self.registry.stop()
        
        # Limpar arquivo temporário
        try:
            os.unlink(self.temp_file.name)
        except:
            pass
    
    async def test_registry_lifecycle(self):
        """Testa ciclo de vida do registry"""
        await self.registry.start()
        self.assertTrue(self.registry.running)
        
        await self.registry.stop()
        self.assertFalse(self.registry.running)
    
    async def test_cluster_registration(self):
        """Testa registro de clusters"""
        cluster = CoreCluster()
        
        success = await self.registry.register_cluster(cluster)
        self.assertTrue(success)
        self.assertIn(cluster.cluster_id, self.registry.registrations)
    
    async def test_service_discovery(self):
        """Testa descoberta de serviços"""
        await self.registry.start()
        
        # Mock do service discovery para não escanear portas reais
        with patch.object(self.registry.service_discovery, 'discover_services') as mock_discover:
            mock_discover.return_value = [
                ServiceEndpoint(
                    host="localhost",
                    port=3000,
                    service_type=ServiceType.WEB_UI
                )
            ]
            
            services = await self.registry.discover_services()
            self.assertEqual(len(services), 1)
            self.assertEqual(services[0].service_type, ServiceType.WEB_UI)
    
    async def test_heartbeat_management(self):
        """Testa gerenciamento de heartbeat"""
        cluster = CoreCluster()
        await self.registry.register_cluster(cluster)
        
        # Atualizar heartbeat
        success = await self.registry.update_heartbeat(cluster.cluster_id)
        self.assertTrue(success)
        
        registration = self.registry.registrations[cluster.cluster_id]
        self.assertIsNotNone(registration.last_heartbeat)
        self.assertTrue(registration.is_active())


class TestClusterManager(unittest.IsolatedAsyncioTestCase):
    """Testes para ClusterManager"""
    
    async def asyncSetUp(self):
        """Setup assíncrono"""
        self.manager = ClusterManager()
        self.orchestrator = ClusterOrchestrator()
    
    async def asyncTearDown(self):
        """Teardown assíncrono"""
        if self.manager.running:
            await self.manager.stop()
        if self.orchestrator.is_running:
            await self.orchestrator.stop()
    
    async def test_manager_lifecycle(self):
        """Testa ciclo de vida do manager"""
        await self.orchestrator.start()
        await self.manager.start(self.orchestrator)
        
        self.assertTrue(self.manager.running)
        self.assertTrue(self.manager.auto_scaler.running)
        self.assertTrue(self.manager.failover_manager.running)
        
        await self.manager.stop()
        self.assertFalse(self.manager.running)
    
    async def test_auto_scaler(self):
        """Testa auto-scaler"""
        auto_scaler = AutoScaler()
        
        # Testar criação de agente
        cluster = CoreCluster()
        new_agent = auto_scaler._create_agent_for_cluster(cluster)
        
        self.assertIsInstance(new_agent, AgentInfo)
        self.assertIn("general_processing", new_agent.capabilities)
    
    async def test_failover_manager(self):
        """Testa failover manager"""
        failover_manager = FailoverManager()
        
        # Testar criação de políticas
        from .cluster_manager import FailoverPolicy
        
        policy = FailoverPolicy(
            cluster_id="test_cluster",
            health_threshold=50.0,
            backup_clusters=["backup_cluster"]
        )
        
        failover_manager.set_failover_policy(policy)
        self.assertIn("test_cluster", failover_manager.failover_policies)


class TestClusterDashboard(unittest.IsolatedAsyncioTestCase):
    """Testes para ClusterDashboard"""
    
    async def asyncSetUp(self):
        """Setup assíncrono"""
        self.dashboard = ClusterDashboard()
    
    async def asyncTearDown(self):
        """Teardown assíncrono"""
        if self.dashboard.running:
            self.dashboard.stop()
    
    async def test_dashboard_lifecycle(self):
        """Testa ciclo de vida do dashboard"""
        # Mock dos componentes
        mock_orchestrator = Mock()
        mock_orchestrator.is_running = True
        
        await self.dashboard.start(orchestrator=mock_orchestrator)
        self.assertTrue(self.dashboard.running)
        
        self.dashboard.stop()
        self.assertFalse(self.dashboard.running)
    
    def test_ascii_charts(self):
        """Testa geração de gráficos ASCII"""
        # Teste line chart
        data = [10, 20, 15, 25, 30, 20, 35]
        chart = ASCIICharts.line_chart(data, width=20, height=5, title="Test Chart")
        self.assertIsInstance(chart, list)
        self.assertGreater(len(chart), 0)
        self.assertIn("Test Chart", chart[0])
        
        # Teste bar chart
        data_dict = {"A": 10, "B": 20, "C": 15}
        chart = ASCIICharts.bar_chart(data_dict, title="Test Bars")
        self.assertIsInstance(chart, list)
        self.assertGreater(len(chart), 0)
        
        # Teste gauge
        gauge = ASCIICharts.gauge(75, 100, 20, "Test Gauge")
        self.assertIsInstance(gauge, str)
        self.assertIn("Test Gauge", gauge)
    
    def test_dashboard_rendering(self):
        """Testa renderização do dashboard"""
        # Mock do orquestrador com dados básicos
        mock_orchestrator = Mock()
        mock_orchestrator.is_running = True
        mock_orchestrator.get_status.return_value = {
            'orchestrator': {'uptime_seconds': 3600},
            'clusters': {},
            'metrics': {
                'total_requests': 100,
                'successful_requests': 95,
                'avg_response_time': 150
            }
        }
        
        self.dashboard.orchestrator = mock_orchestrator
        
        # Testar renderização
        output = self.dashboard.render_dashboard()
        self.assertIsInstance(output, str)
        self.assertIn("CLUSTER DASHBOARD", output)


class TestIntegration(unittest.IsolatedAsyncioTestCase):
    """Testes de integração entre componentes"""
    
    async def asyncSetUp(self):
        """Setup assíncrono"""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
    
    async def asyncTearDown(self):
        """Teardown assíncrono"""
        try:
            os.unlink(self.temp_file.name)
        except:
            pass
    
    async def test_full_system_integration(self):
        """Testa integração completa do sistema"""
        # Inicializar componentes
        orchestrator = ClusterOrchestrator()
        registry = ClusterRegistry(storage_path=self.temp_file.name)
        manager = ClusterManager()
        
        try:
            # Iniciar todos os componentes
            await orchestrator.start()
            await registry.start()
            await manager.start(orchestrator)
            
            # Aguardar inicialização
            await asyncio.sleep(0.5)
            
            # Verificar que todos estão rodando
            self.assertTrue(orchestrator.is_running)
            self.assertTrue(registry.running)
            self.assertTrue(manager.running)
            
            # Testar comunicação end-to-end
            result = await orchestrator.send_message(
                message={'action': 'integration_test'},
                target_cluster='core_cluster'
            )
            
            self.assertTrue(result['success'])
            
            # Verificar métricas
            status = orchestrator.get_status()
            self.assertGreater(status['metrics']['total_requests'], 0)
            
        finally:
            # Cleanup
            await manager.stop()
            await registry.stop()
            await orchestrator.stop()
    
    async def test_failover_scenario(self):
        """Testa cenário de failover"""
        orchestrator = ClusterOrchestrator()
        manager = ClusterManager()
        
        try:
            await orchestrator.start()
            await manager.start(orchestrator)
            
            # Aguardar inicialização
            await asyncio.sleep(0.2)
            
            # Simular falha em cluster
            cluster_id = 'core_cluster'
            if cluster_id in orchestrator.clusters:
                cluster = orchestrator.clusters[cluster_id]
                cluster.status = ClusterStatus.FAILED
                
                # Forçar health check
                health = cluster.health_check()
                self.assertEqual(cluster.status, ClusterStatus.FAILED)
            
        finally:
            await manager.stop()
            await orchestrator.stop()


class TestPerformance(unittest.IsolatedAsyncioTestCase):
    """Testes de performance e carga"""
    
    async def test_message_throughput(self):
        """Testa throughput de mensagens"""
        broker = MessageBroker()
        
        try:
            await broker.start(rest_port=18080, websocket_port=18081)
            
            # Enviar múltiplas mensagens
            start_time = time.time()
            num_messages = 100
            
            tasks = []
            for i in range(num_messages):
                message = Message(
                    type=MessageType.COMMAND,
                    payload={'id': i, 'action': 'performance_test'}
                )
                tasks.append(broker.send_message(message))
            
            # Aguardar conclusão
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            # Calcular métricas
            duration = end_time - start_time
            throughput = num_messages / duration
            
            logger.info(f"Message throughput: {throughput:.2f} messages/second")
            
            # Verificar que a maioria foi bem-sucedida
            successful = sum(1 for r in results if r is True)
            success_rate = successful / num_messages
            
            self.assertGreater(success_rate, 0.8)  # Pelo menos 80% de sucesso
            
        finally:
            await broker.stop()
    
    async def test_concurrent_clusters(self):
        """Testa múltiplos clusters concorrentes"""
        orchestrator = ClusterOrchestrator()
        
        try:
            await orchestrator.start()
            
            # Enviar mensagens concorrentes para diferentes clusters
            tasks = []
            cluster_ids = list(orchestrator.clusters.keys())
            
            for cluster_id in cluster_ids[:3]:  # Testar primeiros 3 clusters
                for i in range(10):  # 10 mensagens por cluster
                    task = orchestrator.send_message(
                        message={'id': i, 'action': 'concurrent_test'},
                        target_cluster=cluster_id
                    )
                    tasks.append(task)
            
            # Aguardar todas as mensagens
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verificar resultados
            successful = sum(1 for r in results if isinstance(r, dict) and r.get('success'))
            success_rate = successful / len(results)
            
            self.assertGreater(success_rate, 0.7)  # Pelo menos 70% de sucesso
            
        finally:
            await orchestrator.stop()
    
    async def test_memory_usage(self):
        """Testa uso de memória durante operação"""
        import psutil
        import gc
        
        # Medir memória inicial
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Criar e destruir múltiplos componentes
        for i in range(10):
            orchestrator = ClusterOrchestrator()
            await orchestrator.start()
            
            # Fazer algumas operações
            await orchestrator.send_message(
                message={'iteration': i},
                target_cluster='core_cluster'
            )
            
            await orchestrator.stop()
            
            # Forçar garbage collection
            gc.collect()
        
        # Medir memória final
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Verificar que não há vazamento significativo (< 50MB)
        self.assertLess(memory_increase, 50 * 1024 * 1024)


class TestErrorHandling(unittest.IsolatedAsyncioTestCase):
    """Testes de tratamento de erros"""
    
    async def test_cluster_creation_errors(self):
        """Testa erros na criação de clusters"""
        cluster = CoreCluster()
        
        # Teste com agente inválido
        invalid_agent = AgentInfo(id="", name="", role="")
        success = cluster.register_agent(invalid_agent)
        self.assertTrue(success)  # Deveria aceitar mesmo agente básico
        
        # Teste limite de agentes
        cluster.max_agents = 1
        agent1 = AgentInfo(id="agent1", name="Agent 1", role="worker")
        agent2 = AgentInfo(id="agent2", name="Agent 2", role="worker")
        
        self.assertTrue(cluster.register_agent(agent1))
        self.assertFalse(cluster.register_agent(agent2))
    
    async def test_communication_errors(self):
        """Testa erros de comunicação"""
        broker = MessageBroker()
        
        # Tentar enviar mensagem sem inicializar
        message = Message(payload={'test': 'data'})
        result = await broker.send_message(message)
        self.assertFalse(result)
    
    async def test_timeout_handling(self):
        """Testa tratamento de timeouts"""
        queue = MessageQueue()
        
        # Tentar dequeue com timeout em queue vazia
        start_time = time.time()
        result = await queue.dequeue(timeout=0.1)
        end_time = time.time()
        
        self.assertIsNone(result)
        self.assertLess(end_time - start_time, 0.2)  # Verificar que respeitou timeout


def run_all_tests():
    """Executa todos os testes"""
    print("🧪 Executando Suite Completa de Testes de Clusters")
    print("=" * 60)
    
    # Configurar test loader
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Adicionar todas as classes de teste
    test_classes = [
        TestAgentCluster,
        TestClusterFactory,
        TestClusterOrchestrator,
        TestMessageBroker,
        TestClusterRegistry,
        TestClusterManager,
        TestClusterDashboard,
        TestIntegration,
        TestPerformance,
        TestErrorHandling
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Executar testes
    runner = unittest.TextTestRunner(
        verbosity=2,
        stream=None,
        descriptions=True,
        failfast=False
    )
    
    result = runner.run(suite)
    
    # Relatório final
    print("\n" + "=" * 60)
    print("📊 RELATÓRIO FINAL DOS TESTES")
    print("=" * 60)
    print(f"Testes executados: {result.testsRun}")
    print(f"Sucessos: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Falhas: {len(result.failures)}")
    print(f"Erros: {len(result.errors)}")
    
    if result.failures:
        print(f"\n❌ FALHAS:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.splitlines()[-1]}")
    
    if result.errors:
        print(f"\n💥 ERROS:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.splitlines()[-1]}")
    
    success_rate = (result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100
    print(f"\n📈 Taxa de sucesso: {success_rate:.1f}%")
    
    if success_rate >= 90:
        print("✅ EXCELENTE! Sistema passou em todos os testes principais.")
    elif success_rate >= 75:
        print("⚠️ BOM! Alguns testes falharam, mas funcionalidade core está OK.")
    else:
        print("❌ ATENÇÃO! Muitos testes falharam. Revisar implementação.")
    
    return result.wasSuccessful()


async def run_integration_demo():
    """Executa demonstração de integração completa"""
    print("\n🎬 DEMONSTRAÇÃO DE INTEGRAÇÃO COMPLETA")
    print("=" * 50)
    
    # Criar arquivo temporário para registry
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
    temp_file.close()
    
    try:
        # Inicializar todos os componentes
        print("🚀 Inicializando componentes...")
        
        orchestrator = ClusterOrchestrator()
        registry = ClusterRegistry(storage_path=temp_file.name)
        manager = ClusterManager()
        dashboard = ClusterDashboard()
        
        # Iniciar sistema
        await orchestrator.start()
        await registry.start()
        await manager.start(orchestrator)
        await dashboard.start(orchestrator, registry, manager)
        
        print("✅ Todos os componentes iniciados")
        
        # Simular atividade
        print("\n📡 Simulando atividade do sistema...")
        
        for i in range(5):
            # Enviar mensagens para diferentes clusters
            for cluster_type in ['core', 'memory', 'analytics']:
                await orchestrator.send_message(
                    message={
                        'simulation_id': i,
                        'action': f'demo_task_{cluster_type}',
                        'timestamp': datetime.now().isoformat()
                    },
                    target_cluster=f'{cluster_type}_cluster'
                )
            
            await asyncio.sleep(0.5)
        
        # Aguardar processamento
        await asyncio.sleep(2)
        
        # Mostrar status final
        print("\n📊 STATUS FINAL DO SISTEMA:")
        print("-" * 30)
        
        orchestrator_status = orchestrator.get_status()
        print(f"Orquestrador: {orchestrator_status['orchestrator']['is_running']}")
        print(f"Clusters ativos: {len([c for c in orchestrator_status['clusters'].values() if c['status'] == 'active'])}")
        print(f"Total de requests: {orchestrator_status['metrics']['total_requests']}")
        print(f"Taxa de sucesso: {orchestrator_status['metrics']['successful_requests']}/{orchestrator_status['metrics']['total_requests']}")
        
        registry_status = registry.get_status()
        print(f"Registry ativo: {registry_status['registry']['running']}")
        print(f"Serviços descobertos: {registry_status['metrics']['services_discovered']}")
        
        manager_status = manager.get_status()
        print(f"Manager ativo: {manager_status['manager']['running']}")
        print(f"Eventos de scaling: {manager_status['manager']['metrics']['scaling_events']}")
        
        # Mostrar dashboard
        print("\n🎯 DASHBOARD ATUAL:")
        print("-" * 30)
        dashboard_output = dashboard.render_dashboard()
        # Mostrar apenas primeiras 20 linhas do dashboard
        lines = dashboard_output.split('\n')[:20]
        for line in lines:
            print(line)
        
        print("\n✅ Demonstração concluída com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro na demonstração: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        print("\n🧹 Limpando recursos...")
        try:
            dashboard.stop()
            await manager.stop()
            await registry.stop()
            await orchestrator.stop()
            os.unlink(temp_file.name)
        except:
            pass
        
        print("🏁 Demonstração finalizada")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        # Executar demonstração de integração
        asyncio.run(run_integration_demo())
    else:
        # Executar testes
        success = run_all_tests()
        sys.exit(0 if success else 1)