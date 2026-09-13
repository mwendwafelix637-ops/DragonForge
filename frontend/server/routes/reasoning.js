import express from 'express';
import path from 'path';
import { fileCache } from '../utils/cache.js';

export default function reasoningRoutes(resultsDir) {
  const router = express.Router();
  const reasoningDir = path.join(resultsDir, 'reasoning');
  const resultPath = path.join(reasoningDir, 'result.json');

  router.get('/', async (req, res, next) => {
    try {
      const data = await fileCache.readJson(resultPath);
      if (data !== null) {
        res.json(data);
      } else {
        res.status(404).json({ error: 'Long-context reasoning results not found' });
      }
    } catch (err) {
      next(err);
    }
  });

  router.get('/comparison', async (req, res, next) => {
    try {
      const data = await fileCache.readJson(resultPath);
      if (data === null) {
        return res.status(404).json({ error: 'Reasoning results not found' });
      }

      const comparison = {
        tasks: Object.keys(data.accuracies || {}).map(task => ({
          name: task,
          bdh: {
            mean: data.bdh_accuracy_mean,
            std: data.bdh_accuracy_std
          },
          transformer: {
            mean: data.transformer_accuracy_mean,
            std: data.transformer_accuracy_std
          },
          seeds: data.seeds,
          tag: data.tag
        }))
      };

      res.json(comparison);
    } catch (err) {
      next(err);
    }
  });

  return router;
}
