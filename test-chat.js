const io = require('socket.io-client');

// Conectar ao servidor
const socket = io('http://localhost:8080');

let sessionId = null;

socket.on('connect', () => {
  console.log('✅ Conectado ao servidor');
  
  // Criar nova sessão
  socket.emit('create_session', { title: 'Teste Automatizado' });
});

socket.on('session_created', (data) => {
  console.log('📁 Sessão criada:', data.sessionId);
  sessionId = data.sessionId;
  
  // Enviar primeira mensagem
  console.log('\n📤 Enviando primeira mensagem: "o que é claude?"');
  socket.emit('message', {
    sessionId: sessionId,
    content: 'o que é claude?'
  });
});

socket.on('processing_step', (data) => {
  console.log('⚙️ Processando:', data.step, data.details || '');
});

socket.on('message_stream', (data) => {
  if (data.content) {
    console.log('🌊 Streaming:', data.content.substring(0, 50) + '...');
  }
});

socket.on('message_complete', (data) => {
  console.log('\n✅ Resposta completa recebida!');
  console.log('📝 Conteúdo:', data.content.substring(0, 200) + '...');
  console.log('📊 Tokens usados:', data.usage?.output_tokens || 0);
  
  // Após receber primeira resposta, enviar segunda mensagem
  if (data.content.includes('Claude')) {
    setTimeout(() => {
      console.log('\n📤 Enviando segunda mensagem: "do que se trata esse projeto?"');
      socket.emit('message', {
        sessionId: sessionId,
        content: 'do que se trata esse projeto?'
      });
    }, 2000);
  } else {
    // Se já é a segunda resposta, encerrar
    setTimeout(() => {
      console.log('\n✅ Teste concluído com sucesso!');
      process.exit(0);
    }, 2000);
  }
});

socket.on('error', (error) => {
  console.error('❌ Erro recebido:', error);
  process.exit(1);
});

socket.on('disconnect', () => {
  console.log('🔌 Desconectado do servidor');
});

// Timeout de segurança
setTimeout(() => {
  console.log('⏱️ Timeout - encerrando teste');
  process.exit(0);
}, 30000);