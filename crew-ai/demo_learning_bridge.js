#!/usr/bin/env node

/**
 * Demonstração Visual do Neo4jLearningTool e Bridge Bidirecional
 * Mostra como o sistema aprende e se comunica
 */

import neo4j from 'neo4j-driver';

const driver = neo4j.driver('bolt://localhost:7687', neo4j.auth.basic('neo4j', 'password'));

async function demonstrateLearningSystem() {
    const session = driver.session();
    
    console.log('\n' + '='.repeat(70));
    console.log('🧠 DEMONSTRAÇÃO: NEO4J LEARNING TOOL - SISTEMA DE APRENDIZADO CONTÍNUO');
    console.log('='.repeat(70));
    
    try {
        // 1. Como o Learning Tool funciona
        console.log('\n📚 1. COMO FUNCIONA O LEARNING TOOL:\n');
        console.log('   O Neo4jLearningTool usa um algoritmo de detecção de padrões:');
        console.log('   ├─ Armazena padrões de sucesso e falha');
        console.log('   ├─ Calcula score médio ponderado');
        console.log('   ├─ Incrementa ocorrências a cada repetição');
        console.log('   └─ Recomenda padrões similares com score > 0.7\n');
        
        // Simular armazenamento de padrões
        const patterns = [
            { type: 'success', context: 'task_planning', outcome: 'efficient_execution', score: 0.9 },
            { type: 'success', context: 'task_planning', outcome: 'optimized_workflow', score: 0.85 },
            { type: 'failure', context: 'resource_allocation', outcome: 'timeout_error', score: -0.5 },
            { type: 'optimization', context: 'parallel_execution', outcome: '40% faster', score: 0.95 }
        ];
        
        for (const pattern of patterns) {
            await session.run(`
                CREATE (p:DemoPattern {
                    type: $type,
                    context: $context,
                    outcome: $outcome,
                    score: $score,
                    occurrences: toInteger(rand() * 10 + 1),
                    created_at: datetime()
                })
            `, pattern);
        }
        
        // Mostrar padrões aprendidos
        const learnedPatterns = await session.run(`
            MATCH (p:DemoPattern)
            RETURN p.type as type, p.context as context, 
                   p.outcome as outcome, p.score as score, 
                   p.occurrences as occurrences
            ORDER BY p.score DESC
        `);
        
        console.log('📊 PADRÕES APRENDIDOS:');
        console.log('   ┌─────────────┬──────────────────┬─────────────────────┬───────┬──────────┐');
        console.log('   │ Tipo        │ Contexto         │ Resultado           │ Score │ Vezes    │');
        console.log('   ├─────────────┼──────────────────┼─────────────────────┼───────┼──────────┤');
        
        for (const record of learnedPatterns.records) {
            const type = record.get('type').padEnd(11);
            const context = record.get('context').padEnd(16);
            const outcome = record.get('outcome').padEnd(19);
            const score = record.get('score').toFixed(2).padStart(5);
            const occurrences = record.get('occurrences').toString().padStart(8);
            console.log(`   │ ${type} │ ${context} │ ${outcome} │ ${score} │ ${occurrences} │`);
        }
        console.log('   └─────────────┴──────────────────┴─────────────────────┴───────┴──────────┘');
        
        // 2. Processo de Aprendizado
        console.log('\n📈 2. PROCESSO DE APRENDIZADO CONTÍNUO:\n');
        
        // Simular evolução de score
        await session.run(`
            MATCH (p:DemoPattern {type: 'success'})
            SET p.score = (p.score * p.occurrences + 0.95) / (p.occurrences + 1),
                p.occurrences = p.occurrences + 1,
                p.last_seen = datetime()
        `);
        
        console.log('   Quando um padrão é observado novamente:');
        console.log('   1️⃣  Score atualizado = (score_anterior × ocorrências + novo_score) / (ocorrências + 1)');
        console.log('   2️⃣  Incrementa contador de ocorrências');
        console.log('   3️⃣  Atualiza timestamp last_seen');
        console.log('   4️⃣  Busca padrões similares com score > 0.7');
        console.log('   5️⃣  Retorna recomendações baseadas em padrões similares\n');
        
        // 3. Sistema de Feedback
        console.log('🔄 3. SISTEMA DE FEEDBACK LOOP:\n');
        
        await session.run(`
            CREATE (f:FeedbackExample {
                type: 'positive',
                task: 'optimization_task',
                rating: 0.9,
                impact: 'Melhorou performance em 30%',
                created_at: datetime()
            })
        `);
        
        console.log('   Feedback positivo (rating > 0.8):');
        console.log('   └─ Aumenta score do padrão em 10%\n');
        
        console.log('   Feedback negativo (rating < 0.5):');
        console.log('   └─ Marca padrão para revisão\n');
        
        // Limpar dados demo
        await session.run('MATCH (p:DemoPattern) DETACH DELETE p');
        await session.run('MATCH (f:FeedbackExample) DETACH DELETE f');
        
    } catch (error) {
        console.error('Erro:', error);
    } finally {
        await session.close();
    }
}

