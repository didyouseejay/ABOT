/**
 * Serves and ships the `abot-dashboard` v1 bundle (docs/DASHBOARD_DATA_CONTRACT.md).
 *
 * dev:   GET <urlPrefix><name> reads <bundleDir>/<name> on every request with a single readFile call,
 *        which opens and closes the file. The bundle directory is never watched (it is outside the
 *        Vite root and is also listed in server.watch.ignored) and no handle stays open, so
 *        `abot export-dashboard` can rename v1/ on Windows while the dev server runs (§10.1).
 * build: copies manifest.json and exactly the files it lists into <outDir>/data/v1/, checking each
 *        file's size and SHA-256 against the manifest while copying. The source bundle is only read;
 *        temporary or backup directories of the exporter are never copied.
 */
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import type { IncomingMessage, ServerResponse } from "node:http";
import path from "node:path";
import type { Plugin, ResolvedConfig } from "vite";

/** A bundle file name: no directory part, so nothing outside the bundle can be requested. */
const FILE_NAME = /^[A-Za-z0-9][A-Za-z0-9._-]*\.(json|geojson)$/;

export interface BundlePluginOptions {
  /** Absolute path of data/processed/dashboard/v1. */
  bundleDir: string;
  /** URL path the browser fetches the bundle from; must end with "/". */
  urlPrefix?: string;
}

export function isBundleFileName(name: string): boolean {
  return FILE_NAME.test(name) && !name.includes("..");
}

/** The file's bytes, or null when the name is not a bundle file name or the file does not exist. */
export async function readBundleFile(bundleDir: string, name: string): Promise<Buffer | null> {
  if (!isBundleFileName(name)) return null;
  try {
    return await readFile(path.join(bundleDir, name));
  } catch (e) {
    const code = (e as NodeJS.ErrnoException).code;
    if (code === "ENOENT" || code === "ENOTDIR" || code === "EISDIR") return null;
    throw e;
  }
}

type Next = (err?: unknown) => void;

export function bundleMiddleware(bundleDir: string, urlPrefix: string) {
  return (req: IncomingMessage, res: ServerResponse, next: Next): void => {
    const url = (req.url ?? "").split("?")[0] ?? "";
    if (!url.startsWith(urlPrefix) || (req.method !== "GET" && req.method !== "HEAD")) {
      next();
      return;
    }
    let name: string;
    try {
      name = decodeURIComponent(url.slice(urlPrefix.length));
    } catch {
      name = "";
    }
    readBundleFile(bundleDir, name).then(
      (body) => {
        res.setHeader("Cache-Control", "no-store");
        if (body === null) {
          res.statusCode = 404;
          res.setHeader("Content-Type", "text/plain; charset=utf-8");
          res.end(`not in the dashboard bundle: ${name}`);
          return;
        }
        res.statusCode = 200;
        res.setHeader("Content-Type", name.endsWith(".geojson") ? "application/geo+json" : "application/json");
        res.setHeader("Content-Length", String(body.length));
        res.end(req.method === "HEAD" ? undefined : body);
      },
      (err: unknown) => next(err),
    );
  };
}

interface ManifestFiles {
  files: { name: string; bytes: number; sha256: string }[];
}

export interface CopyResult {
  files: string[];
  bytes: number;
}

/**
 * Copies the bundle listed by its manifest. Returns null when there is no manifest (no bundle);
 * throws, after writing nothing further, when a listed file is missing or differs from the manifest.
 */
export async function copyBundle(bundleDir: string, targetDir: string): Promise<CopyResult | null> {
  const manifestBytes = await readBundleFile(bundleDir, "manifest.json");
  if (manifestBytes === null) return null;
  const manifest = JSON.parse(manifestBytes.toString("utf-8")) as ManifestFiles;
  const out: [string, Buffer][] = [["manifest.json", manifestBytes]];
  for (const f of manifest.files) {
    const body = await readBundleFile(bundleDir, f.name);
    if (body === null) throw new Error(`bundle file listed in manifest.json is missing: ${f.name}`);
    const hash = createHash("sha256").update(body).digest("hex");
    if (body.length !== f.bytes || hash !== f.sha256) {
      throw new Error(`bundle file differs from manifest.json (size or SHA-256): ${f.name}`);
    }
    out.push([f.name, body]);
  }
  await mkdir(targetDir, { recursive: true });
  for (const [name, body] of out) await writeFile(path.join(targetDir, name), body);
  return { files: out.map(([n]) => n), bytes: out.reduce((s, [, b]) => s + b.length, 0) };
}

export function abotBundle(options: BundlePluginOptions): Plugin {
  const prefix = options.urlPrefix ?? "/data/v1/";
  const bundleDir = path.resolve(options.bundleDir);
  let config: ResolvedConfig | undefined;
  return {
    name: "abot-dashboard-bundle",
    config: () => ({
      // The bundle is outside the Vite root and therefore not watched; ignore it explicitly as well.
      server: { watch: { ignored: [`${path.dirname(bundleDir).replaceAll("\\", "/")}/**`] } },
    }),
    configResolved(resolved) {
      config = resolved;
    },
    configureServer(server) {
      server.middlewares.use(bundleMiddleware(bundleDir, prefix));
    },
    async closeBundle() {
      if (config === undefined || config.command !== "build") return;
      const target = path.resolve(config.root, config.build.outDir, prefix.replace(/^\/+/, ""));
      const result = await copyBundle(bundleDir, target);
      if (result === null) {
        config.logger.warn(
          `\n[abot-dashboard-bundle] no bundle at ${bundleDir}: the build has no data. ` +
            "Run `abot export-dashboard` and build again.",
        );
        return;
      }
      config.logger.info(
        `[abot-dashboard-bundle] copied ${result.files.length} bundle files (${result.bytes.toLocaleString("en")} bytes, ` +
          `sizes and SHA-256 checked) to ${path.relative(config.root, target)}`,
      );
    },
  };
}
