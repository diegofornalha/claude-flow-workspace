const neo4j = require('neo4j-driver');
const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

// Configuração Neo4j
const uri = 'bolt://localhost:7687';
const user = 'neo4j';
const password = 'password';

// Mapear tipos de agentes para clusters
const CLUSTER_MAPPING = {
    'coordinator': 'Orchestration',
    'developer': 'Implementation', 
    'analyst': 'Research',
    'validator': 'Quality',
    'autonomous': 'Autonomous',
    'infrastructure': 'Infrastructure'
};

// Cores para cada cluster
const CLUSTER_COLORS = {
    'Orchestration': '#4ECDC4',
    'Implementation': '#556270',
    'Research': '#C44D58',
    'Quality': '#FF6B6B',
    'Autonomous': '#95E77E',
    'Infrastructure': '#68B3D1'
};

async function parseAgentFile(filePath) {
    const content = fs.readFileSync(filePath, 'utf8');
    const lines = content.split('\n');
    
    // Extrair metadados do frontmatter YAML
    if (lines[0] === '---') {
        const endIndex = lines.indexOf('---', 1);
        if (endIndex > 0) {
            const yamlContent = lines.slice(1, endIndex).join('\n');
            try {
                const metadata = yaml.load(yamlContent);
                
                // Extrair capabilities e hooks
                const capabilities = metadata.capabilities || [];
                const hooks = metadata.hooks || {};
                
                // Extrair seção de integração do markdown
                const integrationMatch = content.match(/## Pontos de Integração\s*([\s\S]*?)(?=##|$)/);
                const integrations = [];
                
                if (integrationMatch) {
                    const intSection = integrationMatch[1];
                    // Extrair agentes relacionados
                    const agentMatches = intSection.matchAll(/\*\*(\w+)\*\*:/g);
                    for (const match of agentMatches) {
                        integrations.push(match[1]);
                    }
                }
                
                return {
                    name: metadata.name,
                    type: metadata.type,
                    description: metadata.description,
                    color: metadata.color || '#888888',
                    priority: metadata.priority || 'medium',
                    capabilities: capabilities,
                    hooks: {
                        pre: hooks && hooks.pre ? true : false,
                        post: hooks && hooks.post ? true : false
                    },
                    integrations: integrations,
                    filePath: filePath
                };
            } catch (e) {
                console.error(`Erro ao processar YAML em ${filePath}:`, e);
            }
        }
    }
    return null;
}

async function findAllAgents(baseDir) {
    const agents = [];
    
    function scanDirectory(dir) {
        const items = fs.readdirSync(dir);
        
        for (const item of items) {
            const fullPath = path.join(dir, item);
            const stat = fs.statSync(fullPath);
            
            if (stat.isDirectory()) {
                scanDirectory(fullPath);
            } else if (item.endsWith('.md') && !item.includes('README')) {
                const agent = parseAgentFile(fullPath);
                if (agent) {
                    agents.push(agent);
                }
            }
        }
    }
    
    scanDirectory(baseDir);
    return agents;
}

async function indexAgentsToNeo4j() {
    const driver = neo4j.driver(uri, neo4j.auth.basic(user, password));
    const session = driver.session();
    
    try {
        console.log('🔄 Conectando ao Neo4j...');
        
        // Limpar dados antigos de agentes
        await session.run('MATCH (a:Agent) DETACH DELETE a');
        await session.run('MATCH (c:Cluster) DETACH DELETE c');
        console.log('🗑️  Dados antigos removidos');
        
        // Buscar todos os agentes
        const agentsDir = '/Users/2a/.claude/.conductor/baku/.claude/agents';
        const agents = await findAllAgents(agentsDir);
        console.log(`📂 Encontrados ${agents.length} agentes`);
        
        // Criar clusters
        const clusters = new Set();
        for (const agent of agents) {
            const cluster = CLUSTER_MAPPING[agent.type] || 'Unknown';
            clusters.add(cluster);
        }
        
        for (const cluster of clusters) {
            await session.run(
                `CREATE (c:Cluster {
                    name: $name,
                    color: $color,
                    created_at: datetime()
                }) RETURN c`,
                { 
                    name: cluster,
                    color: CLUSTER_COLORS[cluster] || '#888888'
                }
            );
        }
        console.log(`🎯 ${clusters.size} clusters criados`);
        
        // Criar nós dos agentes
        for (const agent of agents) {
            const cluster = CLUSTER_MAPPING[agent.type] || 'Unknown';
            
            await session.run(
                `CREATE (a:Agent {
                    name: $name,
                    type: $type,
                    description: $description,
                    color: $color,
                    priority: $priority,
                    capabilities: $capabilities,
                    has_pre_hook: $has_pre_hook,
                    has_post_hook: $has_post_hook,
                    file_path: $file_path,
                    created_at: datetime()
                }) RETURN a`,
                {
                    name: agent.name,
                    type: agent.type,
                    description: agent.description,
                    color: agent.color,
                    priority: agent.priority,
                    capabilities: agent.capabilities,
                    has_pre_hook: agent.hooks.pre,
                    has_post_hook: agent.hooks.post,
                    file_path: agent.filePath
                }
            );
            
            // Conectar agente ao cluster
            await session.run(
                `MATCH (a:Agent {name: $agentName})
                 MATCH (c:Cluster {name: $clusterName})
                 CREATE (a)-[:BELONGS_TO]->(c)`,
                {
                    agentName: agent.name,
                    clusterName: cluster
                }
            );
        }
        console.log(`🤖 ${agents.length} agentes criados`);
        
        // Criar relacionamentos entre agentes
        for (const agent of agents) {
            for (const integration of agent.integrations) {
                // Verificar se o agente integrado existe
                const targetAgent = agents.find(a => 
                    a.name === integration || 
                    a.name === integration.toLowerCase() ||
                    a.name === integration.replace('_', '-')
                );
                
                if (targetAgent) {
                    await session.run(
                        `MATCH (a1:Agent {name: $source})
                         MATCH (a2:Agent {name: $target})
                         CREATE (a1)-[:INTEGRATES_WITH]->(a2)`,
                        {
                            source: agent.name,
                            target: targetAgent.name
                        }
                    );
                }
            }
        }
        console.log('🔗 Relacionamentos criados');
        
        // Criar hierarquia baseada em tipos
        await session.run(`
            MATCH (coordinator:Agent {type: 'coordinator'})
            MATCH (developer:Agent {type: 'developer'})
            WHERE NOT (coordinator)-[:COORDINATES]->(developer)
            CREATE (coordinator)-[:COORDINATES]->(developer)
        `);
        
        await session.run(`
            MATCH (coordinator:Agent {type: 'coordinator'})
            MATCH (validator:Agent {type: 'validator'})
            WHERE NOT (coordinator)-[:VALIDATES_WITH]->(validator)
            CREATE (coordinator)-[:VALIDATES_WITH]->(validator)
        `);
        
        await session.run(`
            MATCH (analyst:Agent {type: 'analyst'})
            MATCH (coordinator:Agent {type: 'coordinator'})
            WHERE NOT (analyst)-[:INFORMS]->(coordinator)
            CREATE (analyst)-[:INFORMS]->(coordinator)
        `);
        
        console.log('🏗️  Hierarquia estabelecida');
        
        // Estatísticas finais
        const stats = await session.run(`
            MATCH (a:Agent)
            OPTIONAL MATCH (a)-[r]-()
            RETURN 
                count(DISTINCT a) as totalAgents,
                count(DISTINCT r) as totalRelationships
        `);
        
        const result = stats.records[0];
        console.log('\n✅ Indexação completa!');
        console.log(`📊 Estatísticas:`);
        console.log(`   - Agentes: ${result.get('totalAgents')}`);
        console.log(`   - Relacionamentos: ${result.get('totalRelationships')}`);
        console.log(`   - Clusters: ${clusters.size}`);
        
        console.log('\n🔍 Queries úteis para visualizar no Neo4j Browser:');
        console.log('   1. Ver tudo: MATCH (n) RETURN n');
        console.log('   2. Ver clusters: MATCH (c:Cluster)<-[:BELONGS_TO]-(a:Agent) RETURN c, a');
        console.log('   3. Ver integrações: MATCH (a1:Agent)-[:INTEGRATES_WITH]->(a2:Agent) RETURN a1, a2');
        console.log('   4. Ver hierarquia: MATCH p=(:Agent)-[r]->(:Agent) RETURN p');
        
    } catch (error) {
        console.error('❌ Erro:', error.message);
    } finally {
        await session.close();
        await driver.close();
    }
}

// Executar
indexAgentsToNeo4j();