#!/usr/bin/env python3
"""
📊 Dashboard de Clusters - Visualização em Tempo Real
Implementação de dashboard interativo para monitoramento de clusters com gráficos ASCII
"""

import asyncio
import json
import logging
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import statistics
import shutil

from .cluster_definition import AgentCluster, ClusterStatus, AgentStatus
from .cluster_orchestrator import ClusterOrchestrator, get_orchestrator
from .cluster_registry import ClusterRegistry, get_cluster_registry
from .cluster_manager import ClusterManager, get_cluster_manager

# Configurar logging
logger = logging.getLogger(__name__)


class DashboardMode(Enum):
    """Modos de visualização do dashboard"""
    OVERVIEW = "overview"
    DETAILED = "detailed"
    METRICS = "metrics"
    LOGS = "logs"
    TOPOLOGY = "topology"


@dataclass
class DashboardConfig:
    """Configurações do dashboard"""
    refresh_interval: int = 5  # segundos
    max_history_points: int = 100
    terminal_width: int = 120
    terminal_height: int = 40
    enable_colors: bool = True
    auto_scroll: bool = True
    show_timestamps: bool = True
    compact_mode: bool = False


class ASCIICharts:
    """Gerador de gráficos ASCII"""
    
    @staticmethod
    def line_chart(data: List[float], 
                   width: int = 60, 
                   height: int = 10,
                   title: str = "",
                   y_label: str = "",
                   min_val: float = None,
                   max_val: float = None) -> List[str]:
        """Gera gráfico de linha ASCII"""
        
        if not data:
            return [f"📈 {title}", "   (sem dados)"]
        
        # Normalizar dados
        if min_val is None:
            min_val = min(data)
        if max_val is None:
            max_val = max(data)
        
        if max_val == min_val:
            max_val = min_val + 1
        
        # Redimensionar dados para largura
        if len(data) > width:
            step = len(data) // width
            data = data[::step][:width]
        elif len(data) < width:
            # Interpolar dados
            factor = width / len(data)
            new_data = []
            for i in range(width):
                idx = int(i / factor)
                if idx >= len(data):
                    idx = len(data) - 1
                new_data.append(data[idx])
            data = new_data
        
        # Gerar gráfico
        lines = []
        if title:
            lines.append(f"📈 {title}")
        
        # Escala Y
        for y in range(height - 1, -1, -1):
            threshold = min_val + (max_val - min_val) * y / (height - 1)
            line = f"{threshold:6.1f}│"
            
            for i, value in enumerate(data):
                if value >= threshold:
                    # Escolher caractere baseado na proximidade
                    if abs(value - threshold) < (max_val - min_val) / (height * 2):
                        line += "●"
                    else:
                        line += "█"
                else:
                    line += " "
            
            line += "│"
            lines.append(line)
        
        # Linha base
        base_line = "      └" + "─" * width + "┘"
        lines.append(base_line)
        
        # Labels do eixo X (timepoints)
        if len(data) > 10:
            x_labels = "        "
            step = width // 10
            for i in range(0, width, step):
                x_labels += f"{i:>3}"
                x_labels += " " * (step - 3)
            lines.append(x_labels)
        
        return lines
    
    @staticmethod
    def bar_chart(data: Dict[str, float], 
                  width: int = 50,
                  title: str = "",
                  show_values: bool = True) -> List[str]:
        """Gera gráfico de barras ASCII"""
        
        if not data:
            return [f"📊 {title}", "   (sem dados)"]
        
        lines = []
        if title:
            lines.append(f"📊 {title}")
        
        max_val = max(data.values()) if data.values() else 1
        max_label_len = max(len(str(k)) for k in data.keys()) if data else 0
        
        for label, value in data.items():
            # Calcular comprimento da barra
            bar_length = int((value / max_val) * width) if max_val > 0 else 0
            
            # Gerar barra
            bar = "█" * bar_length
            spaces = " " * (width - bar_length)
            
            # Formattar linha
            if show_values:
                line = f"{label:>{max_label_len}} │{bar}{spaces}│ {value:6.1f}"
            else:
                line = f"{label:>{max_label_len}} │{bar}{spaces}│"
            
            lines.append(line)
        
        return lines
    
    @staticmethod
    def gauge(value: float, 
              max_value: float = 100, 
              width: int = 40,
              label: str = "",
              unit: str = "%") -> str:
        """Gera gauge ASCII"""
        
        percentage = (value / max_value) * 100 if max_value > 0 else 0
        filled = int((percentage / 100) * width)
        empty = width - filled
        
        # Escolher cor/caractere baseado no valor
        if percentage >= 80:
            fill_char = "█"  # Crítico
        elif percentage >= 60:
            fill_char = "▓"  # Alto
        elif percentage >= 40:
            fill_char = "▒"  # Médio
        else:
            fill_char = "░"  # Baixo
        
        bar = fill_char * filled + "─" * empty
        
        return f"{label} [{bar}] {value:.1f}{unit}"
    
    @staticmethod
    def topology_diagram(clusters: Dict[str, Any], 
                        connections: List[Tuple[str, str]],
                        width: int = 80) -> List[str]:
        """Gera diagrama de topologia ASCII"""
        
        if not clusters:
            return ["🌐 Topologia", "   (nenhum cluster)"]
        
        lines = ["🌐 Topologia de Clusters"]
        lines.append("")
        
        # Layout simples em grid
        cluster_ids = list(clusters.keys())
        cols = min(3, len(cluster_ids))
        rows = (len(cluster_ids) + cols - 1) // cols
        
        grid = {}
        for i, cluster_id in enumerate(cluster_ids):
            row = i // cols
            col = i % cols
            grid[(row, col)] = cluster_id
        
        # Gerar grid
        for row in range(rows):
            line = ""
            for col in range(cols):
                if (row, col) in grid:
                    cluster_id = grid[(row, col)]
                    cluster = clusters[cluster_id]
                    status = cluster.get('status', 'unknown')
                    agent_count = len(cluster.get('agents', {}))
                    
                    # Escolher ícone baseado no status
                    if status == 'active':
                        icon = "🟢"
                    elif status == 'degraded':
                        icon = "🟡"
                    elif status == 'failed':
                        icon = "🔴"
                    else:
                        icon = "⚪"
                    
                    # Formatar nó
                    node = f"{icon} {cluster_id[:12]:<12} ({agent_count})"
                    line += f"{node:<25}"
                else:
                    line += " " * 25
            
            lines.append(line)
        
        # Mostrar conexões (simplificado)
        if connections:
            lines.append("")
            lines.append("🔗 Conexões:")
            for source, target in connections[:10]:  # Limitar a 10
                lines.append(f"   {source} ←→ {target}")
        
        return lines


