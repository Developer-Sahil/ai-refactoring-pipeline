# Prompt Builder - Project Log

## 2026-03-27
- **Reorganised Project Structure**: Migrated from a single-folder layout to a two-folder structure (`prompt_builder/` for programs and `output/` for results) to align with the `cast` project.
- **Improved Code Organization**: Grouped all Python logic (`build_prompts.py`, `few_shot_loader.py`, `prompt_templates.py`) and internal resource data (`few_shot_examples.json`) into the `prompt_builder/` subdirectory.
- **Created Documentation**:
    - `LOGIC_MAP.md`: Detailed the end-to-end prompt rendering pipeline.
    - `AUDIT.md`: Conducted an architectural and code-quality audit.
    - `README.md`: Updated to reflect the new directory layout.
- **Relocated Output**: Relocated `prompts.json` into the `output/` directory and updated the default script arguments to match.
- **Pipeline Execution**: Successfully ran Stage 2 using fresh output from Stage 1 (`chunks_output.json`) generated from `order_service.py`. Resulting prompts are stored in `output/prompts.json`.
- **Infrastructure Cleanup**: Removed temporary input file (`chunks_output.json`) from root after processing.
