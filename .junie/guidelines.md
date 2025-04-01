# Project Guidelines for Junie

## Project Overview

Ma'at is a tool for running experimental software builds across the Cairo language ecosystem, similar to Crater in the
Rust ecosystem. It helps test compatibility and detect regressions when making changes to the Cairo toolchain.

### Key Features

- Runs experiments on Cairo ecosystem projects using Docker containers.
- Tests projects with specific versions of Scarb and Starknet Foundry.
- Generates reports on build, lint, and test results.
- Compares reports to detect regressions.

## Project Structure

The project is organised as follows:

- `src/maat/`: Main Python package.
    - `__init__.py`: CLI implementation using Click.
    - `model.py`: Data models.
    - `agent/`: Dockerfile and content provisioned to sandbox containers which run tests.
    - `ecosystem/`: Code for pulling projects from the Cairo ecosystem.
    - `report/`: Report generation and analysis.
    - `runner/`: Test execution code.
    - `workflows/`: Predefined workflows for build, lint, and test operations.
- `reports/`: Directory for storing experiment reports.
- `workspaces/`: Workspace definitions.

## Testing Guidelines

When working with this project, Junie should:

1. Ensure that any changes maintain compatibility with the existing codebase.
2. Verify that the CLI commands still work as expected.
3. There are no automated tests in this codebase.
4. Running tests `./maat run-local` is VERY slow, avoid doing this unless absolutely necessary.
5. If work is related to analyses, run `./maat reanalyse --all` and check diffs in reports.

## Code Style Guidelines

The project follows these code style guidelines:

1. Use Pydantic V2 models for data structures.
2. Follow PEP 8 conventions for Python code.
3. Use type hints throughout the codebase.
4. Document classes and functions with docstrings.
5. Keep the code modular and maintainable.
6. Comments should use full sentences, ending with dots.
7. Use British English spelling.

## Additional Notes

### Codebase

- The project uses Docker for running experiments, so any changes should maintain compatibility with the Docker-based
  workflow.
- Reports are saved as JSON files and should maintain a consistent format for comparison.
    - Ensure lists are sorted by a stable key.
- The project is designed to be extensible, so new workflows and analysers can be added as needed.

### About Cairo ecosystem

- There are two distinct test runners used throughout the ecosystem: `snforge` (Starknet Foundry, more advanced) and
  `cairo-test` (Cairo Test, callable as `scarb cairo-test`, minimal but faster).
  By convention, projects alias one of these runners as `scarb test`.
  You can examine project's `Scarb.toml` to infer what framework is used.
  It might be possible that some projects attempt to use both runners at once,
  but they tend to conflict (causing compilation errors)—beware of this.

## How to write a new analysis

* Define analysis data structure in the `model.py` file.
* Define an analyser function that takes `TestReport` and `StepReport` parameters.
* Store analysis results in a `step.analyses` dictionary with a unique key.
* Create a `StepMeta` with a unique name and register your analyser function.
* Use `analysers=lambda: [your_analyzer_function]` in the `StepMeta` constructor.
* Ensure your analyser is properly registered in a workflow.
* Access analysis results in the report JSON under the `analyses` field.
* Multiple analysers can mutate the same analysis result.
  Analysers are executed in the order they're defined.
