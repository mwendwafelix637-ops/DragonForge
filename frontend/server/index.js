import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import chokidar from 'chokidar';

import { fileCache } from './utils/cache.js';
import { createRateLimiter } from './middleware/rateLimiter.js';
import structureRoutes from './routes/structure.js';
import continualRoutes from './routes/continual.js';
import reasoningRoutes from './routes/reasoning.js';
import summaryRoutes from './routes/summary.js';
import configRoutes from './routes/config.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3001;

const RESULTS_DIR = process.env.RESULTS_DIR || path.resolve(__dirname, '../../results');
const CONFIG_PATH = process.env.CONFIG_PATH || path.resolve(__dirname, '../../configs/default.yaml');

app.use(cors());
app.use(express.json({ limit: '2mb' }));

app.use(createRateLimiter({
  windowMs: 10 * 1000,
  maxRequests: 200
}));

app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    uptime: process.uptime()
  });
});

app.use('/api/structure', structureRoutes(RESULTS_DIR));
app.use('/api/continual', continualRoutes(RESULTS_DIR));
app.use('/api/reasoning', reasoningRoutes(RESULTS_DIR));
app.use('/api/summary', summaryRoutes(RESULTS_DIR));
app.use('/api/config', configRoutes(CONFIG_PATH));

app.use((req, res) => {
  if (!res.headersSent) {
    res.status(404).json({ error: 'Endpoint not found', path: req.originalUrl });
  }
});

app.use((err, req, res, next) => {
  console.error('[NeuroLens Server Error]:', err && err.stack ? err.stack : err);
  if (!res.headersSent) {
    res.status(err.status || 500).json({
      error: 'Internal server error',
      message: err.message || 'An unexpected error occurred'
    });
  }
});

const server = app.listen(PORT, () => {
  console.log(`NeuroLens API server running on http://localhost:${PORT}`);
  console.log(`Reading results from: ${RESULTS_DIR}`);
  console.log(`Reading config from: ${CONFIG_PATH}`);
});

server.keepAliveTimeout = 65000;
server.headersTimeout = 66000;

process.on('unhandledRejection', (reason) => {
  console.error('[Unhandled Rejection]:', reason && reason.stack ? reason.stack : reason);
});

process.on('uncaughtException', (err) => {
  console.error('[Uncaught Exception]:', err && err.stack ? err.stack : err);
});

try {
  const watchPaths = [RESULTS_DIR, CONFIG_PATH];
  const watcher = chokidar.watch(watchPaths, {
    ignored: /(^|[\/\\])\../,
    persistent: true,
    ignoreInitial: true,
    awaitWriteFinish: { stabilityThreshold: 200, pollInterval: 50 },
  });

  watcher.on('all', (event, filePath) => {
    console.log(`[File Watcher] ${event}: ${filePath}`);
    fileCache.invalidate(filePath);
  });

  watcher.on('error', (err) => {
    console.error('[File Watcher Error]:', err.message);
  });
} catch (err) {
  console.error('[File Watcher Failed to Initialize]:', err.message);
}

export default app;
