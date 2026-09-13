import express from 'express';
import { fileCache } from '../utils/cache.js';

export default function configRoutes(configPath) {
  const router = express.Router();

  router.get('/', async (req, res, next) => {
    try {
      const config = await fileCache.readYaml(configPath);
      if (config !== null) {
        res.json(config);
      } else {
        res.status(404).json({ error: 'Config not found or could not be parsed' });
      }
    } catch (err) {
      next(err);
    }
  });

  router.get('/model', async (req, res, next) => {
    try {
      const config = await fileCache.readYaml(configPath);
      if (config !== null) {
        res.json({
          bdh: config.model?.bdh,
          transformer: config.model?.transformer
        });
      } else {
        res.status(404).json({ error: 'Config not found or could not be parsed' });
      }
    } catch (err) {
      next(err);
    }
  });

  router.get('/instrumentation', async (req, res, next) => {
    try {
      const config = await fileCache.readYaml(configPath);
      if (config !== null) {
        res.json(config.instrumentation || {});
      } else {
        res.status(404).json({ error: 'Config not found or could not be parsed' });
      }
    } catch (err) {
      next(err);
    }
  });

  return router;
}
