# Ma'at Project Guidelines

## Overview

Ma'at tests compatibility and detects regressions when making changes to the Cairo toolchain by
running experiments on Cairo ecosystem projects using Docker containers.

## Key Structure

- `src/maat/`: Main package with CLI, models, and core functionality
    - `model.py`: Core data models
    - `workflow.py`: Predefined workflows for operations
    - `ecosystem/`: Cairo ecosystem project management
    - `report/`: Report generation, metrics, and analysis
    - `runner/`: Experiment execution engines
    - `agent/`: Docker container configuration
    - `utils/`: Helper utilities
    - `web/`: Web interface components
    - `workspace.py`: Workspace management
- `reports/`: Experiment reports storage
- `workspaces/`: Cairo ecosystem project definitions
- `checkouts/`: Local copies of ecosystem projects

## Guidelines

1. No automated tests exist; verify CLI commands work as expected
2. Avoid `./maat run-local` (very slow); use `./maat reanalyse --all` for analysis work
3. Use Pydantic V2 models, PEP 8 style, type hints, and proper docstrings
4. Maintain Docker compatibility and consistent JSON report formats (with sorted lists)
