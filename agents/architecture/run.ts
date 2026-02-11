import fs from "fs";
import path from "path";
import { getModel } from "../../lib/geminiClient";
import { loadFile } from "../../lib/loadFile";
import { normalizeArchitecture } from "../../lib/normalizeArchitecture";
import { ArchitectureSchema } from "./schema";

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

  const cleaned = rawText
    .replace(/```json/g, "")
    .replace(/```/g, "")
    .trim();

  let parsed;
  try {
    parsed = JSON.parse(cleaned);
  } catch {
    console.error("Raw output:\n", rawText);
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
