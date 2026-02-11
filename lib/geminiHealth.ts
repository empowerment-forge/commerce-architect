import { GoogleGenAI } from "@google/genai";
import "dotenv/config";

if (!process.env.GEMINI_API_KEY) {
  throw new Error("Missing GEMINI_API_KEY");
}

const ai = new GoogleGenAI({
  apiKey: process.env.GEMINI_API_KEY
});

async function smokeTest() {
  const response = await ai.models.generateContent({
    model: "gemini-3-flash-preview",
    contents: "Respond with the word OK"
  });

  console.log("Gemini response:", response.text);
}

smokeTest().catch(err => {
  console.error("Gemini smoke test failed:");
  console.error(err);
  process.exit(1);
});