class MetricsCalculator:
    """Calculador de métricas para o dashboard"""
    
    @staticmethod
    def calculate_cluster_health(cluster_data: Dict[str, Any]) -> float:
        """Calcula saúde geral do cluster"""
        if not cluster_data.get('agents'):
            return 0.0
        
        agent_healths = []
        for agent in cluster_data['agents'].values():
            health_score = agent.get('health_score', 100.0)
            agent_healths.append(health_score)
        
        return statistics.mean(agent_healths) if agent_healths else 0.0
    
    @staticmethod
    def calculate_load_distribution(clusters: Dict[str, Any]) -> Dict[str, float]:
        """Calcula distribuição de carga entre clusters"""
        load_data = {}
        
        for cluster_id, cluster in clusters.items():
            agents = cluster.get('agents', {})
            if not agents:
                load_data[cluster_id] = 0.0
                continue
            
            total_tasks = sum(agent.get('current_tasks', 0) for agent in agents.values())
            max_capacity = sum(agent.get('max_concurrent_tasks', 5) for agent in agents.values())
            
            load_percentage = (total_tasks / max_capacity * 100) if max_capacity > 0 else 0.0
            load_data[cluster_id] = load_percentage
        
        return load_data
    
    @staticmethod
    def calculate_response_times(orchestrator_stats: Dict[str, Any]) -> Dict[str, float]:
        """Calcula tempos de resposta por cluster"""
        response_times = {}
        
        load_balancing = orchestrator_stats.get('load_balancing', {})
        for cluster_id, stats in load_balancing.items():
            response_times[cluster_id] = stats.get('avg_response_time', 0.0)
        
        return response_times
    
    @staticmethod
    def get_trending_direction(values: List[float]) -> str:
        """Determina direção da tendência"""
        if len(values) < 2:
            return "→"
        
        recent = values[-min(5, len(values)):]
        if len(recent) < 2:
            return "→"
        
        slope = (recent[-1] - recent[0]) / len(recent)
        
        if slope > 0.1:
            return "↗"
        elif slope < -0.1:
            return "↘"
        else:
            return "→"


