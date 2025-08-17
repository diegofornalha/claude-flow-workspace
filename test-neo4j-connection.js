const neo4j = require('neo4j-driver');

async function testConnection() {
    const uri = 'bolt://localhost:7687';
    const user = 'neo4j';
    const password = 'password';
    
    const driver = neo4j.driver(uri, neo4j.auth.basic(user, password));
    const session = driver.session();
    
    try {
        console.log('🔄 Conectando ao Neo4j...');
        
        // Criar uma memória de teste
        const result = await session.run(
            'CREATE (m:TestMemory {name: $name, created_at: datetime()}) RETURN m',
            { name: 'Teste MCP Conductor' }
        );
        
        console.log('✅ Conexão estabelecida!');
        console.log('📝 Memória criada:', result.records[0].get('m').properties);
        
        // Listar todas as memórias de teste
        const listResult = await session.run('MATCH (m:TestMemory) RETURN m');
        console.log(`\n📊 Total de memórias de teste: ${listResult.records.length}`);
        
    } catch (error) {
        console.error('❌ Erro ao conectar:', error.message);
    } finally {
        await session.close();
        await driver.close();
    }
}

testConnection();