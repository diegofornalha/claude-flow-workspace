#!/usr/bin/env node
/**
 * Claude A2A Wrapper
 * Expõe Claude Code SDK como agente A2A com integração MCP e Neo4j Memory
 */

const Fastify = require('fastify');
const cors = require('@fastify/cors');
const websocket = require('@fastify/websocket');
const { v4: uuidv4 } = require('uuid');
const dotenv = require('dotenv');
const { query } = require('@anthropic-ai/claude-code');

dotenv.config();

// Simular integração com Neo4j via MCP (em produção, usar cliente MCP real)
class MCPNeo4jMemory {
  constructor() {
    this.memories = new Map();
    this.connections = new Map();
  }

  async searchMemories(query, options = {}) {
    // Simular busca de memórias
    const results = [];
    for (const [id, memory] of this.memories) {
      if (memory.properties.content?.includes(query) || 
          memory.properties.name?.includes(query)) {
        results.push({
          id,
          ...memory,
          relevance: Math.random() // Simular score de relevância
        });
      }
    }
    return results.sort((a, b) => b.relevance - a.relevance).slice(0, options.limit || 10);
  }

  async createMemory(label, properties) {
    const id = Date.now();
    const memory = {
      id,
      label,
      properties: {
        ...properties,
        created_at: new Date().toISOString()
      }
    };
    this.memories.set(id, memory);
    return { id, ...memory };
  }

  async createConnection(fromId, toId, type, properties = {}) {
    const connectionId = `${fromId}-${type}-${toId}`;
    const connection = {
      id: connectionId,
      fromMemoryId: fromId,
      toMemoryId: toId,
      type,
      properties: {
        ...properties,
        created_at: new Date().toISOString()
      }
    };
    this.connections.set(connectionId, connection);
    return connection;
  }

  async updateMemory(nodeId, properties) {
    const memory = this.memories.get(nodeId);
    if (memory) {
      memory.properties = {
        ...memory.properties,
        ...properties,
        updated_at: new Date().toISOString()
      };
      return { success: true, memory };
    }
    return { success: false, error: 'Memory not found' };
  }

  async listMemoryLabels() {
    const labels = new Map();
    for (const memory of this.memories.values()) {
      labels.set(memory.label, (labels.get(memory.label) || 0) + 1);
    }
    return Array.from(labels.entries()).map(([label, count]) => ({ label, count }));
  }
}

class ClaudeA2AAgent {
  constructor() {
    this.agentId = `claude-agent-${uuidv4().slice(0, 8)}`;
    this.agentName = 'Claude A2A Agent';
    this.agentType = 'assistant';
    this.sessions = new Map(); // Múltiplas sessões Claude
    this.tasks = new Map(); // Tarefas A2A em execução
    this.peers = new Map(); // Peers conectados
    this.knowledge = []; // Base de conhecimento local
    this.memory = new MCPNeo4jMemory(); // Sistema de memória via MCP
    this.metrics = {
      tasksCompleted: 0,
      decisionseMade: 0,
      learningEvents: 0,
      memoriesCreated: 0,
      connectionsCreated: 0,
      startedAt: new Date().toISOString()
    };

    // Inicializar servidor Fastify
    this.server = Fastify({
      logger: {
        level: process.env.LOG_LEVEL || 'info'
      }
    });
  }

  async setupServer() {
    console.log('🔧 Configurando servidor...');
    // Registrar plugins
    await this.server.register(cors, {
      origin: true,
      credentials: true
    });

    await this.server.register(websocket);

    // Rotas A2A padrão
    this.setupA2ARoutes();
    
    // Rotas específicas do Claude
    this.setupClaudeRoutes();

    // WebSocket para comunicação P2P
    this.setupWebSocket();
  }

