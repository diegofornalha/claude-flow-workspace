#!/usr/bin/env python3
"""
🤖 Hello World Service - Porta 3500
Serviço simples para demonstração do sistema de descoberta
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from datetime import datetime

class HelloWorldHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "status": "healthy",
                "service": "helloworld",
                "version": "1.0.0",
                "timestamp": datetime.now().isoformat(),
                "message": "Hello World Service is running!"
            }
            self.wfile.write(json.dumps(response).encode())
        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "name": "Hello World Service",
                "type": "demo",
                "port": 3500,
                "endpoints": ["/", "/health", "/hello"],
                "description": "Serviço de demonstração para o sistema de descoberta"
            }
            self.wfile.write(json.dumps(response).encode())
        elif self.path == '/hello':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write("Hello, World! 👋".encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {format % args}")

if __name__ == "__main__":
    PORT = 3500
    print(f"🚀 Iniciando Hello World Service na porta {PORT}...")
    print("📍 Endpoints disponíveis:")
    print("   - http://localhost:3500/        (informações do serviço)")
    print("   - http://localhost:3500/health  (status de saúde)")
    print("   - http://localhost:3500/hello   (mensagem hello world)")
    
    httpd = HTTPServer(('localhost', PORT), HelloWorldHandler)
    print(f"✅ Serviço rodando em http://localhost:{PORT}")
    print("🔍 Aguardando descoberta pelo Service Discovery...")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Encerrando Hello World Service...")
        httpd.shutdown()