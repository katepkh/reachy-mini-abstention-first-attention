// Classic worker: the pinned WASM loader uses importScripts. All assets local.
let model = null;
let previousLip = null;
let summarizeFace = null;
let busy = false;

self.onmessage = async ({ data }) => {
  const { id, type } = data;
  if (busy) {
    data.bitmap?.close();
    self.postMessage({ id, error: "WORKER_BUSY" });
    return;
  }
  busy = true;
  try {
    if (type === "initialize") {
      const { FaceLandmarker, FilesetResolver } = await import("../models/avsync_v2/runtime/vision_bundle.mjs");
      ({ summarizeFace } = await import("./robot_camera_pipeline.mjs"));
      const vision = await FilesetResolver.forVisionTasks("../models/avsync_v2/runtime/wasm");
      model?.close();
      model = null;
      previousLip = null;
      // GPU preference and any CPU fallback are declared, never changed mid-capture.
      let delegate = "GPU";
      let fallback = false;
      const options = delegate => ({
        baseOptions: { modelAssetPath: "../models/avsync_v2/face_landmarker.task", delegate },
        canvas: new OffscreenCanvas(1, 1), runningMode: "VIDEO", numFaces: 2,
        minFaceDetectionConfidence: 0.5, minFacePresenceConfidence: 0.5,
        minTrackingConfidence: 0.5,
      });
      const initializeAndWarm = async delegate => {
        model = await FaceLandmarker.createFromOptions(vision, options(delegate));
        // Compile lazy GPU/CPU kernels on a synthetic blank, not the first
        // live frame. Initialization has its own longer, bounded deadline.
        const blank = new OffscreenCanvas(640, 360);
        const context = blank.getContext("2d");
        context.fillStyle = "#333";
        context.fillRect(0, 0, blank.width, blank.height);
        model.detectForVideo(blank, 0);
        blank.width = 0;
        blank.height = 0;
      };
      try { await initializeAndWarm(delegate); }
      catch {
        model?.close();
        model = null;
        delegate = "CPU";
        fallback = true;
        await initializeAndWarm(delegate);
      }
      self.postMessage({ id, delegate, fallback });
    } else if (type === "analyze") {
      if (!model) throw new Error("LANDMARK_MODEL_NOT_READY");
      const started = performance.now();
      const result = model.detectForVideo(data.bitmap, data.observedMs);
      const inferenceMs = performance.now() - started;
      const face = summarizeFace(result.faceLandmarks || [], previousLip, inferenceMs, data.observedMs);
      previousLip = face.count === 1 ? face.lip : null;
      self.postMessage({ id, face });
    } else throw new Error("UNKNOWN_WORKER_REQUEST");
  } catch (error) {
    if (type === "initialize") console.error("Pinned landmark initialization failed:", error);
    // Fixed codes only; no raw input or runtime dump in retained diagnostics.
    self.postMessage({ id, error: type === "initialize" ? "LANDMARK_INITIALIZATION_FAILED" : "LANDMARK_INFERENCE_FAILED" });
  } finally {
    data.bitmap?.close();
    busy = false;
  }
};
