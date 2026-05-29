# Model artifacts

Binary model weights are not stored in git. Use external artifact storage or
`D:/LIMA-external/` for local `.pkl` / `.pt` files.

`router_ml_model.pkl` was removed from tracking because no runtime import path
references it. Restore from git history if a future router experiment needs it.
