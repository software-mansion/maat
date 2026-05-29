import * as childProcess from "node:child_process";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import ms from "ms";
import {
    createMessageConnection,
    Disposable,
    MessageConnection,
    NotificationType,
    RequestType0,
    StreamMessageReader,
    StreamMessageWriter,
} from "vscode-jsonrpc/node";
import {
    ClientCapabilities,
    DiagnosticSeverity,
    DocumentUri,
    ExitNotification,
    InitializedNotification,
    InitializeParams,
    InitializeRequest,
    PublishDiagnosticsNotification,
    PublishDiagnosticsParams,
    RegistrationRequest,
    ShutdownRequest,
    WorkspaceFolder,
} from "vscode-languageserver-protocol";

const SEPARATOR = "\n==============================";

const ViewAnalyzedCrates = new RequestType0<{}, {}>("cairo/viewAnalyzedCrates");

interface ServerStatusParams {
    event: "AnalysisStarted" | "AnalysisFinished";
    idle: boolean;
}

const ServerStatus = new NotificationType<ServerStatusParams>("cairo/serverStatus");

withCairoLS(async (connection, pid) => {
    const rootUri = `file://${process.env.PWD}`;
    await initialize(connection, rootUri, baseCapabilities());

    try {
        // Install various probes.
        const { promise: analysisAwaiter, dispose: disposeAwaiter } = startAnalysisAwaiter(connection);
        const diagnosticsCollector = DiagnosticsCollector.start(connection);

        // Open any lib.cairo file we can find to ensure
        // all packages in the project will be opened and analysed.
        let libCairoFiles = await findAllEntryFiles();
        for (const libCairoFile of libCairoFiles) {
            let fileUrl = path2url(libCairoFile);
            console.log(`Opening ${fileUrl}`);
            await openFile(fileUrl, connection);
        }

        // Wait for project analysis to finish.
        // Assume some healthy timeout in case LS hangs.
        console.log(SEPARATOR);
        try {
            await Promise.race([analysisAwaiter, timeout(ms("5 minutes"), "analysis")]);
        } finally {
            disposeAwaiter();
        }
        const diags = diagnosticsCollector.stop();

        await checkMemoryGrowth(pid);

        let editTargets: string[];
        if (libCairoFiles.length > 0) {
            editTargets = [...libCairoFiles].sort().slice(0, 3);
        } else {
            const fallback = await findAnyCairoFile();
            if (fallback) {
                await openFile(path2url(fallback), connection);
                editTargets = [fallback];
            } else {
                editTargets = [];
            }
        }
        if (editTargets.length > 0) {
            await checkMemoryAfterEdit(pid, editTargets, connection);
        }

        await viewAnalysedCrates(connection);
        showDiagnostics(diags);
    } finally {
        await terminate(connection);
    }
}).catch((err) => {
    console.error(err);
    process.exitCode = 1;
});

/**
 * Finds any `lib.cairo` files in PWD recursively.
 */
