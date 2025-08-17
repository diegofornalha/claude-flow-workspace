#!/usr/bin/env node

/**
 * Sistema de Validação e Alinhamento Final
 * Verifica e corrige todas as incoerências do projeto
 */

import neo4j from 'neo4j-driver';
import fs from 'fs/promises';
import path from 'path';

const driver = neo4j.driver('bolt://localhost:7687', neo4j.auth.basic('neo4j', 'password'));

class SystemValidator {
    constructor() {
        this.issues = [];
        this.fixes = [];
        this.insights = [];
    }

    async validateProject() {
        console.log('\n' + '='.repeat(70));
        console.log('🔍 VALIDAÇÃO COMPLETA DO PROJETO CONDUCTOR-BAKU');
        console.log('='.repeat(70));

        // 1. Validar estrutura de arquivos
        await this.validateFileStructure();
        
        // 2. Validar integração Neo4j
        await this.validateNeo4jIntegration();
        
        // 3. Validar fluxo de dados
        await this.validateDataFlow();
        
        // 4. Validar configurações
        await this.validateConfigurations();
        
        // 5. Gerar relatório
        await this.generateReport();
    }

    async validateFileStructure() {
        console.log('\n📁 VALIDANDO ESTRUTURA DE ARQUIVOS...\n');
        
        const requiredFiles = [
            '/Users/2a/.claude/.conductor/baku/crew-ai/sistema_multi_agente_neo4j/__init__.py',
            '/Users/2a/.claude/.conductor/baku/crew-ai/sistema_multi_agente_neo4j/crew.py',
            '/Users/2a/.claude/.conductor/baku/crew-ai/config/agents.yaml',
            '/Users/2a/.claude/.conductor/baku/crew-ai/config/tasks.yaml',
            '/Users/2a/.claude/.conductor/baku/crew-ai/config/inputs.json',
            '/Users/2a/.claude/.conductor/baku/crew-ai/tools/neo4j_tools.py',
            '/Users/2a/.claude/.conductor/baku/crew-ai/tools/telemetry_callbacks.py',
            '/Users/2a/.claude/.conductor/baku/crew-ai/tools/optimization_manager.py',
            '/Users/2a/.claude/.conductor/baku/crew-ai/tools/continuous_learning.py',
            '/Users/2a/.claude/.conductor/baku/crew-ai/tools/mcp_integration.py'
        ];

        for (const file of requiredFiles) {
            try {
                await fs.access(file);
                console.log(`  ✅ ${path.basename(file)}`);
            } catch {
                console.log(`  ❌ ${path.basename(file)} - MISSING`);
                this.issues.push(`Missing file: ${file}`);
            }
        }
    }

    async validateNeo4jIntegration() {
        console.log('\n🔗 VALIDANDO INTEGRAÇÃO NEO4J...\n');
        const session = driver.session();
        
        try {
            // Verificar componentes essenciais
            const components = [
                { label: 'Agent', minCount: 10 },
                { label: 'Cluster', minCount: 3 },
                { label: 'Project', minCount: 1 },
                { label: 'Memory', minCount: 0 },
                { label: 'Pattern', minCount: 0 }
            ];

            for (const comp of components) {
                const result = await session.run(
                    `MATCH (n:${comp.label}) RETURN count(n) as count`
                );
                const count = result.records[0].get('count').toNumber();
                
                if (count >= comp.minCount) {
                    console.log(`  ✅ ${comp.label}: ${count} nodes`);
                } else {
                    console.log(`  ⚠️ ${comp.label}: ${count} nodes (expected >= ${comp.minCount})`);
                    this.issues.push(`Insufficient ${comp.label} nodes: ${count} < ${comp.minCount}`);
                }
            }

            // Verificar relacionamentos
            const relationships = await session.run(`
                MATCH ()-[r]->()
                RETURN type(r) as type, count(r) as count
                ORDER BY count DESC
            `);

            console.log('\n  📊 Relacionamentos:');
            for (const record of relationships.records.slice(0, 5)) {
                const type = record.get('type');
                const count = record.get('count').toNumber();
                console.log(`     ${type}: ${count}`);
            }

        } catch (error) {
            console.log(`  ❌ Neo4j connection error: ${error.message}`);
            this.issues.push('Neo4j connection failed');
        } finally {
            await session.close();
        }
    }

