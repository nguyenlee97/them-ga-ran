export function notFound(req, res, next) {
  res.status(404).json({ error: "not_found", path: req.originalUrl });
}

// Central error handler — routes throw {status, code, detail} or plain Error.
export function errorHandler(err, req, res, next) {
  const status = err.status || 500;
  const body = {
    error: err.code || (status >= 500 ? "server_error" : "bad_request"),
    detail: err.detail || err.message,
  };
  if (status >= 500) console.error("[error]", err);
  res.status(status).json(body);
}

// Wrap async route handlers so thrown errors reach errorHandler.
export const asyncH = (fn) => (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next);

// Helper to throw a typed HTTP error.
export function httpError(status, code, detail) {
  const e = new Error(detail || code);
  e.status = status;
  e.code = code;
  e.detail = detail;
  return e;
}
