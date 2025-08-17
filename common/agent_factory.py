#!/usr/bin/env python3
"""
🏭 Agent Factory - Sistema de Criação e Gerenciamento de Agentes
Factory pattern para padronizar criação, registro e validação de agentes
"""

import os
import json
import yaml
import time
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Type, Callable, Protocol
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from abc import ABC, abstractmethod
import logging
import uuid
import inspect
from functools import wraps

# CrewAI imports
try:
    from crewai import Agent, Task, Crew
    from crewai.tools import BaseTool
except ImportError:
    print("⚠️  CrewAI não instalado. Execute: pip install crewai")
    # Mock classes para desenvolvimento
    class Agent: pass
    class Task: pass
    class Crew: pass
    class BaseTool: pass

# Local imports
from .cache_manager import get_cache, CacheConfig, CachePolicy
from .logging_config import get_logger
from .telemetry import get_telemetry, timer, counter, gauge
from .validators import InputValidator

logger = get_logger(__name__)
telemetry = get_telemetry()


class AgentType(Enum):
    """Tipos de agentes disponíveis"""
    RESEARCHER = "researcher"
    CODER = "coder"
    TESTER = "tester"
    REVIEWER = "reviewer"
    PLANNER = "planner"
    COORDINATOR = "coordinator"
    ANALYST = "analyst"
    CUSTOM = "custom"


