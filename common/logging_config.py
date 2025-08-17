#!/usr/bin/env python3
"""
📊 Configuração Unificada de Logging - Sistema Centralizado
Centraliza toda a configuração de logging do sistema
"""

import os
import sys
import logging
import logging.handlers
from pathlib import Path
from typing import Dict, Optional, Union, List
from datetime import datetime
import json
import traceback
from dataclasses import dataclass
from enum import Enum


class LogLevel(Enum):
    """Níveis de log suportados"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LoggingConfig:
    """Configuração do sistema de logging"""
    level: LogLevel = LogLevel.INFO
    format_string: str = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    log_dir: Optional[Path] = None
    max_file_size: str = "100MB"
    backup_count: int = 5
    enable_console: bool = True
    enable_file: bool = True
    enable_json: bool = False
    enable_structured: bool = True
    service_name: str = "unified-system"
    
    def __post_init__(self):
        """Configuração pós-inicialização"""
        if self.log_dir is None:
            # Detectar diretório de logs automaticamente
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent
            self.log_dir = project_root / "logging" / "logs"
        
        # Garantir que o diretório existe
        self.log_dir.mkdir(parents=True, exist_ok=True)


class ColoredFormatter(logging.Formatter):
    """Formatter colorido para console"""
    
    # Cores ANSI
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        # Adicionar cor se suportado pelo terminal
        if hasattr(sys.stderr, 'isatty') and sys.stderr.isatty():
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            reset = self.COLORS['RESET']
            record.levelname = f"{color}{record.levelname}{reset}"
        
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """Formatter para logs em formato JSON estruturado"""
    
    def format(self, record):
        # Criar estrutura JSON
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'process': record.process,
            'thread': record.thread,
        }
        
        # Adicionar informações de exceção se presente
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Adicionar campos extras se presentes
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        return json.dumps(log_entry, ensure_ascii=False)


class StructuredLoggerAdapter(logging.LoggerAdapter):
    """Adapter para logging estruturado com campos extras"""
    
    def process(self, msg, kwargs):
        # Extrair campos extras do kwargs
        extra_fields = kwargs.pop('extra_fields', {})
        
        # Adicionar ao record
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        kwargs['extra']['extra_fields'] = extra_fields
        
        return msg, kwargs


class UnifiedLoggingManager:
    """Gerenciador unificado de logging do sistema"""
    
    def __init__(self, config: Optional[LoggingConfig] = None):
        """
        Inicializa o gerenciador de logging
        
        Args:
            config: Configuração de logging (opcional)
        """
        self.config = config or LoggingConfig()
        self._loggers: Dict[str, logging.Logger] = {}
        self._configured = False
        
        # Configurar logging global
        self._setup_logging()
    
    def _setup_logging(self):
        """Configura o sistema de logging global"""
        if self._configured:
            return
        
        # Configurar nível global
        logging.basicConfig(level=getattr(logging, self.config.level.value))
        
        # Remover handlers padrão para evitar duplicação
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        self._configured = True
    
    def get_logger(self, name: str, structured: bool = None) -> Union[logging.Logger, StructuredLoggerAdapter]:
        """
        Obtém logger configurado
        
        Args:
            name: Nome do logger
            structured: Se deve usar logging estruturado
            
        Returns:
            Logger configurado
        """
        if structured is None:
            structured = self.config.enable_structured
        
        if name in self._loggers:
            logger = self._loggers[name]
        else:
            logger = self._create_logger(name)
            self._loggers[name] = logger
        
        if structured:
            return StructuredLoggerAdapter(logger, {})
        
        return logger
    
    def _create_logger(self, name: str) -> logging.Logger:
        """
        Cria novo logger com configuração unificada
        
        Args:
            name: Nome do logger
            
        Returns:
            Logger configurado
        """
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, self.config.level.value))
        
        # Remover handlers existentes
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Adicionar handlers configurados
        if self.config.enable_console:
            logger.addHandler(self._create_console_handler())
        
        if self.config.enable_file:
            logger.addHandler(self._create_file_handler(name))
        
        if self.config.enable_json:
            logger.addHandler(self._create_json_handler(name))
        
        # Evitar propagação dupla
        logger.propagate = False
        
        return logger
    
    def _create_console_handler(self) -> logging.StreamHandler:
        """Cria handler para console com cores"""
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, self.config.level.value))
        
        formatter = ColoredFormatter(
            fmt=self.config.format_string,
            datefmt=self.config.date_format
        )
        handler.setFormatter(formatter)
        
        return handler
    
    def _create_file_handler(self, logger_name: str) -> logging.handlers.RotatingFileHandler:
        """Cria handler para arquivo com rotação"""
        log_file = self.config.log_dir / f"{logger_name}.log"
        
        # Converter tamanho máximo
        max_bytes = self._parse_size(self.config.max_file_size)
        
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=self.config.backup_count,
            encoding='utf-8'
        )
        handler.setLevel(getattr(logging, self.config.level.value))
        
        formatter = logging.Formatter(
            fmt=self.config.format_string,
            datefmt=self.config.date_format
        )
        handler.setFormatter(formatter)
        
        return handler
    
    def _create_json_handler(self, logger_name: str) -> logging.handlers.RotatingFileHandler:
        """Cria handler para logs JSON estruturados"""
        log_file = self.config.log_dir / f"{logger_name}.jsonl"
        
        max_bytes = self._parse_size(self.config.max_file_size)
        
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=self.config.backup_count,
            encoding='utf-8'
        )
        handler.setLevel(getattr(logging, self.config.level.value))
        
        formatter = JSONFormatter()
        handler.setFormatter(formatter)
        
        return handler
    
    def _parse_size(self, size_str: str) -> int:
        """
        Converte string de tamanho para bytes
        
        Args:
            size_str: String como "100MB", "1GB", etc.
            
        Returns:
            Tamanho em bytes
        """
        size_str = size_str.upper()
        
        if size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            # Assumir bytes
            return int(size_str)
    
    def configure_from_env(self):
        """Configura logging a partir de variáveis de ambiente"""
        # Nível de log
        log_level = os.getenv('LOG_LEVEL', self.config.level.value)
        try:
            self.config.level = LogLevel(log_level.upper())
        except ValueError:
            pass
        
        # Diretório de logs
        log_dir = os.getenv('LOG_DIR')
        if log_dir:
            self.config.log_dir = Path(log_dir)
            self.config.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Tamanho máximo do arquivo
        max_size = os.getenv('LOG_MAX_FILE_SIZE')
        if max_size:
            self.config.max_file_size = max_size
        
        # Número de backups
        backup_count = os.getenv('LOG_BACKUP_COUNT')
        if backup_count:
            try:
                self.config.backup_count = int(backup_count)
            except ValueError:
                pass
        
        # Opções de habilitação
        self.config.enable_console = os.getenv('LOG_ENABLE_CONSOLE', 'true').lower() == 'true'
        self.config.enable_file = os.getenv('LOG_ENABLE_FILE', 'true').lower() == 'true'
        self.config.enable_json = os.getenv('LOG_ENABLE_JSON', 'false').lower() == 'true'
        self.config.enable_structured = os.getenv('LOG_ENABLE_STRUCTURED', 'true').lower() == 'true'
        
        # Nome do serviço
        service_name = os.getenv('SERVICE_NAME')
        if service_name:
            self.config.service_name = service_name
    
    def log_system_info(self):
        """Loga informações do sistema na inicialização"""
        system_logger = self.get_logger('system')
        
        system_logger.info("🚀 Sistema de logging unificado inicializado")
        system_logger.info(f"📁 Diretório de logs: {self.config.log_dir}")
        system_logger.info(f"📊 Nível de log: {self.config.level.value}")
        system_logger.info(f"🔄 Rotação: {self.config.max_file_size} / {self.config.backup_count} backups")
        system_logger.info(f"💻 Console: {'✅' if self.config.enable_console else '❌'}")
        system_logger.info(f"📄 Arquivo: {'✅' if self.config.enable_file else '❌'}")
        system_logger.info(f"🔧 JSON: {'✅' if self.config.enable_json else '❌'}")
        system_logger.info(f"📊 Estruturado: {'✅' if self.config.enable_structured else '❌'}")
    
    def get_log_stats(self) -> Dict[str, any]:
        """
        Retorna estatísticas dos logs
        
        Returns:
            Dicionário com estatísticas
        """
        stats = {
            'active_loggers': len(self._loggers),
            'logger_names': list(self._loggers.keys()),
            'log_directory': str(self.config.log_dir),
            'log_files': [],
            'total_log_size': 0
        }
        
        # Escanear arquivos de log
        if self.config.log_dir.exists():
            for log_file in self.config.log_dir.glob("*.log"):
                file_stats = {
                    'name': log_file.name,
                    'size': log_file.stat().st_size,
                    'modified': datetime.fromtimestamp(log_file.stat().st_mtime).isoformat()
                }
                stats['log_files'].append(file_stats)
                stats['total_log_size'] += file_stats['size']
        
        return stats


# Instância global do gerenciador
_logging_manager = None


def get_logging_manager() -> UnifiedLoggingManager:
    """
    Retorna instância singleton do gerenciador de logging
    
    Returns:
        Gerenciador de logging
    """
    global _logging_manager
    if _logging_manager is None:
        config = LoggingConfig()
        _logging_manager = UnifiedLoggingManager(config)
        _logging_manager.configure_from_env()
        _logging_manager.log_system_info()
    return _logging_manager


def get_logger(name: str, structured: bool = None) -> Union[logging.Logger, StructuredLoggerAdapter]:
    """
    Função de conveniência para obter logger
    
    Args:
        name: Nome do logger
        structured: Se deve usar logging estruturado
        
    Returns:
        Logger configurado
    """
    manager = get_logging_manager()
    return manager.get_logger(name, structured)


def setup_logging_for_module(module_name: str) -> Union[logging.Logger, StructuredLoggerAdapter]:
    """
    Configura logging para um módulo específico
    
    Args:
        module_name: Nome do módulo (__name__)
        
    Returns:
        Logger configurado para o módulo
    """
    # Extrair nome curto do módulo
    short_name = module_name.split('.')[-1] if '.' in module_name else module_name
    return get_logger(short_name)


# Funções de conveniência para logging estruturado
def log_info(logger: Union[logging.Logger, StructuredLoggerAdapter], message: str, **kwargs):
    """Log info com campos estruturados"""
    if isinstance(logger, StructuredLoggerAdapter):
        logger.info(message, extra_fields=kwargs)
    else:
        logger.info(message, extra=kwargs)


def log_warning(logger: Union[logging.Logger, StructuredLoggerAdapter], message: str, **kwargs):
    """Log warning com campos estruturados"""
    if isinstance(logger, StructuredLoggerAdapter):
        logger.warning(message, extra_fields=kwargs)
    else:
        logger.warning(message, extra=kwargs)


def log_error(logger: Union[logging.Logger, StructuredLoggerAdapter], message: str, **kwargs):
    """Log error com campos estruturados"""
    if isinstance(logger, StructuredLoggerAdapter):
        logger.error(message, extra_fields=kwargs)
    else:
        logger.error(message, extra=kwargs)


if __name__ == "__main__":
    # Teste do sistema de logging
    print("📊 Testando sistema de logging unificado...")
    
    # Configurar logging
    manager = get_logging_manager()
    
    # Testar diferentes tipos de logger
    simple_logger = get_logger('test_simple', structured=False)
    structured_logger = get_logger('test_structured', structured=True)
    
    # Testar logs simples
    simple_logger.debug("Debug message")
    simple_logger.info("Info message")
    simple_logger.warning("Warning message")
    simple_logger.error("Error message")
    
    # Testar logs estruturados
    log_info(structured_logger, "Structured info message", 
             user_id=123, action="test", component="logging")
    log_warning(structured_logger, "Structured warning", 
                reason="test", severity="medium")
    log_error(structured_logger, "Structured error", 
              error_code=500, component="test")
    
    # Mostrar estatísticas
    stats = manager.get_log_stats()
    print(f"\n📈 Estatísticas do logging:")
    print(f"📋 Loggers ativos: {stats['active_loggers']}")
    print(f"📁 Diretório: {stats['log_directory']}")
    print(f"📄 Arquivos de log: {len(stats['log_files'])}")
    print(f"💾 Tamanho total: {stats['total_log_size']} bytes")
    
    print("\n✅ Sistema de logging testado com sucesso!")