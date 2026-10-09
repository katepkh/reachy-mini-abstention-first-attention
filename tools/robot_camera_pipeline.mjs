// Pure helpers plus a single-flight, bounded worker client. No robot commands.
export function remainingFrameDelay(started, finished, periodMs) {
  return Math.max(0, periodMs - (finished - started));
}

export function numericTimingHeader(headers, name) {
  const raw = headers.get(name);
  if (raw === null || raw.trim() === "") return null;
  const value = Number(raw);
  return Number.isFinite(value) && value >= 0 ? value : null;
}

// All endpoints below are on the MAIN browser clock; only inferenceMs is a
// duration measured by the worker. No worker timestamp is subtracted from it.
export function framePipelineTiming({ started, received, decoded, drawn,
  workerStarted, completed, inferenceMs, previousLoopFinished, previousPublished }) {
  const workerRoundtripMs = completed - workerStarted;
  return { drawMs: drawn - decoded, workerRoundtripMs,
    workerOverheadMs: Math.max(0, workerRoundtripMs - inferenceMs),
    pipelineMs: completed - started,
    loopGapMs: previousLoopFinished === null ? null : started - previousLoopFinished,
    publishIntervalMs: previousPublished === null ? null : completed - previousPublished };
}

export function summarizeFace(faces, previousLip, inferenceMs, observedMs) {
  const empty = { count: Math.min(faces.length, 2), centerX: null, centerY: null,
    cameraRight: null, robotHeading: null, scale: 0, lip: 0, lipMotion: 0,
    inferenceMs, observedMs, bounds: null, dots: [] };
  if (faces.length !== 1) return empty;
  const points = faces[0];
  const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const centerX = (points[33].x + points[263].x) / 2;
  const centerY = (points[33].y + points[263].y) / 2;
  const scale = distance(points[33], points[263]);
  const lip = scale > 0 ? distance(points[13], points[14]) / scale : 0;
  const cameraRight = 180 * Math.atan(
    (centerX - 1905.876059826701 / 3840) / (2001.8076426486707 / 3840),
  ) / Math.PI;
  return { ...empty, count: 1, centerX, centerY, cameraRight,
    robotHeading: -cameraRight, scale, lip,
    lipMotion: previousLip === null ? 0 : Math.abs(lip - previousLip),
    bounds: { left: Math.min(...points.map(p => p.x)),
      right: Math.max(...points.map(p => p.x)),
      top: Math.min(...points.map(p => p.y)), bottom: Math.max(...points.map(p => p.y)) },
    dots: [33, 263, 13, 14].map(i => ({ x: points[i].x, y: points[i].y })) };
}

export class LandmarkWorkerClient {
  constructor(worker) {
    this.worker = worker;
    this.pending = null;
    this.serial = 0;
    this.closed = false;
    worker.onmessage = ({ data }) => {
      if (!this.pending || this.pending.id !== data.id) return;
      if (data.error) return this.close(new Error(data.error));
      const pending = this.pending;
      this.pending = null;
      clearTimeout(pending.timer);
      pending.resolve(data);
    };
    worker.onerror = () => this.close(new Error("LANDMARK_WORKER_FAILED"));
    worker.onmessageerror = () => this.close(new Error("LANDMARK_WORKER_MESSAGE_FAILED"));
  }
  request(message, transfer = [], timeoutMs = 2000) {
    if (this.closed || this.pending) {
      for (const item of transfer) item.close?.();
      return Promise.reject(new Error(this.closed ? "WORKER_CLOSED" : "WORKER_BUSY"));
    }
    return new Promise((resolve, reject) => {
      const id = ++this.serial;
      this.pending = { id, resolve, reject,
        timer: setTimeout(() => this.close(new Error("LANDMARK_WORKER_TIMEOUT")), timeoutMs) };
      try { this.worker.postMessage({ ...message, id }, transfer); }
      catch (error) {
        for (const item of transfer) item.close?.();
        this.close(error);
      }
    });
  }
  close(error = new Error("WORKER_CLOSED")) {
    this.closed = true;
    this.worker.terminate();
    if (this.pending) {
      clearTimeout(this.pending.timer);
      this.pending.reject(error);
      this.pending = null;
    }
  }
}

// Five seconds is a preflight warm-up, not a replacement for offline v1 checks.
export class ProcessingWindow {
  constructor(windowMs = 5000) { this.windowMs = windowMs; this.clear(); }
  clear() { this.rows = []; this.started = null; }
  add(now, frame, face) {
    if (this.started === null) this.started = now;
    this.rows.push({ now, sequence: frame?.sequence ?? 0,
      count: face?.count ?? 0, inference: face?.inferenceMs ?? null });
    while (this.rows.length && this.rows[0].now < now - this.windowMs) this.rows.shift();
  }
  assess(now, checks) {
    const rows = this.rows;
    const span = rows.length > 1 ? now - rows[0].now : 0;
    const median = values => {
      values.sort((a, b) => a - b);
      const n = values.length;
      return n ? (values[(n - 1) >> 1] + values[n >> 1]) / 2 : Infinity;
    };
    const fps = span > 0 ? new Set(rows.filter(r => r.sequence > 0).map(r => r.sequence)).size * 1000 / span : 0;
    const singleFraction = rows.filter(r => r.count === 1).length / Math.max(rows.length, 1);
    const inference = median(rows.map(r => r.inference).filter(Number.isFinite));
    const duplicates = rows.filter((r, i) => i > 0 && r.sequence === rows[i - 1].sequence).length / Math.max(rows.length, 1);
    const warmed = this.started !== null && now - this.started >= this.windowMs && span >= this.windowMs - 200;
    const failures = [];
    if (!warmed) failures.push("wait for five seconds of processing checks");
    if (fps < checks.minimum_unique_analyzed_fps) failures.push(`processing ${fps.toFixed(1)} fps; need ${checks.minimum_unique_analyzed_fps}`);
    if (inference > checks.maximum_median_landmark_inference_ms) failures.push("landmark processing exceeds 60 ms");
    if (duplicates > checks.maximum_duplicate_row_fraction) failures.push("too many repeated frame observations");
    if (singleFraction < checks.minimum_single_face_fraction) failures.push("face detection is intermittent; keep your whole face visible");
    return { fps, singleFraction, inference, duplicates, failures };
  }
}
