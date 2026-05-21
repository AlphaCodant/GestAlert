// Proxy minimal : transmet toutes les requêtes du port 3000 vers le backend FastAPI sur port 8001.
// Cela permet à l'application Jinja2 (server-rendered) du backend GestPro
// d'être servie par l'ingress Kubernetes qui route /* vers le port 3000.
const http = require('http');
const httpProxy = require('http-proxy');

const PORT = process.env.PORT || 3000;
const TARGET = process.env.BACKEND_URL || 'http://127.0.0.1:8001';

const proxy = httpProxy.createProxyServer({
  target: TARGET,
  changeOrigin: false,
  xfwd: true,
  ws: true,
});

proxy.on('error', (err, req, res) => {
  console.error(`[proxy error] ${req.method} ${req.url}: ${err.message}`);
  if (res && !res.headersSent) {
    res.writeHead(502, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end(`Bad gateway: backend FastAPI indisponible (${err.message})`);
  }
});

const server = http.createServer((req, res) => {
  proxy.web(req, res);
});

server.on('upgrade', (req, socket, head) => {
  proxy.ws(req, socket, head);
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[proxy] GestPro frontend proxy listening on 0.0.0.0:${PORT} → ${TARGET}`);
});
