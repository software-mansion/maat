import { execSync } from "child_process";
import { createReadStream } from "fs";
import { cp, mkdir, readFile, rm, stat } from "fs/promises";
import path from "path";
import type { Plugin } from "vite";

const generatedDir = ".maat-generated";
const viewModelVirtualId = "virtual:maat-view-model";
const viewModelResolvedId = `\0${viewModelVirtualId}`;

const viewModelPath = path.join(generatedDir, "vm.json");
const assetsPath = path.join(generatedDir, "assets");

export function maatPlugin(): Plugin {
  let isProduction = false;
  let outDir = "";

  return {
    name: "maat-plugin",

    configResolved(config) {
      isProduction = config.command === "build";
      outDir = config.build.outDir;
    },

    async buildStart() {
      await rm(generatedDir, { recursive: true, force: true });
      await mkdir(generatedDir, { recursive: true });

      console.log("Generating maat assets...");
      execSync(
        `../maat export-web-assets --view-model ${viewModelPath} --assets ${assetsPath} ../reports/*`,
        { stdio: "inherit", cwd: process.cwd() },
      );
      console.log("Ma'at assets generated successfully!");
    },

    resolveId(source) {
      if (source === viewModelVirtualId) {
        return viewModelResolvedId;
      }
    },

    async load(id) {
      if (id === viewModelResolvedId) {
        const viewModelContent = await readFile(viewModelPath, "utf-8");
        const sanitized = JSON.stringify(JSON.parse(viewModelContent));
        return `export default ${sanitized};`;
      }
    },

    configureServer(server) {
      // In dev mode, serve assets from the generated directory.
      server.middlewares.use(async (req, res, next) => {
        if (req.url?.startsWith("/")) {
          const assetPath = path.join(assetsPath, req.url.slice(1));
          if (await isFile(assetPath)) {
            res.setHeader("Content-Type", getMimeType(assetPath));
            const readStream = createReadStream(assetPath);
            readStream.pipe(res);
            return;
          }
        }
        next();
      });
    },

    async generateBundle() {
      if (isProduction) {
        console.log("Copying Ma'at assets to build directory...");
        await cp(assetsPath, outDir, {
          errorOnExist: true,
          preserveTimestamps: true,
          recursive: true,
        });
      }
    },
  };
}

async function isFile(path: string): Promise<boolean> {
  try {
    return (await stat(path)).isFile();
  } catch {
    return false;
  }
}

function getMimeType(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  const mimeTypes: Record<string, string> = {
    ".txt": "text/plain",
    ".json": "application/json",
    ".csv": "text/csv",
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
  };
  return mimeTypes[ext] || "application/octet-stream";
}
