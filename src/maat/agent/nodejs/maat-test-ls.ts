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

/** Reads a duration from an env var (any `ms`-parseable string), falling back to `dflt`. */
function envMs(name: string, dflt: ms.StringValue): number {
    const value = process.env[name];
    return value ? ms(value as ms.StringValue) : ms(dflt);
}

// Per-request timeouts. Every LSP request is raced against these so a wedged CairoLS can never
// make an `await sendRequest(...)` hang forever (the previous behaviour, which let the whole
// step hang until CI's 6h ceiling). Overridable via env for tuning and tests.
const INITIALIZE_TIMEOUT = envMs("MAAT_LS_INITIALIZE_TIMEOUT", "2 minutes");
const REQUEST_TIMEOUT = envMs("MAAT_LS_REQUEST_TIMEOUT", "60 seconds");
const SHUTDOWN_TIMEOUT = envMs("MAAT_LS_SHUTDOWN_TIMEOUT", "30 seconds");
// Independent hard cap on the whole LS run. Must exceed the 20-minute analysis wait plus the
// request timeouts above so the normal path always finishes first; this only fires if the LS
// wedges so badly that even shutdown/close never settle.
const HARD_TIMEOUT = envMs("MAAT_LS_HARD_TIMEOUT", "24 minutes");

const ViewAnalyzedCrates = new RequestType0<{}, {}>("cairo/viewAnalyzedCrates");

interface ServerStatusParams {
    event: "AnalysisStarted" | "AnalysisFinished" | "MacrosBuildingStarted" | "MacrosBuildingFinished" | "DiagnosticsDbFreed";
}

const ServerStatus = new NotificationType<ServerStatusParams>("cairo/serverStatus");

class AnalysisEventLogger {
    lastFinishedMem: Promise<number | null> = Promise.resolve(null);

    constructor(private readonly pid: number) {}

    onEvent(event: ServerStatusParams["event"]): void {
        const time = new Date().toISOString().slice(11, 23); // HH:MM:SS.mmm
        const memStatsPromise = readMemStatsKB(this.pid);
        const memPromise = memStatsPromise.then((stats) => stats?.privateKb ?? null);
        if (event === "AnalysisFinished") {
            this.lastFinishedMem = memPromise;
        }
        memStatsPromise.then((stats) => {
            const mem = stats != null ? formatMemStats(stats) : "—";
            console.log(`${time}  ${event}  ${mem}`);
        });
    }
}

