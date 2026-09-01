# Local face-position model

`face_detection_yunet_2023mar.onnx` is the OpenCV Zoo YuNet face detector.

- Source: https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
- Upstream model licence: MIT; see [`LICENSE_YUNET`](LICENSE_YUNET).
- Size: 232,589 bytes
- SHA-256: `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`

The model runs locally through the already-installed OpenCV package. It
produces face boxes and detector scores only. It performs no identity
recognition, makes no runtime network request, and does not save camera pixels.
