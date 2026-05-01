# Contributing to AI Refactoring Pipeline

Thank you for contributing! We follow high standards to ensure the reliability of our AI-powered transformation tools.

## Getting Started
1. Fork the repository.
2. Install backend dependencies: `pip install -r requirements.txt`.
3. Install frontend dependencies: `cd frontend && npm install`.
4. Configure your `.env` with a `GEMINI_API_KEY`.

## Development Guidelines
- **Python**: Follow PEP8 and use type hints.
- **React**: Adhere to the Neumorphic design system in `frontend/src/index.css`.
- **Logs**: Always update `LOG.md` with your changes.

## Testing
Before submitting a PR, ensure your code passes the Stage 4 Validator:
`python backend/pipeline/validator/run_validation.py --path <target_file>`

## Pull Request Process
- Ensure all CI gates pass.
- Provide a clear description of your changes.
- Submit PRs against the `main` branch.
