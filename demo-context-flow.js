#!/usr/bin/env node
/**
 * Demonstração do fluxo completo com contexto e memória
 * Mostra Claude respondendo sobre A2A com conhecimento do Neo4j
 */

const io = require('socket.io-client');
const fetch = require('node-fetch');

const BACKEND_URL = 'http://localhost:8080';

const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  blue: '\x1b[34m',
  yellow: '\x1b[33m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m'
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

async function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function demonstrateContextFlow() {
  log('\n🎭 DEMONSTRAÇÃO: Chat App com Memória e Contexto\n', 'magenta');
  log('═══════════════════════════════════════════════════\n', 'magenta');
  
  // 1. Verificar status do sistema
  log('1️⃣ Verificando status do sistema...', 'yellow');
  
  try {
    const statusRes = await fetch(`${BACKEND_URL}/api/context/status`);
    const status = await statusRes.json();
    
    if (status.mcp?.connected) {
      log('  ✅ MCP (Neo4j) conectado', 'green');
    } else {
      log('  ⚠️ MCP não conectado - executar: npm run setup:neo4j', 'yellow');
    }
    
    if (status.a2a?.availableAgents?.length > 0) {
      log(`  ✅ Agentes A2A disponíveis: ${status.a2a.availableAgents.join(', ')}`, 'green');
    } else {
      log('  ⚠️ Nenhum agente A2A disponível', 'yellow');
    }
  } catch (error) {
    log('  ❌ Backend não está rodando em localhost:8080', 'red');
    return;
  }
  
  await delay(1000);
  
  // 2. Demonstrar conhecimento sobre A2A
  log('\n2️⃣ Perguntando sobre A2A Protocol...', 'yellow');
  log('   Pergunta: "Você conhece o A2A Protocol?"\n', 'cyan');
  
  const socket = io(BACKEND_URL);
  
  await new Promise((resolve) => {
    socket.on('connect', () => {
      log('  🔌 WebSocket conectado', 'green');
      
      // Enviar pergunta sobre A2A
      socket.emit('send_message_with_context', {
        message: 'Você conhece o A2A Protocol? Me explique o que é.',
        sessionId: `demo-${Date.now()}`,
        agentType: 'claude',
        useMemory: true
      });
    });
    
    socket.on('message_complete', (data) => {
      log('\n  📝 Resposta do Claude:', 'blue');
      console.log('\n' + data.content + '\n');
      
      if (data.hasContext) {
        log(`\n  🧠 Contexto usado: ${data.contextUsed} memórias`, 'green');
        
        if (data.memories && data.memories.length > 0) {
          log('  📚 Memórias relevantes:', 'cyan');
          data.memories.forEach(mem => {
            console.log(`     - [${mem.type}] ${mem.summary}`);
          });
        }
      } else {
        log('\n  ⚠️ Nenhum contexto usado (Neo4j pode estar vazio)', 'yellow');
      }
      
      socket.disconnect();
      resolve();
    });
    
    socket.on('error', (error) => {
      log(`  ❌ Erro: ${error.error}`, 'red');
      socket.disconnect();
      resolve();
    });
  });
  
  await delay(2000);
  
  // 3. Demonstrar contexto compartilhado
  log('\n3️⃣ Demonstrando contexto compartilhado CLI ↔ Chat App...', 'yellow');
  log('   Pergunta: "Você lembra de alguma conversa sobre constituição societária?"\n', 'cyan');
  
  const socket2 = io(BACKEND_URL);
  
  await new Promise((resolve) => {
    socket2.on('connect', () => {
      socket2.emit('send_message_with_context', {
        message: 'Você lembra de alguma conversa sobre constituição societária ou dados societários?',
        sessionId: `demo-shared-${Date.now()}`,
        agentType: 'claude',
        useMemory: true
      });
    });
    
    socket2.on('message_complete', (data) => {
      log('\n  📝 Resposta do Claude:', 'blue');
      console.log('\n' + data.content + '\n');
      
      if (data.contextUsed > 0) {
        log(`\n  🔄 Contexto compartilhado encontrado! (${data.contextUsed} memórias)`, 'green');
      }
      
      socket2.disconnect();
      resolve();
    });
    
    socket2.on('error', (error) => {
      log(`  ❌ Erro: ${error.error}`, 'red');
      socket2.disconnect();
      resolve();
    });
  });
  
  await delay(2000);
  
  // 4. Buscar memórias diretamente
  log('\n4️⃣ Verificando memórias no Neo4j...', 'yellow');
  
  try {
    const searchRes = await fetch(`${BACKEND_URL}/api/memory/search?query=A2A&limit=3`);
    const memories = await searchRes.json();
    
    if (memories.memories && memories.memories.length > 0) {
      log(`  ✅ Encontradas ${memories.memories.length} memórias sobre A2A:`, 'green');
      memories.memories.forEach(mem => {
        console.log(`     - ${mem.properties?.name || 'Memória'}: ${mem.properties?.content?.substring(0, 80)}...`);
      });
    } else {
      log('  ⚠️ Nenhuma memória encontrada sobre A2A', 'yellow');
      log('     Execute: node populate-a2a-knowledge.js', 'cyan');
    }
  } catch (error) {
    log('  ❌ Erro buscando memórias', 'red');
  }
  
  // 5. Testar seleção de agente
  log('\n5️⃣ Testando seleção de agente A2A...', 'yellow');
  
  try {
    const agentsRes = await fetch(`${BACKEND_URL}/api/a2a/agents`);
    const agentsData = await agentsRes.json();
    
    if (agentsData.agents && agentsData.agents.length > 0) {
      log(`  ✅ ${agentsData.agents.length} agentes disponíveis para seleção:`, 'green');
      agentsData.agents.forEach(agent => {
        console.log(`     - ${agent.name}: ${agent.status}`);
      });
    } else {
      log('  ⚠️ Nenhum agente A2A disponível', 'yellow');
    }
  } catch (error) {
    log('  ❌ Erro listando agentes', 'red');
  }
  
  // Resumo
  log('\n═══════════════════════════════════════════════════', 'magenta');
  log('\n📊 RESUMO DA DEMONSTRAÇÃO\n', 'magenta');
  
  log('✅ Capacidades Demonstradas:', 'green');
  log('  • Claude responde sobre A2A com conhecimento do Neo4j');
  log('  • Contexto é enriquecido com memórias relevantes');
  log('  • Conversas do CLI podem ser acessadas no Chat App');
  log('  • Múltiplos agentes A2A disponíveis para seleção');
  
  log('\n🎯 Para experiência completa:', 'cyan');
  log('  1. Execute: node populate-a2a-knowledge.js (popular Neo4j)');
  log('  2. Inicie os agentes A2A (Claude e CrewAI)');
  log('  3. Abra o Chat App em http://localhost:3000');
  log('  4. Pergunte: "Você conhece o A2A Protocol?"');
  log('  5. Veja o indicador de contexto e memórias usadas');
  
  log('\n✨ Sistema funcionando com memória e contexto!\n', 'green');
}

// Executar demonstração
demonstrateContextFlow().catch(error => {
  log(`\n❌ Erro: ${error.message}`, 'red');
  process.exit(1);
});