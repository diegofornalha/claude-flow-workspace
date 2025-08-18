const io = require('socket.io-client');

console.log('🔌 Conectando ao servidor...');
const socket = io('http://localhost:8080');

socket.on('connect', () => {
  console.log('✅ Conectado! Socket ID:', socket.id);
  
  // Aguardar um pouco para receber lista de agentes
  setTimeout(() => {
    console.log('📤 Enviando mensagem via A2A...');
    socket.emit('a2a:send_message', {
      message: 'Olá, teste A2A!',
      sessionId: 'test-' + Date.now(),
      useAgent: true
    });
  }, 1000);
});

// Escutar eventos A2A
socket.on('a2a:agents', (data) => {
  console.log('📋 Agentes disponíveis:', data.agents?.map(a => `${a.name} (${a.status})`).join(', '));
  
  // Selecionar crew-ai se disponível
  const crewAi = data.agents?.find(a => a.name === 'crew-ai' && a.status === 'connected');
  if (crewAi) {
    console.log('🤖 Selecionando crew-ai...');
    socket.emit('a2a:select_agent', { agent: 'crew-ai' });
  }
});

socket.on('a2a:agent_selected', (data) => {
  console.log('✅ Agente selecionado:', data);
});

socket.on('message', (data) => {
  console.log('💬 Mensagem recebida:', {
    type: data.type,
    content: data.content?.substring(0, 100),
    agent: data.agent
  });
});

socket.on('stream', (data) => {
  process.stdout.write(data.chunk || '');
});

socket.on('stream_end', () => {
  console.log('\n✅ Stream finalizado');
  setTimeout(() => {
    console.log('👋 Desconectando...');
    socket.disconnect();
    process.exit(0);
  }, 1000);
});

socket.on('a2a:message_response', (data) => {
  console.log('🤖 Resposta A2A:', data);
});

socket.on('a2a:error', (error) => {
  console.error('❌ Erro A2A:', error);
  process.exit(1);
});

socket.on('error', (error) => {
  console.error('❌ Erro de socket:', error);
  process.exit(1);
});

// Timeout de segurança
setTimeout(() => {
  console.log('⏱️ Timeout - encerrando teste');
  process.exit(0);
}, 15000);