class ClusterDashboard:
    """Dashboard principal para visualização de clusters"""
    
    def __init__(self, config: DashboardConfig = None):
        self.config = config or DashboardConfig()
        self.mode = DashboardMode.OVERVIEW
        self.running = False
        
        # Histórico de métricas
        self.metrics_history = defaultdict(lambda: deque(maxlen=self.config.max_history_points))
        self.last_update = datetime.now()
        
        # Componentes
        self.orchestrator = None
        self.registry = None
        self.manager = None
        
        # Buffer de logs
        self.log_buffer = deque(maxlen=1000)
        
        # Terminal dimensions
        self.update_terminal_size()
    
    def update_terminal_size(self):
        """Atualiza dimensões do terminal"""
        try:
            size = shutil.get_terminal_size()
            self.config.terminal_width = size.columns
            self.config.terminal_height = size.lines
        except:
            # Usar valores padrão se não conseguir detectar
            pass
    
    async def start(self, 
                   orchestrator: ClusterOrchestrator = None,
                   registry: ClusterRegistry = None,
                   manager: ClusterManager = None):
        """Inicia o dashboard"""
        
        if self.running:
            logger.warning("⚠️ Dashboard já está rodando")
            return
        
        self.running = True
        
        # Usar instâncias padrão se não fornecidas
        self.orchestrator = orchestrator or get_orchestrator()
        self.registry = registry or get_cluster_registry()
        self.manager = manager or get_cluster_manager()
        
        logger.info("🚀 Iniciando Cluster Dashboard...")
        
        # Iniciar coleta de métricas
        asyncio.create_task(self._metrics_collection_loop())
        
        logger.info("✅ Dashboard iniciado")
    
    def stop(self):
        """Para o dashboard"""
        self.running = False
        logger.info("⏸️ Dashboard parado")
    
    async def _metrics_collection_loop(self):
        """Loop de coleta de métricas"""
        while self.running:
            try:
                await self._collect_metrics()
                await asyncio.sleep(self.config.refresh_interval)
            except Exception as e:
                logger.error(f"❌ Erro na coleta de métricas do dashboard: {e}")
                await asyncio.sleep(5)
    
    async def _collect_metrics(self):
        """Coleta métricas dos componentes"""
        timestamp = datetime.now()
        
        # Métricas do orquestrador
        if self.orchestrator and self.orchestrator.is_running:
            orchestrator_status = self.orchestrator.get_status()
            
            # Armazenar métricas gerais
            self.metrics_history['total_requests'].append(
                (timestamp, orchestrator_status['metrics']['total_requests'])
            )
            self.metrics_history['successful_requests'].append(
                (timestamp, orchestrator_status['metrics']['successful_requests'])
            )
            self.metrics_history['avg_response_time'].append(
                (timestamp, orchestrator_status['metrics']['avg_response_time'])
            )
            
            # Métricas por cluster
            for cluster_id, cluster_data in orchestrator_status['clusters'].items():
                health = MetricsCalculator.calculate_cluster_health(cluster_data)
                self.metrics_history[f'{cluster_id}_health'].append((timestamp, health))
                
                agent_count = len(cluster_data.get('agents', {}))
                self.metrics_history[f'{cluster_id}_agents'].append((timestamp, agent_count))
        
        # Métricas do registry
        if self.registry and self.registry.running:
            registry_status = self.registry.get_status()
            
            self.metrics_history['services_discovered'].append(
                (timestamp, registry_status['metrics']['services_discovered'])
            )
            self.metrics_history['active_clusters'].append(
                (timestamp, registry_status['registry']['active_clusters'])
            )
        
        # Métricas do manager
        if self.manager and self.manager.running:
            manager_status = self.manager.get_status()
            
            self.metrics_history['scaling_events'].append(
                (timestamp, manager_status['manager']['metrics']['scaling_events'])
            )
            self.metrics_history['failover_events'].append(
                (timestamp, manager_status['manager']['metrics']['failover_events'])
            )
        
        self.last_update = timestamp
    
    def render_dashboard(self) -> str:
        """Renderiza dashboard completo"""
        self.update_terminal_size()
        
        lines = []
        
        # Header
        lines.extend(self._render_header())
        lines.append("")
        
        # Conteúdo baseado no modo
        if self.mode == DashboardMode.OVERVIEW:
            lines.extend(self._render_overview())
        elif self.mode == DashboardMode.DETAILED:
            lines.extend(self._render_detailed())
        elif self.mode == DashboardMode.METRICS:
            lines.extend(self._render_metrics())
        elif self.mode == DashboardMode.TOPOLOGY:
            lines.extend(self._render_topology())
        elif self.mode == DashboardMode.LOGS:
            lines.extend(self._render_logs())
        
        # Footer
        lines.append("")
        lines.extend(self._render_footer())
        
        # Limitar altura
        max_lines = self.config.terminal_height - 2
        if len(lines) > max_lines:
            lines = lines[:max_lines]
        
        return "\n".join(lines)
    
    def _render_header(self) -> List[str]:
        """Renderiza cabeçalho"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Título centralizado
        title = "🎯 CLUSTER DASHBOARD v2.0"
        padding = (self.config.terminal_width - len(title)) // 2
        title_line = " " * padding + title
        
        # Status geral
        status_items = []
        if self.orchestrator and self.orchestrator.is_running:
            status_items.append("🎼 Orchestrator")
        if self.registry and self.registry.running:
            status_items.append("📋 Registry")
        if self.manager and self.manager.running:
            status_items.append("⚡ Manager")
        
        status_line = f"Status: {' | '.join(status_items)} | {now}"
        
        return [
            "═" * self.config.terminal_width,
            title_line,
            f"Mode: {self.mode.value.upper()} | {status_line}",
            "═" * self.config.terminal_width
        ]
    
    def _render_overview(self) -> List[str]:
        """Renderiza visão geral"""
        lines = []
        
        if not self.orchestrator or not self.orchestrator.is_running:
            return ["⚠️ Orquestrador não está rodando"]
        
        status = self.orchestrator.get_status()
        
        # Métricas principais em 3 colunas
        col_width = self.config.terminal_width // 3
        
        # Coluna 1: Clusters
        cluster_lines = ["📊 CLUSTERS"]
        cluster_lines.append("─" * (col_width - 2))
        
        clusters = status['clusters']
        active_clusters = sum(1 for c in clusters.values() if c['status'] == 'active')
        total_agents = sum(len(c['agents']) for c in clusters.values())
        
        cluster_lines.append(f"Total: {len(clusters)}")
        cluster_lines.append(f"Ativos: {active_clusters}")
        cluster_lines.append(f"Agentes: {total_agents}")
        
        # Coluna 2: Performance
        perf_lines = ["📈 PERFORMANCE"]
        perf_lines.append("─" * (col_width - 2))
        
        metrics = status['metrics']
        success_rate = 0
        if metrics['total_requests'] > 0:
            success_rate = (metrics['successful_requests'] / metrics['total_requests']) * 100
        
        perf_lines.append(f"Requests: {metrics['total_requests']}")
        perf_lines.append(f"Sucesso: {success_rate:.1f}%")
        perf_lines.append(f"Resp.Time: {metrics['avg_response_time']:.1f}ms")
        
        # Coluna 3: Sistema
        sys_lines = ["🔧 SISTEMA"]
        sys_lines.append("─" * (col_width - 2))
        
        uptime = status['orchestrator']['uptime_seconds']
        uptime_str = f"{uptime//3600:.0f}h {(uptime%3600)//60:.0f}m"
        
        sys_lines.append(f"Uptime: {uptime_str}")
        sys_lines.append(f"Última atualização:")
        sys_lines.append(f"{self.last_update.strftime('%H:%M:%S')}")
        
        # Combinar colunas
        max_col_lines = max(len(cluster_lines), len(perf_lines), len(sys_lines))
        for i in range(max_col_lines):
            line = ""
            
            if i < len(cluster_lines):
                line += f"{cluster_lines[i]:<{col_width}}"
            else:
                line += " " * col_width
            
            if i < len(perf_lines):
                line += f"{perf_lines[i]:<{col_width}}"
            else:
                line += " " * col_width
            
            if i < len(sys_lines):
                line += sys_lines[i]
            
            lines.append(line)
        
        lines.append("")
        
        # Gráfico de requests ao longo do tempo
        if 'total_requests' in self.metrics_history:
            request_data = [point[1] for point in self.metrics_history['total_requests']]
            if len(request_data) > 1:
                # Calcular diferenças para mostrar rate
                rate_data = []
                for i in range(1, len(request_data)):
                    rate = request_data[i] - request_data[i-1]
                    rate_data.append(max(0, rate))
                
                chart = ASCIICharts.line_chart(
                    rate_data[-30:],  # Últimos 30 pontos
                    width=self.config.terminal_width - 10,
                    height=8,
                    title="Taxa de Requests (últimos 30 pontos)"
                )
                lines.extend(chart)
        
        lines.append("")
        
        # Status dos clusters
        lines.append("🔗 STATUS DOS CLUSTERS")
        lines.append("─" * 50)
        
        for cluster_id, cluster_data in clusters.items():
            status_emoji = "🟢" if cluster_data['status'] == 'active' else "🔴"
            agent_count = len(cluster_data['agents'])
            available_count = cluster_data.get('available_agents', 0)
            
            health = MetricsCalculator.calculate_cluster_health(cluster_data)
            trend = "→"
            
            if f'{cluster_id}_health' in self.metrics_history:
                health_history = [p[1] for p in self.metrics_history[f'{cluster_id}_health']]
                trend = MetricsCalculator.get_trending_direction(health_history)
            
            gauge = ASCIICharts.gauge(
                health, 100, 30, 
                f"{status_emoji} {cluster_id[:15]:<15}", "%"
            )
            
            lines.append(f"{gauge} {trend} ({available_count}/{agent_count} agents)")
        
        return lines
    
    def _render_detailed(self) -> List[str]:
        """Renderiza visão detalhada"""
        lines = ["📋 VISÃO DETALHADA DOS CLUSTERS"]
        lines.append("")
        
        if not self.orchestrator or not self.orchestrator.is_running:
            return lines + ["⚠️ Orquestrador não está rodando"]
        
        status = self.orchestrator.get_status()
        
        for cluster_id, cluster_data in status['clusters'].items():
            lines.append(f"🔗 {cluster_id.upper()}")
            lines.append("─" * 40)
            
            # Informações básicas
            lines.append(f"Status: {cluster_data['status']}")
            lines.append(f"Agentes: {len(cluster_data['agents'])}")
            lines.append(f"Criado em: {cluster_data.get('created_at', 'N/A')}")
            
            # Lista de agentes
            if cluster_data['agents']:
                lines.append("\nAgentes:")
                for agent_id, agent_data in cluster_data['agents'].items():
                    status_icon = "🟢" if agent_data['status'] == 'online' else "🔴"
                    health = agent_data.get('health_score', 100)
                    tasks = agent_data.get('current_tasks', 0)
                    
                    lines.append(f"  {status_icon} {agent_data['name']:<20} | "
                               f"Saúde: {health:5.1f}% | Tarefas: {tasks}")
            
            # Métricas do cluster
            if cluster_id in status.get('load_balancing', {}):
                lb_stats = status['load_balancing'][cluster_id]
                lines.append(f"\nMétricas:")
                lines.append(f"  Requests: {lb_stats['request_count']}")
                lines.append(f"  Taxa de sucesso: {lb_stats['success_rate']:.1f}%")
                lines.append(f"  Tempo de resposta: {lb_stats['avg_response_time']:.1f}ms")
            
            lines.append("")
        
        return lines
    
    def _render_metrics(self) -> List[str]:
        """Renderiza métricas detalhadas"""
        lines = ["📊 MÉTRICAS DETALHADAS"]
        lines.append("")
        
        # Gráficos de métricas principais
        chart_width = self.config.terminal_width - 10
        chart_height = 6
        
        # Response time
        if 'avg_response_time' in self.metrics_history:
            response_data = [p[1] for p in self.metrics_history['avg_response_time']]
            chart = ASCIICharts.line_chart(
                response_data[-50:],
                width=chart_width,
                height=chart_height,
                title="Tempo de Resposta Médio (ms)"
            )
            lines.extend(chart)
            lines.append("")
        
        # Distribuição de carga por cluster
        if self.orchestrator and self.orchestrator.is_running:
            status = self.orchestrator.get_status()
            load_distribution = MetricsCalculator.calculate_load_distribution(status['clusters'])
            
            if load_distribution:
                chart = ASCIICharts.bar_chart(
                    load_distribution,
                    width=40,
                    title="Distribuição de Carga por Cluster (%)"
                )
                lines.extend(chart)
                lines.append("")
        
        # Saúde dos clusters ao longo do tempo
        cluster_healths = {}
        for key in self.metrics_history:
            if key.endswith('_health'):
                cluster_id = key[:-7]
                health_data = [p[1] for p in self.metrics_history[key]]
                if health_data:
                    cluster_healths[cluster_id] = health_data[-1]
        
        if cluster_healths:
            chart = ASCIICharts.bar_chart(
                cluster_healths,
                width=40,
                title="Saúde Atual dos Clusters (%)"
            )
            lines.extend(chart)
        
        return lines
    
    def _render_topology(self) -> List[str]:
        """Renderiza topologia dos clusters"""
        lines = ["🌐 TOPOLOGIA DOS CLUSTERS"]
        lines.append("")
        
        if not self.orchestrator or not self.orchestrator.is_running:
            return lines + ["⚠️ Orquestrador não está rodando"]
        
        status = self.orchestrator.get_status()
        clusters = status['clusters']
        
        # Gerar conexões baseadas nas regras de roteamento
        connections = []
        routing_rules = status.get('routing_rules', [])
        for rule in routing_rules:
            # Conexão implícita baseada em regras
            target = rule.get('target_cluster', '')
            if target in clusters:
                connections.append(('router', target))
        
        # Gerar diagrama de topologia
        topology = ASCIICharts.topology_diagram(
            clusters,
            connections,
            width=self.config.terminal_width - 10
        )
        
        lines.extend(topology)
        lines.append("")
        
        # Informações de conectividade
        lines.append("📡 CONECTIVIDADE")
        lines.append("─" * 30)
        
        # Circuit breakers
        circuit_breakers = status.get('circuit_breakers', {})
        for cluster_id, breaker_data in circuit_breakers.items():
            state = breaker_data['state']
            failures = breaker_data['failure_count']
            
            state_icon = "🟢" if state == 'closed' else "🔴" if state == 'open' else "🟡"
            lines.append(f"{state_icon} {cluster_id}: {state.upper()} (falhas: {failures})")
        
        return lines
    
    def _render_logs(self) -> List[str]:
        """Renderiza logs recentes"""
        lines = ["📜 LOGS RECENTES"]
        lines.append("─" * 30)
        
        # Simular logs (em implementação real, viria do sistema de logging)
        recent_logs = [
            f"{datetime.now().strftime('%H:%M:%S')} [INFO] Sistema funcionando normalmente",
            f"{datetime.now().strftime('%H:%M:%S')} [DEBUG] Health check completado para todos clusters",
            f"{datetime.now().strftime('%H:%M:%S')} [INFO] Auto-scaling analisado: nenhuma ação necessária"
        ]
        
        # Adicionar logs do buffer
        recent_logs.extend(list(self.log_buffer)[-10:])
        
        for log in recent_logs[-20:]:  # Últimos 20 logs
            lines.append(f"  {log}")
        
        return lines
    
    def _render_footer(self) -> List[str]:
        """Renderiza rodapé"""
        controls = "Controles: [o]verview [d]etailed [m]etrics [t]opology [l]ogs [q]uit [r]efresh"
        
        return [
            "─" * self.config.terminal_width,
            controls
        ]
    
    def add_log_entry(self, message: str):
        """Adiciona entrada ao buffer de logs"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_buffer.append(f"{timestamp} {message}")
    
    def set_mode(self, mode: DashboardMode):
        """Define modo de visualização"""
        self.mode = mode
        self.add_log_entry(f"[INFO] Modo alterado para: {mode.value}")
    
    def get_live_view(self) -> str:
        """Retorna view atual do dashboard"""
        return self.render_dashboard()


