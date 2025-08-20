const io = require('socket.io-client');
const fs = require('fs');

// Configuração de teste
const SERVER_URL = 'http://localhost:8081';
const TEST_RESULTS_FILE = 'tests/baseline_results.json';

class MessageDuplicationTester {
  constructor() {
    this.socket = null;
    this.testResults = {
      timestamp: new Date().toISOString(),
      tests: [],
      summary: {
        totalMessages: 0,
        duplicateMessages: 0,
        queueLength: 0,
        errors: []
      }
    };
  }

  async connect() {
    return new Promise((resolve, reject) => {
      this.socket = io(SERVER_URL);
      
      this.socket.on('connect', () => {
        console.log('✅ Conectado ao servidor');
        resolve();
      });

      this.socket.on('connect_error', (error) => {
        console.log('❌ Erro na conexão:', error.message);
        reject(error);
      });

      this.socket.on('disconnect', () => {
        console.log('🔌 Desconectado do servidor');
      });

      // Capturar todas as mensagens
      this.socket.on('message', (data) => {
        console.log('📨 Mensagem recebida:', data);
        this.testResults.summary.totalMessages++;
      });

      this.socket.on('queue_update', (data) => {
        console.log('🔄 Atualização da fila:', data);
        this.testResults.summary.queueLength = data.length || 0;
      });

      this.socket.on('error', (error) => {
        console.log('⚠️ Erro no socket:', error);
        this.testResults.summary.errors.push(error);
      });
    });
  }

  async testSingleMessage() {
    console.log('\n=== TESTE 1: Mensagem Única ===');
    const testMessage = {
      id: 'test-' + Date.now(),
      content: 'Teste de mensagem única',
      timestamp: Date.now()
    };

    return new Promise((resolve) => {
      const messagesReceived = [];
      
      const messageHandler = (data) => {
        messagesReceived.push(data);
        console.log('Mensagem recebida:', data);
      };

      this.socket.on('message', messageHandler);

      // Enviar mensagem
      this.socket.emit('chat_message', testMessage);

      // Aguardar 3 segundos para capturar duplicações
      setTimeout(() => {
        this.socket.off('message', messageHandler);
        
        const testResult = {
          name: 'single_message',
          input: testMessage,
          messagesReceived: messagesReceived.length,
          messages: messagesReceived,
          hasDuplication: messagesReceived.length > 1,
          duplicateCount: messagesReceived.length > 1 ? messagesReceived.length - 1 : 0
        };

        this.testResults.tests.push(testResult);
        this.testResults.summary.duplicateMessages += testResult.duplicateCount;
        
        console.log(`Resultado: ${messagesReceived.length} mensagem(s) recebida(s)`);
        if (testResult.hasDuplication) {
          console.log(`⚠️ DUPLICAÇÃO DETECTADA: ${testResult.duplicateCount} duplicatas`);
        }
        
        resolve(testResult);
      }, 3000);
    });
  }

  async testRapidMessages() {
    console.log('\n=== TESTE 2: Mensagens Rápidas ===');
    const testMessages = [
      { id: 'rapid-1-' + Date.now(), content: 'Mensagem rápida 1' },
      { id: 'rapid-2-' + Date.now(), content: 'Mensagem rápida 2' },
      { id: 'rapid-3-' + Date.now(), content: 'Mensagem rápida 3' }
    ];

    return new Promise((resolve) => {
      const messagesReceived = [];
      
      const messageHandler = (data) => {
        messagesReceived.push(data);
        console.log('Mensagem recebida:', data);
      };

      this.socket.on('message', messageHandler);

      // Enviar mensagens rapidamente
      testMessages.forEach((msg, index) => {
        setTimeout(() => {
          this.socket.emit('chat_message', msg);
        }, index * 100); // 100ms entre mensagens
      });

      // Aguardar 5 segundos para capturar todas as respostas
      setTimeout(() => {
        this.socket.off('message', messageHandler);
        
        const expectedMessages = testMessages.length;
        const actualMessages = messagesReceived.length;
        
        const testResult = {
          name: 'rapid_messages',
          input: testMessages,
          expectedMessages,
          actualMessages,
          messagesReceived,
          hasDuplication: actualMessages > expectedMessages,
          duplicateCount: actualMessages > expectedMessages ? actualMessages - expectedMessages : 0
        };

        this.testResults.tests.push(testResult);
        this.testResults.summary.duplicateMessages += testResult.duplicateCount;
        
        console.log(`Resultado: ${actualMessages} de ${expectedMessages} mensagens esperadas`);
        if (testResult.hasDuplication) {
          console.log(`⚠️ DUPLICAÇÃO DETECTADA: ${testResult.duplicateCount} duplicatas`);
        }
        
        resolve(testResult);
      }, 5000);
    });
  }

