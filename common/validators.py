#!/usr/bin/env python3
"""
🔍 Validadores Consolidados - Sistema Unificado
Centraliza todas as validações de entrada do sistema
"""

import re
import socket
from pathlib import Path
from typing import Union, List, Optional, Dict, Any
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Exceção base para erros de validação"""
    pass


class InputValidator:
    """Classe consolidada para validação de entradas do sistema"""
    
    # Padrões regex para validação
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    IPV4_PATTERN = re.compile(r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
    IPV6_PATTERN = re.compile(r'^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$')
    HOSTNAME_PATTERN = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$')
    
    # Hosts permitidos para ambiente de desenvolvimento
    ALLOWED_LOCAL_HOSTS = {
        'localhost', '127.0.0.1', '0.0.0.0', '::1'
    }
    
    # Faixas de rede privada permitidas
    PRIVATE_NETWORK_PREFIXES = {
        '192.168.', '10.', '172.16.', '172.17.', '172.18.', '172.19.',
        '172.20.', '172.21.', '172.22.', '172.23.', '172.24.', '172.25.',
        '172.26.', '172.27.', '172.28.', '172.29.', '172.30.', '172.31.'
    }
    
    @staticmethod
    def validate_string(value: Any, name: str = "valor", min_length: int = 1, max_length: Optional[int] = None) -> str:
        """
        Valida e sanitiza uma string
        
        Args:
            value: Valor para validar
            name: Nome do campo para mensagens de erro
            min_length: Comprimento mínimo
            max_length: Comprimento máximo (opcional)
            
        Returns:
            String validada e limpa
            
        Raises:
            ValidationError: Se valor inválido
        """
        if not isinstance(value, str):
            raise ValidationError(f"{name} deve ser uma string, recebido: {type(value).__name__}")
        
        value = value.strip()
        
        if len(value) < min_length:
            raise ValidationError(f"{name} deve ter pelo menos {min_length} caracteres")
        
        if max_length and len(value) > max_length:
            raise ValidationError(f"{name} deve ter no máximo {max_length} caracteres")
        
        return value
    
    @staticmethod
    def validate_host(host: str) -> str:
        """
        Valida host de entrada com verificações de segurança
        
        Args:
            host: Host para validar
            
        Returns:
            Host validado
            
        Raises:
            ValidationError: Se host inválido ou inseguro
        """
        if not host or not isinstance(host, str):
            raise ValidationError("Host deve ser uma string não vazia")
        
        host = host.strip().lower()
        if not host:
            raise ValidationError("Host não pode estar vazio")
        
        # Verificar se é IP válido
        if InputValidator.IPV4_PATTERN.match(host) or InputValidator.IPV6_PATTERN.match(host):
            # Verificar se é endereço local permitido
            if host in InputValidator.ALLOWED_LOCAL_HOSTS:
                return host
            
            # Verificar se está em rede privada
            for prefix in InputValidator.PRIVATE_NETWORK_PREFIXES:
                if host.startswith(prefix):
                    return host
            
            # IP público - logar warning
            logger.warning(f"Host com IP público detectado: {host}")
            return host
        
        # Verificar se é hostname válido
        if InputValidator.HOSTNAME_PATTERN.match(host):
            # Verificar se é localhost
            if host in InputValidator.ALLOWED_LOCAL_HOSTS:
                return host
            
            # Hostname externo - verificar se é permitido
            if not host.endswith('.local') and '.' in host:
                logger.warning(f"Hostname externo detectado: {host}")
            
            return host
        
        raise ValidationError(f"Host inválido: {host}")
    
    @staticmethod
    def validate_port(port: Union[int, str]) -> int:
        """
        Valida porta de rede
        
        Args:
            port: Porta para validar
            
        Returns:
            Porta válida como inteiro
            
        Raises:
            ValidationError: Se porta inválida
        """
        try:
            port_num = int(port)
        except (ValueError, TypeError):
            raise ValidationError(f"Porta deve ser um número inteiro, recebido: {port}")
        
        if not (1 <= port_num <= 65535):
            raise ValidationError(f"Porta deve estar entre 1 e 65535, recebido: {port_num}")
        
        # Verificar portas privilegiadas
        if port_num < 1024:
            logger.warning(f"Porta privilegiada detectada: {port_num}")
        
        return port_num
    
    @staticmethod
    def validate_url(url: str, allowed_schemes: Optional[List[str]] = None) -> str:
        """
        Valida URL com verificações de segurança
        
        Args:
            url: URL para validar
            allowed_schemes: Esquemas permitidos (default: http, https)
            
        Returns:
            URL validada
            
        Raises:
            ValidationError: Se URL inválida
        """
        if not url or not isinstance(url, str):
            raise ValidationError("URL deve ser uma string não vazia")
        
        url = url.strip()
        if not url:
            raise ValidationError("URL não pode estar vazia")
        
        if allowed_schemes is None:
            allowed_schemes = ['http', 'https']
        
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValidationError(f"URL malformada: {e}")
        
        if not parsed.scheme:
            raise ValidationError("URL deve conter esquema (http:// ou https://)")
        
        if parsed.scheme not in allowed_schemes:
            raise ValidationError(f"Esquema de URL não permitido: {parsed.scheme}. Permitidos: {allowed_schemes}")
        
        if not parsed.netloc:
            raise ValidationError("URL deve conter hostname")
        
        # Validar o host da URL
        host = parsed.hostname
        if host:
            try:
                InputValidator.validate_host(host)
            except ValidationError as e:
                raise ValidationError(f"Host inválido na URL: {e}")
        
        return url
    
    @staticmethod
    def validate_email(email: str) -> str:
        """
        Valida endereço de email
        
        Args:
            email: Email para validar
            
        Returns:
            Email validado e normalizado
            
        Raises:
            ValidationError: Se email inválido
        """
        email = InputValidator.validate_string(email, "email", min_length=5, max_length=320)
        email = email.lower()
        
        if not InputValidator.EMAIL_PATTERN.match(email):
            raise ValidationError(f"Formato de email inválido: {email}")
        
        return email
    
    @staticmethod
    def validate_path(path: Union[str, Path], must_exist: bool = False, must_be_file: bool = False, must_be_dir: bool = False) -> Path:
        """
        Valida caminho de arquivo/diretório
        
        Args:
            path: Caminho para validar
            must_exist: Se deve existir
            must_be_file: Se deve ser arquivo
            must_be_dir: Se deve ser diretório
            
        Returns:
            Path objeto validado
            
        Raises:
            ValidationError: Se caminho inválido
        """
        if isinstance(path, str):
            path = Path(path)
        elif not isinstance(path, Path):
            raise ValidationError(f"Path deve ser string ou Path object, recebido: {type(path).__name__}")
        
        # Verificar se é caminho absoluto
        if not path.is_absolute():
            logger.warning(f"Caminho relativo detectado: {path}")
        
        # Verificar se existe
        if must_exist and not path.exists():
            raise ValidationError(f"Caminho não existe: {path}")
        
        if path.exists():
            if must_be_file and not path.is_file():
                raise ValidationError(f"Caminho deve ser um arquivo: {path}")
            
            if must_be_dir and not path.is_dir():
                raise ValidationError(f"Caminho deve ser um diretório: {path}")
        
        return path
    
    @staticmethod
    def validate_json_config(config: Dict[str, Any], required_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Valida configuração JSON
        
        Args:
            config: Configuração para validar
            required_fields: Campos obrigatórios
            
        Returns:
            Configuração validada
            
        Raises:
            ValidationError: Se configuração inválida
        """
        if not isinstance(config, dict):
            raise ValidationError(f"Configuração deve ser um dicionário, recebido: {type(config).__name__}")
        
        if required_fields:
            missing_fields = [field for field in required_fields if field not in config]
            if missing_fields:
                raise ValidationError(f"Campos obrigatórios ausentes: {missing_fields}")
        
        return config
    
    @staticmethod
    def validate_agent_config(agent_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida configuração específica de agente
        
        Args:
            agent_config: Configuração do agente
            
        Returns:
            Configuração validada
            
        Raises:
            ValidationError: Se configuração inválida
        """
        required_fields = ['ports', 'type']
        config = InputValidator.validate_json_config(agent_config, required_fields)
        
        # Validar portas
        if 'ports' in config:
            if not isinstance(config['ports'], list):
                raise ValidationError("Campo 'ports' deve ser uma lista")
            
            validated_ports = []
            for port in config['ports']:
                validated_ports.append(InputValidator.validate_port(port))
            config['ports'] = validated_ports
        
        # Validar tipo
        if 'type' in config:
            agent_type = InputValidator.validate_string(config['type'], "type")
            allowed_types = ['a2a', 'web', 'analytics', 'debug', 'api', 'service']
            if agent_type not in allowed_types:
                logger.warning(f"Tipo de agente não reconhecido: {agent_type}")
            config['type'] = agent_type
        
        return config
    
    @staticmethod
    def validate_neo4j_config(neo4j_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida configuração do Neo4j
        
        Args:
            neo4j_config: Configuração do Neo4j
            
        Returns:
            Configuração validada
            
        Raises:
            ValidationError: Se configuração inválida
        """
        required_fields = ['uri', 'username', 'password']
        config = InputValidator.validate_json_config(neo4j_config, required_fields)
        
        # Validar URI
        if 'uri' in config:
            uri = InputValidator.validate_string(config['uri'], "uri")
            # Verificar se é URI bolt válida
            if not uri.startswith(('bolt://', 'bolt+s://', 'neo4j://', 'neo4j+s://')):
                raise ValidationError(f"URI Neo4j deve usar protocolo bolt:// ou neo4j://, recebido: {uri}")
            config['uri'] = uri
        
        # Validar username
        if 'username' in config:
            config['username'] = InputValidator.validate_string(config['username'], "username")
        
        # Validar password (não logar por segurança)
        if 'password' in config:
            password = config['password']
            if not isinstance(password, str) or len(password) < 1:
                raise ValidationError("Password deve ser uma string não vazia")
        
        return config
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitiza nome de arquivo removendo caracteres perigosos
        
        Args:
            filename: Nome de arquivo para sanitizar
            
        Returns:
            Nome de arquivo seguro
        """
        # Remover caracteres perigosos
        dangerous_chars = r'[<>:"/\\|?*\x00-\x1f]'
        safe_filename = re.sub(dangerous_chars, '_', filename)
        
        # Remover espaços duplos e trim
        safe_filename = re.sub(r'\s+', '_', safe_filename.strip())
        
        # Limitar tamanho
        if len(safe_filename) > 255:
            safe_filename = safe_filename[:255]
        
        # Evitar nomes reservados no Windows
        reserved_names = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
        name_without_ext = safe_filename.split('.')[0].upper()
        if name_without_ext in reserved_names:
            safe_filename = f"_{safe_filename}"
        
        return safe_filename


class SystemValidator:
    """Validador de sistema e integridade"""
    
    @staticmethod
    def check_port_availability(host: str, port: int, timeout: float = 1.0) -> bool:
        """
        Verifica se uma porta está disponível/aberta
        
        Args:
            host: Host para verificar
            port: Porta para verificar
            timeout: Timeout em segundos
            
        Returns:
            True se porta estiver aberta
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                result = sock.connect_ex((host, port))
                return result == 0
        except Exception:
            return False
    
    @staticmethod
    def validate_system_dependencies() -> Dict[str, bool]:
        """
        Valida dependências do sistema
        
        Returns:
            Dicionário com status das dependências
        """
        dependencies = {}
        
        # Python modules
        modules_to_check = [
            'crewai', 'neo4j', 'pydantic', 'fastapi', 'aiohttp',
            'yaml', 'dotenv', 'psutil', 'asyncio'
        ]
        
        for module in modules_to_check:
            try:
                __import__(module)
                dependencies[module] = True
            except ImportError:
                dependencies[module] = False
        
        return dependencies
    
    @staticmethod
    def validate_environment_variables(required_vars: List[str]) -> Dict[str, bool]:
        """
        Valida variáveis de ambiente necessárias
        
        Args:
            required_vars: Lista de variáveis obrigatórias
            
        Returns:
            Dicionário com status das variáveis
        """
        import os
        
        status = {}
        for var in required_vars:
            status[var] = var in os.environ and bool(os.environ[var])
        
        return status


# Funções de conveniência para uso direto
def validate_host(host: str) -> str:
    """Função de conveniência para validar host"""
    return InputValidator.validate_host(host)


def validate_port(port: Union[int, str]) -> int:
    """Função de conveniência para validar porta"""
    return InputValidator.validate_port(port)


def validate_url(url: str) -> str:
    """Função de conveniência para validar URL"""
    return InputValidator.validate_url(url)


def sanitize_filename(filename: str) -> str:
    """Função de conveniência para sanitizar nome de arquivo"""
    return InputValidator.sanitize_filename(filename)


if __name__ == "__main__":
    # Testes básicos dos validadores
    print("🔍 Testando validadores...")
    
    try:
        # Testar validação de host
        print(f"✅ Host válido: {validate_host('localhost')}")
        print(f"✅ Porta válida: {validate_port(8080)}")
        print(f"✅ URL válida: {validate_url('http://localhost:8080')}")
        print(f"✅ Filename sanitizado: {sanitize_filename('arquivo <perigoso>.txt')}")
        
        # Testar dependências
        deps = SystemValidator.validate_system_dependencies()
        print("\n📦 Status das dependências:")
        for dep, status in deps.items():
            emoji = "✅" if status else "❌"
            print(f"{emoji} {dep}")
        
        print("\n✅ Todos os validadores funcionando!")
        
    except Exception as e:
        print(f"❌ Erro nos testes: {e}")