  setupA2ARoutes() {
    // Agent Card Padrão A2A v2.0
    this.server.get('/.well-known/agent.json', async (request, reply) => {
      return {
        agent: {
          id: this.agentId,
          name: this.agentName,
          type: this.agentType,
          version: '1.0.0'
        },
        protocol: {
          version: 'a2a/2.0',
          features: [
            'capabilities_negotiation',
            'streaming_responses',
            'p2p_discovery',
            'autonomous_learning',
            'mcp_integration'
          ]
        },
        capabilities: {
          core: [
            'natural_language_processing',
            'code_generation',
            'task_execution',
            'multi_session_support'
          ],
          advanced: [
            'continuous_learning',
            'autonomous_decision_making',
            'streaming_responses',
            'mcp_integration',
            'memory_augmented_generation'
          ]
        },
        endpoints: {
          base_url: `http://localhost:${process.env.PORT || 8001}`,
          agent_card: '/.well-known/agent.json',
          health: '/health',
          negotiate: '/negotiate',
          discover: '/discover',
          tasks: '/tasks',
          streaming: '/stream',
          claude: {
            chat: '/claude/chat',
            stream: '/claude/stream',
            sessions: '/claude/sessions'
          },
          memory: {
            search: '/memory/search',
            create: '/memory/create',
            connect: '/memory/connect',
            labels: '/memory/labels'
          }
        },
        mcp: {
          available: true,
          services: ['neo4j-memory', 'filesystem', 'desktop-commander']
        }
      };
    });

    // Endpoint raiz para compatibilidade
    this.server.get('/', async (request, reply) => {
      return {
        message: 'Claude A2A Agent',
        agent_card: '/.well-known/agent.json',
        status: 'online'
      };
    });

    // Health check
    this.server.get('/health', async () => ({
      status: 'healthy',
      agent_id: this.agentId,
      uptime: this.calculateUptime()
    }));

    // Capabilities Negotiation - Padrão A2A
    this.server.post('/negotiate', async (request, reply) => {
      const { capabilities: peerCapabilities, agent_id: peerId } = request.body;
      
      const ourCapabilities = [
        'natural_language_processing',
        'code_generation', 
        'task_execution',
        'continuous_learning',
        'streaming_responses',
        'multi_session_support',
        'mcp_integration',
        'memory_augmented_generation'
      ];

      const compatible = peerCapabilities ? 
        ourCapabilities.filter(cap => peerCapabilities.includes(cap)) : [];
      
      const learningOpportunities = peerCapabilities ?
        peerCapabilities.filter(cap => !ourCapabilities.includes(cap)) : [];

      return {
        agent_id: this.agentId,
        negotiation_result: {
          compatible_capabilities: compatible,
          offered_capabilities: ourCapabilities,
          learning_opportunities: learningOpportunities,
          collaboration_level: compatible.length > 3 ? 'high' : 
                             compatible.length > 1 ? 'medium' : 'low'
        },
        proposed_collaboration: {
          code_assistance: true,
          knowledge_sharing: true,
          task_delegation: true,
          mcp_resource_sharing: true
        }
      };
    });

    // P2P Discovery - Padrão A2A
    this.server.get('/discover', async (request, reply) => {
      return {
        agent_id: this.agentId,
        discovery_info: {
          agent_type: 'assistant',
          capabilities: [
            'natural_language_processing',
            'code_generation',
            'task_execution', 
            'mcp_integration'
          ],
          availability: 'online',
          load: this.tasks.size / 100, // 100 = estimated max concurrent tasks
          preferred_protocols: ['a2a/2.0'],
          peer_requirements: {
            min_trust_level: 0.8,
            compatible_capabilities: ['task_execution', 'knowledge_sharing']
          }
        },
        network_info: {
          current_peers: this.peers.size,
          max_peers: 100,
          discovery_timestamp: new Date().toISOString()
        },
        mcp_services: {
          available: ['neo4j-memory', 'filesystem', 'desktop-commander'],
          shareable: true
        }
      };
    });

    // Status detalhado
    this.server.get('/status', async () => ({
      agent_id: this.agentId,
      sessions_active: this.sessions.size,
      tasks_running: this.tasks.size,
      peers_connected: this.peers.size,
      metrics: this.metrics
    }));

    // Criar nova tarefa A2A
    this.server.post('/tasks', async (request, reply) => {
      const { task, context, streaming = false } = request.body;
      
      const taskId = `task-${uuidv4()}`;
      const taskData = {
        id: taskId,
        task,
        context,
        status: 'pending',
        created_at: new Date().toISOString(),
        streaming
      };

      this.tasks.set(taskId, taskData);

      // Executar tarefa em background
      this.executeTask(taskId);

      return {
        task_id: taskId,
        status: 'accepted',
        streaming,
        poll_url: `/tasks/${taskId}`,
        stream_url: streaming ? `/tasks/${taskId}/stream` : null
      };
    });

    // Consultar status da tarefa
    this.server.get('/tasks/:taskId', async (request, reply) => {
      const { taskId } = request.params;
      const task = this.tasks.get(taskId);

      if (!task) {
        reply.code(404);
        return { error: 'Task not found' };
      }

      return task;
    });

    // Tomada de decisão autônoma
    this.server.post('/decide', async (request, reply) => {
      const { context, options } = request.body;

      // Usar Claude para avaliar opções
      const sessionId = await this.getOrCreateSession();
      const session = this.sessions.get(sessionId);

      const prompt = `
        Given the context: ${JSON.stringify(context)}
        And these options: ${JSON.stringify(options)}
        
        Evaluate each option and provide:
        1. The best option
        2. Confidence score (0-1)
        3. Reasoning for the decision
        
        Respond in JSON format.
      `;

      const response = await session.sendMessage(prompt);
      
      this.metrics.decisionseMade++;

      // Parse response e retornar decisão estruturada
      try {
        const decision = JSON.parse(response);
        return {
          decision: decision.best_option || options[0],
          confidence: decision.confidence || 0.8,
          reasoning: decision.reasoning || 'Based on context analysis',
          agent_id: this.agentId,
          timestamp: new Date().toISOString()
        };
      } catch (e) {
        return {
          decision: options[0],
          confidence: 0.7,
          reasoning: response,
          agent_id: this.agentId,
          timestamp: new Date().toISOString()
        };
      }
    });

    // Aprendizagem contínua
    this.server.post('/learn', async (request, reply) => {
      const { data, type = 'general' } = request.body;

      // Armazenar conhecimento
      const knowledgeItem = {
        id: uuidv4(),
        type,
        data,
        learned_at: new Date().toISOString(),
        source: 'external'
      };

      this.knowledge.push(knowledgeItem);
      this.metrics.learningEvents++;

      // Integrar com Neo4j via MCP se disponível
      // Isso seria feito através de uma chamada MCP ao neo4j-memory

      return {
        success: true,
        knowledge_id: knowledgeItem.id,
        total_knowledge: this.knowledge.length
      };
    });

    // Auto-adaptação
    this.server.post('/adapt', async (request, reply) => {
      const { feedback, parameters } = request.body;

      // Ajustar parâmetros baseado em feedback
      const adaptation = {
        type: feedback.type || 'performance',
        adjustments: {
          temperature: parameters?.temperature || 0.7,
          max_tokens: parameters?.max_tokens || 2000,
          streaming: parameters?.streaming || true
        },
        applied_at: new Date().toISOString()
      };

      return {
        adapted: true,
        adaptation,
        agent_id: this.agentId
      };
    });

    // Participação em consenso
    this.server.post('/consensus', async (request, reply) => {
      const { proposal, peers } = request.body;

      // Avaliar proposta usando Claude
      const sessionId = await this.getOrCreateSession();
      const session = this.sessions.get(sessionId);

      const evaluation = await session.sendMessage(
        `Evaluate this proposal for consensus: ${JSON.stringify(proposal)}. 
         Should we approve or reject? Provide reasoning.`
      );

      const vote = {
        proposal_id: proposal.id,
        agent_id: this.agentId,
        vote: evaluation.toLowerCase().includes('approve') ? 'approve' : 'reject',
        reasoning: evaluation,
        timestamp: new Date().toISOString()
      };

      return vote;
    });

    // Base de conhecimento
    this.server.get('/knowledge', async () => ({
      agent_id: this.agentId,
      knowledge: this.knowledge.slice(-100), // Últimos 100 items
      total_items: this.knowledge.length
    }));

    this.server.post('/knowledge', async (request, reply) => {
      const { knowledge } = request.body;
      
      this.knowledge.push({
        ...knowledge,
        integrated_at: new Date().toISOString(),
        source: 'peer'
      });

      return {
        integrated: true,
        total_knowledge: this.knowledge.length
      };
    });

    // Memory endpoints (Neo4j via MCP)
    this.server.post('/memory/search', async (request, reply) => {
      const { query, limit = 10, depth = 1 } = request.body;
      
      // Buscar memórias relevantes
      const memories = await this.memory.searchMemories(query, { limit, depth });
      
      return {
        memories,
        count: memories.length,
        query
      };
    });

    this.server.post('/memory/create', async (request, reply) => {
      const { label, properties } = request.body;
      
      // Criar nova memória
      const memory = await this.memory.createMemory(label, properties);
      this.metrics.memoriesCreated++;
      
      return {
        success: true,
        memory
      };
    });

    this.server.post('/memory/connect', async (request, reply) => {
      const { fromMemoryId, toMemoryId, type, properties } = request.body;
      
      // Criar conexão entre memórias
      const connection = await this.memory.createConnection(
        fromMemoryId, 
        toMemoryId, 
        type, 
        properties
      );
      this.metrics.connectionsCreated++;
      
      return {
        success: true,
        connection
      };
    });

    this.server.get('/memory/labels', async (request, reply) => {
      const labels = await this.memory.listMemoryLabels();
      
      return {
        labels,
        total: labels.reduce((sum, l) => sum + l.count, 0)
      };
    });
  }

