#!/usr/bin/env node

/**
 * Script de Teste da Integração de Memória Neo4j
 * Testa se o MemoryMiddleware está funcionando corretamente
 */

const axios = require('axios');
const colors = require('colors');

const BASE_URL = 'http://localhost:8080';
const API_BASE = `${BASE_URL}/api/memory/v2`;

// Função auxiliar para fazer requisições
async function makeRequest(method, endpoint, data = null) {
  try {
    const config = {
      method,
      url: `${API_BASE}${endpoint}`,
      headers: { 'Content-Type': 'application/json' }
    };
    
    if (data) {
      config.data = data;
    }
    
    const response = await axios(config);
    return { success: true, data: response.data };
  } catch (error) {
    return { 
      success: false, 
      error: error.response?.data?.error || error.message 
    };
  }
}

// Testes
async function runTests() {
  console.log('\n🧪 Iniciando Testes de Integração com Neo4j Memory\n'.cyan.bold);
  
  let testsPassed = 0;
  let testsFailed = 0;
  
  // Test 1: Verificar Status
  console.log('🔍 Test 1: Verificar Status do Sistema'.yellow);
  const statsResult = await makeRequest('GET', '/stats');
  if (statsResult.success) {
    console.log('✅ Status obtido com sucesso'.green);
    console.log(`   Neo4j conectado: ${statsResult.data.stats.neo4j.connected}`);
    console.log(`   Sessões ativas: ${statsResult.data.stats.sessions.active}`);
    console.log(`   Total de mensagens: ${statsResult.data.stats.sessions.totalMessages}`);
    testsPassed++;
  } else {
    console.log(`❌ Falha ao obter status: ${statsResult.error}`.red);
    testsFailed++;
  }
  
  // Test 2: Processar Mensagem
  console.log('\n💬 Test 2: Processar Mensagem com Contexto'.yellow);
  const messageData = {
    message: {
      content: 'Como configurar o Neo4j para usar com MCP?',
      role: 'user'
    },
    userId: 'test-user-123',
    sessionId: 'test-session-456'
  };
  
  const processResult = await makeRequest('POST', '/process', messageData);
  if (processResult.success) {
    console.log('✅ Mensagem processada com sucesso'.green);
    const msg = processResult.data.message;
    console.log(`   Intenção detectada: ${msg.intent}`);
    console.log(`   Sentimento: ${msg.sentiment}`);
    console.log(`   Tags: ${msg.tags?.join(', ')}`);
    console.log(`   Entidades: ${msg.entities?.length || 0} encontradas`);
    testsPassed++;
  } else {
    console.log(`❌ Falha ao processar mensagem: ${processResult.error}`.red);
    testsFailed++;
  }
  
  // Test 3: Buscar Memórias
  console.log('\n🔍 Test 3: Buscar Memórias'.yellow);
  const searchResult = await makeRequest('GET', '/search?query=Neo4j&limit=5');
  if (searchResult.success) {
    console.log('✅ Busca realizada com sucesso'.green);
    console.log(`   Memórias encontradas: ${searchResult.data.count}`);
    if (searchResult.data.memories && searchResult.data.memories.length > 0) {
      searchResult.data.memories.slice(0, 3).forEach((mem, i) => {
        console.log(`   ${i+1}. [${mem.label}] ${mem.properties?.name || mem.properties?.content?.substring(0, 50) || 'N/A'}`);
      });
    }
    testsPassed++;
  } else {
    console.log(`❌ Falha na busca: ${searchResult.error}`.red);
    testsFailed++;
  }
  
  // Test 4: Obter Contexto
  console.log('\n🧠 Test 4: Obter Contexto para Mensagem'.yellow);
  const contextData = {
    message: { content: 'Continuar configuração do Neo4j' },
    userId: 'test-user-123',
    sessionId: 'test-session-456'
  };
  
  const contextResult = await makeRequest('POST', '/context', contextData);
  if (contextResult.success) {
    console.log('✅ Contexto obtido com sucesso'.green);
    const ctx = contextResult.data.context;
    if (ctx) {
      Object.keys(ctx).forEach(type => {
        if (ctx[type] && ctx[type].length > 0) {
          console.log(`   ${type}: ${ctx[type].length} itens`);
        }
      });
    }
    testsPassed++;
  } else {
    console.log(`❌ Falha ao obter contexto: ${contextResult.error}`.red);
    testsFailed++;
  }
  
  // Test 5: Resumo da Sessão
  console.log('\n📊 Test 5: Obter Resumo da Sessão'.yellow);
  const summaryResult = await makeRequest('GET', '/session/test-session-456/summary');
  if (summaryResult.success) {
    console.log('✅ Resumo obtido com sucesso'.green);
    const summary = summaryResult.data.summary;
    console.log(`   Mensagens: ${summary.messageCount}`);
    console.log(`   Intenções: ${summary.intents?.join(', ') || 'N/A'}`);
    console.log(`   Sentimentos: 😊 ${summary.sentiments?.positive || 0} | 😐 ${summary.sentiments?.neutral || 0} | 😟 ${summary.sentiments?.negative || 0}`);
    testsPassed++;
  } else {
    console.log(`❌ Falha ao obter resumo: ${summaryResult.error}`.red);
    testsFailed++;
  }
  
  // Test 6: Criar Memória Manual
  console.log('\n📝 Test 6: Criar Memória Manual'.yellow);
  const createData = {
    label: 'knowledge',
    properties: {
      name: 'Neo4j MCP Integration',
      description: 'Integração do Neo4j com MCP para memória persistente',
      category: 'technical',
      importance: 'high'
    }
  };
  
  const createResult = await makeRequest('POST', '/create', createData);
  if (createResult.success) {
    console.log('✅ Memória criada com sucesso'.green);
    console.log(`   ID: ${createResult.data.memory?.id}`);
    console.log(`   Label: ${createResult.data.memory?.label}`);
    testsPassed++;
  } else {
    console.log(`❌ Falha ao criar memória: ${createResult.error}`.red);
    testsFailed++;
  }
  
  // Test 7: Exportar Sessão
  console.log('\n💾 Test 7: Exportar Sessão'.yellow);
  const exportResult = await makeRequest('GET', '/session/test-session-456/export');
  if (exportResult.success) {
    console.log('✅ Sessão exportada com sucesso'.green);
    console.log(`   Session ID: ${exportResult.data.data?.sessionId}`);
    console.log(`   Mensagens: ${exportResult.data.data?.messages?.length || 0}`);
    console.log(`   Exportado em: ${exportResult.data.data?.exported_at}`);
    testsPassed++;
  } else {
    console.log(`❌ Falha ao exportar: ${exportResult.error}`.red);
    testsFailed++;
  }
  
  // Resultado Final
  console.log('\n' + '='.repeat(60));
  console.log('🏁 RESULTADO DOS TESTES'.cyan.bold);
  console.log('='.repeat(60));
  console.log(`✅ Testes aprovados: ${testsPassed}`.green.bold);
  console.log(`❌ Testes falhados: ${testsFailed}`.red.bold);
  
  const successRate = ((testsPassed / (testsPassed + testsFailed)) * 100).toFixed(1);
  if (testsFailed === 0) {
    console.log(`\n🎆 SUCESSO TOTAL! Taxa de sucesso: ${successRate}%`.green.bold);
  } else if (successRate >= 70) {
    console.log(`\n👍 BOM! Taxa de sucesso: ${successRate}%`.yellow.bold);
  } else {
    console.log(`\n🔧 PRECISA DE ATENÇÃO! Taxa de sucesso: ${successRate}%`.red.bold);
  }
  
  // Dicas
  if (testsFailed > 0) {
    console.log('\n💡 DICAS PARA RESOLVER PROBLEMAS:'.yellow);
    console.log('1. Verifique se o servidor está rodando: npm start');
    console.log('2. Verifique se o Neo4j está rodando: neo4j status');
    console.log('3. Verifique se o MCP está configurado: claude mcp list');
    console.log('4. Verifique os logs do servidor para mais detalhes');
  }
}

// Verificar se o servidor está rodando
async function checkServer() {
  try {
    await axios.get(`${BASE_URL}/api/health`);
    return true;
  } catch (error) {
    return false;
  }
}

// Main
async function main() {
  console.log('🚀 Kingston Memory Integration Test Suite'.cyan.bold);
  console.log('Testando integração com Neo4j via MemoryMiddleware\n');
  
  // Verificar servidor
  console.log('🔌 Verificando conexão com servidor...'.yellow);
  const serverUp = await checkServer();
  
  if (!serverUp) {
    console.log('❌ Servidor não está respondendo em http://localhost:8080'.red.bold);
    console.log('\nPor favor, inicie o servidor primeiro:');
    console.log('  cd chat-app-claude-code-sdk/backend');
    console.log('  npm start\n');
    process.exit(1);
  }
  
  console.log('✅ Servidor conectado!\n'.green);
  
  // Rodar testes
  await runTests();
}

// Executar
main().catch(error => {
  console.error('❌ Erro fatal:'.red.bold, error.message);
  process.exit(1);
});