import fs from "fs";

export function loadFile(path: string): string {
  if (!fs.existsSync(path)) {
    throw new Error(`File not found: ${path}`);
  }
  return fs.readFileSync(path, "utf-8");
}
