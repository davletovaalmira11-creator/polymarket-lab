import http.server
import socketserver
import json
import os

PORT = 8080
TEMPLATE_PATH = "/data/data/com.termux/files/home/AI_WORKSPACE/polymarket_lab/templates/index.html"

class MyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            with open(TEMPLATE_PATH, 'rb') as f:
                self.wfile.write(f.read())
        elif self.path == '/api/data':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            balance = 1000.0
            strategy = {}
            if os.path.exists("paper_trades.json"):
                with open("paper_trades.json", "r") as f:
                    balance = json.load(f).get('balance', 1000.0)
            if os.path.exists("best_strategy.json"):
                with open("best_strategy.json", "r") as f:
                    strategy = json.load(f)
                    
            self.wfile.write(json.dumps({'balance': balance, 'strategy': strategy}).encode())
        else:
            super().do_GET()

with socketserver.TCPServer(("", PORT), MyHandler) as httpd:
    httpd.serve_forever()
