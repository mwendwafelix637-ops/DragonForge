import express from 'express';
import path from 'path';
import { fileCache } from '../utils/cache.js';

export default function structureRoutes(resultsDir) {
  const router = express.Router();
  const structureDir = path.join(resultsDir, 'structure');

  router.get('/', async (req, res, next) => {
    try {
      const checkpoints = await fileCache.readJsonDir(
        structureDir,
        f => f.endsWith('.json') && f.startsWith('checkpoint_')
      );
      res.json({ checkpoints, count: checkpoints.length });
    } catch (err) {
      next(err);
    }
  });

  router.get('/latest', async (req, res, next) => {
    try {
      const checkpoints = await fileCache.readJsonDir(
        structureDir,
        f => f.endsWith('.json') && f.startsWith('checkpoint_')
      );

      if (checkpoints.length > 0) {
        res.json(checkpoints[checkpoints.length - 1]);
      } else {
        res.status(404).json({ error: 'No checkpoint data found' });
      }
    } catch (err) {
      next(err);
    }
  });

  router.get('/comparison', async (req, res, next) => {
    try {
      const bdhPath = path.join(structureDir, 'bdh', 'bdh_structural_metrics.json');
      const transPath = path.join(structureDir, 'transformer', 'transformer_structural_metrics.json');

      const [bdhMetrics, transMetrics] = await Promise.all([
        fileCache.readJson(bdhPath),
        fileCache.readJson(transPath)
      ]);

      res.json({ bdh: bdhMetrics, transformer: transMetrics });
    } catch (err) {
      next(err);
    }
  });

  router.get('/graph', async (req, res, next) => {
    try {
      const model = req.query.model === 'transformer' ? 'transformer' : 'bdh';
      const graphPath = path.join(structureDir, model, `${model}_interaction_graph.json`);

      const graph = await fileCache.readJson(graphPath);
      if (graph === null) {
        return res.status(404).json({ error: `Graph data not found or invalid for ${model}` });
      }

      res.json(graph);
    } catch (err) {
      next(err);
    }
  });

  return router;
}
