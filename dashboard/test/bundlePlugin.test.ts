import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import type { IncomingMessage, ServerResponse } from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { bundleMiddleware, copyBundle, isBundleFileName } from "../vite/bundlePlugin.ts";

let root: string;
let v1: string;

async function writeBundle(dir: string) {
  await mkdir(dir, { recursive: true });
  const city = Buffer.from('{"dataset":"city"}\n');
  await writeFile(path.join(dir, "city.json"), city);
  const files = [{ name: "city.json", bytes: city.length, sha256: createHash("sha256").update(city).digest("hex") }];
  await writeFile(path.join(dir, "manifest.json"), JSON.stringify({ files }));
}

function request(mw: ReturnType<typeof bundleMiddleware>, url: string, method = "GET") {
  return new Promise<{ status: number; body: string; headers: Record<string, string>; next: boolean }>((resolve) => {
    const headers: Record<string, string> = {};
    const res = {
      statusCode: 200,
      setHeader: (k: string, v: string) => (headers[k.toLowerCase()] = v),
      end: (b?: Buffer | string) => resolve({ status: res.statusCode, body: b === undefined ? "" : b.toString(), headers, next: false }),
    };
    mw({ url, method } as IncomingMessage, res as unknown as ServerResponse, () => resolve({ status: 0, body: "", headers, next: true }));
  });
}

beforeEach(async () => {
  root = await mkdtemp(path.join(tmpdir(), "abot-dash-"));
  v1 = path.join(root, "v1");
  await writeBundle(v1);
});
afterEach(async () => {
  await rm(root, { recursive: true, force: true });
});

describe("dev middleware", () => {
  it("serves bundle files read on request, uncached", async () => {
    const r = await request(bundleMiddleware(v1, "/data/v1/"), "/data/v1/city.json?t=1");
    expect(r).toMatchObject({ status: 200, body: '{"dataset":"city"}\n' });
    expect(r.headers["cache-control"]).toBe("no-store");
    expect(r.headers["content-type"]).toBe("application/json");
  });
  it("answers 404 for a missing file and never serves outside the bundle", async () => {
    const mw = bundleMiddleware(v1, "/data/v1/");
    expect((await request(mw, "/data/v1/missing.json")).status).toBe(404);
    expect((await request(mw, "/data/v1/..%2F..%2Fsecret.json")).status).toBe(404);
    expect((await request(mw, "/data/v1/sub/city.json")).status).toBe(404);
    expect((await request(mw, "/data/v1/.v1.tmp-0123456789ab")).status).toBe(404);
    expect(isBundleFileName("cells-001.geojson")).toBe(true);
    expect(isBundleFileName("../x.json")).toBe(false);
  });
  it("passes other URLs and methods to the next handler", async () => {
    const mw = bundleMiddleware(v1, "/data/v1/");
    expect((await request(mw, "/src/main.tsx")).next).toBe(true);
    expect((await request(mw, "/data/v1/city.json", "POST")).next).toBe(true);
  });
  it("holds no handle on the bundle: the exporter can rename v1/ right after serving (Windows)", async () => {
    const mw = bundleMiddleware(v1, "/data/v1/");
    await Promise.all([request(mw, "/data/v1/city.json"), request(mw, "/data/v1/manifest.json")]);
    await rename(v1, path.join(root, ".v1.old-0123456789ab"));
    await writeBundle(v1);
    await rename(path.join(root, ".v1.old-0123456789ab"), path.join(root, "old"));
    expect((await request(mw, "/data/v1/city.json")).status).toBe(200);
  });
});

describe("build copy", () => {
  it("copies exactly the manifest and the files it lists, after checking them", async () => {
    await mkdir(path.join(root, ".v1.tmp-0123456789ab"));
    await writeFile(path.join(v1, "stray.json"), "{}");
    const out = path.join(root, "dist", "data", "v1");
    const before = await readFile(path.join(v1, "city.json"));
    const r = await copyBundle(v1, out);
    expect(r?.files).toEqual(["manifest.json", "city.json"]);
    expect((await readdir(out)).sort()).toEqual(["city.json", "manifest.json"]);
    expect(await readFile(path.join(out, "city.json"))).toEqual(before);
    expect(await readFile(path.join(v1, "city.json"))).toEqual(before); // source untouched
  });
  it("refuses a bundle file that differs from its manifest", async () => {
    await writeFile(path.join(v1, "city.json"), '{"dataset":"edited"}\n');
    await expect(copyBundle(v1, path.join(root, "dist"))).rejects.toThrow(/differs from manifest/);
  });
  it("reports no bundle when there is no manifest", async () => {
    expect(await copyBundle(path.join(root, "nothing"), path.join(root, "dist"))).toBeNull();
  });
});
