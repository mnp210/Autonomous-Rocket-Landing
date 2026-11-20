# Stage 9.6 — Dependency and Licensing Audit Report

**Project:** Autonomous Rocket Landing using Deep Reinforcement Learning  
**Milestone:** Stage 9.6 — Final Release, Reproducibility Audit & GitHub Publication Preparation  
**Repository:** `D:\Projects\Autonomous-Rocket-Landing`  
**Date:** 2026-11-20  
**License:** Apache License 2.0  
**Audit Status:** **COMPLIANT — 100% PERMISSIVE & COMPATIBLE**  

---

## 1. Executive Summary

This audit verifies all direct and transitive runtime and development dependencies across the Python backend and JavaScript/TypeScript frontend. The repository is released under the **Apache License 2.0**. All external libraries, packages, and assets were evaluated for license compatibility, redistribution rights, and exact pinning.

---

## 2. Python Dependency Inventory & Licensing

Declared in [`requirements.txt`](file:///d:/Projects/Autonomous-Rocket-Landing/requirements.txt):

| Package | Version Constraint | Installed (.venv) | License | Apache-2.0 Compatibility |
| :--- | :--- | :--- | :--- | :---: |
| `gymnasium[box2d]` | `>=1.0.0` | `1.4.0` / `2.3.10` | MIT / zlib | **Compatible** |
| `stable-baselines3` | `>=2.4.0` | `2.9.2` | MIT | **Compatible** |
| `torch` | `>=2.2.0` | `2.10.0+cpu` | BSD-style | **Compatible** |
| `numpy` | `>=1.26.0` | `2.4.3` | BSD 3-Clause | **Compatible** |
| `scipy` | `>=1.11.0` | `1.17.1` | BSD 3-Clause | **Compatible** |
| `pandas` | `>=2.0.0` | `3.0.1` | BSD 3-Clause | **Compatible** |
| `matplotlib` | `>=3.8.0` | `3.10.8` | PSF-compatible | **Compatible** |
| `tensorboard` | `>=2.16.0` | `2.21.0` | Apache 2.0 | **Compatible** |
| `pyyaml` | `>=6.0` | `6.0.3` | MIT | **Compatible** |
| `fastapi` | `>=0.115.0` | `0.115.0` | MIT | **Compatible** |
| `uvicorn[standard]` | `>=0.30.0` | `0.41.0` | BSD 3-Clause | **Compatible** |
| `websockets` | `>=13.0` | `16.0` | BSD 3-Clause | **Compatible** |
| `pydantic` | `>=2.8.0` | `2.9.2` | MIT | **Compatible** |
| `structlog` | `>=24.0.0` | `26.1.0` | MIT / Apache 2.0 | **Compatible** |
| `psutil` | `>=5.9.0` | `7.2.2` | BSD 3-Clause | **Compatible** |
| `pytest` | `>=8.0.0` | `9.1.1` | MIT | **Compatible** |
| `pytest-asyncio` | `>=0.23.0` | `1.4.0` | Apache 2.0 | **Compatible** |

---

## 3. Frontend Dependency Inventory & Licensing

Declared in [`web/package.json`](file:///d:/Projects/Autonomous-Rocket-Landing/web/package.json) with exact lockfile [`web/package-lock.json`](file:///d:/Projects/Autonomous-Rocket-Landing/web/package-lock.json):

| Package | Declared Version | Lockfile Version | License | Apache-2.0 Compatibility |
| :--- | :--- | :--- | :--- | :---: |
| `react` | `^19.3.1` | `19.3.1` | MIT | **Compatible** |
| `react-dom` | `^19.3.1` | `19.3.1` | MIT | **Compatible** |
| `three` | `^0.187.0` | `0.187.0` | MIT | **Compatible** |
| `typescript` | `~7.0.2` | `7.0.2` | Apache 2.0 | **Compatible** |
| `vite` | `^8.3.6` | `8.3.6` | MIT | **Compatible** |
| `vitest` | `^5.1.1` | `5.1.1` | MIT | **Compatible** |
| `tailwindcss` | `^4.3.5` | `4.3.5` | MIT | **Compatible** |
| `jsdom` | `^31.0.1` | `31.0.1` | MIT | **Compatible** |

---

## 4. Models, Datasets & Asset Licensing

1. **Reinforcement Learning Checkpoints (`models/`):**
   - Authored entirely by this project through training Gymnasium LunarLander-v3.
   - Sized under 42 MB total; distributed under project's Apache 2.0 license.
2. **Procedural 3D Meshes (`web/src/three/boosterModel.ts`, `web/src/three/spaceportScene.ts`):**
   - 100% procedurally generated using Three.js buffer geometries (`CylinderGeometry`, `BoxGeometry`, `RingGeometry`).
   - Zero proprietary or commercial 3D model files (`.gltf`, `.fbx`, `.obj`).
3. **Audio / Media:**
   - Zero copyrighted audio or video tracks embedded.
   - Exhaust flames and particle effects use custom GLSL/WebGL fragment shaders.

---

## 5. Audit Conclusion

All software libraries, packages, procedural models, and datasets are strictly governed by permissive, open-source licenses (Apache 2.0, MIT, BSD 3-Clause) with zero GPL, commercial, or restrictive copyleft encumbrances.