class AgentStatus(Enum):
    """Status dos agentes"""
    CREATED = "created"
    INITIALIZING = "initializing"
    READY = "ready"
    WORKING = "working"
    IDLE = "idle"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class AgentConfig:
    """Configuração de agente"""
    name: str
    role: str
    goal: str
    backstory: str
    type: AgentType
    tools: List[str] = field(default_factory=list)
    llm_config: Dict[str, Any] = field(default_factory=dict)
    max_execution_time: int = 300  # 5 minutos
    max_iterations: int = 10
    memory_enabled: bool = True
    verbose: bool = False
    delegation: bool = False
    custom_properties: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validação pós-inicialização"""
        if not self.name or not self.role:
            raise ValueError("Nome e role são obrigatórios")
        
        # Validar nome do agente
        if not InputValidator.validate_agent_name(self.name):
            raise ValueError(f"Nome de agente inválido: {self.name}")


@dataclass
class AgentMetrics:
    """Métricas do agente"""
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_execution_time: float = 0.0
    average_execution_time: float = 0.0
    error_count: int = 0
    uptime: timedelta = field(default_factory=lambda: timedelta(0))
    
    @property
    def success_rate(self) -> float:
        """Taxa de sucesso das tarefas"""
        total = self.tasks_completed + self.tasks_failed
        return self.tasks_completed / total if total > 0 else 0.0
    
    def update_task_completion(self, execution_time: float, success: bool) -> None:
        """Atualiza métricas após conclusão de tarefa"""
        self.last_activity = datetime.now()
        self.total_execution_time += execution_time
        
        if success:
            self.tasks_completed += 1
        else:
            self.tasks_failed += 1
            self.error_count += 1
        
        # Recalcular tempo médio
        total_tasks = self.tasks_completed + self.tasks_failed
        if total_tasks > 0:
            self.average_execution_time = self.total_execution_time / total_tasks


class AgentWrapper:
    """
    Wrapper para agentes CrewAI com funcionalidades adicionais
    
    Features:
    - Métricas automáticas
    - Logging estruturado
    - Validação de entrada
    - Cache de resultados
    - Circuit breaker
    - Health monitoring
    """
    
    def __init__(self, agent: Agent, config: AgentConfig, factory: 'AgentFactory'):
        self.agent = agent
        self.config = config
        self.factory = factory
        self.id = str(uuid.uuid4())
        self.metrics = AgentMetrics()
        self.status = AgentStatus.CREATED
        self.last_error: Optional[Exception] = None
        
        # Cache para resultados
        cache_config = CacheConfig(
            max_size=100,
            default_ttl=600,  # 10 minutos
            policy=CachePolicy.LRU_TTL
        )
        self._cache = get_cache(f'agent_{self.config.name}', cache_config)
        
        # Instrumentar agente original
        self._instrument_agent()
        
        logger.info(f"🤖 Agente criado: {self.config.name} ({self.config.type.value})")
    
    def _instrument_agent(self) -> None:
        """Adiciona instrumentação ao agente"""
        # Salvar métodos originais
        original_execute = getattr(self.agent, 'execute', None)
        
        if original_execute:
            @wraps(original_execute)
            def instrumented_execute(*args, **kwargs):
                return self._execute_with_metrics(original_execute, *args, **kwargs)
            
            setattr(self.agent, 'execute', instrumented_execute)
    
    def _execute_with_metrics(self, original_method: Callable, *args, **kwargs) -> Any:
        """Executa método com coleta de métricas"""
        start_time = time.time()
        self.status = AgentStatus.WORKING
        
        try:
            # Registrar início da execução
            telemetry.counter('agents.tasks.started', tags={
                'agent_name': self.config.name,
                'agent_type': self.config.type.value
            })
            
            with timer(f'agents.execution_time', tags={'agent_name': self.config.name}):
                result = original_method(*args, **kwargs)
            
            # Registrar sucesso
            execution_time = time.time() - start_time
            self.metrics.update_task_completion(execution_time, True)
            self.status = AgentStatus.IDLE
            
            telemetry.counter('agents.tasks.completed', tags={
                'agent_name': self.config.name,
                'agent_type': self.config.type.value
            })
            
            logger.info(f"✅ Tarefa completada por {self.config.name} em {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            # Registrar falha
            execution_time = time.time() - start_time
            self.metrics.update_task_completion(execution_time, False)
            self.status = AgentStatus.ERROR
            self.last_error = e
            
            telemetry.counter('agents.tasks.failed', tags={
                'agent_name': self.config.name,
                'agent_type': self.config.type.value,
                'error_type': type(e).__name__
            })
            
            logger.error(f"❌ Tarefa falhou para {self.config.name}: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do agente"""
        uptime = datetime.now() - self.metrics.created_at
        
        return {
            'id': self.id,
            'name': self.config.name,
            'type': self.config.type.value,
            'status': self.status.value,
            'metrics': {
                'tasks_completed': self.metrics.tasks_completed,
                'tasks_failed': self.metrics.tasks_failed,
                'success_rate': self.metrics.success_rate,
                'total_execution_time': self.metrics.total_execution_time,
                'average_execution_time': self.metrics.average_execution_time,
                'error_count': self.metrics.error_count,
                'uptime_seconds': uptime.total_seconds()
            },
            'last_activity': self.metrics.last_activity.isoformat(),
            'last_error': str(self.last_error) if self.last_error else None
        }
    
    def health_check(self) -> bool:
        """Verifica saúde do agente"""
        try:
            # Verificações básicas
            if self.status == AgentStatus.ERROR:
                return False
            
            # Verificar se agente não está travado
            time_since_activity = datetime.now() - self.metrics.last_activity
            if time_since_activity > timedelta(hours=1) and self.status == AgentStatus.WORKING:
                logger.warning(f"Agente {self.config.name} pode estar travado")
                return False
            
            # Verificar taxa de erro
            if self.metrics.error_count > 10 and self.metrics.success_rate < 0.5:
                logger.warning(f"Agente {self.config.name} tem alta taxa de erro")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Erro no health check do agente {self.config.name}: {e}")
            return False
    
    def reset_metrics(self) -> None:
        """Reseta métricas do agente"""
        self.metrics = AgentMetrics()
        self.last_error = None
        logger.info(f"Métricas resetadas para agente {self.config.name}")
    
    def stop(self) -> None:
        """Para agente"""
        self.status = AgentStatus.STOPPED
        logger.info(f"Agente {self.config.name} parado")


class AgentTemplate(ABC):
    """Template base para criação de agentes"""
    
    @property
    @abstractmethod
    def agent_type(self) -> AgentType:
        """Tipo do agente"""
        pass
    
    @property
    @abstractmethod
    def default_config(self) -> Dict[str, Any]:
        """Configuração padrão do agente"""
        pass
    
    @abstractmethod
    def create_tools(self, config: AgentConfig) -> List[BaseTool]:
        """Cria ferramentas específicas do agente"""
        pass
    
    def validate_config(self, config: AgentConfig) -> bool:
        """Valida configuração específica do agente"""
        return True
    
    def post_creation_setup(self, agent: Agent, config: AgentConfig) -> None:
        """Setup pós-criação do agente"""
        pass