async function findAllEntryFiles(): Promise<string[]> {
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
 * Finds the first `.cairo` file in PWD recursively.
 * Used as a fallback edit target when no lib.cairo exists.
 */
async function findAnyCairoFile(): Promise<string | null> {
    async function visit(dir: string): Promise<string | null> {
        const entries = await fs.readdir(dir, { withFileTypes: true });

        for (const entry of entries) {
            const fullPath = path.join(dir, entry.name);
            if (entry.isDirectory()) {
                const found = await visit(fullPath);
                if (found) return found;
            } else if (entry.name.endsWith(".cairo")) {
                return fullPath;
            }
        }

        return null;
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
    const result = await connection.sendRequest(ViewAnalyzedCrates);
    console.log(SEPARATOR);
    console.log(result);
}

async function withCairoLS(
    callback: (connection: MessageConnection, pid: number) => Promise<void>,
): Promise<void> {
    const exitPromise = Promise.withResolvers<void>();

    const serverProcess = childProcess.spawn("scarb", ["cairo-language-server"], {
        stdio: ["pipe", "pipe", "inherit"],
    });

    serverProcess.on("close", (code, signal) => {
        console.log(SEPARATOR);
        console.log(`CairoLS process exited with code: ${code ?? signal}`);
        if (code != null && code !== 0) {
            process.exitCode = code;
        }
        exitPromise.resolve();
    });

    try {
        const connection = createMessageConnection(
            new StreamMessageReader(serverProcess.stdout),
            new StreamMessageWriter(serverProcess.stdin),
        );

        try {
            connection.listen();
            await callback(connection, serverProcess.pid!);
        } finally {
            connection.dispose();
        }
    } finally {
        setTimeout(() => {
            if (!serverProcess.killed) {
                serverProcess.kill();
            }
        }, ms("3 seconds")).unref();
    }

    return await exitPromise.promise;
}

/**
 * Reads the resident set size of a process from /proc/<pid>/status (Linux only).
 * Returns null if the file is unavailable (non-Linux host or pid already gone).
 */
async function readProcessRssKB(pid: number): Promise<number | null> {
    try {
        const status = await fs.readFile(`/proc/${pid}/status`, "utf-8");
        const m = status.match(/VmRSS:\s+(\d+)\s+kB/);
        return m ? parseInt(m[1], 10) : null;
    } catch {
        return null;
    }
}

/**
 * Prepends a probe function to all entry files to trigger a non-trivial re-analysis,
 * then logs a memory snapshot so the analysis pipeline can detect post-edit memory growth.
 */
async function checkMemoryAfterEdit(
    pid: number,
    entryFiles: string[],
    connection: MessageConnection,
): Promise<void> {
    console.log(SEPARATOR);
    console.log(`Simulating edit: prepending probe function to ${entryFiles.length} file(s)`);

    for (const [i, entryFile] of entryFiles.entries()) {
        const content = await fs.readFile(entryFile, "utf-8");
        console.log(`Edit ${i + 1}/${entryFiles.length}: ${path2url(entryFile)}`);

        const { promise: editAwaiter, dispose: disposeEditAwaiter } = startAnalysisAwaiter(connection);
        await connection.sendNotification("textDocument/didChange", {
            textDocument: { uri: path2url(entryFile), version: 1 },
            contentChanges: [{ text: "fn __maat_ls_probe__() {}\n" + content }],
        });
        try {
            await Promise.race([editAwaiter, timeout(ms("10 minutes"), `post-edit analysis (file ${i + 1})`)]);
        } catch (err) {
            console.log(`Warning: ${err}`);
        } finally {
            disposeEditAwaiter();
        }
    }

    const memPostEdit = await readProcessRssKB(pid);
    if (memPostEdit === null) return;
    console.log(`Memory after edit+re-analysis: ${memPostEdit} KB`);
    console.log(`MAAT_LS_MEM_POST_EDIT_KB=${memPostEdit}`);
}

/**
 * Takes a memory snapshot right after analysis completes and logs it
 * in the MAAT_* format so the analysis pipeline can extract it.
 */
async function checkMemoryGrowth(pid: number): Promise<void> {
    const memPost = await readProcessRssKB(pid);
    if (memPost === null) {
        return;
    }

    console.log(SEPARATOR);
    console.log(`Memory after analysis: ${memPost} KB`);
    console.log(`MAAT_LS_MEM_POST_ANALYSIS_KB=${memPost}`);
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
 * and returns a promise that resolves when CairoLS becomes truly idle,
 * along with a dispose function to clean up the notification listener.
 */
function startAnalysisAwaiter(connection: MessageConnection): { promise: Promise<void>; dispose: () => void } {
    const defer = Promise.withResolvers<void>();
    let analysisTimer: NodeJS.Timeout | null = null;

    const listener = connection.onNotification(ServerStatus, ({ event }) => {
        // CairoLS notifies about analysis events:
        // - Starting analysis: event = 'AnalysisStarted'
        // - Finishing analysis: event = 'AnalysisFinished'
        //
        // LS tends to spuriously go from busy to idle to busy state again in,
        // so we debounce the event = 'AnalysisFinished' state for some small chunk of time
        // before considering the analysis truly complete.

        let finished = event == 'AnalysisFinished';

        if (analysisTimer) {
            clearTimeout(analysisTimer);
            analysisTimer = null;
        }

        if (finished) {
            analysisTimer = setTimeout(() => {
                console.log("Analysis completed, server is idle.");
                defer.resolve();
            }, ms("3 seconds")).unref();
        }
    });

    const dispose = () => {
        if (analysisTimer) {
            clearTimeout(analysisTimer);
            analysisTimer = null;
        }
        listener.dispose();
    };

    return { promise: defer.promise, dispose };
}

/**
 * Returns a Promise that rejects after a specified timeout period with an error indicating the operation timed out.
 */
function timeout(ms: number, operation: string = "operation"): Promise<void> {
    return new Promise((_, reject) =>
        setTimeout(() => reject(new Error(`${operation} timed out`)), ms).unref(),
    );
}

class DiagnosticsCollector {
    private constructor(
        private readonly store: Map<DocumentUri, PublishDiagnosticsParams>,
        private readonly notificationListener: Disposable,
    ) {}

    public static start(connection: MessageConnection): DiagnosticsCollector {
        const store = new Map<DocumentUri, PublishDiagnosticsParams>();
        const notificationListener = connection.onNotification(
            PublishDiagnosticsNotification.method,
            (incoming: PublishDiagnosticsParams) => {
                const current = store.get(incoming.uri);
                // Store incoming diagnostics only if...
                if (
                    // we didn't store anything yet, or...
                    current == null ||
                    // diagnostics are unversioned, or...
                    current.version == null ||
                    incoming.version == null ||
                    // incoming diagnostics' version is higher than stored ones'.
                    current.version < incoming.version
                ) {
                    store.set(incoming.uri, incoming);
                }
            },
        );
        return new DiagnosticsCollector(store, notificationListener);
    }

    public stop(): PublishDiagnosticsParams[] {
        // Stop listening to new diagnostics.
        this.notificationListener.dispose();

        // Consume all diagnostics that have been accumulated.
        const entries: PublishDiagnosticsParams[] = [];
        for (const params of this.store.values()) {
            if (params.diagnostics.length > 0) {
                entries.push(params);
            }
        }
        this.store.clear();

        // Try to stabilise the output.
        entries.sort((a, b) => a.uri.localeCompare(b.uri));

        return entries;
    }
}

/**
 * Pretty prints diagnostics via `console.log`.
 */
function showDiagnostics(diags: PublishDiagnosticsParams[]): void {
    let totals = {
        [DiagnosticSeverity.Error]: 0,
        [DiagnosticSeverity.Warning]: 0,
        [DiagnosticSeverity.Information]: 0,
        [DiagnosticSeverity.Hint]: 0,
    };

    console.log(SEPARATOR);

    for (const { uri, diagnostics } of diags) {
        console.log(`${uri} (${diagnostics.length})`);
        for (const diag of diagnostics) {
            const severityIcon = {
                [DiagnosticSeverity.Error]: "(E)",
                [DiagnosticSeverity.Warning]: "(W)",
                [DiagnosticSeverity.Information]: "(i)",
                [DiagnosticSeverity.Hint]: "(h)",
                null: "( )",
            }[diag.severity ?? "null"];

            if (diag.severity != null) {
                totals[diag.severity]++;
            }

            console.log(
                indent(
                    putAfterFirstLine(
                        indent(`${severityIcon} ${diag.message}`),
                        ` [Ln ${diag.range.start.line}, Col ${diag.range.start.character}]`,
                    ),
                    true,
                ),
            );
        }
    }

    console.log(
        `total: ${totals[DiagnosticSeverity.Error]} errors, ` +
            `${totals[DiagnosticSeverity.Warning]} warnings, ` +
            `${totals[DiagnosticSeverity.Information]} infos, ` +
            `${totals[DiagnosticSeverity.Hint]} hints`,
    );
}

/**
 * Converts a file URL into a file system path.
 */
function url2path(fileUrl: DocumentUri): string {
    return new URL(fileUrl).pathname;
}

/**
 * Converts a file system path to a file URL.
 *
 * Path is resolved before constructing the URL.
 */
function path2url(filePath: string): DocumentUri {
    return new URL(path.resolve(filePath), "file://").href;
}

/**
 * Indents each line of text.
 */
function indent(text: string, first: boolean = false): string {
    const INDENT = "  ";
    text = text.replace(/\n(?=.+)/g, `\n${INDENT}`);
    if (first) {
        text = INDENT + text;
    }
    return text;
}

/**
 * Inserts a specified string immediately after the first line of the provided text.
 */
function putAfterFirstLine(text: string, after: string): string {
    return text.replace(/^(.*?)(\n|$)/, `$1${after}$2`);
}
