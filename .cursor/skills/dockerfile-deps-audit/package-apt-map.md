# Pip package → Dockerfile apt hints

Debian **`python:3.12-slim`** (Bookworm). Verify when upgrading base image.

## Usually pip-only (no extra apt)

- fastapi, uvicorn, pydantic, httpx, sqlalchemy
- openai, anthropic (HTTP clients)
- python-jose, passlib, bcrypt (wheels on slim)
- python-multipart

## Common: pip + apt

| Pip / feature | Apt packages (typical) | Notes |
|---------------|------------------------|-------|
| `onnxruntime` | `libgomp1` | OpenMP |
| `rapidocr-onnxruntime` | `libgomp1`, `libglib2.0-0`, `libgl1` | Pulls opencv-python + onnxruntime |
| `opencv-python` / headless | `libglib2.0-0`, `libgl1` | Prefer headless in containers if you control deps |
| `Pillow` + large images | often none on slim | If decode fails, add `libjpeg62-turbo`, `zlib1g` |
| `torch` / `sentence-transformers` | `libgomp1` | Image GB-scale; optional feature |
| `psycopg2` (non-binary) | `libpq-dev`, `gcc` | Use `psycopg2-binary` or build stage |
| `lxml` | `libxml2`, `libxslt1.1` | If wheel missing for arch |
| `weasyprint` | many fonts/libs | Avoid unless required |
| Health probe | `curl` | Already in this repo |

## Build-time only (multi-stage)

If a package needs `gcc` / `python3-dev` to compile, use a **builder stage** and copy wheels into slim runtime — do not leave `gcc` in the final image.

## Travel-Agent current stack (reference)

**requirements.txt (OCR path):** `rapidocr-onnxruntime`, `Pillow`, `numpy`

**Dockerfile apt:** `curl`, `libgomp1`, `libglib2.0-0`, `libgl1`

When adding a new row to this table, update `Dockerfile` comments to match.
