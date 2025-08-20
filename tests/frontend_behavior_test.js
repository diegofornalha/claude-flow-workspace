const fs = require('fs');
const path = require('path');

class FrontendBehaviorTester {
  constructor() {
    this.results = {
      timestamp: new Date().toISOString(),
      frontend_url: 'http://localhost:3002',
      backend_url: 'http://localhost:8081',
      tests: [],
      console_logs: [],
      network_requests: [],
      errors: [],
      summary: {
        total_tests: 0,
        passed_tests: 0,
        failed_tests: 0,
        duplicate_messages: 0,
        queue_operations: 0
      }
    };
  }

  async setup() {
    try {
      // Verificar se o puppeteer está disponível
      console.log('🚀 Iniciando teste de comportamento do frontend...');
      console.log('⚠️ NOTA: Este teste simula comportamentos sem puppeteer');
      
      // Simular teste de conexão frontend
      const response = await this.fetchWithTimeout('http://localhost:3002', 5000);
      if (response) {
        console.log('✅ Frontend acessível na porta 3002');
      } else {
        console.log('❌ Frontend não encontrado - continuando com simulação');
      }
      
      return true;
    } catch (error) {
      console.log('⚠️ Erro no setup, continuando com simulação:', error.message);
      return false;
    }
  }

  async fetchWithTimeout(url, timeout = 5000) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);
      
      const response = await fetch(url, {
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      return response;
    } catch (error) {
      return null;
    }
  }

  async testMessageDeduplication() {
    console.log('\n=== TESTE: Dedupliação de Mensagens no Frontend ===');
    
    const testResult = {
      name: 'message_deduplication',
      status: 'simulated',
      findings: [],
      recommendations: []
    };

    // Simular análise baseada nos arquivos existentes
    try {
      const hookFile = '/Users/2a/.claude/.conductor/kingston/chat-app-claude-code-sdk/frontend/src/hooks/useMessageDeduplication.ts';
      const queueFile = '/Users/2a/.claude/.conductor/kingston/chat-app-claude-code-sdk/frontend/src/hooks/useMessageQueue.ts';
      
      if (fs.existsSync(hookFile)) {
        testResult.findings.push('✅ useMessageDeduplication hook encontrado');
        const content = fs.readFileSync(hookFile, 'utf8');
        if (content.includes('generateUniqueId') || content.includes('deduplication')) {
          testResult.findings.push('✅ Lógica de deduplicação identificada');
        }
      } else {
        testResult.findings.push('❌ Hook de deduplicação não encontrado');
        testResult.recommendations.push('Implementar hook useMessageDeduplication.ts');
      }

      if (fs.existsSync(queueFile)) {
        testResult.findings.push('✅ useMessageQueue hook encontrado');
        const content = fs.readFileSync(queueFile, 'utf8');
        if (content.includes('generateUniqueId')) {
          testResult.findings.push('✅ Geração de ID único implementada');
        }
        if (content.includes('processing') && content.includes('queue')) {
          testResult.findings.push('✅ Sistema de fila implementado');
        }
      } else {
        testResult.findings.push('❌ Hook de fila não encontrado');
      }

    } catch (error) {
      testResult.findings.push(`⚠️ Erro na análise: ${error.message}`);
    }

    this.results.tests.push(testResult);
    return testResult;
  }

  async testUIComponents() {
    console.log('\n=== TESTE: Componentes de UI ===');
    
    const testResult = {
      name: 'ui_components',
      status: 'simulated',
      components_found: [],
      components_missing: [],
      issues: []
    };

    const expectedComponents = [
      'MessageQueue',
      'ProcessingIndicator', 
      'SystemMetrics',
      'UISettings',
      'AgentSelector'
    ];

    expectedComponents.forEach(component => {
      const componentPath = `/Users/2a/.claude/.conductor/kingston/chat-app-claude-code-sdk/frontend/src/components/${component}`;
      
      if (fs.existsSync(componentPath) || fs.existsSync(`${componentPath}.tsx`) || fs.existsSync(`${componentPath}/${component}.tsx`)) {
        testResult.components_found.push(component);
      } else {
        testResult.components_missing.push(component);
        testResult.issues.push(`Componente ${component} não encontrado`);
      }
    });

    this.results.tests.push(testResult);
    return testResult;
  }

  async testStateManagement() {
    console.log('\n=== TESTE: Gerenciamento de Estado ===');
    
    const testResult = {
      name: 'state_management',
      status: 'simulated',
      hooks_found: [],
      context_found: false,
      state_issues: []
    };

    // Verificar hooks customizados
    const hooksDir = '/Users/2a/.claude/.conductor/kingston/chat-app-claude-code-sdk/frontend/src/hooks';
    if (fs.existsSync(hooksDir)) {
      const hooks = fs.readdirSync(hooksDir).filter(file => file.endsWith('.ts') || file.endsWith('.tsx'));
      testResult.hooks_found = hooks;
    }

    // Verificar contexto
    const contextDir = '/Users/2a/.claude/.conductor/kingston/chat-app-claude-code-sdk/frontend/src/context';
    if (fs.existsSync(contextDir)) {
      testResult.context_found = true;
    }

    // Analisar App.tsx para duplicações potenciais
    const appFile = '/Users/2a/.claude/.conductor/kingston/chat-app-claude-code-sdk/frontend/src/App.tsx';
    if (fs.existsSync(appFile)) {
      const content = fs.readFileSync(appFile, 'utf8');
      
      // Procurar por potenciais problemas
      const socketConnections = (content.match(/io\(/g) || []).length;
      const useEffects = (content.match(/useEffect/g) || []).length;
      const socketEmits = (content.match(/socket\.emit/g) || []).length;

      testResult.socket_connections = socketConnections;
      testResult.use_effects = useEffects;
      testResult.socket_emits = socketEmits;

      if (socketConnections > 1) {
        testResult.state_issues.push(`Múltiplas conexões socket detectadas: ${socketConnections}`);
      }

      if (useEffects > 10) {
        testResult.state_issues.push(`Muitos useEffect detectados: ${useEffects} - pode causar re-renders`);
      }
    }

    this.results.tests.push(testResult);
    return testResult;
  }

  async checkCurrentErrors() {
    console.log('\n=== VERIFICANDO ERROS ATUAIS ===');
    
    // Verificar logs do frontend
    const frontendLog = '/Users/2a/.claude/.conductor/kingston/chat-app-claude-code-sdk/frontend/frontend_test.log';
    if (fs.existsSync(frontendLog)) {
      const content = fs.readFileSync(frontendLog, 'utf8');
      const errors = content.split('\n').filter(line => 
        line.includes('ERROR') || 
        line.includes('Cannot find module') ||
        line.includes('TS2307')
      );
      
      this.results.errors = errors;
      console.log(`📋 ${errors.length} erros encontrados no frontend`);
      errors.forEach(error => console.log(`   • ${error}`));
    }

    return this.results.errors;
  }

  generateReport() {
    console.log('\n' + '='.repeat(70));
    console.log('           RELATÓRIO DE BASELINE - COMPORTAMENTO DO FRONTEND');
    console.log('='.repeat(70));
    console.log(`📅 Data: ${this.results.timestamp}`);
    console.log(`🌐 Frontend: ${this.results.frontend_url}`);
    console.log(`🔧 Backend: ${this.results.backend_url}`);
    console.log(`📊 Total de testes: ${this.results.tests.length}`);
    console.log(`⚠️ Erros encontrados: ${this.results.errors.length}`);

    this.results.tests.forEach((test, index) => {
      console.log(`\n${index + 1}. ${test.name.toUpperCase().replace(/_/g, ' ')}`);
      console.log(`   Status: ${test.status}`);
      
      if (test.findings) {
        test.findings.forEach(finding => console.log(`   ${finding}`));
      }
      
      if (test.components_found) {
        console.log(`   Componentes encontrados: ${test.components_found.join(', ')}`);
      }
      
      if (test.components_missing && test.components_missing.length > 0) {
        console.log(`   Componentes ausentes: ${test.components_missing.join(', ')}`);
      }
      
      if (test.hooks_found && test.hooks_found.length > 0) {
        console.log(`   Hooks encontrados: ${test.hooks_found.join(', ')}`);
      }
      
      if (test.state_issues && test.state_issues.length > 0) {
        console.log(`   Problemas de estado:`);
        test.state_issues.forEach(issue => console.log(`     • ${issue}`));
      }

      if (test.recommendations && test.recommendations.length > 0) {
        console.log(`   Recomendações:`);
        test.recommendations.forEach(rec => console.log(`     • ${rec}`));
      }
    });

    if (this.results.errors.length > 0) {
      console.log(`\n❌ ERROS CRÍTICOS ENCONTRADOS:`);
      this.results.errors.slice(0, 5).forEach(error => {
        console.log(`   • ${error.trim()}`);
      });
      if (this.results.errors.length > 5) {
        console.log(`   ... e mais ${this.results.errors.length - 5} erros`);
      }
    }

    console.log('\n' + '='.repeat(70));
    
    return this.results;
  }

  async saveResults() {
    const resultsFile = 'tests/frontend_baseline_results.json';
    fs.writeFileSync(resultsFile, JSON.stringify(this.results, null, 2));
    console.log(`\n📄 Resultados salvos em: ${resultsFile}`);
  }

  async cleanup() {
    if (this.browser) {
      await this.browser.close();
    }
  }
}

async function runFrontendTests() {
  const tester = new FrontendBehaviorTester();
  
  try {
    await tester.setup();
    await tester.testMessageDeduplication();
    await tester.testUIComponents();
    await tester.testStateManagement();
    await tester.checkCurrentErrors();
    
    const results = tester.generateReport();
    await tester.saveResults();
    
    return results;
  } catch (error) {
    console.error('❌ Erro durante testes do frontend:', error);
    throw error;
  } finally {
    await tester.cleanup();
  }
}

// Executar se chamado diretamente
if (require.main === module) {
  runFrontendTests()
    .then(() => {
      console.log('\n✅ Testes do frontend concluídos!');
      process.exit(0);
    })
    .catch((error) => {
      console.error('\n❌ Testes do frontend falharam:', error);
      process.exit(1);
    });
}

module.exports = { FrontendBehaviorTester, runFrontendTests };