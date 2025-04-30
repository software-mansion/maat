import * as childProcess from "child_process";
import {
    createMessageConnection,
    type MessageConnection,
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

const ls = spawnCairoLS();
try {
    const connection = await acquireResource(ls);

    const rootUri = `file://${process.env.PWD}`;
    await initialize(connection, rootUri, baseCapabilities());

    try {
        await viewAnalysedCrates(connection);
    } finally {
        await terminate(connection);
    }
} finally {
    await ls.return();
}

async function viewAnalysedCrates(connection: MessageConnection) {
    const SEPARATOR = "==============================";
    const result = await connection.sendRequest("cairo/viewAnalyzedCrates");
    console.log(SEPARATOR);
    console.log(result);
    console.log(SEPARATOR);
}

async function* spawnCairoLS(): AsyncGenerator<MessageConnection, void, void> {
    const serverProcess = childProcess.spawn("scarb", ["cairo-language-server"], {
        stdio: ["pipe", "pipe", "inherit"],
    });

    serverProcess.on("close", (code) => {
        console.log(`CairoLS process exited with code: ${code}`);
        process.exit(code || 0);
    });

    try {
        const connection = createMessageConnection(
            new StreamMessageReader(serverProcess.stdout),
            new StreamMessageWriter(serverProcess.stdin),
        );

        try {
            connection.listen();
            yield connection;
        } finally {
            connection.dispose();
        }
    } finally {
        serverProcess.kill();
    }
}

async function acquireResource<T>(resource: AsyncGenerator<T, unknown, void>): Promise<T> {
    const result = await resource.next();
    if (result.done === true) {
        throw new Error("Resource exhausted");
    }
    return result.value;
}

/**
 * Produces minimal client capabilities provided by the mock language client.
 *
 * Tests will most often need to extend these with test-specific additions.
 */
export function baseCapabilities(): ClientCapabilities {
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
export async function initialize(
    connection: MessageConnection,
    rootUri: string,
    capabilities: ClientCapabilities,
): Promise<void> {
    const workspaceFolders: WorkspaceFolder[] = [
        {
            uri: rootUri,
            name: new URL(rootUri).pathname.split("/").filter(Boolean).pop() || "maat",
        },
    ];

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
export async function terminate(connection: MessageConnection): Promise<void> {
    // Send `shutdown` request
    await connection.sendRequest(ShutdownRequest.method);

    // Send `exit` notification
    await connection.sendNotification(ExitNotification.method);
}
