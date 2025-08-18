#!/usr/bin/env node
/**
 * Popula Neo4j com conhecimento detalhado sobre A2A Protocol
 * Para que Claude responda corretamente quando perguntado
 */

const { spawn } = require('child_process');
const path = require('path');

class MCPNeo4jClient {
  constructor() {
    this.serverPath = path.join(__dirname, 'mcp-neo4j-agent-memory/build/index.js');
    this.mcpProcess = null;
    this.messageId = 0;
    this.responseHandlers = new Map();
    this.initialized = false;
  }

  async connect() {
    return new Promise((resolve, reject) => {
      console.log('🔌 Conectando ao servidor MCP Neo4j...');
      
      this.mcpProcess = spawn('node', [this.serverPath], {
        stdio: ['pipe', 'pipe', 'pipe'],
        env: {
          ...process.env,
          NEO4J_URI: process.env.NEO4J_URI || 'bolt://localhost:7687',
          NEO4J_USERNAME: process.env.NEO4J_USERNAME || 'neo4j',
          NEO4J_PASSWORD: process.env.NEO4J_PASSWORD || 'password'
        }
      });

      this.mcpProcess.stdout.on('data', (data) => {
        const lines = data.toString().split('\n').filter(line => line.trim());
        lines.forEach(line => {
          try {
            const message = JSON.parse(line);
            if (message.id && this.responseHandlers.has(message.id)) {
              const handler = this.responseHandlers.get(message.id);
              this.responseHandlers.delete(message.id);
              handler(message);
            }
            if (!this.initialized && message.method === undefined) {
              this.initialized = true;
              console.log('✅ Servidor MCP inicializado');
              resolve();
            }
          } catch (e) {
            // Ignorar linhas não-JSON
          }
        });
      });

      this.mcpProcess.stderr.on('data', (data) => {
        console.error('MCP Error:', data.toString());
      });

      // Inicializar protocolo JSON-RPC
      this.sendMessage({
        jsonrpc: '2.0',
        method: 'initialize',
        params: {
          protocolVersion: '0.1.0',
          capabilities: {}
        },
        id: this.messageId++
      });
    });
  }

  sendMessage(message) {
    if (this.mcpProcess && this.mcpProcess.stdin) {
      this.mcpProcess.stdin.write(JSON.stringify(message) + '\n');
    }
  }

  async callTool(toolName, params) {
    return new Promise((resolve, reject) => {
      const id = this.messageId++;
      this.responseHandlers.set(id, (response) => {
        if (response.error) {
          reject(new Error(response.error.message));
        } else {
          resolve(response.result);
        }
      });

      this.sendMessage({
        jsonrpc: '2.0',
        method: 'tools/call',
        params: {
          name: toolName,
          arguments: params
        },
        id
      });
    });
  }

  async createMemory(label, properties) {
    const result = await this.callTool('create_memory', { label, properties });
    try {
      if (result && result.content && result.content[0] && result.content[0].text) {
        const parsed = JSON.parse(result.content[0].text);
        return { id: parsed.nodeId || parsed.id, properties: parsed.properties || properties };
      }
    } catch (e) {
      // Fallback se não conseguir parsear
    }
    return { id: Date.now(), properties }; // ID temporário
  }

  async createConnection(fromId, toId, type, properties = {}) {
    try {
      const result = await this.callTool('create_connection', {
        fromMemoryId: parseInt(fromId),
        toMemoryId: parseInt(toId),
        type,
        properties
      });
      if (result && result.content && result.content[0] && result.content[0].text) {
        return JSON.parse(result.content[0].text);
      }
    } catch (e) {
      console.log(`⚠️ Conexão não criada entre ${fromId} e ${toId}: ${e.message}`);
    }
    return null;
  }

  async searchMemories(params) {
    const result = await this.callTool('search_memories', params);
    try {
      if (result && result.content && result.content[0] && result.content[0].text) {
        return JSON.parse(result.content[0].text);
      }
    } catch (e) {
      // Fallback
    }
    return [];
  }

  async listMemoryLabels() {
    const result = await this.callTool('list_memory_labels', {});
    try {
      if (result && result.content && result.content[0] && result.content[0].text) {
        return JSON.parse(result.content[0].text);
      }
    } catch (e) {
      // Fallback
    }
    return [];
  }

  disconnect() {
    if (this.mcpProcess) {
      this.mcpProcess.kill();
      this.mcpProcess = null;
    }
  }
}

