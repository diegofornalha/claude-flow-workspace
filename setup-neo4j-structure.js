#!/usr/bin/env node
/**
 * Script para criar estrutura de dados Neo4j para integração MCP + A2A
 * Cria labels, índices e dados iniciais
 */

const MCPClient = require('./chat-app-claude-code-sdk/backend/mcp/client.js');

async function setupNeo4jStructure() {
  console.log('🚀 Configurando estrutura Neo4j para MCP + A2A...\n');
  
  const mcpClient = new MCPClient({
    debug: true
  });
  
  try {
    // 1. Conectar ao Neo4j via MCP
    console.log('📊 Conectando ao Neo4j...');
    await mcpClient.connect();
    console.log('✅ Conectado com sucesso!\n');
    
    // 2. Criar platforms
    console.log('🏗️ Criando plataformas...');
    
    const cliPlatform = await mcpClient.createMemory('platform', {
      name: 'Claude Code CLI',
      type: 'cli',
      description: 'Command-line interface for Claude Code',
      version: '1.0.0',
      created_at: new Date().toISOString()
    });
    console.log('✅ Platform CLI criada:', cliPlatform.id);
    
    const sdkPlatform = await mcpClient.createMemory('platform', {
      name: 'Claude Code SDK',
      type: 'web_app',
      description: 'Web application using Claude Code SDK with A2A',
      version: '2.0.0',
      has_a2a: true,
      has_mcp: true,
      created_at: new Date().toISOString()
    });
    console.log('✅ Platform SDK criada:', sdkPlatform.id);
    
    // 3. Criar agentes A2A
    console.log('\n🤖 Registrando agentes A2A...');
    
    const claudeAgent = await mcpClient.createMemory('a2a_agent', {
      name: 'Claude A2A Wrapper',
      type: 'assistant',
      url: 'http://localhost:8001',
      capabilities: [
        'natural_language_processing',
        'code_generation',
        'task_execution',
        'continuous_learning',
        'memory_integration'
      ],
      status: 'available',
      created_at: new Date().toISOString()
    });
    console.log('✅ Claude Agent registrado:', claudeAgent.id);
    
    const crewAgent = await mcpClient.createMemory('a2a_agent', {
      name: 'CrewAI Agent',
      type: 'team',
      url: 'http://localhost:8002',
      capabilities: [
        'multi_agent_coordination',
        'task_delegation',
        'role_based_agents',
        'collaborative_problem_solving'
      ],
      status: 'available',
      created_at: new Date().toISOString()
    });
    console.log('✅ CrewAI Agent registrado:', crewAgent.id);
    
    // 4. Criar sessão exemplo
    console.log('\n📝 Criando sessão exemplo...');
    
    const session = await mcpClient.createMemory('session', {
      id: `session-${Date.now()}`,
      platform: 'chat_app_sdk',
      has_a2a: true,
      has_mcp: true,
      agents_used: ['claude', 'crew-ai'],
      started_at: new Date().toISOString(),
      status: 'active'
    });
    console.log('✅ Sessão criada:', session.id);
    
    // 5. Criar mensagens exemplo com contexto A2A
    console.log('\n💬 Criando mensagens exemplo...');
    
    const userMsg = await mcpClient.createMemory('message', {
      content: 'What is the A2A protocol and how does it work?',
      type: 'user',
      session_id: session.properties.id,
      platform: 'chat_app_sdk',
      timestamp: new Date().toISOString()
    });
    console.log('✅ Mensagem do usuário criada:', userMsg.id);
    
    const assistantMsg = await mcpClient.createMemory('message', {
      content: 'The A2A (Agent-to-Agent) protocol is an open standard for autonomous agent communication...',
      type: 'assistant',
      agent_type: 'claude',
      session_id: session.properties.id,
      platform: 'chat_app_sdk',
      has_context: true,
      context_count: 3,
      timestamp: new Date().toISOString()
    });
    console.log('✅ Mensagem do assistente criada:', assistantMsg.id);
    
    // 6. Criar conexões
    console.log('\n🔗 Criando conexões...');
    
    await mcpClient.createConnection(
      userMsg.id,
      assistantMsg.id,
      'RESPONDED_BY',
      {
        agent: 'claude',
        latency_ms: 1234
      }
    );
    console.log('✅ Conexão RESPONDED_BY criada');
    
    await mcpClient.createConnection(
      session.id,
      claudeAgent.id,
      'USES_AGENT',
      {
        first_used: new Date().toISOString()
      }
    );
    console.log('✅ Conexão USES_AGENT criada');
    
    // 7. Criar tarefa A2A
    console.log('\n📋 Criando tarefa A2A...');
    
    const task = await mcpClient.createMemory('a2a_task', {
      id: `task-${Date.now()}`,
      agent: 'CrewAI Agent',
      type: 'research',
      state: 'completed',
      input: 'Research A2A protocol benefits',
      output: 'A2A enables autonomous agent collaboration...',
      created_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      duration_ms: 5432
    });
    console.log('✅ Tarefa A2A criada:', task.id);
    
    // 8. Criar conhecimento compartilhado
    console.log('\n📚 Criando base de conhecimento...');
    
    const knowledge1 = await mcpClient.createMemory('knowledge', {
      name: 'A2A Protocol',
      type: 'concept',
      description: 'Agent-to-Agent communication protocol for autonomous systems',
      content: 'A2A is an open protocol developed by Google for enabling autonomous agents to communicate and collaborate...',
      tags: ['protocol', 'a2a', 'agents', 'communication'],
      source: 'official_docs',
      created_at: new Date().toISOString()
    });
    console.log('✅ Conhecimento sobre A2A criado:', knowledge1.id);
    
    const knowledge2 = await mcpClient.createMemory('knowledge', {
      name: 'MCP Integration',
      type: 'architecture',
      description: 'Model Context Protocol integration with A2A',
      content: 'MCP provides memory and context management for A2A agents...',
      tags: ['mcp', 'memory', 'context', 'integration'],
      source: 'implementation',
      created_at: new Date().toISOString()
    });
    console.log('✅ Conhecimento sobre MCP criado:', knowledge2.id);
    
    // 9. Listar estatísticas
    console.log('\n📊 Estatísticas do Neo4j:');
    
    const labels = await mcpClient.listMemoryLabels();
    console.log('\nLabels criados:');
    labels.forEach(label => {
      console.log(`  - ${label.label}: ${label.count} nós`);
    });
    
    console.log('\n✨ Estrutura Neo4j configurada com sucesso!');
    console.log('\n🎯 Próximos passos:');
    console.log('  1. Iniciar os agentes A2A (Claude e CrewAI)');
    console.log('  2. Iniciar o backend do Chat App');
    console.log('  3. Testar integração completa');
    
    // Desconectar
    await mcpClient.disconnect();
    
  } catch (error) {
    console.error('❌ Erro:', error);
    process.exit(1);
  }
}

// Executar setup
setupNeo4jStructure();