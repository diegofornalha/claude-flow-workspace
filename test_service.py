#!/usr/bin/env python3
"""Serviço de teste para verificar descoberta automática"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class TestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "status": "ok",
                "service": "test-service",
                "version": "1.0.0"
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Silencia logs

print("🚀 Iniciando serviço de teste na porta 3500...")
httpd = HTTPServer(('localhost', 3500), TestHandler)
print("✅ Serviço rodando em http://localhost:3500/health")
httpd.serve_forever()