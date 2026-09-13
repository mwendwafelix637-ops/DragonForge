export function createRateLimiter({
  windowMs = 10 * 1000,
  maxRequests = 150,
  cleanupIntervalMs = 60 * 1000
} = {}) {
  const requestRecords = new Map();

  const cleanupTimer = setInterval(() => {
    const now = Date.now();
    for (const [ip, timestamps] of requestRecords.entries()) {
      const active = timestamps.filter(t => now - t < windowMs);
      if (active.length === 0) {
        requestRecords.delete(ip);
      } else {
        requestRecords.set(ip, active);
      }
    }
  }, cleanupIntervalMs);

  if (cleanupTimer.unref) {
    cleanupTimer.unref();
  }

  return function rateLimiter(req, res, next) {
    const ip = req.ip || req.headers['x-forwarded-for'] || req.socket.remoteAddress || 'unknown';
    const now = Date.now();

    const timestamps = requestRecords.get(ip) || [];
    const recent = timestamps.filter(t => now - t < windowMs);

    if (recent.length >= maxRequests) {
      const oldest = recent[0];
      const retryAfterSeconds = Math.ceil((windowMs - (now - oldest)) / 1000);
      
      res.setHeader('Retry-After', retryAfterSeconds);
      res.setHeader('X-RateLimit-Limit', maxRequests);
      res.setHeader('X-RateLimit-Remaining', 0);
      res.setHeader('X-RateLimit-Reset', Math.ceil((oldest + windowMs) / 1000));

      return res.status(429).json({
        error: 'Too Many Requests',
        message: `Rate limit exceeded (${maxRequests} requests per ${windowMs / 1000}s). Please slow down.`,
        retryAfter: retryAfterSeconds
      });
    }

    recent.push(now);
    requestRecords.set(ip, recent);

    res.setHeader('X-RateLimit-Limit', maxRequests);
    res.setHeader('X-RateLimit-Remaining', Math.max(0, maxRequests - recent.length));

    next();
  };
}

export default createRateLimiter;