    async validateDataFlow() {
        console.log('\n🔄 VALIDANDO FLUXO DE DADOS...\n');
        const session = driver.session();
        
        try {
            // Verificar se há execuções registradas
            const executions = await session.run(`
                MATCH (e:Execution)
                RETURN count(e) as count
            `);
            const execCount = executions.records[0].get('count').toNumber();
            
            if (execCount > 0) {
                console.log(`  ✅ Execuções registradas: ${execCount}`);
            } else {
                console.log('  ⚠️ Nenhuma execução registrada');
                this.insights.push('Sistema ainda não foi executado com telemetria');
            }

            // Verificar padrões de aprendizado
            const patterns = await session.run(`
                MATCH (p:Pattern)
                RETURN p.type as type, avg(p.score) as avg_score, count(p) as count
            `);

            if (patterns.records.length > 0) {
                console.log('  ✅ Padrões de aprendizado detectados');
                for (const record of patterns.records) {
                    const type = record.get('type');
                    const avgScore = record.get('avg_score');
                    const count = record.get('count').toNumber();
                    console.log(`     ${type}: ${count} padrões, score médio: ${avgScore?.toFixed(2) || 'N/A'}`);
                }
            } else {
                console.log('  ⚠️ Nenhum padrão de aprendizado ainda');
                this.insights.push('Sistema precisa executar para começar aprendizado');
            }

            // Verificar memórias sincronizadas
            const memories = await session.run(`
                MATCH (m:Memory {mcp_synced: true})
                RETURN count(m) as count
            `);
            const memCount = memories.records[0].get('count').toNumber();
            
            if (memCount > 0) {
                console.log(`  ✅ Memórias MCP sincronizadas: ${memCount}`);
            } else {
                console.log('  ⚠️ Nenhuma memória MCP sincronizada');
            }

        } finally {
            await session.close();
        }
    }

    async validateConfigurations() {
        console.log('\n⚙️ VALIDANDO CONFIGURAÇÕES...\n');
        
        try {
            // Verificar inputs.json
            const inputsPath = '/Users/2a/.claude/.conductor/baku/crew-ai/config/inputs.json';
            const inputs = JSON.parse(await fs.readFile(inputsPath, 'utf8'));
            
            const requiredInputs = [
                'project_scope', 'research_topic', 'development_task',
                'testing_scope', 'review_scope'
            ];
            
            for (const input of requiredInputs) {
                if (inputs[input]) {
                    console.log(`  ✅ ${input}: configured`);
                } else {
                    console.log(`  ❌ ${input}: missing`);
                    this.issues.push(`Missing input: ${input}`);
                }
            }
            
        } catch (error) {
            console.log(`  ❌ Error reading configurations: ${error.message}`);
            this.issues.push('Configuration files error');
        }
    }

    async applyFixes() {
        console.log('\n🔧 APLICANDO CORREÇÕES AUTOMÁTICAS...\n');
        const session = driver.session();
        
        try {
            // 1. Garantir projeto existe
            await session.run(`
                MERGE (p:Project {name: 'Conductor-Baku'})
                SET p.version = 'claude-20x',
                    p.status = 'active',
                    p.validated_at = datetime()
            `);
            this.fixes.push('Projeto Conductor-Baku garantido');
            
            // 2. Criar clusters básicos se não existirem
            const clusters = ['orchestration', 'implementation', 'quality'];
            for (const cluster of clusters) {
                await session.run(`
                    MERGE (c:Cluster {name: $cluster})
                    SET c.created_at = coalesce(c.created_at, datetime())
                `, { cluster });
            }
            this.fixes.push('Clusters básicos garantidos');
            
            // 3. Conectar agentes órfãos a clusters
            await session.run(`
                MATCH (a:Agent)
                WHERE NOT (a)-[:BELONGS_TO]->(:Cluster)
                WITH a
                MATCH (c:Cluster {name: 'orchestration'})
                CREATE (a)-[:BELONGS_TO]->(c)
            `);
            this.fixes.push('Agentes órfãos conectados');
            
            // 4. Criar nó de sistema de validação
            await session.run(`
                CREATE (v:Validation {
                    id: 'validation_' + toString(timestamp()),
                    timestamp: datetime(),
                    issues_found: $issues,
                    fixes_applied: $fixes,
                    insights: $insights,
                    status: 'completed'
                })
            `, {
                issues: this.issues.length,
                fixes: this.fixes.length,
                insights: this.insights.length
            });
            
            console.log(`  ✅ ${this.fixes.length} correções aplicadas`);
            
        } finally {
            await session.close();
        }
    }

