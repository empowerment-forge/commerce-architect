// @vitest-environment node

import { createServer as createHttpServer } from "node:http";
import type { AddressInfo } from "node:net";
import { fileURLToPath } from "node:url";

import { createServer as createViteServer } from "vite";

const configFile = fileURLToPath(new URL("./vite.config.ts", import.meta.url));

describe("Vite Django proxies", () => {
  it("forwards API, admin, and static paths to the configured backend", async () => {
    const requestedPaths: string[] = [];
    const backend = createHttpServer((request, response) => {
      requestedPaths.push(request.url ?? "");
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(JSON.stringify([{ id: 1, name: "Test product" }]));
    });

    await new Promise<void>((resolve) => backend.listen(0, "127.0.0.1", resolve));
    const backendAddress = backend.address() as AddressInfo;
    const previousProxyTarget = process.env.VITE_API_PROXY_TARGET;
    process.env.VITE_API_PROXY_TARGET = `http://127.0.0.1:${backendAddress.port}`;

    const vite = await createViteServer({
      configFile,
      appType: "custom",
      optimizeDeps: { noDiscovery: true },
      server: { host: "127.0.0.1", port: 0 },
    });

    try {
      await vite.listen();
      const viteAddress = vite.httpServer?.address() as AddressInfo;
      for (const path of ["/api/products/", "/admin/", "/static/admin/css/base.css"]) {
        const response = await fetch(`http://127.0.0.1:${viteAddress.port}${path}`);
        expect(response.status).toBe(200);
        expect(response.headers.get("content-type")).toContain("application/json");
      }
      expect(requestedPaths).toEqual([
        "/api/products/",
        "/admin/",
        "/static/admin/css/base.css",
      ]);
    } finally {
      await vite.close();
      await new Promise<void>((resolve, reject) => {
        backend.close((error) => (error ? reject(error) : resolve()));
      });

      if (previousProxyTarget === undefined) {
        delete process.env.VITE_API_PROXY_TARGET;
      } else {
        process.env.VITE_API_PROXY_TARGET = previousProxyTarget;
      }
    }
  });
});
