#!/usr/bin/env python3
import socketio
import time
import sys

# Criar cliente socket.io
sio = socketio.Client()
session_id = None
message_count = 0

@sio.event
def connect():
    print("✅ Conectado ao servidor")
    # Criar sessão
    sio.emit('create_session', {'title': 'Teste Automatizado'})

@sio.event
def session_created(data):
    global session_id
    session_id = data.get('sessionId', data.get('id'))
    print(f"📁 Sessão criada: {session_id}")
    
    if session_id:
        # Enviar primeira mensagem
        print('\n📤 Enviando: "o que é claude?"')
        sio.emit('message', {
            'sessionId': session_id,
            'content': 'o que é claude?'
        })

@sio.event
def processing_step(data):
    step = data.get('step', '')
    if step:
        print(f"⚙️  {step}")

@sio.event
def message_stream(data):
    content = data.get('content', '')
    if content and len(content) > 0:
        preview = content[:50] + '...' if len(content) > 50 else content
        print(f"🌊 Streaming: {preview}")

@sio.event
def message_complete(data):
    global message_count
    message_count += 1
    
    content = data.get('content', '')
    print(f"\n✅ Mensagem {message_count} completa!")
    
    if content:
        preview = content[:200] + '...' if len(content) > 200 else content
        print(f"📝 Resposta: {preview}")
    
    if message_count == 1:
        # Enviar segunda mensagem
        time.sleep(2)
        print('\n📤 Enviando: "do que se trata esse projeto?"')
        sio.emit('message', {
            'sessionId': session_id,
            'content': 'do que se trata esse projeto?'
        })
    else:
        # Teste concluído
        print("\n🎉 Teste concluído com sucesso!")
        time.sleep(1)
        sio.disconnect()
        sys.exit(0)

@sio.event
def error(data):
    print(f"❌ Erro: {data}")
    sys.exit(1)

@sio.event
def disconnect():
    print("🔌 Desconectado")

# Conectar ao servidor
try:
    print("🔗 Conectando ao servidor...")
    sio.connect('http://localhost:8080')
    
    # Aguardar até 30 segundos
    time.sleep(30)
    print("⏱️  Timeout - encerrando")
    
except Exception as e:
    print(f"❌ Erro de conexão: {e}")
    sys.exit(1)
finally:
    sio.disconnect()