class ResearcherTemplate(AgentTemplate):
    """Template para agentes pesquisadores"""
    
    @property
    def agent_type(self) -> AgentType:
        return AgentType.RESEARCHER
    
    @property
    def default_config(self) -> Dict[str, Any]:
        return {
            'role': 'Senior Research Analyst',
            'goal': 'Uncover cutting-edge developments and provide comprehensive research insights',
            'backstory': 'You are a seasoned research analyst with a passion for uncovering trends and providing deep insights.',
            'tools': ['web_search', 'file_reader', 'document_analyzer'],
            'max_execution_time': 600,  # 10 minutos para pesquisa
            'memory_enabled': True
        }
    
    def create_tools(self, config: AgentConfig) -> List[BaseTool]:
        """Cria ferramentas de pesquisa"""
        tools = []
        
        # Adicionar ferramentas baseadas na configuração
        if 'web_search' in config.tools:
            # TODO: Implementar web search tool
            pass
        
        if 'file_reader' in config.tools:
            # TODO: Implementar file reader tool
            pass
        
        return tools


class CoderTemplate(AgentTemplate):
    """Template para agentes codificadores"""
    
    @property
    def agent_type(self) -> AgentType:
        return AgentType.CODER
    
    @property
    def default_config(self) -> Dict[str, Any]:
        return {
            'role': 'Senior Software Engineer',
            'goal': 'Write clean, efficient, and well-documented code following best practices',
            'backstory': 'You are an experienced software engineer with expertise in multiple programming languages and frameworks.',
            'tools': ['code_executor', 'file_writer', 'code_analyzer'],
            'max_execution_time': 900,  # 15 minutos para codificação
            'memory_enabled': True
        }
    
    def create_tools(self, config: AgentConfig) -> List[BaseTool]:
        """Cria ferramentas de codificação"""
        tools = []
        
        if 'code_executor' in config.tools:
            # TODO: Implementar code executor tool
            pass
        
        if 'file_writer' in config.tools:
            # TODO: Implementar file writer tool
            pass
        
        return tools


class TesterTemplate(AgentTemplate):
    """Template para agentes testadores"""
    
    @property
    def agent_type(self) -> AgentType:
        return AgentType.TESTER
    
    @property
    def default_config(self) -> Dict[str, Any]:
        return {
            'role': 'Quality Assurance Engineer',
            'goal': 'Ensure code quality through comprehensive testing and validation',
            'backstory': 'You are a meticulous QA engineer focused on delivering bug-free, reliable software.',
            'tools': ['test_runner', 'code_analyzer', 'bug_tracker'],
            'max_execution_time': 600,
            'memory_enabled': True
        }
    
    def create_tools(self, config: AgentConfig) -> List[BaseTool]:
        """Cria ferramentas de teste"""
        tools = []
        
        if 'test_runner' in config.tools:
            # TODO: Implementar test runner tool
            pass
        
        return tools


