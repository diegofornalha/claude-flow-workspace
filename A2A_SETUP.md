# Sistema A2A - Guia de Configuração e Execução

## Visão Geral

Este sistema implementa o protocolo A2A (Agent-to-Agent) permitindo comunicação e colaboração entre múltiplos agentes autônomos. O sistema inclui:

1. **Chat App** - Interface web e backend que atua como cliente/orquestrador A2A
2. **Claude A2A Wrapper** - Agente A2A que expõe Claude Code SDK com memória persistente
3. **CrewAI Agent** - Agente A2A que gerencia equipes de agentes especializados
4. **Neo4j Memory** - Sistema de memória via MCP (simulado)

## Arquitetura

```
┌─────────────────┐
│   Frontend      │
│   (React)       │
└────────┬────────┘
         │
┌────────▼────────┐
│  Chat Backend   │
│  (Node.js)      │
│  Port: 8080     │
└────────┬────────┘
         │ A2A Client
    ┌────┴────┬──────────┐
    │         │          │
┌───▼───┐ ┌──▼───┐ ┌────▼────┐
│Claude │ │CrewAI│ │  Neo4j  │
│Agent  │ │Agent │ │ Memory  │
│ :8001 │ │ :8002│ │  (MCP)  │
└───────┘ └──────┘ └─────────┘
```

## Pré-requisitos

- Node.js 18+
- Python 3.9+
- npm ou yarn

## Instalação

### 1. Backend do Chat

```bash
cd chat-app-claude-code-sdk/backend
npm install
npm install ws  # Para WebSocket client
```

### 2. Frontend do Chat

```bash
cd chat-app-claude-code-sdk/frontend
npm install
```

### 3. Claude A2A Wrapper

```bash
cd claude-a2a-wrapper
npm install
```

Configurar `.env`:
```env
PORT=8001
ANTHROPIC_API_KEY=your-api-key-here
```

### 4. CrewAI Agent

```bash
cd agente-crew-ai
pip install -r requirements.txt
```

Configurar `.env`:
```env
PORT=8002
```

## Execução

### Passo 1: Iniciar os Agentes A2A

**Terminal 1 - Claude A2A Agent:**
```bash
cd claude-a2a-wrapper
npm start
# Servidor rodando em http://localhost:8001
```

**Terminal 2 - CrewAI Agent:**
```bash
cd agente-crew-ai
python a2a_server.py
# Servidor rodando em http://localhost:8002
```

### Passo 2: Iniciar o Backend do Chat

**Terminal 3 - Backend:**
```bash
cd chat-app-claude-code-sdk/backend
npm start
# Servidor rodando em http://localhost:8080
```

### Passo 3: Iniciar o Frontend

**Terminal 4 - Frontend:**
```bash
cd chat-app-claude-code-sdk/frontend
npm start
# Aplicação rodando em http://localhost:3000
```

## Testando o Sistema

### Teste Automatizado

Execute o script de teste completo:

```bash
node test-a2a-flow.js
```

Este script testa:
- Agent Cards de cada agente
- Health checks
- Sistema de memória
- Chat com Claude
- Tarefas A2A
- Tomada de decisão
- Aprendizagem contínua
- Conexões WebSocket

### Teste Manual via Interface

1. Abra http://localhost:3000
2. No seletor de agentes (canto superior direito), escolha:
   - **Claude (Direto)** - Conexão direta com Claude Code SDK
   - **claude** - Via agente A2A com memória
   - **crew-ai** - Equipe de agentes CrewAI

3. Teste diferentes capacidades:
   - Envie mensagens normais
   - Peça para tomar decisões
   - Solicite análises complexas
   - Teste streaming de respostas

### Teste via API

**Verificar agentes disponíveis:**
```bash
curl http://localhost:8080/api/a2a/agents
```

**Selecionar agente:**
```bash
curl -X POST http://localhost:8080/api/a2a/select \
  -H "Content-Type: application/json" \
  -d '{"agent": "claude"}'
```

**Enviar tarefa:**
```bash
curl -X POST http://localhost:8080/api/a2a/task \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Explain A2A protocol",
    "options": {"streaming": true}
  }'
```

## Funcionalidades A2A

### 1. Agent Card
Cada agente expõe suas capacidades via endpoint raiz:
- `GET http://localhost:8001/` - Claude Agent Card
- `GET http://localhost:8002/` - CrewAI Agent Card

### 2. Tarefas Assíncronas
```bash
POST /tasks
{
  "task": "Your task description",
  "context": {},
  "streaming": false
}
```

### 3. Tomada de Decisão
```bash
POST /decide
{
  "context": {"situation": "..."},
  "options": ["option1", "option2"]
}
```

### 4. Aprendizagem Contínua
```bash
POST /learn
{
  "data": {...},
  "type": "category"
}
```

### 5. Sistema de Memória (Claude Agent)
```bash
# Criar memória
POST /memory/create
{
  "label": "person",
  "properties": {
    "name": "John",
    "role": "Developer"
  }
}

# Buscar memórias
POST /memory/search
{
  "query": "John",
  "limit": 10
}
```

### 6. WebSocket para Comunicação P2P
```javascript
const ws = new WebSocket('ws://localhost:8001/ws');
ws.send(JSON.stringify({
  type: 'handshake',
  client: 'your-client'
}));
```

## Monitoramento

### Status dos Agentes
- Claude: http://localhost:8001/status
- CrewAI: http://localhost:8002/status

### Métricas
- Tasks completadas
- Decisões tomadas
- Memórias criadas
- Conexões ativas

## Troubleshooting

### Agente não conecta
1. Verifique se o agente está rodando na porta correta
2. Confirme que não há firewall bloqueando
3. Teste o health check diretamente

### Memória não persiste
- A implementação atual usa memória em RAM (simulada)
- Para persistência real, integre com Neo4j real via MCP

### WebSocket desconecta
- Verifique logs do agente
- Confirme compatibilidade de versões do socket.io/ws

## Próximos Passos

1. **Integração Neo4j Real**: Substituir simulação por banco Neo4j real
2. **Autenticação**: Adicionar JWT para segurança
3. **Métricas Prometheus**: Exportar métricas para monitoramento
4. **Deploy Kubernetes**: Containerizar e orquestrar com K8s
5. **Gateway API**: Adicionar Kong ou similar para gerenciamento

## Referências

- [Protocolo A2A](https://a2a-protocol.org)
- [Claude Code SDK](https://github.com/anthropic-ai/claude-code)
- [CrewAI Docs](https://docs.crewai.com)
- [MCP Protocol](https://modelcontextprotocol.io)