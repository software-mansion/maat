# Checkouts

> [!NOTE]
> Check out [Running Ma'at locally](./local.md) before continuing.

The `./maat checkout` command allows you to recreate the environment for a specific test.
This is particularly useful for debugging failing tests.

Consult `./maat checkout --help` for command syntax and available options.

#### Example

```shell
./maat checkout -w release --scarb 2.11.4 --foundry 0.43.0 OpenZeppelin/cairo-contracts
```

## What Happens During Checkout

When you run the `checkout` command:

1. Ma'at identifies the test in the specified workspace.
2. It runs all steps marked for checkout in a Docker container.
3. The contents of the workbench are copied to a directory under `checkouts/`.
4. The appropriate Scarb and Starknet Foundry versions are set in the checkout directory.

## Working with Checkouts

After running the checkout command, you will find the project files in
the `checkouts/TEST_NAME` directory. You can:

1. explore the project structure,
2. modify files to test changes,
3. run Scarb commands directly in the checkout directory,
4. debug issues that occurred during the experiment.

This provides a convenient way to interact with the exact environment that Ma'at uses for testing,
making it easier to reproduce and fix issues.