class AgentRegistry:
    """Registry para gerenciar agentes criados"""
    
    def __init__(self):
        self.agents: Dict[str, AgentWrapper] = {}
        self.agent_configs: Dict[str, AgentConfig] = {}
        self._lock = threading.RLock()
    
    def register(self, agent: AgentWrapper) -> None:
        """Registra agente"""
        with self._lock:
            self.agents[agent.config.name] = agent
            self.agent_configs[agent.config.name] = agent.config
            
            # Atualizar telemetria
            gauge('agents.total_count', len(self.agents))
            gauge('agents.active_count', 
                  len([a for a in self.agents.values() if a.status != AgentStatus.STOPPED]))
            
            logger.info(f"📋 Agente registrado: {agent.config.name}")
    
    def unregister(self, name: str) -> bool:
        """Remove agente do registry"""
        with self._lock:
            if name in self.agents:
                agent = self.agents[name]
                agent.stop()
                del self.agents[name]
                del self.agent_configs[name]
                
                # Atualizar telemetria
                gauge('agents.total_count', len(self.agents))
                
                logger.info(f"📋 Agente removido: {name}")
                return True
        return False
    
    def get(self, name: str) -> Optional[AgentWrapper]:
        """Obtém agente por nome"""
        return self.agents.get(name)
    
    def list_agents(self) -> List[str]:
        """Lista nomes de todos os agentes"""
        return list(self.agents.keys())
    
    def get_by_type(self, agent_type: AgentType) -> List[AgentWrapper]:
        """Obtém agentes por tipo"""
        return [agent for agent in self.agents.values() 
                if agent.config.type == agent_type]
    
    def get_active_agents(self) -> List[AgentWrapper]:
        """Obtém agentes ativos"""
        return [agent for agent in self.agents.values()
                if agent.status not in [AgentStatus.STOPPED, AgentStatus.ERROR]]
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do registry"""
        by_type = {}
        by_status = {}
        
        for agent in self.agents.values():
            # Por tipo
            agent_type = agent.config.type.value
            by_type[agent_type] = by_type.get(agent_type, 0) + 1
            
            # Por status
            status = agent.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            'total_agents': len(self.agents),
            'by_type': by_type,
            'by_status': by_status,
            'active_agents': len(self.get_active_agents())
        }
    
    def health_check_all(self) -> Dict[str, bool]:
        """Executa health check em todos os agentes"""
        results = {}
        for name, agent in self.agents.items():
            results[name] = agent.health_check()
        return results


class AgentFactory:
    """
    Factory principal para criação e gerenciamento de agentes
    
    Features:
    - Templates de agentes pré-configurados
    - Validação de configuração
    - Registry centralizado
    - Métricas automáticas
    - Cache de configurações
    - Loading de configurações YAML
    """
    
    def __init__(self):
        self.registry = AgentRegistry()
        self.templates: Dict[AgentType, AgentTemplate] = {}
        self._setup_templates()
        
        # Cache para configurações
        cache_config = CacheConfig(
            max_size=200,
            default_ttl=1800,  # 30 minutos
            policy=CachePolicy.LRU_TTL
        )
        self._cache = get_cache('agent_factory', cache_config)
        
        logger.info("🏭 Agent Factory inicializada")
    
    def _setup_templates(self) -> None:
        """Configura templates padrão"""
        self.templates[AgentType.RESEARCHER] = ResearcherTemplate()
        self.templates[AgentType.CODER] = CoderTemplate()
        self.templates[AgentType.TESTER] = TesterTemplate()
        
        logger.debug(f"Templates configurados: {list(self.templates.keys())}")
    
    def register_template(self, template: AgentTemplate) -> None:
        """Registra template customizado"""
        self.templates[template.agent_type] = template
        logger.info(f"Template registrado: {template.agent_type.value}")
    
    def create_agent(self, config: AgentConfig, validate: bool = True) -> AgentWrapper:
        """
        Cria agente a partir de configuração
        
        Args:
            config: Configuração do agente
            validate: Se deve validar configuração
            
        Returns:
            AgentWrapper criado
        """
        with timer('agents.creation_time', tags={'agent_type': config.type.value}):
            try:
                logger.info(f"🏭 Criando agente: {config.name} ({config.type.value})")
                
                # Validar configuração
                if validate:
                    self._validate_config(config)
                
                # Obter template
                template = self.templates.get(config.type)
                if not template:
                    raise ValueError(f"Template não encontrado para tipo: {config.type}")
                
                # Merge com configuração padrão
                merged_config = self._merge_with_defaults(config, template)
                
                # Criar ferramentas
                tools = template.create_tools(merged_config)
                
                # Criar agente CrewAI
                agent = Agent(
                    role=merged_config.role,
                    goal=merged_config.goal,
                    backstory=merged_config.backstory,
                    tools=tools,
                    verbose=merged_config.verbose,
                    allow_delegation=merged_config.delegation,
                    memory=merged_config.memory_enabled,
                    max_execution_time=merged_config.max_execution_time,
                    max_iter=merged_config.max_iterations
                )
                
                # Criar wrapper
                wrapper = AgentWrapper(agent, merged_config, self)
                
                # Setup pós-criação
                template.post_creation_setup(agent, merged_config)
                
                # Registrar agente
                self.registry.register(wrapper)
                
                # Atualizar métricas
                counter('agents.created', tags={'agent_type': config.type.value})
                
                wrapper.status = AgentStatus.READY
                
                logger.info(f"✅ Agente criado com sucesso: {config.name}")
                return wrapper
                
            except Exception as e:
                counter('agents.creation_failed', tags={
                    'agent_type': config.type.value,
                    'error_type': type(e).__name__
                })
                logger.error(f"❌ Erro ao criar agente {config.name}: {e}")
                raise
    
    def create_from_template(self, agent_type: AgentType, name: str, 
                           overrides: Optional[Dict[str, Any]] = None) -> AgentWrapper:
        """
        Cria agente a partir de template
        
        Args:
            agent_type: Tipo do agente
            name: Nome do agente
            overrides: Sobrescrita de configurações
            
        Returns:
            AgentWrapper criado
        """
        template = self.templates.get(agent_type)
        if not template:
            raise ValueError(f"Template não encontrado: {agent_type}")
        
        # Configuração base do template
        base_config = template.default_config.copy()
        base_config['name'] = name
        base_config['type'] = agent_type
        
        # Aplicar sobrescritas
        if overrides:
            base_config.update(overrides)
        
        # Criar configuração
        config = AgentConfig(**base_config)
        
        return self.create_agent(config)
    
    def create_from_yaml(self, yaml_path: Path) -> AgentWrapper:
        """
        Cria agente a partir de arquivo YAML
        
        Args:
            yaml_path: Caminho para arquivo YAML
            
        Returns:
            AgentWrapper criado
        """
        # Verificar cache
        cache_key = f"yaml_{yaml_path}_{yaml_path.stat().st_mtime}"
        cached_config = self._cache.get(cache_key)
        
        if cached_config:
            config = AgentConfig(**cached_config)
        else:
            # Carregar e parsear YAML
            with open(yaml_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)
            
            # Validar schema YAML
            self._validate_yaml_schema(yaml_data)
            
            # Converter para configuração
            config_data = yaml_data['agent']
            config_data['type'] = AgentType(config_data['type'])
            config = AgentConfig(**config_data)
            
            # Cachear configuração
            self._cache.set(cache_key, asdict(config), ttl=1800)
        
        return self.create_agent(config)
    
    def create_crew(self, agent_names: List[str], tasks: List[Task], 
                   process_type: str = "sequential") -> Crew:
        """
        Cria crew com agentes especificados
        
        Args:
            agent_names: Nomes dos agentes
            tasks: Lista de tarefas
            process_type: Tipo de processo (sequential, hierarchical)
            
        Returns:
            Crew configurado
        """
        agents = []
        for name in agent_names:
            wrapper = self.registry.get(name)
            if not wrapper:
                raise ValueError(f"Agente não encontrado: {name}")
            agents.append(wrapper.agent)
        
        crew = Crew(
            agents=agents,
            tasks=tasks,
            process=process_type,
            verbose=True
        )
        
        logger.info(f"🚢 Crew criado com {len(agents)} agentes e {len(tasks)} tarefas")
        return crew
    
    def _validate_config(self, config: AgentConfig) -> None:
        """Valida configuração do agente"""
        if not config.name:
            raise ValueError("Nome do agente é obrigatório")
        
        if config.name in self.registry.agents:
            raise ValueError(f"Agente já existe: {config.name}")
        
        if config.type not in self.templates:
            raise ValueError(f"Tipo de agente não suportado: {config.type}")
        
        # Validação específica do template
        template = self.templates[config.type]
        if not template.validate_config(config):
            raise ValueError(f"Configuração inválida para tipo {config.type}")
    
    def _merge_with_defaults(self, config: AgentConfig, template: AgentTemplate) -> AgentConfig:
        """Merge configuração com padrões do template"""
        defaults = template.default_config
        
        # Criar dicionário com valores atuais
        config_dict = asdict(config)
        
        # Aplicar padrões para campos não definidos
        for key, default_value in defaults.items():
            if key in config_dict and not config_dict[key]:
                config_dict[key] = default_value
            elif key not in config_dict:
                config_dict[key] = default_value
        
        return AgentConfig(**config_dict)
    
    def _validate_yaml_schema(self, yaml_data: Dict[str, Any]) -> None:
        """Valida schema do YAML"""
        required_fields = ['agent']
        for field in required_fields:
            if field not in yaml_data:
                raise ValueError(f"Campo obrigatório ausente no YAML: {field}")
        
        agent_data = yaml_data['agent']
        agent_required = ['name', 'role', 'goal', 'backstory', 'type']
        for field in agent_required:
            if field not in agent_data:
                raise ValueError(f"Campo obrigatório ausente em agent: {field}")
    
    def get_agent(self, name: str) -> Optional[AgentWrapper]:
        """Obtém agente por nome"""
        return self.registry.get(name)
    
    def list_agents(self) -> List[str]:
        """Lista todos os agentes"""
        return self.registry.list_agents()
    
    def get_factory_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas da factory"""
        registry_stats = self.registry.get_registry_stats()
        
        return {
            'templates_available': len(self.templates),
            'template_types': [t.value for t in self.templates.keys()],
            'registry_stats': registry_stats,
            'cache_stats': {
                'size': self._cache.size(),
                'hit_rate': self._cache.get_stats().hit_rate
            }
        }
    
    def shutdown(self) -> None:
        """Para todos os agentes e limpa recursos"""
        logger.info("🏭 Parando Agent Factory...")
        
        # Parar todos os agentes
        for agent in self.registry.agents.values():
            agent.stop()
        
        # Limpar registry
        self.registry.agents.clear()
        
        logger.info("✅ Agent Factory parada")