# ==================== INTERFACE INTERATIVA ====================

class InteractiveDashboard:
    """Dashboard interativo com controles de teclado"""
    
    def __init__(self):
        self.dashboard = ClusterDashboard()
        self.running = False
    
    async def start(self):
        """Inicia dashboard interativo"""
        self.running = True
        
        # Inicializar componentes
        orchestrator = get_orchestrator()
        registry = get_cluster_registry()
        manager = get_cluster_manager()
        
        # Iniciar componentes se não estiverem rodando
        if not orchestrator.is_running:
            await orchestrator.start()
        
        if not registry.running:
            await registry.start()
        
        if not manager.running:
            await manager.start(orchestrator)
        
        # Iniciar dashboard
        await self.dashboard.start(orchestrator, registry, manager)
        
        print("🎯 Cluster Dashboard Interativo")
        print("Pressione 'h' para ajuda, 'q' para sair")
        print("─" * 50)
        
        # Loop principal
        try:
            await self._interactive_loop()
        except KeyboardInterrupt:
            print("\n\n👋 Dashboard encerrado pelo usuário")
        finally:
            await self._cleanup()
    
    async def _interactive_loop(self):
        """Loop principal interativo"""
        import sys
        import select
        
        while self.running:
            # Limpar tela
            os.system('clear' if os.name == 'posix' else 'cls')
            
            # Renderizar dashboard
            content = self.dashboard.get_live_view()
            print(content)
            
            # Verificar input do usuário (não-bloqueante)
            if select.select([sys.stdin], [], [], 0.1)[0]:
                key = sys.stdin.read(1).lower()
                await self._handle_input(key)
            
            # Pequena pausa para não sobrecarregar
            await asyncio.sleep(1)
    
    async def _handle_input(self, key: str):
        """Processa input do usuário"""
        if key == 'q':
            self.running = False
        elif key == 'o':
            self.dashboard.set_mode(DashboardMode.OVERVIEW)
        elif key == 'd':
            self.dashboard.set_mode(DashboardMode.DETAILED)
        elif key == 'm':
            self.dashboard.set_mode(DashboardMode.METRICS)
        elif key == 't':
            self.dashboard.set_mode(DashboardMode.TOPOLOGY)
        elif key == 'l':
            self.dashboard.set_mode(DashboardMode.LOGS)
        elif key == 'r':
            self.dashboard.add_log_entry("[INFO] Dashboard atualizado manualmente")
        elif key == 'h':
            self._show_help()
    
    def _show_help(self):
        """Mostra ajuda"""
        help_text = """
🎯 CLUSTER DASHBOARD - AJUDA

Teclas de controle:
  o - Overview (visão geral)
  d - Detailed (visão detalhada)
  m - Metrics (métricas)
  t - Topology (topologia)
  l - Logs (logs recentes)
  r - Refresh (atualizar)
  h - Help (esta ajuda)
  q - Quit (sair)

O dashboard atualiza automaticamente a cada 5 segundos.
Pressione qualquer tecla para continuar...
        """
        
        print("\n" + help_text)
        input()  # Aguardar tecla
    
    async def _cleanup(self):
        """Limpeza ao encerrar"""
        self.dashboard.stop()
        print("🛑 Dashboard encerrado")


# ==================== UTILITÁRIOS ====================

def create_simple_dashboard() -> ClusterDashboard:
    """Cria dashboard simples para uso programático"""
    config = DashboardConfig(
        refresh_interval=10,
        compact_mode=True,
        enable_colors=False
    )
    return ClusterDashboard(config)


async def show_cluster_overview():
    """Mostra overview rápido dos clusters"""
    dashboard = create_simple_dashboard()
    
    # Inicializar com componentes padrão
    await dashboard.start()
    
    # Aguardar algumas coletas de métricas
    await asyncio.sleep(2)
    
    # Mostrar overview
    overview = dashboard.render_dashboard()
    print(overview)
    
    dashboard.stop()


if __name__ == "__main__":
    async def test_dashboard():
        """Teste do dashboard"""
        print("🧪 Testando Cluster Dashboard...")
        
        # Teste simples
        await show_cluster_overview()
        
        print("\n✅ Teste concluído!")
        print("\nPara dashboard interativo completo, execute:")
        print("python -c \"from clusters.cluster_dashboard import InteractiveDashboard; import asyncio; asyncio.run(InteractiveDashboard().start())\"")
    
    # Executar teste
    asyncio.run(test_dashboard())