async function demonstrateBidirectionalBridge() {
    const session = driver.session();
    
    console.log('\n' + '='.repeat(70));
    console.log('🌉 DEMONSTRAÇÃO: BRIDGE DE COMUNICAÇÃO BIDIRECIONAL MCP-CREWAI');
    console.log('='.repeat(70));
    
    try {
        console.log('\n🔄 1. FLUXO DE COMUNICAÇÃO BIDIRECIONAL:\n');
        
        // Criar exemplo de fluxo
        await session.run(`
            CREATE (crew:DemoCrewAI {name: 'CrewAI System'})
            CREATE (mcp:DemoMCP {name: 'MCP Neo4j Server'})
            CREATE (neo4j:DemoNeo4j {name: 'Neo4j Database'})
            
            CREATE (crew)-[:SENDS_TASK]->(mcp)
            CREATE (mcp)-[:STORES_IN]->(neo4j)
            CREATE (neo4j)-[:RETURNS_CONTEXT]->(mcp)
            CREATE (mcp)-[:PROVIDES_TO]->(crew)
        `);
        
        console.log('   CrewAI → MCP Bridge → Neo4j');
        console.log('     ↓         ↓          ↓');
        console.log('   Task → Store Memory → Graph');
        console.log('     ↑         ↑          ↑');
        console.log('   Result ← Context ← Query\n');
        
        // 2. Demonstrar sincronização de memórias
        console.log('📝 2. SINCRONIZAÇÃO DE MEMÓRIAS (CrewAI → Neo4j):\n');
        
        const agentMemories = [
            { agent: 'planner', type: 'decision', content: 'Use parallel execution' },
            { agent: 'coder', type: 'knowledge', content: 'Python best practices' },
            { agent: 'tester', type: 'pattern', content: 'Test coverage > 80%' }
        ];
        
        for (const memory of agentMemories) {
            await session.run(`
                CREATE (m:DemoMemory {
                    agent: $agent,
                    type: $type,
                    content: $content,
                    mcp_synced: true,
                    created_at: datetime()
                })
            `, memory);
        }
        
        console.log('   Quando um agente CrewAI executa uma tarefa:');
        console.log('   ├─ 1. Bridge captura o contexto do agente');
        console.log('   ├─ 2. Cria Memory node com flag mcp_synced=true');
        console.log('   ├─ 3. Conecta memória ao agente: (Agent)-[:HAS_MEMORY]->(Memory)');
        console.log('   └─ 4. Retorna confirmação para o agente\n');
        
        // 3. Demonstrar recuperação de contexto
        console.log('🔍 3. RECUPERAÇÃO DE CONTEXTO (Neo4j → CrewAI):\n');
        
        const context = await session.run(`
            MATCH (m:DemoMemory)
            RETURN m.agent as agent, 
                   collect({type: m.type, content: m.content}) as memories
        `);
        
        console.log('   Quando um agente precisa de contexto:');
        console.log('   ├─ 1. Bridge consulta memórias do agente');
        console.log('   ├─ 2. Busca relacionamentos relevantes');
        console.log('   ├─ 3. Identifica padrões de sucesso (score > 0.5)');
        console.log('   └─ 4. Retorna contexto enriquecido\n');
        
        console.log('   Contexto recuperado:');
        for (const record of context.records) {
            const agent = record.get('agent');
            const memories = record.get('memories');
            console.log(`   └─ ${agent}: ${memories.length} memórias`);
        }
        
        // 4. Funcionalidades do Bridge
        console.log('\n⚙️  4. FUNCIONALIDADES DO BRIDGE:\n');
        
        const features = [
            ['sync_agent_memories()', 'Sincroniza memórias do agente com Neo4j'],
            ['get_agent_context()', 'Recupera contexto completo do agente'],
            ['create_memory_connection()', 'Cria relacionamentos entre memórias'],
            ['search_memories()', 'Busca memórias por palavras-chave'],
            ['sync_execution_to_mcp()', 'Sincroniza execução completa para MCP'],
            ['get_mcp_status()', 'Verifica status e estatísticas do servidor']
        ];
        
        console.log('   ┌─────────────────────────────┬──────────────────────────────────────┐');
        console.log('   │ Método                      │ Descrição                            │');
        console.log('   ├─────────────────────────────┼──────────────────────────────────────┤');
        for (const [method, desc] of features) {
            console.log(`   │ ${method.padEnd(27)} │ ${desc.padEnd(36)} │`);
        }
        console.log('   └─────────────────────────────┴──────────────────────────────────────┘');
        
        // 5. Integração com agentes
        console.log('\n🤖 5. INTEGRAÇÃO COM AGENTES CREWAI:\n');
        
        console.log('   Cada agente recebe automaticamente:');
        console.log('   ├─ agent.mcp_create_memory()  - Criar nova memória');
        console.log('   ├─ agent.mcp_search()          - Buscar memórias');
        console.log('   └─ agent.mcp_get_context()     - Obter contexto completo\n');
        
        console.log('   Processo de execução com MCP:');
        console.log('   1️⃣  Antes: Carrega contexto do Neo4j');
        console.log('   2️⃣  Durante: Executa tarefa com contexto');
        console.log('   3️⃣  Depois: Salva resultado como memória\n');
        
        // Estatísticas
        const stats = await session.run(`
            MATCH (m:DemoMemory)
            WITH count(m) as total_memories,
                 count(DISTINCT m.agent) as unique_agents,
                 count(DISTINCT m.type) as memory_types
            RETURN total_memories, unique_agents, memory_types
        `);
        
        const stat = stats.records[0];
        console.log('📊 ESTATÍSTICAS DO BRIDGE:');
        console.log(`   ├─ Memórias sincronizadas: ${stat.get('total_memories')}`);
        console.log(`   ├─ Agentes únicos: ${stat.get('unique_agents')}`);
        console.log(`   └─ Tipos de memória: ${stat.get('memory_types')}`);
        
        // Limpar dados demo
        await session.run('MATCH (n:DemoCrewAI) DETACH DELETE n');
        await session.run('MATCH (n:DemoMCP) DETACH DELETE n');
        await session.run('MATCH (n:DemoNeo4j) DETACH DELETE n');
        await session.run('MATCH (n:DemoMemory) DETACH DELETE n');
        
    } catch (error) {
        console.error('Erro:', error);
    } finally {
        await session.close();
    }
}