    async generateReport() {
        console.log('\n' + '='.repeat(70));
        console.log('📊 RELATÓRIO DE VALIDAÇÃO E ALINHAMENTO');
        console.log('='.repeat(70));
        
        const totalIssues = this.issues.length;
        const totalFixes = this.fixes.length;
        const totalInsights = this.insights.length;
        
        // Calcular score de alinhamento
        const alignmentScore = Math.max(0, 100 - (totalIssues * 5));
        
        console.log(`\n📈 SCORE DE ALINHAMENTO: ${alignmentScore}%`);
        
        if (alignmentScore >= 90) {
            console.log('   Status: ✅ EXCELENTE - Sistema totalmente alinhado');
        } else if (alignmentScore >= 70) {
            console.log('   Status: ⚠️ BOM - Pequenos ajustes necessários');
        } else {
            console.log('   Status: ❌ PRECISA MELHORIAS - Correções importantes necessárias');
        }
        
        if (this.issues.length > 0) {
            console.log('\n❌ PROBLEMAS ENCONTRADOS:');
            this.issues.forEach((issue, i) => {
                console.log(`   ${i + 1}. ${issue}`);
            });
        } else {
            console.log('\n✅ NENHUM PROBLEMA ENCONTRADO!');
        }
        
        if (this.fixes.length > 0) {
            console.log('\n🔧 CORREÇÕES APLICADAS:');
            this.fixes.forEach((fix, i) => {
                console.log(`   ${i + 1}. ${fix}`);
            });
        }
        
        if (this.insights.length > 0) {
            console.log('\n💡 INSIGHTS E RECOMENDAÇÕES:');
            this.insights.forEach((insight, i) => {
                console.log(`   ${i + 1}. ${insight}`);
            });
        }
        
        // Salvar relatório
        const report = {
            timestamp: new Date().toISOString(),
            alignmentScore,
            issues: this.issues,
            fixes: this.fixes,
            insights: this.insights,
            recommendations: this.generateRecommendations(alignmentScore)
        };
        
        await fs.writeFile(
            '/Users/2a/.claude/.conductor/baku/crew-ai/validation_report.json',
            JSON.stringify(report, null, 2)
        );
        
        console.log('\n📝 Relatório salvo em: validation_report.json');
    }

    generateRecommendations(score) {
        const recommendations = [];
        
        if (score < 100) {
            if (this.issues.some(i => i.includes('Missing file'))) {
                recommendations.push('Instalar dependências Python: pip install -r requirements.txt');
            }
            
            if (this.issues.some(i => i.includes('Neo4j'))) {
                recommendations.push('Verificar se Neo4j está rodando: lsof -i :7687');
            }
            
            if (!this.insights.some(i => i.includes('executado'))) {
                recommendations.push('Executar o sistema para começar coleta de telemetria');
            }
        }
        
        recommendations.push('Executar crew-ai/main.py run para teste completo');
        recommendations.push('Visualizar grafo no Neo4j Browser: http://localhost:7474');
        
        return recommendations;
    }

    async close() {
        await driver.close();
    }
}

// Executar validação
async function runValidation() {
    const validator = new SystemValidator();
    
    try {
        await validator.validateProject();
        await validator.applyFixes();
        await validator.generateReport();
        
        console.log('\n' + '='.repeat(70));
        console.log('✅ VALIDAÇÃO CONCLUÍDA COM SUCESSO!');
        console.log('='.repeat(70));
        
    } catch (error) {
        console.error('❌ Erro na validação:', error);
    } finally {
        await validator.close();
    }
}

runValidation().catch(console.error);