  async testQueueState() {
    console.log('\n=== TESTE 3: Estado da Fila ===');
    
    return new Promise((resolve) => {
      // Solicitar estado da fila
      this.socket.emit('get_queue_status');
      
      const queueHandler = (data) => {
        console.log('Estado da fila:', data);
        
        const testResult = {
          name: 'queue_state',
          queueData: data,
          queueLength: data.length || 0,
          items: data.items || data
        };

        this.testResults.tests.push(testResult);
        this.testResults.summary.queueLength = testResult.queueLength;
        
        this.socket.off('queue_status', queueHandler);
        resolve(testResult);
      };

      this.socket.on('queue_status', queueHandler);
      
      // Timeout caso não receba resposta
      setTimeout(() => {
        this.socket.off('queue_status', queueHandler);
        const testResult = {
          name: 'queue_state',
          error: 'Timeout - nenhuma resposta da fila',
          queueLength: 0
        };
        this.testResults.tests.push(testResult);
        resolve(testResult);
      }, 3000);
    });
  }

  async disconnect() {
    if (this.socket) {
      this.socket.disconnect();
    }
  }

  async saveResults() {
    // Garantir que o diretório existe
    const dir = 'tests';
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    // Adicionar resumo final
    this.testResults.summary.hasDuplicationIssues = this.testResults.summary.duplicateMessages > 0;
    this.testResults.summary.testsPassed = this.testResults.tests.filter(t => !t.hasDuplication && !t.error).length;
    this.testResults.summary.testsTotal = this.testResults.tests.length;

    fs.writeFileSync(TEST_RESULTS_FILE, JSON.stringify(this.testResults, null, 2));
    console.log(`\n📄 Resultados salvos em: ${TEST_RESULTS_FILE}`);
  }

  generateReport() {
    console.log('\n' + '='.repeat(60));
    console.log('           RELATÓRIO DE BASELINE - DUPLICAÇÃO DE MENSAGENS');
    console.log('='.repeat(60));
    console.log(`📅 Data: ${this.testResults.timestamp}`);
    console.log(`📊 Total de testes: ${this.testResults.summary.testsTotal}`);
    console.log(`✅ Testes sem problemas: ${this.testResults.summary.testsPassed}`);
    console.log(`📨 Total de mensagens: ${this.testResults.summary.totalMessages}`);
    console.log(`🔄 Mensagens duplicadas: ${this.testResults.summary.duplicateMessages}`);
    console.log(`📋 Tamanho da fila: ${this.testResults.summary.queueLength}`);
    console.log(`⚠️ Erros: ${this.testResults.summary.errors.length}`);
    
    if (this.testResults.summary.hasDuplicationIssues) {
      console.log('\n❌ PROBLEMA DETECTADO: Duplicação de mensagens identificada');
    } else {
      console.log('\n✅ ESTADO OK: Nenhuma duplicação detectada');
    }

    console.log('\n📋 DETALHES DOS TESTES:');
    this.testResults.tests.forEach((test, index) => {
      console.log(`\n${index + 1}. ${test.name.toUpperCase()}`);
      if (test.hasDuplication) {
        console.log(`   ❌ Duplicação: ${test.duplicateCount} mensagens extras`);
      } else if (test.error) {
        console.log(`   ⚠️ Erro: ${test.error}`);
      } else {
        console.log(`   ✅ OK`);
      }
    });

    console.log('\n' + '='.repeat(60));
    
    return this.testResults;
  }
}

// Executar testes
async function runTests() {
  const tester = new MessageDuplicationTester();
  
  try {
    console.log('🚀 Iniciando testes de baseline...');
    
    await tester.connect();
    await tester.testSingleMessage();
    await tester.testRapidMessages();
    await tester.testQueueState();
    
    await tester.saveResults();
    const results = tester.generateReport();
    
    await tester.disconnect();
    
    return results;
  } catch (error) {
    console.error('❌ Erro durante os testes:', error);
    await tester.disconnect();
    throw error;
  }
}

// Executar se chamado diretamente
if (require.main === module) {
  runTests()
    .then(() => {
      console.log('\n✅ Testes concluídos com sucesso!');
      process.exit(0);
    })
    .catch((error) => {
      console.error('\n❌ Testes falharam:', error);
      process.exit(1);
    });
}

module.exports = { MessageDuplicationTester, runTests };