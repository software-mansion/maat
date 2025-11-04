#!/usr/bin/env python3
"""
Generate mock test reports with different test runner combinations
to demonstrate the test runner badge functionality.

This script creates two mock reports that showcase:
1. Different test runners (cairo-test, snforge, mixed)
2. Projects with consistent test runners across reports
3. Projects with different test runners across reports (showing "mixed" badge)
4. Projects without detected test runner

Usage:
    python3 generate_mock_report.py

Output:
    - reports/mock-report-1.json
    - reports/mock-report-2.json

To view the badges in the UI:
    1. Run: ./maat export-web-assets --view-model frontend/src/vm.json --assets frontend/public reports/mock-report-*.json
    2. Run: npm --prefix frontend run dev
    3. Navigate to http://localhost:5173
    4. Select both mock-report-1 and mock-report-2
    5. Expand the Test Timings section
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Mock report data with various test runner scenarios
mock_report = {
    "workspace": "mock",
    "scarb": "2.13.1",
    "foundry": "0.51.1",
    "maat_commit": "mock123",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "total_execution_time": "PT5M30S",
    "tests": [
        {
            "name": "project-cairo-test",
            "rev": "abc123",
            "steps": [
                {
                    "name": "test",
                    "run": "scarb test --workspace",
                    "exit_code": 0,
                    "execution_time": "PT30S",
                }
            ],
            "analyses": {
                "test_runner": "cairo-test",
                "tests_summary": {
                    "passed": 10,
                    "failed": 0,
                    "skipped": 0,
                    "ignored": 0
                },
                "labels": ["test-pass(cairo-test passed)"]
            }
        },
        {
            "name": "project-snforge",
            "rev": "def456",
            "steps": [
                {
                    "name": "test",
                    "run": "scarb test --workspace",
                    "exit_code": 0,
                    "execution_time": "PT45S",
                }
            ],
            "analyses": {
                "test_runner": "snforge",
                "tests_summary": {
                    "passed": 25,
                    "failed": 0,
                    "skipped": 0,
                    "ignored": 0
                },
                "labels": ["test-pass(snforge passed)"]
            }
        },
        {
            "name": "project-no-runner-detected",
            "rev": "ghi789",
            "steps": [
                {
                    "name": "test",
                    "run": "scarb test --workspace",
                    "exit_code": 0,
                    "execution_time": "PT20S",
                }
            ],
            "analyses": {
                "test_runner": None,
                "tests_summary": {
                    "passed": 5,
                    "failed": 0,
                    "skipped": 0,
                    "ignored": 0
                },
                "labels": ["test-pass"]
            }
        },
        {
            "name": "project-cairo-test-slow",
            "rev": "jkl012",
            "steps": [
                {
                    "name": "test",
                    "run": "scarb test --workspace",
                    "exit_code": 0,
                    "execution_time": "PT2M15S",
                }
            ],
            "analyses": {
                "test_runner": "cairo-test",
                "tests_summary": {
                    "passed": 100,
                    "failed": 0,
                    "skipped": 0,
                    "ignored": 0
                },
                "labels": ["test-pass"]
            }
        },
        {
            "name": "project-snforge-with-failures",
            "rev": "mno345",
            "steps": [
                {
                    "name": "test",
                    "run": "scarb test --workspace",
                    "exit_code": 1,
                    "execution_time": "PT1M10S",
                }
            ],
            "analyses": {
                "test_runner": "snforge",
                "tests_summary": {
                    "passed": 15,
                    "failed": 3,
                    "skipped": 0,
                    "ignored": 0
                },
                "labels": ["test-fail(snforge 3 failed)"]
            }
        }
    ]
}

# Create a second report with different test runners for same projects
# to demonstrate the "mixed" badge
mock_report_2 = {
    "workspace": "mock",
    "scarb": "2.13.2",
    "foundry": "0.51.2",
    "maat_commit": "mock456",
    "created_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    "total_execution_time": "PT6M00S",
    "tests": [
        {
            "name": "project-cairo-test",
            "rev": "abc124",
            "steps": [
                {
                    "name": "test",
                    "run": "scarb test --workspace",
                    "exit_code": 0,
                    "execution_time": "PT35S",
                }
            ],
            "analyses": {
                "test_runner": "cairo-test",  # Same runner - should show "cairo-test" badge
                "tests_summary": {
                    "passed": 12,
                    "failed": 0,
                    "skipped": 0,
                    "ignored": 0
                },
                "labels": ["test-pass"]
            }
        },
        {
            "name": "project-snforge",
            "rev": "def457",
            "steps": [
                {
                    "name": "test",
                    "run": "scarb test --workspace",
                    "exit_code": 0,
                    "execution_time": "PT40S",
                }
            ],
            "analyses": {
                "test_runner": "cairo-test",  # Different runner - should show "mixed" badge
                "tests_summary": {
                    "passed": 20,
                    "failed": 0,
                    "skipped": 0,
                    "ignored": 0
                },
                "labels": ["test-pass"]
            }
        },
        {
            "name": "project-no-runner-detected",
            "rev": "ghi790",
            "steps": [
                {
                    "name": "test",
                    "run": "scarb test --workspace",
                    "exit_code": 0,
                    "execution_time": "PT25S",
                }
            ],
            "analyses": {
                "test_runner": "snforge",  # Different from None - should show "mixed" badge
                "tests_summary": {
                    "passed": 8,
                    "failed": 0,
                    "skipped": 0,
                    "ignored": 0
                },
                "labels": ["test-pass"]
            }
        },
        {
            "name": "project-cairo-test-slow",
            "rev": "jkl013",
            "steps": [
                {
                    "name": "test",
                    "run": "scarb test --workspace",
                    "exit_code": 0,
                    "execution_time": "PT2M30S",
                }
            ],
            "analyses": {
                "test_runner": "cairo-test",  # Same runner
                "tests_summary": {
                    "passed": 105,
                    "failed": 0,
                    "skipped": 0,
                    "ignored": 0
                },
                "labels": ["test-pass"]
            }
        },
        {
            "name": "project-snforge-with-failures",
            "rev": "mno346",
            "steps": [
                {
                    "name": "test",
                    "run": "scarb test --workspace",
                    "exit_code": 0,
                    "execution_time": "PT50S",
                }
            ],
            "analyses": {
                "test_runner": "snforge",  # Same runner
                "tests_summary": {
                    "passed": 18,
                    "failed": 0,
                    "skipped": 0,
                    "ignored": 0
                },
                "labels": ["test-pass"]
            }
        }
    ]
}

def main():
    reports_dir = Path(__file__).parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    
    # Write mock reports
    with open(reports_dir / "mock-report-1.json", "w") as f:
        json.dump(mock_report, f, indent=2)
    
    with open(reports_dir / "mock-report-2.json", "w") as f:
        json.dump(mock_report_2, f, indent=2)
    
    print("✅ Generated mock reports:")
    print(f"   - {reports_dir / 'mock-report-1.json'}")
    print(f"   - {reports_dir / 'mock-report-2.json'}")
    print()
    print("Expected badge behavior when comparing these reports:")
    print("   - project-cairo-test: 'cairo-test' badge (same runner in both)")
    print("   - project-snforge: 'mixed' badge (snforge vs cairo-test)")
    print("   - project-no-runner-detected: 'mixed' badge (None vs snforge)")
    print("   - project-cairo-test-slow: 'cairo-test' badge (same runner in both)")
    print("   - project-snforge-with-failures: 'snforge' badge (same runner in both)")

if __name__ == "__main__":
    main()