  setupClaudeRoutes() {
    // Chat direto com Claude com memória
    this.server.post('/claude/chat', async (request, reply) => {
      const { message, session_id, context, use_memory = true } = request.body;

      const sessionId = session_id || await this.getOrCreateSession();
      const session = this.sessions.get(sessionId);

      if (!session) {
        reply.code(404);
        return { error: 'Session not found' };
      }

      let enrichedMessage = message;
      let relevantMemories = [];

      // Buscar memórias relevantes se habilitado
      if (use_memory) {
        relevantMemories = await this.memory.searchMemories(message, { limit: 5 });
        
        if (relevantMemories.length > 0) {
          const memoryContext = relevantMemories.map(m => 
            `[Memory: ${m.label}] ${m.properties.name || ''}: ${m.properties.content || m.properties.description || ''}`
          ).join('\n');
          
          enrichedMessage = `Relevant memories:\n${memoryContext}\n\nUser message: ${message}`;
        }
      }

      // Adicionar contexto se fornecido
      const fullMessage = context 
        ? `Context: ${JSON.stringify(context)}\n\n${enrichedMessage}`
        : enrichedMessage;

      const response = await session.sendMessage(fullMessage);

      // Salvar interação como memória
      if (use_memory) {
        const conversationMemory = await this.memory.createMemory('conversation', {
          name: `Chat ${sessionId}`,
          content: message,
          response: response,
          timestamp: new Date().toISOString()
        });
        
        // Conectar com memórias relevantes encontradas
        for (const memory of relevantMemories) {
          await this.memory.createConnection(
            conversationMemory.id,
            memory.id,
            'REFERENCES',
            { relevance: memory.relevance }
          );
        }
      }

      return {
        response,
        session_id: sessionId,
        agent_id: this.agentId,
        memories_used: relevantMemories.length,
        timestamp: new Date().toISOString()
      };
    });

    // Streaming de respostas
    this.server.get('/claude/stream', { websocket: true }, (connection, req) => {
      connection.socket.on('message', async (message) => {
        try {
          const data = JSON.parse(message.toString());
          const { text, session_id, context } = data;

          const sessionId = session_id || await this.getOrCreateSession();
          const session = this.sessions.get(sessionId);

          if (!session) {
            connection.socket.send(JSON.stringify({
              error: 'Session not found'
            }));
            return;
          }

          // Stream response from Claude
          const stream = await session.streamMessage(text);
          
          for await (const chunk of stream) {
            connection.socket.send(JSON.stringify({
              type: 'stream',
              content: chunk,
              session_id: sessionId
            }));
          }

          connection.socket.send(JSON.stringify({
            type: 'complete',
            session_id: sessionId
          }));

        } catch (error) {
          connection.socket.send(JSON.stringify({
            error: error.message
          }));
        }
      });
    });

    // Gerenciar sessões
    this.server.get('/claude/sessions', async () => {
      const sessions = [];
      for (const [id, session] of this.sessions) {
        sessions.push({
          id,
          created_at: session.createdAt,
          messages: session.messageCount || 0
        });
      }
      return { sessions, count: sessions.length };
    });

    this.server.post('/claude/sessions', async () => {
      const sessionId = await this.createSession();
      return {
        session_id: sessionId,
        created: true
      };
    });

    // Server-Sent Events para streaming - Padrão A2A
    this.server.get('/stream/:taskId', async (request, reply) => {
      const { taskId } = request.params;
      
      reply.raw.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Cache-Control'
      });

      const task = this.tasks.get(taskId);
      if (!task) {
        reply.raw.write(`data: ${JSON.stringify({ error: 'Task not found' })}\n\n`);
        reply.raw.end();
        return;
      }

      // Simular progresso de streaming
      const sendProgress = (progress, status, data = null) => {
        const eventData = {
          task_id: taskId,
          progress,
          status,
          timestamp: new Date().toISOString(),
          agent_id: this.agentId
        };
        
        if (data) eventData.data = data;
        
        reply.raw.write(`data: ${JSON.stringify(eventData)}\n\n`);
      };

      // Simular execução de tarefa com progresso
      const executeWithProgress = async () => {
        try {
          sendProgress(0, 'starting');
          
          sendProgress(25, 'processing', 'Analyzing task...');
          await new Promise(resolve => setTimeout(resolve, 1000));
          
          sendProgress(50, 'processing', 'Generating response...');
          await new Promise(resolve => setTimeout(resolve, 1000));
          
          sendProgress(75, 'processing', 'Finalizing...');
          await new Promise(resolve => setTimeout(resolve, 500));
          
          sendProgress(100, 'completed', task.result || 'Task completed successfully');
          
          reply.raw.write(`event: close\ndata: ${JSON.stringify({ status: 'stream_ended' })}\n\n`);
          reply.raw.end();
          
        } catch (error) {
          reply.raw.write(`data: ${JSON.stringify({ 
            error: error.message, 
            status: 'failed' 
          })}\n\n`);
          reply.raw.end();
        }
      };

      executeWithProgress();
    });

    this.server.delete('/claude/sessions/:sessionId', async (request, reply) => {
      const { sessionId } = request.params;
      
      if (this.sessions.has(sessionId)) {
        const session = this.sessions.get(sessionId);
        await session.close();
        this.sessions.delete(sessionId);
        return { deleted: true };
      }

      reply.code(404);
      return { error: 'Session not found' };
    });
  }

  setupWebSocket() {
    // WebSocket para comunicação P2P
    this.server.get('/ws', { websocket: true }, (connection, req) => {
      const peerId = `peer-${uuidv4().slice(0, 8)}`;
      
      this.peers.set(peerId, connection.socket);

      connection.socket.send(JSON.stringify({
        type: 'connected',
        peer_id: peerId,
        agent_id: this.agentId
      }));

      connection.socket.on('message', async (message) => {
        try {
          const data = JSON.parse(message.toString());
          await this.handlePeerMessage(peerId, data);
        } catch (error) {
          console.error('WebSocket message error:', error);
        }
      });

      connection.socket.on('close', () => {
        this.peers.delete(peerId);
      });
    });
  }

  async executeTask(taskId) {
    const task = this.tasks.get(taskId);
    if (!task) return;

    task.status = 'running';
    task.started_at = new Date().toISOString();

    try {
      const sessionId = await this.getOrCreateSession();
      const session = this.sessions.get(sessionId);

      // Construir prompt com contexto A2A
      const prompt = `
        Task: ${task.task}
        Context: ${JSON.stringify(task.context)}
        
        Please complete this task and provide a structured response.
      `;

      if (task.streaming) {
        // Streaming response
        const stream = await session.streamMessage(prompt);
        task.stream = stream;
        task.status = 'streaming';
      } else {
        // Regular response
        const response = await session.sendMessage(prompt);
        task.result = response;
        task.status = 'completed';
      }

      task.completed_at = new Date().toISOString();
      this.metrics.tasksCompleted++;

    } catch (error) {
      task.status = 'failed';
      task.error = error.message;
      task.failed_at = new Date().toISOString();
    }

    this.tasks.set(taskId, task);
  }

  async handlePeerMessage(peerId, message) {
    const { type } = message;

    switch (type) {
      case 'knowledge_share':
        // Integrar conhecimento do peer
        this.knowledge.push({
          ...message.data,
          from_peer: peerId,
          received_at: new Date().toISOString()
        });
        break;

      case 'task_request':
        // Processar requisição de tarefa do peer
        const taskId = `peer-task-${uuidv4()}`;
        this.tasks.set(taskId, {
          id: taskId,
          ...message.task,
          from_peer: peerId
        });
        this.executeTask(taskId);
        break;

      case 'consensus':
        // Participar em votação de consenso
        const vote = await this.evaluateProposal(message.proposal);
        const peer = this.peers.get(peerId);
        if (peer) {
          peer.send(JSON.stringify({
            type: 'vote',
            vote,
            agent_id: this.agentId
          }));
        }
        break;
    }
  }

  async getOrCreateSession() {
    // Reutilizar sessão existente ou criar nova
    if (this.sessions.size === 0) {
      return await this.createSession();
    }
    
    // Retornar primeira sessão disponível
    return this.sessions.keys().next().value;
  }

  async createSession() {
    const sessionId = `session-${uuidv4().slice(0, 8)}`;
    
    // Criar sessão simulada usando query API
    const session = {
      id: sessionId,
      createdAt: new Date().toISOString(),
      messageCount: 0,
      messages: [],
      async sendMessage(prompt) {
        try {
          const response = await query(prompt, {
            model: 'claude-3-sonnet-20240229',
            max_tokens: 2000
          });
          this.messageCount++;
          this.messages.push({ role: 'user', content: prompt });
          this.messages.push({ role: 'assistant', content: response });
          return response;
        } catch (error) {
          console.error('Error calling Claude:', error);
          return 'Erro ao processar mensagem com Claude.';
        }
      },
      async streamMessage(prompt) {
        // Simular streaming retornando resposta completa
        const response = await this.sendMessage(prompt);
        return {
          [Symbol.asyncIterator]: async function*() {
            yield { content: response };
          }
        };
      },
      async close() {
        // Cleanup se necessário
      }
    };

    this.sessions.set(sessionId, session);
    return sessionId;
  }

  async evaluateProposal(proposal) {
    const sessionId = await this.getOrCreateSession();
    const session = this.sessions.get(sessionId);

    const response = await session.sendMessage(
      `Evaluate proposal: ${JSON.stringify(proposal)}. Vote approve or reject.`
    );

    return {
      proposal_id: proposal.id,
      vote: response.toLowerCase().includes('approve') ? 'approve' : 'reject',
      confidence: 0.8,
      reasoning: response
    };
  }

  calculateUptime() {
    const started = new Date(this.metrics.startedAt);
    const now = new Date();
    return Math.floor((now - started) / 1000); // seconds
  }

  async start(port = 8001) {
    try {
      await this.setupServer();
      await this.server.listen({ port, host: '0.0.0.0' });
      console.log(`🚀 Claude A2A Agent running on http://localhost:${port}`);
      console.log(`📋 Agent ID: ${this.agentId}`);
      console.log(`🔗 Agent Card: http://localhost:${port}/`);
    } catch (err) {
      console.error('Failed to start server:', err);
      process.exit(1);
    }
  }
}

// Inicializar e executar
console.log('🚀 Iniciando Claude A2A Wrapper...');
const agent = new ClaudeA2AAgent();
const port = process.env.PORT || 8001;
console.log(`📡 Tentando iniciar na porta ${port}...`);
agent.start(port).catch(err => {
  console.error('❌ Erro ao iniciar servidor:', err);
  process.exit(1);
});