withCairoLS(async (connection, pid) => {
    const rootUri = `file://${process.env.PWD}`;
    const eventLogger = new AnalysisEventLogger(pid);
    await initialize(connection, rootUri, baseCapabilities());

    try {
        const { promise: analysisAwaiter, dispose: disposeAwaiter } = startAnalysisAwaiter(
            connection, ms("3 seconds"),
            (event) => eventLogger.onEvent(event),
            () => eventLogger.lastFinishedMem,
        );
        const diagnosticsCollector = DiagnosticsCollector.start(connection);

        const allLibCairoFiles = await findAllEntryFiles();
        // Shortest path ≈ root package; its changes cascade into dependents.
        const entryFile = allLibCairoFiles.sort((a, b) => a.length - b.length)[0] ?? null;

        if (!entryFile) {
            // Packages with no Cairo sources (e.g. pure proc-macro crates like `alexandria_macros`)
            // never open a document, so the LS never starts analysis and `AnalysisFinished` can
            // never fire. Waiting on it would pointlessly burn the entire analysis timeout and then
            // report a bogus LS failure, so finish cleanly instead — there is nothing to analyze.
            console.log(SEPARATOR);
            console.log("No Cairo entry file (lib.cairo) found; nothing to analyze, skipping LS analysis.");
            disposeAwaiter();
            diagnosticsCollector.stop();
            return;
        }

        console.log(`Opening ${path2url(entryFile)}`);
        await openFile(path2url(entryFile), connection);

        // Wait for project analysis to finish.
        // This is only a safety net against a genuinely hung LS. The cap has to comfortably
        // exceed the time the heaviest projects need (e.g. OpenZeppelin/cairo-contracts, whose
        // proc-macro build + analysis alone runs well past 5 minutes), otherwise we'd kill the
        // server mid-analysis and report a bogus LS failure.
        console.log(SEPARATOR);
        let analysisMemKb: number | null = null;
        try {
            analysisMemKb = await Promise.race([analysisAwaiter, timeout(ms("20 minutes"), "analysis")]) ?? null;
        } finally {
            disposeAwaiter();
        }
        const diags = diagnosticsCollector.stop();

        await checkMemoryGrowth(pid, analysisMemKb);

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
 * Opens a file in the LS.
 */
async function openFile(url: string, connection: MessageConnection): Promise<void> {
    const filePath = url2path(url);
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
    const result = await withTimeout("viewAnalyzedCrates", REQUEST_TIMEOUT, () =>
        connection.sendRequest(ViewAnalyzedCrates),
    );
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

    // Hard wall-clock watchdog, armed here and NOT dependent on `callback` settling. Even with
    // per-request timeouts, a badly deadlocked LS could leave `connection.dispose()` / process
    // 'close' hanging; this guarantees the harness process still exits (non-zero) instead of
    // riding to CI's 6h ceiling.
    const hardKill = setTimeout(() => {
        console.error(
            `${SEPARATOR}\nMAAT_LS_HARD_TIMEOUT after ${ms(HARD_TIMEOUT)}; SIGKILLing CairoLS and exiting.`,
        );
        try {
            serverProcess.kill("SIGKILL");
        } catch {}
        process.exit(124);
    }, HARD_TIMEOUT);

    let closed = false;
    serverProcess.on("close", (code, signal) => {
        closed = true;
        console.log(SEPARATOR);
        console.log(`CairoLS process exited with code: ${code ?? signal}`);
        if (code != null && code !== 0) {
            process.exitCode = code;
        }
        exitPromise.resolve();
    });

    let callbackError: unknown = undefined;
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
    } catch (err) {
        // Capture and rethrow after we have ensured the server is dead, so a failing callback
        // still tears the LS down.
        callbackError = err;
    }

    // Escalate: SIGTERM, then SIGKILL if it has not actually exited. Guard on `closed` (real
    // exit), not `serverProcess.killed` (merely "a signal was sent") — a wedged LS may ignore
    // SIGTERM. The live ChildProcess handle keeps the event loop alive so these timers fire.
    setTimeout(() => {
        if (!closed) serverProcess.kill("SIGTERM");
    }, ms("3 seconds")).unref();
    setTimeout(() => {
        if (!closed) serverProcess.kill("SIGKILL");
    }, ms("6 seconds")).unref();

    try {
        await exitPromise.promise;
    } finally {
        clearTimeout(hardKill);
    }

    if (callbackError !== undefined) {
        throw callbackError;
    }
}

function formatMemKB(kb: number): string {
    if (kb >= 1024 * 1024) return `${(kb / 1024 / 1024).toFixed(2)} GB`;
    if (kb >= 1024) return `${Math.round(kb / 1024)} MB`;
    return `${kb} KB`;
}

interface MemStatsKB {
    privateKb: number;
    rssKb: number;
}

function formatMemStats(stats: MemStatsKB): string {
    return `${formatMemKB(stats.privateKb)} private (RSS ${formatMemKB(stats.rssKb)})`;
}

/** Reads Private_Clean + Private_Dirty (activity-monitor-style) and RSS from smaps_rollup. */
async function readMemStatsKB(pid: number): Promise<MemStatsKB | null> {
    try {
        const smaps = await fs.readFile(`/proc/${pid}/smaps_rollup`, "utf-8");
        const rssMatch = smaps.match(/^Rss:\s+(\d+)\s+kB/m);
        const privateCleanMatch = smaps.match(/^Private_Clean:\s+(\d+)\s+kB/m);
        const privateDirtyMatch = smaps.match(/^Private_Dirty:\s+(\d+)\s+kB/m);
        if (!rssMatch || !privateCleanMatch || !privateDirtyMatch) return null;
        return {
            privateKb: parseInt(privateCleanMatch[1], 10) + parseInt(privateDirtyMatch[1], 10),
            rssKb: parseInt(rssMatch[1], 10),
        };
    } catch {
        return null;
    }
}

/** Reads VmHWM (peak RSS) from /proc/<pid>/status. */
async function readPeakMemKB(pid: number): Promise<number | null> {
    try {
        const status = await fs.readFile(`/proc/${pid}/status`, "utf-8");
        const match = status.match(/^VmHWM:\s+(\d+)\s+kB/m);
        if (!match) return null;
        return parseInt(match[1], 10);
    } catch {
        return null;
    }
}

/** Logs private memory at last AnalysisFinished and peak RSS (VmHWM). */
async function checkMemoryGrowth(pid: number, mem: number | null): Promise<void> {
    console.log(SEPARATOR);
    if (mem !== null) {
        console.log(`Private memory at AnalysisFinished: ${mem} KB`);
        console.log(`MAAT_LS_MEM_POST_ANALYSIS_KB=${mem}`);
    }
    const peak = await readPeakMemKB(pid);
    if (peak !== null) {
        console.log(`MAAT_LS_MEM_POST_ANALYSIS_PEAK_KB=${peak}`);
    }
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
    await withTimeout("initialize", INITIALIZE_TIMEOUT, () =>
        connection.sendRequest(InitializeRequest.method, params),
    );

    // Send `initialized` notification.
    await connection.sendNotification(InitializedNotification.method, {});
}

/**
 * Performs the `shutdown`/`exit` handshake with the server.
 * @param connection An active MessageConnection to the server
 */
async function terminate(connection: MessageConnection): Promise<void> {
    // Send `shutdown` request. If the LS is wedged and never answers, don't block forever here —
    // log and fall through to `exit`; the caller's watchdog will force-kill the process.
    try {
        await withTimeout("shutdown", SHUTDOWN_TIMEOUT, () =>
            connection.sendRequest(ShutdownRequest.method),
        );
    } catch (err) {
        console.error(`shutdown request did not complete: ${err}`);
    }

    // Send `exit` notification (best-effort).
    try {
        await connection.sendNotification(ExitNotification.method);
    } catch (err) {
        console.error(`exit notification failed: ${err}`);
    }
}

/**
 * Awaiter for analysis completion: debounces on AnalysisFinished, waiting for
 * `debounceMs` of silence (AnalysisStarted resets the timer), then resolves with
 * the RSS captured at the last AnalysisFinished event.
 */
function startAnalysisAwaiter(
    connection: MessageConnection,
    debounceMs: number = ms("20 seconds"),
    onEvent?: (event: ServerStatusParams["event"]) => void,
    getMem?: () => Promise<number | null>,
): { promise: Promise<number | null>; dispose: () => void } {
    const defer = Promise.withResolvers<number | null>();
    let analysisTimer: NodeJS.Timeout | null = null;

    const listener = connection.onNotification(ServerStatus, ({ event }) => {
        onEvent?.(event);

        if (event === "AnalysisStarted" && analysisTimer) {
            clearTimeout(analysisTimer);
            analysisTimer = null;
        }

        if (event === "AnalysisFinished") {
            analysisTimer = setTimeout(async () => {
                analysisTimer = null;
                const time = new Date().toISOString().slice(11, 23);
                console.log(`Analysis stable (AnalysisFinished).  ${time}`);
                const mem = getMem ? await getMem() : null;
                defer.resolve(mem);
            }, debounceMs).unref();
        }
    });

    const dispose = () => {
        if (analysisTimer) { clearTimeout(analysisTimer); analysisTimer = null; }
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

/** Current wall-clock time as `HH:MM:SS.mmm`, for correlating request traces with LS output. */
function nowTs(): string {
    return new Date().toISOString().slice(11, 23);
}

/**
 * Runs an LSP operation with a timeout, tracing when it is issued and when it settles.
 * Rejects (via {@link timeout}) if it does not complete in time — a stuck request means the LS is
 * not answering, so the caller is expected to tear the server down.
 */
async function withTimeout<T>(
    label: string,
    timeoutMs: number,
    op: () => Promise<T>,
): Promise<T> {
    const started = Date.now();
    console.log(`[${nowTs()}] -> ${label}`);
    try {
        const result = (await Promise.race([op(), timeout(timeoutMs, label)])) as T;
        console.log(`[${nowTs()}] <- ${label} (${Date.now() - started}ms)`);
        return result;
    } catch (err) {
        console.error(`[${nowTs()}] !! ${label} did not complete: ${err}`);
        throw err;
    }
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
        // Only diagnostics emitted for Cairo source files reflect the state of the code.
        // Diagnostics on other files (notably `Scarb.toml` manifest diagnostics such as
        // SE0002 `unknown manifest field`) are surfaced by Scarb, are non-fatal and do not
        // fail `scarb build`, so they must not be counted as errors - otherwise we'd report
        // a bogus LS-vs-build mismatch. They are still printed below for visibility.
        const isCairoSource = uri.endsWith(".cairo");

        console.log(`${uri} (${diagnostics.length})`);
        for (const diag of diagnostics) {
            const severityIcon = {
                [DiagnosticSeverity.Error]: "(E)",
                [DiagnosticSeverity.Warning]: "(W)",
                [DiagnosticSeverity.Information]: "(i)",
                [DiagnosticSeverity.Hint]: "(h)",
                null: "( )",
            }[diag.severity ?? "null"];

            if (diag.severity != null && isCairoSource) {
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
