# Security Policy — AI Refactoring Pipeline

## Vulnerability Reporting
Please report security vulnerabilities privately to the maintainers. Do not open public issues for security bugs.

## Security Architecture
- **Edge Protection**: Cloudflare WAF and DDoS protection in front of all API traffic.
- **Authentication**: JWT-based session management via **Firebase Auth** (Google Identity Platform). Tokens are validated on every protected API request.
- **Secrets**: API keys (`GEMINI_API_KEY`, Firebase service account) must be stored as environment variables or secrets — never committed to the repository.

## Upload Security
- Uploaded `.py` files and `.zip` archives are stored in isolated per-job directories (`backend/input/uploads/{job_id}/`) and are never executed directly — only passed to the refactoring pipeline.
- ZIP extraction uses Python's `zipfile` module with filename filtering to reject path-traversal entries (entries containing `..` or absolute paths).
- File type is validated server-side regardless of the browser's `accept` attribute.

## Data Processing
Source code is processed via the Gemini API. Ensure that no sensitive credentials or PII are present in the files being refactored. The pipeline performs basic path sanitization to prevent directory traversal.
