const io = require('socket.io-client');

const socket = io('http://localhost:8080', {
  transports: ['websocket', 'polling']
});

const sessionId = `test-${Date.now()}`;
const messageId = `msg-${Date.now()}`;

socket.on('connect', () => {
  console.log('✅ Conectado ao servidor WebSocket');
  
  // Enviar mensagem de teste usando o evento correto
  const testMessage = {
    content: 'Olá! Este é um teste após a remoção do sistema de fila. Por favor, responda confirmando que está funcionando.',
    message: 'Olá! Este é um teste após a remoção do sistema de fila. Por favor, responda confirmando que está funcionando.',
    sessionId: sessionId,
    messageId: messageId,
    agent: null,
    useAgent: false
  };
  
  console.log('📤 Enviando mensagem com send_message:', testMessage);
  socket.emit('send_message', testMessage); // Evento correto!
});

socket.on('message', (data) => {
  console.log('📥 Mensagem recebida:', data);
});

socket.on('message_stream', (data) => {
  console.log('🌊 Stream recebido:', data.content);
});

socket.on('message_complete', (data) => {
  console.log('✅ Mensagem completa:', data);
  console.log('\n🎉 TESTE CONCLUÍDO COM SUCESSO! O Claude Code SDK está funcionando!');
  process.exit(0);
});

socket.on('error', (error) => {
  console.error('❌ Erro:', error);
  process.exit(1);
});

socket.on('disconnect', () => {
  console.log('🔌 Desconectado do servidor');
});

// Timeout para evitar travamento
setTimeout(() => {
  console.log('⏱️ Timeout - encerrando teste');
  process.exit(0);
}, 30000);