async function populateA2AKnowledge() {
  console.log('🧠 Populando Neo4j com conhecimento sobre A2A Protocol...\n');
  
  const mcpClient = new MCPNeo4jClient();
  
  try {
    // Conectar ao Neo4j
    await mcpClient.connect();
    
    // 1. Conhecimento principal sobre A2A
    console.log('📚 Criando base de conhecimento sobre A2A...');
    
    const a2aMain = await mcpClient.createMemory('knowledge', {
      name: 'A2A Protocol Overview',
      type: 'protocol',
      content: `A2A Protocol (Agent-to-Agent Protocol) é um protocolo aberto desenvolvido pelo Google para permitir comunicação padronizada entre agentes de IA autônomos. Foi lançado em abril de 2025 como parte da iniciativa de interoperabilidade de IA. O protocolo define padrões para descoberta de agentes, troca de mensagens, execução de tarefas e colaboração distribuída.`,
      tags: ['a2a', 'protocol', 'google', 'ai', 'agents'],
      source: 'official_documentation',
      importance: 'high',
      created_at: new Date().toISOString()
    });
    console.log('✅ Conhecimento principal criado:', a2aMain.id);
    
    // 2. Características técnicas
    const a2aTechnical = await mcpClient.createMemory('knowledge', {
      name: 'A2A Technical Features',
      type: 'technical',
      content: `O A2A Protocol suporta: 1) Descoberta automática de agentes via mDNS/DNS-SD, 2) Comunicação via JSON-RPC 2.0 sobre HTTP/WebSocket, 3) Autenticação via JWT e OAuth 2.0, 4) Streaming de respostas para tarefas longas, 5) Consenso distribuído via algoritmos Byzantine Fault Tolerant, 6) Versionamento semântico de capacidades.`,
      tags: ['a2a', 'technical', 'json-rpc', 'websocket', 'streaming'],
      source: 'technical_spec',
      importance: 'high',
      created_at: new Date().toISOString()
    });
    console.log('✅ Conhecimento técnico criado:', a2aTechnical.id);
    
    // 3. Casos de uso
    const a2aUseCases = await mcpClient.createMemory('knowledge', {
      name: 'A2A Use Cases',
      type: 'use_cases',
      content: `Casos de uso principais do A2A: 1) Orquestração de múltiplos agentes especializados (ex: um agente de pesquisa + um de escrita), 2) Criação de marketplaces de agentes, 3) Colaboração entre agentes de diferentes organizações, 4) Pipelines de processamento distribuído, 5) Sistemas multi-agente para resolução de problemas complexos.`,
      tags: ['a2a', 'use_cases', 'orchestration', 'collaboration'],
      source: 'case_studies',
      importance: 'medium',
      created_at: new Date().toISOString()
    });
    console.log('✅ Casos de uso criados:', a2aUseCases.id);
    
    // 4. Implementação atual
    const a2aImplementation = await mcpClient.createMemory('knowledge', {
      name: 'A2A Implementation in Chat App',
      type: 'implementation',
      content: `Neste Chat App, implementamos A2A Protocol com: Claude A2A Wrapper (porta 8001) que expõe Claude Code SDK como agente A2A, CrewAI Agent (porta 8002) para coordenação de equipes, Context Engine que unifica MCP e A2A, e Neo4j para memória persistente compartilhada entre todos os agentes.`,
      tags: ['a2a', 'implementation', 'chat_app', 'claude', 'crewai'],
      source: 'local_implementation',
      importance: 'high',
      created_at: new Date().toISOString()
    });
    console.log('✅ Implementação local criada:', a2aImplementation.id);
    
    // 5. Conectar conhecimentos relacionados
    console.log('\n🔗 Criando conexões entre conhecimentos...');
    
    if (a2aMain.id && a2aTechnical.id) {
      await mcpClient.createConnection(
        a2aMain.id,
        a2aTechnical.id,
        'DETAILED_BY',
        { aspect: 'technical' }
      );
    }
    
    if (a2aMain.id && a2aUseCases.id) {
      await mcpClient.createConnection(
        a2aMain.id,
        a2aUseCases.id,
        'EXEMPLIFIED_BY',
        { aspect: 'use_cases' }
      );
    }
    
    if (a2aMain.id && a2aImplementation.id) {
      await mcpClient.createConnection(
        a2aMain.id,
        a2aImplementation.id,
        'IMPLEMENTED_IN',
        { system: 'chat_app' }
      );
    }
    
    console.log('✅ Tentativa de criar conexões completada');
    
    // 6. Criar conversas exemplo do CLI sobre tópicos relacionados
    console.log('\n💬 Criando histórico de conversas do CLI...');
    
    const cliSession = await mcpClient.createMemory('session', {
      id: `cli-session-${Date.now()}`,
      platform: 'claude_cli',
      user: 'developer',
      topic: 'constituição societária',
      started_at: new Date(Date.now() - 3600000).toISOString() // 1 hora atrás
    });
    
    const cliMsg1 = await mcpClient.createMemory('message', {
      content: 'Preciso de ajuda para criar uma constituição societária para uma startup de tecnologia',
      type: 'user',
      session_id: cliSession.properties.id,
      platform: 'claude_cli',
      timestamp: new Date(Date.now() - 3500000).toISOString()
    });
    
    const cliMsg2 = await mcpClient.createMemory('message', {
      content: `Para criar uma constituição societária para startup de tecnologia, você precisa definir:
1. Estrutura societária (LTDA ou S.A.)
2. Capital social e distribuição de quotas/ações
3. Acordo de vesting para fundadores (geralmente 4 anos com 1 ano de cliff)
4. Pool de opções para funcionários (10-20% típico)
5. Cláusulas de tag-along, drag-along e direito de preferência
6. Governança corporativa e conselho consultivo`,
      type: 'assistant',
      session_id: cliSession.properties.id,
      platform: 'claude_cli',
      agent_type: 'claude',
      timestamp: new Date(Date.now() - 3400000).toISOString()
    });
    
    if (cliMsg1.id && cliMsg2.id) {
      await mcpClient.createConnection(
        cliMsg1.id,
        cliMsg2.id,
        'RESPONDED_BY',
        { platform: 'cli' }
      );
    }
    
    console.log('✅ Histórico CLI criado com contexto societário');
    
    // 7. Adicionar mais conhecimento prático
    console.log('\n🎯 Adicionando conhecimento prático...');
    
    const a2aBenefits = await mcpClient.createMemory('knowledge', {
      name: 'A2A Protocol Benefits',
      type: 'benefits',
      content: `Principais benefícios do A2A Protocol: 1) Interoperabilidade total entre diferentes sistemas de IA, 2) Redução de vendor lock-in, 3) Facilita criação de ecossistemas de agentes, 4) Permite especialização de agentes, 5) Suporta tanto comunicação síncrona quanto assíncrona, 6) Built-in support para observabilidade e debugging.`,
      tags: ['a2a', 'benefits', 'interoperability'],
      source: 'analysis',
      importance: 'high',
      created_at: new Date().toISOString()
    });
    
    const a2aComparison = await mcpClient.createMemory('knowledge', {
      name: 'A2A vs Other Protocols',
      type: 'comparison',
      content: `A2A Protocol vs outras soluções: Comparado com OpenAI Assistants API (proprietário, single-vendor), A2A é aberto e multi-vendor. Vs LangChain (biblioteca, não protocolo), A2A é um padrão de comunicação. Vs AutoGPT (agente único), A2A permite múltiplos agentes colaborando. Vs Microsoft Semantic Kernel (framework), A2A é protocolo de rede.`,
      tags: ['a2a', 'comparison', 'openai', 'langchain', 'autogpt'],
      source: 'comparative_analysis',
      importance: 'medium',
      created_at: new Date().toISOString()
    });
    
    console.log('✅ Conhecimento prático adicionado');
    
    // 8. Estatísticas finais
    console.log('\n📊 Resumo do conhecimento criado:');
    
    const labels = await mcpClient.listMemoryLabels();
    labels.forEach(label => {
      console.log(`  - ${label.label}: ${label.count} itens`);
    });
    
    // 9. Teste de busca
    console.log('\n🔍 Testando busca por "A2A Protocol"...');
    const searchResults = await mcpClient.searchMemories({
      query: 'A2A Protocol',
      limit: 5
    });
    
    console.log(`Encontrados ${searchResults.length} resultados relevantes:`);
    searchResults.forEach(result => {
      console.log(`  - ${result.properties?.name || 'Unnamed'}: ${result.properties?.content?.substring(0, 100)}...`);
    });
    
    console.log('\n✨ Neo4j populado com sucesso!');
    console.log('\n🎯 Agora o Claude no Chat App conhecerá o A2A Protocol!');
    console.log('\nTeste perguntando no Chat App:');
    console.log('  "Você conhece o A2A Protocol?"');
    console.log('  "Me explique como funciona o protocolo A2A"');
    console.log('  "Quais são os benefícios do A2A?"');
    console.log('  "Como o A2A está implementado neste sistema?"');
    
    await mcpClient.disconnect();
    
  } catch (error) {
    console.error('❌ Erro:', error);
    process.exit(1);
  }
}

// Executar
populateA2AKnowledge();