# Instância global da factory
_agent_factory: Optional[AgentFactory] = None
_factory_lock = threading.Lock()


def get_agent_factory() -> AgentFactory:
    """
    Obtém instância singleton da agent factory
    
    Returns:
        Instância da factory
    """
    global _agent_factory
    
    if _agent_factory is None:
        with _factory_lock:
            if _agent_factory is None:
                _agent_factory = AgentFactory()
    
    return _agent_factory


# Funções de conveniência
def create_agent(config: AgentConfig) -> AgentWrapper:
    """Função de conveniência para criar agente"""
    return get_agent_factory().create_agent(config)


def create_researcher(name: str, **kwargs) -> AgentWrapper:
    """Cria agente pesquisador"""
    return get_agent_factory().create_from_template(AgentType.RESEARCHER, name, kwargs)


def create_coder(name: str, **kwargs) -> AgentWrapper:
    """Cria agente codificador"""
    return get_agent_factory().create_from_template(AgentType.CODER, name, kwargs)


def create_tester(name: str, **kwargs) -> AgentWrapper:
    """Cria agente testador"""
    return get_agent_factory().create_from_template(AgentType.TESTER, name, kwargs)


if __name__ == "__main__":
    # Teste da agent factory
    print("🏭 Testando Agent Factory...")
    
    try:
        # Obter factory
        factory = get_agent_factory()
        
        # Criar agente researcher
        researcher = create_researcher(
            "test_researcher",
            goal="Pesquisar tendências em IA",
            backstory="Especialista em pesquisa de IA com 10 anos de experiência"
        )
        
        print(f"✅ Researcher criado: {researcher.config.name}")
        
        # Criar agente coder
        coder = create_coder(
            "test_coder",
            goal="Implementar soluções Python robustas",
            tools=['code_executor', 'file_writer']
        )
        
        print(f"✅ Coder criado: {coder.config.name}")
        
        # Testar health check
        health_results = factory.registry.health_check_all()
        print(f"Health check results: {health_results}")
        
        # Mostrar estatísticas
        stats = factory.get_factory_stats()
        print(f"\nEstatísticas da factory:")
        print(f"Templates disponíveis: {stats['templates_available']}")
        print(f"Total de agentes: {stats['registry_stats']['total_agents']}")
        print(f"Agentes ativos: {stats['registry_stats']['active_agents']}")
        print(f"Por tipo: {stats['registry_stats']['by_type']}")
        
        # Mostrar estatísticas individuais
        for agent_name in factory.list_agents():
            agent = factory.get_agent(agent_name)
            agent_stats = agent.get_stats()
            print(f"\nAgente {agent_name}:")
            print(f"  Status: {agent_stats['status']}")
            print(f"  Tipo: {agent_stats['type']}")
            print(f"  Uptime: {agent_stats['metrics']['uptime_seconds']:.1f}s")
        
        print("\n✅ Agent Factory testada com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        logger.error(f"Erro no teste da factory: {e}")
    
    finally:
        # Limpar recursos
        if _agent_factory:
            _agent_factory.shutdown()