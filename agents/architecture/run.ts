import fs from "fs";
import path from "path";
import { getModel } from "../../lib/geminiClient";
import { loadFile } from "../../lib/loadFile";
import { normalizeArchitecture } from "../../lib/normalizeArchitecture";
import { ArchitectureSchema } from "./schema";

function extractFirstJsonBlock(text: string): string | null {
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fenced && fenced[1]) {
    return fenced[1].trim();
  }

  const startCandidates = [text.indexOf("{"), text.indexOf("[")]
    .filter((idx) => idx >= 0)
    .sort((a, b) => a - b);

  if (startCandidates.length === 0) {
    return null;
  }

  const start = startCandidates[0];
  const openChar = text[start];
  const closeChar = openChar === "{" ? "}" : "]";

  let depth = 0;
  let inString = false;
  let escaped = false;

  for (let i = start; i < text.length; i++) {
    const ch = text[i];

    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (ch === "\\") {
        escaped = true;
      } else if (ch === "\"") {
        inString = false;
      }
      continue;
    }

    if (ch === "\"") {
      inString = true;
      continue;
    }

    if (ch === openChar) {
      depth += 1;
      continue;
    }

    if (ch === closeChar) {
      depth -= 1;
      if (depth === 0) {
        return text.slice(start, i + 1).trim();
      }
    }
  }

  return null;
}

async function run() {
  const inputPath = process.argv[2];

  if (!inputPath) {
    throw new Error("Usage: npm run architecture <input.json>");
  }

  const prompt = loadFile("agents/architecture/prompt.md");
  const inputJson = loadFile(inputPath);

  const model = getModel();

  // ✅ Single source of truth for model output
  const rawText = await model.generate(
    `${prompt}\n\nINPUT JSON:\n${inputJson}`
  );

  if (!rawText || typeof rawText !== "string") {
    throw new Error("Model returned no text output");
  }

  const cleaned = extractFirstJsonBlock(rawText) ?? rawText.trim();

  let parsed;
  try {
    parsed = JSON.parse(cleaned);
  } catch {
    console.error("Raw output:\n", rawText);
    console.error("Extracted JSON candidate:\n", cleaned);
    throw new Error("Model did not return valid JSON");
  }

  console.log(
    "RAW MODEL OUTPUT (parsed JSON):\n",
    JSON.stringify(parsed, null, 2)
  );

  const normalized = normalizeArchitecture(parsed);
  const validated = ArchitectureSchema.parse(normalized);

  const outputFile = path.join(
    "outputs",
    `architecture_${Date.now()}.json`
  );

  fs.writeFileSync(
    outputFile,
    JSON.stringify(validated, null, 2)
  );

  console.log(`✅ Architecture written to ${outputFile}`);
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
