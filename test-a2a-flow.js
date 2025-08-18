#!/usr/bin/env node
/**
 * Script de teste para o fluxo completo A2A
 * Testa: Claude A2A Wrapper, CrewAI Agent, Cliente A2A, e integração com memória
 */

import fetch from 'node-fetch';
import WebSocket from 'ws';

const CLAUDE_AGENT_URL = 'http://localhost:8001';
const CREW_AGENT_URL = 'http://localhost:8002';
const CHAT_BACKEND_URL = 'http://localhost:8080';

const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m'
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

async function testEndpoint(name, url, options = {}) {
  try {
    log(`\nTestando ${name}...`, 'blue');
    const response = await fetch(url, options);
    const data = await response.json();
    
    if (response.ok) {
      log(`✅ ${name} OK`, 'green');
      console.log(JSON.stringify(data, null, 2));
      return data;
    } else {
      log(`❌ ${name} Falhou: ${response.status}`, 'red');
      console.log(data);
      return null;
    }
  } catch (error) {
    log(`❌ ${name} Erro: ${error.message}`, 'red');
    return null;
  }
}

async function runTests() {
  log('\n🚀 Iniciando testes do fluxo A2A completo\n', 'magenta');

  // 1. Testar Agent Cards
  log('\n=== 1. TESTANDO AGENT CARDS ===', 'yellow');
  
  const claudeCard = await testEndpoint(
    'Claude Agent Card',
    CLAUDE_AGENT_URL
  );

  const crewCard = await testEndpoint(
    'CrewAI Agent Card',
    CREW_AGENT_URL
  );

  // 2. Testar Health Checks
  log('\n=== 2. TESTANDO HEALTH CHECKS ===', 'yellow');
  
  await testEndpoint(
    'Claude Health',
    `${CLAUDE_AGENT_URL}/health`
  );

  await testEndpoint(
    'CrewAI Health',
    `${CREW_AGENT_URL}/health`
  );

  // 3. Testar Memória (Neo4j via MCP)
  log('\n=== 3. TESTANDO SISTEMA DE MEMÓRIA ===', 'yellow');

  // Criar memória
  const memory = await testEndpoint(
    'Criar Memória',
    `${CLAUDE_AGENT_URL}/memory/create`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        label: 'test',
        properties: {
          name: 'Test Memory',
          content: 'This is a test memory for A2A flow',
          type: 'test'
        }
      })
    }
  );

  // Buscar memória
  await testEndpoint(
    'Buscar Memória',
    `${CLAUDE_AGENT_URL}/memory/search`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: 'test',
        limit: 5
      })
    }
  );

  // 4. Testar Chat com Claude (com memória)
  log('\n=== 4. TESTANDO CHAT COM CLAUDE ===', 'yellow');

  const chatResponse = await testEndpoint(
    'Chat com Claude',
    `${CLAUDE_AGENT_URL}/claude/chat`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: 'What is the A2A protocol?',
        use_memory: true
      })
    }
  );

  // 5. Testar Criação de Tarefa A2A
  log('\n=== 5. TESTANDO TAREFAS A2A ===', 'yellow');

  const claudeTask = await testEndpoint(
    'Criar Tarefa Claude',
    `${CLAUDE_AGENT_URL}/tasks`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task: 'Explain the benefits of agent-to-agent communication',
        context: { domain: 'distributed systems' },
        streaming: false
      })
    }
  );

  if (claudeTask) {
    // Aguardar e verificar status da tarefa
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    await testEndpoint(
      'Status da Tarefa',
      `${CLAUDE_AGENT_URL}/tasks/${claudeTask.task_id}`
    );
  }

  // 6. Testar CrewAI
  log('\n=== 6. TESTANDO CREWAI ===', 'yellow');

  const crewTask = await testEndpoint(
    'Criar Tarefa CrewAI',
    `${CREW_AGENT_URL}/tasks`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task: 'Research and analyze the A2A protocol',
        context: { focus: 'architecture' }
      })
    }
  );

  // 7. Testar Tomada de Decisão
  log('\n=== 7. TESTANDO TOMADA DE DECISÃO ===', 'yellow');

  await testEndpoint(
    'Decisão Claude',
    `${CLAUDE_AGENT_URL}/decide`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        context: { situation: 'choosing communication protocol' },
        options: ['REST', 'GraphQL', 'WebSocket', 'gRPC']
      })
    }
  );

  await testEndpoint(
    'Decisão CrewAI',
    `${CREW_AGENT_URL}/decide`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        context: { project: 'microservices' },
        options: ['Kubernetes', 'Docker Swarm', 'Nomad']
      })
    }
  );

  // 8. Testar Aprendizagem
  log('\n=== 8. TESTANDO APRENDIZAGEM ===', 'yellow');

  await testEndpoint(
    'Aprendizagem Claude',
    `${CLAUDE_AGENT_URL}/learn`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        data: {
          topic: 'A2A Protocol',
          insight: 'Enables autonomous agent collaboration'
        },
        type: 'protocol'
      })
    }
  );

  // 9. Testar WebSocket
  log('\n=== 9. TESTANDO WEBSOCKET ===', 'yellow');

  await testWebSocket();

  // 10. Testar integração com Backend do Chat
  log('\n=== 10. TESTANDO INTEGRAÇÃO COM CHAT BACKEND ===', 'yellow');

  await testEndpoint(
    'Listar Agentes A2A',
    `${CHAT_BACKEND_URL}/api/a2a/agents`
  );

  log('\n✨ Testes concluídos!', 'magenta');
}

async function testWebSocket() {
  return new Promise((resolve) => {
    log('Testando conexão WebSocket com Claude...', 'blue');
    
    const ws = new WebSocket(`${CLAUDE_AGENT_URL.replace('http', 'ws')}/ws`);
    
    ws.on('open', () => {
      log('✅ WebSocket conectado', 'green');
      
      // Enviar mensagem de teste
      ws.send(JSON.stringify({
        type: 'handshake',
        client: 'test-script'
      }));
    });
    
    ws.on('message', (data) => {
      const message = JSON.parse(data);
      log(`📨 Mensagem recebida: ${JSON.stringify(message)}`, 'green');
      
      // Fechar após receber resposta
      ws.close();
    });
    
    ws.on('close', () => {
      log('WebSocket fechado', 'yellow');
      resolve();
    });
    
    ws.on('error', (error) => {
      log(`❌ Erro WebSocket: ${error.message}`, 'red');
      resolve();
    });
    
    // Timeout de 5 segundos
    setTimeout(() => {
      ws.close();
      resolve();
    }, 5000);
  });
}

// Executar testes
runTests().catch(error => {
  log(`\n❌ Erro fatal: ${error.message}`, 'red');
  process.exit(1);
});