import { useState } from "react";
import { convertFileSrc } from "@tauri-apps/api/core";
import { generateImage } from "./api/client";

export default function App() {
  const [prompt, setPrompt] = useState("");
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "generating" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate() {
    if (!prompt.trim()) return;
    setStatus("generating");
    setError(null);

    try {
      const result = await generateImage({ prompt });
      setImageSrc(convertFileSrc(result.file_path));
      setStatus("idle");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setStatus("error");
    }
  }

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem", maxWidth: 640, margin: "0 auto" }}>
      <h1>Codex Creatures</h1>
      <p>Describe the creature asset you want to generate.</p>

      <textarea
        value={prompt}
        onChange={(event) => setPrompt(event.target.value)}
        rows={4}
        style={{ width: "100%" }}
        placeholder="A bioluminescent forest sprite, concept art, clean background"
      />

      <div style={{ marginTop: "1rem" }}>
        <button onClick={handleGenerate} disabled={status === "generating"}>
          {status === "generating" ? "Generating..." : "Generate"}
        </button>
      </div>

      {error && <p style={{ color: "crimson" }}>{error}</p>}

      {imageSrc && (
        <img src={imageSrc} alt={prompt} style={{ marginTop: "1.5rem", maxWidth: "100%" }} />
      )}
    </main>
  );
}
