import * as childProcess from "node:child_process";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import ms from "ms";
import {
    createMessageConnection,
    type MessageConnection,
    NotificationType,
    RequestType0,
    StreamMessageReader,
    StreamMessageWriter,
} from "vscode-jsonrpc/node";
import {
    type ClientCapabilities,
    ExitNotification,
    InitializedNotification,
    type InitializeParams,
    InitializeRequest,
    RegistrationRequest,
    ShutdownRequest,
    type WorkspaceFolder,
} from "vscode-languageserver-protocol";

const ViewAnalyzedCrates = new RequestType0<{}, {}>("cairo/viewAnalyzedCrates");

interface ServerStatusParams {
    event: "AnalysisStarted" | "AnalysisFinished";
    idle: boolean;
}

const ServerStatus = new NotificationType<ServerStatusParams>("cairo/serverStatus");

main().catch((err) => {
    console.error(err);
    process.exit(1);
});

async function main(): Promise<void> {
    const exitCode = await withCairoLS(async (connection) => {
        const rootUri = `file://${process.env.PWD}`;
        await initialize(connection, rootUri, baseCapabilities());

        try {
            const analysisAwaiter = startAnalysisAwaiter(connection);

            // Open any lib.cairo file we can find to ensure all packages in the project will be opened and analysed.
            let libCairoFiles = await findAllLibCairoFiles();
            for (const libCairoFile of libCairoFiles) {
                let fileUrl = path2url(libCairoFile);
                console.log(`Opening ${fileUrl}`);
                await openFile(fileUrl, connection);
            }

            // Wait for project analysis to finish.
            // Assume some healthy timeout in case LS hangs.
            await Promise.race([analysisAwaiter, timeout(ms("5 minutes"), "analysis")]);

            await viewAnalysedCrates(connection);
        } finally {
            await terminate(connection);
        }
    });

    process.exit(exitCode);
}

/**
 * Finds any `lib.cairo` files in PWD recursively.
 */
async function findAllLibCairoFiles(): Promise<string[]> {
    async function visit(dir: string): Promise<string[]> {
        const results: string[] = [];
        const entries = await fs.readdir(dir, { withFileTypes: true });

        for (const entry of entries) {
            const fullPath = path.join(dir, entry.name);
            if (entry.isDirectory()) {
                results.push(...(await visit(fullPath)));
            } else if (entry.name === "lib.cairo") {
                results.push(fullPath);
            }
        }

        return results;
    }

    return visit(".");
}

/**
 * Opens a file in the LS.
 */
async function openFile(url: string, connection: MessageConnection): Promise<void> {
    let filePath = url2path(url);
    await connection.sendNotification("textDocument/didOpen", {
        textDocument: {
            uri: url,
            languageId: path.extname(filePath).slice(1),
            version: 0,
            text: await fs.readFile(filePath, "utf-8"),
        },
    });
}

/**
 * Calls `cairo/viewAnalyzedCrates` and console-logs the result.
 */
async function viewAnalysedCrates(connection: MessageConnection) {
    const SEPARATOR = "==============================";
    const result = await connection.sendRequest(ViewAnalyzedCrates);
    console.log(SEPARATOR);
    console.log(result);
    console.log(SEPARATOR);
}

async function withCairoLS(
    callback: (connection: MessageConnection) => Promise<void>,
): Promise<number> {
    const exitPromise = Promise.withResolvers<number>();

    const serverProcess = childProcess.spawn("scarb", ["cairo-language-server"], {
        stdio: ["pipe", "pipe", "inherit"],
    });

    serverProcess.on("close", (code) => {
        console.log(`CairoLS process exited with code: ${code}`);
        exitPromise.resolve(code || 0);
    });

    try {
        const connection = createMessageConnection(
            new StreamMessageReader(serverProcess.stdout),
            new StreamMessageWriter(serverProcess.stdin),
        );

        try {
            connection.listen();
            await callback(connection);
        } finally {
            connection.dispose();
        }
    } finally {
        serverProcess.kill();
    }

    return await exitPromise.promise;
}

/**
 * Produces minimal client capabilities provided by the mock language client.
 *
 * Tests will most often need to extend these with test-specific additions.
 */
function baseCapabilities(): ClientCapabilities {
    return {
        workspace: {
            configuration: false,
        },
        window: {
            workDoneProgress: false,
        },
    };
}

/**
 * Performs the `initialize`/`initialized` handshake with the server.
 * @param connection An active MessageConnection to the server
 * @param rootUri The workspace root URI (string)
 * @param capabilities Client capabilities
 */
async function initialize(
    connection: MessageConnection,
    rootUri: string,
    capabilities: ClientCapabilities,
): Promise<void> {
    const workspaceFolders: WorkspaceFolder[] = [
        {
            uri: rootUri,
            name: url2path(rootUri).split("/").filter(Boolean).pop() || "maat",
        },
    ];

    // noinspection JSDeprecatedSymbols
    const params: InitializeParams = {
        processId: process.pid,
        capabilities,
        rootUri: null,
        workspaceFolders,
        clientInfo: {
            name: "maat-test-ls",
            version: "1.0.0",
        },
        locale: "en",
    };

    // Swallow any `client/registerCapability` requests.
    connection.onRequest(RegistrationRequest.method, () => {});

    // Send `initialize` request.
    await connection.sendRequest(InitializeRequest.method, params);

    // Send `initialized` notification.
    await connection.sendNotification(InitializedNotification.method, {});
}

/**
 * Performs the `shutdown`/`exit` handshake with the server.
 * @param connection An active MessageConnection to the server
 */
async function terminate(connection: MessageConnection): Promise<void> {
    // Send `shutdown` request
    await connection.sendRequest(ShutdownRequest.method);

    // Send `exit` notification
    await connection.sendNotification(ExitNotification.method);
}

/**
 * Starts listening for `cairo/serverStatus` notifications
 * and returns a promise that resolves when CairoLS becomes truly idle.
 */
function startAnalysisAwaiter(connection: MessageConnection): Promise<void> {
    const defer = Promise.withResolvers<void>();
    let idleTimer: NodeJS.Timeout | null = null;

    connection.onNotification(ServerStatus, ({ idle }) => {
        // CairoLS notifies about its idle state:
        // - During analysis: idle = false
        // - After analysis: idle = true
        //
        // LS tends to spuriously go from busy to idle to busy state again in,
        // so we debounce the idle = true state for some small chunk of time
        // before considering the analysis truly complete.

        if (idleTimer) {
            clearTimeout(idleTimer);
            idleTimer = null;
        }

        if (idle) {
            idleTimer = setTimeout(() => {
                console.log("Analysis completed, server is idle.");
                defer.resolve();
            }, ms("3 seconds"));
        }
    });
    return defer.promise;
}

/**
 * Returns a Promise that rejects after a specified timeout period with an error indicating the operation timed out.
 */
function timeout(ms: number, operation: string = "operation"): Promise<void> {
    return new Promise((_, reject) =>
        setTimeout(() => reject(new Error(`${operation} timed out`)), ms),
    );
}

/**
 * Converts a file URL into a file system path.
 */
function url2path(fileUrl: string): string {
    return new URL(fileUrl).pathname;
}

/**
 * Converts a file system path to a file URL.
 *
 * Path is resolved before constructing the URL.
 */
function path2url(filePath: string): string {
    return new URL(path.resolve(filePath), "file://").href;
}