async function showRealTimeExample() {
    const session = driver.session();
    
    console.log('\n' + '='.repeat(70));
    console.log('🎬 EXEMPLO EM TEMPO REAL: CICLO COMPLETO DE APRENDIZADO');
    console.log('='.repeat(70));
    
    try {
        console.log('\n📍 Cenário: Agente "planner" executando tarefa de otimização\n');
        
        // Passo 1: Agente busca contexto
        console.log('PASSO 1: Agente busca contexto via Bridge');
        console.log('─────────────────────────────────────────');
        
        await session.run(`
            CREATE (context:RealTimeDemo {
                step: 1,
                action: 'get_agent_context',
                agent: 'planner',
                result: 'Memórias: 5, Padrões: 3, Relacionamentos: 7',
                timestamp: datetime()
            })
        `);
        
        console.log('   Bridge.get_agent_context("planner")');
        console.log('   └─ Retorna: {memories: [...], patterns: [...], relationships: [...]}\n');
        
        // Passo 2: Executa tarefa
        console.log('PASSO 2: Executa tarefa com contexto');
        console.log('────────────────────────────────────');
        
        await session.run(`
            CREATE (exec:RealTimeDemo {
                step: 2,
                action: 'execute_task',
                task: 'optimize_workflow',
                execution_time: 3.5,
                success: true,
                timestamp: datetime()
            })
        `);
        
        console.log('   Tarefa: "optimize_workflow"');
        console.log('   Tempo: 3.5 segundos');
        console.log('   Status: ✅ Sucesso\n');
        
        // Passo 3: Learning Tool analisa
        console.log('PASSO 3: Learning Tool analisa execução');
        console.log('───────────────────────────────────────');
        
        await session.run(`
            CREATE (learn:RealTimeDemo {
                step: 3,
                action: 'learning_analysis',
                pattern_detected: 'efficient_execution',
                score: 0.92,
                similar_patterns: 2,
                timestamp: datetime()
            })
        `);
        
        console.log('   Neo4jLearningTool detecta padrão:');
        console.log('   ├─ Tipo: "efficient_execution"');
        console.log('   ├─ Score: 0.92');
        console.log('   └─ Padrões similares encontrados: 2\n');
        
        // Passo 4: Salva memória
        console.log('PASSO 4: Bridge salva resultado como memória');
        console.log('────────────────────────────────────────────');
        
        await session.run(`
            CREATE (save:RealTimeDemo {
                step: 4,
                action: 'sync_memory',
                memory_type: 'task_result',
                mcp_synced: true,
                timestamp: datetime()
            })
        `);
        
        console.log('   Bridge.sync_agent_memories("planner", [{');
        console.log('     type: "task_result",');
        console.log('     content: {task: "optimize_workflow", time: 3.5}');
        console.log('   }])\n');
        
        // Passo 5: Atualiza padrões
        console.log('PASSO 5: Sistema atualiza padrões de aprendizado');
        console.log('────────────────────────────────────────────────');
        
        await session.run(`
            CREATE (update:RealTimeDemo {
                step: 5,
                action: 'update_patterns',
                patterns_updated: 3,
                new_recommendations: 'Use parallel execution for similar tasks',
                timestamp: datetime()
            })
        `);
        
        console.log('   Padrões atualizados: 3');
        console.log('   Nova recomendação: "Use execução paralela para tarefas similares"');
        console.log('   Score médio melhorado: 0.85 → 0.92\n');
        
        // Mostrar fluxo completo
        const flow = await session.run(`
            MATCH (demo:RealTimeDemo)
            RETURN demo.step as step, demo.action as action
            ORDER BY demo.step
        `);
        
        console.log('🔄 FLUXO COMPLETO DO CICLO:');
        console.log('───────────────────────────\n');
        
        for (const record of flow.records) {
            const step = record.get('step');
            const action = record.get('action');
            const arrow = step < 5 ? '↓' : '✓';
            console.log(`   ${step}. ${action}`);
            if (step < 5) console.log(`   ${arrow}`);
        }
        
        console.log('\n📈 RESULTADO: Sistema aprendeu e melhorou para próximas execuções!');
        
        // Limpar dados demo
        await session.run('MATCH (demo:RealTimeDemo) DETACH DELETE demo');
        
    } catch (error) {
        console.error('Erro:', error);
    } finally {
        await session.close();
    }
}

// Executar demonstrações
async function runDemonstrations() {
    console.log('\n🚀 INICIANDO DEMONSTRAÇÕES DO SISTEMA DE APRENDIZADO E BRIDGE\n');
    
    await demonstrateLearningSystem();
    await demonstrateBidirectionalBridge();
    await showRealTimeExample();
    
    console.log('\n' + '='.repeat(70));
    console.log('✅ DEMONSTRAÇÕES CONCLUÍDAS!');
    console.log('='.repeat(70));
    console.log('\n💡 O sistema está aprendendo continuamente e melhorando a cada execução!');
    console.log('🔗 Toda comunicação é bidirecional através do Bridge MCP-CrewAI.\n');
    
    await driver.close();
}

runDemonstrations().catch(console.error);