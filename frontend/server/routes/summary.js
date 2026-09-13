import express from 'express';
import path from 'path';
import { fileCache } from '../utils/cache.js';

export default function summaryRoutes(resultsDir) {
  const router = express.Router();
  const summaryPath = path.join(resultsDir, 'summary.json');

  router.get('/', async (req, res, next) => {
    try {
      const data = await fileCache.readJson(summaryPath);
      if (data !== null) {
        res.json(data);
      } else {
        res.status(404).json({ error: 'Summary not found' });
      }
    } catch (err) {
      next(err);
    }
  });

  router.get('/headline', async (req, res, next) => {
    try {
      const data = await fileCache.readJson(summaryPath);
      if (data !== null) {
        res.json({ headline: data.headline });
      } else {
        res.status(404).json({ error: 'Summary not found' });
      }
    } catch (err) {
      next(err);
    }
  });

  return router;
}
