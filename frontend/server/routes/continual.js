import express from 'express';
import path from 'path';
import { fileCache } from '../utils/cache.js';

export default function continualRoutes(resultsDir) {
  const router = express.Router();
  const continualDir = path.join(resultsDir, 'continual');
  const resultPath = path.join(continualDir, 'result.json');

  router.get('/', async (req, res, next) => {
    try {
      const data = await fileCache.readJson(resultPath);
      if (data !== null) {
        res.json(data);
      } else {
        res.status(404).json({ error: 'Continual learning results not found' });
      }
    } catch (err) {
      next(err);
    }
  });

  router.get('/bdh', async (req, res, next) => {
    try {
      const bdhPath = path.join(continualDir, 'bdh_result.json');
      const bdhData = await fileCache.readJson(bdhPath);
      
      if (bdhData !== null) {
        return res.json(bdhData);
      }

      const data = await fileCache.readJson(resultPath);
      if (data !== null) {
        return res.json({
          task_a_before: data.task_a_before,
          task_a_after: data.task_a_after,
          task_b_after: data.task_b_after,
          forgetting: data.forgetting,
          tag: data.tag,
          seeds: data.seeds
        });
      }

      res.status(404).json({ error: 'BDH continual results not found' });
    } catch (err) {
      next(err);
    }
  });

  router.get('/transformer', async (req, res, next) => {
    try {
      const transPath = path.join(continualDir, 'transformer_result.json');
      const transData = await fileCache.readJson(transPath);

      if (transData !== null) {
        return res.json(transData);
      }

      const data = await fileCache.readJson(resultPath);
      if (data !== null) {
        return res.json(data.baseline_transformer || {});
      }

      res.status(404).json({ error: 'Transformer continual results not found' });
    } catch (err) {
      next(err);
    }
  });

  return router;
}
